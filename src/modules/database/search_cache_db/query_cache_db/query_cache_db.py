"""
Module: query_cache_db
Description: Caches frequent search queries and results for performance optimization with query normalization and TTL management
Phase: 4
Location: /src/modules/database/search_cache_db/query_cache_db/
"""

# Standard library imports
import hashlib
import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class QueryType(Enum):
    """Types of search queries."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    VECTOR = "vector"
    BOOLEAN = "boolean"
    PHRASE = "phrase"
    FUZZY = "fuzzy"


class CacheStatus(Enum):
    """Status of cache entries."""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    PENDING = "pending"


class QueryCacheDB:
    """
    Query cache database manager.
    
    Manages caching of frequent search queries with normalization, TTL management,
    and performance optimization. Provides efficient storage and retrieval of
    query patterns, normalized forms, and associated metadata for search acceleration.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the query cache database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to search cache data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "search_cache"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "query_cache.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Cache settings
        self._default_ttl_hours = 24  # Default TTL for cached queries
        self._max_cache_entries = 100000  # Maximum cache entries
        self._cleanup_interval_hours = 6  # Cleanup interval
        self._batch_size = 1000
        
        # Query normalization patterns
        self._normalization_patterns = [
            (r'\s+', ' '),  # Multiple spaces to single space
            (r'[^\w\s\-\.]', ''),  # Remove special characters except hyphens and dots
            (r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', ''),  # Remove stop words
        ]
        
        self._initialize_database()
        
        self._logger.info(f"QueryCacheDB initialized with database: {self._db_path}")
    
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
                
                # Create query cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_cache (
                        cache_id TEXT PRIMARY KEY,
                        original_query TEXT NOT NULL,
                        normalized_query TEXT NOT NULL,
                        query_hash TEXT NOT NULL UNIQUE,
                        query_type TEXT NOT NULL,
                        query_terms TEXT,  -- JSON array of terms
                        query_filters TEXT,  -- JSON object of filters
                        hit_count INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        status TEXT DEFAULT 'active',
                        processing_time_ms REAL DEFAULT 0.0,
                        result_count INTEGER DEFAULT 0,
                        metadata TEXT  -- JSON object for additional data
                    )
                """)
                
                # Create query patterns table for pattern analysis
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        pattern_text TEXT NOT NULL,
                        pattern_type TEXT NOT NULL,
                        frequency INTEGER DEFAULT 1,
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        avg_processing_time_ms REAL DEFAULT 0.0,
                        avg_result_count REAL DEFAULT 0.0,
                        metadata TEXT
                    )
                """)
                
                # Create query statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_statistics (
                        stat_id TEXT PRIMARY KEY,
                        date_bucket TEXT NOT NULL,  -- YYYY-MM-DD-HH format
                        query_type TEXT NOT NULL,
                        total_queries INTEGER DEFAULT 0,
                        cache_hits INTEGER DEFAULT 0,
                        cache_misses INTEGER DEFAULT 0,
                        avg_processing_time_ms REAL DEFAULT 0.0,
                        unique_queries INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_hash ON query_cache(query_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_normalized ON query_cache(normalized_query)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_type ON query_cache(query_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON query_cache(expires_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_status ON query_cache(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_accessed ON query_cache(last_accessed)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_patterns_type ON query_patterns(pattern_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_patterns_frequency ON query_patterns(frequency)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_stats_bucket ON query_statistics(date_bucket)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_stats_type ON query_statistics(query_type)")
                
                conn.commit()
                self._logger.info("Query cache database schema initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize query cache database: {e}")
                raise
            finally:
                conn.close()

    def _normalize_query(self, query: str) -> str:
        """
        Normalize query text for consistent caching.

        Args:
            query: Original query text

        Returns:
            Normalized query text
        """
        if not query:
            return ""

        normalized = query.lower().strip()

        # Apply normalization patterns
        for pattern, replacement in self._normalization_patterns:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        return normalized

    def _generate_query_hash(self, normalized_query: str, query_type: QueryType,
                           filters: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate unique hash for query caching.

        Args:
            normalized_query: Normalized query text
            query_type: Type of query
            filters: Optional query filters

        Returns:
            SHA-256 hash of query components
        """
        hash_components = [
            normalized_query,
            query_type.value,
            json.dumps(filters or {}, sort_keys=True)
        ]

        hash_input = "|".join(hash_components)
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

    def cache_query(self, original_query: str, query_type: QueryType,
                   query_terms: Optional[List[str]] = None,
                   query_filters: Optional[Dict[str, Any]] = None,
                   processing_time_ms: float = 0.0,
                   result_count: int = 0,
                   ttl_hours: Optional[int] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Cache a search query with its metadata.

        Args:
            original_query: Original query text
            query_type: Type of search query
            query_terms: Extracted query terms
            query_filters: Applied filters
            processing_time_ms: Query processing time
            result_count: Number of results returned
            ttl_hours: Time-to-live in hours
            metadata: Additional metadata

        Returns:
            Cache ID for the stored query
        """
        if not original_query:
            raise ValueError("Query cannot be empty")

        cache_id = str(uuid.uuid4())
        normalized_query = self._normalize_query(original_query)
        query_hash = self._generate_query_hash(normalized_query, query_type, query_filters)

        ttl_hours = ttl_hours or self._default_ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if query already exists
                cursor.execute("""
                    SELECT cache_id, hit_count FROM query_cache
                    WHERE query_hash = ? AND status = 'active' AND expires_at > CURRENT_TIMESTAMP
                """, (query_hash,))

                existing = cursor.fetchone()
                if existing:
                    # Update existing entry
                    existing_cache_id, hit_count = existing
                    cursor.execute("""
                        UPDATE query_cache SET
                            hit_count = hit_count + 1,
                            last_accessed = CURRENT_TIMESTAMP,
                            processing_time_ms = (processing_time_ms * hit_count + ?) / (hit_count + 1),
                            result_count = ?,
                            expires_at = ?,
                            metadata = ?
                        WHERE cache_id = ?
                    """, (processing_time_ms, result_count, expires_at.isoformat(),
                         json.dumps(metadata) if metadata else None, existing_cache_id))

                    conn.commit()
                    return existing_cache_id

                # Insert new entry
                cursor.execute("""
                    INSERT INTO query_cache (
                        cache_id, original_query, normalized_query, query_hash,
                        query_type, query_terms, query_filters, processing_time_ms,
                        result_count, expires_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_id, original_query, normalized_query, query_hash,
                    query_type.value,
                    json.dumps(query_terms) if query_terms else None,
                    json.dumps(query_filters) if query_filters else None,
                    processing_time_ms, result_count, expires_at.isoformat(),
                    json.dumps(metadata) if metadata else None
                ))

                # Update query patterns
                self._update_query_patterns(cursor, normalized_query, query_type,
                                          processing_time_ms, result_count)

                # Update statistics
                self._update_query_statistics(cursor, query_type, cache_miss=True)

                conn.commit()
                return cache_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cache query: {e}")
                raise
            finally:
                conn.close()

    def get_cached_query(self, query: str, query_type: QueryType,
                        query_filters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached query information.

        Args:
            query: Query text to look up
            query_type: Type of search query
            query_filters: Applied filters

        Returns:
            Cached query data or None if not found
        """
        normalized_query = self._normalize_query(query)
        query_hash = self._generate_query_hash(normalized_query, query_type, query_filters)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cache_id, original_query, normalized_query, query_terms,
                           query_filters, hit_count, last_accessed, created_at,
                           expires_at, processing_time_ms, result_count, metadata
                    FROM query_cache
                    WHERE query_hash = ? AND status = 'active' AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY last_accessed DESC
                    LIMIT 1
                """, (query_hash,))

                row = cursor.fetchone()
                if not row:
                    # Update statistics for cache miss
                    self._update_query_statistics(cursor, query_type, cache_miss=True)
                    conn.commit()
                    return None

                # Update hit count and last accessed
                cache_id = row[0]
                cursor.execute("""
                    UPDATE query_cache SET
                        hit_count = hit_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE cache_id = ?
                """, (cache_id,))

                # Update statistics for cache hit
                self._update_query_statistics(cursor, query_type, cache_hit=True)

                conn.commit()

                return {
                    'cache_id': row[0],
                    'original_query': row[1],
                    'normalized_query': row[2],
                    'query_terms': json.loads(row[3]) if row[3] else None,
                    'query_filters': json.loads(row[4]) if row[4] else None,
                    'hit_count': row[5] + 1,  # Include the current hit
                    'last_accessed': row[6],
                    'created_at': row[7],
                    'expires_at': row[8],
                    'processing_time_ms': row[9],
                    'result_count': row[10],
                    'metadata': json.loads(row[11]) if row[11] else None
                }

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to retrieve cached query: {e}")
                raise
            finally:
                conn.close()

    def invalidate_query(self, cache_id: str) -> bool:
        """
        Invalidate a cached query.

        Args:
            cache_id: ID of the cached query to invalidate

        Returns:
            True if successfully invalidated, False otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE query_cache SET status = 'invalidated'
                    WHERE cache_id = ? AND status = 'active'
                """, (cache_id,))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.debug(f"Invalidated cached query: {cache_id}")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to invalidate cached query: {e}")
                return False
            finally:
                conn.close()

    def cleanup_expired_queries(self) -> int:
        """
        Remove expired query cache entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Mark expired entries
                cursor.execute("""
                    UPDATE query_cache SET status = 'expired'
                    WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP
                """)

                expired_count = cursor.rowcount

                # Delete old expired entries (older than 7 days)
                cursor.execute("""
                    DELETE FROM query_cache
                    WHERE status = 'expired' AND expires_at < datetime('now', '-7 days')
                """)

                deleted_count = cursor.rowcount

                conn.commit()

                if expired_count > 0:
                    self._logger.info(f"Marked {expired_count} queries as expired, deleted {deleted_count} old entries")

                return expired_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup expired queries: {e}")
                return 0
            finally:
                conn.close()

    def _update_query_patterns(self, cursor: sqlite3.Cursor, normalized_query: str,
                              query_type: QueryType, processing_time_ms: float,
                              result_count: int) -> None:
        """Update query patterns for analysis."""
        try:
            # Extract pattern (first 3 words)
            words = normalized_query.split()[:3]
            pattern_text = ' '.join(words) if words else normalized_query
            pattern_id = hashlib.md5(f"{pattern_text}:{query_type.value}".encode()).hexdigest()

            # Check if pattern exists
            cursor.execute("""
                SELECT frequency, avg_processing_time_ms, avg_result_count
                FROM query_patterns WHERE pattern_id = ?
            """, (pattern_id,))

            existing = cursor.fetchone()
            if existing:
                frequency, avg_time, avg_count = existing
                new_frequency = frequency + 1
                new_avg_time = (avg_time * frequency + processing_time_ms) / new_frequency
                new_avg_count = (avg_count * frequency + result_count) / new_frequency

                cursor.execute("""
                    UPDATE query_patterns SET
                        frequency = ?, last_seen = CURRENT_TIMESTAMP,
                        avg_processing_time_ms = ?, avg_result_count = ?
                    WHERE pattern_id = ?
                """, (new_frequency, new_avg_time, new_avg_count, pattern_id))
            else:
                cursor.execute("""
                    INSERT INTO query_patterns (
                        pattern_id, pattern_text, pattern_type, frequency,
                        avg_processing_time_ms, avg_result_count
                    ) VALUES (?, ?, ?, 1, ?, ?)
                """, (pattern_id, pattern_text, query_type.value, processing_time_ms, result_count))

        except Exception as e:
            self._logger.warning(f"Failed to update query patterns: {e}")

    def _update_query_statistics(self, cursor: sqlite3.Cursor, query_type: QueryType,
                                cache_hit: bool = False, cache_miss: bool = False) -> None:
        """Update query statistics for monitoring."""
        try:
            # Create date bucket (hour-level granularity)
            now = datetime.now(timezone.utc)
            date_bucket = now.strftime("%Y-%m-%d-%H")
            stat_id = f"{date_bucket}:{query_type.value}"

            # Check if statistics entry exists
            cursor.execute("""
                SELECT total_queries, cache_hits, cache_misses
                FROM query_statistics WHERE stat_id = ?
            """, (stat_id,))

            existing = cursor.fetchone()
            if existing:
                total_queries, cache_hits, cache_misses = existing
                new_total = total_queries + 1
                new_hits = cache_hits + (1 if cache_hit else 0)
                new_misses = cache_misses + (1 if cache_miss else 0)

                cursor.execute("""
                    UPDATE query_statistics SET
                        total_queries = ?, cache_hits = ?, cache_misses = ?
                    WHERE stat_id = ?
                """, (new_total, new_hits, new_misses, stat_id))
            else:
                cursor.execute("""
                    INSERT INTO query_statistics (
                        stat_id, date_bucket, query_type, total_queries,
                        cache_hits, cache_misses, unique_queries
                    ) VALUES (?, ?, ?, 1, ?, ?, 1)
                """, (stat_id, date_bucket, query_type.value,
                     1 if cache_hit else 0, 1 if cache_miss else 0))

        except Exception as e:
            self._logger.warning(f"Failed to update query statistics: {e}")

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
                        AVG(processing_time_ms) as avg_processing_time,
                        AVG(result_count) as avg_result_count
                    FROM query_cache
                """)

                basic_stats = cursor.fetchone()

                # Query type distribution
                cursor.execute("""
                    SELECT query_type, COUNT(*) as count
                    FROM query_cache WHERE status = 'active'
                    GROUP BY query_type
                """)

                type_distribution = dict(cursor.fetchall())

                # Recent cache performance (last 24 hours)
                cursor.execute("""
                    SELECT
                        SUM(total_queries) as total_queries,
                        SUM(cache_hits) as cache_hits,
                        SUM(cache_misses) as cache_misses
                    FROM query_statistics
                    WHERE date_bucket >= datetime('now', '-24 hours')
                """)

                performance_stats = cursor.fetchone()

                # Top query patterns
                cursor.execute("""
                    SELECT pattern_text, pattern_type, frequency
                    FROM query_patterns
                    ORDER BY frequency DESC
                    LIMIT 10
                """)

                top_patterns = [
                    {'pattern': row[0], 'type': row[1], 'frequency': row[2]}
                    for row in cursor.fetchall()
                ]

                total_queries = performance_stats[0] or 0
                cache_hits = performance_stats[1] or 0
                hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0

                return {
                    'total_entries': basic_stats[0] or 0,
                    'active_entries': basic_stats[1] or 0,
                    'expired_entries': basic_stats[2] or 0,
                    'avg_hit_count': round(basic_stats[3] or 0, 2),
                    'avg_processing_time_ms': round(basic_stats[4] or 0, 2),
                    'avg_result_count': round(basic_stats[5] or 0, 2),
                    'query_type_distribution': type_distribution,
                    'cache_hit_rate_24h': round(hit_rate, 2),
                    'total_queries_24h': total_queries,
                    'cache_hits_24h': cache_hits,
                    'cache_misses_24h': performance_stats[2] or 0,
                    'top_query_patterns': top_patterns
                }

            except Exception as e:
                self._logger.error(f"Failed to get cache statistics: {e}")
                return {}
            finally:
                conn.close()
