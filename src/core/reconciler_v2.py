"""
Enhanced job reconciler with strict typing and performance optimizations.

This module provides improved reconciliation logic with:
- Strict type safety using protocols
- Concurrent processing for better performance
- Comprehensive error handling with specific exceptions
- 100% test coverage support
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Set
from dataclasses import dataclass
from pydantic import BaseModel, Field

from .protocols import (
    FlinkClientProtocol, StateStoreProtocol, ChangeTrackerProtocol,
    MetricsCollectorProtocol, CircuitBreakerProtocol
)
from .exceptions import (
    ReconciliationError, ConcurrentReconciliationError, JobDeploymentError,
    SavepointError, SavepointCreationError, CircuitBreakerOpenError,
    FlinkClusterError, ErrorCode
)
from .reconciler import JobSpec, JobType, JobState, ReconciliationAction


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Immutable configuration for circuit breaker."""
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    expected_exceptions: tuple = (Exception,)


@dataclass(frozen=True)
class ReconcilerConfig:
    """Immutable configuration for reconciler."""
    max_concurrent_reconciliations: int = 10
    reconciliation_timeout: float = 300.0  # 5 minutes
    enable_metrics: bool = True
    enable_performance_logging: bool = False


class ReconciliationResult(BaseModel):
    """Strongly typed reconciliation result."""
    
    job_id: str = Field(..., min_length=1)
    action_taken: ReconciliationAction
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = Field(..., ge=0)
    reconciled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: Dict[str, str] = Field(default_factory=dict)


class ReconciliationStatistics(BaseModel):
    """Statistics for reconciliation operations."""
    
    total_jobs: int = Field(..., ge=0)
    successful_reconciliations: int = Field(..., ge=0) 
    failed_reconciliations: int = Field(..., ge=0)
    concurrent_reconciliation_attempts: int = Field(..., ge=0)
    average_duration_ms: float = Field(..., ge=0.0)
    actions_taken: Dict[str, int] = Field(default_factory=dict)
    error_codes: Dict[str, int] = Field(default_factory=dict)


