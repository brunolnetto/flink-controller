"""
Job reconciliation logic for Flink Job Controller.

This module handles the core reconciliation loop for streaming and batch jobs,
ensuring the desired state matches the current state in the Flink cluster.
"""

import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, NamedTuple
from enum import Enum
from pydantic import BaseModel, Field

from ..resilience.circuit_breaker import CircuitBreaker, CircuitBreakerError


class JobType(Enum):
    """Types of Flink jobs."""
    STREAMING = "streaming"
    BATCH = "batch"


class JobState(Enum):
    """Job reconciliation states."""
    PENDING = "pending"           # Job not yet deployed
    RUNNING = "running"          # Job is running in Flink
    STOPPED = "stopped"          # Job was stopped gracefully
    FAILED = "failed"            # Job failed or deployment failed
    RECONCILING = "reconciling"  # Currently being reconciled
    UNKNOWN = "unknown"          # Unable to determine state


class ReconciliationAction(Enum):
    """Actions that can be taken during reconciliation."""
    DEPLOY = "deploy"            # Deploy new job
    UPDATE = "update"            # Update existing job (with savepoint)
    STOP = "stop"               # Stop running job
    RESTART = "restart"         # Restart failed job
    NO_ACTION = "no_action"     # No action needed


class JobSpec(BaseModel):
    """Job specification model for reconciliation."""
    
    job_id: str = Field(..., description="Unique job identifier")
    job_type: JobType = Field(..., description="Type of job (streaming/batch)")
    artifact_path: str = Field(..., description="Path to job artifact")
    artifact_signature: Optional[str] = Field(None, description="Artifact signature for verification")
    
    # Deployment configuration
    parallelism: int = Field(default=1, description="Job parallelism")
    checkpoint_interval: Optional[int] = Field(None, description="Checkpoint interval in ms")
    savepoint_path: Optional[str] = Field(None, description="Savepoint path")
    restart_strategy: str = Field(default="fixed-delay", description="Restart strategy")
    max_restart_attempts: int = Field(default=3, description="Max restart attempts")
    
    # Resource configuration
    memory: str = Field(default="1g", description="Memory allocation")
    cpu_cores: int = Field(default=1, description="CPU cores")
    
    # Streaming-specific configuration
    savepoint_trigger_interval: Optional[int] = Field(None, description="Savepoint trigger interval")
    checkpoint_timeout: Optional[int] = Field(None, description="Checkpoint timeout")
    
    def spec_hash(self) -> str:
        """Calculate hash of spec for change detection."""
        import hashlib
        spec_str = f"{self.job_id}:{self.artifact_path}:{self.parallelism}:{self.checkpoint_interval}"
        return hashlib.sha256(spec_str.encode()).hexdigest()


class JobStatus(BaseModel):
    """Current job status from Flink cluster."""
    
    job_id: str
    flink_job_id: Optional[str] = None  # Flink's internal job ID
    state: JobState
    last_update: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    restart_count: int = 0
    last_savepoint: Optional[str] = None
    
    # Streaming-specific status
    is_streaming: bool = False
    checkpoint_count: int = 0
    last_checkpoint: Optional[str] = None


class ReconciliationResult(BaseModel):
    """Result of a reconciliation operation."""
    
    job_id: str
    action_taken: ReconciliationAction
    success: bool
    error_message: Optional[str] = None
    duration_ms: int = 0
    reconciled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConflictType(Enum):
    """Types of reconciliation conflicts."""
    CONCURRENT_UPDATE = "concurrent_update"
    STATE_MISMATCH = "state_mismatch"
    RESOURCE_CONFLICT = "resource_conflict"


class Conflict(NamedTuple):
    """Represents a reconciliation conflict."""
    job_id: str
    conflict_type: ConflictType
    description: str
    suggested_resolution: str


class ConflictResolution(BaseModel):
    """Resolution strategy for reconciliation conflicts."""
    
    resolved_conflicts: List[Conflict]
    unresolved_conflicts: List[Conflict]
    resolution_strategy: str
    success: bool


