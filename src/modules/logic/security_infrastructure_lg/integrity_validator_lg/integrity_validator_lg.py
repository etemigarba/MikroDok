"""
Module: integrity_validator_lg
Description: Validates data integrity with checksums and signatures for tamper detection
Phase: 4
Location: /src/modules/logic/security_infrastructure_lg/integrity_validator_lg/integrity_validator_lg.py
"""

# Standard library imports
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
import threading

# Third-party imports
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# Local imports
from src.modules.logic.security_infrastructure_lg.base_interfaces import (
    IIntegrityValidator, IntegrityConfig, IntegrityResult, IntegrityAlgorithm
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager


class IntegrityValidationError(Exception):
    """Exception raised for integrity validation-related errors."""
    pass


class IntegrityValidator(IIntegrityValidator):
    """
    Validates data integrity with checksums and signatures.
    
    Provides SHA-256/SHA-512/BLAKE2b checksums, HMAC verification,
    digital signatures, and comprehensive tamper detection for data integrity.
    """
    
    def __init__(self, config: Optional[IntegrityConfig] = None):
        """
        Initialize integrity validator.
        
        Args:
            config: Integrity validation configuration
        """
        self._config = config or IntegrityConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._lock = threading.RLock()
        
        # Hash algorithm mapping
        self._hash_algorithms = {
            IntegrityAlgorithm.SHA256: hashlib.sha256,
            IntegrityAlgorithm.SHA512: hashlib.sha512,
            IntegrityAlgorithm.BLAKE2B: lambda: hashlib.blake2b(digest_size=32)
        }
        
        # HMAC algorithm mapping
        self._hmac_algorithms = {
            IntegrityAlgorithm.HMAC_SHA256: hashlib.sha256,
            IntegrityAlgorithm.HMAC_SHA512: hashlib.sha512
        }
        
        self._logger.info("IntegrityValidator initialized")
    
    def calculate_hash(self, data: bytes, config: Optional[IntegrityConfig] = None) -> str:
        """
        Calculate hash for data.
        
        Args:
            data: Data to hash
            config: Integrity configuration
            
        Returns:
            Calculated hash as hex string
        """
        try:
            # Use provided config or default
            integrity_config = config or self._config
            
            # Get hash algorithm
            if integrity_config.algorithm in self._hash_algorithms:
                hash_func = self._hash_algorithms[integrity_config.algorithm]()
                hash_func.update(data)
                return hash_func.hexdigest()
            else:
                raise IntegrityValidationError(f"Unsupported hash algorithm: {integrity_config.algorithm}")
                
        except Exception as e:
            self._logger.error(f"Hash calculation failed: {str(e)}")
            raise IntegrityValidationError(f"Hash calculation failed: {str(e)}")
    
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
        start_time = time.time()
        
        try:
            # Use provided config or default
            integrity_config = config or self._config
            
            # Calculate actual hash
            actual_hash = self.calculate_hash(data, integrity_config)
            
            # Compare hashes
            valid = actual_hash.lower() == expected_hash.lower()
            
            verification_time = time.time() - start_time
            
            result = IntegrityResult(
                valid=valid,
                algorithm=integrity_config.algorithm,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
                verification_time=verification_time
            )
            
            if valid:
                self._logger.debug(f"Data integrity verified successfully")
            else:
                self._logger.warning(f"Data integrity verification failed")
                result.error_message = "Hash mismatch detected"
            
            return result
            
        except Exception as e:
            self._logger.error(f"Data verification failed: {str(e)}")
            return IntegrityResult(
                valid=False,
                algorithm=config.algorithm if config else self._config.algorithm,
                error_message=str(e),
                verification_time=time.time() - start_time
            )
    
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
        try:
            if not file_path.exists():
                raise IntegrityValidationError(f"File not found: {file_path}")
            
            # Use provided config or default
            integrity_config = config or self._config
            
            # Get hash algorithm
            if integrity_config.algorithm in self._hash_algorithms:
                hash_func = self._hash_algorithms[integrity_config.algorithm]()
            else:
                raise IntegrityValidationError(f"Unsupported hash algorithm: {integrity_config.algorithm}")
            
            # Read file in chunks to handle large files
            chunk_size = 64 * 1024  # 64KB chunks
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_func.update(chunk)
            
            file_hash = hash_func.hexdigest()
            self._logger.debug(f"File hash calculated: {file_path}")
            
            return file_hash
            
        except Exception as e:
            self._logger.error(f"File hash calculation failed: {str(e)}")
            raise IntegrityValidationError(f"File hash calculation failed: {str(e)}")
    
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
        start_time = time.time()
        
        try:
            if not file_path.exists():
                return IntegrityResult(
                    valid=False,
                    algorithm=config.algorithm if config else self._config.algorithm,
                    error_message=f"File not found: {file_path}",
                    verification_time=time.time() - start_time
                )
            
            # Use provided config or default
            integrity_config = config or self._config
            
            # Get expected hash
            if expected_hash is None:
                checksum_file = file_path.with_suffix(
                    file_path.suffix + integrity_config.checksum_file_extension
                )
                if checksum_file.exists():
                    expected_hash = self._read_checksum_file(checksum_file)
                else:
                    return IntegrityResult(
                        valid=False,
                        algorithm=integrity_config.algorithm,
                        error_message="No expected hash provided and no checksum file found",
                        verification_time=time.time() - start_time
                    )
            
            # Calculate actual hash
            actual_hash = self.calculate_file_hash(file_path, integrity_config)
            
            # Compare hashes
            valid = actual_hash.lower() == expected_hash.lower()
            
            verification_time = time.time() - start_time
            
            result = IntegrityResult(
                valid=valid,
                algorithm=integrity_config.algorithm,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
                verification_time=verification_time
            )
            
            if valid:
                self._logger.debug(f"File integrity verified: {file_path}")
            else:
                self._logger.warning(f"File integrity verification failed: {file_path}")
                result.error_message = "File hash mismatch detected"
            
            return result
            
        except Exception as e:
            self._logger.error(f"File verification failed: {str(e)}")
            return IntegrityResult(
                valid=False,
                algorithm=config.algorithm if config else self._config.algorithm,
                error_message=str(e),
                verification_time=time.time() - start_time
            )
    
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
        try:
            if not file_path.exists():
                raise IntegrityValidationError(f"File not found: {file_path}")
            
            # Use provided config or default
            integrity_config = config or self._config
            
            # Calculate file hash
            file_hash = self.calculate_file_hash(file_path, integrity_config)
            
            # Create checksum file
            checksum_file = file_path.with_suffix(
                file_path.suffix + integrity_config.checksum_file_extension
            )
            
            checksum_data = {
                'file_path': str(file_path),
                'algorithm': integrity_config.algorithm.value,
                'hash': file_hash,
                'created_at': time.time(),
                'file_size': file_path.stat().st_size,
                'file_mtime': file_path.stat().st_mtime
            }
            
            with open(checksum_file, 'w') as f:
                json.dump(checksum_data, f, indent=2)
            
            self._logger.info(f"Checksum file created: {checksum_file}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to create checksum file: {str(e)}")
            return False

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
        start_time = time.time()

        try:
            # Load public key
            public_key_obj = serialization.load_pem_public_key(
                public_key,
                backend=default_backend()
            )

            # Verify signature
            try:
                public_key_obj.verify(
                    signature,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                valid = True
                error_message = None
            except Exception:
                valid = False
                error_message = "Digital signature verification failed"

            verification_time = time.time() - start_time

            result = IntegrityResult(
                valid=valid,
                algorithm=IntegrityAlgorithm.SHA256,  # Used for signature
                error_message=error_message,
                verification_time=verification_time
            )

            if valid:
                self._logger.debug("Digital signature verified successfully")
            else:
                self._logger.warning("Digital signature verification failed")

            return result

        except Exception as e:
            self._logger.error(f"Signature verification failed: {str(e)}")
            return IntegrityResult(
                valid=False,
                algorithm=IntegrityAlgorithm.SHA256,
                error_message=str(e),
                verification_time=time.time() - start_time
            )

    def calculate_hmac(self, data: bytes, key: bytes,
                      algorithm: IntegrityAlgorithm = IntegrityAlgorithm.HMAC_SHA256) -> str:
        """
        Calculate HMAC for data.

        Args:
            data: Data to authenticate
            key: Secret key for HMAC
            algorithm: HMAC algorithm to use

        Returns:
            HMAC as hex string
        """
        try:
            if algorithm not in self._hmac_algorithms:
                raise IntegrityValidationError(f"Unsupported HMAC algorithm: {algorithm}")

            hash_func = self._hmac_algorithms[algorithm]
            mac = hmac.new(key, data, hash_func)

            return mac.hexdigest()

        except Exception as e:
            self._logger.error(f"HMAC calculation failed: {str(e)}")
            raise IntegrityValidationError(f"HMAC calculation failed: {str(e)}")

    def verify_hmac(self, data: bytes, key: bytes, expected_hmac: str,
                   algorithm: IntegrityAlgorithm = IntegrityAlgorithm.HMAC_SHA256) -> IntegrityResult:
        """
        Verify HMAC for data.

        Args:
            data: Data to verify
            key: Secret key for HMAC
            expected_hmac: Expected HMAC value
            algorithm: HMAC algorithm to use

        Returns:
            IntegrityResult with verification outcome
        """
        start_time = time.time()

        try:
            # Calculate actual HMAC
            actual_hmac = self.calculate_hmac(data, key, algorithm)

            # Compare HMACs using constant-time comparison
            valid = hmac.compare_digest(actual_hmac, expected_hmac)

            verification_time = time.time() - start_time

            result = IntegrityResult(
                valid=valid,
                algorithm=algorithm,
                expected_hash=expected_hmac,
                actual_hash=actual_hmac,
                verification_time=verification_time
            )

            if valid:
                self._logger.debug("HMAC verification successful")
            else:
                self._logger.warning("HMAC verification failed")
                result.error_message = "HMAC mismatch detected"

            return result

        except Exception as e:
            self._logger.error(f"HMAC verification failed: {str(e)}")
            return IntegrityResult(
                valid=False,
                algorithm=algorithm,
                error_message=str(e),
                verification_time=time.time() - start_time
            )

    def batch_verify_files(self, file_paths: list[Path],
                          config: Optional[IntegrityConfig] = None) -> Dict[str, IntegrityResult]:
        """
        Verify integrity of multiple files.

        Args:
            file_paths: List of file paths to verify
            config: Integrity configuration

        Returns:
            Dictionary mapping file paths to verification results
        """
        results = {}

        for file_path in file_paths:
            try:
                result = self.verify_file(file_path, config=config)
                results[str(file_path)] = result
            except Exception as e:
                self._logger.error(f"Failed to verify file {file_path}: {str(e)}")
                results[str(file_path)] = IntegrityResult(
                    valid=False,
                    algorithm=config.algorithm if config else self._config.algorithm,
                    error_message=str(e)
                )

        return results

    def _read_checksum_file(self, checksum_file: Path) -> str:
        """Read hash from checksum file."""
        try:
            with open(checksum_file, 'r') as f:
                checksum_data = json.load(f)
                return checksum_data.get('hash', '')
        except Exception as e:
            self._logger.error(f"Failed to read checksum file: {str(e)}")
            raise IntegrityValidationError(f"Failed to read checksum file: {str(e)}")

    def get_file_integrity_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Get integrity information for a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with integrity information or None if not available
        """
        try:
            checksum_file = file_path.with_suffix(
                file_path.suffix + self._config.checksum_file_extension
            )

            if not checksum_file.exists():
                return None

            with open(checksum_file, 'r') as f:
                return json.load(f)

        except Exception as e:
            self._logger.error(f"Failed to get integrity info: {str(e)}")
            return None
