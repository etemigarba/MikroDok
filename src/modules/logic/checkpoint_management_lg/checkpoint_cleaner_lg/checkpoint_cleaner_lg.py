"""
Module: checkpoint_cleaner_lg
Description: Manages checkpoint retention policies and cleanup of old checkpoints with configurable retention rules
Phase: 4
Location: /src/modules/logic/checkpoint_management_lg/checkpoint_cleaner_lg/
"""

# Standard library imports
import pickle
import shutil
import threading
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Local imports
from ..base_interfaces import (
    ICheckpointCleaner, CleanupResult, CheckpointMetadata, 
    CheckpointStatus, CheckpointType, RetentionPolicy
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class CleanupConfig:
    """Configuration for checkpoint cleanup operations."""
    
    def __init__(self,
                 checkpoint_dir: Path,
                 backup_before_delete: bool = True,
                 backup_dir: Optional[Path] = None,
                 dry_run: bool = False,
                 parallel_cleanup: bool = True,
                 verify_before_delete: bool = True,
                 preserve_best_models: bool = True,
                 preserve_milestones: bool = True):
        """
        Initialize cleanup configuration.
        
        Args:
            checkpoint_dir: Directory containing checkpoints
            backup_before_delete: Whether to backup checkpoints before deletion
            backup_dir: Directory for backups (defaults to checkpoint_dir/backups)
            dry_run: Whether to perform dry run without actual deletion
            parallel_cleanup: Whether to use parallel cleanup operations
            verify_before_delete: Whether to verify checkpoints before deletion
            preserve_best_models: Whether to preserve best model checkpoints
            preserve_milestones: Whether to preserve milestone checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.backup_before_delete = backup_before_delete
        self.backup_dir = Path(backup_dir) if backup_dir else self.checkpoint_dir / "backups"
        self.dry_run = dry_run
        self.parallel_cleanup = parallel_cleanup
        self.verify_before_delete = verify_before_delete
        self.preserve_best_models = preserve_best_models
        self.preserve_milestones = preserve_milestones
        
        # Ensure directories exist
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        if self.backup_before_delete:
            self.backup_dir.mkdir(parents=True, exist_ok=True)


class RetentionManager:
    """Manages checkpoint retention policies and rules."""
    
    def __init__(self, config: CleanupConfig):
        """
        Initialize retention manager.
        
        Args:
            config: Cleanup configuration
        """
        self.config = config
        self._logger = get_logger(__name__)
    
    def apply_retention_policy(self, checkpoints: List[CheckpointMetadata], 
                              policy: RetentionPolicy, 
                              retention_count: int = 5,
                              retention_days: int = 30) -> List[CheckpointMetadata]:
        """
        Apply retention policy to get cleanup candidates.
        
        Args:
            checkpoints: List of checkpoint metadata
            policy: Retention policy to apply
            retention_count: Number of checkpoints to keep
            retention_days: Number of days to keep checkpoints
            
        Returns:
            List of checkpoints to be cleaned up
        """
        try:
            cleanup_candidates = []
            
            if policy == RetentionPolicy.KEEP_ALL:
                return []
            
            # Sort checkpoints by creation time (newest first)
            sorted_checkpoints = sorted(checkpoints, key=lambda x: x.created_at, reverse=True)
            
            if policy == RetentionPolicy.KEEP_BEST:
                # Keep only best models and recent checkpoints
                best_checkpoints = [cp for cp in sorted_checkpoints if cp.is_best]
                recent_checkpoints = sorted_checkpoints[:retention_count]
                
                keep_set = set(cp.checkpoint_id for cp in best_checkpoints + recent_checkpoints)
                cleanup_candidates = [cp for cp in sorted_checkpoints if cp.checkpoint_id not in keep_set]
                
            elif policy == RetentionPolicy.KEEP_RECENT:
                # Keep only recent checkpoints
                cleanup_candidates = sorted_checkpoints[retention_count:]
                
            elif policy == RetentionPolicy.KEEP_MILESTONES:
                # Keep milestones and recent checkpoints
                milestone_checkpoints = [cp for cp in sorted_checkpoints 
                                       if cp.checkpoint_type in [CheckpointType.MILESTONE, CheckpointType.BEST_MODEL]]
                recent_checkpoints = sorted_checkpoints[:retention_count]
                
                keep_set = set(cp.checkpoint_id for cp in milestone_checkpoints + recent_checkpoints)
                cleanup_candidates = [cp for cp in sorted_checkpoints if cp.checkpoint_id not in keep_set]
                
            elif policy == RetentionPolicy.TIME_BASED:
                # Keep checkpoints newer than retention_days
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
                cleanup_candidates = [cp for cp in sorted_checkpoints if cp.created_at < cutoff_date]
                
            elif policy == RetentionPolicy.COUNT_BASED:
                # Keep only retention_count checkpoints
                cleanup_candidates = sorted_checkpoints[retention_count:]
                
            elif policy == RetentionPolicy.SIZE_BASED:
                # Keep checkpoints until total size exceeds limit
                total_size = 0
                max_size = retention_count * 1024 * 1024 * 1024  # retention_count in GB
                
                for i, checkpoint in enumerate(sorted_checkpoints):
                    total_size += checkpoint.total_size
                    if total_size > max_size:
                        cleanup_candidates = sorted_checkpoints[i:]
                        break
            
            # Apply preservation rules
            if self.config.preserve_best_models:
                cleanup_candidates = [cp for cp in cleanup_candidates if not cp.is_best]
            
            if self.config.preserve_milestones:
                cleanup_candidates = [cp for cp in cleanup_candidates 
                                    if cp.checkpoint_type not in [CheckpointType.MILESTONE, CheckpointType.FINAL]]
            
            self._logger.info(f"Retention policy {policy.value} identified {len(cleanup_candidates)} cleanup candidates")
            return cleanup_candidates
            
        except Exception as e:
            self._logger.error(f"Failed to apply retention policy: {e}")
            return []
    
    def get_checkpoint_metadata(self, checkpoint_path: Path) -> Optional[CheckpointMetadata]:
        """
        Extract metadata from checkpoint file.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            CheckpointMetadata or None if failed
        """
        try:
            with open(checkpoint_path, 'rb') as f:
                checkpoint_data = f.read()
            
            # Try to deserialize
            try:
                checkpoint_dict = pickle.loads(checkpoint_data)
            except pickle.PickleError:
                # Try decompression first
                try:
                    decompressed_data = zlib.decompress(checkpoint_data)
                    checkpoint_dict = pickle.loads(decompressed_data)
                except (zlib.error, pickle.PickleError):
                    return None
            
            # Create metadata object
            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_dict.get('checkpoint_id', 'unknown'),
                checkpoint_type=CheckpointType(checkpoint_dict.get('checkpoint_type', 'periodic')),
                status=CheckpointStatus.VALID,
                file_path=checkpoint_path,
                created_at=datetime.fromisoformat(checkpoint_dict.get('created_at', datetime.now().isoformat())),
                model_state_size=len(checkpoint_dict.get('model_state', b'')),
                optimizer_state_size=len(checkpoint_dict.get('optimizer_state', b'')),
                total_size=len(checkpoint_data),
                checksum="",  # Would need to calculate
                training_step=checkpoint_dict.get('training_step', 0),
                epoch=checkpoint_dict.get('epoch', 0),
                loss_value=checkpoint_dict.get('loss_value', 0.0),
                metrics=checkpoint_dict.get('metadata', {}).get('metrics', {}),
                tags=set(checkpoint_dict.get('metadata', {}).get('tags', [])),
                description=checkpoint_dict.get('metadata', {}).get('description'),
                is_best=checkpoint_dict.get('metadata', {}).get('is_best', False)
            )
            
            return metadata
            
        except Exception as e:
            self._logger.error(f"Failed to extract checkpoint metadata: {e}")
            return None


class CleanupOrchestrator:
    """Orchestrates the complete cleanup process."""
    
    def __init__(self, config: CleanupConfig):
        """
        Initialize cleanup orchestrator.
        
        Args:
            config: Cleanup configuration
        """
        self.config = config
        self._logger = get_logger(__name__)
        self.retention_manager = RetentionManager(config)
    
    def orchestrate_cleanup(self, retention_policy: RetentionPolicy,
                           retention_count: int = 5,
                           retention_days: int = 30) -> CleanupResult:
        """
        Orchestrate complete cleanup process.
        
        Args:
            retention_policy: Policy for checkpoint retention
            retention_count: Number of checkpoints to keep
            retention_days: Number of days to keep checkpoints
            
        Returns:
            CleanupResult with cleanup details
        """
        try:
            cleanup_time = datetime.now(timezone.utc)
            result = CleanupResult(
                success=False,
                cleanup_time=cleanup_time,
                checkpoints_removed=0,
                space_freed=0
            )
            
            # Discover checkpoints
            checkpoint_files = list(self.config.checkpoint_dir.glob("checkpoint_*.pt"))
            if not checkpoint_files:
                result.success = True
                result.add_warning("No checkpoint files found")
                return result
            
            # Extract metadata for all checkpoints
            checkpoints = []
            for checkpoint_file in checkpoint_files:
                metadata = self.retention_manager.get_checkpoint_metadata(checkpoint_file)
                if metadata:
                    checkpoints.append(metadata)
                else:
                    result.add_warning(f"Failed to read metadata from {checkpoint_file}")
            
            if not checkpoints:
                result.success = True
                result.add_warning("No valid checkpoints found")
                return result
            
            # Apply retention policy
            cleanup_candidates = self.retention_manager.apply_retention_policy(
                checkpoints, retention_policy, retention_count, retention_days
            )
            
            if not cleanup_candidates:
                result.success = True
                result.add_warning("No checkpoints need cleanup")
                return result
            
            # Perform cleanup
            for checkpoint in cleanup_candidates:
                try:
                    if self._cleanup_checkpoint(checkpoint, result):
                        result.checkpoints_removed += 1
                        result.space_freed += checkpoint.total_size
                        result.removed_checkpoint_ids.append(checkpoint.checkpoint_id)
                except Exception as e:
                    result.add_error(f"Failed to cleanup checkpoint {checkpoint.checkpoint_id}: {e}")
            
            result.success = len(result.errors) == 0
            
            if result.success:
                self._logger.info(f"Cleanup completed: {result.checkpoints_removed} checkpoints removed, "
                                f"{result.space_freed / (1024*1024):.1f} MB freed")
            else:
                self._logger.error(f"Cleanup completed with errors: {len(result.errors)} errors")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Cleanup orchestration failed: {e}")
            result = CleanupResult(
                success=False,
                cleanup_time=datetime.now(timezone.utc),
                checkpoints_removed=0,
                space_freed=0
            )
            result.add_error(f"Cleanup orchestration failed: {e}")
            return result
    
    def _cleanup_checkpoint(self, checkpoint: CheckpointMetadata, result: CleanupResult) -> bool:
        """
        Clean up a single checkpoint.
        
        Args:
            checkpoint: Checkpoint metadata
            result: Cleanup result to update
            
        Returns:
            True if cleanup successful
        """
        try:
            if self.config.dry_run:
                self._logger.info(f"DRY RUN: Would delete checkpoint {checkpoint.checkpoint_id}")
                return True
            
            # Backup before deletion if configured
            if self.config.backup_before_delete:
                backup_success = self._backup_checkpoint(checkpoint)
                if not backup_success:
                    result.add_warning(f"Failed to backup checkpoint {checkpoint.checkpoint_id}")
            
            # Verify checkpoint before deletion if configured
            if self.config.verify_before_delete:
                if not checkpoint.file_path.exists():
                    result.add_warning(f"Checkpoint file already deleted: {checkpoint.file_path}")
                    return False
            
            # Delete checkpoint file
            checkpoint.file_path.unlink()
            self._logger.debug(f"Deleted checkpoint: {checkpoint.file_path}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to cleanup checkpoint {checkpoint.checkpoint_id}: {e}")
            return False
    
    def _backup_checkpoint(self, checkpoint: CheckpointMetadata) -> bool:
        """
        Backup checkpoint before deletion.
        
        Args:
            checkpoint: Checkpoint metadata
            
        Returns:
            True if backup successful
        """
        try:
            backup_filename = f"backup_{checkpoint.checkpoint_id}_{checkpoint.file_path.name}"
            backup_path = self.config.backup_dir / backup_filename
            
            shutil.copy2(checkpoint.file_path, backup_path)
            self._logger.debug(f"Backed up checkpoint to: {backup_path}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to backup checkpoint {checkpoint.checkpoint_id}: {e}")
            return False


class CheckpointCleaner(ICheckpointCleaner):
    """Comprehensive checkpoint cleanup with configurable retention policies."""

    def __init__(self, config: CleanupConfig):
        """
        Initialize checkpoint cleaner.

        Args:
            config: Cleanup configuration
        """
        self.config = config
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()

        self.cleanup_orchestrator = CleanupOrchestrator(config)

        # Thread safety
        self._lock = threading.RLock()

        self._logger.info(f"CheckpointCleaner initialized for directory: {config.checkpoint_dir}")

    def cleanup_checkpoints(self, retention_policy: RetentionPolicy,
                           retention_count: int = 5,
                           retention_days: int = 30) -> CleanupResult:
        """
        Clean up old checkpoints based on retention policy.

        Args:
            retention_policy: Policy for checkpoint retention
            retention_count: Number of checkpoints to keep
            retention_days: Number of days to keep checkpoints

        Returns:
            CleanupResult with detailed cleanup information
        """
        try:
            with self._lock:
                self._logger.info(f"Starting checkpoint cleanup with policy: {retention_policy.value}")

                # Validate configuration
                if not self.config.checkpoint_dir.exists():
                    result = CleanupResult(
                        success=False,
                        cleanup_time=datetime.now(timezone.utc),
                        checkpoints_removed=0,
                        space_freed=0
                    )
                    result.add_error(f"Checkpoint directory does not exist: {self.config.checkpoint_dir}")
                    return result

                # Delegate to orchestrator
                result = self.cleanup_orchestrator.orchestrate_cleanup(
                    retention_policy, retention_count, retention_days
                )

                if result.success:
                    self._logger.info(f"Cleanup successful: {result.checkpoints_removed} checkpoints removed")
                else:
                    self._logger.error(f"Cleanup failed with {len(result.errors)} errors")
                    error_context = {
                        'retention_policy': retention_policy.value,
                        'checkpoint_dir': str(self.config.checkpoint_dir)
                    }
                    # Create a generic exception for error classification
                    cleanup_error = Exception(f"Cleanup failed: {'; '.join(result.errors)}")
                    self._error_classifier.classify_error(cleanup_error, error_context)

                return result

        except Exception as e:
            self._logger.error(f"Checkpoint cleanup operation failed: {e}")
            error_context = {
                'retention_policy': retention_policy.value,
                'checkpoint_dir': str(self.config.checkpoint_dir)
            }
            self._error_classifier.classify_error(e, error_context)

            result = CleanupResult(
                success=False,
                cleanup_time=datetime.now(timezone.utc),
                checkpoints_removed=0,
                space_freed=0
            )
            result.add_error(f"Cleanup operation failed: {e}")
            return result

    def get_cleanup_candidates(self, retention_policy: RetentionPolicy,
                              retention_count: int = 5,
                              retention_days: int = 30) -> List[CheckpointMetadata]:
        """
        Get list of checkpoints that can be cleaned up without actually deleting them.

        Args:
            retention_policy: Policy for checkpoint retention
            retention_count: Number of checkpoints to keep
            retention_days: Number of days to keep checkpoints

        Returns:
            List of checkpoint metadata for cleanup candidates
        """
        try:
            # Discover checkpoints
            checkpoint_files = list(self.config.checkpoint_dir.glob("checkpoint_*.pt"))
            if not checkpoint_files:
                self._logger.info("No checkpoint files found")
                return []

            # Extract metadata for all checkpoints
            checkpoints = []
            for checkpoint_file in checkpoint_files:
                metadata = self.cleanup_orchestrator.retention_manager.get_checkpoint_metadata(checkpoint_file)
                if metadata:
                    checkpoints.append(metadata)
                else:
                    self._logger.warning(f"Failed to read metadata from {checkpoint_file}")

            if not checkpoints:
                self._logger.info("No valid checkpoints found")
                return []

            # Apply retention policy to get candidates
            cleanup_candidates = self.cleanup_orchestrator.retention_manager.apply_retention_policy(
                checkpoints, retention_policy, retention_count, retention_days
            )

            self._logger.info(f"Found {len(cleanup_candidates)} cleanup candidates")
            return cleanup_candidates

        except Exception as e:
            self._logger.error(f"Failed to get cleanup candidates: {e}")
            return []

    def get_storage_usage(self) -> Dict[str, Any]:
        """
        Get storage usage statistics for checkpoints.

        Returns:
            Dictionary with storage usage information
        """
        try:
            checkpoint_files = list(self.config.checkpoint_dir.glob("checkpoint_*.pt"))

            total_size = 0
            total_count = 0
            type_stats = {}

            for checkpoint_file in checkpoint_files:
                try:
                    file_size = checkpoint_file.stat().st_size
                    total_size += file_size
                    total_count += 1

                    # Try to get checkpoint type
                    metadata = self.cleanup_orchestrator.retention_manager.get_checkpoint_metadata(checkpoint_file)
                    if metadata:
                        checkpoint_type = metadata.checkpoint_type.value
                        if checkpoint_type not in type_stats:
                            type_stats[checkpoint_type] = {'count': 0, 'size': 0}
                        type_stats[checkpoint_type]['count'] += 1
                        type_stats[checkpoint_type]['size'] += file_size

                except Exception as e:
                    self._logger.warning(f"Failed to get stats for {checkpoint_file}: {e}")
                    continue

            usage_stats = {
                'total_checkpoints': total_count,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'total_size_gb': total_size / (1024 * 1024 * 1024),
                'by_type': type_stats,
                'directory': str(self.config.checkpoint_dir)
            }

            return usage_stats

        except Exception as e:
            self._logger.error(f"Failed to get storage usage: {e}")
            return {}

    def cleanup_corrupted_checkpoints(self) -> CleanupResult:
        """
        Clean up corrupted or invalid checkpoints.

        Returns:
            CleanupResult with cleanup details
        """
        try:
            cleanup_time = datetime.now(timezone.utc)
            result = CleanupResult(
                success=False,
                cleanup_time=cleanup_time,
                checkpoints_removed=0,
                space_freed=0
            )

            checkpoint_files = list(self.config.checkpoint_dir.glob("checkpoint_*.pt"))
            if not checkpoint_files:
                result.success = True
                result.add_warning("No checkpoint files found")
                return result

            corrupted_checkpoints = []

            # Identify corrupted checkpoints
            for checkpoint_file in checkpoint_files:
                try:
                    # Try to load checkpoint metadata
                    metadata = self.cleanup_orchestrator.retention_manager.get_checkpoint_metadata(checkpoint_file)
                    if not metadata:
                        # Failed to load metadata - likely corrupted
                        file_size = checkpoint_file.stat().st_size
                        corrupted_checkpoints.append((checkpoint_file, file_size))
                        self._logger.warning(f"Corrupted checkpoint detected: {checkpoint_file}")

                except Exception as e:
                    # Exception during loading - definitely corrupted
                    try:
                        file_size = checkpoint_file.stat().st_size
                    except:
                        file_size = 0
                    corrupted_checkpoints.append((checkpoint_file, file_size))
                    self._logger.warning(f"Corrupted checkpoint detected: {checkpoint_file} ({e})")

            if not corrupted_checkpoints:
                result.success = True
                result.add_warning("No corrupted checkpoints found")
                return result

            # Clean up corrupted checkpoints
            for checkpoint_file, file_size in corrupted_checkpoints:
                try:
                    if self.config.dry_run:
                        self._logger.info(f"DRY RUN: Would delete corrupted checkpoint {checkpoint_file}")
                        result.checkpoints_removed += 1
                        result.space_freed += file_size
                        continue

                    # Backup if configured
                    if self.config.backup_before_delete:
                        backup_filename = f"corrupted_backup_{checkpoint_file.name}"
                        backup_path = self.config.backup_dir / backup_filename
                        try:
                            shutil.copy2(checkpoint_file, backup_path)
                            self._logger.debug(f"Backed up corrupted checkpoint to: {backup_path}")
                        except Exception as e:
                            result.add_warning(f"Failed to backup corrupted checkpoint {checkpoint_file}: {e}")

                    # Delete corrupted checkpoint
                    checkpoint_file.unlink()
                    result.checkpoints_removed += 1
                    result.space_freed += file_size
                    result.removed_checkpoint_ids.append(str(checkpoint_file))

                    self._logger.info(f"Deleted corrupted checkpoint: {checkpoint_file}")

                except Exception as e:
                    result.add_error(f"Failed to delete corrupted checkpoint {checkpoint_file}: {e}")

            result.success = len(result.errors) == 0

            if result.success:
                self._logger.info(f"Corrupted checkpoint cleanup completed: {result.checkpoints_removed} removed")
            else:
                self._logger.error(f"Corrupted checkpoint cleanup failed with {len(result.errors)} errors")

            return result

        except Exception as e:
            self._logger.error(f"Corrupted checkpoint cleanup failed: {e}")
            result = CleanupResult(
                success=False,
                cleanup_time=datetime.now(timezone.utc),
                checkpoints_removed=0,
                space_freed=0
            )
            result.add_error(f"Corrupted checkpoint cleanup failed: {e}")
            return result

    def emergency_cleanup(self, target_free_space_gb: float = 10.0) -> CleanupResult:
        """
        Perform emergency cleanup to free up space.

        Args:
            target_free_space_gb: Target free space in GB

        Returns:
            CleanupResult with cleanup details
        """
        try:
            self._logger.warning(f"Performing emergency cleanup to free {target_free_space_gb} GB")

            # Start with corrupted checkpoints
            result = self.cleanup_corrupted_checkpoints()

            target_bytes = target_free_space_gb * 1024 * 1024 * 1024

            if result.space_freed >= target_bytes:
                self._logger.info("Emergency cleanup completed by removing corrupted checkpoints")
                return result

            # Continue with aggressive retention policy
            remaining_target = target_bytes - result.space_freed

            # Try progressively more aggressive policies
            policies = [
                (RetentionPolicy.KEEP_RECENT, 3),
                (RetentionPolicy.KEEP_RECENT, 2),
                (RetentionPolicy.KEEP_RECENT, 1),
            ]

            for policy, count in policies:
                if result.space_freed >= target_bytes:
                    break

                additional_result = self.cleanup_checkpoints(policy, count)

                # Merge results
                result.checkpoints_removed += additional_result.checkpoints_removed
                result.space_freed += additional_result.space_freed
                result.errors.extend(additional_result.errors)
                result.warnings.extend(additional_result.warnings)
                result.removed_checkpoint_ids.extend(additional_result.removed_checkpoint_ids)

                if additional_result.success and result.space_freed >= target_bytes:
                    break

            result.success = result.space_freed >= target_bytes and len(result.errors) == 0

            if result.success:
                self._logger.info(f"Emergency cleanup successful: {result.space_freed / (1024*1024*1024):.1f} GB freed")
            else:
                self._logger.error(f"Emergency cleanup insufficient: only {result.space_freed / (1024*1024*1024):.1f} GB freed")

            return result

        except Exception as e:
            self._logger.error(f"Emergency cleanup failed: {e}")
            result = CleanupResult(
                success=False,
                cleanup_time=datetime.now(timezone.utc),
                checkpoints_removed=0,
                space_freed=0
            )
            result.add_error(f"Emergency cleanup failed: {e}")
            return result
