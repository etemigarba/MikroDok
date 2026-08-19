"""
Module: checkpoint_archiver_lg
Description: Archives and manages training checkpoints with compression, metadata management, and cleanup policies
Phase: 4
Location: /src/modules/logic/backup_recovery_lg/checkpoint_archiver_lg/
"""

# Standard library imports
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
import tarfile

# Local imports
from ..base_interfaces import (
    ICheckpointArchiver, ArchiveConfig, ArchiveResult, ArchiveType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_logger


class CompressionManager:
    """Handles compression operations for archives."""
    
    def __init__(self):
        """Initialize compression manager."""
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
    
    def create_tar_archive(self, source_path: Path, archive_path: Path, compression_level: int = 6) -> bool:
        """
        Create compressed tar archive.
        
        Args:
            source_path: Source path to archive
            archive_path: Target archive path
            compression_level: Compression level
            
        Returns:
            True if archive creation successful
        """
        try:
            with tarfile.open(archive_path, 'w:gz', compresslevel=compression_level) as tar:
                if source_path.is_file():
                    tar.add(source_path, arcname=source_path.name)
                elif source_path.is_dir():
                    tar.add(source_path, arcname=source_path.name)
            
            self._logger.info(f"Created tar archive: {source_path} -> {archive_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to create tar archive {archive_path}: {e}")
            return False
    
    def extract_tar_archive(self, archive_path: Path, extract_path: Path) -> bool:
        """
        Extract tar archive.
        
        Args:
            archive_path: Archive file path
            extract_path: Extraction target path
            
        Returns:
            True if extraction successful
        """
        try:
            extract_path.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(path=extract_path)
            
            self._logger.info(f"Extracted tar archive: {archive_path} -> {extract_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to extract tar archive {archive_path}: {e}")
            return False


class MetadataManager:
    """Handles metadata management for archives."""
    
    def __init__(self):
        """Initialize metadata manager."""
        self._logger = get_logger(__name__)
    
    def create_archive_metadata(self, archive_id: str, source_path: Path, 
                               archive_config: ArchiveConfig, archive_result: ArchiveResult) -> Dict[str, Any]:
        """
        Create archive metadata.
        
        Args:
            archive_id: Archive identifier
            source_path: Source path that was archived
            archive_config: Archive configuration
            archive_result: Archive result
            
        Returns:
            Metadata dictionary
        """
        try:
            metadata = {
                'archive_id': archive_id,
                'archive_type': archive_config.archive_type.value,
                'source_path': str(source_path),
                'archive_path': str(archive_result.archive_path),
                'timestamp': archive_result.start_time.isoformat(),
                'compression_level': archive_config.compression_level,
                'encryption_enabled': archive_config.encryption_enabled,
                'original_size': archive_result.original_size,
                'compressed_size': archive_result.compressed_size,
                'compression_ratio': archive_result.compression_ratio,
                'files_archived': archive_result.files_archived,
                'checksum': archive_result.checksum,
                'retention_policy': archive_config.retention_policy,
                'retention_days': archive_config.retention_days
            }
            
            # Add source file information
            if source_path.exists():
                if source_path.is_file():
                    metadata['source_type'] = 'file'
                    metadata['source_size'] = source_path.stat().st_size
                elif source_path.is_dir():
                    metadata['source_type'] = 'directory'
                    metadata['source_files'] = len(list(source_path.rglob('*')))
            
            return metadata
            
        except Exception as e:
            self._logger.error(f"Failed to create archive metadata: {e}")
            return {}
    
    def save_metadata(self, metadata: Dict[str, Any], metadata_path: Path) -> bool:
        """
        Save metadata to file.
        
        Args:
            metadata: Metadata dictionary
            metadata_path: Path to save metadata
            
        Returns:
            True if save successful
        """
        try:
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save metadata {metadata_path}: {e}")
            return False
    
    def load_metadata(self, metadata_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load metadata from file.
        
        Args:
            metadata_path: Path to metadata file
            
        Returns:
            Metadata dictionary or None if failed
        """
        try:
            if not metadata_path.exists():
                return None
            
            with open(metadata_path, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            self._logger.error(f"Failed to load metadata {metadata_path}: {e}")
            return None
    
    def update_metadata(self, metadata_path: Path, updates: Dict[str, Any]) -> bool:
        """
        Update existing metadata.
        
        Args:
            metadata_path: Path to metadata file
            updates: Updates to apply
            
        Returns:
            True if update successful
        """
        try:
            metadata = self.load_metadata(metadata_path)
            if metadata is None:
                return False
            
            metadata.update(updates)
            return self.save_metadata(metadata, metadata_path)
            
        except Exception as e:
            self._logger.error(f"Failed to update metadata {metadata_path}: {e}")
            return False


class ArchiveManager:
    """Manages archive operations and lifecycle."""
    
    def __init__(self):
        """Initialize archive manager."""
        self._logger = get_logger(__name__)
        self._compression_manager = CompressionManager()
        self._metadata_manager = MetadataManager()
    
    def create_archive(self, source_path: Path, archive_config: ArchiveConfig, archive_result: ArchiveResult) -> bool:
        """
        Create archive from source path.
        
        Args:
            source_path: Source path to archive
            archive_config: Archive configuration
            archive_result: Archive result to update
            
        Returns:
            True if archive creation successful
        """
        try:
            # Ensure archive directory exists
            archive_config.archive_directory.mkdir(parents=True, exist_ok=True)
            
            # Calculate original size
            original_size = 0
            files_count = 0
            
            if source_path.is_file():
                original_size = source_path.stat().st_size
                files_count = 1
            elif source_path.is_dir():
                for file_path in source_path.rglob('*'):
                    if file_path.is_file():
                        original_size += file_path.stat().st_size
                        files_count += 1
            
            archive_result.original_size = original_size
            archive_result.files_archived = files_count
            
            # Create archive based on type
            if archive_config.archive_type in [ArchiveType.CHECKPOINT_ARCHIVE, ArchiveType.COMPRESSED_ARCHIVE]:
                success = self._compression_manager.create_tar_archive(
                    source_path, archive_result.archive_path, archive_config.compression_level
                )
            else:
                # Simple copy for other types
                if source_path.is_file():
                    shutil.copy2(source_path, archive_result.archive_path)
                else:
                    shutil.copytree(source_path, archive_result.archive_path, dirs_exist_ok=True)
                success = True
            
            if success and archive_result.archive_path.exists():
                # Calculate compressed size and ratio
                compressed_size = archive_result.archive_path.stat().st_size
                archive_result.compressed_size = compressed_size
                
                if original_size > 0:
                    archive_result.compression_ratio = compressed_size / original_size
                
                # Calculate checksum
                archive_result.checksum = self._calculate_checksum(archive_result.archive_path)
                
                # Create and save metadata
                metadata = self._metadata_manager.create_archive_metadata(
                    archive_result.archive_id, source_path, archive_config, archive_result
                )
                
                metadata_path = archive_result.archive_path.with_suffix('.meta')
                self._metadata_manager.save_metadata(metadata, metadata_path)
                
                return True
            
            return False
            
        except Exception as e:
            archive_result.add_error(f"Archive creation failed: {e}")
            return False
    
    def extract_archive(self, archive_path: Path, extract_path: Path) -> bool:
        """
        Extract archive to specified path.
        
        Args:
            archive_path: Path to archive
            extract_path: Path to extract to
            
        Returns:
            True if extraction successful
        """
        try:
            if not archive_path.exists():
                return False
            
            # Check if it's a tar archive
            if archive_path.suffix in ['.tar', '.gz', '.tgz']:
                return self._compression_manager.extract_tar_archive(archive_path, extract_path)
            else:
                # Simple copy for other types
                extract_path.mkdir(parents=True, exist_ok=True)
                
                if archive_path.is_file():
                    shutil.copy2(archive_path, extract_path / archive_path.name)
                else:
                    shutil.copytree(archive_path, extract_path / archive_path.name, dirs_exist_ok=True)
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to extract archive {archive_path}: {e}")
            return False
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> Optional[str]:
        """Calculate file checksum."""
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            self._logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return None
    
    def validate_archive(self, archive_path: Path) -> bool:
        """
        Validate archive integrity.
        
        Args:
            archive_path: Path to archive
            
        Returns:
            True if archive is valid
        """
        try:
            if not archive_path.exists():
                return False
            
            # Check metadata
            metadata_path = archive_path.with_suffix('.meta')
            if metadata_path.exists():
                metadata = self._metadata_manager.load_metadata(metadata_path)
                if metadata:
                    # Verify checksum if available
                    expected_checksum = metadata.get('checksum')
                    if expected_checksum:
                        actual_checksum = self._calculate_checksum(archive_path)
                        return actual_checksum == expected_checksum
            
            # Basic validation - check if file is readable and has content
            return archive_path.stat().st_size > 0
            
        except Exception as e:
            self._logger.error(f"Failed to validate archive {archive_path}: {e}")
            return False


class CheckpointArchiver(ICheckpointArchiver):
    """
    Comprehensive checkpoint archiver for managing training checkpoints.

    Features:
    - Multiple archive types (checkpoint, model, data, compressed, encrypted)
    - Compression with configurable levels
    - Metadata management and indexing
    - Retention policies and cleanup
    - Deduplication support
    - Integrity verification
    - Comprehensive error handling and logging
    """

    def __init__(self):
        """Initialize checkpoint archiver."""
        self._logger = get_logger(__name__)
        self._archive_manager = ArchiveManager()
        self._metadata_manager = MetadataManager()
        self._compression_manager = CompressionManager()

        # Thread safety
        self._lock = threading.RLock()

        # Archive tracking
        self._active_archives: Dict[str, ArchiveResult] = {}
        self._archive_history: List[ArchiveResult] = []
        self._archive_index: Dict[str, Dict[str, Any]] = {}

        self._logger.info("CheckpointArchiver initialized")

    def archive_checkpoint(self, checkpoint_path: Path, archive_config: ArchiveConfig) -> ArchiveResult:
        """
        Archive checkpoint.

        Args:
            checkpoint_path: Path to checkpoint
            archive_config: Archive configuration

        Returns:
            ArchiveResult with operation details
        """
        archive_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        # Generate archive filename
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        archive_filename = f"checkpoint_archive_{timestamp}_{archive_id[:8]}.tar.gz"
        archive_path = archive_config.archive_directory / archive_filename

        result = ArchiveResult(
            success=False,
            archive_id=archive_id,
            archive_path=archive_path,
            archive_type=archive_config.archive_type,
            start_time=start_time
        )

        try:
            with self._lock:
                self._active_archives[archive_id] = result

            # Validate checkpoint path
            if not checkpoint_path.exists():
                result.add_error(f"Checkpoint path does not exist: {checkpoint_path}")
                return result

            # Check available space
            if not self._check_available_space(checkpoint_path, archive_config):
                result.add_error("Insufficient disk space for archive")
                return result

            # Check for deduplication if enabled
            if archive_config.deduplication_enabled:
                existing_archive = self._find_duplicate_archive(checkpoint_path, archive_config)
                if existing_archive:
                    result.add_warning(f"Duplicate archive found: {existing_archive}")
                    # Could return existing archive or continue with new one

            # Create archive
            success = self._archive_manager.create_archive(checkpoint_path, archive_config, result)

            if success:
                # Validate archive if created
                if self._archive_manager.validate_archive(result.archive_path):
                    result.success = True

                    # Update index if enabled
                    if archive_config.index_enabled:
                        self._update_archive_index(result, archive_config)

                    self._logger.info(f"Checkpoint archived successfully: {archive_id}")
                else:
                    result.add_error("Archive validation failed")

            result.end_time = datetime.now(timezone.utc)

            # Add to history
            with self._lock:
                self._archive_history.append(result)
                if archive_id in self._active_archives:
                    del self._active_archives[archive_id]

            # Cleanup old archives if needed
            if result.success:
                self._cleanup_old_archives(archive_config)

            return result

        except Exception as e:
            result.add_error(f"Archive operation failed: {e}")
            result.end_time = datetime.now(timezone.utc)
            self._logger.error(f"Archive {archive_id} failed: {e}", exc_info=True)

            with self._lock:
                if archive_id in self._active_archives:
                    del self._active_archives[archive_id]

            return result

    def extract_checkpoint(self, archive_path: Path, extract_path: Path) -> bool:
        """
        Extract checkpoint from archive.

        Args:
            archive_path: Path to archive
            extract_path: Path to extract to

        Returns:
            True if extraction successful
        """
        try:
            if not archive_path.exists():
                self._logger.error(f"Archive does not exist: {archive_path}")
                return False

            # Validate archive before extraction
            if not self._archive_manager.validate_archive(archive_path):
                self._logger.error(f"Archive validation failed: {archive_path}")
                return False

            # Extract archive
            success = self._archive_manager.extract_archive(archive_path, extract_path)

            if success:
                self._logger.info(f"Checkpoint extracted successfully: {archive_path} -> {extract_path}")
            else:
                self._logger.error(f"Failed to extract checkpoint: {archive_path}")

            return success

        except Exception as e:
            self._logger.error(f"Failed to extract checkpoint {archive_path}: {e}")
            return False

    def list_archived_checkpoints(self, archive_directory: Path) -> List[Dict[str, Any]]:
        """
        List archived checkpoints.

        Args:
            archive_directory: Directory containing archives

        Returns:
            List of archive metadata
        """
        archives = []

        try:
            if not archive_directory.exists():
                return archives

            for archive_file in archive_directory.iterdir():
                if archive_file.is_file() and archive_file.suffix in ['.tar', '.gz', '.tgz']:
                    metadata_path = archive_file.with_suffix('.meta')

                    if metadata_path.exists():
                        metadata = self._metadata_manager.load_metadata(metadata_path)
                        if metadata:
                            # Add file system info
                            metadata['archive_path'] = str(archive_file)
                            metadata['archive_size'] = archive_file.stat().st_size
                            metadata['last_modified'] = datetime.fromtimestamp(
                                archive_file.stat().st_mtime, tz=timezone.utc
                            ).isoformat()

                            archives.append(metadata)
                    else:
                        # Create basic metadata for archives without metadata files
                        basic_metadata = {
                            'archive_id': archive_file.stem,
                            'archive_path': str(archive_file),
                            'archive_size': archive_file.stat().st_size,
                            'timestamp': datetime.fromtimestamp(
                                archive_file.stat().st_mtime, tz=timezone.utc
                            ).isoformat(),
                            'archive_type': 'unknown'
                        }
                        archives.append(basic_metadata)

            # Sort by timestamp (newest first)
            archives.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        except Exception as e:
            self._logger.error(f"Failed to list archived checkpoints: {e}")

        return archives

    def _check_available_space(self, source_path: Path, archive_config: ArchiveConfig) -> bool:
        """Check if there's enough space for archive."""
        try:
            # Calculate source size
            source_size = 0
            if source_path.is_file():
                source_size = source_path.stat().st_size
            elif source_path.is_dir():
                source_size = sum(f.stat().st_size for f in source_path.rglob('*') if f.is_file())

            # Estimate archive size (assume 50% compression)
            estimated_archive_size = int(source_size * 0.5)

            # Check available space
            available_space = shutil.disk_usage(archive_config.archive_directory.parent).free

            return estimated_archive_size < available_space

        except Exception as e:
            self._logger.error(f"Failed to check available space: {e}")
            return True  # Assume space is available if check fails

    def _find_duplicate_archive(self, checkpoint_path: Path, archive_config: ArchiveConfig) -> Optional[str]:
        """Find duplicate archive based on content."""
        try:
            # Simple deduplication based on file size and modification time
            if checkpoint_path.is_file():
                source_size = checkpoint_path.stat().st_size
                source_mtime = checkpoint_path.stat().st_mtime

                for archive_info in self.list_archived_checkpoints(archive_config.archive_directory):
                    metadata_path = Path(archive_info['archive_path']).with_suffix('.meta')
                    metadata = self._metadata_manager.load_metadata(metadata_path)

                    if metadata:
                        if (metadata.get('source_size') == source_size and
                            abs(metadata.get('source_mtime', 0) - source_mtime) < 1):
                            return archive_info['archive_path']

            return None

        except Exception as e:
            self._logger.error(f"Failed to find duplicate archive: {e}")
            return None

    def _update_archive_index(self, result: ArchiveResult, archive_config: ArchiveConfig) -> None:
        """Update archive index."""
        try:
            with self._lock:
                self._archive_index[result.archive_id] = {
                    'archive_path': str(result.archive_path),
                    'archive_type': result.archive_type.value,
                    'timestamp': result.start_time.isoformat(),
                    'size': result.compressed_size,
                    'checksum': result.checksum
                }

            # Save index to file
            index_path = archive_config.archive_directory / "archive_index.json"
            with open(index_path, 'w') as f:
                json.dump(self._archive_index, f, indent=2)

        except Exception as e:
            self._logger.error(f"Failed to update archive index: {e}")

    def _cleanup_old_archives(self, archive_config: ArchiveConfig) -> None:
        """Clean up old archives based on retention policy."""
        try:
            archives = self.list_archived_checkpoints(archive_config.archive_directory)

            if archive_config.retention_policy == "time_based":
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=archive_config.retention_days)

                for archive in archives:
                    try:
                        archive_time = datetime.fromisoformat(archive['timestamp'])
                        if archive_time < cutoff_date:
                            archive_path = Path(archive['archive_path'])
                            metadata_path = archive_path.with_suffix('.meta')

                            if archive_path.exists():
                                archive_path.unlink()
                            if metadata_path.exists():
                                metadata_path.unlink()

                            self._logger.info(f"Cleaned up old archive: {archive_path}")

                    except Exception as e:
                        self._logger.warning(f"Failed to cleanup archive {archive.get('archive_path')}: {e}")

            elif archive_config.retention_policy == "size_based":
                # Sort by timestamp and remove oldest if total size exceeds limit
                total_size = sum(archive.get('archive_size', 0) for archive in archives)

                if total_size > archive_config.max_archive_size:
                    # Remove oldest archives until under limit
                    archives.sort(key=lambda x: x.get('timestamp', ''))

                    for archive in archives:
                        if total_size <= archive_config.max_archive_size:
                            break

                        try:
                            archive_path = Path(archive['archive_path'])
                            metadata_path = archive_path.with_suffix('.meta')

                            archive_size = archive.get('archive_size', 0)

                            if archive_path.exists():
                                archive_path.unlink()
                                total_size -= archive_size
                            if metadata_path.exists():
                                metadata_path.unlink()

                            self._logger.info(f"Cleaned up archive for size limit: {archive_path}")

                        except Exception as e:
                            self._logger.warning(f"Failed to cleanup archive {archive.get('archive_path')}: {e}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old archives: {e}")

    def get_archive_status(self, archive_id: str) -> Optional[ArchiveResult]:
        """
        Get status of active archive operation.

        Args:
            archive_id: Archive identifier

        Returns:
            ArchiveResult or None if not found
        """
        with self._lock:
            return self._active_archives.get(archive_id)

    def get_archive_history(self) -> List[ArchiveResult]:
        """
        Get archive operation history.

        Returns:
            List of completed archive results
        """
        with self._lock:
            return self._archive_history.copy()

    def get_archive_index(self) -> Dict[str, Dict[str, Any]]:
        """
        Get archive index.

        Returns:
            Archive index dictionary
        """
        with self._lock:
            return self._archive_index.copy()
