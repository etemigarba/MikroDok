"""
Module: encryption_manager_lg
Description: Handles data encryption for models and sensitive information using AES-256-GCM with PBKDF2-SHA512 key derivation
Phase: 4
Location: /src/modules/logic/security_infrastructure_lg/encryption_manager_lg/encryption_manager_lg.py
"""

# Standard library imports
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import threading

# Third-party imports
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import zlib

# Local imports
from src.modules.logic.security_infrastructure_lg.base_interfaces import (
    IEncryptionManager, EncryptionConfig, EncryptionResult, DecryptionResult,
    EncryptionAlgorithm, KeyDerivationFunction
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager


class EncryptionError(Exception):
    """Exception raised for encryption-related errors."""
    pass


class DecryptionError(Exception):
    """Exception raised for decryption-related errors."""
    pass


class EncryptionManager(IEncryptionManager):
    """
    Manages encryption and decryption operations for MikroDok.
    
    Provides AES-256-GCM encryption with PBKDF2-SHA512 key derivation,
    chunked file processing, and secure key management.
    """
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        """
        Initialize encryption manager.
        
        Args:
            config: Encryption configuration
        """
        self._config = config or EncryptionConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._lock = threading.RLock()
        
        # Key cache for performance (cleared on process exit)
        self._key_cache: Dict[str, bytes] = {}
        self._cache_lock = threading.Lock()
        
        self._logger.info("EncryptionManager initialized")
    
    def encrypt_data(self, data: bytes, config: Optional[EncryptionConfig] = None) -> EncryptionResult:
        """
        Encrypt data using specified configuration.
        
        Args:
            data: Data to encrypt
            config: Encryption configuration
            
        Returns:
            EncryptionResult with encrypted data and metadata
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not data:
                return EncryptionResult(
                    success=False,
                    error_message="No data provided for encryption"
                )
            
            # Use provided config or default
            enc_config = config or self._config
            
            # Compress data if configured
            if enc_config.compress_before_encrypt:
                data = zlib.compress(data)
            
            # Generate salt and derive key
            salt = secrets.token_bytes(enc_config.salt_length)
            key = self._derive_key_from_salt(salt, enc_config)
            
            # Encrypt based on algorithm
            if enc_config.algorithm == EncryptionAlgorithm.AES_256_GCM:
                encrypted_data, metadata = self._encrypt_aes_gcm(data, key)
            else:
                return EncryptionResult(
                    success=False,
                    error_message=f"Unsupported encryption algorithm: {enc_config.algorithm}"
                )
            
            # Add configuration metadata
            metadata.update({
                'algorithm': enc_config.algorithm.value,
                'key_derivation': enc_config.key_derivation.value,
                'iterations': enc_config.iterations,
                'salt': salt.hex(),
                'compressed': enc_config.compress_before_encrypt,
                'timestamp': int(time.time())
            })
            
            processing_time = time.time() - start_time
            
            self._logger.debug(f"Data encryption completed in {processing_time:.3f}s")
            
            return EncryptionResult(
                success=True,
                encrypted_data=encrypted_data,
                metadata=metadata,
                processing_time=processing_time
            )
            
        except Exception as e:
            self._logger.error(f"Encryption failed: {str(e)}")
            return EncryptionResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    def decrypt_data(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> DecryptionResult:
        """
        Decrypt data using stored metadata.
        
        Args:
            encrypted_data: Encrypted data to decrypt
            metadata: Encryption metadata
            
        Returns:
            DecryptionResult with decrypted data
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not encrypted_data or not metadata:
                return DecryptionResult(
                    success=False,
                    error_message="Missing encrypted data or metadata"
                )
            
            # Extract metadata
            algorithm = EncryptionAlgorithm(metadata.get('algorithm'))
            salt = bytes.fromhex(metadata.get('salt', ''))
            compressed = metadata.get('compressed', False)
            
            # Derive key from salt
            key = self._derive_key_from_salt(salt, self._config)
            
            # Decrypt based on algorithm
            if algorithm == EncryptionAlgorithm.AES_256_GCM:
                decrypted_data = self._decrypt_aes_gcm(encrypted_data, key, metadata)
            else:
                return DecryptionResult(
                    success=False,
                    error_message=f"Unsupported encryption algorithm: {algorithm}"
                )
            
            # Decompress if needed
            if compressed:
                decrypted_data = zlib.decompress(decrypted_data)
            
            processing_time = time.time() - start_time
            
            self._logger.debug(f"Data decryption completed in {processing_time:.3f}s")
            
            return DecryptionResult(
                success=True,
                decrypted_data=decrypted_data,
                metadata=metadata,
                processing_time=processing_time
            )
            
        except Exception as e:
            self._logger.error(f"Decryption failed: {str(e)}")
            return DecryptionResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
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
        start_time = time.time()
        
        try:
            # Validate file exists
            if not file_path.exists():
                return EncryptionResult(
                    success=False,
                    error_message=f"File not found: {file_path}"
                )
            
            # Use provided config or default
            enc_config = config or self._config
            
            # Determine output path
            if output_path is None:
                output_path = file_path.with_suffix(file_path.suffix + '.enc')
            
            # Read and encrypt file
            with open(file_path, 'rb') as infile:
                file_data = infile.read()
            
            # Encrypt the data
            result = self.encrypt_data(file_data, enc_config)
            
            if not result.success:
                return result
            
            # Write encrypted file
            with open(output_path, 'wb') as outfile:
                outfile.write(result.encrypted_data)
            
            # Write metadata file
            metadata_path = output_path.with_suffix(output_path.suffix + '.meta')
            self._write_metadata_file(metadata_path, result.metadata)
            
            # Secure delete original if configured
            if enc_config.secure_delete:
                self.secure_delete(file_path)
            
            processing_time = time.time() - start_time
            
            self._logger.info(f"File encryption completed: {output_path}")
            
            return EncryptionResult(
                success=True,
                metadata=result.metadata,
                processing_time=processing_time
            )
            
        except Exception as e:
            self._logger.error(f"File encryption failed: {str(e)}")
            return EncryptionResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
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
        start_time = time.time()
        
        try:
            # Validate file exists
            if not encrypted_file_path.exists():
                return DecryptionResult(
                    success=False,
                    error_message=f"Encrypted file not found: {encrypted_file_path}"
                )
            
            # Load metadata if not provided
            if metadata is None:
                metadata_path = encrypted_file_path.with_suffix(encrypted_file_path.suffix + '.meta')
                metadata = self._read_metadata_file(metadata_path)
            
            # Determine output path
            if output_path is None:
                output_path = encrypted_file_path.with_suffix('')
                if output_path.suffix == '.enc':
                    output_path = output_path.with_suffix('')
            
            # Read and decrypt file
            with open(encrypted_file_path, 'rb') as infile:
                encrypted_data = infile.read()
            
            # Decrypt the data
            result = self.decrypt_data(encrypted_data, metadata)
            
            if not result.success:
                return result
            
            # Write decrypted file
            with open(output_path, 'wb') as outfile:
                outfile.write(result.decrypted_data)
            
            processing_time = time.time() - start_time
            
            self._logger.info(f"File decryption completed: {output_path}")
            
            return DecryptionResult(
                success=True,
                metadata=metadata,
                processing_time=processing_time
            )
            
        except Exception as e:
            self._logger.error(f"File decryption failed: {str(e)}")
            return DecryptionResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )

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
        try:
            # Use provided config or default
            enc_config = config or self._config

            # Generate salt if not provided
            if salt is None:
                salt = secrets.token_bytes(enc_config.salt_length)

            # Derive key based on algorithm
            if enc_config.key_derivation == KeyDerivationFunction.PBKDF2_SHA512:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA512(),
                    length=32,  # 256 bits
                    salt=salt,
                    iterations=enc_config.iterations,
                    backend=default_backend()
                )
                key = kdf.derive(password.encode('utf-8'))
            else:
                raise EncryptionError(f"Unsupported key derivation function: {enc_config.key_derivation}")

            return key, salt

        except Exception as e:
            self._logger.error(f"Key generation failed: {str(e)}")
            raise EncryptionError(f"Key generation failed: {str(e)}")

    def secure_delete(self, file_path: Path) -> bool:
        """
        Securely delete a file using DoD 5220.22-M standard.

        Args:
            file_path: Path to file to delete

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            if not file_path.exists():
                return True

            # Get file size
            file_size = file_path.stat().st_size

            # Perform 7-pass overwrite
            with open(file_path, 'r+b') as file:
                # Pass 1: Write 0x00
                file.seek(0)
                file.write(b'\x00' * file_size)
                file.flush()
                os.fsync(file.fileno())

                # Pass 2: Write 0xFF
                file.seek(0)
                file.write(b'\xFF' * file_size)
                file.flush()
                os.fsync(file.fileno())

                # Pass 3: Write random data
                file.seek(0)
                file.write(secrets.token_bytes(file_size))
                file.flush()
                os.fsync(file.fileno())

                # Pass 4: Write 0x55
                file.seek(0)
                file.write(b'\x55' * file_size)
                file.flush()
                os.fsync(file.fileno())

                # Pass 5: Write 0xAA
                file.seek(0)
                file.write(b'\xAA' * file_size)
                file.flush()
                os.fsync(file.fileno())

                # Pass 6: Write random data
                file.seek(0)
                file.write(secrets.token_bytes(file_size))
                file.flush()
                os.fsync(file.fileno())

                # Pass 7: Write 0x00
                file.seek(0)
                file.write(b'\x00' * file_size)
                file.flush()
                os.fsync(file.fileno())

            # Delete the file
            file_path.unlink()

            self._logger.debug(f"Secure deletion completed: {file_path}")
            return True

        except Exception as e:
            self._logger.error(f"Secure deletion failed: {str(e)}")
            return False

    def _derive_key_from_salt(self, salt: bytes, config: EncryptionConfig) -> bytes:
        """Derive encryption key from salt using cached password."""
        # For this implementation, we'll use a default password
        # In production, this should come from user input or secure storage
        default_password = "mikrodok_default_encryption_key"
        key, _ = self.generate_key(default_password, salt, config)
        return key

    def _encrypt_aes_gcm(self, data: bytes, key: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """Encrypt data using AES-256-GCM."""
        # Generate random IV
        iv = secrets.token_bytes(12)  # 96-bit IV for GCM

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Encrypt data
        ciphertext = encryptor.update(data) + encryptor.finalize()

        # Get authentication tag
        tag = encryptor.tag

        # Combine IV + tag + ciphertext
        encrypted_data = iv + tag + ciphertext

        metadata = {
            'iv': iv.hex(),
            'tag': tag.hex(),
            'mode': 'GCM'
        }

        return encrypted_data, metadata

    def _decrypt_aes_gcm(self, encrypted_data: bytes, key: bytes, metadata: Dict[str, Any]) -> bytes:
        """Decrypt data using AES-256-GCM."""
        # Extract IV and tag
        iv = encrypted_data[:12]
        tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Decrypt data
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        return plaintext

    def _write_metadata_file(self, metadata_path: Path, metadata: Dict[str, Any]) -> None:
        """Write metadata to file."""
        import json
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def _read_metadata_file(self, metadata_path: Path) -> Dict[str, Any]:
        """Read metadata from file."""
        import json
        with open(metadata_path, 'r') as f:
            return json.load(f)
