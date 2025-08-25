"""
Comprehensive exception hierarchy for Flink Job Controller.

This module provides specific exception types instead of generic Exception usage.
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(Enum):
    """Standardized error codes for categorization."""
    
    # Reconciliation errors
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    CONCURRENT_RECONCILIATION = "CONCURRENT_RECONCILIATION"
    RECONCILIATION_TIMEOUT = "RECONCILIATION_TIMEOUT"
    
    # Job management errors  
    JOB_DEPLOYMENT_FAILED = "JOB_DEPLOYMENT_FAILED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_ALREADY_EXISTS = "JOB_ALREADY_EXISTS"
    JOB_STATE_INVALID = "JOB_STATE_INVALID"
    
    # Flink cluster errors
    FLINK_CLUSTER_UNAVAILABLE = "FLINK_CLUSTER_UNAVAILABLE"
    FLINK_API_ERROR = "FLINK_API_ERROR"
    FLINK_AUTHENTICATION_FAILED = "FLINK_AUTHENTICATION_FAILED"
    
    # Savepoint errors
    SAVEPOINT_CREATION_FAILED = "SAVEPOINT_CREATION_FAILED"
    SAVEPOINT_NOT_FOUND = "SAVEPOINT_NOT_FOUND"
    SAVEPOINT_RESTORE_FAILED = "SAVEPOINT_RESTORE_FAILED"
    
    # State store errors
    STATE_STORE_ERROR = "STATE_STORE_ERROR"
    STATE_NOT_FOUND = "STATE_NOT_FOUND"
    STATE_CORRUPTION = "STATE_CORRUPTION"
    
    # Validation errors
    SPEC_VALIDATION_FAILED = "SPEC_VALIDATION_FAILED"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    ARTIFACT_VERIFICATION_FAILED = "ARTIFACT_VERIFICATION_FAILED"
    
    # Circuit breaker errors
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    
    # Configuration errors
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    DEPENDENCY_NOT_AVAILABLE = "DEPENDENCY_NOT_AVAILABLE"


class FlinkControllerError(Exception):
    """Base exception for all Flink Controller errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode,
        job_id: Optional[str] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.job_id = job_id
        self.cause = cause
        self.context = context or {}
    
    def __str__(self) -> str:
        parts = [f"[{self.error_code.value}]"]
        if self.job_id:
            parts.append(f"Job {self.job_id}")
        parts.append(self.message)
        
        if self.cause:
            parts.append(f"Caused by: {self.cause}")
        
        return " - ".join(parts)


class ReconciliationError(FlinkControllerError):
    """Errors during job reconciliation process."""
    
    def __init__(
        self, 
        message: str, 
        job_id: str, 
        error_code: ErrorCode = ErrorCode.RECONCILIATION_FAILED,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, job_id, cause, context)


class ConcurrentReconciliationError(ReconciliationError):
    """Error when trying to reconcile a job already being reconciled."""
    
    def __init__(self, job_id: str, started_at: str):
        super().__init__(
            f"Job is already being reconciled since {started_at}",
            job_id,
            ErrorCode.CONCURRENT_RECONCILIATION,
            context={"started_at": started_at}
        )


class JobDeploymentError(FlinkControllerError):
    """Errors during job deployment."""
    
    def __init__(
        self, 
        message: str, 
        job_id: str,
        deployment_config: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message, 
            ErrorCode.JOB_DEPLOYMENT_FAILED, 
            job_id, 
            cause,
            context={"deployment_config": deployment_config}
        )


class JobNotFoundError(FlinkControllerError):
    """Error when job is not found."""
    
    def __init__(self, job_id: str, searched_in: Optional[str] = None):
        message = f"Job not found: {job_id}"
        if searched_in:
            message += f" (searched in: {searched_in})"
        
        super().__init__(
            message, 
            ErrorCode.JOB_NOT_FOUND, 
            job_id,
            context={"searched_in": searched_in}
        )


class SavepointError(FlinkControllerError):
    """Errors related to savepoint operations."""
    
    def __init__(
        self, 
        message: str, 
        job_id: str,
        error_code: ErrorCode,
        savepoint_path: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message, 
            error_code, 
            job_id, 
            cause,
            context={"savepoint_path": savepoint_path}
        )


class SavepointCreationError(SavepointError):
    """Error during savepoint creation."""
    
    def __init__(self, job_id: str, savepoint_dir: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to create savepoint in {savepoint_dir}",
            job_id,
            ErrorCode.SAVEPOINT_CREATION_FAILED,
            savepoint_dir,
            cause
        )


class SavepointRestoreError(SavepointError):
    """Error during savepoint restore."""
    
    def __init__(self, job_id: str, savepoint_path: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to restore from savepoint {savepoint_path}",
            job_id,
            ErrorCode.SAVEPOINT_RESTORE_FAILED,
            savepoint_path,
            cause
        )


class FlinkClusterError(FlinkControllerError):
    """Errors related to Flink cluster communication."""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.FLINK_CLUSTER_UNAVAILABLE,
        cluster_url: Optional[str] = None,
        status_code: Optional[int] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message, 
            error_code, 
            cause=cause,
            context={"cluster_url": cluster_url, "status_code": status_code}
        )


class FlinkAPIError(FlinkClusterError):
    """Errors from Flink REST API."""
    
    def __init__(
        self, 
        message: str, 
        endpoint: str,
        status_code: Optional[int] = None, 
        response_data: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message, 
            ErrorCode.FLINK_API_ERROR,
            status_code=status_code,
            cause=cause
        )
        self.endpoint = endpoint
        self.response_data = response_data


class StateStoreError(FlinkControllerError):
    """Errors related to persistent state storage."""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.STATE_STORE_ERROR,
        job_id: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, error_code, job_id, cause)


class StateNotFoundError(StateStoreError):
    """Error when job state is not found in store."""
    
    def __init__(self, job_id: str):
        super().__init__(
            f"Job state not found: {job_id}",
            ErrorCode.STATE_NOT_FOUND,
            job_id
        )


class SpecValidationError(FlinkControllerError):
    """Errors during job specification validation."""
    
    def __init__(
        self, 
        message: str, 
        job_id: Optional[str] = None,
        validation_errors: Optional[list] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message, 
            ErrorCode.SPEC_VALIDATION_FAILED, 
            job_id, 
            cause,
            context={"validation_errors": validation_errors}
        )


class ArtifactError(FlinkControllerError):
    """Errors related to job artifacts."""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode,
        artifact_path: str,
        job_id: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message, 
            error_code, 
            job_id, 
            cause,
            context={"artifact_path": artifact_path}
        )


class ArtifactNotFoundError(ArtifactError):
    """Error when job artifact file is not found."""
    
    def __init__(self, artifact_path: str, job_id: Optional[str] = None):
        super().__init__(
            f"Artifact not found: {artifact_path}",
            ErrorCode.ARTIFACT_NOT_FOUND,
            artifact_path,
            job_id
        )


class CircuitBreakerOpenError(FlinkControllerError):
    """Error when circuit breaker is open."""
    
    def __init__(self, service_name: str, failure_count: int, last_failure: str):
        super().__init__(
            f"Circuit breaker open for {service_name}",
            ErrorCode.CIRCUIT_BREAKER_OPEN,
            context={
                "service_name": service_name,
                "failure_count": failure_count, 
                "last_failure": last_failure
            }
        )


class ConfigurationError(FlinkControllerError):
    """Errors in configuration."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message, 
            ErrorCode.CONFIGURATION_ERROR,
            context={"config_key": config_key}
        )