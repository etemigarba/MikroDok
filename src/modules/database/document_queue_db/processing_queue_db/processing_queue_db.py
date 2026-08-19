"""
Module: processing_queue_db
Description: Manages document processing queue with priority and retry mechanisms
Phase: 3
Location: /src/modules/database/document_queue_db/processing_queue_db/
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


class QueuePriority(Enum):
    """Document processing queue priority levels."""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class QueueStatus(Enum):
    """Document processing queue status."""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    RETRY = "RETRY"


class OperationType(Enum):
    """Document processing operation types."""
    INGEST = "INGEST"
    CHUNK = "CHUNK"
    EMBED = "EMBED"
    EXTRACT = "EXTRACT"
    VALIDATE = "VALIDATE"
    INDEX = "INDEX"
    ANALYZE = "ANALYZE"


class ProcessingQueueDB:
    """
    Processing queue database for document processing workflow management.
    
    Manages document processing queue with priority and retry mechanisms
    using SQLite database operations. Provides thread-safe operations
    with transaction support for queue management, priority scheduling,
    retry logic, and processing workflow coordination.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the processing queue database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to queue data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "queue"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "processing_queue.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Queue configuration
        self._max_retry_count = 3
        self._retry_delay_minutes = [5, 15, 60]  # Progressive delay
        self._max_queue_size = 10000
        self._batch_size = 100
        
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
                
                # Create processing queue table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing_queue (
                        queue_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        priority INTEGER DEFAULT 3,
                        operation TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        scheduled_at TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_details TEXT,
                        processing_metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 5),
                        CONSTRAINT valid_status CHECK (status IN (
                            'PENDING', 'QUEUED', 'PROCESSING', 'COMPLETED', 
                            'FAILED', 'CANCELLED', 'PAUSED', 'RETRY'
                        )),
                        CONSTRAINT valid_operation CHECK (operation IN (
                            'INGEST', 'CHUNK', 'EMBED', 'EXTRACT', 
                            'VALIDATE', 'INDEX', 'ANALYZE'
                        ))
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_queue_status_priority 
                    ON processing_queue(status, priority, scheduled_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_queue_document 
                    ON processing_queue(document_id, operation)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_queue_scheduled 
                    ON processing_queue(scheduled_at) 
                    WHERE status IN ('PENDING', 'QUEUED', 'RETRY')
                """)
                
                # Create queue statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS queue_statistics (
                        stat_id TEXT PRIMARY KEY,
                        operation_type TEXT NOT NULL,
                        total_queued INTEGER DEFAULT 0,
                        total_processed INTEGER DEFAULT 0,
                        total_failed INTEGER DEFAULT 0,
                        average_processing_time_seconds REAL DEFAULT 0.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create queue configuration table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS queue_configuration (
                        config_key TEXT PRIMARY KEY,
                        config_value TEXT NOT NULL,
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert default configuration
                cursor.execute("""
                    INSERT OR IGNORE INTO queue_configuration 
                    (config_key, config_value, description) VALUES
                    ('max_retry_count', '3', 'Maximum number of retry attempts'),
                    ('max_queue_size', '10000', 'Maximum queue size'),
                    ('batch_size', '100', 'Processing batch size'),
                    ('retry_delay_base_minutes', '5', 'Base retry delay in minutes')
                """)
                
                # Create triggers for automatic timestamp updates
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_processing_queue_timestamp
                    AFTER UPDATE ON processing_queue
                    BEGIN
                        UPDATE processing_queue 
                        SET updated_at = CURRENT_TIMESTAMP 
                        WHERE queue_id = NEW.queue_id;
                    END
                """)
                
                conn.commit()
                self._logger.info("Processing queue database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize processing queue database: {e}")
                raise
            finally:
                conn.close()

    def enqueue_document(self, document_id: str, operation: OperationType,
                        priority: QueuePriority = QueuePriority.NORMAL,
                        scheduled_at: Optional[datetime] = None,
                        metadata: Optional[Dict[str, Any]] = None,
                        max_retries: Optional[int] = None) -> str:
        """
        Add a document to the processing queue.

        Args:
            document_id: Document identifier
            operation: Processing operation type
            priority: Queue priority level
            scheduled_at: Scheduled processing time (None for immediate)
            metadata: Additional processing metadata
            max_retries: Maximum retry attempts (None for default)

        Returns:
            Queue ID for tracking

        Raises:
            ValueError: If queue is full or invalid parameters
        """
        queue_id = str(uuid.uuid4())

        if scheduled_at is None:
            scheduled_at = datetime.now(timezone.utc)

        if max_retries is None:
            max_retries = self._max_retry_count

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check queue size limit
                cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE status NOT IN ('COMPLETED', 'CANCELLED')")
                current_size = cursor.fetchone()[0]

                if current_size >= self._max_queue_size:
                    raise ValueError(f"Queue is full (max size: {self._max_queue_size})")

                # Check for duplicate operations
                cursor.execute("""
                    SELECT queue_id FROM processing_queue
                    WHERE document_id = ? AND operation = ?
                    AND status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
                """, (document_id, operation.value))

                existing = cursor.fetchone()
                if existing:
                    self._logger.warning(f"Document {document_id} already queued for {operation.value}")
                    return existing[0]

                # Insert queue entry
                cursor.execute("""
                    INSERT INTO processing_queue (
                        queue_id, document_id, priority, operation, status,
                        scheduled_at, max_retries, processing_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    queue_id, document_id, priority.value, operation.value,
                    QueueStatus.PENDING.value, scheduled_at.isoformat(),
                    max_retries, json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Enqueued document {document_id} for {operation.value} with priority {priority.value}")
                return queue_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to enqueue document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def dequeue_next(self, operation_types: Optional[List[OperationType]] = None,
                    max_items: int = 1) -> List[Dict[str, Any]]:
        """
        Get next items from the queue for processing.

        Args:
            operation_types: Filter by operation types (None for all)
            max_items: Maximum number of items to dequeue

        Returns:
            List of queue items ready for processing
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with optional operation filter
                where_clause = "WHERE status IN ('PENDING', 'QUEUED', 'RETRY') AND scheduled_at <= ?"
                params = [datetime.now(timezone.utc).isoformat()]

                if operation_types:
                    operation_values = [op.value for op in operation_types]
                    placeholders = ','.join(['?' for _ in operation_values])
                    where_clause += f" AND operation IN ({placeholders})"
                    params.extend(operation_values)

                query = f"""
                    SELECT queue_id, document_id, priority, operation, status,
                           retry_count, max_retries, scheduled_at, processing_metadata
                    FROM processing_queue
                    {where_clause}
                    ORDER BY priority ASC, scheduled_at ASC
                    LIMIT ?
                """
                params.append(max_items)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                if not rows:
                    return []

                # Mark items as processing
                queue_ids = [row[0] for row in rows]
                placeholders = ','.join(['?' for _ in queue_ids])

                cursor.execute(f"""
                    UPDATE processing_queue
                    SET status = ?, started_at = ?
                    WHERE queue_id IN ({placeholders})
                """, [QueueStatus.PROCESSING.value, datetime.now(timezone.utc).isoformat()] + queue_ids)

                conn.commit()

                # Convert to dictionaries
                items = []
                for row in rows:
                    metadata = json.loads(row[8]) if row[8] else {}
                    items.append({
                        'queue_id': row[0],
                        'document_id': row[1],
                        'priority': row[2],
                        'operation': row[3],
                        'status': QueueStatus.PROCESSING.value,
                        'retry_count': row[5],
                        'max_retries': row[6],
                        'scheduled_at': row[7],
                        'metadata': metadata
                    })

                self._logger.info(f"Dequeued {len(items)} items for processing")
                return items

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to dequeue items: {e}")
                raise
            finally:
                conn.close()

    def complete_processing(self, queue_id: str, success: bool = True,
                           error_details: Optional[str] = None,
                           processing_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a queue item as completed or failed.

        Args:
            queue_id: Queue item identifier
            success: Whether processing was successful
            error_details: Error information if failed
            processing_metadata: Additional processing metadata

        Returns:
            True if status updated successfully
        """
        status = QueueStatus.COMPLETED if success else QueueStatus.FAILED

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update queue item status - allow completion from PROCESSING or PENDING states
                cursor.execute("""
                    UPDATE processing_queue
                    SET status = ?, completed_at = ?, error_details = ?, processing_metadata = ?,
                        started_at = COALESCE(started_at, ?)
                    WHERE queue_id = ? AND status IN (?, ?)
                """, (
                    status.value, datetime.now(timezone.utc).isoformat(),
                    error_details, json.dumps(processing_metadata) if processing_metadata else None,
                    datetime.now(timezone.utc).isoformat(),  # Set started_at if not already set
                    queue_id, QueueStatus.PROCESSING.value, QueueStatus.PENDING.value
                ))

                if cursor.rowcount == 0:
                    self._logger.warning(f"Queue item {queue_id} not found or not in processable state")
                    return False

                # If failed and retries available, schedule retry
                if not success:
                    cursor.execute("""
                        SELECT retry_count, max_retries FROM processing_queue
                        WHERE queue_id = ?
                    """, (queue_id,))

                    row = cursor.fetchone()
                    if row and row[0] < row[1]:  # retry_count < max_retries
                        retry_count = row[0] + 1
                        retry_delay = self._calculate_retry_delay(retry_count)
                        scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=retry_delay)

                        cursor.execute("""
                            UPDATE processing_queue
                            SET status = ?, retry_count = ?, scheduled_at = ?, started_at = NULL
                            WHERE queue_id = ?
                        """, (QueueStatus.RETRY.value, retry_count, scheduled_at.isoformat(), queue_id))

                        self._logger.info(f"Scheduled retry {retry_count} for queue item {queue_id} at {scheduled_at}")

                conn.commit()
                self._logger.info(f"Queue item {queue_id} marked as {status.value}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to complete processing for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def _calculate_retry_delay(self, retry_count: int) -> int:
        """
        Calculate retry delay in minutes based on retry count.

        Args:
            retry_count: Current retry attempt number

        Returns:
            Delay in minutes
        """
        if retry_count <= len(self._retry_delay_minutes):
            return self._retry_delay_minutes[retry_count - 1]
        else:
            # Exponential backoff for higher retry counts
            return self._retry_delay_minutes[-1] * (2 ** (retry_count - len(self._retry_delay_minutes)))

    def cancel_queue_item(self, queue_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel a queue item.

        Args:
            queue_id: Queue item identifier
            reason: Cancellation reason

        Returns:
            True if cancelled successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE processing_queue
                    SET status = ?, completed_at = ?, error_details = ?
                    WHERE queue_id = ? AND status NOT IN ('COMPLETED', 'CANCELLED')
                """, (
                    QueueStatus.CANCELLED.value, datetime.now(timezone.utc).isoformat(),
                    f"Cancelled: {reason}" if reason else "Cancelled by user", queue_id
                ))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Queue item {queue_id} cancelled: {reason}")
                else:
                    self._logger.warning(f"Queue item {queue_id} not found or already completed")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cancel queue item {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def start_processing(self, queue_id: str) -> bool:
        """
        Mark a queue item as started processing.

        Args:
            queue_id: Queue item identifier

        Returns:
            True if status updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE processing_queue
                    SET status = ?, started_at = ?
                    WHERE queue_id = ? AND status IN (?, ?, ?)
                """, (
                    QueueStatus.PROCESSING.value, datetime.now(timezone.utc).isoformat(),
                    queue_id, QueueStatus.PENDING.value, QueueStatus.QUEUED.value, QueueStatus.RETRY.value
                ))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Queue item {queue_id} started processing")
                else:
                    self._logger.warning(f"Queue item {queue_id} not found or not in startable state")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to start processing for {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def get_queue_item(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific queue item by ID.

        Args:
            queue_id: Queue item identifier

        Returns:
            Queue item data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT queue_id, document_id, priority, operation, status,
                           retry_count, max_retries, scheduled_at, started_at,
                           completed_at, error_details, processing_metadata,
                           created_at, updated_at
                    FROM processing_queue WHERE queue_id = ?
                """, (queue_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                metadata = json.loads(row[11]) if row[11] else {}

                return {
                    'queue_id': row[0],
                    'document_id': row[1],
                    'priority': row[2],
                    'operation': row[3],
                    'status': row[4],
                    'retry_count': row[5],
                    'max_retries': row[6],
                    'scheduled_at': row[7],
                    'started_at': row[8],
                    'completed_at': row[9],
                    'error_details': row[10],
                    'metadata': metadata,
                    'created_at': row[12],
                    'updated_at': row[13]
                }

            except Exception as e:
                self._logger.error(f"Failed to get queue item {queue_id}: {e}")
                raise
            finally:
                conn.close()

    def get_queue_status(self, document_id: Optional[str] = None,
                        operation: Optional[OperationType] = None,
                        status: Optional[QueueStatus] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get queue items with optional filtering.

        Args:
            document_id: Filter by document ID
            operation: Filter by operation type
            status: Filter by status
            limit: Maximum number of items to return

        Returns:
            List of queue items matching criteria
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic query
                where_conditions = []
                params = []

                if document_id:
                    where_conditions.append("document_id = ?")
                    params.append(document_id)

                if operation:
                    where_conditions.append("operation = ?")
                    params.append(operation.value)

                if status:
                    where_conditions.append("status = ?")
                    params.append(status.value)

                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)

                query = f"""
                    SELECT queue_id, document_id, priority, operation, status,
                           retry_count, scheduled_at, started_at, completed_at,
                           error_details, created_at, updated_at
                    FROM processing_queue
                    {where_clause}
                    ORDER BY priority ASC, created_at DESC
                    LIMIT ?
                """
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                items = []
                for row in rows:
                    items.append({
                        'queue_id': row[0],
                        'document_id': row[1],
                        'priority': row[2],
                        'operation': row[3],
                        'status': row[4],
                        'retry_count': row[5],
                        'scheduled_at': row[6],
                        'started_at': row[7],
                        'completed_at': row[8],
                        'error_details': row[9],
                        'created_at': row[10],
                        'updated_at': row[11]
                    })

                return items

            except Exception as e:
                self._logger.error(f"Failed to get queue status: {e}")
                raise
            finally:
                conn.close()

    def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive queue statistics.

        Returns:
            Dictionary with queue statistics and metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get status counts
                cursor.execute("""
                    SELECT status, COUNT(*)
                    FROM processing_queue
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())

                # Get operation counts
                cursor.execute("""
                    SELECT operation, COUNT(*)
                    FROM processing_queue
                    GROUP BY operation
                """)
                operation_counts = dict(cursor.fetchall())

                # Get priority distribution
                cursor.execute("""
                    SELECT priority, COUNT(*)
                    FROM processing_queue
                    WHERE status NOT IN ('COMPLETED', 'CANCELLED')
                    GROUP BY priority
                """)
                priority_distribution = dict(cursor.fetchall())

                # Get average processing times
                cursor.execute("""
                    SELECT operation,
                           AVG(CAST((julianday(completed_at) - julianday(started_at)) * 86400 AS REAL)) as avg_seconds
                    FROM processing_queue
                    WHERE status = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL
                    GROUP BY operation
                """)
                avg_processing_times = dict(cursor.fetchall())

                # Get retry statistics
                cursor.execute("""
                    SELECT AVG(retry_count), MAX(retry_count), COUNT(*)
                    FROM processing_queue
                    WHERE retry_count > 0
                """)
                retry_stats = cursor.fetchone()

                # Get queue size and oldest pending
                cursor.execute("""
                    SELECT COUNT(*), MIN(created_at)
                    FROM processing_queue
                    WHERE status IN ('PENDING', 'QUEUED', 'RETRY')
                """)
                queue_info = cursor.fetchone()

                return {
                    'status_counts': status_counts,
                    'operation_counts': operation_counts,
                    'priority_distribution': priority_distribution,
                    'average_processing_times': avg_processing_times,
                    'retry_statistics': {
                        'average_retries': retry_stats[0] or 0,
                        'max_retries': retry_stats[1] or 0,
                        'items_with_retries': retry_stats[2] or 0
                    },
                    'queue_info': {
                        'pending_items': queue_info[0] or 0,
                        'oldest_pending': queue_info[1]
                    },
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                self._logger.error(f"Failed to get queue statistics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_completed_items(self, older_than_days: int = 30) -> int:
        """
        Clean up old completed and cancelled queue items.

        Args:
            older_than_days: Remove items older than this many days

        Returns:
            Number of items removed
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    DELETE FROM processing_queue
                    WHERE status IN ('COMPLETED', 'CANCELLED')
                    AND completed_at < ?
                """, (cutoff_date.isoformat(),))

                removed_count = cursor.rowcount
                conn.commit()

                self._logger.info(f"Cleaned up {removed_count} old queue items")
                return removed_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup queue items: {e}")
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("Processing queue database closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
