"""
Job specification management for Flink Job Controller.

This module manages job specification loading, validation, and lifecycle operations
for both streaming and batch Flink jobs.
"""

import os
import yaml
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ValidationError

from .reconciler import JobSpec, JobType, JobState


class ValidationResult(BaseModel):
    """Result of job specification validation."""
    
    valid: bool = Field(..., description="Whether the spec is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    job_id: Optional[str] = Field(None, description="Job ID being validated")


class JobSpecManager:
    """Manages job specification loading, validation, and lifecycle."""
    
    def __init__(self, spec_directory: str = "job-specs", database=None):
        """
        Initialize the job specification manager.
        
        Args:
            spec_directory: Directory containing job specification files
            database: Database connection for persistent storage
        """
        self.spec_directory = Path(spec_directory)
        self.database = database
        self._spec_cache: Dict[str, JobSpec] = {}
        self._last_load_time: Optional[datetime] = None
    
    async def load_all_specs(self) -> List[JobSpec]:
        """
        Load and validate all job specifications from database and files.
        
        Returns:
            List of validated job specifications
        """
        specs = []
        
        # Load from database if available
        if self.database:
            db_specs = await self._load_specs_from_database()
            specs.extend(db_specs)
        
        # Load from filesystem
        file_specs = await self._load_specs_from_files()
        specs.extend(file_specs)
        
        # Validate all specs
        validated_specs = []
        for spec in specs:
            validation_result = await self.validate_spec(spec.dict() if isinstance(spec, JobSpec) else spec)
            if validation_result.valid:
                validated_specs.append(spec if isinstance(spec, JobSpec) else JobSpec(**spec))
            else:
                print(f"Warning: Invalid spec for job {validation_result.job_id}: {validation_result.errors}")
        
        # Update cache
        self._spec_cache = {spec.job_id: spec for spec in validated_specs}
        self._last_load_time = datetime.now(timezone.utc)
        
        return validated_specs
    
    async def _load_specs_from_database(self) -> List[Dict[str, Any]]:
        """Load job specifications from database."""
        # This would implement actual database loading
        # For now, return empty list
        return []
    
    async def _load_specs_from_files(self) -> List[Dict[str, Any]]:
        """Load job specifications from filesystem."""
        specs = []
        
        if not self.spec_directory.exists():
            print(f"Spec directory {self.spec_directory} does not exist")
            return specs
        
        for spec_file in self.spec_directory.glob("*.yaml"):
            try:
                with open(spec_file, 'r') as f:
                    spec_data = yaml.safe_load(f)
                    specs.append(spec_data)
            except Exception as e:
                print(f"Error loading spec file {spec_file}: {e}")
        
        for spec_file in self.spec_directory.glob("*.json"):
            try:
                with open(spec_file, 'r') as f:
                    spec_data = json.load(f)
                    specs.append(spec_data)
            except Exception as e:
                print(f"Error loading spec file {spec_file}: {e}")
        
        return specs
    
    async def validate_spec(self, spec: Dict[str, Any]) -> ValidationResult:
        """
        Validate job specification against schema and business rules.
        
        Args:
            spec: Job specification dictionary
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        job_id = spec.get('job_id', 'unknown')
        
        try:
            # First, try to create JobSpec object (validates Pydantic schema)
            job_spec = JobSpec(**spec)
            
            # Business rule validations
            await self._validate_business_rules(job_spec, errors, warnings)
            
        except ValidationError as e:
            # Pydantic validation errors
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                errors.append(f"Field '{field}': {error['msg']}")
        except Exception as e:
            errors.append(f"Unexpected validation error: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            job_id=job_id
        )
    
    async def _validate_business_rules(self, spec: JobSpec, errors: List[str], warnings: List[str]):
        """Validate business-specific rules for job specifications."""
        
        # Validate artifact exists
        if not os.path.exists(spec.artifact_path):
            errors.append(f"Artifact file not found: {spec.artifact_path}")
        
        # Validate parallelism
        if spec.parallelism < 1:
            errors.append("Parallelism must be greater than 0")
        elif spec.parallelism > 100:
            warnings.append("High parallelism (>100) may impact cluster performance")
        
        # Validate memory allocation
        memory_value = self._parse_memory_string(spec.memory)
        if memory_value < 512:  # Less than 512MB
            warnings.append("Low memory allocation may cause job failures")
        elif memory_value > 8192:  # More than 8GB
            warnings.append("High memory allocation may impact cluster resources")
        
        # Streaming-specific validations
        if spec.job_type == JobType.STREAMING:
            if spec.checkpoint_interval and spec.checkpoint_interval < 10000:  # Less than 10 seconds
                warnings.append("Very short checkpoint interval may impact performance")
            
            if not spec.checkpoint_interval:
                warnings.append("No checkpoint interval specified for streaming job")
        
        # Validate restart strategy
        valid_strategies = ["fixed-delay", "exponential-delay", "failure-rate"]
        if spec.restart_strategy not in valid_strategies:
            errors.append(f"Invalid restart strategy: {spec.restart_strategy}")
        
        # Validate CPU cores
        if spec.cpu_cores < 1:
            errors.append("CPU cores must be greater than 0")
        elif spec.cpu_cores > 16:
            warnings.append("High CPU allocation may impact cluster resources")
    
    def _parse_memory_string(self, memory_str: str) -> int:
        """Parse memory string (e.g., '1g', '512m') to MB."""
        memory_str = memory_str.lower().strip()
        
        if memory_str.endswith('g'):
            return int(memory_str[:-1]) * 1024
        elif memory_str.endswith('m'):
            return int(memory_str[:-1])
        elif memory_str.endswith('k'):
            return int(memory_str[:-1]) // 1024
        else:
            # Assume bytes, convert to MB
            return int(memory_str) // (1024 * 1024)
    
    async def get_job_status(self, job_id: str, flink_client=None) -> Optional[Dict[str, Any]]:
        """
        Get current status of a job from Flink cluster.
        
        Args:
            job_id: Job identifier
            flink_client: Flink REST API client
            
        Returns:
            Job status information or None if not found
        """
        if not flink_client:
            return None
        
        try:
            # This would call the Flink REST API
            # For now, return mock status
            return {
                "job_id": job_id,
                "flink_job_id": f"flink-{job_id}",
                "state": "RUNNING",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "parallelism": 1,
                "checkpoints": {
                    "count": 10,
                    "last_checkpoint": datetime.now(timezone.utc).isoformat()
                }
            }
        except Exception as e:
            print(f"Error getting job status for {job_id}: {e}")
            return None
    
    async def save_spec(self, spec: JobSpec, persist_to_file: bool = True) -> bool:
        """
        Save job specification to cache and optionally to file.
        
        Args:
            spec: Job specification to save
            persist_to_file: Whether to persist to filesystem
            
        Returns:
            True if saved successfully
        """
        try:
            # Update cache
            self._spec_cache[spec.job_id] = spec
            
            # Save to database if available
            if self.database:
                await self._save_spec_to_database(spec)
            
            # Save to file if requested
            if persist_to_file:
                await self._save_spec_to_file(spec)
            
            return True
        except Exception as e:
            print(f"Error saving spec for job {spec.job_id}: {e}")
            return False
    
    async def _save_spec_to_database(self, spec: JobSpec):
        """Save job specification to database."""
        # This would implement actual database saving
        pass
    
    async def _save_spec_to_file(self, spec: JobSpec):
        """Save job specification to YAML file."""
        self.spec_directory.mkdir(parents=True, exist_ok=True)
        
        spec_file = self.spec_directory / f"{spec.job_id}.yaml"
        spec_dict = spec.dict()
        
        # Convert enums to strings for YAML serialization
        if isinstance(spec_dict.get('job_type'), JobType):
            spec_dict['job_type'] = spec_dict['job_type'].value
        
        with open(spec_file, 'w') as f:
            yaml.dump(spec_dict, f, default_flow_style=False, indent=2)
    
    async def delete_spec(self, job_id: str, delete_file: bool = True) -> bool:
        """
        Delete job specification from cache and optionally from file.
        
        Args:
            job_id: Job identifier
            delete_file: Whether to delete from filesystem
            
        Returns:
            True if deleted successfully
        """
        try:
            # Remove from cache
            self._spec_cache.pop(job_id, None)
            
            # Delete from database if available
            if self.database:
                await self._delete_spec_from_database(job_id)
            
            # Delete file if requested
            if delete_file:
                spec_file = self.spec_directory / f"{job_id}.yaml"
                if spec_file.exists():
                    spec_file.unlink()
            
            return True
        except Exception as e:
            print(f"Error deleting spec for job {job_id}: {e}")
            return False
    
    async def _delete_spec_from_database(self, job_id: str):
        """Delete job specification from database."""
        # This would implement actual database deletion
        pass
    
    def get_cached_spec(self, job_id: str) -> Optional[JobSpec]:
        """Get job specification from cache."""
        return self._spec_cache.get(job_id)
    
    def get_all_cached_specs(self) -> Dict[str, JobSpec]:
        """Get all cached job specifications."""
        return self._spec_cache.copy()
    
    async def has_spec_changed(self, job_id: str, new_spec_hash: str) -> bool:
        """
        Check if job specification has changed by comparing hashes.
        
        Args:
            job_id: Job identifier
            new_spec_hash: Hash of the new specification
            
        Returns:
            True if specification has changed
        """
        cached_spec = self.get_cached_spec(job_id)
        if not cached_spec:
            return True  # No cached spec means it's new/changed
        
        return cached_spec.spec_hash() != new_spec_hash
    
    async def create_sample_spec(self, job_id: str, job_type: JobType = JobType.STREAMING) -> JobSpec:
        """
        Create a sample job specification for testing/development.
        
        Args:
            job_id: Job identifier
            job_type: Type of job to create
            
        Returns:
            Sample job specification
        """
        base_config = {
            "job_id": job_id,
            "job_type": job_type,
            "artifact_path": f"/artifacts/{job_id}.jar",
            "parallelism": 2,
            "memory": "1g",
            "cpu_cores": 1,
            "restart_strategy": "fixed-delay",
            "max_restart_attempts": 3
        }
        
        if job_type == JobType.STREAMING:
            base_config.update({
                "checkpoint_interval": 60000,
                "savepoint_trigger_interval": 300000,
                "checkpoint_timeout": 60000
            })
        
        return JobSpec(**base_config)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded job specifications."""
        total_specs = len(self._spec_cache)
        streaming_count = sum(1 for spec in self._spec_cache.values() if spec.job_type == JobType.STREAMING)
        batch_count = total_specs - streaming_count
        
        return {
            "total_specs": total_specs,
            "streaming_jobs": streaming_count,
            "batch_jobs": batch_count,
            "last_load_time": self._last_load_time.isoformat() if self._last_load_time else None,
            "cache_size": len(self._spec_cache)
        }