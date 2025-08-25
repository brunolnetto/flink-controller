"""
Comprehensive job type support for Flink Job Controller.

This module provides support for various job types beyond basic streaming:
- Scheduled batch jobs with cron expressions
- Job templates and parameterization
- Job pipelines with dependencies
- Multi-artifact jobs
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, validator
import croniter

from .reconciler import JobSpec, JobType


class DependencyType(Enum):
    """Types of job dependencies."""
    SEQUENTIAL = "sequential"      # Must complete in order
    PARALLEL = "parallel"          # Can run concurrently
    CONDITIONAL = "conditional"    # Depends on condition


class WaitStrategy(Enum):
    """Strategies for waiting on dependencies."""
    COMPLETION = "completion"      # Wait for successful completion
    START = "start"               # Wait for job to start
    FAILURE = "failure"           # Wait for job to fail (error handling)


class JobTemplate(BaseModel):
    """Template for parameterized jobs."""
    
    template_id: str = Field(..., description="Unique template identifier")
    template_name: str = Field(..., description="Human-readable template name")
    description: Optional[str] = Field(None, description="Template description")
    
    # Base job specification
    base_spec: Dict[str, Any] = Field(..., description="Base job specification")
    
    # Parameters that can be substituted
    parameters: Dict[str, str] = Field(default_factory=dict, description="Template parameters")
    
    # Parameter validation rules
    parameter_schema: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, 
        description="JSON schema for parameter validation"
    )
    
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Template creation time"
    )
    
    def render(self, parameters: Dict[str, str]) -> Dict[str, Any]:
        """Render template with provided parameters."""
        rendered_spec = self.base_spec.copy()
        
        # Simple parameter substitution (in production, use proper templating engine)
        for key, value in parameters.items():
            if key in self.parameters:
                self._substitute_in_dict(rendered_spec, f"${{{key}}}", value)
        
        return rendered_spec
    
    def _substitute_in_dict(self, data: Any, placeholder: str, value: str) -> None:
        """Recursively substitute placeholders in dictionary."""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str) and placeholder in v:
                    data[k] = v.replace(placeholder, value)
                else:
                    self._substitute_in_dict(v, placeholder, value)
        elif isinstance(data, list):
            for item in data:
                self._substitute_in_dict(item, placeholder, value)


class JobDependency(BaseModel):
    """Defines dependency between jobs."""
    
    depends_on: List[str] = Field(..., description="Job IDs this job depends on")
    dependency_type: DependencyType = Field(
        default=DependencyType.SEQUENTIAL, 
        description="Type of dependency"
    )
    wait_strategy: WaitStrategy = Field(
        default=WaitStrategy.COMPLETION, 
        description="How to wait for dependencies"
    )
    timeout_seconds: Optional[int] = Field(None, description="Timeout for dependency wait")
    
    # Conditional dependencies
    condition: Optional[str] = Field(None, description="Condition expression for conditional dependencies")


class ScheduledJobSpec(JobSpec):
    """Job specification for scheduled batch jobs."""
    
    # Override job type to be batch scheduled
    job_type: JobType = Field(default=JobType.BATCH, description="Job type (must be batch)")
    
    # Scheduling configuration
    schedule: str = Field(..., description="Cron expression for scheduling")
    timezone: str = Field(default="UTC", description="Timezone for schedule")
    
    # Execution control
    max_runs: Optional[int] = Field(None, description="Maximum number of runs (None = unlimited)")
    ttl_seconds: Optional[int] = Field(None, description="Job time-to-live in seconds")
    cleanup_on_completion: bool = Field(default=True, description="Clean up job after completion")
    
    # Failure handling
    retry_on_failure: bool = Field(default=True, description="Retry job on failure")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=300, description="Delay between retries")
    
    # Execution history tracking
    last_run_at: Optional[str] = Field(None, description="Last execution time")
    next_run_at: Optional[str] = Field(None, description="Next scheduled execution time")
    run_count: int = Field(default=0, description="Number of times job has been executed")
    
    @validator('schedule')
    def validate_cron_expression(cls, v):
        """Validate that schedule is a valid cron expression."""
        try:
            croniter.croniter(v)
            return v
        except ValueError as e:
            raise ValueError(f"Invalid cron expression: {e}")
    
    def get_next_run_time(self, from_time: Optional[datetime] = None) -> datetime:
        """Get next scheduled run time."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        
        cron = croniter.croniter(self.schedule, from_time)
        return cron.get_next(datetime)
    
    def should_run_now(self) -> bool:
        """Check if job should run now based on schedule."""
        if self.max_runs and self.run_count >= self.max_runs:
            return False
        
        next_run = self.get_next_run_time()
        return datetime.now(timezone.utc) >= next_run


