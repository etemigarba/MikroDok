"""
Module: performance_history_db
Description: Long-term storage of aggregated performance metrics for trend analysis and reporting
Phase: 2
Location: /src/modules/database/resource_monitoring_db/performance_history_db/
"""

# Standard library imports
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import statistics

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class PerformanceHistoryDB:
    """
    Performance history database manager.
    
    Handles long-term storage of aggregated performance metrics for trend analysis,
    reporting, and predictive analytics. Provides efficient data aggregation and
    statistical analysis capabilities for resource monitoring data.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the performance history database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "performance_history.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._hourly_retention_days = 90  # Keep hourly data for 90 days
        self._daily_retention_months = 12  # Keep daily data for 12 months
        self._weekly_retention_years = 5   # Keep weekly data for 5 years
        
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
                
                # Create performance summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        period_type TEXT NOT NULL,
                        period_start TIMESTAMP NOT NULL,
                        period_end TIMESTAMP NOT NULL,
                        metric_category TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        avg_value REAL,
                        min_value REAL,
                        max_value REAL,
                        median_value REAL,
                        std_deviation REAL,
                        percentile_95 REAL,
                        percentile_99 REAL,
                        sample_count INTEGER,
                        total_value REAL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create performance trends table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_trends (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        metric_category TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        trend_period TEXT NOT NULL,
                        trend_direction TEXT,
                        trend_strength REAL,
                        slope REAL,
                        correlation_coefficient REAL,
                        prediction_accuracy REAL,
                        anomaly_score REAL,
                        baseline_value REAL,
                        current_value REAL,
                        change_percentage REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create performance benchmarks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_benchmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        benchmark_name TEXT NOT NULL,
                        benchmark_category TEXT NOT NULL,
                        hardware_config TEXT,
                        software_config TEXT,
                        test_duration_seconds INTEGER,
                        cpu_score REAL,
                        gpu_score REAL,
                        memory_score REAL,
                        disk_score REAL,
                        overall_score REAL,
                        percentile_rank REAL,
                        comparison_baseline TEXT,
                        test_conditions TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create system health metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_health_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        health_score REAL NOT NULL,
                        stability_index REAL,
                        performance_index REAL,
                        efficiency_index REAL,
                        thermal_health REAL,
                        memory_health REAL,
                        storage_health REAL,
                        network_health REAL,
                        critical_alerts_count INTEGER,
                        warning_alerts_count INTEGER,
                        uptime_hours REAL,
                        crash_count INTEGER,
                        recovery_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create performance alerts history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_alerts_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        metric_category TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        threshold_value REAL,
                        actual_value REAL,
                        deviation_percentage REAL,
                        duration_seconds INTEGER,
                        resolution_action TEXT,
                        resolution_timestamp TIMESTAMP,
                        impact_assessment TEXT,
                        false_positive BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_summary_time_metric ON performance_summary(timestamp DESC, metric_category, metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_trends_time_metric ON performance_trends(timestamp DESC, metric_category, metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_benchmarks_time_category ON performance_benchmarks(timestamp DESC, benchmark_category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_timestamp ON system_health_metrics(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time_severity ON performance_alerts_history(timestamp DESC, severity)")
                
                conn.commit()
                self._logger.info("Performance history database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize performance history database: {e}")
                raise
            finally:
                conn.close()

    def store_performance_summary(self, summary_data: Dict[str, Any]) -> None:
        """
        Store aggregated performance summary data.

        Args:
            summary_data: Dictionary containing performance summary metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO performance_summary (
                        timestamp, period_type, period_start, period_end,
                        metric_category, metric_name, avg_value, min_value,
                        max_value, median_value, std_deviation, percentile_95,
                        percentile_99, sample_count, total_value, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    summary_data.get('timestamp', datetime.now()),
                    summary_data.get('period_type'),
                    summary_data.get('period_start'),
                    summary_data.get('period_end'),
                    summary_data.get('metric_category'),
                    summary_data.get('metric_name'),
                    summary_data.get('avg_value'),
                    summary_data.get('min_value'),
                    summary_data.get('max_value'),
                    summary_data.get('median_value'),
                    summary_data.get('std_deviation'),
                    summary_data.get('percentile_95'),
                    summary_data.get('percentile_99'),
                    summary_data.get('sample_count'),
                    summary_data.get('total_value'),
                    json.dumps(summary_data.get('metadata', {}))
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store performance summary: {e}")
                raise
            finally:
                conn.close()

    def store_performance_trend(self, trend_data: Dict[str, Any]) -> None:
        """
        Store performance trend analysis data.

        Args:
            trend_data: Dictionary containing trend analysis results
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO performance_trends (
                        timestamp, metric_category, metric_name, trend_period,
                        trend_direction, trend_strength, slope, correlation_coefficient,
                        prediction_accuracy, anomaly_score, baseline_value,
                        current_value, change_percentage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trend_data.get('timestamp', datetime.now()),
                    trend_data.get('metric_category'),
                    trend_data.get('metric_name'),
                    trend_data.get('trend_period'),
                    trend_data.get('trend_direction'),
                    trend_data.get('trend_strength'),
                    trend_data.get('slope'),
                    trend_data.get('correlation_coefficient'),
                    trend_data.get('prediction_accuracy'),
                    trend_data.get('anomaly_score'),
                    trend_data.get('baseline_value'),
                    trend_data.get('current_value'),
                    trend_data.get('change_percentage')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store performance trend: {e}")
                raise
            finally:
                conn.close()

    def store_benchmark_result(self, benchmark_data: Dict[str, Any]) -> None:
        """
        Store performance benchmark results.

        Args:
            benchmark_data: Dictionary containing benchmark results
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO performance_benchmarks (
                        timestamp, benchmark_name, benchmark_category, hardware_config,
                        software_config, test_duration_seconds, cpu_score, gpu_score,
                        memory_score, disk_score, overall_score, percentile_rank,
                        comparison_baseline, test_conditions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    benchmark_data.get('timestamp', datetime.now()),
                    benchmark_data.get('benchmark_name'),
                    benchmark_data.get('benchmark_category'),
                    json.dumps(benchmark_data.get('hardware_config', {})),
                    json.dumps(benchmark_data.get('software_config', {})),
                    benchmark_data.get('test_duration_seconds'),
                    benchmark_data.get('cpu_score'),
                    benchmark_data.get('gpu_score'),
                    benchmark_data.get('memory_score'),
                    benchmark_data.get('disk_score'),
                    benchmark_data.get('overall_score'),
                    benchmark_data.get('percentile_rank'),
                    benchmark_data.get('comparison_baseline'),
                    json.dumps(benchmark_data.get('test_conditions', {}))
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store benchmark result: {e}")
                raise
            finally:
                conn.close()

    def store_system_health_metrics(self, health_data: Dict[str, Any]) -> None:
        """
        Store system health metrics.

        Args:
            health_data: Dictionary containing system health metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_health_metrics (
                        timestamp, health_score, stability_index, performance_index,
                        efficiency_index, thermal_health, memory_health, storage_health,
                        network_health, critical_alerts_count, warning_alerts_count,
                        uptime_hours, crash_count, recovery_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    health_data.get('timestamp', datetime.now()),
                    health_data.get('health_score'),
                    health_data.get('stability_index'),
                    health_data.get('performance_index'),
                    health_data.get('efficiency_index'),
                    health_data.get('thermal_health'),
                    health_data.get('memory_health'),
                    health_data.get('storage_health'),
                    health_data.get('network_health'),
                    health_data.get('critical_alerts_count', 0),
                    health_data.get('warning_alerts_count', 0),
                    health_data.get('uptime_hours'),
                    health_data.get('crash_count', 0),
                    health_data.get('recovery_count', 0)
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store system health metrics: {e}")
                raise
            finally:
                conn.close()

    def get_performance_summary(self, metric_category: str, metric_name: str,
                              period_type: str = "hourly", days: int = 7) -> List[Dict[str, Any]]:
        """
        Get performance summary data for trend analysis.

        Args:
            metric_category: Category of metrics to retrieve
            metric_name: Specific metric name
            period_type: Type of aggregation period ('hourly', 'daily', 'weekly')
            days: Number of days of data to retrieve

        Returns:
            List of performance summary dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM performance_summary
                    WHERE metric_category = ? AND metric_name = ?
                    AND period_type = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (metric_category, metric_name, period_type, cutoff_time))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_performance_trends(self, metric_category: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get performance trend analysis data.

        Args:
            metric_category: Category of metrics to analyze
            days: Number of days of trend data to retrieve

        Returns:
            List of trend analysis dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM performance_trends
                    WHERE metric_category = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (metric_category, cutoff_time))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_benchmark_history(self, benchmark_category: Optional[str] = None,
                            days: int = 90) -> List[Dict[str, Any]]:
        """
        Get benchmark results history.

        Args:
            benchmark_category: Specific benchmark category to filter by
            days: Number of days of benchmark data to retrieve

        Returns:
            List of benchmark result dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if benchmark_category:
                    cursor.execute("""
                        SELECT * FROM performance_benchmarks
                        WHERE benchmark_category = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (benchmark_category, cutoff_time))
                else:
                    cursor.execute("""
                        SELECT * FROM performance_benchmarks
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_system_health_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get system health metrics history.

        Args:
            days: Number of days of health data to retrieve

        Returns:
            List of system health dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM system_health_metrics
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def calculate_performance_statistics(self, values: List[float]) -> Dict[str, float]:
        """
        Calculate statistical metrics for performance data.

        Args:
            values: List of numeric values to analyze

        Returns:
            Dictionary containing statistical metrics
        """
        if not values:
            return {}

        try:
            sorted_values = sorted(values)
            n = len(values)

            stats = {
                'avg_value': statistics.mean(values),
                'min_value': min(values),
                'max_value': max(values),
                'median_value': statistics.median(values),
                'sample_count': n
            }

            if n > 1:
                stats['std_deviation'] = statistics.stdev(values)
            else:
                stats['std_deviation'] = 0.0

            # Calculate percentiles
            if n >= 20:  # Only calculate percentiles for sufficient data
                p95_index = int(0.95 * (n - 1))
                p99_index = int(0.99 * (n - 1))
                stats['percentile_95'] = sorted_values[p95_index]
                stats['percentile_99'] = sorted_values[p99_index]

            return stats

        except Exception as e:
            self._logger.error(f"Failed to calculate performance statistics: {e}")
            return {}

    def aggregate_hourly_data(self, metric_category: str, metric_name: str,
                            start_time: datetime, end_time: datetime,
                            raw_values: List[float]) -> Dict[str, Any]:
        """
        Aggregate raw metric data into hourly summaries.

        Args:
            metric_category: Category of the metric
            metric_name: Name of the metric
            start_time: Start of the aggregation period
            end_time: End of the aggregation period
            raw_values: List of raw metric values

        Returns:
            Dictionary containing aggregated data
        """
        stats = self.calculate_performance_statistics(raw_values)

        return {
            'timestamp': end_time,
            'period_type': 'hourly',
            'period_start': start_time,
            'period_end': end_time,
            'metric_category': metric_category,
            'metric_name': metric_name,
            'total_value': sum(raw_values) if raw_values else 0,
            **stats
        }

    def cleanup_old_data(self) -> None:
        """Clean up old performance history data based on retention policies."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up old hourly summaries
                hourly_cutoff = datetime.now() - timedelta(days=self._hourly_retention_days)
                cursor.execute("""
                    DELETE FROM performance_summary
                    WHERE period_type = 'hourly' AND timestamp < ?
                """, (hourly_cutoff,))

                # Clean up old daily summaries
                daily_cutoff = datetime.now() - timedelta(days=self._daily_retention_months * 30)
                cursor.execute("""
                    DELETE FROM performance_summary
                    WHERE period_type = 'daily' AND timestamp < ?
                """, (daily_cutoff,))

                # Clean up old weekly summaries
                weekly_cutoff = datetime.now() - timedelta(days=self._weekly_retention_years * 365)
                cursor.execute("""
                    DELETE FROM performance_summary
                    WHERE period_type = 'weekly' AND timestamp < ?
                """, (weekly_cutoff,))

                # Clean up old trend data
                trend_cutoff = datetime.now() - timedelta(days=365)  # Keep trends for 1 year
                cursor.execute("""
                    DELETE FROM performance_trends WHERE timestamp < ?
                """, (trend_cutoff,))

                # Clean up old benchmark data
                benchmark_cutoff = datetime.now() - timedelta(days=730)  # Keep benchmarks for 2 years
                cursor.execute("""
                    DELETE FROM performance_benchmarks WHERE timestamp < ?
                """, (benchmark_cutoff,))

                # Clean up old health metrics
                health_cutoff = datetime.now() - timedelta(days=180)  # Keep health data for 6 months
                cursor.execute("""
                    DELETE FROM system_health_metrics WHERE timestamp < ?
                """, (health_cutoff,))

                # Clean up old alert history
                alert_cutoff = datetime.now() - timedelta(days=365)  # Keep alerts for 1 year
                cursor.execute("""
                    DELETE FROM performance_alerts_history WHERE timestamp < ?
                """, (alert_cutoff,))

                conn.commit()
                self._logger.info("Performance history data cleanup completed successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup performance history data: {e}")
            finally:
                conn.close()

    def get_performance_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.

        Args:
            days: Number of days to include in the report

        Returns:
            Dictionary containing performance report data
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get overall system health trend
                cursor.execute("""
                    SELECT AVG(health_score) as avg_health,
                           MIN(health_score) as min_health,
                           MAX(health_score) as max_health,
                           COUNT(*) as sample_count
                    FROM system_health_metrics
                    WHERE timestamp >= ?
                """, (cutoff_time,))

                health_data = cursor.fetchone()

                # Get performance summary by category
                cursor.execute("""
                    SELECT metric_category,
                           AVG(avg_value) as avg_performance,
                           MIN(min_value) as min_performance,
                           MAX(max_value) as max_performance
                    FROM performance_summary
                    WHERE timestamp >= ?
                    GROUP BY metric_category
                """, (cutoff_time,))

                performance_data = cursor.fetchall()

                # Get recent alerts count
                cursor.execute("""
                    SELECT severity, COUNT(*) as alert_count
                    FROM performance_alerts_history
                    WHERE timestamp >= ?
                    GROUP BY severity
                """, (cutoff_time,))

                alerts_data = cursor.fetchall()

                return {
                    'report_period_days': days,
                    'generated_at': datetime.now(),
                    'system_health': {
                        'avg_health_score': health_data[0] if health_data[0] else 0,
                        'min_health_score': health_data[1] if health_data[1] else 0,
                        'max_health_score': health_data[2] if health_data[2] else 0,
                        'sample_count': health_data[3] if health_data[3] else 0
                    },
                    'performance_by_category': {
                        row[0]: {
                            'avg_performance': row[1],
                            'min_performance': row[2],
                            'max_performance': row[3]
                        } for row in performance_data
                    },
                    'alerts_summary': {
                        row[0]: row[1] for row in alerts_data
                    }
                }

            finally:
                conn.close()
