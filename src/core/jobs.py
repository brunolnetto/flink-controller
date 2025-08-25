"""
Strictly typed job specification manager.

This module eliminates all 'Any' types and provides complete type safety
for job specification management operations.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol

import yaml
from pydantic import BaseModel, Field, ValidationError

from .reconciler import JobSpec, JobState, JobType
from .types import (ArtifactPath, DatabaseRecordDict, JobId, JobSpecDict,
                    ValidationErrorDict, is_valid_artifact_path,
                    is_valid_job_id, is_valid_memory_string,
                    safe_cast_artifact_path, safe_cast_job_id)


class DatabaseProtocol(Protocol):
    """Protocol for database operations with strict typing."""

    async def save_spec(self, job_id: JobId, spec_data: JobSpecDict) -> bool:
        """Save job specification to database."""
        ...

    async def load_spec(self, job_id: JobId) -> Optional[JobSpecDict]:
        """Load job specification from database."""
        ...

    async def load_all_specs(self) -> List[JobSpecDict]:
        """Load all job specifications from database."""
        ...

    async def delete_spec(self, job_id: JobId) -> bool:
        """Delete job specification from database."""
        ...


class FlinkStatusProtocol(Protocol):
    """Protocol for Flink status operations with strict typing."""

    async def get_job_status(self, job_id: JobId) -> Optional[Dict[str, str]]:
        """Get job status from Flink cluster."""
        ...


class ValidationResult(BaseModel):
    """Strictly typed validation result."""

    valid: bool = Field(..., description="Whether the spec is valid")
    errors: List[ValidationErrorDict] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: List[ValidationErrorDict] = Field(
        default_factory=list, description="Validation warnings"
    )
    job_id: Optional[JobId] = Field(None, description="Job ID being validated")


class JobSpecManager:
    """Strictly typed job specification manager."""

    def __init__(
        self,
        spec_directory: str = "job-specs",
        database: Optional[DatabaseProtocol] = None,
    ):
        """
        Initialize job specification manager with strict typing.

        Args:
            spec_directory: Directory containing job specification files
            database: Database connection for persistent storage
        """
        self._spec_directory = Path(spec_directory)
        self._database = database
        self._spec_cache: Dict[JobId, JobSpec] = {}
        self._last_load_time: Optional[datetime] = None

    async def load_all_specs(self) -> List[JobSpec]:
        """
        Load and validate all job specifications with strict typing.

        Returns:
            List of validated job specifications

        Raises:
            ValueError: If any spec has invalid format
            FileNotFoundError: If spec directory doesn't exist
        """
        specs: List[JobSpecDict] = []

        # Load from database if available
        if self._database:
            db_specs = await self._database.load_all_specs()
            specs.extend(db_specs)

        # Load from filesystem
        file_specs = await self._load_specs_from_files()
        specs.extend(file_specs)

        # Convert to JobSpec objects with validation
        validated_specs: List[JobSpec] = []
        for spec_dict in specs:
            validation_result = await self.validate_spec(spec_dict)
            if validation_result.valid:
                try:
                    job_spec = self._convert_dict_to_jobspec(spec_dict)
                    validated_specs.append(job_spec)
                except Exception as e:
                    raise ValueError(
                        f"Failed to create JobSpec from {spec_dict.get('job_id', 'unknown')}: {e}"
                    )
            else:
                error_messages = [
                    f"{err['field']}: {err['message']}"
                    for err in validation_result.errors
                ]
                raise ValueError(
                    f"Invalid spec for job {validation_result.job_id}: {error_messages}"
                )

        # Update cache with strict typing
        self._spec_cache = {
            safe_cast_job_id(spec.job_id): spec for spec in validated_specs
        }
        self._last_load_time = datetime.now(timezone.utc)

        return validated_specs

    async def _load_specs_from_files(self) -> List[JobSpecDict]:
        """Load job specifications from filesystem with strict typing."""
        specs: List[JobSpecDict] = []

        if not self._spec_directory.exists():
            raise FileNotFoundError(
                f"Spec directory {self._spec_directory} does not exist"
            )

        # Load YAML files
        for spec_file in self._spec_directory.glob("*.yaml"):
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    spec_data = yaml.safe_load(f)
                    validated_spec = self._validate_spec_dict_structure(
                        spec_data, spec_file.name
                    )
                    specs.append(validated_spec)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {spec_file}: {e}")
            except Exception as e:
                raise ValueError(f"Error loading spec file {spec_file}: {e}")

        # Load JSON files
        for spec_file in self._spec_directory.glob("*.json"):
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    spec_data = json.load(f)
                    validated_spec = self._validate_spec_dict_structure(
                        spec_data, spec_file.name
                    )
                    specs.append(validated_spec)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {spec_file}: {e}")
            except Exception as e:
                raise ValueError(f"Error loading spec file {spec_file}: {e}")

        return specs

    def _validate_spec_dict_structure(self, data: dict, filename: str) -> JobSpecDict:
        """Validate and convert generic dict to strictly typed JobSpecDict."""
        if not isinstance(data, dict):
            raise ValueError(f"Spec file {filename} must contain a dictionary")

        # Extract required fields with type checking
        job_id = data.get("job_id")
        if not isinstance(job_id, str) or not is_valid_job_id(job_id):
            raise ValueError(f"Invalid job_id in {filename}: {job_id}")

        job_type = data.get("job_type")
        if not isinstance(job_type, str) or job_type not in ["streaming", "batch"]:
            raise ValueError(f"Invalid job_type in {filename}: {job_type}")

        artifact_path = data.get("artifact_path")
        if not isinstance(artifact_path, str) or not is_valid_artifact_path(
            artifact_path
        ):
            raise ValueError(f"Invalid artifact_path in {filename}: {artifact_path}")

        # Build strictly typed dict
        spec_dict: JobSpecDict = {
            "job_id": job_id,
            "job_type": job_type,
            "artifact_path": artifact_path,
        }

        # Optional fields with type validation
        if "parallelism" in data:
            parallelism = data["parallelism"]
            if not isinstance(parallelism, int) or parallelism < 1:
                raise ValueError(f"Invalid parallelism in {filename}: {parallelism}")
            spec_dict["parallelism"] = parallelism

        if "checkpoint_interval" in data:
            interval = data["checkpoint_interval"]
            if not isinstance(interval, int) or interval < 1000:
                raise ValueError(
                    f"Invalid checkpoint_interval in {filename}: {interval}"
                )
            spec_dict["checkpoint_interval"] = interval

        if "memory" in data:
            memory = data["memory"]
            if not isinstance(memory, str) or not is_valid_memory_string(memory):
                raise ValueError(
                    f"Invalid memory specification in {filename}: {memory}"
                )
            spec_dict["memory"] = memory

        if "cpu_cores" in data:
            cpu_cores = data["cpu_cores"]
            if not isinstance(cpu_cores, int) or cpu_cores < 1:
                raise ValueError(f"Invalid cpu_cores in {filename}: {cpu_cores}")
            spec_dict["cpu_cores"] = cpu_cores

        return spec_dict

    def _convert_dict_to_jobspec(self, spec_dict: JobSpecDict) -> JobSpec:
        """Convert JobSpecDict to JobSpec with proper type conversion."""
        # Handle job type enum conversion
        job_type = (
            JobType.STREAMING if spec_dict["job_type"] == "streaming" else JobType.BATCH
        )

        return JobSpec(
            job_id=spec_dict["job_id"],
            job_type=job_type,
            artifact_path=spec_dict["artifact_path"],
            parallelism=spec_dict.get("parallelism", 1),
            checkpoint_interval=spec_dict.get("checkpoint_interval"),
            savepoint_path=spec_dict.get("savepoint_path"),
            restart_strategy=spec_dict.get("restart_strategy", "fixed-delay"),
            max_restart_attempts=spec_dict.get("max_restart_attempts", 3),
            memory=spec_dict.get("memory", "1g"),
            cpu_cores=spec_dict.get("cpu_cores", 1),
            savepoint_trigger_interval=spec_dict.get("savepoint_trigger_interval"),
            checkpoint_timeout=spec_dict.get("checkpoint_timeout"),
        )

    async def validate_spec(self, spec_dict: JobSpecDict) -> ValidationResult:
        """
        Validate job specification with strict typing.

        Args:
            spec_dict: Strictly typed job specification dictionary

        Returns:
            Validation result with typed errors and warnings
        """
        errors: List[ValidationErrorDict] = []
        warnings: List[ValidationErrorDict] = []
        job_id_str = spec_dict.get("job_id", "unknown")
        job_id: Optional[JobId] = None

        try:
            job_id = safe_cast_job_id(job_id_str) if job_id_str != "unknown" else None

            # Create JobSpec to leverage Pydantic validation
            job_spec = self._convert_dict_to_jobspec(spec_dict)

            # Business rule validations with strict typing
            await self._validate_business_rules(job_spec, errors, warnings)

        except ValidationError as e:
            # Convert Pydantic errors to our typed format
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                errors.append(
                    ValidationErrorDict(
                        field=field,
                        message=error["msg"],
                        invalid_value=str(error.get("input", "")),
                    )
                )
        except ValueError as e:
            errors.append(
                ValidationErrorDict(
                    field="general", message=str(e), invalid_value=job_id_str
                )
            )
        except Exception as e:
            errors.append(
                ValidationErrorDict(
                    field="unexpected",
                    message=f"Unexpected validation error: {str(e)}",
                    invalid_value=job_id_str,
                )
            )

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, job_id=job_id
        )

    async def _validate_business_rules(
        self,
        spec: JobSpec,
        errors: List[ValidationErrorDict],
        warnings: List[ValidationErrorDict],
    ) -> None:
        """Validate business-specific rules with strict typing."""

        # Validate artifact exists
        if not os.path.exists(spec.artifact_path):
            errors.append(
                ValidationErrorDict(
                    field="artifact_path",
                    message=f"Artifact file not found: {spec.artifact_path}",
                    invalid_value=spec.artifact_path,
                )
            )

        # Validate parallelism bounds
        if spec.parallelism < 1:
            errors.append(
                ValidationErrorDict(
                    field="parallelism",
                    message="Parallelism must be greater than 0",
                    invalid_value=str(spec.parallelism),
                )
            )
        elif spec.parallelism > 100:
            warnings.append(
                ValidationErrorDict(
                    field="parallelism",
                    message="High parallelism (>100) may impact cluster performance",
                    invalid_value=str(spec.parallelism),
                )
            )

        # Validate memory allocation with proper parsing
        memory_mb = self._parse_memory_string(spec.memory)
        if memory_mb < 512:  # Less than 512MB
            warnings.append(
                ValidationErrorDict(
                    field="memory",
                    message="Low memory allocation may cause job failures",
                    invalid_value=spec.memory,
                )
            )
        elif memory_mb > 8192:  # More than 8GB
            warnings.append(
                ValidationErrorDict(
                    field="memory",
                    message="High memory allocation may impact cluster resources",
                    invalid_value=spec.memory,
                )
            )

        # Streaming-specific validations with strict typing
        if spec.job_type == JobType.STREAMING:
            if (
                spec.checkpoint_interval and spec.checkpoint_interval < 10000
            ):  # Less than 10 seconds
                warnings.append(
                    ValidationErrorDict(
                        field="checkpoint_interval",
                        message="Very short checkpoint interval may impact performance",
                        invalid_value=str(spec.checkpoint_interval),
                    )
                )

            if not spec.checkpoint_interval:
                warnings.append(
                    ValidationErrorDict(
                        field="checkpoint_interval",
                        message="No checkpoint interval specified for streaming job",
                        invalid_value="None",
                    )
                )

        # Validate restart strategy against allowed values
        valid_strategies = ["fixed-delay", "exponential-delay", "failure-rate"]
        if spec.restart_strategy not in valid_strategies:
            errors.append(
                ValidationErrorDict(
                    field="restart_strategy",
                    message=f"Invalid restart strategy. Must be one of: {valid_strategies}",
                    invalid_value=spec.restart_strategy,
                )
            )

        # Validate CPU cores
        if spec.cpu_cores < 1:
            errors.append(
                ValidationErrorDict(
                    field="cpu_cores",
                    message="CPU cores must be greater than 0",
                    invalid_value=str(spec.cpu_cores),
                )
            )
        elif spec.cpu_cores > 16:
            warnings.append(
                ValidationErrorDict(
                    field="cpu_cores",
                    message="High CPU allocation may impact cluster resources",
                    invalid_value=str(spec.cpu_cores),
                )
            )

    def _parse_memory_string(self, memory_str: str) -> int:
        """Parse memory string (e.g., '1g', '512m') to MB with strict typing."""
        if not isinstance(memory_str, str):
            raise ValueError(f"Memory must be string, got {type(memory_str)}")

        memory_str = memory_str.lower().strip()

        if memory_str.endswith("g"):
            return int(memory_str[:-1]) * 1024
        elif memory_str.endswith("m"):
            return int(memory_str[:-1])
        elif memory_str.endswith("k"):
            return max(1, int(memory_str[:-1]) // 1024)
        else:
            # Assume bytes, convert to MB
            return max(1, int(memory_str) // (1024 * 1024))

    async def get_job_status(
        self, job_id: JobId, flink_client: Optional[FlinkStatusProtocol] = None
    ) -> Optional[Dict[str, str]]:
        """
        Get current status of a job from Flink cluster with strict typing.

        Args:
            job_id: Strictly typed job identifier
            flink_client: Flink REST API client with typed protocol

        Returns:
            Strictly typed job status information or None if not found
        """
        if not flink_client:
            return None

        try:
            status = await flink_client.get_job_status(job_id)
            if status is None:
                return None

            # Ensure return type is strictly typed
            typed_status: Dict[str, str] = {
                "job_id": str(job_id),
                "state": status.get("state", "UNKNOWN"),
                "start_time": status.get("start_time", ""),
                "parallelism": str(status.get("parallelism", "1")),
            }

            return typed_status

        except Exception as e:
            # Log error but don't raise - return None for not found
            print(f"Error getting job status for {job_id}: {e}")
            return None

    async def save_spec(self, spec: JobSpec, persist_to_file: bool = True) -> bool:
        """
        Save job specification with strict typing.

        Args:
            spec: Job specification to save
            persist_to_file: Whether to persist to filesystem

        Returns:
            True if saved successfully

        Raises:
            ValueError: If spec is invalid
        """
        try:
            # Validate job ID
            job_id = safe_cast_job_id(spec.job_id)

            # Update cache with strict typing
            self._spec_cache[job_id] = spec

            # Save to database if available
            if self._database:
                spec_dict = self._convert_jobspec_to_dict(spec)
                await self._database.save_spec(job_id, spec_dict)

            # Save to file if requested
            if persist_to_file:
                await self._save_spec_to_file(spec)

            return True

        except Exception as e:
            print(f"Error saving spec for job {spec.job_id}: {e}")
            return False

    def _convert_jobspec_to_dict(self, spec: JobSpec) -> JobSpecDict:
        """Convert JobSpec to strictly typed dictionary."""
        spec_dict: JobSpecDict = {
            "job_id": spec.job_id,
            "job_type": spec.job_type.value,
            "artifact_path": spec.artifact_path,
            "parallelism": spec.parallelism,
            "restart_strategy": spec.restart_strategy,
            "max_restart_attempts": spec.max_restart_attempts,
            "memory": spec.memory,
            "cpu_cores": spec.cpu_cores,
        }

        # Optional fields
        if spec.checkpoint_interval is not None:
            spec_dict["checkpoint_interval"] = spec.checkpoint_interval
        if spec.savepoint_path is not None:
            spec_dict["savepoint_path"] = spec.savepoint_path
        if spec.savepoint_trigger_interval is not None:
            spec_dict["savepoint_trigger_interval"] = spec.savepoint_trigger_interval
        if spec.checkpoint_timeout is not None:
            spec_dict["checkpoint_timeout"] = spec.checkpoint_timeout

        return spec_dict

    async def _save_spec_to_file(self, spec: JobSpec) -> None:
        """Save job specification to YAML file with strict typing."""
        self._spec_directory.mkdir(parents=True, exist_ok=True)

        spec_file = self._spec_directory / f"{spec.job_id}.yaml"
        spec_dict = self._convert_jobspec_to_dict(spec)

        try:
            with open(spec_file, "w", encoding="utf-8") as f:
                yaml.dump(spec_dict, f, default_flow_style=False, indent=2)
        except Exception as e:
            raise ValueError(f"Failed to save spec to {spec_file}: {e}")

    def get_cached_spec(self, job_id: str) -> Optional[JobSpec]:
        """Get job specification from cache with strict typing."""
        try:
            typed_job_id = safe_cast_job_id(job_id)
            return self._spec_cache.get(typed_job_id)
        except ValueError:
            return None

    def get_all_cached_specs(self) -> Dict[JobId, JobSpec]:
        """Get all cached job specifications with strict typing."""
        return self._spec_cache.copy()

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics with strict typing - no Any types."""
        total_specs = len(self._spec_cache)
        streaming_count = sum(
            1
            for spec in self._spec_cache.values()
            if spec.job_type == JobType.STREAMING
        )
        batch_count = total_specs - streaming_count

        return {
            "total_specs": total_specs,
            "streaming_jobs": streaming_count,
            "batch_jobs": batch_count,
            "cache_size": len(self._spec_cache),
        }
