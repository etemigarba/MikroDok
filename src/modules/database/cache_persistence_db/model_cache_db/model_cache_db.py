"""
Module: model_cache_db
Description: Implements persistent caching layer for frequently accessed model metadata
Phase: 4
Location: /src/modules/database/cache_persistence_db/model_cache_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import hashlib

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
from src.modules.database.database_core_db.connection_manager_db.connection_manager_db import (
    ConnectionManagerDB, ConnectionType
)


class CacheStatus(Enum):
    """Cache entry status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    PENDING = "pending"


@dataclass
class ModelCacheEntry:
    """Model cache entry data structure."""
    cache_key: str
    model_id: str
    model_type: str
    model_metadata: Dict[str, Any]
    model_config: Dict[str, Any]
    model_size_bytes: int
    model_path: Optional[str]
    load_time_ms: float
    access_count: int
    hit_count: int
    miss_count: int
    last_accessed: datetime
    created_at: datetime
    expires_at: Optional[datetime]
    status: CacheStatus
    checksum: str
    version: str
    tags: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return {
            'cache_key': self.cache_key,
            'model_id': self.model_id,
            'model_type': self.model_type,
            'model_metadata': self.model_metadata,
            'model_config': self.model_config,
            'model_size_bytes': self.model_size_bytes,
            'model_path': self.model_path,
            'load_time_ms': self.load_time_ms,
            'access_count': self.access_count,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'last_accessed': self.last_accessed.isoformat(),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'status': self.status.value,
            'checksum': self.checksum,
            'version': self.version,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelCacheEntry':
        """Create entry from dictionary."""
        return cls(
            cache_key=data['cache_key'],
            model_id=data['model_id'],
            model_type=data['model_type'],
            model_metadata=data['model_metadata'],
            model_config=data['model_config'],
            model_size_bytes=data['model_size_bytes'],
            model_path=data['model_path'],
            load_time_ms=data['load_time_ms'],
            access_count=data['access_count'],
            hit_count=data['hit_count'],
            miss_count=data['miss_count'],
            last_accessed=datetime.fromisoformat(data['last_accessed']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None,
            status=CacheStatus(data['status']),
            checksum=data['checksum'],
            version=data['version'],
            tags=data['tags']
        )


@dataclass
class CacheStats:
    """Cache statistics data structure."""
    total_entries: int
    active_entries: int
    expired_entries: int
    total_size_bytes: int
    hit_rate: float
    miss_rate: float
    average_load_time_ms: float
    cache_efficiency: float
    last_cleanup: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return asdict(self)


class ModelCacheDB:
    """
    Persistent caching layer for frequently accessed model metadata.
    
    Provides high-performance caching with SQLite persistence, intelligent
    cache invalidation, TTL management, and comprehensive statistics tracking.
    Optimized for machine learning model metadata storage and retrieval.
    """
    
    def __init__(self, db_path: Optional[Path] = None, 
                 max_cache_size_mb: int = 500,
                 default_ttl_hours: int = 24,
                 cleanup_interval_minutes: int = 30):
        """
        Initialize model cache database.
        
        Args:
            db_path: Path to SQLite database file
            max_cache_size_mb: Maximum cache size in megabytes
            default_ttl_hours: Default TTL for cache entries in hours
            cleanup_interval_minutes: Cleanup interval in minutes
        """
        self._logger = get_logger(__name__)
        
        # Configuration
        self._db_path = db_path or Path("data/cache/model_cache.db")
        self._max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self._default_ttl = timedelta(hours=default_ttl_hours)
        self._cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Connection manager
        self._connection_manager: Optional[ConnectionManagerDB] = None
        
        # Background cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Statistics
        self._stats_cache: Optional[CacheStats] = None
        self._stats_last_updated: Optional[datetime] = None
        
        # Initialize database
        self._initialize_database()
        self._start_cleanup_thread()
        
        self._logger.info(f"ModelCacheDB initialized with max size: {max_cache_size_mb}MB")
    
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
            
            self._logger.info("Model cache database initialized successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize model cache database: {e}")
            raise
    
    def _create_schema(self) -> None:
        """Create database schema for model cache."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS model_cache (
            cache_key TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            model_type TEXT NOT NULL,
            model_metadata TEXT NOT NULL,
            model_config TEXT NOT NULL,
            model_size_bytes INTEGER NOT NULL,
            model_path TEXT,
            load_time_ms REAL NOT NULL,
            access_count INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            miss_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP,
            status TEXT NOT NULL,
            checksum TEXT NOT NULL,
            version TEXT NOT NULL,
            tags TEXT NOT NULL,
            UNIQUE(model_id, version)
        );
        
        CREATE INDEX IF NOT EXISTS idx_model_cache_model_id ON model_cache(model_id);
        CREATE INDEX IF NOT EXISTS idx_model_cache_model_type ON model_cache(model_type);
        CREATE INDEX IF NOT EXISTS idx_model_cache_status ON model_cache(status);
        CREATE INDEX IF NOT EXISTS idx_model_cache_expires_at ON model_cache(expires_at);
        CREATE INDEX IF NOT EXISTS idx_model_cache_last_accessed ON model_cache(last_accessed);
        CREATE INDEX IF NOT EXISTS idx_model_cache_created_at ON model_cache(created_at);
        
        CREATE TABLE IF NOT EXISTS cache_stats (
            id INTEGER PRIMARY KEY,
            total_entries INTEGER NOT NULL,
            active_entries INTEGER NOT NULL,
            expired_entries INTEGER NOT NULL,
            total_size_bytes INTEGER NOT NULL,
            hit_rate REAL NOT NULL,
            miss_rate REAL NOT NULL,
            average_load_time_ms REAL NOT NULL,
            cache_efficiency REAL NOT NULL,
            last_cleanup TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
        """
        
        with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def _generate_cache_key(self, model_id: str, version: str = "latest") -> str:
        """Generate cache key for model."""
        key_data = f"{model_id}:{version}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def _calculate_checksum(self, metadata: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Calculate checksum for model data."""
        data = json.dumps({"metadata": metadata, "config": config}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def put(self, model_id: str, model_type: str, metadata: Dict[str, Any],
            config: Dict[str, Any], model_size_bytes: int = 0,
            model_path: Optional[str] = None, load_time_ms: float = 0.0,
            version: str = "latest", tags: Optional[List[str]] = None,
            ttl_hours: Optional[int] = None) -> bool:
        """
        Store model metadata in cache.

        Args:
            model_id: Unique model identifier
            model_type: Type of model (e.g., 'transformer', 'embedding')
            metadata: Model metadata dictionary
            config: Model configuration dictionary
            model_size_bytes: Model size in bytes
            model_path: Path to model file
            load_time_ms: Model loading time in milliseconds
            version: Model version
            tags: List of tags for categorization
            ttl_hours: Time-to-live in hours (uses default if None)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self._lock:
                cache_key = self._generate_cache_key(model_id, version)
                checksum = self._calculate_checksum(metadata, config)
                now = datetime.now(timezone.utc)
                ttl = timedelta(hours=ttl_hours) if ttl_hours else self._default_ttl
                expires_at = now + ttl

                entry = ModelCacheEntry(
                    cache_key=cache_key,
                    model_id=model_id,
                    model_type=model_type,
                    model_metadata=metadata,
                    model_config=config,
                    model_size_bytes=model_size_bytes,
                    model_path=model_path,
                    load_time_ms=load_time_ms,
                    access_count=0,
                    hit_count=0,
                    miss_count=0,
                    last_accessed=now,
                    created_at=now,
                    expires_at=expires_at,
                    status=CacheStatus.ACTIVE,
                    checksum=checksum,
                    version=version,
                    tags=tags or []
                )

                # Check cache size limits
                if not self._check_cache_limits(model_size_bytes):
                    self._evict_entries(model_size_bytes)

                # Insert or update entry
                sql = """
                INSERT OR REPLACE INTO model_cache (
                    cache_key, model_id, model_type, model_metadata, model_config,
                    model_size_bytes, model_path, load_time_ms, access_count,
                    hit_count, miss_count, last_accessed, created_at, expires_at,
                    status, checksum, version, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params = (
                    entry.cache_key, entry.model_id, entry.model_type,
                    json.dumps(entry.model_metadata), json.dumps(entry.model_config),
                    entry.model_size_bytes, entry.model_path, entry.load_time_ms,
                    entry.access_count, entry.hit_count, entry.miss_count,
                    entry.last_accessed, entry.created_at, entry.expires_at,
                    entry.status.value, entry.checksum, entry.version,
                    json.dumps(entry.tags)
                )

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    conn.execute(sql, params)
                    conn.commit()

                self._invalidate_stats_cache()
                self._logger.debug(f"Stored model cache entry: {model_id}:{version}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to store model cache entry {model_id}: {e}")
            return False

    def get(self, model_id: str, version: str = "latest") -> Optional[ModelCacheEntry]:
        """
        Retrieve model metadata from cache.

        Args:
            model_id: Model identifier
            version: Model version

        Returns:
            ModelCacheEntry if found and valid, None otherwise
        """
        try:
            with self._lock:
                cache_key = self._generate_cache_key(model_id, version)

                sql = """
                SELECT * FROM model_cache
                WHERE cache_key = ? AND status = 'active'
                """

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql, (cache_key,))
                    row = cursor.fetchone()

                if not row:
                    self._record_miss(model_id)
                    return None

                # Convert row to entry
                entry = self._row_to_entry(row)

                # Check expiration
                if entry.expires_at and datetime.now(timezone.utc) > entry.expires_at:
                    self._mark_expired(cache_key)
                    self._record_miss(model_id)
                    return None

                # Update access statistics
                self._update_access_stats(cache_key)
                self._record_hit(model_id)

                return entry

        except Exception as e:
            self._logger.error(f"Failed to retrieve model cache entry {model_id}: {e}")
            return None

    def invalidate(self, model_id: str, version: Optional[str] = None) -> bool:
        """
        Invalidate cache entries for a model.

        Args:
            model_id: Model identifier
            version: Specific version to invalidate (all versions if None)

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            with self._lock:
                if version:
                    cache_key = self._generate_cache_key(model_id, version)
                    sql = "UPDATE model_cache SET status = 'invalidated' WHERE cache_key = ?"
                    params = (cache_key,)
                else:
                    sql = "UPDATE model_cache SET status = 'invalidated' WHERE model_id = ?"
                    params = (model_id,)

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, params)
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Invalidated {affected_rows} cache entries for {model_id}")
                return affected_rows > 0

        except Exception as e:
            self._logger.error(f"Failed to invalidate cache entries for {model_id}: {e}")
            return False

    def delete(self, model_id: str, version: Optional[str] = None) -> bool:
        """
        Delete cache entries for a model.

        Args:
            model_id: Model identifier
            version: Specific version to delete (all versions if None)

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            with self._lock:
                if version:
                    cache_key = self._generate_cache_key(model_id, version)
                    sql = "DELETE FROM model_cache WHERE cache_key = ?"
                    params = (cache_key,)
                else:
                    sql = "DELETE FROM model_cache WHERE model_id = ?"
                    params = (model_id,)

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql, params)
                    conn.commit()
                    affected_rows = cursor.rowcount

                self._invalidate_stats_cache()
                self._logger.debug(f"Deleted {affected_rows} cache entries for {model_id}")
                return affected_rows > 0

        except Exception as e:
            self._logger.error(f"Failed to delete cache entries for {model_id}: {e}")
            return False

    def list_models(self, model_type: Optional[str] = None,
                   status: CacheStatus = CacheStatus.ACTIVE) -> List[str]:
        """
        List cached model IDs.

        Args:
            model_type: Filter by model type
            status: Filter by cache status

        Returns:
            List of model IDs
        """
        try:
            sql = "SELECT DISTINCT model_id FROM model_cache WHERE status = ?"
            params = [status.value]

            if model_type:
                sql += " AND model_type = ?"
                params.append(model_type)

            sql += " ORDER BY model_id"

            with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                cursor = conn.execute(sql, params)
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            self._logger.error(f"Failed to list models: {e}")
            return []

    def get_stats(self, force_refresh: bool = False) -> CacheStats:
        """
        Get cache statistics.

        Args:
            force_refresh: Force refresh of cached statistics

        Returns:
            CacheStats object
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
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_entries,
                    SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired_entries,
                    SUM(model_size_bytes) as total_size_bytes,
                    AVG(CASE WHEN access_count > 0 THEN CAST(hit_count AS REAL) / access_count ELSE 0 END) as hit_rate,
                    AVG(CASE WHEN access_count > 0 THEN CAST(miss_count AS REAL) / access_count ELSE 0 END) as miss_rate,
                    AVG(load_time_ms) as average_load_time_ms
                FROM model_cache
                """

                with self._connection_manager.get_connection(ConnectionType.READ_ONLY) as conn:
                    cursor = conn.execute(sql)
                    row = cursor.fetchone()

                if row:
                    total_entries = row[0] or 0
                    active_entries = row[1] or 0
                    expired_entries = row[2] or 0
                    total_size_bytes = row[3] or 0
                    hit_rate = row[4] or 0.0
                    miss_rate = row[5] or 0.0
                    average_load_time_ms = row[6] or 0.0

                    # Calculate cache efficiency
                    cache_efficiency = hit_rate / (hit_rate + miss_rate) if (hit_rate + miss_rate) > 0 else 0.0

                    stats = CacheStats(
                        total_entries=total_entries,
                        active_entries=active_entries,
                        expired_entries=expired_entries,
                        total_size_bytes=total_size_bytes,
                        hit_rate=hit_rate,
                        miss_rate=miss_rate,
                        average_load_time_ms=average_load_time_ms,
                        cache_efficiency=cache_efficiency,
                        last_cleanup=datetime.now(timezone.utc)
                    )

                    # Cache the stats
                    self._stats_cache = stats
                    self._stats_last_updated = datetime.now(timezone.utc)

                    return stats
                else:
                    return CacheStats(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, datetime.now(timezone.utc))

        except Exception as e:
            self._logger.error(f"Failed to get cache statistics: {e}")
            return CacheStats(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, datetime.now(timezone.utc))

    def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.

        Returns:
            Number of entries cleaned up
        """
        try:
            with self._lock:
                now = datetime.now(timezone.utc)

                # Mark expired entries
                sql_mark = """
                UPDATE model_cache
                SET status = 'expired'
                WHERE expires_at < ? AND status = 'active'
                """

                # Delete expired entries
                sql_delete = "DELETE FROM model_cache WHERE status = 'expired'"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    cursor = conn.execute(sql_mark, (now,))
                    marked_count = cursor.rowcount

                    cursor = conn.execute(sql_delete)
                    deleted_count = cursor.rowcount

                    conn.commit()

                self._invalidate_stats_cache()
                self._logger.debug(f"Cleaned up {deleted_count} expired cache entries")
                return deleted_count

        except Exception as e:
            self._logger.error(f"Failed to cleanup expired entries: {e}")
            return 0

    def _check_cache_limits(self, additional_size: int = 0) -> bool:
        """Check if cache is within size limits."""
        try:
            sql = "SELECT SUM(model_size_bytes) FROM model_cache WHERE status = 'active'"

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
            SELECT cache_key, model_size_bytes
            FROM model_cache
            WHERE status = 'active'
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
                sql_evict = f"DELETE FROM model_cache WHERE cache_key IN ({placeholders})"

                with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                    conn.execute(sql_evict, keys_to_evict)
                    conn.commit()

                self._logger.debug(f"Evicted {len(keys_to_evict)} entries, freed {freed_space} bytes")

        except Exception as e:
            self._logger.error(f"Failed to evict cache entries: {e}")

    def _row_to_entry(self, row: sqlite3.Row) -> ModelCacheEntry:
        """Convert database row to ModelCacheEntry."""
        return ModelCacheEntry(
            cache_key=row['cache_key'],
            model_id=row['model_id'],
            model_type=row['model_type'],
            model_metadata=json.loads(row['model_metadata']),
            model_config=json.loads(row['model_config']),
            model_size_bytes=row['model_size_bytes'],
            model_path=row['model_path'],
            load_time_ms=row['load_time_ms'],
            access_count=row['access_count'],
            hit_count=row['hit_count'],
            miss_count=row['miss_count'],
            last_accessed=datetime.fromisoformat(row['last_accessed']),
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            status=CacheStatus(row['status']),
            checksum=row['checksum'],
            version=row['version'],
            tags=json.loads(row['tags'])
        )

    def _update_access_stats(self, cache_key: str) -> None:
        """Update access statistics for cache entry."""
        try:
            sql = """
            UPDATE model_cache
            SET access_count = access_count + 1,
                last_accessed = ?
            WHERE cache_key = ?
            """

            with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                conn.execute(sql, (datetime.now(timezone.utc), cache_key))
                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to update access stats: {e}")

    def _record_hit(self, model_id: str) -> None:
        """Record cache hit for model."""
        try:
            sql = "UPDATE model_cache SET hit_count = hit_count + 1 WHERE model_id = ?"

            with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                conn.execute(sql, (model_id,))
                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to record cache hit: {e}")

    def _record_miss(self, model_id: str) -> None:
        """Record cache miss for model."""
        try:
            sql = "UPDATE model_cache SET miss_count = miss_count + 1 WHERE model_id = ?"

            with self._connection_manager.get_connection(ConnectionType.READ_WRITE) as conn:
                conn.execute(sql, (model_id,))
                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to record cache miss: {e}")

    def _mark_expired(self, cache_key: str) -> None:
        """Mark cache entry as expired."""
        try:
            sql = "UPDATE model_cache SET status = 'expired' WHERE cache_key = ?"

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

            self._logger.info("ModelCacheDB closed successfully")

        except Exception as e:
            self._logger.error(f"Error closing ModelCacheDB: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
