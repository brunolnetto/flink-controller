"""
Strict type definitions for Flink Job Controller.

This module provides specific types to replace all 'Any' usage
and ensure complete type safety throughout the application.
"""

from typing import Dict, List, Optional, Union, Literal, TypedDict, NewType
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# Strong type aliases to replace Any
JobId = NewType('JobId', str)
FlinkJobId = NewType('FlinkJobId', str)
ArtifactPath = NewType('ArtifactPath', str)
SavepointPath = NewType('SavepointPath', str)
ChecksumHash = NewType('ChecksumHash', str)
SpecHash = NewType('SpecHash', str)
CronExpression = NewType('CronExpression', str)
TemplateId = NewType('TemplateId', str)
PipelineId = NewType('PipelineId', str)


class JobSpecDict(TypedDict, total=False):
    """Strictly typed dictionary for job specifications."""
    job_id: str
    job_type: str
    artifact_path: str
    artifact_signature: Optional[str]
    parallelism: int
    checkpoint_interval: Optional[int]
    savepoint_path: Optional[str]
    restart_strategy: str
    max_restart_attempts: int
    memory: str
    cpu_cores: int
    savepoint_trigger_interval: Optional[int]
    checkpoint_timeout: Optional[int]


class FlinkJobDetailsDict(TypedDict, total=False):
    """Strictly typed dictionary for Flink job details."""
    job_id: str
    name: str
    state: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration: Optional[int]
    parallelism: int
    vertices: List[Dict[str, Union[str, int]]]


class FlinkClusterOverviewDict(TypedDict):
    """Strictly typed dictionary for Flink cluster overview."""
    cluster_id: str
    flink_version: str
    taskmanagers: int
    slots_total: int
    slots_available: int
    jobs_running: int


class CheckpointInfoDict(TypedDict, total=False):
    """Strictly typed dictionary for checkpoint information."""
    count: int
    latest: Dict[str, Union[str, int]]
    history: List[Dict[str, Union[str, int, bool]]]


class SavepointInfoDict(TypedDict, total=False):
    """Strictly typed dictionary for savepoint information."""
    location: str
    trigger_timestamp: int
    status: str
    request_id: str


class DatabaseRecordDict(TypedDict, total=False):
    """Strictly typed dictionary for database records."""
    job_id: str
    spec_hash: str
    last_updated: str
    created_at: str
    state: str
    metadata: str


class MetricsDataDict(TypedDict, total=False):
    """Strictly typed dictionary for metrics data."""
    reconciliation_count: int
    deployment_count: int
    error_count: int
    average_duration: float
    success_rate: float
    timestamp: str


class ConfigurationDict(TypedDict, total=False):
    """Strictly typed dictionary for configuration."""
    max_concurrent_reconciliations: int
    reconciliation_timeout: float
    circuit_breaker_threshold: int
    circuit_breaker_timeout: float
    enable_metrics: bool
    enable_performance_logging: bool


class ValidationErrorDict(TypedDict):
    """Strictly typed dictionary for validation errors."""
    field: str
    message: str
    invalid_value: str


class DeploymentConfigDict(TypedDict, total=False):
    """Strictly typed dictionary for deployment configuration."""
    entry_class: Optional[str]
    program_args: List[str]
    parallelism: Optional[int]
    savepoint_path: Optional[str]
    allow_non_restored_state: bool
    jar_id: str


class JobStatisticsDict(TypedDict):
    """Strictly typed dictionary for job statistics."""
    total_jobs: int
    running_jobs: int
    failed_jobs: int
    completed_jobs: int
    average_uptime: float


class PipelineStageDict(TypedDict):
    """Strictly typed dictionary for pipeline stage information."""
    stage_name: str
    job_ids: List[str]
    dependencies: List[str]
    parallel_execution: bool
    timeout_seconds: Optional[int]


class TemplateParameterDict(TypedDict):
    """Strictly typed dictionary for template parameters."""
    parameter_name: str
    parameter_type: Literal['string', 'integer', 'boolean', 'float']
    default_value: Optional[str]
    required: bool
    description: str


class AuditLogEntryDict(TypedDict):
    """Strictly typed dictionary for audit log entries."""
    timestamp: str
    operation: str
    job_id: str
    user: str
    details: str
    success: bool


