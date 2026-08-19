"""
Module: session_manager_lg
Description: Manages training session lifecycle including creation, execution, pause, resume, and termination
Phase: 4
Location: /src/modules/logic/training_orchestration_lg/session_manager_lg/
"""

# Standard library imports
import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sqlite3

# Local imports
from ..base_interfaces import (
    ISessionManager, TrainingSession, TrainingConfig, TrainingStatus, 
    TrainingMetrics, ExecutionResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class SessionStateManager:
    """Manages session state persistence and recovery."""
    
    def __init__(self, db_path: Path):
        """
        Initialize session state manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS training_sessions (
                        session_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        config_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        paused_at TEXT,
                        resumed_at TEXT,
                        current_epoch INTEGER DEFAULT 0,
                        current_step INTEGER DEFAULT 0,
                        total_steps INTEGER DEFAULT 0,
                        best_metric REAL,
                        last_checkpoint_path TEXT,
                        error_message TEXT,
                        resource_allocation_json TEXT,
                        metadata_json TEXT
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        epoch INTEGER NOT NULL,
                        step INTEGER NOT NULL,
                        loss REAL NOT NULL,
                        accuracy REAL,
                        validation_loss REAL,
                        validation_accuracy REAL,
                        learning_rate REAL NOT NULL,
                        batch_size INTEGER NOT NULL,
                        processing_time_ms REAL DEFAULT 0.0,
                        memory_usage_mb REAL DEFAULT 0.0,
                        gpu_utilization REAL DEFAULT 0.0,
                        timestamp TEXT NOT NULL,
                        custom_metrics_json TEXT,
                        FOREIGN KEY (session_id) REFERENCES training_sessions (session_id)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_status 
                    ON training_sessions (status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_created 
                    ON training_sessions (created_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_session 
                    ON session_metrics (session_id, epoch, step)
                """)
                
                conn.commit()
                self._logger.info("Session database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize session database: {e}")
                raise
            finally:
                conn.close()
    
    def save_session(self, session: TrainingSession) -> bool:
        """
        Save session to database.
        
        Args:
            session: Training session to save
            
        Returns:
            True if saved successfully
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO training_sessions (
                        session_id, model_id, config_json, status, created_at,
                        started_at, completed_at, paused_at, resumed_at,
                        current_epoch, current_step, total_steps, best_metric,
                        last_checkpoint_path, error_message, resource_allocation_json,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id,
                    session.model_id,
                    json.dumps(session.config.__dict__, default=str),
                    session.status.value,
                    session.created_at.isoformat(),
                    session.started_at.isoformat() if session.started_at else None,
                    session.completed_at.isoformat() if session.completed_at else None,
                    session.paused_at.isoformat() if session.paused_at else None,
                    session.resumed_at.isoformat() if session.resumed_at else None,
                    session.current_epoch,
                    session.current_step,
                    session.total_steps,
                    session.best_metric,
                    str(session.last_checkpoint_path) if session.last_checkpoint_path else None,
                    session.error_message,
                    json.dumps(session.resource_allocation),
                    json.dumps(session.metadata)
                ))
                
                conn.commit()
                self._logger.debug(f"Saved session {session.session_id}")
                return True
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to save session {session.session_id}: {e}")
                return False
            finally:
                conn.close()
    
    def load_session(self, session_id: str) -> Optional[TrainingSession]:
        """
        Load session from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            TrainingSession object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM training_sessions WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Load metrics history
                cursor.execute("""
                    SELECT * FROM session_metrics 
                    WHERE session_id = ? 
                    ORDER BY epoch, step
                """, (session_id,))
                
                metrics_rows = cursor.fetchall()
                metrics_history = []
                
                for metrics_row in metrics_rows:
                    metrics = TrainingMetrics(
                        epoch=metrics_row[2],
                        step=metrics_row[3],
                        loss=metrics_row[4],
                        accuracy=metrics_row[5],
                        validation_loss=metrics_row[6],
                        validation_accuracy=metrics_row[7],
                        learning_rate=metrics_row[8],
                        batch_size=metrics_row[9],
                        processing_time_ms=metrics_row[10],
                        memory_usage_mb=metrics_row[11],
                        gpu_utilization=metrics_row[12],
                        timestamp=datetime.fromisoformat(metrics_row[13]),
                        custom_metrics=json.loads(metrics_row[14]) if metrics_row[14] else {}
                    )
                    metrics_history.append(metrics)
                
                # Reconstruct session object
                config_data = json.loads(row[2])
                session = TrainingSession(
                    session_id=row[0],
                    model_id=row[1],
                    config=self._reconstruct_config(config_data),
                    status=TrainingStatus(row[3]),
                    created_at=datetime.fromisoformat(row[4]),
                    started_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    paused_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    resumed_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    current_epoch=row[9],
                    current_step=row[10],
                    total_steps=row[11],
                    best_metric=row[12],
                    last_checkpoint_path=Path(row[13]) if row[13] else None,
                    error_message=row[14],
                    metrics_history=metrics_history,
                    resource_allocation=json.loads(row[15]) if row[15] else {},
                    metadata=json.loads(row[16]) if row[16] else {}
                )
                
                return session
                
            except Exception as e:
                self._logger.error(f"Failed to load session {session_id}: {e}")
                return None
            finally:
                conn.close()
    
    def _reconstruct_config(self, config_data: Dict[str, Any]) -> TrainingConfig:
        """Reconstruct TrainingConfig from serialized data."""
        # This is a simplified reconstruction - in practice, you'd need
        # more sophisticated deserialization for complex objects
        return TrainingConfig(
            model_name=config_data.get('model_name', ''),
            dataset_path=Path(config_data.get('dataset_path', '')),
            output_dir=Path(config_data.get('output_dir', '')),
            hyperparameters=config_data.get('hyperparameters', {}),
            max_epochs=config_data.get('max_epochs', 100),
            early_stopping_patience=config_data.get('early_stopping_patience', 10),
            checkpoint_interval=config_data.get('checkpoint_interval', 1000),
            validation_split=config_data.get('validation_split', 0.2)
        )

    def save_metrics(self, session_id: str, metrics: TrainingMetrics) -> bool:
        """
        Save training metrics to database.

        Args:
            session_id: Session identifier
            metrics: Training metrics to save

        Returns:
            True if saved successfully
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO session_metrics (
                        session_id, epoch, step, loss, accuracy, validation_loss,
                        validation_accuracy, learning_rate, batch_size, processing_time_ms,
                        memory_usage_mb, gpu_utilization, timestamp, custom_metrics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    metrics.epoch,
                    metrics.step,
                    metrics.loss,
                    metrics.accuracy,
                    metrics.validation_loss,
                    metrics.validation_accuracy,
                    metrics.learning_rate,
                    metrics.batch_size,
                    metrics.processing_time_ms,
                    metrics.memory_usage_mb,
                    metrics.gpu_utilization,
                    metrics.timestamp.isoformat(),
                    json.dumps(metrics.custom_metrics)
                ))

                conn.commit()
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to save metrics for session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def list_sessions(self, status_filter: Optional[TrainingStatus] = None) -> List[str]:
        """
        List session IDs with optional status filter.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of session IDs
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                if status_filter:
                    cursor.execute("""
                        SELECT session_id FROM training_sessions
                        WHERE status = ?
                        ORDER BY created_at DESC
                    """, (status_filter.value,))
                else:
                    cursor.execute("""
                        SELECT session_id FROM training_sessions
                        ORDER BY created_at DESC
                    """)

                return [row[0] for row in cursor.fetchall()]

            except Exception as e:
                self._logger.error(f"Failed to list sessions: {e}")
                return []
            finally:
                conn.close()


