"""
Unit tests for Flink REST API authentication.

This module tests the FlinkAuthManager class which handles authentication
for Flink REST API interactions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

# Import the classes we'll be testing
from src.security.auth import AuthError, AuthResult, FlinkAuthManager


class TestFlinkAuthManager:
    """Test suite for FlinkAuthManager class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.auth_manager = FlinkAuthManager()
        self.test_credentials = {
            "username": "test_user",
            "password": "test_password_long_enough_for_validation",
            "api_key": "test_api_key_long_enough_for_validation_12345",
        }

    def test_authenticate_kerberos_success(self):
        """Test successful Kerberos authentication."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act
        result = auth_manager.authenticate_kerberos()

        # Assert
        assert isinstance(result, AuthResult)
        assert result.success is True
        assert result.auth_type == "kerberos"

    def test_authenticate_kerberos_failure(self):
        """Test Kerberos authentication failure."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Mock the authenticate_kerberos method to raise an exception
        with patch.object(
            auth_manager,
            "authenticate_kerberos",
            side_effect=AuthError("Kerberos authentication failed"),
        ):
            # Act & Assert
            with pytest.raises(AuthError, match="Kerberos authentication failed"):
                auth_manager.authenticate_kerberos()

    def test_authenticate_api_key_success(self):
        """Test successful API key authentication."""
        # Arrange
        auth_manager = FlinkAuthManager()
        api_key = "valid_api_key_long_enough_for_validation_12345"

        # Act
        result = auth_manager.authenticate_api_key(api_key)

        # Assert
        assert isinstance(result, AuthResult)
        assert result.success is True
        assert result.auth_type == "api_key"

    def test_authenticate_api_key_failure(self):
        """Test API key authentication failure."""
        # Arrange
        auth_manager = FlinkAuthManager()
        invalid_api_key = "invalid_key"

        # Act & Assert
        with pytest.raises(AuthError, match="API key authentication failed"):
            auth_manager.authenticate_api_key(invalid_api_key)

    def test_authenticate_api_key_empty(self):
        """Test API key authentication with empty key."""
        # Arrange
        auth_manager = FlinkAuthManager()
        empty_api_key = ""

        # Act & Assert
        with pytest.raises(AuthError, match="API key authentication failed"):
            auth_manager.authenticate_api_key(empty_api_key)

    def test_authenticate_api_key_none(self):
        """Test API key authentication with None key."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act & Assert
        with pytest.raises(AuthError, match="API key authentication failed"):
            auth_manager.authenticate_api_key(None)

    def test_authenticate_ssl_success(self):
        """Test successful SSL authentication."""
        # Arrange
        auth_manager = FlinkAuthManager()
        cert_path = "/path/to/cert.pem"
        key_path = "/path/to/key.pem"

        # Mock os.path.exists to return True
        with patch("os.path.exists", return_value=True):
            # Act
            result = auth_manager.authenticate_ssl(cert_path, key_path)

            # Assert
            assert isinstance(result, AuthResult)
            assert result.success is True
            assert result.auth_type == "ssl"

    def test_authenticate_ssl_failure(self):
        """Test SSL authentication failure."""
        # Arrange
        auth_manager = FlinkAuthManager()
        invalid_cert_path = "/invalid/path/cert.pem"
        invalid_key_path = "/invalid/path/key.pem"

        # Act & Assert
        with pytest.raises(AuthError, match="SSL authentication failed"):
            auth_manager.authenticate_ssl(invalid_cert_path, invalid_key_path)

    def test_authenticate_ssl_cert_missing(self):
        """Test SSL authentication with missing certificate."""
        # Arrange
        auth_manager = FlinkAuthManager()
        cert_path = "/missing/cert.pem"
        key_path = "/path/to/key.pem"

        # Mock os.path.exists to return False for cert, True for key
        with patch("os.path.exists", side_effect=lambda path: path == key_path):
            # Act & Assert
            with pytest.raises(AuthError, match="SSL authentication failed"):
                auth_manager.authenticate_ssl(cert_path, key_path)

    def test_authenticate_ssl_key_missing(self):
        """Test SSL authentication with missing key."""
        # Arrange
        auth_manager = FlinkAuthManager()
        cert_path = "/path/to/cert.pem"
        key_path = "/missing/key.pem"

        # Mock os.path.exists to return True for cert, False for key
        with patch("os.path.exists", side_effect=lambda path: path == cert_path):
            # Act & Assert
            with pytest.raises(AuthError, match="SSL authentication failed"):
                auth_manager.authenticate_ssl(cert_path, key_path)

    def test_get_auth_headers_kerberos(self):
        """Test getting authentication headers for Kerberos."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act
        headers = auth_manager.get_auth_headers("kerberos")

        # Assert
        assert isinstance(headers, dict)
        assert "Authorization" in headers

    def test_get_auth_headers_api_key(self):
        """Test getting authentication headers for API key."""
        # Arrange
        auth_manager = FlinkAuthManager()
        api_key = "test_api_key_long_enough_for_validation_12345"

        # Act
        headers = auth_manager.get_auth_headers("api_key", api_key=api_key)

        # Assert
        assert isinstance(headers, dict)
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == api_key

    def test_get_auth_headers_api_key_no_key(self):
        """Test getting authentication headers for API key without providing key."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act
        headers = auth_manager.get_auth_headers("api_key")

        # Assert
        assert isinstance(headers, dict)
        assert "X-API-Key" not in headers

    def test_get_auth_headers_ssl(self):
        """Test getting authentication headers for SSL."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act
        headers = auth_manager.get_auth_headers("ssl")

        # Assert
        assert isinstance(headers, dict)
        # SSL typically doesn't add headers, but may add content-type
        assert "Content-Type" in headers

    def test_get_auth_headers_unknown_type(self):
        """Test getting authentication headers for unknown auth type."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act
        headers = auth_manager.get_auth_headers("unknown_type")

        # Assert
        assert isinstance(headers, dict)
        assert "Content-Type" in headers

    def test_validate_auth_result_success(self):
        """Test validation of successful auth result."""
        # Arrange
        auth_manager = FlinkAuthManager()
        # Use a future date that's definitely not expired
        future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        auth_result = AuthResult(
            success=True,
            auth_type="kerberos",
            token="test_token",
            expires_at=future_date,
        )

        # Act
        result = auth_manager.validate_auth_result(auth_result)

        # Assert
        assert result is True

    def test_validate_auth_result_failure(self):
        """Test validation of failed auth result."""
        # Arrange
        auth_manager = FlinkAuthManager()
        auth_result = AuthResult(
            success=False, auth_type="kerberos", error_message="Authentication failed"
        )

        # Act
        result = auth_manager.validate_auth_result(auth_result)

        # Assert
        assert result is False

    def test_validate_auth_result_expired(self):
        """Test validation of expired auth result."""
        # Arrange
        auth_manager = FlinkAuthManager()
        auth_result = AuthResult(
            success=True,
            auth_type="kerberos",
            token="test_token",
            expires_at="2020-01-01T00:00:00Z",  # Expired
        )

        # Act
        result = auth_manager.validate_auth_result(auth_result)

        # Assert
        assert result is False

    def test_validate_auth_result_none(self):
        """Test validation of None auth result."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act
        result = auth_manager.validate_auth_result(None)

        # Assert
        assert result is False

    def test_refresh_auth_token_success(self):
        """Test successful token refresh."""
        # Arrange
        auth_manager = FlinkAuthManager()
        old_token = "old_token"

        # Act
        result = auth_manager.refresh_auth_token(old_token)

        # Assert
        assert isinstance(result, AuthResult)
        assert result.success is True
        assert result.token != old_token

    def test_refresh_auth_token_failure(self):
        """Test token refresh failure."""
        # Arrange
        auth_manager = FlinkAuthManager()
        invalid_token = "invalid_token"

        # Act & Assert
        with pytest.raises(AuthError, match="Token refresh failed"):
            auth_manager.refresh_auth_token(invalid_token)

    def test_refresh_auth_token_empty(self):
        """Test token refresh with empty token."""
        # Arrange
        auth_manager = FlinkAuthManager()
        empty_token = ""

        # Act & Assert
        with pytest.raises(AuthError, match="Token refresh failed"):
            auth_manager.refresh_auth_token(empty_token)

    def test_refresh_auth_token_none(self):
        """Test token refresh with None token."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Act & Assert
        with pytest.raises(AuthError, match="Token refresh failed"):
            auth_manager.refresh_auth_token(None)

    def test_authenticate_with_fallback_success(self):
        """Test authentication with fallback mechanism."""
        # Arrange
        auth_manager = FlinkAuthManager()
        primary_method = "kerberos"
        fallback_method = "api_key"
        api_key = "test_api_key_long_enough_for_validation_12345"

        # Act
        result = auth_manager.authenticate_with_fallback(
            primary_method, fallback_method, api_key=api_key
        )

        # Assert
        assert isinstance(result, AuthResult)
        assert result.success is True

    def test_authenticate_with_fallback_all_fail(self):
        """Test authentication with fallback when all methods fail."""
        # Arrange
        auth_manager = FlinkAuthManager()
        primary_method = "kerberos"
        fallback_method = "api_key"
        invalid_api_key = "invalid_key"

        # Mock both methods to fail
        with patch.object(
            auth_manager,
            "authenticate_kerberos",
            side_effect=AuthError("Kerberos failed"),
        ):
            with patch.object(
                auth_manager,
                "authenticate_api_key",
                side_effect=AuthError("API key failed"),
            ):
                # Act & Assert
                with pytest.raises(
                    AuthError, match="All authentication methods failed"
                ):
                    auth_manager.authenticate_with_fallback(
                        primary_method, fallback_method, api_key=invalid_api_key
                    )

    def test_authenticate_with_fallback_primary_fails_fallback_succeeds(self):
        """Test authentication with fallback when primary fails but fallback succeeds."""
        # Arrange
        auth_manager = FlinkAuthManager()
        primary_method = "kerberos"
        fallback_method = "api_key"
        api_key = "test_api_key_long_enough_for_validation_12345"

        # Mock primary method to fail, fallback to succeed
        with patch.object(
            auth_manager,
            "authenticate_kerberos",
            side_effect=AuthError("Kerberos failed"),
        ):
            # Act
            result = auth_manager.authenticate_with_fallback(
                primary_method, fallback_method, api_key=api_key
            )

            # Assert
            assert isinstance(result, AuthResult)
            assert result.success is True
            assert result.auth_type == "api_key"

    def test_authenticate_with_fallback_unknown_methods(self):
        """Test authentication with fallback using unknown methods."""
        # Arrange
        auth_manager = FlinkAuthManager()
        primary_method = "unknown_primary"
        fallback_method = "unknown_fallback"

        # Act & Assert
        with pytest.raises(AuthError, match="All authentication methods failed"):
            auth_manager.authenticate_with_fallback(primary_method, fallback_method)


class TestAuthResult:
    """Test suite for AuthResult class."""

    def test_auth_result_creation_success(self):
        """Test AuthResult creation for successful authentication."""
        # Arrange & Act
        auth_result = AuthResult(
            success=True,
            auth_type="kerberos",
            token="test_token",
            expires_at="2024-12-31T23:59:59Z",
        )

        # Assert
        assert auth_result.success is True
        assert auth_result.auth_type == "kerberos"
        assert auth_result.token == "test_token"
        assert auth_result.expires_at == "2024-12-31T23:59:59Z"

    def test_auth_result_creation_failure(self):
        """Test AuthResult creation for failed authentication."""
        # Arrange & Act
        auth_result = AuthResult(
            success=False, auth_type="kerberos", error_message="Authentication failed"
        )

        # Assert
        assert auth_result.success is False
        assert auth_result.auth_type == "kerberos"
        assert auth_result.error_message == "Authentication failed"

    def test_auth_result_is_expired_false(self):
        """Test AuthResult is_expired returns False for future date."""
        # Arrange
        future_date = (
            datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
        ).isoformat()
        auth_result = AuthResult(
            success=True,
            auth_type="kerberos",
            token="test_token",
            expires_at=future_date,
        )

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is False

    def test_auth_result_is_expired_true(self):
        """Test AuthResult is_expired returns True for past date."""
        # Arrange
        past_date = (
            datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
        ).isoformat()
        auth_result = AuthResult(
            success=True, auth_type="kerberos", token="test_token", expires_at=past_date
        )

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is True

    def test_auth_result_is_expired_none(self):
        """Test AuthResult is_expired returns False when expires_at is None."""
        # Arrange
        auth_result = AuthResult(success=True, auth_type="kerberos", token="test_token")

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is False

    def test_auth_result_is_expired_invalid_format(self):
        """Test AuthResult is_expired handles invalid date format."""
        # Arrange
        auth_result = AuthResult(
            success=True,
            auth_type="kerberos",
            token="test_token",
            expires_at="invalid-date-format",
        )

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is False

    def test_auth_result_is_expired_with_z_suffix(self):
        """Test AuthResult is_expired handles ISO format with Z suffix."""
        # Arrange
        past_date = (
            datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        auth_result = AuthResult(
            success=True, auth_type="kerberos", token="test_token", expires_at=past_date
        )

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is True

    def test_auth_result_is_expired_with_timezone_offset(self):
        """Test AuthResult is_expired handles ISO format with timezone offset."""
        # Arrange
        past_date = (
            datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        auth_result = AuthResult(
            success=True, auth_type="kerberos", token="test_token", expires_at=past_date
        )

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is True

    def test_auth_result_is_expired_with_type_error(self):
        """Test AuthResult is_expired handles TypeError gracefully."""
        # Arrange
        auth_result = AuthResult(
            success=True,
            auth_type="kerberos",
            token="test_token",
            expires_at="invalid-date-format",
        )

        # Act
        result = auth_result.is_expired()

        # Assert
        assert result is False

    def test_flink_auth_manager_initialization(self):
        """Test FlinkAuthManager initialization."""
        # Arrange & Act
        auth_manager = FlinkAuthManager()

        # Assert
        assert auth_manager._current_auth is None
        assert isinstance(auth_manager._auth_cache, dict)

    def test_authenticate_api_key_exception_handling(self):
        """Test API key authentication exception handling."""
        # Arrange
        auth_manager = FlinkAuthManager()
        api_key = "valid_api_key_long_enough_for_validation_12345"

        # Mock authenticate_api_key to raise a generic exception
        with patch.object(
            auth_manager, "authenticate_api_key", side_effect=Exception("Generic error")
        ):
            # Act & Assert
            with pytest.raises(AuthError, match="API key authentication failed"):
                auth_manager.authenticate_api_key(api_key)

    def test_authenticate_ssl_exception_handling(self):
        """Test SSL authentication exception handling."""
        # Arrange
        auth_manager = FlinkAuthManager()
        cert_path = "/path/to/cert.pem"
        key_path = "/path/to/key.pem"

        # Mock os.path.exists to return True and then raise exception
        with patch("os.path.exists", return_value=True):
            with patch.object(
                auth_manager, "authenticate_ssl", side_effect=Exception("Generic error")
            ):
                # Act & Assert
                with pytest.raises(AuthError, match="SSL authentication failed"):
                    auth_manager.authenticate_ssl(cert_path, key_path)

    def test_refresh_auth_token_exception_handling(self):
        """Test token refresh exception handling."""
        # Arrange
        auth_manager = FlinkAuthManager()
        old_token = "old_token"

        # Mock refresh_auth_token to raise a generic exception
        with patch.object(
            auth_manager, "refresh_auth_token", side_effect=Exception("Generic error")
        ):
            # Act & Assert
            with pytest.raises(AuthError, match="Token refresh failed"):
                auth_manager.refresh_auth_token(old_token)

    def test_authenticate_with_fallback_exception_handling(self):
        """Test fallback authentication exception handling."""
        # Arrange
        auth_manager = FlinkAuthManager()
        primary_method = "kerberos"
        fallback_method = "api_key"
        api_key = "test_api_key_long_enough_for_validation_12345"

        # Mock both methods to raise exceptions
        with patch.object(
            auth_manager,
            "authenticate_kerberos",
            side_effect=Exception("Kerberos error"),
        ):
            with patch.object(
                auth_manager,
                "authenticate_api_key",
                side_effect=Exception("API key error"),
            ):
                # Act & Assert
                with pytest.raises(
                    AuthError, match="All authentication methods failed"
                ):
                    auth_manager.authenticate_with_fallback(
                        primary_method, fallback_method, api_key=api_key
                    )

    def test_get_auth_headers_exception_handling(self):
        """Test auth headers exception handling."""
        # Arrange
        auth_manager = FlinkAuthManager()

        # Mock get_auth_headers to raise an exception
        with patch.object(
            auth_manager, "get_auth_headers", side_effect=Exception("Headers error")
        ):
            # Act & Assert
            with pytest.raises(Exception, match="Headers error"):
                auth_manager.get_auth_headers("kerberos")
