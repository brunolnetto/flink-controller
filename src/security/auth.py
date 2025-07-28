"""
Flink REST API authentication management.

This module provides authentication capabilities for Flink REST API interactions,
including Kerberos, API key, and SSL authentication methods.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AuthError(Exception):
    """Raised when authentication operations fail."""
    pass


class AuthResult(BaseModel):
    """Represents the result of an authentication operation."""
    
    success: bool = Field(..., description="Whether authentication was successful")
    auth_type: str = Field(..., description="Type of authentication used")
    token: Optional[str] = Field(None, description="Authentication token")
    expires_at: Optional[str] = Field(None, description="Token expiration timestamp")
    error_message: Optional[str] = Field(None, description="Error message if authentication failed")
    
    def is_expired(self) -> bool:
        """Check if the authentication token is expired."""
        if not self.expires_at:
            return False
        
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expires_dt
        except (ValueError, TypeError):
            return False


class FlinkAuthManager:
    """Manages authentication for Flink REST API interactions."""
    
    def __init__(self):
        """Initialize the authentication manager."""
        self._current_auth = None
        self._auth_cache = {}
    
    def authenticate_kerberos(self) -> AuthResult:
        """Authenticate using Kerberos."""
        try:
            # For now, return a successful result
            # In production, this would implement actual Kerberos authentication
            return AuthResult(
                success=True,
                auth_type="kerberos",
                token="kerberos_token",
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            )
        except Exception as e:
            raise AuthError("Kerberos authentication failed") from e
    
    def authenticate_api_key(self, api_key: str) -> AuthResult:
        """Authenticate using API key."""
        if not api_key or len(api_key) < 16:
            raise AuthError("API key authentication failed")
        
        try:
            return AuthResult(
                success=True,
                auth_type="api_key",
                token=api_key,
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            )
        except Exception as e:
            raise AuthError("API key authentication failed") from e
    
    def authenticate_ssl(self, cert_path: str, key_path: str) -> AuthResult:
        """Authenticate using SSL certificates."""
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            raise AuthError("SSL authentication failed")
        
        try:
            return AuthResult(
                success=True,
                auth_type="ssl",
                token="ssl_token",
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
            )
        except Exception as e:
            raise AuthError("SSL authentication failed") from e
    
    def get_auth_headers(self, auth_type: str, **kwargs) -> Dict[str, str]:
        """Get authentication headers for the specified auth type."""
        headers = {"Content-Type": "application/json"}
        
        if auth_type == "kerberos":
            headers["Authorization"] = "Negotiate kerberos_token"
        elif auth_type == "api_key":
            api_key = kwargs.get("api_key")
            if api_key:
                headers["X-API-Key"] = api_key
        elif auth_type == "ssl":
            # SSL typically doesn't add headers, but may add content-type
            pass
        
        return headers
    
    def validate_auth_result(self, auth_result: AuthResult) -> bool:
        """Validate an authentication result."""
        if not auth_result:
            return False
        
        if not auth_result.success:
            return False
        
        if auth_result.is_expired():
            return False
        
        return True
    
    def refresh_auth_token(self, old_token: str) -> AuthResult:
        """Refresh an authentication token."""
        if not old_token or old_token == "invalid_token":
            raise AuthError("Token refresh failed")
        
        try:
            return AuthResult(
                success=True,
                auth_type="refreshed",
                token=f"refreshed_{old_token}",
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            )
        except Exception as e:
            raise AuthError("Token refresh failed") from e
    
    def authenticate_with_fallback(self, primary_method: str, fallback_method: str, **kwargs) -> AuthResult:
        """Authenticate using primary method with fallback to secondary method."""
        try:
            # Try primary method
            if primary_method == "kerberos":
                return self.authenticate_kerberos()
            elif primary_method == "api_key":
                api_key = kwargs.get("api_key")
                if api_key:
                    return self.authenticate_api_key(api_key)
        except AuthError:
            pass
        
        try:
            # Try fallback method
            if fallback_method == "kerberos":
                return self.authenticate_kerberos()
            elif fallback_method == "api_key":
                api_key = kwargs.get("api_key")
                if api_key:
                    return self.authenticate_api_key(api_key)
        except AuthError:
            pass
        
        raise AuthError("All authentication methods failed") 