class SessionManager(ISessionManager):
    """
    Manages training session lifecycle including creation, execution, pause, resume, and termination.

    This class provides comprehensive session management with state persistence,
    recovery capabilities, and thread-safe operations for long-running training sessions.
    """

    def __init__(self, db_path: Optional[Path] = None, checkpoint_dir: Optional[Path] = None):
        """
        Initialize session manager.

        Args:
            db_path: Path to session database (defaults to data/sessions.db)
            checkpoint_dir: Directory for checkpoints (defaults to checkpoints/)
        """
        self.db_path = db_path or Path("data/sessions.db")
        self.checkpoint_dir = checkpoint_dir or Path("checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._state_manager = SessionStateManager(self.db_path)
        self._active_sessions: Dict[str, TrainingSession] = {}
        self._session_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()

        # Load active sessions from database
        self._load_active_sessions()

    def _load_active_sessions(self) -> None:
        """Load active sessions from database on startup."""
        try:
            active_statuses = [TrainingStatus.RUNNING, TrainingStatus.PAUSED, TrainingStatus.RESUMING]
            for status in active_statuses:
                session_ids = self._state_manager.list_sessions(status)
                for session_id in session_ids:
                    session = self._state_manager.load_session(session_id)
                    if session:
                        self._active_sessions[session_id] = session
                        self._session_locks[session_id] = threading.Lock()

            self._logger.info(f"Loaded {len(self._active_sessions)} active sessions")

        except Exception as e:
            self._logger.error(f"Failed to load active sessions: {e}")

    async def create_session(self, model_id: str, config: TrainingConfig) -> str:
        """
        Create a new training session.

        Args:
            model_id: Unique model identifier
            config: Training configuration

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        try:
            # Create session object
            session = TrainingSession(
                session_id=session_id,
                model_id=model_id,
                config=config,
                status=TrainingStatus.INITIALIZING,
                created_at=datetime.now()
            )

            # Save to database
            if not self._state_manager.save_session(session):
                raise RuntimeError("Failed to save session to database")

            # Add to active sessions
            with self._global_lock:
                self._active_sessions[session_id] = session
                self._session_locks[session_id] = threading.Lock()

            # Update status to ready
            session.status = TrainingStatus.READY
            self._state_manager.save_session(session)

            self._logger.info(f"Created training session {session_id} for model {model_id}")
            return session_id

        except Exception as e:
            self._logger.error(f"Failed to create session: {e}")
            # Cleanup on failure
            with self._global_lock:
                self._active_sessions.pop(session_id, None)
                self._session_locks.pop(session_id, None)
            raise

    async def start_session(self, session_id: str) -> bool:
        """
        Start a training session.

        Args:
            session_id: Session identifier

        Returns:
            True if started successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                self._logger.error(f"Session {session_id} not found")
                return False

            if session.status not in [TrainingStatus.READY, TrainingStatus.PAUSED]:
                self._logger.error(f"Cannot start session {session_id} in status {session.status}")
                return False

            # Update session status
            with self._session_locks[session_id]:
                session.status = TrainingStatus.RUNNING
                session.started_at = datetime.now()
                if session.paused_at:
                    session.resumed_at = datetime.now()

                # Save updated session
                if not self._state_manager.save_session(session):
                    return False

                self._active_sessions[session_id] = session

            self._logger.info(f"Started training session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to start session {session_id}: {e}")
            return False

    async def pause_session(self, session_id: str) -> bool:
        """
        Pause a running training session.

        Args:
            session_id: Session identifier

        Returns:
            True if paused successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                self._logger.error(f"Session {session_id} not found")
                return False

            if session.status != TrainingStatus.RUNNING:
                self._logger.error(f"Cannot pause session {session_id} in status {session.status}")
                return False

            # Update session status
            with self._session_locks[session_id]:
                session.status = TrainingStatus.PAUSED
                session.paused_at = datetime.now()

                # Save updated session
                if not self._state_manager.save_session(session):
                    return False

                self._active_sessions[session_id] = session

            self._logger.info(f"Paused training session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to pause session {session_id}: {e}")
            return False

    async def resume_session(self, session_id: str) -> bool:
        """
        Resume a paused training session.

        Args:
            session_id: Session identifier

        Returns:
            True if resumed successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                self._logger.error(f"Session {session_id} not found")
                return False

            if session.status != TrainingStatus.PAUSED:
                self._logger.error(f"Cannot resume session {session_id} in status {session.status}")
                return False

            # Update session status
            with self._session_locks[session_id]:
                session.status = TrainingStatus.RESUMING
                session.resumed_at = datetime.now()

                # Save updated session
                if not self._state_manager.save_session(session):
                    return False

                # Change to running after brief resuming state
                await asyncio.sleep(0.1)
                session.status = TrainingStatus.RUNNING
                self._state_manager.save_session(session)

                self._active_sessions[session_id] = session

            self._logger.info(f"Resumed training session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to resume session {session_id}: {e}")
            return False

    async def stop_session(self, session_id: str, save_checkpoint: bool = True) -> bool:
        """
        Stop a training session.

        Args:
            session_id: Session identifier
            save_checkpoint: Whether to save final checkpoint

        Returns:
            True if stopped successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                self._logger.error(f"Session {session_id} not found")
                return False

            if session.status in [TrainingStatus.COMPLETED, TrainingStatus.FAILED, TrainingStatus.CANCELLED]:
                self._logger.warning(f"Session {session_id} already stopped with status {session.status}")
                return True

            # Update session status
            with self._session_locks[session_id]:
                session.status = TrainingStatus.COMPLETED
                session.completed_at = datetime.now()

                # Save final checkpoint if requested
                if save_checkpoint and session.current_epoch > 0:
                    checkpoint_path = self.checkpoint_dir / f"{session_id}_final.pt"
                    session.last_checkpoint_path = checkpoint_path

                # Save updated session
                if not self._state_manager.save_session(session):
                    return False

                self._active_sessions[session_id] = session

            self._logger.info(f"Stopped training session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to stop session {session_id}: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[TrainingSession]:
        """
        Get training session information.

        Args:
            session_id: Session identifier

        Returns:
            TrainingSession object or None if not found
        """
        try:
            # Check active sessions first
            if session_id in self._active_sessions:
                return self._active_sessions[session_id]

            # Load from database
            session = self._state_manager.load_session(session_id)
            if session:
                # Add to active sessions if it's an active status
                if session.status in [TrainingStatus.RUNNING, TrainingStatus.PAUSED, TrainingStatus.RESUMING]:
                    with self._global_lock:
                        self._active_sessions[session_id] = session
                        if session_id not in self._session_locks:
                            self._session_locks[session_id] = threading.Lock()

            return session

        except Exception as e:
            self._logger.error(f"Failed to get session {session_id}: {e}")
            return None

    async def list_sessions(self, status_filter: Optional[TrainingStatus] = None) -> List[TrainingSession]:
        """
        List training sessions with optional status filter.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of TrainingSession objects
        """
        try:
            session_ids = self._state_manager.list_sessions(status_filter)
            sessions = []

            for session_id in session_ids:
                session = await self.get_session(session_id)
                if session:
                    sessions.append(session)

            return sessions

        except Exception as e:
            self._logger.error(f"Failed to list sessions: {e}")
            return []

    async def update_session_metrics(self, session_id: str, metrics: TrainingMetrics) -> bool:
        """
        Update session with new training metrics.

        Args:
            session_id: Session identifier
            metrics: Training metrics to add

        Returns:
            True if updated successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                self._logger.error(f"Session {session_id} not found")
                return False

            # Update session with new metrics
            with self._session_locks.get(session_id, threading.Lock()):
                session.metrics_history.append(metrics)
                session.current_epoch = metrics.epoch
                session.current_step = metrics.step

                # Update best metric if applicable
                if session.config.metric_for_best_model == "eval_loss":
                    if session.best_metric is None or (metrics.validation_loss and metrics.validation_loss < session.best_metric):
                        session.best_metric = metrics.validation_loss
                elif session.config.metric_for_best_model == "eval_accuracy":
                    if session.best_metric is None or (metrics.validation_accuracy and metrics.validation_accuracy > session.best_metric):
                        session.best_metric = metrics.validation_accuracy

                # Save metrics to database
                if not self._state_manager.save_metrics(session_id, metrics):
                    return False

                # Save updated session
                if not self._state_manager.save_session(session):
                    return False

                self._active_sessions[session_id] = session

            return True

        except Exception as e:
            self._logger.error(f"Failed to update session metrics {session_id}: {e}")
            return False

    async def handle_session_error(self, session_id: str, error: Exception) -> bool:
        """
        Handle session error and update status.

        Args:
            session_id: Session identifier
            error: Exception that occurred

        Returns:
            True if handled successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Classify error
            classification = self._error_classifier.classify_error(error)

            # Update session with error information
            with self._session_locks.get(session_id, threading.Lock()):
                session.status = TrainingStatus.FAILED
                session.error_message = str(error)
                session.completed_at = datetime.now()

                # Save updated session
                self._state_manager.save_session(session)
                self._active_sessions[session_id] = session

            self._logger.error(f"Session {session_id} failed with error: {error}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to handle session error for {session_id}: {e}")
            return False

    async def cleanup_completed_sessions(self, max_age_days: int = 30) -> int:
        """
        Cleanup old completed sessions.

        Args:
            max_age_days: Maximum age in days for completed sessions

        Returns:
            Number of sessions cleaned up
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            completed_sessions = await self.list_sessions(TrainingStatus.COMPLETED)

            cleanup_count = 0
            for session in completed_sessions:
                if session.completed_at and session.completed_at < cutoff_date:
                    # Remove from active sessions
                    with self._global_lock:
                        self._active_sessions.pop(session.session_id, None)
                        self._session_locks.pop(session.session_id, None)

                    cleanup_count += 1

            self._logger.info(f"Cleaned up {cleanup_count} old completed sessions")
            return cleanup_count

        except Exception as e:
            self._logger.error(f"Failed to cleanup completed sessions: {e}")
            return 0
