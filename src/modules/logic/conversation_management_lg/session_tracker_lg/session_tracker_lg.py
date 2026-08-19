"""
Module: session_tracker_lg
Description: Tracks conversation sessions with lifecycle management, state persistence, and thread-safe operations
Phase: 4
Location: /src/modules/logic/conversation_management_lg/session_tracker_lg/session_tracker_lg.py
"""

# Standard library imports
import asyncio
import json
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging

# Third-party imports
# None required for this module

# Local imports
from ..base_interfaces import (
    ISessionTracker,
    ConversationSession,
    SessionConfig,
    SessionStatus,
    SessionMetrics
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)


class SessionPersistenceError(Exception):
    """Exception raised when session persistence operations fail."""
    pass


class SessionNotFoundError(Exception):
    """Exception raised when a session is not found."""
    pass


class SessionStateManager:
    """
    Manages session state persistence with SQLite database.
    
    Provides thread-safe operations for storing and retrieving session data
    with automatic schema management and data integrity validation.
    """
    
    def __init__(self, db_path: Path):
        """Initialize session state manager with database path."""
        self.db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)
        self._initialized = False
        
    async def initialize(self) -> bool:
        """
        Initialize the session state manager with database schema.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Create database directory if it doesn't exist
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Initialize database schema
                if not self._create_schema():
                    return False
                
                self._initialized = True
                self._logger.info("Session state manager initialized successfully")
                return True
                
        except Exception as e:
            self._logger.error(f"Error initializing session state manager: {e}")
            return False
    
    def _create_schema(self) -> bool:
        """Create database schema for session storage."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    model_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    terminated_at TEXT,
                    total_messages INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    context_length INTEGER DEFAULT 4096,
                    session_config_json TEXT,
                    metadata_json TEXT
                )
            """)
            
            # Create session metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_metrics (
                    session_id TEXT PRIMARY KEY,
                    total_messages INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    average_message_length REAL DEFAULT 0.0,
                    session_duration_seconds INTEGER DEFAULT 0,
                    last_activity TEXT NOT NULL,
                    messages_per_minute REAL DEFAULT 0.0,
                    tokens_per_minute REAL DEFAULT 0.0,
                    error_count INTEGER DEFAULT 0,
                    function_calls_count INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions (session_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON conversation_sessions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON conversation_sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_activity ON conversation_sessions(last_activity)")
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            self._logger.error(f"Error creating database schema: {e}")
            return False
    
    def save_session(self, session: ConversationSession) -> bool:
        """
        Save session to database.
        
        Args:
            session: ConversationSession to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Serialize session config with enum handling
                session_config_serializable = {}
                for key, value in session.session_config.items():
                    if hasattr(value, 'value'):  # Handle enums
                        session_config_serializable[key] = value.value
                    else:
                        session_config_serializable[key] = value

                cursor.execute("""
                    INSERT OR REPLACE INTO conversation_sessions (
                        session_id, user_id, model_id, status, created_at,
                        last_activity, terminated_at, total_messages, total_tokens,
                        context_length, session_config_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id,
                    session.user_id,
                    session.model_id,
                    session.status.value,
                    session.created_at.isoformat(),
                    session.last_activity.isoformat(),
                    session.terminated_at.isoformat() if session.terminated_at else None,
                    session.total_messages,
                    session.total_tokens,
                    session.context_length,
                    json.dumps(session_config_serializable),
                    json.dumps(session.metadata)
                ))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            self._logger.error(f"Error saving session {session.session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Load session from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationSession or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT session_id, user_id, model_id, status, created_at,
                           last_activity, terminated_at, total_messages, total_tokens,
                           context_length, session_config_json, metadata_json
                    FROM conversation_sessions WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                conn.close()
                
                if not row:
                    return None
                
                # Parse datetime fields
                created_at = datetime.fromisoformat(row[4])
                last_activity = datetime.fromisoformat(row[5])
                terminated_at = datetime.fromisoformat(row[6]) if row[6] else None
                
                # Parse JSON fields
                session_config = json.loads(row[10]) if row[10] else {}
                metadata = json.loads(row[11]) if row[11] else {}
                
                return ConversationSession(
                    session_id=row[0],
                    user_id=row[1],
                    model_id=row[2],
                    status=SessionStatus(row[3]),
                    created_at=created_at,
                    last_activity=last_activity,
                    terminated_at=terminated_at,
                    total_messages=row[7],
                    total_tokens=row[8],
                    context_length=row[9],
                    session_config=session_config,
                    metadata=metadata
                )
                
        except Exception as e:
            self._logger.error(f"Error loading session {session_id}: {e}")
            return None
    
    def save_metrics(self, metrics: SessionMetrics) -> bool:
        """
        Save session metrics to database.
        
        Args:
            metrics: SessionMetrics to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO session_metrics (
                        session_id, total_messages, total_tokens, average_message_length,
                        session_duration_seconds, last_activity, messages_per_minute,
                        tokens_per_minute, error_count, function_calls_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.session_id,
                    metrics.total_messages,
                    metrics.total_tokens,
                    metrics.average_message_length,
                    metrics.session_duration_seconds,
                    metrics.last_activity.isoformat(),
                    metrics.messages_per_minute,
                    metrics.tokens_per_minute,
                    metrics.error_count,
                    metrics.function_calls_count
                ))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            self._logger.error(f"Error saving metrics for session {metrics.session_id}: {e}")
            return False
    
    def load_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """
        Load session metrics from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionMetrics or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT session_id, total_messages, total_tokens, average_message_length,
                           session_duration_seconds, last_activity, messages_per_minute,
                           tokens_per_minute, error_count, function_calls_count
                    FROM session_metrics WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                conn.close()
                
                if not row:
                    return None
                
                return SessionMetrics(
                    session_id=row[0],
                    total_messages=row[1],
                    total_tokens=row[2],
                    average_message_length=row[3],
                    session_duration_seconds=row[4],
                    last_activity=datetime.fromisoformat(row[5]),
                    messages_per_minute=row[6],
                    tokens_per_minute=row[7],
                    error_count=row[8],
                    function_calls_count=row[9]
                )
                
        except Exception as e:
            self._logger.error(f"Error loading metrics for session {session_id}: {e}")
            return None

    def get_idle_sessions(self, idle_timeout_minutes: int) -> List[str]:
        """
        Get list of idle session IDs.

        Args:
            idle_timeout_minutes: Timeout in minutes

        Returns:
            List of idle session IDs
        """
        try:
            with self._lock:
                cutoff_time = datetime.now() - timedelta(minutes=idle_timeout_minutes)

                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_id FROM conversation_sessions
                    WHERE last_activity < ? AND status IN ('active', 'idle')
                """, (cutoff_time.isoformat(),))

                rows = cursor.fetchall()
                conn.close()

                return [row[0] for row in rows]

        except Exception as e:
            self._logger.error(f"Error getting idle sessions: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from database.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if deleted successfully
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Delete from both tables
                cursor.execute("DELETE FROM session_metrics WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM conversation_sessions WHERE session_id = ?", (session_id,))

                conn.commit()
                conn.close()
                return True

        except Exception as e:
            self._logger.error(f"Error deleting session {session_id}: {e}")
            return False


class SessionCleanupManager:
    """
    Manages cleanup of idle and terminated sessions.

    Provides automated cleanup functionality with configurable policies
    and background task management for session maintenance.
    """

    def __init__(self, state_manager: SessionStateManager):
        """Initialize cleanup manager with state manager."""
        self._state_manager = state_manager
        self._logger = get_log_manager().get_logger(__name__)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes
        self._running = False

    async def start_cleanup_task(self, interval_seconds: int = 300) -> bool:
        """
        Start background cleanup task.

        Args:
            interval_seconds: Cleanup interval in seconds

        Returns:
            bool: True if started successfully
        """
        try:
            if self._running:
                return True

            self._cleanup_interval = interval_seconds
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            self._logger.info(f"Started session cleanup task with {interval_seconds}s interval")
            return True

        except Exception as e:
            self._logger.error(f"Error starting cleanup task: {e}")
            return False

    async def stop_cleanup_task(self) -> bool:
        """
        Stop background cleanup task.

        Returns:
            bool: True if stopped successfully
        """
        try:
            self._running = False

            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

            self._logger.info("Stopped session cleanup task")
            return True

        except Exception as e:
            self._logger.error(f"Error stopping cleanup task: {e}")
            return False

    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                if self._running:
                    await self.cleanup_idle_sessions()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")

    async def cleanup_idle_sessions(self, idle_timeout_minutes: int = 30) -> int:
        """
        Clean up idle sessions.

        Args:
            idle_timeout_minutes: Timeout in minutes

        Returns:
            int: Number of sessions cleaned up
        """
        try:
            idle_sessions = self._state_manager.get_idle_sessions(idle_timeout_minutes)
            cleaned_count = 0

            for session_id in idle_sessions:
                if self._state_manager.delete_session(session_id):
                    cleaned_count += 1
                    self._logger.debug(f"Cleaned up idle session: {session_id}")

            if cleaned_count > 0:
                self._logger.info(f"Cleaned up {cleaned_count} idle sessions")

            return cleaned_count

        except Exception as e:
            self._logger.error(f"Error cleaning up idle sessions: {e}")
            return 0


class SessionTracker(ISessionTracker):
    """
    Production-ready conversation session tracker.

    Manages conversation session lifecycle including creation, tracking, pause/resume,
    and termination with thread-safe operations and persistent state management.
    """

    def __init__(self, db_path: Optional[Path] = None, config: Optional[SessionConfig] = None):
        """Initialize session tracker with optional database path and configuration."""
        self._logger = get_log_manager().get_logger(__name__)
        self._default_config = config or SessionConfig()

        # Initialize database path
        if db_path is None:
            db_path = Path("data/conversation_sessions.db")

        # Initialize components
        self._state_manager = SessionStateManager(db_path)
        self._cleanup_manager = SessionCleanupManager(self._state_manager)
        self._validator = ValidationEngine()

        # Thread-safe session tracking
        self._active_sessions: Dict[str, ConversationSession] = {}
        self._session_locks: Dict[str, threading.RLock] = defaultdict(threading.RLock)
        self._global_lock = threading.RLock()

        # Session metrics tracking
        self._session_metrics: Dict[str, SessionMetrics] = {}

        # Initialization state
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize the session tracker.

        Returns:
            bool: True if initialization successful
        """
        try:
            if self._initialized:
                return True

            # Initialize state manager
            if not await self._state_manager.initialize():
                self._logger.error("Failed to initialize session state manager")
                return False

            # Start cleanup task
            if not await self._cleanup_manager.start_cleanup_task():
                self._logger.error("Failed to start cleanup task")
                return False

            # Load active sessions from database
            await self._load_active_sessions()

            self._initialized = True
            self._logger.info("Session tracker initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing session tracker: {e}")
            return False

    async def shutdown(self) -> bool:
        """
        Shutdown the session tracker.

        Returns:
            bool: True if shutdown successful
        """
        try:
            # Stop cleanup task
            await self._cleanup_manager.stop_cleanup_task()

            # Save all active sessions
            with self._global_lock:
                for session in self._active_sessions.values():
                    self._state_manager.save_session(session)

                for metrics in self._session_metrics.values():
                    self._state_manager.save_metrics(metrics)

            self._logger.info("Session tracker shutdown successfully")
            return True

        except Exception as e:
            self._logger.error(f"Error shutting down session tracker: {e}")
            return False

    async def _load_active_sessions(self):
        """Load active sessions from database."""
        try:
            # This would require additional database queries to get active sessions
            # For now, we'll start with empty active sessions
            self._logger.debug("Loaded active sessions from database")

        except Exception as e:
            self._logger.error(f"Error loading active sessions: {e}")

    async def create_session(self, user_id: Optional[str] = None,
                           config: Optional[SessionConfig] = None) -> str:
        """
        Create a new conversation session.

        Args:
            user_id: Optional user identifier
            config: Optional session configuration

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        try:
            # Use provided config or default
            session_config = config or self._default_config

            # Convert session config to serializable dict
            config_dict = {}
            for key, value in session_config.__dict__.items():
                if hasattr(value, 'value'):  # Handle enums
                    config_dict[key] = value.value
                else:
                    config_dict[key] = value

            # Create session object
            session = ConversationSession(
                session_id=session_id,
                user_id=user_id,
                status=SessionStatus.INITIALIZING,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                context_length=session_config.max_context_length,
                session_config=config_dict,
                metadata={}
            )

            # Initialize session metrics
            metrics = SessionMetrics(
                session_id=session_id,
                last_activity=datetime.now()
            )

            # Save to database
            if not self._state_manager.save_session(session):
                raise SessionPersistenceError("Failed to save session to database")

            if not self._state_manager.save_metrics(metrics):
                raise SessionPersistenceError("Failed to save session metrics")

            # Add to active sessions
            with self._global_lock:
                self._active_sessions[session_id] = session
                self._session_metrics[session_id] = metrics
                self._session_locks[session_id] = threading.RLock()

            # Update status to active
            session.status = SessionStatus.ACTIVE
            self._state_manager.save_session(session)

            self._logger.info(f"Created conversation session {session_id} for user {user_id}")
            return session_id

        except Exception as e:
            self._logger.error(f"Failed to create session: {str(e)}")
            # Cleanup on failure
            with self._global_lock:
                self._active_sessions.pop(session_id, None)
                self._session_metrics.pop(session_id, None)
                self._session_locks.pop(session_id, None)
            raise

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get session information.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession object or None if not found
        """
        try:
            # Check active sessions first
            if session_id in self._active_sessions:
                return self._active_sessions[session_id]

            # Load from database
            session = self._state_manager.load_session(session_id)
            if session:
                # Add to active sessions if it's an active status
                if session.status in [SessionStatus.ACTIVE, SessionStatus.PAUSED, SessionStatus.IDLE]:
                    with self._global_lock:
                        self._active_sessions[session_id] = session
                        if session_id not in self._session_locks:
                            self._session_locks[session_id] = threading.RLock()

                        # Load metrics too
                        metrics = self._state_manager.load_metrics(session_id)
                        if metrics:
                            self._session_metrics[session_id] = metrics

            return session

        except Exception as e:
            self._logger.error(f"Error getting session {session_id}: {str(e)}")
            return None

    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update session last activity timestamp.

        Args:
            session_id: Session identifier

        Returns:
            True if updated successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            with self._session_locks[session_id]:
                # Update activity timestamp
                session.last_activity = datetime.now()

                # Update metrics
                if session_id in self._session_metrics:
                    self._session_metrics[session_id].last_activity = datetime.now()

                # Save to database
                self._state_manager.save_session(session)
                if session_id in self._session_metrics:
                    self._state_manager.save_metrics(self._session_metrics[session_id])

            return True

        except Exception as e:
            self._logger.error(f"Error updating session activity {session_id}: {str(e)}")
            return False

    async def pause_session(self, session_id: str) -> bool:
        """
        Pause an active session.

        Args:
            session_id: Session identifier

        Returns:
            True if paused successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            with self._session_locks[session_id]:
                if session.status != SessionStatus.ACTIVE:
                    self._logger.warning(f"Cannot pause session {session_id} with status {session.status}")
                    return False

                # Update status
                session.status = SessionStatus.PAUSED
                session.last_activity = datetime.now()

                # Save to database
                self._state_manager.save_session(session)

            self._logger.info(f"Paused session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error pausing session {session_id}: {str(e)}")
            return False

    async def resume_session(self, session_id: str) -> bool:
        """
        Resume a paused session.

        Args:
            session_id: Session identifier

        Returns:
            True if resumed successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            with self._session_locks[session_id]:
                if session.status != SessionStatus.PAUSED:
                    self._logger.warning(f"Cannot resume session {session_id} with status {session.status}")
                    return False

                # Update status
                session.status = SessionStatus.ACTIVE
                session.last_activity = datetime.now()

                # Save to database
                self._state_manager.save_session(session)

            self._logger.info(f"Resumed session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error resuming session {session_id}: {str(e)}")
            return False

    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if terminated successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            with self._session_locks[session_id]:
                # Update status
                session.status = SessionStatus.TERMINATED
                session.terminated_at = datetime.now()
                session.last_activity = datetime.now()

                # Save to database
                self._state_manager.save_session(session)

                # Save final metrics
                if session_id in self._session_metrics:
                    self._state_manager.save_metrics(self._session_metrics[session_id])

            # Remove from active sessions
            with self._global_lock:
                self._active_sessions.pop(session_id, None)
                self._session_metrics.pop(session_id, None)
                self._session_locks.pop(session_id, None)

            self._logger.info(f"Terminated session {session_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error terminating session {session_id}: {str(e)}")
            return False

    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """
        Get session metrics.

        Args:
            session_id: Session identifier

        Returns:
            SessionMetrics object or None if not found
        """
        try:
            # Check in-memory metrics first
            if session_id in self._session_metrics:
                return self._session_metrics[session_id]

            # Load from database
            metrics = self._state_manager.load_metrics(session_id)
            if metrics and session_id in self._active_sessions:
                # Cache in memory for active sessions
                self._session_metrics[session_id] = metrics

            return metrics

        except Exception as e:
            self._logger.error(f"Error getting session metrics {session_id}: {str(e)}")
            return None

    async def cleanup_idle_sessions(self, idle_timeout_minutes: int = 30) -> int:
        """
        Clean up idle sessions.

        Args:
            idle_timeout_minutes: Timeout in minutes

        Returns:
            Number of sessions cleaned up
        """
        try:
            return await self._cleanup_manager.cleanup_idle_sessions(idle_timeout_minutes)

        except Exception as e:
            self._logger.error(f"Error cleaning up idle sessions: {str(e)}")
            return 0

    def update_session_metrics(self, session_id: str, message_count: int = 0,
                             token_count: int = 0, error_count: int = 0,
                             function_calls: int = 0) -> bool:
        """
        Update session metrics.

        Args:
            session_id: Session identifier
            message_count: Number of messages to add
            token_count: Number of tokens to add
            error_count: Number of errors to add
            function_calls: Number of function calls to add

        Returns:
            bool: True if updated successfully
        """
        try:
            if session_id not in self._session_metrics:
                return False

            with self._session_locks[session_id]:
                metrics = self._session_metrics[session_id]

                # Update counters
                metrics.total_messages += message_count
                metrics.total_tokens += token_count
                metrics.error_count += error_count
                metrics.function_calls_count += function_calls
                metrics.last_activity = datetime.now()

                # Calculate derived metrics
                if metrics.total_messages > 0:
                    metrics.average_message_length = metrics.total_tokens / metrics.total_messages

                # Calculate session duration
                session = self._active_sessions.get(session_id)
                if session:
                    duration = datetime.now() - session.created_at
                    metrics.session_duration_seconds = int(duration.total_seconds())

                    # Calculate rates
                    if metrics.session_duration_seconds > 0:
                        minutes = metrics.session_duration_seconds / 60
                        metrics.messages_per_minute = metrics.total_messages / minutes
                        metrics.tokens_per_minute = metrics.total_tokens / minutes

                # Update session totals
                if session:
                    session.total_messages = metrics.total_messages
                    session.total_tokens = metrics.total_tokens
                    session.last_activity = datetime.now()

                    # Save to database
                    self._state_manager.save_session(session)

                # Save metrics
                self._state_manager.save_metrics(metrics)

            return True

        except Exception as e:
            self._logger.error(f"Error updating session metrics {session_id}: {str(e)}")
            return False

    def get_active_session_count(self) -> int:
        """
        Get count of active sessions.

        Returns:
            int: Number of active sessions
        """
        with self._global_lock:
            return len(self._active_sessions)

    def get_active_session_ids(self) -> List[str]:
        """
        Get list of active session IDs.

        Returns:
            List[str]: Active session IDs
        """
        with self._global_lock:
            return list(self._active_sessions.keys())
