"""
Module: user_preferences_db
Description: User preferences database management for MikroDok application
Phase: 1
Location: /src/modules/database/app_state_db/user_preferences_db/user_preferences_db.py
"""

# Standard library imports
import sqlite3
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
import threading


class UserPreferencesDB:
    """
    User preferences database manager.
    
    Handles storage and retrieval of user preferences including
    theme settings, UI preferences, and application configuration.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the user preferences database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to user data directory
            data_dir = Path.home() / ".mikrodok" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "user_preferences.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Create preferences table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL DEFAULT 'default',
                        preference_key TEXT NOT NULL,
                        preference_value TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, preference_key)
                    )
                """)
                
                # Create settings table for complex preferences
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL DEFAULT 'default',
                        settings_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id)
                    )
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                table_names = [table[0] for table in tables]

                if 'user_preferences' not in table_names:
                    raise RuntimeError("Failed to create user_preferences table")
                if 'user_settings' not in table_names:
                    raise RuntimeError("Failed to create user_settings table")

                # Debug: Print successful initialization
                print(f"Database initialized successfully at {self._db_path}")
                print(f"Tables created: {table_names}")

            except Exception as e:
                conn.rollback()
                print(f"Database initialization error: {e}")
                raise RuntimeError(f"Database initialization failed: {e}")
            finally:
                conn.close()
    
    def save_user_preferences(self, preferences: Dict[str, Any], user_id: str = "default") -> None:
        """
        Save user preferences to database.
        
        Args:
            preferences: Dictionary of preferences to save
            user_id: User identifier
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Save as JSON in settings table
                settings_json = json.dumps(preferences)
                cursor.execute("""
                    INSERT OR REPLACE INTO user_settings (user_id, settings_data, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (user_id, settings_json))
                
                # Also save individual preferences for easy querying
                for key, value in preferences.items():
                    value_json = json.dumps(value)
                    cursor.execute("""
                        INSERT OR REPLACE INTO user_preferences 
                        (user_id, preference_key, preference_value, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """, (user_id, key, value_json))
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
    
    def get_user_preferences(self, user_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get user preferences from database.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary of preferences or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Try to get from settings table first
                cursor.execute("""
                    SELECT settings_data FROM user_settings WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                
                # Fallback to individual preferences
                cursor.execute("""
                    SELECT preference_key, preference_value 
                    FROM user_preferences 
                    WHERE user_id = ?
                """, (user_id,))
                
                rows = cursor.fetchall()
                if rows:
                    preferences = {}
                    for key, value_json in rows:
                        preferences[key] = json.loads(value_json)
                    return preferences
                
                return None
            finally:
                conn.close()
    
    def get_preference(self, key: str, default: Any = None, user_id: str = "default") -> Any:
        """
        Get a specific preference value.
        
        Args:
            key: Preference key
            default: Default value if not found
            user_id: User identifier
            
        Returns:
            Preference value or default
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT preference_value FROM user_preferences 
                    WHERE user_id = ? AND preference_key = ?
                """, (user_id, key))
                
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return default
            finally:
                conn.close()
    
    def set_preference(self, key: str, value: Any, user_id: str = "default") -> None:
        """
        Set a specific preference value.
        
        Args:
            key: Preference key
            value: Preference value
            user_id: User identifier
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                value_json = json.dumps(value)
                cursor.execute("""
                    INSERT OR REPLACE INTO user_preferences 
                    (user_id, preference_key, preference_value, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, key, value_json))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
    
    def delete_preference(self, key: str, user_id: str = "default") -> None:
        """
        Delete a specific preference.
        
        Args:
            key: Preference key to delete
            user_id: User identifier
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM user_preferences 
                    WHERE user_id = ? AND preference_key = ?
                """, (user_id, key))
                conn.commit()
            finally:
                conn.close()
    
    def clear_all_preferences(self, user_id: str = "default") -> None:
        """
        Clear all preferences for a user.
        
        Args:
            user_id: User identifier
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
                conn.commit()
            finally:
                conn.close()
    
    def export_preferences(self, user_id: str = "default") -> Dict[str, Any]:
        """
        Export all preferences for backup.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary of all preferences
        """
        preferences = self.get_user_preferences(user_id)
        return preferences if preferences else {}
    
    def import_preferences(self, preferences: Dict[str, Any], user_id: str = "default") -> None:
        """
        Import preferences from backup.
        
        Args:
            preferences: Dictionary of preferences to import
            user_id: User identifier
        """
        self.save_user_preferences(preferences, user_id)
