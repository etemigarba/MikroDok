"""
Module: base_interfaces
Description: Base interfaces and common data structures for security infrastructure modules
Phase: 4
Location: /src/modules/logic/security_infrastructure_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
import uuid

# Local imports
from src.modules.logic.error_handling_lg import ValidationError


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    CHACHA20_POLY1305 = "chacha20_poly1305"


class KeyDerivationFunction(Enum):
    """Supported key derivation functions."""
    PBKDF2_SHA512 = "pbkdf2_sha512"
    SCRYPT = "scrypt"
    ARGON2ID = "argon2id"


class AccessLevel(Enum):
    """Access levels for role-based access control."""
    NONE = "none"
    READ_ONLY = "read_only"
    STANDARD = "standard"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class SessionStatus(Enum):
    """Session status values."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class IntegrityAlgorithm(Enum):
    """Supported integrity verification algorithms."""
    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"


class StorageType(Enum):
    """Types of secure storage."""
    MEMORY = "memory"
    ENCRYPTED_FILE = "encrypted_file"
    KEYRING = "keyring"
    HARDWARE_SECURITY_MODULE = "hsm"


@dataclass
class EncryptionConfig:
    """Configuration for encryption operations."""
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key_derivation: KeyDerivationFunction = KeyDerivationFunction.PBKDF2_SHA512
    iterations: int = 256000
    salt_length: int = 32
    chunk_size: int = 1024 * 1024  # 1MB chunks
    compress_before_encrypt: bool = True
    secure_delete: bool = True


@dataclass
class AccessControlConfig:
    """Configuration for access control."""
    session_timeout: timedelta = field(default_factory=lambda: timedelta(hours=24))
    max_failed_attempts: int = 5
    lockout_duration: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    require_password_change: bool = False
    audit_all_access: bool = True
    enable_role_inheritance: bool = True


@dataclass
class SecureStorageConfig:
    """Configuration for secure storage."""
    storage_type: StorageType = StorageType.ENCRYPTED_FILE
    encryption_config: EncryptionConfig = field(default_factory=EncryptionConfig)
    backup_enabled: bool = True
    auto_backup_interval: timedelta = field(default_factory=lambda: timedelta(hours=6))
    max_backup_count: int = 10


@dataclass
class IntegrityConfig:
    """Configuration for integrity validation."""
    algorithm: IntegrityAlgorithm = IntegrityAlgorithm.SHA256
    verify_on_read: bool = True
    verify_on_write: bool = True
    store_checksums: bool = True
    checksum_file_extension: str = ".checksum"


@dataclass
class EncryptionResult:
    """Result of encryption operation."""
    success: bool
    encrypted_data: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    processing_time: float = 0.0


@dataclass
class DecryptionResult:
    """Result of decryption operation."""
    success: bool
    decrypted_data: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    processing_time: float = 0.0


@dataclass
class AccessSession:
    """Represents an access session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    access_level: AccessLevel = AccessLevel.NONE
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessRequest:
    """Represents an access request."""
    resource_id: str
    user_id: str
    requested_level: AccessLevel
    session_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AccessResult:
    """Result of access control check."""
    granted: bool
    session: Optional[AccessSession] = None
    required_level: AccessLevel = AccessLevel.NONE
    actual_level: AccessLevel = AccessLevel.NONE
    reason: Optional[str] = None
    audit_entry_id: Optional[str] = None


@dataclass
class SecureCredential:
    """Represents a secure credential."""
    credential_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    credential_type: str = ""
    encrypted_value: bytes = b""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


@dataclass
class IntegrityResult:
    """Result of integrity validation."""
    valid: bool
    algorithm: IntegrityAlgorithm
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    error_message: Optional[str] = None
    verification_time: float = 0.0


class IEncryptionManager(ABC):
    """Base interface for encryption management."""

    @abstractmethod
    def encrypt_data(self, data: bytes, config: Optional[EncryptionConfig] = None) -> EncryptionResult:
        """
        Encrypt data using specified configuration.
        
        Args:
            data: Data to encrypt
            config: Encryption configuration
            
        Returns:
            EncryptionResult with encrypted data and metadata
        """
        pass

    @abstractmethod
    def decrypt_data(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> DecryptionResult:
        """
        Decrypt data using stored metadata.
        
        Args:
            encrypted_data: Encrypted data to decrypt
            metadata: Encryption metadata
            
        Returns:
            DecryptionResult with decrypted data
        """
        pass

    @abstractmethod
    def encrypt_file(self, file_path: Path, output_path: Optional[Path] = None, 
                    config: Optional[EncryptionConfig] = None) -> EncryptionResult:
        """
        Encrypt a file with chunked processing.
        
        Args:
            file_path: Path to file to encrypt
            output_path: Path for encrypted file
            config: Encryption configuration
            
        Returns:
            EncryptionResult with operation status
        """
        pass

    @abstractmethod
    def decrypt_file(self, encrypted_file_path: Path, output_path: Optional[Path] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> DecryptionResult:
        """
        Decrypt a file with chunked processing.
        
        Args:
            encrypted_file_path: Path to encrypted file
            output_path: Path for decrypted file
            metadata: Encryption metadata
            
        Returns:
            DecryptionResult with operation status
        """
        pass

    @abstractmethod
    def generate_key(self, password: str, salt: Optional[bytes] = None,
                    config: Optional[EncryptionConfig] = None) -> Tuple[bytes, bytes]:
        """
        Generate encryption key from password.
        
        Args:
            password: Password for key derivation
            salt: Salt for key derivation
            config: Key derivation configuration
            
        Returns:
            Tuple of (key, salt)
        """
        pass

    @abstractmethod
    def secure_delete(self, file_path: Path) -> bool:
        """
        Securely delete a file.

        Args:
            file_path: Path to file to delete

        Returns:
            True if deletion successful, False otherwise
        """
        pass


class IAccessController(ABC):
    """Base interface for access control management."""

    @abstractmethod
    def create_session(self, user_id: str, access_level: AccessLevel,
                      config: Optional[AccessControlConfig] = None) -> AccessSession:
        """
        Create a new access session.

        Args:
            user_id: User identifier
            access_level: Requested access level
            config: Access control configuration

        Returns:
            AccessSession with session details
        """
        pass

    @abstractmethod
    def validate_access(self, request: AccessRequest) -> AccessResult:
        """
        Validate access request against permissions.

        Args:
            request: Access request to validate

        Returns:
            AccessResult with validation outcome
        """
        pass

    @abstractmethod
    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke an active session.

        Args:
            session_id: Session identifier to revoke

        Returns:
            True if revocation successful, False otherwise
        """
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[AccessSession]:
        """
        Get session information.

        Args:
            session_id: Session identifier

        Returns:
            AccessSession if found, None otherwise
        """
        pass

    @abstractmethod
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        pass

    @abstractmethod
    def audit_access(self, request: AccessRequest, result: AccessResult) -> str:
        """
        Log access attempt for audit trail.

        Args:
            request: Access request
            result: Access result

        Returns:
            Audit entry identifier
        """
        pass


