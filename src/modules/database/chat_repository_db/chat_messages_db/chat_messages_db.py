"""
Module: chat_messages_db
Description: Persists individual chat messages with context window management
Phase: 4
Location: /src/modules/database/chat_repository_db/chat_messages_db/
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


class MessageRole(Enum):
    """Chat message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"


class MessageStatus(Enum):
    """Chat message status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ChatMessage:
    """Chat message data structure."""
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime = None
    status: MessageStatus = MessageStatus.COMPLETED
    token_count: int = 0
    processing_time_ms: Optional[float] = None
    parent_message_id: Optional[str] = None
    thread_id: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    function_response: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class ChatMessagesDB:
    """
    Database manager for chat messages with context window management.
    
    Provides thread-safe operations for storing and retrieving chat messages
    with efficient context window management and message threading support.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the chat messages database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to chat data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "chat"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "chat_messages.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._message_retention_days = 365  # Keep messages for 1 year
        self._max_messages_per_session = 10000  # Maximum messages per session
        self._context_window_size = 4096  # Default context window size
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
                
                # Create chat messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        message_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        status TEXT NOT NULL,
                        token_count INTEGER DEFAULT 0,
                        processing_time_ms REAL,
                        parent_message_id TEXT,
                        thread_id TEXT,
                        function_call_json TEXT,
                        function_response_json TEXT,
                        metadata_json TEXT,
                        sequence_number INTEGER,
                        FOREIGN KEY (parent_message_id) REFERENCES chat_messages(message_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id 
                    ON chat_messages(session_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp 
                    ON chat_messages(timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_role 
                    ON chat_messages(role)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_status 
                    ON chat_messages(status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id 
                    ON chat_messages(thread_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_sequence 
                    ON chat_messages(session_id, sequence_number)
                """)
                
                # Create message context table for efficient context window management
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS message_context (
                        session_id TEXT NOT NULL,
                        context_window_start INTEGER NOT NULL,
                        context_window_end INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        last_updated TEXT NOT NULL,
                        PRIMARY KEY (session_id)
                    )
                """)
                
                # Create message threads table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS message_threads (
                        thread_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        parent_message_id TEXT,
                        thread_name TEXT,
                        created_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        message_count INTEGER DEFAULT 0,
                        metadata_json TEXT
                    )
                """)
                
                conn.commit()
                self._logger.info("Chat messages database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize chat messages database: {e}")
                raise
            finally:
                conn.close()

    def add_message(self, session_id: str, role: MessageRole, content: str,
                   token_count: int = 0,
                   processing_time_ms: Optional[float] = None,
                   parent_message_id: Optional[str] = None,
                   thread_id: Optional[str] = None,
                   function_call: Optional[Dict[str, Any]] = None,
                   function_response: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new chat message.

        Args:
            session_id: Session identifier
            role: Message role
            content: Message content
            token_count: Number of tokens in the message
            processing_time_ms: Processing time in milliseconds
            parent_message_id: Parent message ID for threading
            thread_id: Thread identifier
            function_call: Function call data
            function_response: Function response data
            metadata: Additional metadata

        Returns:
            Message ID

        Raises:
            ValueError: If message limit exceeded
        """
        message_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check message limit per session
                cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
                message_count = cursor.fetchone()[0]

                if message_count >= self._max_messages_per_session:
                    raise ValueError(f"Maximum messages per session ({self._max_messages_per_session}) exceeded")

                # Get next sequence number
                cursor.execute("""
                    SELECT COALESCE(MAX(sequence_number), 0) + 1
                    FROM chat_messages WHERE session_id = ?
                """, (session_id,))
                sequence_number = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO chat_messages (
                        message_id, session_id, role, content, timestamp, status,
                        token_count, processing_time_ms, parent_message_id, thread_id,
                        function_call_json, function_response_json, metadata_json,
                        sequence_number
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_id, session_id, role.value, content, current_time,
                    MessageStatus.COMPLETED.value, token_count, processing_time_ms,
                    parent_message_id, thread_id,
                    json.dumps(function_call) if function_call else None,
                    json.dumps(function_response) if function_response else None,
                    json.dumps(metadata) if metadata else None,
                    sequence_number
                ))

                # Update thread if specified
                if thread_id:
                    cursor.execute("""
                        INSERT OR REPLACE INTO message_threads (
                            thread_id, session_id, parent_message_id, created_at,
                            last_activity, message_count
                        ) VALUES (?, ?, ?,
                            COALESCE((SELECT created_at FROM message_threads WHERE thread_id = ?), ?),
                            ?,
                            COALESCE((SELECT message_count FROM message_threads WHERE thread_id = ?), 0) + 1
                        )
                    """, (thread_id, session_id, parent_message_id, thread_id, current_time,
                          current_time, thread_id))

                # Update context window
                self._update_context_window(cursor, session_id, token_count, current_time)

                conn.commit()
                self._logger.debug(f"Added message {message_id} to session {session_id}")
                return message_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add message to session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def _update_context_window(self, cursor: sqlite3.Cursor, session_id: str,
                              token_count: int, timestamp: str) -> None:
        """
        Update context window for efficient token management.

        Args:
            cursor: Database cursor
            session_id: Session identifier
            token_count: Number of tokens to add
            timestamp: Current timestamp
        """
        # Get current context window
        cursor.execute("""
            SELECT context_window_start, context_window_end, total_tokens
            FROM message_context WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if row:
            start, end, total_tokens = row
            new_total = total_tokens + token_count
            new_end = end + 1
        else:
            start, new_end, new_total = 1, 1, token_count

        # Adjust window if exceeding context limit
        if new_total > self._context_window_size:
            # Find messages to remove from start of window
            cursor.execute("""
                SELECT sequence_number, token_count
                FROM chat_messages
                WHERE session_id = ? AND sequence_number >= ?
                ORDER BY sequence_number
            """, (session_id, start))

            cumulative_tokens = new_total
            new_start = start

            for seq_num, tokens in cursor.fetchall():
                if cumulative_tokens <= self._context_window_size:
                    break
                cumulative_tokens -= tokens
                new_start = seq_num + 1

            start = new_start
            new_total = cumulative_tokens

        # Update context window
        cursor.execute("""
            INSERT OR REPLACE INTO message_context (
                session_id, context_window_start, context_window_end,
                total_tokens, last_updated
            ) VALUES (?, ?, ?, ?, ?)
        """, (session_id, start, new_end, new_total, timestamp))

    def get_message(self, message_id: str) -> Optional[ChatMessage]:
        """
        Retrieve a chat message by ID.

        Args:
            message_id: Message identifier

        Returns:
            ChatMessage object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT message_id, session_id, role, content, timestamp, status,
                           token_count, processing_time_ms, parent_message_id, thread_id,
                           function_call_json, function_response_json, metadata_json
                    FROM chat_messages WHERE message_id = ?
                """, (message_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return ChatMessage(
                    message_id=row[0],
                    session_id=row[1],
                    role=MessageRole(row[2]),
                    content=row[3],
                    timestamp=datetime.fromisoformat(row[4]),
                    status=MessageStatus(row[5]),
                    token_count=row[6],
                    processing_time_ms=row[7],
                    parent_message_id=row[8],
                    thread_id=row[9],
                    function_call=json.loads(row[10]) if row[10] else None,
                    function_response=json.loads(row[11]) if row[11] else None,
                    metadata=json.loads(row[12]) if row[12] else None
                )

            except Exception as e:
                self._logger.error(f"Failed to get message {message_id}: {e}")
                return None
            finally:
                conn.close()

    def get_session_messages(self, session_id: str,
                           limit: Optional[int] = None,
                           offset: int = 0,
                           include_context_only: bool = False) -> List[ChatMessage]:
        """
        Get messages for a session with optional context window filtering.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            include_context_only: Only return messages in current context window

        Returns:
            List of ChatMessage objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT message_id, session_id, role, content, timestamp, status,
                           token_count, processing_time_ms, parent_message_id, thread_id,
                           function_call_json, function_response_json, metadata_json
                    FROM chat_messages WHERE session_id = ?
                """
                params = [session_id]

                # Filter by context window if requested
                if include_context_only:
                    cursor.execute("""
                        SELECT context_window_start, context_window_end
                        FROM message_context WHERE session_id = ?
                    """, (session_id,))

                    context_row = cursor.fetchone()
                    if context_row:
                        start, end = context_row
                        query += " AND sequence_number BETWEEN ? AND ?"
                        params.extend([start, end])

                query += " ORDER BY sequence_number"

                if limit:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                messages = []
                for row in rows:
                    messages.append(ChatMessage(
                        message_id=row[0],
                        session_id=row[1],
                        role=MessageRole(row[2]),
                        content=row[3],
                        timestamp=datetime.fromisoformat(row[4]),
                        status=MessageStatus(row[5]),
                        token_count=row[6],
                        processing_time_ms=row[7],
                        parent_message_id=row[8],
                        thread_id=row[9],
                        function_call=json.loads(row[10]) if row[10] else None,
                        function_response=json.loads(row[11]) if row[11] else None,
                        metadata=json.loads(row[12]) if row[12] else None
                    ))

                return messages

            except Exception as e:
                self._logger.error(f"Failed to get messages for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def update_message_status(self, message_id: str, status: MessageStatus,
                             processing_time_ms: Optional[float] = None) -> bool:
        """
        Update message status and processing time.

        Args:
            message_id: Message identifier
            status: New message status
            processing_time_ms: Processing time in milliseconds

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if processing_time_ms is not None:
                    cursor.execute("""
                        UPDATE chat_messages SET status = ?, processing_time_ms = ?
                        WHERE message_id = ?
                    """, (status.value, processing_time_ms, message_id))
                else:
                    cursor.execute("""
                        UPDATE chat_messages SET status = ?
                        WHERE message_id = ?
                    """, (status.value, message_id))

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update message status {message_id}: {e}")
                return False
            finally:
                conn.close()

    def delete_message(self, message_id: str) -> bool:
        """
        Delete a chat message.

        Args:
            message_id: Message identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get message info before deletion for context window update
                cursor.execute("""
                    SELECT session_id, token_count FROM chat_messages WHERE message_id = ?
                """, (message_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                session_id, token_count = row

                # Delete message
                cursor.execute("DELETE FROM chat_messages WHERE message_id = ?", (message_id,))

                # Update context window
                current_time = datetime.now(timezone.utc).isoformat()
                self._update_context_window(cursor, session_id, -token_count, current_time)

                conn.commit()
                self._logger.info(f"Deleted message {message_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete message {message_id}: {e}")
                return False
            finally:
                conn.close()

    def get_thread_messages(self, thread_id: str) -> List[ChatMessage]:
        """
        Get all messages in a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            List of ChatMessage objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT message_id, session_id, role, content, timestamp, status,
                           token_count, processing_time_ms, parent_message_id, thread_id,
                           function_call_json, function_response_json, metadata_json
                    FROM chat_messages WHERE thread_id = ?
                    ORDER BY sequence_number
                """, (thread_id,))

                rows = cursor.fetchall()

                messages = []
                for row in rows:
                    messages.append(ChatMessage(
                        message_id=row[0],
                        session_id=row[1],
                        role=MessageRole(row[2]),
                        content=row[3],
                        timestamp=datetime.fromisoformat(row[4]),
                        status=MessageStatus(row[5]),
                        token_count=row[6],
                        processing_time_ms=row[7],
                        parent_message_id=row[8],
                        thread_id=row[9],
                        function_call=json.loads(row[10]) if row[10] else None,
                        function_response=json.loads(row[11]) if row[11] else None,
                        metadata=json.loads(row[12]) if row[12] else None
                    ))

                return messages

            except Exception as e:
                self._logger.error(f"Failed to get thread messages {thread_id}: {e}")
                return []
            finally:
                conn.close()

    def get_context_window_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get context window information for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with context window info or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT context_window_start, context_window_end, total_tokens, last_updated
                    FROM message_context WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'context_window_start': row[0],
                    'context_window_end': row[1],
                    'total_tokens': row[2],
                    'last_updated': row[3],
                    'context_window_size': self._context_window_size
                }

            except Exception as e:
                self._logger.error(f"Failed to get context window info for session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def cleanup_old_messages(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old messages based on retention policy.

        Args:
            retention_days: Number of days to retain messages

        Returns:
            Number of messages deleted
        """
        if retention_days is None:
            retention_days = self._message_retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old messages
                cursor.execute("""
                    DELETE FROM chat_messages WHERE timestamp < ?
                """, (cutoff_str,))

                deleted_count = cursor.rowcount

                # Clean up orphaned context windows and threads
                cursor.execute("""
                    DELETE FROM message_context
                    WHERE session_id NOT IN (SELECT DISTINCT session_id FROM chat_messages)
                """)

                cursor.execute("""
                    DELETE FROM message_threads
                    WHERE session_id NOT IN (SELECT DISTINCT session_id FROM chat_messages)
                """)

                conn.commit()

                if deleted_count > 0:
                    self._logger.info(f"Cleaned up {deleted_count} old chat messages")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old messages: {e}")
                return 0
            finally:
                conn.close()

    def get_message_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get message statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with message statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get basic statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_messages,
                        SUM(token_count) as total_tokens,
                        AVG(token_count) as avg_tokens_per_message,
                        AVG(processing_time_ms) as avg_processing_time_ms,
                        COUNT(DISTINCT role) as unique_roles,
                        COUNT(DISTINCT thread_id) as thread_count
                    FROM chat_messages WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()

                stats = {
                    'total_messages': row[0] or 0,
                    'total_tokens': row[1] or 0,
                    'avg_tokens_per_message': row[2] or 0.0,
                    'avg_processing_time_ms': row[3] or 0.0,
                    'unique_roles': row[4] or 0,
                    'thread_count': row[5] or 0
                }

                # Get role distribution
                cursor.execute("""
                    SELECT role, COUNT(*) FROM chat_messages
                    WHERE session_id = ? GROUP BY role
                """, (session_id,))

                stats['role_distribution'] = dict(cursor.fetchall())

                return stats

            except Exception as e:
                self._logger.error(f"Failed to get message statistics for session {session_id}: {e}")
                return {}
            finally:
                conn.close()
