"""
Module: index_manager_db
Description: Manages database indexes with automatic optimization and statistics updates
Phase: 4
Location: /src/modules/database/optimization_db/index_manager_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Set

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class IndexType(Enum):
    """Types of database indexes."""
    BTREE = "btree"
    UNIQUE = "unique"
    PARTIAL = "partial"
    COVERING = "covering"
    COMPOSITE = "composite"
    EXPRESSION = "expression"


class IndexStatus(Enum):
    """Status of database indexes."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    REBUILDING = "rebuilding"
    ANALYZING = "analyzing"
    DROPPED = "dropped"
    ERROR = "error"


class OptimizationStrategy(Enum):
    """Index optimization strategies."""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    THRESHOLD_BASED = "threshold_based"
    PERFORMANCE_DRIVEN = "performance_driven"


@dataclass
class IndexInfo:
    """Information about a database index."""
    index_id: str
    index_name: str
    table_name: str
    columns: List[str]
    index_type: IndexType
    status: IndexStatus
    created_at: datetime
    last_analyzed: Optional[datetime]
    last_rebuilt: Optional[datetime]
    size_bytes: int
    row_count: int
    fragmentation_percent: float
    usage_count: int
    last_used: Optional[datetime]
    is_unique: bool
    is_partial: bool
    condition_sql: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class IndexStatistics:
    """Statistics for database indexes."""
    stat_id: str
    index_id: str
    collected_at: datetime
    query_count: int
    scan_count: int
    seek_count: int
    update_count: int
    avg_query_time_ms: float
    max_query_time_ms: float
    min_query_time_ms: float
    total_io_operations: int
    cache_hit_ratio: float
    fragmentation_level: float
    size_growth_rate: float
    effectiveness_score: float


@dataclass
class OptimizationTask:
    """Index optimization task."""
    task_id: str
    index_id: str
    task_type: str
    strategy: OptimizationStrategy
    priority: int
    scheduled_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    progress_percent: float
    estimated_duration_seconds: Optional[int]
    actual_duration_seconds: Optional[int]
    result_summary: Optional[str]
    error_details: Optional[str]
    metadata: Dict[str, Any]


