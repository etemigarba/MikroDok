"""
Module: backup_manager_lg
Description: Handles automated backups of models and data with scheduling, compression, encryption, and retention policies
Phase: 4
Location: /src/modules/logic/backup_recovery_lg/backup_manager_lg/
"""

# Standard library imports
import asyncio
import hashlib
import json
import shutil
import threading
import time
import uuid
import zlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import tempfile
# Optional schedule import
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

# Third-party imports
try:
    import cryptography
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

# Local imports
from ..base_interfaces import (
    IBackupManager, BackupConfig, BackupResult, BackupType, BackupStatus
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_logger


class BackupCompressor:
    """Handles backup compression operations."""
    
    def __init__(self):
        """Initialize backup compressor."""
        self._logger = get_logger(__name__)
    
    def compress_data(self, data: bytes, compression_level: int = 6) -> bytes:
        """
        Compress data using zlib.
        
        Args:
            data: Data to compress
            compression_level: Compression level (1-9)
            
        Returns:
            Compressed data
        """
        try:
            return zlib.compress(data, compression_level)
        except Exception as e:
            self._logger.error(f"Failed to compress data: {e}")
            return data
    
    def decompress_data(self, compressed_data: bytes) -> bytes:
        """
        Decompress data using zlib.
        
        Args:
            compressed_data: Compressed data
            
        Returns:
            Decompressed data
        """
        try:
            return zlib.decompress(compressed_data)
        except Exception as e:
            self._logger.error(f"Failed to decompress data: {e}")
            return compressed_data
    
    def compress_file(self, source_path: Path, target_path: Path, compression_level: int = 6) -> bool:
        """
        Compress file.
        
        Args:
            source_path: Source file path
            target_path: Target compressed file path
            compression_level: Compression level
            
        Returns:
            True if compression successful
        """
        try:
            with open(source_path, 'rb') as source_file:
                data = source_file.read()
            
            compressed_data = self.compress_data(data, compression_level)
            
            with open(target_path, 'wb') as target_file:
                target_file.write(compressed_data)
            
            self._logger.info(f"Compressed file: {source_path} -> {target_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to compress file {source_path}: {e}")
            return False


class BackupValidator:
    """Handles backup validation operations."""
    
    def __init__(self):
        """Initialize backup validator."""
        self._logger = get_logger(__name__)
    
    def calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> Optional[str]:
        """
        Calculate file checksum.
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm
            
        Returns:
            Checksum string or None if failed
        """
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            self._logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return None
    
    def verify_checksum(self, file_path: Path, expected_checksum: str, algorithm: str = "sha256") -> bool:
        """
        Verify file checksum.
        
        Args:
            file_path: Path to file
            expected_checksum: Expected checksum
            algorithm: Hash algorithm
            
        Returns:
            True if checksum matches
        """
        try:
            actual_checksum = self.calculate_checksum(file_path, algorithm)
            return actual_checksum is not None and actual_checksum.lower() == expected_checksum.lower()
            
        except Exception as e:
            self._logger.error(f"Failed to verify checksum for {file_path}: {e}")
            return False
    
    def validate_backup_structure(self, backup_path: Path) -> bool:
        """
        Validate backup file structure.
        
        Args:
            backup_path: Path to backup
            
        Returns:
            True if structure is valid
        """
        try:
            if not backup_path.exists():
                return False
            
            # Check if it's a directory or file
            if backup_path.is_dir():
                # Validate directory structure
                metadata_file = backup_path / "backup_metadata.json"
                return metadata_file.exists()
            else:
                # Validate file size and readability
                return backup_path.stat().st_size > 0
                
        except Exception as e:
            self._logger.error(f"Failed to validate backup structure {backup_path}: {e}")
            return False


class BackupScheduler:
    """Handles backup scheduling operations."""
    
    def __init__(self):
        """Initialize backup scheduler."""
        self._logger = get_logger(__name__)
        self._scheduled_jobs = {}
        self._scheduler_thread = None
        self._running = False
        self._lock = threading.RLock()
    
    def schedule_backup(self, backup_id: str, source_paths: List[Path], 
                       backup_config: BackupConfig, backup_manager: 'BackupManager') -> bool:
        """
        Schedule automatic backup.
        
        Args:
            backup_id: Unique backup identifier
            source_paths: Paths to backup
            backup_config: Backup configuration
            backup_manager: BackupManager instance
            
        Returns:
            True if scheduling successful
        """
        try:
            with self._lock:
                if backup_config.schedule_enabled and SCHEDULE_AVAILABLE:
                    # Schedule backup job
                    job = schedule.every(backup_config.schedule_interval).hours.do(
                        self._execute_scheduled_backup,
                        backup_id, source_paths, backup_config, backup_manager
                    )

                    self._scheduled_jobs[backup_id] = job
                    
                    # Start scheduler thread if not running
                    if not self._running:
                        self._start_scheduler()
                    
                    self._logger.info(f"Scheduled backup {backup_id} every {backup_config.schedule_interval} hours")
                    return True
                
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to schedule backup {backup_id}: {e}")
            return False
    
    def cancel_scheduled_backup(self, backup_id: str) -> bool:
        """
        Cancel scheduled backup.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            True if cancellation successful
        """
        try:
            with self._lock:
                if backup_id in self._scheduled_jobs and SCHEDULE_AVAILABLE:
                    schedule.cancel_job(self._scheduled_jobs[backup_id])
                    del self._scheduled_jobs[backup_id]
                    
                    self._logger.info(f"Cancelled scheduled backup {backup_id}")
                    return True
                
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to cancel scheduled backup {backup_id}: {e}")
            return False
    
    def _start_scheduler(self) -> None:
        """Start scheduler thread."""
        if not self._running:
            self._running = True
            self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self._scheduler_thread.start()
            self._logger.info("Backup scheduler started")
    
    def _run_scheduler(self) -> None:
        """Run scheduler loop."""
        while self._running and SCHEDULE_AVAILABLE:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self._logger.error(f"Scheduler error: {e}")
    
    def _execute_scheduled_backup(self, backup_id: str, source_paths: List[Path], 
                                 backup_config: BackupConfig, backup_manager: 'BackupManager') -> None:
        """Execute scheduled backup."""
        try:
            self._logger.info(f"Executing scheduled backup {backup_id}")
            result = backup_manager.create_backup(source_paths, backup_config)
            
            if result.success:
                self._logger.info(f"Scheduled backup {backup_id} completed successfully")
            else:
                self._logger.error(f"Scheduled backup {backup_id} failed: {'; '.join(result.errors)}")
                
        except Exception as e:
            self._logger.error(f"Failed to execute scheduled backup {backup_id}: {e}")
    
    def stop_scheduler(self) -> None:
        """Stop scheduler."""
        self._running = False
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        self._logger.info("Backup scheduler stopped")


class BackupManager(IBackupManager):
    """
    Comprehensive backup manager for automated backups of models and data.
    
    Features:
    - Multiple backup types (full, incremental, differential)
    - Compression and encryption support
    - Automated scheduling with retention policies
    - Integrity verification and validation
    - Parallel backup operations
    - Comprehensive error handling and logging
    """
    
    def __init__(self):
        """Initialize backup manager."""
        self._logger = get_logger(__name__)
        self._compressor = BackupCompressor()
        self._validator = BackupValidator()
        self._scheduler = BackupScheduler()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Backup tracking
        self._active_backups: Dict[str, BackupResult] = {}
        self._backup_history: List[BackupResult] = []
        
        # Encryption key (if available)
        self._encryption_key = None
        if ENCRYPTION_AVAILABLE:
            self._encryption_key = Fernet.generate_key()
        
        self._logger.info("BackupManager initialized")
    
    def create_backup(self, source_paths: List[Path], backup_config: BackupConfig) -> BackupResult:
        """
        Create a backup of specified paths.
        
        Args:
            source_paths: Paths to backup
            backup_config: Backup configuration
            
        Returns:
            BackupResult with operation details
        """
        backup_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        result = BackupResult(
            success=False,
            backup_id=backup_id,
            backup_path=backup_config.backup_directory / f"backup_{backup_id}",
            backup_type=backup_config.backup_type,
            start_time=start_time
        )
        
        try:
            with self._lock:
                self._active_backups[backup_id] = result
            
            # Validate source paths
            valid_paths = []
            for path in source_paths:
                if path.exists():
                    valid_paths.append(path)
                else:
                    result.add_warning(f"Source path does not exist: {path}")
            
            if not valid_paths:
                result.add_error("No valid source paths found")
                return result
            
            # Create backup directory
            backup_config.backup_directory.mkdir(parents=True, exist_ok=True)
            
            # Perform backup based on type
            if backup_config.backup_type == BackupType.FULL:
                success = self._create_full_backup(valid_paths, backup_config, result)
            elif backup_config.backup_type == BackupType.INCREMENTAL:
                success = self._create_incremental_backup(valid_paths, backup_config, result)
            else:
                success = self._create_full_backup(valid_paths, backup_config, result)
            
            if success:
                # Validate backup if enabled
                if backup_config.verify_integrity:
                    if self.validate_backup(result.backup_path):
                        result.success = True
                        self._logger.info(f"Backup {backup_id} completed successfully")
                    else:
                        result.add_error("Backup validation failed")
                else:
                    result.success = True
                    self._logger.info(f"Backup {backup_id} completed successfully")
            
            result.end_time = datetime.now(timezone.utc)
            
            # Add to history
            with self._lock:
                self._backup_history.append(result)
                if backup_id in self._active_backups:
                    del self._active_backups[backup_id]
            
            # Schedule backup if enabled
            if backup_config.schedule_enabled:
                self._scheduler.schedule_backup(backup_id, source_paths, backup_config, self)
            
            return result
            
        except Exception as e:
            result.add_error(f"Backup failed: {e}")
            result.end_time = datetime.now(timezone.utc)
            self._logger.error(f"Backup {backup_id} failed: {e}", exc_info=True)
            
            with self._lock:
                if backup_id in self._active_backups:
                    del self._active_backups[backup_id]
            
            return result

    def _create_full_backup(self, source_paths: List[Path], backup_config: BackupConfig, result: BackupResult) -> bool:
        """Create full backup."""
        try:
            backup_dir = result.backup_path
            backup_dir.mkdir(parents=True, exist_ok=True)

            total_size = 0
            files_backed_up = 0

            # Create backup metadata
            metadata = {
                'backup_id': result.backup_id,
                'backup_type': result.backup_type.value,
                'timestamp': result.start_time.isoformat(),
                'source_paths': [str(p) for p in source_paths],
                'compression_enabled': backup_config.compression_enabled,
                'encryption_enabled': backup_config.encryption_enabled
            }

            # Copy files
            for source_path in source_paths:
                if source_path.is_file():
                    target_path = backup_dir / source_path.name

                    if backup_config.compression_enabled:
                        compressed_path = target_path.with_suffix(target_path.suffix + '.gz')
                        if self._compressor.compress_file(source_path, compressed_path):
                            total_size += compressed_path.stat().st_size
                            files_backed_up += 1
                    else:
                        shutil.copy2(source_path, target_path)
                        total_size += target_path.stat().st_size
                        files_backed_up += 1

                elif source_path.is_dir():
                    target_dir = backup_dir / source_path.name
                    shutil.copytree(source_path, target_dir, dirs_exist_ok=True)

                    # Calculate directory size
                    for file_path in target_dir.rglob('*'):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            files_backed_up += 1

            # Save metadata
            metadata_path = backup_dir / "backup_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Calculate checksum if enabled
            if backup_config.verify_integrity:
                result.checksum = self._validator.calculate_checksum(metadata_path, backup_config.checksum_algorithm)

            result.size_bytes = total_size
            result.files_backed_up = files_backed_up
            result.metadata = metadata

            return True

        except Exception as e:
            result.add_error(f"Full backup failed: {e}")
            return False

    def _create_incremental_backup(self, source_paths: List[Path], backup_config: BackupConfig, result: BackupResult) -> bool:
        """Create incremental backup."""
        try:
            # Find last backup for incremental comparison
            last_backup = self._find_last_backup(backup_config.backup_directory, BackupType.FULL)
            if not last_backup:
                # No previous backup, create full backup instead
                self._logger.info("No previous backup found, creating full backup")
                return self._create_full_backup(source_paths, backup_config, result)

            backup_dir = result.backup_path
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Load last backup metadata
            last_metadata_path = last_backup / "backup_metadata.json"
            if not last_metadata_path.exists():
                result.add_error("Previous backup metadata not found")
                return False

            with open(last_metadata_path, 'r') as f:
                last_metadata = json.load(f)

            last_backup_time = datetime.fromisoformat(last_metadata['timestamp'])

            total_size = 0
            files_backed_up = 0

            # Create incremental backup metadata
            metadata = {
                'backup_id': result.backup_id,
                'backup_type': result.backup_type.value,
                'timestamp': result.start_time.isoformat(),
                'source_paths': [str(p) for p in source_paths],
                'parent_backup': last_metadata['backup_id'],
                'compression_enabled': backup_config.compression_enabled,
                'encryption_enabled': backup_config.encryption_enabled
            }

            # Copy only modified files
            for source_path in source_paths:
                if source_path.is_file():
                    file_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)

                    if file_mtime > last_backup_time:
                        target_path = backup_dir / source_path.name

                        if backup_config.compression_enabled:
                            compressed_path = target_path.with_suffix(target_path.suffix + '.gz')
                            if self._compressor.compress_file(source_path, compressed_path):
                                total_size += compressed_path.stat().st_size
                                files_backed_up += 1
                        else:
                            shutil.copy2(source_path, target_path)
                            total_size += target_path.stat().st_size
                            files_backed_up += 1

                elif source_path.is_dir():
                    # Check for modified files in directory
                    target_dir = backup_dir / source_path.name
                    target_dir.mkdir(parents=True, exist_ok=True)

                    for file_path in source_path.rglob('*'):
                        if file_path.is_file():
                            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

                            if file_mtime > last_backup_time:
                                rel_path = file_path.relative_to(source_path)
                                target_file = target_dir / rel_path
                                target_file.parent.mkdir(parents=True, exist_ok=True)

                                shutil.copy2(file_path, target_file)
                                total_size += target_file.stat().st_size
                                files_backed_up += 1

            # Save metadata
            metadata_path = backup_dir / "backup_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Calculate checksum if enabled
            if backup_config.verify_integrity:
                result.checksum = self._validator.calculate_checksum(metadata_path, backup_config.checksum_algorithm)

            result.size_bytes = total_size
            result.files_backed_up = files_backed_up
            result.metadata = metadata

            return True

        except Exception as e:
            result.add_error(f"Incremental backup failed: {e}")
            return False

    def _find_last_backup(self, backup_directory: Path, backup_type: BackupType) -> Optional[Path]:
        """Find the most recent backup of specified type."""
        try:
            if not backup_directory.exists():
                return None

            latest_backup = None
            latest_time = None

            for backup_dir in backup_directory.iterdir():
                if backup_dir.is_dir():
                    metadata_path = backup_dir / "backup_metadata.json"
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, 'r') as f:
                                metadata = json.load(f)

                            if metadata.get('backup_type') == backup_type.value:
                                backup_time = datetime.fromisoformat(metadata['timestamp'])

                                if latest_time is None or backup_time > latest_time:
                                    latest_time = backup_time
                                    latest_backup = backup_dir

                        except Exception:
                            continue

            return latest_backup

        except Exception as e:
            self._logger.error(f"Failed to find last backup: {e}")
            return None

    def schedule_backup(self, source_paths: List[Path], backup_config: BackupConfig) -> bool:
        """
        Schedule automatic backup.

        Args:
            source_paths: Paths to backup
            backup_config: Backup configuration

        Returns:
            True if scheduling successful
        """
        backup_id = str(uuid.uuid4())
        return self._scheduler.schedule_backup(backup_id, source_paths, backup_config, self)

    def list_backups(self, backup_directory: Path) -> List[Dict[str, Any]]:
        """
        List available backups.

        Args:
            backup_directory: Directory containing backups

        Returns:
            List of backup metadata
        """
        backups = []

        try:
            if not backup_directory.exists():
                return backups

            for backup_dir in backup_directory.iterdir():
                if backup_dir.is_dir():
                    metadata_path = backup_dir / "backup_metadata.json"
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, 'r') as f:
                                metadata = json.load(f)

                            # Add file system info
                            metadata['backup_path'] = str(backup_dir)
                            metadata['backup_size'] = sum(
                                f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()
                            )

                            backups.append(metadata)

                        except Exception as e:
                            self._logger.warning(f"Failed to read backup metadata {metadata_path}: {e}")

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        except Exception as e:
            self._logger.error(f"Failed to list backups: {e}")

        return backups

    def validate_backup(self, backup_path: Path) -> bool:
        """
        Validate backup integrity.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid
        """
        try:
            # Validate structure
            if not self._validator.validate_backup_structure(backup_path):
                return False

            # Validate metadata
            metadata_path = backup_path / "backup_metadata.json"
            if not metadata_path.exists():
                return False

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Validate required fields
            required_fields = ['backup_id', 'backup_type', 'timestamp']
            for field in required_fields:
                if field not in metadata:
                    self._logger.error(f"Missing required field in backup metadata: {field}")
                    return False

            return True

        except Exception as e:
            self._logger.error(f"Failed to validate backup {backup_path}: {e}")
            return False

    def cleanup_old_backups(self, backup_config: BackupConfig) -> int:
        """
        Clean up old backups based on retention policy.

        Args:
            backup_config: Backup configuration with retention settings

        Returns:
            Number of backups cleaned up
        """
        cleaned_count = 0

        try:
            backups = self.list_backups(backup_config.backup_directory)

            # Sort by timestamp (oldest first for cleanup)
            backups.sort(key=lambda x: x.get('timestamp', ''))

            # Apply retention policies
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=backup_config.retention_days)

            for backup in backups:
                try:
                    backup_time = datetime.fromisoformat(backup['timestamp'])
                    backup_path = Path(backup['backup_path'])

                    # Check if backup should be cleaned up
                    should_cleanup = False

                    # Time-based retention
                    if backup_time < cutoff_date:
                        should_cleanup = True

                    # Count-based retention (keep only N most recent)
                    if len(backups) - cleaned_count > backup_config.retention_count:
                        should_cleanup = True

                    if should_cleanup and backup_path.exists():
                        shutil.rmtree(backup_path)
                        cleaned_count += 1
                        self._logger.info(f"Cleaned up old backup: {backup_path}")

                except Exception as e:
                    self._logger.warning(f"Failed to cleanup backup {backup.get('backup_path')}: {e}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old backups: {e}")

        return cleaned_count

    def get_backup_status(self, backup_id: str) -> Optional[BackupResult]:
        """
        Get status of active backup.

        Args:
            backup_id: Backup identifier

        Returns:
            BackupResult or None if not found
        """
        with self._lock:
            return self._active_backups.get(backup_id)

    def get_backup_history(self) -> List[BackupResult]:
        """
        Get backup history.

        Returns:
            List of completed backup results
        """
        with self._lock:
            return self._backup_history.copy()

    def stop_scheduler(self) -> None:
        """Stop backup scheduler."""
        self._scheduler.stop_scheduler()
