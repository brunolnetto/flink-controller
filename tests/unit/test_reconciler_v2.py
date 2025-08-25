"""
Comprehensive tests for enhanced reconciler with 100% coverage.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from src.core.reconciler_v2 import (
    EnhancedJobReconciler, ReconcilerConfig, CircuitBreakerConfig,
    ReconciliationResult, ReconciliationStatistics
)
from src.core.reconciler import JobSpec, JobType, JobState, ReconciliationAction
from src.core.exceptions import (
    ConcurrentReconciliationError, CircuitBreakerOpenError,
    ReconciliationError, JobDeploymentError, ErrorCode
)


class TestEnhancedJobReconciler:
    """Comprehensive test coverage for EnhancedJobReconciler."""
    
    @pytest.fixture
    def mock_flink_client(self):
        """Create mock Flink client."""
        client = Mock()
        client.get_cluster_info = AsyncMock()
        client.get_job_details = AsyncMock()
        client.deploy_job = AsyncMock(return_value="flink-job-123")
        client.stop_job = AsyncMock()
        client.trigger_savepoint = AsyncMock(return_value="savepoint-req-123")
        client.health_check = AsyncMock(return_value=True)
        return client
    
    @pytest.fixture
    def mock_state_store(self):
        """Create mock state store."""
        store = Mock()
        store.save_job_state = AsyncMock()
        store.get_job_state = AsyncMock()
        store.delete_job_state = AsyncMock()
        return store
    
    @pytest.fixture
    def mock_change_tracker(self):
        """Create mock change tracker."""
        tracker = Mock()
        tracker.has_changed = AsyncMock(return_value=False)
        tracker.update_tracker = AsyncMock()
        return tracker
    
    @pytest.fixture
    def mock_metrics_collector(self):
        """Create mock metrics collector."""
        collector = Mock()
        collector.record_reconciliation = Mock()
        collector.record_deployment = Mock()
        collector.record_error = Mock()
        return collector
    
    @pytest.fixture
    def mock_circuit_breaker(self):
        """Create mock circuit breaker."""
        breaker = Mock()
        breaker.call = Mock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
        breaker.is_open = False
        breaker.is_closed = True
        return breaker
    
    @pytest.fixture
    def reconciler_config(self):
        """Create reconciler configuration."""
        return ReconcilerConfig(
            max_concurrent_reconciliations=5,
            reconciliation_timeout=60.0,
            enable_metrics=True
        )
    
    @pytest.fixture
    def reconciler(self, mock_flink_client, mock_state_store, mock_change_tracker, 
                   mock_metrics_collector, mock_circuit_breaker, reconciler_config):
        """Create enhanced reconciler with mocked dependencies."""
        return EnhancedJobReconciler(
            flink_client=mock_flink_client,
            state_store=mock_state_store,
            change_tracker=mock_change_tracker,
            metrics_collector=mock_metrics_collector,
            circuit_breaker=mock_circuit_breaker,
            config=reconciler_config
        )
    
    @pytest.fixture
    def sample_job_spec(self):
        """Create sample job specification."""
        return JobSpec(
            job_id="test-streaming-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/job.jar",
            parallelism=2,
            checkpoint_interval=60000
        )
    
    @pytest.mark.asyncio
    async def test_reconcile_job_deploy_new_job(self, reconciler, sample_job_spec, 
                                               mock_flink_client, mock_metrics_collector):
        """Test deploying a new job."""
        # Mock job doesn't exist
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.DEPLOY
        assert result.error_code is None
        assert result.duration_ms >= 0
        mock_flink_client.deploy_job.assert_called_once()
        mock_metrics_collector.record_reconciliation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconcile_job_no_action_needed(self, reconciler, sample_job_spec,
                                                 mock_flink_client, mock_change_tracker):
        """Test job that needs no action."""
        # Mock running job with no changes
        from src.core.flink_client import FlinkJobInfo, FlinkJobState
        mock_flink_client.get_job_details.return_value = FlinkJobInfo(
            job_id="flink-123",
            job_name="test-job",
            state=FlinkJobState.RUNNING,
            parallelism=2
        )
        mock_change_tracker.has_changed.return_value = False
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.NO_ACTION
    
    @pytest.mark.asyncio
    async def test_reconcile_job_update_streaming_job(self, reconciler, sample_job_spec,
                                                     mock_flink_client, mock_change_tracker):
        """Test updating streaming job with changes."""
        # Mock running job with changes
        from src.core.flink_client import FlinkJobInfo, FlinkJobState
        mock_flink_client.get_job_details.return_value = FlinkJobInfo(
            job_id="flink-123",
            job_name="test-job", 
            state=FlinkJobState.RUNNING,
            parallelism=2
        )
        mock_change_tracker.has_changed.return_value = True
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.UPDATE
        mock_flink_client.trigger_savepoint.assert_called_once()
        mock_flink_client.stop_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconcile_job_restart_failed_job(self, reconciler, sample_job_spec,
                                                   mock_flink_client):
        """Test restarting failed job."""
        # Mock failed job
        from src.core.flink_client import FlinkJobInfo, FlinkJobState
        mock_flink_client.get_job_details.return_value = FlinkJobInfo(
            job_id="flink-123",
            job_name="test-job",
            state=FlinkJobState.FAILED,
            parallelism=2
        )
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        assert result.action_taken == ReconciliationAction.RESTART
        mock_flink_client.deploy_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconcile_job_concurrent_reconciliation(self, reconciler, sample_job_spec):
        """Test handling concurrent reconciliation attempts."""
        # Start first reconciliation
        task1 = asyncio.create_task(reconciler.reconcile_job(sample_job_spec))
        
        # Small delay to ensure first reconciliation starts
        await asyncio.sleep(0.01)
        
        # Try second reconciliation - should fail with concurrent error
        result2 = await reconciler.reconcile_job(sample_job_spec)
        
        # Wait for first to complete
        result1 = await task1
        
        assert result1.success
        assert not result2.success
        assert result2.error_code == ErrorCode.CONCURRENT_RECONCILIATION.value
    
    @pytest.mark.asyncio
    async def test_reconcile_job_circuit_breaker_open(self, reconciler, sample_job_spec,
                                                     mock_circuit_breaker):
        """Test handling circuit breaker open."""
        mock_circuit_breaker.is_open = True
        mock_circuit_breaker.call.side_effect = Exception("Circuit breaker open")
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert not result.success
        assert ErrorCode.FLINK_CLUSTER_UNAVAILABLE.value in result.error_message
    
    @pytest.mark.asyncio
    async def test_reconcile_job_deployment_error(self, reconciler, sample_job_spec,
                                                 mock_flink_client):
        """Test handling deployment errors."""
        # Mock job doesn't exist but deployment fails
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        mock_flink_client.deploy_job.side_effect = Exception("Deployment failed")
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert not result.success
        assert result.action_taken == ReconciliationAction.NO_ACTION
        assert result.error_code == ErrorCode.RECONCILIATION_FAILED.value
    
    @pytest.mark.asyncio
    async def test_reconcile_all_concurrent_processing(self, reconciler):
        """Test concurrent processing of multiple jobs."""
        specs = [
            JobSpec(job_id=f"job-{i}", job_type=JobType.STREAMING, artifact_path=f"/job{i}.jar")
            for i in range(10)
        ]
        
        # All jobs don't exist, will be deployed
        reconciler._flink_client.get_job_details.side_effect = Exception("Job not found")
        
        results = await reconciler.reconcile_all(specs)
        
        assert len(results) == 10
        assert all(result.success for result in results)
        assert all(result.action_taken == ReconciliationAction.DEPLOY for result in results)
        
        # Verify all jobs were processed concurrently
        assert reconciler._flink_client.deploy_job.call_count == 10
    
    @pytest.mark.asyncio
    async def test_reconcile_all_with_exceptions(self, reconciler, mock_flink_client):
        """Test handling exceptions during concurrent processing."""
        specs = [
            JobSpec(job_id="job-1", job_type=JobType.STREAMING, artifact_path="/job1.jar"),
            JobSpec(job_id="job-2", job_type=JobType.STREAMING, artifact_path="/job2.jar")
        ]
        
        # First job succeeds, second fails
        mock_flink_client.get_job_details.side_effect = [
            Exception("Job not found"),  # job-1 doesn't exist
            Exception("Job not found")   # job-2 doesn't exist
        ]
        mock_flink_client.deploy_job.side_effect = [
            "flink-job-1",               # job-1 deploys successfully
            Exception("Deployment failed")  # job-2 fails
        ]
        
        results = await reconciler.reconcile_all(specs)
        
        assert len(results) == 2
        assert results[0].success
        assert not results[1].success
        assert results[1].error_code == ErrorCode.RECONCILIATION_FAILED.value
    
    @pytest.mark.asyncio
    async def test_reconcile_empty_job_list(self, reconciler):
        """Test reconciling empty job list."""
        results = await reconciler.reconcile_all([])
        assert results == []
    
    def test_get_statistics(self, reconciler):
        """Test getting reconciliation statistics."""
        stats = reconciler.get_statistics()
        
        assert isinstance(stats, ReconciliationStatistics)
        assert stats.total_jobs == 0
        assert stats.successful_reconciliations == 0
        assert stats.failed_reconciliations == 0
    
    def test_get_active_reconciliations(self, reconciler):
        """Test getting active reconciliations."""
        active = reconciler.get_active_reconciliations()
        assert isinstance(active, dict)
        assert len(active) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, reconciler, mock_flink_client, mock_circuit_breaker):
        """Test health check when everything is healthy."""
        mock_flink_client.health_check.return_value = True
        mock_circuit_breaker.is_open = False
        
        is_healthy = await reconciler.health_check()
        assert is_healthy
    
    @pytest.mark.asyncio
    async def test_health_check_circuit_breaker_open(self, reconciler, mock_circuit_breaker):
        """Test health check when circuit breaker is open."""
        mock_circuit_breaker.is_open = True
        
        is_healthy = await reconciler.health_check()
        assert not is_healthy
    
    @pytest.mark.asyncio
    async def test_health_check_flink_unhealthy(self, reconciler, mock_flink_client):
        """Test health check when Flink is unhealthy."""
        mock_flink_client.health_check.return_value = False
        
        is_healthy = await reconciler.health_check()
        assert not is_healthy
    
    @pytest.mark.asyncio
    async def test_health_check_exception(self, reconciler, mock_flink_client):
        """Test health check with exception."""
        mock_flink_client.health_check.side_effect = Exception("Health check failed")
        
        is_healthy = await reconciler.health_check()
        assert not is_healthy
    
    def test_reconciler_config_immutable(self):
        """Test that reconciler config is immutable."""
        config = ReconcilerConfig(max_concurrent_reconciliations=5)
        
        with pytest.raises(Exception):  # dataclass frozen=True should prevent modification
            config.max_concurrent_reconciliations = 10
    
    def test_circuit_breaker_config_immutable(self):
        """Test that circuit breaker config is immutable."""
        config = CircuitBreakerConfig(failure_threshold=3)
        
        with pytest.raises(Exception):  # dataclass frozen=True should prevent modification
            config.failure_threshold = 5
    
    @pytest.mark.asyncio
    async def test_reconciliation_timeout_cleanup(self, reconciler, sample_job_spec):
        """Test cleanup of timed out reconciliations."""
        # Manually add old reconciliation
        old_time = datetime.now(timezone.utc).replace(year=2020)  # Very old
        reconciler._active_reconciliations[sample_job_spec.job_id] = old_time
        
        # This should clean up the old reconciliation and proceed
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success  # Should not fail due to concurrent reconciliation
        assert sample_job_spec.job_id not in reconciler._active_reconciliations
    
    @pytest.mark.asyncio
    async def test_state_store_integration(self, reconciler, sample_job_spec, 
                                          mock_state_store, mock_flink_client):
        """Test integration with state store."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        mock_state_store.save_job_state.assert_called_once_with(
            sample_job_spec.job_id, JobState.RUNNING
        )
    
    @pytest.mark.asyncio
    async def test_change_tracker_integration(self, reconciler, sample_job_spec,
                                             mock_change_tracker, mock_flink_client):
        """Test integration with change tracker."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        mock_change_tracker.update_tracker.assert_called_once_with(
            sample_job_spec.job_id, sample_job_spec
        )
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, reconciler, sample_job_spec,
                                     mock_metrics_collector, mock_flink_client):
        """Test metrics collection during reconciliation."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        
        result = await reconciler.reconcile_job(sample_job_spec)
        
        assert result.success
        mock_metrics_collector.record_reconciliation.assert_called_once()
        mock_metrics_collector.record_deployment.assert_called_once_with(
            sample_job_spec.job_id, True, 0
        )
    
    def test_statistics_update(self, reconciler):
        """Test statistics updating."""
        results = [
            ReconciliationResult(
                job_id="job-1",
                action_taken=ReconciliationAction.DEPLOY,
                success=True,
                duration_ms=100
            ),
            ReconciliationResult(
                job_id="job-2", 
                action_taken=ReconciliationAction.UPDATE,
                success=False,
                error_code=ErrorCode.JOB_DEPLOYMENT_FAILED.value,
                duration_ms=200
            )
        ]
        
        reconciler._update_statistics(results)
        stats = reconciler.get_statistics()
        
        assert stats.successful_reconciliations == 1
        assert stats.failed_reconciliations == 1
        assert stats.actions_taken[ReconciliationAction.DEPLOY.value] == 1
        assert stats.actions_taken[ReconciliationAction.UPDATE.value] == 1
        assert stats.error_codes[ErrorCode.JOB_DEPLOYMENT_FAILED.value] == 1
        assert stats.average_duration_ms == 150.0


