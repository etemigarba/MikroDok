"""
Module: inference_metrics_db
Description: Tracks inference performance metrics and resource usage per session
Phase: 4
Location: /src/modules/database/chat_repository_db/inference_metrics_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import uuid
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MetricType(Enum):
    """Inference metric type enumeration."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    GPU_UTILIZATION = "gpu_utilization"
    CPU_UTILIZATION = "cpu_utilization"
    TOKEN_RATE = "token_rate"
    ERROR_RATE = "error_rate"
    QUEUE_TIME = "queue_time"


@dataclass
class InferenceMetric:
    """Inference metric data structure."""
    metric_id: str
    session_id: str
    message_id: Optional[str]
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime = None
    model_id: Optional[str] = None
    request_id: Optional[str] = None
    batch_size: int = 1
    sequence_length: int = 0
    context_length: int = 0
    temperature: float = 0.7
    max_tokens: int = 0
    actual_tokens: int = 0
    processing_stage: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class InferenceMetricsDB:
    """
    Database manager for inference performance metrics and resource usage tracking.
    
    Provides thread-safe operations for storing and retrieving inference metrics
    with time-series data storage and efficient aggregation capabilities.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the inference metrics database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to chat data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "chat"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "inference_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._metric_retention_days = 90  # Keep metrics for 90 days
        self._aggregation_interval_minutes = 5  # Aggregate metrics every 5 minutes
        self._max_metrics_per_session = 100000  # Maximum metrics per session
        self._batch_size = 1000  # Batch size for bulk operations
        
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
                
                # Create inference metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS inference_metrics (
                        metric_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        message_id TEXT,
                        metric_type TEXT NOT NULL,
                        value REAL NOT NULL,
                        unit TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        model_id TEXT,
                        request_id TEXT,
                        batch_size INTEGER DEFAULT 1,
                        sequence_length INTEGER DEFAULT 0,
                        context_length INTEGER DEFAULT 0,
                        temperature REAL DEFAULT 0.7,
                        max_tokens INTEGER DEFAULT 0,
                        actual_tokens INTEGER DEFAULT 0,
                        processing_stage TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_inference_metrics_session_id 
                    ON inference_metrics(session_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_inference_metrics_timestamp 
                    ON inference_metrics(timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_inference_metrics_type 
                    ON inference_metrics(metric_type)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_inference_metrics_model_id 
                    ON inference_metrics(model_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_inference_metrics_message_id 
                    ON inference_metrics(message_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_inference_metrics_request_id 
                    ON inference_metrics(request_id)
                """)
                
                # Create aggregated metrics table for performance
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS aggregated_metrics (
                        aggregation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        model_id TEXT,
                        metric_type TEXT NOT NULL,
                        time_window_start TEXT NOT NULL,
                        time_window_end TEXT NOT NULL,
                        count INTEGER NOT NULL,
                        min_value REAL NOT NULL,
                        max_value REAL NOT NULL,
                        avg_value REAL NOT NULL,
                        median_value REAL,
                        std_dev REAL,
                        percentile_95 REAL,
                        percentile_99 REAL,
                        total_requests INTEGER DEFAULT 0,
                        error_count INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregated_metrics_session_id 
                    ON aggregated_metrics(session_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregated_metrics_time_window 
                    ON aggregated_metrics(time_window_start, time_window_end)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregated_metrics_type 
                    ON aggregated_metrics(metric_type)
                """)
                
                # Create session performance summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_performance_summary (
                        session_id TEXT PRIMARY KEY,
                        model_id TEXT,
                        total_requests INTEGER DEFAULT 0,
                        total_tokens INTEGER DEFAULT 0,
                        avg_latency_ms REAL DEFAULT 0.0,
                        avg_throughput_tokens_per_sec REAL DEFAULT 0.0,
                        peak_memory_usage_mb REAL DEFAULT 0.0,
                        avg_gpu_utilization REAL DEFAULT 0.0,
                        avg_cpu_utilization REAL DEFAULT 0.0,
                        error_count INTEGER DEFAULT 0,
                        error_rate REAL DEFAULT 0.0,
                        first_request_at TEXT,
                        last_request_at TEXT,
                        total_session_time_ms REAL DEFAULT 0.0,
                        last_updated TEXT NOT NULL
                    )
                """)
                
                conn.commit()
                self._logger.info("Inference metrics database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize inference metrics database: {e}")
                raise
            finally:
                conn.close()

    def record_metric(self, session_id: str, metric_type: MetricType, value: float, unit: str,
                     message_id: Optional[str] = None,
                     model_id: Optional[str] = None,
                     request_id: Optional[str] = None,
                     batch_size: int = 1,
                     sequence_length: int = 0,
                     context_length: int = 0,
                     temperature: float = 0.7,
                     max_tokens: int = 0,
                     actual_tokens: int = 0,
                     processing_stage: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record an inference metric.

        Args:
            session_id: Session identifier
            metric_type: Type of metric
            value: Metric value
            unit: Unit of measurement
            message_id: Associated message ID
            model_id: Model identifier
            request_id: Request identifier
            batch_size: Batch size
            sequence_length: Sequence length
            context_length: Context length
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            actual_tokens: Actual tokens generated
            processing_stage: Processing stage
            metadata: Additional metadata

        Returns:
            Metric ID

        Raises:
            ValueError: If metric limit exceeded
        """
        metric_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check metric limit per session
                cursor.execute("SELECT COUNT(*) FROM inference_metrics WHERE session_id = ?", (session_id,))
                metric_count = cursor.fetchone()[0]

                if metric_count >= self._max_metrics_per_session:
                    raise ValueError(f"Maximum metrics per session ({self._max_metrics_per_session}) exceeded")

                cursor.execute("""
                    INSERT INTO inference_metrics (
                        metric_id, session_id, message_id, metric_type, value, unit,
                        timestamp, model_id, request_id, batch_size, sequence_length,
                        context_length, temperature, max_tokens, actual_tokens,
                        processing_stage, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, session_id, message_id, metric_type.value, value, unit,
                    current_time, model_id, request_id, batch_size, sequence_length,
                    context_length, temperature, max_tokens, actual_tokens,
                    processing_stage, json.dumps(metadata) if metadata else None
                ))

                # Update session performance summary
                self._update_session_summary(cursor, session_id, metric_type, value,
                                           model_id, actual_tokens, current_time)

                conn.commit()
                self._logger.debug(f"Recorded metric {metric_id} for session {session_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record metric for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def _update_session_summary(self, cursor: sqlite3.Cursor, session_id: str,
                               metric_type: MetricType, value: float,
                               model_id: Optional[str], tokens: int, timestamp: str) -> None:
        """
        Update session performance summary.

        Args:
            cursor: Database cursor
            session_id: Session identifier
            metric_type: Type of metric
            value: Metric value
            model_id: Model identifier
            tokens: Number of tokens
            timestamp: Current timestamp
        """
        # Get current summary
        cursor.execute("""
            SELECT total_requests, total_tokens, avg_latency_ms, avg_throughput_tokens_per_sec,
                   peak_memory_usage_mb, avg_gpu_utilization, avg_cpu_utilization,
                   error_count, first_request_at
            FROM session_performance_summary WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if row:
            (total_requests, total_tokens, avg_latency, avg_throughput,
             peak_memory, avg_gpu, avg_cpu, error_count, first_request) = row
        else:
            total_requests = total_tokens = avg_latency = avg_throughput = 0
            peak_memory = avg_gpu = avg_cpu = error_count = 0
            first_request = timestamp

        # Update based on metric type
        if metric_type == MetricType.LATENCY:
            total_requests += 1
            avg_latency = ((avg_latency * (total_requests - 1)) + value) / total_requests
        elif metric_type == MetricType.THROUGHPUT:
            avg_throughput = ((avg_throughput * total_requests) + value) / (total_requests + 1)
        elif metric_type == MetricType.MEMORY_USAGE:
            peak_memory = max(peak_memory, value)
        elif metric_type == MetricType.GPU_UTILIZATION:
            avg_gpu = ((avg_gpu * total_requests) + value) / (total_requests + 1)
        elif metric_type == MetricType.CPU_UTILIZATION:
            avg_cpu = ((avg_cpu * total_requests) + value) / (total_requests + 1)
        elif metric_type == MetricType.ERROR_RATE:
            error_count += 1

        total_tokens += tokens
        error_rate = error_count / max(total_requests, 1)

        # Calculate total session time
        first_dt = datetime.fromisoformat(first_request)
        current_dt = datetime.fromisoformat(timestamp)
        total_session_time_ms = (current_dt - first_dt).total_seconds() * 1000

        cursor.execute("""
            INSERT OR REPLACE INTO session_performance_summary (
                session_id, model_id, total_requests, total_tokens, avg_latency_ms,
                avg_throughput_tokens_per_sec, peak_memory_usage_mb, avg_gpu_utilization,
                avg_cpu_utilization, error_count, error_rate, first_request_at,
                last_request_at, total_session_time_ms, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, model_id, total_requests, total_tokens, avg_latency,
            avg_throughput, peak_memory, avg_gpu, avg_cpu, error_count, error_rate,
            first_request, timestamp, total_session_time_ms, timestamp
        ))

    def get_session_metrics(self, session_id: str,
                           metric_type: Optional[MetricType] = None,
                           start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None,
                           limit: int = 1000,
                           offset: int = 0) -> List[InferenceMetric]:
        """
        Get metrics for a session with optional filtering.

        Args:
            session_id: Session identifier
            metric_type: Filter by metric type
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of metrics to return
            offset: Number of metrics to skip

        Returns:
            List of InferenceMetric objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT metric_id, session_id, message_id, metric_type, value, unit,
                           timestamp, model_id, request_id, batch_size, sequence_length,
                           context_length, temperature, max_tokens, actual_tokens,
                           processing_stage, metadata_json
                    FROM inference_metrics WHERE session_id = ?
                """
                params = [session_id]

                if metric_type:
                    query += " AND metric_type = ?"
                    params.append(metric_type.value)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                metrics = []
                for row in rows:
                    metrics.append(InferenceMetric(
                        metric_id=row[0],
                        session_id=row[1],
                        message_id=row[2],
                        metric_type=MetricType(row[3]),
                        value=row[4],
                        unit=row[5],
                        timestamp=datetime.fromisoformat(row[6]),
                        model_id=row[7],
                        request_id=row[8],
                        batch_size=row[9],
                        sequence_length=row[10],
                        context_length=row[11],
                        temperature=row[12],
                        max_tokens=row[13],
                        actual_tokens=row[14],
                        processing_stage=row[15],
                        metadata=json.loads(row[16]) if row[16] else None
                    ))

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get metrics for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def get_session_performance_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get performance summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with performance summary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT model_id, total_requests, total_tokens, avg_latency_ms,
                           avg_throughput_tokens_per_sec, peak_memory_usage_mb,
                           avg_gpu_utilization, avg_cpu_utilization, error_count,
                           error_rate, first_request_at, last_request_at,
                           total_session_time_ms, last_updated
                    FROM session_performance_summary WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'model_id': row[0],
                    'total_requests': row[1],
                    'total_tokens': row[2],
                    'avg_latency_ms': row[3],
                    'avg_throughput_tokens_per_sec': row[4],
                    'peak_memory_usage_mb': row[5],
                    'avg_gpu_utilization': row[6],
                    'avg_cpu_utilization': row[7],
                    'error_count': row[8],
                    'error_rate': row[9],
                    'first_request_at': row[10],
                    'last_request_at': row[11],
                    'total_session_time_ms': row[12],
                    'last_updated': row[13]
                }

            except Exception as e:
                self._logger.error(f"Failed to get performance summary for session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def aggregate_metrics(self, session_id: str, metric_type: MetricType,
                         start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
        """
        Aggregate metrics for a time window.

        Args:
            session_id: Session identifier
            metric_type: Type of metric to aggregate
            start_time: Start of time window
            end_time: End of time window

        Returns:
            Dictionary with aggregated statistics or None if no data
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT value FROM inference_metrics
                    WHERE session_id = ? AND metric_type = ?
                    AND timestamp BETWEEN ? AND ?
                    ORDER BY value
                """, (session_id, metric_type.value, start_time.isoformat(), end_time.isoformat()))

                values = [row[0] for row in cursor.fetchall()]

                if not values:
                    return None

                # Calculate statistics
                count = len(values)
                min_val = min(values)
                max_val = max(values)
                avg_val = statistics.mean(values)
                median_val = statistics.median(values)
                std_dev = statistics.stdev(values) if count > 1 else 0.0

                # Calculate percentiles
                percentile_95 = values[int(0.95 * count)] if count > 0 else 0.0
                percentile_99 = values[int(0.99 * count)] if count > 0 else 0.0

                # Store aggregated result
                aggregation_id = str(uuid.uuid4())
                current_time = datetime.now(timezone.utc).isoformat()

                cursor.execute("""
                    INSERT INTO aggregated_metrics (
                        aggregation_id, session_id, metric_type, time_window_start,
                        time_window_end, count, min_value, max_value, avg_value,
                        median_value, std_dev, percentile_95, percentile_99, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aggregation_id, session_id, metric_type.value, start_time.isoformat(),
                    end_time.isoformat(), count, min_val, max_val, avg_val,
                    median_val, std_dev, percentile_95, percentile_99, current_time
                ))

                conn.commit()

                return {
                    'aggregation_id': aggregation_id,
                    'count': count,
                    'min_value': min_val,
                    'max_value': max_val,
                    'avg_value': avg_val,
                    'median_value': median_val,
                    'std_dev': std_dev,
                    'percentile_95': percentile_95,
                    'percentile_99': percentile_99,
                    'time_window_start': start_time.isoformat(),
                    'time_window_end': end_time.isoformat()
                }

            except Exception as e:
                self._logger.error(f"Failed to aggregate metrics for session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def get_model_performance_comparison(self, model_ids: List[str],
                                       metric_type: MetricType,
                                       start_time: Optional[datetime] = None,
                                       end_time: Optional[datetime] = None) -> Dict[str, Dict[str, Any]]:
        """
        Compare performance metrics across multiple models.

        Args:
            model_ids: List of model identifiers
            metric_type: Type of metric to compare
            start_time: Start time filter
            end_time: End time filter

        Returns:
            Dictionary with model performance comparison
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                results = {}

                for model_id in model_ids:
                    query = """
                        SELECT AVG(value), MIN(value), MAX(value), COUNT(*)
                        FROM inference_metrics
                        WHERE model_id = ? AND metric_type = ?
                    """
                    params = [model_id, metric_type.value]

                    if start_time:
                        query += " AND timestamp >= ?"
                        params.append(start_time.isoformat())

                    if end_time:
                        query += " AND timestamp <= ?"
                        params.append(end_time.isoformat())

                    cursor.execute(query, params)
                    row = cursor.fetchone()

                    if row and row[3] > 0:  # Check if we have data
                        results[model_id] = {
                            'avg_value': row[0],
                            'min_value': row[1],
                            'max_value': row[2],
                            'sample_count': row[3]
                        }

                return results

            except Exception as e:
                self._logger.error(f"Failed to compare model performance: {e}")
                return {}
            finally:
                conn.close()

    def delete_session_metrics(self, session_id: str) -> int:
        """
        Delete all metrics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of metrics deleted
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete metrics
                cursor.execute("DELETE FROM inference_metrics WHERE session_id = ?", (session_id,))
                deleted_count = cursor.rowcount

                # Delete aggregated metrics
                cursor.execute("DELETE FROM aggregated_metrics WHERE session_id = ?", (session_id,))

                # Delete performance summary
                cursor.execute("DELETE FROM session_performance_summary WHERE session_id = ?", (session_id,))

                conn.commit()
                self._logger.info(f"Deleted {deleted_count} metrics for session {session_id}")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete metrics for session {session_id}: {e}")
                return 0
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
            retention_days = self._metric_retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old metrics
                cursor.execute("DELETE FROM inference_metrics WHERE timestamp < ?", (cutoff_str,))
                deleted_count = cursor.rowcount

                # Delete old aggregated metrics
                cursor.execute("DELETE FROM aggregated_metrics WHERE time_window_end < ?", (cutoff_str,))

                # Clean up orphaned performance summaries
                cursor.execute("""
                    DELETE FROM session_performance_summary
                    WHERE session_id NOT IN (SELECT DISTINCT session_id FROM inference_metrics)
                """)

                conn.commit()

                if deleted_count > 0:
                    self._logger.info(f"Cleaned up {deleted_count} old inference metrics")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old metrics: {e}")
                return 0
            finally:
                conn.close()

    def get_metric_statistics(self, session_id: Optional[str] = None,
                             model_id: Optional[str] = None,
                             metric_type: Optional[MetricType] = None) -> Dict[str, Any]:
        """
        Get comprehensive metric statistics.

        Args:
            session_id: Filter by session ID
            model_id: Filter by model ID
            metric_type: Filter by metric type

        Returns:
            Dictionary with metric statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT
                        COUNT(*) as total_metrics,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        COUNT(DISTINCT model_id) as unique_models,
                        COUNT(DISTINCT metric_type) as unique_metric_types,
                        MIN(timestamp) as earliest_metric,
                        MAX(timestamp) as latest_metric
                    FROM inference_metrics
                """

                conditions = []
                params = []

                if session_id:
                    conditions.append("session_id = ?")
                    params.append(session_id)

                if model_id:
                    conditions.append("model_id = ?")
                    params.append(model_id)

                if metric_type:
                    conditions.append("metric_type = ?")
                    params.append(metric_type.value)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                cursor.execute(query, params)
                row = cursor.fetchone()

                stats = {
                    'total_metrics': row[0] or 0,
                    'unique_sessions': row[1] or 0,
                    'unique_models': row[2] or 0,
                    'unique_metric_types': row[3] or 0,
                    'earliest_metric': row[4],
                    'latest_metric': row[5]
                }

                # Get metric type distribution
                type_query = "SELECT metric_type, COUNT(*) FROM inference_metrics"
                if conditions:
                    type_query += " WHERE " + " AND ".join(conditions)
                type_query += " GROUP BY metric_type"

                cursor.execute(type_query, params)
                stats['metric_type_distribution'] = dict(cursor.fetchall())

                return stats

            except Exception as e:
                self._logger.error(f"Failed to get metric statistics: {e}")
                return {}
            finally:
                conn.close()
