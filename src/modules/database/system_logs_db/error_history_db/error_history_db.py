"""
Module: error_history_db
Description: Persists error occurrences and recovery attempts with detailed error tracking and analysis for system reliability monitoring
Phase: 4
Location: /src/modules/database/system_logs_db/error_history_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ErrorSeverity(Enum):
    """Error severity enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class ErrorCategory(Enum):
    """Error category enumeration."""
    SYSTEM = "SYSTEM"
    APPLICATION = "APPLICATION"
    DATABASE = "DATABASE"
    NETWORK = "NETWORK"
    MEMORY = "MEMORY"
    DISK = "DISK"
    SECURITY = "SECURITY"
    VALIDATION = "VALIDATION"
    CONFIGURATION = "CONFIGURATION"
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"
    DATA_PROCESSING = "DATA_PROCESSING"
    USER_INPUT = "USER_INPUT"


class ErrorStatus(Enum):
    """Error status enumeration."""
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    RECURRING = "RECURRING"
    IGNORED = "IGNORED"


class RecoveryAction(Enum):
    """Recovery action enumeration."""
    NONE = "NONE"
    RETRY = "RETRY"
    RESTART = "RESTART"
    FALLBACK = "FALLBACK"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    SYSTEM_RECOVERY = "SYSTEM_RECOVERY"
    DATA_RECOVERY = "DATA_RECOVERY"
    CONFIGURATION_RESET = "CONFIGURATION_RESET"


@dataclass
class ErrorEntry:
    """Error entry data structure."""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    status: ErrorStatus
    error_code: Optional[str]
    error_message: str
    stack_trace: Optional[str]
    source_module: str
    source_function: Optional[str]
    source_line: Optional[int]
    context: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    recovery_action: Optional[RecoveryAction] = None
    recovery_attempts: int = 0
    recovery_successful: bool = False
    resolution_notes: Optional[str] = None
    first_occurrence: Optional[datetime] = None
    last_occurrence: Optional[datetime] = None
    occurrence_count: int = 1


