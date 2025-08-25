"""
Unit tests for resilience patterns including circuit breaker, retry logic, and error handling.
"""

import pytest
import time
from unittest.mock import Mock, patch
from src.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


class TestCircuitBreaker:
    """Test circuit breaker pattern implementation."""

    def test_circuit_breaker_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )

        # Assert
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_successful_call_remains_closed(self):
        """Test that successful calls keep circuit breaker in CLOSED state."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )
        mock_function = Mock(return_value="success")

        # Act
        result = circuit_breaker.call(mock_function)

        # Assert
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    def test_circuit_breaker_failure_increments_count(self):
        """Test that failures increment the failure count."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )
        mock_function = Mock(side_effect=Exception("Test error"))

        # Act
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function)

        # Assert
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_opens_after_threshold_reached(self):
        """Test that circuit breaker opens after failure threshold is reached."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=60,
            expected_exception=Exception
        )
        mock_function = Mock(side_effect=Exception("Test error"))

        # Act - First failure
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function)

        # Act - Second failure (should open circuit)
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function)

        # Assert circuit is now open
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 2
        
        # Act - Third call should fail fast
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
            circuit_breaker.call(mock_function)

    def test_circuit_breaker_opens_after_threshold_reached_with_different_functions(self):
        """Test that circuit breaker opens after threshold is reached with different functions."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=60,
            expected_exception=Exception
        )
        mock_function1 = Mock(side_effect=Exception("Test error 1"))
        mock_function2 = Mock(side_effect=Exception("Test error 2"))

        # Act - First failure
        with pytest.raises(Exception, match="Test error 1"):
            circuit_breaker.call(mock_function1)

        # Act - Second failure (should open circuit)
        with pytest.raises(Exception, match="Test error 2"):
            circuit_breaker.call(mock_function2)

        # Assert circuit is now open
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 2
        
        # Act - Third call should fail fast
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
            circuit_breaker.call(mock_function2)

        # Assert
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 2

    def test_circuit_breaker_transitions_to_half_open_after_timeout(self):
        """Test that circuit breaker transitions to HALF_OPEN after recovery timeout."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,  # Short timeout for testing
            expected_exception=Exception
        )
        mock_function = Mock(side_effect=Exception("Test error"))

        # Act - Cause circuit to open
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function)

        # Wait for recovery timeout
        time.sleep(0.2)

        # Assert - Should be in HALF_OPEN state
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    def test_circuit_breaker_successful_call_in_half_open_closes_circuit(self):
        """Test that successful call in HALF_OPEN state closes the circuit."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            expected_exception=Exception
        )
        mock_function_fail = Mock(side_effect=Exception("Test error"))
        mock_function_success = Mock(return_value="success")

        # Act - Cause circuit to open
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function_fail)

        # Wait for recovery timeout
        time.sleep(0.2)

        # Act - Successful call in HALF_OPEN state
        result = circuit_breaker.call(mock_function_success)

        # Assert
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    def test_circuit_breaker_failed_call_in_half_open_opens_circuit(self):
        """Test that failed call in HALF_OPEN state opens the circuit."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            expected_exception=Exception
        )
        mock_function_fail = Mock(side_effect=Exception("Test error"))

        # Act - Cause circuit to open
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function_fail)

        # Wait for recovery timeout
        time.sleep(0.2)

        # Act - Failed call in HALF_OPEN state
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function_fail)

        # Assert
        assert circuit_breaker.state == CircuitState.OPEN

    def test_circuit_breaker_ignores_unexpected_exceptions(self):
        """Test that circuit breaker ignores exceptions not in expected_exception."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=60,
            expected_exception=ValueError
        )
        mock_function = Mock(side_effect=TypeError("Unexpected error"))

        # Act
        with pytest.raises(TypeError, match="Unexpected error"):
            circuit_breaker.call(mock_function)

        # Assert - Should not count unexpected exceptions
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_reset_functionality(self):
        """Test that circuit breaker can be manually reset."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=60,
            expected_exception=Exception
        )
        mock_function = Mock(side_effect=Exception("Test error"))

        # Act - Cause circuit to open
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function)

        # Act - Reset circuit breaker
        circuit_breaker.reset()

        # Assert
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    def test_circuit_breaker_with_custom_exception_types(self):
        """Test circuit breaker with custom exception types."""
        # Arrange
        class CustomError(Exception):
            pass

        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=60,
            expected_exception=(CustomError, ValueError)
        )
        mock_function = Mock(side_effect=CustomError("Custom error"))

        # Act
        with pytest.raises(CustomError, match="Custom error"):
            circuit_breaker.call(mock_function)

        # Assert
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.OPEN

    def test_circuit_breaker_call_with_arguments(self):
        """Test that circuit breaker passes arguments to the wrapped function."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )
        mock_function = Mock(return_value="success")

        # Act
        result = circuit_breaker.call(mock_function, "arg1", "arg2", kwarg1="value1")

        # Assert
        mock_function.assert_called_once_with("arg1", "arg2", kwarg1="value1")
        assert result == "success"

    def test_circuit_breaker_state_transitions(self):
        """Test all state transitions of the circuit breaker."""
        # Arrange
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            expected_exception=Exception
        )
        mock_function_fail = Mock(side_effect=Exception("Test error"))
        mock_function_success = Mock(return_value="success")

        # Assert initial state
        assert circuit_breaker.state == CircuitState.CLOSED

        # Act - Open circuit
        with pytest.raises(Exception, match="Test error"):
            circuit_breaker.call(mock_function_fail)

        # Assert OPEN state
        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Assert HALF_OPEN state
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Act - Close circuit with success
        result = circuit_breaker.call(mock_function_success)

        # Assert CLOSED state
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED 