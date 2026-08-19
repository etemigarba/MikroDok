"""
Module: embedding_cache_db
Description: Persists computed embeddings to avoid recomputation during RAG operations
Phase: 4
Location: /src/modules/database/cache_persistence_db/embedding_cache_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import time
import zlib
import struct
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Set
import hashlib

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
from src.modules.database.database_core_db.connection_manager_db.connection_manager_db import (
    ConnectionManagerDB, ConnectionType
)


class EmbeddingType(Enum):
    """Embedding type enumeration."""
    DOCUMENT = "document"
    CHUNK = "chunk"
    QUERY = "query"
    SENTENCE = "sentence"
    TOKEN = "token"


class CompressionMethod(Enum):
    """Compression method enumeration."""
    NONE = "none"
    ZLIB = "zlib"
    QUANTIZED = "quantized"
    SPARSE = "sparse"


@dataclass
class EmbeddingCacheEntry:
    """Embedding cache entry data structure."""
    cache_key: str
    chunk_id: str
    document_id: str
    embedding_model: str
    embedding_type: EmbeddingType
    embedding_vector: np.ndarray
    vector_dimension: int
    compression_method: CompressionMethod
    compressed_size_bytes: int
    original_size_bytes: int
    text_content: str
    text_hash: str
    access_count: int
    hit_count: int
    last_accessed: datetime
    created_at: datetime
    expires_at: Optional[datetime]
    metadata: Dict[str, Any]
    tags: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return {
            'cache_key': self.cache_key,
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'embedding_model': self.embedding_model,
            'embedding_type': self.embedding_type.value,
            'vector_dimension': self.vector_dimension,
            'compression_method': self.compression_method.value,
            'compressed_size_bytes': self.compressed_size_bytes,
            'original_size_bytes': self.original_size_bytes,
            'text_content': self.text_content,
            'text_hash': self.text_hash,
            'access_count': self.access_count,
            'hit_count': self.hit_count,
            'last_accessed': self.last_accessed.isoformat(),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'metadata': self.metadata,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], embedding_vector: np.ndarray) -> 'EmbeddingCacheEntry':
        """Create entry from dictionary and vector."""
        return cls(
            cache_key=data['cache_key'],
            chunk_id=data['chunk_id'],
            document_id=data['document_id'],
            embedding_model=data['embedding_model'],
            embedding_type=EmbeddingType(data['embedding_type']),
            embedding_vector=embedding_vector,
            vector_dimension=data['vector_dimension'],
            compression_method=CompressionMethod(data['compression_method']),
            compressed_size_bytes=data['compressed_size_bytes'],
            original_size_bytes=data['original_size_bytes'],
            text_content=data['text_content'],
            text_hash=data['text_hash'],
            access_count=data['access_count'],
            hit_count=data['hit_count'],
            last_accessed=datetime.fromisoformat(data['last_accessed']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None,
            metadata=data['metadata'],
            tags=data['tags']
        )


@dataclass
class EmbeddingCacheStats:
    """Embedding cache statistics data structure."""
    total_entries: int
    active_entries: int
    expired_entries: int
    total_size_bytes: int
    compressed_size_bytes: int
    total_vectors: int
    average_dimension: float
    hit_rate: float
    miss_rate: float
    compression_ratio: float
    cache_efficiency: float
    last_cleanup: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return asdict(self)


class EmbeddingCacheDB:
    """
    Persistent storage for computed embeddings to avoid recomputation during RAG operations.
    
    Provides high-performance caching of embedding vectors with compression, batch operations,
    and intelligent memory management. Optimized for machine learning workloads with
    large embedding vectors and frequent similarity searches.
    """
    
    def __init__(self, db_path: Optional[Path] = None,
                 max_cache_size_mb: int = 1000,
                 default_ttl_hours: int = 168,  # 1 week
                 compression_threshold_kb: int = 4,
                 cleanup_interval_minutes: int = 60):
        """
        Initialize embedding cache database.
        
        Args:
            db_path: Path to SQLite database file
            max_cache_size_mb: Maximum cache size in megabytes
            default_ttl_hours: Default TTL for cache entries in hours
            compression_threshold_kb: Compress vectors larger than this (KB)
            cleanup_interval_minutes: Cleanup interval in minutes
        """
        self._logger = get_logger(__name__)
        
        # Configuration
        self._db_path = db_path or Path("data/cache/embedding_cache.db")
        self._max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self._default_ttl = timedelta(hours=default_ttl_hours)
        self._compression_threshold = compression_threshold_kb * 1024
        self._cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Connection manager
        self._connection_manager: Optional[ConnectionManagerDB] = None
        
        # Background cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Statistics
        self._stats_cache: Optional[EmbeddingCacheStats] = None
        self._stats_last_updated: Optional[datetime] = None
        
        # Initialize database
        self._initialize_database()
        self._start_cleanup_thread()
        
        self._logger.info(f"EmbeddingCacheDB initialized with max size: {max_cache_size_mb}MB")
    
    def _initialize_database(self) -> None:
        """Initialize database schema and connection manager."""
        try:
            # Ensure directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Initialize connection manager
            self._connection_manager = ConnectionManagerDB(
                db_path=self._db_path,
                max_connections=10,
                connection_timeout=30.0
            )
            
            # Create schema
            self._create_schema()
            
            self._logger.info("Embedding cache database initialized successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize embedding cache database: {e}")
            raise
    
    def _create_schema(self) -> None:
        """Create database schema for embedding cache."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS embedding_cache (
            cache_key TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_type TEXT NOT NULL,
            embedding_vector BLOB NOT NULL,
            vector_dimension INTEGER NOT NULL,
            compression_method TEXT NOT NULL,
            compressed_size_bytes INTEGER NOT NULL,
            original_size_bytes INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            access_count INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP,
            metadata TEXT NOT NULL,
            tags TEXT NOT NULL,
            UNIQUE(chunk_id, embedding_model)
        );
        
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_chunk_id ON embedding_cache(chunk_id);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_document_id ON embedding_cache(document_id);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_embedding_model ON embedding_cache(embedding_model);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_embedding_type ON embedding_cache(embedding_type);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_text_hash ON embedding_cache(text_hash);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_expires_at ON embedding_cache(expires_at);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_last_accessed ON embedding_cache(last_accessed);
        CREATE INDEX IF NOT EXISTS idx_embedding_cache_created_at ON embedding_cache(created_at);
        
        CREATE TABLE IF NOT EXISTS cache_stats (
            id INTEGER PRIMARY KEY,
            total_entries INTEGER NOT NULL,
            active_entries INTEGER NOT NULL,
            expired_entries INTEGER NOT NULL,
            total_size_bytes INTEGER NOT NULL,
            compressed_size_bytes INTEGER NOT NULL,
            total_vectors INTEGER NOT NULL,
            average_dimension REAL NOT NULL,
            hit_rate REAL NOT NULL,
            miss_rate REAL NOT NULL,
            compression_ratio REAL NOT NULL,
            cache_efficiency REAL NOT NULL,
            last_cleanup TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
        """
        
        with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def _generate_cache_key(self, chunk_id: str, embedding_model: str) -> str:
        """Generate cache key for embedding."""
        key_data = f"{chunk_id}:{embedding_model}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def _calculate_text_hash(self, text_content: str) -> str:
        """Calculate hash for text content."""
        return hashlib.sha256(text_content.encode()).hexdigest()

    def _compress_vector(self, vector: np.ndarray) -> Tuple[bytes, CompressionMethod, int]:
        """Compress embedding vector if beneficial."""
        original_bytes = vector.tobytes()
        original_size = len(original_bytes)

        if original_size < self._compression_threshold:
            return original_bytes, CompressionMethod.NONE, original_size

        # Try zlib compression
        compressed = zlib.compress(original_bytes, level=6)

        if len(compressed) < original_size * 0.8:  # Only compress if >20% reduction
            return compressed, CompressionMethod.ZLIB, original_size
        else:
            return original_bytes, CompressionMethod.NONE, original_size

    def _decompress_vector(self, data: bytes, compression_method: CompressionMethod,
                          vector_dimension: int, dtype: np.dtype = np.float32) -> np.ndarray:
        """Decompress embedding vector."""
        if compression_method == CompressionMethod.ZLIB:
            decompressed = zlib.decompress(data)
            return np.frombuffer(decompressed, dtype=dtype).reshape(-1)
        else:
            return np.frombuffer(data, dtype=dtype).reshape(-1)

    def put(self, chunk_id: str, document_id: str, embedding_model: str,
            embedding_vector: np.ndarray, text_content: str,
            embedding_type: EmbeddingType = EmbeddingType.CHUNK,
            ttl_hours: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None,
            tags: Optional[List[str]] = None) -> bool:
        """
        Store embedding in cache.

        Args:
            chunk_id: Unique chunk identifier
            document_id: Document identifier
            embedding_model: Model used to generate embedding
            embedding_vector: Embedding vector as numpy array
            text_content: Original text content
            embedding_type: Type of embedding
            ttl_hours: Time-to-live in hours (uses default if None)
            metadata: Additional metadata dictionary
            tags: List of tags for categorization

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self._lock:
                cache_key = self._generate_cache_key(chunk_id, embedding_model)
                text_hash = self._calculate_text_hash(text_content)

                # Compress vector
                compressed_data, compression_method, original_size = self._compress_vector(embedding_vector)

                now = datetime.now(timezone.utc)
                ttl = timedelta(hours=ttl_hours) if ttl_hours else self._default_ttl
                expires_at = now + ttl

                entry = EmbeddingCacheEntry(
                    cache_key=cache_key,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    embedding_model=embedding_model,
                    embedding_type=embedding_type,
                    embedding_vector=embedding_vector,
                    vector_dimension=len(embedding_vector),
                    compression_method=compression_method,
                    compressed_size_bytes=len(compressed_data),
                    original_size_bytes=original_size,
                    text_content=text_content,
                    text_hash=text_hash,
                    access_count=0,
                    hit_count=0,
                    last_accessed=now,
                    created_at=now,
                    expires_at=expires_at,
                    metadata=metadata or {},
                    tags=tags or []
                )

                # Check cache size limits
                if not self._check_cache_limits(len(compressed_data)):
                    self._evict_entries(len(compressed_data))

                # Insert or update entry
                sql = """
                INSERT OR REPLACE INTO embedding_cache (
                    cache_key, chunk_id, document_id, embedding_model, embedding_type,
                    embedding_vector, vector_dimension, compression_method,
                    compressed_size_bytes, original_size_bytes, text_content, text_hash,
                    access_count, hit_count, last_accessed, created_at, expires_at,
                    metadata, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params = (
                    entry.cache_key, entry.chunk_id, entry.document_id,
                    entry.embedding_model, entry.embedding_type.value,
                    compressed_data, entry.vector_dimension, entry.compression_method.value,
                    entry.compressed_size_bytes, entry.original_size_bytes,
                    entry.text_content, entry.text_hash, entry.access_count,
                    entry.hit_count, entry.last_accessed, entry.created_at,
                    entry.expires_at, json.dumps(entry.metadata), json.dumps(entry.tags)
                )

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    conn.execute(sql, params)
                    conn.commit()

                self._invalidate_stats_cache()
                self._logger.debug(f"Stored embedding cache entry: {chunk_id}:{embedding_model}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to store embedding cache entry {chunk_id}: {e}")
            return False

    def get(self, chunk_id: str, embedding_model: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding from cache.

        Args:
            chunk_id: Chunk identifier
            embedding_model: Model identifier

        Returns:
            Embedding vector if found and valid, None otherwise
        """
        try:
            with self._lock:
                cache_key = self._generate_cache_key(chunk_id, embedding_model)

                sql = """
                SELECT embedding_vector, compression_method, vector_dimension, expires_at, cache_key
                FROM embedding_cache
                WHERE cache_key = ?
                """

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql, (cache_key,))
                    row = cursor.fetchone()

                if not row:
                    return None

                vector_data, compression_method, vector_dimension, expires_at, cache_key = row

                # Check expiration
                if expires_at:
                    expires_dt = datetime.fromisoformat(expires_at)
                    if datetime.now(timezone.utc) > expires_dt:
                        self._mark_expired(cache_key)
                        return None

                # Update access statistics
                self._update_access_stats(cache_key)

                # Decompress and return vector
                compression_enum = CompressionMethod(compression_method)
                return self._decompress_vector(vector_data, compression_enum, vector_dimension)

        except Exception as e:
            self._logger.error(f"Failed to retrieve embedding cache entry {chunk_id}: {e}")
            return None

    def get_entry(self, chunk_id: str, embedding_model: str) -> Optional[EmbeddingCacheEntry]:
        """
        Retrieve full embedding cache entry.

        Args:
            chunk_id: Chunk identifier
            embedding_model: Model identifier

        Returns:
            EmbeddingCacheEntry if found and valid, None otherwise
        """
        try:
            with self._lock:
                cache_key = self._generate_cache_key(chunk_id, embedding_model)

                sql = "SELECT * FROM embedding_cache WHERE cache_key = ?"

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql, (cache_key,))
                    row = cursor.fetchone()

                if not row:
                    return None

                # Check expiration
                if row['expires_at']:
                    expires_dt = datetime.fromisoformat(row['expires_at'])
                    if datetime.now(timezone.utc) > expires_dt:
                        self._mark_expired(cache_key)
                        return None

                # Update access statistics
                self._update_access_stats(cache_key)

                # Convert row to entry
                return self._row_to_entry(row)

        except Exception as e:
            self._logger.error(f"Failed to retrieve embedding cache entry {chunk_id}: {e}")
            return None

    def put_batch(self, entries: List[Tuple[str, str, str, np.ndarray, str]]) -> int:
        """
        Store multiple embeddings in batch.

        Args:
            entries: List of (chunk_id, document_id, embedding_model, vector, text_content) tuples

        Returns:
            Number of entries successfully stored
        """
        try:
            with self._lock:
                successful_count = 0

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    for chunk_id, document_id, embedding_model, vector, text_content in entries:
                        try:
                            cache_key = self._generate_cache_key(chunk_id, embedding_model)
                            text_hash = self._calculate_text_hash(text_content)

                            # Compress vector
                            compressed_data, compression_method, original_size = self._compress_vector(vector)

                            now = datetime.now(timezone.utc)
                            expires_at = now + self._default_ttl

                            sql = """
                            INSERT OR REPLACE INTO embedding_cache (
                                cache_key, chunk_id, document_id, embedding_model, embedding_type,
                                embedding_vector, vector_dimension, compression_method,
                                compressed_size_bytes, original_size_bytes, text_content, text_hash,
                                access_count, hit_count, last_accessed, created_at, expires_at,
                                metadata, tags
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """

                            params = (
                                cache_key, chunk_id, document_id, embedding_model,
                                EmbeddingType.CHUNK.value, compressed_data, len(vector),
                                compression_method.value, len(compressed_data), original_size,
                                text_content, text_hash, 0, 0, now, now, expires_at,
                                json.dumps({}), json.dumps([])
                            )

                            conn.execute(sql, params)
                            successful_count += 1

                        except Exception as e:
                            self._logger.error(f"Failed to store batch entry {chunk_id}: {e}")
                            continue

                    conn.commit()

                self._invalidate_stats_cache()
                self._logger.debug(f"Stored {successful_count}/{len(entries)} embedding entries in batch")
                return successful_count

        except Exception as e:
            self._logger.error(f"Failed to store embedding batch: {e}")
            return 0

    def invalidate_by_document(self, document_id: str) -> int:
        """
        Invalidate all embeddings for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of entries invalidated
        """
        try:
            with self._lock:
                sql = "DELETE FROM embedding_cache WHERE document_id = ?"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, (document_id,))
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Invalidated {affected_rows} embeddings for document: {document_id}")
                return affected_rows

        except Exception as e:
            self._logger.error(f"Failed to invalidate embeddings for document {document_id}: {e}")
            return 0

    def invalidate_by_model(self, embedding_model: str) -> int:
        """
        Invalidate all embeddings for a specific model.

        Args:
            embedding_model: Model identifier

        Returns:
            Number of entries invalidated
        """
        try:
            with self._lock:
                sql = "DELETE FROM embedding_cache WHERE embedding_model = ?"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, (embedding_model,))
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Invalidated {affected_rows} embeddings for model: {embedding_model}")
                return affected_rows

        except Exception as e:
            self._logger.error(f"Failed to invalidate embeddings for model {embedding_model}: {e}")
            return 0

    def search_similar(self, query_vector: np.ndarray, embedding_model: str,
                      top_k: int = 10, threshold: float = 0.7) -> List[Tuple[str, float]]:
        """
        Search for similar embeddings using cosine similarity.

        Args:
            query_vector: Query embedding vector
            embedding_model: Model to search within
            top_k: Number of top results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (chunk_id, similarity_score) tuples
        """
        try:
            with self._lock:
                sql = """
                SELECT chunk_id, embedding_vector, compression_method, vector_dimension
                FROM embedding_cache
                WHERE embedding_model = ? AND (expires_at IS NULL OR expires_at > datetime('now'))
                """

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql, (embedding_model,))
                    rows = cursor.fetchall()

                if not rows:
                    return []

                # Calculate similarities
                similarities = []
                query_norm = np.linalg.norm(query_vector)

                for row in rows:
                    chunk_id, vector_data, compression_method, vector_dimension = row

                    # Decompress vector
                    compression_enum = CompressionMethod(compression_method)
                    cached_vector = self._decompress_vector(vector_data, compression_enum, vector_dimension)

                    # Calculate cosine similarity
                    cached_norm = np.linalg.norm(cached_vector)
                    if cached_norm > 0 and query_norm > 0:
                        similarity = np.dot(query_vector, cached_vector) / (query_norm * cached_norm)

                        if similarity >= threshold:
                            similarities.append((chunk_id, float(similarity)))

                # Sort by similarity and return top_k
                similarities.sort(key=lambda x: x[1], reverse=True)
                return similarities[:top_k]

        except Exception as e:
            self._logger.error(f"Failed to search similar embeddings: {e}")
            return []

    def get_stats(self, force_refresh: bool = False) -> EmbeddingCacheStats:
        """
        Get cache statistics.

        Args:
            force_refresh: Force refresh of cached statistics

        Returns:
            EmbeddingCacheStats object
        """
        try:
            # Check if cached stats are still valid
            if (not force_refresh and self._stats_cache and self._stats_last_updated and
                datetime.now(timezone.utc) - self._stats_last_updated < timedelta(minutes=5)):
                return self._stats_cache

            with self._lock:
                sql = """
                SELECT
                    COUNT(*) as total_entries,
                    SUM(CASE WHEN expires_at IS NULL OR expires_at > datetime('now') THEN 1 ELSE 0 END) as active_entries,
                    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at <= datetime('now') THEN 1 ELSE 0 END) as expired_entries,
                    SUM(original_size_bytes) as total_size_bytes,
                    SUM(compressed_size_bytes) as compressed_size_bytes,
                    COUNT(embedding_vector) as total_vectors,
                    AVG(vector_dimension) as average_dimension,
                    AVG(CASE WHEN access_count > 0 THEN CAST(hit_count AS REAL) / access_count ELSE 0 END) as hit_rate
                FROM embedding_cache
                """

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql)
                    row = cursor.fetchone()

                if row:
                    total_entries = row[0] or 0
                    active_entries = row[1] or 0
                    expired_entries = row[2] or 0
                    total_size_bytes = row[3] or 0
                    compressed_size_bytes = row[4] or 0
                    total_vectors = row[5] or 0
                    average_dimension = row[6] or 0.0
                    hit_rate = row[7] or 0.0

                    # Calculate derived metrics
                    miss_rate = 1.0 - hit_rate if hit_rate > 0 else 0.0
                    compression_ratio = (compressed_size_bytes / total_size_bytes) if total_size_bytes > 0 else 0.0
                    cache_efficiency = hit_rate

                    stats = EmbeddingCacheStats(
                        total_entries=total_entries,
                        active_entries=active_entries,
                        expired_entries=expired_entries,
                        total_size_bytes=total_size_bytes,
                        compressed_size_bytes=compressed_size_bytes,
                        total_vectors=total_vectors,
                        average_dimension=average_dimension,
                        hit_rate=hit_rate,
                        miss_rate=miss_rate,
                        compression_ratio=compression_ratio,
                        cache_efficiency=cache_efficiency,
                        last_cleanup=datetime.now(timezone.utc)
                    )

                    # Cache the stats
                    self._stats_cache = stats
                    self._stats_last_updated = datetime.now(timezone.utc)

                    return stats
                else:
                    return EmbeddingCacheStats(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, datetime.now(timezone.utc))

        except Exception as e:
            self._logger.error(f"Failed to get cache statistics: {e}")
            return EmbeddingCacheStats(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, datetime.now(timezone.utc))

    def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.

        Returns:
            Number of entries cleaned up
        """
        try:
            with self._lock:
                now = datetime.now(timezone.utc)

                # Delete expired entries
                sql = "DELETE FROM embedding_cache WHERE expires_at < ?"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, (now,))
                    conn.commit()
                    deleted_count = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Cleaned up {deleted_count} expired embedding entries")
                return deleted_count

        except Exception as e:
            self._logger.error(f"Failed to cleanup expired entries: {e}")
            return 0

    def _check_cache_limits(self, additional_size: int = 0) -> bool:
        """Check if cache is within size limits."""
        try:
            sql = "SELECT SUM(compressed_size_bytes) FROM embedding_cache"

            with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                cursor = conn.execute(sql)
                current_size = cursor.fetchone()[0] or 0

            return (current_size + additional_size) <= self._max_cache_size_bytes

        except Exception as e:
            self._logger.error(f"Failed to check cache limits: {e}")
            return False

    def _evict_entries(self, required_space: int) -> None:
        """Evict least recently used entries to make space."""
        try:
            # Get entries sorted by last accessed (LRU)
            sql = """
            SELECT cache_key, compressed_size_bytes
            FROM embedding_cache
            ORDER BY last_accessed ASC
            """

            with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                cursor = conn.execute(sql)
                entries = cursor.fetchall()

            freed_space = 0
            keys_to_evict = []

            for cache_key, size_bytes in entries:
                keys_to_evict.append(cache_key)
                freed_space += size_bytes

                if freed_space >= required_space:
                    break

            if keys_to_evict:
                placeholders = ','.join(['?'] * len(keys_to_evict))
                sql_evict = f"DELETE FROM embedding_cache WHERE cache_key IN ({placeholders})"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    conn.execute(sql_evict, keys_to_evict)
                    conn.commit()

                self._logger.debug(f"Evicted {len(keys_to_evict)} entries, freed {freed_space} bytes")

        except Exception as e:
            self._logger.error(f"Failed to evict cache entries: {e}")

    def _row_to_entry(self, row: sqlite3.Row) -> EmbeddingCacheEntry:
        """Convert database row to EmbeddingCacheEntry."""
        # Decompress vector
        compression_method = CompressionMethod(row['compression_method'])
        embedding_vector = self._decompress_vector(
            row['embedding_vector'], compression_method, row['vector_dimension']
        )

        return EmbeddingCacheEntry(
            cache_key=row['cache_key'],
            chunk_id=row['chunk_id'],
            document_id=row['document_id'],
            embedding_model=row['embedding_model'],
            embedding_type=EmbeddingType(row['embedding_type']),
            embedding_vector=embedding_vector,
            vector_dimension=row['vector_dimension'],
            compression_method=compression_method,
            compressed_size_bytes=row['compressed_size_bytes'],
            original_size_bytes=row['original_size_bytes'],
            text_content=row['text_content'],
            text_hash=row['text_hash'],
            access_count=row['access_count'],
            hit_count=row['hit_count'],
            last_accessed=datetime.fromisoformat(row['last_accessed']),
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            metadata=json.loads(row['metadata']),
            tags=json.loads(row['tags'])
        )

    def _update_access_stats(self, cache_key: str) -> None:
        """Update access statistics for cache entry."""
        try:
            sql = """
            UPDATE embedding_cache
            SET access_count = access_count + 1,
                hit_count = hit_count + 1,
                last_accessed = ?
            WHERE cache_key = ?
            """

            with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                conn.execute(sql, (datetime.now(timezone.utc), cache_key))
                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to update access stats: {e}")

    def _mark_expired(self, cache_key: str) -> None:
        """Mark cache entry as expired by deleting it."""
        try:
            sql = "DELETE FROM embedding_cache WHERE cache_key = ?"

            with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                conn.execute(sql, (cache_key,))
                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to mark entry as expired: {e}")

    def _invalidate_stats_cache(self) -> None:
        """Invalidate cached statistics."""
        self._stats_cache = None
        self._stats_last_updated = None

    def _start_cleanup_thread(self) -> None:
        """Start background cleanup thread."""
        def cleanup_worker():
            while not self._shutdown_event.wait(self._cleanup_interval.total_seconds()):
                try:
                    self.cleanup_expired()
                except Exception as e:
                    self._logger.error(f"Error in cleanup thread: {e}")

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        self._logger.debug("Started background cleanup thread")

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            # Stop cleanup thread
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                self._shutdown_event.set()
                self._cleanup_thread.join(timeout=5.0)

            # Close connection manager
            if self._connection_manager:
                self._connection_manager.close()

            self._logger.info("EmbeddingCacheDB closed successfully")

        except Exception as e:
            self._logger.error(f"Error closing EmbeddingCacheDB: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