class PipelineJobSpec(JobSpec):
    """Job specification for pipeline jobs with dependencies."""
    
    # Pipeline configuration
    pipeline_id: str = Field(..., description="Pipeline identifier")
    stage: str = Field(..., description="Pipeline stage name")
    
    # Dependencies
    dependencies: List[JobDependency] = Field(
        default_factory=list, 
        description="Job dependencies"
    )
    
    # Pipeline-specific settings
    fail_pipeline_on_failure: bool = Field(
        default=True, 
        description="Fail entire pipeline if this job fails"
    )
    pipeline_timeout_seconds: Optional[int] = Field(
        None, 
        description="Timeout for entire pipeline"
    )
    
    def has_dependencies(self) -> bool:
        """Check if job has dependencies."""
        return len(self.dependencies) > 0
    
    def get_dependency_job_ids(self) -> List[str]:
        """Get all job IDs this job depends on."""
        job_ids = []
        for dep in self.dependencies:
            job_ids.extend(dep.depends_on)
        return list(set(job_ids))  # Remove duplicates


class MultiArtifactJobSpec(JobSpec):
    """Job specification for jobs with multiple artifacts."""
    
    # Override single artifact path with multiple
    artifact_paths: List[str] = Field(..., description="Paths to job artifacts")
    
    # Artifact configuration
    main_artifact_index: int = Field(default=0, description="Index of main artifact")
    artifact_order: List[int] = Field(
        default_factory=list, 
        description="Order of artifact loading"
    )
    
    # Artifact-specific configurations
    artifact_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-artifact configurations"
    )
    
    @validator('artifact_paths')
    def validate_artifact_paths(cls, v):
        """Validate that at least one artifact path is provided."""
        if not v:
            raise ValueError("At least one artifact path must be provided")
        return v
    
    @validator('main_artifact_index')
    def validate_main_artifact_index(cls, v, values):
        """Validate main artifact index is within bounds."""
        if 'artifact_paths' in values:
            artifact_paths = values['artifact_paths']
            if v >= len(artifact_paths):
                raise ValueError(f"Main artifact index {v} is out of bounds for {len(artifact_paths)} artifacts")
        return v
    
    def get_main_artifact_path(self) -> str:
        """Get path to main artifact."""
        return self.artifact_paths[self.main_artifact_index]
    
    def get_ordered_artifact_paths(self) -> List[str]:
        """Get artifacts in specified loading order."""
        if not self.artifact_order:
            return self.artifact_paths
        
        ordered_paths = []
        for index in self.artifact_order:
            if 0 <= index < len(self.artifact_paths):
                ordered_paths.append(self.artifact_paths[index])
        
        return ordered_paths


class TemplateJobSpec(BaseModel):
    """Job specification created from a template."""
    
    template_id: str = Field(..., description="Template used to create this job")
    job_id: str = Field(..., description="Unique job identifier") 
    parameters: Dict[str, str] = Field(..., description="Parameters used to render template")
    
    # Rendered job specification
    rendered_spec: Dict[str, Any] = Field(..., description="Rendered job specification")
    
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Job creation time"
    )
    
    def to_job_spec(self) -> JobSpec:
        """Convert to standard JobSpec."""
        return JobSpec(**self.rendered_spec)


