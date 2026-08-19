"""
Module: model_dao_db
Description: Handles model metadata persistence, version tracking, and performance metrics storage
Phase: 4
Location: /src/modules/database/model_repository_db/model_dao_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ModelStatus(Enum):
    """Model status enumeration."""
    CREATED = "created"
    TRAINING = "training"
    TRAINED = "trained"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelArchitecture(Enum):
    """Model architecture enumeration."""
    SMALL_1B = "1B"
    MEDIUM_3B = "3B"
    LARGE_7B = "7B"


class QuantizationType(Enum):
    """Model quantization type enumeration."""
    INT4 = "INT4"
    INT8 = "INT8"
    FP16 = "FP16"
    FP32 = "FP32"


@dataclass
class ModelMetadata:
    """Model metadata data structure."""
    model_id: str
    project_id: str
    name: str
    version: str
    architecture: ModelArchitecture
    status: ModelStatus
    base_model: Optional[str] = None
    model_path: Optional[str] = None
    onnx_path: Optional[str] = None
    quantization_type: QuantizationType = QuantizationType.FP16
    parameters_count: Optional[int] = None
    model_size_mb: Optional[float] = None
    created_at: datetime = None
    updated_at: datetime = None
    created_by: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    training_config: Optional[Dict[str, Any]] = None
    deployment_config: Optional[Dict[str, Any]] = None
    checksum: Optional[str] = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.tags is None:
            self.tags = []


class ModelDAODB:
    """
    Model Data Access Object for handling model metadata persistence.
    
    Provides comprehensive CRUD operations for model entities with optimized
    queries, transaction management, and performance metrics tracking.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the model DAO database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to model repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "model_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "model_dao.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._model_retention_days = 365  # Keep models for 1 year
        self._max_models_per_project = 100  # Maximum models per project
        self._batch_size = 50  # Batch size for bulk operations
        
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
                
                # Create models table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS models (
                        model_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        version TEXT NOT NULL,
                        architecture TEXT NOT NULL,
                        status TEXT NOT NULL,
                        base_model TEXT,
                        model_path TEXT,
                        onnx_path TEXT,
                        quantization_type TEXT NOT NULL DEFAULT 'FP16',
                        parameters_count INTEGER,
                        model_size_mb REAL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        created_by TEXT,
                        description TEXT,
                        tags_json TEXT,
                        performance_metrics_json TEXT,
                        training_config_json TEXT,
                        deployment_config_json TEXT,
                        checksum TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        
                        CONSTRAINT valid_architecture CHECK (architecture IN ('1B', '3B', '7B')),
                        CONSTRAINT valid_status CHECK (status IN ('created', 'training', 'trained', 'deployed', 'archived', 'failed')),
                        CONSTRAINT valid_quantization CHECK (quantization_type IN ('INT4', 'INT8', 'FP16', 'FP32'))
                    )
                """)
                
                # Create performance-optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_models_project_status 
                    ON models(project_id, status, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_models_name_version 
                    ON models(name, version)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_models_architecture_status 
                    ON models(architecture, status, is_active)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_models_created_at 
                    ON models(created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_models_checksum 
                    ON models(checksum)
                """)
                
                # Create model performance metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_performance_metrics (
                        metric_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        metric_type TEXT NOT NULL,
                        measurement_timestamp TEXT NOT NULL,
                        benchmark_name TEXT,
                        dataset_name TEXT,
                        evaluation_config_json TEXT,
                        metadata_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_performance_model_metric 
                    ON model_performance_metrics(model_id, metric_name, measurement_timestamp DESC)
                """)
                
                # Create model usage statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_usage_stats (
                        stat_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        usage_type TEXT NOT NULL,
                        usage_count INTEGER DEFAULT 0,
                        last_used_at TEXT,
                        total_inference_time_ms INTEGER DEFAULT 0,
                        average_response_time_ms REAL DEFAULT 0.0,
                        error_count INTEGER DEFAULT 0,
                        success_rate REAL DEFAULT 1.0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_stats_model 
                    ON model_usage_stats(model_id, usage_type)
                """)
                
                conn.commit()
                self._logger.info("Model DAO database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize model DAO database: {e}")
                raise
            finally:
                conn.close()

    def create_model(self, model_metadata: ModelMetadata) -> str:
        """
        Create a new model record.

        Args:
            model_metadata: Model metadata to store

        Returns:
            Model ID of the created model

        Raises:
            ValueError: If model data is invalid
            sqlite3.IntegrityError: If model already exists
        """
        if not model_metadata.model_id:
            model_metadata.model_id = str(uuid.uuid4())

        # Validate required fields
        if not model_metadata.project_id:
            raise ValueError("Project ID is required")
        if not model_metadata.name:
            raise ValueError("Model name is required")
        if not model_metadata.version:
            raise ValueError("Model version is required")

        model_metadata.updated_at = datetime.now(timezone.utc)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if model with same name and version exists in project
                cursor.execute("""
                    SELECT model_id FROM models
                    WHERE project_id = ? AND name = ? AND version = ? AND is_active = 1
                """, (model_metadata.project_id, model_metadata.name, model_metadata.version))

                if cursor.fetchone():
                    raise ValueError(f"Model {model_metadata.name} version {model_metadata.version} already exists in project")

                # Insert model record
                cursor.execute("""
                    INSERT INTO models (
                        model_id, project_id, name, version, architecture, status,
                        base_model, model_path, onnx_path, quantization_type,
                        parameters_count, model_size_mb, created_at, updated_at,
                        created_by, description, tags_json, performance_metrics_json,
                        training_config_json, deployment_config_json, checksum, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model_metadata.model_id,
                    model_metadata.project_id,
                    model_metadata.name,
                    model_metadata.version,
                    model_metadata.architecture.value,
                    model_metadata.status.value,
                    model_metadata.base_model,
                    model_metadata.model_path,
                    model_metadata.onnx_path,
                    model_metadata.quantization_type.value,
                    model_metadata.parameters_count,
                    model_metadata.model_size_mb,
                    model_metadata.created_at.isoformat(),
                    model_metadata.updated_at.isoformat(),
                    model_metadata.created_by,
                    model_metadata.description,
                    json.dumps(model_metadata.tags) if model_metadata.tags else None,
                    json.dumps(model_metadata.performance_metrics) if model_metadata.performance_metrics else None,
                    json.dumps(model_metadata.training_config) if model_metadata.training_config else None,
                    json.dumps(model_metadata.deployment_config) if model_metadata.deployment_config else None,
                    model_metadata.checksum,
                    model_metadata.is_active
                ))

                # Initialize usage statistics
                cursor.execute("""
                    INSERT INTO model_usage_stats (
                        stat_id, model_id, usage_type, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    model_metadata.model_id,
                    'inference',
                    model_metadata.created_at.isoformat(),
                    model_metadata.updated_at.isoformat()
                ))

                conn.commit()
                self._logger.info(f"Created model: {model_metadata.model_id}")
                return model_metadata.model_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create model {model_metadata.model_id}: {e}")
                raise
            finally:
                conn.close()

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """
        Retrieve a model by ID.

        Args:
            model_id: Model identifier

        Returns:
            Model metadata or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT model_id, project_id, name, version, architecture, status,
                           base_model, model_path, onnx_path, quantization_type,
                           parameters_count, model_size_mb, created_at, updated_at,
                           created_by, description, tags_json, performance_metrics_json,
                           training_config_json, deployment_config_json, checksum, is_active
                    FROM models
                    WHERE model_id = ? AND is_active = 1
                """, (model_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_model_metadata(row)

            except Exception as e:
                self._logger.error(f"Failed to get model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def update_model(self, model_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update model metadata.

        Args:
            model_id: Model identifier
            updates: Dictionary of fields to update

        Returns:
            True if model was updated, False if not found
        """
        if not updates:
            return False

        # Validate update fields
        valid_fields = {
            'name', 'version', 'architecture', 'status', 'base_model',
            'model_path', 'onnx_path', 'quantization_type', 'parameters_count',
            'model_size_mb', 'created_by', 'description', 'tags',
            'performance_metrics', 'training_config', 'deployment_config',
            'checksum', 'is_active'
        }

        invalid_fields = set(updates.keys()) - valid_fields
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {invalid_fields}")

        # Build update query
        set_clauses = []
        params = []

        for field, value in updates.items():
            if field in ['tags', 'performance_metrics', 'training_config', 'deployment_config']:
                set_clauses.append(f"{field}_json = ?")
                params.append(json.dumps(value) if value is not None else None)
            elif field in ['architecture', 'status', 'quantization_type']:
                set_clauses.append(f"{field} = ?")
                params.append(value.value if hasattr(value, 'value') else value)
            else:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(model_id)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = f"""
                    UPDATE models
                    SET {', '.join(set_clauses)}
                    WHERE model_id = ? AND is_active = 1
                """

                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.info(f"Updated model: {model_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_model(self, model_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a model (soft delete by default).

        Args:
            model_id: Model identifier
            soft_delete: If True, mark as inactive; if False, permanently delete

        Returns:
            True if model was deleted, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if soft_delete:
                    cursor.execute("""
                        UPDATE models
                        SET is_active = 0, updated_at = ?
                        WHERE model_id = ? AND is_active = 1
                    """, (datetime.now(timezone.utc).isoformat(), model_id))
                else:
                    cursor.execute("""
                        DELETE FROM models WHERE model_id = ?
                    """, (model_id,))

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.info(f"{'Soft deleted' if soft_delete else 'Deleted'} model: {model_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def list_models(self, project_id: Optional[str] = None, status: Optional[ModelStatus] = None,
                   architecture: Optional[ModelArchitecture] = None, limit: int = 100,
                   offset: int = 0, include_inactive: bool = False) -> List[ModelMetadata]:
        """
        List models with optional filtering.

        Args:
            project_id: Filter by project ID
            status: Filter by model status
            architecture: Filter by model architecture
            limit: Maximum number of results
            offset: Number of results to skip
            include_inactive: Include soft-deleted models

        Returns:
            List of model metadata
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT model_id, project_id, name, version, architecture, status,
                           base_model, model_path, onnx_path, quantization_type,
                           parameters_count, model_size_mb, created_at, updated_at,
                           created_by, description, tags_json, performance_metrics_json,
                           training_config_json, deployment_config_json, checksum, is_active
                    FROM models
                    WHERE 1=1
                """
                params = []

                if not include_inactive:
                    query += " AND is_active = 1"

                if project_id:
                    query += " AND project_id = ?"
                    params.append(project_id)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                if architecture:
                    query += " AND architecture = ?"
                    params.append(architecture.value)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_model_metadata(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to list models: {e}")
                raise
            finally:
                conn.close()

    def add_performance_metric(self, model_id: str, metric_name: str, metric_value: float,
                              metric_type: str = "accuracy", benchmark_name: Optional[str] = None,
                              dataset_name: Optional[str] = None, evaluation_config: Optional[Dict[str, Any]] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a performance metric for a model.

        Args:
            model_id: Model identifier
            metric_name: Name of the metric (e.g., 'accuracy', 'f1_score')
            metric_value: Metric value
            metric_type: Type of metric
            benchmark_name: Name of the benchmark used
            dataset_name: Name of the dataset used
            evaluation_config: Configuration used for evaluation
            metadata: Additional metadata

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Verify model exists
                cursor.execute("SELECT 1 FROM models WHERE model_id = ? AND is_active = 1", (model_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Model {model_id} not found")

                cursor.execute("""
                    INSERT INTO model_performance_metrics (
                        metric_id, model_id, metric_name, metric_value, metric_type,
                        measurement_timestamp, benchmark_name, dataset_name,
                        evaluation_config_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, model_id, metric_name, metric_value, metric_type,
                    timestamp, benchmark_name, dataset_name,
                    json.dumps(evaluation_config) if evaluation_config else None,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Added performance metric for model {model_id}: {metric_name}={metric_value}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add performance metric for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def get_performance_metrics(self, model_id: str, metric_name: Optional[str] = None,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get performance metrics for a model.

        Args:
            model_id: Model identifier
            metric_name: Filter by specific metric name
            limit: Maximum number of results

        Returns:
            List of performance metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT metric_id, metric_name, metric_value, metric_type,
                           measurement_timestamp, benchmark_name, dataset_name,
                           evaluation_config_json, metadata_json, created_at
                    FROM model_performance_metrics
                    WHERE model_id = ?
                """
                params = [model_id]

                if metric_name:
                    query += " AND metric_name = ?"
                    params.append(metric_name)

                query += " ORDER BY measurement_timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                metrics = []
                for row in rows:
                    metric = {
                        'metric_id': row[0],
                        'metric_name': row[1],
                        'metric_value': row[2],
                        'metric_type': row[3],
                        'measurement_timestamp': row[4],
                        'benchmark_name': row[5],
                        'dataset_name': row[6],
                        'evaluation_config': json.loads(row[7]) if row[7] else None,
                        'metadata': json.loads(row[8]) if row[8] else None,
                        'created_at': row[9]
                    }
                    metrics.append(metric)

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get performance metrics for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def update_usage_stats(self, model_id: str, usage_type: str = "inference",
                          inference_time_ms: Optional[int] = None, success: bool = True) -> None:
        """
        Update usage statistics for a model.

        Args:
            model_id: Model identifier
            usage_type: Type of usage (e.g., 'inference', 'training')
            inference_time_ms: Time taken for inference in milliseconds
            success: Whether the operation was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get current stats
                cursor.execute("""
                    SELECT usage_count, total_inference_time_ms, error_count
                    FROM model_usage_stats
                    WHERE model_id = ? AND usage_type = ?
                """, (model_id, usage_type))

                row = cursor.fetchone()
                if row:
                    usage_count, total_time, error_count = row
                    usage_count += 1
                    if not success:
                        error_count += 1
                    if inference_time_ms:
                        total_time += inference_time_ms

                    avg_time = total_time / usage_count if usage_count > 0 else 0.0
                    success_rate = (usage_count - error_count) / usage_count if usage_count > 0 else 1.0

                    cursor.execute("""
                        UPDATE model_usage_stats
                        SET usage_count = ?, total_inference_time_ms = ?, error_count = ?,
                            average_response_time_ms = ?, success_rate = ?, last_used_at = ?, updated_at = ?
                        WHERE model_id = ? AND usage_type = ?
                    """, (
                        usage_count, total_time, error_count, avg_time, success_rate,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                        model_id, usage_type
                    ))
                else:
                    # Create new stats record
                    cursor.execute("""
                        INSERT INTO model_usage_stats (
                            stat_id, model_id, usage_type, usage_count, total_inference_time_ms,
                            error_count, average_response_time_ms, success_rate, last_used_at,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()), model_id, usage_type, 1,
                        inference_time_ms or 0, 0 if success else 1,
                        inference_time_ms or 0.0, 1.0 if success else 0.0,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat()
                    ))

                conn.commit()

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update usage stats for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def get_usage_stats(self, model_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a model.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary containing usage statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT usage_type, usage_count, last_used_at, total_inference_time_ms,
                           average_response_time_ms, error_count, success_rate
                    FROM model_usage_stats
                    WHERE model_id = ?
                """, (model_id,))

                rows = cursor.fetchall()
                stats = {}

                for row in rows:
                    usage_type = row[0]
                    stats[usage_type] = {
                        'usage_count': row[1],
                        'last_used_at': row[2],
                        'total_inference_time_ms': row[3],
                        'average_response_time_ms': row[4],
                        'error_count': row[5],
                        'success_rate': row[6]
                    }

                return stats

            except Exception as e:
                self._logger.error(f"Failed to get usage stats for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def _row_to_model_metadata(self, row: Tuple) -> ModelMetadata:
        """Convert database row to ModelMetadata object."""
        return ModelMetadata(
            model_id=row[0],
            project_id=row[1],
            name=row[2],
            version=row[3],
            architecture=ModelArchitecture(row[4]),
            status=ModelStatus(row[5]),
            base_model=row[6],
            model_path=row[7],
            onnx_path=row[8],
            quantization_type=QuantizationType(row[9]),
            parameters_count=row[10],
            model_size_mb=row[11],
            created_at=datetime.fromisoformat(row[12]) if row[12] else None,
            updated_at=datetime.fromisoformat(row[13]) if row[13] else None,
            created_by=row[14],
            description=row[15],
            tags=json.loads(row[16]) if row[16] else [],
            performance_metrics=json.loads(row[17]) if row[17] else None,
            training_config=json.loads(row[18]) if row[18] else None,
            deployment_config=json.loads(row[19]) if row[19] else None,
            checksum=row[20],
            is_active=bool(row[21])
        )

    def cleanup_old_models(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old inactive models.

        Args:
            retention_days: Number of days to retain models (uses default if None)

        Returns:
            Number of models cleaned up
        """
        if retention_days is None:
            retention_days = self._model_retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    DELETE FROM models
                    WHERE is_active = 0 AND updated_at < ?
                """, (cutoff_date.isoformat(),))

                deleted_count = cursor.rowcount
                conn.commit()

                self._logger.info(f"Cleaned up {deleted_count} old models")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old models: {e}")
                raise
            finally:
                conn.close()

    def get_model_count(self, project_id: Optional[str] = None, include_inactive: bool = False) -> int:
        """
        Get total count of models.

        Args:
            project_id: Filter by project ID
            include_inactive: Include soft-deleted models

        Returns:
            Total number of models
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = "SELECT COUNT(*) FROM models WHERE 1=1"
                params = []

                if not include_inactive:
                    query += " AND is_active = 1"

                if project_id:
                    query += " AND project_id = ?"
                    params.append(project_id)

                cursor.execute(query, params)
                return cursor.fetchone()[0]

            except Exception as e:
                self._logger.error(f"Failed to get model count: {e}")
                raise
            finally:
                conn.close()
