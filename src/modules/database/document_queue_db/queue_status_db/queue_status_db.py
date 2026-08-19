"""
Module: queue_status_db
Description: Tracks processing status, error logs, and retry attempts
Phase: 3
Location: /src/modules/database/document_queue_db/queue_status_db/
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


class ProcessingStatus(Enum):
    """Processing status types."""
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    RETRYING = "RETRYING"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LogLevel(Enum):
    """Log entry levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class QueueStatusDB:
    """
    Queue status database for processing status tracking and error logging.
    
    Tracks processing status, error logs, and retry attempts with SQLite
    database operations. Provides thread-safe operations with transaction
    support for status tracking, error logging, retry management, and
    comprehensive processing history with performance metrics.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the queue status database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to queue data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "queue"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "queue_status.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Status tracking configuration
        self._max_log_entries = 100000
        self._log_retention_days = 90
        self._error_retention_days = 180
        self._batch_size = 1000
        
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
                
                # Create processing status table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing_status (
                        status_id TEXT PRIMARY KEY,
                        queue_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress_percentage REAL DEFAULT 0.0,
                        current_step TEXT,
                        total_steps INTEGER,
                        processing_start_time TIMESTAMP,
                        processing_end_time TIMESTAMP,
                        processing_duration_seconds REAL,
                        resource_usage TEXT,
                        status_metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_status CHECK (status IN (
                            'STARTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED',
                            'CANCELLED', 'PAUSED', 'RESUMED', 'RETRYING'
                        )),
                        CONSTRAINT valid_progress CHECK (progress_percentage BETWEEN 0.0 AND 100.0)
                    )
                """)
                
                # Create error logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS error_logs (
                        error_id TEXT PRIMARY KEY,
                        queue_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        error_message TEXT NOT NULL,
                        error_details TEXT,
                        stack_trace TEXT,
                        severity TEXT NOT NULL DEFAULT 'MEDIUM',
                        retry_attempt INTEGER DEFAULT 0,
                        is_recoverable BOOLEAN DEFAULT 1,
                        recovery_suggestion TEXT,
                        context_data TEXT,
                        occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
                    )
                """)
                
                # Create retry attempts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retry_attempts (
                        retry_id TEXT PRIMARY KEY,
                        queue_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        retry_reason TEXT,
                        scheduled_at TIMESTAMP NOT NULL,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        status TEXT NOT NULL DEFAULT 'SCHEDULED',
                        error_before_retry TEXT,
                        success_after_retry BOOLEAN,
                        retry_metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_retry_status CHECK (status IN (
                            'SCHEDULED', 'STARTED', 'COMPLETED', 'FAILED', 'CANCELLED'
                        ))
                    )
                """)
                
                # Create processing logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing_logs (
                        log_id TEXT PRIMARY KEY,
                        queue_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        log_level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT,
                        component TEXT,
                        function_name TEXT,
                        line_number INTEGER,
                        execution_time_ms REAL,
                        memory_usage_mb REAL,
                        log_metadata TEXT,
                        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_log_level CHECK (log_level IN (
                            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
                        ))
                    )
                """)
                
                # Create performance metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        metric_id TEXT PRIMARY KEY,
                        queue_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        metric_unit TEXT,
                        measurement_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metric_metadata TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_status_queue
                    ON processing_status(queue_id, status)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_error_logs_queue_severity
                    ON error_logs(queue_id, severity, occurred_at)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retry_attempts_queue
                    ON retry_attempts(queue_id, attempt_number)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_logs_queue_level
                    ON processing_logs(queue_id, log_level, logged_at)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_performance_metrics_queue
                    ON performance_metrics(queue_id, metric_name, measurement_time)
                """)

                # Create triggers for automatic timestamp updates
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_processing_status_timestamp
                    AFTER UPDATE ON processing_status
                    BEGIN
                        UPDATE processing_status
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE status_id = NEW.status_id;
                    END
                """)

                conn.commit()
                self._logger.info("Queue status database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize queue status database: {e}")
                raise
            finally:
                conn.close()

    def update_processing_status(self, queue_id: str, document_id: str, operation: str,
                                status: ProcessingStatus, progress: Optional[float] = None,
                                current_step: Optional[str] = None, total_steps: Optional[int] = None,
                                resource_usage: Optional[Dict[str, Any]] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Update processing status for a queue item.

        Args:
            queue_id: Queue item identifier
            document_id: Document identifier
            operation: Processing operation
            status: Current processing status
            progress: Progress percentage (0-100)
            current_step: Current processing step description
            total_steps: Total number of processing steps
            resource_usage: Resource usage information
            metadata: Additional status metadata

        Returns:
            Status ID for tracking
        """
        status_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate processing duration if completing
                processing_duration = None
                if status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                    cursor.execute("""
                        SELECT processing_start_time FROM processing_status
                        WHERE queue_id = ? AND status = 'STARTED'
                        ORDER BY created_at DESC LIMIT 1
                    """, (queue_id,))

                    start_row = cursor.fetchone()
                    if start_row:
                        start_time = datetime.fromisoformat(start_row[0])
                        end_time = datetime.now(timezone.utc)
                        processing_duration = (end_time - start_time).total_seconds()

                # Insert status update
                cursor.execute("""
                    INSERT INTO processing_status (
                        status_id, queue_id, document_id, operation, status,
                        progress_percentage, current_step, total_steps,
                        processing_start_time, processing_end_time, processing_duration_seconds,
                        resource_usage, status_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    status_id, queue_id, document_id, operation, status.value,
                    progress, current_step, total_steps,
                    datetime.now(timezone.utc).isoformat() if status == ProcessingStatus.STARTED else None,
                    datetime.now(timezone.utc).isoformat() if status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED] else None,
                    processing_duration,
                    json.dumps(resource_usage) if resource_usage else None,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Updated processing status for queue {queue_id}: {status.value}")
                return status_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update processing status for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def log_error(self, queue_id: str, document_id: str, operation: str,
                  error_type: str, error_message: str, error_details: Optional[str] = None,
                  stack_trace: Optional[str] = None, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                  retry_attempt: int = 0, is_recoverable: bool = True,
                  recovery_suggestion: Optional[str] = None,
                  context_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Log an error for a queue item.

        Args:
            queue_id: Queue item identifier
            document_id: Document identifier
            operation: Processing operation
            error_type: Type of error
            error_message: Error message
            error_details: Detailed error information
            stack_trace: Stack trace if available
            severity: Error severity level
            retry_attempt: Current retry attempt number
            is_recoverable: Whether error is recoverable
            recovery_suggestion: Suggested recovery action
            context_data: Additional context information

        Returns:
            Error ID for tracking
        """
        error_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO error_logs (
                        error_id, queue_id, document_id, operation, error_type,
                        error_message, error_details, stack_trace, severity,
                        retry_attempt, is_recoverable, recovery_suggestion, context_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    error_id, queue_id, document_id, operation, error_type,
                    error_message, error_details, stack_trace, severity.value,
                    retry_attempt, is_recoverable, recovery_suggestion,
                    json.dumps(context_data) if context_data else None
                ))

                conn.commit()
                self._logger.error(f"Logged error for queue {queue_id}: {error_type} - {error_message}")
                return error_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log error for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def log_retry_attempt(self, queue_id: str, document_id: str, operation: str,
                         attempt_number: int, retry_reason: str,
                         scheduled_at: datetime, error_before_retry: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a retry attempt for a queue item.

        Args:
            queue_id: Queue item identifier
            document_id: Document identifier
            operation: Processing operation
            attempt_number: Retry attempt number
            retry_reason: Reason for retry
            scheduled_at: When retry is scheduled
            error_before_retry: Error that triggered retry
            metadata: Additional retry metadata

        Returns:
            Retry ID for tracking
        """
        retry_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO retry_attempts (
                        retry_id, queue_id, document_id, operation, attempt_number,
                        retry_reason, scheduled_at, error_before_retry, retry_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    retry_id, queue_id, document_id, operation, attempt_number,
                    retry_reason, scheduled_at.isoformat(), error_before_retry,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Logged retry attempt {attempt_number} for queue {queue_id}")
                return retry_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log retry attempt for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def update_retry_status(self, retry_id: str, status: str, started_at: Optional[datetime] = None,
                           completed_at: Optional[datetime] = None, success: Optional[bool] = None) -> bool:
        """
        Update the status of a retry attempt.

        Args:
            retry_id: Retry attempt identifier
            status: New status
            started_at: When retry started
            completed_at: When retry completed
            success: Whether retry was successful

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE retry_attempts
                    SET status = ?, started_at = ?, completed_at = ?, success_after_retry = ?
                    WHERE retry_id = ?
                """, (
                    status,
                    started_at.isoformat() if started_at else None,
                    completed_at.isoformat() if completed_at else None,
                    success, retry_id
                ))

                success_updated = cursor.rowcount > 0
                conn.commit()

                if success_updated:
                    self._logger.info(f"Updated retry status for {retry_id}: {status}")
                else:
                    self._logger.warning(f"Retry {retry_id} not found for status update")

                return success_updated

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update retry status for {retry_id}: {e}")
                raise
            finally:
                conn.close()

    def log_processing_event(self, queue_id: str, document_id: str, operation: str,
                            log_level: LogLevel, message: str, details: Optional[str] = None,
                            component: Optional[str] = None, function_name: Optional[str] = None,
                            line_number: Optional[int] = None, execution_time_ms: Optional[float] = None,
                            memory_usage_mb: Optional[float] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a processing event.

        Args:
            queue_id: Queue item identifier
            document_id: Document identifier
            operation: Processing operation
            log_level: Log level
            message: Log message
            details: Detailed information
            component: Component name
            function_name: Function name
            line_number: Line number
            execution_time_ms: Execution time in milliseconds
            memory_usage_mb: Memory usage in MB
            metadata: Additional metadata

        Returns:
            Log ID for tracking
        """
        log_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO processing_logs (
                        log_id, queue_id, document_id, operation, log_level,
                        message, details, component, function_name, line_number,
                        execution_time_ms, memory_usage_mb, log_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id, queue_id, document_id, operation, log_level.value,
                    message, details, component, function_name, line_number,
                    execution_time_ms, memory_usage_mb,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                return log_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log processing event for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def record_performance_metric(self, queue_id: str, document_id: str, operation: str,
                                 metric_name: str, metric_value: float, metric_unit: Optional[str] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a performance metric.

        Args:
            queue_id: Queue item identifier
            document_id: Document identifier
            operation: Processing operation
            metric_name: Name of the metric
            metric_value: Metric value
            metric_unit: Unit of measurement
            metadata: Additional metadata

        Returns:
            Metric ID for tracking
        """
        metric_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO performance_metrics (
                        metric_id, queue_id, document_id, operation,
                        metric_name, metric_value, metric_unit, metric_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, queue_id, document_id, operation,
                    metric_name, metric_value, metric_unit,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record performance metric for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def get_processing_status_history(self, queue_id: str) -> List[Dict[str, Any]]:
        """
        Get processing status history for a queue item.

        Args:
            queue_id: Queue item identifier

        Returns:
            List of status history entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status_id, status, progress_percentage, current_step,
                           total_steps, processing_duration_seconds, resource_usage,
                           status_metadata, created_at, updated_at
                    FROM processing_status
                    WHERE queue_id = ?
                    ORDER BY created_at ASC
                """, (queue_id,))

                rows = cursor.fetchall()
                history = []

                for row in rows:
                    resource_usage = json.loads(row[6]) if row[6] else {}
                    metadata = json.loads(row[7]) if row[7] else {}

                    history.append({
                        'status_id': row[0],
                        'status': row[1],
                        'progress_percentage': row[2],
                        'current_step': row[3],
                        'total_steps': row[4],
                        'processing_duration_seconds': row[5],
                        'resource_usage': resource_usage,
                        'metadata': metadata,
                        'created_at': row[8],
                        'updated_at': row[9]
                    })

                return history

            except Exception as e:
                self._logger.error(f"Failed to get processing status history for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def get_error_logs(self, queue_id: Optional[str] = None, severity: Optional[ErrorSeverity] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get error logs with optional filtering.

        Args:
            queue_id: Filter by queue ID
            severity: Filter by error severity
            limit: Maximum number of logs to return

        Returns:
            List of error log entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic query
                where_conditions = []
                params = []

                if queue_id:
                    where_conditions.append("queue_id = ?")
                    params.append(queue_id)

                if severity:
                    where_conditions.append("severity = ?")
                    params.append(severity.value)

                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)

                query = f"""
                    SELECT error_id, queue_id, document_id, operation, error_type,
                           error_message, error_details, severity, retry_attempt,
                           is_recoverable, recovery_suggestion, context_data, occurred_at
                    FROM error_logs
                    {where_clause}
                    ORDER BY occurred_at DESC
                    LIMIT ?
                """
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                logs = []
                for row in rows:
                    context_data = json.loads(row[11]) if row[11] else {}

                    logs.append({
                        'error_id': row[0],
                        'queue_id': row[1],
                        'document_id': row[2],
                        'operation': row[3],
                        'error_type': row[4],
                        'error_message': row[5],
                        'error_details': row[6],
                        'severity': row[7],
                        'retry_attempt': row[8],
                        'is_recoverable': bool(row[9]),
                        'recovery_suggestion': row[10],
                        'context_data': context_data,
                        'occurred_at': row[12]
                    })

                return logs

            except Exception as e:
                self._logger.error(f"Failed to get error logs: {e}")
                raise
            finally:
                conn.close()

    def get_retry_history(self, queue_id: str) -> List[Dict[str, Any]]:
        """
        Get retry history for a queue item.

        Args:
            queue_id: Queue item identifier

        Returns:
            List of retry attempt entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT retry_id, attempt_number, retry_reason, scheduled_at,
                           started_at, completed_at, status, error_before_retry,
                           success_after_retry, retry_metadata, created_at
                    FROM retry_attempts
                    WHERE queue_id = ?
                    ORDER BY attempt_number ASC
                """, (queue_id,))

                rows = cursor.fetchall()
                history = []

                for row in rows:
                    metadata = json.loads(row[9]) if row[9] else {}

                    history.append({
                        'retry_id': row[0],
                        'attempt_number': row[1],
                        'retry_reason': row[2],
                        'scheduled_at': row[3],
                        'started_at': row[4],
                        'completed_at': row[5],
                        'status': row[6],
                        'error_before_retry': row[7],
                        'success_after_retry': bool(row[8]) if row[8] is not None else None,
                        'metadata': metadata,
                        'created_at': row[10]
                    })

                return history

            except Exception as e:
                self._logger.error(f"Failed to get retry history for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def get_performance_metrics(self, queue_id: Optional[str] = None, metric_name: Optional[str] = None,
                               limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get performance metrics with optional filtering.

        Args:
            queue_id: Filter by queue ID
            metric_name: Filter by metric name
            limit: Maximum number of metrics to return

        Returns:
            List of performance metric entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic query
                where_conditions = []
                params = []

                if queue_id:
                    where_conditions.append("queue_id = ?")
                    params.append(queue_id)

                if metric_name:
                    where_conditions.append("metric_name = ?")
                    params.append(metric_name)

                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)

                query = f"""
                    SELECT metric_id, queue_id, document_id, operation,
                           metric_name, metric_value, metric_unit,
                           measurement_time, metric_metadata
                    FROM performance_metrics
                    {where_clause}
                    ORDER BY measurement_time DESC
                    LIMIT ?
                """
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                metrics = []
                for row in rows:
                    metadata = json.loads(row[8]) if row[8] else {}

                    metrics.append({
                        'metric_id': row[0],
                        'queue_id': row[1],
                        'document_id': row[2],
                        'operation': row[3],
                        'metric_name': row[4],
                        'metric_value': row[5],
                        'metric_unit': row[6],
                        'measurement_time': row[7],
                        'metadata': metadata
                    })

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get performance metrics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_logs(self, older_than_days: int = 90) -> Dict[str, int]:
        """
        Clean up old log entries.

        Args:
            older_than_days: Remove logs older than this many days

        Returns:
            Dictionary with cleanup counts by table
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        cleanup_counts = {}

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up processing logs
                cursor.execute("""
                    DELETE FROM processing_logs
                    WHERE logged_at < ?
                """, (cutoff_date.isoformat(),))
                cleanup_counts['processing_logs'] = cursor.rowcount

                # Clean up performance metrics
                cursor.execute("""
                    DELETE FROM performance_metrics
                    WHERE measurement_time < ?
                """, (cutoff_date.isoformat(),))
                cleanup_counts['performance_metrics'] = cursor.rowcount

                # Clean up old processing status (keep recent ones)
                cursor.execute("""
                    DELETE FROM processing_status
                    WHERE created_at < ? AND status IN ('COMPLETED', 'FAILED', 'CANCELLED')
                """, (cutoff_date.isoformat(),))
                cleanup_counts['processing_status'] = cursor.rowcount

                # Clean up old retry attempts
                cursor.execute("""
                    DELETE FROM retry_attempts
                    WHERE created_at < ? AND status IN ('COMPLETED', 'FAILED', 'CANCELLED')
                """, (cutoff_date.isoformat(),))
                cleanup_counts['retry_attempts'] = cursor.rowcount

                conn.commit()

                total_cleaned = sum(cleanup_counts.values())
                self._logger.info(f"Cleaned up {total_cleaned} old log entries")
                return cleanup_counts

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old logs: {e}")
                raise
            finally:
                conn.close()

    def get_status_summary(self, queue_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive status summary.

        Args:
            queue_id: Filter by specific queue ID (None for all)

        Returns:
            Dictionary with status summary information
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                where_clause = "WHERE queue_id = ?" if queue_id else ""
                params = [queue_id] if queue_id else []

                # Get status distribution
                cursor.execute(f"""
                    SELECT status, COUNT(*)
                    FROM processing_status
                    {where_clause}
                    GROUP BY status
                """, params)
                status_counts = dict(cursor.fetchall())

                # Get error severity distribution
                cursor.execute(f"""
                    SELECT severity, COUNT(*)
                    FROM error_logs
                    {where_clause}
                    GROUP BY severity
                """, params)
                error_severity_counts = dict(cursor.fetchall())

                # Get retry statistics
                cursor.execute(f"""
                    SELECT AVG(attempt_number), MAX(attempt_number), COUNT(*)
                    FROM retry_attempts
                    {where_clause}
                """, params)
                retry_stats = cursor.fetchone()

                # Get recent activity
                recent_where = where_clause + (" AND " if where_clause else "WHERE ") + "created_at > ?"
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM processing_status
                    {recent_where}
                """, params + [datetime.now(timezone.utc) - timedelta(hours=24)])
                recent_activity = cursor.fetchone()[0]

                return {
                    'status_counts': status_counts,
                    'error_severity_counts': error_severity_counts,
                    'retry_statistics': {
                        'average_attempts': retry_stats[0] or 0,
                        'max_attempts': retry_stats[1] or 0,
                        'total_retries': retry_stats[2] or 0
                    },
                    'recent_activity_24h': recent_activity,
                    'summary_generated_at': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                self._logger.error(f"Failed to get status summary: {e}")
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("Queue status database closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
