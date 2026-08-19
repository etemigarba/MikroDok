"""
Module: embedding_repository_db
Description: Repository pattern for managing document embeddings persistence
Phase: 4
Location: /src/modules/database/vector_storage_db/embedding_repository_db/
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

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class EmbeddingStatus(Enum):
    """Status of embedding processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    OUTDATED = "outdated"


class SimilarityMetric(Enum):
    """Supported similarity metrics."""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"


class EmbeddingRepositoryDB:
    """
    Repository pattern for managing document embeddings persistence.
    
    Provides high-dimensional vector storage with efficient similarity search support.
    Manages embedding metadata, versioning, and lifecycle operations with SQLite backend.
    Designed for offline operation with optimized indexing and caching.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the embedding repository database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to vector storage data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "embeddings"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "embedding_repository.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._embedding_retention_days = 365  # Keep embeddings for 1 year
        self._max_batch_size = 1000  # Maximum batch size for operations
        self._similarity_threshold = 0.7  # Default similarity threshold
        
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
                
                # Create embeddings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        embedding_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        chunk_id TEXT,
                        model_name TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        embedding_vector BLOB NOT NULL,
                        vector_dimension INTEGER NOT NULL,
                        status TEXT NOT NULL DEFAULT 'completed',
                        similarity_metric TEXT DEFAULT 'cosine',
                        processing_time_ms INTEGER,
                        memory_usage_mb REAL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """)
                
                # Create embedding collections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_collections (
                        collection_id TEXT PRIMARY KEY,
                        collection_name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        model_name TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        vector_dimension INTEGER NOT NULL,
                        similarity_metric TEXT DEFAULT 'cosine',
                        embedding_count INTEGER DEFAULT 0,
                        total_size_mb REAL DEFAULT 0.0,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create embedding statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_statistics (
                        stat_id TEXT PRIMARY KEY,
                        collection_id TEXT,
                        embedding_id TEXT,
                        stat_type TEXT NOT NULL,
                        stat_name TEXT NOT NULL,
                        stat_value REAL NOT NULL,
                        stat_metadata TEXT,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES embedding_collections(collection_id),
                        FOREIGN KEY (embedding_id) REFERENCES embeddings(embedding_id)
                    )
                """)
                
                # Create similarity cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS similarity_cache (
                        cache_id TEXT PRIMARY KEY,
                        query_embedding_id TEXT NOT NULL,
                        target_embedding_id TEXT NOT NULL,
                        similarity_score REAL NOT NULL,
                        similarity_metric TEXT NOT NULL,
                        computation_time_ms INTEGER,
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        FOREIGN KEY (query_embedding_id) REFERENCES embeddings(embedding_id),
                        FOREIGN KEY (target_embedding_id) REFERENCES embeddings(embedding_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_document_id ON embeddings(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON embeddings(chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_name, model_version)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_status ON embeddings(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON embeddings(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_expires_at ON embeddings(expires_at)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_name ON embedding_collections(collection_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_model ON embedding_collections(model_name, model_version)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_collection ON embedding_statistics(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_embedding ON embedding_statistics(embedding_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_type ON embedding_statistics(stat_type, stat_name)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_query ON similarity_cache(query_embedding_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_target ON similarity_cache(target_embedding_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_score ON similarity_cache(similarity_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_expires ON similarity_cache(expires_at)")
                
                conn.commit()
                self._logger.info("Embedding repository database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize embedding repository database: {e}")
                raise
            finally:
                conn.close()
    
    def store_embedding(self, document_id: str, embedding_vector: Union[List[float], np.ndarray],
                       model_name: str, model_version: str, chunk_id: Optional[str] = None,
                       status: EmbeddingStatus = EmbeddingStatus.COMPLETED,
                       similarity_metric: SimilarityMetric = SimilarityMetric.COSINE,
                       processing_time_ms: Optional[int] = None,
                       memory_usage_mb: Optional[float] = None,
                       metadata: Optional[Dict[str, Any]] = None,
                       expires_at: Optional[datetime] = None) -> str:
        """
        Store an embedding vector in the repository.
        
        Args:
            document_id: Document identifier
            embedding_vector: Vector representation
            model_name: Name of the embedding model
            model_version: Version of the embedding model
            chunk_id: Optional chunk identifier
            status: Processing status
            similarity_metric: Similarity metric used
            processing_time_ms: Processing time in milliseconds
            memory_usage_mb: Memory usage in MB
            metadata: Additional metadata
            expires_at: Expiration timestamp
            
        Returns:
            Embedding ID
        """
        embedding_id = str(uuid.uuid4())
        
        # Convert numpy array to list if needed
        if isinstance(embedding_vector, np.ndarray):
            embedding_vector = embedding_vector.tolist()
        
        # Serialize vector as JSON for storage
        vector_blob = json.dumps(embedding_vector).encode('utf-8')
        vector_dimension = len(embedding_vector)
        
        # Set default expiration if not provided
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=self._embedding_retention_days)
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO embeddings (
                        embedding_id, document_id, chunk_id, model_name, model_version,
                        embedding_vector, vector_dimension, status, similarity_metric,
                        processing_time_ms, memory_usage_mb, metadata, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    embedding_id, document_id, chunk_id, model_name, model_version,
                    vector_blob, vector_dimension, status.value, similarity_metric.value,
                    processing_time_ms, memory_usage_mb,
                    json.dumps(metadata) if metadata else None, expires_at
                ))
                
                conn.commit()
                self._logger.info(f"Stored embedding {embedding_id} for document {document_id}")
                return embedding_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store embedding for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_embedding(self, embedding_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an embedding by ID.

        Args:
            embedding_id: Embedding identifier

        Returns:
            Embedding data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT embedding_id, document_id, chunk_id, model_name, model_version,
                           embedding_vector, vector_dimension, status, similarity_metric,
                           processing_time_ms, memory_usage_mb, metadata, created_at,
                           updated_at, expires_at
                    FROM embeddings
                    WHERE embedding_id = ?
                """, (embedding_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Deserialize vector
                vector_blob = row[5]
                embedding_vector = json.loads(vector_blob.decode('utf-8'))

                return {
                    'embedding_id': row[0],
                    'document_id': row[1],
                    'chunk_id': row[2],
                    'model_name': row[3],
                    'model_version': row[4],
                    'embedding_vector': embedding_vector,
                    'vector_dimension': row[6],
                    'status': row[7],
                    'similarity_metric': row[8],
                    'processing_time_ms': row[9],
                    'memory_usage_mb': row[10],
                    'metadata': json.loads(row[11]) if row[11] else None,
                    'created_at': row[12],
                    'updated_at': row[13],
                    'expires_at': row[14]
                }

            except Exception as e:
                self._logger.error(f"Failed to get embedding {embedding_id}: {e}")
                return None
            finally:
                conn.close()

    def get_embeddings_by_document(self, document_id: str,
                                  model_name: Optional[str] = None,
                                  model_version: Optional[str] = None,
                                  status: Optional[EmbeddingStatus] = None) -> List[Dict[str, Any]]:
        """
        Get all embeddings for a document.

        Args:
            document_id: Document identifier
            model_name: Filter by model name
            model_version: Filter by model version
            status: Filter by status

        Returns:
            List of embedding dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with optional filters
                query = """
                    SELECT embedding_id, document_id, chunk_id, model_name, model_version,
                           embedding_vector, vector_dimension, status, similarity_metric,
                           processing_time_ms, memory_usage_mb, metadata, created_at,
                           updated_at, expires_at
                    FROM embeddings
                    WHERE document_id = ?
                """
                params = [document_id]

                if model_name:
                    query += " AND model_name = ?"
                    params.append(model_name)

                if model_version:
                    query += " AND model_version = ?"
                    params.append(model_version)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                embeddings = []
                for row in rows:
                    # Deserialize vector
                    vector_blob = row[5]
                    embedding_vector = json.loads(vector_blob.decode('utf-8'))

                    embeddings.append({
                        'embedding_id': row[0],
                        'document_id': row[1],
                        'chunk_id': row[2],
                        'model_name': row[3],
                        'model_version': row[4],
                        'embedding_vector': embedding_vector,
                        'vector_dimension': row[6],
                        'status': row[7],
                        'similarity_metric': row[8],
                        'processing_time_ms': row[9],
                        'memory_usage_mb': row[10],
                        'metadata': json.loads(row[11]) if row[11] else None,
                        'created_at': row[12],
                        'updated_at': row[13],
                        'expires_at': row[14]
                    })

                return embeddings

            except Exception as e:
                self._logger.error(f"Failed to get embeddings for document {document_id}: {e}")
                return []
            finally:
                conn.close()

    def update_embedding_status(self, embedding_id: str, status: EmbeddingStatus,
                               processing_time_ms: Optional[int] = None,
                               memory_usage_mb: Optional[float] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update embedding status and metadata.

        Args:
            embedding_id: Embedding identifier
            status: New status
            processing_time_ms: Processing time in milliseconds
            memory_usage_mb: Memory usage in MB
            metadata: Additional metadata

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build update query
                update_fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
                params = [status.value]

                if processing_time_ms is not None:
                    update_fields.append("processing_time_ms = ?")
                    params.append(processing_time_ms)

                if memory_usage_mb is not None:
                    update_fields.append("memory_usage_mb = ?")
                    params.append(memory_usage_mb)

                if metadata is not None:
                    update_fields.append("metadata = ?")
                    params.append(json.dumps(metadata))

                params.append(embedding_id)

                query = f"UPDATE embeddings SET {', '.join(update_fields)} WHERE embedding_id = ?"

                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    self._logger.warning(f"No embedding found with ID {embedding_id}")
                    return False

                conn.commit()
                self._logger.info(f"Updated embedding {embedding_id} status to {status.value}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update embedding {embedding_id}: {e}")
                return False
            finally:
                conn.close()

    def delete_embedding(self, embedding_id: str) -> bool:
        """
        Delete an embedding from the repository.

        Args:
            embedding_id: Embedding identifier

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete related records first
                cursor.execute("DELETE FROM similarity_cache WHERE query_embedding_id = ? OR target_embedding_id = ?",
                             (embedding_id, embedding_id))
                cursor.execute("DELETE FROM embedding_statistics WHERE embedding_id = ?", (embedding_id,))
                cursor.execute("DELETE FROM embeddings WHERE embedding_id = ?", (embedding_id,))

                if cursor.rowcount == 0:
                    self._logger.warning(f"No embedding found with ID {embedding_id}")
                    return False

                conn.commit()
                self._logger.info(f"Deleted embedding {embedding_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete embedding {embedding_id}: {e}")
                return False
            finally:
                conn.close()

    def delete_embeddings_by_document(self, document_id: str) -> int:
        """
        Delete all embeddings for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of embeddings deleted
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get embedding IDs first
                cursor.execute("SELECT embedding_id FROM embeddings WHERE document_id = ?", (document_id,))
                embedding_ids = [row[0] for row in cursor.fetchall()]

                if not embedding_ids:
                    return 0

                # Delete related records
                placeholders = ','.join(['?'] * len(embedding_ids))
                cursor.execute(f"DELETE FROM similarity_cache WHERE query_embedding_id IN ({placeholders}) OR target_embedding_id IN ({placeholders})",
                             embedding_ids + embedding_ids)
                cursor.execute(f"DELETE FROM embedding_statistics WHERE embedding_id IN ({placeholders})", embedding_ids)
                cursor.execute("DELETE FROM embeddings WHERE document_id = ?", (document_id,))

                deleted_count = cursor.rowcount
                conn.commit()
                self._logger.info(f"Deleted {deleted_count} embeddings for document {document_id}")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete embeddings for document {document_id}: {e}")
                return 0
            finally:
                conn.close()

    def create_collection(self, collection_name: str, model_name: str, model_version: str,
                         vector_dimension: int, description: Optional[str] = None,
                         similarity_metric: SimilarityMetric = SimilarityMetric.COSINE,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new embedding collection.

        Args:
            collection_name: Unique collection name
            model_name: Embedding model name
            model_version: Embedding model version
            vector_dimension: Vector dimension
            description: Collection description
            similarity_metric: Default similarity metric
            metadata: Additional metadata

        Returns:
            Collection ID
        """
        collection_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO embedding_collections (
                        collection_id, collection_name, description, model_name,
                        model_version, vector_dimension, similarity_metric, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    collection_id, collection_name, description, model_name,
                    model_version, vector_dimension, similarity_metric.value,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Created embedding collection {collection_name} with ID {collection_id}")
                return collection_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
            finally:
                conn.close()

    def get_collection(self, collection_name: str) -> Optional[Dict[str, Any]]:
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
                    SELECT collection_id, collection_name, description, model_name,
                           model_version, vector_dimension, similarity_metric,
                           embedding_count, total_size_mb, metadata, created_at, updated_at
                    FROM embedding_collections
                    WHERE collection_name = ?
                """, (collection_name,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'collection_id': row[0],
                    'collection_name': row[1],
                    'description': row[2],
                    'model_name': row[3],
                    'model_version': row[4],
                    'vector_dimension': row[5],
                    'similarity_metric': row[6],
                    'embedding_count': row[7],
                    'total_size_mb': row[8],
                    'metadata': json.loads(row[9]) if row[9] else None,
                    'created_at': row[10],
                    'updated_at': row[11]
                }

            except Exception as e:
                self._logger.error(f"Failed to get collection {collection_name}: {e}")
                return None
            finally:
                conn.close()

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all embedding collections.

        Returns:
            List of collection dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT collection_id, collection_name, description, model_name,
                           model_version, vector_dimension, similarity_metric,
                           embedding_count, total_size_mb, metadata, created_at, updated_at
                    FROM embedding_collections
                    ORDER BY created_at DESC
                """)

                collections = []
                for row in cursor.fetchall():
                    collections.append({
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'description': row[2],
                        'model_name': row[3],
                        'model_version': row[4],
                        'vector_dimension': row[5],
                        'similarity_metric': row[6],
                        'embedding_count': row[7],
                        'total_size_mb': row[8],
                        'metadata': json.loads(row[9]) if row[9] else None,
                        'created_at': row[10],
                        'updated_at': row[11]
                    })

                return collections

            except Exception as e:
                self._logger.error(f"Failed to list collections: {e}")
                return []
            finally:
                conn.close()

    def cleanup_expired_embeddings(self) -> int:
        """
        Remove expired embeddings from the repository.

        Returns:
            Number of embeddings cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                current_time = datetime.now(timezone.utc)

                # Get expired embedding IDs
                cursor.execute("SELECT embedding_id FROM embeddings WHERE expires_at < ?", (current_time,))
                expired_ids = [row[0] for row in cursor.fetchall()]

                if not expired_ids:
                    return 0

                # Delete related records
                placeholders = ','.join(['?'] * len(expired_ids))
                cursor.execute(f"DELETE FROM similarity_cache WHERE query_embedding_id IN ({placeholders}) OR target_embedding_id IN ({placeholders})",
                             expired_ids + expired_ids)
                cursor.execute(f"DELETE FROM embedding_statistics WHERE embedding_id IN ({placeholders})", expired_ids)
                cursor.execute("DELETE FROM embeddings WHERE expires_at < ?", (current_time,))

                cleaned_count = cursor.rowcount
                conn.commit()
                self._logger.info(f"Cleaned up {cleaned_count} expired embeddings")
                return cleaned_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup expired embeddings: {e}")
                return 0
            finally:
                conn.close()

    def get_repository_statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics and metrics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get basic counts
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                total_embeddings = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM embedding_collections")
                total_collections = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM embeddings WHERE status = 'completed'")
                completed_embeddings = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM embeddings WHERE status = 'failed'")
                failed_embeddings = cursor.fetchone()[0]

                # Get size statistics
                cursor.execute("SELECT SUM(LENGTH(embedding_vector)) FROM embeddings")
                total_size_bytes = cursor.fetchone()[0] or 0

                # Get model distribution
                cursor.execute("""
                    SELECT model_name, model_version, COUNT(*)
                    FROM embeddings
                    GROUP BY model_name, model_version
                """)
                model_distribution = {}
                for row in cursor.fetchall():
                    model_key = f"{row[0]}:{row[1]}"
                    model_distribution[model_key] = row[2]

                # Get recent activity
                cursor.execute("""
                    SELECT COUNT(*) FROM embeddings
                    WHERE created_at > datetime('now', '-24 hours')
                """)
                recent_embeddings = cursor.fetchone()[0]

                return {
                    'total_embeddings': total_embeddings,
                    'total_collections': total_collections,
                    'completed_embeddings': completed_embeddings,
                    'failed_embeddings': failed_embeddings,
                    'total_size_bytes': total_size_bytes,
                    'total_size_mb': total_size_bytes / (1024 * 1024),
                    'model_distribution': model_distribution,
                    'recent_embeddings_24h': recent_embeddings,
                    'completion_rate': (completed_embeddings / total_embeddings * 100) if total_embeddings > 0 else 0
                }

            except Exception as e:
                self._logger.error(f"Failed to get repository statistics: {e}")
                return {}
            finally:
                conn.close()

    def search_similar_embeddings(self, query_vector: Union[List[float], np.ndarray],
                                 model_name: str, model_version: str,
                                 limit: int = 10, similarity_threshold: float = 0.7,
                                 document_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings using vector similarity.

        Note: This is a basic implementation. For production use, consider
        integrating with specialized vector databases like ChromaDB or Faiss.

        Args:
            query_vector: Query vector
            model_name: Model name to search within
            model_version: Model version to search within
            limit: Maximum number of results
            similarity_threshold: Minimum similarity threshold
            document_ids: Optional list of document IDs to search within

        Returns:
            List of similar embeddings with similarity scores
        """
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query
                query = """
                    SELECT embedding_id, document_id, chunk_id, embedding_vector,
                           metadata, created_at
                    FROM embeddings
                    WHERE model_name = ? AND model_version = ? AND status = 'completed'
                """
                params = [model_name, model_version]

                if document_ids:
                    placeholders = ','.join(['?'] * len(document_ids))
                    query += f" AND document_id IN ({placeholders})"
                    params.extend(document_ids)

                cursor.execute(query, params)

                similar_embeddings = []
                for row in cursor.fetchall():
                    # Deserialize stored vector
                    stored_vector = json.loads(row[3].decode('utf-8'))

                    # Calculate cosine similarity (basic implementation)
                    similarity = self._calculate_cosine_similarity(query_vector, stored_vector)

                    if similarity >= similarity_threshold:
                        similar_embeddings.append({
                            'embedding_id': row[0],
                            'document_id': row[1],
                            'chunk_id': row[2],
                            'similarity_score': similarity,
                            'metadata': json.loads(row[4]) if row[4] else None,
                            'created_at': row[5]
                        })

                # Sort by similarity score and limit results
                similar_embeddings.sort(key=lambda x: x['similarity_score'], reverse=True)
                return similar_embeddings[:limit]

            except Exception as e:
                self._logger.error(f"Failed to search similar embeddings: {e}")
                return []
            finally:
                conn.close()

    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score
        """
        try:
            # Convert to numpy arrays for efficient computation
            a = np.array(vec1)
            b = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return dot_product / (norm_a * norm_b)

        except Exception as e:
            self._logger.error(f"Failed to calculate cosine similarity: {e}")
            return 0.0

    def close(self) -> None:
        """Close database connections and clean up resources."""
        try:
            # No persistent connections to close in this implementation
            self._logger.info("Embedding repository closed")
        except Exception as e:
            self._logger.error(f"Error closing embedding repository: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
