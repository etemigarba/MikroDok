"""
Module: system_logs_db
Description: Manages application event logs, errors, and audit trails with retention policies and efficient log rotation
Phase: 4
Location: /src/modules/database/monitoring_repository_db/system_logs_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import gzip
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class LogLevel(Enum):
    """Log levels for system events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    """Categories of system logs."""
    APPLICATION = "application"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATABASE = "database"
    NETWORK = "network"
    TRAINING = "training"
    INFERENCE = "inference"
    SYSTEM = "system"
    AUDIT = "audit"


class EventType(Enum):
    """Types of system events."""
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    SECURITY_EVENT = "security_event"
    PERFORMANCE_EVENT = "performance_event"
    AUDIT_EVENT = "audit_event"


@dataclass
class LogEntry:
    """System log entry data structure."""
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'log_id': self.log_id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'category': self.category.value,
            'event_type': self.event_type.value,
            'source': self.source,
            'message': self.message,
            'details': self.details,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'correlation_id': self.correlation_id,
            'stack_trace': self.stack_trace
        }


@dataclass
class AuditTrail:
    """Audit trail entry data structure."""
    audit_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SystemLogsDB:
    """
    System logs database manager.
    
    Handles storage and retrieval of application event logs, errors,
    and audit trails with retention policies and efficient log rotation
    for comprehensive system monitoring and compliance.
    """
    
    def __init__(self, db_path: Optional[str] = None, max_log_size_mb: int = 100):
        """
        Initialize the system logs database.
        
        Args:
            db_path: Path to the database file
            max_log_size_mb: Maximum size of log database before rotation
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "system_logs.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._max_log_size_bytes = max_log_size_mb * 1024 * 1024
        
        # Retention settings
        self._log_retention_days = 90  # Keep logs for 90 days
        self._audit_retention_days = 365  # Keep audit trails for 1 year
        self._archive_retention_days = 1095  # Keep archives for 3 years
        
        # Archive directory
        self._archive_dir = Path(db_path).parent / "archives"
        self._archive_dir.mkdir(exist_ok=True)
        
        self._initialize_database()
        self._start_maintenance_thread()
        
        self._logger.info(f"SystemLogsDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database tables and indexes."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            
            # Create system logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create audit trails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_trails (
                    audit_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create log statistics table for monitoring
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_statistics (
                    stat_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp 
                ON system_logs(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_system_logs_level_category 
                ON system_logs(level, category, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_system_logs_source 
                ON system_logs(source, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_system_logs_correlation 
                ON system_logs(correlation_id, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_trails_user_time 
                ON audit_trails(user_id, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_trails_resource 
                ON audit_trails(resource_type, resource_id, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_log_statistics_date_level 
                ON log_statistics(date, level, category)
            """)
            
            conn.commit()
            conn.close()
            
            self._logger.info("System logs database initialized successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize system logs database: {e}")
            raise

    def _start_maintenance_thread(self) -> None:
        """Start background thread for log maintenance and rotation."""
        def maintenance_worker():
            import time
            while True:
                try:
                    time.sleep(3600)  # Run every hour
                    self._check_log_rotation()
                    self._cleanup_old_logs()
                    self._update_log_statistics()
                except Exception as e:
                    self._logger.error(f"Maintenance thread error: {e}")

        maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
        maintenance_thread.start()
        self._logger.info("Started log maintenance thread")

    def log_event(self, level: LogLevel, category: LogCategory, event_type: EventType,
                  source: str, message: str, details: Optional[Dict[str, Any]] = None,
                  user_id: Optional[str] = None, session_id: Optional[str] = None,
                  correlation_id: Optional[str] = None, stack_trace: Optional[str] = None) -> str:
        """
        Log a system event.

        Args:
            level: Log level
            category: Log category
            event_type: Type of event
            source: Source of the log entry
            message: Log message
            details: Optional additional details
            user_id: Optional user ID
            session_id: Optional session ID
            correlation_id: Optional correlation ID for tracking related events
            stack_trace: Optional stack trace for errors

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
                    INSERT INTO system_logs (
                        log_id, timestamp, level, category, event_type, source,
                        message, details, user_id, session_id, correlation_id, stack_trace
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id, timestamp.isoformat(), level.value, category.value,
                    event_type.value, source, message,
                    json.dumps(details) if details else None,
                    user_id, session_id, correlation_id, stack_trace
                ))

                conn.commit()
                conn.close()

                # Log to application logger as well for immediate visibility
                if level == LogLevel.CRITICAL:
                    self._logger.critical(f"[{source}] {message}")
                elif level == LogLevel.ERROR:
                    self._logger.error(f"[{source}] {message}")
                elif level == LogLevel.WARNING:
                    self._logger.warning(f"[{source}] {message}")
                elif level == LogLevel.INFO:
                    self._logger.info(f"[{source}] {message}")
                else:  # DEBUG
                    self._logger.debug(f"[{source}] {message}")

                return log_id

            except Exception as e:
                self._logger.error(f"Failed to log event: {e}")
                raise

    def log_audit_event(self, user_id: str, action: str, resource_type: str,
                       resource_id: str, old_values: Optional[Dict[str, Any]] = None,
                       new_values: Optional[Dict[str, Any]] = None,
                       ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> str:
        """
        Log an audit trail event.

        Args:
            user_id: ID of the user performing the action
            action: Action being performed
            resource_type: Type of resource being acted upon
            resource_id: ID of the resource
            old_values: Optional old values before change
            new_values: Optional new values after change
            ip_address: Optional IP address of the user
            user_agent: Optional user agent string

        Returns:
            Audit entry ID
        """
        audit_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO audit_trails (
                        audit_id, timestamp, user_id, action, resource_type,
                        resource_id, old_values, new_values, ip_address, user_agent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_id, timestamp.isoformat(), user_id, action, resource_type,
                    resource_id,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    ip_address, user_agent
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Audit: {user_id} performed {action} on {resource_type}:{resource_id}")
                return audit_id

            except Exception as e:
                self._logger.error(f"Failed to log audit event: {e}")
                raise

    def get_logs(self, level: Optional[LogLevel] = None, category: Optional[LogCategory] = None,
                 source: Optional[str] = None, start_time: Optional[datetime] = None,
                 end_time: Optional[datetime] = None, correlation_id: Optional[str] = None,
                 limit: int = 1000) -> List[LogEntry]:
        """
        Retrieve system logs with filtering options.

        Args:
            level: Optional log level filter
            category: Optional category filter
            source: Optional source filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            correlation_id: Optional correlation ID filter
            limit: Maximum number of logs to return

        Returns:
            List of log entries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = """
                    SELECT log_id, timestamp, level, category, event_type, source,
                           message, details, user_id, session_id, correlation_id, stack_trace
                    FROM system_logs WHERE 1=1
                """
                params = []

                if level:
                    query += " AND level = ?"
                    params.append(level.value)

                if category:
                    query += " AND category = ?"
                    params.append(category.value)

                if source:
                    query += " AND source = ?"
                    params.append(source)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                if correlation_id:
                    query += " AND correlation_id = ?"
                    params.append(correlation_id)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                logs = []
                for row in rows:
                    log_entry = LogEntry(
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
                        stack_trace=row[11]
                    )
                    logs.append(log_entry)

                return logs

            except Exception as e:
                self._logger.error(f"Failed to get logs: {e}")
                raise

    def get_audit_trails(self, user_id: Optional[str] = None, resource_type: Optional[str] = None,
                        resource_id: Optional[str] = None, start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None, limit: int = 1000) -> List[AuditTrail]:
        """
        Retrieve audit trails with filtering options.

        Args:
            user_id: Optional user ID filter
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of audit entries to return

        Returns:
            List of audit trail entries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = """
                    SELECT audit_id, timestamp, user_id, action, resource_type,
                           resource_id, old_values, new_values, ip_address, user_agent
                    FROM audit_trails WHERE 1=1
                """
                params = []

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                if resource_type:
                    query += " AND resource_type = ?"
                    params.append(resource_type)

                if resource_id:
                    query += " AND resource_id = ?"
                    params.append(resource_id)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                audit_trails = []
                for row in rows:
                    audit_entry = AuditTrail(
                        audit_id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        user_id=row[2],
                        action=row[3],
                        resource_type=row[4],
                        resource_id=row[5],
                        old_values=json.loads(row[6]) if row[6] else None,
                        new_values=json.loads(row[7]) if row[7] else None,
                        ip_address=row[8],
                        user_agent=row[9]
                    )
                    audit_trails.append(audit_entry)

                return audit_trails

            except Exception as e:
                self._logger.error(f"Failed to get audit trails: {e}")
                raise

    def get_log_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Get log statistics for a date range.

        Args:
            start_date: Start date for statistics
            end_date: End date for statistics

        Returns:
            Dictionary with log statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get counts by level and category
                cursor.execute("""
                    SELECT level, category, COUNT(*) as count
                    FROM system_logs
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY level, category
                    ORDER BY count DESC
                """, (start_date.isoformat(), end_date.isoformat()))

                level_category_stats = {}
                for row in cursor.fetchall():
                    level, category, count = row
                    if level not in level_category_stats:
                        level_category_stats[level] = {}
                    level_category_stats[level][category] = count

                # Get total counts by level
                cursor.execute("""
                    SELECT level, COUNT(*) as count
                    FROM system_logs
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY level
                """, (start_date.isoformat(), end_date.isoformat()))

                level_totals = {row[0]: row[1] for row in cursor.fetchall()}

                # Get error trends (hourly)
                cursor.execute("""
                    SELECT strftime('%Y-%m-%d %H:00:00', timestamp) as hour, COUNT(*) as count
                    FROM system_logs
                    WHERE level IN ('error', 'critical')
                    AND timestamp >= ? AND timestamp <= ?
                    GROUP BY hour
                    ORDER BY hour
                """, (start_date.isoformat(), end_date.isoformat()))

                error_trends = [(row[0], row[1]) for row in cursor.fetchall()]

                conn.close()

                return {
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    },
                    'level_totals': level_totals,
                    'level_category_breakdown': level_category_stats,
                    'error_trends': error_trends,
                    'total_logs': sum(level_totals.values())
                }

            except Exception as e:
                self._logger.error(f"Failed to get log statistics: {e}")
                raise

    def _check_log_rotation(self) -> None:
        """Check if log rotation is needed based on database size."""
        try:
            db_path = Path(self._db_path)
            if db_path.exists() and db_path.stat().st_size > self._max_log_size_bytes:
                self._rotate_logs()
        except Exception as e:
            self._logger.error(f"Failed to check log rotation: {e}")

    def _rotate_logs(self) -> None:
        """Rotate logs by archiving old data."""
        try:
            current_time = datetime.now(timezone.utc)
            archive_filename = f"system_logs_{current_time.strftime('%Y%m%d_%H%M%S')}.db.gz"
            archive_path = self._archive_dir / archive_filename

            # Create archive of current database
            with open(self._db_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Clear old logs from current database
            cutoff_time = current_time - timedelta(days=7)  # Keep last 7 days in active DB

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("DELETE FROM system_logs WHERE timestamp < ?", (cutoff_time.isoformat(),))
                deleted_logs = cursor.rowcount

                cursor.execute("DELETE FROM log_statistics WHERE date < ?", (cutoff_time.date().isoformat(),))
                deleted_stats = cursor.rowcount

                # Vacuum to reclaim space
                cursor.execute("VACUUM")

                conn.commit()
                conn.close()

            self._logger.info(f"Log rotation completed: archived {deleted_logs} logs and {deleted_stats} statistics to {archive_filename}")

        except Exception as e:
            self._logger.error(f"Failed to rotate logs: {e}")

    def _cleanup_old_logs(self) -> None:
        """Clean up old logs and archives based on retention policies."""
        try:
            current_time = datetime.now(timezone.utc)

            # Clean up old logs
            log_cutoff = current_time - timedelta(days=self._log_retention_days)
            audit_cutoff = current_time - timedelta(days=self._audit_retention_days)

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Delete old system logs
                cursor.execute("DELETE FROM system_logs WHERE timestamp < ?", (log_cutoff.isoformat(),))
                logs_deleted = cursor.rowcount

                # Delete old audit trails
                cursor.execute("DELETE FROM audit_trails WHERE timestamp < ?", (audit_cutoff.isoformat(),))
                audits_deleted = cursor.rowcount

                conn.commit()
                conn.close()

            # Clean up old archives
            archive_cutoff = current_time - timedelta(days=self._archive_retention_days)
            for archive_file in self._archive_dir.glob("system_logs_*.db.gz"):
                if archive_file.stat().st_mtime < archive_cutoff.timestamp():
                    archive_file.unlink()
                    self._logger.info(f"Deleted old archive: {archive_file.name}")

            if logs_deleted > 0 or audits_deleted > 0:
                self._logger.info(f"Cleaned up {logs_deleted} old logs and {audits_deleted} old audit entries")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old logs: {e}")

    def _update_log_statistics(self) -> None:
        """Update daily log statistics."""
        try:
            current_date = datetime.now(timezone.utc).date()

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get daily statistics
                cursor.execute("""
                    SELECT level, category, COUNT(*) as count
                    FROM system_logs
                    WHERE date(timestamp) = ?
                    GROUP BY level, category
                """, (current_date.isoformat(),))

                stats = cursor.fetchall()

                for level, category, count in stats:
                    # Insert or update statistics
                    stat_id = str(uuid4())
                    cursor.execute("""
                        INSERT OR REPLACE INTO log_statistics (
                            stat_id, date, level, category, count
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (stat_id, current_date.isoformat(), level, category, count))

                conn.commit()
                conn.close()

        except Exception as e:
            self._logger.error(f"Failed to update log statistics: {e}")

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            self._logger.info("SystemLogsDB closed successfully")
        except Exception as e:
            self._logger.error(f"Error closing SystemLogsDB: {e}")