# Specific union types to replace Any
JobSpecValue = Union[str, int, bool, List[str], None]
FlinkAPIResponse = Union[FlinkJobDetailsDict, FlinkClusterOverviewDict, CheckpointInfoDict]
ConfigurationValue = Union[str, int, float, bool, List[str]]
MetricValue = Union[int, float, str]
DatabaseValue = Union[str, int, float, bool, None]


class JobSpecManager:
    """Strictly typed job specification manager interface."""
    
    def load_all_specs(self) -> List[JobSpecDict]:
        """Load all job specifications with strict typing."""
        ...
    
    def validate_spec(self, spec: JobSpecDict) -> List[ValidationErrorDict]:
        """Validate job specification with typed errors."""
        ...
    
    def get_job_status(self, job_id: JobId) -> Optional[FlinkJobDetailsDict]:
        """Get job status with strict return type."""
        ...


class StrictFlinkClient:
    """Strictly typed Flink client interface."""
    
    def get_cluster_info(self) -> FlinkClusterOverviewDict:
        """Get cluster information with strict typing."""
        ...
    
    def get_job_details(self, job_id: FlinkJobId) -> FlinkJobDetailsDict:
        """Get job details with strict typing."""
        ...
    
    def deploy_job(self, jar_path: ArtifactPath, config: DeploymentConfigDict) -> FlinkJobId:
        """Deploy job with strict typing."""
        ...


class StrictChangeTracker:
    """Strictly typed change tracker interface."""
    
    def calculate_spec_hash(self, spec: JobSpecDict) -> SpecHash:
        """Calculate spec hash with strict typing."""
        ...
    
    def has_changed(self, job_id: JobId, spec: JobSpecDict) -> bool:
        """Check for changes with strict typing."""
        ...
    
    def get_tracked_jobs(self) -> Dict[JobId, SpecHash]:
        """Get tracked jobs with strict typing."""
        ...


class StrictMetricsCollector:
    """Strictly typed metrics collector interface."""
    
    def record_reconciliation(
        self, 
        job_id: JobId, 
        action: str, 
        success: bool, 
        duration_ms: int
    ) -> None:
        """Record reconciliation metrics with strict typing."""
        ...
    
    def get_metrics_data(self) -> MetricsDataDict:
        """Get metrics data with strict typing."""
        ...


# Type guards for runtime type checking
def is_valid_job_id(value: str) -> bool:
    """Type guard for job ID validation."""
    import re
    pattern = r'^[a-zA-Z0-9_-]+$'
    return len(value) > 0 and len(value) <= 255 and bool(re.match(pattern, value))


def is_valid_cron_expression(value: str) -> bool:
    """Type guard for cron expression validation."""
    # Simple validation for standard 5-field cron expressions
    import re
    cron_pattern = re.compile(
        r'^(\*|[0-5]?\d)\s+(\*|1?\d|2[0-3])\s+(\*|[12]?\d|3[01])\s+(\*|[1-9]|1[0-2])\s+(\*|[0-6])$'
    )
    return bool(cron_pattern.match(value.strip()))


def is_valid_artifact_path(value: str) -> bool:
    """Type guard for artifact path validation."""
    return len(value) > 0 and (value.endswith('.jar') or value.endswith('.zip'))


def is_valid_memory_string(value: str) -> bool:
    """Type guard for memory string validation."""
    import re
    pattern = r'^\d+[kmgKMG]?$'
    return bool(re.match(pattern, value))


# Runtime type conversion utilities
def safe_cast_job_id(value: str) -> JobId:
    """Safely cast string to JobId with validation."""
    if not is_valid_job_id(value):
        raise ValueError(f"Invalid job ID: {value}")
    return JobId(value)


def safe_cast_artifact_path(value: str) -> ArtifactPath:
    """Safely cast string to ArtifactPath with validation."""
    if not is_valid_artifact_path(value):
        raise ValueError(f"Invalid artifact path: {value}")
    return ArtifactPath(value)


def safe_cast_cron_expression(value: str) -> CronExpression:
    """Safely cast string to CronExpression with validation."""
    if not is_valid_cron_expression(value):
        raise ValueError(f"Invalid cron expression: {value}")
    return CronExpression(value)