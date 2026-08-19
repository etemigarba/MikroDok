"""
Module: checkpoint_validator_lg
Description: Validates checkpoint integrity using checksums, state verification, and corruption detection
Phase: 4
Location: /src/modules/logic/checkpoint_management_lg/checkpoint_validator_lg/
"""

# Standard library imports
import hashlib
import pickle
import threading
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Third-party imports
import torch

# Local imports
from ..base_interfaces import (
    ICheckpointValidator, CheckpointValidationResult, CheckpointMetadata, 
    CheckpointStatus, CheckpointType
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError, ErrorClassifier


class CheckpointValidationConfig:
    """Configuration for checkpoint validation operations."""
    
    def __init__(self,
                 verify_checksums: bool = True,
                 validate_state_structure: bool = True,
                 check_file_corruption: bool = True,
                 validate_metadata: bool = True,
                 strict_validation: bool = False,
                 max_file_size: int = 50 * 1024 * 1024 * 1024):  # 50GB
        """
        Initialize checkpoint validation configuration.
        
        Args:
            verify_checksums: Whether to verify file checksums
            validate_state_structure: Whether to validate state dictionary structure
            check_file_corruption: Whether to check for file corruption
            validate_metadata: Whether to validate checkpoint metadata
            strict_validation: Whether to use strict validation rules
            max_file_size: Maximum allowed checkpoint file size
        """
        self.verify_checksums = verify_checksums
        self.validate_state_structure = validate_state_structure
        self.check_file_corruption = check_file_corruption
        self.validate_metadata = validate_metadata
        self.strict_validation = strict_validation
        self.max_file_size = max_file_size


class IntegrityValidator:
    """Validates checkpoint file integrity."""
    
    def __init__(self):
        """Initialize integrity validator."""
        self._logger = get_logger(__name__)
    
    def verify_file_integrity(self, file_path: Path, expected_checksum: Optional[str] = None) -> Tuple[bool, str]:
        """
        Verify file integrity using checksum.
        
        Args:
            file_path: Path to checkpoint file
            expected_checksum: Expected checksum (if available)
            
        Returns:
            Tuple of (is_valid, actual_checksum)
        """
        try:
            if not file_path.exists():
                return False, ""
            
            # Calculate file checksum
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            
            actual_checksum = hasher.hexdigest()
            
            if expected_checksum:
                is_valid = actual_checksum.lower() == expected_checksum.lower()
            else:
                is_valid = True  # No expected checksum to compare against
            
            return is_valid, actual_checksum
            
        except Exception as e:
            self._logger.error(f"Failed to verify file integrity: {e}")
            return False, ""
    
    def check_file_corruption(self, file_path: Path) -> Tuple[bool, List[str]]:
        """
        Check for file corruption indicators.
        
        Args:
            file_path: Path to checkpoint file
            
        Returns:
            Tuple of (is_corrupted, corruption_indicators)
        """
        try:
            corruption_indicators = []
            
            if not file_path.exists():
                corruption_indicators.append("File does not exist")
                return True, corruption_indicators
            
            file_size = file_path.stat().st_size
            if file_size == 0:
                corruption_indicators.append("File is empty")
                return True, corruption_indicators
            
            # Try to read file header
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(1024)
                    if len(header) < 10:
                        corruption_indicators.append("File too small to contain valid checkpoint")
            except Exception as e:
                corruption_indicators.append(f"Cannot read file header: {e}")
            
            # Check for common corruption patterns
            try:
                with open(file_path, 'rb') as f:
                    # Check for null bytes at the beginning
                    first_bytes = f.read(100)
                    if first_bytes.count(b'\x00') > 50:
                        corruption_indicators.append("Excessive null bytes detected")
                    
                    # Check file ending
                    f.seek(-100, 2)  # Seek to 100 bytes from end
                    last_bytes = f.read(100)
                    if last_bytes.count(b'\x00') == len(last_bytes):
                        corruption_indicators.append("File ends with null bytes")
                        
            except Exception as e:
                corruption_indicators.append(f"Error reading file content: {e}")
            
            is_corrupted = len(corruption_indicators) > 0
            return is_corrupted, corruption_indicators
            
        except Exception as e:
            self._logger.error(f"Failed to check file corruption: {e}")
            return True, [f"Corruption check failed: {e}"]


class StateValidator:
    """Validates checkpoint state structure and content."""
    
    def __init__(self):
        """Initialize state validator."""
        self._logger = get_logger(__name__)
        self._required_fields = {
            'checkpoint_id', 'checkpoint_type', 'training_step', 
            'epoch', 'loss_value', 'created_at'
        }
    
    def validate_checkpoint_structure(self, checkpoint_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate checkpoint data structure.
        
        Args:
            checkpoint_data: Checkpoint data dictionary
            
        Returns:
            Tuple of (is_valid, validation_errors)
        """
        try:
            validation_errors = []
            
            # Check required fields
            missing_fields = self._required_fields - set(checkpoint_data.keys())
            if missing_fields:
                validation_errors.append(f"Missing required fields: {missing_fields}")
            
            # Validate field types and values
            if 'checkpoint_id' in checkpoint_data:
                if not isinstance(checkpoint_data['checkpoint_id'], str):
                    validation_errors.append("checkpoint_id must be a string")
            
            if 'training_step' in checkpoint_data:
                if not isinstance(checkpoint_data['training_step'], int) or checkpoint_data['training_step'] < 0:
                    validation_errors.append("training_step must be a non-negative integer")
            
            if 'epoch' in checkpoint_data:
                if not isinstance(checkpoint_data['epoch'], int) or checkpoint_data['epoch'] < 0:
                    validation_errors.append("epoch must be a non-negative integer")
            
            if 'loss_value' in checkpoint_data:
                if not isinstance(checkpoint_data['loss_value'], (int, float)):
                    validation_errors.append("loss_value must be a number")
            
            # Validate state dictionaries
            if 'model_state' in checkpoint_data:
                if not isinstance(checkpoint_data['model_state'], bytes):
                    validation_errors.append("model_state must be serialized bytes")
            
            if 'optimizer_state' in checkpoint_data:
                if not isinstance(checkpoint_data['optimizer_state'], bytes):
                    validation_errors.append("optimizer_state must be serialized bytes")
            
            is_valid = len(validation_errors) == 0
            return is_valid, validation_errors
            
        except Exception as e:
            self._logger.error(f"Failed to validate checkpoint structure: {e}")
            return False, [f"Structure validation failed: {e}"]
    
    def validate_state_content(self, state_data: bytes, state_type: str) -> Tuple[bool, List[str]]:
        """
        Validate state content by attempting deserialization.
        
        Args:
            state_data: Serialized state data
            state_type: Type of state (model/optimizer)
            
        Returns:
            Tuple of (is_valid, validation_errors)
        """
        try:
            validation_errors = []
            
            # Try to decompress if needed
            try:
                decompressed_data = zlib.decompress(state_data)
            except zlib.error:
                # Data might not be compressed
                decompressed_data = state_data
            
            # Try to deserialize
            try:
                state_dict = pickle.loads(decompressed_data)
                
                # Basic validation of state dictionary
                if not isinstance(state_dict, dict):
                    validation_errors.append(f"{state_type}_state must deserialize to a dictionary")
                elif len(state_dict) == 0:
                    validation_errors.append(f"{state_type}_state is empty")
                
            except pickle.PickleError as e:
                validation_errors.append(f"Failed to deserialize {state_type}_state: {e}")
            except Exception as e:
                validation_errors.append(f"Unexpected error deserializing {state_type}_state: {e}")
            
            is_valid = len(validation_errors) == 0
            return is_valid, validation_errors
            
        except Exception as e:
            self._logger.error(f"Failed to validate state content: {e}")
            return False, [f"State content validation failed: {e}"]


class CorruptionDetector:
    """Detects various forms of checkpoint corruption."""
    
    def __init__(self):
        """Initialize corruption detector."""
        self._logger = get_logger(__name__)
    
    def detect_corruption_patterns(self, file_path: Path) -> Tuple[bool, List[str], float]:
        """
        Detect corruption patterns in checkpoint file.
        
        Args:
            file_path: Path to checkpoint file
            
        Returns:
            Tuple of (is_corrupted, corruption_patterns, corruption_score)
        """
        try:
            corruption_patterns = []
            corruption_score = 0.0
            
            if not file_path.exists():
                return True, ["File does not exist"], 1.0
            
            file_size = file_path.stat().st_size
            
            with open(file_path, 'rb') as f:
                # Sample file content for analysis
                sample_size = min(file_size, 10240)  # 10KB sample
                sample_data = f.read(sample_size)
                
                # Check for excessive repetition
                unique_bytes = len(set(sample_data))
                if unique_bytes < 10:
                    corruption_patterns.append("Excessive byte repetition detected")
                    corruption_score += 0.3
                
                # Check for null byte patterns
                null_ratio = sample_data.count(b'\x00') / len(sample_data)
                if null_ratio > 0.5:
                    corruption_patterns.append("High null byte ratio")
                    corruption_score += 0.4
                
                # Check for random data patterns (entropy)
                byte_counts = [sample_data.count(bytes([i])) for i in range(256)]
                entropy = -sum((count / len(sample_data)) * 
                              (count / len(sample_data)).bit_length() 
                              for count in byte_counts if count > 0)
                
                if entropy < 2.0:  # Very low entropy
                    corruption_patterns.append("Suspiciously low data entropy")
                    corruption_score += 0.2
                elif entropy > 7.8:  # Very high entropy (random data)
                    corruption_patterns.append("Suspiciously high data entropy")
                    corruption_score += 0.1
            
            is_corrupted = corruption_score > 0.5
            return is_corrupted, corruption_patterns, corruption_score
            
        except Exception as e:
            self._logger.error(f"Failed to detect corruption patterns: {e}")
            return True, [f"Corruption detection failed: {e}"], 1.0


class CheckpointValidator(ICheckpointValidator):
    """Comprehensive checkpoint validation with integrity and corruption detection."""

    def __init__(self, config: Optional[CheckpointValidationConfig] = None):
        """
        Initialize checkpoint validator.

        Args:
            config: Validation configuration
        """
        self.config = config or CheckpointValidationConfig()
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()

        self.integrity_validator = IntegrityValidator()
        self.state_validator = StateValidator()
        self.corruption_detector = CorruptionDetector()

        # Thread safety
        self._lock = threading.RLock()

        self._logger.info("CheckpointValidator initialized")

    def validate_checkpoint(self, checkpoint_path: Path) -> CheckpointValidationResult:
        """
        Perform comprehensive checkpoint validation.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            CheckpointValidationResult with detailed validation information
        """
        try:
            validation_time = datetime.now(timezone.utc)
            result = CheckpointValidationResult(
                is_valid=True,
                checkpoint_id="unknown",
                validation_time=validation_time,
                file_size=0
            )

            # Basic file existence check
            if not checkpoint_path.exists():
                error = ValidationError(f"Checkpoint file does not exist: {checkpoint_path}")
                result.add_error(error)
                return result

            result.file_size = checkpoint_path.stat().st_size

            # Check file size limits
            if result.file_size > self.config.max_file_size:
                error = ValidationError(f"Checkpoint file too large: {result.file_size} bytes")
                result.add_error(error)
                return result

            # File corruption check
            if self.config.check_file_corruption:
                is_corrupted, corruption_indicators = self.integrity_validator.check_file_corruption(checkpoint_path)
                if is_corrupted:
                    result.corruption_detected = True
                    for indicator in corruption_indicators:
                        error = ValidationError(f"Corruption detected: {indicator}")
                        result.add_error(error)

                # Advanced corruption detection
                is_corrupted_adv, patterns, score = self.corruption_detector.detect_corruption_patterns(checkpoint_path)
                if is_corrupted_adv:
                    result.corruption_detected = True
                    for pattern in patterns:
                        result.add_warning(f"Corruption pattern: {pattern}")

            # Load and parse checkpoint
            try:
                checkpoint_data = self._load_checkpoint_data(checkpoint_path)
                if checkpoint_data:
                    result.checkpoint_id = checkpoint_data.get('checkpoint_id', 'unknown')
                else:
                    error = ValidationError("Failed to load checkpoint data")
                    result.add_error(error)
                    return result
            except Exception as e:
                error = ValidationError(f"Failed to load checkpoint: {e}")
                result.add_error(error)
                return result

            # Checksum verification
            if self.config.verify_checksums:
                is_valid, actual_checksum = self.integrity_validator.verify_file_integrity(checkpoint_path)
                result.actual_checksum = actual_checksum
                if not is_valid and result.expected_checksum:
                    result.integrity_check_passed = False
                    error = ValidationError("Checksum verification failed")
                    result.add_error(error)

            # Structure validation
            if self.config.validate_state_structure:
                is_valid, structure_errors = self.state_validator.validate_checkpoint_structure(checkpoint_data)
                if not is_valid:
                    result.state_check_passed = False
                    for error_msg in structure_errors:
                        error = ValidationError(f"Structure validation: {error_msg}")
                        result.add_error(error)

            # State content validation
            if self.config.validate_state_structure and 'model_state' in checkpoint_data:
                is_valid, content_errors = self.state_validator.validate_state_content(
                    checkpoint_data['model_state'], 'model'
                )
                if not is_valid:
                    result.state_check_passed = False
                    for error_msg in content_errors:
                        error = ValidationError(f"Model state validation: {error_msg}")
                        result.add_error(error)

            if self.config.validate_state_structure and 'optimizer_state' in checkpoint_data:
                is_valid, content_errors = self.state_validator.validate_state_content(
                    checkpoint_data['optimizer_state'], 'optimizer'
                )
                if not is_valid:
                    result.state_check_passed = False
                    for error_msg in content_errors:
                        error = ValidationError(f"Optimizer state validation: {error_msg}")
                        result.add_error(error)

            # Metadata validation
            if self.config.validate_metadata:
                metadata_errors = self._validate_metadata(checkpoint_data)
                for error_msg in metadata_errors:
                    result.add_warning(f"Metadata validation: {error_msg}")

            # Final validation result
            result.is_valid = (len(result.errors) == 0 and
                             result.integrity_check_passed and
                             result.state_check_passed and
                             not result.corruption_detected)

            if result.is_valid:
                self._logger.info(f"Checkpoint validation passed: {checkpoint_path}")
            else:
                self._logger.warning(f"Checkpoint validation failed: {checkpoint_path}")

            return result

        except Exception as e:
            self._logger.error(f"Checkpoint validation error: {e}")
            error_context = {'checkpoint_path': str(checkpoint_path)}
            self._error_classifier.classify_error(e, error_context)

            result = CheckpointValidationResult(
                is_valid=False,
                checkpoint_id="unknown",
                validation_time=datetime.now(timezone.utc)
            )
            result.add_error(ValidationError(f"Validation failed: {e}"))
            return result

    def verify_integrity(self, checkpoint_path: Path, expected_checksum: str) -> bool:
        """
        Verify checkpoint integrity against expected checksum.

        Args:
            checkpoint_path: Path to checkpoint file
            expected_checksum: Expected checksum value

        Returns:
            True if integrity verification passes
        """
        try:
            is_valid, actual_checksum = self.integrity_validator.verify_file_integrity(
                checkpoint_path, expected_checksum
            )

            if is_valid:
                self._logger.debug(f"Integrity verification passed: {checkpoint_path}")
            else:
                self._logger.warning(f"Integrity verification failed: {checkpoint_path}")
                self._logger.warning(f"Expected: {expected_checksum}, Actual: {actual_checksum}")

            return is_valid

        except Exception as e:
            self._logger.error(f"Integrity verification error: {e}")
            return False

    def _load_checkpoint_data(self, checkpoint_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint data from file.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Checkpoint data dictionary or None if failed
        """
        try:
            with open(checkpoint_path, 'rb') as f:
                checkpoint_bytes = f.read()

            # Try to deserialize
            try:
                checkpoint_data = pickle.loads(checkpoint_bytes)
                return checkpoint_data
            except pickle.PickleError:
                # Try decompression first
                try:
                    decompressed_data = zlib.decompress(checkpoint_bytes)
                    checkpoint_data = pickle.loads(decompressed_data)
                    return checkpoint_data
                except (zlib.error, pickle.PickleError):
                    return None

        except Exception as e:
            self._logger.error(f"Failed to load checkpoint data: {e}")
            return None

    def _validate_metadata(self, checkpoint_data: Dict[str, Any]) -> List[str]:
        """
        Validate checkpoint metadata.

        Args:
            checkpoint_data: Checkpoint data dictionary

        Returns:
            List of validation error messages
        """
        try:
            errors = []
            metadata = checkpoint_data.get('metadata', {})

            # Check for reasonable timestamp
            if 'created_at' in checkpoint_data:
                try:
                    created_at = datetime.fromisoformat(checkpoint_data['created_at'])
                    now = datetime.now(timezone.utc)
                    if created_at > now:
                        errors.append("Checkpoint creation time is in the future")
                except ValueError:
                    errors.append("Invalid timestamp format")

            # Check for reasonable loss values
            if 'loss_value' in checkpoint_data:
                loss = checkpoint_data['loss_value']
                if loss < 0:
                    errors.append("Negative loss value")
                elif loss > 1000:
                    errors.append("Unusually high loss value")

            # Check training step consistency
            if 'training_step' in checkpoint_data and 'epoch' in checkpoint_data:
                step = checkpoint_data['training_step']
                epoch = checkpoint_data['epoch']
                if step < epoch:
                    errors.append("Training step less than epoch number")

            return errors

        except Exception as e:
            self._logger.error(f"Metadata validation error: {e}")
            return [f"Metadata validation failed: {e}"]

    def batch_validate_checkpoints(self, checkpoint_paths: List[Path]) -> Dict[str, CheckpointValidationResult]:
        """
        Validate multiple checkpoints in batch.

        Args:
            checkpoint_paths: List of checkpoint file paths

        Returns:
            Dictionary mapping checkpoint paths to validation results
        """
        try:
            results = {}

            for checkpoint_path in checkpoint_paths:
                try:
                    result = self.validate_checkpoint(checkpoint_path)
                    results[str(checkpoint_path)] = result
                except Exception as e:
                    self._logger.error(f"Failed to validate checkpoint {checkpoint_path}: {e}")
                    result = CheckpointValidationResult(
                        is_valid=False,
                        checkpoint_id="unknown",
                        validation_time=datetime.now(timezone.utc)
                    )
                    result.add_error(ValidationError(f"Validation failed: {e}"))
                    results[str(checkpoint_path)] = result

            return results

        except Exception as e:
            self._logger.error(f"Batch validation error: {e}")
            return {}
