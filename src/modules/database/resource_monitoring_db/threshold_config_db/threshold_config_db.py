"""
Module: threshold_config_db
Description: Persists user-defined resource monitoring thresholds and alert configurations
Phase: 2
Location: /src/modules/database/resource_monitoring_db/threshold_config_db/
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


class ThresholdConfigDB:
    """
    Threshold configuration database manager.
    
    Persists user-defined resource monitoring thresholds and alert configurations.
    Stores CPU, GPU, memory, thermal thresholds with alert severity levels and
    notification settings for comprehensive resource monitoring.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the threshold configuration database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "threshold_config.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        self._initialize_database()
        self._load_default_thresholds()
    
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
                
                # Create threshold configurations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS threshold_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_id TEXT NOT NULL UNIQUE,
                        config_name TEXT NOT NULL,
                        resource_category TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        threshold_type TEXT NOT NULL,
                        warning_threshold REAL,
                        critical_threshold REAL,
                        emergency_threshold REAL,
                        threshold_unit TEXT,
                        comparison_operator TEXT DEFAULT 'greater_than',
                        enabled BOOLEAN DEFAULT 1,
                        user_id TEXT DEFAULT 'default',
                        profile_name TEXT DEFAULT 'default',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create alert configurations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_id TEXT NOT NULL UNIQUE,
                        config_id TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity_level TEXT NOT NULL,
                        notification_enabled BOOLEAN DEFAULT 1,
                        notification_channels TEXT,
                        cooldown_minutes INTEGER DEFAULT 5,
                        escalation_enabled BOOLEAN DEFAULT 0,
                        escalation_threshold_minutes INTEGER,
                        auto_recovery_enabled BOOLEAN DEFAULT 0,
                        recovery_action TEXT,
                        message_template TEXT,
                        enabled BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (config_id) REFERENCES threshold_configurations(config_id)
                    )
                """)
                
                # Create threshold profiles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS threshold_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_id TEXT NOT NULL UNIQUE,
                        profile_name TEXT NOT NULL,
                        description TEXT,
                        profile_type TEXT DEFAULT 'custom',
                        is_default BOOLEAN DEFAULT 0,
                        user_id TEXT DEFAULT 'default',
                        configuration_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create threshold history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS threshold_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        history_id TEXT NOT NULL UNIQUE,
                        config_id TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        old_values TEXT,
                        new_values TEXT,
                        changed_by TEXT DEFAULT 'system',
                        change_reason TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (config_id) REFERENCES threshold_configurations(config_id)
                    )
                """)
                
                # Create adaptive thresholds table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS adaptive_thresholds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        adaptive_id TEXT NOT NULL UNIQUE,
                        config_id TEXT NOT NULL,
                        baseline_value REAL,
                        adaptive_factor REAL DEFAULT 1.2,
                        learning_enabled BOOLEAN DEFAULT 1,
                        adaptation_period_hours INTEGER DEFAULT 24,
                        confidence_level REAL DEFAULT 0.95,
                        last_adaptation TIMESTAMP,
                        adaptation_count INTEGER DEFAULT 0,
                        performance_impact REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (config_id) REFERENCES threshold_configurations(config_id)
                    )
                """)
                
                # Create notification settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS notification_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_id TEXT NOT NULL UNIQUE,
                        user_id TEXT DEFAULT 'default',
                        notification_type TEXT NOT NULL,
                        enabled BOOLEAN DEFAULT 1,
                        endpoint_config TEXT,
                        rate_limit_minutes INTEGER DEFAULT 5,
                        quiet_hours_start TEXT,
                        quiet_hours_end TEXT,
                        severity_filter TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thresholds_category_metric ON threshold_configurations(resource_category, metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thresholds_profile ON threshold_configurations(profile_name, user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_config_id ON alert_configurations(config_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alert_configurations(severity_level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_user ON threshold_profiles(user_id, profile_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_config_time ON threshold_history(config_id, timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adaptive_config ON adaptive_thresholds(config_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notification_settings(user_id, notification_type)")
                
                conn.commit()
                self._logger.info("Threshold configuration database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize threshold configuration database: {e}")
                raise
            finally:
                conn.close()

    def _load_default_thresholds(self) -> None:
        """Load default threshold configurations if none exist."""
        if not self.get_threshold_configurations():
            self._create_default_thresholds()

    def _create_default_thresholds(self) -> None:
        """Create default threshold configurations."""
        default_thresholds = [
            # CPU thresholds
            {
                'config_name': 'CPU Usage',
                'resource_category': 'cpu',
                'metric_name': 'cpu_usage_percent',
                'threshold_type': 'usage',
                'warning_threshold': 70.0,
                'critical_threshold': 85.0,
                'emergency_threshold': 95.0,
                'threshold_unit': 'percent',
                'comparison_operator': 'greater_than'
            },
            # GPU thresholds
            {
                'config_name': 'GPU Usage',
                'resource_category': 'gpu',
                'metric_name': 'gpu_usage_percent',
                'threshold_type': 'usage',
                'warning_threshold': 80.0,
                'critical_threshold': 90.0,
                'emergency_threshold': 98.0,
                'threshold_unit': 'percent',
                'comparison_operator': 'greater_than'
            },
            {
                'config_name': 'GPU Memory',
                'resource_category': 'gpu',
                'metric_name': 'memory_usage_percent',
                'threshold_type': 'memory',
                'warning_threshold': 75.0,
                'critical_threshold': 90.0,
                'emergency_threshold': 98.0,
                'threshold_unit': 'percent',
                'comparison_operator': 'greater_than'
            },
            {
                'config_name': 'GPU Temperature',
                'resource_category': 'gpu',
                'metric_name': 'temperature_celsius',
                'threshold_type': 'thermal',
                'warning_threshold': 75.0,
                'critical_threshold': 85.0,
                'emergency_threshold': 95.0,
                'threshold_unit': 'celsius',
                'comparison_operator': 'greater_than'
            },
            # Memory thresholds
            {
                'config_name': 'System Memory',
                'resource_category': 'memory',
                'metric_name': 'usage_percent',
                'threshold_type': 'usage',
                'warning_threshold': 80.0,
                'critical_threshold': 90.0,
                'emergency_threshold': 98.0,
                'threshold_unit': 'percent',
                'comparison_operator': 'greater_than'
            },
            # Disk thresholds
            {
                'config_name': 'Disk Utilization',
                'resource_category': 'disk',
                'metric_name': 'utilization_percent',
                'threshold_type': 'usage',
                'warning_threshold': 70.0,
                'critical_threshold': 85.0,
                'emergency_threshold': 95.0,
                'threshold_unit': 'percent',
                'comparison_operator': 'greater_than'
            }
        ]

        for threshold_config in default_thresholds:
            self.create_threshold_configuration(threshold_config)

    def create_threshold_configuration(self, config_data: Dict[str, Any]) -> str:
        """
        Create a new threshold configuration.

        Args:
            config_data: Dictionary containing threshold configuration

        Returns:
            Configuration ID
        """
        config_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO threshold_configurations (
                        config_id, config_name, resource_category, metric_name,
                        threshold_type, warning_threshold, critical_threshold,
                        emergency_threshold, threshold_unit, comparison_operator,
                        enabled, user_id, profile_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config_id,
                    config_data.get('config_name'),
                    config_data.get('resource_category'),
                    config_data.get('metric_name'),
                    config_data.get('threshold_type'),
                    config_data.get('warning_threshold'),
                    config_data.get('critical_threshold'),
                    config_data.get('emergency_threshold'),
                    config_data.get('threshold_unit'),
                    config_data.get('comparison_operator', 'greater_than'),
                    config_data.get('enabled', True),
                    config_data.get('user_id', 'default'),
                    config_data.get('profile_name', 'default')
                ))
                conn.commit()
                self._logger.info(f"Threshold configuration created: {config_id}")
                return config_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create threshold configuration: {e}")
                raise
            finally:
                conn.close()

    def update_threshold_configuration(self, config_id: str, updates: Dict[str, Any]) -> None:
        """
        Update an existing threshold configuration.

        Args:
            config_id: Configuration ID to update
            updates: Dictionary containing fields to update
        """
        # Log the change for history
        old_config = self.get_threshold_configuration(config_id)
        if old_config:
            self._log_threshold_change(config_id, 'update', old_config, updates)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build dynamic update query
                update_fields = []
                values = []

                for field, value in updates.items():
                    if field in ['config_name', 'warning_threshold', 'critical_threshold',
                               'emergency_threshold', 'threshold_unit', 'comparison_operator',
                               'enabled', 'profile_name']:
                        update_fields.append(f"{field} = ?")
                        values.append(value)

                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(config_id)

                    query = f"UPDATE threshold_configurations SET {', '.join(update_fields)} WHERE config_id = ?"
                    cursor.execute(query, values)
                    conn.commit()
                    self._logger.info(f"Threshold configuration updated: {config_id}")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update threshold configuration: {e}")
                raise
            finally:
                conn.close()

    def get_threshold_configuration(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific threshold configuration.

        Args:
            config_id: Configuration ID to retrieve

        Returns:
            Configuration dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM threshold_configurations WHERE config_id = ?
                """, (config_id,))

                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
            finally:
                conn.close()

    def get_threshold_configurations(self, resource_category: Optional[str] = None,
                                   profile_name: str = 'default',
                                   user_id: str = 'default') -> List[Dict[str, Any]]:
        """
        Get threshold configurations.

        Args:
            resource_category: Filter by resource category
            profile_name: Profile name to filter by
            user_id: User ID to filter by

        Returns:
            List of configuration dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if resource_category:
                    cursor.execute("""
                        SELECT * FROM threshold_configurations
                        WHERE resource_category = ? AND profile_name = ? AND user_id = ?
                        ORDER BY metric_name
                    """, (resource_category, profile_name, user_id))
                else:
                    cursor.execute("""
                        SELECT * FROM threshold_configurations
                        WHERE profile_name = ? AND user_id = ?
                        ORDER BY resource_category, metric_name
                    """, (profile_name, user_id))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def create_alert_configuration(self, alert_data: Dict[str, Any]) -> str:
        """
        Create an alert configuration for a threshold.

        Args:
            alert_data: Dictionary containing alert configuration

        Returns:
            Alert ID
        """
        alert_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO alert_configurations (
                        alert_id, config_id, alert_type, severity_level,
                        notification_enabled, notification_channels, cooldown_minutes,
                        escalation_enabled, escalation_threshold_minutes,
                        auto_recovery_enabled, recovery_action, message_template, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert_id,
                    alert_data.get('config_id'),
                    alert_data.get('alert_type'),
                    alert_data.get('severity_level'),
                    alert_data.get('notification_enabled', True),
                    json.dumps(alert_data.get('notification_channels', [])),
                    alert_data.get('cooldown_minutes', 5),
                    alert_data.get('escalation_enabled', False),
                    alert_data.get('escalation_threshold_minutes'),
                    alert_data.get('auto_recovery_enabled', False),
                    alert_data.get('recovery_action'),
                    alert_data.get('message_template'),
                    alert_data.get('enabled', True)
                ))
                conn.commit()
                self._logger.info(f"Alert configuration created: {alert_id}")
                return alert_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create alert configuration: {e}")
                raise
            finally:
                conn.close()

    def evaluate_thresholds(self, resource_category: str, metric_name: str,
                          current_value: float) -> List[Dict[str, Any]]:
        """
        Evaluate current metric value against configured thresholds.

        Args:
            resource_category: Category of the resource
            metric_name: Name of the metric
            current_value: Current metric value

        Returns:
            List of threshold violations
        """
        violations = []
        configs = self.get_threshold_configurations(resource_category)

        for config in configs:
            if config['metric_name'] == metric_name and config['enabled']:
                violation = self._check_threshold_violation(config, current_value)
                if violation:
                    violations.append(violation)

        return violations

    def _check_threshold_violation(self, config: Dict[str, Any],
                                 current_value: float) -> Optional[Dict[str, Any]]:
        """
        Check if a value violates a threshold configuration.

        Args:
            config: Threshold configuration
            current_value: Current metric value

        Returns:
            Violation details or None if no violation
        """
        comparison_op = config.get('comparison_operator', 'greater_than')

        # Determine violation level
        violation_level = None
        threshold_value = None

        if comparison_op == 'greater_than':
            if config['emergency_threshold'] and current_value >= config['emergency_threshold']:
                violation_level = 'emergency'
                threshold_value = config['emergency_threshold']
            elif config['critical_threshold'] and current_value >= config['critical_threshold']:
                violation_level = 'critical'
                threshold_value = config['critical_threshold']
            elif config['warning_threshold'] and current_value >= config['warning_threshold']:
                violation_level = 'warning'
                threshold_value = config['warning_threshold']
        elif comparison_op == 'less_than':
            if config['emergency_threshold'] and current_value <= config['emergency_threshold']:
                violation_level = 'emergency'
                threshold_value = config['emergency_threshold']
            elif config['critical_threshold'] and current_value <= config['critical_threshold']:
                violation_level = 'critical'
                threshold_value = config['critical_threshold']
            elif config['warning_threshold'] and current_value <= config['warning_threshold']:
                violation_level = 'warning'
                threshold_value = config['warning_threshold']

        if violation_level:
            return {
                'config_id': config['config_id'],
                'config_name': config['config_name'],
                'resource_category': config['resource_category'],
                'metric_name': config['metric_name'],
                'violation_level': violation_level,
                'current_value': current_value,
                'threshold_value': threshold_value,
                'threshold_unit': config['threshold_unit'],
                'timestamp': datetime.now()
            }

        return None

    def _log_threshold_change(self, config_id: str, change_type: str,
                            old_values: Dict[str, Any], new_values: Dict[str, Any]) -> None:
        """
        Log threshold configuration changes for audit trail.

        Args:
            config_id: Configuration ID
            change_type: Type of change ('create', 'update', 'delete')
            old_values: Previous values
            new_values: New values
        """
        history_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO threshold_history (
                        history_id, config_id, change_type, old_values,
                        new_values, changed_by, change_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    history_id,
                    config_id,
                    change_type,
                    json.dumps(old_values),
                    json.dumps(new_values),
                    'user',  # Could be enhanced to track actual user
                    f"Threshold {change_type} operation"
                ))
                conn.commit()

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log threshold change: {e}")
            finally:
                conn.close()

    def get_threshold_history(self, config_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get threshold configuration change history.

        Args:
            config_id: Configuration ID
            days: Number of days of history to retrieve

        Returns:
            List of change history dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM threshold_history
                    WHERE config_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (config_id, cutoff_time))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]
            finally:
                conn.close()

    def delete_threshold_configuration(self, config_id: str) -> None:
        """
        Delete a threshold configuration.

        Args:
            config_id: Configuration ID to delete
        """
        # Log the deletion
        old_config = self.get_threshold_configuration(config_id)
        if old_config:
            self._log_threshold_change(config_id, 'delete', old_config, {})

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete related alert configurations
                cursor.execute("DELETE FROM alert_configurations WHERE config_id = ?", (config_id,))

                # Delete adaptive threshold data
                cursor.execute("DELETE FROM adaptive_thresholds WHERE config_id = ?", (config_id,))

                # Delete the threshold configuration
                cursor.execute("DELETE FROM threshold_configurations WHERE config_id = ?", (config_id,))

                conn.commit()
                self._logger.info(f"Threshold configuration deleted: {config_id}")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete threshold configuration: {e}")
                raise
            finally:
                conn.close()
