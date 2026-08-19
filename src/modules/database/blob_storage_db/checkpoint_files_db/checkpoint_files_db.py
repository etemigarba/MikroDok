"""
Module: checkpoint_files_db
Description: Manages checkpoint binary data with compression and incremental storage
Phase: 4
Location: /src/modules/database/blob_storage_db/checkpoint_files_db/
"""

# Standard library imports
import gzip
import hashlib
import json
import lzma
import os
import sqlite3
import threading
import uuid
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class CheckpointFileNotFoundError(Exception):
    """Exception raised when checkpoint file is not found."""
    pass


class CheckpointCompressionError(Exception):
    """Exception raised when checkpoint compression/decompression fails."""
    pass


class CheckpointFilesDB:
    """
    Checkpoint files database manager.
    
    Manages checkpoint binary data with compression and incremental storage.
    Provides CRUD operations for checkpoint files, compression handling,
    and incremental storage logic. Supports checkpoint versioning, metadata tracking,
    and automated cleanup of old checkpoints.
    """
    
    def __init__(self, db_path: Optional[str] = None, storage_root: Optional[str] = None):
        """
        Initialize the checkpoint files database.
        
        Args:
            db_path: Path to the database file
            storage_root: Root directory for checkpoint file storage
        """
        if db_path is None:
            # Default to checkpoint files data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "checkpoint_files"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "checkpoint_files.db")
        
        if storage_root is None:
            # Default storage root for checkpoint files
            storage_root = str(Path.home() / ".mikrodok" / "storage" / "checkpoints")
        
        self._db_path = db_path
        self._storage_root = Path(storage_root)
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._checkpoint_retention_days = 30  # Keep checkpoints for 30 days
        self._max_checkpoint_versions = 10  # Maximum versions per model
        self._compression_level = 6  # Default compression level
        self._compression_methods = {
            'gzip': {'compress': gzip.compress, 'decompress': gzip.decompress},
            'lzma': {'compress': lzma.compress, 'decompress': lzma.decompress},
            'zlib': {'compress': zlib.compress, 'decompress': zlib.decompress}
        }
        self._default_compression = 'gzip'
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Create checkpoint files table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        checkpoint_id TEXT NOT NULL UNIQUE,
                        model_name TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        checkpoint_version INTEGER NOT NULL,
                        checkpoint_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        compressed_size INTEGER NOT NULL,
                        uncompressed_size INTEGER NOT NULL,
                        compression_method TEXT NOT NULL,
                        compression_ratio REAL NOT NULL,
                        file_hash TEXT NOT NULL,
                        metadata JSON,
                        status TEXT NOT NULL DEFAULT 'active',
                        training_step INTEGER,
                        training_epoch INTEGER,
                        validation_loss REAL,
                        training_metrics JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(model_name, model_version, checkpoint_version)
                    )
                """)
                
                # Create checkpoint increments table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_increments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        increment_id TEXT NOT NULL UNIQUE,
                        base_checkpoint_id TEXT NOT NULL,
                        increment_checkpoint_id TEXT NOT NULL,
                        increment_type TEXT NOT NULL,
                        increment_size INTEGER NOT NULL,
                        increment_path TEXT NOT NULL,
                        increment_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (base_checkpoint_id) REFERENCES checkpoint_files (checkpoint_id) ON DELETE CASCADE,
                        FOREIGN KEY (increment_checkpoint_id) REFERENCES checkpoint_files (checkpoint_id) ON DELETE CASCADE
                    )
                """)
                
                # Create checkpoint dependencies table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_dependencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dependency_id TEXT NOT NULL UNIQUE,
                        checkpoint_id TEXT NOT NULL,
                        dependency_checkpoint_id TEXT NOT NULL,
                        dependency_type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoint_files (checkpoint_id) ON DELETE CASCADE,
                        FOREIGN KEY (dependency_checkpoint_id) REFERENCES checkpoint_files (checkpoint_id) ON DELETE CASCADE,
                        UNIQUE(checkpoint_id, dependency_checkpoint_id, dependency_type)
                    )
                """)
                
                # Create checkpoint access log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_access_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        access_id TEXT NOT NULL UNIQUE,
                        checkpoint_id TEXT NOT NULL,
                        access_type TEXT NOT NULL,
                        session_id TEXT,
                        access_duration_seconds REAL,
                        decompression_time_seconds REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoint_files (checkpoint_id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_model_name ON checkpoint_files (model_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_model_version ON checkpoint_files (model_version)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_checkpoint_version ON checkpoint_files (checkpoint_version)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_checkpoint_type ON checkpoint_files (checkpoint_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON checkpoint_files (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_training_step ON checkpoint_files (training_step)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON checkpoint_files (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_increments_base ON checkpoint_increments (base_checkpoint_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_increments_increment ON checkpoint_increments (increment_checkpoint_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_checkpoint ON checkpoint_dependencies (checkpoint_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_dependency ON checkpoint_dependencies (dependency_checkpoint_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_log_checkpoint ON checkpoint_access_log (checkpoint_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_log_session ON checkpoint_access_log (session_id)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_checkpoints_timestamp 
                    AFTER UPDATE ON checkpoint_files
                    BEGIN
                        UPDATE checkpoint_files SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'checkpoint_files', 'checkpoint_increments', 
                    'checkpoint_dependencies', 'checkpoint_access_log'
                ]

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Checkpoint files database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize checkpoint files database: {e}")
                raise
            finally:
                conn.close()

    def add_checkpoint(self, model_name: str, model_version: str, checkpoint_data: bytes,
                      checkpoint_type: str = "full", training_step: Optional[int] = None,
                      training_epoch: Optional[int] = None, validation_loss: Optional[float] = None,
                      training_metrics: Optional[Dict[str, Any]] = None,
                      compression_method: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new checkpoint to the database with compression.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            checkpoint_data: Binary checkpoint data
            checkpoint_type: Type of checkpoint (full, incremental, etc.)
            training_step: Training step number
            training_epoch: Training epoch number
            validation_loss: Validation loss value
            training_metrics: Training metrics dictionary
            compression_method: Compression method to use
            metadata: Additional checkpoint metadata

        Returns:
            Checkpoint ID of the added checkpoint

        Raises:
            ValueError: If checkpoint data is invalid
            CheckpointCompressionError: If compression fails
        """
        if not checkpoint_data:
            raise ValueError("Checkpoint data cannot be empty")

        if compression_method is None:
            compression_method = self._default_compression

        if compression_method not in self._compression_methods:
            raise ValueError(f"Unsupported compression method: {compression_method}")

        checkpoint_id = str(uuid.uuid4())
        uncompressed_size = len(checkpoint_data)

        # Get next checkpoint version
        checkpoint_version = self._get_next_checkpoint_version(model_name, model_version)

        try:
            # Compress checkpoint data
            compress_func = self._compression_methods[compression_method]['compress']
            compressed_data = compress_func(checkpoint_data)
            compressed_size = len(compressed_data)
            compression_ratio = compressed_size / uncompressed_size if uncompressed_size > 0 else 0

            # Calculate hash of compressed data
            file_hash = hashlib.sha256(compressed_data).hexdigest()

            # Create storage path
            checkpoint_filename = f"{checkpoint_id}_{model_name}_{model_version}_v{checkpoint_version}.ckpt"
            checkpoint_path = self._storage_root / checkpoint_filename

            # Write compressed data to file
            with open(checkpoint_path, 'wb') as f:
                f.write(compressed_data)

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Insert checkpoint record
                    cursor.execute("""
                        INSERT INTO checkpoint_files (
                            checkpoint_id, model_name, model_version, checkpoint_version,
                            checkpoint_type, file_path, compressed_size, uncompressed_size,
                            compression_method, compression_ratio, file_hash, metadata,
                            training_step, training_epoch, validation_loss, training_metrics
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        checkpoint_id, model_name, model_version, checkpoint_version,
                        checkpoint_type, str(checkpoint_path), compressed_size, uncompressed_size,
                        compression_method, compression_ratio, file_hash,
                        json.dumps(metadata) if metadata else None,
                        training_step, training_epoch, validation_loss,
                        json.dumps(training_metrics) if training_metrics else None
                    ))

                    conn.commit()

                    # Clean up old checkpoints if needed
                    self._cleanup_old_checkpoints(model_name, model_version)

                    self._logger.info(f"Added checkpoint {checkpoint_id}: {model_name} v{model_version} "
                                    f"(compression: {compression_ratio:.2f})")
                    return checkpoint_id

                except Exception as e:
                    conn.rollback()
                    # Clean up file on database error
                    if checkpoint_path.exists():
                        checkpoint_path.unlink()
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to add checkpoint: {e}")
            if isinstance(e, (zlib.error, gzip.BadGzipFile, lzma.LZMAError)):
                raise CheckpointCompressionError(f"Compression failed: {e}")
            raise

    def get_checkpoint(self, checkpoint_id: str, decompress: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get checkpoint by ID.

        Args:
            checkpoint_id: ID of the checkpoint to retrieve
            decompress: Whether to decompress the checkpoint data

        Returns:
            Checkpoint information dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT checkpoint_id, model_name, model_version, checkpoint_version,
                           checkpoint_type, file_path, compressed_size, uncompressed_size,
                           compression_method, compression_ratio, file_hash, metadata,
                           training_step, training_epoch, validation_loss, training_metrics,
                           status, created_at, updated_at
                    FROM checkpoint_files WHERE checkpoint_id = ?
                """, (checkpoint_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                checkpoint_info = {
                    'checkpoint_id': row[0],
                    'model_name': row[1],
                    'model_version': row[2],
                    'checkpoint_version': row[3],
                    'checkpoint_type': row[4],
                    'file_path': row[5],
                    'compressed_size': row[6],
                    'uncompressed_size': row[7],
                    'compression_method': row[8],
                    'compression_ratio': row[9],
                    'file_hash': row[10],
                    'metadata': json.loads(row[11]) if row[11] else None,
                    'training_step': row[12],
                    'training_epoch': row[13],
                    'validation_loss': row[14],
                    'training_metrics': json.loads(row[15]) if row[15] else None,
                    'status': row[16],
                    'created_at': row[17],
                    'updated_at': row[18]
                }

                # Load and decompress checkpoint data if requested
                if decompress:
                    start_time = datetime.now()
                    checkpoint_data = self._load_checkpoint_data(checkpoint_info)
                    decompression_time = (datetime.now() - start_time).total_seconds()

                    checkpoint_info['checkpoint_data'] = checkpoint_data
                    checkpoint_info['decompression_time'] = decompression_time

                    # Log access
                    self._log_checkpoint_access(checkpoint_id, "read", decompression_time=decompression_time)

                return checkpoint_info

            except Exception as e:
                self._logger.error(f"Failed to get checkpoint {checkpoint_id}: {e}")
                return None
            finally:
                conn.close()

    def get_checkpoints_by_model(self, model_name: str, model_version: Optional[str] = None,
                                limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get checkpoints for a specific model.

        Args:
            model_name: Name of the model
            model_version: Version of the model (optional)
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint information dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if model_version:
                    query = """
                        SELECT checkpoint_id, model_name, model_version, checkpoint_version,
                               checkpoint_type, compressed_size, uncompressed_size,
                               compression_method, compression_ratio, training_step,
                               training_epoch, validation_loss, status, created_at
                        FROM checkpoint_files
                        WHERE model_name = ? AND model_version = ? AND status = 'active'
                        ORDER BY checkpoint_version DESC
                    """
                    params = (model_name, model_version)
                else:
                    query = """
                        SELECT checkpoint_id, model_name, model_version, checkpoint_version,
                               checkpoint_type, compressed_size, uncompressed_size,
                               compression_method, compression_ratio, training_step,
                               training_epoch, validation_loss, status, created_at
                        FROM checkpoint_files
                        WHERE model_name = ? AND status = 'active'
                        ORDER BY model_version DESC, checkpoint_version DESC
                    """
                    params = (model_name,)

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query, params)

                checkpoints = []
                for row in cursor.fetchall():
                    checkpoints.append({
                        'checkpoint_id': row[0],
                        'model_name': row[1],
                        'model_version': row[2],
                        'checkpoint_version': row[3],
                        'checkpoint_type': row[4],
                        'compressed_size': row[5],
                        'uncompressed_size': row[6],
                        'compression_method': row[7],
                        'compression_ratio': row[8],
                        'training_step': row[9],
                        'training_epoch': row[10],
                        'validation_loss': row[11],
                        'status': row[12],
                        'created_at': row[13]
                    })

                return checkpoints

            except Exception as e:
                self._logger.error(f"Failed to get checkpoints for model {model_name}: {e}")
                return []
            finally:
                conn.close()

    def delete_checkpoint(self, checkpoint_id: str, delete_file: bool = True) -> bool:
        """
        Delete a checkpoint from the database.

        Args:
            checkpoint_id: ID of the checkpoint to delete
            delete_file: Whether to also delete the physical file

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            checkpoint_info = self.get_checkpoint(checkpoint_id, decompress=False)
            if not checkpoint_info:
                self._logger.warning(f"Checkpoint not found for deletion: {checkpoint_id}")
                return False

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Check for dependencies
                    cursor.execute("""
                        SELECT COUNT(*) FROM checkpoint_dependencies
                        WHERE dependency_checkpoint_id = ?
                    """, (checkpoint_id,))
                    dependency_count = cursor.fetchone()[0]

                    if dependency_count > 0:
                        raise ValueError(f"Cannot delete checkpoint with {dependency_count} dependencies")

                    # Delete checkpoint record
                    cursor.execute("DELETE FROM checkpoint_files WHERE checkpoint_id = ?", (checkpoint_id,))

                    if cursor.rowcount == 0:
                        return False

                    conn.commit()

                    # Delete physical file if requested
                    if delete_file:
                        file_path = Path(checkpoint_info['file_path'])
                        if file_path.exists():
                            file_path.unlink()
                            self._logger.info(f"Deleted checkpoint file: {file_path}")

                    self._logger.info(f"Deleted checkpoint {checkpoint_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error deleting checkpoint {checkpoint_id}: {e}")
            return False

    def cleanup_old_checkpoints(self, model_name: Optional[str] = None) -> int:
        """
        Clean up old checkpoints based on retention policy.

        Args:
            model_name: Optional model name to limit cleanup to

        Returns:
            Number of checkpoints cleaned up
        """
        cleanup_count = 0
        cutoff_date = datetime.now() - timedelta(days=self._checkpoint_retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Find old checkpoints
                if model_name:
                    cursor.execute("""
                        SELECT checkpoint_id, file_path FROM checkpoint_files
                        WHERE model_name = ? AND created_at < ? AND status = 'active'
                        ORDER BY created_at
                    """, (model_name, cutoff_date.isoformat()))
                else:
                    cursor.execute("""
                        SELECT checkpoint_id, file_path FROM checkpoint_files
                        WHERE created_at < ? AND status = 'active'
                        ORDER BY created_at
                    """, (cutoff_date.isoformat(),))

                old_checkpoints = cursor.fetchall()

                for checkpoint_id, file_path in old_checkpoints:
                    try:
                        # Delete physical file
                        file_path_obj = Path(file_path)
                        if file_path_obj.exists():
                            file_path_obj.unlink()
                            self._logger.info(f"Deleted old checkpoint file: {file_path}")

                        # Update status to deleted
                        cursor.execute("""
                            UPDATE checkpoint_files
                            SET status = 'deleted'
                            WHERE checkpoint_id = ?
                        """, (checkpoint_id,))
                        cleanup_count += 1

                    except Exception as e:
                        self._logger.error(f"Failed to cleanup checkpoint {checkpoint_id}: {e}")

                conn.commit()

                if cleanup_count > 0:
                    self._logger.info(f"Cleaned up {cleanup_count} old checkpoints")

                return cleanup_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old checkpoints: {e}")
                return 0
            finally:
                conn.close()

    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics for checkpoint files.

        Returns:
            Dictionary containing storage statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get total count and sizes
                cursor.execute("""
                    SELECT COUNT(*), SUM(compressed_size), SUM(uncompressed_size), AVG(compression_ratio)
                    FROM checkpoint_files WHERE status = 'active'
                """)
                total_count, total_compressed, total_uncompressed, avg_compression = cursor.fetchone()

                # Get count by compression method
                cursor.execute("""
                    SELECT compression_method, COUNT(*), SUM(compressed_size), AVG(compression_ratio)
                    FROM checkpoint_files WHERE status = 'active'
                    GROUP BY compression_method
                """)
                compression_stats = {}
                for method, count, size, ratio in cursor.fetchall():
                    compression_stats[method] = {
                        'count': count,
                        'total_compressed_size': size or 0,
                        'average_compression_ratio': ratio or 0
                    }

                # Get count by checkpoint type
                cursor.execute("""
                    SELECT checkpoint_type, COUNT(*), SUM(compressed_size)
                    FROM checkpoint_files WHERE status = 'active'
                    GROUP BY checkpoint_type
                """)
                type_stats = {}
                for checkpoint_type, count, size in cursor.fetchall():
                    type_stats[checkpoint_type] = {
                        'count': count,
                        'total_size': size or 0
                    }

                return {
                    'total_checkpoints': total_count or 0,
                    'total_compressed_size_bytes': total_compressed or 0,
                    'total_uncompressed_size_bytes': total_uncompressed or 0,
                    'average_compression_ratio': avg_compression or 0,
                    'space_saved_bytes': (total_uncompressed or 0) - (total_compressed or 0),
                    'checkpoints_by_compression': compression_stats,
                    'checkpoints_by_type': type_stats,
                    'storage_root': str(self._storage_root)
                }

            except Exception as e:
                self._logger.error(f"Failed to get storage statistics: {e}")
                return {}
            finally:
                conn.close()

    def _get_next_checkpoint_version(self, model_name: str, model_version: str) -> int:
        """Get the next checkpoint version number for a model."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(checkpoint_version) FROM checkpoint_files
                    WHERE model_name = ? AND model_version = ?
                """, (model_name, model_version))

                result = cursor.fetchone()
                max_version = result[0] if result and result[0] is not None else 0
                return max_version + 1

            except Exception as e:
                self._logger.error(f"Failed to get next checkpoint version: {e}")
                return 1
            finally:
                conn.close()

    def _load_checkpoint_data(self, checkpoint_info: Dict[str, Any]) -> bytes:
        """Load and decompress checkpoint data from file."""
        try:
            file_path = Path(checkpoint_info['file_path'])
            compression_method = checkpoint_info['compression_method']

            if not file_path.exists():
                raise CheckpointFileNotFoundError(f"Checkpoint file not found: {file_path}")

            # Read compressed data
            with open(file_path, 'rb') as f:
                compressed_data = f.read()

            # Verify hash
            file_hash = hashlib.sha256(compressed_data).hexdigest()
            if file_hash != checkpoint_info['file_hash']:
                raise CheckpointCompressionError(f"Checkpoint file hash mismatch: {file_path}")

            # Decompress data
            decompress_func = self._compression_methods[compression_method]['decompress']
            checkpoint_data = decompress_func(compressed_data)

            return checkpoint_data

        except Exception as e:
            self._logger.error(f"Failed to load checkpoint data: {e}")
            if isinstance(e, (zlib.error, gzip.BadGzipFile, lzma.LZMAError)):
                raise CheckpointCompressionError(f"Decompression failed: {e}")
            raise

    def _cleanup_old_checkpoints(self, model_name: str, model_version: str) -> None:
        """Clean up old checkpoints for a specific model version."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get checkpoint count for this model version
                cursor.execute("""
                    SELECT COUNT(*) FROM checkpoint_files
                    WHERE model_name = ? AND model_version = ? AND status = 'active'
                """, (model_name, model_version))

                checkpoint_count = cursor.fetchone()[0]

                if checkpoint_count > self._max_checkpoint_versions:
                    # Get oldest checkpoints to delete
                    excess_count = checkpoint_count - self._max_checkpoint_versions
                    cursor.execute("""
                        SELECT checkpoint_id, file_path FROM checkpoint_files
                        WHERE model_name = ? AND model_version = ? AND status = 'active'
                        ORDER BY checkpoint_version ASC
                        LIMIT ?
                    """, (model_name, model_version, excess_count))

                    old_checkpoints = cursor.fetchall()

                    for checkpoint_id, file_path in old_checkpoints:
                        try:
                            # Delete physical file
                            file_path_obj = Path(file_path)
                            if file_path_obj.exists():
                                file_path_obj.unlink()

                            # Update status
                            cursor.execute("""
                                UPDATE checkpoint_files
                                SET status = 'deleted'
                                WHERE checkpoint_id = ?
                            """, (checkpoint_id,))

                        except Exception as e:
                            self._logger.error(f"Failed to cleanup old checkpoint {checkpoint_id}: {e}")

                conn.commit()

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old checkpoints: {e}")
            finally:
                conn.close()

    def _log_checkpoint_access(self, checkpoint_id: str, access_type: str,
                              session_id: Optional[str] = None, duration: Optional[float] = None,
                              decompression_time: Optional[float] = None) -> None:
        """Log checkpoint access for analytics."""
        access_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO checkpoint_access_log (
                        access_id, checkpoint_id, access_type, session_id,
                        access_duration_seconds, decompression_time_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (access_id, checkpoint_id, access_type, session_id, duration, decompression_time))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log checkpoint access: {e}")
            finally:
                conn.close()
