"""
Module: checkpoint_recovery_lg
Description: Recovers training from checkpoints after interruptions or failures with state restoration
Phase: 4
Location: /src/modules/logic/checkpoint_management_lg/checkpoint_recovery_lg/
"""

# Standard library imports
import pickle
import threading
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party imports
import torch

# Local imports
from ..base_interfaces import (
    ICheckpointRecovery, RecoveryResult, CheckpointMetadata, 
    CheckpointStatus, CheckpointType
)
from ..checkpoint_validator_lg.checkpoint_validator_lg import CheckpointValidator, CheckpointValidationConfig
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class RecoveryConfig:
    """Configuration for checkpoint recovery operations."""
    
    def __init__(self,
                 validate_before_recovery: bool = True,
                 allow_partial_recovery: bool = True,
                 recovery_timeout: int = 300,  # 5 minutes
                 backup_failed_recovery: bool = True,
                 strict_version_matching: bool = False,
                 auto_repair_corruption: bool = False):
        """
        Initialize recovery configuration.
        
        Args:
            validate_before_recovery: Whether to validate checkpoint before recovery
            allow_partial_recovery: Whether to allow partial state recovery
            recovery_timeout: Maximum time for recovery operation (seconds)
            backup_failed_recovery: Whether to backup failed recovery attempts
            strict_version_matching: Whether to enforce strict version matching
            auto_repair_corruption: Whether to attempt automatic corruption repair
        """
        self.validate_before_recovery = validate_before_recovery
        self.allow_partial_recovery = allow_partial_recovery
        self.recovery_timeout = recovery_timeout
        self.backup_failed_recovery = backup_failed_recovery
        self.strict_version_matching = strict_version_matching
        self.auto_repair_corruption = auto_repair_corruption


class StateRestorer:
    """Handles restoration of model and optimizer states."""
    
    def __init__(self):
        """Initialize state restorer."""
        self._logger = get_logger(__name__)
    
    def restore_model_state(self, model_state_data: bytes, target_model: Optional[Any] = None) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Restore model state from serialized data.
        
        Args:
            model_state_data: Serialized model state data
            target_model: Target model to restore state to (optional)
            
        Returns:
            Tuple of (success, state_dict, errors)
        """
        try:
            errors = []
            
            # Deserialize model state
            try:
                # Try decompression first
                try:
                    decompressed_data = zlib.decompress(model_state_data)
                    model_state = pickle.loads(decompressed_data)
                except zlib.error:
                    # Data might not be compressed
                    model_state = pickle.loads(model_state_data)
            except Exception as e:
                errors.append(f"Failed to deserialize model state: {e}")
                return False, {}, errors
            
            # Validate state dictionary
            if not isinstance(model_state, dict):
                errors.append("Model state is not a dictionary")
                return False, {}, errors
            
            if len(model_state) == 0:
                errors.append("Model state is empty")
                return False, {}, errors
            
            # If target model provided, attempt to load state
            if target_model is not None:
                try:
                    # Check for state dict compatibility
                    if hasattr(target_model, 'state_dict'):
                        current_state = target_model.state_dict()
                        
                        # Check for missing or extra keys
                        missing_keys = set(current_state.keys()) - set(model_state.keys())
                        extra_keys = set(model_state.keys()) - set(current_state.keys())
                        
                        if missing_keys:
                            errors.append(f"Missing keys in checkpoint: {missing_keys}")
                        if extra_keys:
                            errors.append(f"Extra keys in checkpoint: {extra_keys}")
                        
                        # Load state with strict=False to allow partial loading
                        target_model.load_state_dict(model_state, strict=False)
                        
                except Exception as e:
                    errors.append(f"Failed to load state into model: {e}")
                    return False, model_state, errors
            
            success = len(errors) == 0
            return success, model_state, errors
            
        except Exception as e:
            self._logger.error(f"Model state restoration failed: {e}")
            return False, {}, [f"Model state restoration failed: {e}"]
    
    def restore_optimizer_state(self, optimizer_state_data: bytes, target_optimizer: Optional[Any] = None) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Restore optimizer state from serialized data.
        
        Args:
            optimizer_state_data: Serialized optimizer state data
            target_optimizer: Target optimizer to restore state to (optional)
            
        Returns:
            Tuple of (success, state_dict, errors)
        """
        try:
            errors = []
            
            # Deserialize optimizer state
            try:
                # Try decompression first
                try:
                    decompressed_data = zlib.decompress(optimizer_state_data)
                    optimizer_state = pickle.loads(decompressed_data)
                except zlib.error:
                    # Data might not be compressed
                    optimizer_state = pickle.loads(optimizer_state_data)
            except Exception as e:
                errors.append(f"Failed to deserialize optimizer state: {e}")
                return False, {}, errors
            
            # Validate state dictionary
            if not isinstance(optimizer_state, dict):
                errors.append("Optimizer state is not a dictionary")
                return False, {}, errors
            
            # If target optimizer provided, attempt to load state
            if target_optimizer is not None:
                try:
                    target_optimizer.load_state_dict(optimizer_state)
                except Exception as e:
                    errors.append(f"Failed to load state into optimizer: {e}")
                    return False, optimizer_state, errors
            
            success = len(errors) == 0
            return success, optimizer_state, errors
            
        except Exception as e:
            self._logger.error(f"Optimizer state restoration failed: {e}")
            return False, {}, [f"Optimizer state restoration failed: {e}"]


