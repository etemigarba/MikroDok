"""
Module: metric_repository_db
Description: Stores and retrieves training metrics time-series data with efficient batch operations and time-based queries
Phase: 4
Location: /src/modules/database/training_metrics_db/metric_repository_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from src.modules.logic.common.logging_utils import get_logger
from src.modules.logic.training_metrics_lg.base_interfaces import MetricType, MetricResult


class MetricPriority(Enum):
    """Priority levels for metrics storage."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class MetricRecord:
    """Training metric record structure."""
    metric_id: str
    session_id: str
    metric_type: str
    metric_name: str
    metric_value: float
    epoch: int
    step: int
    timestamp: datetime
    priority: MetricPriority = MetricPriority.NORMAL
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


@dataclass
class TimeSeriesQuery:
    """Time series query parameters."""
    session_id: Optional[str] = None
    metric_types: Optional[List[str]] = None
    metric_names: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    epoch_range: Optional[Tuple[int, int]] = None
    step_range: Optional[Tuple[int, int]] = None
    limit: Optional[int] = None
    order_by: str = "timestamp"
    ascending: bool = True


class MetricRepositoryDB:
    """
    Database operations for training metrics time-series data storage and retrieval.
    
    Provides efficient storage and querying of training metrics with time-series
    optimization, batch operations, and advanced filtering capabilities.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the metric repository database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training metrics data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_metrics"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "metric_repository.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._batch_size = 1000  # Batch size for bulk operations
        self._retention_days = 365  # Keep metrics for 1 year
        self._max_metrics_per_session = 1000000  # Maximum metrics per session
        self._compression_threshold = 10000  # Compress when metrics exceed this
        
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
                        priority INTEGER NOT NULL DEFAULT 2,
                        metadata_json TEXT,
                        tags_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES training_sessions(session_id)
                    )
                """)
                
                # Create time-series optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_session_time 
                    ON training_metrics(session_id, timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_type_time 
                    ON training_metrics(metric_type, timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_epoch_step 
                    ON training_metrics(session_id, epoch, step)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_name_time 
                    ON training_metrics(metric_name, timestamp)
                """)
                
                # Create metric aggregates table for performance
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_aggregates (
                        aggregate_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        aggregation_type TEXT NOT NULL,
                        aggregation_value REAL NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        sample_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES training_sessions(session_id)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregates_session_type 
                    ON metric_aggregates(session_id, metric_type, aggregation_type)
                """)
                
                # Create metric metadata table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_metadata (
                        metadata_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        description TEXT,
                        unit TEXT,
                        data_type TEXT NOT NULL DEFAULT 'float',
                        min_value REAL,
                        max_value REAL,
                        expected_range TEXT,
                        collection_frequency TEXT,
                        importance_level INTEGER DEFAULT 2,
                        custom_properties_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(session_id, metric_name)
                    )
                """)
                
                conn.commit()
                self._logger.info("Metric repository database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize metric repository database: {e}")
                raise
            finally:
                conn.close()

    def store_metric(self, session_id: str, metric_type: str, metric_name: str,
                    metric_value: float, epoch: int, step: int,
                    priority: MetricPriority = MetricPriority.NORMAL,
                    metadata: Optional[Dict[str, Any]] = None,
                    tags: Optional[List[str]] = None) -> str:
        """
        Store a single training metric.

        Args:
            session_id: Training session ID
            metric_type: Type of metric (loss, accuracy, etc.)
            metric_name: Specific metric name
            metric_value: Metric value
            epoch: Training epoch
            step: Training step
            priority: Metric priority level
            metadata: Additional metadata
            tags: Metric tags

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())
        timestamp = datetime.now()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO training_metrics (
                        metric_id, session_id, metric_type, metric_name,
                        metric_value, epoch, step, timestamp, priority,
                        metadata_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, session_id, metric_type, metric_name,
                    metric_value, epoch, step, timestamp.isoformat(),
                    priority.value,
                    json.dumps(metadata) if metadata else None,
                    json.dumps(tags) if tags else None
                ))

                conn.commit()
                self._logger.debug(f"Stored metric {metric_name} for session {session_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store metric: {e}")
                raise
            finally:
                conn.close()

    def store_metrics_batch(self, metrics: List[MetricRecord]) -> List[str]:
        """
        Store multiple metrics in a batch operation.

        Args:
            metrics: List of metric records

        Returns:
            List of metric IDs
        """
        if not metrics:
            return []

        metric_ids = []

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Prepare batch data
                batch_data = []
                for metric in metrics:
                    if not metric.metric_id:
                        metric.metric_id = str(uuid.uuid4())

                    batch_data.append((
                        metric.metric_id,
                        metric.session_id,
                        metric.metric_type,
                        metric.metric_name,
                        metric.metric_value,
                        metric.epoch,
                        metric.step,
                        metric.timestamp.isoformat(),
                        metric.priority.value,
                        json.dumps(metric.metadata) if metric.metadata else None,
                        json.dumps(metric.tags) if metric.tags else None
                    ))
                    metric_ids.append(metric.metric_id)

                # Execute batch insert
                cursor.executemany("""
                    INSERT INTO training_metrics (
                        metric_id, session_id, metric_type, metric_name,
                        metric_value, epoch, step, timestamp, priority,
                        metadata_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_data)

                conn.commit()
                self._logger.info(f"Stored {len(metrics)} metrics in batch")
                return metric_ids

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store metrics batch: {e}")
                raise
            finally:
                conn.close()

    def get_metrics(self, query: TimeSeriesQuery) -> List[MetricRecord]:
        """
        Retrieve metrics based on query parameters.

        Args:
            query: Time series query parameters

        Returns:
            List of metric records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic query
                sql_parts = ["SELECT * FROM training_metrics WHERE 1=1"]
                params = []

                if query.session_id:
                    sql_parts.append("AND session_id = ?")
                    params.append(query.session_id)

                if query.metric_types:
                    placeholders = ",".join("?" * len(query.metric_types))
                    sql_parts.append(f"AND metric_type IN ({placeholders})")
                    params.extend(query.metric_types)

                if query.metric_names:
                    placeholders = ",".join("?" * len(query.metric_names))
                    sql_parts.append(f"AND metric_name IN ({placeholders})")
                    params.extend(query.metric_names)

                if query.start_time:
                    sql_parts.append("AND timestamp >= ?")
                    params.append(query.start_time.isoformat())

                if query.end_time:
                    sql_parts.append("AND timestamp <= ?")
                    params.append(query.end_time.isoformat())

                if query.epoch_range:
                    sql_parts.append("AND epoch BETWEEN ? AND ?")
                    params.extend(query.epoch_range)

                if query.step_range:
                    sql_parts.append("AND step BETWEEN ? AND ?")
                    params.extend(query.step_range)

                # Add ordering
                order_direction = "ASC" if query.ascending else "DESC"
                sql_parts.append(f"ORDER BY {query.order_by} {order_direction}")

                # Add limit
                if query.limit:
                    sql_parts.append("LIMIT ?")
                    params.append(query.limit)

                sql = " ".join(sql_parts)
                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # Convert to MetricRecord objects
                metrics = []
                for row in rows:
                    metric = MetricRecord(
                        metric_id=row[0],
                        session_id=row[1],
                        metric_type=row[2],
                        metric_name=row[3],
                        metric_value=row[4],
                        epoch=row[5],
                        step=row[6],
                        timestamp=datetime.fromisoformat(row[7]),
                        priority=MetricPriority(row[8]),
                        metadata=json.loads(row[9]) if row[9] else None,
                        tags=json.loads(row[10]) if row[10] else None
                    )
                    metrics.append(metric)

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to retrieve metrics: {e}")
                raise
            finally:
                conn.close()

    def get_latest_metrics(self, session_id: str, metric_names: Optional[List[str]] = None,
                          limit: int = 100) -> List[MetricRecord]:
        """
        Get the latest metrics for a session.

        Args:
            session_id: Training session ID
            metric_names: Specific metric names to retrieve
            limit: Maximum number of metrics to return

        Returns:
            List of latest metric records
        """
        query = TimeSeriesQuery(
            session_id=session_id,
            metric_names=metric_names,
            limit=limit,
            order_by="timestamp",
            ascending=False
        )
        return self.get_metrics(query)

    def get_metric_statistics(self, session_id: str, metric_name: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> Dict[str, float]:
        """
        Get statistical summary for a specific metric.

        Args:
            session_id: Training session ID
            metric_name: Metric name
            start_time: Start time for analysis
            end_time: End time for analysis

        Returns:
            Dictionary with statistical measures
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with time filters
                sql = """
                    SELECT
                        COUNT(*) as count,
                        AVG(metric_value) as mean,
                        MIN(metric_value) as min_value,
                        MAX(metric_value) as max_value,
                        SUM(metric_value * metric_value) as sum_squares
                    FROM training_metrics
                    WHERE session_id = ? AND metric_name = ?
                """
                params = [session_id, metric_name]

                if start_time:
                    sql += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    sql += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                cursor.execute(sql, params)
                row = cursor.fetchone()

                if row and row[0] > 0:
                    count, mean, min_val, max_val, sum_squares = row
                    variance = (sum_squares / count) - (mean * mean)
                    std_dev = variance ** 0.5 if variance > 0 else 0.0

                    return {
                        'count': count,
                        'mean': mean,
                        'std_dev': std_dev,
                        'min': min_val,
                        'max': max_val,
                        'variance': variance
                    }
                else:
                    return {
                        'count': 0,
                        'mean': 0.0,
                        'std_dev': 0.0,
                        'min': 0.0,
                        'max': 0.0,
                        'variance': 0.0
                    }

            except Exception as e:
                self._logger.error(f"Failed to get metric statistics: {e}")
                raise
            finally:
                conn.close()

    def delete_metrics(self, session_id: str, metric_names: Optional[List[str]] = None,
                      before_time: Optional[datetime] = None) -> int:
        """
        Delete metrics based on criteria.

        Args:
            session_id: Training session ID
            metric_names: Specific metric names to delete
            before_time: Delete metrics before this time

        Returns:
            Number of deleted metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build delete query
                sql_parts = ["DELETE FROM training_metrics WHERE session_id = ?"]
                params = [session_id]

                if metric_names:
                    placeholders = ",".join("?" * len(metric_names))
                    sql_parts.append(f"AND metric_name IN ({placeholders})")
                    params.extend(metric_names)

                if before_time:
                    sql_parts.append("AND timestamp < ?")
                    params.append(before_time.isoformat())

                sql = " ".join(sql_parts)
                cursor.execute(sql, params)
                deleted_count = cursor.rowcount

                conn.commit()
                self._logger.info(f"Deleted {deleted_count} metrics for session {session_id}")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete metrics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_metrics(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old metrics based on retention policy.

        Args:
            retention_days: Number of days to retain metrics

        Returns:
            Number of deleted metrics
        """
        if retention_days is None:
            retention_days = self._retention_days

        cutoff_time = datetime.now() - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM training_metrics
                    WHERE timestamp < ?
                """, (cutoff_time.isoformat(),))

                deleted_count = cursor.rowcount
                conn.commit()

                self._logger.info(f"Cleaned up {deleted_count} old metrics")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old metrics: {e}")
                raise
            finally:
                conn.close()

    def get_session_metrics_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary information for all metrics in a session.

        Args:
            session_id: Training session ID

        Returns:
            Summary dictionary with metric counts and ranges
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get overall session metrics summary
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_metrics,
                        COUNT(DISTINCT metric_name) as unique_metrics,
                        MIN(timestamp) as first_metric,
                        MAX(timestamp) as last_metric,
                        MIN(epoch) as min_epoch,
                        MAX(epoch) as max_epoch,
                        MIN(step) as min_step,
                        MAX(step) as max_step
                    FROM training_metrics
                    WHERE session_id = ?
                """, (session_id,))

                summary_row = cursor.fetchone()

                # Get per-metric breakdown
                cursor.execute("""
                    SELECT
                        metric_name,
                        metric_type,
                        COUNT(*) as count,
                        AVG(metric_value) as avg_value,
                        MIN(metric_value) as min_value,
                        MAX(metric_value) as max_value
                    FROM training_metrics
                    WHERE session_id = ?
                    GROUP BY metric_name, metric_type
                    ORDER BY metric_name
                """, (session_id,))

                metric_breakdown = cursor.fetchall()

                return {
                    'session_id': session_id,
                    'total_metrics': summary_row[0] if summary_row else 0,
                    'unique_metrics': summary_row[1] if summary_row else 0,
                    'first_metric': summary_row[2] if summary_row else None,
                    'last_metric': summary_row[3] if summary_row else None,
                    'epoch_range': (summary_row[4], summary_row[5]) if summary_row else (0, 0),
                    'step_range': (summary_row[6], summary_row[7]) if summary_row else (0, 0),
                    'metrics_breakdown': [
                        {
                            'name': row[0],
                            'type': row[1],
                            'count': row[2],
                            'avg_value': row[3],
                            'min_value': row[4],
                            'max_value': row[5]
                        }
                        for row in metric_breakdown
                    ]
                }

            except Exception as e:
                self._logger.error(f"Failed to get session metrics summary: {e}")
                raise
            finally:
                conn.close()
