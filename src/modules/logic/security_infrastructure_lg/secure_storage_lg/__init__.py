"""
MikroDok Secure Storage Package
Provides secure storage for credentials and API keys with encryption and memory protection.
"""

from .secure_storage_lg import (
    SecureStorage,
    SecureStorageError,
    CredentialNotFoundError
)

__all__ = [
    'SecureStorage',
    'SecureStorageError',
    'CredentialNotFoundError'
]
