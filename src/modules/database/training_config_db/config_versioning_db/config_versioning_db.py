"""
Module: config_versioning_db
Description: Manages configuration version history with tracking, comparison, rollback capabilities, and change auditing
Phase: 4
Location: /src/modules/database/training_config_db/config_versioning_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ChangeType(Enum):
    """Types of configuration changes."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    MERGE = "merge"


class VersionStatus(Enum):
    """Version status."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ConfigVersioningDB:
    """
    Database operations for training configuration version management.
    
    Provides comprehensive version tracking, comparison, rollback capabilities,
    and change auditing for training configurations.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize configuration versioning database.
        
        Args:
            db_path: Optional custom database path
        """
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Set database path
        if db_path:
            self._db_path = db_path
        else:
            db_dir = Path("data/database/training_config")
            db_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = db_dir / "config_versioning.db"
        
        # Initialize database
        self._initialize_database()
        self._logger.info(f"ConfigVersioningDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database schema."""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Enable foreign keys
                    cursor.execute("PRAGMA foreign_keys = ON")
                    
                    # Create configuration versions table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS config_versions (
                            version_id TEXT PRIMARY KEY,
                            config_id TEXT NOT NULL,
                            version_number INTEGER NOT NULL,
                            version_tag TEXT,
                            parent_version_id TEXT,
                            change_type TEXT NOT NULL,
                            change_summary TEXT,
                            change_description TEXT,
                            config_data_json TEXT NOT NULL,
                            config_hash TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            created_by TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_major_version BOOLEAN DEFAULT 0,
                            is_rollback BOOLEAN DEFAULT 0,
                            rollback_from_version TEXT,
                            metadata_json TEXT,
                            
                            CONSTRAINT valid_change_type CHECK (change_type IN ('create', 'update', 'delete', 'restore', 'merge')),
                            CONSTRAINT valid_status CHECK (status IN ('active', 'archived', 'deprecated')),
                            CONSTRAINT unique_config_version UNIQUE (config_id, version_number),
                            FOREIGN KEY (parent_version_id) REFERENCES config_versions (version_id),
                            FOREIGN KEY (rollback_from_version) REFERENCES config_versions (version_id)
                        )
                    """)
                    
                    # Create version changes table for detailed change tracking
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS version_changes (
                            change_id TEXT PRIMARY KEY,
                            version_id TEXT NOT NULL,
                            field_path TEXT NOT NULL,
                            change_operation TEXT NOT NULL,
                            old_value TEXT,
                            new_value TEXT,
                            value_type TEXT,
                            change_impact TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            CONSTRAINT valid_operation CHECK (change_operation IN ('add', 'modify', 'remove', 'move')),
                            FOREIGN KEY (version_id) REFERENCES config_versions (version_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create version relationships table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS version_relationships (
                            relationship_id TEXT PRIMARY KEY,
                            source_version_id TEXT NOT NULL,
                            target_version_id TEXT NOT NULL,
                            relationship_type TEXT NOT NULL,
                            relationship_metadata TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            CONSTRAINT valid_relationship CHECK (relationship_type IN ('parent', 'child', 'branch', 'merge', 'fork')),
                            FOREIGN KEY (source_version_id) REFERENCES config_versions (version_id) ON DELETE CASCADE,
                            FOREIGN KEY (target_version_id) REFERENCES config_versions (version_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create version tags table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS version_tags (
                            tag_id TEXT PRIMARY KEY,
                            version_id TEXT NOT NULL,
                            tag_name TEXT NOT NULL,
                            tag_description TEXT,
                            tag_type TEXT DEFAULT 'user',
                            created_by TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            CONSTRAINT valid_tag_type CHECK (tag_type IN ('user', 'system', 'release', 'milestone')),
                            CONSTRAINT unique_version_tag UNIQUE (version_id, tag_name),
                            FOREIGN KEY (version_id) REFERENCES config_versions (version_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create indexes for better performance
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_version_config_id ON config_versions (config_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_version_number ON config_versions (config_id, version_number)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_version_created_at ON config_versions (created_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_version_hash ON config_versions (config_hash)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_version_status ON config_versions (status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_change_version_id ON version_changes (version_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_change_field_path ON version_changes (field_path)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationship_source ON version_relationships (source_version_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationship_target ON version_relationships (target_version_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_version_id ON version_tags (version_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_name ON version_tags (tag_name)")
                    
                    conn.commit()
                    self._logger.debug("Database schema initialized successfully")
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to initialize database schema: {e}")
                    raise
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error initializing database: {e}")
            raise
    
    def create_version(self, config_id: str, 
                      config_data: Dict[str, Any],
                      change_type: ChangeType = ChangeType.CREATE,
                      change_summary: Optional[str] = None,
                      change_description: Optional[str] = None,
                      version_tag: Optional[str] = None,
                      parent_version_id: Optional[str] = None,
                      created_by: str = "system",
                      is_major_version: bool = False,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new configuration version.
        
        Args:
            config_id: Configuration identifier
            config_data: Configuration data
            change_type: Type of change
            change_summary: Brief summary of changes
            change_description: Detailed description of changes
            version_tag: Optional version tag
            parent_version_id: Parent version identifier
            created_by: User creating the version
            is_major_version: Whether this is a major version
            metadata: Optional metadata
            
        Returns:
            Version ID
        """
        version_id = str(uuid.uuid4())
        
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Get next version number
                    cursor.execute("""
                        SELECT COALESCE(MAX(version_number), 0) + 1 
                        FROM config_versions 
                        WHERE config_id = ?
                    """, (config_id,))
                    version_number = cursor.fetchone()[0]
                    
                    # Calculate configuration hash
                    config_json = json.dumps(config_data, sort_keys=True)
                    config_hash = str(hash(config_json))
                    
                    # Check for duplicate configuration
                    cursor.execute("""
                        SELECT version_id FROM config_versions 
                        WHERE config_id = ? AND config_hash = ?
                    """, (config_id, config_hash))
                    
                    existing_version = cursor.fetchone()
                    if existing_version and change_type != ChangeType.CREATE:
                        self._logger.warning(f"Configuration unchanged, skipping version creation")
                        return existing_version[0]
                    
                    # Create version record
                    cursor.execute("""
                        INSERT INTO config_versions (
                            version_id, config_id, version_number, version_tag,
                            parent_version_id, change_type, change_summary, change_description,
                            config_data_json, config_hash, created_by, is_major_version,
                            metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        version_id, config_id, version_number, version_tag,
                        parent_version_id, change_type.value, change_summary, change_description,
                        config_json, config_hash, created_by, is_major_version,
                        json.dumps(metadata) if metadata else None
                    ))
                    
                    conn.commit()
                    self._logger.info(f"Created version {version_number} for config {config_id}")
                    return version_id
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create version: {e}")
                    raise
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error creating version: {e}")
            raise

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific configuration version.

        Args:
            version_id: Version identifier

        Returns:
            Version data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT * FROM config_versions
                        WHERE version_id = ?
                    """, (version_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert row to dictionary
                    columns = [desc[0] for desc in cursor.description]
                    version_data = dict(zip(columns, row))

                    # Deserialize JSON fields
                    if version_data['config_data_json']:
                        version_data['config_data'] = json.loads(version_data['config_data_json'])
                    if version_data['metadata_json']:
                        version_data['metadata'] = json.loads(version_data['metadata_json'])

                    return version_data

                except Exception as e:
                    self._logger.error(f"Failed to get version {version_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting version: {e}")
            return None

    def get_version_history(self, config_id: str,
                          limit: int = 100,
                          include_archived: bool = False) -> List[Dict[str, Any]]:
        """
        Get version history for a configuration.

        Args:
            config_id: Configuration identifier
            limit: Maximum number of versions to return
            include_archived: Whether to include archived versions

        Returns:
            List of version records
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    where_clause = "WHERE config_id = ?"
                    params = [config_id]

                    if not include_archived:
                        where_clause += " AND status != 'archived'"

                    cursor.execute(f"""
                        SELECT version_id, version_number, version_tag, change_type,
                               change_summary, change_description, created_by, created_at,
                               is_major_version, is_rollback, status
                        FROM config_versions
                        {where_clause}
                        ORDER BY version_number DESC
                        LIMIT ?
                    """, params + [limit])

                    versions = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        version_data = dict(zip(columns, row))
                        versions.append(version_data)

                    return versions

                except Exception as e:
                    self._logger.error(f"Failed to get version history for {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting version history: {e}")
            return []

    def compare_versions(self, version_id_1: str, version_id_2: str) -> Dict[str, Any]:
        """
        Compare two configuration versions.

        Args:
            version_id_1: First version identifier
            version_id_2: Second version identifier

        Returns:
            Comparison result with differences
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get both versions
                    cursor.execute("""
                        SELECT version_id, version_number, config_data_json, created_at, created_by
                        FROM config_versions
                        WHERE version_id IN (?, ?)
                    """, (version_id_1, version_id_2))

                    rows = cursor.fetchall()
                    if len(rows) != 2:
                        raise ValueError("One or both versions not found")

                    # Parse version data
                    versions = {}
                    for row in rows:
                        version_id, version_number, config_data_json, created_at, created_by = row
                        versions[version_id] = {
                            'version_number': version_number,
                            'config_data': json.loads(config_data_json),
                            'created_at': created_at,
                            'created_by': created_by
                        }

                    # Compare configurations
                    config_1 = versions[version_id_1]['config_data']
                    config_2 = versions[version_id_2]['config_data']

                    differences = self._calculate_differences(config_1, config_2)

                    comparison_result = {
                        'version_1': {
                            'version_id': version_id_1,
                            'version_number': versions[version_id_1]['version_number'],
                            'created_at': versions[version_id_1]['created_at'],
                            'created_by': versions[version_id_1]['created_by']
                        },
                        'version_2': {
                            'version_id': version_id_2,
                            'version_number': versions[version_id_2]['version_number'],
                            'created_at': versions[version_id_2]['created_at'],
                            'created_by': versions[version_id_2]['created_by']
                        },
                        'differences': differences,
                        'has_differences': len(differences) > 0,
                        'compared_at': datetime.now(timezone.utc).isoformat()
                    }

                    return comparison_result

                except Exception as e:
                    self._logger.error(f"Failed to compare versions {version_id_1} and {version_id_2}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error comparing versions: {e}")
            return {}

    def _calculate_differences(self, config_1: Dict[str, Any], config_2: Dict[str, Any],
                             path: str = "") -> List[Dict[str, Any]]:
        """
        Calculate differences between two configurations.

        Args:
            config_1: First configuration
            config_2: Second configuration
            path: Current path in the configuration tree

        Returns:
            List of differences
        """
        differences = []

        # Get all keys from both configurations
        all_keys = set(config_1.keys()) | set(config_2.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            if key not in config_1:
                # Key added in config_2
                differences.append({
                    'path': current_path,
                    'operation': 'add',
                    'old_value': None,
                    'new_value': config_2[key],
                    'value_type': type(config_2[key]).__name__
                })
            elif key not in config_2:
                # Key removed in config_2
                differences.append({
                    'path': current_path,
                    'operation': 'remove',
                    'old_value': config_1[key],
                    'new_value': None,
                    'value_type': type(config_1[key]).__name__
                })
            elif config_1[key] != config_2[key]:
                # Key modified
                if isinstance(config_1[key], dict) and isinstance(config_2[key], dict):
                    # Recursively compare nested dictionaries
                    nested_diffs = self._calculate_differences(config_1[key], config_2[key], current_path)
                    differences.extend(nested_diffs)
                else:
                    differences.append({
                        'path': current_path,
                        'operation': 'modify',
                        'old_value': config_1[key],
                        'new_value': config_2[key],
                        'value_type': type(config_2[key]).__name__
                    })

        return differences

    def rollback_to_version(self, config_id: str, target_version_id: str,
                          created_by: str = "system",
                          rollback_reason: Optional[str] = None) -> str:
        """
        Rollback configuration to a previous version.

        Args:
            config_id: Configuration identifier
            target_version_id: Version to rollback to
            created_by: User performing the rollback
            rollback_reason: Reason for rollback

        Returns:
            New version ID created for the rollback
        """
        try:
            # Get target version data
            target_version = self.get_version(target_version_id)
            if not target_version:
                raise ValueError(f"Target version {target_version_id} not found")

            if target_version['config_id'] != config_id:
                raise ValueError("Target version does not belong to the specified configuration")

            # Create new version with rollback data
            rollback_metadata = {
                'rollback_target': target_version_id,
                'rollback_reason': rollback_reason,
                'rollback_timestamp': datetime.now(timezone.utc).isoformat()
            }

            new_version_id = self.create_version(
                config_id=config_id,
                config_data=target_version['config_data'],
                change_type=ChangeType.RESTORE,
                change_summary=f"Rollback to version {target_version['version_number']}",
                change_description=rollback_reason or f"Restored configuration from version {target_version['version_number']}",
                created_by=created_by,
                metadata=rollback_metadata
            )

            # Update the new version to mark it as a rollback
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE config_versions
                        SET is_rollback = 1, rollback_from_version = ?
                        WHERE version_id = ?
                    """, (target_version_id, new_version_id))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise
                finally:
                    conn.close()

            self._logger.info(f"Rolled back config {config_id} to version {target_version['version_number']}")
            return new_version_id

        except Exception as e:
            self._logger.error(f"Error rolling back to version: {e}")
            raise

    def add_version_tag(self, version_id: str, tag_name: str,
                       tag_description: Optional[str] = None,
                       tag_type: str = "user",
                       created_by: str = "system") -> str:
        """
        Add a tag to a version.

        Args:
            version_id: Version identifier
            tag_name: Tag name
            tag_description: Optional tag description
            tag_type: Type of tag (user, system, release, milestone)
            created_by: User creating the tag

        Returns:
            Tag ID
        """
        tag_id = str(uuid.uuid4())

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        INSERT INTO version_tags (
                            tag_id, version_id, tag_name, tag_description,
                            tag_type, created_by
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (tag_id, version_id, tag_name, tag_description, tag_type, created_by))

                    conn.commit()
                    self._logger.info(f"Added tag '{tag_name}' to version {version_id}")
                    return tag_id

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to add tag to version {version_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error adding version tag: {e}")
            raise

    def get_version_by_tag(self, config_id: str, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get version by tag name.

        Args:
            config_id: Configuration identifier
            tag_name: Tag name to search for

        Returns:
            Version data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT cv.* FROM config_versions cv
                        JOIN version_tags vt ON cv.version_id = vt.version_id
                        WHERE cv.config_id = ? AND vt.tag_name = ?
                        ORDER BY cv.version_number DESC
                        LIMIT 1
                    """, (config_id, tag_name))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert row to dictionary
                    columns = [desc[0] for desc in cursor.description]
                    version_data = dict(zip(columns, row))

                    # Deserialize JSON fields
                    if version_data['config_data_json']:
                        version_data['config_data'] = json.loads(version_data['config_data_json'])
                    if version_data['metadata_json']:
                        version_data['metadata'] = json.loads(version_data['metadata_json'])

                    return version_data

                except Exception as e:
                    self._logger.error(f"Failed to get version by tag {tag_name}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting version by tag: {e}")
            return None

    def get_latest_version(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest version of a configuration.

        Args:
            config_id: Configuration identifier

        Returns:
            Latest version data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT * FROM config_versions
                        WHERE config_id = ? AND status = 'active'
                        ORDER BY version_number DESC
                        LIMIT 1
                    """, (config_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert row to dictionary
                    columns = [desc[0] for desc in cursor.description]
                    version_data = dict(zip(columns, row))

                    # Deserialize JSON fields
                    if version_data['config_data_json']:
                        version_data['config_data'] = json.loads(version_data['config_data_json'])
                    if version_data['metadata_json']:
                        version_data['metadata'] = json.loads(version_data['metadata_json'])

                    return version_data

                except Exception as e:
                    self._logger.error(f"Failed to get latest version for {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting latest version: {e}")
            return None

    def archive_version(self, version_id: str, user: str = "system") -> bool:
        """
        Archive a configuration version.

        Args:
            version_id: Version identifier
            user: User performing the archive

        Returns:
            True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE config_versions
                        SET status = 'archived'
                        WHERE version_id = ?
                    """, (version_id,))

                    if cursor.rowcount == 0:
                        self._logger.warning(f"Version not found: {version_id}")
                        return False

                    conn.commit()
                    self._logger.info(f"Archived version {version_id} by {user}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to archive version {version_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error archiving version: {e}")
            return False

    def get_version_statistics(self, config_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get version statistics.

        Args:
            config_id: Optional configuration ID to filter by

        Returns:
            Dictionary with statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    stats = {}

                    # Base query conditions
                    where_clause = ""
                    params = []
                    if config_id:
                        where_clause = "WHERE config_id = ?"
                        params = [config_id]

                    # Total versions
                    cursor.execute(f"SELECT COUNT(*) FROM config_versions {where_clause}", params)
                    stats['total_versions'] = cursor.fetchone()[0]

                    # Versions by change type
                    cursor.execute(f"""
                        SELECT change_type, COUNT(*)
                        FROM config_versions {where_clause}
                        GROUP BY change_type
                    """, params)
                    stats['by_change_type'] = dict(cursor.fetchall())

                    # Versions by status
                    cursor.execute(f"""
                        SELECT status, COUNT(*)
                        FROM config_versions {where_clause}
                        GROUP BY status
                    """, params)
                    stats['by_status'] = dict(cursor.fetchall())

                    # Major versions
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM config_versions
                        {where_clause} {'AND' if where_clause else 'WHERE'} is_major_version = 1
                    """, params)
                    stats['major_versions'] = cursor.fetchone()[0]

                    # Rollback versions
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM config_versions
                        {where_clause} {'AND' if where_clause else 'WHERE'} is_rollback = 1
                    """, params)
                    stats['rollback_versions'] = cursor.fetchone()[0]

                    # Recent activity (last 7 days)
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM config_versions
                        {where_clause} {'AND' if where_clause else 'WHERE'} created_at >= datetime('now', '-7 days')
                    """, params)
                    stats['recent_versions'] = cursor.fetchone()[0]

                    # Most active configurations (if not filtering by config_id)
                    if not config_id:
                        cursor.execute("""
                            SELECT config_id, COUNT(*) as version_count
                            FROM config_versions
                            GROUP BY config_id
                            ORDER BY version_count DESC
                            LIMIT 10
                        """)
                        stats['most_active_configs'] = [
                            {'config_id': row[0], 'version_count': row[1]}
                            for row in cursor.fetchall()
                        ]

                    return stats

                except Exception as e:
                    self._logger.error(f"Failed to get version statistics: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting version statistics: {e}")
            return {}

    def cleanup_old_versions(self, config_id: str, keep_count: int = 50) -> int:
        """
        Clean up old versions, keeping only the most recent ones.

        Args:
            config_id: Configuration identifier
            keep_count: Number of versions to keep

        Returns:
            Number of versions deleted
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get versions to delete (excluding major versions and tagged versions)
                    cursor.execute("""
                        SELECT version_id FROM config_versions cv
                        WHERE cv.config_id = ?
                        AND cv.is_major_version = 0
                        AND cv.version_id NOT IN (
                            SELECT DISTINCT vt.version_id FROM version_tags vt
                        )
                        ORDER BY cv.version_number DESC
                        LIMIT -1 OFFSET ?
                    """, (config_id, keep_count))

                    versions_to_delete = [row[0] for row in cursor.fetchall()]

                    if not versions_to_delete:
                        return 0

                    # Delete old versions
                    placeholders = ','.join(['?' for _ in versions_to_delete])
                    cursor.execute(f"""
                        DELETE FROM config_versions
                        WHERE version_id IN ({placeholders})
                    """, versions_to_delete)

                    deleted_count = cursor.rowcount
                    conn.commit()

                    self._logger.info(f"Cleaned up {deleted_count} old versions for config {config_id}")
                    return deleted_count

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to cleanup versions for {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error cleaning up versions: {e}")
            return 0

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            # No persistent connections to close in this implementation
            self._logger.info("ConfigVersioningDB closed successfully")
        except Exception as e:
            self._logger.error(f"Error closing ConfigVersioningDB: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