class JobReconciler:
    """Handles reconciliation logic for Flink jobs with conflict resolution."""
    
    def __init__(self, flink_client=None, state_store=None, circuit_breaker_config=None):
        """
        Initialize the job reconciler.
        
        Args:
            flink_client: Flink REST API client
            state_store: Persistent state storage
            circuit_breaker_config: Circuit breaker configuration
        """
        self.flink_client = flink_client
        self.state_store = state_store
        
        # Initialize circuit breaker for resilient Flink calls
        cb_config = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get('failure_threshold', 3),
            recovery_timeout=cb_config.get('recovery_timeout', 30.0),
            expected_exception=Exception
        )
        
        # Reconciliation state
        self._active_reconciliations: Dict[str, datetime] = {}
        self._reconciliation_lock = asyncio.Lock()
        
    async def reconcile_all(self, job_specs: List[JobSpec]) -> List[ReconciliationResult]:
        """
        Reconcile all jobs with proper error handling.
        
        Args:
            job_specs: List of job specifications to reconcile
            
        Returns:
            List of reconciliation results
        """
        results = []
        
        for spec in job_specs:
            try:
                result = await self.reconcile_job(spec)
                results.append(result)
            except Exception as e:
                # Create failure result for job that couldn't be reconciled
                results.append(ReconciliationResult(
                    job_id=spec.job_id,
                    action_taken=ReconciliationAction.NO_ACTION,
                    success=False,
                    error_message=f"Reconciliation failed: {str(e)}"
                ))
        
        return results
    
    async def reconcile_job(self, spec: JobSpec) -> ReconciliationResult:
        """
        Reconcile single job with conflict resolution.
        
        Args:
            spec: Job specification to reconcile
            
        Returns:
            Reconciliation result
        """
        start_time = time.time()
        
        async with self._reconciliation_lock:
            # Check if job is already being reconciled
            if self._is_job_being_reconciled(spec.job_id):
                return ReconciliationResult(
                    job_id=spec.job_id,
                    action_taken=ReconciliationAction.NO_ACTION,
                    success=False,
                    error_message="Job is already being reconciled",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Mark job as being reconciled
            self._active_reconciliations[spec.job_id] = datetime.now(timezone.utc)
        
        try:
            # Get current job status from Flink
            current_status = await self._get_job_status_with_circuit_breaker(spec.job_id)
            
            # Determine what action to take
            action = await self._determine_reconciliation_action(spec, current_status)
            
            # Execute the reconciliation action
            result = await self._execute_reconciliation_action(spec, current_status, action)
            
            # Update duration
            result.duration_ms = int((time.time() - start_time) * 1000)
            
            return result
            
        except CircuitBreakerError:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.NO_ACTION,
                success=False,
                error_message="Circuit breaker is open - Flink cluster unavailable",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.NO_ACTION,
                success=False,
                error_message=f"Reconciliation failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        finally:
            # Remove job from active reconciliations
            async with self._reconciliation_lock:
                self._active_reconciliations.pop(spec.job_id, None)
    
    async def _get_job_status_with_circuit_breaker(self, job_id: str) -> Optional[JobStatus]:
        """Get job status with circuit breaker protection."""
        def get_status():
            # This would call the actual Flink client
            # For now, return a mock status
            if not self.flink_client:
                return None
            return JobStatus(
                job_id=job_id,
                flink_job_id=f"flink-{job_id}",
                state=JobState.UNKNOWN
            )
        
        try:
            return self.circuit_breaker.call(get_status)
        except CircuitBreakerError:
            raise
        except Exception:
            # Return unknown status if we can't get the real status
            return JobStatus(job_id=job_id, state=JobState.UNKNOWN)
    
    async def _determine_reconciliation_action(self, spec: JobSpec, current_status: Optional[JobStatus]) -> ReconciliationAction:
        """
        Determine what reconciliation action to take.
        
        Args:
            spec: Desired job specification
            current_status: Current job status from Flink
            
        Returns:
            Action to take during reconciliation
        """
        if not current_status or current_status.state == JobState.UNKNOWN:
            # Job doesn't exist or status unknown - deploy it
            return ReconciliationAction.DEPLOY
        
        if current_status.state == JobState.FAILED:
            # Job failed - restart it
            return ReconciliationAction.RESTART
        
        if current_status.state == JobState.RUNNING:
            # Check if spec has changed (simplified change detection)
            if await self._has_spec_changed(spec):
                if spec.job_type == JobType.STREAMING:
                    # For streaming jobs, update with savepoint
                    return ReconciliationAction.UPDATE
                else:
                    # For batch jobs, stop and redeploy
                    return ReconciliationAction.STOP
            else:
                # No changes needed
                return ReconciliationAction.NO_ACTION
        
        if current_status.state == JobState.STOPPED:
            # Job was stopped - check if it should be running
            return ReconciliationAction.DEPLOY
        
        return ReconciliationAction.NO_ACTION
    
    async def _execute_reconciliation_action(
        self, 
        spec: JobSpec, 
        current_status: Optional[JobStatus], 
        action: ReconciliationAction
    ) -> ReconciliationResult:
        """Execute the determined reconciliation action."""
        
        if action == ReconciliationAction.NO_ACTION:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=action,
                success=True
            )
        
        elif action == ReconciliationAction.DEPLOY:
            return await self._deploy_job(spec)
        
        elif action == ReconciliationAction.UPDATE:
            return await self._update_streaming_job(spec, current_status)
        
        elif action == ReconciliationAction.STOP:
            return await self._stop_job(spec, current_status)
        
        elif action == ReconciliationAction.RESTART:
            return await self._restart_job(spec, current_status)
        
        else:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=action,
                success=False,
                error_message=f"Unknown action: {action}"
            )
    
    async def _deploy_job(self, spec: JobSpec) -> ReconciliationResult:
        """Deploy a new job to Flink."""
        try:
            # This would use the Flink client to deploy the job
            # For now, simulate deployment
            await asyncio.sleep(0.1)  # Simulate API call
            
            # Update state store
            if self.state_store:
                await self._update_job_state(spec.job_id, JobState.RUNNING)
            
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.DEPLOY,
                success=True
            )
        except Exception as e:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.DEPLOY,
                success=False,
                error_message=f"Deployment failed: {str(e)}"
            )
    
    async def _update_streaming_job(self, spec: JobSpec, current_status: JobStatus) -> ReconciliationResult:
        """Update a streaming job using savepoint-based deployment."""
        try:
            # For streaming jobs, we need to:
            # 1. Trigger savepoint
            # 2. Stop the job
            # 3. Deploy new version from savepoint
            
            savepoint_path = await self._trigger_savepoint(spec.job_id, current_status)
            await self._stop_job_internal(spec.job_id, current_status, graceful=True)
            await self._deploy_from_savepoint(spec, savepoint_path)
            
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.UPDATE,
                success=True
            )
        except Exception as e:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.UPDATE,
                success=False,
                error_message=f"Update failed: {str(e)}"
            )
    
    async def _stop_job(self, spec: JobSpec, current_status: JobStatus) -> ReconciliationResult:
        """Stop a running job."""
        try:
            await self._stop_job_internal(spec.job_id, current_status, graceful=True)
            
            if self.state_store:
                await self._update_job_state(spec.job_id, JobState.STOPPED)
            
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.STOP,
                success=True
            )
        except Exception as e:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.STOP,
                success=False,
                error_message=f"Stop failed: {str(e)}"
            )
    
    async def _restart_job(self, spec: JobSpec, current_status: JobStatus) -> ReconciliationResult:
        """Restart a failed job."""
        try:
            # For restart, we typically want to start from the latest checkpoint/savepoint
            savepoint_path = current_status.last_savepoint if current_status else None
            
            if savepoint_path:
                await self._deploy_from_savepoint(spec, savepoint_path)
            else:
                # No savepoint available, do fresh deployment
                await self._deploy_job(spec)
            
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.RESTART,
                success=True
            )
        except Exception as e:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.RESTART,
                success=False,
                error_message=f"Restart failed: {str(e)}"
            )
    
    async def _trigger_savepoint(self, job_id: str, current_status: JobStatus) -> str:
        """Trigger savepoint for streaming job."""
        # This would call Flink REST API to trigger savepoint
        await asyncio.sleep(0.2)  # Simulate savepoint operation
        return f"/savepoints/{job_id}-{int(time.time())}"
    
    async def _stop_job_internal(self, job_id: str, current_status: JobStatus, graceful: bool = True):
        """Internal method to stop a job."""
        # This would call Flink REST API to stop the job
        await asyncio.sleep(0.1)  # Simulate stop operation
    
    async def _deploy_from_savepoint(self, spec: JobSpec, savepoint_path: str):
        """Deploy job from savepoint."""
        # This would call Flink REST API to deploy from savepoint
        await asyncio.sleep(0.1)  # Simulate deployment
    
    async def _has_spec_changed(self, spec: JobSpec) -> bool:
        """Check if job specification has changed."""
        if not self.state_store:
            return True  # Assume changed if no state store
        
        # This would check against stored spec hash
        return True  # For now, assume always changed
    
    async def _update_job_state(self, job_id: str, state: JobState):
        """Update job state in state store."""
        if self.state_store:
            # This would update the state store
            pass
    
    def _is_job_being_reconciled(self, job_id: str) -> bool:
        """Check if job is currently being reconciled."""
        if job_id not in self._active_reconciliations:
            return False
        
        # Check if reconciliation has been running too long (timeout)
        reconciliation_start = self._active_reconciliations[job_id]
        timeout_duration = datetime.now(timezone.utc) - reconciliation_start
        
        # If reconciliation has been running for more than 5 minutes, consider it stale
        if timeout_duration.total_seconds() > 300:
            self._active_reconciliations.pop(job_id, None)
            return False
        
        return True
    
    async def handle_conflicts(self, conflicts: List[Conflict]) -> ConflictResolution:
        """
        Handle reconciliation conflicts with business rules.
        
        Args:
            conflicts: List of conflicts to resolve
            
        Returns:
            Conflict resolution result
        """
        resolved = []
        unresolved = []
        
        for conflict in conflicts:
            if conflict.conflict_type == ConflictType.CONCURRENT_UPDATE:
                # For concurrent updates, use last-writer-wins strategy
                resolved.append(conflict)
            elif conflict.conflict_type == ConflictType.STATE_MISMATCH:
                # For state mismatches, prefer Flink cluster state as source of truth
                resolved.append(conflict)
            else:
                # Other conflicts need manual resolution
                unresolved.append(conflict)
        
        return ConflictResolution(
            resolved_conflicts=resolved,
            unresolved_conflicts=unresolved,
            resolution_strategy="automatic_with_fallback",
            success=len(unresolved) == 0
        )