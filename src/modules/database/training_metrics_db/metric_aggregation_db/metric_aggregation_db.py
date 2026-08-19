"""
Module: metric_aggregation_db
Description: Stores aggregated metric summaries and statistics with efficient aggregation functions and performance optimization
Phase: 4
Location: /src/modules/database/training_metrics_db/metric_aggregation_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import uuid
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from src.modules.logic.common.logging_utils import get_logger
from src.modules.logic.training_metrics_lg.base_interfaces import AggregationStrategy


class AggregationWindow(Enum):
    """Time window types for aggregation."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    EPOCH = "epoch"
    STEP_RANGE = "step_range"
    CUSTOM = "custom"


class AggregationStatus(Enum):
    """Status of aggregation operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AggregationConfig:
    """Configuration for metric aggregation."""
    session_id: str
    metric_names: List[str]
    aggregation_strategy: AggregationStrategy
    window_type: AggregationWindow
    window_size: int
    overlap_percent: float = 0.0
    min_samples: int = 1
    custom_params: Optional[Dict[str, Any]] = None


@dataclass
class AggregatedMetric:
    """Aggregated metric result."""
    aggregate_id: str
    session_id: str
    metric_name: str
    metric_type: str
    aggregation_strategy: AggregationStrategy
    aggregated_value: float
    window_start: datetime
    window_end: datetime
    sample_count: int
    confidence_score: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StatisticalSummary:
    """Statistical summary of metrics."""
    metric_name: str
    session_id: str
    count: int
    mean: float
    median: float
    std_dev: float
    variance: float
    min_value: float
    max_value: float
    percentiles: Dict[str, float]
    skewness: float
    kurtosis: float
    timestamp: datetime


class MetricAggregationDB:
    """
    Database operations for aggregated metric summaries and statistics.
    
    Provides efficient storage and computation of aggregated training metrics
    with various aggregation strategies, time windows, and statistical analysis.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the metric aggregation database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training metrics data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_metrics"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "metric_aggregation.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._default_window_size = 100  # Default aggregation window
        self._max_aggregation_jobs = 10  # Maximum concurrent aggregation jobs
        self._retention_days = 180  # Keep aggregated data for 6 months
        self._batch_size = 1000  # Batch size for aggregation operations
        
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
                
                # Create aggregated metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS aggregated_metrics (
                        aggregate_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        aggregation_strategy TEXT NOT NULL,
                        aggregated_value REAL NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        sample_count INTEGER NOT NULL,
                        confidence_score REAL NOT NULL DEFAULT 1.0,
                        metadata_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES training_sessions(session_id)
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregated_session_metric 
                    ON aggregated_metrics(session_id, metric_name, aggregation_strategy)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_aggregated_time_window 
                    ON aggregated_metrics(window_start, window_end)
                """)
                
                # Create statistical summaries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS statistical_summaries (
                        summary_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        count INTEGER NOT NULL,
                        mean REAL NOT NULL,
                        median REAL NOT NULL,
                        std_dev REAL NOT NULL,
                        variance REAL NOT NULL,
                        min_value REAL NOT NULL,
                        max_value REAL NOT NULL,
                        percentiles_json TEXT,
                        skewness REAL,
                        kurtosis REAL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES training_sessions(session_id)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_summaries_session_metric 
                    ON statistical_summaries(session_id, metric_name)
                """)
                
                # Create aggregation jobs table for tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS aggregation_jobs (
                        job_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        config_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        progress_percent REAL NOT NULL DEFAULT 0.0,
                        error_message TEXT,
                        started_at TEXT,
                        completed_at TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_jobs_session_status 
                    ON aggregation_jobs(session_id, status)
                """)
                
                # Create aggregation cache table for performance
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS aggregation_cache (
                        cache_id TEXT PRIMARY KEY,
                        cache_key TEXT UNIQUE NOT NULL,
                        aggregation_result_json TEXT NOT NULL,
                        expiry_time TEXT NOT NULL,
                        access_count INTEGER NOT NULL DEFAULT 0,
                        last_accessed TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_key_expiry 
                    ON aggregation_cache(cache_key, expiry_time)
                """)
                
                conn.commit()
                self._logger.info("Metric aggregation database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize metric aggregation database: {e}")
                raise
            finally:
                conn.close()

    def create_aggregation(self, session_id: str, metric_name: str, metric_type: str,
                          values: List[float], aggregation_strategy: AggregationStrategy,
                          window_start: datetime, window_end: datetime,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create an aggregated metric from raw values.

        Args:
            session_id: Training session ID
            metric_name: Name of the metric
            metric_type: Type of the metric
            values: List of metric values to aggregate
            aggregation_strategy: Strategy for aggregation
            window_start: Start of aggregation window
            window_end: End of aggregation window
            metadata: Additional metadata

        Returns:
            Aggregate ID
        """
        if not values:
            raise ValueError("Cannot aggregate empty values list")

        # Calculate aggregated value based on strategy
        aggregated_value = self._calculate_aggregation(values, aggregation_strategy)
        confidence_score = self._calculate_confidence_score(values, aggregation_strategy)

        aggregate_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO aggregated_metrics (
                        aggregate_id, session_id, metric_name, metric_type,
                        aggregation_strategy, aggregated_value, window_start,
                        window_end, sample_count, confidence_score, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aggregate_id, session_id, metric_name, metric_type,
                    aggregation_strategy.value, aggregated_value,
                    window_start.isoformat(), window_end.isoformat(),
                    len(values), confidence_score,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.debug(f"Created aggregation {aggregate_id} for metric {metric_name}")
                return aggregate_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create aggregation: {e}")
                raise
            finally:
                conn.close()

    def _calculate_aggregation(self, values: List[float],
                              strategy: AggregationStrategy) -> float:
        """Calculate aggregated value based on strategy."""
        if strategy == AggregationStrategy.MEAN:
            return statistics.mean(values)
        elif strategy == AggregationStrategy.MEDIAN:
            return statistics.median(values)
        elif strategy == AggregationStrategy.MIN:
            return min(values)
        elif strategy == AggregationStrategy.MAX:
            return max(values)
        elif strategy == AggregationStrategy.STD:
            return statistics.stdev(values) if len(values) > 1 else 0.0
        elif strategy == AggregationStrategy.PERCENTILE:
            # Default to 95th percentile
            return statistics.quantiles(values, n=20)[18] if len(values) >= 20 else max(values)
        elif strategy == AggregationStrategy.WEIGHTED_AVERAGE:
            # Simple weighted average (more recent values have higher weight)
            weights = [i + 1 for i in range(len(values))]
            weighted_sum = sum(v * w for v, w in zip(values, weights))
            return weighted_sum / sum(weights)
        elif strategy == AggregationStrategy.EXPONENTIAL_MOVING_AVERAGE:
            # Calculate EMA with alpha = 0.1
            alpha = 0.1
            ema = values[0]
            for value in values[1:]:
                ema = alpha * value + (1 - alpha) * ema
            return ema
        else:
            return statistics.mean(values)  # Default fallback

    def _calculate_confidence_score(self, values: List[float],
                                   strategy: AggregationStrategy) -> float:
        """Calculate confidence score for aggregation."""
        if len(values) < 2:
            return 0.5

        # Base confidence on sample size and variance
        sample_size_factor = min(1.0, len(values) / 100.0)

        try:
            variance = statistics.variance(values)
            mean_val = statistics.mean(values)
            cv = (variance ** 0.5) / abs(mean_val) if mean_val != 0 else 1.0
            variance_factor = max(0.1, 1.0 - min(1.0, cv))
        except:
            variance_factor = 0.5

        return min(1.0, sample_size_factor * 0.5 + variance_factor * 0.5)

    def get_aggregated_metrics(self, session_id: str, metric_name: Optional[str] = None,
                              aggregation_strategy: Optional[AggregationStrategy] = None,
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None) -> List[AggregatedMetric]:
        """
        Retrieve aggregated metrics based on criteria.

        Args:
            session_id: Training session ID
            metric_name: Specific metric name
            aggregation_strategy: Specific aggregation strategy
            start_time: Start time filter
            end_time: End time filter

        Returns:
            List of aggregated metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic query
                sql_parts = ["SELECT * FROM aggregated_metrics WHERE session_id = ?"]
                params = [session_id]

                if metric_name:
                    sql_parts.append("AND metric_name = ?")
                    params.append(metric_name)

                if aggregation_strategy:
                    sql_parts.append("AND aggregation_strategy = ?")
                    params.append(aggregation_strategy.value)

                if start_time:
                    sql_parts.append("AND window_start >= ?")
                    params.append(start_time.isoformat())

                if end_time:
                    sql_parts.append("AND window_end <= ?")
                    params.append(end_time.isoformat())

                sql_parts.append("ORDER BY window_start ASC")
                sql = " ".join(sql_parts)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # Convert to AggregatedMetric objects
                aggregated_metrics = []
                for row in rows:
                    metric = AggregatedMetric(
                        aggregate_id=row[0],
                        session_id=row[1],
                        metric_name=row[2],
                        metric_type=row[3],
                        aggregation_strategy=AggregationStrategy(row[4]),
                        aggregated_value=row[5],
                        window_start=datetime.fromisoformat(row[6]),
                        window_end=datetime.fromisoformat(row[7]),
                        sample_count=row[8],
                        confidence_score=row[9],
                        metadata=json.loads(row[10]) if row[10] else None
                    )
                    aggregated_metrics.append(metric)

                return aggregated_metrics

            except Exception as e:
                self._logger.error(f"Failed to retrieve aggregated metrics: {e}")
                raise
            finally:
                conn.close()

    def create_statistical_summary(self, session_id: str, metric_name: str,
                                  metric_type: str, values: List[float],
                                  window_start: datetime, window_end: datetime) -> str:
        """
        Create comprehensive statistical summary for a metric.

        Args:
            session_id: Training session ID
            metric_name: Name of the metric
            metric_type: Type of the metric
            values: List of metric values
            window_start: Start of analysis window
            window_end: End of analysis window

        Returns:
            Summary ID
        """
        if not values:
            raise ValueError("Cannot create summary for empty values list")

        # Calculate statistical measures
        count = len(values)
        mean = statistics.mean(values)
        median = statistics.median(values)

        if count > 1:
            std_dev = statistics.stdev(values)
            variance = statistics.variance(values)
        else:
            std_dev = 0.0
            variance = 0.0

        min_value = min(values)
        max_value = max(values)

        # Calculate percentiles
        percentiles = {}
        if count >= 4:
            try:
                quantiles = statistics.quantiles(values, n=100)
                percentiles = {
                    'p25': quantiles[24],
                    'p50': median,
                    'p75': quantiles[74],
                    'p90': quantiles[89],
                    'p95': quantiles[94],
                    'p99': quantiles[98] if len(quantiles) > 98 else max_value
                }
            except:
                percentiles = {'p50': median}
        else:
            percentiles = {'p50': median}

        # Calculate skewness and kurtosis (simplified)
        skewness = self._calculate_skewness(values, mean, std_dev)
        kurtosis = self._calculate_kurtosis(values, mean, std_dev)

        summary_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO statistical_summaries (
                        summary_id, session_id, metric_name, metric_type,
                        count, mean, median, std_dev, variance,
                        min_value, max_value, percentiles_json,
                        skewness, kurtosis, window_start, window_end
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    summary_id, session_id, metric_name, metric_type,
                    count, mean, median, std_dev, variance,
                    min_value, max_value, json.dumps(percentiles),
                    skewness, kurtosis, window_start.isoformat(), window_end.isoformat()
                ))

                conn.commit()
                self._logger.debug(f"Created statistical summary {summary_id} for metric {metric_name}")
                return summary_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create statistical summary: {e}")
                raise
            finally:
                conn.close()

    def _calculate_skewness(self, values: List[float], mean: float, std_dev: float) -> float:
        """Calculate skewness of the distribution."""
        if std_dev == 0 or len(values) < 3:
            return 0.0

        n = len(values)
        skew_sum = sum(((x - mean) / std_dev) ** 3 for x in values)
        return (n / ((n - 1) * (n - 2))) * skew_sum

    def _calculate_kurtosis(self, values: List[float], mean: float, std_dev: float) -> float:
        """Calculate kurtosis of the distribution."""
        if std_dev == 0 or len(values) < 4:
            return 0.0

        n = len(values)
        kurt_sum = sum(((x - mean) / std_dev) ** 4 for x in values)
        return ((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))) * kurt_sum - (3 * (n - 1) ** 2) / ((n - 2) * (n - 3))

    def get_statistical_summaries(self, session_id: str, metric_name: Optional[str] = None,
                                 start_time: Optional[datetime] = None,
                                 end_time: Optional[datetime] = None) -> List[StatisticalSummary]:
        """
        Retrieve statistical summaries based on criteria.

        Args:
            session_id: Training session ID
            metric_name: Specific metric name
            start_time: Start time filter
            end_time: End time filter

        Returns:
            List of statistical summaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic query
                sql_parts = ["SELECT * FROM statistical_summaries WHERE session_id = ?"]
                params = [session_id]

                if metric_name:
                    sql_parts.append("AND metric_name = ?")
                    params.append(metric_name)

                if start_time:
                    sql_parts.append("AND window_start >= ?")
                    params.append(start_time.isoformat())

                if end_time:
                    sql_parts.append("AND window_end <= ?")
                    params.append(end_time.isoformat())

                sql_parts.append("ORDER BY window_start ASC")
                sql = " ".join(sql_parts)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # Convert to StatisticalSummary objects
                summaries = []
                for row in rows:
                    summary = StatisticalSummary(
                        metric_name=row[2],
                        session_id=row[1],
                        count=row[4],
                        mean=row[5],
                        median=row[6],
                        std_dev=row[7],
                        variance=row[8],
                        min_value=row[9],
                        max_value=row[10],
                        percentiles=json.loads(row[11]) if row[11] else {},
                        skewness=row[12] or 0.0,
                        kurtosis=row[13] or 0.0,
                        timestamp=datetime.fromisoformat(row[16])  # created_at
                    )
                    summaries.append(summary)

                return summaries

            except Exception as e:
                self._logger.error(f"Failed to retrieve statistical summaries: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_aggregations(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old aggregated data based on retention policy.

        Args:
            retention_days: Number of days to retain aggregated data

        Returns:
            Number of deleted records
        """
        if retention_days is None:
            retention_days = self._retention_days

        cutoff_time = datetime.now() - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up aggregated metrics
                cursor.execute("""
                    DELETE FROM aggregated_metrics
                    WHERE created_at < ?
                """, (cutoff_time.isoformat(),))

                aggregated_deleted = cursor.rowcount

                # Clean up statistical summaries
                cursor.execute("""
                    DELETE FROM statistical_summaries
                    WHERE created_at < ?
                """, (cutoff_time.isoformat(),))

                summaries_deleted = cursor.rowcount

                # Clean up expired cache entries
                cursor.execute("""
                    DELETE FROM aggregation_cache
                    WHERE expiry_time < ?
                """, (datetime.now().isoformat(),))

                cache_deleted = cursor.rowcount

                conn.commit()
                total_deleted = aggregated_deleted + summaries_deleted + cache_deleted

                self._logger.info(f"Cleaned up {total_deleted} old aggregation records")
                return total_deleted

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old aggregations: {e}")
                raise
            finally:
                conn.close()
