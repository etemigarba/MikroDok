"""
Module: config_storage_db
Description: Stores system configuration, feature flags, and environment-specific settings
Phase: 1
Location: /src/modules/database/system_config_db/config_storage_db/
"""

# Standard library imports
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ConfigStorageDB:
    """
    System configuration database manager.
    
    Handles storage and retrieval of system configuration including
    feature flags, environment settings, and application preferences.
    Provides thread-safe operations with transaction support.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the configuration storage database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to system data directory
            data_dir = Path.home() / ".mikrodok" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "system_config.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Create configuration table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_key TEXT NOT NULL UNIQUE,
                        config_value TEXT NOT NULL,
                        value_type TEXT NOT NULL DEFAULT 'string',
                        category TEXT NOT NULL DEFAULT 'general',
                        description TEXT,
                        is_feature_flag BOOLEAN DEFAULT 0,
                        is_environment_specific BOOLEAN DEFAULT 0,
                        environment TEXT DEFAULT 'default',
                        is_encrypted BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'system',
                        updated_by TEXT DEFAULT 'system'
                    )
                """)
                
                # Create configuration metadata table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_key TEXT NOT NULL,
                        metadata_key TEXT NOT NULL,
                        metadata_value TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (config_key) REFERENCES system_config(config_key) ON DELETE CASCADE,
                        UNIQUE(config_key, metadata_key)
                    )
                """)
                
                # Create configuration categories table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        parent_category TEXT,
                        display_order INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_config_key 
                    ON system_config(config_key)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_config_category 
                    ON system_config(category)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_config_environment 
                    ON system_config(environment)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_config_feature_flags 
                    ON system_config(is_feature_flag) WHERE is_feature_flag = 1
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_config_updated_at 
                    ON system_config(updated_at DESC)
                """)
                
                # Insert default categories
                default_categories = [
                    ('general', 'General application settings', None, 1),
                    ('ui', 'User interface configuration', None, 2),
                    ('performance', 'Performance and optimization settings', None, 3),
                    ('security', 'Security and privacy settings', None, 4),
                    ('logging', 'Logging configuration', None, 5),
                    ('features', 'Feature flags and toggles', None, 6),
                    ('environment', 'Environment-specific settings', None, 7),
                    ('database', 'Database configuration', None, 8),
                    ('memory', 'Memory management settings', None, 9),
                    ('training', 'Training configuration', None, 10)
                ]
                
                cursor.executemany("""
                    INSERT OR IGNORE INTO config_categories 
                    (category_name, description, parent_category, display_order)
                    VALUES (?, ?, ?, ?)
                """, default_categories)
                
                conn.commit()
                self._logger.info("Configuration storage database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize configuration database: {e}")
                raise e
            finally:
                conn.close()
    
    def set_config(self, key: str, value: Any, 
                   category: str = "general",
                   description: Optional[str] = None,
                   is_feature_flag: bool = False,
                   is_environment_specific: bool = False,
                   environment: str = "default",
                   user: str = "system") -> bool:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            category: Configuration category
            description: Optional description
            is_feature_flag: Whether this is a feature flag
            is_environment_specific: Whether this is environment-specific
            environment: Environment name
            user: User making the change
            
        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Determine value type and serialize value
                    value_type, serialized_value = self._serialize_value(value)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO system_config 
                        (config_key, config_value, value_type, category, description,
                         is_feature_flag, is_environment_specific, environment,
                         updated_at, updated_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    """, (key, serialized_value, value_type, category, description,
                          is_feature_flag, is_environment_specific, environment, user))
                    
                    conn.commit()
                    self._logger.debug(f"Configuration set: {key} = {value}")
                    return True
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to set configuration {key}: {e}")
                    raise e
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error setting configuration: {e}")
            return False
    
    def get_config(self, key: str, 
                   environment: str = "default",
                   default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            environment: Environment name
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Try environment-specific first, then default
                    cursor.execute("""
                        SELECT config_value, value_type 
                        FROM system_config 
                        WHERE config_key = ? AND environment = ?
                        ORDER BY updated_at DESC
                        LIMIT 1
                    """, (key, environment))
                    
                    result = cursor.fetchone()
                    if not result and environment != "default":
                        # Fallback to default environment
                        cursor.execute("""
                            SELECT config_value, value_type 
                            FROM system_config 
                            WHERE config_key = ? AND environment = 'default'
                            ORDER BY updated_at DESC
                            LIMIT 1
                        """, (key,))
                        result = cursor.fetchone()
                    
                    if result:
                        value, value_type = result
                        return self._deserialize_value(value, value_type)
                    
                    return default
                    
                except Exception as e:
                    self._logger.error(f"Failed to get configuration {key}: {e}")
                    return default
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error getting configuration: {e}")
            return default

    def get_configs_by_category(self, category: str,
                               environment: str = "default") -> Dict[str, Any]:
        """
        Get all configurations in a category.

        Args:
            category: Configuration category
            environment: Environment name

        Returns:
            Dictionary of configuration key-value pairs
        """
        configs = {}
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT config_key, config_value, value_type
                        FROM system_config
                        WHERE category = ? AND environment = ?
                        ORDER BY config_key
                    """, (category, environment))

                    for row in cursor.fetchall():
                        key, value, value_type = row
                        configs[key] = self._deserialize_value(value, value_type)

                    return configs

                except Exception as e:
                    self._logger.error(f"Failed to get configurations for category {category}: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting configurations by category: {e}")
            return {}

    def get_feature_flags(self, environment: str = "default") -> Dict[str, bool]:
        """
        Get all feature flags.

        Args:
            environment: Environment name

        Returns:
            Dictionary of feature flag key-value pairs
        """
        flags = {}
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT config_key, config_value, value_type
                        FROM system_config
                        WHERE is_feature_flag = 1 AND environment = ?
                        ORDER BY config_key
                    """, (environment,))

                    for row in cursor.fetchall():
                        key, value, value_type = row
                        flags[key] = self._deserialize_value(value, value_type)

                    return flags

                except Exception as e:
                    self._logger.error(f"Failed to get feature flags: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting feature flags: {e}")
            return {}

    def delete_config(self, key: str, environment: str = "default") -> bool:
        """
        Delete a configuration entry.

        Args:
            key: Configuration key
            environment: Environment name

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        DELETE FROM system_config
                        WHERE config_key = ? AND environment = ?
                    """, (key, environment))

                    deleted_count = cursor.rowcount
                    conn.commit()

                    if deleted_count > 0:
                        self._logger.debug(f"Configuration deleted: {key}")
                        return True
                    else:
                        self._logger.warning(f"Configuration not found for deletion: {key}")
                        return False

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to delete configuration {key}: {e}")
                    raise e
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error deleting configuration: {e}")
            return False

    def list_configurations(self, environment: str = "default",
                           category: Optional[str] = None,
                           include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        List all configurations with optional filtering.

        Args:
            environment: Environment name
            category: Optional category filter
            include_metadata: Whether to include metadata

        Returns:
            List of configuration dictionaries
        """
        configs = []
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    query = """
                        SELECT config_key, config_value, value_type, category,
                               description, is_feature_flag, is_environment_specific,
                               environment, created_at, updated_at, created_by, updated_by
                        FROM system_config
                        WHERE environment = ?
                    """
                    params = [environment]

                    if category:
                        query += " AND category = ?"
                        params.append(category)

                    query += " ORDER BY category, config_key"

                    cursor.execute(query, params)

                    for row in cursor.fetchall():
                        config = {
                            'key': row[0],
                            'value': self._deserialize_value(row[1], row[2]),
                            'value_type': row[2],
                            'category': row[3],
                            'description': row[4],
                            'is_feature_flag': bool(row[5]),
                            'is_environment_specific': bool(row[6]),
                            'environment': row[7],
                            'created_at': row[8],
                            'updated_at': row[9],
                            'created_by': row[10],
                            'updated_by': row[11]
                        }

                        if include_metadata:
                            config['metadata'] = self._get_config_metadata(cursor, row[0])

                        configs.append(config)

                    return configs

                except Exception as e:
                    self._logger.error(f"Failed to list configurations: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error listing configurations: {e}")
            return []

    def set_config_metadata(self, config_key: str, metadata_key: str,
                           metadata_value: Any) -> bool:
        """
        Set metadata for a configuration entry.

        Args:
            config_key: Configuration key
            metadata_key: Metadata key
            metadata_value: Metadata value

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        INSERT OR REPLACE INTO config_metadata
                        (config_key, metadata_key, metadata_value)
                        VALUES (?, ?, ?)
                    """, (config_key, metadata_key, json.dumps(metadata_value)))

                    conn.commit()
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to set metadata for {config_key}: {e}")
                    raise e
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error setting configuration metadata: {e}")
            return False

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get all configuration categories.

        Returns:
            List of category dictionaries
        """
        categories = []
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT category_name, description, parent_category,
                               display_order, is_active, created_at
                        FROM config_categories
                        WHERE is_active = 1
                        ORDER BY display_order, category_name
                    """)

                    for row in cursor.fetchall():
                        categories.append({
                            'name': row[0],
                            'description': row[1],
                            'parent_category': row[2],
                            'display_order': row[3],
                            'is_active': bool(row[4]),
                            'created_at': row[5]
                        })

                    return categories

                except Exception as e:
                    self._logger.error(f"Failed to get categories: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting categories: {e}")
            return []

    def _serialize_value(self, value: Any) -> Tuple[str, str]:
        """
        Serialize a value for database storage.

        Args:
            value: Value to serialize

        Returns:
            Tuple of (value_type, serialized_value)
        """
        if isinstance(value, bool):
            return "boolean", json.dumps(value)
        elif isinstance(value, int):
            return "integer", str(value)
        elif isinstance(value, float):
            return "float", str(value)
        elif isinstance(value, str):
            return "string", value
        elif isinstance(value, (list, dict)):
            return "json", json.dumps(value)
        else:
            return "string", str(value)

    def _deserialize_value(self, value: str, value_type: str) -> Any:
        """
        Deserialize a value from database storage.

        Args:
            value: Serialized value
            value_type: Type of the value

        Returns:
            Deserialized value
        """
        try:
            if value_type == "boolean":
                return json.loads(value)
            elif value_type == "integer":
                return int(value)
            elif value_type == "float":
                return float(value)
            elif value_type == "string":
                return value
            elif value_type == "json":
                return json.loads(value)
            else:
                return value
        except (ValueError, json.JSONDecodeError) as e:
            self._logger.warning(f"Failed to deserialize value {value} of type {value_type}: {e}")
            return value

    def _get_config_metadata(self, cursor: sqlite3.Cursor, config_key: str) -> Dict[str, Any]:
        """
        Get metadata for a configuration entry.

        Args:
            cursor: Database cursor
            config_key: Configuration key

        Returns:
            Dictionary of metadata
        """
        metadata = {}
        try:
            cursor.execute("""
                SELECT metadata_key, metadata_value
                FROM config_metadata
                WHERE config_key = ?
            """, (config_key,))

            for row in cursor.fetchall():
                key, value = row
                try:
                    metadata[key] = json.loads(value)
                except json.JSONDecodeError:
                    metadata[key] = value

            return metadata

        except Exception as e:
            self._logger.error(f"Failed to get metadata for {config_key}: {e}")
            return {}

    def backup_configurations(self, backup_path: Optional[str] = None) -> bool:
        """
        Create a backup of all configurations.

        Args:
            backup_path: Optional backup file path

        Returns:
            bool: True if successful
        """
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"config_backup_{timestamp}.json"

            configs = self.list_configurations(include_metadata=True)
            categories = self.get_categories()

            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'configurations': configs,
                'categories': categories
            }

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, default=str)

            self._logger.info(f"Configuration backup created: {backup_path}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to create configuration backup: {e}")
            return False

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.debug("Configuration storage database closed")


def create_config_storage_db(db_path: Optional[str] = None) -> ConfigStorageDB:
    """
    Factory function to create a ConfigStorageDB instance.

    Args:
        db_path: Optional database path

    Returns:
        ConfigStorageDB instance
    """
    return ConfigStorageDB(db_path)
