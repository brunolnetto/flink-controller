"""
Comprehensive test suite for production reconciler with 100% coverage.

This test suite covers all code paths, edge cases, and error conditions
to achieve 100% test coverage for the production reconciler.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.exceptions import (CircuitBreakerOpenError,
                                 ConcurrentReconciliationError, ErrorCode,
                                 FlinkClusterError, JobDeploymentError,
                                 ReconciliationError, SavepointError)
from src.core.reconciler import (ChangeTrackerProtocol, CircuitBreakerProtocol,
                                 FlinkClientProtocol, JobReconciler, JobSpec,
                                 JobState, JobType, MetricsCollectorProtocol,
                                 ReconcilerConfig, ReconciliationAction,
                                 ReconciliationResult,
                                 ReconciliationStatistics, StateStoreProtocol)
from src.core.types import JobId, safe_cast_job_id


class MockFlinkClient:
    """Mock Flink client for testing."""

    def __init__(self):
        self.get_cluster_info = AsyncMock(return_value={"cluster_id": "test"})
        self.get_job_details = AsyncMock()
        self.deploy_job = AsyncMock(return_value="flink-job-123")
        self.stop_job = AsyncMock()
        self.trigger_savepoint = AsyncMock(return_value="savepoint-123")
        self.health_check = AsyncMock(return_value=True)


class MockStateStore:
    """Mock state store for testing."""

    def __init__(self):
        self.get_job_state = AsyncMock()
        self.save_job_state = AsyncMock()


class MockChangeTracker:
    """Mock change tracker for testing."""

    def __init__(self):
        self.has_changed = AsyncMock(return_value=False)
        self.update_tracker = AsyncMock()


class MockMetricsCollector:
    """Mock metrics collector for testing."""

    def __init__(self):
        self.record_reconciliation = Mock()
        self.record_deployment = Mock()
        self.record_error = Mock()


class MockCircuitBreaker:
    """Mock circuit breaker for testing."""

    def __init__(self):
        self.call = Mock(
            side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        )
        self.is_open = False


class TestJobReconciler:
    """Comprehensive tests for JobReconciler."""

    @pytest.fixture
    def reconciler_config(self):
        """Create reconciler configuration."""
        return ReconcilerConfig(
            max_concurrent_reconciliations=5,
            reconciliation_timeout=60.0,
            enable_metrics=True,
            enable_performance_logging=True,
        )

    @pytest.fixture
    def mock_flink_client(self):
        """Create mock Flink client."""
        return MockFlinkClient()

    @pytest.fixture
    def mock_state_store(self):
        """Create mock state store."""
        return MockStateStore()

    @pytest.fixture
    def mock_change_tracker(self):
        """Create mock change tracker."""
        return MockChangeTracker()

    @pytest.fixture
    def mock_metrics_collector(self):
        """Create mock metrics collector."""
        return MockMetricsCollector()

    @pytest.fixture
    def mock_circuit_breaker(self):
        """Create mock circuit breaker."""
        return MockCircuitBreaker()

    @pytest.fixture
    def reconciler(
        self,
        mock_flink_client,
        mock_state_store,
        mock_change_tracker,
        mock_metrics_collector,
        mock_circuit_breaker,
        reconciler_config,
    ):
        """Create production reconciler with all mocks."""
        return JobReconciler(
            flink_client=mock_flink_client,
            state_store=mock_state_store,
            change_tracker=mock_change_tracker,
            metrics_collector=mock_metrics_collector,
            circuit_breaker=mock_circuit_breaker,
            config=reconciler_config,
        )

    @pytest.fixture
    def minimal_reconciler(self, mock_flink_client):
        """Create minimal reconciler with only required dependencies."""
        return JobReconciler(flink_client=mock_flink_client)

    @pytest.fixture
    def sample_streaming_spec(self):
        """Create sample streaming job spec."""
        return JobSpec(
            job_id="test-streaming-job",
            job_type=JobType.STREAMING,
            artifact_path="/path/to/streaming.jar",
            parallelism=2,
            checkpoint_interval=60000,
            savepoint_trigger_interval=300000,
        )

    @pytest.fixture
    def sample_batch_spec(self):
        """Create sample batch job spec."""
        return JobSpec(
            job_id="test-batch-job",
            job_type=JobType.BATCH,
            artifact_path="/path/to/batch.jar",
            parallelism=1,
        )

    # Test initialization and configuration
    def test_reconciler_initialization_full_config(self, reconciler):
        """Test reconciler initialization with full configuration."""
        assert reconciler._config.max_concurrent_reconciliations == 5
        assert reconciler._config.reconciliation_timeout == 60.0
        assert reconciler._config.enable_metrics is True
        assert len(reconciler._active_reconciliations) == 0

        stats = reconciler.get_statistics()
        assert stats.total_jobs == 0
        assert stats.successful_reconciliations == 0

    def test_reconciler_initialization_minimal_config(self, minimal_reconciler):
        """Test reconciler initialization with minimal configuration."""
        assert minimal_reconciler._config.max_concurrent_reconciliations == 10
        assert minimal_reconciler._state_store is None
        assert minimal_reconciler._change_tracker is None

    def test_reconciler_config_immutability(self):
        """Test that reconciler config is immutable."""
        config = ReconcilerConfig(max_concurrent_reconciliations=5)
        with pytest.raises(
            Exception
        ):  # dataclass frozen=True should prevent modification
            config.max_concurrent_reconciliations = 10

    # Test job reconciliation - success cases
    @pytest.mark.asyncio
    async def test_reconcile_job_deploy_new_job(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test deploying a new job that doesn't exist."""
        # Mock job doesn't exist
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.DEPLOY
        assert result.error_code is None
        assert result.duration_ms >= 0
        assert result.job_id == sample_streaming_spec.job_id

        # Verify Flink client calls
        mock_flink_client.get_cluster_info.assert_called_once()
        mock_flink_client.deploy_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_job_no_action_needed(
        self, reconciler, sample_streaming_spec, mock_flink_client, mock_change_tracker
    ):
        """Test job that needs no action (running and no changes)."""
        # Mock running job with no changes
        mock_flink_client.get_job_details.return_value = {"state": "RUNNING"}
        mock_change_tracker.has_changed.return_value = False

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.NO_ACTION
        assert result.error_code is None

    @pytest.mark.asyncio
    async def test_reconcile_job_update_streaming_job(
        self, reconciler, sample_streaming_spec, mock_flink_client, mock_change_tracker
    ):
        """Test updating streaming job with changes."""
        # Mock running streaming job with changes
        mock_flink_client.get_job_details.return_value = {"state": "RUNNING"}
        mock_change_tracker.has_changed.return_value = True

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.UPDATE

        # Verify savepoint and deployment calls
        mock_flink_client.trigger_savepoint.assert_called_once()
        mock_flink_client.stop_job.assert_called_once()
        mock_flink_client.deploy_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_job_update_batch_job(
        self, reconciler, sample_batch_spec, mock_flink_client, mock_change_tracker
    ):
        """Test updating batch job with changes (should stop, not update)."""
        # Mock running batch job with changes
        mock_flink_client.get_job_details.return_value = {"state": "RUNNING"}
        mock_change_tracker.has_changed.return_value = True

        result = await reconciler.reconcile_job(sample_batch_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.STOP
        mock_flink_client.stop_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_job_restart_failed_job(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test restarting failed job."""
        # Mock failed job
        mock_flink_client.get_job_details.return_value = {"state": "FAILED"}

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.RESTART
        mock_flink_client.deploy_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_job_redeploy_stopped_job(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test redeploying stopped job."""
        # Mock stopped job
        mock_flink_client.get_job_details.return_value = {"state": "CANCELLED"}

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.DEPLOY
        mock_flink_client.deploy_job.assert_called_once()

    # Test error handling and edge cases
    @pytest.mark.asyncio
    async def test_reconcile_job_concurrent_reconciliation(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test handling concurrent reconciliation attempts."""

        # Configure mock to add delay to first reconciliation
        async def slow_get_job_details(*args, **kwargs):
            await asyncio.sleep(0.1)  # Make first reconciliation take 100ms
            return {"state": "RUNNING", "job_id": "flink-job-123"}

        mock_flink_client.get_job_details.side_effect = slow_get_job_details

        # Start first reconciliation
        task1 = asyncio.create_task(reconciler.reconcile_job(sample_streaming_spec))

        # Small delay to ensure first reconciliation starts and acquires the lock
        await asyncio.sleep(0.01)

        # Try second reconciliation - should detect concurrent reconciliation
        result2 = await reconciler.reconcile_job(sample_streaming_spec)

        # Wait for first to complete
        result1 = await task1

        assert result1.success
        assert not result2.success
        assert result2.error_code == ErrorCode.CONCURRENT_RECONCILIATION.value
        assert "already being reconciled" in result2.error_message.lower()

    @pytest.mark.asyncio
    async def test_reconcile_job_concurrent_timeout_cleanup(
        self, reconciler, sample_streaming_spec
    ):
        """Test cleanup of timed out concurrent reconciliation."""
        job_id = safe_cast_job_id(sample_streaming_spec.job_id)

        # Manually add old reconciliation (simulate timeout)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)  # 10 minutes ago
        reconciler._active_reconciliations[job_id] = old_time

        # This should clean up the old reconciliation and proceed
        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success  # Should not fail due to concurrent reconciliation
        assert job_id not in reconciler._active_reconciliations

    @pytest.mark.asyncio
    async def test_reconcile_job_circuit_breaker_open(
        self, reconciler, sample_streaming_spec, mock_circuit_breaker, mock_flink_client
    ):
        """Test handling circuit breaker open."""
        mock_circuit_breaker.is_open = True
        mock_flink_client.get_cluster_info.side_effect = Exception(
            "Circuit breaker open"
        )

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert not result.success
        assert result.error_code == ErrorCode.CIRCUIT_BREAKER_OPEN.value

    @pytest.mark.asyncio
    async def test_reconcile_job_flink_cluster_error(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test handling Flink cluster errors."""
        # Use FlinkClusterError to trigger proper error code
        from src.core.exceptions import FlinkClusterError

        mock_flink_client.get_job_details.side_effect = FlinkClusterError(
            "Cluster unreachable"
        )

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert not result.success
        assert result.error_code == ErrorCode.FLINK_CLUSTER_UNAVAILABLE.value

    @pytest.mark.asyncio
    async def test_reconcile_job_deployment_error(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test handling deployment errors."""
        # Mock job doesn't exist but deployment fails
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        mock_flink_client.deploy_job.side_effect = Exception("Deployment failed")

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert not result.success
        assert result.error_code == ErrorCode.RECONCILIATION_FAILED.value
        assert "deployment failed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_reconcile_job_savepoint_error(
        self, reconciler, sample_streaming_spec, mock_flink_client, mock_change_tracker
    ):
        """Test handling savepoint errors during update."""
        # Mock running job with changes
        mock_flink_client.get_job_details.return_value = {"state": "RUNNING"}
        mock_change_tracker.has_changed.return_value = True
        mock_flink_client.trigger_savepoint.side_effect = Exception("Savepoint failed")

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert not result.success
        assert result.error_code == ErrorCode.RECONCILIATION_FAILED.value

    @pytest.mark.asyncio
    async def test_reconcile_job_unexpected_exception(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test handling unexpected exceptions."""
        mock_flink_client.get_cluster_info.side_effect = RuntimeError(
            "Unexpected error"
        )

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert not result.success
        # RuntimeError from Flink client gets wrapped as FlinkClusterError
        assert result.error_code == ErrorCode.FLINK_CLUSTER_UNAVAILABLE.value
        assert "unexpected error" in result.error_message.lower()

    # Test batch reconciliation
    @pytest.mark.asyncio
    async def test_reconcile_all_empty_list(self, reconciler):
        """Test reconciling empty job list."""
        results = await reconciler.reconcile_all([])
        assert results == []

    @pytest.mark.asyncio
    async def test_reconcile_all_single_job(
        self, reconciler, sample_streaming_spec, mock_flink_client
    ):
        """Test reconciling single job."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")

        results = await reconciler.reconcile_all([sample_streaming_spec])

        assert len(results) == 1
        assert results[0].success
        assert results[0].action_taken == ReconciliationAction.DEPLOY

    @pytest.mark.asyncio
    async def test_reconcile_all_multiple_jobs_concurrent(
        self, reconciler, mock_flink_client
    ):
        """Test concurrent reconciliation of multiple jobs."""
        specs = [
            JobSpec(
                job_id=f"job-{i}",
                job_type=JobType.STREAMING,
                artifact_path=f"/job{i}.jar",
            )
            for i in range(10)
        ]

        # All jobs don't exist, will be deployed
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")

        start_time = time.time()
        results = await reconciler.reconcile_all(specs)
        duration = time.time() - start_time

        assert len(results) == 10
        assert all(result.success for result in results)
        assert all(
            result.action_taken == ReconciliationAction.DEPLOY for result in results
        )

        # Should complete much faster than sequential processing
        assert duration < 2.0  # Should be much less than 10 sequential operations

        # Verify all jobs were processed
        assert mock_flink_client.deploy_job.call_count == 10

    @pytest.mark.asyncio
    async def test_reconcile_all_mixed_success_failure(
        self, reconciler, mock_flink_client
    ):
        """Test reconciling with mixed success and failure results."""
        specs = [
            JobSpec(
                job_id="success-job",
                job_type=JobType.STREAMING,
                artifact_path="/success.jar",
            ),
            JobSpec(
                job_id="failure-job",
                job_type=JobType.STREAMING,
                artifact_path="/failure.jar",
            ),
        ]

        # First job succeeds, second fails
        def mock_deploy(jar_path, config):
            if "success" in jar_path:
                return "flink-job-1"
            else:
                raise Exception("Deployment failed")

        mock_flink_client.get_job_details.side_effect = Exception("Job not found")
        mock_flink_client.deploy_job.side_effect = mock_deploy

        results = await reconciler.reconcile_all(specs)

        assert len(results) == 2
        assert results[0].success
        assert not results[1].success
        assert results[1].error_code == ErrorCode.RECONCILIATION_FAILED.value

    @pytest.mark.asyncio
    async def test_reconcile_all_exception_conversion(
        self, reconciler, mock_flink_client
    ):
        """Test that exceptions in concurrent processing are converted to failed results."""
        specs = [
            JobSpec(
                job_id="test-job", job_type=JobType.STREAMING, artifact_path="/test.jar"
            )
        ]

        # Mock to raise unexpected exception
        mock_flink_client.get_cluster_info.side_effect = RuntimeError(
            "Unexpected runtime error"
        )

        results = await reconciler.reconcile_all(specs)

        assert len(results) == 1
        assert not results[0].success
        # RuntimeError from Flink client gets wrapped as FlinkClusterError
        assert results[0].error_code == ErrorCode.FLINK_CLUSTER_UNAVAILABLE.value

    # Test state integration
    @pytest.mark.asyncio
    async def test_state_store_integration(
        self, reconciler, sample_streaming_spec, mock_state_store, mock_flink_client
    ):
        """Test integration with state store."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        mock_state_store.save_job_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_change_tracker_integration(
        self, reconciler, sample_streaming_spec, mock_change_tracker, mock_flink_client
    ):
        """Test integration with change tracker."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        mock_change_tracker.update_tracker.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_integration(
        self,
        reconciler,
        sample_streaming_spec,
        mock_metrics_collector,
        mock_flink_client,
    ):
        """Test metrics collection integration."""
        mock_flink_client.get_job_details.side_effect = Exception("Job not found")

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        mock_metrics_collector.record_reconciliation.assert_called_once()
        mock_metrics_collector.record_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_error_recording(
        self,
        reconciler,
        sample_streaming_spec,
        mock_metrics_collector,
        mock_flink_client,
    ):
        """Test error metrics recording."""
        # Trigger an error during reconciliation
        mock_flink_client.get_job_details.side_effect = Exception(
            "Job details fetch failed"
        )

        result = await reconciler.reconcile_job(sample_streaming_spec)

        assert not result.success
        # Verify that reconciliation metrics were recorded (including failure)
        assert mock_metrics_collector.record_reconciliation.call_count >= 1

    # Test state management
    def test_get_statistics_initial(self, reconciler):
        """Test getting initial statistics."""
        stats = reconciler.get_statistics()

        assert isinstance(stats, ReconciliationStatistics)
        assert stats.total_jobs == 0
        assert stats.successful_reconciliations == 0
        assert stats.failed_reconciliations == 0
        assert stats.concurrent_reconciliation_attempts == 0
        assert stats.average_duration_ms == 0.0

    def test_get_active_reconciliations_empty(self, reconciler):
        """Test getting active reconciliations when none active."""
        active = reconciler.get_active_reconciliations()
        assert isinstance(active, dict)
        assert len(active) == 0

    def test_statistics_update(self, reconciler):
        """Test statistics updating after reconciliation."""
        results = [
            ReconciliationResult(
                job_id="job-1",
                action_taken=ReconciliationAction.DEPLOY,
                success=True,
                duration_ms=100,
            ),
            ReconciliationResult(
                job_id="job-2",
                action_taken=ReconciliationAction.UPDATE,
                success=False,
                error_code=ErrorCode.JOB_DEPLOYMENT_FAILED.value,
                duration_ms=200,
            ),
            ReconciliationResult(
                job_id="job-3",
                action_taken=ReconciliationAction.NO_ACTION,
                success=True,
                duration_ms=50,
            ),
        ]

        reconciler._update_statistics(results)
        stats = reconciler.get_statistics()

        assert stats.successful_reconciliations == 2
        assert stats.failed_reconciliations == 1
        assert stats.actions_taken[ReconciliationAction.DEPLOY.value] == 1
        assert stats.actions_taken[ReconciliationAction.UPDATE.value] == 1
        assert stats.actions_taken[ReconciliationAction.NO_ACTION.value] == 1
        assert stats.error_codes[ErrorCode.JOB_DEPLOYMENT_FAILED.value] == 1
        assert (
            abs(stats.average_duration_ms - 116.67) < 0.01
        )  # (100 + 200 + 50) / 3, with tolerance

    # Test health checking
    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, reconciler, mock_flink_client, mock_circuit_breaker
    ):
        """Test health check when everything is healthy."""
        mock_flink_client.health_check.return_value = True
        mock_circuit_breaker.is_open = False

        is_healthy = await reconciler.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_flink_unhealthy(self, reconciler, mock_flink_client):
        """Test health check when Flink is unhealthy."""
        mock_flink_client.health_check.return_value = False

        is_healthy = await reconciler.health_check()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_circuit_breaker_open(
        self, reconciler, mock_circuit_breaker
    ):
        """Test health check when circuit breaker is open."""
        mock_circuit_breaker.is_open = True

        is_healthy = await reconciler.health_check()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, reconciler, mock_flink_client):
        """Test health check with exception."""
        mock_flink_client.health_check.side_effect = Exception("Health check failed")

        is_healthy = await reconciler.health_check()
        assert is_healthy is False

    # Test edge cases and boundary conditions
    @pytest.mark.asyncio
    async def test_reconcile_job_invalid_job_id(self, reconciler):
        """Test reconciling job with invalid job ID."""
        invalid_spec = JobSpec(
            job_id="",  # Invalid empty job ID
            job_type=JobType.STREAMING,
            artifact_path="/test.jar",
        )

        with pytest.raises(ValueError):
            await reconciler.reconcile_job(invalid_spec)

    def test_state_conversion_edge_cases(self, reconciler):
        """Test Flink state to job state conversion edge cases."""
        # Test all known mappings
        assert (
            reconciler._convert_flink_state_to_job_state("RUNNING") == JobState.RUNNING
        )
        assert (
            reconciler._convert_flink_state_to_job_state("FINISHED") == JobState.STOPPED
        )
        assert (
            reconciler._convert_flink_state_to_job_state("CANCELED") == JobState.STOPPED
        )
        assert (
            reconciler._convert_flink_state_to_job_state("CANCELLED")
            == JobState.STOPPED
        )
        assert reconciler._convert_flink_state_to_job_state("FAILED") == JobState.FAILED
        assert (
            reconciler._convert_flink_state_to_job_state("RESTARTING")
            == JobState.RECONCILING
        )

        # Test unknown state
        assert (
            reconciler._convert_flink_state_to_job_state("UNKNOWN_STATE")
            == JobState.UNKNOWN
        )

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_wrapper(self, reconciler, mock_circuit_breaker):
        """Test circuit breaker call wrapper with async functions."""

        async def mock_async_func(arg1, arg2):
            return f"result: {arg1}, {arg2}"

        result = await reconciler._call_with_circuit_breaker(
            mock_async_func, "test1", "test2"
        )
        assert result == "result: test1, test2"

    @pytest.mark.asyncio
    async def test_minimal_reconciler_without_optional_components(
        self, minimal_reconciler, sample_streaming_spec
    ):
        """Test reconciler works with minimal configuration (no optional components)."""
        # Should work without state store, change tracker, metrics collector, circuit breaker
        minimal_reconciler._flink_client.get_job_details.side_effect = Exception(
            "Job not found"
        )

        result = await minimal_reconciler.reconcile_job(sample_streaming_spec)

        assert result.success
        assert result.action_taken == ReconciliationAction.DEPLOY


class TestReconciliationResult:
    """Test ReconciliationResult model validation."""

    def test_valid_reconciliation_result(self):
        """Test creating valid reconciliation result."""
        result = ReconciliationResult(
            job_id="test-job",
            action_taken=ReconciliationAction.DEPLOY,
            success=True,
            duration_ms=100,
        )

        assert result.job_id == "test-job"
        assert result.action_taken == ReconciliationAction.DEPLOY
        assert result.success is True
        assert result.duration_ms == 100
        assert result.error_code is None

    def test_reconciliation_result_validation_empty_job_id(self):
        """Test validation fails for empty job ID."""
        with pytest.raises(Exception):  # Pydantic validation error
            ReconciliationResult(
                job_id="",  # Empty string should fail min_length validation
                action_taken=ReconciliationAction.DEPLOY,
                success=True,
                duration_ms=100,
            )

    def test_reconciliation_result_validation_negative_duration(self):
        """Test validation fails for negative duration."""
        with pytest.raises(Exception):  # Pydantic validation error
            ReconciliationResult(
                job_id="test-job",
                action_taken=ReconciliationAction.DEPLOY,
                success=True,
                duration_ms=-1,  # Negative duration should fail ge=0 validation
            )

    def test_reconciliation_result_with_error_info(self):
        """Test reconciliation result with error information."""
        result = ReconciliationResult(
            job_id="failed-job",
            action_taken=ReconciliationAction.NO_ACTION,
            success=False,
            error_code="DEPLOYMENT_FAILED",
            error_message="Job deployment failed due to invalid artifact",
            duration_ms=250,
            context={"artifact_path": "/invalid/path.jar"},
        )

        assert result.success is False
        assert result.error_code == "DEPLOYMENT_FAILED"
        assert "deployment failed" in result.error_message.lower()
        assert result.context["artifact_path"] == "/invalid/path.jar"


class TestReconciliationStatistics:
    """Test ReconciliationStatistics model validation."""

    def test_valid_reconciliation_statistics(self):
        """Test creating valid reconciliation statistics."""
        stats = ReconciliationStatistics(
            total_jobs=10,
            successful_reconciliations=8,
            failed_reconciliations=2,
            concurrent_reconciliation_attempts=1,
            average_duration_ms=125.5,
            actions_taken={"deploy": 5, "update": 3},
            error_codes={"DEPLOYMENT_FAILED": 1, "TIMEOUT": 1},
        )

        assert stats.total_jobs == 10
        assert stats.successful_reconciliations == 8
        assert stats.failed_reconciliations == 2
        assert stats.average_duration_ms == 125.5

    def test_reconciliation_statistics_validation(self):
        """Test validation of reconciliation statistics."""
        # Negative values should fail validation
        with pytest.raises(Exception):  # Pydantic validation error
            ReconciliationStatistics(
                total_jobs=-1,  # Should fail ge=0 validation
                successful_reconciliations=0,
                failed_reconciliations=0,
                concurrent_reconciliation_attempts=0,
                average_duration_ms=0.0,
            )