class RecoveryOrchestrator:
    """Orchestrates the complete recovery process."""
    
    def __init__(self, config: RecoveryConfig):
        """
        Initialize recovery orchestrator.
        
        Args:
            config: Recovery configuration
        """
        self.config = config
        self._logger = get_logger(__name__)
        self.state_restorer = StateRestorer()
        
        if config.validate_before_recovery:
            self.validator = CheckpointValidator(CheckpointValidationConfig(
                strict_validation=config.strict_version_matching
            ))
        else:
            self.validator = None
    
    def orchestrate_recovery(self, checkpoint_path: Path, target_model: Optional[Any] = None,
                           target_optimizer: Optional[Any] = None) -> RecoveryResult:
        """
        Orchestrate complete recovery process.
        
        Args:
            checkpoint_path: Path to checkpoint file
            target_model: Target model for state restoration
            target_optimizer: Target optimizer for state restoration
            
        Returns:
            RecoveryResult with recovery details
        """
        try:
            recovery_time = datetime.now(timezone.utc)
            result = RecoveryResult(
                success=False,
                checkpoint_id="unknown",
                recovery_time=recovery_time,
                recovered_step=0,
                recovered_epoch=0,
                recovered_loss=0.0
            )
            
            # Validate checkpoint if configured
            if self.config.validate_before_recovery and self.validator:
                validation_result = self.validator.validate_checkpoint(checkpoint_path)
                if not validation_result.is_valid:
                    for error in validation_result.errors:
                        result.add_error(f"Validation failed: {error}")
                    return result
                
                result.checkpoint_id = validation_result.checkpoint_id
            
            # Load checkpoint data
            checkpoint_data = self._load_checkpoint_data(checkpoint_path)
            if not checkpoint_data:
                result.add_error("Failed to load checkpoint data")
                return result
            
            # Extract metadata
            result.checkpoint_id = checkpoint_data.get('checkpoint_id', 'unknown')
            result.recovered_step = checkpoint_data.get('training_step', 0)
            result.recovered_epoch = checkpoint_data.get('epoch', 0)
            result.recovered_loss = checkpoint_data.get('loss_value', 0.0)
            
            # Restore model state
            if 'model_state' in checkpoint_data:
                model_success, model_state, model_errors = self.state_restorer.restore_model_state(
                    checkpoint_data['model_state'], target_model
                )
                
                if not model_success:
                    if self.config.allow_partial_recovery:
                        result.partial_recovery = True
                        for error in model_errors:
                            result.add_warning(f"Model recovery: {error}")
                    else:
                        for error in model_errors:
                            result.add_error(f"Model recovery: {error}")
                        return result
            
            # Restore optimizer state
            if 'optimizer_state' in checkpoint_data:
                optimizer_success, optimizer_state, optimizer_errors = self.state_restorer.restore_optimizer_state(
                    checkpoint_data['optimizer_state'], target_optimizer
                )
                
                if not optimizer_success:
                    if self.config.allow_partial_recovery:
                        result.partial_recovery = True
                        for error in optimizer_errors:
                            result.add_warning(f"Optimizer recovery: {error}")
                    else:
                        for error in optimizer_errors:
                            result.add_error(f"Optimizer recovery: {error}")
                        return result
            
            # Recovery successful
            result.success = True
            
            if result.partial_recovery:
                self._logger.warning(f"Partial recovery completed from checkpoint: {checkpoint_path}")
            else:
                self._logger.info(f"Full recovery completed from checkpoint: {checkpoint_path}")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Recovery orchestration failed: {e}")
            result = RecoveryResult(
                success=False,
                checkpoint_id="unknown",
                recovery_time=datetime.now(timezone.utc),
                recovered_step=0,
                recovered_epoch=0,
                recovered_loss=0.0
            )
            result.add_error(f"Recovery orchestration failed: {e}")
            return result
    
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


