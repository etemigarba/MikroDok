"""
Module: chat_session_db
Description: Stores interactive inference sessions with conversation history
Phase: 4
Location: /src/modules/database/chat_repository_db/chat_session_db/
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


class SessionStatus(Enum):
    """Chat session status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class ChatSession:
    """Chat session data structure."""
    session_id: str
    model_id: str
    user_id: Optional[str] = None
    session_name: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = None
    last_activity: datetime = None
    terminated_at: Optional[datetime] = None
    total_messages: int = 0
    total_tokens: int = 0
    context_length: int = 4096
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: Optional[str] = None
    session_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.last_activity is None:
            self.last_activity = self.created_at


class ChatSessionDB:
    """
    Database manager for chat sessions with conversation history.
    
    Provides thread-safe operations for storing and retrieving chat session data
    with automatic schema management and performance optimization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the chat session database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to chat data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "chat"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "chat_sessions.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._session_retention_days = 365  # Keep sessions for 1 year
        self._max_sessions_per_user = 1000  # Maximum sessions per user
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
                
                # Create chat sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        user_id TEXT,
                        session_name TEXT,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        terminated_at TEXT,
                        total_messages INTEGER DEFAULT 0,
                        total_tokens INTEGER DEFAULT 0,
                        context_length INTEGER DEFAULT 4096,
                        temperature REAL DEFAULT 0.7,
                        max_tokens INTEGER DEFAULT 2048,
                        system_prompt TEXT,
                        session_config_json TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_model_id 
                    ON chat_sessions(model_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id 
                    ON chat_sessions(user_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_status 
                    ON chat_sessions(status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at 
                    ON chat_sessions(created_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_activity 
                    ON chat_sessions(last_activity)
                """)
                
                # Create session statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_statistics (
                        session_id TEXT PRIMARY KEY,
                        avg_response_time_ms REAL,
                        total_inference_time_ms REAL,
                        avg_tokens_per_message REAL,
                        peak_memory_usage_mb REAL,
                        total_processing_time_ms REAL,
                        error_count INTEGER DEFAULT 0,
                        last_updated TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                    )
                """)
                
                conn.commit()
                self._logger.info("Chat session database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize chat session database: {e}")
                raise
            finally:
                conn.close()

    def create_session(self, model_id: str, user_id: Optional[str] = None,
                      session_name: Optional[str] = None,
                      context_length: int = 4096,
                      temperature: float = 0.7,
                      max_tokens: int = 2048,
                      system_prompt: Optional[str] = None,
                      session_config: Optional[Dict[str, Any]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new chat session.

        Args:
            model_id: Model identifier
            user_id: User identifier
            session_name: Optional session name
            context_length: Context window length
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
            system_prompt: System prompt for the session
            session_config: Session configuration
            metadata: Additional metadata

        Returns:
            Session ID

        Raises:
            ValueError: If session limit exceeded
        """
        session_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        if session_name is None:
            session_name = f"Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check session limit per user
                if user_id:
                    cursor.execute("SELECT COUNT(*) FROM chat_sessions WHERE user_id = ?", (user_id,))
                    session_count = cursor.fetchone()[0]

                    if session_count >= self._max_sessions_per_user:
                        raise ValueError(f"Maximum sessions per user ({self._max_sessions_per_user}) exceeded")

                cursor.execute("""
                    INSERT INTO chat_sessions (
                        session_id, model_id, user_id, session_name, status,
                        created_at, last_activity, total_messages, total_tokens,
                        context_length, temperature, max_tokens, system_prompt,
                        session_config_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, model_id, user_id, session_name, SessionStatus.ACTIVE.value,
                    current_time, current_time, 0, 0,
                    context_length, temperature, max_tokens, system_prompt,
                    json.dumps(session_config) if session_config else None,
                    json.dumps(metadata) if metadata else None
                ))

                # Initialize session statistics
                cursor.execute("""
                    INSERT INTO session_statistics (
                        session_id, avg_response_time_ms, total_inference_time_ms,
                        avg_tokens_per_message, peak_memory_usage_mb,
                        total_processing_time_ms, error_count, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, 0.0, 0.0, 0.0, 0.0, 0.0, 0, current_time))

                conn.commit()
                self._logger.info(f"Created chat session {session_id} for model {model_id}")
                return session_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create chat session: {e}")
                raise
            finally:
                conn.close()

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Retrieve a chat session by ID.

        Args:
            session_id: Session identifier

        Returns:
            ChatSession object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_id, model_id, user_id, session_name, status,
                           created_at, last_activity, terminated_at, total_messages,
                           total_tokens, context_length, temperature, max_tokens,
                           system_prompt, session_config_json, metadata_json
                    FROM chat_sessions WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return ChatSession(
                    session_id=row[0],
                    model_id=row[1],
                    user_id=row[2],
                    session_name=row[3],
                    status=SessionStatus(row[4]),
                    created_at=datetime.fromisoformat(row[5]),
                    last_activity=datetime.fromisoformat(row[6]),
                    terminated_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    total_messages=row[8],
                    total_tokens=row[9],
                    context_length=row[10],
                    temperature=row[11],
                    max_tokens=row[12],
                    system_prompt=row[13],
                    session_config=json.loads(row[14]) if row[14] else None,
                    metadata=json.loads(row[15]) if row[15] else None
                )

            except Exception as e:
                self._logger.error(f"Failed to get chat session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def update_session(self, session: ChatSession) -> bool:
        """
        Update an existing chat session.

        Args:
            session: ChatSession object with updated data

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE chat_sessions SET
                        model_id = ?, user_id = ?, session_name = ?, status = ?,
                        last_activity = ?, terminated_at = ?, total_messages = ?,
                        total_tokens = ?, context_length = ?, temperature = ?,
                        max_tokens = ?, system_prompt = ?, session_config_json = ?,
                        metadata_json = ?
                    WHERE session_id = ?
                """, (
                    session.model_id, session.user_id, session.session_name,
                    session.status.value, session.last_activity.isoformat(),
                    session.terminated_at.isoformat() if session.terminated_at else None,
                    session.total_messages, session.total_tokens,
                    session.context_length, session.temperature, session.max_tokens,
                    session.system_prompt,
                    json.dumps(session.session_config) if session.session_config else None,
                    json.dumps(session.metadata) if session.metadata else None,
                    session.session_id
                ))

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update chat session {session.session_id}: {e}")
                return False
            finally:
                conn.close()

    def update_session_activity(self, session_id: str, message_count: int = 1,
                               token_count: int = 0) -> bool:
        """
        Update session activity metrics.

        Args:
            session_id: Session identifier
            message_count: Number of messages to add
            token_count: Number of tokens to add

        Returns:
            True if updated successfully
        """
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE chat_sessions SET
                        last_activity = ?,
                        total_messages = total_messages + ?,
                        total_tokens = total_tokens + ?
                    WHERE session_id = ?
                """, (current_time, message_count, token_count, session_id))

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update session activity {session_id}: {e}")
                return False
            finally:
                conn.close()

    def terminate_session(self, session_id: str, status: SessionStatus = SessionStatus.COMPLETED) -> bool:
        """
        Terminate a chat session.

        Args:
            session_id: Session identifier
            status: Final session status

        Returns:
            True if terminated successfully
        """
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE chat_sessions SET
                        status = ?,
                        terminated_at = ?,
                        last_activity = ?
                    WHERE session_id = ?
                """, (status.value, current_time, current_time, session_id))

                conn.commit()
                self._logger.info(f"Terminated chat session {session_id} with status {status.value}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to terminate chat session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def list_sessions(self, user_id: Optional[str] = None,
                     model_id: Optional[str] = None,
                     status: Optional[SessionStatus] = None,
                     limit: int = 100,
                     offset: int = 0) -> List[ChatSession]:
        """
        List chat sessions with optional filtering.

        Args:
            user_id: Filter by user ID
            model_id: Filter by model ID
            status: Filter by session status
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip

        Returns:
            List of ChatSession objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT session_id, model_id, user_id, session_name, status,
                           created_at, last_activity, terminated_at, total_messages,
                           total_tokens, context_length, temperature, max_tokens,
                           system_prompt, session_config_json, metadata_json
                    FROM chat_sessions
                """

                conditions = []
                params = []

                if user_id:
                    conditions.append("user_id = ?")
                    params.append(user_id)

                if model_id:
                    conditions.append("model_id = ?")
                    params.append(model_id)

                if status:
                    conditions.append("status = ?")
                    params.append(status.value)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY last_activity DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                sessions = []
                for row in rows:
                    sessions.append(ChatSession(
                        session_id=row[0],
                        model_id=row[1],
                        user_id=row[2],
                        session_name=row[3],
                        status=SessionStatus(row[4]),
                        created_at=datetime.fromisoformat(row[5]),
                        last_activity=datetime.fromisoformat(row[6]),
                        terminated_at=datetime.fromisoformat(row[7]) if row[7] else None,
                        total_messages=row[8],
                        total_tokens=row[9],
                        context_length=row[10],
                        temperature=row[11],
                        max_tokens=row[12],
                        system_prompt=row[13],
                        session_config=json.loads(row[14]) if row[14] else None,
                        metadata=json.loads(row[15]) if row[15] else None
                    ))

                return sessions

            except Exception as e:
                self._logger.error(f"Failed to list chat sessions: {e}")
                return []
            finally:
                conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session and all associated data.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete session (statistics will be deleted by CASCADE)
                cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))

                conn.commit()
                self._logger.info(f"Deleted chat session {session_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete chat session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def update_session_statistics(self, session_id: str,
                                 avg_response_time_ms: Optional[float] = None,
                                 total_inference_time_ms: Optional[float] = None,
                                 avg_tokens_per_message: Optional[float] = None,
                                 peak_memory_usage_mb: Optional[float] = None,
                                 total_processing_time_ms: Optional[float] = None,
                                 error_count: Optional[int] = None) -> bool:
        """
        Update session statistics.

        Args:
            session_id: Session identifier
            avg_response_time_ms: Average response time in milliseconds
            total_inference_time_ms: Total inference time in milliseconds
            avg_tokens_per_message: Average tokens per message
            peak_memory_usage_mb: Peak memory usage in MB
            total_processing_time_ms: Total processing time in milliseconds
            error_count: Number of errors

        Returns:
            True if updated successfully
        """
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build update query dynamically
                updates = []
                params = []

                if avg_response_time_ms is not None:
                    updates.append("avg_response_time_ms = ?")
                    params.append(avg_response_time_ms)

                if total_inference_time_ms is not None:
                    updates.append("total_inference_time_ms = ?")
                    params.append(total_inference_time_ms)

                if avg_tokens_per_message is not None:
                    updates.append("avg_tokens_per_message = ?")
                    params.append(avg_tokens_per_message)

                if peak_memory_usage_mb is not None:
                    updates.append("peak_memory_usage_mb = ?")
                    params.append(peak_memory_usage_mb)

                if total_processing_time_ms is not None:
                    updates.append("total_processing_time_ms = ?")
                    params.append(total_processing_time_ms)

                if error_count is not None:
                    updates.append("error_count = ?")
                    params.append(error_count)

                if not updates:
                    return True  # Nothing to update

                updates.append("last_updated = ?")
                params.append(current_time)
                params.append(session_id)

                query = f"UPDATE session_statistics SET {', '.join(updates)} WHERE session_id = ?"
                cursor.execute(query, params)

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update session statistics {session_id}: {e}")
                return False
            finally:
                conn.close()

    def get_session_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session statistics.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with statistics or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT avg_response_time_ms, total_inference_time_ms,
                           avg_tokens_per_message, peak_memory_usage_mb,
                           total_processing_time_ms, error_count, last_updated
                    FROM session_statistics WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'avg_response_time_ms': row[0],
                    'total_inference_time_ms': row[1],
                    'avg_tokens_per_message': row[2],
                    'peak_memory_usage_mb': row[3],
                    'total_processing_time_ms': row[4],
                    'error_count': row[5],
                    'last_updated': row[6]
                }

            except Exception as e:
                self._logger.error(f"Failed to get session statistics {session_id}: {e}")
                return None
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
                    DELETE FROM chat_sessions
                    WHERE created_at < ? AND status IN ('completed', 'terminated')
                """, (cutoff_str,))

                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    self._logger.info(f"Cleaned up {deleted_count} old chat sessions")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old sessions: {e}")
                return 0
            finally:
                conn.close()