class IndexManagerDB:
    """
    Database index manager with automatic optimization and statistics updates.
    
    Manages database indexes with automatic optimization, statistics collection,
    and performance monitoring. Provides comprehensive index lifecycle management
    including creation, analysis, rebuilding, and removal based on usage patterns.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the index manager database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to optimization data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "optimization"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "index_manager.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._fragmentation_threshold = 30.0  # Rebuild when fragmentation > 30%
        self._usage_threshold = 100  # Consider dropping if usage < 100 in 30 days
        self._analysis_interval_hours = 24  # Analyze indexes every 24 hours
        self._max_concurrent_optimizations = 2
        
        # Runtime state
        self._active_optimizations: Set[str] = set()
        self._optimization_queue: List[OptimizationTask] = []
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                
                # Enable WAL mode and optimize settings
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Create indexes table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS indexes (
                        index_id TEXT PRIMARY KEY,
                        index_name TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        columns_json TEXT NOT NULL,
                        index_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        last_analyzed TIMESTAMP,
                        last_rebuilt TIMESTAMP,
                        size_bytes INTEGER DEFAULT 0,
                        row_count INTEGER DEFAULT 0,
                        fragmentation_percent REAL DEFAULT 0.0,
                        usage_count INTEGER DEFAULT 0,
                        last_used TIMESTAMP,
                        is_unique BOOLEAN DEFAULT FALSE,
                        is_partial BOOLEAN DEFAULT FALSE,
                        condition_sql TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create index statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS index_statistics (
                        stat_id TEXT PRIMARY KEY,
                        index_id TEXT NOT NULL,
                        collected_at TIMESTAMP NOT NULL,
                        query_count INTEGER DEFAULT 0,
                        scan_count INTEGER DEFAULT 0,
                        seek_count INTEGER DEFAULT 0,
                        update_count INTEGER DEFAULT 0,
                        avg_query_time_ms REAL DEFAULT 0.0,
                        max_query_time_ms REAL DEFAULT 0.0,
                        min_query_time_ms REAL DEFAULT 0.0,
                        total_io_operations INTEGER DEFAULT 0,
                        cache_hit_ratio REAL DEFAULT 0.0,
                        fragmentation_level REAL DEFAULT 0.0,
                        size_growth_rate REAL DEFAULT 0.0,
                        effectiveness_score REAL DEFAULT 0.0,
                        FOREIGN KEY (index_id) REFERENCES indexes (index_id)
                    )
                """)
                
                # Create optimization tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_tasks (
                        task_id TEXT PRIMARY KEY,
                        index_id TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        priority INTEGER DEFAULT 5,
                        scheduled_at TIMESTAMP NOT NULL,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        status TEXT NOT NULL,
                        progress_percent REAL DEFAULT 0.0,
                        estimated_duration_seconds INTEGER,
                        actual_duration_seconds INTEGER,
                        result_summary TEXT,
                        error_details TEXT,
                        metadata_json TEXT,
                        FOREIGN KEY (index_id) REFERENCES indexes (index_id)
                    )
                """)
                
                # Create performance indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexes_table_status ON indexes (table_name, status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexes_fragmentation ON indexes (fragmentation_percent)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexes_usage ON indexes (usage_count, last_used)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_index_time ON index_statistics (index_id, collected_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON optimization_tasks (status, priority)")
                
                conn.commit()
                conn.close()
                
                self._logger.info("Index manager database initialized successfully")
                
        except Exception as e:
            self._logger.error(f"Failed to initialize index manager database: {e}")
            raise

    def register_index(self, index_name: str, table_name: str, columns: List[str],
                      index_type: IndexType = IndexType.BTREE, is_unique: bool = False,
                      is_partial: bool = False, condition_sql: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Register a new index for management.

        Args:
            index_name: Name of the index
            table_name: Target table name
            columns: List of columns in the index
            index_type: Type of index
            is_unique: Whether index enforces uniqueness
            is_partial: Whether index is partial (has WHERE condition)
            condition_sql: SQL condition for partial indexes
            metadata: Additional metadata

        Returns:
            Index ID
        """
        index_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if index already exists
                cursor.execute("SELECT index_id FROM indexes WHERE index_name = ?", (index_name,))
                if cursor.fetchone():
                    raise ValueError(f"Index {index_name} already registered")

                # Register the index
                cursor.execute("""
                    INSERT INTO indexes (
                        index_id, index_name, table_name, columns_json, index_type,
                        status, created_at, is_unique, is_partial, condition_sql, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    index_id, index_name, table_name, json.dumps(columns),
                    index_type.value, IndexStatus.ACTIVE.value, datetime.now(timezone.utc),
                    is_unique, is_partial, condition_sql,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Registered index {index_name} with ID {index_id}")
                return index_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to register index {index_name}: {e}")
                raise
            finally:
                conn.close()

    def update_index_statistics(self, index_id: str, statistics: IndexStatistics) -> str:
        """
        Update statistics for an index.

        Args:
            index_id: Index identifier
            statistics: Index statistics data

        Returns:
            Statistics ID
        """
        stat_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Insert statistics
                cursor.execute("""
                    INSERT INTO index_statistics (
                        stat_id, index_id, collected_at, query_count, scan_count,
                        seek_count, update_count, avg_query_time_ms, max_query_time_ms,
                        min_query_time_ms, total_io_operations, cache_hit_ratio,
                        fragmentation_level, size_growth_rate, effectiveness_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stat_id, index_id, statistics.collected_at, statistics.query_count,
                    statistics.scan_count, statistics.seek_count, statistics.update_count,
                    statistics.avg_query_time_ms, statistics.max_query_time_ms,
                    statistics.min_query_time_ms, statistics.total_io_operations,
                    statistics.cache_hit_ratio, statistics.fragmentation_level,
                    statistics.size_growth_rate, statistics.effectiveness_score
                ))

                # Update index with latest statistics
                cursor.execute("""
                    UPDATE indexes SET
                        fragmentation_percent = ?,
                        usage_count = usage_count + ?,
                        last_used = ?,
                        last_analyzed = ?
                    WHERE index_id = ?
                """, (
                    statistics.fragmentation_level,
                    statistics.query_count,
                    datetime.now(timezone.utc),
                    statistics.collected_at,
                    index_id
                ))

                conn.commit()
                self._logger.debug(f"Updated statistics for index {index_id}")
                return stat_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update statistics for index {index_id}: {e}")
                raise
            finally:
                conn.close()

    def analyze_index_performance(self, index_id: str) -> Dict[str, Any]:
        """
        Analyze index performance and recommend optimizations.

        Args:
            index_id: Index identifier

        Returns:
            Performance analysis results
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get index information
                cursor.execute("""
                    SELECT index_name, table_name, fragmentation_percent, usage_count,
                           last_used, size_bytes, row_count
                    FROM indexes WHERE index_id = ?
                """, (index_id,))

                index_row = cursor.fetchone()
                if not index_row:
                    raise ValueError(f"Index {index_id} not found")

                index_name, table_name, fragmentation, usage_count, last_used, size_bytes, row_count = index_row

                # Get recent statistics
                cursor.execute("""
                    SELECT avg_query_time_ms, cache_hit_ratio, effectiveness_score,
                           scan_count, seek_count
                    FROM index_statistics
                    WHERE index_id = ? AND collected_at >= ?
                    ORDER BY collected_at DESC LIMIT 10
                """, (index_id, datetime.now(timezone.utc) - timedelta(days=7)))

                stats_rows = cursor.fetchall()

                # Calculate performance metrics
                analysis = {
                    'index_id': index_id,
                    'index_name': index_name,
                    'table_name': table_name,
                    'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
                    'fragmentation_percent': fragmentation,
                    'usage_count': usage_count,
                    'size_mb': round(size_bytes / (1024 * 1024), 2) if size_bytes else 0,
                    'recommendations': []
                }

                # Analyze fragmentation
                if fragmentation > self._fragmentation_threshold:
                    analysis['recommendations'].append({
                        'type': 'rebuild',
                        'priority': 'high',
                        'reason': f'High fragmentation: {fragmentation:.1f}%',
                        'estimated_benefit': 'Improved query performance and reduced I/O'
                    })

                # Analyze usage patterns
                if usage_count < self._usage_threshold:
                    last_used_date = datetime.fromisoformat(last_used) if last_used else None
                    days_since_used = (datetime.now(timezone.utc) - last_used_date).days if last_used_date else 999

                    if days_since_used > 30:
                        analysis['recommendations'].append({
                            'type': 'consider_dropping',
                            'priority': 'medium',
                            'reason': f'Low usage: {usage_count} queries, last used {days_since_used} days ago',
                            'estimated_benefit': 'Reduced storage and maintenance overhead'
                        })

                # Analyze performance trends
                if stats_rows:
                    avg_query_times = [row[0] for row in stats_rows if row[0] is not None]
                    cache_hit_ratios = [row[1] for row in stats_rows if row[1] is not None]
                    effectiveness_scores = [row[2] for row in stats_rows if row[2] is not None]

                    if avg_query_times:
                        analysis['avg_query_time_ms'] = sum(avg_query_times) / len(avg_query_times)

                        if analysis['avg_query_time_ms'] > 100:  # Slow queries
                            analysis['recommendations'].append({
                                'type': 'optimize',
                                'priority': 'medium',
                                'reason': f'Slow average query time: {analysis["avg_query_time_ms"]:.1f}ms',
                                'estimated_benefit': 'Faster query execution'
                            })

                    if cache_hit_ratios:
                        analysis['avg_cache_hit_ratio'] = sum(cache_hit_ratios) / len(cache_hit_ratios)

                        if analysis['avg_cache_hit_ratio'] < 0.8:  # Low cache hit ratio
                            analysis['recommendations'].append({
                                'type': 'analyze_usage',
                                'priority': 'low',
                                'reason': f'Low cache hit ratio: {analysis["avg_cache_hit_ratio"]:.1%}',
                                'estimated_benefit': 'Better memory utilization'
                            })

                self._logger.info(f"Analyzed performance for index {index_name}")
                return analysis

            except Exception as e:
                self._logger.error(f"Failed to analyze index performance for {index_id}: {e}")
                raise
            finally:
                conn.close()

    def schedule_optimization(self, index_id: str, task_type: str,
                            strategy: OptimizationStrategy = OptimizationStrategy.AUTOMATIC,
                            priority: int = 5, scheduled_at: Optional[datetime] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Schedule an optimization task for an index.

        Args:
            index_id: Index identifier
            task_type: Type of optimization task (rebuild, analyze, drop)
            strategy: Optimization strategy
            priority: Task priority (1-10, higher = more urgent)
            scheduled_at: When to execute the task
            metadata: Additional task metadata

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        scheduled_at = scheduled_at or datetime.now(timezone.utc)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Verify index exists
                cursor.execute("SELECT index_name FROM indexes WHERE index_id = ?", (index_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Index {index_id} not found")

                # Create optimization task
                task = OptimizationTask(
                    task_id=task_id,
                    index_id=index_id,
                    task_type=task_type,
                    strategy=strategy,
                    priority=priority,
                    scheduled_at=scheduled_at,
                    started_at=None,
                    completed_at=None,
                    status='scheduled',
                    progress_percent=0.0,
                    estimated_duration_seconds=None,
                    actual_duration_seconds=None,
                    result_summary=None,
                    error_details=None,
                    metadata=metadata or {}
                )

                # Insert task
                cursor.execute("""
                    INSERT INTO optimization_tasks (
                        task_id, index_id, task_type, strategy, priority,
                        scheduled_at, status, progress_percent, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, index_id, task_type, strategy.value, priority,
                    scheduled_at, 'scheduled', 0.0,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Scheduled {task_type} optimization for index {index_id}")
                return task_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to schedule optimization for index {index_id}: {e}")
                raise
            finally:
                conn.close()

    def execute_optimization_task(self, task_id: str) -> bool:
        """
        Execute a scheduled optimization task.

        Args:
            task_id: Task identifier

        Returns:
            True if task executed successfully
        """
        if task_id in self._active_optimizations:
            self._logger.warning(f"Optimization task {task_id} already running")
            return False

        if len(self._active_optimizations) >= self._max_concurrent_optimizations:
            self._logger.warning("Maximum concurrent optimizations reached")
            return False

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get task details
                cursor.execute("""
                    SELECT index_id, task_type, strategy, metadata_json
                    FROM optimization_tasks WHERE task_id = ? AND status = 'scheduled'
                """, (task_id,))

                task_row = cursor.fetchone()
                if not task_row:
                    self._logger.warning(f"Task {task_id} not found or not scheduled")
                    return False

                index_id, task_type, strategy, metadata_json = task_row
                metadata = json.loads(metadata_json) if metadata_json else {}

                # Mark task as running
                start_time = datetime.now(timezone.utc)
                cursor.execute("""
                    UPDATE optimization_tasks SET
                        status = 'running',
                        started_at = ?,
                        progress_percent = 10.0
                    WHERE task_id = ?
                """, (start_time, task_id))

                conn.commit()
                self._active_optimizations.add(task_id)

                # Execute the optimization
                success = False
                error_details = None
                result_summary = None

                try:
                    if task_type == 'rebuild':
                        success, result_summary = self._rebuild_index(index_id, task_id)
                    elif task_type == 'analyze':
                        success, result_summary = self._analyze_index(index_id, task_id)
                    elif task_type == 'drop':
                        success, result_summary = self._drop_index(index_id, task_id)
                    else:
                        raise ValueError(f"Unknown task type: {task_type}")

                except Exception as e:
                    success = False
                    error_details = str(e)
                    result_summary = f"Task failed: {e}"
                    self._logger.error(f"Optimization task {task_id} failed: {e}")

                # Update task completion
                end_time = datetime.now(timezone.utc)
                duration = int((end_time - start_time).total_seconds())

                cursor.execute("""
                    UPDATE optimization_tasks SET
                        status = ?,
                        completed_at = ?,
                        progress_percent = 100.0,
                        actual_duration_seconds = ?,
                        result_summary = ?,
                        error_details = ?
                    WHERE task_id = ?
                """, (
                    'completed' if success else 'failed',
                    end_time, duration, result_summary, error_details, task_id
                ))

                conn.commit()
                self._active_optimizations.discard(task_id)

                self._logger.info(f"Optimization task {task_id} {'completed' if success else 'failed'}")
                return success

            except Exception as e:
                self._logger.error(f"Failed to execute optimization task {task_id}: {e}")
                self._active_optimizations.discard(task_id)
                return False
            finally:
                conn.close()

    def _rebuild_index(self, index_id: str, task_id: str) -> Tuple[bool, str]:
        """
        Rebuild an index to reduce fragmentation.

        Args:
            index_id: Index identifier
            task_id: Task identifier for progress tracking

        Returns:
            Tuple of (success, result_summary)
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get index information
                cursor.execute("""
                    SELECT index_name, table_name, columns_json, index_type,
                           is_unique, is_partial, condition_sql
                    FROM indexes WHERE index_id = ?
                """, (index_id,))

                index_row = cursor.fetchone()
                if not index_row:
                    return False, f"Index {index_id} not found"

                index_name, table_name, columns_json, index_type, is_unique, is_partial, condition_sql = index_row
                columns = json.loads(columns_json)

                # Update progress
                cursor.execute("""
                    UPDATE optimization_tasks SET progress_percent = 30.0 WHERE task_id = ?
                """, (task_id,))
                conn.commit()

                # Drop existing index
                cursor.execute(f"DROP INDEX IF EXISTS {index_name}")

                # Update progress
                cursor.execute("""
                    UPDATE optimization_tasks SET progress_percent = 60.0 WHERE task_id = ?
                """, (task_id,))
                conn.commit()

                # Recreate index
                columns_str = ", ".join(columns)
                unique_clause = "UNIQUE " if is_unique else ""
                where_clause = f" WHERE {condition_sql}" if is_partial and condition_sql else ""

                create_sql = f"CREATE {unique_clause}INDEX {index_name} ON {table_name} ({columns_str}){where_clause}"
                cursor.execute(create_sql)

                # Update progress
                cursor.execute("""
                    UPDATE optimization_tasks SET progress_percent = 90.0 WHERE task_id = ?
                """, (task_id,))
                conn.commit()

                # Update index status
                cursor.execute("""
                    UPDATE indexes SET
                        last_rebuilt = ?,
                        fragmentation_percent = 0.0,
                        status = ?
                    WHERE index_id = ?
                """, (datetime.now(timezone.utc), IndexStatus.ACTIVE.value, index_id))

                conn.commit()
                conn.close()

                return True, f"Index {index_name} rebuilt successfully"

        except Exception as e:
            return False, f"Failed to rebuild index: {e}"

    def _analyze_index(self, index_id: str, task_id: str) -> Tuple[bool, str]:
        """
        Analyze an index and update statistics.

        Args:
            index_id: Index identifier
            task_id: Task identifier for progress tracking

        Returns:
            Tuple of (success, result_summary)
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get index information
                cursor.execute("""
                    SELECT index_name, table_name FROM indexes WHERE index_id = ?
                """, (index_id,))

                index_row = cursor.fetchone()
                if not index_row:
                    return False, f"Index {index_id} not found"

                index_name, table_name = index_row

                # Update progress
                cursor.execute("""
                    UPDATE optimization_tasks SET progress_percent = 25.0 WHERE task_id = ?
                """, (task_id,))
                conn.commit()

                # Run ANALYZE on the table
                cursor.execute(f"ANALYZE {table_name}")

                # Update progress
                cursor.execute("""
                    UPDATE optimization_tasks SET progress_percent = 75.0 WHERE task_id = ?
                """, (task_id,))
                conn.commit()

                # Update index analysis timestamp
                cursor.execute("""
                    UPDATE indexes SET last_analyzed = ? WHERE index_id = ?
                """, (datetime.now(timezone.utc), index_id))

                conn.commit()
                conn.close()

                return True, f"Index {index_name} analyzed successfully"

        except Exception as e:
            return False, f"Failed to analyze index: {e}"

    def _drop_index(self, index_id: str, task_id: str) -> Tuple[bool, str]:
        """
        Drop an unused index.

        Args:
            index_id: Index identifier
            task_id: Task identifier for progress tracking

        Returns:
            Tuple of (success, result_summary)
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get index information
                cursor.execute("""
                    SELECT index_name FROM indexes WHERE index_id = ?
                """, (index_id,))

                index_row = cursor.fetchone()
                if not index_row:
                    return False, f"Index {index_id} not found"

                index_name = index_row[0]

                # Update progress
                cursor.execute("""
                    UPDATE optimization_tasks SET progress_percent = 50.0 WHERE task_id = ?
                """, (task_id,))
                conn.commit()

                # Drop the index
                cursor.execute(f"DROP INDEX IF EXISTS {index_name}")

                # Update index status
                cursor.execute("""
                    UPDATE indexes SET status = ? WHERE index_id = ?
                """, (IndexStatus.DROPPED.value, index_id))

                conn.commit()
                conn.close()

                return True, f"Index {index_name} dropped successfully"

        except Exception as e:
            return False, f"Failed to drop index: {e}"

    def get_index_info(self, index_id: str) -> Optional[IndexInfo]:
        """
        Get information about an index.

        Args:
            index_id: Index identifier

        Returns:
            IndexInfo object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT index_id, index_name, table_name, columns_json, index_type,
                           status, created_at, last_analyzed, last_rebuilt, size_bytes,
                           row_count, fragmentation_percent, usage_count, last_used,
                           is_unique, is_partial, condition_sql, metadata_json
                    FROM indexes WHERE index_id = ?
                """, (index_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return IndexInfo(
                    index_id=row[0],
                    index_name=row[1],
                    table_name=row[2],
                    columns=json.loads(row[3]),
                    index_type=IndexType(row[4]),
                    status=IndexStatus(row[5]),
                    created_at=datetime.fromisoformat(row[6]),
                    last_analyzed=datetime.fromisoformat(row[7]) if row[7] else None,
                    last_rebuilt=datetime.fromisoformat(row[8]) if row[8] else None,
                    size_bytes=row[9] or 0,
                    row_count=row[10] or 0,
                    fragmentation_percent=row[11] or 0.0,
                    usage_count=row[12] or 0,
                    last_used=datetime.fromisoformat(row[13]) if row[13] else None,
                    is_unique=bool(row[14]),
                    is_partial=bool(row[15]),
                    condition_sql=row[16],
                    metadata=json.loads(row[17]) if row[17] else {}
                )

            except Exception as e:
                self._logger.error(f"Failed to get index info for {index_id}: {e}")
                return None
            finally:
                conn.close()

    def list_indexes(self, table_name: Optional[str] = None,
                    status: Optional[IndexStatus] = None) -> List[IndexInfo]:
        """
        List indexes with optional filtering.

        Args:
            table_name: Filter by table name
            status: Filter by index status

        Returns:
            List of IndexInfo objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT index_id, index_name, table_name, columns_json, index_type,
                           status, created_at, last_analyzed, last_rebuilt, size_bytes,
                           row_count, fragmentation_percent, usage_count, last_used,
                           is_unique, is_partial, condition_sql, metadata_json
                    FROM indexes WHERE 1=1
                """
                params = []

                if table_name:
                    query += " AND table_name = ?"
                    params.append(table_name)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                query += " ORDER BY index_name"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                indexes = []
                for row in rows:
                    indexes.append(IndexInfo(
                        index_id=row[0],
                        index_name=row[1],
                        table_name=row[2],
                        columns=json.loads(row[3]),
                        index_type=IndexType(row[4]),
                        status=IndexStatus(row[5]),
                        created_at=datetime.fromisoformat(row[6]),
                        last_analyzed=datetime.fromisoformat(row[7]) if row[7] else None,
                        last_rebuilt=datetime.fromisoformat(row[8]) if row[8] else None,
                        size_bytes=row[9] or 0,
                        row_count=row[10] or 0,
                        fragmentation_percent=row[11] or 0.0,
                        usage_count=row[12] or 0,
                        last_used=datetime.fromisoformat(row[13]) if row[13] else None,
                        is_unique=bool(row[14]),
                        is_partial=bool(row[15]),
                        condition_sql=row[16],
                        metadata=json.loads(row[17]) if row[17] else {}
                    ))

                return indexes

            except Exception as e:
                self._logger.error(f"Failed to list indexes: {e}")
                return []
            finally:
                conn.close()

    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get optimization recommendations for all indexes.

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        try:
            # Get all active indexes
            indexes = self.list_indexes(status=IndexStatus.ACTIVE)

            for index in indexes:
                # Check fragmentation
                if index.fragmentation_percent > self._fragmentation_threshold:
                    recommendations.append({
                        'index_id': index.index_id,
                        'index_name': index.index_name,
                        'table_name': index.table_name,
                        'recommendation_type': 'rebuild',
                        'priority': 'high' if index.fragmentation_percent > 50 else 'medium',
                        'reason': f'High fragmentation: {index.fragmentation_percent:.1f}%',
                        'estimated_benefit': 'Improved query performance',
                        'fragmentation_percent': index.fragmentation_percent
                    })

                # Check usage patterns
                if index.usage_count < self._usage_threshold:
                    days_since_used = 999
                    if index.last_used:
                        days_since_used = (datetime.now(timezone.utc) - index.last_used).days

                    if days_since_used > 30:
                        recommendations.append({
                            'index_id': index.index_id,
                            'index_name': index.index_name,
                            'table_name': index.table_name,
                            'recommendation_type': 'consider_dropping',
                            'priority': 'low',
                            'reason': f'Low usage: {index.usage_count} queries, {days_since_used} days since last use',
                            'estimated_benefit': 'Reduced storage overhead',
                            'usage_count': index.usage_count,
                            'days_since_used': days_since_used
                        })

                # Check if analysis is needed
                if not index.last_analyzed or (datetime.now(timezone.utc) - index.last_analyzed).total_seconds() > (self._analysis_interval_hours * 3600):
                    recommendations.append({
                        'index_id': index.index_id,
                        'index_name': index.index_name,
                        'table_name': index.table_name,
                        'recommendation_type': 'analyze',
                        'priority': 'low',
                        'reason': 'Statistics need updating',
                        'estimated_benefit': 'Better query optimization',
                        'last_analyzed': index.last_analyzed.isoformat() if index.last_analyzed else None
                    })

            # Sort by priority
            priority_order = {'high': 1, 'medium': 2, 'low': 3}
            recommendations.sort(key=lambda x: priority_order.get(x['priority'], 4))

            return recommendations

        except Exception as e:
            self._logger.error(f"Failed to get optimization recommendations: {e}")
            return []

    def cleanup_old_statistics(self, retention_days: int = 90) -> int:
        """
        Clean up old statistics records.

        Args:
            retention_days: Number of days to retain statistics

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old statistics
                cursor.execute("""
                    DELETE FROM index_statistics WHERE collected_at < ?
                """, (cutoff_date,))

                deleted_count = cursor.rowcount

                # Delete old completed tasks
                cursor.execute("""
                    DELETE FROM optimization_tasks
                    WHERE status IN ('completed', 'failed') AND completed_at < ?
                """, (cutoff_date,))

                deleted_count += cursor.rowcount

                conn.commit()
                self._logger.info(f"Cleaned up {deleted_count} old records")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old statistics: {e}")
                return 0
            finally:
                conn.close()
