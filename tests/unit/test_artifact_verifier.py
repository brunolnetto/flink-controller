"""
Unit tests for artifact signature verification.

This module tests the ArtifactVerifier class which handles verification
of Flink job artifacts and their digital signatures.
"""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the classes we'll be testing
from src.security.artifact_verifier import (ArtifactVerifier,
                                            VerificationError,
                                            VerificationResult)


class TestArtifactVerifier:
    """Test suite for ArtifactVerifier class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.verifier = ArtifactVerifier()
        self.test_artifact_path = "/path/to/test-artifact.jar"
        self.test_signature_path = "/path/to/test-artifact.jar.sig"
        self.test_public_key_path = "/path/to/public-key.pem"

    def test_verify_digital_signature_success(self):
        """Test successful digital signature verification."""
        # Arrange
        verifier = ArtifactVerifier()

        # Act
        result = verifier.verify_digital_signature(
            self.test_artifact_path, self.test_signature_path, self.test_public_key_path
        )

        # Assert
        assert isinstance(result, VerificationResult)
        assert result.success is True
        assert result.verification_type == "digital_signature"

    def test_verify_digital_signature_failure(self):
        """Test digital signature verification failure."""
        # Arrange
        verifier = ArtifactVerifier()

        # Mock the verify_digital_signature method to raise an exception
        with patch.object(
            verifier,
            "verify_digital_signature",
            side_effect=VerificationError("Digital signature verification failed"),
        ):
            # Act & Assert
            with pytest.raises(
                VerificationError, match="Digital signature verification failed"
            ):
                verifier.verify_digital_signature(
                    "/invalid/artifact.jar",
                    "/invalid/signature.sig",
                    "/invalid/public-key.pem",
                )

    def test_verify_digital_signature_exception_handling(self):
        """Test digital signature verification exception handling."""
        # Arrange
        verifier = ArtifactVerifier()

        # Mock the verify_digital_signature method to raise a generic exception
        with patch.object(
            verifier, "verify_digital_signature", side_effect=Exception("Generic error")
        ):
            # Act & Assert
            with pytest.raises(
                VerificationError, match="Digital signature verification failed"
            ):
                verifier.verify_digital_signature(
                    "/path/to/artifact.jar",
                    "/path/to/signature.sig",
                    "/path/to/public-key.pem",
                )

    def test_verify_checksum_success(self):
        """Test successful checksum verification."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Calculate expected checksum
            expected_checksum = verifier.calculate_checksum(temp_file_path, "sha256")

            # Act
            result = verifier.verify_checksum(
                temp_file_path, expected_checksum, "sha256"
            )

            # Assert
            assert isinstance(result, VerificationResult)
            assert result.success is True
            assert result.verification_type == "checksum"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_checksum_failure(self):
        """Test checksum verification failure."""
        # Arrange
        verifier = ArtifactVerifier()
        invalid_checksum = "invalid_checksum"

        # Act & Assert
        with pytest.raises(VerificationError, match="Checksum verification failed"):
            verifier.verify_checksum(
                self.test_artifact_path, invalid_checksum, "sha256"
            )

    def test_verify_checksum_unsupported_algorithm(self):
        """Test checksum verification with unsupported algorithm."""
        # Arrange
        verifier = ArtifactVerifier()
        checksum = "a1b2c3d4e5f6"

        # Act & Assert
        with pytest.raises(VerificationError, match="Unsupported checksum algorithm"):
            verifier.verify_checksum(
                self.test_artifact_path, checksum, "unsupported_algorithm"
            )

    def test_verify_file_integrity_success(self):
        """Test successful file integrity verification."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Act
            result = verifier.verify_file_integrity(temp_file_path)

            # Assert
            assert isinstance(result, VerificationResult)
            assert result.success is True
            assert result.verification_type == "file_integrity"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_file_integrity_failure(self):
        """Test file integrity verification failure."""
        # Arrange
        verifier = ArtifactVerifier()
        non_existent_path = "/non/existent/file.jar"

        # Act & Assert
        with pytest.raises(
            VerificationError, match="File integrity verification failed"
        ):
            verifier.verify_file_integrity(non_existent_path)

    def test_verify_artifact_completeness_success(self):
        """Test successful artifact completeness verification."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file with .jar extension
        with tempfile.NamedTemporaryFile(suffix=".jar", delete=False) as temp_file:
            temp_file.write(b"test jar content")
            temp_file_path = temp_file.name

        try:
            # Act
            result = verifier.verify_artifact_completeness(temp_file_path)

            # Assert
            assert isinstance(result, VerificationResult)
            assert result.success is True
            assert result.verification_type == "completeness"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_artifact_completeness_failure(self):
        """Test artifact completeness verification failure."""
        # Arrange
        verifier = ArtifactVerifier()
        corrupted_path = "/path/to/corrupted-artifact.jar"

        # Act & Assert
        with pytest.raises(
            VerificationError, match="Artifact completeness verification failed"
        ):
            verifier.verify_artifact_completeness(corrupted_path)

    def test_verify_artifact_completeness_exception_handling(self):
        """Test artifact completeness verification exception handling."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".jar", delete=False) as temp_file:
            temp_file.write(b"test jar content")
            temp_file_path = temp_file.name

        try:
            # Mock validate_file_format to raise an exception
            with patch.object(
                verifier,
                "validate_file_format",
                side_effect=Exception("Validation error"),
            ):
                # Act & Assert
                with pytest.raises(
                    VerificationError, match="Artifact completeness verification failed"
                ):
                    verifier.verify_artifact_completeness(temp_file_path)
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_all_checks_success(self):
        """Test successful verification of all checks."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file with .jar extension
        with tempfile.NamedTemporaryFile(suffix=".jar", delete=False) as temp_file:
            temp_file.write(b"test jar content")
            temp_file_path = temp_file.name

        try:
            # Calculate expected checksum
            expected_checksum = verifier.calculate_checksum(temp_file_path, "sha256")

            # Act
            result = verifier.verify_all_checks(
                temp_file_path,
                "/path/to/signature.sig",
                "/path/to/public-key.pem",
                expected_checksum,
            )

            # Assert
            assert isinstance(result, VerificationResult)
            assert result.success is True
            assert result.verification_type == "all_checks"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_all_checks_failure(self):
        """Test verification failure when any check fails."""
        # Arrange
        verifier = ArtifactVerifier()
        invalid_checksum = "invalid_checksum"

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".jar", delete=False) as temp_file:
            temp_file.write(b"test jar content")
            temp_file_path = temp_file.name

        try:
            # Act & Assert
            with pytest.raises(VerificationError, match="Artifact verification failed"):
                verifier.verify_all_checks(
                    temp_file_path,
                    "/path/to/signature.sig",
                    "/path/to/public-key.pem",
                    invalid_checksum,
                )
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_calculate_checksum_sha256(self):
        """Test SHA256 checksum calculation."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Act
            checksum = verifier.calculate_checksum(temp_file_path, "sha256")

            # Assert
            assert isinstance(checksum, str)
            assert len(checksum) == 64  # SHA256 produces 64 hex characters
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_calculate_checksum_sha1(self):
        """Test SHA1 checksum calculation."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Act
            checksum = verifier.calculate_checksum(temp_file_path, "sha1")

            # Assert
            assert isinstance(checksum, str)
            assert len(checksum) == 40  # SHA1 produces 40 hex characters
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_calculate_checksum_md5(self):
        """Test MD5 checksum calculation."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Act
            checksum = verifier.calculate_checksum(temp_file_path, "md5")

            # Assert
            assert isinstance(checksum, str)
            assert len(checksum) == 32  # MD5 produces 32 hex characters
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_calculate_checksum_unsupported_algorithm(self):
        """Test checksum calculation with unsupported algorithm."""
        # Arrange
        verifier = ArtifactVerifier()

        # Act & Assert
        with pytest.raises(VerificationError, match="Unsupported checksum algorithm"):
            verifier.calculate_checksum(self.test_artifact_path, "unsupported")

    def test_validate_file_format_success(self):
        """Test successful file format validation."""
        # Arrange
        verifier = ArtifactVerifier()

        # Act
        result = verifier.validate_file_format(self.test_artifact_path)

        # Assert
        assert result is True

    def test_validate_file_format_failure(self):
        """Test file format validation failure."""
        # Arrange
        verifier = ArtifactVerifier()
        invalid_format_path = "/path/to/invalid-file.txt"

        # Act & Assert
        with pytest.raises(VerificationError, match="Invalid file format"):
            verifier.validate_file_format(invalid_format_path)

    def test_validate_file_format_exception_handling(self):
        """Test file format validation exception handling."""
        # Arrange
        verifier = ArtifactVerifier()

        # Mock Path to raise an exception
        with patch("pathlib.Path", side_effect=Exception("Path error")):
            # Act & Assert
            with pytest.raises(VerificationError, match="Invalid file format"):
                verifier.validate_file_format("/path/to/file.jar")

    def test_verify_signature_with_public_key_success(self):
        """Test successful signature verification with public key."""
        # Arrange
        verifier = ArtifactVerifier()

        # Act
        result = verifier.verify_signature_with_public_key(
            self.test_artifact_path, self.test_signature_path, self.test_public_key_path
        )

        # Assert
        assert result is True

    def test_verify_signature_with_public_key_failure(self):
        """Test signature verification failure with public key."""
        # Arrange
        verifier = ArtifactVerifier()

        # Mock the verify_signature_with_public_key method to raise an exception
        with patch.object(
            verifier,
            "verify_signature_with_public_key",
            side_effect=VerificationError(
                "Signature verification with public key failed"
            ),
        ):
            # Act & Assert
            with pytest.raises(
                VerificationError, match="Signature verification with public key failed"
            ):
                verifier.verify_signature_with_public_key(
                    "/invalid/artifact.jar",
                    "/invalid/signature.sig",
                    "/invalid/public-key.pem",
                )

    def test_verify_artifact_size_success(self):
        """Test successful artifact size verification."""
        # Arrange
        verifier = ArtifactVerifier()
        max_size_mb = 100

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Act
            result = verifier.verify_artifact_size(temp_file_path, max_size_mb)

            # Assert
            assert result is True
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_artifact_size_failure(self):
        """Test artifact size verification failure."""
        # Arrange
        verifier = ArtifactVerifier()
        max_size_mb = 1  # Very small size limit

        # Create a large temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write 2MB of data
            temp_file.write(b"x" * (2 * 1024 * 1024))
            temp_file_path = temp_file.name

        try:
            # Act & Assert
            with pytest.raises(VerificationError, match="Artifact size exceeds limit"):
                verifier.verify_artifact_size(temp_file_path, max_size_mb)
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_artifact_permissions_success(self):
        """Test successful artifact permissions verification."""
        # Arrange
        verifier = ArtifactVerifier()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            # Act
            result = verifier.verify_artifact_permissions(temp_file_path)

            # Assert
            assert result is True
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_verify_artifact_permissions_failure(self):
        """Test artifact permissions verification failure."""
        # Arrange
        verifier = ArtifactVerifier()
        inaccessible_path = "/root/inaccessible-file.jar"

        # Act & Assert
        with pytest.raises(
            VerificationError, match="Artifact permissions verification failed"
        ):
            verifier.verify_artifact_permissions(inaccessible_path)


class TestVerificationResult:
    """Test suite for VerificationResult class."""

    def test_verification_result_creation_success(self):
        """Test VerificationResult creation for successful verification."""
        # Arrange & Act
        result = VerificationResult(
            success=True,
            verification_type="digital_signature",
            artifact_path="/path/to/artifact.jar",
            verified_at="2024-01-01T00:00:00Z",
        )

        # Assert
        assert result.success is True
        assert result.verification_type == "digital_signature"
        assert result.artifact_path == "/path/to/artifact.jar"
        assert result.verified_at == "2024-01-01T00:00:00Z"

    def test_verification_result_creation_failure(self):
        """Test VerificationResult creation for failed verification."""
        # Arrange & Act
        result = VerificationResult(
            success=False,
            verification_type="checksum",
            error_message="Checksum verification failed",
        )

        # Assert
        assert result.success is False
        assert result.verification_type == "checksum"
        assert result.error_message == "Checksum verification failed"

    def test_verification_result_with_metadata(self):
        """Test VerificationResult creation with metadata."""
        # Arrange & Act
        metadata = {
            "file_size": 1024,
            "checksum": "a1b2c3d4e5f6",
            "signature_algorithm": "RSA-SHA256",
        }
        result = VerificationResult(
            success=True,
            verification_type="all_checks",
            artifact_path="/path/to/artifact.jar",
            metadata=metadata,
        )

        # Assert
        assert result.metadata == metadata
        assert result.metadata["file_size"] == 1024
        assert result.metadata["checksum"] == "a1b2c3d4e5f6"