class EnhancedJobReconciler:
    """
    Enhanced job reconciler with strict typing and performance optimizations.
    
    This reconciler eliminates duck typing and provides:
    - Protocol-based dependency injection
    - Concurrent reconciliation with semaphore control
    - Comprehensive error handling with specific exception types
    - Performance monitoring and metrics collection
    - 100% testable with proper dependency injection
    """
    
    def __init__(
        self,
        flink_client: FlinkClientProtocol,
        state_store: Optional[StateStoreProtocol] = None,
        change_tracker: Optional[ChangeTrackerProtocol] = None,
        metrics_collector: Optional[MetricsCollectorProtocol] = None,
        circuit_breaker: Optional[CircuitBreakerProtocol] = None,
        config: ReconcilerConfig = ReconcilerConfig()
    ):
        """
        Initialize enhanced reconciler with strict typing.
        
        Args:
            flink_client: Flink REST API client (required)
            state_store: Persistent state storage (optional)
            change_tracker: Job specification change tracker (optional)
            metrics_collector: Metrics collection service (optional)
            circuit_breaker: Circuit breaker for resilience (optional)
            config: Reconciler configuration
        """
        self._flink_client = flink_client
        self._state_store = state_store
        self._change_tracker = change_tracker
        self._metrics_collector = metrics_collector
        self._circuit_breaker = circuit_breaker
        self._config = config
        
        # Reconciliation state with proper typing
        self._active_reconciliations: Dict[str, datetime] = {}
        self._reconciliation_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(config.max_concurrent_reconciliations)
        
        # Statistics tracking
        self._statistics = ReconciliationStatistics(
            total_jobs=0,
            successful_reconciliations=0,
            failed_reconciliations=0,
            concurrent_reconciliation_attempts=0,
            average_duration_ms=0.0
        )
    
    async def reconcile_all(self, job_specs: List[JobSpec]) -> List[ReconciliationResult]:
        """
        Reconcile all jobs concurrently with proper error handling.
        
        Args:
            job_specs: List of job specifications to reconcile
            
        Returns:
            List of reconciliation results
            
        Raises:
            ReconciliationError: If reconciliation fails with unrecoverable error
        """
        if not job_specs:
            return []
        
        self._statistics.total_jobs = len(job_specs)
        
        # Create concurrent tasks with semaphore control
        tasks = [
            self._reconcile_with_semaphore(spec) 
            for spec in job_specs
        ]
        
        # Execute all reconciliations concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Convert exception to failed result
                processed_results.append(ReconciliationResult(
                    job_id=job_specs[i].job_id,
                    action_taken=ReconciliationAction.NO_ACTION,
                    success=False,
                    error_code=ErrorCode.RECONCILIATION_FAILED.value,
                    error_message=str(result),
                    duration_ms=0
                ))
            else:
                processed_results.append(result)
        
        # Update statistics
        self._update_statistics(processed_results)
        
        return processed_results
    
    async def _reconcile_with_semaphore(self, spec: JobSpec) -> ReconciliationResult:
        """Reconcile job with semaphore control to limit concurrency."""
        async with self._semaphore:
            return await self.reconcile_job(spec)
    
    async def reconcile_job(self, spec: JobSpec) -> ReconciliationResult:
        """
        Reconcile single job with comprehensive error handling.
        
        Args:
            spec: Job specification to reconcile
            
        Returns:
            Reconciliation result with detailed information
        """
        start_time = time.perf_counter()
        
        try:
            # Check for concurrent reconciliation
            await self._check_concurrent_reconciliation(spec.job_id)
            
            # Mark job as being reconciled
            await self._mark_reconciliation_start(spec.job_id)
            
            try:
                # Get current job status with circuit breaker protection
                current_status = await self._get_job_status_protected(spec.job_id)
                
                # Determine reconciliation action
                action = await self._determine_reconciliation_action(spec, current_status)
                
                # Execute reconciliation
                result = await self._execute_reconciliation_action(spec, current_status, action)
                
                # Record success metrics
                if self._metrics_collector:
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    self._metrics_collector.record_reconciliation(
                        spec.job_id, action.value, True, duration_ms
                    )
                
                return result
                
            finally:
                # Always clean up reconciliation state
                await self._mark_reconciliation_complete(spec.job_id)
        
        except ConcurrentReconciliationError as e:
            self._statistics.concurrent_reconciliation_attempts += 1
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.NO_ACTION,
                success=False,
                error_code=e.error_code.value,
                error_message=str(e),
                duration_ms=int((time.perf_counter() - start_time) * 1000)
            )
        
        except CircuitBreakerOpenError as e:
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.NO_ACTION,
                success=False,
                error_code=e.error_code.value,
                error_message=str(e),
                duration_ms=int((time.perf_counter() - start_time) * 1000)
            )
        
        except ReconciliationError as e:
            # Record error metrics
            if self._metrics_collector:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._metrics_collector.record_error(spec.job_id, e.error_code.value, str(e))
            
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.NO_ACTION,
                success=False,
                error_code=e.error_code.value,
                error_message=str(e),
                duration_ms=int((time.perf_counter() - start_time) * 1000),
                context=e.context
            )
        
        except Exception as e:
            # Catch-all for unexpected exceptions
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=ReconciliationAction.NO_ACTION,
                success=False,
                error_code=ErrorCode.RECONCILIATION_FAILED.value,
                error_message=f"Unexpected error: {str(e)}",
                duration_ms=int((time.perf_counter() - start_time) * 1000)
            )
    
    async def _check_concurrent_reconciliation(self, job_id: str) -> None:
        """Check if job is already being reconciled."""
        async with self._reconciliation_lock:
            if job_id in self._active_reconciliations:
                started_at = self._active_reconciliations[job_id]
                
                # Check for timeout
                if (datetime.now(timezone.utc) - started_at).total_seconds() > self._config.reconciliation_timeout:
                    # Reconciliation timed out, remove it
                    del self._active_reconciliations[job_id]
                else:
                    raise ConcurrentReconciliationError(job_id, started_at.isoformat())
    
    async def _mark_reconciliation_start(self, job_id: str) -> None:
        """Mark job as being reconciled."""
        async with self._reconciliation_lock:
            self._active_reconciliations[job_id] = datetime.now(timezone.utc)
    
    async def _mark_reconciliation_complete(self, job_id: str) -> None:
        """Mark job reconciliation as complete."""
        async with self._reconciliation_lock:
            self._active_reconciliations.pop(job_id, None)
    
    async def _get_job_status_protected(self, job_id: str) -> Optional[JobState]:
        """Get job status with circuit breaker protection."""
        try:
            if self._circuit_breaker:
                # Use circuit breaker if available
                cluster_info = self._circuit_breaker.call(
                    self._flink_client.get_cluster_info
                )
                job_details = self._circuit_breaker.call(
                    self._flink_client.get_job_details, job_id
                )
            else:
                # Direct call if no circuit breaker
                await self._flink_client.get_cluster_info()  # Health check
                job_details = await self._flink_client.get_job_details(job_id)
            
            # Convert Flink job state to our job state
            return self._convert_flink_state_to_job_state(job_details.state)
            
        except Exception as e:
            if self._circuit_breaker and self._circuit_breaker.is_open:
                raise CircuitBreakerOpenError("Flink Cluster", 0, str(e))
            
            # If job not found, return None (new job)
            if "not found" in str(e).lower():
                return None
            
            raise FlinkClusterError(f"Failed to get job status: {str(e)}", cause=e)
    
    def _convert_flink_state_to_job_state(self, flink_state: str) -> JobState:
        """Convert Flink job state to our internal job state."""
        state_mapping = {
            "RUNNING": JobState.RUNNING,
            "FINISHED": JobState.STOPPED,
            "CANCELED": JobState.STOPPED,
            "CANCELLED": JobState.STOPPED,
            "FAILED": JobState.FAILED,
            "RESTARTING": JobState.RECONCILING
        }
        return state_mapping.get(flink_state, JobState.UNKNOWN)
    
    async def _determine_reconciliation_action(
        self, 
        spec: JobSpec, 
        current_status: Optional[JobState]
    ) -> ReconciliationAction:
        """Determine what reconciliation action to take."""
        if not current_status or current_status == JobState.UNKNOWN:
            return ReconciliationAction.DEPLOY
        
        if current_status == JobState.FAILED:
            return ReconciliationAction.RESTART
        
        if current_status == JobState.RUNNING:
            # Check for changes using change tracker
            if self._change_tracker and await self._change_tracker.has_changed(spec.job_id, spec):
                return ReconciliationAction.UPDATE if spec.job_type == JobType.STREAMING else ReconciliationAction.STOP
            return ReconciliationAction.NO_ACTION
        
        if current_status == JobState.STOPPED:
            return ReconciliationAction.DEPLOY
        
        return ReconciliationAction.NO_ACTION
    
    async def _execute_reconciliation_action(
        self,
        spec: JobSpec,
        current_status: Optional[JobState],
        action: ReconciliationAction
    ) -> ReconciliationResult:
        """Execute the determined reconciliation action."""
        start_time = time.perf_counter()
        
        try:
            if action == ReconciliationAction.NO_ACTION:
                return ReconciliationResult(
                    job_id=spec.job_id,
                    action_taken=action,
                    success=True,
                    duration_ms=int((time.perf_counter() - start_time) * 1000)
                )
            
            elif action == ReconciliationAction.DEPLOY:
                await self._deploy_job(spec)
            
            elif action == ReconciliationAction.UPDATE:
                await self._update_streaming_job(spec)
            
            elif action == ReconciliationAction.STOP:
                await self._stop_job(spec.job_id)
            
            elif action == ReconciliationAction.RESTART:
                await self._restart_job(spec)
            
            # Update state store if available
            if self._state_store:
                await self._state_store.save_job_state(spec.job_id, JobState.RUNNING)
            
            # Update change tracker if available
            if self._change_tracker:
                await self._change_tracker.update_tracker(spec.job_id, spec)
            
            return ReconciliationResult(
                job_id=spec.job_id,
                action_taken=action,
                success=True,
                duration_ms=int((time.perf_counter() - start_time) * 1000)
            )
        
        except Exception as e:
            raise ReconciliationError(
                f"Failed to execute {action.value}",
                spec.job_id,
                cause=e
            )
    
    async def _deploy_job(self, spec: JobSpec) -> None:
        """Deploy a job to Flink cluster."""
        try:
            from .flink_client import DeploymentConfig
            
            config = DeploymentConfig(
                parallelism=spec.parallelism,
                savepoint_path=spec.savepoint_path,
                program_args=[]
            )
            
            flink_job_id = await self._flink_client.deploy_job(
                spec.artifact_path, 
                config, 
                spec.job_id
            )
            
            if self._metrics_collector:
                self._metrics_collector.record_deployment(spec.job_id, True, 0)
        
        except Exception as e:
            if self._metrics_collector:
                self._metrics_collector.record_deployment(spec.job_id, False, 0)
            
            raise JobDeploymentError(
                f"Failed to deploy job {spec.job_id}",
                spec.job_id,
                deployment_config=spec.dict(),
                cause=e
            )
    
    async def _update_streaming_job(self, spec: JobSpec) -> None:
        """Update streaming job with savepoint."""
        try:
            # Trigger savepoint
            savepoint_request = await self._flink_client.trigger_savepoint(
                spec.job_id, 
                f"/savepoints/{spec.job_id}"
            )
            
            # Wait for savepoint completion (simplified)
            await asyncio.sleep(5)
            
            # Stop job with savepoint
            await self._flink_client.stop_job(spec.job_id, drain=False)
            
            # Deploy new version
            await self._deploy_job(spec)
        
        except Exception as e:
            raise SavepointError(
                f"Failed to update streaming job {spec.job_id}",
                spec.job_id,
                ErrorCode.SAVEPOINT_CREATION_FAILED,
                cause=e
            )
    
    async def _stop_job(self, job_id: str) -> None:
        """Stop a running job."""
        await self._flink_client.stop_job(job_id)
    
    async def _restart_job(self, spec: JobSpec) -> None:
        """Restart a failed job."""
        # For restart, try to use latest savepoint if available
        try:
            await self._deploy_job(spec)
        except Exception as e:
            raise JobDeploymentError(
                f"Failed to restart job {spec.job_id}",
                spec.job_id,
                cause=e
            )
    
    def _update_statistics(self, results: List[ReconciliationResult]) -> None:
        """Update reconciliation statistics."""
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        self._statistics.successful_reconciliations += successful
        self._statistics.failed_reconciliations += failed
        
        # Update average duration
        durations = [r.duration_ms for r in results if r.duration_ms > 0]
        if durations:
            total_duration = sum(durations)
            total_ops = self._statistics.successful_reconciliations + self._statistics.failed_reconciliations
            self._statistics.average_duration_ms = total_duration / total_ops
        
        # Update action counts
        for result in results:
            action = result.action_taken.value
            self._statistics.actions_taken[action] = self._statistics.actions_taken.get(action, 0) + 1
        
        # Update error code counts
        for result in results:
            if result.error_code:
                self._statistics.error_codes[result.error_code] = \
                    self._statistics.error_codes.get(result.error_code, 0) + 1
    
    def get_statistics(self) -> ReconciliationStatistics:
        """Get current reconciliation statistics."""
        return self._statistics.copy(deep=True)
    
    def get_active_reconciliations(self) -> Dict[str, str]:
        """Get currently active reconciliations."""
        return {
            job_id: started_at.isoformat() 
            for job_id, started_at in self._active_reconciliations.items()
        }
    
    async def health_check(self) -> bool:
        """Check if reconciler and its dependencies are healthy."""
        try:
            # Check Flink cluster health
            is_healthy = await self._flink_client.health_check()
            
            # Check circuit breaker state
            if self._circuit_breaker and self._circuit_breaker.is_open:
                return False
            
            return is_healthy
        
        except Exception:
            return False