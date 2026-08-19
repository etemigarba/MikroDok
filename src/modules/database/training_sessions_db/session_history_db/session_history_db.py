"""
Module: session_history_db
Description: Maintains historical training session data with metrics tracking and analysis capabilities
Phase: 4
Location: /src/modules/database/training_sessions_db/session_history_db/
"""

# Standard library imports
import json
import sqlite3
import statistics
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class HistoryEventType(Enum):
    """History event type enumeration."""
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"
    SESSION_CANCELLED = "session_cancelled"
    EPOCH_COMPLETED = "epoch_completed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    METRIC_RECORDED = "metric_recorded"
    ERROR_OCCURRED = "error_occurred"
    RESOURCE_ALLOCATED = "resource_allocated"
    HYPERPARAMETER_UPDATED = "hyperparameter_updated"


class MetricAggregationType(Enum):
    """Metric aggregation types."""
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    SUM = "sum"
    COUNT = "count"
    MEDIAN = "median"
    STANDARD_DEVIATION = "std_dev"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"


class SessionHistoryDB:
    """
    Session history database for training session historical data management.
    
    Maintains historical training session data with comprehensive metrics tracking,
    event logging, and analysis capabilities. Provides thread-safe operations
    with transaction support for historical data persistence, time-series metrics
    storage, and analytical queries with configurable retention policies.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the session history database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training sessions data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_sessions"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "session_history.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._history_retention_days = 730  # Keep history for 2 years
        self._metrics_retention_days = 365  # Keep detailed metrics for 1 year
        self._aggregation_retention_days = 1095  # Keep aggregated data for 3 years
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
                
                # Create session history events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_history_events (
                        event_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        event_timestamp TEXT NOT NULL,
                        event_data_json TEXT,
                        event_source TEXT,
                        event_category TEXT,
                        severity_level TEXT DEFAULT 'info',
                        duration_ms INTEGER,
                        resource_usage_json TEXT,
                        error_details TEXT,
                        correlation_id TEXT,
                        tags_json TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session_id ON session_history_events (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON session_history_events (event_timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_type ON session_history_events (event_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_category ON session_history_events (event_category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session_type ON session_history_events (session_id, event_type)")
                
                # Create time-series metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_metrics_timeseries (
                        metric_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_unit TEXT,
                        timestamp TEXT NOT NULL,
                        epoch INTEGER,
                        step INTEGER,
                        batch_size INTEGER,
                        learning_rate REAL,
                        gradient_norm REAL,
                        loss_value REAL,
                        accuracy_value REAL,
                        validation_metric REAL,
                        resource_utilization_json TEXT,
                        model_parameters_json TEXT,
                        metadata_json TEXT
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_session_id ON session_metrics_timeseries (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON session_metrics_timeseries (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON session_metrics_timeseries (metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_epoch ON session_metrics_timeseries (epoch)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_session_name ON session_metrics_timeseries (session_id, metric_name)")
                
                # Create aggregated metrics table for performance
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_metrics_aggregated (
                        aggregation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        aggregation_type TEXT NOT NULL,
                        aggregation_period TEXT NOT NULL,
                        period_start TEXT NOT NULL,
                        period_end TEXT NOT NULL,
                        aggregated_value REAL NOT NULL,
                        sample_count INTEGER NOT NULL,
                        min_value REAL,
                        max_value REAL,
                        std_deviation REAL,
                        percentile_95 REAL,
                        percentile_99 REAL,
                        created_at TEXT NOT NULL,
                        metadata_json TEXT
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_agg_session_id ON session_metrics_aggregated (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_agg_period ON session_metrics_aggregated (aggregation_period)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_agg_metric ON session_metrics_aggregated (metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_agg_type ON session_metrics_aggregated (aggregation_type)")
                
                # Create session summaries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_summaries (
                        summary_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        model_id TEXT NOT NULL,
                        session_name TEXT,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        total_duration_seconds REAL,
                        total_epochs INTEGER,
                        total_steps INTEGER,
                        final_status TEXT,
                        best_metric_name TEXT,
                        best_metric_value REAL,
                        final_loss REAL,
                        final_accuracy REAL,
                        total_checkpoints INTEGER,
                        total_errors INTEGER,
                        resource_efficiency_score REAL,
                        convergence_epoch INTEGER,
                        training_stability_score REAL,
                        hyperparameters_json TEXT,
                        resource_usage_summary_json TEXT,
                        performance_metrics_json TEXT,
                        notes TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_session_id ON session_summaries (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_model_id ON session_summaries (model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_start_time ON session_summaries (start_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_status ON session_summaries (final_status)")
                
                conn.commit()
                self._logger.info("Session history database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize session history database: {e}")
                raise
            finally:
                conn.close()
    
    def record_event(self, session_id: str, event_type: HistoryEventType, event_data: Optional[Dict[str, Any]] = None,
                    event_source: Optional[str] = None, event_category: Optional[str] = None,
                    severity_level: str = "info", duration_ms: Optional[int] = None,
                    resource_usage: Optional[Dict[str, Any]] = None, error_details: Optional[str] = None,
                    correlation_id: Optional[str] = None, tags: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a historical event for a training session.
        
        Args:
            session_id: Session identifier
            event_type: Type of event
            event_data: Event-specific data
            event_source: Source of the event
            event_category: Event category
            severity_level: Severity level (info, warning, error, critical)
            duration_ms: Event duration in milliseconds
            resource_usage: Resource usage during event
            error_details: Error details if applicable
            correlation_id: Correlation ID for related events
            tags: Event tags
            metadata: Additional metadata
            
        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO session_history_events (
                        event_id, session_id, event_type, event_timestamp,
                        event_data_json, event_source, event_category, severity_level,
                        duration_ms, resource_usage_json, error_details, correlation_id,
                        tags_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, session_id, event_type.value, current_time,
                    json.dumps(event_data) if event_data else None,
                    event_source, event_category, severity_level, duration_ms,
                    json.dumps(resource_usage) if resource_usage else None,
                    error_details, correlation_id,
                    json.dumps(tags) if tags else None,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                return event_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record event for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def record_metric(self, session_id: str, metric_name: str, metric_value: float,
                     metric_type: str = "training", metric_unit: Optional[str] = None,
                     epoch: Optional[int] = None, step: Optional[int] = None,
                     batch_size: Optional[int] = None, learning_rate: Optional[float] = None,
                     gradient_norm: Optional[float] = None, loss_value: Optional[float] = None,
                     accuracy_value: Optional[float] = None, validation_metric: Optional[float] = None,
                     resource_utilization: Optional[Dict[str, Any]] = None,
                     model_parameters: Optional[Dict[str, Any]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a time-series metric for a training session.

        Args:
            session_id: Session identifier
            metric_name: Name of the metric
            metric_value: Metric value
            metric_type: Type of metric (training, validation, test)
            metric_unit: Unit of measurement
            epoch: Training epoch
            step: Training step
            batch_size: Batch size used
            learning_rate: Learning rate at this point
            gradient_norm: Gradient norm
            loss_value: Loss value
            accuracy_value: Accuracy value
            validation_metric: Validation metric value
            resource_utilization: Resource usage data
            model_parameters: Model parameter information
            metadata: Additional metadata

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO session_metrics_timeseries (
                        metric_id, session_id, metric_name, metric_value, metric_type,
                        metric_unit, timestamp, epoch, step, batch_size, learning_rate,
                        gradient_norm, loss_value, accuracy_value, validation_metric,
                        resource_utilization_json, model_parameters_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, session_id, metric_name, metric_value, metric_type,
                    metric_unit, current_time, epoch, step, batch_size, learning_rate,
                    gradient_norm, loss_value, accuracy_value, validation_metric,
                    json.dumps(resource_utilization) if resource_utilization else None,
                    json.dumps(model_parameters) if model_parameters else None,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record metric for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def get_session_events(self, session_id: str, event_type: Optional[HistoryEventType] = None,
                          start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
                          limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get historical events for a training session.

        Args:
            session_id: Session identifier
            event_type: Filter by event type
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of events to return

        Returns:
            List of event records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT event_id, session_id, event_type, event_timestamp,
                           event_data_json, event_source, event_category, severity_level,
                           duration_ms, resource_usage_json, error_details, correlation_id,
                           tags_json, metadata_json
                    FROM session_history_events
                    WHERE session_id = ?
                """
                params = [session_id]

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type.value)

                if start_time:
                    query += " AND event_timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND event_timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY event_timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)

                events = []
                for row in cursor.fetchall():
                    event_data = {
                        'event_id': row[0],
                        'session_id': row[1],
                        'event_type': row[2],
                        'event_timestamp': row[3],
                        'event_data': json.loads(row[4]) if row[4] else None,
                        'event_source': row[5],
                        'event_category': row[6],
                        'severity_level': row[7],
                        'duration_ms': row[8],
                        'resource_usage': json.loads(row[9]) if row[9] else None,
                        'error_details': row[10],
                        'correlation_id': row[11],
                        'tags': json.loads(row[12]) if row[12] else None,
                        'metadata': json.loads(row[13]) if row[13] else None
                    }
                    events.append(event_data)

                return events

            except Exception as e:
                self._logger.error(f"Failed to get events for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def get_session_metrics(self, session_id: str, metric_name: Optional[str] = None,
                           start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
                           limit: int = 10000) -> List[Dict[str, Any]]:
        """
        Get time-series metrics for a training session.

        Args:
            session_id: Session identifier
            metric_name: Filter by metric name
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of metrics to return

        Returns:
            List of metric records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT metric_id, session_id, metric_name, metric_value, metric_type,
                           metric_unit, timestamp, epoch, step, batch_size, learning_rate,
                           gradient_norm, loss_value, accuracy_value, validation_metric,
                           resource_utilization_json, model_parameters_json, metadata_json
                    FROM session_metrics_timeseries
                    WHERE session_id = ?
                """
                params = [session_id]

                if metric_name:
                    query += " AND metric_name = ?"
                    params.append(metric_name)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp ASC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)

                metrics = []
                for row in cursor.fetchall():
                    metric_data = {
                        'metric_id': row[0],
                        'session_id': row[1],
                        'metric_name': row[2],
                        'metric_value': row[3],
                        'metric_type': row[4],
                        'metric_unit': row[5],
                        'timestamp': row[6],
                        'epoch': row[7],
                        'step': row[8],
                        'batch_size': row[9],
                        'learning_rate': row[10],
                        'gradient_norm': row[11],
                        'loss_value': row[12],
                        'accuracy_value': row[13],
                        'validation_metric': row[14],
                        'resource_utilization': json.loads(row[15]) if row[15] else None,
                        'model_parameters': json.loads(row[16]) if row[16] else None,
                        'metadata': json.loads(row[17]) if row[17] else None
                    }
                    metrics.append(metric_data)

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get metrics for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def create_session_summary(self, session_id: str, model_id: str, session_name: Optional[str] = None,
                              start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
                              total_duration_seconds: Optional[float] = None, total_epochs: Optional[int] = None,
                              total_steps: Optional[int] = None, final_status: Optional[str] = None,
                              best_metric_name: Optional[str] = None, best_metric_value: Optional[float] = None,
                              final_loss: Optional[float] = None, final_accuracy: Optional[float] = None,
                              total_checkpoints: Optional[int] = None, total_errors: Optional[int] = None,
                              resource_efficiency_score: Optional[float] = None,
                              convergence_epoch: Optional[int] = None,
                              training_stability_score: Optional[float] = None,
                              hyperparameters: Optional[Dict[str, Any]] = None,
                              resource_usage_summary: Optional[Dict[str, Any]] = None,
                              performance_metrics: Optional[Dict[str, Any]] = None,
                              notes: Optional[str] = None) -> str:
        """
        Create a summary record for a completed training session.

        Args:
            session_id: Session identifier
            model_id: Model identifier
            session_name: Session name
            start_time: Session start time
            end_time: Session end time
            total_duration_seconds: Total training duration
            total_epochs: Total epochs completed
            total_steps: Total training steps
            final_status: Final session status
            best_metric_name: Name of best metric
            best_metric_value: Best metric value achieved
            final_loss: Final loss value
            final_accuracy: Final accuracy value
            total_checkpoints: Number of checkpoints created
            total_errors: Number of errors encountered
            resource_efficiency_score: Resource efficiency score
            convergence_epoch: Epoch where convergence was achieved
            training_stability_score: Training stability score
            hyperparameters: Hyperparameter configuration
            resource_usage_summary: Resource usage summary
            performance_metrics: Performance metrics summary
            notes: Additional notes

        Returns:
            Summary ID
        """
        summary_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO session_summaries (
                        summary_id, session_id, model_id, session_name, start_time, end_time,
                        total_duration_seconds, total_epochs, total_steps, final_status,
                        best_metric_name, best_metric_value, final_loss, final_accuracy,
                        total_checkpoints, total_errors, resource_efficiency_score,
                        convergence_epoch, training_stability_score, hyperparameters_json,
                        resource_usage_summary_json, performance_metrics_json, notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    summary_id, session_id, model_id, session_name,
                    start_time.isoformat() if start_time else None,
                    end_time.isoformat() if end_time else None,
                    total_duration_seconds, total_epochs, total_steps, final_status,
                    best_metric_name, best_metric_value, final_loss, final_accuracy,
                    total_checkpoints, total_errors, resource_efficiency_score,
                    convergence_epoch, training_stability_score,
                    json.dumps(hyperparameters) if hyperparameters else None,
                    json.dumps(resource_usage_summary) if resource_usage_summary else None,
                    json.dumps(performance_metrics) if performance_metrics else None,
                    notes, current_time, current_time
                ))

                conn.commit()
                return summary_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create session summary for {session_id}: {e}")
                raise
            finally:
                conn.close()

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session summary by session ID.

        Args:
            session_id: Session identifier

        Returns:
            Session summary data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT summary_id, session_id, model_id, session_name, start_time, end_time,
                           total_duration_seconds, total_epochs, total_steps, final_status,
                           best_metric_name, best_metric_value, final_loss, final_accuracy,
                           total_checkpoints, total_errors, resource_efficiency_score,
                           convergence_epoch, training_stability_score, hyperparameters_json,
                           resource_usage_summary_json, performance_metrics_json, notes,
                           created_at, updated_at
                    FROM session_summaries
                    WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'summary_id': row[0],
                    'session_id': row[1],
                    'model_id': row[2],
                    'session_name': row[3],
                    'start_time': row[4],
                    'end_time': row[5],
                    'total_duration_seconds': row[6],
                    'total_epochs': row[7],
                    'total_steps': row[8],
                    'final_status': row[9],
                    'best_metric_name': row[10],
                    'best_metric_value': row[11],
                    'final_loss': row[12],
                    'final_accuracy': row[13],
                    'total_checkpoints': row[14],
                    'total_errors': row[15],
                    'resource_efficiency_score': row[16],
                    'convergence_epoch': row[17],
                    'training_stability_score': row[18],
                    'hyperparameters': json.loads(row[19]) if row[19] else None,
                    'resource_usage_summary': json.loads(row[20]) if row[20] else None,
                    'performance_metrics': json.loads(row[21]) if row[21] else None,
                    'notes': row[22],
                    'created_at': row[23],
                    'updated_at': row[24]
                }

            except Exception as e:
                self._logger.error(f"Failed to get session summary for {session_id}: {e}")
                return None
            finally:
                conn.close()

    def aggregate_metrics(self, session_id: str, metric_name: str,
                         aggregation_type: MetricAggregationType,
                         aggregation_period: str = "hourly",
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Aggregate metrics for analysis and reporting.

        Args:
            session_id: Session identifier
            metric_name: Name of metric to aggregate
            aggregation_type: Type of aggregation
            aggregation_period: Period for aggregation (hourly, daily, epoch)
            start_time: Start time for aggregation
            end_time: End time for aggregation

        Returns:
            List of aggregated metric records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get raw metrics
                query = """
                    SELECT metric_value, timestamp, epoch
                    FROM session_metrics_timeseries
                    WHERE session_id = ? AND metric_name = ?
                """
                params = [session_id, metric_name]

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp ASC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                if not rows:
                    return []

                # Group metrics by period
                grouped_metrics = self._group_metrics_by_period(rows, aggregation_period)

                # Calculate aggregations
                aggregated_results = []
                for period_key, metrics in grouped_metrics.items():
                    values = [m[0] for m in metrics]  # metric_value is first element

                    if aggregation_type == MetricAggregationType.AVERAGE:
                        aggregated_value = statistics.mean(values)
                    elif aggregation_type == MetricAggregationType.MINIMUM:
                        aggregated_value = min(values)
                    elif aggregation_type == MetricAggregationType.MAXIMUM:
                        aggregated_value = max(values)
                    elif aggregation_type == MetricAggregationType.SUM:
                        aggregated_value = sum(values)
                    elif aggregation_type == MetricAggregationType.COUNT:
                        aggregated_value = len(values)
                    elif aggregation_type == MetricAggregationType.MEDIAN:
                        aggregated_value = statistics.median(values)
                    elif aggregation_type == MetricAggregationType.STANDARD_DEVIATION:
                        aggregated_value = statistics.stdev(values) if len(values) > 1 else 0
                    else:
                        aggregated_value = statistics.mean(values)  # Default to average

                    # Calculate additional statistics
                    min_value = min(values)
                    max_value = max(values)
                    std_dev = statistics.stdev(values) if len(values) > 1 else 0

                    # Calculate percentiles
                    sorted_values = sorted(values)
                    p95_idx = int(0.95 * len(sorted_values))
                    p99_idx = int(0.99 * len(sorted_values))
                    p95 = sorted_values[min(p95_idx, len(sorted_values) - 1)]
                    p99 = sorted_values[min(p99_idx, len(sorted_values) - 1)]

                    aggregated_results.append({
                        'period': period_key,
                        'aggregation_type': aggregation_type.value,
                        'aggregated_value': aggregated_value,
                        'sample_count': len(values),
                        'min_value': min_value,
                        'max_value': max_value,
                        'std_deviation': std_dev,
                        'percentile_95': p95,
                        'percentile_99': p99
                    })

                return aggregated_results

            except Exception as e:
                self._logger.error(f"Failed to aggregate metrics for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def _group_metrics_by_period(self, metrics: List[Tuple], period: str) -> Dict[str, List[Tuple]]:
        """Group metrics by time period."""
        grouped = {}

        for metric in metrics:
            timestamp_str = metric[1]  # timestamp is second element
            timestamp = datetime.fromisoformat(timestamp_str)

            if period == "hourly":
                period_key = timestamp.strftime("%Y-%m-%d %H:00")
            elif period == "daily":
                period_key = timestamp.strftime("%Y-%m-%d")
            elif period == "epoch":
                epoch = metric[2]  # epoch is third element
                period_key = f"epoch_{epoch}" if epoch is not None else "epoch_unknown"
            else:
                period_key = timestamp.strftime("%Y-%m-%d %H:00")  # Default to hourly

            if period_key not in grouped:
                grouped[period_key] = []
            grouped[period_key].append(metric)

        return grouped

    def cleanup_old_history(self) -> int:
        """
        Clean up old historical data based on retention policies.

        Returns:
            Number of records cleaned up
        """
        current_time = datetime.now(timezone.utc)

        # Calculate cutoff dates
        history_cutoff = (current_time - timedelta(days=self._history_retention_days)).isoformat()
        metrics_cutoff = (current_time - timedelta(days=self._metrics_retention_days)).isoformat()
        aggregation_cutoff = (current_time - timedelta(days=self._aggregation_retention_days)).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up old events
                cursor.execute("""
                    DELETE FROM session_history_events
                    WHERE event_timestamp < ?
                """, (history_cutoff,))
                events_cleaned = cursor.rowcount

                # Clean up old metrics
                cursor.execute("""
                    DELETE FROM session_metrics_timeseries
                    WHERE timestamp < ?
                """, (metrics_cutoff,))
                metrics_cleaned = cursor.rowcount

                # Clean up old aggregations
                cursor.execute("""
                    DELETE FROM session_metrics_aggregated
                    WHERE created_at < ?
                """, (aggregation_cutoff,))
                aggregations_cleaned = cursor.rowcount

                conn.commit()

                total_cleaned = events_cleaned + metrics_cleaned + aggregations_cleaned
                self._logger.info(f"Cleaned up {total_cleaned} old history records")
                return total_cleaned

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old history: {e}")
                return 0
            finally:
                conn.close()

    def get_history_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about session history data.

        Returns:
            Dictionary with history statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get event statistics
                cursor.execute("SELECT COUNT(*) FROM session_history_events")
                total_events = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT event_type, COUNT(*)
                    FROM session_history_events
                    GROUP BY event_type
                    ORDER BY COUNT(*) DESC
                """)
                event_type_counts = dict(cursor.fetchall())

                # Get metrics statistics
                cursor.execute("SELECT COUNT(*) FROM session_metrics_timeseries")
                total_metrics = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT metric_name, COUNT(*)
                    FROM session_metrics_timeseries
                    GROUP BY metric_name
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                metric_name_counts = dict(cursor.fetchall())

                # Get summary statistics
                cursor.execute("SELECT COUNT(*) FROM session_summaries")
                total_summaries = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT final_status, COUNT(*)
                    FROM session_summaries
                    GROUP BY final_status
                """)
                status_counts = dict(cursor.fetchall())

                # Get aggregation statistics
                cursor.execute("SELECT COUNT(*) FROM session_metrics_aggregated")
                total_aggregations = cursor.fetchone()[0]

                # Get database size information
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                db_size_bytes = cursor.fetchone()[0]

                return {
                    'total_events': total_events,
                    'event_type_counts': event_type_counts,
                    'total_metrics': total_metrics,
                    'metric_name_counts': metric_name_counts,
                    'total_summaries': total_summaries,
                    'session_status_counts': status_counts,
                    'total_aggregations': total_aggregations,
                    'database_size_bytes': db_size_bytes,
                    'database_size_mb': round(db_size_bytes / (1024 * 1024), 2)
                }

            except Exception as e:
                self._logger.error(f"Failed to get history statistics: {e}")
                return {}
            finally:
                conn.close()

    def export_session_data(self, session_id: str, include_events: bool = True,
                           include_metrics: bool = True, include_summary: bool = True) -> Dict[str, Any]:
        """
        Export all historical data for a session.

        Args:
            session_id: Session identifier
            include_events: Whether to include events
            include_metrics: Whether to include metrics
            include_summary: Whether to include summary

        Returns:
            Dictionary with all session historical data
        """
        export_data = {
            'session_id': session_id,
            'export_timestamp': datetime.now(timezone.utc).isoformat()
        }

        if include_events:
            export_data['events'] = self.get_session_events(session_id)

        if include_metrics:
            export_data['metrics'] = self.get_session_metrics(session_id)

        if include_summary:
            export_data['summary'] = self.get_session_summary(session_id)

        return export_data