class TestReconcilerV2EdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_malformed_job_spec(self):
        """Test handling malformed job specifications."""
        # This would be caught by Pydantic validation
        with pytest.raises(Exception):
            JobSpec(job_id="", job_type=JobType.STREAMING, artifact_path="")
    
    @pytest.mark.asyncio
    async def test_network_timeout_during_reconciliation(self, mock_flink_client):
        """Test network timeout during reconciliation."""
        mock_flink_client.health_check.side_effect = asyncio.TimeoutError("Network timeout")
        
        reconciler = EnhancedJobReconciler(flink_client=mock_flink_client)
        
        is_healthy = await reconciler.health_check()
        assert not is_healthy
    
    def test_reconciliation_result_validation(self):
        """Test ReconciliationResult validation."""
        # Valid result
        result = ReconciliationResult(
            job_id="test-job",
            action_taken=ReconciliationAction.DEPLOY,
            success=True,
            duration_ms=100
        )
        assert result.job_id == "test-job"
        
        # Invalid job_id (empty string)
        with pytest.raises(Exception):
            ReconciliationResult(
                job_id="",  # Empty string should fail validation
                action_taken=ReconciliationAction.DEPLOY,
                success=True,
                duration_ms=100
            )
        
        # Invalid duration_ms (negative)
        with pytest.raises(Exception):
            ReconciliationResult(
                job_id="test-job",
                action_taken=ReconciliationAction.DEPLOY,
                success=True,
                duration_ms=-1  # Negative should fail validation
            )