class ISecureStorage(ABC):
    """Base interface for secure storage management."""

    @abstractmethod
    def store_credential(self, credential: SecureCredential,
                        config: Optional[SecureStorageConfig] = None) -> bool:
        """
        Store a credential securely.

        Args:
            credential: Credential to store
            config: Storage configuration

        Returns:
            True if storage successful, False otherwise
        """
        pass

    @abstractmethod
    def retrieve_credential(self, credential_id: str) -> Optional[SecureCredential]:
        """
        Retrieve a stored credential.

        Args:
            credential_id: Credential identifier

        Returns:
            SecureCredential if found, None otherwise
        """
        pass

    @abstractmethod
    def update_credential(self, credential: SecureCredential) -> bool:
        """
        Update an existing credential.

        Args:
            credential: Updated credential

        Returns:
            True if update successful, False otherwise
        """
        pass

    @abstractmethod
    def delete_credential(self, credential_id: str) -> bool:
        """
        Delete a stored credential.

        Args:
            credential_id: Credential identifier

        Returns:
            True if deletion successful, False otherwise
        """
        pass

    @abstractmethod
    def list_credentials(self, credential_type: Optional[str] = None) -> List[str]:
        """
        List stored credential identifiers.

        Args:
            credential_type: Filter by credential type

        Returns:
            List of credential identifiers
        """
        pass

    @abstractmethod
    def backup_storage(self, backup_path: Path) -> bool:
        """
        Create a backup of secure storage.

        Args:
            backup_path: Path for backup file

        Returns:
            True if backup successful, False otherwise
        """
        pass

    @abstractmethod
    def restore_storage(self, backup_path: Path) -> bool:
        """
        Restore secure storage from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if restore successful, False otherwise
        """
        pass


class IIntegrityValidator(ABC):
    """Base interface for integrity validation."""

    @abstractmethod
    def calculate_hash(self, data: bytes, config: Optional[IntegrityConfig] = None) -> str:
        """
        Calculate hash for data.

        Args:
            data: Data to hash
            config: Integrity configuration

        Returns:
            Calculated hash as hex string
        """
        pass

    @abstractmethod
    def verify_data(self, data: bytes, expected_hash: str,
                   config: Optional[IntegrityConfig] = None) -> IntegrityResult:
        """
        Verify data integrity against expected hash.

        Args:
            data: Data to verify
            expected_hash: Expected hash value
            config: Integrity configuration

        Returns:
            IntegrityResult with verification outcome
        """
        pass

    @abstractmethod
    def calculate_file_hash(self, file_path: Path,
                           config: Optional[IntegrityConfig] = None) -> str:
        """
        Calculate hash for file.

        Args:
            file_path: Path to file
            config: Integrity configuration

        Returns:
            Calculated hash as hex string
        """
        pass

    @abstractmethod
    def verify_file(self, file_path: Path, expected_hash: Optional[str] = None,
                   config: Optional[IntegrityConfig] = None) -> IntegrityResult:
        """
        Verify file integrity.

        Args:
            file_path: Path to file
            expected_hash: Expected hash (if None, reads from checksum file)
            config: Integrity configuration

        Returns:
            IntegrityResult with verification outcome
        """
        pass

    @abstractmethod
    def create_checksum_file(self, file_path: Path,
                            config: Optional[IntegrityConfig] = None) -> bool:
        """
        Create checksum file for a file.

        Args:
            file_path: Path to file
            config: Integrity configuration

        Returns:
            True if checksum file created successfully, False otherwise
        """
        pass

    @abstractmethod
    def verify_with_signature(self, data: bytes, signature: bytes,
                             public_key: bytes) -> IntegrityResult:
        """
        Verify data with digital signature.

        Args:
            data: Data to verify
            signature: Digital signature
            public_key: Public key for verification

        Returns:
            IntegrityResult with verification outcome
        """
        pass
