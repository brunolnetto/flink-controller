"""
Type protocols for strict typing and dependency injection.

This module defines protocols to eliminate duck typing and provide
strict type safety for all components.
"""

from typing import Protocol, Optional, List, Dict
from datetime import datetime
from .reconciler import JobSpec, JobStatus, JobState
from .flink_client import FlinkJobInfo, DeploymentConfig, FlinkClusterInfo


class FlinkClientProtocol(Protocol):
    """Protocol for Flink REST API client."""
    
    async def get_cluster_info(self) -> FlinkClusterInfo:
        """Get Flink cluster information."""
        ...
    
    async def list_jobs(self) -> List[FlinkJobInfo]:
        """List all jobs in the cluster."""
        ...
    
    async def get_job_details(self, job_id: str) -> FlinkJobInfo:
        """Get detailed job information."""
        ...
    
    async def deploy_job(self, jar_file_path: str, config: DeploymentConfig, job_name: Optional[str] = None) -> str:
        """Deploy a job and return Flink job ID."""
        ...
    
    async def stop_job(self, job_id: str, savepoint_path: Optional[str] = None, drain: bool = False) -> Optional[str]:
        """Stop a job, optionally creating a savepoint."""
        ...
    
    async def trigger_savepoint(self, job_id: str, savepoint_dir: str) -> str:
        """Trigger a savepoint and return request ID."""
        ...
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        ...
    
    async def health_check(self) -> bool:
        """Check if Flink cluster is healthy."""
        ...


class StateStoreProtocol(Protocol):
    """Protocol for persistent state storage."""
    
    async def get_job_state(self, job_id: str) -> Optional[JobState]:
        """Get current job state."""
        ...
    
    async def save_job_state(self, job_id: str, state: JobState) -> None:
        """Save job state."""
        ...
    
    async def delete_job_state(self, job_id: str) -> bool:
        """Delete job state."""
        ...
    
    async def list_job_states(self) -> Dict[str, JobState]:
        """List all job states."""
        ...


class ChangeTrackerProtocol(Protocol):
    """Protocol for job specification change tracking."""
    
    def calculate_spec_hash(self, spec: JobSpec) -> str:
        """Calculate deterministic hash of spec."""
        ...
    
    async def has_changed(self, job_id: str, spec: JobSpec) -> bool:
        """Check if job specification has changed."""
        ...
    
    async def update_tracker(self, job_id: str, spec: JobSpec) -> None:
        """Update tracker with new spec."""
        ...
    
    async def get_tracked_jobs(self) -> Dict[str, str]:
        """Get all tracked jobs and hashes."""
        ...


class JobSpecManagerProtocol(Protocol):
    """Protocol for job specification management."""
    
    async def load_all_specs(self) -> List[JobSpec]:
        """Load all job specifications."""
        ...
    
    async def validate_spec(self, spec_dict: Dict[str, any]) -> 'ValidationResult':
        """Validate job specification."""
        ...
    
    async def save_spec(self, spec: JobSpec, persist_to_file: bool = True) -> bool:
        """Save job specification."""
        ...
    
    def get_cached_spec(self, job_id: str) -> Optional[JobSpec]:
        """Get cached job specification."""
        ...


class MetricsCollectorProtocol(Protocol):
    """Protocol for metrics collection."""
    
    def record_reconciliation(self, job_id: str, action: str, success: bool, duration_ms: int) -> None:
        """Record reconciliation metrics."""
        ...
    
    def record_deployment(self, job_id: str, success: bool, duration_ms: int) -> None:
        """Record deployment metrics."""
        ...
    
    def record_error(self, job_id: str, error_type: str, error_message: str) -> None:
        """Record error metrics."""
        ...


class CircuitBreakerProtocol(Protocol):
    """Protocol for circuit breaker functionality."""
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        ...
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        ...
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        ...
    
    def reset(self) -> None:
        """Reset circuit breaker."""
        ...