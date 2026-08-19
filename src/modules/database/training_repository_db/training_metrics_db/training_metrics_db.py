"""
Module: training_metrics_db
Description: Time-series storage for training metrics with efficient batch insertion and aggregation
Phase: 4
Location: /src/modules/database/training_repository_db/training_metrics_db/
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
import statistics

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MetricType(Enum):
    """Training metric type enumeration."""
    LOSS = "loss"
    ACCURACY = "accuracy"
    LEARNING_RATE = "learning_rate"
    GRADIENT_NORM = "gradient_norm"
    VALIDATION_LOSS = "validation_loss"
    VALIDATION_ACCURACY = "validation_accuracy"
    PERPLEXITY = "perplexity"
    BLEU_SCORE = "bleu_score"
    F1_SCORE = "f1_score"
    PRECISION = "precision"
    RECALL = "recall"
    CUSTOM = "custom"


class MetricPriority(Enum):
    """Metric priority for storage and retrieval optimization."""
    CRITICAL = 1  # Always store, never aggregate
    HIGH = 2      # Store frequently, aggregate rarely
    MEDIUM = 3    # Store moderately, aggregate regularly
    LOW = 4       # Store sparsely, aggregate frequently


@dataclass
class TrainingMetric:
    """Training metric data structure."""
    metric_id: str
    session_id: str
    metric_type: MetricType
    metric_name: str
    metric_value: float
    epoch: int
    step: int
    timestamp: datetime
    priority: MetricPriority = MetricPriority.MEDIUM
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    
    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class MetricAggregation:
    """Aggregated metric data structure."""
    aggregation_id: str
    session_id: str
    metric_type: MetricType
    metric_name: str
    epoch_start: int
    epoch_end: int
    step_start: int
    step_end: int
    min_value: float
    max_value: float
    mean_value: float
    median_value: float
    std_deviation: float
    sample_count: int
    timestamp_start: datetime
    timestamp_end: datetime
    created_at: datetime


class TrainingMetricsDB:
    """
    Database manager for training metrics with time-series optimization.
    
    Provides efficient storage and retrieval of training metrics with batch insertion,
    automatic aggregation, and performance optimization for large-scale training sessions.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the training metrics database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "training_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._batch_size = 1000  # Batch size for bulk operations
        self._retention_days = 365  # Keep metrics for 1 year
        self._aggregation_threshold = 10000  # Aggregate when metrics exceed this count
        self._compression_ratio = 10  # Compress old metrics by this ratio
        
        # Batch insertion buffer
        self._batch_buffer: List[TrainingMetric] = []
        self._buffer_lock = threading.Lock()
        
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
                cursor.execute("PRAGMA cache_size=20000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Create training metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS training_metrics (
                        metric_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        epoch INTEGER NOT NULL,
                        step INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 3,
                        metadata_json TEXT,
                        tags_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create time-series optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_session_time 
                    ON training_metrics(session_id, timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_session_epoch_step 
                    ON training_metrics(session_id, epoch, step)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_type_name 
                    ON training_metrics(metric_type, metric_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_priority 
                    ON training_metrics(priority, timestamp)
                """)
                
                # Create metric aggregations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_aggregations (
                        aggregation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        epoch_start INTEGER NOT NULL,
                        epoch_end INTEGER NOT NULL,
                        step_start INTEGER NOT NULL,
                        step_end INTEGER NOT NULL,
                        min_value REAL NOT NULL,
                        max_value REAL NOT NULL,
                        mean_value REAL NOT NULL,
                        median_value REAL NOT NULL,
                        std_deviation REAL NOT NULL,
                        sample_count INTEGER NOT NULL,
                        timestamp_start TEXT NOT NULL,
                        timestamp_end TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregations_session_type 
                    ON metric_aggregations(session_id, metric_type, metric_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregations_epoch_range 
                    ON metric_aggregations(session_id, epoch_start, epoch_end)
                """)
                
                # Create metric metadata table for efficient querying
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_metadata (
                        session_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        first_epoch INTEGER NOT NULL,
                        last_epoch INTEGER NOT NULL,
                        first_step INTEGER NOT NULL,
                        last_step INTEGER NOT NULL,
                        total_samples INTEGER NOT NULL,
                        min_value REAL NOT NULL,
                        max_value REAL NOT NULL,
                        last_updated TEXT NOT NULL,
                        PRIMARY KEY (session_id, metric_type, metric_name)
                    )
                """)
                
                conn.commit()
                self._logger.info("Training metrics database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize training metrics database: {e}")
                raise
            finally:
                conn.close()

    def record_metric(self, session_id: str, metric_type: MetricType, metric_name: str,
                     metric_value: float, epoch: int, step: int,
                     priority: MetricPriority = MetricPriority.MEDIUM,
                     metadata: Optional[Dict[str, Any]] = None,
                     tags: Optional[List[str]] = None,
                     batch_insert: bool = True) -> str:
        """
        Record a training metric.

        Args:
            session_id: Training session identifier
            metric_type: Type of metric
            metric_name: Name of the metric
            metric_value: Metric value
            epoch: Training epoch
            step: Training step
            priority: Metric priority
            metadata: Additional metadata
            tags: Metric tags
            batch_insert: Whether to use batch insertion

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        metric = TrainingMetric(
            metric_id=metric_id,
            session_id=session_id,
            metric_type=metric_type,
            metric_name=metric_name,
            metric_value=metric_value,
            epoch=epoch,
            step=step,
            timestamp=timestamp,
            priority=priority,
            metadata=metadata,
            tags=tags
        )

        if batch_insert:
            self._add_to_batch(metric)
        else:
            self._insert_metric_direct(metric)

        return metric_id

    def _add_to_batch(self, metric: TrainingMetric) -> None:
        """Add metric to batch buffer."""
        with self._buffer_lock:
            self._batch_buffer.append(metric)

            if len(self._batch_buffer) >= self._batch_size:
                self._flush_batch()

    def _insert_metric_direct(self, metric: TrainingMetric) -> None:
        """Insert metric directly to database."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO training_metrics (
                        metric_id, session_id, metric_type, metric_name, metric_value,
                        epoch, step, timestamp, priority, metadata_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric.metric_id, metric.session_id, metric.metric_type.value,
                    metric.metric_name, metric.metric_value, metric.epoch, metric.step,
                    metric.timestamp.isoformat(), metric.priority.value,
                    json.dumps(metric.metadata) if metric.metadata else None,
                    json.dumps(metric.tags) if metric.tags else None
                ))

                # Update metadata
                self._update_metric_metadata(cursor, metric)

                conn.commit()

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to insert metric: {e}")
                raise
            finally:
                conn.close()

    def flush_batch(self) -> int:
        """
        Flush the batch buffer to database.

        Returns:
            Number of metrics flushed
        """
        with self._buffer_lock:
            return self._flush_batch()

    def _flush_batch(self) -> int:
        """Internal method to flush batch buffer."""
        if not self._batch_buffer:
            return 0

        metrics_to_insert = self._batch_buffer.copy()
        self._batch_buffer.clear()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Batch insert metrics
                metric_data = []
                for metric in metrics_to_insert:
                    metric_data.append((
                        metric.metric_id, metric.session_id, metric.metric_type.value,
                        metric.metric_name, metric.metric_value, metric.epoch, metric.step,
                        metric.timestamp.isoformat(), metric.priority.value,
                        json.dumps(metric.metadata) if metric.metadata else None,
                        json.dumps(metric.tags) if metric.tags else None
                    ))

                cursor.executemany("""
                    INSERT INTO training_metrics (
                        metric_id, session_id, metric_type, metric_name, metric_value,
                        epoch, step, timestamp, priority, metadata_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, metric_data)

                # Update metadata for each unique metric type/name combination
                unique_metrics = {}
                for metric in metrics_to_insert:
                    key = (metric.session_id, metric.metric_type.value, metric.metric_name)
                    if key not in unique_metrics:
                        unique_metrics[key] = []
                    unique_metrics[key].append(metric)

                for metrics_group in unique_metrics.values():
                    self._update_metric_metadata(cursor, metrics_group[0], len(metrics_group))

                conn.commit()
                self._logger.debug(f"Flushed {len(metrics_to_insert)} metrics to database")
                return len(metrics_to_insert)

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to flush batch: {e}")
                # Return metrics to buffer
                with self._buffer_lock:
                    self._batch_buffer.extend(metrics_to_insert)
                raise
            finally:
                conn.close()

    def _update_metric_metadata(self, cursor: sqlite3.Cursor, metric: TrainingMetric,
                               sample_count: int = 1) -> None:
        """Update metric metadata for efficient querying."""
        current_time = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO metric_metadata (
                session_id, metric_type, metric_name, first_epoch, last_epoch,
                first_step, last_step, total_samples, min_value, max_value, last_updated
            ) VALUES (
                ?, ?, ?,
                COALESCE((SELECT MIN(first_epoch, ?) FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), ?),
                COALESCE((SELECT MAX(last_epoch, ?) FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), ?),
                COALESCE((SELECT MIN(first_step, ?) FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), ?),
                COALESCE((SELECT MAX(last_step, ?) FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), ?),
                COALESCE((SELECT total_samples FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), 0) + ?,
                COALESCE((SELECT MIN(min_value, ?) FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), ?),
                COALESCE((SELECT MAX(max_value, ?) FROM metric_metadata
                         WHERE session_id = ? AND metric_type = ? AND metric_name = ?), ?),
                ?
            )
        """, (
            metric.session_id, metric.metric_type.value, metric.metric_name,
            metric.epoch, metric.session_id, metric.metric_type.value, metric.metric_name, metric.epoch,
            metric.epoch, metric.session_id, metric.metric_type.value, metric.metric_name, metric.epoch,
            metric.step, metric.session_id, metric.metric_type.value, metric.metric_name, metric.step,
            metric.step, metric.session_id, metric.metric_type.value, metric.metric_name, metric.step,
            metric.session_id, metric.metric_type.value, metric.metric_name, sample_count,
            metric.metric_value, metric.session_id, metric.metric_type.value, metric.metric_name, metric.metric_value,
            metric.metric_value, metric.session_id, metric.metric_type.value, metric.metric_name, metric.metric_value,
            current_time
        ))

    def get_metrics(self, session_id: str, metric_type: Optional[MetricType] = None,
                   metric_name: Optional[str] = None, epoch_start: Optional[int] = None,
                   epoch_end: Optional[int] = None, step_start: Optional[int] = None,
                   step_end: Optional[int] = None, limit: int = 1000,
                   offset: int = 0) -> List[TrainingMetric]:
        """
        Retrieve training metrics with filtering.

        Args:
            session_id: Training session identifier
            metric_type: Filter by metric type
            metric_name: Filter by metric name
            epoch_start: Start epoch filter
            epoch_end: End epoch filter
            step_start: Start step filter
            step_end: End step filter
            limit: Maximum number of metrics to return
            offset: Number of metrics to skip

        Returns:
            List of TrainingMetric objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT metric_id, session_id, metric_type, metric_name, metric_value,
                           epoch, step, timestamp, priority, metadata_json, tags_json
                    FROM training_metrics
                    WHERE session_id = ?
                """
                params = [session_id]

                if metric_type:
                    query += " AND metric_type = ?"
                    params.append(metric_type.value)

                if metric_name:
                    query += " AND metric_name = ?"
                    params.append(metric_name)

                if epoch_start is not None:
                    query += " AND epoch >= ?"
                    params.append(epoch_start)

                if epoch_end is not None:
                    query += " AND epoch <= ?"
                    params.append(epoch_end)

                if step_start is not None:
                    query += " AND step >= ?"
                    params.append(step_start)

                if step_end is not None:
                    query += " AND step <= ?"
                    params.append(step_end)

                query += " ORDER BY epoch, step LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                metrics = []
                for row in rows:
                    metrics.append(TrainingMetric(
                        metric_id=row[0],
                        session_id=row[1],
                        metric_type=MetricType(row[2]),
                        metric_name=row[3],
                        metric_value=row[4],
                        epoch=row[5],
                        step=row[6],
                        timestamp=datetime.fromisoformat(row[7]),
                        priority=MetricPriority(row[8]),
                        metadata=json.loads(row[9]) if row[9] else None,
                        tags=json.loads(row[10]) if row[10] else None
                    ))

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get metrics: {e}")
                return []
            finally:
                conn.close()

    def get_metric_summary(self, session_id: str, metric_type: MetricType,
                          metric_name: str) -> Optional[Dict[str, Any]]:
        """
        Get summary statistics for a metric.

        Args:
            session_id: Training session identifier
            metric_type: Metric type
            metric_name: Metric name

        Returns:
            Dictionary with summary statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT COUNT(*), MIN(metric_value), MAX(metric_value),
                           AVG(metric_value), MIN(epoch), MAX(epoch),
                           MIN(step), MAX(step), MIN(timestamp), MAX(timestamp)
                    FROM training_metrics
                    WHERE session_id = ? AND metric_type = ? AND metric_name = ?
                """, (session_id, metric_type.value, metric_name))

                row = cursor.fetchone()
                if not row or row[0] == 0:
                    return None

                return {
                    'count': row[0],
                    'min_value': row[1],
                    'max_value': row[2],
                    'mean_value': row[3],
                    'min_epoch': row[4],
                    'max_epoch': row[5],
                    'min_step': row[6],
                    'max_step': row[7],
                    'first_timestamp': row[8],
                    'last_timestamp': row[9]
                }

            except Exception as e:
                self._logger.error(f"Failed to get metric summary: {e}")
                return None
            finally:
                conn.close()

    def aggregate_metrics(self, session_id: str, metric_type: MetricType,
                         metric_name: str, epoch_window: int = 10) -> str:
        """
        Create aggregated metrics for efficient querying.

        Args:
            session_id: Training session identifier
            metric_type: Metric type
            metric_name: Metric name
            epoch_window: Number of epochs to aggregate

        Returns:
            Aggregation ID
        """
        aggregation_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get metrics to aggregate
                cursor.execute("""
                    SELECT metric_value, epoch, step, timestamp
                    FROM training_metrics
                    WHERE session_id = ? AND metric_type = ? AND metric_name = ?
                    ORDER BY epoch, step
                """, (session_id, metric_type.value, metric_name))

                rows = cursor.fetchall()
                if not rows:
                    return aggregation_id

                # Group by epoch windows
                epoch_groups = {}
                for row in rows:
                    epoch_group = row[1] // epoch_window
                    if epoch_group not in epoch_groups:
                        epoch_groups[epoch_group] = []
                    epoch_groups[epoch_group].append(row)

                # Create aggregations
                for epoch_group, group_rows in epoch_groups.items():
                    values = [row[0] for row in group_rows]
                    epochs = [row[1] for row in group_rows]
                    steps = [row[2] for row in group_rows]
                    timestamps = [row[3] for row in group_rows]

                    cursor.execute("""
                        INSERT INTO metric_aggregations (
                            aggregation_id, session_id, metric_type, metric_name,
                            epoch_start, epoch_end, step_start, step_end,
                            min_value, max_value, mean_value, median_value,
                            std_deviation, sample_count, timestamp_start,
                            timestamp_end, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        f"{aggregation_id}_{epoch_group}", session_id, metric_type.value, metric_name,
                        min(epochs), max(epochs), min(steps), max(steps),
                        min(values), max(values), statistics.mean(values),
                        statistics.median(values), statistics.stdev(values) if len(values) > 1 else 0.0,
                        len(values), min(timestamps), max(timestamps), current_time
                    ))

                conn.commit()
                self._logger.info(f"Created metric aggregation {aggregation_id}")
                return aggregation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to aggregate metrics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_metrics(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old metrics based on retention policy.

        Args:
            retention_days: Number of days to retain metrics

        Returns:
            Number of metrics deleted
        """
        if retention_days is None:
            retention_days = self._retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old metrics with low priority
                cursor.execute("""
                    DELETE FROM training_metrics
                    WHERE timestamp < ? AND priority >= ?
                """, (cutoff_str, MetricPriority.MEDIUM.value))

                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    self._logger.info(f"Cleaned up {deleted_count} old training metrics")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old metrics: {e}")
                return 0
            finally:
                conn.close()
