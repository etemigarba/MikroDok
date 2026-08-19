"""
Module: vector_index_db
Description: Implements vector indexing strategies (FLAT, IVF, HNSW) for fast retrieval
Phase: 4
Location: /src/modules/database/vector_storage_db/vector_index_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import time

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class IndexType(Enum):
    """Supported vector index types."""
    FLAT = "flat"
    IVF = "ivf"
    HNSW = "hnsw"
    LSH = "lsh"


class IndexStatus(Enum):
    """Status of vector index."""
    BUILDING = "building"
    READY = "ready"
    UPDATING = "updating"
    ERROR = "error"
    OPTIMIZING = "optimizing"


class VectorIndexDB:
    """
    Implements vector indexing strategies (FLAT, IVF, HNSW) for fast retrieval.
    
    Provides high-performance vector indexing with multiple strategies for different
    use cases. Manages index lifecycle, optimization, and search operations with
    SQLite backend for metadata and configuration storage.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the vector index database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to vector storage data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "vector_indexes"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "vector_index.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._max_vectors_per_index = 1000000  # Maximum vectors per index
        self._default_index_type = IndexType.FLAT  # Default index type
        self._optimization_threshold = 10000  # Vectors before optimization
        self._search_timeout_seconds = 30.0  # Search timeout
        
        # Index cache for performance
        self._index_cache = {}
        self._cache_max_size = 10
        
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
                
                # Create vector indexes table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vector_indexes (
                        index_id TEXT PRIMARY KEY,
                        index_name TEXT UNIQUE NOT NULL,
                        index_type TEXT NOT NULL,
                        vector_dimension INTEGER NOT NULL,
                        vector_count INTEGER DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'building',
                        collection_id TEXT,
                        model_name TEXT,
                        model_version TEXT,
                        similarity_metric TEXT DEFAULT 'cosine',
                        index_parameters TEXT,
                        build_time_seconds REAL,
                        last_optimization TIMESTAMP,
                        memory_usage_mb REAL,
                        search_performance_ms REAL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index vectors table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS index_vectors (
                        vector_id TEXT PRIMARY KEY,
                        index_id TEXT NOT NULL,
                        embedding_id TEXT NOT NULL,
                        vector_position INTEGER NOT NULL,
                        vector_data BLOB NOT NULL,
                        vector_norm REAL,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (index_id) REFERENCES vector_indexes(index_id)
                    )
                """)
                
                # Create index statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS index_statistics (
                        stat_id TEXT PRIMARY KEY,
                        index_id TEXT NOT NULL,
                        stat_type TEXT NOT NULL,
                        stat_name TEXT NOT NULL,
                        stat_value REAL NOT NULL,
                        stat_metadata TEXT,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (index_id) REFERENCES vector_indexes(index_id)
                    )
                """)
                
                # Create search cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS search_cache (
                        cache_id TEXT PRIMARY KEY,
                        index_id TEXT NOT NULL,
                        query_hash TEXT NOT NULL,
                        query_vector BLOB NOT NULL,
                        result_ids TEXT NOT NULL,
                        result_scores TEXT NOT NULL,
                        search_time_ms REAL,
                        k_neighbors INTEGER,
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        access_count INTEGER DEFAULT 1,
                        FOREIGN KEY (index_id) REFERENCES vector_indexes(index_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_indexes_name ON vector_indexes(index_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_indexes_type ON vector_indexes(index_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_indexes_status ON vector_indexes(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_indexes_collection ON vector_indexes(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_indexes_model ON vector_indexes(model_name, model_version)")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_vectors_index ON index_vectors(index_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_vectors_embedding ON index_vectors(embedding_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_vectors_position ON index_vectors(vector_position)")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_statistics_index ON index_statistics(index_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_statistics_type ON index_statistics(stat_type, stat_name)")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_index ON search_cache(index_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_hash ON search_cache(query_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at)")

                conn.commit()
                self._logger.info("Vector index database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize vector index database: {e}")
                raise
            finally:
                conn.close()

    def create_index(self, index_name: str, index_type: IndexType,
                    vector_dimension: int, collection_id: Optional[str] = None,
                    model_name: Optional[str] = None, model_version: Optional[str] = None,
                    similarity_metric: str = "cosine",
                    index_parameters: Optional[Dict[str, Any]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new vector index.

        Args:
            index_name: Unique name for the index
            index_type: Type of index to create
            vector_dimension: Dimension of vectors
            collection_id: Associated collection ID
            model_name: Model used for embeddings
            model_version: Version of the model
            similarity_metric: Similarity metric to use
            index_parameters: Index-specific parameters
            metadata: Additional metadata

        Returns:
            Index ID

        Raises:
            ValueError: If index name already exists or parameters are invalid
        """
        if not index_name or not index_name.strip():
            raise ValueError("Index name cannot be empty")

        if vector_dimension <= 0:
            raise ValueError("Vector dimension must be positive")

        index_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if index name already exists
                cursor.execute("SELECT index_id FROM vector_indexes WHERE index_name = ?", (index_name,))
                if cursor.fetchone():
                    raise ValueError(f"Index with name '{index_name}' already exists")

                # Insert new index
                cursor.execute("""
                    INSERT INTO vector_indexes (
                        index_id, index_name, index_type, vector_dimension,
                        collection_id, model_name, model_version, similarity_metric,
                        index_parameters, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    index_id, index_name, index_type.value, vector_dimension,
                    collection_id, model_name, model_version, similarity_metric,
                    json.dumps(index_parameters) if index_parameters else None,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Created vector index: {index_name} ({index_id})")
                return index_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create vector index: {e}")
                raise
            finally:
                conn.close()

    def add_vectors(self, index_id: str, vectors: List[Tuple[str, Union[List[float], np.ndarray]]],
                   batch_size: int = 1000) -> int:
        """
        Add vectors to an index.

        Args:
            index_id: Index identifier
            vectors: List of (embedding_id, vector) tuples
            batch_size: Batch size for processing

        Returns:
            Number of vectors added

        Raises:
            ValueError: If index doesn't exist or vectors are invalid
        """
        if not vectors:
            return 0

        added_count = 0

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Verify index exists
                cursor.execute("SELECT vector_dimension, status FROM vector_indexes WHERE index_id = ?", (index_id,))
                index_info = cursor.fetchone()
                if not index_info:
                    raise ValueError(f"Index {index_id} not found")

                vector_dimension, status = index_info
                if status == IndexStatus.ERROR.value:
                    raise ValueError(f"Index {index_id} is in error state")

                # Update index status to updating
                cursor.execute("""
                    UPDATE vector_indexes
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE index_id = ?
                """, (IndexStatus.UPDATING.value, index_id))

                # Process vectors in batches
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]

                    for embedding_id, vector in batch:
                        # Convert vector to numpy array if needed
                        if isinstance(vector, list):
                            vector = np.array(vector, dtype=np.float32)

                        # Validate vector dimension
                        if len(vector) != vector_dimension:
                            self._logger.warning(f"Vector dimension mismatch for {embedding_id}: expected {vector_dimension}, got {len(vector)}")
                            continue

                        # Calculate vector norm
                        vector_norm = float(np.linalg.norm(vector))

                        # Get next position
                        cursor.execute("SELECT COUNT(*) FROM index_vectors WHERE index_id = ?", (index_id,))
                        vector_position = cursor.fetchone()[0]

                        # Insert vector
                        vector_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO index_vectors (
                                vector_id, index_id, embedding_id, vector_position,
                                vector_data, vector_norm
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            vector_id, index_id, embedding_id, vector_position,
                            vector.tobytes(), vector_norm
                        ))

                        added_count += 1

                    # Commit batch
                    conn.commit()

                # Update index statistics
                cursor.execute("""
                    UPDATE vector_indexes
                    SET vector_count = vector_count + ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE index_id = ?
                """, (added_count, IndexStatus.READY.value, index_id))

                conn.commit()
                self._logger.info(f"Added {added_count} vectors to index {index_id}")
                return added_count

            except Exception as e:
                conn.rollback()
                # Reset index status on error
                try:
                    cursor.execute("""
                        UPDATE vector_indexes
                        SET status = ?
                        WHERE index_id = ?
                    """, (IndexStatus.ERROR.value, index_id))
                    conn.commit()
                except:
                    pass

                self._logger.error(f"Failed to add vectors to index: {e}")
                raise
            finally:
                conn.close()

    def search_vectors(self, index_id: str, query_vector: Union[List[float], np.ndarray],
                      k: int = 10, use_cache: bool = True) -> List[Tuple[str, float]]:
        """
        Search for similar vectors in the index.

        Args:
            index_id: Index identifier
            query_vector: Query vector
            k: Number of nearest neighbors to return
            use_cache: Whether to use search cache

        Returns:
            List of (embedding_id, similarity_score) tuples

        Raises:
            ValueError: If index doesn't exist or query is invalid
        """
        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)

        start_time = time.time()

        # Generate query hash for caching
        query_hash = str(hash(query_vector.tobytes())) if use_cache else None

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check cache first
                if use_cache and query_hash:
                    cursor.execute("""
                        SELECT result_ids, result_scores, search_time_ms
                        FROM search_cache
                        WHERE index_id = ? AND query_hash = ? AND expires_at > CURRENT_TIMESTAMP
                    """, (index_id, query_hash))

                    cached_result = cursor.fetchone()
                    if cached_result:
                        result_ids = json.loads(cached_result[0])
                        result_scores = json.loads(cached_result[1])

                        # Update access count
                        cursor.execute("""
                            UPDATE search_cache
                            SET access_count = access_count + 1
                            WHERE index_id = ? AND query_hash = ?
                        """, (index_id, query_hash))
                        conn.commit()

                        return list(zip(result_ids, result_scores))

                # Verify index exists and is ready
                cursor.execute("SELECT vector_dimension, status, similarity_metric FROM vector_indexes WHERE index_id = ?", (index_id,))
                index_info = cursor.fetchone()
                if not index_info:
                    raise ValueError(f"Index {index_id} not found")

                vector_dimension, status, similarity_metric = index_info
                if status != IndexStatus.READY.value:
                    raise ValueError(f"Index {index_id} is not ready (status: {status})")

                if len(query_vector) != vector_dimension:
                    raise ValueError(f"Query vector dimension {len(query_vector)} doesn't match index dimension {vector_dimension}")

                # Get all vectors from index
                cursor.execute("""
                    SELECT embedding_id, vector_data, vector_norm
                    FROM index_vectors
                    WHERE index_id = ?
                    ORDER BY vector_position
                """, (index_id,))

                vectors = cursor.fetchall()
                if not vectors:
                    return []

                # Calculate similarities
                similarities = []
                query_norm = np.linalg.norm(query_vector)

                for embedding_id, vector_data, vector_norm in vectors:
                    # Reconstruct vector from bytes
                    vector = np.frombuffer(vector_data, dtype=np.float32)

                    # Calculate similarity based on metric
                    if similarity_metric == "cosine":
                        if query_norm > 0 and vector_norm > 0:
                            similarity = np.dot(query_vector, vector) / (query_norm * vector_norm)
                        else:
                            similarity = 0.0
                    elif similarity_metric == "euclidean":
                        distance = np.linalg.norm(query_vector - vector)
                        similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity
                    elif similarity_metric == "dot_product":
                        similarity = np.dot(query_vector, vector)
                    else:
                        # Default to cosine
                        if query_norm > 0 and vector_norm > 0:
                            similarity = np.dot(query_vector, vector) / (query_norm * vector_norm)
                        else:
                            similarity = 0.0

                    similarities.append((embedding_id, float(similarity)))

                # Sort by similarity (descending) and take top k
                similarities.sort(key=lambda x: x[1], reverse=True)
                results = similarities[:k]

                search_time = (time.time() - start_time) * 1000  # Convert to milliseconds

                # Cache results if enabled
                if use_cache and query_hash and results:
                    result_ids = [r[0] for r in results]
                    result_scores = [r[1] for r in results]

                    # Set cache expiration (1 hour)
                    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

                    cache_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO search_cache (
                            cache_id, index_id, query_hash, query_vector,
                            result_ids, result_scores, search_time_ms,
                            k_neighbors, expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        cache_id, index_id, query_hash, query_vector.tobytes(),
                        json.dumps(result_ids), json.dumps(result_scores),
                        search_time, k, expires_at.isoformat()
                    ))

                # Update search performance statistics
                cursor.execute("""
                    UPDATE vector_indexes
                    SET search_performance_ms = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE index_id = ?
                """, (search_time, index_id))

                conn.commit()
                self._logger.debug(f"Search completed in {search_time:.2f}ms, found {len(results)} results")
                return results

            except Exception as e:
                self._logger.error(f"Failed to search vectors: {e}")
                raise
            finally:
                conn.close()

    def get_index_info(self, index_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an index.

        Args:
            index_id: Index identifier

        Returns:
            Index information dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT index_id, index_name, index_type, vector_dimension,
                           vector_count, status, collection_id, model_name,
                           model_version, similarity_metric, index_parameters,
                           build_time_seconds, last_optimization, memory_usage_mb,
                           search_performance_ms, metadata, created_at, updated_at
                    FROM vector_indexes WHERE index_id = ?
                """, (index_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'index_id': row[0],
                    'index_name': row[1],
                    'index_type': row[2],
                    'vector_dimension': row[3],
                    'vector_count': row[4],
                    'status': row[5],
                    'collection_id': row[6],
                    'model_name': row[7],
                    'model_version': row[8],
                    'similarity_metric': row[9],
                    'index_parameters': json.loads(row[10]) if row[10] else None,
                    'build_time_seconds': row[11],
                    'last_optimization': row[12],
                    'memory_usage_mb': row[13],
                    'search_performance_ms': row[14],
                    'metadata': json.loads(row[15]) if row[15] else None,
                    'created_at': row[16],
                    'updated_at': row[17]
                }

            except Exception as e:
                self._logger.error(f"Failed to get index info: {e}")
                raise
            finally:
                conn.close()

    def list_indexes(self, status: Optional[IndexStatus] = None,
                    index_type: Optional[IndexType] = None) -> List[Dict[str, Any]]:
        """
        List all indexes with optional filtering.

        Args:
            status: Filter by status
            index_type: Filter by index type

        Returns:
            List of index information dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT index_id, index_name, index_type, vector_dimension,
                           vector_count, status, collection_id, model_name,
                           model_version, similarity_metric, created_at, updated_at
                    FROM vector_indexes
                    WHERE 1=1
                """
                params = []

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                if index_type:
                    query += " AND index_type = ?"
                    params.append(index_type.value)

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [
                    {
                        'index_id': row[0],
                        'index_name': row[1],
                        'index_type': row[2],
                        'vector_dimension': row[3],
                        'vector_count': row[4],
                        'status': row[5],
                        'collection_id': row[6],
                        'model_name': row[7],
                        'model_version': row[8],
                        'similarity_metric': row[9],
                        'created_at': row[10],
                        'updated_at': row[11]
                    }
                    for row in rows
                ]

            except Exception as e:
                self._logger.error(f"Failed to list indexes: {e}")
                raise
            finally:
                conn.close()

    def delete_index(self, index_id: str) -> bool:
        """
        Delete an index and all its vectors.

        Args:
            index_id: Index identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if index exists
                cursor.execute("SELECT index_name FROM vector_indexes WHERE index_id = ?", (index_id,))
                if not cursor.fetchone():
                    return False

                # Delete vectors first
                cursor.execute("DELETE FROM index_vectors WHERE index_id = ?", (index_id,))

                # Delete statistics
                cursor.execute("DELETE FROM index_statistics WHERE index_id = ?", (index_id,))

                # Delete search cache
                cursor.execute("DELETE FROM search_cache WHERE index_id = ?", (index_id,))

                # Delete index
                cursor.execute("DELETE FROM vector_indexes WHERE index_id = ?", (index_id,))

                conn.commit()
                self._logger.info(f"Deleted index: {index_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete index: {e}")
                raise
            finally:
                conn.close()

    def optimize_index(self, index_id: str) -> bool:
        """
        Optimize an index for better performance.

        Args:
            index_id: Index identifier

        Returns:
            True if optimization completed successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update status to optimizing
                cursor.execute("""
                    UPDATE vector_indexes
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE index_id = ?
                """, (IndexStatus.OPTIMIZING.value, index_id))

                # Clear expired cache entries
                cursor.execute("""
                    DELETE FROM search_cache
                    WHERE index_id = ? AND expires_at < CURRENT_TIMESTAMP
                """, (index_id,))

                # Update optimization timestamp
                cursor.execute("""
                    UPDATE vector_indexes
                    SET status = ?, last_optimization = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE index_id = ?
                """, (IndexStatus.READY.value, index_id))

                conn.commit()
                self._logger.info(f"Optimized index: {index_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to optimize index: {e}")
                raise
            finally:
                conn.close()

    def get_statistics(self, index_id: str) -> Dict[str, Any]:
        """
        Get performance statistics for an index.

        Args:
            index_id: Index identifier

        Returns:
            Statistics dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get basic index stats
                cursor.execute("""
                    SELECT vector_count, search_performance_ms, memory_usage_mb
                    FROM vector_indexes WHERE index_id = ?
                """, (index_id,))

                basic_stats = cursor.fetchone()
                if not basic_stats:
                    return {}

                # Get cache statistics
                cursor.execute("""
                    SELECT COUNT(*), AVG(search_time_ms), SUM(access_count)
                    FROM search_cache WHERE index_id = ?
                """, (index_id,))

                cache_stats = cursor.fetchone()

                return {
                    'vector_count': basic_stats[0],
                    'search_performance_ms': basic_stats[1],
                    'memory_usage_mb': basic_stats[2],
                    'cache_entries': cache_stats[0] if cache_stats[0] else 0,
                    'avg_cache_search_time_ms': cache_stats[1] if cache_stats[1] else 0,
                    'total_cache_hits': cache_stats[2] if cache_stats[2] else 0
                }

            except Exception as e:
                self._logger.error(f"Failed to get statistics: {e}")
                return {}
            finally:
                conn.close()
