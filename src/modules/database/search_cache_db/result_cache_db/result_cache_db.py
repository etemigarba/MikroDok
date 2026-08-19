"""
Module: result_cache_db
Description: Stores cached search results with TTL management, result serialization, and cache invalidation strategies
Phase: 4
Location: /src/modules/database/search_cache_db/result_cache_db/
"""

# Standard library imports
import gzip
import hashlib
import json
import pickle
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ResultType(Enum):
    """Types of search results."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    VECTOR = "vector"
    FILTERED = "filtered"


class CompressionType(Enum):
    """Types of result compression."""
    NONE = "none"
    GZIP = "gzip"
    PICKLE = "pickle"
    JSON = "json"


class CacheStatus(Enum):
    """Status of cache entries."""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    COMPRESSED = "compressed"


class ResultCacheDB:
    """
    Result cache database manager.
    
    Manages caching of search results with TTL management, result serialization,
    and cache invalidation strategies. Provides efficient storage and retrieval of
    search results with compression and performance optimization for large result sets.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the result cache database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to search cache data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "search_cache"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "result_cache.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Cache settings
        self._default_ttl_hours = 12  # Default TTL for cached results
        self._max_cache_entries = 50000  # Maximum cache entries
        self._max_result_size_mb = 100  # Maximum size per result set
        self._compression_threshold_kb = 50  # Compress results larger than 50KB
        self._cleanup_interval_hours = 4  # Cleanup interval
        self._batch_size = 500
        
        self._initialize_database()
        
        self._logger.info(f"ResultCacheDB initialized with database: {self._db_path}")
    
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
                
                # Create result cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS result_cache (
                        cache_id TEXT PRIMARY KEY,
                        query_hash TEXT NOT NULL,
                        result_type TEXT NOT NULL,
                        result_data BLOB NOT NULL,
                        result_metadata TEXT,  -- JSON object
                        compression_type TEXT DEFAULT 'none',
                        original_size_bytes INTEGER DEFAULT 0,
                        compressed_size_bytes INTEGER DEFAULT 0,
                        result_count INTEGER DEFAULT 0,
                        hit_count INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        status TEXT DEFAULT 'active',
                        processing_time_ms REAL DEFAULT 0.0,
                        search_parameters TEXT,  -- JSON object of search params
                        relevance_scores TEXT,  -- JSON array of scores
                        facet_data TEXT,  -- JSON object for faceted search
                        total_results INTEGER DEFAULT 0,
                        page_number INTEGER DEFAULT 1,
                        page_size INTEGER DEFAULT 20
                    )
                """)
                
                # Create result statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS result_statistics (
                        stat_id TEXT PRIMARY KEY,
                        date_bucket TEXT NOT NULL,  -- YYYY-MM-DD-HH format
                        result_type TEXT NOT NULL,
                        total_cached INTEGER DEFAULT 0,
                        cache_hits INTEGER DEFAULT 0,
                        cache_misses INTEGER DEFAULT 0,
                        avg_result_size_bytes REAL DEFAULT 0.0,
                        avg_processing_time_ms REAL DEFAULT 0.0,
                        compression_ratio REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create cache invalidation log
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cache_invalidation_log (
                        log_id TEXT PRIMARY KEY,
                        cache_id TEXT NOT NULL,
                        invalidation_reason TEXT NOT NULL,
                        invalidated_by TEXT,
                        invalidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        affected_queries INTEGER DEFAULT 0,
                        metadata TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_cache_query_hash ON result_cache(query_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_cache_type ON result_cache(result_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_cache_expires ON result_cache(expires_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_cache_status ON result_cache(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_cache_accessed ON result_cache(last_accessed)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_cache_size ON result_cache(compressed_size_bytes)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_stats_bucket ON result_statistics(date_bucket)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_stats_type ON result_statistics(result_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_invalidation_log_cache_id ON cache_invalidation_log(cache_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_invalidation_log_reason ON cache_invalidation_log(invalidation_reason)")
                
                conn.commit()
                self._logger.info("Result cache database schema initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize result cache database: {e}")
                raise
            finally:
                conn.close()

    def _compress_data(self, data: Any, compression_type: CompressionType = CompressionType.GZIP) -> Tuple[bytes, int, int]:
        """
        Compress result data for storage.

        Args:
            data: Data to compress
            compression_type: Type of compression to use

        Returns:
            Tuple of (compressed_data, original_size, compressed_size)
        """
        if compression_type == CompressionType.NONE:
            serialized = json.dumps(data).encode('utf-8')
            return serialized, len(serialized), len(serialized)

        elif compression_type == CompressionType.JSON:
            serialized = json.dumps(data).encode('utf-8')
            return serialized, len(serialized), len(serialized)

        elif compression_type == CompressionType.PICKLE:
            serialized = pickle.dumps(data)
            return serialized, len(serialized), len(serialized)

        elif compression_type == CompressionType.GZIP:
            serialized = json.dumps(data).encode('utf-8')
            compressed = gzip.compress(serialized)
            return compressed, len(serialized), len(compressed)

        else:
            raise ValueError(f"Unsupported compression type: {compression_type}")

    def _decompress_data(self, compressed_data: bytes, compression_type: CompressionType) -> Any:
        """
        Decompress result data from storage.

        Args:
            compressed_data: Compressed data bytes
            compression_type: Type of compression used

        Returns:
            Decompressed data
        """
        if compression_type == CompressionType.NONE or compression_type == CompressionType.JSON:
            return json.loads(compressed_data.decode('utf-8'))

        elif compression_type == CompressionType.PICKLE:
            return pickle.loads(compressed_data)

        elif compression_type == CompressionType.GZIP:
            decompressed = gzip.decompress(compressed_data)
            return json.loads(decompressed.decode('utf-8'))

        else:
            raise ValueError(f"Unsupported compression type: {compression_type}")

    def cache_results(self, query_hash: str, results: List[Dict[str, Any]],
                     result_type: ResultType,
                     search_parameters: Optional[Dict[str, Any]] = None,
                     processing_time_ms: float = 0.0,
                     total_results: int = 0,
                     page_number: int = 1,
                     page_size: int = 20,
                     ttl_hours: Optional[int] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Cache search results with compression and TTL management.

        Args:
            query_hash: Hash of the search query
            results: List of search result items
            result_type: Type of search results
            search_parameters: Parameters used for search
            processing_time_ms: Time taken to generate results
            total_results: Total number of results available
            page_number: Page number of results
            page_size: Number of results per page
            ttl_hours: Time-to-live in hours
            metadata: Additional metadata

        Returns:
            Cache ID for the stored results
        """
        if not results:
            raise ValueError("Results cannot be empty")

        cache_id = str(uuid.uuid4())
        ttl_hours = ttl_hours or self._default_ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        # Determine compression type based on data size
        data_size_estimate = len(json.dumps(results).encode('utf-8'))
        compression_type = (CompressionType.GZIP
                          if data_size_estimate > self._compression_threshold_kb * 1024
                          else CompressionType.JSON)

        # Compress the results
        compressed_data, original_size, compressed_size = self._compress_data(results, compression_type)

        # Check size limits
        if compressed_size > self._max_result_size_mb * 1024 * 1024:
            raise ValueError(f"Result set too large: {compressed_size / (1024*1024):.2f}MB > {self._max_result_size_mb}MB")

        # Extract relevance scores if available
        relevance_scores = [
            result.get('similarity_score', result.get('score', 0.0))
            for result in results
        ]

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if results already cached for this query
                cursor.execute("""
                    SELECT cache_id FROM result_cache
                    WHERE query_hash = ? AND result_type = ? AND status = 'active'
                    AND expires_at > CURRENT_TIMESTAMP AND page_number = ?
                """, (query_hash, result_type.value, page_number))

                existing = cursor.fetchone()
                if existing:
                    # Update existing entry
                    existing_cache_id = existing[0]
                    cursor.execute("""
                        UPDATE result_cache SET
                            result_data = ?, result_metadata = ?, compression_type = ?,
                            original_size_bytes = ?, compressed_size_bytes = ?,
                            result_count = ?, hit_count = hit_count + 1,
                            last_accessed = CURRENT_TIMESTAMP, expires_at = ?,
                            processing_time_ms = ?, search_parameters = ?,
                            relevance_scores = ?, total_results = ?, page_size = ?
                        WHERE cache_id = ?
                    """, (
                        compressed_data, json.dumps(metadata) if metadata else None,
                        compression_type.value, original_size, compressed_size,
                        len(results), expires_at.isoformat(), processing_time_ms,
                        json.dumps(search_parameters) if search_parameters else None,
                        json.dumps(relevance_scores), total_results, page_size,
                        existing_cache_id
                    ))

                    conn.commit()
                    return existing_cache_id

                # Insert new entry
                cursor.execute("""
                    INSERT INTO result_cache (
                        cache_id, query_hash, result_type, result_data, result_metadata,
                        compression_type, original_size_bytes, compressed_size_bytes,
                        result_count, processing_time_ms, search_parameters,
                        relevance_scores, total_results, page_number, page_size, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_id, query_hash, result_type.value, compressed_data,
                    json.dumps(metadata) if metadata else None, compression_type.value,
                    original_size, compressed_size, len(results), processing_time_ms,
                    json.dumps(search_parameters) if search_parameters else None,
                    json.dumps(relevance_scores), total_results, page_number, page_size,
                    expires_at.isoformat()
                ))

                # Update statistics
                self._update_result_statistics(cursor, result_type, compressed_size,
                                             processing_time_ms, original_size, compressed_size)

                conn.commit()
                return cache_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cache results: {e}")
                raise
            finally:
                conn.close()

    def get_cached_results(self, query_hash: str, result_type: ResultType,
                          page_number: int = 1) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached search results.

        Args:
            query_hash: Hash of the search query
            result_type: Type of search results
            page_number: Page number of results

        Returns:
            Cached results data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cache_id, result_data, result_metadata, compression_type,
                           original_size_bytes, compressed_size_bytes, result_count,
                           hit_count, last_accessed, created_at, expires_at,
                           processing_time_ms, search_parameters, relevance_scores,
                           total_results, page_size
                    FROM result_cache
                    WHERE query_hash = ? AND result_type = ? AND page_number = ?
                    AND status = 'active' AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (query_hash, result_type.value, page_number))

                row = cursor.fetchone()
                if not row:
                    # Update statistics for cache miss
                    self._update_result_statistics(cursor, result_type, cache_miss=True)
                    conn.commit()
                    return None

                # Update hit count and last accessed
                cache_id = row[0]
                cursor.execute("""
                    UPDATE result_cache SET
                        hit_count = hit_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE cache_id = ?
                """, (cache_id,))

                # Update statistics for cache hit
                self._update_result_statistics(cursor, result_type, cache_hit=True)

                conn.commit()

                # Decompress results
                compression_type = CompressionType(row[3])
                results = self._decompress_data(row[1], compression_type)

                return {
                    'cache_id': cache_id,
                    'results': results,
                    'metadata': json.loads(row[2]) if row[2] else None,
                    'compression_type': compression_type.value,
                    'original_size_bytes': row[4],
                    'compressed_size_bytes': row[5],
                    'result_count': row[6],
                    'hit_count': row[7] + 1,  # Include current hit
                    'last_accessed': row[8],
                    'created_at': row[9],
                    'expires_at': row[10],
                    'processing_time_ms': row[11],
                    'search_parameters': json.loads(row[12]) if row[12] else None,
                    'relevance_scores': json.loads(row[13]) if row[13] else None,
                    'total_results': row[14],
                    'page_size': row[15]
                }

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to retrieve cached results: {e}")
                raise
            finally:
                conn.close()

    def invalidate_results(self, query_hash: Optional[str] = None,
                          result_type: Optional[ResultType] = None,
                          cache_id: Optional[str] = None,
                          reason: str = "manual_invalidation",
                          invalidated_by: Optional[str] = None) -> int:
        """
        Invalidate cached results based on criteria.

        Args:
            query_hash: Hash of queries to invalidate
            result_type: Type of results to invalidate
            cache_id: Specific cache ID to invalidate
            reason: Reason for invalidation
            invalidated_by: Who initiated the invalidation

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build WHERE clause based on criteria
                where_conditions = ["status = 'active'"]
                params = []

                if cache_id:
                    where_conditions.append("cache_id = ?")
                    params.append(cache_id)
                elif query_hash:
                    where_conditions.append("query_hash = ?")
                    params.append(query_hash)
                    if result_type:
                        where_conditions.append("result_type = ?")
                        params.append(result_type.value)
                elif result_type:
                    where_conditions.append("result_type = ?")
                    params.append(result_type.value)

                where_clause = " AND ".join(where_conditions)

                # Get cache IDs to be invalidated for logging
                cursor.execute(f"""
                    SELECT cache_id FROM result_cache WHERE {where_clause}
                """, params)

                cache_ids = [row[0] for row in cursor.fetchall()]

                # Invalidate entries
                cursor.execute(f"""
                    UPDATE result_cache SET status = 'invalidated'
                    WHERE {where_clause}
                """, params)

                invalidated_count = cursor.rowcount

                # Log invalidation
                for cache_id_to_log in cache_ids:
                    log_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO cache_invalidation_log (
                            log_id, cache_id, invalidation_reason, invalidated_by
                        ) VALUES (?, ?, ?, ?)
                    """, (log_id, cache_id_to_log, reason, invalidated_by))

                conn.commit()

                if invalidated_count > 0:
                    self._logger.info(f"Invalidated {invalidated_count} cached result entries: {reason}")

                return invalidated_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to invalidate cached results: {e}")
                return 0
            finally:
                conn.close()

    def cleanup_expired_results(self) -> int:
        """
        Remove expired result cache entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Mark expired entries
                cursor.execute("""
                    UPDATE result_cache SET status = 'expired'
                    WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP
                """)

                expired_count = cursor.rowcount

                # Delete old expired entries (older than 3 days)
                cursor.execute("""
                    DELETE FROM result_cache
                    WHERE status = 'expired' AND expires_at < datetime('now', '-3 days')
                """)

                deleted_count = cursor.rowcount

                conn.commit()

                if expired_count > 0:
                    self._logger.info(f"Marked {expired_count} results as expired, deleted {deleted_count} old entries")

                return expired_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup expired results: {e}")
                return 0
            finally:
                conn.close()

    def _update_result_statistics(self, cursor: sqlite3.Cursor, result_type: ResultType,
                                 result_size_bytes: int = 0, processing_time_ms: float = 0.0,
                                 original_size: int = 0, compressed_size: int = 0,
                                 cache_hit: bool = False, cache_miss: bool = False) -> None:
        """Update result statistics for monitoring."""
        try:
            # Create date bucket (hour-level granularity)
            now = datetime.now(timezone.utc)
            date_bucket = now.strftime("%Y-%m-%d-%H")
            stat_id = f"{date_bucket}:{result_type.value}"

            # Calculate compression ratio
            compression_ratio = (compressed_size / original_size) if original_size > 0 else 1.0

            # Check if statistics entry exists
            cursor.execute("""
                SELECT total_cached, cache_hits, cache_misses, avg_result_size_bytes,
                       avg_processing_time_ms, compression_ratio
                FROM result_statistics WHERE stat_id = ?
            """, (stat_id,))

            existing = cursor.fetchone()
            if existing:
                total_cached, cache_hits, cache_misses, avg_size, avg_time, avg_compression = existing

                new_total = total_cached + (1 if not cache_hit and not cache_miss else 0)
                new_hits = cache_hits + (1 if cache_hit else 0)
                new_misses = cache_misses + (1 if cache_miss else 0)

                # Update averages
                if new_total > 0:
                    new_avg_size = (avg_size * total_cached + result_size_bytes) / new_total if result_size_bytes > 0 else avg_size
                    new_avg_time = (avg_time * total_cached + processing_time_ms) / new_total if processing_time_ms > 0 else avg_time
                    new_avg_compression = (avg_compression * total_cached + compression_ratio) / new_total if compression_ratio > 0 else avg_compression
                else:
                    new_avg_size = avg_size
                    new_avg_time = avg_time
                    new_avg_compression = avg_compression

                cursor.execute("""
                    UPDATE result_statistics SET
                        total_cached = ?, cache_hits = ?, cache_misses = ?,
                        avg_result_size_bytes = ?, avg_processing_time_ms = ?,
                        compression_ratio = ?
                    WHERE stat_id = ?
                """, (new_total, new_hits, new_misses, new_avg_size, new_avg_time,
                     new_avg_compression, stat_id))
            else:
                cursor.execute("""
                    INSERT INTO result_statistics (
                        stat_id, date_bucket, result_type, total_cached,
                        cache_hits, cache_misses, avg_result_size_bytes,
                        avg_processing_time_ms, compression_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stat_id, date_bucket, result_type.value,
                     1 if not cache_hit and not cache_miss else 0,
                     1 if cache_hit else 0, 1 if cache_miss else 0,
                     result_size_bytes, processing_time_ms, compression_ratio))

        except Exception as e:
            self._logger.warning(f"Failed to update result statistics: {e}")

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with cache performance metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Basic cache stats
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_entries,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_entries,
                        COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries,
                        AVG(hit_count) as avg_hit_count,
                        AVG(compressed_size_bytes) as avg_size_bytes,
                        AVG(processing_time_ms) as avg_processing_time,
                        SUM(compressed_size_bytes) as total_size_bytes,
                        AVG(CAST(compressed_size_bytes AS REAL) / original_size_bytes) as avg_compression_ratio
                    FROM result_cache
                """)

                basic_stats = cursor.fetchone()

                # Result type distribution
                cursor.execute("""
                    SELECT result_type, COUNT(*) as count, AVG(result_count) as avg_results
                    FROM result_cache WHERE status = 'active'
                    GROUP BY result_type
                """)

                type_distribution = {
                    row[0]: {'count': row[1], 'avg_results': round(row[2] or 0, 2)}
                    for row in cursor.fetchall()
                }

                # Recent cache performance (last 24 hours)
                cursor.execute("""
                    SELECT
                        SUM(total_cached) as total_cached,
                        SUM(cache_hits) as cache_hits,
                        SUM(cache_misses) as cache_misses,
                        AVG(avg_result_size_bytes) as avg_size,
                        AVG(compression_ratio) as avg_compression
                    FROM result_statistics
                    WHERE date_bucket >= datetime('now', '-24 hours')
                """)

                performance_stats = cursor.fetchone()

                total_requests = (performance_stats[1] or 0) + (performance_stats[2] or 0)
                hit_rate = ((performance_stats[1] or 0) / total_requests * 100) if total_requests > 0 else 0

                return {
                    'total_entries': basic_stats[0] or 0,
                    'active_entries': basic_stats[1] or 0,
                    'expired_entries': basic_stats[2] or 0,
                    'avg_hit_count': round(basic_stats[3] or 0, 2),
                    'avg_size_bytes': round(basic_stats[4] or 0, 2),
                    'avg_processing_time_ms': round(basic_stats[5] or 0, 2),
                    'total_size_mb': round((basic_stats[6] or 0) / (1024 * 1024), 2),
                    'avg_compression_ratio': round(basic_stats[7] or 1.0, 3),
                    'result_type_distribution': type_distribution,
                    'cache_hit_rate_24h': round(hit_rate, 2),
                    'total_cached_24h': performance_stats[0] or 0,
                    'cache_hits_24h': performance_stats[1] or 0,
                    'cache_misses_24h': performance_stats[2] or 0,
                    'avg_size_bytes_24h': round(performance_stats[3] or 0, 2),
                    'avg_compression_ratio_24h': round(performance_stats[4] or 1.0, 3)
                }

            except Exception as e:
                self._logger.error(f"Failed to get cache statistics: {e}")
                return {}
            finally:
                conn.close()
