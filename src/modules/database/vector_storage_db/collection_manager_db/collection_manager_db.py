"""
Module: collection_manager_db
Description: Manages vector collections with metadata and configuration
Phase: 4
Location: /src/modules/database/vector_storage_db/collection_manager_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class CollectionStatus(Enum):
    """Status of vector collection."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUILDING = "building"
    OPTIMIZING = "optimizing"
    ERROR = "error"
    ARCHIVED = "archived"


class IndexType(Enum):
    """Supported index types for collections."""
    FLAT = "flat"
    IVF = "ivf"
    HNSW = "hnsw"
    LSH = "lsh"


class CollectionManagerDB:
    """
    Manages vector collections with metadata and configuration.
    
    Provides collection lifecycle management including creation, configuration,
    optimization, and metadata operations. Handles collection hierarchies,
    access control, and performance monitoring for vector storage systems.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the collection manager database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to vector storage data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "collections"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "collection_manager.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._collection_retention_days = 365  # Keep collections for 1 year
        self._max_collections_per_user = 100  # Maximum collections per user
        self._default_index_type = IndexType.FLAT
        
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
                
                # Create collections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collections (
                        collection_id TEXT PRIMARY KEY,
                        collection_name TEXT UNIQUE NOT NULL,
                        display_name TEXT,
                        description TEXT,
                        owner_id TEXT,
                        parent_collection_id TEXT,
                        status TEXT NOT NULL DEFAULT 'active',
                        index_type TEXT DEFAULT 'flat',
                        vector_dimension INTEGER,
                        similarity_metric TEXT DEFAULT 'cosine',
                        distance_threshold REAL DEFAULT 0.7,
                        max_vectors INTEGER,
                        current_vector_count INTEGER DEFAULT 0,
                        storage_size_mb REAL DEFAULT 0.0,
                        configuration TEXT,
                        access_permissions TEXT,
                        tags TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed_at TIMESTAMP,
                        expires_at TIMESTAMP,
                        FOREIGN KEY (parent_collection_id) REFERENCES collections(collection_id)
                    )
                """)
                
                # Create collection metadata table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_metadata (
                        metadata_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        metadata_key TEXT NOT NULL,
                        metadata_value TEXT,
                        metadata_type TEXT DEFAULT 'string',
                        is_searchable BOOLEAN DEFAULT FALSE,
                        is_indexed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES collections(collection_id),
                        UNIQUE(collection_id, metadata_key)
                    )
                """)
                
                # Create collection statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_statistics (
                        stat_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        stat_name TEXT NOT NULL,
                        stat_value REAL NOT NULL,
                        stat_unit TEXT,
                        stat_category TEXT,
                        measurement_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES collections(collection_id)
                    )
                """)
                
                # Create collection operations log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_operations (
                        operation_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        operation_type TEXT NOT NULL,
                        operation_status TEXT NOT NULL,
                        operation_details TEXT,
                        user_id TEXT,
                        execution_time_ms INTEGER,
                        memory_usage_mb REAL,
                        error_message TEXT,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES collections(collection_id)
                    )
                """)
                
                # Create collection access log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_access_log (
                        access_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        user_id TEXT,
                        access_type TEXT NOT NULL,
                        access_details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES collections(collection_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(collection_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_owner ON collections(owner_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_parent ON collections(parent_collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_status ON collections(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_created_at ON collections(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_last_accessed ON collections(last_accessed_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_expires_at ON collections(expires_at)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_collection ON collection_metadata(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_key ON collection_metadata(metadata_key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_searchable ON collection_metadata(is_searchable)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_collection ON collection_statistics(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_name ON collection_statistics(stat_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_time ON collection_statistics(measurement_time)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_collection ON collection_operations(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_type ON collection_operations(operation_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_status ON collection_operations(operation_status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_started ON collection_operations(started_at)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_collection ON collection_access_log(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_user ON collection_access_log(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_type ON collection_access_log(access_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_time ON collection_access_log(accessed_at)")
                
                conn.commit()
                self._logger.info("Collection manager database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize collection manager database: {e}")
                raise
            finally:
                conn.close()
    
    def create_collection(self, collection_name: str, display_name: Optional[str] = None,
                         description: Optional[str] = None, owner_id: Optional[str] = None,
                         parent_collection_id: Optional[str] = None,
                         vector_dimension: Optional[int] = None,
                         index_type: IndexType = IndexType.FLAT,
                         similarity_metric: str = "cosine",
                         distance_threshold: float = 0.7,
                         max_vectors: Optional[int] = None,
                         configuration: Optional[Dict[str, Any]] = None,
                         access_permissions: Optional[Dict[str, Any]] = None,
                         tags: Optional[List[str]] = None,
                         expires_at: Optional[datetime] = None) -> str:
        """
        Create a new vector collection.
        
        Args:
            collection_name: Unique collection name
            display_name: Human-readable display name
            description: Collection description
            owner_id: Owner identifier
            parent_collection_id: Parent collection for hierarchical organization
            vector_dimension: Dimension of vectors in this collection
            index_type: Type of vector index to use
            similarity_metric: Similarity metric for vector comparison
            distance_threshold: Default distance threshold for searches
            max_vectors: Maximum number of vectors allowed
            configuration: Additional configuration parameters
            access_permissions: Access control settings
            tags: Collection tags for organization
            expires_at: Expiration timestamp
            
        Returns:
            Collection ID
        """
        collection_id = str(uuid.uuid4())
        
        # Set default expiration if not provided
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=self._collection_retention_days)
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO collections (
                        collection_id, collection_name, display_name, description,
                        owner_id, parent_collection_id, status, index_type,
                        vector_dimension, similarity_metric, distance_threshold,
                        max_vectors, configuration, access_permissions, tags, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    collection_id, collection_name, display_name, description,
                    owner_id, parent_collection_id, CollectionStatus.ACTIVE.value, index_type.value,
                    vector_dimension, similarity_metric, distance_threshold,
                    max_vectors,
                    json.dumps(configuration) if configuration else None,
                    json.dumps(access_permissions) if access_permissions else None,
                    json.dumps(tags) if tags else None,
                    expires_at
                ))
                
                # Log the creation operation
                self._log_operation(collection_id, "create", "completed", 
                                  f"Created collection {collection_name}", owner_id)
                
                conn.commit()
                self._logger.info(f"Created collection {collection_name} with ID {collection_id}")
                return collection_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
            finally:
                conn.close()

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get collection information by ID.

        Args:
            collection_id: Collection identifier

        Returns:
            Collection data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT collection_id, collection_name, display_name, description,
                           owner_id, parent_collection_id, status, index_type,
                           vector_dimension, similarity_metric, distance_threshold,
                           max_vectors, current_vector_count, storage_size_mb,
                           configuration, access_permissions, tags, created_at,
                           updated_at, last_accessed_at, expires_at
                    FROM collections
                    WHERE collection_id = ?
                """, (collection_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Update last accessed time
                cursor.execute("UPDATE collections SET last_accessed_at = CURRENT_TIMESTAMP WHERE collection_id = ?",
                             (collection_id,))
                conn.commit()

                return {
                    'collection_id': row[0],
                    'collection_name': row[1],
                    'display_name': row[2],
                    'description': row[3],
                    'owner_id': row[4],
                    'parent_collection_id': row[5],
                    'status': row[6],
                    'index_type': row[7],
                    'vector_dimension': row[8],
                    'similarity_metric': row[9],
                    'distance_threshold': row[10],
                    'max_vectors': row[11],
                    'current_vector_count': row[12],
                    'storage_size_mb': row[13],
                    'configuration': json.loads(row[14]) if row[14] else None,
                    'access_permissions': json.loads(row[15]) if row[15] else None,
                    'tags': json.loads(row[16]) if row[16] else None,
                    'created_at': row[17],
                    'updated_at': row[18],
                    'last_accessed_at': row[19],
                    'expires_at': row[20]
                }

            except Exception as e:
                self._logger.error(f"Failed to get collection {collection_id}: {e}")
                return None
            finally:
                conn.close()

    def get_collection_by_name(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get collection information by name.

        Args:
            collection_name: Collection name

        Returns:
            Collection data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT collection_id, collection_name, display_name, description,
                           owner_id, parent_collection_id, status, index_type,
                           vector_dimension, similarity_metric, distance_threshold,
                           max_vectors, current_vector_count, storage_size_mb,
                           configuration, access_permissions, tags, created_at,
                           updated_at, last_accessed_at, expires_at
                    FROM collections
                    WHERE collection_name = ?
                """, (collection_name,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Update last accessed time
                cursor.execute("UPDATE collections SET last_accessed_at = CURRENT_TIMESTAMP WHERE collection_name = ?",
                             (collection_name,))
                conn.commit()

                return {
                    'collection_id': row[0],
                    'collection_name': row[1],
                    'display_name': row[2],
                    'description': row[3],
                    'owner_id': row[4],
                    'parent_collection_id': row[5],
                    'status': row[6],
                    'index_type': row[7],
                    'vector_dimension': row[8],
                    'similarity_metric': row[9],
                    'distance_threshold': row[10],
                    'max_vectors': row[11],
                    'current_vector_count': row[12],
                    'storage_size_mb': row[13],
                    'configuration': json.loads(row[14]) if row[14] else None,
                    'access_permissions': json.loads(row[15]) if row[15] else None,
                    'tags': json.loads(row[16]) if row[16] else None,
                    'created_at': row[17],
                    'updated_at': row[18],
                    'last_accessed_at': row[19],
                    'expires_at': row[20]
                }

            except Exception as e:
                self._logger.error(f"Failed to get collection by name {collection_name}: {e}")
                return None
            finally:
                conn.close()

    def update_collection(self, collection_id: str,
                         display_name: Optional[str] = None,
                         description: Optional[str] = None,
                         status: Optional[CollectionStatus] = None,
                         index_type: Optional[IndexType] = None,
                         distance_threshold: Optional[float] = None,
                         max_vectors: Optional[int] = None,
                         configuration: Optional[Dict[str, Any]] = None,
                         access_permissions: Optional[Dict[str, Any]] = None,
                         tags: Optional[List[str]] = None) -> bool:
        """
        Update collection properties.

        Args:
            collection_id: Collection identifier
            display_name: New display name
            description: New description
            status: New status
            index_type: New index type
            distance_threshold: New distance threshold
            max_vectors: New maximum vector count
            configuration: New configuration
            access_permissions: New access permissions
            tags: New tags

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build update query dynamically
                update_fields = ["updated_at = CURRENT_TIMESTAMP"]
                params = []

                if display_name is not None:
                    update_fields.append("display_name = ?")
                    params.append(display_name)

                if description is not None:
                    update_fields.append("description = ?")
                    params.append(description)

                if status is not None:
                    update_fields.append("status = ?")
                    params.append(status.value)

                if index_type is not None:
                    update_fields.append("index_type = ?")
                    params.append(index_type.value)

                if distance_threshold is not None:
                    update_fields.append("distance_threshold = ?")
                    params.append(distance_threshold)

                if max_vectors is not None:
                    update_fields.append("max_vectors = ?")
                    params.append(max_vectors)

                if configuration is not None:
                    update_fields.append("configuration = ?")
                    params.append(json.dumps(configuration))

                if access_permissions is not None:
                    update_fields.append("access_permissions = ?")
                    params.append(json.dumps(access_permissions))

                if tags is not None:
                    update_fields.append("tags = ?")
                    params.append(json.dumps(tags))

                params.append(collection_id)

                query = f"UPDATE collections SET {', '.join(update_fields)} WHERE collection_id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    self._logger.warning(f"No collection found with ID {collection_id}")
                    return False

                # Log the update operation
                self._log_operation(collection_id, "update", "completed",
                                  "Updated collection properties")

                conn.commit()
                self._logger.info(f"Updated collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update collection {collection_id}: {e}")
                return False
            finally:
                conn.close()

    def delete_collection(self, collection_id: str, cascade: bool = False) -> bool:
        """
        Delete a collection and optionally its child collections.

        Args:
            collection_id: Collection identifier
            cascade: Whether to delete child collections

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if collection exists
                cursor.execute("SELECT collection_name FROM collections WHERE collection_id = ?", (collection_id,))
                result = cursor.fetchone()
                if not result:
                    self._logger.warning(f"No collection found with ID {collection_id}")
                    return False

                collection_name = result[0]

                # Handle child collections
                if cascade:
                    # Get all child collections recursively
                    child_collections = self._get_child_collections_recursive(collection_id, cursor)
                    for child_id in child_collections:
                        self._delete_collection_data(child_id, cursor)

                else:
                    # Check for child collections
                    cursor.execute("SELECT COUNT(*) FROM collections WHERE parent_collection_id = ?", (collection_id,))
                    child_count = cursor.fetchone()[0]
                    if child_count > 0:
                        raise ValueError(f"Collection has {child_count} child collections. Use cascade=True to delete them.")

                # Delete the collection and its data
                self._delete_collection_data(collection_id, cursor)

                # Log the deletion operation
                self._log_operation(collection_id, "delete", "completed",
                                  f"Deleted collection {collection_name}")

                conn.commit()
                self._logger.info(f"Deleted collection {collection_name} (ID: {collection_id})")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete collection {collection_id}: {e}")
                return False
            finally:
                conn.close()

    def _get_child_collections_recursive(self, parent_id: str, cursor) -> List[str]:
        """Get all child collection IDs recursively."""
        cursor.execute("SELECT collection_id FROM collections WHERE parent_collection_id = ?", (parent_id,))
        child_ids = [row[0] for row in cursor.fetchall()]

        all_children = child_ids.copy()
        for child_id in child_ids:
            all_children.extend(self._get_child_collections_recursive(child_id, cursor))

        return all_children

    def _delete_collection_data(self, collection_id: str, cursor) -> None:
        """Delete all data associated with a collection."""
        # Delete in order to respect foreign key constraints
        cursor.execute("DELETE FROM collection_access_log WHERE collection_id = ?", (collection_id,))
        cursor.execute("DELETE FROM collection_operations WHERE collection_id = ?", (collection_id,))
        cursor.execute("DELETE FROM collection_statistics WHERE collection_id = ?", (collection_id,))
        cursor.execute("DELETE FROM collection_metadata WHERE collection_id = ?", (collection_id,))
        cursor.execute("DELETE FROM collections WHERE collection_id = ?", (collection_id,))

    def list_collections(self, owner_id: Optional[str] = None,
                        parent_collection_id: Optional[str] = None,
                        status: Optional[CollectionStatus] = None,
                        tags: Optional[List[str]] = None,
                        limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List collections with optional filtering.

        Args:
            owner_id: Filter by owner
            parent_collection_id: Filter by parent collection
            status: Filter by status
            tags: Filter by tags (collections must have all specified tags)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of collection dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT collection_id, collection_name, display_name, description,
                           owner_id, parent_collection_id, status, index_type,
                           vector_dimension, similarity_metric, distance_threshold,
                           max_vectors, current_vector_count, storage_size_mb,
                           configuration, access_permissions, tags, created_at,
                           updated_at, last_accessed_at, expires_at
                    FROM collections
                    WHERE 1=1
                """
                params = []

                if owner_id:
                    query += " AND owner_id = ?"
                    params.append(owner_id)

                if parent_collection_id:
                    query += " AND parent_collection_id = ?"
                    params.append(parent_collection_id)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)

                collections = []
                for row in cursor.fetchall():
                    collection_data = {
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'display_name': row[2],
                        'description': row[3],
                        'owner_id': row[4],
                        'parent_collection_id': row[5],
                        'status': row[6],
                        'index_type': row[7],
                        'vector_dimension': row[8],
                        'similarity_metric': row[9],
                        'distance_threshold': row[10],
                        'max_vectors': row[11],
                        'current_vector_count': row[12],
                        'storage_size_mb': row[13],
                        'configuration': json.loads(row[14]) if row[14] else None,
                        'access_permissions': json.loads(row[15]) if row[15] else None,
                        'tags': json.loads(row[16]) if row[16] else None,
                        'created_at': row[17],
                        'updated_at': row[18],
                        'last_accessed_at': row[19],
                        'expires_at': row[20]
                    }

                    # Filter by tags if specified
                    if tags:
                        collection_tags = collection_data.get('tags', [])
                        if not all(tag in collection_tags for tag in tags):
                            continue

                    collections.append(collection_data)

                return collections

            except Exception as e:
                self._logger.error(f"Failed to list collections: {e}")
                return []
            finally:
                conn.close()

    def update_collection_statistics(self, collection_id: str,
                                   vector_count: Optional[int] = None,
                                   storage_size_mb: Optional[float] = None,
                                   custom_stats: Optional[Dict[str, float]] = None) -> bool:
        """
        Update collection statistics.

        Args:
            collection_id: Collection identifier
            vector_count: Current vector count
            storage_size_mb: Storage size in MB
            custom_stats: Additional custom statistics

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update basic statistics in collections table
                if vector_count is not None or storage_size_mb is not None:
                    update_fields = ["updated_at = CURRENT_TIMESTAMP"]
                    params = []

                    if vector_count is not None:
                        update_fields.append("current_vector_count = ?")
                        params.append(vector_count)

                    if storage_size_mb is not None:
                        update_fields.append("storage_size_mb = ?")
                        params.append(storage_size_mb)

                    params.append(collection_id)

                    query = f"UPDATE collections SET {', '.join(update_fields)} WHERE collection_id = ?"
                    cursor.execute(query, params)

                # Add custom statistics
                if custom_stats:
                    for stat_name, stat_value in custom_stats.items():
                        stat_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO collection_statistics (
                                stat_id, collection_id, stat_name, stat_value, stat_category
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (stat_id, collection_id, stat_name, stat_value, "custom"))

                conn.commit()
                self._logger.info(f"Updated statistics for collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update collection statistics {collection_id}: {e}")
                return False
            finally:
                conn.close()

    def set_collection_metadata(self, collection_id: str, metadata_key: str,
                               metadata_value: str, metadata_type: str = "string",
                               is_searchable: bool = False, is_indexed: bool = False) -> bool:
        """
        Set metadata for a collection.

        Args:
            collection_id: Collection identifier
            metadata_key: Metadata key
            metadata_value: Metadata value
            metadata_type: Type of metadata (string, number, boolean, json)
            is_searchable: Whether metadata is searchable
            is_indexed: Whether metadata should be indexed

        Returns:
            True if successful, False otherwise
        """
        metadata_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle updates
                cursor.execute("""
                    INSERT OR REPLACE INTO collection_metadata (
                        metadata_id, collection_id, metadata_key, metadata_value,
                        metadata_type, is_searchable, is_indexed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (metadata_id, collection_id, metadata_key, metadata_value,
                      metadata_type, is_searchable, is_indexed))

                conn.commit()
                self._logger.info(f"Set metadata {metadata_key} for collection {collection_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to set metadata for collection {collection_id}: {e}")
                return False
            finally:
                conn.close()

    def get_collection_metadata(self, collection_id: str,
                               metadata_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for a collection.

        Args:
            collection_id: Collection identifier
            metadata_key: Specific metadata key (if None, returns all metadata)

        Returns:
            Metadata dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if metadata_key:
                    cursor.execute("""
                        SELECT metadata_key, metadata_value, metadata_type,
                               is_searchable, is_indexed, created_at, updated_at
                        FROM collection_metadata
                        WHERE collection_id = ? AND metadata_key = ?
                    """, (collection_id, metadata_key))

                    row = cursor.fetchone()
                    if not row:
                        return {}

                    return {
                        'metadata_key': row[0],
                        'metadata_value': row[1],
                        'metadata_type': row[2],
                        'is_searchable': row[3],
                        'is_indexed': row[4],
                        'created_at': row[5],
                        'updated_at': row[6]
                    }

                else:
                    cursor.execute("""
                        SELECT metadata_key, metadata_value, metadata_type,
                               is_searchable, is_indexed, created_at, updated_at
                        FROM collection_metadata
                        WHERE collection_id = ?
                    """, (collection_id,))

                    metadata = {}
                    for row in cursor.fetchall():
                        metadata[row[0]] = {
                            'value': row[1],
                            'type': row[2],
                            'is_searchable': row[3],
                            'is_indexed': row[4],
                            'created_at': row[5],
                            'updated_at': row[6]
                        }

                    return metadata

            except Exception as e:
                self._logger.error(f"Failed to get metadata for collection {collection_id}: {e}")
                return {}
            finally:
                conn.close()

    def _log_operation(self, collection_id: str, operation_type: str,
                      operation_status: str, operation_details: Optional[str] = None,
                      user_id: Optional[str] = None, execution_time_ms: Optional[int] = None,
                      memory_usage_mb: Optional[float] = None,
                      error_message: Optional[str] = None) -> str:
        """
        Log a collection operation.

        Args:
            collection_id: Collection identifier
            operation_type: Type of operation
            operation_status: Status of operation
            operation_details: Operation details
            user_id: User who performed the operation
            execution_time_ms: Execution time in milliseconds
            memory_usage_mb: Memory usage in MB
            error_message: Error message if operation failed

        Returns:
            Operation ID
        """
        operation_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO collection_operations (
                        operation_id, collection_id, operation_type, operation_status,
                        operation_details, user_id, execution_time_ms, memory_usage_mb,
                        error_message, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (operation_id, collection_id, operation_type, operation_status,
                      operation_details, user_id, execution_time_ms, memory_usage_mb,
                      error_message))

                conn.commit()
                return operation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log operation for collection {collection_id}: {e}")
                return operation_id
            finally:
                conn.close()

    def get_collection_statistics(self, collection_id: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Statistics dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get basic collection info
                cursor.execute("""
                    SELECT current_vector_count, storage_size_mb, created_at, last_accessed_at
                    FROM collections
                    WHERE collection_id = ?
                """, (collection_id,))

                row = cursor.fetchone()
                if not row:
                    return {}

                stats = {
                    'current_vector_count': row[0] or 0,
                    'storage_size_mb': row[1] or 0.0,
                    'created_at': row[2],
                    'last_accessed_at': row[3]
                }

                # Get custom statistics
                cursor.execute("""
                    SELECT stat_name, stat_value, stat_unit, stat_category, measurement_time
                    FROM collection_statistics
                    WHERE collection_id = ?
                    ORDER BY measurement_time DESC
                """, (collection_id,))

                custom_stats = []
                for row in cursor.fetchall():
                    custom_stats.append({
                        'stat_name': row[0],
                        'stat_value': row[1],
                        'stat_unit': row[2],
                        'stat_category': row[3],
                        'measurement_time': row[4]
                    })

                stats['custom_statistics'] = custom_stats

                # Get operation counts
                cursor.execute("""
                    SELECT operation_type, COUNT(*)
                    FROM collection_operations
                    WHERE collection_id = ?
                    GROUP BY operation_type
                """, (collection_id,))

                operation_counts = {}
                for row in cursor.fetchall():
                    operation_counts[row[0]] = row[1]

                stats['operation_counts'] = operation_counts

                return stats

            except Exception as e:
                self._logger.error(f"Failed to get statistics for collection {collection_id}: {e}")
                return {}
            finally:
                conn.close()

    def cleanup_expired_collections(self) -> int:
        """
        Remove expired collections from the database.

        Returns:
            Number of collections cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                current_time = datetime.now(timezone.utc)

                # Get expired collection IDs
                cursor.execute("SELECT collection_id, collection_name FROM collections WHERE expires_at < ?",
                             (current_time,))
                expired_collections = cursor.fetchall()

                if not expired_collections:
                    return 0

                # Delete expired collections
                for collection_id, collection_name in expired_collections:
                    self._delete_collection_data(collection_id, cursor)
                    self._logger.info(f"Cleaned up expired collection: {collection_name}")

                conn.commit()
                self._logger.info(f"Cleaned up {len(expired_collections)} expired collections")
                return len(expired_collections)

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup expired collections: {e}")
                return 0
            finally:
                conn.close()

    def close(self) -> None:
        """Close database connections and clean up resources."""
        try:
            # No persistent connections to close in this implementation
            self._logger.info("Collection manager closed")
        except Exception as e:
            self._logger.error(f"Error closing collection manager: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
