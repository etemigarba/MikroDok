"""
Module: collection_metadata_db
Description: Stores collection-level settings, tags, and aggregated statistics with SQLite database operations
Phase: 3
Location: /src/modules/database/document_collections_db/collection_metadata_db/
"""

# Standard library imports
import sqlite3
import threading
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger


class CollectionMetadataDB:
    """
    Collection metadata database for collection-level settings and statistics.
    
    Stores collection-level settings, tags, and aggregated statistics
    with SQLite database operations. Provides thread-safe operations
    with transaction support for metadata management, tagging system,
    and statistical aggregation.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the collection metadata database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to collections data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "collections"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "collection_metadata.db")
        
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
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Create collection settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_settings (
                        setting_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        setting_key TEXT NOT NULL,
                        setting_value TEXT NOT NULL,
                        setting_type TEXT DEFAULT 'string',
                        is_encrypted BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        UNIQUE(collection_id, setting_key)
                    )
                """)
                
                # Create collection tags table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_tags (
                        tag_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        tag_name TEXT NOT NULL,
                        tag_value TEXT,
                        tag_color TEXT,
                        tag_category TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        UNIQUE(collection_id, tag_name)
                    )
                """)
                
                # Create collection statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_statistics (
                        stat_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        stat_name TEXT NOT NULL,
                        stat_value REAL NOT NULL,
                        stat_type TEXT DEFAULT 'counter',
                        measurement_unit TEXT,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        calculation_method TEXT,
                        metadata TEXT DEFAULT '{}',
                        UNIQUE(collection_id, stat_name)
                    )
                """)
                
                # Create collection aggregations table for time-series data
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_aggregations (
                        aggregation_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        aggregation_type TEXT NOT NULL,
                        time_period TEXT NOT NULL,
                        period_start TIMESTAMP NOT NULL,
                        period_end TIMESTAMP NOT NULL,
                        aggregated_value REAL NOT NULL,
                        sample_count INTEGER DEFAULT 1,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                # Create collection preferences table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_preferences (
                        preference_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        preference_category TEXT NOT NULL,
                        preference_key TEXT NOT NULL,
                        preference_value TEXT NOT NULL,
                        is_inherited BOOLEAN DEFAULT 0,
                        inherited_from TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_by TEXT,
                        UNIQUE(collection_id, preference_category, preference_key)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_settings_collection ON collection_settings(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_settings_key ON collection_settings(setting_key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_collection ON collection_tags(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON collection_tags(tag_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_category ON collection_tags(tag_category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_collection ON collection_statistics(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_name ON collection_statistics(stat_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aggregations_collection ON collection_aggregations(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aggregations_metric ON collection_aggregations(metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aggregations_period ON collection_aggregations(period_start, period_end)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_preferences_collection ON collection_preferences(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_preferences_category ON collection_preferences(preference_category)")
                
                conn.commit()
                
                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = ['collection_settings', 'collection_tags', 'collection_statistics', 
                                 'collection_aggregations', 'collection_preferences']
                
                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")
                
                self._logger.info("Collection metadata database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize collection metadata database: {e}")
                raise
            finally:
                conn.close()
    
    def set_collection_setting(self, collection_id: str, setting_key: str, 
                              setting_value: Any, setting_type: str = "string",
                              is_encrypted: bool = False, created_by: Optional[str] = None) -> bool:
        """
        Set a collection setting.
        
        Args:
            collection_id: Collection identifier
            setting_key: Setting key
            setting_value: Setting value
            setting_type: Type of setting (string, number, boolean, json)
            is_encrypted: Whether the setting should be encrypted
            created_by: User who created the setting
            
        Returns:
            True if setting was successful
        """
        setting_id = str(uuid.uuid4())
        
        # Convert value to string based on type
        if setting_type == "json":
            value_str = json.dumps(setting_value)
        elif setting_type == "boolean":
            value_str = str(bool(setting_value)).lower()
        else:
            value_str = str(setting_value)
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_settings 
                    (setting_id, collection_id, setting_key, setting_value, setting_type,
                     is_encrypted, created_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (setting_id, collection_id, setting_key, value_str, setting_type,
                      is_encrypted, created_by, datetime.now(timezone.utc).isoformat()))
                
                conn.commit()
                self._logger.info(f"Set setting {setting_key} for collection {collection_id}")
                return True
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to set collection setting: {e}")
                raise
            finally:
                conn.close()

    def get_collection_setting(self, collection_id: str, setting_key: str) -> Optional[Any]:
        """
        Get a collection setting.

        Args:
            collection_id: Collection identifier
            setting_key: Setting key

        Returns:
            Setting value or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT setting_value, setting_type FROM collection_settings
                    WHERE collection_id = ? AND setting_key = ?
                """, (collection_id, setting_key))

                row = cursor.fetchone()
                if row:
                    value_str, setting_type = row

                    # Convert value based on type
                    if setting_type == "json":
                        return json.loads(value_str)
                    elif setting_type == "boolean":
                        return value_str.lower() == "true"
                    elif setting_type == "number":
                        try:
                            return float(value_str) if '.' in value_str else int(value_str)
                        except ValueError:
                            return value_str
                    else:
                        return value_str

                return None

            except Exception as e:
                self._logger.error(f"Failed to get collection setting: {e}")
                raise
            finally:
                conn.close()

    def get_collection_settings(self, collection_id: str) -> Dict[str, Any]:
        """
        Get all settings for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Dictionary of settings
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT setting_key, setting_value, setting_type, created_at, updated_at
                    FROM collection_settings
                    WHERE collection_id = ?
                    ORDER BY setting_key
                """, (collection_id,))

                settings = {}
                for row in cursor.fetchall():
                    key, value_str, setting_type, created_at, updated_at = row

                    # Convert value based on type
                    if setting_type == "json":
                        value = json.loads(value_str)
                    elif setting_type == "boolean":
                        value = value_str.lower() == "true"
                    elif setting_type == "number":
                        try:
                            value = float(value_str) if '.' in value_str else int(value_str)
                        except ValueError:
                            value = value_str
                    else:
                        value = value_str

                    settings[key] = {
                        'value': value,
                        'type': setting_type,
                        'created_at': created_at,
                        'updated_at': updated_at
                    }

                return settings

            except Exception as e:
                self._logger.error(f"Failed to get collection settings: {e}")
                raise
            finally:
                conn.close()

    def delete_collection_setting(self, collection_id: str, setting_key: str) -> bool:
        """
        Delete a collection setting.

        Args:
            collection_id: Collection identifier
            setting_key: Setting key

        Returns:
            True if deletion was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM collection_settings
                    WHERE collection_id = ? AND setting_key = ?
                """, (collection_id, setting_key))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Deleted setting {setting_key} for collection {collection_id}")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete collection setting: {e}")
                raise
            finally:
                conn.close()

    def add_collection_tag(self, collection_id: str, tag_name: str,
                          tag_value: Optional[str] = None, tag_color: Optional[str] = None,
                          tag_category: Optional[str] = None, created_by: Optional[str] = None) -> bool:
        """
        Add a tag to a collection.

        Args:
            collection_id: Collection identifier
            tag_name: Tag name
            tag_value: Optional tag value
            tag_color: Optional tag color
            tag_category: Optional tag category
            created_by: User who created the tag

        Returns:
            True if tag was added successfully
        """
        tag_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_tags
                    (tag_id, collection_id, tag_name, tag_value, tag_color, tag_category, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (tag_id, collection_id, tag_name, tag_value, tag_color, tag_category, created_by))

                conn.commit()
                self._logger.info(f"Added tag {tag_name} to collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add collection tag: {e}")
                raise
            finally:
                conn.close()

    def get_collection_tags(self, collection_id: str, tag_category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get tags for a collection.

        Args:
            collection_id: Collection identifier
            tag_category: Optional filter by tag category

        Returns:
            List of tags
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT tag_id, tag_name, tag_value, tag_color, tag_category, created_at, created_by
                    FROM collection_tags
                    WHERE collection_id = ?
                """
                params = [collection_id]

                if tag_category:
                    query += " AND tag_category = ?"
                    params.append(tag_category)

                query += " ORDER BY tag_name"
                cursor.execute(query, params)

                tags = []
                for row in cursor.fetchall():
                    tags.append({
                        'tag_id': row[0],
                        'tag_name': row[1],
                        'tag_value': row[2],
                        'tag_color': row[3],
                        'tag_category': row[4],
                        'created_at': row[5],
                        'created_by': row[6]
                    })

                return tags

            except Exception as e:
                self._logger.error(f"Failed to get collection tags: {e}")
                raise
            finally:
                conn.close()

    def remove_collection_tag(self, collection_id: str, tag_name: str) -> bool:
        """
        Remove a tag from a collection.

        Args:
            collection_id: Collection identifier
            tag_name: Tag name to remove

        Returns:
            True if removal was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM collection_tags
                    WHERE collection_id = ? AND tag_name = ?
                """, (collection_id, tag_name))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Removed tag {tag_name} from collection {collection_id}")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to remove collection tag: {e}")
                raise
            finally:
                conn.close()

    def update_collection_statistic(self, collection_id: str, stat_name: str,
                                   stat_value: float, stat_type: str = "counter",
                                   measurement_unit: Optional[str] = None,
                                   calculation_method: Optional[str] = None,
                                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update a collection statistic.

        Args:
            collection_id: Collection identifier
            stat_name: Statistic name
            stat_value: Statistic value
            stat_type: Type of statistic (counter, gauge, histogram, etc.)
            measurement_unit: Unit of measurement
            calculation_method: Method used to calculate the statistic
            metadata: Additional metadata

        Returns:
            True if update was successful
        """
        stat_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_statistics
                    (stat_id, collection_id, stat_name, stat_value, stat_type,
                     measurement_unit, calculation_method, metadata, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stat_id, collection_id, stat_name, stat_value, stat_type,
                      measurement_unit, calculation_method, metadata_json,
                      datetime.now(timezone.utc).isoformat()))

                conn.commit()
                self._logger.info(f"Updated statistic {stat_name} for collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update collection statistic: {e}")
                raise
            finally:
                conn.close()

    def get_collection_statistics(self, collection_id: str) -> Dict[str, Any]:
        """
        Get all statistics for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Dictionary of statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT stat_name, stat_value, stat_type, measurement_unit,
                           calculation_method, calculated_at, metadata
                    FROM collection_statistics
                    WHERE collection_id = ?
                    ORDER BY stat_name
                """, (collection_id,))

                statistics = {}
                for row in cursor.fetchall():
                    stat_name, stat_value, stat_type, unit, method, calculated_at, metadata_str = row

                    statistics[stat_name] = {
                        'value': stat_value,
                        'type': stat_type,
                        'unit': unit,
                        'calculation_method': method,
                        'calculated_at': calculated_at,
                        'metadata': json.loads(metadata_str) if metadata_str else {}
                    }

                return statistics

            except Exception as e:
                self._logger.error(f"Failed to get collection statistics: {e}")
                raise
            finally:
                conn.close()

    def add_collection_aggregation(self, collection_id: str, metric_name: str,
                                  aggregation_type: str, time_period: str,
                                  period_start: datetime, period_end: datetime,
                                  aggregated_value: float, sample_count: int = 1,
                                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a time-series aggregation for a collection.

        Args:
            collection_id: Collection identifier
            metric_name: Name of the metric
            aggregation_type: Type of aggregation (sum, avg, min, max, count)
            time_period: Time period (hour, day, week, month)
            period_start: Start of the time period
            period_end: End of the time period
            aggregated_value: Aggregated value
            sample_count: Number of samples in the aggregation
            metadata: Additional metadata

        Returns:
            True if addition was successful
        """
        aggregation_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_aggregations
                    (aggregation_id, collection_id, metric_name, aggregation_type,
                     time_period, period_start, period_end, aggregated_value,
                     sample_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (aggregation_id, collection_id, metric_name, aggregation_type,
                      time_period, period_start.isoformat(), period_end.isoformat(),
                      aggregated_value, sample_count, metadata_json))

                conn.commit()
                self._logger.info(f"Added aggregation for {metric_name} in collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add collection aggregation: {e}")
                raise
            finally:
                conn.close()

    def get_collection_aggregations(self, collection_id: str, metric_name: Optional[str] = None,
                                   time_period: Optional[str] = None,
                                   start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get aggregations for a collection.

        Args:
            collection_id: Collection identifier
            metric_name: Optional filter by metric name
            time_period: Optional filter by time period
            start_date: Optional filter by start date
            end_date: Optional filter by end date

        Returns:
            List of aggregations
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT aggregation_id, metric_name, aggregation_type, time_period,
                           period_start, period_end, aggregated_value, sample_count,
                           calculated_at, metadata
                    FROM collection_aggregations
                    WHERE collection_id = ?
                """
                params = [collection_id]

                if metric_name:
                    query += " AND metric_name = ?"
                    params.append(metric_name)

                if time_period:
                    query += " AND time_period = ?"
                    params.append(time_period)

                if start_date:
                    query += " AND period_start >= ?"
                    params.append(start_date.isoformat())

                if end_date:
                    query += " AND period_end <= ?"
                    params.append(end_date.isoformat())

                query += " ORDER BY period_start DESC"
                cursor.execute(query, params)

                aggregations = []
                for row in cursor.fetchall():
                    aggregations.append({
                        'aggregation_id': row[0],
                        'metric_name': row[1],
                        'aggregation_type': row[2],
                        'time_period': row[3],
                        'period_start': row[4],
                        'period_end': row[5],
                        'aggregated_value': row[6],
                        'sample_count': row[7],
                        'calculated_at': row[8],
                        'metadata': json.loads(row[9]) if row[9] else {}
                    })

                return aggregations

            except Exception as e:
                self._logger.error(f"Failed to get collection aggregations: {e}")
                raise
            finally:
                conn.close()

    def set_collection_preference(self, collection_id: str, preference_category: str,
                                 preference_key: str, preference_value: Any,
                                 is_inherited: bool = False, inherited_from: Optional[str] = None,
                                 updated_by: Optional[str] = None) -> bool:
        """
        Set a collection preference.

        Args:
            collection_id: Collection identifier
            preference_category: Category of preference
            preference_key: Preference key
            preference_value: Preference value
            is_inherited: Whether the preference is inherited
            inherited_from: Source of inheritance
            updated_by: User who updated the preference

        Returns:
            True if setting was successful
        """
        preference_id = str(uuid.uuid4())
        value_str = json.dumps(preference_value) if isinstance(preference_value, (dict, list)) else str(preference_value)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_preferences
                    (preference_id, collection_id, preference_category, preference_key,
                     preference_value, is_inherited, inherited_from, updated_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (preference_id, collection_id, preference_category, preference_key,
                      value_str, is_inherited, inherited_from, updated_by,
                      datetime.now(timezone.utc).isoformat()))

                conn.commit()
                self._logger.info(f"Set preference {preference_key} for collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to set collection preference: {e}")
                raise
            finally:
                conn.close()

    def get_collection_preferences(self, collection_id: str,
                                  preference_category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get preferences for a collection.

        Args:
            collection_id: Collection identifier
            preference_category: Optional filter by category

        Returns:
            Dictionary of preferences
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT preference_category, preference_key, preference_value,
                           is_inherited, inherited_from, updated_at, updated_by
                    FROM collection_preferences
                    WHERE collection_id = ?
                """
                params = [collection_id]

                if preference_category:
                    query += " AND preference_category = ?"
                    params.append(preference_category)

                query += " ORDER BY preference_category, preference_key"
                cursor.execute(query, params)

                preferences = {}
                for row in cursor.fetchall():
                    category, key, value_str, is_inherited, inherited_from, updated_at, updated_by = row

                    # Try to parse JSON, fallback to string
                    try:
                        value = json.loads(value_str)
                    except (json.JSONDecodeError, TypeError):
                        value = value_str

                    if category not in preferences:
                        preferences[category] = {}

                    preferences[category][key] = {
                        'value': value,
                        'is_inherited': bool(is_inherited),
                        'inherited_from': inherited_from,
                        'updated_at': updated_at,
                        'updated_by': updated_by
                    }

                return preferences

            except Exception as e:
                self._logger.error(f"Failed to get collection preferences: {e}")
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("Collection metadata database closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
