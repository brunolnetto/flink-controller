"""
Unit tests for the job reconciler module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from src.core.reconciler import (
    JobReconciler, JobSpec, JobStatus, JobState, JobType, 
    ReconciliationAction, ReconciliationResult, Conflict, ConflictType
)


class TestJobReconciler:
    """Test cases for JobReconciler."""
    
    @pytest.fixture
    def reconciler(self):
        """Create a JobReconciler instance for testing."""
        return JobReconciler()
    
    @pytest.fixture
    def sample_streaming_spec(self):
        """Create a sample streaming job specification."""
        return JobSpec(
            job_id="test-streaming-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/streaming.jar",
            parallelism=2,
            checkpoint_interval=60000,
            savepoint_trigger_interval=300000
        )
    
    @pytest.fixture
    def sample_batch_spec(self):
        """Create a sample batch job specification."""
        return JobSpec(
            job_id="test-batch-job",
            job_type=JobType.BATCH,
            artifact_path="/path/to/batch.jar",
            parallelism=1
        )
    
    @pytest.mark.asyncio
    async def test_reconcile_job_deploy_new_job(self, reconciler, sample_streaming_spec):
        """Test reconciling a new job that needs deployment."""
        # Mock the get status method to return None (job doesn't exist)
        reconciler._get_job_status_with_circuit_breaker = AsyncMock(return_value=None)
        reconciler._deploy_job = AsyncMock(return_value=ReconciliationResult(
            job_id=sample_streaming_spec.job_id,
            action_taken=ReconciliationAction.DEPLOY,
            success=True
        ))
        
        result = await reconciler.reconcile_job(sample_streaming_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.DEPLOY
        assert result.job_id == sample_streaming_spec.job_id
        reconciler._deploy_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconcile_job_no_action_needed(self, reconciler, sample_streaming_spec):
        """Test reconciling a job that needs no action."""
        # Mock job status as running and no changes
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.RUNNING
        )
        reconciler._get_job_status_with_circuit_breaker = AsyncMock(return_value=mock_status)
        reconciler._has_spec_changed = AsyncMock(return_value=False)
        
        result = await reconciler.reconcile_job(sample_streaming_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.NO_ACTION
    
    @pytest.mark.asyncio
    async def test_reconcile_job_update_streaming_job(self, reconciler, sample_streaming_spec):
        """Test updating a streaming job with changes."""
        # Mock job status as running with changes
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.RUNNING,
            is_streaming=True
        )
        reconciler._get_job_status_with_circuit_breaker = AsyncMock(return_value=mock_status)
        reconciler._has_spec_changed = AsyncMock(return_value=True)
        reconciler._update_streaming_job = AsyncMock(return_value=ReconciliationResult(
            job_id=sample_streaming_spec.job_id,
            action_taken=ReconciliationAction.UPDATE,
            success=True
        ))
        
        result = await reconciler.reconcile_job(sample_streaming_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.UPDATE
        reconciler._update_streaming_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconcile_job_restart_failed_job(self, reconciler, sample_streaming_spec):
        """Test restarting a failed job."""
        # Mock job status as failed
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.FAILED
        )
        reconciler._get_job_status_with_circuit_breaker = AsyncMock(return_value=mock_status)
        reconciler._restart_job = AsyncMock(return_value=ReconciliationResult(
            job_id=sample_streaming_spec.job_id,
            action_taken=ReconciliationAction.RESTART,
            success=True
        ))
        
        result = await reconciler.reconcile_job(sample_streaming_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.RESTART
        reconciler._restart_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconcile_all_jobs(self, reconciler):
        """Test reconciling multiple jobs."""
        specs = [
            JobSpec(job_id="job1", job_type=JobType.STREAMING, artifact_path="/job1.jar"),
            JobSpec(job_id="job2", job_type=JobType.BATCH, artifact_path="/job2.jar"),
            JobSpec(job_id="job3", job_type=JobType.STREAMING, artifact_path="/job3.jar")
        ]
        
        # Mock reconcile_job to return success for all jobs
        reconciler.reconcile_job = AsyncMock(side_effect=[
            ReconciliationResult(job_id="job1", action_taken=ReconciliationAction.DEPLOY, success=True),
            ReconciliationResult(job_id="job2", action_taken=ReconciliationAction.NO_ACTION, success=True),
            ReconciliationResult(job_id="job3", action_taken=ReconciliationAction.UPDATE, success=True)
        ])
        
        results = await reconciler.reconcile_all(specs)
        
        assert len(results) == 3
        assert all(result.success for result in results)
        assert reconciler.reconcile_job.call_count == 3
    
    @pytest.mark.asyncio
    async def test_reconcile_job_concurrent_reconciliation(self, reconciler, sample_streaming_spec):
        """Test that concurrent reconciliation is prevented."""
        # Mark job as already being reconciled
        reconciler._active_reconciliations[sample_streaming_spec.job_id] = datetime.now(timezone.utc)
        
        result = await reconciler.reconcile_job(sample_streaming_spec)
        
        assert not result.success
        assert result.action_taken == ReconciliationAction.NO_ACTION
        assert "already being reconciled" in result.error_message
    
    @pytest.mark.asyncio
    async def test_handle_conflicts_automatic_resolution(self, reconciler):
        """Test automatic conflict resolution."""
        conflicts = [
            Conflict(
                job_id="test-job",
                conflict_type=ConflictType.CONCURRENT_UPDATE,
                description="Concurrent update detected",
                suggested_resolution="Use last-writer-wins"
            ),
            Conflict(
                job_id="test-job-2",
                conflict_type=ConflictType.STATE_MISMATCH,
                description="State mismatch between spec and cluster",
                suggested_resolution="Use cluster state as truth"
            )
        ]
        
        resolution = await reconciler.handle_conflicts(conflicts)
        
        assert resolution.success
        assert len(resolution.resolved_conflicts) == 2
        assert len(resolution.unresolved_conflicts) == 0
    
    @pytest.mark.asyncio
    async def test_deploy_job_success(self, reconciler, sample_streaming_spec):
        """Test successful job deployment."""
        reconciler.state_store = AsyncMock()
        reconciler._update_job_state = AsyncMock()
        
        result = await reconciler._deploy_job(sample_streaming_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.DEPLOY
        assert result.job_id == sample_streaming_spec.job_id
    
    @pytest.mark.asyncio
    async def test_update_streaming_job_with_savepoint(self, reconciler, sample_streaming_spec):
        """Test updating streaming job with savepoint."""
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.RUNNING,
            is_streaming=True
        )
        
        reconciler._trigger_savepoint = AsyncMock(return_value="/savepoints/test-savepoint")
        reconciler._stop_job_internal = AsyncMock()
        reconciler._deploy_from_savepoint = AsyncMock()
        
        result = await reconciler._update_streaming_job(sample_streaming_spec, mock_status)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.UPDATE
        reconciler._trigger_savepoint.assert_called_once()
        reconciler._stop_job_internal.assert_called_once()
        reconciler._deploy_from_savepoint.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_job_success(self, reconciler, sample_streaming_spec):
        """Test successful job stop."""
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.RUNNING
        )
        
        reconciler._stop_job_internal = AsyncMock()
        reconciler._update_job_state = AsyncMock()
        
        result = await reconciler._stop_job(sample_streaming_spec, mock_status)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.STOP
        reconciler._stop_job_internal.assert_called_once_with(
            sample_streaming_spec.job_id, mock_status, graceful=True
        )
    
    @pytest.mark.asyncio
    async def test_restart_job_with_savepoint(self, reconciler, sample_streaming_spec):
        """Test restarting job with existing savepoint."""
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.FAILED,
            last_savepoint="/savepoints/previous"
        )
        
        reconciler._deploy_from_savepoint = AsyncMock()
        
        result = await reconciler._restart_job(sample_streaming_spec, mock_status)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.RESTART
        reconciler._deploy_from_savepoint.assert_called_once_with(
            sample_streaming_spec, "/savepoints/previous"
        )
    
    @pytest.mark.asyncio
    async def test_restart_job_without_savepoint(self, reconciler, sample_streaming_spec):
        """Test restarting job without savepoint."""
        mock_status = JobStatus(
            job_id=sample_streaming_spec.job_id,
            state=JobState.FAILED,
            last_savepoint=None
        )
        
        reconciler._deploy_job = AsyncMock(return_value=ReconciliationResult(
            job_id=sample_streaming_spec.job_id,
            action_taken=ReconciliationAction.DEPLOY,
            success=True
        ))
        
        result = await reconciler._restart_job(sample_streaming_spec, mock_status)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.RESTART


class TestJobSpec:
    """Test cases for JobSpec model."""
    
    def test_job_spec_creation(self):
        """Test creating a valid job specification."""
        spec = JobSpec(
            job_id="test-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/job.jar",
            parallelism=2,
            checkpoint_interval=60000
        )
        
        assert spec.job_id == "test-job"
        assert spec.job_type == JobType.STREAMING
        assert spec.parallelism == 2
        assert spec.checkpoint_interval == 60000
    
    def test_job_spec_hash_deterministic(self):
        """Test that spec hash is deterministic."""
        spec1 = JobSpec(
            job_id="test-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/job.jar",
            parallelism=2
        )
        
        spec2 = JobSpec(
            job_id="test-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/job.jar",
            parallelism=2
        )
        
        assert spec1.spec_hash() == spec2.spec_hash()
    
    def test_job_spec_hash_different_for_changes(self):
        """Test that spec hash changes when specification changes."""
        spec1 = JobSpec(
            job_id="test-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/job.jar",
            parallelism=2
        )
        
        spec2 = JobSpec(
            job_id="test-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/job.jar",
            parallelism=4  # Different parallelism
        )
        
        assert spec1.spec_hash() != spec2.spec_hash()


class TestJobStatus:
    """Test cases for JobStatus model."""
    
    def test_job_status_creation(self):
        """Test creating a job status."""
        status = JobStatus(
            job_id="test-job",
            flink_job_id="flink-12345",
            state=JobState.RUNNING,
            restart_count=1,
            is_streaming=True
        )
        
        assert status.job_id == "test-job"
        assert status.flink_job_id == "flink-12345"
        assert status.state == JobState.RUNNING
        assert status.is_streaming is True