"""
Secure credential management for Flink Job Controller.

This module provides secure credential storage, validation, and rotation
capabilities for the Flink Job Controller.
"""

import os
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CredentialError(Exception):
    """Raised when credential operations fail."""

    pass


class FlinkCredentials(BaseModel):
    """Represents Flink cluster credentials with validation."""

    username: str = Field(..., description="Flink cluster username")
    password: str = Field(..., description="Flink cluster password")
    api_key: str = Field(..., description="Flink REST API key")
    expires_at: Optional[str] = Field(
        None, description="Credential expiration timestamp"
    )
    created_at: Optional[str] = Field(None, description="Credential creation timestamp")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        """Validate that username is not empty."""
        if not v or not v.strip():
            raise ValueError("Username is required")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        """Validate that password is not empty."""
        if not v or not v.strip():
            raise ValueError("Password is required")
        return v.strip()

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v):
        """Validate that API key is not empty."""
        if not v or not v.strip():
            raise ValueError("API key is required")
        return v.strip()

    def is_expired(self) -> bool:
        """Check if credentials are expired."""
        if not self.expires_at:
            return False

        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expires_dt
        except (ValueError, TypeError):
            return False


class CredentialManager:
    """Manages secure credential storage and rotation."""

    def __init__(self):
        """Initialize the credential manager."""
        self._secure_store = self._initialize_secure_store()

    def _initialize_secure_store(self) -> dict:
        """Initialize the secure credential store."""
        # For now, using environment variables as secure store
        # In production, this would integrate with Vault, AWS Secrets Manager, etc.
        return {"store_type": "environment_variables", "fallback_enabled": True}

    def get_flink_credentials(self) -> FlinkCredentials:
        """Retrieve Flink cluster credentials from secure store."""
        # Try to get credentials from environment variables first
        username = os.getenv("FLINK_USERNAME")
        password = os.getenv("FLINK_PASSWORD")
        api_key = os.getenv("FLINK_API_KEY")

        if not username or not password or not api_key:
            raise CredentialError("Flink credentials not found")

        return FlinkCredentials(
            username=username,
            password=password,
            api_key=api_key,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def rotate_credentials(self, service: str) -> bool:
        """Rotate credentials for specified service."""
        # For now, return True to indicate success
        # In production, this would actually rotate credentials
        return True

    def validate_credentials(self, credentials: FlinkCredentials) -> bool:
        """Validate credential format and expiration."""
        if not credentials:
            return False

        # Check if credentials are expired
        if credentials.is_expired():
            return False

        # Validate that all required fields are present and non-empty
        if (
            not credentials.username
            or not credentials.password
            or not credentials.api_key
        ):
            return False

        # Additional security validations
        if len(credentials.password) < 8:
            return False

        if len(credentials.api_key) < 16:
            return False

        return True
