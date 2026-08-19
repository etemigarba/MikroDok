"""
Module: checkpoint_registry_db
Description: Maintains registry of all checkpoints with metadata, providing comprehensive CRUD operations, search functionality, and integrity validation for checkpoint management
Phase: 4
Location: /src/modules/database/checkpoints_db/checkpoint_registry_db/
"""

# Standard library imports
import sqlite3
import json
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import asdict

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
from src.modules.logic.checkpoint_management_lg.base_interfaces import (
    CheckpointMetadata, CheckpointType, CheckpointStatus
)


class CheckpointRegistryDB:
    """
    Database layer for checkpoint registry management.
    
    Provides comprehensive checkpoint metadata storage, retrieval, and management
    operations with support for complex queries, integrity validation, and
    performance optimization through proper indexing.
    """
    
    def __init__(self, db_path: str = "data/checkpoints_registry.db"):
        """
        Initialize checkpoint registry database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Initialize database schema
        self._init_database()
        
        self._logger.info(f"CheckpointRegistryDB initialized with database: {self.db_path}")
    
    def _init_database(self) -> None:
        """Initialize database schema with optimized tables and indexes."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                
                # Create main checkpoint registry table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_registry (
                        checkpoint_id TEXT PRIMARY KEY,
                        checkpoint_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        model_state_size INTEGER NOT NULL,
                        optimizer_state_size INTEGER NOT NULL,
                        total_size INTEGER NOT NULL,
                        checksum TEXT NOT NULL,
                        training_step INTEGER NOT NULL,
                        epoch INTEGER NOT NULL,
                        loss_value REAL NOT NULL,
                        metrics_json TEXT,
                        tags_json TEXT,
                        description TEXT,
                        parent_checkpoint_id TEXT,
                        is_best BOOLEAN DEFAULT FALSE,
                        validation_errors_json TEXT,
                        session_id TEXT,
                        model_id TEXT,
                        created_by TEXT,
                        last_accessed TEXT,
                        access_count INTEGER DEFAULT 0,
                        storage_tier TEXT DEFAULT 'local',
                        compression_ratio REAL DEFAULT 1.0,
                        encryption_enabled BOOLEAN DEFAULT FALSE,
                        backup_status TEXT DEFAULT 'none',
                        retention_policy TEXT DEFAULT 'default',
                        archived BOOLEAN DEFAULT FALSE,
                        archived_at TEXT,
                        metadata_json TEXT,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (parent_checkpoint_id) REFERENCES checkpoint_registry(checkpoint_id)
                    )
                """)
                
                # Create performance-optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_status 
                    ON checkpoint_registry(status, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_type_epoch 
                    ON checkpoint_registry(checkpoint_type, epoch DESC, training_step DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_session 
                    ON checkpoint_registry(session_id, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_best 
                    ON checkpoint_registry(is_best, loss_value ASC) WHERE is_best = TRUE
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_parent 
                    ON checkpoint_registry(parent_checkpoint_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_model 
                    ON checkpoint_registry(model_id, epoch DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_size 
                    ON checkpoint_registry(total_size DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_access 
                    ON checkpoint_registry(last_accessed DESC, access_count DESC)
                """)
                
                # Create checkpoint tags table for efficient tag queries
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_tags (
                        checkpoint_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (checkpoint_id, tag),
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoint_registry(checkpoint_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tags_tag 
                    ON checkpoint_tags(tag, checkpoint_id)
                """)
                
                # Create checkpoint metrics table for efficient metric queries
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_metrics (
                        checkpoint_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        metric_type TEXT DEFAULT 'training',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (checkpoint_id, metric_name),
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoint_registry(checkpoint_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_name_value 
                    ON checkpoint_metrics(metric_name, metric_value DESC)
                """)
                
                # Create checkpoint search index for full-text search
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS checkpoint_search USING fts5(
                        checkpoint_id UNINDEXED,
                        description,
                        tags,
                        metadata,
                        content='checkpoint_registry',
                        content_rowid='rowid'
                    )
                """)
                
                # Create triggers to maintain search index
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS checkpoint_search_insert AFTER INSERT ON checkpoint_registry
                    BEGIN
                        INSERT INTO checkpoint_search(checkpoint_id, description, tags, metadata)
                        VALUES (NEW.checkpoint_id, NEW.description, NEW.tags_json, NEW.metadata_json);
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS checkpoint_search_update AFTER UPDATE ON checkpoint_registry
                    BEGIN
                        UPDATE checkpoint_search SET 
                            description = NEW.description,
                            tags = NEW.tags_json,
                            metadata = NEW.metadata_json
                        WHERE checkpoint_id = NEW.checkpoint_id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS checkpoint_search_delete AFTER DELETE ON checkpoint_registry
                    BEGIN
                        DELETE FROM checkpoint_search WHERE checkpoint_id = OLD.checkpoint_id;
                    END
                """)
                
                conn.commit()
                
                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'checkpoint_registry', 'checkpoint_tags', 'checkpoint_metrics', 'checkpoint_search'
                ]
                
                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")
                
                self._logger.info("Checkpoint registry database initialized successfully")
                
            except Exception as e:
                self._logger.error(f"Failed to initialize checkpoint registry database: {e}")
                raise
            finally:
                conn.close()
    
    def register_checkpoint(self, metadata: CheckpointMetadata) -> bool:
        """
        Register a new checkpoint in the registry.
        
        Args:
            metadata: Checkpoint metadata to register
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()
                    
                    # Convert metadata to database format
                    data = self._metadata_to_db_format(metadata)
                    
                    # Insert checkpoint record
                    cursor.execute("""
                        INSERT INTO checkpoint_registry (
                            checkpoint_id, checkpoint_type, status, file_path, created_at,
                            model_state_size, optimizer_state_size, total_size, checksum,
                            training_step, epoch, loss_value, metrics_json, tags_json,
                            description, parent_checkpoint_id, is_best, validation_errors_json,
                            session_id, model_id, created_by, last_accessed, access_count,
                            storage_tier, compression_ratio, encryption_enabled, backup_status,
                            retention_policy, archived, archived_at, metadata_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, data)
                    
                    # Insert tags if present
                    if metadata.tags:
                        for tag in metadata.tags:
                            cursor.execute("""
                                INSERT OR IGNORE INTO checkpoint_tags (checkpoint_id, tag)
                                VALUES (?, ?)
                            """, (metadata.checkpoint_id, tag))
                    
                    # Insert metrics if present
                    if metadata.metrics:
                        for metric_name, metric_value in metadata.metrics.items():
                            cursor.execute("""
                                INSERT OR REPLACE INTO checkpoint_metrics (checkpoint_id, metric_name, metric_value)
                                VALUES (?, ?, ?)
                            """, (metadata.checkpoint_id, metric_name, float(metric_value)))
                    
                    conn.commit()
                    
                    self._logger.info(f"Checkpoint registered successfully: {metadata.checkpoint_id}")
                    return True
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to register checkpoint {metadata.checkpoint_id}: {e}")
                    return False
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Database connection error during checkpoint registration: {e}")
            return False

    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """
        Retrieve checkpoint metadata by ID.

        Args:
            checkpoint_id: Unique checkpoint identifier

        Returns:
            CheckpointMetadata if found, None otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get checkpoint record
                    cursor.execute("""
                        SELECT * FROM checkpoint_registry WHERE checkpoint_id = ?
                    """, (checkpoint_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Update access tracking
                    cursor.execute("""
                        UPDATE checkpoint_registry
                        SET last_accessed = ?, access_count = access_count + 1
                        WHERE checkpoint_id = ?
                    """, (datetime.now(timezone.utc).isoformat(), checkpoint_id))

                    conn.commit()

                    # Convert to metadata object
                    metadata = self._db_format_to_metadata(row)

                    self._logger.debug(f"Retrieved checkpoint: {checkpoint_id}")
                    return metadata

                except Exception as e:
                    self._logger.error(f"Failed to retrieve checkpoint {checkpoint_id}: {e}")
                    return None
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during checkpoint retrieval: {e}")
            return None

    def update_checkpoint(self, metadata: CheckpointMetadata) -> bool:
        """
        Update existing checkpoint metadata.

        Args:
            metadata: Updated checkpoint metadata

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Check if checkpoint exists
                    cursor.execute("""
                        SELECT checkpoint_id FROM checkpoint_registry WHERE checkpoint_id = ?
                    """, (metadata.checkpoint_id,))

                    if not cursor.fetchone():
                        self._logger.warning(f"Checkpoint not found for update: {metadata.checkpoint_id}")
                        return False

                    # Convert metadata to database format
                    data = self._metadata_to_db_format(metadata)

                    # Update checkpoint record
                    cursor.execute("""
                        UPDATE checkpoint_registry SET
                            checkpoint_type = ?, status = ?, file_path = ?, created_at = ?,
                            model_state_size = ?, optimizer_state_size = ?, total_size = ?, checksum = ?,
                            training_step = ?, epoch = ?, loss_value = ?, metrics_json = ?, tags_json = ?,
                            description = ?, parent_checkpoint_id = ?, is_best = ?, validation_errors_json = ?,
                            session_id = ?, model_id = ?, created_by = ?, last_accessed = ?, access_count = ?,
                            storage_tier = ?, compression_ratio = ?, encryption_enabled = ?, backup_status = ?,
                            retention_policy = ?, archived = ?, archived_at = ?, metadata_json = ?, updated_at = ?
                        WHERE checkpoint_id = ?
                    """, data[1:] + (metadata.checkpoint_id,))

                    # Update tags
                    cursor.execute("DELETE FROM checkpoint_tags WHERE checkpoint_id = ?", (metadata.checkpoint_id,))
                    if metadata.tags:
                        for tag in metadata.tags:
                            cursor.execute("""
                                INSERT INTO checkpoint_tags (checkpoint_id, tag)
                                VALUES (?, ?)
                            """, (metadata.checkpoint_id, tag))

                    # Update metrics
                    cursor.execute("DELETE FROM checkpoint_metrics WHERE checkpoint_id = ?", (metadata.checkpoint_id,))
                    if metadata.metrics:
                        for metric_name, metric_value in metadata.metrics.items():
                            cursor.execute("""
                                INSERT INTO checkpoint_metrics (checkpoint_id, metric_name, metric_value)
                                VALUES (?, ?, ?)
                            """, (metadata.checkpoint_id, metric_name, float(metric_value)))

                    conn.commit()

                    self._logger.info(f"Checkpoint updated successfully: {metadata.checkpoint_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update checkpoint {metadata.checkpoint_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during checkpoint update: {e}")
            return False

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete checkpoint from registry.

        Args:
            checkpoint_id: Unique checkpoint identifier

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Check if checkpoint exists
                    cursor.execute("""
                        SELECT checkpoint_id FROM checkpoint_registry WHERE checkpoint_id = ?
                    """, (checkpoint_id,))

                    if not cursor.fetchone():
                        self._logger.warning(f"Checkpoint not found for deletion: {checkpoint_id}")
                        return False

                    # Delete checkpoint (cascading deletes will handle related tables)
                    cursor.execute("DELETE FROM checkpoint_registry WHERE checkpoint_id = ?", (checkpoint_id,))

                    conn.commit()

                    self._logger.info(f"Checkpoint deleted successfully: {checkpoint_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during checkpoint deletion: {e}")
            return False

    def list_checkpoints(self, session_id: Optional[str] = None, model_id: Optional[str] = None,
                        checkpoint_type: Optional[CheckpointType] = None, status: Optional[CheckpointStatus] = None,
                        limit: int = 100, offset: int = 0) -> List[CheckpointMetadata]:
        """
        List checkpoints with optional filtering.

        Args:
            session_id: Filter by session ID
            model_id: Filter by model ID
            checkpoint_type: Filter by checkpoint type
            status: Filter by status
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of checkpoint metadata
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Build query with filters
                    query = "SELECT * FROM checkpoint_registry WHERE 1=1"
                    params = []

                    if session_id:
                        query += " AND session_id = ?"
                        params.append(session_id)

                    if model_id:
                        query += " AND model_id = ?"
                        params.append(model_id)

                    if checkpoint_type:
                        query += " AND checkpoint_type = ?"
                        params.append(checkpoint_type.value)

                    if status:
                        query += " AND status = ?"
                        params.append(status.value)

                    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Convert to metadata objects
                    checkpoints = []
                    for row in rows:
                        metadata = self._db_format_to_metadata(row)
                        if metadata:
                            checkpoints.append(metadata)

                    self._logger.debug(f"Listed {len(checkpoints)} checkpoints")
                    return checkpoints

                except Exception as e:
                    self._logger.error(f"Failed to list checkpoints: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during checkpoint listing: {e}")
            return []

    def search_checkpoints(self, query: str, limit: int = 50) -> List[CheckpointMetadata]:
        """
        Full-text search for checkpoints.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching checkpoint metadata
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Perform full-text search
                    cursor.execute("""
                        SELECT cr.* FROM checkpoint_registry cr
                        JOIN checkpoint_search cs ON cr.checkpoint_id = cs.checkpoint_id
                        WHERE checkpoint_search MATCH ?
                        ORDER BY rank LIMIT ?
                    """, (query, limit))

                    rows = cursor.fetchall()

                    # Convert to metadata objects
                    checkpoints = []
                    for row in rows:
                        metadata = self._db_format_to_metadata(row)
                        if metadata:
                            checkpoints.append(metadata)

                    self._logger.debug(f"Search found {len(checkpoints)} checkpoints for query: {query}")
                    return checkpoints

                except Exception as e:
                    self._logger.error(f"Failed to search checkpoints: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during checkpoint search: {e}")
            return []

    def get_best_checkpoints(self, model_id: Optional[str] = None, limit: int = 10) -> List[CheckpointMetadata]:
        """
        Get best performing checkpoints.

        Args:
            model_id: Filter by model ID
            limit: Maximum number of results

        Returns:
            List of best checkpoint metadata
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    query = """
                        SELECT * FROM checkpoint_registry
                        WHERE is_best = TRUE
                    """
                    params = []

                    if model_id:
                        query += " AND model_id = ?"
                        params.append(model_id)

                    query += " ORDER BY loss_value ASC LIMIT ?"
                    params.append(limit)

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Convert to metadata objects
                    checkpoints = []
                    for row in rows:
                        metadata = self._db_format_to_metadata(row)
                        if metadata:
                            checkpoints.append(metadata)

                    self._logger.debug(f"Retrieved {len(checkpoints)} best checkpoints")
                    return checkpoints

                except Exception as e:
                    self._logger.error(f"Failed to get best checkpoints: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during best checkpoints retrieval: {e}")
            return []

    def get_checkpoint_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive checkpoint registry statistics.

        Returns:
            Dictionary with various statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    stats = {}

                    # Total checkpoint count
                    cursor.execute("SELECT COUNT(*) FROM checkpoint_registry")
                    stats['total_checkpoints'] = cursor.fetchone()[0]

                    # Count by status
                    cursor.execute("""
                        SELECT status, COUNT(*) FROM checkpoint_registry
                        GROUP BY status
                    """)
                    stats['by_status'] = dict(cursor.fetchall())

                    # Count by type
                    cursor.execute("""
                        SELECT checkpoint_type, COUNT(*) FROM checkpoint_registry
                        GROUP BY checkpoint_type
                    """)
                    stats['by_type'] = dict(cursor.fetchall())

                    # Storage statistics
                    cursor.execute("""
                        SELECT
                            SUM(total_size) as total_size,
                            AVG(total_size) as avg_size,
                            MAX(total_size) as max_size,
                            MIN(total_size) as min_size
                        FROM checkpoint_registry
                    """)
                    size_stats = cursor.fetchone()
                    stats['storage'] = {
                        'total_size_bytes': size_stats[0] or 0,
                        'average_size_bytes': size_stats[1] or 0,
                        'largest_size_bytes': size_stats[2] or 0,
                        'smallest_size_bytes': size_stats[3] or 0
                    }

                    # Best checkpoints count
                    cursor.execute("SELECT COUNT(*) FROM checkpoint_registry WHERE is_best = TRUE")
                    stats['best_checkpoints'] = cursor.fetchone()[0]

                    # Recent activity (last 24 hours)
                    cursor.execute("""
                        SELECT COUNT(*) FROM checkpoint_registry
                        WHERE created_at > datetime('now', '-1 day')
                    """)
                    stats['recent_checkpoints'] = cursor.fetchone()[0]

                    # Most accessed checkpoints
                    cursor.execute("""
                        SELECT checkpoint_id, access_count FROM checkpoint_registry
                        ORDER BY access_count DESC LIMIT 5
                    """)
                    stats['most_accessed'] = [
                        {'checkpoint_id': row[0], 'access_count': row[1]}
                        for row in cursor.fetchall()
                    ]

                    self._logger.debug("Retrieved checkpoint registry statistics")
                    return stats

                except Exception as e:
                    self._logger.error(f"Failed to get checkpoint statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during statistics retrieval: {e}")
            return {}

    def verify_integrity(self, checkpoint_id: str) -> Tuple[bool, List[str]]:
        """
        Verify checkpoint integrity and consistency.

        Args:
            checkpoint_id: Checkpoint to verify

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get checkpoint record
                    cursor.execute("""
                        SELECT file_path, checksum, total_size FROM checkpoint_registry
                        WHERE checkpoint_id = ?
                    """, (checkpoint_id,))

                    row = cursor.fetchone()
                    if not row:
                        issues.append(f"Checkpoint {checkpoint_id} not found in registry")
                        return False, issues

                    file_path, expected_checksum, expected_size = row

                    # Check if file exists
                    checkpoint_file = Path(file_path)
                    if not checkpoint_file.exists():
                        issues.append(f"Checkpoint file not found: {file_path}")
                    else:
                        # Verify file size
                        actual_size = checkpoint_file.stat().st_size
                        if actual_size != expected_size:
                            issues.append(f"File size mismatch: expected {expected_size}, got {actual_size}")

                        # Verify checksum
                        try:
                            actual_checksum = self._calculate_file_checksum(checkpoint_file)
                            if actual_checksum != expected_checksum:
                                issues.append(f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}")
                        except Exception as e:
                            issues.append(f"Failed to calculate checksum: {e}")

                    # Check parent relationship consistency
                    cursor.execute("""
                        SELECT parent_checkpoint_id FROM checkpoint_registry
                        WHERE checkpoint_id = ?
                    """, (checkpoint_id,))

                    parent_result = cursor.fetchone()
                    if parent_result and parent_result[0]:
                        parent_id = parent_result[0]
                        cursor.execute("""
                            SELECT checkpoint_id FROM checkpoint_registry
                            WHERE checkpoint_id = ?
                        """, (parent_id,))

                        if not cursor.fetchone():
                            issues.append(f"Parent checkpoint {parent_id} not found")

                    is_valid = len(issues) == 0

                    self._logger.debug(f"Integrity check for {checkpoint_id}: {'PASSED' if is_valid else 'FAILED'}")
                    return is_valid, issues

                except Exception as e:
                    issues.append(f"Database error during integrity check: {e}")
                    return False, issues
                finally:
                    conn.close()

        except Exception as e:
            issues.append(f"Connection error during integrity check: {e}")
            return False, issues

    def _metadata_to_db_format(self, metadata: CheckpointMetadata) -> Tuple:
        """Convert CheckpointMetadata to database tuple format."""
        return (
            metadata.checkpoint_id,
            metadata.checkpoint_type.value,
            metadata.status.value,
            str(metadata.file_path),
            metadata.created_at.isoformat(),
            metadata.model_state_size,
            metadata.optimizer_state_size,
            metadata.total_size,
            metadata.checksum,
            metadata.training_step,
            metadata.epoch,
            metadata.loss_value,
            json.dumps(metadata.metrics) if metadata.metrics else None,
            json.dumps(list(metadata.tags)) if metadata.tags else None,
            metadata.description,
            metadata.parent_checkpoint_id,
            metadata.is_best,
            json.dumps([str(error) for error in metadata.validation_errors]) if metadata.validation_errors else None,
            getattr(metadata, 'session_id', None),
            getattr(metadata, 'model_id', None),
            getattr(metadata, 'created_by', None),
            datetime.now(timezone.utc).isoformat(),  # last_accessed
            0,  # access_count
            getattr(metadata, 'storage_tier', 'local'),
            getattr(metadata, 'compression_ratio', 1.0),
            getattr(metadata, 'encryption_enabled', False),
            getattr(metadata, 'backup_status', 'none'),
            getattr(metadata, 'retention_policy', 'default'),
            getattr(metadata, 'archived', False),
            getattr(metadata, 'archived_at', None),
            json.dumps(getattr(metadata, 'additional_metadata', {})),
            datetime.now(timezone.utc).isoformat()  # updated_at
        )

    def _db_format_to_metadata(self, row: Tuple) -> Optional[CheckpointMetadata]:
        """Convert database row to CheckpointMetadata object."""
        try:
            if not row:
                return None

            # Parse JSON fields safely
            metrics = json.loads(row[12]) if row[12] else {}
            tags = set(json.loads(row[13])) if row[13] else set()
            validation_errors = json.loads(row[17]) if row[17] else []

            # Create metadata object
            metadata = CheckpointMetadata(
                checkpoint_id=row[0],
                checkpoint_type=CheckpointType(row[1]),
                status=CheckpointStatus(row[2]),
                file_path=Path(row[3]),
                created_at=datetime.fromisoformat(row[4]),
                model_state_size=row[5],
                optimizer_state_size=row[6],
                total_size=row[7],
                checksum=row[8],
                training_step=row[9],
                epoch=row[10],
                loss_value=row[11],
                metrics=metrics,
                tags=tags,
                description=row[14],
                parent_checkpoint_id=row[15],
                is_best=bool(row[16]),
                validation_errors=validation_errors
            )

            # Add extended attributes
            metadata.session_id = row[18]
            metadata.model_id = row[19]
            metadata.created_by = row[20]
            metadata.last_accessed = row[21]
            metadata.access_count = row[22]
            metadata.storage_tier = row[23]
            metadata.compression_ratio = row[24]
            metadata.encryption_enabled = bool(row[25])
            metadata.backup_status = row[26]
            metadata.retention_policy = row[27]
            metadata.archived = bool(row[28])
            metadata.archived_at = row[29]
            metadata.additional_metadata = json.loads(row[30]) if row[30] else {}
            metadata.updated_at = row[31]

            return metadata

        except Exception as e:
            self._logger.error(f"Failed to convert database row to metadata: {e}")
            return None

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("CheckpointRegistryDB closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
