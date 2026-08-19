"""
MikroDok Security Infrastructure Package
Provides comprehensive security functionality including encryption, access control, secure storage, and integrity validation.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        # Enums
        EncryptionAlgorithm,
        KeyDerivationFunction,
        AccessLevel,
        SessionStatus,
        IntegrityAlgorithm,
        StorageType,
        
        # Configuration Classes
        EncryptionConfig,
        AccessControlConfig,
        SecureStorageConfig,
        IntegrityConfig,
        
        # Data Classes
        EncryptionResult,
        DecryptionResult,
        AccessSession,
        AccessRequest,
        AccessResult,
        SecureCredential,
        IntegrityResult,
        
        # Interfaces
        IEncryptionManager,
        IAccessController,
        ISecureStorage,
        IIntegrityValidator
    )
except ImportError:
    pass

# Import encryption manager components
try:
    from .encryption_manager_lg.encryption_manager_lg import (
        EncryptionManager,
        EncryptionError,
        DecryptionError
    )
except ImportError:
    pass

# Import access controller components
try:
    from .access_controller_lg.access_controller_lg import (
        AccessController,
        AccessControlError,
        SessionExpiredError
    )
except ImportError:
    pass

# Import secure storage components
try:
    from .secure_storage_lg.secure_storage_lg import (
        SecureStorage,
        SecureStorageError,
        CredentialNotFoundError
    )
except ImportError:
    pass

# Import integrity validator components
try:
    from .integrity_validator_lg.integrity_validator_lg import (
        IntegrityValidator,
        IntegrityValidationError
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'EncryptionAlgorithm',
    'KeyDerivationFunction',
    'AccessLevel',
    'SessionStatus',
    'IntegrityAlgorithm',
    'StorageType',
    'EncryptionConfig',
    'AccessControlConfig',
    'SecureStorageConfig',
    'IntegrityConfig',
    'EncryptionResult',
    'DecryptionResult',
    'AccessSession',
    'AccessRequest',
    'AccessResult',
    'SecureCredential',
    'IntegrityResult',
    'IEncryptionManager',
    'IAccessController',
    'ISecureStorage',
    'IIntegrityValidator',
    
    # Encryption Manager
    'EncryptionManager',
    'EncryptionError',
    'DecryptionError',
    
    # Access Controller
    'AccessController',
    'AccessControlError',
    'SessionExpiredError',
    
    # Secure Storage
    'SecureStorage',
    'SecureStorageError',
    'CredentialNotFoundError',
    
    # Integrity Validator
    'IntegrityValidator',
    'IntegrityValidationError'
]
