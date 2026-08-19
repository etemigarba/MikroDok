"""
Module: monitoring_metrics_db
Description: Stores time-series resource utilization data with efficient circular buffer implementation
Phase: 2
Location: /src/modules/database/resource_monitoring_db/monitoring_metrics_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MonitoringMetricsDB:
    """
    Monitoring metrics database manager.
    
    Handles storage and retrieval of time-series resource utilization data
    with efficient circular buffer implementation for real-time monitoring.
    Supports 1-second sampling rate with configurable retention policies.
    """
    
    def __init__(self, db_path: Optional[str] = None, max_buffer_size: int = 3600):
        """
        Initialize the monitoring metrics database.
        
        Args:
            db_path: Path to the database file
            max_buffer_size: Maximum number of metrics to keep in memory buffer
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "monitoring_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._max_buffer_size = max_buffer_size
        
        # In-memory circular buffers for real-time access
        self._cpu_buffer = deque(maxlen=max_buffer_size)
        self._gpu_buffer = deque(maxlen=max_buffer_size)
        self._memory_buffer = deque(maxlen=max_buffer_size)
        self._disk_buffer = deque(maxlen=max_buffer_size)
        self._network_buffer = deque(maxlen=max_buffer_size)
        
        # Retention settings (in hours)
        self._detailed_retention_hours = 24  # Keep detailed metrics for 24 hours
        self._aggregated_retention_days = 30  # Keep aggregated metrics for 30 days
        
        self._initialize_database()
        self._start_cleanup_thread()
    
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
                
                # Create CPU metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cpu_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        cpu_usage_percent REAL NOT NULL,
                        cpu_frequency_mhz REAL,
                        core_count INTEGER,
                        thread_count INTEGER,
                        load_average_1m REAL,
                        load_average_5m REAL,
                        load_average_15m REAL,
                        context_switches_per_sec INTEGER,
                        interrupts_per_sec INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create GPU metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS gpu_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        gpu_id INTEGER NOT NULL,
                        gpu_usage_percent REAL NOT NULL,
                        memory_used_mb INTEGER NOT NULL,
                        memory_total_mb INTEGER NOT NULL,
                        memory_usage_percent REAL NOT NULL,
                        temperature_celsius REAL,
                        power_draw_watts REAL,
                        fan_speed_percent REAL,
                        clock_speed_mhz REAL,
                        memory_clock_mhz REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create memory metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        total_mb INTEGER NOT NULL,
                        available_mb INTEGER NOT NULL,
                        used_mb INTEGER NOT NULL,
                        usage_percent REAL NOT NULL,
                        swap_total_mb INTEGER,
                        swap_used_mb INTEGER,
                        swap_usage_percent REAL,
                        cached_mb INTEGER,
                        buffers_mb INTEGER,
                        shared_mb INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create disk I/O metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS disk_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        device_name TEXT NOT NULL,
                        read_bytes_per_sec INTEGER,
                        write_bytes_per_sec INTEGER,
                        read_ops_per_sec INTEGER,
                        write_ops_per_sec INTEGER,
                        read_latency_ms REAL,
                        write_latency_ms REAL,
                        queue_depth INTEGER,
                        utilization_percent REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create network metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS network_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        interface_name TEXT NOT NULL,
                        bytes_sent_per_sec INTEGER,
                        bytes_recv_per_sec INTEGER,
                        packets_sent_per_sec INTEGER,
                        packets_recv_per_sec INTEGER,
                        errors_in INTEGER,
                        errors_out INTEGER,
                        drops_in INTEGER,
                        drops_out INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create aggregated metrics table for long-term storage
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS aggregated_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        metric_type TEXT NOT NULL,
                        aggregation_period TEXT NOT NULL,
                        avg_value REAL,
                        min_value REAL,
                        max_value REAL,
                        sum_value REAL,
                        count_value INTEGER,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpu_timestamp ON cpu_metrics(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_timestamp ON gpu_metrics(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_metrics(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_disk_timestamp ON disk_metrics(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_timestamp ON network_metrics(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aggregated_type_time ON aggregated_metrics(metric_type, timestamp DESC)")
                
                conn.commit()
                self._logger.info("Monitoring metrics database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize monitoring metrics database: {e}")
                raise
            finally:
                conn.close()

    def _start_cleanup_thread(self) -> None:
        """Start background thread for data cleanup and aggregation."""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(3600)  # Run cleanup every hour
                    self._cleanup_old_data()
                    self._aggregate_metrics()
                except Exception as e:
                    self._logger.error(f"Error in cleanup thread: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def store_cpu_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Store CPU metrics data.

        Args:
            metrics: Dictionary containing CPU metrics
        """
        timestamp = datetime.now()

        # Add to circular buffer
        buffer_entry = {
            'timestamp': timestamp,
            **metrics
        }
        self._cpu_buffer.append(buffer_entry)

        # Store in database
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cpu_metrics (
                        timestamp, cpu_usage_percent, cpu_frequency_mhz,
                        core_count, thread_count, load_average_1m,
                        load_average_5m, load_average_15m, context_switches_per_sec,
                        interrupts_per_sec
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    metrics.get('cpu_usage_percent', 0.0),
                    metrics.get('cpu_frequency_mhz'),
                    metrics.get('core_count'),
                    metrics.get('thread_count'),
                    metrics.get('load_average_1m'),
                    metrics.get('load_average_5m'),
                    metrics.get('load_average_15m'),
                    metrics.get('context_switches_per_sec'),
                    metrics.get('interrupts_per_sec')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store CPU metrics: {e}")
                raise
            finally:
                conn.close()

    def store_gpu_metrics(self, gpu_id: int, metrics: Dict[str, Any]) -> None:
        """
        Store GPU metrics data.

        Args:
            gpu_id: GPU identifier
            metrics: Dictionary containing GPU metrics
        """
        timestamp = datetime.now()

        # Add to circular buffer
        buffer_entry = {
            'timestamp': timestamp,
            'gpu_id': gpu_id,
            **metrics
        }
        self._gpu_buffer.append(buffer_entry)

        # Store in database
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO gpu_metrics (
                        timestamp, gpu_id, gpu_usage_percent, memory_used_mb,
                        memory_total_mb, memory_usage_percent, temperature_celsius,
                        power_draw_watts, fan_speed_percent, clock_speed_mhz,
                        memory_clock_mhz
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    gpu_id,
                    metrics.get('gpu_usage_percent', 0.0),
                    metrics.get('memory_used_mb', 0),
                    metrics.get('memory_total_mb', 0),
                    metrics.get('memory_usage_percent', 0.0),
                    metrics.get('temperature_celsius'),
                    metrics.get('power_draw_watts'),
                    metrics.get('fan_speed_percent'),
                    metrics.get('clock_speed_mhz'),
                    metrics.get('memory_clock_mhz')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store GPU metrics: {e}")
                raise
            finally:
                conn.close()

    def store_memory_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Store memory metrics data.

        Args:
            metrics: Dictionary containing memory metrics
        """
        timestamp = datetime.now()

        # Add to circular buffer
        buffer_entry = {
            'timestamp': timestamp,
            **metrics
        }
        self._memory_buffer.append(buffer_entry)

        # Store in database
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memory_metrics (
                        timestamp, total_mb, available_mb, used_mb,
                        usage_percent, swap_total_mb, swap_used_mb,
                        swap_usage_percent, cached_mb, buffers_mb, shared_mb
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    metrics.get('total_mb', 0),
                    metrics.get('available_mb', 0),
                    metrics.get('used_mb', 0),
                    metrics.get('usage_percent', 0.0),
                    metrics.get('swap_total_mb'),
                    metrics.get('swap_used_mb'),
                    metrics.get('swap_usage_percent'),
                    metrics.get('cached_mb'),
                    metrics.get('buffers_mb'),
                    metrics.get('shared_mb')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store memory metrics: {e}")
                raise
            finally:
                conn.close()

    def store_disk_metrics(self, device_name: str, metrics: Dict[str, Any]) -> None:
        """
        Store disk I/O metrics data.

        Args:
            device_name: Name of the disk device
            metrics: Dictionary containing disk metrics
        """
        timestamp = datetime.now()

        # Add to circular buffer
        buffer_entry = {
            'timestamp': timestamp,
            'device_name': device_name,
            **metrics
        }
        self._disk_buffer.append(buffer_entry)

        # Store in database
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO disk_metrics (
                        timestamp, device_name, read_bytes_per_sec, write_bytes_per_sec,
                        read_ops_per_sec, write_ops_per_sec, read_latency_ms,
                        write_latency_ms, queue_depth, utilization_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    device_name,
                    metrics.get('read_bytes_per_sec'),
                    metrics.get('write_bytes_per_sec'),
                    metrics.get('read_ops_per_sec'),
                    metrics.get('write_ops_per_sec'),
                    metrics.get('read_latency_ms'),
                    metrics.get('write_latency_ms'),
                    metrics.get('queue_depth'),
                    metrics.get('utilization_percent')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store disk metrics: {e}")
                raise
            finally:
                conn.close()

    def store_network_metrics(self, interface_name: str, metrics: Dict[str, Any]) -> None:
        """
        Store network metrics data.

        Args:
            interface_name: Name of the network interface
            metrics: Dictionary containing network metrics
        """
        timestamp = datetime.now()

        # Add to circular buffer
        buffer_entry = {
            'timestamp': timestamp,
            'interface_name': interface_name,
            **metrics
        }
        self._network_buffer.append(buffer_entry)

        # Store in database
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO network_metrics (
                        timestamp, interface_name, bytes_sent_per_sec, bytes_recv_per_sec,
                        packets_sent_per_sec, packets_recv_per_sec, errors_in,
                        errors_out, drops_in, drops_out
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    interface_name,
                    metrics.get('bytes_sent_per_sec'),
                    metrics.get('bytes_recv_per_sec'),
                    metrics.get('packets_sent_per_sec'),
                    metrics.get('packets_recv_per_sec'),
                    metrics.get('errors_in'),
                    metrics.get('errors_out'),
                    metrics.get('drops_in'),
                    metrics.get('drops_out')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store network metrics: {e}")
                raise
            finally:
                conn.close()

    def get_recent_cpu_metrics(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent CPU metrics from circular buffer.

        Args:
            minutes: Number of minutes of data to retrieve

        Returns:
            List of CPU metrics dictionaries
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            entry for entry in self._cpu_buffer
            if entry['timestamp'] >= cutoff_time
        ]

    def get_recent_gpu_metrics(self, gpu_id: Optional[int] = None, minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent GPU metrics from circular buffer.

        Args:
            gpu_id: Specific GPU ID to filter by (None for all GPUs)
            minutes: Number of minutes of data to retrieve

        Returns:
            List of GPU metrics dictionaries
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        metrics = [
            entry for entry in self._gpu_buffer
            if entry['timestamp'] >= cutoff_time
        ]

        if gpu_id is not None:
            metrics = [entry for entry in metrics if entry.get('gpu_id') == gpu_id]

        return metrics

    def get_recent_memory_metrics(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent memory metrics from circular buffer.

        Args:
            minutes: Number of minutes of data to retrieve

        Returns:
            List of memory metrics dictionaries
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            entry for entry in self._memory_buffer
            if entry['timestamp'] >= cutoff_time
        ]

    def get_historical_metrics(self, metric_type: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical metrics from database.

        Args:
            metric_type: Type of metrics ('cpu', 'gpu', 'memory', 'disk', 'network')
            hours: Number of hours of historical data to retrieve

        Returns:
            List of metrics dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        table_name = f"{metric_type}_metrics"

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT 10000
                """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def _cleanup_old_data(self) -> None:
        """Clean up old detailed metrics data."""
        cutoff_time = datetime.now() - timedelta(hours=self._detailed_retention_hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up old detailed metrics
                tables = ['cpu_metrics', 'gpu_metrics', 'memory_metrics', 'disk_metrics', 'network_metrics']
                for table in tables:
                    cursor.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff_time,))

                # Clean up old aggregated metrics
                aggregated_cutoff = datetime.now() - timedelta(days=self._aggregated_retention_days)
                cursor.execute("DELETE FROM aggregated_metrics WHERE timestamp < ?", (aggregated_cutoff,))

                conn.commit()
                self._logger.info("Old metrics data cleaned up successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old data: {e}")
            finally:
                conn.close()

    def _aggregate_metrics(self) -> None:
        """Aggregate metrics for long-term storage."""
        # Aggregate data from 1 hour ago to avoid interfering with current data
        end_time = datetime.now() - timedelta(hours=1)
        start_time = end_time - timedelta(hours=1)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Aggregate CPU metrics
                cursor.execute("""
                    INSERT INTO aggregated_metrics (
                        timestamp, metric_type, aggregation_period,
                        avg_value, min_value, max_value, count_value
                    )
                    SELECT
                        ? as timestamp,
                        'cpu_usage' as metric_type,
                        'hourly' as aggregation_period,
                        AVG(cpu_usage_percent) as avg_value,
                        MIN(cpu_usage_percent) as min_value,
                        MAX(cpu_usage_percent) as max_value,
                        COUNT(*) as count_value
                    FROM cpu_metrics
                    WHERE timestamp BETWEEN ? AND ?
                """, (end_time, start_time, end_time))

                # Aggregate GPU metrics
                cursor.execute("""
                    INSERT INTO aggregated_metrics (
                        timestamp, metric_type, aggregation_period,
                        avg_value, min_value, max_value, count_value
                    )
                    SELECT
                        ? as timestamp,
                        'gpu_usage' as metric_type,
                        'hourly' as aggregation_period,
                        AVG(gpu_usage_percent) as avg_value,
                        MIN(gpu_usage_percent) as min_value,
                        MAX(gpu_usage_percent) as max_value,
                        COUNT(*) as count_value
                    FROM gpu_metrics
                    WHERE timestamp BETWEEN ? AND ?
                """, (end_time, start_time, end_time))

                # Aggregate memory metrics
                cursor.execute("""
                    INSERT INTO aggregated_metrics (
                        timestamp, metric_type, aggregation_period,
                        avg_value, min_value, max_value, count_value
                    )
                    SELECT
                        ? as timestamp,
                        'memory_usage' as metric_type,
                        'hourly' as aggregation_period,
                        AVG(usage_percent) as avg_value,
                        MIN(usage_percent) as min_value,
                        MAX(usage_percent) as max_value,
                        COUNT(*) as count_value
                    FROM memory_metrics
                    WHERE timestamp BETWEEN ? AND ?
                """, (end_time, start_time, end_time))

                conn.commit()
                self._logger.debug("Metrics aggregation completed successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to aggregate metrics: {e}")
            finally:
                conn.close()

    def get_aggregated_metrics(self, metric_type: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get aggregated metrics for trend analysis.

        Args:
            metric_type: Type of aggregated metrics to retrieve
            days: Number of days of aggregated data to retrieve

        Returns:
            List of aggregated metrics dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM aggregated_metrics
                    WHERE metric_type = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (metric_type, cutoff_time))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_buffer_status(self) -> Dict[str, int]:
        """
        Get current status of circular buffers.

        Returns:
            Dictionary with buffer sizes
        """
        return {
            'cpu_buffer_size': len(self._cpu_buffer),
            'gpu_buffer_size': len(self._gpu_buffer),
            'memory_buffer_size': len(self._memory_buffer),
            'disk_buffer_size': len(self._disk_buffer),
            'network_buffer_size': len(self._network_buffer),
            'max_buffer_size': self._max_buffer_size
        }
