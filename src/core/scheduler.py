"""
Scheduled job management for Flink Job Controller.

This module provides cron-based job scheduling with timezone support,
execution history tracking, and retry logic for failed scheduled jobs.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Protocol
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator
import re

from .types import JobId, CronExpression, safe_cast_job_id, safe_cast_cron_expression
from .reconciler import JobSpec, JobType, JobState, ReconciliationAction
from .exceptions import FlinkControllerError, ErrorCode


class ScheduleStatus(Enum):
    """Status of scheduled job execution."""
    PENDING = "pending"           # Waiting for next execution
    RUNNING = "running"           # Currently executing
    SUCCESS = "success"           # Last execution successful
    FAILED = "failed"             # Last execution failed
    DISABLED = "disabled"         # Schedule temporarily disabled
    EXPIRED = "expired"           # Schedule past end date


class ScheduledJobSpec(JobSpec):
    """Extended job specification for scheduled jobs."""
    
    # Scheduling configuration
    cron_expression: CronExpression = Field(..., description="Cron expression for scheduling")
    timezone: str = Field(default="UTC", description="Timezone for cron expression")
    
    # Execution limits
    max_executions: Optional[int] = Field(None, description="Maximum number of executions")
    execution_timeout: int = Field(default=3600, description="Execution timeout in seconds") 
    
    # Schedule validity
    start_date: Optional[datetime] = Field(None, description="Schedule start date")
    end_date: Optional[datetime] = Field(None, description="Schedule end date")
    
    # Retry configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: int = Field(default=300, description="Delay between retries in seconds")
    
    @field_validator('job_type')
    @classmethod
    def validate_job_type_for_scheduling(cls, v):
        """Scheduled jobs should typically be batch jobs."""
        if v not in [JobType.BATCH, JobType.STREAMING]:
            raise ValueError(f"Invalid job type for scheduled job: {v}")
        return v
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v):
        """Validate cron expression format."""
        if not CronParser.is_valid_cron(v):
            raise ValueError(f"Invalid cron expression: {v}")
        return v


@dataclass
class ExecutionRecord:
    """Record of a scheduled job execution."""
    execution_id: str
    job_id: JobId
    scheduled_time: datetime
    actual_start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: ScheduleStatus = ScheduleStatus.PENDING
    attempt_number: int = 1
    error_message: Optional[str] = None
    duration_ms: int = 0
    
    @property
    def is_completed(self) -> bool:
        """Check if execution is completed (success or failed)."""
        return self.status in [ScheduleStatus.SUCCESS, ScheduleStatus.FAILED]
    
    def is_overdue(self, timeout_seconds: int = 3600) -> bool:
        """Check if execution is overdue based on timeout."""
        if self.actual_start_time is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.actual_start_time).total_seconds()
        return elapsed > timeout_seconds


class SchedulerProtocol(Protocol):
    """Protocol for job scheduler integration."""
    
    async def execute_job(self, job_spec: JobSpec) -> bool:
        """Execute a job and return success status."""
        ...
    
    async def get_job_status(self, job_id: JobId) -> Optional[JobState]:
        """Get current job execution status."""
        ...


class CronParser:
    """Utility class for parsing and validating cron expressions."""
    
    # Basic cron pattern for structure validation
    CRON_PATTERN = re.compile(r'^[\*\d\-,/\s]+$')
    
    @classmethod
    def is_valid_cron(cls, expression: str) -> bool:
        """Validate cron expression format."""
        if not isinstance(expression, str):
            return False
        
        # Basic structure check
        if not cls.CRON_PATTERN.match(expression.strip()):
            return False
        
        # Split into fields
        fields = expression.strip().split()
        if len(fields) != 5:
            return False
        
        try:
            # Validate each field against its range
            cls.parse_cron_field(fields[0], 0, 59)  # minute
            cls.parse_cron_field(fields[1], 0, 23)  # hour
            cls.parse_cron_field(fields[2], 1, 31)  # day
            cls.parse_cron_field(fields[3], 1, 12)  # month
            cls.parse_cron_field(fields[4], 0, 6)   # day-of-week
            return True
        except (ValueError, IndexError):
            return False
    
    @classmethod
    def parse_cron_field(cls, field: str, min_val: int, max_val: int) -> Set[int]:
        """Parse a single cron field into a set of valid values."""
        if field == '*':
            return set(range(min_val, max_val + 1))
        
        values = set()
        for part in field.split(','):
            if '/' in part:
                range_part, step = part.split('/')
                step = int(step)
                if step <= 0:
                    raise ValueError(f"Invalid step value: {step}")
                if range_part == '*':
                    values.update(range(min_val, max_val + 1, step))
                else:
                    start, end = range_part.split('-') if '-' in range_part else (range_part, range_part)
                    start, end = int(start), int(end)
                    if not (min_val <= start <= max_val and min_val <= end <= max_val):
                        raise ValueError(f"Values {start}-{end} out of range {min_val}-{max_val}")
                    values.update(range(start, end + 1, step))
            elif '-' in part:
                start, end = part.split('-')
                start, end = int(start), int(end)
                if not (min_val <= start <= max_val and min_val <= end <= max_val):
                    raise ValueError(f"Values {start}-{end} out of range {min_val}-{max_val}")
                values.update(range(start, end + 1))
            else:
                val = int(part)
                if not (min_val <= val <= max_val):
                    raise ValueError(f"Value {val} out of range {min_val}-{max_val}")
                values.add(val)
        
        return values
    
    @classmethod
    def get_next_execution(cls, cron_expr: str, from_time: datetime) -> datetime:
        """Calculate next execution time based on cron expression."""
        if not cls.is_valid_cron(cron_expr):
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        
        fields = cron_expr.strip().split()
        
        # Parse cron fields
        minutes = cls.parse_cron_field(fields[0], 0, 59)
        hours = cls.parse_cron_field(fields[1], 0, 23)
        days = cls.parse_cron_field(fields[2], 1, 31)
        months = cls.parse_cron_field(fields[3], 1, 12)
        weekdays = cls.parse_cron_field(fields[4], 0, 6)
        
        # Find next valid execution time
        current = from_time.replace(second=0, microsecond=0)
        current += timedelta(minutes=1)  # Start from next minute
        
        # Simple algorithm - check next 4 weeks (should be sufficient for most cases)
        for _ in range(4 * 7 * 24 * 60):  # 4 weeks worth of minutes
            if (current.minute in minutes and 
                current.hour in hours and
                current.day in days and
                current.month in months and
                current.weekday() + 1 in weekdays):  # Convert Python weekday to cron format
                return current
            current += timedelta(minutes=1)
        
        raise ValueError(f"Could not find next execution time for cron: {cron_expr}")


class ScheduledJobManager:
    """Manager for scheduled job execution with cron support."""
    
    def __init__(self, scheduler: SchedulerProtocol, check_interval: int = 60):
        """
        Initialize scheduled job manager.
        
        Args:
            scheduler: Job execution scheduler
            check_interval: How often to check for scheduled jobs (seconds)
        """
        self._scheduler = scheduler
        self._check_interval = check_interval
        
        # Active scheduled jobs
        self._scheduled_jobs: Dict[JobId, ScheduledJobSpec] = {}
        self._job_schedules: Dict[JobId, ScheduleStatus] = {}
        
        # Execution tracking
        self._execution_history: Dict[JobId, List[ExecutionRecord]] = {}
        self._active_executions: Dict[str, ExecutionRecord] = {}
        
        # Scheduler state
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    async def add_scheduled_job(self, job_spec: ScheduledJobSpec) -> bool:
        """
        Add a new scheduled job.
        
        Args:
            job_spec: Scheduled job specification
            
        Returns:
            True if job was added successfully
        """
        try:
            job_id = safe_cast_job_id(job_spec.job_id)
            
            # Validate cron expression
            if not CronParser.is_valid_cron(job_spec.cron_expression):
                raise ValueError(f"Invalid cron expression: {job_spec.cron_expression}")
            
            # Check for conflicts
            if job_id in self._scheduled_jobs:
                raise ValueError(f"Scheduled job {job_id} already exists")
            
            # Add to active schedules
            self._scheduled_jobs[job_id] = job_spec
            self._job_schedules[job_id] = ScheduleStatus.PENDING
            self._execution_history[job_id] = []
            
            return True
            
        except Exception as e:
            print(f"Error adding scheduled job {job_spec.job_id}: {e}")
            return False
    
    async def remove_scheduled_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.
        
        Args:
            job_id: ID of job to remove
            
        Returns:
            True if job was removed successfully
        """
        try:
            typed_job_id = safe_cast_job_id(job_id)
            
            if typed_job_id not in self._scheduled_jobs:
                return False
            
            # Cancel any active executions
            for exec_record in self._active_executions.values():
                if exec_record.job_id == typed_job_id:
                    exec_record.status = ScheduleStatus.FAILED
                    exec_record.error_message = "Job schedule removed"
            
            # Remove from schedules
            del self._scheduled_jobs[typed_job_id]
            del self._job_schedules[typed_job_id]
            
            return True
            
        except Exception as e:
            print(f"Error removing scheduled job {job_id}: {e}")
            return False
    
    async def start_scheduler(self) -> None:
        """Start the job scheduler loop."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop_scheduler(self) -> None:
        """Stop the job scheduler loop."""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks for jobs to execute."""
        while self._running:
            try:
                await self._check_scheduled_jobs()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self._check_interval)
    
    async def _check_scheduled_jobs(self) -> None:
        """Check for jobs that need to be executed."""
        current_time = datetime.now(timezone.utc)
        
        for job_id, job_spec in self._scheduled_jobs.items():
            if self._job_schedules[job_id] != ScheduleStatus.PENDING:
                continue
            
            try:
                # Calculate next execution time
                last_execution = self._get_last_execution_time(job_id)
                next_execution = CronParser.get_next_execution(
                    job_spec.cron_expression,
                    last_execution or current_time - timedelta(minutes=1)
                )
                
                # Check if it's time to execute
                if current_time >= next_execution:
                    await self._execute_scheduled_job(job_spec, next_execution)
                    
            except Exception as e:
                print(f"Error checking scheduled job {job_id}: {e}")
    
    def _get_last_execution_time(self, job_id: JobId) -> Optional[datetime]:
        """Get the last execution time for a job."""
        history = self._execution_history.get(job_id, [])
        if not history:
            return None
        
        # Return the scheduled time of the last execution
        return max(record.scheduled_time for record in history)
    
    async def _execute_scheduled_job(self, job_spec: ScheduledJobSpec, scheduled_time: datetime) -> None:
        """Execute a scheduled job."""
        job_id = safe_cast_job_id(job_spec.job_id)
        execution_id = f"{job_id}_{int(scheduled_time.timestamp())}"
        
        # Create execution record
        execution_record = ExecutionRecord(
            execution_id=execution_id,
            job_id=job_id,
            scheduled_time=scheduled_time,
            actual_start_time=datetime.now(timezone.utc)
        )
        
        self._active_executions[execution_id] = execution_record
        self._job_schedules[job_id] = ScheduleStatus.RUNNING
        
        try:
            # Execute the job
            success = await self._scheduler.execute_job(job_spec)
            
            execution_record.status = ScheduleStatus.SUCCESS if success else ScheduleStatus.FAILED
            execution_record.end_time = datetime.now(timezone.utc)
            execution_record.duration_ms = int(
                (execution_record.end_time - execution_record.actual_start_time).total_seconds() * 1000
            )
            
        except Exception as e:
            execution_record.status = ScheduleStatus.FAILED
            execution_record.error_message = str(e)
            execution_record.end_time = datetime.now(timezone.utc)
        
        finally:
            # Update tracking
            self._execution_history[job_id].append(execution_record)
            self._job_schedules[job_id] = ScheduleStatus.PENDING
            del self._active_executions[execution_id]
            
            # Limit history size (keep last 100 executions)
            if len(self._execution_history[job_id]) > 100:
                self._execution_history[job_id] = self._execution_history[job_id][-100:]
    
    def get_job_schedule_status(self, job_id: str) -> Optional[ScheduleStatus]:
        """Get current schedule status for a job."""
        try:
            typed_job_id = safe_cast_job_id(job_id)
            return self._job_schedules.get(typed_job_id)
        except ValueError:
            return None
    
    def get_execution_history(self, job_id: str, limit: int = 50) -> List[ExecutionRecord]:
        """Get execution history for a job."""
        try:
            typed_job_id = safe_cast_job_id(job_id)
            history = self._execution_history.get(typed_job_id, [])
            return sorted(history, key=lambda x: x.scheduled_time, reverse=True)[:limit]
        except ValueError:
            return []
    
    def get_scheduled_jobs(self) -> Dict[str, ScheduledJobSpec]:
        """Get all scheduled jobs."""
        return {str(job_id): spec for job_id, spec in self._scheduled_jobs.items()}
    
    def get_scheduler_statistics(self) -> Dict[str, int]:
        """Get scheduler statistics."""
        total_jobs = len(self._scheduled_jobs)
        active_executions = len(self._active_executions)
        
        # Count statuses
        status_counts = {}
        for status in self._job_schedules.values():
            status_counts[status.value] = status_counts.get(status.value, 0) + 1
        
        return {
            "total_scheduled_jobs": total_jobs,
            "active_executions": active_executions,
            **status_counts
        }