@dataclass
class RecoveryAttempt:
    """Recovery attempt data structure."""
    attempt_id: str
    error_id: str
    timestamp: datetime
    action: RecoveryAction
    success: bool
    duration_seconds: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ErrorHistoryDB:
    """
    Error history database manager.
    
    Persists error occurrences and recovery attempts with detailed tracking,
    analysis capabilities, and automated recovery coordination for comprehensive
    system reliability monitoring and incident management.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the error history database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to system logs data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "system_logs"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "error_history.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._detailed_retention_days = 90  # Keep detailed errors for 90 days
        self._summary_retention_months = 24  # Keep summaries for 24 months
        self._critical_retention_years = 5   # Keep critical errors for 5 years
        
        # Error tracking settings
        self._duplicate_threshold_minutes = 5  # Consider errors duplicates within 5 minutes
        self._auto_recovery_enabled = True
        self._max_recovery_attempts = 3
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Create error entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_entries (
                    error_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT,
                    source_module TEXT NOT NULL,
                    source_function TEXT,
                    source_line INTEGER,
                    context TEXT,
                    user_id TEXT,
                    session_id TEXT,
                    correlation_id TEXT,
                    recovery_action TEXT,
                    recovery_attempts INTEGER NOT NULL DEFAULT 0,
                    recovery_successful INTEGER NOT NULL DEFAULT 0,
                    resolution_notes TEXT,
                    first_occurrence TEXT NOT NULL,
                    last_occurrence TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create recovery attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    error_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL,
                    details TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (error_id) REFERENCES error_entries (error_id)
                )
            """)
            
            # Create error patterns table for analysis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_hash TEXT NOT NULL UNIQUE,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    error_signature TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    resolution_rate REAL NOT NULL DEFAULT 0.0,
                    avg_recovery_time_seconds REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create error summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_summaries (
                    summary_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    resolved_count INTEGER NOT NULL DEFAULT 0,
                    avg_resolution_time_seconds REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_timestamp ON error_entries(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_severity ON error_entries(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_category ON error_entries(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_status ON error_entries(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_source_module ON error_entries(source_module)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_user_id ON error_entries(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_session_id ON error_entries(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_entries_correlation_id ON error_entries(correlation_id)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_attempts_error_id ON recovery_attempts(error_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_attempts_timestamp ON recovery_attempts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_attempts_action ON recovery_attempts(action)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_patterns_pattern_hash ON error_patterns(pattern_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_patterns_category ON error_patterns(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_patterns_severity ON error_patterns(severity)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_summaries_date_hour ON error_summaries(date, hour)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_summaries_severity ON error_summaries(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_summaries_category ON error_summaries(category)")
            
            conn.commit()
            conn.close()
            
            self._logger.info("Error history database initialized successfully")
    
    def _generate_error_signature(self, error_message: str, source_module: str,
                                 source_function: Optional[str] = None) -> str:
        """Generate a signature for error pattern matching."""
        # Create a normalized signature for pattern matching
        signature_parts = [
            source_module,
            source_function or "unknown",
            # Normalize error message by removing dynamic parts
            error_message.split(':')[0] if ':' in error_message else error_message
        ]
        return "|".join(signature_parts).lower()
    
    def _calculate_pattern_hash(self, signature: str, severity: str, category: str) -> str:
        """Calculate hash for error pattern identification."""
        import hashlib
        pattern_string = f"{signature}|{severity}|{category}"
        return hashlib.md5(pattern_string.encode('utf-8')).hexdigest()
    
    def log_error(self, severity: ErrorSeverity, category: ErrorCategory,
                  error_message: str, source_module: str,
                  error_code: Optional[str] = None,
                  stack_trace: Optional[str] = None,
                  source_function: Optional[str] = None,
                  source_line: Optional[int] = None,
                  context: Optional[Dict[str, Any]] = None,
                  user_id: Optional[str] = None,
                  session_id: Optional[str] = None,
                  correlation_id: Optional[str] = None) -> str:
        """
        Log a new error occurrence.
        
        Args:
            severity: Error severity level
            category: Error category
            error_message: Error message
            source_module: Source module where error occurred
            error_code: Optional error code
            stack_trace: Optional stack trace
            source_function: Optional source function
            source_line: Optional source line number
            context: Optional additional context
            user_id: Optional user ID
            session_id: Optional session ID
            correlation_id: Optional correlation ID for tracking related events
            
        Returns:
            Error entry ID
        """
        error_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Generate error signature for pattern matching
        signature = self._generate_error_signature(error_message, source_module, source_function)
        pattern_hash = self._calculate_pattern_hash(signature, severity.value, category.value)
        
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                
                # Check for duplicate errors within threshold
                threshold_time = timestamp - timedelta(minutes=self._duplicate_threshold_minutes)
                cursor.execute("""
                    SELECT error_id, occurrence_count FROM error_entries
                    WHERE source_module = ? AND error_message = ? AND timestamp > ?
                    ORDER BY timestamp DESC LIMIT 1
                """, (source_module, error_message, threshold_time.isoformat()))
                
                duplicate = cursor.fetchone()
                
                if duplicate:
                    # Update existing error
                    existing_error_id, count = duplicate
                    cursor.execute("""
                        UPDATE error_entries
                        SET last_occurrence = ?, occurrence_count = ?, status = ?
                        WHERE error_id = ?
                    """, (timestamp.isoformat(), count + 1, ErrorStatus.RECURRING.value, existing_error_id))
                    
                    conn.commit()
                    conn.close()
                    
                    self._logger.info(f"Updated recurring error {existing_error_id} (count: {count + 1})")
                    return existing_error_id
                
                # Create new error entry
                cursor.execute("""
                    INSERT INTO error_entries (
                        error_id, timestamp, severity, category, status, error_code,
                        error_message, stack_trace, source_module, source_function,
                        source_line, context, user_id, session_id, correlation_id,
                        first_occurrence, last_occurrence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    error_id, timestamp.isoformat(), severity.value, category.value,
                    ErrorStatus.NEW.value, error_code, error_message, stack_trace,
                    source_module, source_function, source_line,
                    json.dumps(context) if context else None,
                    user_id, session_id, correlation_id,
                    timestamp.isoformat(), timestamp.isoformat()
                ))
                
                # Update error pattern
                self._update_error_pattern(cursor, pattern_hash, signature, severity, category, timestamp)
                
                # Update summary
                self._update_error_summary(cursor, timestamp, severity, category)
                
                conn.commit()
                conn.close()
                
                self._logger.error(f"Logged {severity.value} error {error_id}: {error_message}")
                
                # Trigger auto-recovery if enabled and appropriate
                if self._auto_recovery_enabled and severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                    self._attempt_auto_recovery(error_id, category)
                
                return error_id
                
            except Exception as e:
                self._logger.error(f"Failed to log error: {e}")
                raise

    def _update_error_pattern(self, cursor: sqlite3.Cursor, pattern_hash: str,
                             signature: str, severity: ErrorSeverity,
                             category: ErrorCategory, timestamp: datetime) -> None:
        """Update error pattern statistics."""
        # Check if pattern exists
        cursor.execute("""
            SELECT occurrence_count FROM error_patterns
            WHERE pattern_hash = ?
        """, (pattern_hash,))

        result = cursor.fetchone()

        if result:
            # Update existing pattern
            count = result[0]
            cursor.execute("""
                UPDATE error_patterns
                SET occurrence_count = ?, last_seen = ?
                WHERE pattern_hash = ?
            """, (count + 1, timestamp.isoformat(), pattern_hash))
        else:
            # Create new pattern
            pattern_id = str(uuid4())
            cursor.execute("""
                INSERT INTO error_patterns (
                    pattern_id, pattern_hash, severity, category, error_signature,
                    first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern_id, pattern_hash, severity.value, category.value,
                signature, timestamp.isoformat(), timestamp.isoformat()
            ))

    def _update_error_summary(self, cursor: sqlite3.Cursor, timestamp: datetime,
                             severity: ErrorSeverity, category: ErrorCategory) -> None:
        """Update error summary statistics."""
        date_str = timestamp.date().isoformat()
        hour = timestamp.hour
        summary_id = f"{date_str}_{hour}_{severity.value}_{category.value}"

        # Check if summary exists
        cursor.execute("""
            SELECT count FROM error_summaries
            WHERE summary_id = ?
        """, (summary_id,))

        result = cursor.fetchone()

        if result:
            # Update existing summary
            count = result[0]
            cursor.execute("""
                UPDATE error_summaries
                SET count = ?
                WHERE summary_id = ?
            """, (count + 1, summary_id))
        else:
            # Create new summary
            cursor.execute("""
                INSERT INTO error_summaries (
                    summary_id, date, hour, severity, category, count
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (summary_id, date_str, hour, severity.value, category.value, 1))

    def _attempt_auto_recovery(self, error_id: str, category: ErrorCategory) -> None:
        """Attempt automatic recovery for the error."""
        try:
            # Determine recovery action based on category
            recovery_action = RecoveryAction.NONE

            if category == ErrorCategory.MEMORY:
                recovery_action = RecoveryAction.SYSTEM_RECOVERY
            elif category == ErrorCategory.DATABASE:
                recovery_action = RecoveryAction.RETRY
            elif category == ErrorCategory.NETWORK:
                recovery_action = RecoveryAction.RETRY
            elif category == ErrorCategory.CONFIGURATION:
                recovery_action = RecoveryAction.CONFIGURATION_RESET
            elif category in [ErrorCategory.TRAINING, ErrorCategory.INFERENCE]:
                recovery_action = RecoveryAction.RESTART

            if recovery_action != RecoveryAction.NONE:
                self.log_recovery_attempt(error_id, recovery_action, success=False,
                                        details={'auto_recovery': True, 'category': category.value})

        except Exception as e:
            self._logger.error(f"Auto-recovery attempt failed for error {error_id}: {e}")

    def log_recovery_attempt(self, error_id: str, action: RecoveryAction,
                           success: bool, duration_seconds: Optional[float] = None,
                           details: Optional[Dict[str, Any]] = None,
                           error_message: Optional[str] = None) -> str:
        """
        Log a recovery attempt for an error.

        Args:
            error_id: ID of the error being recovered
            action: Recovery action taken
            success: Whether the recovery was successful
            duration_seconds: Optional duration of recovery attempt
            details: Optional additional details
            error_message: Optional error message if recovery failed

        Returns:
            Recovery attempt ID
        """
        attempt_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Log recovery attempt
                cursor.execute("""
                    INSERT INTO recovery_attempts (
                        attempt_id, error_id, timestamp, action, success,
                        duration_seconds, details, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt_id, error_id, timestamp.isoformat(), action.value,
                    1 if success else 0, duration_seconds,
                    json.dumps(details) if details else None, error_message
                ))

                # Update error entry
                cursor.execute("""
                    UPDATE error_entries
                    SET recovery_attempts = recovery_attempts + 1,
                        recovery_successful = ?,
                        recovery_action = ?,
                        status = ?
                    WHERE error_id = ?
                """, (
                    1 if success else 0, action.value,
                    ErrorStatus.RESOLVED.value if success else ErrorStatus.IN_PROGRESS.value,
                    error_id
                ))

                conn.commit()
                conn.close()

                status = "SUCCESS" if success else "FAILURE"
                self._logger.info(f"Recovery attempt {attempt_id} [{status}]: {action.value} for error {error_id}")

                return attempt_id

            except Exception as e:
                self._logger.error(f"Failed to log recovery attempt: {e}")
                raise

    def get_error_entries(self, start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         severity: Optional[ErrorSeverity] = None,
                         category: Optional[ErrorCategory] = None,
                         status: Optional[ErrorStatus] = None,
                         source_module: Optional[str] = None,
                         user_id: Optional[str] = None,
                         session_id: Optional[str] = None,
                         correlation_id: Optional[str] = None,
                         limit: int = 1000) -> List[ErrorEntry]:
        """
        Retrieve error entries with filtering options.

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            severity: Optional severity filter
            category: Optional category filter
            status: Optional status filter
            source_module: Optional source module filter
            user_id: Optional user ID filter
            session_id: Optional session ID filter
            correlation_id: Optional correlation ID filter
            limit: Maximum number of entries to return

        Returns:
            List of error entries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Build query with filters
                query = "SELECT * FROM error_entries WHERE 1=1"
                params = []

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                if severity:
                    query += " AND severity = ?"
                    params.append(severity.value)

                if category:
                    query += " AND category = ?"
                    params.append(category.value)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                if source_module:
                    query += " AND source_module = ?"
                    params.append(source_module)

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

                # Convert rows to ErrorEntry objects
                entries = []
                for row in rows:
                    entry = ErrorEntry(
                        error_id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        severity=ErrorSeverity(row[2]),
                        category=ErrorCategory(row[3]),
                        status=ErrorStatus(row[4]),
                        error_code=row[5],
                        error_message=row[6],
                        stack_trace=row[7],
                        source_module=row[8],
                        source_function=row[9],
                        source_line=row[10],
                        context=json.loads(row[11]) if row[11] else None,
                        user_id=row[12],
                        session_id=row[13],
                        correlation_id=row[14],
                        recovery_action=RecoveryAction(row[15]) if row[15] else None,
                        recovery_attempts=row[16],
                        recovery_successful=bool(row[17]),
                        resolution_notes=row[18],
                        first_occurrence=datetime.fromisoformat(row[19]),
                        last_occurrence=datetime.fromisoformat(row[20]),
                        occurrence_count=row[21]
                    )
                    entries.append(entry)

                return entries

            except Exception as e:
                self._logger.error(f"Failed to get error entries: {e}")
                raise

    def get_error_patterns(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get error patterns for analysis.

        Args:
            limit: Maximum number of patterns to return

        Returns:
            List of error pattern dictionaries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM error_patterns
                    ORDER BY occurrence_count DESC, last_seen DESC
                    LIMIT ?
                """, (limit,))

                rows = cursor.fetchall()
                conn.close()

                patterns = []
                for row in rows:
                    pattern = {
                        'pattern_id': row[0],
                        'pattern_hash': row[1],
                        'severity': row[2],
                        'category': row[3],
                        'error_signature': row[4],
                        'occurrence_count': row[5],
                        'first_seen': row[6],
                        'last_seen': row[7],
                        'resolution_rate': row[8],
                        'avg_recovery_time_seconds': row[9]
                    }
                    patterns.append(pattern)

                return patterns

            except Exception as e:
                self._logger.error(f"Failed to get error patterns: {e}")
                raise

    def get_recovery_attempts(self, error_id: Optional[str] = None,
                            action: Optional[RecoveryAction] = None,
                            success_only: Optional[bool] = None,
                            limit: int = 100) -> List[RecoveryAttempt]:
        """
        Get recovery attempts with filtering options.

        Args:
            error_id: Optional error ID filter
            action: Optional recovery action filter
            success_only: Optional filter for successful attempts only
            limit: Maximum number of attempts to return

        Returns:
            List of recovery attempts
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = "SELECT * FROM recovery_attempts WHERE 1=1"
                params = []

                if error_id:
                    query += " AND error_id = ?"
                    params.append(error_id)

                if action:
                    query += " AND action = ?"
                    params.append(action.value)

                if success_only is not None:
                    query += " AND success = ?"
                    params.append(1 if success_only else 0)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                attempts = []
                for row in rows:
                    attempt = RecoveryAttempt(
                        attempt_id=row[0],
                        error_id=row[1],
                        timestamp=datetime.fromisoformat(row[2]),
                        action=RecoveryAction(row[3]),
                        success=bool(row[4]),
                        duration_seconds=row[5],
                        details=json.loads(row[6]) if row[6] else None,
                        error_message=row[7]
                    )
                    attempts.append(attempt)

                return attempts

            except Exception as e:
                self._logger.error(f"Failed to get recovery attempts: {e}")
                raise

    def update_error_status(self, error_id: str, status: ErrorStatus,
                           resolution_notes: Optional[str] = None) -> bool:
        """
        Update error status and resolution notes.

        Args:
            error_id: Error ID to update
            status: New status
            resolution_notes: Optional resolution notes

        Returns:
            True if update was successful
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE error_entries
                    SET status = ?, resolution_notes = ?
                    WHERE error_id = ?
                """, (status.value, resolution_notes, error_id))

                updated = cursor.rowcount > 0
                conn.commit()
                conn.close()

                if updated:
                    self._logger.info(f"Updated error {error_id} status to {status.value}")

                return updated

            except Exception as e:
                self._logger.error(f"Failed to update error status: {e}")
                raise

    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive error statistics.

        Returns:
            Error statistics dictionary
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Total error counts by severity
                cursor.execute("""
                    SELECT severity, COUNT(*) as count
                    FROM error_entries
                    GROUP BY severity
                """)
                severity_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Total error counts by category
                cursor.execute("""
                    SELECT category, COUNT(*) as count
                    FROM error_entries
                    GROUP BY category
                """)
                category_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Resolution statistics
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM error_entries
                    GROUP BY status
                """)
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Recovery success rate
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_attempts,
                        SUM(success) as successful_attempts
                    FROM recovery_attempts
                """)
                result = cursor.fetchone()
                total_attempts = result[0] if result else 0
                successful_attempts = result[1] if result else 0
                recovery_success_rate = successful_attempts / total_attempts if total_attempts > 0 else 0

                # Top error patterns
                cursor.execute("""
                    SELECT error_signature, occurrence_count
                    FROM error_patterns
                    ORDER BY occurrence_count DESC
                    LIMIT 10
                """)
                top_patterns = [{'signature': row[0], 'count': row[1]} for row in cursor.fetchall()]

                # Recent error trends (last 24 hours)
                recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                cursor.execute("""
                    SELECT COUNT(*) FROM error_entries
                    WHERE timestamp > ?
                """, (recent_cutoff.isoformat(),))
                recent_errors = cursor.fetchone()[0]

                # Database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                db_size_mb = (page_count * page_size) / (1024 * 1024)

                conn.close()

                return {
                    'severity_counts': severity_counts,
                    'category_counts': category_counts,
                    'status_counts': status_counts,
                    'total_errors': sum(severity_counts.values()),
                    'recovery_success_rate': recovery_success_rate,
                    'total_recovery_attempts': total_attempts,
                    'successful_recovery_attempts': successful_attempts,
                    'top_error_patterns': top_patterns,
                    'recent_errors_24h': recent_errors,
                    'database_size_mb': db_size_mb,
                    'retention_days': self._detailed_retention_days,
                    'auto_recovery_enabled': self._auto_recovery_enabled
                }

            except Exception as e:
                self._logger.error(f"Failed to get error statistics: {e}")
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

                # Clean up old error entries (except critical ones)
                retention_cutoff = datetime.now(timezone.utc) - timedelta(days=self._detailed_retention_days)
                critical_cutoff = datetime.now(timezone.utc) - timedelta(days=self._critical_retention_years * 365)

                # Delete non-critical old errors
                cursor.execute("""
                    DELETE FROM error_entries
                    WHERE timestamp < ? AND severity NOT IN ('CRITICAL', 'FATAL')
                """, (retention_cutoff.isoformat(),))
                deleted_entries = cursor.rowcount

                # Delete very old critical errors
                cursor.execute("""
                    DELETE FROM error_entries
                    WHERE timestamp < ?
                """, (critical_cutoff.isoformat(),))
                deleted_critical = cursor.rowcount

                # Clean up old recovery attempts
                cursor.execute("""
                    DELETE FROM recovery_attempts
                    WHERE timestamp < ?
                """, (retention_cutoff.isoformat(),))
                deleted_attempts = cursor.rowcount

                # Clean up old summaries
                summary_cutoff = datetime.now(timezone.utc) - timedelta(days=self._summary_retention_months * 30)
                cursor.execute("""
                    DELETE FROM error_summaries
                    WHERE date < ?
                """, (summary_cutoff.date().isoformat(),))
                deleted_summaries = cursor.rowcount

                conn.commit()
                conn.close()

                stats = {
                    'deleted_entries': deleted_entries,
                    'deleted_critical': deleted_critical,
                    'deleted_attempts': deleted_attempts,
                    'deleted_summaries': deleted_summaries
                }

                self._logger.info(f"Cleanup completed: {deleted_entries + deleted_critical} entries, {deleted_attempts} attempts, {deleted_summaries} summaries deleted")
                return stats

            except Exception as e:
                self._logger.error(f"Failed to cleanup old data: {e}")
                raise
