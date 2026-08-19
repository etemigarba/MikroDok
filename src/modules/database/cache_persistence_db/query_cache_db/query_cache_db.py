"""
Module: query_cache_db
Description: Caches database query results with intelligent invalidation rules
Phase: 4
Location: /src/modules/database/cache_persistence_db/query_cache_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import time
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Set
import hashlib

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
from src.modules.database.database_core_db.connection_manager_db.connection_manager_db import (
    ConnectionManagerDB, ConnectionType
)


class QueryType(Enum):
    """Query type enumeration."""
    SELECT = "select"
    COUNT = "count"
    AGGREGATE = "aggregate"
    JOIN = "join"
    SEARCH = "search"


class InvalidationRule(Enum):
    """Cache invalidation rule enumeration."""
    TTL_ONLY = "ttl_only"
    TABLE_BASED = "table_based"
    DEPENDENCY_BASED = "dependency_based"
    MANUAL = "manual"


@dataclass
class QueryCacheEntry:
    """Query cache entry data structure."""
    cache_key: str
    query_hash: str
    query_text: str
    query_params: List[Any]
    query_type: QueryType
    result_data: Any
    result_size_bytes: int
    execution_time_ms: float
    access_count: int
    hit_count: int
    last_accessed: datetime
    created_at: datetime
    expires_at: Optional[datetime]
    invalidation_rule: InvalidationRule
    dependent_tables: Set[str]
    tags: List[str]
    compressed: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return {
            'cache_key': self.cache_key,
            'query_hash': self.query_hash,
            'query_text': self.query_text,
            'query_params': self.query_params,
            'query_type': self.query_type.value,
            'result_data': self.result_data,
            'result_size_bytes': self.result_size_bytes,
            'execution_time_ms': self.execution_time_ms,
            'access_count': self.access_count,
            'hit_count': self.hit_count,
            'last_accessed': self.last_accessed.isoformat(),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'invalidation_rule': self.invalidation_rule.value,
            'dependent_tables': list(self.dependent_tables),
            'tags': self.tags,
            'compressed': self.compressed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueryCacheEntry':
        """Create entry from dictionary."""
        return cls(
            cache_key=data['cache_key'],
            query_hash=data['query_hash'],
            query_text=data['query_text'],
            query_params=data['query_params'],
            query_type=QueryType(data['query_type']),
            result_data=data['result_data'],
            result_size_bytes=data['result_size_bytes'],
            execution_time_ms=data['execution_time_ms'],
            access_count=data['access_count'],
            hit_count=data['hit_count'],
            last_accessed=datetime.fromisoformat(data['last_accessed']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None,
            invalidation_rule=InvalidationRule(data['invalidation_rule']),
            dependent_tables=set(data['dependent_tables']),
            tags=data['tags'],
            compressed=data['compressed']
        )


@dataclass
class QueryCacheStats:
    """Query cache statistics data structure."""
    total_entries: int
    active_entries: int
    expired_entries: int
    total_size_bytes: int
    compressed_size_bytes: int
    hit_rate: float
    miss_rate: float
    average_execution_time_ms: float
    cache_efficiency: float
    compression_ratio: float
    last_cleanup: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return asdict(self)


class QueryCacheDB:
    """
    Database query result caching with intelligent invalidation rules.
    
    Provides high-performance caching of database query results with TTL management,
    table-based invalidation, compression, and comprehensive statistics tracking.
    Optimized for frequently executed queries with stable results.
    """
    
    def __init__(self, db_path: Optional[Path] = None,
                 max_cache_size_mb: int = 200,
                 default_ttl_minutes: int = 60,
                 compression_threshold_bytes: int = 1024,
                 cleanup_interval_minutes: int = 15):
        """
        Initialize query cache database.
        
        Args:
            db_path: Path to SQLite database file
            max_cache_size_mb: Maximum cache size in megabytes
            default_ttl_minutes: Default TTL for cache entries in minutes
            compression_threshold_bytes: Compress results larger than this
            cleanup_interval_minutes: Cleanup interval in minutes
        """
        self._logger = get_logger(__name__)
        
        # Configuration
        self._db_path = db_path or Path("data/cache/query_cache.db")
        self._max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self._default_ttl = timedelta(minutes=default_ttl_minutes)
        self._compression_threshold = compression_threshold_bytes
        self._cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Connection manager
        self._connection_manager: Optional[ConnectionManagerDB] = None
        
        # Background cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Table dependency tracking
        self._table_dependencies: Dict[str, Set[str]] = {}
        
        # Statistics
        self._stats_cache: Optional[QueryCacheStats] = None
        self._stats_last_updated: Optional[datetime] = None
        
        # Initialize database
        self._initialize_database()
        self._start_cleanup_thread()
        
        self._logger.info(f"QueryCacheDB initialized with max size: {max_cache_size_mb}MB")
    
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
            
            self._logger.info("Query cache database initialized successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize query cache database: {e}")
            raise
    
    def _create_schema(self) -> None:
        """Create database schema for query cache."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS query_cache (
            cache_key TEXT PRIMARY KEY,
            query_hash TEXT NOT NULL,
            query_text TEXT NOT NULL,
            query_params TEXT NOT NULL,
            query_type TEXT NOT NULL,
            result_data BLOB NOT NULL,
            result_size_bytes INTEGER NOT NULL,
            execution_time_ms REAL NOT NULL,
            access_count INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP,
            invalidation_rule TEXT NOT NULL,
            dependent_tables TEXT NOT NULL,
            tags TEXT NOT NULL,
            compressed INTEGER DEFAULT 0
        );
        
        CREATE INDEX IF NOT EXISTS idx_query_cache_query_hash ON query_cache(query_hash);
        CREATE INDEX IF NOT EXISTS idx_query_cache_query_type ON query_cache(query_type);
        CREATE INDEX IF NOT EXISTS idx_query_cache_expires_at ON query_cache(expires_at);
        CREATE INDEX IF NOT EXISTS idx_query_cache_last_accessed ON query_cache(last_accessed);
        CREATE INDEX IF NOT EXISTS idx_query_cache_created_at ON query_cache(created_at);
        
        CREATE TABLE IF NOT EXISTS table_dependencies (
            table_name TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            PRIMARY KEY (table_name, cache_key),
            FOREIGN KEY (cache_key) REFERENCES query_cache(cache_key) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_table_dependencies_table_name ON table_dependencies(table_name);
        CREATE INDEX IF NOT EXISTS idx_table_dependencies_cache_key ON table_dependencies(cache_key);
        
        CREATE TABLE IF NOT EXISTS cache_stats (
            id INTEGER PRIMARY KEY,
            total_entries INTEGER NOT NULL,
            active_entries INTEGER NOT NULL,
            expired_entries INTEGER NOT NULL,
            total_size_bytes INTEGER NOT NULL,
            compressed_size_bytes INTEGER NOT NULL,
            hit_rate REAL NOT NULL,
            miss_rate REAL NOT NULL,
            average_execution_time_ms REAL NOT NULL,
            cache_efficiency REAL NOT NULL,
            compression_ratio REAL NOT NULL,
            last_cleanup TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
        """
        
        with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def _generate_query_hash(self, query_text: str, params: List[Any]) -> str:
        """Generate hash for query and parameters."""
        query_data = f"{query_text}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(query_data.encode()).hexdigest()

    def _generate_cache_key(self, query_hash: str) -> str:
        """Generate cache key from query hash."""
        return f"query_{query_hash[:32]}"

    def _compress_data(self, data: Any) -> Tuple[bytes, bool]:
        """Compress data if it exceeds threshold."""
        serialized = json.dumps(data).encode('utf-8')

        if len(serialized) > self._compression_threshold:
            compressed = zlib.compress(serialized, level=6)
            return compressed, True
        else:
            return serialized, False

    def _decompress_data(self, data: bytes, compressed: bool) -> Any:
        """Decompress data if needed."""
        if compressed:
            decompressed = zlib.decompress(data)
            return json.loads(decompressed.decode('utf-8'))
        else:
            return json.loads(data.decode('utf-8'))

    def _extract_table_names(self, query_text: str) -> Set[str]:
        """Extract table names from SQL query."""
        # Simple table name extraction (can be enhanced with SQL parser)
        import re

        # Remove comments and normalize whitespace
        query = re.sub(r'--.*?\n', ' ', query_text)
        query = re.sub(r'/\*.*?\*/', ' ', query, flags=re.DOTALL)
        query = re.sub(r'\s+', ' ', query).strip().lower()

        tables = set()

        # Extract FROM clauses
        from_matches = re.findall(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', query)
        tables.update(from_matches)

        # Extract JOIN clauses
        join_matches = re.findall(r'\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)', query)
        tables.update(join_matches)

        # Extract UPDATE clauses
        update_matches = re.findall(r'\bupdate\s+([a-zA-Z_][a-zA-Z0-9_]*)', query)
        tables.update(update_matches)

        # Extract INSERT INTO clauses
        insert_matches = re.findall(r'\binsert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)', query)
        tables.update(insert_matches)

        # Extract DELETE FROM clauses
        delete_matches = re.findall(r'\bdelete\s+from\s+([a-zA-Z_][a-zA-Z0-9_]*)', query)
        tables.update(delete_matches)

        return tables

    def _classify_query_type(self, query_text: str) -> QueryType:
        """Classify query type based on SQL text."""
        query_lower = query_text.lower().strip()

        if query_lower.startswith('select'):
            if 'count(' in query_lower:
                return QueryType.COUNT
            elif any(func in query_lower for func in ['sum(', 'avg(', 'max(', 'min(', 'group by']):
                return QueryType.AGGREGATE
            elif 'join' in query_lower:
                return QueryType.JOIN
            elif any(keyword in query_lower for keyword in ['like', 'match', 'fts']):
                return QueryType.SEARCH
            else:
                return QueryType.SELECT
        else:
            return QueryType.SELECT

    def put(self, query_text: str, params: List[Any], result_data: Any,
            execution_time_ms: float, ttl_minutes: Optional[int] = None,
            invalidation_rule: InvalidationRule = InvalidationRule.TTL_ONLY,
            tags: Optional[List[str]] = None) -> bool:
        """
        Store query result in cache.

        Args:
            query_text: SQL query text
            params: Query parameters
            result_data: Query result data
            execution_time_ms: Query execution time in milliseconds
            ttl_minutes: Time-to-live in minutes (uses default if None)
            invalidation_rule: Cache invalidation rule
            tags: List of tags for categorization

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self._lock:
                query_hash = self._generate_query_hash(query_text, params)
                cache_key = self._generate_cache_key(query_hash)
                query_type = self._classify_query_type(query_text)
                dependent_tables = self._extract_table_names(query_text)

                # Compress result data
                compressed_data, is_compressed = self._compress_data(result_data)

                now = datetime.now(timezone.utc)
                ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self._default_ttl
                expires_at = now + ttl

                entry = QueryCacheEntry(
                    cache_key=cache_key,
                    query_hash=query_hash,
                    query_text=query_text,
                    query_params=params,
                    query_type=query_type,
                    result_data=result_data,
                    result_size_bytes=len(compressed_data),
                    execution_time_ms=execution_time_ms,
                    access_count=0,
                    hit_count=0,
                    last_accessed=now,
                    created_at=now,
                    expires_at=expires_at,
                    invalidation_rule=invalidation_rule,
                    dependent_tables=dependent_tables,
                    tags=tags or [],
                    compressed=is_compressed
                )

                # Check cache size limits
                if not self._check_cache_limits(len(compressed_data)):
                    self._evict_entries(len(compressed_data))

                # Insert or update entry
                sql = """
                INSERT OR REPLACE INTO query_cache (
                    cache_key, query_hash, query_text, query_params, query_type,
                    result_data, result_size_bytes, execution_time_ms, access_count,
                    hit_count, last_accessed, created_at, expires_at,
                    invalidation_rule, dependent_tables, tags, compressed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params_data = (
                    entry.cache_key, entry.query_hash, entry.query_text,
                    json.dumps(entry.query_params), entry.query_type.value,
                    compressed_data, entry.result_size_bytes, entry.execution_time_ms,
                    entry.access_count, entry.hit_count, entry.last_accessed,
                    entry.created_at, entry.expires_at, entry.invalidation_rule.value,
                    json.dumps(list(entry.dependent_tables)), json.dumps(entry.tags),
                    1 if entry.compressed else 0
                )

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    conn.execute(sql, params_data)

                    # Update table dependencies
                    if dependent_tables:
                        # Remove old dependencies
                        conn.execute("DELETE FROM table_dependencies WHERE cache_key = ?", (cache_key,))

                        # Add new dependencies
                        for table_name in dependent_tables:
                            conn.execute(
                                "INSERT INTO table_dependencies (table_name, cache_key, created_at) VALUES (?, ?, ?)",
                                (table_name, cache_key, now)
                            )

                    conn.commit()

                self._invalidate_stats_cache()
                self._logger.debug(f"Stored query cache entry: {cache_key}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to store query cache entry: {e}")
            return False

    def get(self, query_text: str, params: List[Any]) -> Optional[Any]:
        """
        Retrieve query result from cache.

        Args:
            query_text: SQL query text
            params: Query parameters

        Returns:
            Cached result data if found and valid, None otherwise
        """
        try:
            with self._lock:
                query_hash = self._generate_query_hash(query_text, params)
                cache_key = self._generate_cache_key(query_hash)

                sql = """
                SELECT result_data, compressed, expires_at, cache_key
                FROM query_cache
                WHERE cache_key = ?
                """

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql, (cache_key,))
                    row = cursor.fetchone()

                if not row:
                    return None

                result_data, compressed, expires_at, cache_key = row

                # Check expiration
                if expires_at:
                    expires_dt = datetime.fromisoformat(expires_at)
                    if datetime.now(timezone.utc) > expires_dt:
                        self._mark_expired(cache_key)
                        return None

                # Update access statistics
                self._update_access_stats(cache_key)

                # Decompress and return result
                return self._decompress_data(result_data, bool(compressed))

        except Exception as e:
            self._logger.error(f"Failed to retrieve query cache entry: {e}")
            return None

    def invalidate_by_table(self, table_name: str) -> int:
        """
        Invalidate cache entries that depend on a specific table.

        Args:
            table_name: Name of the table that was modified

        Returns:
            Number of entries invalidated
        """
        try:
            with self._lock:
                # Get cache keys that depend on this table
                sql = "SELECT cache_key FROM table_dependencies WHERE table_name = ?"

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql, (table_name,))
                    cache_keys = [row[0] for row in cursor.fetchall()]

                if not cache_keys:
                    return 0

                # Delete cache entries
                placeholders = ','.join(['?'] * len(cache_keys))
                sql_delete = f"DELETE FROM query_cache WHERE cache_key IN ({placeholders})"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql_delete, cache_keys)
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Invalidated {affected_rows} cache entries for table: {table_name}")
                return affected_rows

        except Exception as e:
            self._logger.error(f"Failed to invalidate cache entries for table {table_name}: {e}")
            return 0

    def invalidate_by_query(self, query_text: str, params: List[Any]) -> bool:
        """
        Invalidate specific query cache entry.

        Args:
            query_text: SQL query text
            params: Query parameters

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            with self._lock:
                query_hash = self._generate_query_hash(query_text, params)
                cache_key = self._generate_cache_key(query_hash)

                sql = "DELETE FROM query_cache WHERE cache_key = ?"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, (cache_key,))
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                return affected_rows > 0

        except Exception as e:
            self._logger.error(f"Failed to invalidate query cache entry: {e}")
            return False

    def clear_all(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        try:
            with self._lock:
                sql = "DELETE FROM query_cache"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql)
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Cleared {affected_rows} cache entries")
                return affected_rows

        except Exception as e:
            self._logger.error(f"Failed to clear cache: {e}")
            return 0

    def get_stats(self, force_refresh: bool = False) -> QueryCacheStats:
        """
        Get cache statistics.

        Args:
            force_refresh: Force refresh of cached statistics

        Returns:
            QueryCacheStats object
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
                    SUM(result_size_bytes) as total_size_bytes,
                    SUM(CASE WHEN compressed = 1 THEN result_size_bytes ELSE 0 END) as compressed_size_bytes,
                    AVG(CASE WHEN access_count > 0 THEN CAST(hit_count AS REAL) / access_count ELSE 0 END) as hit_rate,
                    AVG(execution_time_ms) as average_execution_time_ms
                FROM query_cache
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
                    hit_rate = row[5] or 0.0
                    average_execution_time_ms = row[6] or 0.0

                    # Calculate derived metrics
                    miss_rate = 1.0 - hit_rate if hit_rate > 0 else 0.0
                    cache_efficiency = hit_rate
                    compression_ratio = (compressed_size_bytes / total_size_bytes) if total_size_bytes > 0 else 0.0

                    stats = QueryCacheStats(
                        total_entries=total_entries,
                        active_entries=active_entries,
                        expired_entries=expired_entries,
                        total_size_bytes=total_size_bytes,
                        compressed_size_bytes=compressed_size_bytes,
                        hit_rate=hit_rate,
                        miss_rate=miss_rate,
                        average_execution_time_ms=average_execution_time_ms,
                        cache_efficiency=cache_efficiency,
                        compression_ratio=compression_ratio,
                        last_cleanup=datetime.now(timezone.utc)
                    )

                    # Cache the stats
                    self._stats_cache = stats
                    self._stats_last_updated = datetime.now(timezone.utc)

                    return stats
                else:
                    return QueryCacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, datetime.now(timezone.utc))

        except Exception as e:
            self._logger.error(f"Failed to get cache statistics: {e}")
            return QueryCacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, datetime.now(timezone.utc))

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
                sql = "DELETE FROM query_cache WHERE expires_at < ?"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, (now,))
                    conn.commit()
                    deleted_count = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Cleaned up {deleted_count} expired cache entries")
                return deleted_count

        except Exception as e:
            self._logger.error(f"Failed to cleanup expired entries: {e}")
            return 0

    def _check_cache_limits(self, additional_size: int = 0) -> bool:
        """Check if cache is within size limits."""
        try:
            sql = "SELECT SUM(result_size_bytes) FROM query_cache"

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
            SELECT cache_key, result_size_bytes
            FROM query_cache
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
                sql_evict = f"DELETE FROM query_cache WHERE cache_key IN ({placeholders})"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    conn.execute(sql_evict, keys_to_evict)
                    conn.commit()

                self._logger.debug(f"Evicted {len(keys_to_evict)} entries, freed {freed_space} bytes")

        except Exception as e:
            self._logger.error(f"Failed to evict cache entries: {e}")

    def _update_access_stats(self, cache_key: str) -> None:
        """Update access statistics for cache entry."""
        try:
            sql = """
            UPDATE query_cache
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
            sql = "DELETE FROM query_cache WHERE cache_key = ?"

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

            self._logger.info("QueryCacheDB closed successfully")

        except Exception as e:
            self._logger.error(f"Error closing QueryCacheDB: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
