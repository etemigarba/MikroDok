"""
Module: checkpoint_storage_db
Description: Stores training checkpoint metadata with retention policies and best model tracking
Phase: 4
Location: /src/modules/database/model_repository_db/checkpoint_storage_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class CheckpointStatus(Enum):
    """Checkpoint status enumeration."""
    CREATED = "created"
    SAVING = "saving"
    SAVED = "saved"
    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"
    CORRUPTED = "corrupted"
    ARCHIVED = "archived"


class CheckpointType(Enum):
    """Checkpoint type enumeration."""
    TRAINING = "training"
    VALIDATION = "validation"
    BEST_MODEL = "best_model"
    FINAL_MODEL = "final_model"
    BACKUP = "backup"
    MILESTONE = "milestone"


class RetentionPolicy(Enum):
    """Retention policy enumeration."""
    KEEP_ALL = "keep_all"
    KEEP_BEST = "keep_best"
    KEEP_RECENT = "keep_recent"
    KEEP_MILESTONES = "keep_milestones"
    CUSTOM = "custom"


@dataclass
class CheckpointMetadata:
    """Checkpoint metadata data structure."""
    checkpoint_id: str
    model_id: str
    training_session_id: Optional[str] = None
    checkpoint_type: CheckpointType = CheckpointType.TRAINING
    status: CheckpointStatus = CheckpointStatus.CREATED
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    epoch: Optional[int] = None
    step: Optional[int] = None
    loss_value: Optional[float] = None
    metrics: Optional[Dict[str, float]] = None
    created_at: datetime = None
    updated_at: datetime = None
    created_by: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_best: bool = False
    is_milestone: bool = False
    retention_policy: RetentionPolicy = RetentionPolicy.KEEP_RECENT
    expiry_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.tags is None:
            self.tags = []
        if self.metrics is None:
            self.metrics = {}


@dataclass
class RetentionRule:
    """Retention rule configuration."""
    rule_id: str
    model_id: str
    policy: RetentionPolicy
    max_checkpoints: Optional[int] = None
    retention_days: Optional[int] = None
    keep_best_n: Optional[int] = None
    metric_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class CheckpointStorageDB:
    """
    Checkpoint storage database for managing training checkpoint metadata.
    
    Provides comprehensive checkpoint management including retention policies,
    best model tracking, and automated cleanup based on configurable rules.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the checkpoint storage database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to model repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "model_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "checkpoint_storage.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._default_retention_days = 30  # Keep checkpoints for 30 days by default
        self._max_checkpoints_per_model = 100  # Maximum checkpoints per model
        self._cleanup_interval_hours = 24  # Run cleanup every 24 hours
        self._best_model_retention_days = 365  # Keep best models for 1 year
        
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
                
                # Create checkpoints table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        training_session_id TEXT,
                        checkpoint_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        file_path TEXT,
                        file_size_bytes INTEGER,
                        checksum TEXT,
                        epoch INTEGER,
                        step INTEGER,
                        loss_value REAL,
                        metrics_json TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        created_by TEXT,
                        description TEXT,
                        tags_json TEXT,
                        is_best BOOLEAN DEFAULT 0,
                        is_milestone BOOLEAN DEFAULT 0,
                        retention_policy TEXT NOT NULL DEFAULT 'keep_recent',
                        expiry_date TEXT,
                        metadata_json TEXT,
                        
                        CONSTRAINT valid_checkpoint_type CHECK (checkpoint_type IN ('training', 'validation', 'best_model', 'final_model', 'backup', 'milestone')),
                        CONSTRAINT valid_status CHECK (status IN ('created', 'saving', 'saved', 'loading', 'loaded', 'failed', 'corrupted', 'archived')),
                        CONSTRAINT valid_retention_policy CHECK (retention_policy IN ('keep_all', 'keep_best', 'keep_recent', 'keep_milestones', 'custom'))
                    )
                """)
                
                # Create performance-optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_model_type 
                    ON checkpoints(model_id, checkpoint_type, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_session 
                    ON checkpoints(training_session_id, epoch DESC, step DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_best 
                    ON checkpoints(model_id, is_best, loss_value ASC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_expiry 
                    ON checkpoints(expiry_date, retention_policy)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_status 
                    ON checkpoints(status, created_at DESC)
                """)
                
                # Create retention rules table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retention_rules (
                        rule_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        policy TEXT NOT NULL,
                        max_checkpoints INTEGER,
                        retention_days INTEGER,
                        keep_best_n INTEGER,
                        metric_name TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_policy CHECK (policy IN ('keep_all', 'keep_best', 'keep_recent', 'keep_milestones', 'custom')),
                        UNIQUE(model_id, policy)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retention_rules_model 
                    ON retention_rules(model_id, is_active)
                """)
                
                # Create checkpoint access log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_access_log (
                        access_id TEXT PRIMARY KEY,
                        checkpoint_id TEXT NOT NULL,
                        access_type TEXT NOT NULL,
                        accessed_at TEXT NOT NULL,
                        accessed_by TEXT,
                        access_duration_ms INTEGER,
                        success BOOLEAN DEFAULT 1,
                        error_message TEXT,
                        
                        CONSTRAINT valid_access_type CHECK (access_type IN ('load', 'save', 'verify', 'delete')),
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(checkpoint_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_access_log_checkpoint 
                    ON checkpoint_access_log(checkpoint_id, accessed_at DESC)
                """)
                
                # Create checkpoint validation table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_validation (
                        validation_id TEXT PRIMARY KEY,
                        checkpoint_id TEXT NOT NULL,
                        validation_type TEXT NOT NULL,
                        validation_status TEXT NOT NULL,
                        validation_result_json TEXT,
                        validated_at TEXT NOT NULL,
                        validated_by TEXT,
                        error_details TEXT,
                        
                        CONSTRAINT valid_validation_type CHECK (validation_type IN ('integrity', 'format', 'compatibility', 'performance')),
                        CONSTRAINT valid_validation_status CHECK (validation_status IN ('passed', 'failed', 'warning', 'skipped')),
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(checkpoint_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_validation_checkpoint 
                    ON checkpoint_validation(checkpoint_id, validation_type, validated_at DESC)
                """)
                
                conn.commit()
                self._logger.info("Checkpoint storage database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize checkpoint storage database: {e}")
                raise
            finally:
                conn.close()

    def create_checkpoint(self, checkpoint_metadata: CheckpointMetadata) -> str:
        """
        Create a new checkpoint record.

        Args:
            checkpoint_metadata: Checkpoint metadata to store

        Returns:
            Checkpoint ID of the created checkpoint

        Raises:
            ValueError: If checkpoint data is invalid
        """
        if not checkpoint_metadata.checkpoint_id:
            checkpoint_metadata.checkpoint_id = str(uuid.uuid4())

        # Validate required fields
        if not checkpoint_metadata.model_id:
            raise ValueError("Model ID is required")

        checkpoint_metadata.updated_at = datetime.now(timezone.utc)

        # Set expiry date based on retention policy
        if not checkpoint_metadata.expiry_date:
            checkpoint_metadata.expiry_date = self._calculate_expiry_date(checkpoint_metadata)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clear previous best model flag if this is marked as best
                if checkpoint_metadata.is_best:
                    cursor.execute("""
                        UPDATE checkpoints
                        SET is_best = 0
                        WHERE model_id = ? AND is_best = 1
                    """, (checkpoint_metadata.model_id,))

                # Insert checkpoint record
                cursor.execute("""
                    INSERT INTO checkpoints (
                        checkpoint_id, model_id, training_session_id, checkpoint_type, status,
                        file_path, file_size_bytes, checksum, epoch, step, loss_value,
                        metrics_json, created_at, updated_at, created_by, description,
                        tags_json, is_best, is_milestone, retention_policy, expiry_date, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    checkpoint_metadata.checkpoint_id,
                    checkpoint_metadata.model_id,
                    checkpoint_metadata.training_session_id,
                    checkpoint_metadata.checkpoint_type.value,
                    checkpoint_metadata.status.value,
                    checkpoint_metadata.file_path,
                    checkpoint_metadata.file_size_bytes,
                    checkpoint_metadata.checksum,
                    checkpoint_metadata.epoch,
                    checkpoint_metadata.step,
                    checkpoint_metadata.loss_value,
                    json.dumps(checkpoint_metadata.metrics) if checkpoint_metadata.metrics else None,
                    checkpoint_metadata.created_at.isoformat(),
                    checkpoint_metadata.updated_at.isoformat(),
                    checkpoint_metadata.created_by,
                    checkpoint_metadata.description,
                    json.dumps(checkpoint_metadata.tags) if checkpoint_metadata.tags else None,
                    checkpoint_metadata.is_best,
                    checkpoint_metadata.is_milestone,
                    checkpoint_metadata.retention_policy.value,
                    checkpoint_metadata.expiry_date.isoformat() if checkpoint_metadata.expiry_date else None,
                    json.dumps(checkpoint_metadata.metadata) if checkpoint_metadata.metadata else None
                ))

                conn.commit()
                self._logger.info(f"Created checkpoint: {checkpoint_metadata.checkpoint_id}")

                # Apply retention policies
                self._apply_retention_policies(checkpoint_metadata.model_id)

                return checkpoint_metadata.checkpoint_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create checkpoint {checkpoint_metadata.checkpoint_id}: {e}")
                raise
            finally:
                conn.close()

    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """
        Retrieve a checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint metadata or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT checkpoint_id, model_id, training_session_id, checkpoint_type, status,
                           file_path, file_size_bytes, checksum, epoch, step, loss_value,
                           metrics_json, created_at, updated_at, created_by, description,
                           tags_json, is_best, is_milestone, retention_policy, expiry_date, metadata_json
                    FROM checkpoints
                    WHERE checkpoint_id = ?
                """, (checkpoint_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_checkpoint_metadata(row)

            except Exception as e:
                self._logger.error(f"Failed to get checkpoint {checkpoint_id}: {e}")
                raise
            finally:
                conn.close()

    def update_checkpoint(self, checkpoint_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update checkpoint metadata.

        Args:
            checkpoint_id: Checkpoint identifier
            updates: Dictionary of fields to update

        Returns:
            True if checkpoint was updated, False if not found
        """
        if not updates:
            return False

        # Validate update fields
        valid_fields = {
            'status', 'file_path', 'file_size_bytes', 'checksum', 'epoch', 'step',
            'loss_value', 'metrics', 'description', 'tags', 'is_best', 'is_milestone',
            'retention_policy', 'expiry_date', 'metadata'
        }

        invalid_fields = set(updates.keys()) - valid_fields
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {invalid_fields}")

        # Build update query
        set_clauses = []
        params = []

        for field, value in updates.items():
            if field in ['metrics', 'tags', 'metadata']:
                set_clauses.append(f"{field}_json = ?")
                params.append(json.dumps(value) if value is not None else None)
            elif field in ['status', 'checkpoint_type', 'retention_policy']:
                set_clauses.append(f"{field} = ?")
                params.append(value.value if hasattr(value, 'value') else value)
            elif field == 'expiry_date' and value:
                set_clauses.append(f"{field} = ?")
                params.append(value.isoformat() if hasattr(value, 'isoformat') else value)
            else:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(checkpoint_id)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Handle best model flag
                if 'is_best' in updates and updates['is_best']:
                    # Get model_id first
                    cursor.execute("SELECT model_id FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))
                    result = cursor.fetchone()
                    if result:
                        model_id = result[0]
                        cursor.execute("""
                            UPDATE checkpoints
                            SET is_best = 0
                            WHERE model_id = ? AND is_best = 1 AND checkpoint_id != ?
                        """, (model_id, checkpoint_id))

                query = f"""
                    UPDATE checkpoints
                    SET {', '.join(set_clauses)}
                    WHERE checkpoint_id = ?
                """

                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.info(f"Updated checkpoint: {checkpoint_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update checkpoint {checkpoint_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            True if checkpoint was deleted, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("DELETE FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.info(f"Deleted checkpoint: {checkpoint_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
                raise
            finally:
                conn.close()

    def list_checkpoints(self, model_id: Optional[str] = None, training_session_id: Optional[str] = None,
                        checkpoint_type: Optional[CheckpointType] = None, status: Optional[CheckpointStatus] = None,
                        is_best: Optional[bool] = None, limit: int = 100, offset: int = 0) -> List[CheckpointMetadata]:
        """
        List checkpoints with optional filtering.

        Args:
            model_id: Filter by model ID
            training_session_id: Filter by training session ID
            checkpoint_type: Filter by checkpoint type
            status: Filter by status
            is_best: Filter by best model flag
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of checkpoint metadata
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT checkpoint_id, model_id, training_session_id, checkpoint_type, status,
                           file_path, file_size_bytes, checksum, epoch, step, loss_value,
                           metrics_json, created_at, updated_at, created_by, description,
                           tags_json, is_best, is_milestone, retention_policy, expiry_date, metadata_json
                    FROM checkpoints
                    WHERE 1=1
                """
                params = []

                if model_id:
                    query += " AND model_id = ?"
                    params.append(model_id)

                if training_session_id:
                    query += " AND training_session_id = ?"
                    params.append(training_session_id)

                if checkpoint_type:
                    query += " AND checkpoint_type = ?"
                    params.append(checkpoint_type.value)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                if is_best is not None:
                    query += " AND is_best = ?"
                    params.append(is_best)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_checkpoint_metadata(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to list checkpoints: {e}")
                raise
            finally:
                conn.close()

    def get_best_checkpoint(self, model_id: str, metric_name: Optional[str] = None) -> Optional[CheckpointMetadata]:
        """
        Get the best checkpoint for a model.

        Args:
            model_id: Model identifier
            metric_name: Specific metric to optimize for

        Returns:
            Best checkpoint metadata or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if metric_name:
                    # Find best based on specific metric
                    cursor.execute("""
                        SELECT checkpoint_id, model_id, training_session_id, checkpoint_type, status,
                               file_path, file_size_bytes, checksum, epoch, step, loss_value,
                               metrics_json, created_at, updated_at, created_by, description,
                               tags_json, is_best, is_milestone, retention_policy, expiry_date, metadata_json
                        FROM checkpoints
                        WHERE model_id = ? AND metrics_json IS NOT NULL
                        ORDER BY json_extract(metrics_json, '$.' || ?) DESC
                        LIMIT 1
                    """, (model_id, metric_name))
                else:
                    # Find checkpoint marked as best or best by loss
                    cursor.execute("""
                        SELECT checkpoint_id, model_id, training_session_id, checkpoint_type, status,
                               file_path, file_size_bytes, checksum, epoch, step, loss_value,
                               metrics_json, created_at, updated_at, created_by, description,
                               tags_json, is_best, is_milestone, retention_policy, expiry_date, metadata_json
                        FROM checkpoints
                        WHERE model_id = ? AND (is_best = 1 OR loss_value IS NOT NULL)
                        ORDER BY is_best DESC, loss_value ASC
                        LIMIT 1
                    """, (model_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_checkpoint_metadata(row)

            except Exception as e:
                self._logger.error(f"Failed to get best checkpoint for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def create_retention_rule(self, retention_rule: RetentionRule) -> str:
        """
        Create a retention rule for a model.

        Args:
            retention_rule: Retention rule configuration

        Returns:
            Rule ID
        """
        if not retention_rule.rule_id:
            retention_rule.rule_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO retention_rules (
                        rule_id, model_id, policy, max_checkpoints, retention_days,
                        keep_best_n, metric_name, is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    retention_rule.rule_id,
                    retention_rule.model_id,
                    retention_rule.policy.value,
                    retention_rule.max_checkpoints,
                    retention_rule.retention_days,
                    retention_rule.keep_best_n,
                    retention_rule.metric_name,
                    retention_rule.is_active,
                    retention_rule.created_at.isoformat()
                ))

                conn.commit()
                self._logger.info(f"Created retention rule for model {retention_rule.model_id}")
                return retention_rule.rule_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create retention rule: {e}")
                raise
            finally:
                conn.close()

    def log_checkpoint_access(self, checkpoint_id: str, access_type: str, accessed_by: Optional[str] = None,
                             access_duration_ms: Optional[int] = None, success: bool = True,
                             error_message: Optional[str] = None) -> str:
        """
        Log checkpoint access for auditing.

        Args:
            checkpoint_id: Checkpoint identifier
            access_type: Type of access (load, save, verify, delete)
            accessed_by: User performing the access
            access_duration_ms: Duration of access in milliseconds
            success: Whether the access was successful
            error_message: Error message if access failed

        Returns:
            Access log ID
        """
        access_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO checkpoint_access_log (
                        access_id, checkpoint_id, access_type, accessed_at, accessed_by,
                        access_duration_ms, success, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    access_id, checkpoint_id, access_type,
                    datetime.now(timezone.utc).isoformat(),
                    accessed_by, access_duration_ms, success, error_message
                ))

                conn.commit()
                return access_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log checkpoint access: {e}")
                raise
            finally:
                conn.close()

    def cleanup_expired_checkpoints(self) -> int:
        """
        Clean up expired checkpoints based on retention policies.

        Returns:
            Number of checkpoints cleaned up
        """
        current_time = datetime.now(timezone.utc)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Don't delete best models or milestones
                cursor.execute("""
                    DELETE FROM checkpoints
                    WHERE expiry_date < ? AND is_best = 0 AND is_milestone = 0
                """, (current_time.isoformat(),))

                deleted_count = cursor.rowcount
                conn.commit()

                self._logger.info(f"Cleaned up {deleted_count} expired checkpoints")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup expired checkpoints: {e}")
                raise
            finally:
                conn.close()

    def _apply_retention_policies(self, model_id: str) -> None:
        """Apply retention policies for a model."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            # Get retention rules for the model
            cursor.execute("""
                SELECT policy, max_checkpoints, retention_days, keep_best_n, metric_name
                FROM retention_rules
                WHERE model_id = ? AND is_active = 1
            """, (model_id,))

            rules = cursor.fetchall()

            for rule in rules:
                policy, max_checkpoints, retention_days, keep_best_n, metric_name = rule

                if policy == 'keep_recent' and max_checkpoints:
                    self._apply_keep_recent_policy(cursor, model_id, max_checkpoints)
                elif policy == 'keep_best' and keep_best_n:
                    self._apply_keep_best_policy(cursor, model_id, keep_best_n, metric_name)

    def _apply_keep_recent_policy(self, cursor: sqlite3.Cursor, model_id: str, max_checkpoints: int) -> None:
        """Apply keep recent policy."""
        cursor.execute("""
            DELETE FROM checkpoints
            WHERE model_id = ? AND is_best = 0 AND is_milestone = 0
            AND checkpoint_id NOT IN (
                SELECT checkpoint_id FROM checkpoints
                WHERE model_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            )
        """, (model_id, model_id, max_checkpoints))

    def _apply_keep_best_policy(self, cursor: sqlite3.Cursor, model_id: str, keep_best_n: int, metric_name: Optional[str]) -> None:
        """Apply keep best policy."""
        if metric_name:
            # Keep best N based on specific metric
            cursor.execute("""
                DELETE FROM checkpoints
                WHERE model_id = ? AND is_milestone = 0
                AND checkpoint_id NOT IN (
                    SELECT checkpoint_id FROM checkpoints
                    WHERE model_id = ? AND metrics_json IS NOT NULL
                    ORDER BY json_extract(metrics_json, '$.' || ?) DESC
                    LIMIT ?
                )
            """, (model_id, model_id, metric_name, keep_best_n))
        else:
            # Keep best N based on loss value
            cursor.execute("""
                DELETE FROM checkpoints
                WHERE model_id = ? AND is_milestone = 0
                AND checkpoint_id NOT IN (
                    SELECT checkpoint_id FROM checkpoints
                    WHERE model_id = ? AND loss_value IS NOT NULL
                    ORDER BY loss_value ASC
                    LIMIT ?
                )
            """, (model_id, model_id, keep_best_n))

    def _calculate_expiry_date(self, checkpoint_metadata: CheckpointMetadata) -> Optional[datetime]:
        """Calculate expiry date based on retention policy."""
        if checkpoint_metadata.retention_policy == RetentionPolicy.KEEP_ALL:
            return None
        elif checkpoint_metadata.retention_policy == RetentionPolicy.KEEP_BEST and checkpoint_metadata.is_best:
            return datetime.now(timezone.utc) + timedelta(days=self._best_model_retention_days)
        elif checkpoint_metadata.retention_policy == RetentionPolicy.KEEP_MILESTONES and checkpoint_metadata.is_milestone:
            return None
        else:
            return datetime.now(timezone.utc) + timedelta(days=self._default_retention_days)

    def _row_to_checkpoint_metadata(self, row: Tuple) -> CheckpointMetadata:
        """Convert database row to CheckpointMetadata object."""
        return CheckpointMetadata(
            checkpoint_id=row[0],
            model_id=row[1],
            training_session_id=row[2],
            checkpoint_type=CheckpointType(row[3]),
            status=CheckpointStatus(row[4]),
            file_path=row[5],
            file_size_bytes=row[6],
            checksum=row[7],
            epoch=row[8],
            step=row[9],
            loss_value=row[10],
            metrics=json.loads(row[11]) if row[11] else {},
            created_at=datetime.fromisoformat(row[12]) if row[12] else None,
            updated_at=datetime.fromisoformat(row[13]) if row[13] else None,
            created_by=row[14],
            description=row[15],
            tags=json.loads(row[16]) if row[16] else [],
            is_best=bool(row[17]),
            is_milestone=bool(row[18]),
            retention_policy=RetentionPolicy(row[19]),
            expiry_date=datetime.fromisoformat(row[20]) if row[20] else None,
            metadata=json.loads(row[21]) if row[21] else None
        )

    def get_checkpoint_statistics(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get checkpoint statistics.

        Args:
            model_id: Filter by model ID

        Returns:
            Dictionary containing checkpoint statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                base_query = "FROM checkpoints WHERE 1=1"
                params = []

                if model_id:
                    base_query += " AND model_id = ?"
                    params.append(model_id)

                # Total count
                cursor.execute(f"SELECT COUNT(*) {base_query}", params)
                total_count = cursor.fetchone()[0]

                # Count by type
                cursor.execute(f"SELECT checkpoint_type, COUNT(*) {base_query} GROUP BY checkpoint_type", params)
                type_counts = dict(cursor.fetchall())

                # Count by status
                cursor.execute(f"SELECT status, COUNT(*) {base_query} GROUP BY status", params)
                status_counts = dict(cursor.fetchall())

                # Total file size
                cursor.execute(f"SELECT SUM(file_size_bytes) {base_query}", params)
                total_size = cursor.fetchone()[0] or 0

                # Best models count
                cursor.execute(f"SELECT COUNT(*) {base_query} AND is_best = 1", params)
                best_count = cursor.fetchone()[0]

                return {
                    'total_checkpoints': total_count,
                    'checkpoints_by_type': type_counts,
                    'checkpoints_by_status': status_counts,
                    'total_size_bytes': total_size,
                    'best_models_count': best_count
                }

            except Exception as e:
                self._logger.error(f"Failed to get checkpoint statistics: {e}")
                raise
            finally:
                conn.close()
