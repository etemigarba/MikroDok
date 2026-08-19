"""
Module: session_repository_db
Description: CRUD operations for training session records with transaction support and thread-safe operations
Phase: 4
Location: /src/modules/database/training_sessions_db/session_repository_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class SessionStatus(Enum):
    """Training session status enumeration."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESUMING = "resuming"


class SessionPriority(Enum):
    """Training session priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class SessionRepositoryDB:
    """
    Session repository database for training session CRUD operations.
    
    Handles creating, reading, updating, and deleting training session records
    with SQLite database operations. Provides thread-safe operations with
    transaction support for session management, status tracking, and metadata
    persistence with optimized queries for session retrieval and filtering.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the session repository database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training sessions data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_sessions"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "session_repository.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._session_retention_days = 365  # Keep sessions for 1 year
        self._max_sessions_per_model = 1000  # Maximum sessions per model
        self._batch_size = 100  # Batch size for bulk operations
        
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
                
                # Create training sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS training_sessions (
                        session_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        session_name TEXT,
                        description TEXT,
                        status TEXT NOT NULL DEFAULT 'created',
                        priority INTEGER NOT NULL DEFAULT 2,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        paused_at TEXT,
                        resumed_at TEXT,
                        last_updated_at TEXT NOT NULL,
                        created_by TEXT,
                        total_epochs INTEGER DEFAULT 0,
                        current_epoch INTEGER DEFAULT 0,
                        current_step INTEGER DEFAULT 0,
                        total_steps INTEGER DEFAULT 0,
                        estimated_duration_seconds REAL,
                        actual_duration_seconds REAL,
                        best_metric REAL,
                        best_metric_name TEXT,
                        last_checkpoint_path TEXT,
                        error_message TEXT,
                        error_count INTEGER DEFAULT 0,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        configuration_json TEXT,
                        resource_allocation_json TEXT,
                        hyperparameters_json TEXT,
                        metadata_json TEXT,
                        tags_json TEXT,
                        notes TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_model_id ON training_sessions (model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON training_sessions (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON training_sessions (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_priority ON training_sessions (priority, created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_model_status ON training_sessions (model_id, status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON training_sessions (last_updated_at)")
                
                # Create session metrics table for performance tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_metrics (
                        metric_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        metric_type TEXT NOT NULL,
                        epoch INTEGER,
                        step INTEGER,
                        timestamp TEXT NOT NULL,
                        metadata_json TEXT,
                        FOREIGN KEY (session_id) REFERENCES training_sessions (session_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_session_id ON session_metrics (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON session_metrics (metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON session_metrics (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_epoch ON session_metrics (epoch)")
                
                # Create session checkpoints table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        checkpoint_name TEXT NOT NULL,
                        checkpoint_path TEXT NOT NULL,
                        epoch INTEGER NOT NULL,
                        step INTEGER NOT NULL,
                        metric_value REAL,
                        metric_name TEXT,
                        file_size_mb REAL,
                        is_best BOOLEAN DEFAULT FALSE,
                        is_latest BOOLEAN DEFAULT FALSE,
                        created_at TEXT NOT NULL,
                        metadata_json TEXT,
                        FOREIGN KEY (session_id) REFERENCES training_sessions (session_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session_id ON session_checkpoints (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_epoch ON session_checkpoints (epoch)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_best ON session_checkpoints (is_best)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_latest ON session_checkpoints (is_latest)")
                
                conn.commit()
                self._logger.info("Session repository database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize session repository database: {e}")
                raise
            finally:
                conn.close()
    
    def create_session(self, model_id: str, model_name: str, session_name: Optional[str] = None,
                      description: Optional[str] = None, priority: SessionPriority = SessionPriority.NORMAL,
                      created_by: Optional[str] = None, configuration: Optional[Dict[str, Any]] = None,
                      resource_allocation: Optional[Dict[str, Any]] = None,
                      hyperparameters: Optional[Dict[str, Any]] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      tags: Optional[List[str]] = None) -> str:
        """
        Create a new training session record.
        
        Args:
            model_id: Model identifier
            model_name: Model name
            session_name: Optional session name
            description: Optional session description
            priority: Session priority level
            created_by: User who created the session
            configuration: Training configuration
            resource_allocation: Resource allocation settings
            hyperparameters: Hyperparameter configuration
            metadata: Additional metadata
            tags: Session tags
            
        Returns:
            Session ID
            
        Raises:
            ValueError: If required parameters are invalid
            RuntimeError: If database operation fails
        """
        if not model_id or not model_name:
            raise ValueError("Model ID and name are required")
        
        session_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        if session_name is None:
            session_name = f"Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Check session limit per model
                cursor.execute("SELECT COUNT(*) FROM training_sessions WHERE model_id = ?", (model_id,))
                session_count = cursor.fetchone()[0]
                
                if session_count >= self._max_sessions_per_model:
                    raise ValueError(f"Maximum sessions per model ({self._max_sessions_per_model}) exceeded")
                
                # Insert new session
                cursor.execute("""
                    INSERT INTO training_sessions (
                        session_id, model_id, model_name, session_name, description,
                        status, priority, created_at, last_updated_at, created_by,
                        configuration_json, resource_allocation_json, hyperparameters_json,
                        metadata_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, model_id, model_name, session_name, description,
                    SessionStatus.CREATED.value, priority.value, current_time, current_time, created_by,
                    json.dumps(configuration) if configuration else None,
                    json.dumps(resource_allocation) if resource_allocation else None,
                    json.dumps(hyperparameters) if hyperparameters else None,
                    json.dumps(metadata) if metadata else None,
                    json.dumps(tags) if tags else None
                ))
                
                conn.commit()
                self._logger.info(f"Created training session {session_id} for model {model_id}")
                return session_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create session for model {model_id}: {e}")
                raise RuntimeError(f"Failed to create session: {e}")
            finally:
                conn.close()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a training session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_id, model_id, model_name, session_name, description,
                           status, priority, created_at, started_at, completed_at,
                           paused_at, resumed_at, last_updated_at, created_by,
                           total_epochs, current_epoch, current_step, total_steps,
                           estimated_duration_seconds, actual_duration_seconds,
                           best_metric, best_metric_name, last_checkpoint_path,
                           error_message, error_count, retry_count, max_retries,
                           configuration_json, resource_allocation_json,
                           hyperparameters_json, metadata_json, tags_json, notes
                    FROM training_sessions
                    WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Convert row to dictionary
                session_data = {
                    'session_id': row[0],
                    'model_id': row[1],
                    'model_name': row[2],
                    'session_name': row[3],
                    'description': row[4],
                    'status': row[5],
                    'priority': row[6],
                    'created_at': row[7],
                    'started_at': row[8],
                    'completed_at': row[9],
                    'paused_at': row[10],
                    'resumed_at': row[11],
                    'last_updated_at': row[12],
                    'created_by': row[13],
                    'total_epochs': row[14],
                    'current_epoch': row[15],
                    'current_step': row[16],
                    'total_steps': row[17],
                    'estimated_duration_seconds': row[18],
                    'actual_duration_seconds': row[19],
                    'best_metric': row[20],
                    'best_metric_name': row[21],
                    'last_checkpoint_path': row[22],
                    'error_message': row[23],
                    'error_count': row[24],
                    'retry_count': row[25],
                    'max_retries': row[26],
                    'configuration': json.loads(row[27]) if row[27] else None,
                    'resource_allocation': json.loads(row[28]) if row[28] else None,
                    'hyperparameters': json.loads(row[29]) if row[29] else None,
                    'metadata': json.loads(row[30]) if row[30] else None,
                    'tags': json.loads(row[31]) if row[31] else None,
                    'notes': row[32]
                }

                return session_data

            except Exception as e:
                self._logger.error(f"Failed to get session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def update_session(self, session_id: str, **kwargs) -> bool:
        """
        Update a training session record.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update

        Returns:
            True if updated successfully
        """
        if not kwargs:
            return True

        # Build update query dynamically
        update_fields = []
        update_values = []

        # Handle JSON fields
        json_fields = {
            'configuration': 'configuration_json',
            'resource_allocation': 'resource_allocation_json',
            'hyperparameters': 'hyperparameters_json',
            'metadata': 'metadata_json',
            'tags': 'tags_json'
        }

        for field, value in kwargs.items():
            if field in json_fields:
                update_fields.append(f"{json_fields[field]} = ?")
                update_values.append(json.dumps(value) if value is not None else None)
            elif field in ['session_name', 'description', 'status', 'priority', 'started_at',
                          'completed_at', 'paused_at', 'resumed_at', 'created_by', 'total_epochs',
                          'current_epoch', 'current_step', 'total_steps', 'estimated_duration_seconds',
                          'actual_duration_seconds', 'best_metric', 'best_metric_name',
                          'last_checkpoint_path', 'error_message', 'error_count', 'retry_count',
                          'max_retries', 'notes']:
                update_fields.append(f"{field} = ?")
                update_values.append(value)

        if not update_fields:
            return True

        # Always update last_updated_at
        update_fields.append("last_updated_at = ?")
        update_values.append(datetime.now(timezone.utc).isoformat())
        update_values.append(session_id)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = f"UPDATE training_sessions SET {', '.join(update_fields)} WHERE session_id = ?"
                cursor.execute(query, update_values)

                if cursor.rowcount == 0:
                    self._logger.warning(f"No session found with ID {session_id}")
                    return False

                conn.commit()
                self._logger.debug(f"Updated session {session_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a training session record.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete session (cascades to metrics and checkpoints)
                cursor.execute("DELETE FROM training_sessions WHERE session_id = ?", (session_id,))

                if cursor.rowcount == 0:
                    self._logger.warning(f"No session found with ID {session_id}")
                    return False

                conn.commit()
                self._logger.info(f"Deleted session {session_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def list_sessions(self, model_id: Optional[str] = None, status: Optional[str] = None,
                     created_by: Optional[str] = None, limit: int = 100,
                     offset: int = 0, order_by: str = "created_at",
                     order_desc: bool = True) -> List[Dict[str, Any]]:
        """
        List training sessions with filtering and pagination.

        Args:
            model_id: Filter by model ID
            status: Filter by status
            created_by: Filter by creator
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            order_by: Field to order by
            order_desc: Whether to order in descending order

        Returns:
            List of session dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT session_id, model_id, model_name, session_name, description,
                           status, priority, created_at, started_at, completed_at,
                           paused_at, resumed_at, last_updated_at, created_by,
                           total_epochs, current_epoch, current_step, total_steps,
                           estimated_duration_seconds, actual_duration_seconds,
                           best_metric, best_metric_name, last_checkpoint_path,
                           error_message, error_count, retry_count, max_retries,
                           configuration_json, resource_allocation_json,
                           hyperparameters_json, metadata_json, tags_json, notes
                    FROM training_sessions
                    WHERE 1=1
                """
                params = []

                if model_id:
                    query += " AND model_id = ?"
                    params.append(model_id)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                if created_by:
                    query += " AND created_by = ?"
                    params.append(created_by)

                # Add ordering
                valid_order_fields = ['created_at', 'last_updated_at', 'session_name', 'status', 'priority']
                if order_by not in valid_order_fields:
                    order_by = 'created_at'

                query += f" ORDER BY {order_by}"
                if order_desc:
                    query += " DESC"

                # Add pagination
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                sessions = []
                for row in rows:
                    session_data = {
                        'session_id': row[0],
                        'model_id': row[1],
                        'model_name': row[2],
                        'session_name': row[3],
                        'description': row[4],
                        'status': row[5],
                        'priority': row[6],
                        'created_at': row[7],
                        'started_at': row[8],
                        'completed_at': row[9],
                        'paused_at': row[10],
                        'resumed_at': row[11],
                        'last_updated_at': row[12],
                        'created_by': row[13],
                        'total_epochs': row[14],
                        'current_epoch': row[15],
                        'current_step': row[16],
                        'total_steps': row[17],
                        'estimated_duration_seconds': row[18],
                        'actual_duration_seconds': row[19],
                        'best_metric': row[20],
                        'best_metric_name': row[21],
                        'last_checkpoint_path': row[22],
                        'error_message': row[23],
                        'error_count': row[24],
                        'retry_count': row[25],
                        'max_retries': row[26],
                        'configuration': json.loads(row[27]) if row[27] else None,
                        'resource_allocation': json.loads(row[28]) if row[28] else None,
                        'hyperparameters': json.loads(row[29]) if row[29] else None,
                        'metadata': json.loads(row[30]) if row[30] else None,
                        'tags': json.loads(row[31]) if row[31] else None,
                        'notes': row[32]
                    }
                    sessions.append(session_data)

                return sessions

            except Exception as e:
                self._logger.error(f"Failed to list sessions: {e}")
                return []
            finally:
                conn.close()

    def get_session_count(self, model_id: Optional[str] = None, status: Optional[str] = None) -> int:
        """
        Get count of training sessions with optional filtering.

        Args:
            model_id: Filter by model ID
            status: Filter by status

        Returns:
            Number of sessions matching criteria
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = "SELECT COUNT(*) FROM training_sessions WHERE 1=1"
                params = []

                if model_id:
                    query += " AND model_id = ?"
                    params.append(model_id)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                cursor.execute(query, params)
                return cursor.fetchone()[0]

            except Exception as e:
                self._logger.error(f"Failed to get session count: {e}")
                return 0
            finally:
                conn.close()

    def add_session_metric(self, session_id: str, metric_name: str, metric_value: float,
                          metric_type: str = "training", epoch: Optional[int] = None,
                          step: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a metric record for a training session.

        Args:
            session_id: Session identifier
            metric_name: Name of the metric
            metric_value: Metric value
            metric_type: Type of metric (training, validation, test)
            epoch: Training epoch
            step: Training step
            metadata: Additional metadata

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO session_metrics (
                        metric_id, session_id, metric_name, metric_value, metric_type,
                        epoch, step, timestamp, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, session_id, metric_name, metric_value, metric_type,
                    epoch, step, current_time,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add metric for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def add_session_checkpoint(self, session_id: str, checkpoint_name: str, checkpoint_path: str,
                              epoch: int, step: int, metric_value: Optional[float] = None,
                              metric_name: Optional[str] = None, file_size_mb: Optional[float] = None,
                              is_best: bool = False, is_latest: bool = True,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a checkpoint record for a training session.

        Args:
            session_id: Session identifier
            checkpoint_name: Name of the checkpoint
            checkpoint_path: Path to checkpoint file
            epoch: Training epoch
            step: Training step
            metric_value: Associated metric value
            metric_name: Name of the metric
            file_size_mb: Checkpoint file size in MB
            is_best: Whether this is the best checkpoint
            is_latest: Whether this is the latest checkpoint
            metadata: Additional metadata

        Returns:
            Checkpoint ID
        """
        checkpoint_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # If this is the latest checkpoint, update previous ones
                if is_latest:
                    cursor.execute("""
                        UPDATE session_checkpoints
                        SET is_latest = FALSE
                        WHERE session_id = ? AND is_latest = TRUE
                    """, (session_id,))

                # If this is the best checkpoint, update previous ones
                if is_best:
                    cursor.execute("""
                        UPDATE session_checkpoints
                        SET is_best = FALSE
                        WHERE session_id = ? AND is_best = TRUE
                    """, (session_id,))

                cursor.execute("""
                    INSERT INTO session_checkpoints (
                        checkpoint_id, session_id, checkpoint_name, checkpoint_path,
                        epoch, step, metric_value, metric_name, file_size_mb,
                        is_best, is_latest, created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    checkpoint_id, session_id, checkpoint_name, checkpoint_path,
                    epoch, step, metric_value, metric_name, file_size_mb,
                    is_best, is_latest, current_time,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                return checkpoint_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add checkpoint for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_sessions(self) -> int:
        """
        Clean up old training sessions based on retention policy.

        Returns:
            Number of sessions cleaned up
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=self._session_retention_days)).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get sessions to delete
                cursor.execute("""
                    SELECT session_id FROM training_sessions
                    WHERE created_at < ? AND status IN ('completed', 'failed', 'cancelled')
                """, (cutoff_date,))

                session_ids = [row[0] for row in cursor.fetchall()]

                if not session_ids:
                    return 0

                # Delete old sessions
                placeholders = ','.join(['?'] * len(session_ids))
                cursor.execute(f"DELETE FROM training_sessions WHERE session_id IN ({placeholders})", session_ids)

                deleted_count = cursor.rowcount
                conn.commit()

                self._logger.info(f"Cleaned up {deleted_count} old training sessions")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old sessions: {e}")
                return 0
            finally:
                conn.close()

    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about training sessions.

        Returns:
            Dictionary with session statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get overall statistics
                cursor.execute("SELECT COUNT(*) FROM training_sessions")
                total_sessions = cursor.fetchone()[0]

                cursor.execute("SELECT status, COUNT(*) FROM training_sessions GROUP BY status")
                status_counts = dict(cursor.fetchall())

                cursor.execute("SELECT COUNT(DISTINCT model_id) FROM training_sessions")
                unique_models = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT AVG(actual_duration_seconds)
                    FROM training_sessions
                    WHERE actual_duration_seconds IS NOT NULL
                """)
                avg_duration = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM session_metrics")
                total_metrics = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM session_checkpoints")
                total_checkpoints = cursor.fetchone()[0]

                return {
                    'total_sessions': total_sessions,
                    'status_counts': status_counts,
                    'unique_models': unique_models,
                    'average_duration_seconds': avg_duration,
                    'total_metrics': total_metrics,
                    'total_checkpoints': total_checkpoints
                }

            except Exception as e:
                self._logger.error(f"Failed to get session statistics: {e}")
                return {}
            finally:
                conn.close()
