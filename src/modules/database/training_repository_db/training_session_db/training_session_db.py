"""
Module: training_session_db
Description: Persists training session data including configuration, progress, and resource allocation
Phase: 4
Location: /src/modules/database/training_repository_db/training_session_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class TrainingStatus(Enum):
    """Training session status enumeration."""
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESUMING = "resuming"


class ResourceTier(Enum):
    """Resource tier enumeration for IDRAlloc."""
    GPU_MEMORY = "gpu_memory"
    CPU_MEMORY = "cpu_memory"
    NVME_SWAP = "nvme_swap"
    DISK_CACHE = "disk_cache"


@dataclass
class TrainingSession:
    """Training session data structure."""
    session_id: str
    model_name: str
    dataset_path: str
    output_directory: str
    status: TrainingStatus = TrainingStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_checkpoint_at: Optional[datetime] = None
    current_epoch: int = 0
    total_epochs: int = 100
    current_step: int = 0
    total_steps: Optional[int] = None
    learning_rate: float = 0.001
    batch_size: int = 32
    validation_split: float = 0.2
    early_stopping_patience: int = 10
    checkpoint_interval: int = 1000
    save_best_only: bool = True
    enable_mixed_precision: bool = False
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    warmup_steps: int = 0
    logging_steps: int = 100
    eval_steps: int = 500
    save_steps: int = 1000
    max_checkpoints: int = 5
    seed: int = 42
    gpu_memory_limit_mb: Optional[int] = None
    cpu_memory_limit_mb: Optional[int] = None
    nvme_swap_limit_mb: Optional[int] = None
    allocation_strategy: str = "auto"
    resource_profile_id: Optional[str] = None
    training_config: Optional[Dict[str, Any]] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    resource_allocation: Optional[Dict[str, Any]] = None
    progress_metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class TrainingSessionDB:
    """
    Database manager for training sessions with comprehensive session tracking.
    
    Provides thread-safe operations for storing and retrieving training session data
    with automatic schema management, resource allocation tracking, and performance optimization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the training session database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "training_sessions.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._session_retention_days = 365  # Keep sessions for 1 year
        self._max_sessions_per_model = 1000  # Maximum sessions per model
        self._batch_size = 100  # Batch size for bulk operations
        self._checkpoint_retention_count = 10  # Keep last 10 checkpoints per session
        
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
                        model_name TEXT NOT NULL,
                        dataset_path TEXT NOT NULL,
                        output_directory TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        last_checkpoint_at TEXT,
                        current_epoch INTEGER DEFAULT 0,
                        total_epochs INTEGER DEFAULT 100,
                        current_step INTEGER DEFAULT 0,
                        total_steps INTEGER,
                        learning_rate REAL DEFAULT 0.001,
                        batch_size INTEGER DEFAULT 32,
                        validation_split REAL DEFAULT 0.2,
                        early_stopping_patience INTEGER DEFAULT 10,
                        checkpoint_interval INTEGER DEFAULT 1000,
                        save_best_only BOOLEAN DEFAULT 1,
                        enable_mixed_precision BOOLEAN DEFAULT 0,
                        gradient_accumulation_steps INTEGER DEFAULT 1,
                        max_grad_norm REAL DEFAULT 1.0,
                        warmup_steps INTEGER DEFAULT 0,
                        logging_steps INTEGER DEFAULT 100,
                        eval_steps INTEGER DEFAULT 500,
                        save_steps INTEGER DEFAULT 1000,
                        max_checkpoints INTEGER DEFAULT 5,
                        seed INTEGER DEFAULT 42,
                        gpu_memory_limit_mb INTEGER,
                        cpu_memory_limit_mb INTEGER,
                        nvme_swap_limit_mb INTEGER,
                        allocation_strategy TEXT DEFAULT 'auto',
                        resource_profile_id TEXT,
                        training_config_json TEXT,
                        hyperparameters_json TEXT,
                        resource_allocation_json TEXT,
                        progress_metrics_json TEXT,
                        error_message TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_training_sessions_model_name
                    ON training_sessions(model_name)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_training_sessions_status
                    ON training_sessions(status)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_training_sessions_created_at
                    ON training_sessions(created_at)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_training_sessions_started_at
                    ON training_sessions(started_at)
                """)

                # Create session checkpoints table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        checkpoint_path TEXT NOT NULL,
                        epoch INTEGER NOT NULL,
                        step INTEGER NOT NULL,
                        loss_value REAL,
                        validation_loss REAL,
                        best_metric_value REAL,
                        is_best BOOLEAN DEFAULT 0,
                        file_size_mb REAL,
                        created_at TEXT NOT NULL,
                        metadata_json TEXT,
                        FOREIGN KEY (session_id) REFERENCES training_sessions(session_id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_checkpoints_session_id
                    ON session_checkpoints(session_id)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_checkpoints_epoch
                    ON session_checkpoints(session_id, epoch)
                """)

                # Create resource usage tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_resource_usage (
                        usage_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        gpu_memory_used_mb REAL,
                        cpu_memory_used_mb REAL,
                        nvme_swap_used_mb REAL,
                        gpu_utilization_percent REAL,
                        cpu_utilization_percent REAL,
                        temperature_celsius REAL,
                        power_consumption_watts REAL,
                        allocation_tier TEXT,
                        swap_events_count INTEGER DEFAULT 0,
                        reallocation_events_count INTEGER DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES training_sessions(session_id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_resource_usage_session_time
                    ON session_resource_usage(session_id, timestamp)
                """)

                conn.commit()
                self._logger.info("Training session database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize training session database: {e}")
                raise
            finally:
                conn.close()

    def create_session(self, model_name: str, dataset_path: str, output_directory: str,
                      total_epochs: int = 100, learning_rate: float = 0.001,
                      batch_size: int = 32, validation_split: float = 0.2,
                      early_stopping_patience: int = 10, checkpoint_interval: int = 1000,
                      save_best_only: bool = True, enable_mixed_precision: bool = False,
                      gradient_accumulation_steps: int = 1, max_grad_norm: float = 1.0,
                      warmup_steps: int = 0, logging_steps: int = 100,
                      eval_steps: int = 500, save_steps: int = 1000,
                      max_checkpoints: int = 5, seed: int = 42,
                      gpu_memory_limit_mb: Optional[int] = None,
                      cpu_memory_limit_mb: Optional[int] = None,
                      nvme_swap_limit_mb: Optional[int] = None,
                      allocation_strategy: str = "auto",
                      resource_profile_id: Optional[str] = None,
                      training_config: Optional[Dict[str, Any]] = None,
                      hyperparameters: Optional[Dict[str, Any]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new training session.

        Args:
            model_name: Name of the model to train
            dataset_path: Path to the training dataset
            output_directory: Directory for training outputs
            total_epochs: Total number of training epochs
            learning_rate: Learning rate for training
            batch_size: Training batch size
            validation_split: Validation data split ratio
            early_stopping_patience: Early stopping patience
            checkpoint_interval: Steps between checkpoints
            save_best_only: Whether to save only best checkpoints
            enable_mixed_precision: Enable mixed precision training
            gradient_accumulation_steps: Gradient accumulation steps
            max_grad_norm: Maximum gradient norm for clipping
            warmup_steps: Learning rate warmup steps
            logging_steps: Steps between logging
            eval_steps: Steps between evaluations
            save_steps: Steps between saves
            max_checkpoints: Maximum checkpoints to keep
            seed: Random seed
            gpu_memory_limit_mb: GPU memory limit in MB
            cpu_memory_limit_mb: CPU memory limit in MB
            nvme_swap_limit_mb: NVMe swap limit in MB
            allocation_strategy: Memory allocation strategy
            resource_profile_id: Resource profile identifier
            training_config: Training configuration
            hyperparameters: Model hyperparameters
            metadata: Additional metadata

        Returns:
            Session ID

        Raises:
            ValueError: If session limit exceeded
        """
        session_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check session limit per model
                cursor.execute("SELECT COUNT(*) FROM training_sessions WHERE model_name = ?", (model_name,))
                session_count = cursor.fetchone()[0]

                if session_count >= self._max_sessions_per_model:
                    raise ValueError(f"Maximum sessions per model ({self._max_sessions_per_model}) exceeded")

                cursor.execute("""
                    INSERT INTO training_sessions (
                        session_id, model_name, dataset_path, output_directory, status,
                        created_at, current_epoch, total_epochs, current_step,
                        learning_rate, batch_size, validation_split, early_stopping_patience,
                        checkpoint_interval, save_best_only, enable_mixed_precision,
                        gradient_accumulation_steps, max_grad_norm, warmup_steps,
                        logging_steps, eval_steps, save_steps, max_checkpoints, seed,
                        gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                        allocation_strategy, resource_profile_id, training_config_json,
                        hyperparameters_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, model_name, dataset_path, output_directory, TrainingStatus.PENDING.value,
                    current_time, 0, total_epochs, 0,
                    learning_rate, batch_size, validation_split, early_stopping_patience,
                    checkpoint_interval, save_best_only, enable_mixed_precision,
                    gradient_accumulation_steps, max_grad_norm, warmup_steps,
                    logging_steps, eval_steps, save_steps, max_checkpoints, seed,
                    gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                    allocation_strategy, resource_profile_id,
                    json.dumps(training_config) if training_config else None,
                    json.dumps(hyperparameters) if hyperparameters else None,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Created training session {session_id} for model {model_name}")
                return session_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create training session: {e}")
                raise
            finally:
                conn.close()

    def get_session(self, session_id: str) -> Optional[TrainingSession]:
        """
        Retrieve a training session by ID.

        Args:
            session_id: Session identifier

        Returns:
            TrainingSession object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_id, model_name, dataset_path, output_directory, status,
                           created_at, started_at, completed_at, last_checkpoint_at,
                           current_epoch, total_epochs, current_step, total_steps,
                           learning_rate, batch_size, validation_split, early_stopping_patience,
                           checkpoint_interval, save_best_only, enable_mixed_precision,
                           gradient_accumulation_steps, max_grad_norm, warmup_steps,
                           logging_steps, eval_steps, save_steps, max_checkpoints, seed,
                           gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                           allocation_strategy, resource_profile_id, training_config_json,
                           hyperparameters_json, resource_allocation_json, progress_metrics_json,
                           error_message, metadata_json
                    FROM training_sessions WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return TrainingSession(
                    session_id=row[0],
                    model_name=row[1],
                    dataset_path=row[2],
                    output_directory=row[3],
                    status=TrainingStatus(row[4]),
                    created_at=datetime.fromisoformat(row[5]),
                    started_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    last_checkpoint_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    current_epoch=row[9],
                    total_epochs=row[10],
                    current_step=row[11],
                    total_steps=row[12],
                    learning_rate=row[13],
                    batch_size=row[14],
                    validation_split=row[15],
                    early_stopping_patience=row[16],
                    checkpoint_interval=row[17],
                    save_best_only=bool(row[18]),
                    enable_mixed_precision=bool(row[19]),
                    gradient_accumulation_steps=row[20],
                    max_grad_norm=row[21],
                    warmup_steps=row[22],
                    logging_steps=row[23],
                    eval_steps=row[24],
                    save_steps=row[25],
                    max_checkpoints=row[26],
                    seed=row[27],
                    gpu_memory_limit_mb=row[28],
                    cpu_memory_limit_mb=row[29],
                    nvme_swap_limit_mb=row[30],
                    allocation_strategy=row[31],
                    resource_profile_id=row[32],
                    training_config=json.loads(row[33]) if row[33] else None,
                    hyperparameters=json.loads(row[34]) if row[34] else None,
                    resource_allocation=json.loads(row[35]) if row[35] else None,
                    progress_metrics=json.loads(row[36]) if row[36] else None,
                    error_message=row[37],
                    metadata=json.loads(row[38]) if row[38] else None
                )

            except Exception as e:
                self._logger.error(f"Failed to get training session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def update_session_status(self, session_id: str, status: TrainingStatus,
                             error_message: Optional[str] = None) -> bool:
        """
        Update session status.

        Args:
            session_id: Session identifier
            status: New session status
            error_message: Error message if status is FAILED

        Returns:
            True if updated successfully
        """
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update status and timestamps
                updates = ["status = ?"]
                params = [status.value]

                if status == TrainingStatus.RUNNING and not self._get_started_at(cursor, session_id):
                    updates.append("started_at = ?")
                    params.append(current_time)

                if status in [TrainingStatus.COMPLETED, TrainingStatus.FAILED, TrainingStatus.CANCELLED]:
                    updates.append("completed_at = ?")
                    params.append(current_time)

                if error_message:
                    updates.append("error_message = ?")
                    params.append(error_message)

                params.append(session_id)

                query = f"UPDATE training_sessions SET {', '.join(updates)} WHERE session_id = ?"
                cursor.execute(query, params)

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update session status {session_id}: {e}")
                return False
            finally:
                conn.close()

    def _get_started_at(self, cursor: sqlite3.Cursor, session_id: str) -> Optional[str]:
        """Helper method to get started_at timestamp."""
        cursor.execute("SELECT started_at FROM training_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    def update_session_progress(self, session_id: str, current_epoch: int,
                               current_step: int, total_steps: Optional[int] = None,
                               progress_metrics: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update session training progress.

        Args:
            session_id: Session identifier
            current_epoch: Current training epoch
            current_step: Current training step
            total_steps: Total training steps
            progress_metrics: Progress metrics dictionary

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                updates = ["current_epoch = ?", "current_step = ?"]
                params = [current_epoch, current_step]

                if total_steps is not None:
                    updates.append("total_steps = ?")
                    params.append(total_steps)

                if progress_metrics:
                    updates.append("progress_metrics_json = ?")
                    params.append(json.dumps(progress_metrics))

                params.append(session_id)

                query = f"UPDATE training_sessions SET {', '.join(updates)} WHERE session_id = ?"
                cursor.execute(query, params)

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update session progress {session_id}: {e}")
                return False
            finally:
                conn.close()

    def record_checkpoint(self, session_id: str, checkpoint_path: str,
                         epoch: int, step: int, loss_value: Optional[float] = None,
                         validation_loss: Optional[float] = None,
                         best_metric_value: Optional[float] = None,
                         is_best: bool = False, file_size_mb: Optional[float] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a training checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_path: Path to checkpoint file
            epoch: Training epoch
            step: Training step
            loss_value: Training loss value
            validation_loss: Validation loss value
            best_metric_value: Best metric value
            is_best: Whether this is the best checkpoint
            file_size_mb: Checkpoint file size in MB
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

                cursor.execute("""
                    INSERT INTO session_checkpoints (
                        checkpoint_id, session_id, checkpoint_path, epoch, step,
                        loss_value, validation_loss, best_metric_value, is_best,
                        file_size_mb, created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    checkpoint_id, session_id, checkpoint_path, epoch, step,
                    loss_value, validation_loss, best_metric_value, is_best,
                    file_size_mb, current_time,
                    json.dumps(metadata) if metadata else None
                ))

                # Update session last checkpoint time
                cursor.execute("""
                    UPDATE training_sessions SET last_checkpoint_at = ? WHERE session_id = ?
                """, (current_time, session_id))

                # Clean up old checkpoints if needed
                self._cleanup_old_checkpoints(cursor, session_id)

                conn.commit()
                self._logger.info(f"Recorded checkpoint {checkpoint_id} for session {session_id}")
                return checkpoint_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record checkpoint: {e}")
                raise
            finally:
                conn.close()

    def _cleanup_old_checkpoints(self, cursor: sqlite3.Cursor, session_id: str) -> None:
        """Clean up old checkpoints beyond retention limit."""
        cursor.execute("""
            SELECT checkpoint_id FROM session_checkpoints
            WHERE session_id = ? AND is_best = 0
            ORDER BY created_at DESC
            LIMIT -1 OFFSET ?
        """, (session_id, self._checkpoint_retention_count))

        old_checkpoints = cursor.fetchall()
        if old_checkpoints:
            checkpoint_ids = [row[0] for row in old_checkpoints]
            placeholders = ','.join(['?'] * len(checkpoint_ids))
            cursor.execute(f"""
                DELETE FROM session_checkpoints
                WHERE checkpoint_id IN ({placeholders})
            """, checkpoint_ids)

    def record_resource_usage(self, session_id: str,
                             gpu_memory_used_mb: Optional[float] = None,
                             cpu_memory_used_mb: Optional[float] = None,
                             nvme_swap_used_mb: Optional[float] = None,
                             gpu_utilization_percent: Optional[float] = None,
                             cpu_utilization_percent: Optional[float] = None,
                             temperature_celsius: Optional[float] = None,
                             power_consumption_watts: Optional[float] = None,
                             allocation_tier: Optional[ResourceTier] = None,
                             swap_events_count: int = 0,
                             reallocation_events_count: int = 0) -> str:
        """
        Record resource usage for a training session.

        Args:
            session_id: Session identifier
            gpu_memory_used_mb: GPU memory usage in MB
            cpu_memory_used_mb: CPU memory usage in MB
            nvme_swap_used_mb: NVMe swap usage in MB
            gpu_utilization_percent: GPU utilization percentage
            cpu_utilization_percent: CPU utilization percentage
            temperature_celsius: System temperature in Celsius
            power_consumption_watts: Power consumption in watts
            allocation_tier: Current allocation tier
            swap_events_count: Number of swap events
            reallocation_events_count: Number of reallocation events

        Returns:
            Usage record ID
        """
        usage_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO session_resource_usage (
                        usage_id, session_id, timestamp, gpu_memory_used_mb,
                        cpu_memory_used_mb, nvme_swap_used_mb, gpu_utilization_percent,
                        cpu_utilization_percent, temperature_celsius, power_consumption_watts,
                        allocation_tier, swap_events_count, reallocation_events_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    usage_id, session_id, current_time, gpu_memory_used_mb,
                    cpu_memory_used_mb, nvme_swap_used_mb, gpu_utilization_percent,
                    cpu_utilization_percent, temperature_celsius, power_consumption_watts,
                    allocation_tier.value if allocation_tier else None,
                    swap_events_count, reallocation_events_count
                ))

                conn.commit()
                return usage_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record resource usage: {e}")
                raise
            finally:
                conn.close()

    def list_sessions(self, model_name: Optional[str] = None,
                     status: Optional[TrainingStatus] = None,
                     limit: int = 100, offset: int = 0) -> List[TrainingSession]:
        """
        List training sessions with optional filtering.

        Args:
            model_name: Filter by model name
            status: Filter by session status
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip

        Returns:
            List of TrainingSession objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT session_id, model_name, dataset_path, output_directory, status,
                           created_at, started_at, completed_at, last_checkpoint_at,
                           current_epoch, total_epochs, current_step, total_steps,
                           learning_rate, batch_size, validation_split, early_stopping_patience,
                           checkpoint_interval, save_best_only, enable_mixed_precision,
                           gradient_accumulation_steps, max_grad_norm, warmup_steps,
                           logging_steps, eval_steps, save_steps, max_checkpoints, seed,
                           gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                           allocation_strategy, resource_profile_id, training_config_json,
                           hyperparameters_json, resource_allocation_json, progress_metrics_json,
                           error_message, metadata_json
                    FROM training_sessions
                """

                conditions = []
                params = []

                if model_name:
                    conditions.append("model_name = ?")
                    params.append(model_name)

                if status:
                    conditions.append("status = ?")
                    params.append(status.value)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                sessions = []
                for row in rows:
                    sessions.append(TrainingSession(
                        session_id=row[0],
                        model_name=row[1],
                        dataset_path=row[2],
                        output_directory=row[3],
                        status=TrainingStatus(row[4]),
                        created_at=datetime.fromisoformat(row[5]),
                        started_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                        last_checkpoint_at=datetime.fromisoformat(row[8]) if row[8] else None,
                        current_epoch=row[9],
                        total_epochs=row[10],
                        current_step=row[11],
                        total_steps=row[12],
                        learning_rate=row[13],
                        batch_size=row[14],
                        validation_split=row[15],
                        early_stopping_patience=row[16],
                        checkpoint_interval=row[17],
                        save_best_only=bool(row[18]),
                        enable_mixed_precision=bool(row[19]),
                        gradient_accumulation_steps=row[20],
                        max_grad_norm=row[21],
                        warmup_steps=row[22],
                        logging_steps=row[23],
                        eval_steps=row[24],
                        save_steps=row[25],
                        max_checkpoints=row[26],
                        seed=row[27],
                        gpu_memory_limit_mb=row[28],
                        cpu_memory_limit_mb=row[29],
                        nvme_swap_limit_mb=row[30],
                        allocation_strategy=row[31],
                        resource_profile_id=row[32],
                        training_config=json.loads(row[33]) if row[33] else None,
                        hyperparameters=json.loads(row[34]) if row[34] else None,
                        resource_allocation=json.loads(row[35]) if row[35] else None,
                        progress_metrics=json.loads(row[36]) if row[36] else None,
                        error_message=row[37],
                        metadata=json.loads(row[38]) if row[38] else None
                    ))

                return sessions

            except Exception as e:
                self._logger.error(f"Failed to list training sessions: {e}")
                return []
            finally:
                conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a training session and all associated data.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete session (checkpoints and resource usage will be deleted by CASCADE)
                cursor.execute("DELETE FROM training_sessions WHERE session_id = ?", (session_id,))

                conn.commit()
                self._logger.info(f"Deleted training session {session_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete training session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def cleanup_old_sessions(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old sessions based on retention policy.

        Args:
            retention_days: Number of days to retain sessions

        Returns:
            Number of sessions deleted
        """
        if retention_days is None:
            retention_days = self._session_retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old sessions
                cursor.execute("""
                    DELETE FROM training_sessions
                    WHERE created_at < ? AND status IN ('completed', 'failed', 'cancelled')
                """, (cutoff_str,))

                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    self._logger.info(f"Cleaned up {deleted_count} old training sessions")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old sessions: {e}")
                return 0
            finally:
                conn.close()
