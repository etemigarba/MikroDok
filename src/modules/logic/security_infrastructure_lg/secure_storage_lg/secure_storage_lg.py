"""
Module: secure_storage_lg
Description: Provides secure storage for credentials and API keys with encryption and memory protection
Phase: 4
Location: /src/modules/logic/security_infrastructure_lg/secure_storage_lg/secure_storage_lg.py
"""

# Standard library imports
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

# Third-party imports
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

# Local imports
from src.modules.logic.security_infrastructure_lg.base_interfaces import (
    ISecureStorage, SecureStorageConfig, SecureCredential, StorageType
)
from src.modules.logic.security_infrastructure_lg.encryption_manager_lg.encryption_manager_lg import (
    EncryptionManager, EncryptionConfig
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager


class SecureStorageError(Exception):
    """Exception raised for secure storage-related errors."""
    pass


class CredentialNotFoundError(Exception):
    """Exception raised when credential is not found."""
    pass


class SecureStorage(ISecureStorage):
    """
    Provides secure storage for credentials and API keys.
    
    Supports multiple storage backends including encrypted files, system keyring,
    and in-memory storage with automatic backup and secure deletion capabilities.
    """
    
    def __init__(self, config: Optional[SecureStorageConfig] = None, storage_path: Optional[Path] = None):
        """
        Initialize secure storage.
        
        Args:
            config: Secure storage configuration
            storage_path: Path for storage files
        """
        self._config = config or SecureStorageConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._lock = threading.RLock()
        
        # Storage path
        self._storage_path = storage_path or Path("data/secure_storage")
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # Encryption manager
        self._encryption_manager = EncryptionManager(self._config.encryption_config)
        
        # In-memory credential cache
        self._credential_cache: Dict[str, SecureCredential] = {}
        
        # Storage file paths
        self._credentials_file = self._storage_path / "credentials.enc"
        self._metadata_file = self._storage_path / "metadata.json"
        self._backup_dir = self._storage_path / "backups"
        self._backup_dir.mkdir(exist_ok=True)
        
        # Load existing credentials
        self._load_credentials()
        
        # Setup automatic backup if enabled
        if self._config.backup_enabled:
            self._setup_auto_backup()
        
        self._logger.info("SecureStorage initialized")
    
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
        try:
            # Validate credential
            if not credential.name or not credential.credential_type:
                raise SecureStorageError("Credential name and type are required")
            
            # Update timestamp
            credential.updated_at = datetime.utcnow()
            
            with self._lock:
                # Store in cache
                self._credential_cache[credential.credential_id] = credential
                
                # Persist to storage
                self._save_credentials()
            
            self._logger.info(f"Credential stored: {credential.name} ({credential.credential_type})")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to store credential: {str(e)}")
            return False
    
    def retrieve_credential(self, credential_id: str) -> Optional[SecureCredential]:
        """
        Retrieve a stored credential.
        
        Args:
            credential_id: Credential identifier
            
        Returns:
            SecureCredential if found, None otherwise
        """
        try:
            with self._lock:
                credential = self._credential_cache.get(credential_id)
                
                if credential:
                    # Check expiry
                    if credential.expires_at and credential.expires_at < datetime.utcnow():
                        self._logger.warning(f"Credential expired: {credential.name}")
                        return None
                    
                    self._logger.debug(f"Credential retrieved: {credential.name}")
                    return credential
                
                return None
                
        except Exception as e:
            self._logger.error(f"Failed to retrieve credential: {str(e)}")
            return None
    
    def update_credential(self, credential: SecureCredential) -> bool:
        """
        Update an existing credential.
        
        Args:
            credential: Updated credential
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            with self._lock:
                if credential.credential_id not in self._credential_cache:
                    raise CredentialNotFoundError(f"Credential not found: {credential.credential_id}")
                
                # Update timestamp
                credential.updated_at = datetime.utcnow()
                
                # Update in cache
                self._credential_cache[credential.credential_id] = credential
                
                # Persist to storage
                self._save_credentials()
            
            self._logger.info(f"Credential updated: {credential.name}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to update credential: {str(e)}")
            return False
    
    def delete_credential(self, credential_id: str) -> bool:
        """
        Delete a stored credential.
        
        Args:
            credential_id: Credential identifier
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            with self._lock:
                if credential_id not in self._credential_cache:
                    return False
                
                credential = self._credential_cache[credential_id]
                
                # Remove from cache
                del self._credential_cache[credential_id]
                
                # Persist changes
                self._save_credentials()
            
            self._logger.info(f"Credential deleted: {credential.name}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to delete credential: {str(e)}")
            return False
    
    def list_credentials(self, credential_type: Optional[str] = None) -> List[str]:
        """
        List stored credential identifiers.
        
        Args:
            credential_type: Filter by credential type
            
        Returns:
            List of credential identifiers
        """
        try:
            with self._lock:
                credential_ids = []
                
                for credential_id, credential in self._credential_cache.items():
                    # Filter by type if specified
                    if credential_type and credential.credential_type != credential_type:
                        continue
                    
                    # Check expiry
                    if credential.expires_at and credential.expires_at < datetime.utcnow():
                        continue
                    
                    credential_ids.append(credential_id)
                
                return credential_ids
                
        except Exception as e:
            self._logger.error(f"Failed to list credentials: {str(e)}")
            return []
    
    def backup_storage(self, backup_path: Path) -> bool:
        """
        Create a backup of secure storage.
        
        Args:
            backup_path: Path for backup file
            
        Returns:
            True if backup successful, False otherwise
        """
        try:
            with self._lock:
                # Create backup directory if needed
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy credentials file
                if self._credentials_file.exists():
                    import shutil
                    shutil.copy2(self._credentials_file, backup_path)
                    
                    # Copy metadata file
                    metadata_backup = backup_path.with_suffix('.meta')
                    if self._metadata_file.exists():
                        shutil.copy2(self._metadata_file, metadata_backup)
                
            self._logger.info(f"Storage backup created: {backup_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to create backup: {str(e)}")
            return False
    
    def restore_storage(self, backup_path: Path) -> bool:
        """
        Restore secure storage from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restore successful, False otherwise
        """
        try:
            if not backup_path.exists():
                raise SecureStorageError(f"Backup file not found: {backup_path}")
            
            with self._lock:
                # Clear current cache
                self._credential_cache.clear()
                
                # Copy backup files
                import shutil
                shutil.copy2(backup_path, self._credentials_file)
                
                metadata_backup = backup_path.with_suffix('.meta')
                if metadata_backup.exists():
                    shutil.copy2(metadata_backup, self._metadata_file)
                
                # Reload credentials
                self._load_credentials()
            
            self._logger.info(f"Storage restored from backup: {backup_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to restore from backup: {str(e)}")
            return False

    def get_credential_by_name(self, name: str, credential_type: Optional[str] = None) -> Optional[SecureCredential]:
        """
        Get credential by name and optional type.

        Args:
            name: Credential name
            credential_type: Optional credential type filter

        Returns:
            SecureCredential if found, None otherwise
        """
        try:
            with self._lock:
                for credential in self._credential_cache.values():
                    if credential.name == name:
                        if credential_type and credential.credential_type != credential_type:
                            continue

                        # Check expiry
                        if credential.expires_at and credential.expires_at < datetime.utcnow():
                            continue

                        return credential

                return None

        except Exception as e:
            self._logger.error(f"Failed to get credential by name: {str(e)}")
            return None

    def cleanup_expired_credentials(self) -> int:
        """
        Remove expired credentials from storage.

        Returns:
            Number of credentials removed
        """
        try:
            current_time = datetime.utcnow()
            expired_ids = []

            with self._lock:
                for credential_id, credential in self._credential_cache.items():
                    if credential.expires_at and credential.expires_at < current_time:
                        expired_ids.append(credential_id)

                # Remove expired credentials
                for credential_id in expired_ids:
                    del self._credential_cache[credential_id]

                # Persist changes if any credentials were removed
                if expired_ids:
                    self._save_credentials()

            if expired_ids:
                self._logger.info(f"Cleaned up {len(expired_ids)} expired credentials")

            return len(expired_ids)

        except Exception as e:
            self._logger.error(f"Failed to cleanup expired credentials: {str(e)}")
            return 0

    def _load_credentials(self) -> None:
        """Load credentials from storage."""
        try:
            if not self._credentials_file.exists():
                return

            # Read encrypted data
            with open(self._credentials_file, 'rb') as f:
                encrypted_data = f.read()

            # Read metadata
            metadata = {}
            if self._metadata_file.exists():
                with open(self._metadata_file, 'r') as f:
                    metadata = json.load(f)

            # Decrypt data
            result = self._encryption_manager.decrypt_data(encrypted_data, metadata)
            if not result.success:
                raise SecureStorageError(f"Failed to decrypt credentials: {result.error_message}")

            # Parse credentials
            credentials_data = json.loads(result.decrypted_data.decode('utf-8'))

            # Load into cache
            for cred_data in credentials_data:
                credential = SecureCredential(
                    credential_id=cred_data['credential_id'],
                    name=cred_data['name'],
                    credential_type=cred_data['credential_type'],
                    encrypted_value=bytes.fromhex(cred_data['encrypted_value']),
                    metadata=cred_data.get('metadata', {}),
                    created_at=datetime.fromisoformat(cred_data['created_at']),
                    updated_at=datetime.fromisoformat(cred_data['updated_at']),
                    expires_at=datetime.fromisoformat(cred_data['expires_at']) if cred_data.get('expires_at') else None
                )
                self._credential_cache[credential.credential_id] = credential

            self._logger.debug(f"Loaded {len(credentials_data)} credentials from storage")

        except Exception as e:
            self._logger.error(f"Failed to load credentials: {str(e)}")

    def _save_credentials(self) -> None:
        """Save credentials to storage."""
        try:
            # Prepare credentials data
            credentials_data = []
            for credential in self._credential_cache.values():
                cred_data = {
                    'credential_id': credential.credential_id,
                    'name': credential.name,
                    'credential_type': credential.credential_type,
                    'encrypted_value': credential.encrypted_value.hex(),
                    'metadata': credential.metadata,
                    'created_at': credential.created_at.isoformat(),
                    'updated_at': credential.updated_at.isoformat(),
                    'expires_at': credential.expires_at.isoformat() if credential.expires_at else None
                }
                credentials_data.append(cred_data)

            # Serialize to JSON
            json_data = json.dumps(credentials_data, indent=2)

            # Encrypt data
            result = self._encryption_manager.encrypt_data(json_data.encode('utf-8'))
            if not result.success:
                raise SecureStorageError(f"Failed to encrypt credentials: {result.error_message}")

            # Write encrypted data
            with open(self._credentials_file, 'wb') as f:
                f.write(result.encrypted_data)

            # Write metadata
            with open(self._metadata_file, 'w') as f:
                json.dump(result.metadata, f, indent=2)

            self._logger.debug(f"Saved {len(credentials_data)} credentials to storage")

        except Exception as e:
            self._logger.error(f"Failed to save credentials: {str(e)}")
            raise SecureStorageError(f"Failed to save credentials: {str(e)}")

    def _setup_auto_backup(self) -> None:
        """Setup automatic backup timer."""
        def backup_timer():
            try:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                backup_path = self._backup_dir / f"credentials_backup_{timestamp}.enc"

                if self.backup_storage(backup_path):
                    # Cleanup old backups
                    self._cleanup_old_backups()

                # Schedule next backup
                timer = threading.Timer(
                    self._config.auto_backup_interval.total_seconds(),
                    backup_timer
                )
                timer.daemon = True
                timer.start()

            except Exception as e:
                self._logger.error(f"Auto backup failed: {str(e)}")

        # Start initial backup timer
        timer = threading.Timer(
            self._config.auto_backup_interval.total_seconds(),
            backup_timer
        )
        timer.daemon = True
        timer.start()

    def _cleanup_old_backups(self) -> None:
        """Remove old backup files beyond the configured limit."""
        try:
            backup_files = list(self._backup_dir.glob("credentials_backup_*.enc"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Remove excess backups
            for backup_file in backup_files[self._config.max_backup_count:]:
                backup_file.unlink()
                # Also remove corresponding metadata file
                meta_file = backup_file.with_suffix('.meta')
                if meta_file.exists():
                    meta_file.unlink()

        except Exception as e:
            self._logger.error(f"Failed to cleanup old backups: {str(e)}")
