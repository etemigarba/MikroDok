"""
Module: preset_manager_db
Description: Stores and manages training configuration presets with categorization and template management
Phase: 4
Location: /src/modules/database/training_config_db/preset_manager_db/
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


class PresetCategory(Enum):
    """Preset categories."""
    GENERAL = "general"
    FINE_TUNING = "fine_tuning"
    RESEARCH = "research"
    PRODUCTION = "production"
    EXPERIMENTAL = "experimental"
    CUSTOM = "custom"


class PresetType(Enum):
    """Preset types."""
    SYSTEM = "system"
    USER = "user"
    SHARED = "shared"
    TEMPLATE = "template"


class PresetStatus(Enum):
    """Preset status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PresetManagerDB:
    """
    Database operations for training configuration preset management.
    
    Provides comprehensive preset storage, categorization, template management,
    and sharing capabilities for training configurations.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize preset manager database.
        
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
            self._db_path = db_dir / "preset_manager.db"
        
        # Initialize database
        self._initialize_database()
        self._logger.info(f"PresetManagerDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database schema."""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Enable foreign keys
                    cursor.execute("PRAGMA foreign_keys = ON")
                    
                    # Create configuration presets table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS config_presets (
                            preset_id TEXT PRIMARY KEY,
                            preset_name TEXT NOT NULL UNIQUE,
                            preset_description TEXT,
                            category TEXT NOT NULL DEFAULT 'general',
                            preset_type TEXT NOT NULL DEFAULT 'user',
                            status TEXT NOT NULL DEFAULT 'active',
                            config_data_json TEXT NOT NULL,
                            config_schema_version TEXT DEFAULT '1.0',
                            default_values_json TEXT,
                            validation_rules_json TEXT,
                            tags_json TEXT,
                            metadata_json TEXT,
                            created_by TEXT NOT NULL,
                            updated_by TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_used_at TIMESTAMP,
                            usage_count INTEGER DEFAULT 0,
                            is_public BOOLEAN DEFAULT 0,
                            is_featured BOOLEAN DEFAULT 0,
                            rating_average REAL DEFAULT 0.0,
                            rating_count INTEGER DEFAULT 0,
                            download_count INTEGER DEFAULT 0,
                            source_preset_id TEXT,
                            version_info_json TEXT,
                            
                            CONSTRAINT valid_category CHECK (category IN ('general', 'fine_tuning', 'research', 'production', 'experimental', 'custom')),
                            CONSTRAINT valid_type CHECK (preset_type IN ('system', 'user', 'shared', 'template')),
                            CONSTRAINT valid_status CHECK (status IN ('active', 'deprecated', 'archived')),
                            CONSTRAINT valid_rating CHECK (rating_average >= 0.0 AND rating_average <= 5.0),
                            FOREIGN KEY (source_preset_id) REFERENCES config_presets (preset_id)
                        )
                    """)
                    
                    # Create preset parameters table for detailed parameter management
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS preset_parameters (
                            parameter_id TEXT PRIMARY KEY,
                            preset_id TEXT NOT NULL,
                            parameter_name TEXT NOT NULL,
                            parameter_path TEXT NOT NULL,
                            parameter_type TEXT NOT NULL,
                            default_value TEXT,
                            min_value REAL,
                            max_value REAL,
                            allowed_values_json TEXT,
                            is_required BOOLEAN DEFAULT 1,
                            is_tunable BOOLEAN DEFAULT 1,
                            description TEXT,
                            validation_pattern TEXT,
                            display_order INTEGER DEFAULT 0,
                            group_name TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            CONSTRAINT valid_param_type CHECK (parameter_type IN ('int', 'float', 'string', 'boolean', 'list', 'dict')),
                            CONSTRAINT unique_preset_param UNIQUE (preset_id, parameter_path),
                            FOREIGN KEY (preset_id) REFERENCES config_presets (preset_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create preset usage history table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS preset_usage_history (
                            usage_id TEXT PRIMARY KEY,
                            preset_id TEXT NOT NULL,
                            used_by TEXT NOT NULL,
                            usage_context TEXT,
                            session_id TEXT,
                            customizations_json TEXT,
                            performance_metrics_json TEXT,
                            success BOOLEAN,
                            error_message TEXT,
                            feedback_rating INTEGER,
                            feedback_comment TEXT,
                            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            CONSTRAINT valid_rating CHECK (feedback_rating IS NULL OR (feedback_rating >= 1 AND feedback_rating <= 5)),
                            FOREIGN KEY (preset_id) REFERENCES config_presets (preset_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create preset collections table for grouping presets
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS preset_collections (
                            collection_id TEXT PRIMARY KEY,
                            collection_name TEXT NOT NULL,
                            collection_description TEXT,
                            created_by TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_public BOOLEAN DEFAULT 0,
                            tags_json TEXT,
                            metadata_json TEXT
                        )
                    """)
                    
                    # Create preset collection memberships table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS preset_collection_memberships (
                            membership_id TEXT PRIMARY KEY,
                            collection_id TEXT NOT NULL,
                            preset_id TEXT NOT NULL,
                            added_by TEXT NOT NULL,
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            display_order INTEGER DEFAULT 0,
                            
                            CONSTRAINT unique_collection_preset UNIQUE (collection_id, preset_id),
                            FOREIGN KEY (collection_id) REFERENCES preset_collections (collection_id) ON DELETE CASCADE,
                            FOREIGN KEY (preset_id) REFERENCES config_presets (preset_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create indexes for better performance
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_category ON config_presets (category)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_type ON config_presets (preset_type)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_status ON config_presets (status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_created_at ON config_presets (created_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_usage_count ON config_presets (usage_count)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_rating ON config_presets (rating_average)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_public ON config_presets (is_public)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preset_featured ON config_presets (is_featured)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_preset_id ON preset_parameters (preset_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_name ON preset_parameters (parameter_name)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_preset_id ON preset_usage_history (preset_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_used_at ON preset_usage_history (used_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_public ON preset_collections (is_public)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_membership_collection ON preset_collection_memberships (collection_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_membership_preset ON preset_collection_memberships (preset_id)")
                    
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
    
    def create_preset(self, preset_name: str,
                     config_data: Dict[str, Any],
                     preset_description: Optional[str] = None,
                     category: PresetCategory = PresetCategory.CUSTOM,
                     preset_type: PresetType = PresetType.USER,
                     tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     created_by: str = "system",
                     is_public: bool = False,
                     default_values: Optional[Dict[str, Any]] = None,
                     validation_rules: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new configuration preset.
        
        Args:
            preset_name: Name of the preset
            config_data: Configuration data
            preset_description: Optional description
            category: Preset category
            preset_type: Type of preset
            tags: Optional tags
            metadata: Optional metadata
            created_by: User creating the preset
            is_public: Whether preset is publicly available
            default_values: Default parameter values
            validation_rules: Validation rules for parameters
            
        Returns:
            Preset ID
        """
        preset_id = str(uuid.uuid4())
        
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO config_presets (
                            preset_id, preset_name, preset_description, category, preset_type,
                            config_data_json, default_values_json, validation_rules_json,
                            tags_json, metadata_json, created_by, updated_by, is_public
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        preset_id, preset_name, preset_description, category.value, preset_type.value,
                        json.dumps(config_data),
                        json.dumps(default_values) if default_values else None,
                        json.dumps(validation_rules) if validation_rules else None,
                        json.dumps(tags) if tags else None,
                        json.dumps(metadata) if metadata else None,
                        created_by, created_by, is_public
                    ))
                    
                    conn.commit()
                    self._logger.info(f"Created preset: {preset_name} ({preset_id})")
                    return preset_id
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create preset: {e}")
                    raise
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error creating preset: {e}")
            raise

    def get_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a preset by ID.

        Args:
            preset_id: Preset identifier

        Returns:
            Preset data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT * FROM config_presets
                        WHERE preset_id = ?
                    """, (preset_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert row to dictionary
                    columns = [desc[0] for desc in cursor.description]
                    preset_data = dict(zip(columns, row))

                    # Deserialize JSON fields
                    if preset_data['config_data_json']:
                        preset_data['config_data'] = json.loads(preset_data['config_data_json'])
                    if preset_data['default_values_json']:
                        preset_data['default_values'] = json.loads(preset_data['default_values_json'])
                    if preset_data['validation_rules_json']:
                        preset_data['validation_rules'] = json.loads(preset_data['validation_rules_json'])
                    if preset_data['tags_json']:
                        preset_data['tags'] = json.loads(preset_data['tags_json'])
                    if preset_data['metadata_json']:
                        preset_data['metadata'] = json.loads(preset_data['metadata_json'])
                    if preset_data['version_info_json']:
                        preset_data['version_info'] = json.loads(preset_data['version_info_json'])

                    return preset_data

                except Exception as e:
                    self._logger.error(f"Failed to get preset {preset_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting preset: {e}")
            return None

    def get_preset_by_name(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a preset by name.

        Args:
            preset_name: Preset name

        Returns:
            Preset data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT * FROM config_presets
                        WHERE preset_name = ? AND status = 'active'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (preset_name,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert row to dictionary and deserialize JSON fields
                    columns = [desc[0] for desc in cursor.description]
                    preset_data = dict(zip(columns, row))

                    # Deserialize JSON fields
                    if preset_data['config_data_json']:
                        preset_data['config_data'] = json.loads(preset_data['config_data_json'])
                    if preset_data['tags_json']:
                        preset_data['tags'] = json.loads(preset_data['tags_json'])
                    if preset_data['metadata_json']:
                        preset_data['metadata'] = json.loads(preset_data['metadata_json'])

                    return preset_data

                except Exception as e:
                    self._logger.error(f"Failed to get preset by name {preset_name}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting preset by name: {e}")
            return None

    def list_presets(self,
                    category: Optional[PresetCategory] = None,
                    preset_type: Optional[PresetType] = None,
                    status: PresetStatus = PresetStatus.ACTIVE,
                    is_public: Optional[bool] = None,
                    tags: Optional[List[str]] = None,
                    created_by: Optional[str] = None,
                    limit: int = 100,
                    offset: int = 0,
                    order_by: str = "updated_at",
                    order_desc: bool = True) -> List[Dict[str, Any]]:
        """
        List presets with filtering and pagination.

        Args:
            category: Filter by category
            preset_type: Filter by type
            status: Filter by status
            is_public: Filter by public status
            tags: Filter by tags (any match)
            created_by: Filter by creator
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Field to order by
            order_desc: Whether to order descending

        Returns:
            List of preset data
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Build query with filters
                    where_clauses = []
                    params = []

                    if category:
                        where_clauses.append("category = ?")
                        params.append(category.value)

                    if preset_type:
                        where_clauses.append("preset_type = ?")
                        params.append(preset_type.value)

                    if status:
                        where_clauses.append("status = ?")
                        params.append(status.value)

                    if is_public is not None:
                        where_clauses.append("is_public = ?")
                        params.append(is_public)

                    if created_by:
                        where_clauses.append("created_by = ?")
                        params.append(created_by)

                    if tags:
                        # Check if any of the provided tags match
                        tag_conditions = []
                        for tag in tags:
                            tag_conditions.append("tags_json LIKE ?")
                            params.append(f'%"{tag}"%')
                        where_clauses.append(f"({' OR '.join(tag_conditions)})")

                    where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                    order_direction = "DESC" if order_desc else "ASC"

                    query = f"""
                        SELECT preset_id, preset_name, preset_description, category, preset_type,
                               status, created_by, created_at, updated_at, last_used_at,
                               usage_count, is_public, is_featured, rating_average, rating_count,
                               tags_json
                        FROM config_presets
                        {where_clause}
                        ORDER BY {order_by} {order_direction}
                        LIMIT ? OFFSET ?
                    """

                    params.extend([limit, offset])
                    cursor.execute(query, params)

                    presets = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        preset_data = dict(zip(columns, row))

                        # Deserialize tags
                        if preset_data['tags_json']:
                            preset_data['tags'] = json.loads(preset_data['tags_json'])
                        else:
                            preset_data['tags'] = []

                        del preset_data['tags_json']  # Remove raw JSON field
                        presets.append(preset_data)

                    return presets

                except Exception as e:
                    self._logger.error(f"Failed to list presets: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error listing presets: {e}")
            return []

    def search_presets(self, query: str,
                      category: Optional[PresetCategory] = None,
                      limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search presets by name, description, or tags.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum number of results

        Returns:
            List of matching presets
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    where_clauses = [
                        "(preset_name LIKE ? OR preset_description LIKE ? OR tags_json LIKE ?)",
                        "status = 'active'"
                    ]
                    params = [f"%{query}%", f"%{query}%", f"%{query}%"]

                    if category:
                        where_clauses.append("category = ?")
                        params.append(category.value)

                    where_clause = f"WHERE {' AND '.join(where_clauses)}"
                    params.append(limit)

                    cursor.execute(f"""
                        SELECT preset_id, preset_name, preset_description, category, preset_type,
                               created_by, created_at, updated_at, usage_count, rating_average,
                               is_public, is_featured, tags_json
                        FROM config_presets
                        {where_clause}
                        ORDER BY rating_average DESC, usage_count DESC, updated_at DESC
                        LIMIT ?
                    """, params)

                    presets = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        preset_data = dict(zip(columns, row))

                        # Deserialize tags
                        if preset_data['tags_json']:
                            preset_data['tags'] = json.loads(preset_data['tags_json'])
                        else:
                            preset_data['tags'] = []

                        del preset_data['tags_json']
                        presets.append(preset_data)

                    return presets

                except Exception as e:
                    self._logger.error(f"Failed to search presets: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error searching presets: {e}")
            return []

    def update_preset(self, preset_id: str,
                     updates: Dict[str, Any],
                     updated_by: str = "system") -> bool:
        """
        Update a preset.

        Args:
            preset_id: Preset identifier
            updates: Dictionary of fields to update
            updated_by: User making the update

        Returns:
            True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Build dynamic update query
                    set_clauses = []
                    values = []

                    for field, value in updates.items():
                        if field in ['config_data', 'default_values', 'validation_rules', 'tags', 'metadata', 'version_info']:
                            # JSON fields
                            set_clauses.append(f"{field}_json = ?")
                            values.append(json.dumps(value) if value else None)
                        elif field not in ['preset_id', 'created_at', 'created_by']:
                            # Regular fields (excluding immutable ones)
                            set_clauses.append(f"{field} = ?")
                            values.append(value)

                    if not set_clauses:
                        return True  # No updates to make

                    # Add updated_by and updated_at
                    set_clauses.extend(['updated_by = ?', 'updated_at = CURRENT_TIMESTAMP'])
                    values.extend([updated_by])
                    values.append(preset_id)  # For WHERE clause

                    query = f"""
                        UPDATE config_presets
                        SET {', '.join(set_clauses)}
                        WHERE preset_id = ?
                    """

                    cursor.execute(query, values)

                    if cursor.rowcount == 0:
                        self._logger.warning(f"No preset found with ID: {preset_id}")
                        return False

                    conn.commit()
                    self._logger.info(f"Updated preset: {preset_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update preset {preset_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error updating preset: {e}")
            return False

    def delete_preset(self, preset_id: str, user: str = "system") -> bool:
        """
        Delete a preset.

        Args:
            preset_id: Preset identifier
            user: User performing the deletion

        Returns:
            True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Check if preset exists
                    cursor.execute("SELECT preset_name FROM config_presets WHERE preset_id = ?", (preset_id,))
                    result = cursor.fetchone()
                    if not result:
                        self._logger.warning(f"Preset not found: {preset_id}")
                        return False

                    preset_name = result[0]

                    # Delete preset (cascades to parameters and usage history)
                    cursor.execute("DELETE FROM config_presets WHERE preset_id = ?", (preset_id,))

                    conn.commit()
                    self._logger.info(f"Deleted preset: {preset_name} ({preset_id}) by {user}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to delete preset {preset_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error deleting preset: {e}")
            return False

    def record_usage(self, preset_id: str,
                    used_by: str = "system",
                    usage_context: Optional[str] = None,
                    session_id: Optional[str] = None,
                    customizations: Optional[Dict[str, Any]] = None,
                    performance_metrics: Optional[Dict[str, Any]] = None,
                    success: Optional[bool] = None,
                    error_message: Optional[str] = None,
                    feedback_rating: Optional[int] = None,
                    feedback_comment: Optional[str] = None) -> str:
        """
        Record preset usage.

        Args:
            preset_id: Preset identifier
            used_by: User using the preset
            usage_context: Context of usage
            session_id: Optional session ID
            customizations: Any customizations made
            performance_metrics: Performance metrics
            success: Whether usage was successful
            error_message: Error message if unsuccessful
            feedback_rating: User rating (1-5)
            feedback_comment: User feedback comment

        Returns:
            Usage record ID
        """
        usage_id = str(uuid.uuid4())

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Record usage
                    cursor.execute("""
                        INSERT INTO preset_usage_history (
                            usage_id, preset_id, used_by, usage_context, session_id,
                            customizations_json, performance_metrics_json, success,
                            error_message, feedback_rating, feedback_comment
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        usage_id, preset_id, used_by, usage_context, session_id,
                        json.dumps(customizations) if customizations else None,
                        json.dumps(performance_metrics) if performance_metrics else None,
                        success, error_message, feedback_rating, feedback_comment
                    ))

                    # Update usage count and last used timestamp
                    cursor.execute("""
                        UPDATE config_presets
                        SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP
                        WHERE preset_id = ?
                    """, (preset_id,))

                    # Update rating if feedback provided
                    if feedback_rating is not None:
                        cursor.execute("""
                            UPDATE config_presets
                            SET rating_average = (
                                SELECT AVG(CAST(feedback_rating AS REAL))
                                FROM preset_usage_history
                                WHERE preset_id = ? AND feedback_rating IS NOT NULL
                            ),
                            rating_count = (
                                SELECT COUNT(*)
                                FROM preset_usage_history
                                WHERE preset_id = ? AND feedback_rating IS NOT NULL
                            )
                            WHERE preset_id = ?
                        """, (preset_id, preset_id, preset_id))

                    conn.commit()
                    self._logger.debug(f"Recorded usage for preset {preset_id}")
                    return usage_id

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to record usage for {preset_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error recording usage: {e}")
            raise

    def get_featured_presets(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get featured presets.

        Args:
            limit: Maximum number of presets to return

        Returns:
            List of featured presets
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT preset_id, preset_name, preset_description, category,
                               rating_average, rating_count, usage_count, created_by,
                               tags_json
                        FROM config_presets
                        WHERE is_featured = 1 AND status = 'active'
                        ORDER BY rating_average DESC, usage_count DESC
                        LIMIT ?
                    """, (limit,))

                    presets = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        preset_data = dict(zip(columns, row))

                        # Deserialize tags
                        if preset_data['tags_json']:
                            preset_data['tags'] = json.loads(preset_data['tags_json'])
                        else:
                            preset_data['tags'] = []

                        del preset_data['tags_json']
                        presets.append(preset_data)

                    return presets

                except Exception as e:
                    self._logger.error(f"Failed to get featured presets: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting featured presets: {e}")
            return []

    def get_popular_presets(self, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get popular presets based on recent usage.

        Args:
            limit: Maximum number of presets to return
            days: Number of days to consider for popularity

        Returns:
            List of popular presets
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT cp.preset_id, cp.preset_name, cp.preset_description, cp.category,
                               cp.rating_average, cp.rating_count, cp.usage_count,
                               COUNT(puh.usage_id) as recent_usage_count,
                               cp.tags_json
                        FROM config_presets cp
                        LEFT JOIN preset_usage_history puh ON cp.preset_id = puh.preset_id
                            AND puh.used_at >= datetime('now', '-{} days')
                        WHERE cp.status = 'active'
                        GROUP BY cp.preset_id
                        ORDER BY recent_usage_count DESC, cp.rating_average DESC
                        LIMIT ?
                    """.format(days), (limit,))

                    presets = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        preset_data = dict(zip(columns, row))

                        # Deserialize tags
                        if preset_data['tags_json']:
                            preset_data['tags'] = json.loads(preset_data['tags_json'])
                        else:
                            preset_data['tags'] = []

                        del preset_data['tags_json']
                        presets.append(preset_data)

                    return presets

                except Exception as e:
                    self._logger.error(f"Failed to get popular presets: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting popular presets: {e}")
            return []

    def get_preset_statistics(self) -> Dict[str, Any]:
        """
        Get preset repository statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    stats = {}

                    # Total presets
                    cursor.execute("SELECT COUNT(*) FROM config_presets WHERE status = 'active'")
                    stats['total_presets'] = cursor.fetchone()[0]

                    # Presets by category
                    cursor.execute("""
                        SELECT category, COUNT(*)
                        FROM config_presets
                        WHERE status = 'active'
                        GROUP BY category
                    """)
                    stats['by_category'] = dict(cursor.fetchall())

                    # Presets by type
                    cursor.execute("""
                        SELECT preset_type, COUNT(*)
                        FROM config_presets
                        WHERE status = 'active'
                        GROUP BY preset_type
                    """)
                    stats['by_type'] = dict(cursor.fetchall())

                    # Public presets
                    cursor.execute("SELECT COUNT(*) FROM config_presets WHERE is_public = 1 AND status = 'active'")
                    stats['public_presets'] = cursor.fetchone()[0]

                    # Featured presets
                    cursor.execute("SELECT COUNT(*) FROM config_presets WHERE is_featured = 1 AND status = 'active'")
                    stats['featured_presets'] = cursor.fetchone()[0]

                    # Most used presets
                    cursor.execute("""
                        SELECT preset_name, usage_count
                        FROM config_presets
                        WHERE status = 'active'
                        ORDER BY usage_count DESC
                        LIMIT 10
                    """)
                    stats['most_used'] = [{'name': row[0], 'usage_count': row[1]} for row in cursor.fetchall()]

                    # Highest rated presets
                    cursor.execute("""
                        SELECT preset_name, rating_average, rating_count
                        FROM config_presets
                        WHERE status = 'active' AND rating_count > 0
                        ORDER BY rating_average DESC, rating_count DESC
                        LIMIT 10
                    """)
                    stats['highest_rated'] = [
                        {'name': row[0], 'rating': row[1], 'rating_count': row[2]}
                        for row in cursor.fetchall()
                    ]

                    # Recent activity
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM preset_usage_history
                        WHERE used_at >= datetime('now', '-7 days')
                    """)
                    stats['usage_last_week'] = cursor.fetchone()[0]

                    return stats

                except Exception as e:
                    self._logger.error(f"Failed to get preset statistics: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting preset statistics: {e}")
            return {}

    def cleanup_old_usage_records(self, days_to_keep: int = 90) -> int:
        """
        Clean up old usage records.

        Args:
            days_to_keep: Number of days of records to keep

        Returns:
            Number of records deleted
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        DELETE FROM preset_usage_history
                        WHERE used_at < datetime('now', '-{} days')
                    """.format(days_to_keep))

                    deleted_count = cursor.rowcount
                    conn.commit()

                    self._logger.info(f"Cleaned up {deleted_count} old usage records")
                    return deleted_count

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to cleanup usage records: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error cleaning up usage records: {e}")
            return 0

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            # No persistent connections to close in this implementation
            self._logger.info("PresetManagerDB closed successfully")
        except Exception as e:
            self._logger.error(f"Error closing PresetManagerDB: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