class CheckpointRecovery(ICheckpointRecovery):
    """Comprehensive checkpoint recovery with state restoration and error handling."""

    def __init__(self, config: Optional[RecoveryConfig] = None):
        """
        Initialize checkpoint recovery.

        Args:
            config: Recovery configuration
        """
        self.config = config or RecoveryConfig()
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()

        self.recovery_orchestrator = RecoveryOrchestrator(self.config)

        # Thread safety
        self._lock = threading.RLock()

        self._logger.info("CheckpointRecovery initialized")

    def recover_from_checkpoint(self, checkpoint_path: Path) -> RecoveryResult:
        """
        Recover training state from checkpoint with comprehensive error handling.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            RecoveryResult with detailed recovery information
        """
        try:
            with self._lock:
                self._logger.info(f"Starting recovery from checkpoint: {checkpoint_path}")

                # Basic validation
                if not checkpoint_path.exists():
                    result = RecoveryResult(
                        success=False,
                        checkpoint_id="unknown",
                        recovery_time=datetime.now(timezone.utc),
                        recovered_step=0,
                        recovered_epoch=0,
                        recovered_loss=0.0
                    )
                    result.add_error(f"Checkpoint file does not exist: {checkpoint_path}")
                    return result

                # Delegate to orchestrator
                result = self.recovery_orchestrator.orchestrate_recovery(checkpoint_path)

                if result.success:
                    self._logger.info(f"Recovery successful: {result.checkpoint_id}")
                else:
                    self._logger.error(f"Recovery failed: {result.checkpoint_id}")
                    error_context = {
                        'checkpoint_path': str(checkpoint_path),
                        'checkpoint_id': result.checkpoint_id
                    }
                    # Create a generic exception for error classification
                    recovery_error = Exception(f"Recovery failed: {'; '.join(result.errors)}")
                    self._error_classifier.classify_error(recovery_error, error_context)

                return result

        except Exception as e:
            self._logger.error(f"Recovery operation failed: {e}")
            error_context = {'checkpoint_path': str(checkpoint_path)}
            self._error_classifier.classify_error(e, error_context)

            result = RecoveryResult(
                success=False,
                checkpoint_id="unknown",
                recovery_time=datetime.now(timezone.utc),
                recovered_step=0,
                recovered_epoch=0,
                recovered_loss=0.0
            )
            result.add_error(f"Recovery operation failed: {e}")
            return result

    def find_latest_checkpoint(self, checkpoint_dir: Path) -> Optional[Path]:
        """
        Find the latest valid checkpoint in directory.

        Args:
            checkpoint_dir: Directory containing checkpoints

        Returns:
            Path to latest checkpoint or None if not found
        """
        try:
            if not checkpoint_dir.exists() or not checkpoint_dir.is_dir():
                self._logger.warning(f"Checkpoint directory does not exist: {checkpoint_dir}")
                return None

            # Find all checkpoint files
            checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pt"))

            if not checkpoint_files:
                self._logger.info(f"No checkpoint files found in: {checkpoint_dir}")
                return None

            # Sort by modification time (newest first)
            checkpoint_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Validate checkpoints and return first valid one
            for checkpoint_file in checkpoint_files:
                try:
                    if self.config.validate_before_recovery:
                        validator = CheckpointValidator()
                        validation_result = validator.validate_checkpoint(checkpoint_file)
                        if validation_result.is_valid:
                            self._logger.info(f"Latest valid checkpoint found: {checkpoint_file}")
                            return checkpoint_file
                        else:
                            self._logger.warning(f"Invalid checkpoint skipped: {checkpoint_file}")
                    else:
                        # Just check if file is readable
                        with open(checkpoint_file, 'rb') as f:
                            f.read(1024)  # Try to read first 1KB
                        self._logger.info(f"Latest checkpoint found: {checkpoint_file}")
                        return checkpoint_file

                except Exception as e:
                    self._logger.warning(f"Checkpoint validation failed for {checkpoint_file}: {e}")
                    continue

            self._logger.warning(f"No valid checkpoints found in: {checkpoint_dir}")
            return None

        except Exception as e:
            self._logger.error(f"Failed to find latest checkpoint: {e}")
            return None

    def find_best_checkpoint(self, checkpoint_dir: Path) -> Optional[Path]:
        """
        Find the best checkpoint based on loss value.

        Args:
            checkpoint_dir: Directory containing checkpoints

        Returns:
            Path to best checkpoint or None if not found
        """
        try:
            if not checkpoint_dir.exists() or not checkpoint_dir.is_dir():
                return None

            checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pt"))
            if not checkpoint_files:
                return None

            best_checkpoint = None
            best_loss = float('inf')

            for checkpoint_file in checkpoint_files:
                try:
                    # Load checkpoint metadata
                    checkpoint_data = self.recovery_orchestrator._load_checkpoint_data(checkpoint_file)
                    if not checkpoint_data:
                        continue

                    loss_value = checkpoint_data.get('loss_value', float('inf'))
                    if loss_value < best_loss:
                        best_loss = loss_value
                        best_checkpoint = checkpoint_file

                except Exception as e:
                    self._logger.warning(f"Failed to read checkpoint {checkpoint_file}: {e}")
                    continue

            if best_checkpoint:
                self._logger.info(f"Best checkpoint found: {best_checkpoint} (loss: {best_loss})")

            return best_checkpoint

        except Exception as e:
            self._logger.error(f"Failed to find best checkpoint: {e}")
            return None

    def recover_with_fallback(self, checkpoint_paths: List[Path]) -> RecoveryResult:
        """
        Attempt recovery with fallback to alternative checkpoints.

        Args:
            checkpoint_paths: List of checkpoint paths in order of preference

        Returns:
            RecoveryResult from first successful recovery
        """
        try:
            last_result = None

            for i, checkpoint_path in enumerate(checkpoint_paths):
                self._logger.info(f"Attempting recovery from checkpoint {i+1}/{len(checkpoint_paths)}: {checkpoint_path}")

                result = self.recover_from_checkpoint(checkpoint_path)

                if result.success:
                    self._logger.info(f"Recovery successful on attempt {i+1}")
                    return result
                else:
                    self._logger.warning(f"Recovery failed on attempt {i+1}: {'; '.join(result.errors)}")
                    last_result = result

            # All recovery attempts failed
            if last_result:
                last_result.add_error("All fallback recovery attempts failed")
                return last_result
            else:
                result = RecoveryResult(
                    success=False,
                    checkpoint_id="unknown",
                    recovery_time=datetime.now(timezone.utc),
                    recovered_step=0,
                    recovered_epoch=0,
                    recovered_loss=0.0
                )
                result.add_error("No checkpoint paths provided for recovery")
                return result

        except Exception as e:
            self._logger.error(f"Fallback recovery failed: {e}")
            result = RecoveryResult(
                success=False,
                checkpoint_id="unknown",
                recovery_time=datetime.now(timezone.utc),
                recovered_step=0,
                recovered_epoch=0,
                recovered_loss=0.0
            )
            result.add_error(f"Fallback recovery failed: {e}")
            return result

    def get_recovery_candidates(self, checkpoint_dir: Path, max_candidates: int = 5) -> List[Path]:
        """
        Get list of recovery candidate checkpoints.

        Args:
            checkpoint_dir: Directory containing checkpoints
            max_candidates: Maximum number of candidates to return

        Returns:
            List of checkpoint paths sorted by preference
        """
        try:
            if not checkpoint_dir.exists() or not checkpoint_dir.is_dir():
                return []

            checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pt"))
            if not checkpoint_files:
                return []

            # Score checkpoints based on multiple criteria
            scored_checkpoints = []

            for checkpoint_file in checkpoint_files:
                try:
                    score = 0.0

                    # Load checkpoint data
                    checkpoint_data = self.recovery_orchestrator._load_checkpoint_data(checkpoint_file)
                    if not checkpoint_data:
                        continue

                    # Score based on checkpoint type
                    checkpoint_type = checkpoint_data.get('checkpoint_type', 'periodic')
                    if checkpoint_type == 'best_model':
                        score += 100
                    elif checkpoint_type == 'milestone':
                        score += 50
                    elif checkpoint_type == 'final':
                        score += 75

                    # Score based on loss (lower is better)
                    loss_value = checkpoint_data.get('loss_value', float('inf'))
                    if loss_value != float('inf'):
                        score += max(0, 100 - loss_value)

                    # Score based on recency
                    file_age_hours = (datetime.now().timestamp() - checkpoint_file.stat().st_mtime) / 3600
                    recency_score = max(0, 50 - file_age_hours)
                    score += recency_score

                    scored_checkpoints.append((score, checkpoint_file))

                except Exception as e:
                    self._logger.warning(f"Failed to score checkpoint {checkpoint_file}: {e}")
                    continue

            # Sort by score (highest first) and return top candidates
            scored_checkpoints.sort(key=lambda x: x[0], reverse=True)
            candidates = [checkpoint for _, checkpoint in scored_checkpoints[:max_candidates]]

            self._logger.info(f"Found {len(candidates)} recovery candidates")
            return candidates

        except Exception as e:
            self._logger.error(f"Failed to get recovery candidates: {e}")
            return []
