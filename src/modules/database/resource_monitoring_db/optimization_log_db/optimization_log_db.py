"""
Module: optimization_log_db
Description: Records optimization trigger events, actions taken, and their effectiveness
Phase: 2
Location: /src/modules/database/resource_monitoring_db/optimization_log_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class OptimizationLogDB:
    """
    Optimization log database manager.
    
    Records optimization trigger events, actions taken, and their effectiveness.
    Tracks IDRAlloc optimization decisions, resource allocation changes, and
    performance impact measurements for continuous improvement.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the optimization log database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "optimization_log.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._detailed_retention_days = 90  # Keep detailed logs for 90 days
        self._summary_retention_months = 12  # Keep summaries for 12 months
        
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
                
                # Create optimization events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        trigger_type TEXT NOT NULL,
                        trigger_source TEXT NOT NULL,
                        trigger_condition TEXT,
                        severity_level TEXT NOT NULL,
                        resource_category TEXT NOT NULL,
                        current_metrics TEXT,
                        threshold_values TEXT,
                        trigger_reason TEXT,
                        system_state TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create optimization actions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action_id TEXT NOT NULL UNIQUE,
                        event_id TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        action_type TEXT NOT NULL,
                        action_category TEXT NOT NULL,
                        action_description TEXT,
                        target_resource TEXT,
                        previous_allocation TEXT,
                        new_allocation TEXT,
                        allocation_change_percent REAL,
                        expected_impact TEXT,
                        action_parameters TEXT,
                        execution_status TEXT DEFAULT 'pending',
                        execution_duration_ms INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES optimization_events(event_id)
                    )
                """)
                
                # Create optimization results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        result_id TEXT NOT NULL UNIQUE,
                        action_id TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        measurement_period_minutes INTEGER,
                        before_metrics TEXT,
                        after_metrics TEXT,
                        performance_improvement_percent REAL,
                        efficiency_improvement_percent REAL,
                        resource_utilization_change REAL,
                        stability_impact_score REAL,
                        success_indicator BOOLEAN,
                        side_effects TEXT,
                        rollback_required BOOLEAN DEFAULT 0,
                        effectiveness_score REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (action_id) REFERENCES optimization_actions(action_id)
                    )
                """)
                
                # Create IDRAlloc optimization log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS idralloc_optimization_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        optimization_type TEXT NOT NULL,
                        memory_tier TEXT NOT NULL,
                        current_allocation_gb REAL,
                        target_allocation_gb REAL,
                        allocation_change_gb REAL,
                        gpu_memory_pressure REAL,
                        ram_memory_pressure REAL,
                        nvme_utilization REAL,
                        bridge_active BOOLEAN,
                        bridge_throughput_gbps REAL,
                        prediction_confidence REAL,
                        optimization_reason TEXT,
                        execution_result TEXT,
                        performance_impact TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create optimization patterns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        pattern_type TEXT NOT NULL,
                        trigger_conditions TEXT,
                        action_sequence TEXT,
                        success_rate REAL,
                        average_improvement REAL,
                        usage_frequency INTEGER,
                        last_used TIMESTAMP,
                        effectiveness_trend TEXT,
                        recommended BOOLEAN DEFAULT 1,
                        pattern_metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create optimization summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        summary_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        period_start TIMESTAMP NOT NULL,
                        period_end TIMESTAMP NOT NULL,
                        total_events INTEGER,
                        total_actions INTEGER,
                        successful_actions INTEGER,
                        failed_actions INTEGER,
                        average_improvement REAL,
                        total_resource_savings REAL,
                        most_effective_action TEXT,
                        most_frequent_trigger TEXT,
                        optimization_categories TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON optimization_events(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_trigger_type ON optimization_events(trigger_type, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_event_id ON optimization_actions(event_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_timestamp ON optimization_actions(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_action_id ON optimization_results(action_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_timestamp ON optimization_results(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_idralloc_timestamp ON idralloc_optimization_log(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON optimization_patterns(pattern_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_summary_timestamp ON optimization_summary(timestamp DESC)")
                
                conn.commit()
                self._logger.info("Optimization log database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize optimization log database: {e}")
                raise
            finally:
                conn.close()

    def log_optimization_event(self, event_data: Dict[str, Any]) -> str:
        """
        Log an optimization trigger event.

        Args:
            event_data: Dictionary containing event details

        Returns:
            Event ID for tracking related actions
        """
        event_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO optimization_events (
                        event_id, timestamp, trigger_type, trigger_source,
                        trigger_condition, severity_level, resource_category,
                        current_metrics, threshold_values, trigger_reason,
                        system_state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    event_data.get('timestamp', datetime.now()),
                    event_data.get('trigger_type'),
                    event_data.get('trigger_source'),
                    event_data.get('trigger_condition'),
                    event_data.get('severity_level'),
                    event_data.get('resource_category'),
                    json.dumps(event_data.get('current_metrics', {})),
                    json.dumps(event_data.get('threshold_values', {})),
                    event_data.get('trigger_reason'),
                    json.dumps(event_data.get('system_state', {}))
                ))
                conn.commit()
                self._logger.info(f"Optimization event logged: {event_id}")
                return event_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log optimization event: {e}")
                raise
            finally:
                conn.close()

    def log_optimization_action(self, action_data: Dict[str, Any]) -> str:
        """
        Log an optimization action taken.

        Args:
            action_data: Dictionary containing action details

        Returns:
            Action ID for tracking results
        """
        action_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO optimization_actions (
                        action_id, event_id, timestamp, action_type,
                        action_category, action_description, target_resource,
                        previous_allocation, new_allocation, allocation_change_percent,
                        expected_impact, action_parameters, execution_status,
                        execution_duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    action_id,
                    action_data.get('event_id'),
                    action_data.get('timestamp', datetime.now()),
                    action_data.get('action_type'),
                    action_data.get('action_category'),
                    action_data.get('action_description'),
                    action_data.get('target_resource'),
                    json.dumps(action_data.get('previous_allocation', {})),
                    json.dumps(action_data.get('new_allocation', {})),
                    action_data.get('allocation_change_percent'),
                    json.dumps(action_data.get('expected_impact', {})),
                    json.dumps(action_data.get('action_parameters', {})),
                    action_data.get('execution_status', 'pending'),
                    action_data.get('execution_duration_ms')
                ))
                conn.commit()
                self._logger.info(f"Optimization action logged: {action_id}")
                return action_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log optimization action: {e}")
                raise
            finally:
                conn.close()

    def log_optimization_result(self, result_data: Dict[str, Any]) -> str:
        """
        Log the results of an optimization action.

        Args:
            result_data: Dictionary containing result details

        Returns:
            Result ID for tracking
        """
        result_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO optimization_results (
                        result_id, action_id, timestamp, measurement_period_minutes,
                        before_metrics, after_metrics, performance_improvement_percent,
                        efficiency_improvement_percent, resource_utilization_change,
                        stability_impact_score, success_indicator, side_effects,
                        rollback_required, effectiveness_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result_id,
                    result_data.get('action_id'),
                    result_data.get('timestamp', datetime.now()),
                    result_data.get('measurement_period_minutes'),
                    json.dumps(result_data.get('before_metrics', {})),
                    json.dumps(result_data.get('after_metrics', {})),
                    result_data.get('performance_improvement_percent'),
                    result_data.get('efficiency_improvement_percent'),
                    result_data.get('resource_utilization_change'),
                    result_data.get('stability_impact_score'),
                    result_data.get('success_indicator'),
                    json.dumps(result_data.get('side_effects', [])),
                    result_data.get('rollback_required', False),
                    result_data.get('effectiveness_score')
                ))
                conn.commit()
                self._logger.info(f"Optimization result logged: {result_id}")
                return result_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log optimization result: {e}")
                raise
            finally:
                conn.close()

    def log_idralloc_optimization(self, idralloc_data: Dict[str, Any]) -> str:
        """
        Log IDRAlloc-specific optimization event.

        Args:
            idralloc_data: Dictionary containing IDRAlloc optimization details

        Returns:
            Log ID for tracking
        """
        log_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO idralloc_optimization_log (
                        log_id, timestamp, optimization_type, memory_tier,
                        current_allocation_gb, target_allocation_gb, allocation_change_gb,
                        gpu_memory_pressure, ram_memory_pressure, nvme_utilization,
                        bridge_active, bridge_throughput_gbps, prediction_confidence,
                        optimization_reason, execution_result, performance_impact
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id,
                    idralloc_data.get('timestamp', datetime.now()),
                    idralloc_data.get('optimization_type'),
                    idralloc_data.get('memory_tier'),
                    idralloc_data.get('current_allocation_gb'),
                    idralloc_data.get('target_allocation_gb'),
                    idralloc_data.get('allocation_change_gb'),
                    idralloc_data.get('gpu_memory_pressure'),
                    idralloc_data.get('ram_memory_pressure'),
                    idralloc_data.get('nvme_utilization'),
                    idralloc_data.get('bridge_active'),
                    idralloc_data.get('bridge_throughput_gbps'),
                    idralloc_data.get('prediction_confidence'),
                    idralloc_data.get('optimization_reason'),
                    idralloc_data.get('execution_result'),
                    json.dumps(idralloc_data.get('performance_impact', {}))
                ))
                conn.commit()
                self._logger.info(f"IDRAlloc optimization logged: {log_id}")
                return log_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log IDRAlloc optimization: {e}")
                raise
            finally:
                conn.close()

    def get_optimization_events(self, hours: int = 24, trigger_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent optimization events.

        Args:
            hours: Number of hours of events to retrieve
            trigger_type: Specific trigger type to filter by

        Returns:
            List of optimization event dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if trigger_type:
                    cursor.execute("""
                        SELECT * FROM optimization_events
                        WHERE timestamp >= ? AND trigger_type = ?
                        ORDER BY timestamp DESC
                    """, (cutoff_time, trigger_type))
                else:
                    cursor.execute("""
                        SELECT * FROM optimization_events
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_optimization_actions(self, event_id: Optional[str] = None,
                               hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get optimization actions.

        Args:
            event_id: Specific event ID to filter by
            hours: Number of hours of actions to retrieve

        Returns:
            List of optimization action dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if event_id:
                    cursor.execute("""
                        SELECT * FROM optimization_actions
                        WHERE event_id = ?
                        ORDER BY timestamp DESC
                    """, (event_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM optimization_actions
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_optimization_results(self, action_id: Optional[str] = None,
                               hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get optimization results.

        Args:
            action_id: Specific action ID to filter by
            hours: Number of hours of results to retrieve

        Returns:
            List of optimization result dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if action_id:
                    cursor.execute("""
                        SELECT * FROM optimization_results
                        WHERE action_id = ?
                        ORDER BY timestamp DESC
                    """, (action_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM optimization_results
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_idralloc_optimization_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get IDRAlloc optimization history.

        Args:
            days: Number of days of history to retrieve

        Returns:
            List of IDRAlloc optimization dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM idralloc_optimization_log
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_optimization_effectiveness_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get optimization effectiveness summary.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary containing effectiveness metrics
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get overall statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(DISTINCT trigger_type) as unique_triggers
                    FROM optimization_events
                    WHERE timestamp >= ?
                """, (cutoff_time,))

                event_stats = cursor.fetchone()

                # Get action statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_actions,
                        SUM(CASE WHEN execution_status = 'completed' THEN 1 ELSE 0 END) as completed_actions,
                        SUM(CASE WHEN execution_status = 'failed' THEN 1 ELSE 0 END) as failed_actions
                    FROM optimization_actions
                    WHERE timestamp >= ?
                """, (cutoff_time,))

                action_stats = cursor.fetchone()

                # Get effectiveness statistics
                cursor.execute("""
                    SELECT
                        AVG(effectiveness_score) as avg_effectiveness,
                        AVG(performance_improvement_percent) as avg_performance_improvement,
                        COUNT(CASE WHEN success_indicator = 1 THEN 1 END) as successful_results,
                        COUNT(*) as total_results
                    FROM optimization_results
                    WHERE timestamp >= ?
                """, (cutoff_time,))

                result_stats = cursor.fetchone()

                return {
                    'analysis_period_days': days,
                    'total_events': event_stats[0] if event_stats[0] else 0,
                    'unique_trigger_types': event_stats[1] if event_stats[1] else 0,
                    'total_actions': action_stats[0] if action_stats[0] else 0,
                    'completed_actions': action_stats[1] if action_stats[1] else 0,
                    'failed_actions': action_stats[2] if action_stats[2] else 0,
                    'success_rate': (action_stats[1] / action_stats[0] * 100) if action_stats[0] > 0 else 0,
                    'avg_effectiveness_score': result_stats[0] if result_stats[0] else 0,
                    'avg_performance_improvement': result_stats[1] if result_stats[1] else 0,
                    'successful_results': result_stats[2] if result_stats[2] else 0,
                    'total_results': result_stats[3] if result_stats[3] else 0
                }

            finally:
                conn.close()

    def cleanup_old_data(self) -> None:
        """Clean up old optimization log data based on retention policies."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up old detailed logs
                detailed_cutoff = datetime.now() - timedelta(days=self._detailed_retention_days)

                cursor.execute("DELETE FROM optimization_events WHERE timestamp < ?", (detailed_cutoff,))
                cursor.execute("DELETE FROM optimization_actions WHERE timestamp < ?", (detailed_cutoff,))
                cursor.execute("DELETE FROM optimization_results WHERE timestamp < ?", (detailed_cutoff,))
                cursor.execute("DELETE FROM idralloc_optimization_log WHERE timestamp < ?", (detailed_cutoff,))

                # Clean up old summaries
                summary_cutoff = datetime.now() - timedelta(days=self._summary_retention_months * 30)
                cursor.execute("DELETE FROM optimization_summary WHERE timestamp < ?", (summary_cutoff,))

                # Keep optimization patterns longer as they are valuable for learning
                pattern_cutoff = datetime.now() - timedelta(days=365)  # Keep patterns for 1 year
                cursor.execute("DELETE FROM optimization_patterns WHERE timestamp < ?", (pattern_cutoff,))

                conn.commit()
                self._logger.info("Optimization log data cleanup completed successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup optimization log data: {e}")
            finally:
                conn.close()

    def update_action_status(self, action_id: str, status: str,
                           execution_duration_ms: Optional[int] = None) -> None:
        """
        Update the execution status of an optimization action.

        Args:
            action_id: ID of the action to update
            status: New execution status
            execution_duration_ms: Duration of execution in milliseconds
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if execution_duration_ms is not None:
                    cursor.execute("""
                        UPDATE optimization_actions
                        SET execution_status = ?, execution_duration_ms = ?
                        WHERE action_id = ?
                    """, (status, execution_duration_ms, action_id))
                else:
                    cursor.execute("""
                        UPDATE optimization_actions
                        SET execution_status = ?
                        WHERE action_id = ?
                    """, (status, action_id))

                conn.commit()

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update action status: {e}")
                raise
            finally:
                conn.close()
