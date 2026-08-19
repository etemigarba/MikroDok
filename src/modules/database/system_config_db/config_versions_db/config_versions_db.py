"""
Module: config_versions_db
Description: Tracks configuration changes, maintains version history, and enables rollback capabilities
Phase: 1
Location: /src/modules/database/system_config_db/config_versions_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ConfigVersionsDB:
    """
    Configuration versions database manager.
    
    Handles tracking of configuration changes, maintains version history,
    and provides rollback capabilities. Supports branching and tagging
    of configuration versions for different environments.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the configuration versions database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to system data directory
            data_dir = Path.home() / ".mikrodok" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "config_versions.db")
        
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
                
                # Create configuration versions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_id TEXT NOT NULL UNIQUE,
                        config_key TEXT NOT NULL,
                        old_value TEXT,
                        new_value TEXT,
                        old_value_type TEXT,
                        new_value_type TEXT,
                        change_type TEXT NOT NULL,
                        category TEXT,
                        environment TEXT DEFAULT 'default',
                        branch_name TEXT DEFAULT 'main',
                        parent_version_id TEXT,
                        commit_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'system',
                        is_rollback BOOLEAN DEFAULT 0,
                        rollback_from_version TEXT,
                        checksum TEXT
                    )
                """)
                
                # Create configuration snapshots table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id TEXT NOT NULL UNIQUE,
                        snapshot_name TEXT,
                        description TEXT,
                        environment TEXT DEFAULT 'default',
                        branch_name TEXT DEFAULT 'main',
                        config_data TEXT NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'system',
                        is_tagged BOOLEAN DEFAULT 0,
                        tag_name TEXT,
                        is_backup BOOLEAN DEFAULT 0
                    )
                """)
                
                # Create configuration branches table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_branches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        branch_name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        parent_branch TEXT DEFAULT 'main',
                        created_from_version TEXT,
                        environment TEXT DEFAULT 'default',
                        is_active BOOLEAN DEFAULT 1,
                        is_protected BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'system'
                    )
                """)
                
                # Create configuration tags table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_name TEXT NOT NULL,
                        version_id TEXT,
                        snapshot_id TEXT,
                        description TEXT,
                        environment TEXT DEFAULT 'default',
                        branch_name TEXT DEFAULT 'main',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'system',
                        UNIQUE(tag_name, environment, branch_name)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_config_key 
                    ON config_versions(config_key)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_created_at 
                    ON config_versions(created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_environment 
                    ON config_versions(environment)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_branch 
                    ON config_versions(branch_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_created_at 
                    ON config_snapshots(created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_environment 
                    ON config_snapshots(environment)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tags_name 
                    ON config_tags(tag_name)
                """)
                
                # Insert default branch
                cursor.execute("""
                    INSERT OR IGNORE INTO config_branches 
                    (branch_name, description, is_protected)
                    VALUES ('main', 'Main configuration branch', 1)
                """)
                
                conn.commit()
                self._logger.info("Configuration versions database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize configuration versions database: {e}")
                raise e
            finally:
                conn.close()
    
    def record_change(self, config_key: str, old_value: Any, new_value: Any,
                     change_type: str, category: str = "general",
                     environment: str = "default", branch: str = "main",
                     commit_message: Optional[str] = None,
                     user: str = "system") -> str:
        """
        Record a configuration change.
        
        Args:
            config_key: Configuration key that changed
            old_value: Previous value
            new_value: New value
            change_type: Type of change (CREATE, UPDATE, DELETE)
            category: Configuration category
            environment: Environment name
            branch: Branch name
            commit_message: Optional commit message
            user: User making the change
            
        Returns:
            str: Version ID of the recorded change
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    version_id = str(uuid.uuid4())
                    
                    # Get parent version
                    parent_version_id = self._get_latest_version_id(cursor, config_key, environment, branch)
                    
                    # Serialize values
                    old_value_type, old_value_serialized = self._serialize_value(old_value) if old_value is not None else (None, None)
                    new_value_type, new_value_serialized = self._serialize_value(new_value) if new_value is not None else (None, None)
                    
                    # Calculate checksum
                    checksum = self._calculate_checksum(config_key, new_value_serialized, change_type)
                    
                    cursor.execute("""
                        INSERT INTO config_versions 
                        (version_id, config_key, old_value, new_value, old_value_type, new_value_type,
                         change_type, category, environment, branch_name, parent_version_id,
                         commit_message, created_by, checksum)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (version_id, config_key, old_value_serialized, new_value_serialized,
                          old_value_type, new_value_type, change_type, category, environment,
                          branch, parent_version_id, commit_message, user, checksum))
                    
                    conn.commit()
                    self._logger.debug(f"Configuration change recorded: {config_key} ({change_type})")
                    return version_id
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to record configuration change: {e}")
                    raise e
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error recording configuration change: {e}")
            return ""

    def get_version_history(self, config_key: Optional[str] = None,
                           environment: str = "default",
                           branch: str = "main",
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get version history for configuration(s).

        Args:
            config_key: Optional specific configuration key
            environment: Environment name
            branch: Branch name
            limit: Maximum number of versions to return

        Returns:
            List of version dictionaries
        """
        versions = []
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    query = """
                        SELECT version_id, config_key, old_value, new_value,
                               old_value_type, new_value_type, change_type, category,
                               environment, branch_name, parent_version_id, commit_message,
                               created_at, created_by, is_rollback, rollback_from_version
                        FROM config_versions
                        WHERE environment = ? AND branch_name = ?
                    """
                    params = [environment, branch]

                    if config_key:
                        query += " AND config_key = ?"
                        params.append(config_key)

                    query += " ORDER BY created_at DESC LIMIT ?"
                    params.append(limit)

                    cursor.execute(query, params)

                    for row in cursor.fetchall():
                        version = {
                            'version_id': row[0],
                            'config_key': row[1],
                            'old_value': self._deserialize_value(row[2], row[4]) if row[2] else None,
                            'new_value': self._deserialize_value(row[3], row[5]) if row[3] else None,
                            'change_type': row[6],
                            'category': row[7],
                            'environment': row[8],
                            'branch_name': row[9],
                            'parent_version_id': row[10],
                            'commit_message': row[11],
                            'created_at': row[12],
                            'created_by': row[13],
                            'is_rollback': bool(row[14]),
                            'rollback_from_version': row[15]
                        }
                        versions.append(version)

                    return versions

                except Exception as e:
                    self._logger.error(f"Failed to get version history: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting version history: {e}")
            return []

    def create_snapshot(self, config_data: Dict[str, Any],
                       snapshot_name: Optional[str] = None,
                       description: Optional[str] = None,
                       environment: str = "default",
                       branch: str = "main",
                       user: str = "system",
                       tag_name: Optional[str] = None) -> str:
        """
        Create a configuration snapshot.

        Args:
            config_data: Configuration data to snapshot
            snapshot_name: Optional snapshot name
            description: Optional description
            environment: Environment name
            branch: Branch name
            user: User creating the snapshot
            tag_name: Optional tag name

        Returns:
            str: Snapshot ID
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    snapshot_id = str(uuid.uuid4())

                    if snapshot_name is None:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        snapshot_name = f"snapshot_{timestamp}"

                    # Serialize configuration data
                    config_json = json.dumps(config_data, sort_keys=True, default=str)

                    # Create metadata
                    metadata = {
                        'config_count': len(config_data),
                        'created_timestamp': datetime.now().isoformat(),
                        'checksum': self._calculate_checksum("snapshot", config_json, "CREATE")
                    }

                    cursor.execute("""
                        INSERT INTO config_snapshots
                        (snapshot_id, snapshot_name, description, environment, branch_name,
                         config_data, metadata, created_by, is_tagged, tag_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (snapshot_id, snapshot_name, description, environment, branch,
                          config_json, json.dumps(metadata), user,
                          tag_name is not None, tag_name))

                    # Create tag if specified
                    if tag_name:
                        cursor.execute("""
                            INSERT OR REPLACE INTO config_tags
                            (tag_name, snapshot_id, description, environment, branch_name, created_by)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (tag_name, snapshot_id, description, environment, branch, user))

                    conn.commit()
                    self._logger.info(f"Configuration snapshot created: {snapshot_name}")
                    return snapshot_id

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create configuration snapshot: {e}")
                    raise e
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error creating configuration snapshot: {e}")
            return ""

    def rollback_to_version(self, version_id: str, user: str = "system") -> bool:
        """
        Rollback configuration to a specific version.

        Args:
            version_id: Version ID to rollback to
            user: User performing the rollback

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get the target version
                    cursor.execute("""
                        SELECT config_key, new_value, new_value_type, category, environment, branch_name
                        FROM config_versions
                        WHERE version_id = ?
                    """, (version_id,))

                    target_version = cursor.fetchone()
                    if not target_version:
                        self._logger.error(f"Version not found: {version_id}")
                        return False

                    config_key, value, value_type, category, environment, branch = target_version
                    rollback_value = self._deserialize_value(value, value_type)

                    # Record the rollback as a new version
                    rollback_version_id = str(uuid.uuid4())
                    checksum = self._calculate_checksum(config_key, value, "ROLLBACK")

                    cursor.execute("""
                        INSERT INTO config_versions
                        (version_id, config_key, new_value, new_value_type, change_type,
                         category, environment, branch_name, commit_message, created_by,
                         is_rollback, rollback_from_version, checksum)
                        VALUES (?, ?, ?, ?, 'ROLLBACK', ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (rollback_version_id, config_key, value, value_type, category,
                          environment, branch, f"Rollback to version {version_id}", user,
                          version_id, checksum))

                    conn.commit()
                    self._logger.info(f"Configuration rolled back to version: {version_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to rollback to version {version_id}: {e}")
                    raise e
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error rolling back configuration: {e}")
            return False

    def create_branch(self, branch_name: str, description: Optional[str] = None,
                     parent_branch: str = "main", environment: str = "default",
                     user: str = "system") -> bool:
        """
        Create a new configuration branch.

        Args:
            branch_name: Name of the new branch
            description: Optional description
            parent_branch: Parent branch name
            environment: Environment name
            user: User creating the branch

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get latest version from parent branch
                    cursor.execute("""
                        SELECT version_id FROM config_versions
                        WHERE branch_name = ? AND environment = ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (parent_branch, environment))

                    parent_version = cursor.fetchone()
                    created_from_version = parent_version[0] if parent_version else None

                    cursor.execute("""
                        INSERT INTO config_branches
                        (branch_name, description, parent_branch, created_from_version,
                         environment, created_by)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (branch_name, description, parent_branch, created_from_version,
                          environment, user))

                    conn.commit()
                    self._logger.info(f"Configuration branch created: {branch_name}")
                    return True

                except sqlite3.IntegrityError:
                    self._logger.warning(f"Branch already exists: {branch_name}")
                    return False
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create branch {branch_name}: {e}")
                    raise e
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error creating configuration branch: {e}")
            return False

    def get_snapshots(self, environment: str = "default",
                     branch: str = "main", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get configuration snapshots.

        Args:
            environment: Environment name
            branch: Branch name
            limit: Maximum number of snapshots to return

        Returns:
            List of snapshot dictionaries
        """
        snapshots = []
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT snapshot_id, snapshot_name, description, environment,
                               branch_name, metadata, created_at, created_by,
                               is_tagged, tag_name, is_backup
                        FROM config_snapshots
                        WHERE environment = ? AND branch_name = ?
                        ORDER BY created_at DESC LIMIT ?
                    """, (environment, branch, limit))

                    for row in cursor.fetchall():
                        snapshot = {
                            'snapshot_id': row[0],
                            'snapshot_name': row[1],
                            'description': row[2],
                            'environment': row[3],
                            'branch_name': row[4],
                            'metadata': json.loads(row[5]) if row[5] else {},
                            'created_at': row[6],
                            'created_by': row[7],
                            'is_tagged': bool(row[8]),
                            'tag_name': row[9],
                            'is_backup': bool(row[10])
                        }
                        snapshots.append(snapshot)

                    return snapshots

                except Exception as e:
                    self._logger.error(f"Failed to get snapshots: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting snapshots: {e}")
            return []

    def get_branches(self, environment: str = "default") -> List[Dict[str, Any]]:
        """
        Get all configuration branches.

        Args:
            environment: Environment name

        Returns:
            List of branch dictionaries
        """
        branches = []
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT branch_name, description, parent_branch, created_from_version,
                               environment, is_active, is_protected, created_at, created_by
                        FROM config_branches
                        WHERE environment = ? AND is_active = 1
                        ORDER BY created_at DESC
                    """, (environment,))

                    for row in cursor.fetchall():
                        branch = {
                            'branch_name': row[0],
                            'description': row[1],
                            'parent_branch': row[2],
                            'created_from_version': row[3],
                            'environment': row[4],
                            'is_active': bool(row[5]),
                            'is_protected': bool(row[6]),
                            'created_at': row[7],
                            'created_by': row[8]
                        }
                        branches.append(branch)

                    return branches

                except Exception as e:
                    self._logger.error(f"Failed to get branches: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting branches: {e}")
            return []

    def _get_latest_version_id(self, cursor: sqlite3.Cursor, config_key: str,
                              environment: str, branch: str) -> Optional[str]:
        """
        Get the latest version ID for a configuration key.

        Args:
            cursor: Database cursor
            config_key: Configuration key
            environment: Environment name
            branch: Branch name

        Returns:
            Latest version ID or None
        """
        try:
            cursor.execute("""
                SELECT version_id FROM config_versions
                WHERE config_key = ? AND environment = ? AND branch_name = ?
                ORDER BY created_at DESC LIMIT 1
            """, (config_key, environment, branch))

            result = cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            self._logger.error(f"Failed to get latest version ID: {e}")
            return None

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

    def _calculate_checksum(self, key: str, value: str, change_type: str) -> str:
        """
        Calculate checksum for integrity verification.

        Args:
            key: Configuration key
            value: Configuration value
            change_type: Type of change

        Returns:
            Checksum string
        """
        import hashlib

        data = f"{key}:{value}:{change_type}:{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def get_configuration_diff(self, version_id1: str, version_id2: str) -> Dict[str, Any]:
        """
        Get differences between two configuration versions.

        Args:
            version_id1: First version ID
            version_id2: Second version ID

        Returns:
            Dictionary containing the differences
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get both versions
                    cursor.execute("""
                        SELECT config_key, new_value, new_value_type, change_type, created_at
                        FROM config_versions
                        WHERE version_id IN (?, ?)
                        ORDER BY created_at
                    """, (version_id1, version_id2))

                    versions = cursor.fetchall()
                    if len(versions) != 2:
                        return {'error': 'One or both versions not found'}

                    v1, v2 = versions

                    diff = {
                        'version1': {
                            'version_id': version_id1,
                            'config_key': v1[0],
                            'value': self._deserialize_value(v1[1], v1[2]) if v1[1] else None,
                            'change_type': v1[3],
                            'created_at': v1[4]
                        },
                        'version2': {
                            'version_id': version_id2,
                            'config_key': v2[0],
                            'value': self._deserialize_value(v2[1], v2[2]) if v2[1] else None,
                            'change_type': v2[3],
                            'created_at': v2[4]
                        },
                        'has_changes': v1[1] != v2[1]
                    }

                    return diff

                except Exception as e:
                    self._logger.error(f"Failed to get configuration diff: {e}")
                    return {'error': str(e)}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting configuration diff: {e}")
            return {'error': str(e)}

    def cleanup_old_versions(self, retention_days: int = 90,
                            keep_tagged: bool = True) -> int:
        """
        Clean up old configuration versions.

        Args:
            retention_days: Number of days to retain versions
            keep_tagged: Whether to keep tagged versions

        Returns:
            Number of versions cleaned up
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Calculate cutoff date
                    cutoff_date = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)

                    query = """
                        DELETE FROM config_versions
                        WHERE created_at < datetime(?, 'unixepoch')
                    """
                    params = [cutoff_date]

                    if keep_tagged:
                        query += """
                            AND version_id NOT IN (
                                SELECT version_id FROM config_tags
                                WHERE version_id IS NOT NULL
                            )
                        """

                    cursor.execute(query, params)
                    deleted_count = cursor.rowcount

                    conn.commit()
                    self._logger.info(f"Cleaned up {deleted_count} old configuration versions")
                    return deleted_count

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to cleanup old versions: {e}")
                    raise e
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error cleaning up old versions: {e}")
            return 0

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.debug("Configuration versions database closed")


def create_config_versions_db(db_path: Optional[str] = None) -> ConfigVersionsDB:
    """
    Factory function to create a ConfigVersionsDB instance.

    Args:
        db_path: Optional database path

    Returns:
        ConfigVersionsDB instance
    """
    return ConfigVersionsDB(db_path)
