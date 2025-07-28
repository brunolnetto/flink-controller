"""
Unit tests for secure credential management.

This module tests the CredentialManager class which handles secure
credential storage and rotation for the Flink Job Controller.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any
import os
from datetime import datetime, timezone, timedelta

# Import the classes we'll be testing
from src.security.credentials import CredentialManager, FlinkCredentials, CredentialError


class TestCredentialManager:
    """Test suite for CredentialManager class."""

    def setup_method(self):
        """Setup test fixtures."""
        # self.credential_manager = CredentialManager()
        pass

    def test_get_flink_credentials_returns_valid_credentials(self):
        """Test that get_flink_credentials returns valid FlinkCredentials."""
        # Arrange
        credential_manager = CredentialManager()
        
        # Set environment variables for testing
        import os
        os.environ["FLINK_USERNAME"] = "test_user"
        os.environ["FLINK_PASSWORD"] = "test_password_long_enough_for_validation"
        os.environ["FLINK_API_KEY"] = "test_api_key_long_enough_for_validation_12345"
        
        # Act
        credentials = credential_manager.get_flink_credentials()
        
        # Assert
        assert isinstance(credentials, FlinkCredentials)
        assert credentials.username is not None
        assert credentials.password is not None
        assert credentials.api_key is not None
        
        # Clean up
        del os.environ["FLINK_USERNAME"]
        del os.environ["FLINK_PASSWORD"]
        del os.environ["FLINK_API_KEY"]

    def test_get_flink_credentials_raises_error_when_credentials_not_found(self):
        """Test that get_flink_credentials raises CredentialError when credentials not found."""
        # Arrange
        credential_manager = CredentialManager()
        # Mock the secure store to return None by clearing environment variables
        
        # Act & Assert
        with pytest.raises(CredentialError, match="Flink credentials not found"):
            credential_manager.get_flink_credentials()

    def test_rotate_credentials_successfully_rotates_credentials(self):
        """Test that rotate_credentials successfully rotates credentials."""
        # Arrange
        credential_manager = CredentialManager()
        service = "flink"
        
        # Act
        result = credential_manager.rotate_credentials(service)
        
        # Assert
        assert result is True
        # Verify that new credentials are different from old ones

    def test_validate_credentials_returns_true_for_valid_credentials(self):
        """Test that validate_credentials returns True for valid credentials."""
        # Arrange
        credential_manager = CredentialManager()
        valid_credentials = FlinkCredentials(
            username="test_user",
            password="test_password_long_enough_for_validation",
            api_key="test_api_key_long_enough_for_validation_12345"
        )
        
        # Act
        result = credential_manager.validate_credentials(valid_credentials)
        
        # Assert
        assert result is True

    def test_validate_credentials_returns_false_for_invalid_credentials(self):
        """Test that validate_credentials returns False for invalid credentials."""
        # Arrange
        credential_manager = CredentialManager()
        
        # Create invalid credentials by setting empty values after creation
        invalid_credentials = FlinkCredentials(
            username="test_user",
            password="test_password_long_enough_for_validation",
            api_key="test_api_key_long_enough_for_validation_12345"
        )
        # Manually set empty username to test validation
        invalid_credentials.username = ""
        
        # Act
        result = credential_manager.validate_credentials(invalid_credentials)
        
        # Assert
        assert result is False

    def test_validate_credentials_returns_false_for_expired_credentials(self):
        """Test that validate_credentials returns False for expired credentials."""
        # Arrange
        credential_manager = CredentialManager()
        expired_credentials = FlinkCredentials(
            username="test_user",
            password="test_password_long_enough_for_validation",
            api_key="test_api_key_long_enough_for_validation_12345",
            expires_at="2020-01-01T00:00:00Z"  # Expired date
        )
        
        # Act
        result = credential_manager.validate_credentials(expired_credentials)
        
        # Assert
        assert result is False

    def test_validate_credentials_returns_false_for_none_credentials(self):
        """Test that validate_credentials returns False for None credentials."""
        # Arrange
        credential_manager = CredentialManager()
        
        # Act
        result = credential_manager.validate_credentials(None)
        
        # Assert
        assert result is False

    def test_validate_credentials_returns_false_for_short_password(self):
        """Test that validate_credentials returns False for short password."""
        # Arrange
        credential_manager = CredentialManager()
        credentials_with_short_password = FlinkCredentials(
            username="test_user",
            password="short",  # Less than 8 characters
            api_key="test_api_key_long_enough_for_validation_12345"
        )
        
        # Act
        result = credential_manager.validate_credentials(credentials_with_short_password)
        
        # Assert
        assert result is False

    def test_validate_credentials_returns_false_for_short_api_key(self):
        """Test that validate_credentials returns False for short API key."""
        # Arrange
        credential_manager = CredentialManager()
        credentials_with_short_api_key = FlinkCredentials(
            username="test_user",
            password="test_password_long_enough_for_validation",
            api_key="short"  # Less than 16 characters
        )
        
        # Act
        result = credential_manager.validate_credentials(credentials_with_short_api_key)
        
        # Assert
        assert result is False

    def test_initialize_secure_store_returns_expected_config(self):
        """Test that _initialize_secure_store returns expected configuration."""
        # Arrange
        credential_manager = CredentialManager()
        
        # Act
        store_config = credential_manager._secure_store
        
        # Assert
        assert isinstance(store_config, dict)
        assert store_config["store_type"] == "environment_variables"
        assert store_config["fallback_enabled"] is True


class TestFlinkCredentials:
    """Test suite for FlinkCredentials class."""

    def test_flink_credentials_creation_with_valid_data(self):
        """Test FlinkCredentials creation with valid data."""
        # Arrange & Act
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key"
        )
        
        # Assert
        assert credentials.username == "test_user"
        assert credentials.password == "test_password"
        assert credentials.api_key == "test_api_key"

    def test_flink_credentials_creation_with_optional_fields(self):
        """Test FlinkCredentials creation with optional fields."""
        # Arrange & Act
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key",
            expires_at="2024-12-31T23:59:59Z",
            created_at="2024-01-01T00:00:00Z"
        )
        
        # Assert
        assert credentials.expires_at == "2024-12-31T23:59:59Z"
        assert credentials.created_at == "2024-01-01T00:00:00Z"

    def test_flink_credentials_validation_requires_username(self):
        """Test that FlinkCredentials validation requires username."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Username is required"):
            FlinkCredentials(
                username="",  # Empty username
                password="test_password",
                api_key="test_api_key"
            )

    def test_flink_credentials_validation_requires_password(self):
        """Test that FlinkCredentials validation requires password."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Password is required"):
            FlinkCredentials(
                username="test_user",
                password="",  # Empty password
                api_key="test_api_key"
            )

    def test_flink_credentials_validation_requires_api_key(self):
        """Test that FlinkCredentials validation requires API key."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="API key is required"):
            FlinkCredentials(
                username="test_user",
                password="test_password",
                api_key=""  # Empty API key
            )

    def test_flink_credentials_validation_strips_whitespace(self):
        """Test that FlinkCredentials validation strips whitespace."""
        # Arrange & Act
        credentials = FlinkCredentials(
            username="  test_user  ",
            password="  test_password  ",
            api_key="  test_api_key  "
        )
        
        # Assert
        assert credentials.username == "test_user"
        assert credentials.password == "test_password"
        assert credentials.api_key == "test_api_key"

    def test_is_expired_returns_false_when_no_expires_at(self):
        """Test that is_expired returns False when expires_at is None."""
        # Arrange
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key"
        )
        
        # Act
        result = credentials.is_expired()
        
        # Assert
        assert result is False

    def test_is_expired_returns_false_for_future_date(self):
        """Test that is_expired returns False for future expiration date."""
        # Arrange
        future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key",
            expires_at=future_date
        )
        
        # Act
        result = credentials.is_expired()
        
        # Assert
        assert result is False

    def test_is_expired_returns_true_for_past_date(self):
        """Test that is_expired returns True for past expiration date."""
        # Arrange
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key",
            expires_at=past_date
        )
        
        # Act
        result = credentials.is_expired()
        
        # Assert
        assert result is True

    def test_is_expired_handles_invalid_date_format(self):
        """Test that is_expired handles invalid date format gracefully."""
        # Arrange
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key",
            expires_at="invalid-date-format"
        )
        
        # Act
        result = credentials.is_expired()
        
        # Assert
        assert result is False

    def test_is_expired_handles_none_expires_at(self):
        """Test that is_expired handles None expires_at gracefully."""
        # Arrange
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key",
            expires_at=None
        )
        
        # Act
        result = credentials.is_expired()
        
        # Assert
        assert result is False

    def test_is_expired_handles_isoformat_with_z_suffix(self):
        """Test that is_expired handles ISO format with Z suffix."""
        # Arrange
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        credentials = FlinkCredentials(
            username="test_user",
            password="test_password",
            api_key="test_api_key",
            expires_at=past_date
        )
        
        # Act
        result = credentials.is_expired()
        
        # Assert
        assert result is True 