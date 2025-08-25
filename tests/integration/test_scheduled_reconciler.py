"""
Integration tests for ScheduledJobReconciler.

Tests the integration between the reconciler and scheduled job management.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.reconciler import (JobSpec, JobState, JobType,
                                 ScheduledJobReconciler)
from src.core.scheduler import ScheduledJobManager, ScheduledJobSpec
from src.core.types import safe_cast_cron_expression, safe_cast_job_id


class MockFlinkClient:
    """Mock Flink client for testing."""

    def __init__(self):
        self.jobs = {}
        self.health = True

    async def health_check(self):
        return self.health

    async def get_job_id_by_name(self, job_name):
        return self.jobs.get(job_name, {}).get("id")

    async def get_job_details(self, job_id):
        for job_name, job_info in self.jobs.items():
            if job_info["id"] == job_id:
                return {"state": job_info.get("state", "RUNNING")}
        return {"state": "UNKNOWN"}

    async def deploy_job(self, artifact_path, config):
        job_id = f"flink_job_{len(self.jobs)}"
        self.jobs[config.get("job_name", "test_job")] = {
            "id": job_id,
            "state": "RUNNING",
        }
        return job_id


class TestScheduledJobReconciler:
    """Test integration between reconciler and scheduler."""

    @pytest.fixture
    def mock_flink_client(self):
        return MockFlinkClient()

    @pytest.fixture
    def scheduled_reconciler(self, mock_flink_client):
        # Create mock dependencies
        from src.core.reconciler import (ReconciliationAction,
                                         ReconciliationResult)

        reconciler = ScheduledJobReconciler(flink_client=mock_flink_client)

        # Mock the reconcile_job method to return success
        async def mock_reconcile_job(spec):
            return ReconciliationResult(
                job_id=spec.job_id,
                success=True,
                action_taken=ReconciliationAction.DEPLOY,
                duration_ms=100,
                message="Job deployed successfully",
                error_code=None,
            )

        reconciler.reconcile_job = mock_reconcile_job
        return reconciler

    @pytest.fixture
    def scheduled_job_spec(self):
        return ScheduledJobSpec(
            job_id="test_scheduled_job",
            job_type=JobType.BATCH,
            artifact_path="s3://bucket/job.jar",
            parallelism=2,
            memory="2g",
            cpu_cores=2,
            cron_expression="0 0 * * *",  # Daily at midnight
            timezone="UTC",
            max_executions=10,
            execution_timeout=3600,
        )

    @pytest.mark.asyncio
    async def test_execute_job_with_scheduled_spec(
        self, scheduled_reconciler, scheduled_job_spec, mock_flink_client
    ):
        """Test executing a scheduled job spec."""
        # Mock successful deployment
        mock_flink_client.deploy_job = AsyncMock(return_value="flink_job_123")

        # Execute the scheduled job
        success = await scheduled_reconciler.execute_job(scheduled_job_spec)

        assert success is True

    @pytest.mark.asyncio
    async def test_get_job_status(self, scheduled_reconciler, mock_flink_client):
        """Test getting job status."""
        job_id = safe_cast_job_id("test_job")

        # Setup mock job
        mock_flink_client.jobs["test_job"] = {"id": "flink_123", "state": "RUNNING"}

        status = await scheduled_reconciler.get_job_status(job_id)
        assert status == JobState.RUNNING

    @pytest.mark.asyncio
    async def test_scheduler_manager_integration(self, scheduled_reconciler):
        """Test integration with ScheduledJobManager."""
        # Create scheduler manager
        scheduler_manager = ScheduledJobManager(scheduled_reconciler, check_interval=1)
        scheduled_reconciler.set_scheduler_manager(scheduler_manager)

        # Test scheduler operations
        await scheduled_reconciler.start_scheduled_jobs()

        # Test getting empty results
        jobs = scheduled_reconciler.get_scheduled_jobs()
        stats = scheduled_reconciler.get_scheduler_statistics()
        history = scheduled_reconciler.get_execution_history("test_job")

        assert isinstance(jobs, dict)
        assert isinstance(stats, dict)
        assert isinstance(history, list)

        await scheduled_reconciler.stop_scheduled_jobs()

    @pytest.mark.asyncio
    async def test_add_remove_scheduled_job(
        self, scheduled_reconciler, scheduled_job_spec
    ):
        """Test adding and removing scheduled jobs."""
        # Create scheduler manager
        scheduler_manager = ScheduledJobManager(scheduled_reconciler, check_interval=1)
        scheduled_reconciler.set_scheduler_manager(scheduler_manager)

        # Add scheduled job
        success = await scheduled_reconciler.add_scheduled_job(scheduled_job_spec)
        assert success is True

        # Remove scheduled job
        success = await scheduled_reconciler.remove_scheduled_job("test_scheduled_job")
        assert success is True

    @pytest.mark.asyncio
    async def test_scheduled_execution_flow(
        self, scheduled_reconciler, scheduled_job_spec, mock_flink_client
    ):
        """Test full scheduled execution flow."""
        # Create scheduler manager with short interval for testing
        scheduler_manager = ScheduledJobManager(scheduled_reconciler, check_interval=1)
        scheduled_reconciler.set_scheduler_manager(scheduler_manager)

        # Mock successful deployment
        mock_flink_client.deploy_job = AsyncMock(return_value="flink_job_456")

        # Start scheduler
        await scheduled_reconciler.start_scheduled_jobs()

        # Create a job that runs every minute (for testing)
        test_spec = ScheduledJobSpec(
            job_id="minute_job",
            job_type=JobType.BATCH,
            artifact_path="s3://bucket/job.jar",
            parallelism=1,
            memory="1g",
            cpu_cores=1,
            cron_expression="* * * * *",  # Every minute
            timezone="UTC",
        )

        # Add the scheduled job
        success = await scheduled_reconciler.add_scheduled_job(test_spec)
        assert success is True

        # Let scheduler run briefly
        await asyncio.sleep(0.1)

        # Check that job was added
        jobs = scheduled_reconciler.get_scheduled_jobs()
        assert "minute_job" in jobs

        # Stop scheduler
        await scheduled_reconciler.stop_scheduled_jobs()

    @pytest.mark.asyncio
    async def test_no_scheduler_manager(self, scheduled_reconciler):
        """Test operations when no scheduler manager is set."""
        # All operations should return default values
        jobs = scheduled_reconciler.get_scheduled_jobs()
        stats = scheduled_reconciler.get_scheduler_statistics()
        history = scheduled_reconciler.get_execution_history("test")

        assert jobs == {}
        assert stats == {}
        assert history == []

        # Operations should return False
        success1 = await scheduled_reconciler.add_scheduled_job(None)
        success2 = await scheduled_reconciler.remove_scheduled_job("test")

        assert success1 is False
        assert success2 is False

    @pytest.mark.asyncio
    async def test_error_handling_in_execute_job(
        self, scheduled_reconciler, scheduled_job_spec
    ):
        """Test error handling in job execution."""
        # Mock reconcile_job to raise an exception
        scheduled_reconciler.reconcile_job = AsyncMock(
            side_effect=Exception("Test error")
        )

        success = await scheduled_reconciler.execute_job(scheduled_job_spec)
        assert success is False

    @pytest.mark.asyncio
    async def test_error_handling_in_get_job_status(
        self, scheduled_reconciler, mock_flink_client
    ):
        """Test error handling in get job status."""
        job_id = safe_cast_job_id("error_job")

        # Mock client method to raise exception
        mock_flink_client.get_job_id_by_name = AsyncMock(
            side_effect=Exception("Connection error")
        )

        status = await scheduled_reconciler.get_job_status(job_id)
        assert status == JobState.UNKNOWN
