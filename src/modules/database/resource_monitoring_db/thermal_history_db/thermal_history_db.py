"""
Module: thermal_history_db
Description: Tracks temperature readings and thermal throttling events for hardware protection
Phase: 2
Location: /src/modules/database/resource_monitoring_db/thermal_history_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import statistics

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ThermalHistoryDB:
    """
    Thermal history database manager.
    
    Tracks temperature readings and thermal throttling events for hardware protection.
    Monitors CPU/GPU temperatures, throttling events, and thermal management decisions
    to ensure system stability and prevent hardware damage.
    """
    
    def __init__(self, db_path: Optional[str] = None, buffer_size: int = 1800):
        """
        Initialize the thermal history database.
        
        Args:
            db_path: Path to the database file
            buffer_size: Size of in-memory temperature buffer (30 minutes at 1-second intervals)
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "thermal_history.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._buffer_size = buffer_size
        
        # In-memory circular buffers for real-time thermal monitoring
        self._cpu_temp_buffer = deque(maxlen=buffer_size)
        self._gpu_temp_buffer = deque(maxlen=buffer_size)
        
        # Retention settings
        self._detailed_retention_hours = 48  # Keep detailed data for 48 hours
        self._summary_retention_days = 90   # Keep summaries for 90 days
        self._critical_retention_days = 365  # Keep critical events for 1 year
        
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
                
                # Create temperature readings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS temperature_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        device_type TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        sensor_name TEXT,
                        temperature_celsius REAL NOT NULL,
                        temperature_fahrenheit REAL,
                        critical_threshold REAL,
                        warning_threshold REAL,
                        max_safe_temperature REAL,
                        ambient_temperature REAL,
                        fan_speed_percent REAL,
                        power_draw_watts REAL,
                        workload_intensity REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create thermal events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS thermal_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        device_type TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        severity_level TEXT NOT NULL,
                        temperature_celsius REAL NOT NULL,
                        threshold_exceeded REAL,
                        duration_seconds INTEGER,
                        trigger_condition TEXT,
                        system_response TEXT,
                        performance_impact TEXT,
                        recovery_time_seconds INTEGER,
                        event_resolved BOOLEAN DEFAULT 0,
                        resolution_timestamp TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create throttling events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS throttling_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        throttle_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        device_type TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        throttle_type TEXT NOT NULL,
                        throttle_reason TEXT NOT NULL,
                        pre_throttle_frequency REAL,
                        throttled_frequency REAL,
                        frequency_reduction_percent REAL,
                        pre_throttle_temperature REAL,
                        throttle_temperature REAL,
                        throttle_duration_seconds INTEGER,
                        performance_loss_percent REAL,
                        power_reduction_watts REAL,
                        recovery_timestamp TIMESTAMP,
                        automatic_recovery BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create thermal management actions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS thermal_management_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        trigger_event_id TEXT,
                        action_type TEXT NOT NULL,
                        target_device TEXT NOT NULL,
                        action_description TEXT,
                        pre_action_temperature REAL,
                        target_temperature REAL,
                        action_parameters TEXT,
                        execution_status TEXT DEFAULT 'pending',
                        execution_duration_ms INTEGER,
                        effectiveness_score REAL,
                        temperature_reduction REAL,
                        side_effects TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create thermal summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS thermal_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        summary_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        period_start TIMESTAMP NOT NULL,
                        period_end TIMESTAMP NOT NULL,
                        device_type TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        avg_temperature REAL,
                        min_temperature REAL,
                        max_temperature REAL,
                        temperature_variance REAL,
                        time_above_warning REAL,
                        time_above_critical REAL,
                        throttling_events_count INTEGER,
                        total_throttle_time_seconds INTEGER,
                        thermal_efficiency_score REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create thermal alerts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS thermal_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP NOT NULL,
                        device_type TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        temperature_celsius REAL NOT NULL,
                        threshold_value REAL,
                        alert_message TEXT,
                        notification_sent BOOLEAN DEFAULT 0,
                        acknowledgment_required BOOLEAN DEFAULT 0,
                        acknowledged BOOLEAN DEFAULT 0,
                        acknowledged_by TEXT,
                        acknowledged_at TIMESTAMP,
                        resolved BOOLEAN DEFAULT 0,
                        resolved_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_temp_readings_device_time ON temperature_readings(device_type, device_id, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thermal_events_device_time ON thermal_events(device_type, device_id, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thermal_events_severity ON thermal_events(severity_level, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_throttling_device_time ON throttling_events(device_type, device_id, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thermal_actions_trigger ON thermal_management_actions(trigger_event_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thermal_summary_device_time ON thermal_summary(device_type, device_id, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thermal_alerts_device_severity ON thermal_alerts(device_type, severity, timestamp DESC)")
                
                conn.commit()
                self._logger.info("Thermal history database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize thermal history database: {e}")
                raise
            finally:
                conn.close()

    def record_temperature_reading(self, reading_data: Dict[str, Any]) -> None:
        """
        Record a temperature reading.

        Args:
            reading_data: Dictionary containing temperature reading data
        """
        timestamp = datetime.now()

        # Add to appropriate circular buffer
        buffer_entry = {
            'timestamp': timestamp,
            'device_type': reading_data.get('device_type'),
            'device_id': reading_data.get('device_id'),
            'temperature_celsius': reading_data.get('temperature_celsius')
        }

        if reading_data.get('device_type') == 'cpu':
            self._cpu_temp_buffer.append(buffer_entry)
        elif reading_data.get('device_type') == 'gpu':
            self._gpu_temp_buffer.append(buffer_entry)

        # Store in database
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO temperature_readings (
                        timestamp, device_type, device_id, sensor_name,
                        temperature_celsius, temperature_fahrenheit, critical_threshold,
                        warning_threshold, max_safe_temperature, ambient_temperature,
                        fan_speed_percent, power_draw_watts, workload_intensity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    reading_data.get('device_type'),
                    reading_data.get('device_id'),
                    reading_data.get('sensor_name'),
                    reading_data.get('temperature_celsius'),
                    reading_data.get('temperature_fahrenheit'),
                    reading_data.get('critical_threshold'),
                    reading_data.get('warning_threshold'),
                    reading_data.get('max_safe_temperature'),
                    reading_data.get('ambient_temperature'),
                    reading_data.get('fan_speed_percent'),
                    reading_data.get('power_draw_watts'),
                    reading_data.get('workload_intensity')
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record temperature reading: {e}")
                raise
            finally:
                conn.close()

    def record_thermal_event(self, event_data: Dict[str, Any]) -> str:
        """
        Record a thermal event.

        Args:
            event_data: Dictionary containing thermal event data

        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO thermal_events (
                        event_id, timestamp, device_type, device_id, event_type,
                        severity_level, temperature_celsius, threshold_exceeded,
                        duration_seconds, trigger_condition, system_response,
                        performance_impact, recovery_time_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    event_data.get('timestamp', datetime.now()),
                    event_data.get('device_type'),
                    event_data.get('device_id'),
                    event_data.get('event_type'),
                    event_data.get('severity_level'),
                    event_data.get('temperature_celsius'),
                    event_data.get('threshold_exceeded'),
                    event_data.get('duration_seconds'),
                    event_data.get('trigger_condition'),
                    json.dumps(event_data.get('system_response', {})),
                    json.dumps(event_data.get('performance_impact', {})),
                    event_data.get('recovery_time_seconds')
                ))
                conn.commit()
                self._logger.info(f"Thermal event recorded: {event_id}")
                return event_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record thermal event: {e}")
                raise
            finally:
                conn.close()

    def record_throttling_event(self, throttle_data: Dict[str, Any]) -> str:
        """
        Record a thermal throttling event.

        Args:
            throttle_data: Dictionary containing throttling event data

        Returns:
            Throttle ID
        """
        throttle_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO throttling_events (
                        throttle_id, timestamp, device_type, device_id, throttle_type,
                        throttle_reason, pre_throttle_frequency, throttled_frequency,
                        frequency_reduction_percent, pre_throttle_temperature,
                        throttle_temperature, throttle_duration_seconds,
                        performance_loss_percent, power_reduction_watts, automatic_recovery
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    throttle_id,
                    throttle_data.get('timestamp', datetime.now()),
                    throttle_data.get('device_type'),
                    throttle_data.get('device_id'),
                    throttle_data.get('throttle_type'),
                    throttle_data.get('throttle_reason'),
                    throttle_data.get('pre_throttle_frequency'),
                    throttle_data.get('throttled_frequency'),
                    throttle_data.get('frequency_reduction_percent'),
                    throttle_data.get('pre_throttle_temperature'),
                    throttle_data.get('throttle_temperature'),
                    throttle_data.get('throttle_duration_seconds'),
                    throttle_data.get('performance_loss_percent'),
                    throttle_data.get('power_reduction_watts'),
                    throttle_data.get('automatic_recovery', True)
                ))
                conn.commit()
                self._logger.info(f"Throttling event recorded: {throttle_id}")
                return throttle_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record throttling event: {e}")
                raise
            finally:
                conn.close()

    def get_recent_temperatures(self, device_type: str, device_id: str,
                              minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get recent temperature readings from circular buffer.

        Args:
            device_type: Type of device ('cpu', 'gpu')
            device_id: Device identifier
            minutes: Number of minutes of data to retrieve

        Returns:
            List of temperature readings
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        if device_type == 'cpu':
            buffer = self._cpu_temp_buffer
        elif device_type == 'gpu':
            buffer = self._gpu_temp_buffer
        else:
            return []

        return [
            entry for entry in buffer
            if (entry['timestamp'] >= cutoff_time and
                entry.get('device_id') == device_id)
        ]

    def get_thermal_events(self, device_type: Optional[str] = None,
                         severity_level: Optional[str] = None,
                         hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get thermal events from database.

        Args:
            device_type: Filter by device type
            severity_level: Filter by severity level
            hours: Number of hours of events to retrieve

        Returns:
            List of thermal event dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = "SELECT * FROM thermal_events WHERE timestamp >= ?"
                params = [cutoff_time]

                if device_type:
                    query += " AND device_type = ?"
                    params.append(device_type)

                if severity_level:
                    query += " AND severity_level = ?"
                    params.append(severity_level)

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def get_throttling_events(self, device_type: Optional[str] = None,
                            hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get throttling events from database.

        Args:
            device_type: Filter by device type
            hours: Number of hours of events to retrieve

        Returns:
            List of throttling event dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if device_type:
                    cursor.execute("""
                        SELECT * FROM throttling_events
                        WHERE device_type = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (device_type, cutoff_time))
                else:
                    cursor.execute("""
                        SELECT * FROM throttling_events
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    """, (cutoff_time,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def analyze_thermal_trends(self, device_type: str, device_id: str,
                             hours: int = 24) -> Dict[str, Any]:
        """
        Analyze thermal trends for a specific device.

        Args:
            device_type: Type of device
            device_id: Device identifier
            hours: Number of hours to analyze

        Returns:
            Dictionary containing thermal analysis
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get temperature statistics
                cursor.execute("""
                    SELECT
                        AVG(temperature_celsius) as avg_temp,
                        MIN(temperature_celsius) as min_temp,
                        MAX(temperature_celsius) as max_temp,
                        COUNT(*) as reading_count
                    FROM temperature_readings
                    WHERE device_type = ? AND device_id = ? AND timestamp >= ?
                """, (device_type, device_id, cutoff_time))

                temp_stats = cursor.fetchone()

                # Get thermal events count
                cursor.execute("""
                    SELECT severity_level, COUNT(*) as event_count
                    FROM thermal_events
                    WHERE device_type = ? AND device_id = ? AND timestamp >= ?
                    GROUP BY severity_level
                """, (device_type, device_id, cutoff_time))

                event_counts = dict(cursor.fetchall())

                # Get throttling statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as throttle_count,
                        SUM(throttle_duration_seconds) as total_throttle_time,
                        AVG(performance_loss_percent) as avg_performance_loss
                    FROM throttling_events
                    WHERE device_type = ? AND device_id = ? AND timestamp >= ?
                """, (device_type, device_id, cutoff_time))

                throttle_stats = cursor.fetchone()

                return {
                    'device_type': device_type,
                    'device_id': device_id,
                    'analysis_period_hours': hours,
                    'temperature_stats': {
                        'avg_temperature': temp_stats[0] if temp_stats[0] else 0,
                        'min_temperature': temp_stats[1] if temp_stats[1] else 0,
                        'max_temperature': temp_stats[2] if temp_stats[2] else 0,
                        'reading_count': temp_stats[3] if temp_stats[3] else 0
                    },
                    'thermal_events': event_counts,
                    'throttling_stats': {
                        'throttle_count': throttle_stats[0] if throttle_stats[0] else 0,
                        'total_throttle_time_seconds': throttle_stats[1] if throttle_stats[1] else 0,
                        'avg_performance_loss_percent': throttle_stats[2] if throttle_stats[2] else 0
                    }
                }

            finally:
                conn.close()

    def cleanup_old_data(self) -> None:
        """Clean up old thermal data based on retention policies."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up old detailed temperature readings
                detailed_cutoff = datetime.now() - timedelta(hours=self._detailed_retention_hours)
                cursor.execute("DELETE FROM temperature_readings WHERE timestamp < ?", (detailed_cutoff,))

                # Clean up old thermal summaries
                summary_cutoff = datetime.now() - timedelta(days=self._summary_retention_days)
                cursor.execute("DELETE FROM thermal_summary WHERE timestamp < ?", (summary_cutoff,))

                # Keep critical thermal events longer
                critical_cutoff = datetime.now() - timedelta(days=self._critical_retention_days)
                cursor.execute("""
                    DELETE FROM thermal_events
                    WHERE timestamp < ? AND severity_level NOT IN ('critical', 'emergency')
                """, (summary_cutoff,))

                cursor.execute("""
                    DELETE FROM thermal_events
                    WHERE timestamp < ? AND severity_level IN ('critical', 'emergency')
                """, (critical_cutoff,))

                # Clean up old throttling events
                cursor.execute("DELETE FROM throttling_events WHERE timestamp < ?", (summary_cutoff,))

                # Clean up old thermal management actions
                cursor.execute("DELETE FROM thermal_management_actions WHERE timestamp < ?", (summary_cutoff,))

                # Clean up resolved thermal alerts
                cursor.execute("""
                    DELETE FROM thermal_alerts
                    WHERE timestamp < ? AND resolved = 1
                """, (summary_cutoff,))

                conn.commit()
                self._logger.info("Thermal history data cleanup completed successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup thermal history data: {e}")
            finally:
                conn.close()

    def get_thermal_health_score(self, device_type: str, device_id: str) -> float:
        """
        Calculate thermal health score for a device.

        Args:
            device_type: Type of device
            device_id: Device identifier

        Returns:
            Thermal health score (0-100)
        """
        analysis = self.analyze_thermal_trends(device_type, device_id, hours=24)

        # Base score starts at 100
        health_score = 100.0

        # Deduct points for high temperatures
        max_temp = analysis['temperature_stats']['max_temperature']
        if max_temp > 85:  # Critical temperature threshold
            health_score -= min(30, (max_temp - 85) * 2)
        elif max_temp > 75:  # Warning temperature threshold
            health_score -= min(15, (max_temp - 75) * 1.5)

        # Deduct points for thermal events
        event_counts = analysis['thermal_events']
        health_score -= event_counts.get('warning', 0) * 2
        health_score -= event_counts.get('critical', 0) * 5
        health_score -= event_counts.get('emergency', 0) * 10

        # Deduct points for throttling
        throttle_stats = analysis['throttling_stats']
        throttle_count = throttle_stats['throttle_count']
        health_score -= min(20, throttle_count * 3)

        # Ensure score doesn't go below 0
        return max(0.0, health_score)