class JobTypeManager:
    """Manager for different job types and their specifications."""
    
    def __init__(self):
        self._templates: Dict[str, JobTemplate] = {}
        self._pipelines: Dict[str, List[PipelineJobSpec]] = {}
        self._scheduled_jobs: Dict[str, ScheduledJobSpec] = {}
    
    def register_template(self, template: JobTemplate) -> None:
        """Register a job template."""
        self._templates[template.template_id] = template
    
    def create_job_from_template(
        self, 
        template_id: str, 
        job_id: str, 
        parameters: Dict[str, str]
    ) -> TemplateJobSpec:
        """Create a job from a template."""
        if template_id not in self._templates:
            raise ValueError(f"Template {template_id} not found")
        
        template = self._templates[template_id]
        rendered_spec = template.render(parameters)
        rendered_spec['job_id'] = job_id
        
        return TemplateJobSpec(
            template_id=template_id,
            job_id=job_id,
            parameters=parameters,
            rendered_spec=rendered_spec
        )
    
    def register_scheduled_job(self, job_spec: ScheduledJobSpec) -> None:
        """Register a scheduled job."""
        self._scheduled_jobs[job_spec.job_id] = job_spec
    
    def get_jobs_ready_to_run(self) -> List[ScheduledJobSpec]:
        """Get scheduled jobs that are ready to run."""
        ready_jobs = []
        now = datetime.now(timezone.utc)
        
        for job_spec in self._scheduled_jobs.values():
            if job_spec.should_run_now():
                ready_jobs.append(job_spec)
        
        return ready_jobs
    
    def register_pipeline(self, pipeline_id: str, jobs: List[PipelineJobSpec]) -> None:
        """Register a job pipeline."""
        self._pipelines[pipeline_id] = jobs
    
    def get_pipeline_execution_order(self, pipeline_id: str) -> List[List[str]]:
        """Get execution order for pipeline jobs."""
        if pipeline_id not in self._pipelines:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        jobs = self._pipelines[pipeline_id]
        
        # Simple topological sort for dependency resolution
        execution_stages = []
        remaining_jobs = {job.job_id: job for job in jobs}
        completed_jobs = set()
        
        while remaining_jobs:
            # Find jobs with no unsatisfied dependencies
            ready_jobs = []
            for job_id, job in remaining_jobs.items():
                dependencies = job.get_dependency_job_ids()
                if all(dep_id in completed_jobs for dep_id in dependencies):
                    ready_jobs.append(job_id)
            
            if not ready_jobs:
                # Circular dependency or unsatisfied dependency
                remaining_job_ids = list(remaining_jobs.keys())
                raise ValueError(f"Circular or unsatisfied dependencies in pipeline {pipeline_id}: {remaining_job_ids}")
            
            execution_stages.append(ready_jobs)
            
            # Mark these jobs as completed for next iteration
            for job_id in ready_jobs:
                completed_jobs.add(job_id)
                del remaining_jobs[job_id]
        
        return execution_stages
    
    def get_template(self, template_id: str) -> Optional[JobTemplate]:
        """Get a job template by ID."""
        return self._templates.get(template_id)
    
    def get_scheduled_job(self, job_id: str) -> Optional[ScheduledJobSpec]:
        """Get a scheduled job by ID."""
        return self._scheduled_jobs.get(job_id)
    
    def get_pipeline_jobs(self, pipeline_id: str) -> Optional[List[PipelineJobSpec]]:
        """Get all jobs in a pipeline."""
        return self._pipelines.get(pipeline_id)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about registered job types."""
        return {
            "templates": len(self._templates),
            "scheduled_jobs": len(self._scheduled_jobs),
            "pipelines": len(self._pipelines),
            "total_pipeline_jobs": sum(len(jobs) for jobs in self._pipelines.values())
        }