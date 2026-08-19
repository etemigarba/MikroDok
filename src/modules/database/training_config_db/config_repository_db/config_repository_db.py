"""
Module: config_repository_db
Description: CRUD operations for training configuration storage with comprehensive metadata management
Phase: 4
Location: /src/modules/database/training_config_db/config_repository_db/
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
from src.modules.logic.training_orchestration_lg.base_interfaces import TrainingConfig


class ConfigStatus(Enum):
    """Training configuration status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ConfigCategory(Enum):
    """Training configuration categories."""
    GENERAL = "general"
    FINE_TUNING = "fine_tuning"
    RESEARCH = "research"
    PRODUCTION = "production"
    EXPERIMENTAL = "experimental"


class ConfigRepositoryDB:
    """
    Database operations for training configuration storage and management.
    
    Provides comprehensive CRUD operations for training configurations with
    metadata management, categorization, and search capabilities.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize configuration repository database.
        
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
            self._db_path = db_dir / "config_repository.db"
        
        # Initialize database
        self._initialize_database()
        self._logger.info(f"ConfigRepositoryDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database schema."""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Enable foreign keys
                    cursor.execute("PRAGMA foreign_keys = ON")
                    
                    # Create training configurations table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS training_configurations (
                            config_id TEXT PRIMARY KEY,
                            config_name TEXT NOT NULL,
                            config_description TEXT,
                            category TEXT NOT NULL DEFAULT 'general',
                            status TEXT NOT NULL DEFAULT 'draft',
                            model_name TEXT NOT NULL,
                            dataset_path TEXT NOT NULL,
                            output_dir TEXT NOT NULL,
                            max_epochs INTEGER NOT NULL DEFAULT 100,
                            early_stopping_patience INTEGER DEFAULT 10,
                            checkpoint_interval INTEGER DEFAULT 1000,
                            validation_split REAL DEFAULT 0.2,
                            save_best_only BOOLEAN DEFAULT 1,
                            enable_mixed_precision BOOLEAN DEFAULT 0,
                            gradient_accumulation_steps INTEGER DEFAULT 1,
                            max_grad_norm REAL DEFAULT 1.0,
                            warmup_steps INTEGER DEFAULT 0,
                            logging_steps INTEGER DEFAULT 100,
                            evaluation_strategy TEXT DEFAULT 'epoch',
                            save_strategy TEXT DEFAULT 'epoch',
                            load_best_model_at_end BOOLEAN DEFAULT 1,
                            metric_for_best_model TEXT DEFAULT 'eval_loss',
                            greater_is_better BOOLEAN DEFAULT 0,
                            hyperparameters_json TEXT,
                            custom_config_json TEXT,
                            tags_json TEXT,
                            metadata_json TEXT,
                            created_by TEXT DEFAULT 'system',
                            updated_by TEXT DEFAULT 'system',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_used_at TIMESTAMP,
                            usage_count INTEGER DEFAULT 0,
                            is_template BOOLEAN DEFAULT 0,
                            template_source TEXT,
                            validation_errors_json TEXT,
                            
                            CONSTRAINT valid_category CHECK (category IN ('general', 'fine_tuning', 'research', 'production', 'experimental')),
                            CONSTRAINT valid_status CHECK (status IN ('draft', 'active', 'archived', 'deprecated')),
                            CONSTRAINT valid_validation_split CHECK (validation_split >= 0.0 AND validation_split <= 1.0),
                            CONSTRAINT valid_max_grad_norm CHECK (max_grad_norm > 0.0)
                        )
                    """)
                    
                    # Create configuration dependencies table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS config_dependencies (
                            dependency_id TEXT PRIMARY KEY,
                            config_id TEXT NOT NULL,
                            dependency_type TEXT NOT NULL,
                            dependency_name TEXT NOT NULL,
                            dependency_version TEXT,
                            is_required BOOLEAN DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            FOREIGN KEY (config_id) REFERENCES training_configurations (config_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create configuration usage history table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS config_usage_history (
                            usage_id TEXT PRIMARY KEY,
                            config_id TEXT NOT NULL,
                            session_id TEXT,
                            used_by TEXT NOT NULL,
                            usage_type TEXT NOT NULL DEFAULT 'training',
                            usage_context TEXT,
                            performance_metrics_json TEXT,
                            success BOOLEAN,
                            error_message TEXT,
                            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            
                            FOREIGN KEY (config_id) REFERENCES training_configurations (config_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create indexes for better performance
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_category ON training_configurations (category)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_status ON training_configurations (status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_created_at ON training_configurations (created_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_updated_at ON training_configurations (updated_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_usage_count ON training_configurations (usage_count)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_is_template ON training_configurations (is_template)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependency_config_id ON config_dependencies (config_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_config_id ON config_usage_history (config_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_used_at ON config_usage_history (used_at)")
                    
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
    
    def store_configuration(self, config: TrainingConfig, 
                          config_name: str,
                          config_description: Optional[str] = None,
                          category: ConfigCategory = ConfigCategory.GENERAL,
                          status: ConfigStatus = ConfigStatus.DRAFT,
                          tags: Optional[List[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None,
                          user: str = "system",
                          is_template: bool = False,
                          template_source: Optional[str] = None) -> str:
        """
        Store a training configuration.
        
        Args:
            config: Training configuration object
            config_name: Name for the configuration
            config_description: Optional description
            category: Configuration category
            status: Configuration status
            tags: Optional tags for categorization
            metadata: Optional metadata
            user: User storing the configuration
            is_template: Whether this is a template configuration
            template_source: Source of template if applicable
            
        Returns:
            Configuration ID
        """
        config_id = str(uuid.uuid4())
        
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Serialize complex data
                    hyperparameters_json = json.dumps({
                        name: {
                            'value': hp.value,
                            'param_type': hp.param_type.value,
                            'min_value': hp.min_value,
                            'max_value': hp.max_value,
                            'step_size': hp.step_size,
                            'choices': hp.choices,
                            'is_tunable': hp.is_tunable,
                            'description': hp.description
                        }
                        for name, hp in config.hyperparameters.items()
                    })
                    
                    cursor.execute("""
                        INSERT INTO training_configurations (
                            config_id, config_name, config_description, category, status,
                            model_name, dataset_path, output_dir, max_epochs,
                            early_stopping_patience, checkpoint_interval, validation_split,
                            save_best_only, enable_mixed_precision, gradient_accumulation_steps,
                            max_grad_norm, warmup_steps, logging_steps, evaluation_strategy,
                            save_strategy, load_best_model_at_end, metric_for_best_model,
                            greater_is_better, hyperparameters_json, custom_config_json,
                            tags_json, metadata_json, created_by, updated_by,
                            is_template, template_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        config_id, config_name, config_description, category.value, status.value,
                        config.model_name, str(config.dataset_path), str(config.output_dir),
                        config.max_epochs, config.early_stopping_patience, config.checkpoint_interval,
                        config.validation_split, config.save_best_only, config.enable_mixed_precision,
                        config.gradient_accumulation_steps, config.max_grad_norm, config.warmup_steps,
                        config.logging_steps, config.evaluation_strategy, config.save_strategy,
                        config.load_best_model_at_end, config.metric_for_best_model,
                        config.greater_is_better, hyperparameters_json,
                        json.dumps(config.custom_config) if config.custom_config else None,
                        json.dumps(tags) if tags else None,
                        json.dumps(metadata) if metadata else None,
                        user, user, is_template, template_source
                    ))
                    
                    conn.commit()
                    self._logger.info(f"Stored training configuration: {config_name} ({config_id})")
                    return config_id
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to store configuration: {e}")
                    raise
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Error storing configuration: {e}")
            raise

    def get_configuration(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a training configuration by ID.

        Args:
            config_id: Configuration identifier

        Returns:
            Configuration data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT * FROM training_configurations
                        WHERE config_id = ?
                    """, (config_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert row to dictionary
                    columns = [desc[0] for desc in cursor.description]
                    config_data = dict(zip(columns, row))

                    # Deserialize JSON fields
                    if config_data['hyperparameters_json']:
                        config_data['hyperparameters'] = json.loads(config_data['hyperparameters_json'])
                    if config_data['custom_config_json']:
                        config_data['custom_config'] = json.loads(config_data['custom_config_json'])
                    if config_data['tags_json']:
                        config_data['tags'] = json.loads(config_data['tags_json'])
                    if config_data['metadata_json']:
                        config_data['metadata'] = json.loads(config_data['metadata_json'])
                    if config_data['validation_errors_json']:
                        config_data['validation_errors'] = json.loads(config_data['validation_errors_json'])

                    return config_data

                except Exception as e:
                    self._logger.error(f"Failed to get configuration {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting configuration: {e}")
            return None

    def update_configuration(self, config_id: str,
                           updates: Dict[str, Any],
                           user: str = "system") -> bool:
        """
        Update a training configuration.

        Args:
            config_id: Configuration identifier
            updates: Dictionary of fields to update
            user: User making the update

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
                        if field in ['hyperparameters', 'custom_config', 'tags', 'metadata', 'validation_errors']:
                            # JSON fields
                            set_clauses.append(f"{field}_json = ?")
                            values.append(json.dumps(value) if value else None)
                        elif field not in ['config_id', 'created_at', 'created_by']:
                            # Regular fields (excluding immutable ones)
                            set_clauses.append(f"{field} = ?")
                            values.append(value)

                    if not set_clauses:
                        return True  # No updates to make

                    # Add updated_by and updated_at
                    set_clauses.extend(['updated_by = ?', 'updated_at = CURRENT_TIMESTAMP'])
                    values.extend([user])
                    values.append(config_id)  # For WHERE clause

                    query = f"""
                        UPDATE training_configurations
                        SET {', '.join(set_clauses)}
                        WHERE config_id = ?
                    """

                    cursor.execute(query, values)

                    if cursor.rowcount == 0:
                        self._logger.warning(f"No configuration found with ID: {config_id}")
                        return False

                    conn.commit()
                    self._logger.info(f"Updated configuration: {config_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update configuration {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error updating configuration: {e}")
            return False

    def delete_configuration(self, config_id: str, user: str = "system") -> bool:
        """
        Delete a training configuration.

        Args:
            config_id: Configuration identifier
            user: User performing the deletion

        Returns:
            True if successful
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Check if configuration exists
                    cursor.execute("SELECT config_name FROM training_configurations WHERE config_id = ?", (config_id,))
                    result = cursor.fetchone()
                    if not result:
                        self._logger.warning(f"Configuration not found: {config_id}")
                        return False

                    config_name = result[0]

                    # Delete configuration (cascades to dependencies and usage history)
                    cursor.execute("DELETE FROM training_configurations WHERE config_id = ?", (config_id,))

                    conn.commit()
                    self._logger.info(f"Deleted configuration: {config_name} ({config_id}) by {user}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to delete configuration {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error deleting configuration: {e}")
            return False

    def list_configurations(self,
                          category: Optional[ConfigCategory] = None,
                          status: Optional[ConfigStatus] = None,
                          tags: Optional[List[str]] = None,
                          is_template: Optional[bool] = None,
                          limit: int = 100,
                          offset: int = 0,
                          order_by: str = "updated_at",
                          order_desc: bool = True) -> List[Dict[str, Any]]:
        """
        List training configurations with filtering and pagination.

        Args:
            category: Filter by category
            status: Filter by status
            tags: Filter by tags (any match)
            is_template: Filter by template status
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Field to order by
            order_desc: Whether to order descending

        Returns:
            List of configuration data
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

                    if status:
                        where_clauses.append("status = ?")
                        params.append(status.value)

                    if is_template is not None:
                        where_clauses.append("is_template = ?")
                        params.append(is_template)

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
                        SELECT config_id, config_name, config_description, category, status,
                               model_name, created_by, created_at, updated_at, last_used_at,
                               usage_count, is_template, tags_json
                        FROM training_configurations
                        {where_clause}
                        ORDER BY {order_by} {order_direction}
                        LIMIT ? OFFSET ?
                    """

                    params.extend([limit, offset])
                    cursor.execute(query, params)

                    configurations = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        config_data = dict(zip(columns, row))

                        # Deserialize tags
                        if config_data['tags_json']:
                            config_data['tags'] = json.loads(config_data['tags_json'])
                        else:
                            config_data['tags'] = []

                        del config_data['tags_json']  # Remove raw JSON field
                        configurations.append(config_data)

                    return configurations

                except Exception as e:
                    self._logger.error(f"Failed to list configurations: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error listing configurations: {e}")
            return []

    def search_configurations(self, query: str,
                            category: Optional[ConfigCategory] = None,
                            limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search configurations by name, description, or tags.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum number of results

        Returns:
            List of matching configurations
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    where_clauses = [
                        "(config_name LIKE ? OR config_description LIKE ? OR tags_json LIKE ?)"
                    ]
                    params = [f"%{query}%", f"%{query}%", f"%{query}%"]

                    if category:
                        where_clauses.append("category = ?")
                        params.append(category.value)

                    where_clause = f"WHERE {' AND '.join(where_clauses)}"
                    params.append(limit)

                    cursor.execute(f"""
                        SELECT config_id, config_name, config_description, category, status,
                               model_name, created_by, created_at, updated_at, usage_count,
                               is_template, tags_json
                        FROM training_configurations
                        {where_clause}
                        ORDER BY usage_count DESC, updated_at DESC
                        LIMIT ?
                    """, params)

                    configurations = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        config_data = dict(zip(columns, row))

                        # Deserialize tags
                        if config_data['tags_json']:
                            config_data['tags'] = json.loads(config_data['tags_json'])
                        else:
                            config_data['tags'] = []

                        del config_data['tags_json']
                        configurations.append(config_data)

                    return configurations

                except Exception as e:
                    self._logger.error(f"Failed to search configurations: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error searching configurations: {e}")
            return []

    def record_usage(self, config_id: str,
                    session_id: Optional[str] = None,
                    used_by: str = "system",
                    usage_type: str = "training",
                    usage_context: Optional[str] = None,
                    performance_metrics: Optional[Dict[str, Any]] = None,
                    success: Optional[bool] = None,
                    error_message: Optional[str] = None) -> str:
        """
        Record configuration usage.

        Args:
            config_id: Configuration identifier
            session_id: Optional training session ID
            used_by: User or system using the configuration
            usage_type: Type of usage (training, validation, etc.)
            usage_context: Optional context information
            performance_metrics: Optional performance metrics
            success: Whether usage was successful
            error_message: Error message if unsuccessful

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
                        INSERT INTO config_usage_history (
                            usage_id, config_id, session_id, used_by, usage_type,
                            usage_context, performance_metrics_json, success, error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        usage_id, config_id, session_id, used_by, usage_type,
                        usage_context,
                        json.dumps(performance_metrics) if performance_metrics else None,
                        success, error_message
                    ))

                    # Update usage count and last used timestamp
                    cursor.execute("""
                        UPDATE training_configurations
                        SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP
                        WHERE config_id = ?
                    """, (config_id,))

                    conn.commit()
                    self._logger.debug(f"Recorded usage for configuration {config_id}")
                    return usage_id

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to record usage for {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error recording usage: {e}")
            raise

    def get_usage_history(self, config_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get usage history for a configuration.

        Args:
            config_id: Configuration identifier
            limit: Maximum number of records

        Returns:
            List of usage records
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT usage_id, session_id, used_by, usage_type, usage_context,
                               performance_metrics_json, success, error_message, used_at
                        FROM config_usage_history
                        WHERE config_id = ?
                        ORDER BY used_at DESC
                        LIMIT ?
                    """, (config_id, limit))

                    usage_records = []
                    for row in cursor.fetchall():
                        columns = [desc[0] for desc in cursor.description]
                        usage_data = dict(zip(columns, row))

                        # Deserialize performance metrics
                        if usage_data['performance_metrics_json']:
                            usage_data['performance_metrics'] = json.loads(usage_data['performance_metrics_json'])
                        else:
                            usage_data['performance_metrics'] = {}

                        del usage_data['performance_metrics_json']
                        usage_records.append(usage_data)

                    return usage_records

                except Exception as e:
                    self._logger.error(f"Failed to get usage history for {config_id}: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting usage history: {e}")
            return []

    def get_configuration_statistics(self) -> Dict[str, Any]:
        """
        Get configuration repository statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    stats = {}

                    # Total configurations
                    cursor.execute("SELECT COUNT(*) FROM training_configurations")
                    stats['total_configurations'] = cursor.fetchone()[0]

                    # Configurations by category
                    cursor.execute("""
                        SELECT category, COUNT(*)
                        FROM training_configurations
                        GROUP BY category
                    """)
                    stats['by_category'] = dict(cursor.fetchall())

                    # Configurations by status
                    cursor.execute("""
                        SELECT status, COUNT(*)
                        FROM training_configurations
                        GROUP BY status
                    """)
                    stats['by_status'] = dict(cursor.fetchall())

                    # Template configurations
                    cursor.execute("SELECT COUNT(*) FROM training_configurations WHERE is_template = 1")
                    stats['template_count'] = cursor.fetchone()[0]

                    # Most used configurations
                    cursor.execute("""
                        SELECT config_name, usage_count
                        FROM training_configurations
                        ORDER BY usage_count DESC
                        LIMIT 10
                    """)
                    stats['most_used'] = [{'name': row[0], 'usage_count': row[1]} for row in cursor.fetchall()]

                    # Recent activity
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM config_usage_history
                        WHERE used_at >= datetime('now', '-7 days')
                    """)
                    stats['usage_last_week'] = cursor.fetchone()[0]

                    return stats

                except Exception as e:
                    self._logger.error(f"Failed to get configuration statistics: {e}")
                    raise
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error getting configuration statistics: {e}")
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
                        DELETE FROM config_usage_history
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
            self._logger.info("ConfigRepositoryDB closed successfully")
        except Exception as e:
            self._logger.error(f"Error closing ConfigRepositoryDB: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
