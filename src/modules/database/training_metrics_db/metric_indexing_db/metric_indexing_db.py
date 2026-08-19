"""
Module: metric_indexing_db
Description: Indexes metrics for efficient querying and analysis with advanced search capabilities and query optimization
Phase: 4
Location: /src/modules/database/training_metrics_db/metric_indexing_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Set
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from src.modules.logic.common.logging_utils import get_logger


class IndexType(Enum):
    """Types of metric indexes."""
    BTREE = "btree"
    HASH = "hash"
    COMPOSITE = "composite"
    FULL_TEXT = "full_text"
    TIME_SERIES = "time_series"


class QueryOperator(Enum):
    """Query operators for metric searches."""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    BETWEEN = "BETWEEN"
    IN = "IN"
    NOT_IN = "NOT IN"
    LIKE = "LIKE"
    CONTAINS = "CONTAINS"


@dataclass
class IndexDefinition:
    """Definition of a metric index."""
    index_id: str
    index_name: str
    index_type: IndexType
    columns: List[str]
    session_id: Optional[str] = None
    metric_names: Optional[List[str]] = None
    is_unique: bool = False
    is_partial: bool = False
    condition: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class QueryCondition:
    """Query condition for metric searches."""
    column: str
    operator: QueryOperator
    value: Any
    values: Optional[List[Any]] = None  # For IN, NOT IN, BETWEEN operators


@dataclass
class SearchQuery:
    """Complex search query for metrics."""
    session_ids: Optional[List[str]] = None
    metric_names: Optional[List[str]] = None
    metric_types: Optional[List[str]] = None
    conditions: Optional[List[QueryCondition]] = None
    time_range: Optional[Tuple[datetime, datetime]] = None
    epoch_range: Optional[Tuple[int, int]] = None
    step_range: Optional[Tuple[int, int]] = None
    value_range: Optional[Tuple[float, float]] = None
    tags: Optional[List[str]] = None
    order_by: Optional[str] = None
    ascending: bool = True
    limit: Optional[int] = None
    offset: Optional[int] = None


@dataclass
class IndexStatistics:
    """Statistics about an index."""
    index_id: str
    index_name: str
    table_name: str
    column_count: int
    row_count: int
    unique_values: int
    selectivity: float
    size_bytes: int
    last_updated: datetime
    usage_count: int


class MetricIndexingDB:
    """
    Database operations for metrics indexing and efficient querying.
    
    Provides advanced indexing capabilities for training metrics with
    query optimization, search functionality, and performance monitoring.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the metric indexing database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training metrics data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_metrics"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "metric_indexing.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._max_indexes_per_table = 20  # Maximum indexes per table
        self._index_rebuild_threshold = 0.3  # Rebuild when 30% of data changes
        self._query_cache_size = 1000  # Maximum cached queries
        self._statistics_update_interval = 3600  # Update stats every hour
        
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
                
                # Create metric indexes registry table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_indexes (
                        index_id TEXT PRIMARY KEY,
                        index_name TEXT UNIQUE NOT NULL,
                        index_type TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        columns_json TEXT NOT NULL,
                        session_id TEXT,
                        metric_names_json TEXT,
                        is_unique BOOLEAN NOT NULL DEFAULT 0,
                        is_partial BOOLEAN NOT NULL DEFAULT 0,
                        condition_sql TEXT,
                        metadata_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_rebuilt TEXT,
                        usage_count INTEGER NOT NULL DEFAULT 0
                    )
                """)
                
                # Create index statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS index_statistics (
                        stat_id TEXT PRIMARY KEY,
                        index_id TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        column_count INTEGER NOT NULL,
                        row_count INTEGER NOT NULL,
                        unique_values INTEGER NOT NULL,
                        selectivity REAL NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (index_id) REFERENCES metric_indexes(index_id)
                    )
                """)
                
                # Create query cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_cache (
                        cache_id TEXT PRIMARY KEY,
                        query_hash TEXT UNIQUE NOT NULL,
                        query_sql TEXT NOT NULL,
                        result_count INTEGER NOT NULL,
                        execution_time_ms REAL NOT NULL,
                        indexes_used_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_accessed TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER NOT NULL DEFAULT 1
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_cache_hash 
                    ON query_cache(query_hash)
                """)
                
                # Create search patterns table for optimization
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS search_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        pattern_hash TEXT UNIQUE NOT NULL,
                        pattern_description TEXT NOT NULL,
                        columns_used_json TEXT NOT NULL,
                        frequency INTEGER NOT NULL DEFAULT 1,
                        avg_execution_time_ms REAL NOT NULL,
                        suggested_indexes_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_used TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_patterns_frequency 
                    ON search_patterns(frequency DESC)
                """)
                
                # Create metric value ranges table for optimization
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_value_ranges (
                        range_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        min_value REAL NOT NULL,
                        max_value REAL NOT NULL,
                        avg_value REAL NOT NULL,
                        value_count INTEGER NOT NULL,
                        distinct_values INTEGER NOT NULL,
                        last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(session_id, metric_name)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_value_ranges_session_metric 
                    ON metric_value_ranges(session_id, metric_name)
                """)
                
                conn.commit()
                self._logger.info("Metric indexing database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize metric indexing database: {e}")
                raise
            finally:
                conn.close()

    def create_index(self, index_name: str, table_name: str, columns: List[str],
                    index_type: IndexType = IndexType.BTREE,
                    session_id: Optional[str] = None,
                    metric_names: Optional[List[str]] = None,
                    is_unique: bool = False,
                    condition: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new index for metrics.

        Args:
            index_name: Name of the index
            table_name: Target table name
            columns: List of columns to index
            index_type: Type of index to create
            session_id: Optional session filter
            metric_names: Optional metric names filter
            is_unique: Whether index should enforce uniqueness
            condition: Optional WHERE condition for partial index
            metadata: Additional metadata

        Returns:
            Index ID
        """
        index_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build index creation SQL
                index_sql = self._build_index_sql(
                    index_name, table_name, columns, index_type,
                    is_unique, condition
                )

                # Create the actual index
                cursor.execute(index_sql)

                # Register the index
                cursor.execute("""
                    INSERT INTO metric_indexes (
                        index_id, index_name, index_type, table_name,
                        columns_json, session_id, metric_names_json,
                        is_unique, is_partial, condition_sql, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    index_id, index_name, index_type.value, table_name,
                    json.dumps(columns), session_id,
                    json.dumps(metric_names) if metric_names else None,
                    is_unique, bool(condition), condition,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Created index {index_name} on {table_name}")
                return index_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create index: {e}")
                raise
            finally:
                conn.close()

    def _build_index_sql(self, index_name: str, table_name: str, columns: List[str],
                        index_type: IndexType, is_unique: bool,
                        condition: Optional[str] = None) -> str:
        """Build SQL for index creation."""
        unique_clause = "UNIQUE " if is_unique else ""
        columns_clause = ", ".join(columns)
        where_clause = f" WHERE {condition}" if condition else ""

        return f"CREATE {unique_clause}INDEX {index_name} ON {table_name}({columns_clause}){where_clause}"

    def search_metrics(self, query: SearchQuery) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search metrics using advanced query capabilities.

        Args:
            query: Search query parameters

        Returns:
            Tuple of (results, query_metadata)
        """
        start_time = datetime.now()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build optimized query
                sql, params = self._build_search_sql(query)

                # Execute query
                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # Get column names
                column_names = [description[0] for description in cursor.description]

                # Convert to dictionaries
                results = [dict(zip(column_names, row)) for row in rows]

                # Calculate execution time
                execution_time = (datetime.now() - start_time).total_seconds() * 1000

                # Cache query for optimization
                self._cache_query(sql, len(results), execution_time)

                # Build query metadata
                query_metadata = {
                    'execution_time_ms': execution_time,
                    'result_count': len(results),
                    'query_sql': sql,
                    'parameters': params,
                    'timestamp': start_time.isoformat()
                }

                return results, query_metadata

            except Exception as e:
                self._logger.error(f"Failed to search metrics: {e}")
                raise
            finally:
                conn.close()

    def _build_search_sql(self, query: SearchQuery) -> Tuple[str, List[Any]]:
        """Build optimized SQL query from search parameters."""
        # Base query
        sql_parts = ["SELECT * FROM training_metrics WHERE 1=1"]
        params = []

        # Session filter
        if query.session_ids:
            placeholders = ",".join("?" * len(query.session_ids))
            sql_parts.append(f"AND session_id IN ({placeholders})")
            params.extend(query.session_ids)

        # Metric names filter
        if query.metric_names:
            placeholders = ",".join("?" * len(query.metric_names))
            sql_parts.append(f"AND metric_name IN ({placeholders})")
            params.extend(query.metric_names)

        # Metric types filter
        if query.metric_types:
            placeholders = ",".join("?" * len(query.metric_types))
            sql_parts.append(f"AND metric_type IN ({placeholders})")
            params.extend(query.metric_types)

        # Time range filter
        if query.time_range:
            sql_parts.append("AND timestamp BETWEEN ? AND ?")
            params.extend([query.time_range[0].isoformat(), query.time_range[1].isoformat()])

        # Epoch range filter
        if query.epoch_range:
            sql_parts.append("AND epoch BETWEEN ? AND ?")
            params.extend(query.epoch_range)

        # Step range filter
        if query.step_range:
            sql_parts.append("AND step BETWEEN ? AND ?")
            params.extend(query.step_range)

        # Value range filter
        if query.value_range:
            sql_parts.append("AND metric_value BETWEEN ? AND ?")
            params.extend(query.value_range)

        # Custom conditions
        if query.conditions:
            for condition in query.conditions:
                condition_sql, condition_params = self._build_condition_sql(condition)
                sql_parts.append(f"AND {condition_sql}")
                params.extend(condition_params)

        # Tags filter (JSON search)
        if query.tags:
            for tag in query.tags:
                sql_parts.append("AND JSON_EXTRACT(tags_json, '$') LIKE ?")
                params.append(f'%"{tag}"%')

        # Ordering
        if query.order_by:
            direction = "ASC" if query.ascending else "DESC"
            sql_parts.append(f"ORDER BY {query.order_by} {direction}")
        else:
            sql_parts.append("ORDER BY timestamp ASC")

        # Limit and offset
        if query.limit:
            sql_parts.append("LIMIT ?")
            params.append(query.limit)

            if query.offset:
                sql_parts.append("OFFSET ?")
                params.append(query.offset)

        return " ".join(sql_parts), params

    def _build_condition_sql(self, condition: QueryCondition) -> Tuple[str, List[Any]]:
        """Build SQL for a single condition."""
        column = condition.column
        operator = condition.operator

        if operator == QueryOperator.EQUALS:
            return f"{column} = ?", [condition.value]
        elif operator == QueryOperator.NOT_EQUALS:
            return f"{column} != ?", [condition.value]
        elif operator == QueryOperator.GREATER_THAN:
            return f"{column} > ?", [condition.value]
        elif operator == QueryOperator.LESS_THAN:
            return f"{column} < ?", [condition.value]
        elif operator == QueryOperator.GREATER_EQUAL:
            return f"{column} >= ?", [condition.value]
        elif operator == QueryOperator.LESS_EQUAL:
            return f"{column} <= ?", [condition.value]
        elif operator == QueryOperator.BETWEEN:
            if condition.values and len(condition.values) >= 2:
                return f"{column} BETWEEN ? AND ?", condition.values[:2]
            else:
                raise ValueError("BETWEEN operator requires two values")
        elif operator == QueryOperator.IN:
            if condition.values:
                placeholders = ",".join("?" * len(condition.values))
                return f"{column} IN ({placeholders})", condition.values
            else:
                raise ValueError("IN operator requires values list")
        elif operator == QueryOperator.NOT_IN:
            if condition.values:
                placeholders = ",".join("?" * len(condition.values))
                return f"{column} NOT IN ({placeholders})", condition.values
            else:
                raise ValueError("NOT IN operator requires values list")
        elif operator == QueryOperator.LIKE:
            return f"{column} LIKE ?", [condition.value]
        elif operator == QueryOperator.CONTAINS:
            return f"{column} LIKE ?", [f"%{condition.value}%"]
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def _cache_query(self, sql: str, result_count: int, execution_time: float) -> None:
        """Cache query for performance analysis."""
        query_hash = hashlib.md5(sql.encode()).hexdigest()

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Check if query already exists
                    cursor.execute("""
                        SELECT cache_id, access_count FROM query_cache
                        WHERE query_hash = ?
                    """, (query_hash,))

                    existing = cursor.fetchone()

                    if existing:
                        # Update existing entry
                        cursor.execute("""
                            UPDATE query_cache
                            SET access_count = access_count + 1,
                                last_accessed = CURRENT_TIMESTAMP
                            WHERE cache_id = ?
                        """, (existing[0],))
                    else:
                        # Insert new entry
                        cache_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO query_cache (
                                cache_id, query_hash, query_sql, result_count,
                                execution_time_ms, indexes_used_json
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            cache_id, query_hash, sql, result_count,
                            execution_time, json.dumps([])
                        ))

                    conn.commit()

                except Exception:
                    conn.rollback()
                finally:
                    conn.close()

        except Exception as e:
            self._logger.warning(f"Failed to cache query: {e}")

    def get_index_statistics(self, index_id: Optional[str] = None) -> List[IndexStatistics]:
        """
        Get statistics for indexes.

        Args:
            index_id: Specific index ID (optional)

        Returns:
            List of index statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if index_id:
                    cursor.execute("""
                        SELECT mi.index_id, mi.index_name, mi.table_name,
                               JSON_ARRAY_LENGTH(mi.columns_json) as column_count,
                               COALESCE(ist.row_count, 0) as row_count,
                               COALESCE(ist.unique_values, 0) as unique_values,
                               COALESCE(ist.selectivity, 0.0) as selectivity,
                               COALESCE(ist.size_bytes, 0) as size_bytes,
                               COALESCE(ist.last_updated, mi.created_at) as last_updated,
                               mi.usage_count
                        FROM metric_indexes mi
                        LEFT JOIN index_statistics ist ON mi.index_id = ist.index_id
                        WHERE mi.index_id = ?
                    """, (index_id,))
                else:
                    cursor.execute("""
                        SELECT mi.index_id, mi.index_name, mi.table_name,
                               JSON_ARRAY_LENGTH(mi.columns_json) as column_count,
                               COALESCE(ist.row_count, 0) as row_count,
                               COALESCE(ist.unique_values, 0) as unique_values,
                               COALESCE(ist.selectivity, 0.0) as selectivity,
                               COALESCE(ist.size_bytes, 0) as size_bytes,
                               COALESCE(ist.last_updated, mi.created_at) as last_updated,
                               mi.usage_count
                        FROM metric_indexes mi
                        LEFT JOIN index_statistics ist ON mi.index_id = ist.index_id
                        ORDER BY mi.usage_count DESC
                    """)

                rows = cursor.fetchall()

                statistics = []
                for row in rows:
                    stat = IndexStatistics(
                        index_id=row[0],
                        index_name=row[1],
                        table_name=row[2],
                        column_count=row[3],
                        row_count=row[4],
                        unique_values=row[5],
                        selectivity=row[6],
                        size_bytes=row[7],
                        last_updated=datetime.fromisoformat(row[8]),
                        usage_count=row[9]
                    )
                    statistics.append(stat)

                return statistics

            except Exception as e:
                self._logger.error(f"Failed to get index statistics: {e}")
                raise
            finally:
                conn.close()

    def update_value_ranges(self, session_id: str, metric_name: str,
                           metric_type: str, values: List[float]) -> None:
        """
        Update value ranges for optimization.

        Args:
            session_id: Training session ID
            metric_name: Metric name
            metric_type: Metric type
            values: List of metric values
        """
        if not values:
            return

        min_value = min(values)
        max_value = max(values)
        avg_value = sum(values) / len(values)
        value_count = len(values)
        distinct_values = len(set(values))

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO metric_value_ranges (
                        range_id, session_id, metric_name, metric_type,
                        min_value, max_value, avg_value, value_count,
                        distinct_values, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), session_id, metric_name, metric_type,
                    min_value, max_value, avg_value, value_count,
                    distinct_values, datetime.now().isoformat()
                ))

                conn.commit()
                self._logger.debug(f"Updated value ranges for {metric_name}")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update value ranges: {e}")
                raise
            finally:
                conn.close()

    def suggest_indexes(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Suggest indexes based on query patterns.

        Args:
            session_id: Training session ID

        Returns:
            List of index suggestions
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Analyze query patterns
                cursor.execute("""
                    SELECT pattern_description, columns_used_json, frequency,
                           avg_execution_time_ms
                    FROM search_patterns
                    WHERE frequency > 5 AND avg_execution_time_ms > 100
                    ORDER BY frequency DESC, avg_execution_time_ms DESC
                    LIMIT 10
                """)

                patterns = cursor.fetchall()

                suggestions = []
                for pattern in patterns:
                    columns_used = json.loads(pattern[1])

                    # Generate index suggestion
                    suggestion = {
                        'suggested_name': f"idx_metrics_{'_'.join(columns_used[:3])}",
                        'table_name': 'training_metrics',
                        'columns': columns_used,
                        'reason': pattern[0],
                        'frequency': pattern[2],
                        'avg_execution_time_ms': pattern[3],
                        'estimated_benefit': self._estimate_index_benefit(
                            columns_used, pattern[2], pattern[3]
                        )
                    }
                    suggestions.append(suggestion)

                return suggestions

            except Exception as e:
                self._logger.error(f"Failed to suggest indexes: {e}")
                raise
            finally:
                conn.close()

    def _estimate_index_benefit(self, columns: List[str], frequency: int,
                               execution_time: float) -> float:
        """Estimate the benefit of creating an index."""
        # Simple heuristic: benefit = frequency * time_saved_factor
        time_saved_factor = min(0.8, execution_time / 1000.0)  # Max 80% improvement
        return frequency * time_saved_factor

    def drop_index(self, index_id: str) -> bool:
        """
        Drop an existing index.

        Args:
            index_id: Index ID to drop

        Returns:
            True if successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get index name
                cursor.execute("""
                    SELECT index_name FROM metric_indexes WHERE index_id = ?
                """, (index_id,))

                result = cursor.fetchone()
                if not result:
                    return False

                index_name = result[0]

                # Drop the actual index
                cursor.execute(f"DROP INDEX IF EXISTS {index_name}")

                # Remove from registry
                cursor.execute("""
                    DELETE FROM metric_indexes WHERE index_id = ?
                """, (index_id,))

                # Remove statistics
                cursor.execute("""
                    DELETE FROM index_statistics WHERE index_id = ?
                """, (index_id,))

                conn.commit()
                self._logger.info(f"Dropped index {index_name}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to drop index: {e}")
                raise
            finally:
                conn.close()

    def cleanup_unused_indexes(self, min_usage_threshold: int = 10) -> int:
        """
        Clean up indexes that are rarely used.

        Args:
            min_usage_threshold: Minimum usage count to keep index

        Returns:
            Number of indexes dropped
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Find unused indexes
                cursor.execute("""
                    SELECT index_id, index_name FROM metric_indexes
                    WHERE usage_count < ?
                """, (min_usage_threshold,))

                unused_indexes = cursor.fetchall()
                dropped_count = 0

                for index_id, index_name in unused_indexes:
                    try:
                        # Drop the index
                        cursor.execute(f"DROP INDEX IF EXISTS {index_name}")

                        # Remove from registry
                        cursor.execute("""
                            DELETE FROM metric_indexes WHERE index_id = ?
                        """, (index_id,))

                        dropped_count += 1

                    except Exception as e:
                        self._logger.warning(f"Failed to drop unused index {index_name}: {e}")

                conn.commit()
                self._logger.info(f"Cleaned up {dropped_count} unused indexes")
                return dropped_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup unused indexes: {e}")
                raise
            finally:
                conn.close()
