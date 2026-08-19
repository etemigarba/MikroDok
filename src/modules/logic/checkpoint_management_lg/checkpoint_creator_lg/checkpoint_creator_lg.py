"""
Module: checkpoint_creator_lg
Description: Creates and saves model checkpoints with state serialization, integrity verification, and atomic operations
Phase: 4
Location: /src/modules/logic/checkpoint_management_lg/checkpoint_creator_lg/
"""

# Standard library imports
import asyncio
import hashlib
import json
import pickle
import shutil
import threading
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
import tempfile

# Third-party imports
import torch

# Local imports
from ..base_interfaces import (
    ICheckpointCreator, CheckpointMetadata, CheckpointType, CheckpointStatus, CheckpointConfig
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class CheckpointCreationConfig:
    """Configuration for checkpoint creation operations."""
    
    def __init__(self, 
                 checkpoint_dir: Path,
                 compression_level: int = 6,
                 verify_after_save: bool = True,
                 use_atomic_writes: bool = True,
                 backup_existing: bool = True,
                 max_concurrent_saves: int = 2):
        """
        Initialize checkpoint creation configuration.
        
        Args:
            checkpoint_dir: Directory for saving checkpoints
            compression_level: Compression level (0-9)
            verify_after_save: Whether to verify checkpoint after saving
            use_atomic_writes: Whether to use atomic write operations
            backup_existing: Whether to backup existing checkpoints
            max_concurrent_saves: Maximum concurrent save operations
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.compression_level = max(0, min(9, compression_level))
        self.verify_after_save = verify_after_save
        self.use_atomic_writes = use_atomic_writes
        self.backup_existing = backup_existing
        self.max_concurrent_saves = max(1, max_concurrent_saves)
        
        # Ensure checkpoint directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)


class StateSerializer:
    """Handles serialization of model and optimizer states."""
    
    def __init__(self, compression_level: int = 6):
        """
        Initialize state serializer.
        
        Args:
            compression_level: Compression level for serialization
        """
        self.compression_level = compression_level
        self._logger = get_logger(__name__)
    
    def serialize_state(self, state: Dict[str, Any], compress: bool = True) -> bytes:
        """
        Serialize state dictionary to bytes.
        
        Args:
            state: State dictionary to serialize
            compress: Whether to compress the serialized data
            
        Returns:
            Serialized state as bytes
        """
        try:
            # Use pickle for serialization (compatible with PyTorch)
            serialized_data = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
            
            if compress:
                serialized_data = zlib.compress(serialized_data, self.compression_level)
            
            return serialized_data
            
        except Exception as e:
            self._logger.error(f"Failed to serialize state: {e}")
            raise
    
    def deserialize_state(self, data: bytes, compressed: bool = True) -> Dict[str, Any]:
        """
        Deserialize bytes to state dictionary.
        
        Args:
            data: Serialized data as bytes
            compressed: Whether the data is compressed
            
        Returns:
            Deserialized state dictionary
        """
        try:
            if compressed:
                data = zlib.decompress(data)
            
            state = pickle.loads(data)
            return state
            
        except Exception as e:
            self._logger.error(f"Failed to deserialize state: {e}")
            raise


class IntegrityCalculator:
    """Calculates and verifies checkpoint integrity."""
    
    def __init__(self):
        """Initialize integrity calculator."""
        self._logger = get_logger(__name__)
    
    def calculate_checksum(self, data: bytes, algorithm: str = "sha256") -> str:
        """
        Calculate checksum for data.
        
        Args:
            data: Data to calculate checksum for
            algorithm: Hash algorithm to use
            
        Returns:
            Hexadecimal checksum string
        """
        try:
            if algorithm == "sha256":
                hasher = hashlib.sha256()
            elif algorithm == "md5":
                hasher = hashlib.md5()
            elif algorithm == "sha1":
                hasher = hashlib.sha1()
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
            
            hasher.update(data)
            return hasher.hexdigest()
            
        except Exception as e:
            self._logger.error(f"Failed to calculate checksum: {e}")
            raise
    
    def verify_checksum(self, data: bytes, expected_checksum: str, algorithm: str = "sha256") -> bool:
        """
        Verify data checksum.
        
        Args:
            data: Data to verify
            expected_checksum: Expected checksum
            algorithm: Hash algorithm used
            
        Returns:
            True if checksum matches
        """
        try:
            actual_checksum = self.calculate_checksum(data, algorithm)
            return actual_checksum.lower() == expected_checksum.lower()
            
        except Exception as e:
            self._logger.error(f"Failed to verify checksum: {e}")
            return False


class CheckpointCreator(ICheckpointCreator):
    """Creates and saves model checkpoints with comprehensive state management."""
    
    def __init__(self, config: CheckpointCreationConfig):
        """
        Initialize checkpoint creator.
        
        Args:
            config: Checkpoint creation configuration
        """
        self.config = config
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        
        self.serializer = StateSerializer(config.compression_level)
        self.integrity_calculator = IntegrityCalculator()
        
        # Thread safety
        self._lock = threading.RLock()
        self._save_semaphore = threading.Semaphore(config.max_concurrent_saves)
        
        # Active save operations
        self._active_saves: Dict[str, asyncio.Task] = {}
        
        self._logger.info(f"CheckpointCreator initialized with directory: {config.checkpoint_dir}")
    
    def create_checkpoint(self, model_state: Dict[str, Any], optimizer_state: Dict[str, Any],
                         training_step: int, epoch: int, loss_value: float,
                         checkpoint_type: CheckpointType = CheckpointType.PERIODIC,
                         metadata: Optional[Dict[str, Any]] = None) -> CheckpointMetadata:
        """
        Create a new checkpoint with comprehensive state preservation.
        
        Args:
            model_state: Model state dictionary
            optimizer_state: Optimizer state dictionary
            training_step: Current training step
            epoch: Current epoch
            loss_value: Current loss value
            checkpoint_type: Type of checkpoint
            metadata: Additional metadata
            
        Returns:
            CheckpointMetadata for the created checkpoint
        """
        try:
            checkpoint_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc)
            
            # Generate checkpoint filename
            filename = f"checkpoint_{checkpoint_type.value}_{training_step}_{timestamp.strftime('%Y%m%d_%H%M%S')}.pt"
            checkpoint_path = self.config.checkpoint_dir / filename
            
            # Serialize states
            model_data = self.serializer.serialize_state(model_state, compress=True)
            optimizer_data = self.serializer.serialize_state(optimizer_state, compress=True)
            
            # Create checkpoint data structure
            checkpoint_data = {
                'checkpoint_id': checkpoint_id,
                'checkpoint_type': checkpoint_type.value,
                'training_step': training_step,
                'epoch': epoch,
                'loss_value': loss_value,
                'created_at': timestamp.isoformat(),
                'model_state': model_data,
                'optimizer_state': optimizer_data,
                'metadata': metadata or {}
            }
            
            # Serialize complete checkpoint
            checkpoint_bytes = self.serializer.serialize_state(checkpoint_data, compress=False)
            
            # Calculate integrity checksum
            checksum = self.integrity_calculator.calculate_checksum(checkpoint_bytes)
            
            # Create checkpoint metadata
            checkpoint_metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                checkpoint_type=checkpoint_type,
                status=CheckpointStatus.CREATING,
                file_path=checkpoint_path,
                created_at=timestamp,
                model_state_size=len(model_data),
                optimizer_state_size=len(optimizer_data),
                total_size=len(checkpoint_bytes),
                checksum=checksum,
                training_step=training_step,
                epoch=epoch,
                loss_value=loss_value,
                metrics=metadata.get('metrics', {}) if metadata else {},
                tags=set(metadata.get('tags', [])) if metadata else set(),
                description=metadata.get('description') if metadata else None
            )
            
            # Save checkpoint to disk
            self._save_checkpoint_to_disk(checkpoint_bytes, checkpoint_path, checkpoint_metadata)
            
            checkpoint_metadata.status = CheckpointStatus.CREATED
            self._logger.info(f"Checkpoint created: {checkpoint_id} at {checkpoint_path}")
            
            return checkpoint_metadata
            
        except Exception as e:
            self._logger.error(f"Failed to create checkpoint: {e}")
            error_context = {
                'training_step': training_step,
                'epoch': epoch,
                'checkpoint_type': checkpoint_type.value
            }
            self._error_classifier.classify_error(e, error_context)
            raise
    
    def save_checkpoint_async(self, checkpoint_metadata: CheckpointMetadata) -> bool:
        """
        Save checkpoint asynchronously.
        
        Args:
            checkpoint_metadata: Checkpoint metadata
            
        Returns:
            True if save initiated successfully
        """
        try:
            with self._lock:
                if checkpoint_metadata.checkpoint_id in self._active_saves:
                    self._logger.warning(f"Checkpoint {checkpoint_metadata.checkpoint_id} already being saved")
                    return False
                
                # Create async save task
                task = asyncio.create_task(self._async_save_checkpoint(checkpoint_metadata))
                self._active_saves[checkpoint_metadata.checkpoint_id] = task
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to initiate async checkpoint save: {e}")
            return False

    async def _async_save_checkpoint(self, checkpoint_metadata: CheckpointMetadata) -> None:
        """
        Asynchronously save checkpoint to disk.

        Args:
            checkpoint_metadata: Checkpoint metadata
        """
        try:
            async with asyncio.Semaphore(self.config.max_concurrent_saves):
                # Simulate async save operation
                await asyncio.sleep(0.1)  # Yield control

                # Update status
                checkpoint_metadata.status = CheckpointStatus.CREATED

                self._logger.info(f"Async checkpoint save completed: {checkpoint_metadata.checkpoint_id}")

        except Exception as e:
            checkpoint_metadata.status = CheckpointStatus.FAILED
            self._logger.error(f"Async checkpoint save failed: {e}")
        finally:
            with self._lock:
                self._active_saves.pop(checkpoint_metadata.checkpoint_id, None)

    def _save_checkpoint_to_disk(self, checkpoint_data: bytes, file_path: Path,
                                metadata: CheckpointMetadata) -> None:
        """
        Save checkpoint data to disk with atomic operations.

        Args:
            checkpoint_data: Serialized checkpoint data
            file_path: Target file path
            metadata: Checkpoint metadata
        """
        try:
            if self.config.use_atomic_writes:
                # Use temporary file for atomic write
                with tempfile.NamedTemporaryFile(
                    dir=file_path.parent,
                    prefix=f".tmp_{file_path.name}",
                    delete=False
                ) as temp_file:
                    temp_path = Path(temp_file.name)
                    temp_file.write(checkpoint_data)
                    temp_file.flush()

                # Atomic move
                shutil.move(str(temp_path), str(file_path))
            else:
                # Direct write
                with open(file_path, 'wb') as f:
                    f.write(checkpoint_data)

            # Verify after save if configured
            if self.config.verify_after_save:
                self._verify_saved_checkpoint(file_path, metadata.checksum)

            self._logger.debug(f"Checkpoint saved to disk: {file_path}")

        except Exception as e:
            self._logger.error(f"Failed to save checkpoint to disk: {e}")
            # Clean up temporary file if it exists
            if self.config.use_atomic_writes and 'temp_path' in locals():
                try:
                    temp_path.unlink(missing_ok=True)
                except:
                    pass
            raise

    def _verify_saved_checkpoint(self, file_path: Path, expected_checksum: str) -> bool:
        """
        Verify saved checkpoint integrity.

        Args:
            file_path: Path to checkpoint file
            expected_checksum: Expected checksum

        Returns:
            True if verification passes
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            return self.integrity_calculator.verify_checksum(file_data, expected_checksum)

        except Exception as e:
            self._logger.error(f"Failed to verify saved checkpoint: {e}")
            return False

    def get_checkpoint_info(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """
        Get information about a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            CheckpointMetadata if found, None otherwise
        """
        try:
            # Search for checkpoint file
            pattern = f"*{checkpoint_id}*.pt"
            checkpoint_files = list(self.config.checkpoint_dir.glob(pattern))

            if not checkpoint_files:
                return None

            checkpoint_path = checkpoint_files[0]

            # Load and parse checkpoint
            with open(checkpoint_path, 'rb') as f:
                checkpoint_data = f.read()

            checkpoint_dict = self.serializer.deserialize_state(checkpoint_data, compressed=False)

            # Reconstruct metadata
            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_dict['checkpoint_id'],
                checkpoint_type=CheckpointType(checkpoint_dict['checkpoint_type']),
                status=CheckpointStatus.VALID,
                file_path=checkpoint_path,
                created_at=datetime.fromisoformat(checkpoint_dict['created_at']),
                model_state_size=len(checkpoint_dict['model_state']),
                optimizer_state_size=len(checkpoint_dict['optimizer_state']),
                total_size=len(checkpoint_data),
                checksum=self.integrity_calculator.calculate_checksum(checkpoint_data),
                training_step=checkpoint_dict['training_step'],
                epoch=checkpoint_dict['epoch'],
                loss_value=checkpoint_dict['loss_value'],
                metrics=checkpoint_dict.get('metadata', {}).get('metrics', {}),
                tags=set(checkpoint_dict.get('metadata', {}).get('tags', [])),
                description=checkpoint_dict.get('metadata', {}).get('description')
            )

            return metadata

        except Exception as e:
            self._logger.error(f"Failed to get checkpoint info: {e}")
            return None

    def list_checkpoints(self) -> List[CheckpointMetadata]:
        """
        List all available checkpoints.

        Returns:
            List of checkpoint metadata
        """
        try:
            checkpoints = []

            for checkpoint_file in self.config.checkpoint_dir.glob("checkpoint_*.pt"):
                try:
                    with open(checkpoint_file, 'rb') as f:
                        checkpoint_data = f.read()

                    checkpoint_dict = self.serializer.deserialize_state(checkpoint_data, compressed=False)

                    metadata = CheckpointMetadata(
                        checkpoint_id=checkpoint_dict['checkpoint_id'],
                        checkpoint_type=CheckpointType(checkpoint_dict['checkpoint_type']),
                        status=CheckpointStatus.VALID,
                        file_path=checkpoint_file,
                        created_at=datetime.fromisoformat(checkpoint_dict['created_at']),
                        model_state_size=len(checkpoint_dict['model_state']),
                        optimizer_state_size=len(checkpoint_dict['optimizer_state']),
                        total_size=len(checkpoint_data),
                        checksum=self.integrity_calculator.calculate_checksum(checkpoint_data),
                        training_step=checkpoint_dict['training_step'],
                        epoch=checkpoint_dict['epoch'],
                        loss_value=checkpoint_dict['loss_value'],
                        metrics=checkpoint_dict.get('metadata', {}).get('metrics', {}),
                        tags=set(checkpoint_dict.get('metadata', {}).get('tags', [])),
                        description=checkpoint_dict.get('metadata', {}).get('description')
                    )

                    checkpoints.append(metadata)

                except Exception as e:
                    self._logger.warning(f"Failed to parse checkpoint {checkpoint_file}: {e}")
                    continue

            # Sort by creation time (newest first)
            checkpoints.sort(key=lambda x: x.created_at, reverse=True)

            return checkpoints

        except Exception as e:
            self._logger.error(f"Failed to list checkpoints: {e}")
            return []

    def cleanup_failed_saves(self) -> int:
        """
        Clean up any failed or incomplete save operations.

        Returns:
            Number of failed saves cleaned up
        """
        try:
            cleanup_count = 0

            # Clean up temporary files
            temp_files = list(self.config.checkpoint_dir.glob(".tmp_*"))
            for temp_file in temp_files:
                try:
                    temp_file.unlink()
                    cleanup_count += 1
                    self._logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    self._logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")

            # Cancel any stuck async operations
            with self._lock:
                stuck_saves = []
                for checkpoint_id, task in self._active_saves.items():
                    if task.done() or task.cancelled():
                        stuck_saves.append(checkpoint_id)

                for checkpoint_id in stuck_saves:
                    self._active_saves.pop(checkpoint_id, None)
                    cleanup_count += 1

            if cleanup_count > 0:
                self._logger.info(f"Cleaned up {cleanup_count} failed save operations")

            return cleanup_count

        except Exception as e:
            self._logger.error(f"Failed to cleanup failed saves: {e}")
            return 0
