"""
Module: project_settings_db
Description: Manages project-specific configurations and user preferences with JSON storage
Phase: 4
Location: /src/modules/database/project_repository_db/project_settings_db/
"""

# Standard library imports
import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Local imports
from ..entities import ProjectSettingEntry, SettingType, SettingCategory
from ...database_core_db.connection_manager_db.connection_manager_db import ConnectionManagerDB


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class ProjectSettingsDB:
    """
    Project-specific settings database manager.
    
    Handles storage and retrieval of project-specific configurations and
    user preferences with JSON storage support, type validation, and
    hierarchical settings management.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the project settings database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to projects data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "projects"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "project_settings.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._connection_manager = ConnectionManagerDB(db_path)
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the database schema."""
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create project_settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS project_settings (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        setting_key TEXT NOT NULL,
                        setting_value TEXT NOT NULL,
                        setting_type TEXT NOT NULL DEFAULT 'string',
                        category TEXT NOT NULL DEFAULT 'general',
                        description TEXT,
                        is_user_defined BOOLEAN DEFAULT 1,
                        is_encrypted BOOLEAN DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(project_id, setting_key),
                        CONSTRAINT chk_setting_type CHECK (setting_type IN ('string', 'integer', 'float', 'boolean', 'json', 'list')),
                        CONSTRAINT chk_category CHECK (category IN ('general', 'training', 'inference', 'performance', 'security', 'ui', 'advanced'))
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_settings_project_id ON project_settings(project_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_settings_key ON project_settings(setting_key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_settings_category ON project_settings(category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_settings_type ON project_settings(setting_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_settings_updated ON project_settings(updated_at)")
                
                # Create trigger for automatic updated_at timestamp
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_project_settings_timestamp 
                    AFTER UPDATE ON project_settings
                    FOR EACH ROW
                    BEGIN
                        UPDATE project_settings SET updated_at = datetime('now') WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()
                self._logger.debug("Project settings database initialized successfully")
                
        except Exception as e:
            self._logger.error(f"Failed to initialize project settings database: {e}")
            raise
    
    def set_setting(self, project_id: str, key: str, value: Any,
                   setting_type: SettingType = SettingType.STRING,
                   category: SettingCategory = SettingCategory.GENERAL,
                   description: Optional[str] = None,
                   is_user_defined: bool = True,
                   is_encrypted: bool = False) -> bool:
        """
        Set a project setting value.
        
        Args:
            project_id: Project identifier
            key: Setting key
            value: Setting value
            setting_type: Type of the setting value
            category: Setting category
            description: Optional description
            is_user_defined: Whether this is a user-defined setting
            is_encrypted: Whether the value should be encrypted
            
        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                # Convert value to string based on type
                if setting_type in (SettingType.JSON, SettingType.LIST):
                    string_value = json.dumps(value)
                else:
                    string_value = str(value)
                
                # Create setting entry
                setting = ProjectSettingEntry(
                    project_id=project_id,
                    setting_key=key,
                    setting_value=string_value,
                    setting_type=setting_type,
                    category=category,
                    description=description,
                    is_user_defined=is_user_defined,
                    is_encrypted=is_encrypted
                )
                
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO project_settings (
                            id, project_id, setting_key, setting_value, setting_type,
                            category, description, is_user_defined, is_encrypted,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        setting.id,
                        setting.project_id,
                        setting.setting_key,
                        setting.setting_value,
                        setting.setting_type.value,
                        setting.category.value,
                        setting.description,
                        setting.is_user_defined,
                        setting.is_encrypted,
                        setting.created_at.isoformat(),
                        setting.updated_at.isoformat()
                    ))
                    
                    conn.commit()
                    self._logger.debug(f"Set setting {key} for project {project_id}")
                    return True
                    
        except Exception as e:
            self._logger.error(f"Failed to set setting {key} for project {project_id}: {e}")
            raise
    
    def get_setting(self, project_id: str, key: str, default: Any = None) -> Any:
        """
        Get a project setting value.
        
        Args:
            project_id: Project identifier
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            Setting value with proper type conversion
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM project_settings 
                    WHERE project_id = ? AND setting_key = ?
                """, (project_id, key))
                
                row = cursor.fetchone()
                if row:
                    setting = self._row_to_setting(row)
                    return setting.get_typed_value()
                
                return default
                
        except Exception as e:
            self._logger.error(f"Failed to get setting {key} for project {project_id}: {e}")
            return default
    
    def get_setting_entry(self, project_id: str, key: str) -> Optional[ProjectSettingEntry]:
        """
        Get a complete setting entry.
        
        Args:
            project_id: Project identifier
            key: Setting key
            
        Returns:
            ProjectSettingEntry or None if not found
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM project_settings 
                    WHERE project_id = ? AND setting_key = ?
                """, (project_id, key))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_setting(row)
                
                return None
                
        except Exception as e:
            self._logger.error(f"Failed to get setting entry {key} for project {project_id}: {e}")
            return None
    
    def get_all_settings(self, project_id: str, 
                        category: Optional[SettingCategory] = None) -> Dict[str, Any]:
        """
        Get all settings for a project.
        
        Args:
            project_id: Project identifier
            category: Optional category filter
            
        Returns:
            Dictionary of setting key-value pairs
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                if category:
                    cursor.execute("""
                        SELECT * FROM project_settings 
                        WHERE project_id = ? AND category = ?
                        ORDER BY setting_key
                    """, (project_id, category.value))
                else:
                    cursor.execute("""
                        SELECT * FROM project_settings 
                        WHERE project_id = ?
                        ORDER BY category, setting_key
                    """, (project_id,))
                
                rows = cursor.fetchall()
                settings = {}
                
                for row in rows:
                    setting = self._row_to_setting(row)
                    settings[setting.setting_key] = setting.get_typed_value()
                
                return settings
                
        except Exception as e:
            self._logger.error(f"Failed to get all settings for project {project_id}: {e}")
            return {}
    
    def get_settings_by_category(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all settings grouped by category.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary grouped by category
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM project_settings 
                    WHERE project_id = ?
                    ORDER BY category, setting_key
                """, (project_id,))
                
                rows = cursor.fetchall()
                settings_by_category = {}
                
                for row in rows:
                    setting = self._row_to_setting(row)
                    category = setting.category.value
                    
                    if category not in settings_by_category:
                        settings_by_category[category] = {}
                    
                    settings_by_category[category][setting.setting_key] = setting.get_typed_value()
                
                return settings_by_category
                
        except Exception as e:
            self._logger.error(f"Failed to get settings by category for project {project_id}: {e}")
            return {}
    
    def delete_setting(self, project_id: str, key: str) -> bool:
        """
        Delete a project setting.
        
        Args:
            project_id: Project identifier
            key: Setting key
            
        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        DELETE FROM project_settings 
                        WHERE project_id = ? AND setting_key = ?
                    """, (project_id, key))
                    
                    if cursor.rowcount > 0:
                        conn.commit()
                        self._logger.debug(f"Deleted setting {key} for project {project_id}")
                        return True
                    else:
                        self._logger.warning(f"Setting {key} not found for project {project_id}")
                        return False
                        
        except Exception as e:
            self._logger.error(f"Failed to delete setting {key} for project {project_id}: {e}")
            raise

    def delete_all_settings(self, project_id: str) -> bool:
        """
        Delete all settings for a project.

        Args:
            project_id: Project identifier

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute("""
                        DELETE FROM project_settings WHERE project_id = ?
                    """, (project_id,))

                    conn.commit()
                    self._logger.info(f"Deleted all settings for project {project_id}")
                    return True

        except Exception as e:
            self._logger.error(f"Failed to delete all settings for project {project_id}: {e}")
            raise

    def update_setting_value(self, project_id: str, key: str, value: Any) -> bool:
        """
        Update only the value of an existing setting.

        Args:
            project_id: Project identifier
            key: Setting key
            value: New setting value

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                # Get existing setting to preserve type and other metadata
                existing = self.get_setting_entry(project_id, key)
                if not existing:
                    self._logger.warning(f"Setting {key} not found for project {project_id}")
                    return False

                # Update value with type conversion
                existing.set_typed_value(value)

                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE project_settings
                        SET setting_value = ?, updated_at = ?
                        WHERE project_id = ? AND setting_key = ?
                    """, (
                        existing.setting_value,
                        existing.updated_at.isoformat(),
                        project_id,
                        key
                    ))

                    if cursor.rowcount > 0:
                        conn.commit()
                        self._logger.debug(f"Updated setting value {key} for project {project_id}")
                        return True
                    else:
                        return False

        except Exception as e:
            self._logger.error(f"Failed to update setting value {key} for project {project_id}: {e}")
            raise

    def bulk_set_settings(self, project_id: str, settings: Dict[str, Any],
                         category: SettingCategory = SettingCategory.GENERAL,
                         setting_type: SettingType = SettingType.STRING) -> bool:
        """
        Set multiple settings in a single transaction.

        Args:
            project_id: Project identifier
            settings: Dictionary of key-value pairs
            category: Default category for all settings
            setting_type: Default type for all settings

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()

                    for key, value in settings.items():
                        # Convert value to string based on type
                        if setting_type in (SettingType.JSON, SettingType.LIST):
                            string_value = json.dumps(value)
                        else:
                            string_value = str(value)

                        # Create setting entry
                        setting = ProjectSettingEntry(
                            project_id=project_id,
                            setting_key=key,
                            setting_value=string_value,
                            setting_type=setting_type,
                            category=category
                        )

                        cursor.execute("""
                            INSERT OR REPLACE INTO project_settings (
                                id, project_id, setting_key, setting_value, setting_type,
                                category, description, is_user_defined, is_encrypted,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            setting.id,
                            setting.project_id,
                            setting.setting_key,
                            setting.setting_value,
                            setting.setting_type.value,
                            setting.category.value,
                            setting.description,
                            setting.is_user_defined,
                            setting.is_encrypted,
                            setting.created_at.isoformat(),
                            setting.updated_at.isoformat()
                        ))

                    conn.commit()
                    self._logger.info(f"Bulk set {len(settings)} settings for project {project_id}")
                    return True

        except Exception as e:
            self._logger.error(f"Failed to bulk set settings for project {project_id}: {e}")
            raise

    def export_settings(self, project_id: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Export project settings to JSON format.

        Args:
            project_id: Project identifier
            file_path: Optional file path to save JSON

        Returns:
            Dictionary of exported settings
        """
        try:
            settings_data = {
                "project_id": project_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "settings": self.get_settings_by_category(project_id)
            }

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(settings_data, f, indent=2, ensure_ascii=False)
                self._logger.info(f"Exported settings for project {project_id} to {file_path}")

            return settings_data

        except Exception as e:
            self._logger.error(f"Failed to export settings for project {project_id}: {e}")
            raise

    def import_settings(self, project_id: str, settings_data: Union[Dict[str, Any], str],
                       overwrite: bool = False) -> bool:
        """
        Import project settings from JSON data.

        Args:
            project_id: Project identifier
            settings_data: Settings data as dict or JSON string
            overwrite: Whether to overwrite existing settings

        Returns:
            bool: True if successful
        """
        try:
            # Parse JSON if string
            if isinstance(settings_data, str):
                if settings_data.endswith('.json'):
                    # File path
                    with open(settings_data, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    # JSON string
                    data = json.loads(settings_data)
            else:
                data = settings_data

            settings = data.get("settings", {})

            with self._lock:
                for category_name, category_settings in settings.items():
                    try:
                        category = SettingCategory(category_name)
                    except ValueError:
                        category = SettingCategory.GENERAL

                    for key, value in category_settings.items():
                        # Skip if setting exists and not overwriting
                        if not overwrite and self.get_setting_entry(project_id, key):
                            continue

                        # Determine setting type from value
                        if isinstance(value, bool):
                            setting_type = SettingType.BOOLEAN
                        elif isinstance(value, int):
                            setting_type = SettingType.INTEGER
                        elif isinstance(value, float):
                            setting_type = SettingType.FLOAT
                        elif isinstance(value, (list, dict)):
                            setting_type = SettingType.JSON
                        else:
                            setting_type = SettingType.STRING

                        self.set_setting(project_id, key, value, setting_type, category)

                self._logger.info(f"Imported settings for project {project_id}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to import settings for project {project_id}: {e}")
            raise

    def _row_to_setting(self, row: sqlite3.Row) -> ProjectSettingEntry:
        """
        Convert database row to ProjectSettingEntry.

        Args:
            row: Database row

        Returns:
            ProjectSettingEntry
        """
        try:
            return ProjectSettingEntry(
                id=row["id"],
                project_id=row["project_id"],
                setting_key=row["setting_key"],
                setting_value=row["setting_value"],
                setting_type=SettingType(row["setting_type"]),
                category=SettingCategory(row["category"]),
                description=row["description"],
                is_user_defined=bool(row["is_user_defined"]),
                is_encrypted=bool(row["is_encrypted"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"])
            )

        except Exception as e:
            self._logger.error(f"Failed to convert row to setting: {e}")
            raise

    def close(self):
        """Close database connections and cleanup resources."""
        try:
            if hasattr(self, '_connection_manager'):
                self._connection_manager.close()
            self._logger.debug("Project settings database closed")
        except Exception as e:
            self._logger.error(f"Error closing project settings database: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
