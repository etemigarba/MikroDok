"""
Module: log_entries_db
Description: Manages application event logs with efficient storage, retrieval, and retention policies for comprehensive system monitoring
Phase: 4
Location: /src/modules/database/system_logs_db/log_entries_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import gzip
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Log category enumeration."""
    SYSTEM = "SYSTEM"
    APPLICATION = "APPLICATION"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    USER_ACTION = "USER_ACTION"
    DATA_PROCESSING = "DATA_PROCESSING"
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"


class EventType(Enum):
    """Event type enumeration."""
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    OPERATION_START = "OPERATION_START"
    OPERATION_END = "OPERATION_END"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"
    RESOURCE_DEALLOCATION = "RESOURCE_DEALLOCATION"
    DATA_IMPORT = "DATA_IMPORT"
    DATA_EXPORT = "DATA_EXPORT"
    MODEL_TRAINING = "MODEL_TRAINING"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"


@dataclass
class LogEntry:
    """Log entry data structure."""
    log_id: str
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    event_type: EventType
    source: str
    message: str
    details: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    stack_trace: Optional[str] = None
    thread_id: Optional[int] = None
    process_id: Optional[int] = None
    execution_time_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None


class LogEntriesDB:
    """
    Log entries database manager.
    
    Handles storage and retrieval of application event logs with efficient
    storage, indexing, and retention policies for comprehensive system
    monitoring and debugging capabilities.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the log entries database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to system logs data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "system_logs"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "log_entries.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._detailed_retention_days = 30  # Keep detailed logs for 30 days
        self._summary_retention_months = 12  # Keep summaries for 12 months
        self._archive_retention_years = 5   # Keep archives for 5 years
        
        # Performance settings
        self._batch_size = 1000
        self._compression_threshold_mb = 100
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Create log entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_entries (
                    log_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    user_id TEXT,
                    session_id TEXT,
                    correlation_id TEXT,
                    stack_trace TEXT,
                    thread_id INTEGER,
                    process_id INTEGER,
                    execution_time_ms REAL,
                    memory_usage_mb REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create log summaries table for aggregated data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_summaries (
                    summary_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    avg_execution_time_ms REAL,
                    avg_memory_usage_mb REAL,
                    first_occurrence TEXT NOT NULL,
                    last_occurrence TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create archived logs table for compressed historical data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS archived_logs (
                    archive_id TEXT PRIMARY KEY,
                    archive_date TEXT NOT NULL,
                    compressed_data BLOB NOT NULL,
                    entry_count INTEGER NOT NULL,
                    original_size_mb REAL NOT NULL,
                    compressed_size_mb REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_timestamp ON log_entries(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_level ON log_entries(level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_category ON log_entries(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_event_type ON log_entries(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_source ON log_entries(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_user_id ON log_entries(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_session_id ON log_entries(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_correlation_id ON log_entries(correlation_id)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_summaries_date_hour ON log_summaries(date, hour)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_summaries_level ON log_summaries(level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_summaries_category ON log_summaries(category)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_logs_date ON archived_logs(archive_date)")
            
            conn.commit()
            conn.close()
            
            self._logger.info("Log entries database initialized successfully")
    
    def add_log_entry(self, level: LogLevel, category: LogCategory, event_type: EventType,
                     source: str, message: str, details: Optional[Dict[str, Any]] = None,
                     user_id: Optional[str] = None, session_id: Optional[str] = None,
                     correlation_id: Optional[str] = None, stack_trace: Optional[str] = None,
                     thread_id: Optional[int] = None, process_id: Optional[int] = None,
                     execution_time_ms: Optional[float] = None,
                     memory_usage_mb: Optional[float] = None) -> str:
        """
        Add a new log entry.
        
        Args:
            level: Log level
            category: Log category
            event_type: Event type
            source: Source component or module
            message: Log message
            details: Optional additional details
            user_id: Optional user ID
            session_id: Optional session ID
            correlation_id: Optional correlation ID for tracking related events
            stack_trace: Optional stack trace for errors
            thread_id: Optional thread ID
            process_id: Optional process ID
            execution_time_ms: Optional execution time in milliseconds
            memory_usage_mb: Optional memory usage in MB
            
        Returns:
            Log entry ID
        """
        log_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)
        
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO log_entries (
                        log_id, timestamp, level, category, event_type, source,
                        message, details, user_id, session_id, correlation_id, stack_trace,
                        thread_id, process_id, execution_time_ms, memory_usage_mb
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id, timestamp.isoformat(), level.value, category.value,
                    event_type.value, source, message,
                    json.dumps(details) if details else None,
                    user_id, session_id, correlation_id, stack_trace,
                    thread_id, process_id, execution_time_ms, memory_usage_mb
                ))
                
                conn.commit()
                conn.close()
                
                # Update summaries asynchronously
                self._update_log_summary(timestamp, level, category, event_type,
                                       execution_time_ms, memory_usage_mb)
                
                return log_id
                
            except Exception as e:
                self._logger.error(f"Failed to add log entry: {e}")
                raise

    def _update_log_summary(self, timestamp: datetime, level: LogLevel, category: LogCategory,
                           event_type: EventType, execution_time_ms: Optional[float] = None,
                           memory_usage_mb: Optional[float] = None) -> None:
        """Update log summary statistics."""
        try:
            date_str = timestamp.date().isoformat()
            hour = timestamp.hour
            summary_id = f"{date_str}_{hour}_{level.value}_{category.value}_{event_type.value}"

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Check if summary exists
                cursor.execute("""
                    SELECT count, avg_execution_time_ms, avg_memory_usage_mb
                    FROM log_summaries
                    WHERE summary_id = ?
                """, (summary_id,))

                result = cursor.fetchone()

                if result:
                    # Update existing summary
                    count, avg_exec_time, avg_memory = result
                    new_count = count + 1

                    # Calculate new averages
                    new_avg_exec_time = avg_exec_time
                    if execution_time_ms is not None:
                        if avg_exec_time is not None:
                            new_avg_exec_time = ((avg_exec_time * count) + execution_time_ms) / new_count
                        else:
                            new_avg_exec_time = execution_time_ms

                    new_avg_memory = avg_memory
                    if memory_usage_mb is not None:
                        if avg_memory is not None:
                            new_avg_memory = ((avg_memory * count) + memory_usage_mb) / new_count
                        else:
                            new_avg_memory = memory_usage_mb

                    cursor.execute("""
                        UPDATE log_summaries
                        SET count = ?, avg_execution_time_ms = ?, avg_memory_usage_mb = ?,
                            last_occurrence = ?
                        WHERE summary_id = ?
                    """, (new_count, new_avg_exec_time, new_avg_memory,
                          timestamp.isoformat(), summary_id))
                else:
                    # Create new summary
                    cursor.execute("""
                        INSERT INTO log_summaries (
                            summary_id, date, hour, level, category, event_type,
                            count, avg_execution_time_ms, avg_memory_usage_mb,
                            first_occurrence, last_occurrence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        summary_id, date_str, hour, level.value, category.value,
                        event_type.value, 1, execution_time_ms, memory_usage_mb,
                        timestamp.isoformat(), timestamp.isoformat()
                    ))

                conn.commit()
                conn.close()

        except Exception as e:
            self._logger.error(f"Failed to update log summary: {e}")

    def get_log_entries(self, start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       level: Optional[LogLevel] = None,
                       category: Optional[LogCategory] = None,
                       event_type: Optional[EventType] = None,
                       source: Optional[str] = None,
                       user_id: Optional[str] = None,
                       session_id: Optional[str] = None,
                       correlation_id: Optional[str] = None,
                       limit: int = 1000) -> List[LogEntry]:
        """
        Retrieve log entries with filtering options.

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            level: Optional log level filter
            category: Optional category filter
            event_type: Optional event type filter
            source: Optional source filter
            user_id: Optional user ID filter
            session_id: Optional session ID filter
            correlation_id: Optional correlation ID filter
            limit: Maximum number of entries to return

        Returns:
            List of log entries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Build query with filters
                query = "SELECT * FROM log_entries WHERE 1=1"
                params = []

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                if level:
                    query += " AND level = ?"
                    params.append(level.value)

                if category:
                    query += " AND category = ?"
                    params.append(category.value)

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type.value)

                if source:
                    query += " AND source = ?"
                    params.append(source)

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                if session_id:
                    query += " AND session_id = ?"
                    params.append(session_id)

                if correlation_id:
                    query += " AND correlation_id = ?"
                    params.append(correlation_id)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                # Convert rows to LogEntry objects
                entries = []
                for row in rows:
                    entry = LogEntry(
                        log_id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        level=LogLevel(row[2]),
                        category=LogCategory(row[3]),
                        event_type=EventType(row[4]),
                        source=row[5],
                        message=row[6],
                        details=json.loads(row[7]) if row[7] else None,
                        user_id=row[8],
                        session_id=row[9],
                        correlation_id=row[10],
                        stack_trace=row[11],
                        thread_id=row[12],
                        process_id=row[13],
                        execution_time_ms=row[14],
                        memory_usage_mb=row[15]
                    )
                    entries.append(entry)

                return entries

            except Exception as e:
                self._logger.error(f"Failed to get log entries: {e}")
                raise

    def get_log_summaries(self, start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         level: Optional[LogLevel] = None,
                         category: Optional[LogCategory] = None) -> List[Dict[str, Any]]:
        """
        Get log summaries for analysis.

        Args:
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            level: Optional log level filter
            category: Optional category filter

        Returns:
            List of summary dictionaries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = "SELECT * FROM log_summaries WHERE 1=1"
                params = []

                if start_date:
                    query += " AND date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND date <= ?"
                    params.append(end_date)

                if level:
                    query += " AND level = ?"
                    params.append(level.value)

                if category:
                    query += " AND category = ?"
                    params.append(category.value)

                query += " ORDER BY date DESC, hour DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                summaries = []
                for row in rows:
                    summary = {
                        'summary_id': row[0],
                        'date': row[1],
                        'hour': row[2],
                        'level': row[3],
                        'category': row[4],
                        'event_type': row[5],
                        'count': row[6],
                        'avg_execution_time_ms': row[7],
                        'avg_memory_usage_mb': row[8],
                        'first_occurrence': row[9],
                        'last_occurrence': row[10]
                    }
                    summaries.append(summary)

                return summaries

            except Exception as e:
                self._logger.error(f"Failed to get log summaries: {e}")
                raise

    def archive_old_logs(self, archive_before_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Archive old log entries to compressed storage.

        Args:
            archive_before_date: Date before which to archive logs

        Returns:
            Archive operation statistics
        """
        if archive_before_date is None:
            archive_before_date = datetime.now(timezone.utc) - timedelta(days=self._detailed_retention_days)

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get logs to archive
                cursor.execute("""
                    SELECT * FROM log_entries
                    WHERE timestamp < ?
                    ORDER BY timestamp
                """, (archive_before_date.isoformat(),))

                logs_to_archive = cursor.fetchall()

                if not logs_to_archive:
                    conn.close()
                    return {'archived_count': 0, 'compressed_size_mb': 0}

                # Prepare data for compression
                archive_data = []
                for row in logs_to_archive:
                    log_dict = {
                        'log_id': row[0],
                        'timestamp': row[1],
                        'level': row[2],
                        'category': row[3],
                        'event_type': row[4],
                        'source': row[5],
                        'message': row[6],
                        'details': row[7],
                        'user_id': row[8],
                        'session_id': row[9],
                        'correlation_id': row[10],
                        'stack_trace': row[11],
                        'thread_id': row[12],
                        'process_id': row[13],
                        'execution_time_ms': row[14],
                        'memory_usage_mb': row[15]
                    }
                    archive_data.append(log_dict)

                # Compress data
                json_data = json.dumps(archive_data)
                original_size = len(json_data.encode('utf-8'))
                compressed_data = gzip.compress(json_data.encode('utf-8'))
                compressed_size = len(compressed_data)

                # Store compressed archive
                archive_id = str(uuid4())
                archive_date = archive_before_date.date().isoformat()

                cursor.execute("""
                    INSERT INTO archived_logs (
                        archive_id, archive_date, compressed_data, entry_count,
                        original_size_mb, compressed_size_mb
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    archive_id, archive_date, compressed_data, len(logs_to_archive),
                    original_size / (1024 * 1024), compressed_size / (1024 * 1024)
                ))

                # Delete archived logs
                cursor.execute("""
                    DELETE FROM log_entries
                    WHERE timestamp < ?
                """, (archive_before_date.isoformat(),))

                conn.commit()
                conn.close()

                stats = {
                    'archive_id': archive_id,
                    'archived_count': len(logs_to_archive),
                    'original_size_mb': original_size / (1024 * 1024),
                    'compressed_size_mb': compressed_size / (1024 * 1024),
                    'compression_ratio': compressed_size / original_size if original_size > 0 else 0
                }

                self._logger.info(f"Archived {len(logs_to_archive)} log entries to {archive_id}")
                return stats

            except Exception as e:
                self._logger.error(f"Failed to archive logs: {e}")
                raise

    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old data based on retention policies.

        Returns:
            Cleanup statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Clean up old summaries
                summary_cutoff = datetime.now(timezone.utc) - timedelta(days=self._summary_retention_months * 30)
                cursor.execute("""
                    DELETE FROM log_summaries
                    WHERE date < ?
                """, (summary_cutoff.date().isoformat(),))
                deleted_summaries = cursor.rowcount

                # Clean up old archives
                archive_cutoff = datetime.now(timezone.utc) - timedelta(days=self._archive_retention_years * 365)
                cursor.execute("""
                    DELETE FROM archived_logs
                    WHERE archive_date < ?
                """, (archive_cutoff.date().isoformat(),))
                deleted_archives = cursor.rowcount

                conn.commit()
                conn.close()

                stats = {
                    'deleted_summaries': deleted_summaries,
                    'deleted_archives': deleted_archives
                }

                self._logger.info(f"Cleanup completed: {deleted_summaries} summaries, {deleted_archives} archives deleted")
                return stats

            except Exception as e:
                self._logger.error(f"Failed to cleanup old data: {e}")
                raise

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Database statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get log entries count
                cursor.execute("SELECT COUNT(*) FROM log_entries")
                entries_count = cursor.fetchone()[0]

                # Get summaries count
                cursor.execute("SELECT COUNT(*) FROM log_summaries")
                summaries_count = cursor.fetchone()[0]

                # Get archives count
                cursor.execute("SELECT COUNT(*) FROM archived_logs")
                archives_count = cursor.fetchone()[0]

                # Get database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                db_size_mb = (page_count * page_size) / (1024 * 1024)

                # Get oldest and newest entries
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM log_entries")
                result = cursor.fetchone()
                oldest_entry = result[0] if result[0] else None
                newest_entry = result[1] if result[1] else None

                conn.close()

                return {
                    'entries_count': entries_count,
                    'summaries_count': summaries_count,
                    'archives_count': archives_count,
                    'database_size_mb': db_size_mb,
                    'oldest_entry': oldest_entry,
                    'newest_entry': newest_entry,
                    'retention_days': self._detailed_retention_days,
                    'summary_retention_months': self._summary_retention_months,
                    'archive_retention_years': self._archive_retention_years
                }

            except Exception as e:
                self._logger.error(f"Failed to get statistics: {e}")
                raise
