"""
Module: memory_metrics_db
Description: Persists memory allocation history and performance metrics for optimization analysis
Phase: 2
Location: /src/modules/database/resource_allocation_db/memory_metrics_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MemoryTier(Enum):
    """Memory tier types for IDRAlloc."""
    GPU_VRAM = "gpu_vram"
    SYSTEM_RAM = "system_ram"
    NVME_SWAP = "nvme_swap"


class AllocationStrategy(Enum):
    """Memory allocation strategies."""
    FREQUENCY = "frequency"
    SIZE = "size"
    MANUAL = "manual"
    HYBRID = "hybrid"


class MemoryMetricsDB:
    """
    Memory metrics database manager.
    
    Persists memory allocation history and performance metrics for optimization analysis.
    Tracks memory usage patterns, allocation efficiency, and performance characteristics
    across different memory tiers in the IDRAlloc system.
    """
    
    def __init__(self, db_path: Optional[str] = None, buffer_size: int = 10000):
        """
        Initialize the memory metrics database.
        
        Args:
            db_path: Path to the database file
            buffer_size: Size of in-memory metrics buffer
        """
        if db_path is None:
            # Default to resource allocation data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "resource_allocation"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "memory_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Buffer settings
        self._buffer_size = buffer_size
        self._metrics_buffer = []
        self._buffer_lock = threading.Lock()
        
        # Retention settings
        self._detailed_retention_hours = 72  # Keep detailed metrics for 72 hours
        self._hourly_retention_days = 30     # Keep hourly aggregates for 30 days
        self._daily_retention_months = 12    # Keep daily aggregates for 12 months
        
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
                
                # Create memory allocation history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_allocation_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        allocation_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        layer_group TEXT NOT NULL,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')) NOT NULL,
                        size_mb INTEGER NOT NULL,
                        access_frequency INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP,
                        allocation_strategy TEXT CHECK(allocation_strategy IN ('frequency','size','manual','hybrid')) NOT NULL,
                        allocation_duration_ms INTEGER,
                        deallocation_timestamp TIMESTAMP,
                        peak_usage_mb INTEGER,
                        average_usage_mb INTEGER,
                        fragmentation_score REAL,
                        compression_ratio REAL,
                        swap_in_count INTEGER DEFAULT 0,
                        swap_out_count INTEGER DEFAULT 0,
                        prefetch_hit_rate REAL,
                        cache_hit_rate REAL,
                        metadata_json TEXT
                    )
                """)
                
                # Create memory performance metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metric_type TEXT NOT NULL,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')),
                        metric_value REAL NOT NULL,
                        measurement_unit TEXT,
                        aggregation_period TEXT,
                        context_data TEXT
                    )
                """)
                
                # Create memory tier utilization table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_tier_utilization (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        utilization_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')) NOT NULL,
                        total_capacity_mb INTEGER NOT NULL,
                        allocated_mb INTEGER NOT NULL,
                        used_mb INTEGER NOT NULL,
                        free_mb INTEGER NOT NULL,
                        fragmented_mb INTEGER DEFAULT 0,
                        utilization_percentage REAL NOT NULL,
                        fragmentation_percentage REAL DEFAULT 0,
                        allocation_efficiency REAL,
                        throughput_mbps REAL,
                        latency_ms REAL,
                        bandwidth_utilization REAL
                    )
                """)
                
                # Create allocation optimization events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS allocation_optimization_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        event_type TEXT NOT NULL,
                        trigger_condition TEXT,
                        source_tier TEXT CHECK(source_tier IN ('gpu_vram','system_ram','nvme_swap')),
                        target_tier TEXT CHECK(target_tier IN ('gpu_vram','system_ram','nvme_swap')),
                        affected_layers TEXT,
                        moved_size_mb INTEGER,
                        optimization_duration_ms INTEGER,
                        performance_impact_score REAL,
                        success_status BOOLEAN DEFAULT 1,
                        error_message TEXT,
                        optimization_metadata TEXT
                    )
                """)
                
                # Create hourly aggregates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_metrics_hourly (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        hour_timestamp TIMESTAMP NOT NULL,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')) NOT NULL,
                        avg_utilization_percentage REAL,
                        max_utilization_percentage REAL,
                        avg_allocation_size_mb REAL,
                        total_allocations INTEGER,
                        total_deallocations INTEGER,
                        total_swaps INTEGER,
                        avg_allocation_duration_ms REAL,
                        avg_fragmentation_score REAL,
                        avg_throughput_mbps REAL,
                        avg_latency_ms REAL,
                        optimization_events_count INTEGER,
                        UNIQUE(session_id, hour_timestamp, memory_tier)
                    )
                """)
                
                # Create daily aggregates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_metrics_daily (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        date DATE NOT NULL,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')) NOT NULL,
                        avg_utilization_percentage REAL,
                        max_utilization_percentage REAL,
                        total_allocated_mb INTEGER,
                        total_allocations INTEGER,
                        total_swaps INTEGER,
                        avg_allocation_efficiency REAL,
                        avg_throughput_mbps REAL,
                        optimization_events_count INTEGER,
                        UNIQUE(session_id, date, memory_tier)
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_allocation_session ON memory_allocation_history(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_allocation_timestamp ON memory_allocation_history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_allocation_tier ON memory_allocation_history(memory_tier)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_allocation_layer ON memory_allocation_history(layer_group)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_performance_session ON memory_performance_metrics(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_performance_timestamp ON memory_performance_metrics(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_performance_type ON memory_performance_metrics(metric_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_tier_session ON memory_tier_utilization(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_tier_timestamp ON memory_tier_utilization(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimization_events_session ON allocation_optimization_events(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimization_events_timestamp ON allocation_optimization_events(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hourly_session_time ON memory_metrics_hourly(session_id, hour_timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_session_date ON memory_metrics_daily(session_id, date)")
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'memory_allocation_history', 'memory_performance_metrics', 
                    'memory_tier_utilization', 'allocation_optimization_events',
                    'memory_metrics_hourly', 'memory_metrics_daily'
                ]

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Memory metrics database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize memory metrics database: {e}")
                raise
            finally:
                conn.close()

    def record_allocation(self, session_id: str, layer_group: str, memory_tier: MemoryTier,
                         size_mb: int, allocation_strategy: AllocationStrategy,
                         allocation_duration_ms: Optional[int] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record memory allocation event.

        Args:
            session_id: Training session ID
            layer_group: Model layer group identifier
            memory_tier: Memory tier where allocation occurred
            size_mb: Allocation size in MB
            allocation_strategy: Strategy used for allocation
            allocation_duration_ms: Time taken for allocation
            metadata: Additional metadata

        Returns:
            Allocation ID
        """
        allocation_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memory_allocation_history (
                        allocation_id, session_id, layer_group, memory_tier,
                        size_mb, allocation_strategy, allocation_duration_ms, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    allocation_id, session_id, layer_group, memory_tier.value,
                    size_mb, allocation_strategy.value, allocation_duration_ms,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.debug(f"Recorded allocation {allocation_id} for session {session_id}")
                return allocation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record allocation: {e}")
                raise
            finally:
                conn.close()

    def update_allocation_usage(self, allocation_id: str, access_frequency: Optional[int] = None,
                               peak_usage_mb: Optional[int] = None,
                               average_usage_mb: Optional[int] = None,
                               fragmentation_score: Optional[float] = None,
                               compression_ratio: Optional[float] = None,
                               swap_in_count: Optional[int] = None,
                               swap_out_count: Optional[int] = None,
                               prefetch_hit_rate: Optional[float] = None,
                               cache_hit_rate: Optional[float] = None) -> bool:
        """
        Update allocation usage statistics.

        Args:
            allocation_id: Allocation ID
            access_frequency: Number of accesses
            peak_usage_mb: Peak usage in MB
            average_usage_mb: Average usage in MB
            fragmentation_score: Fragmentation score
            compression_ratio: Compression ratio
            swap_in_count: Number of swap-in operations
            swap_out_count: Number of swap-out operations
            prefetch_hit_rate: Prefetch hit rate
            cache_hit_rate: Cache hit rate

        Returns:
            True if updated successfully
        """
        update_fields = []
        values = []

        if access_frequency is not None:
            update_fields.append("access_frequency = ?")
            values.append(access_frequency)
            update_fields.append("last_accessed = CURRENT_TIMESTAMP")

        if peak_usage_mb is not None:
            update_fields.append("peak_usage_mb = ?")
            values.append(peak_usage_mb)

        if average_usage_mb is not None:
            update_fields.append("average_usage_mb = ?")
            values.append(average_usage_mb)

        if fragmentation_score is not None:
            update_fields.append("fragmentation_score = ?")
            values.append(fragmentation_score)

        if compression_ratio is not None:
            update_fields.append("compression_ratio = ?")
            values.append(compression_ratio)

        if swap_in_count is not None:
            update_fields.append("swap_in_count = ?")
            values.append(swap_in_count)

        if swap_out_count is not None:
            update_fields.append("swap_out_count = ?")
            values.append(swap_out_count)

        if prefetch_hit_rate is not None:
            update_fields.append("prefetch_hit_rate = ?")
            values.append(prefetch_hit_rate)

        if cache_hit_rate is not None:
            update_fields.append("cache_hit_rate = ?")
            values.append(cache_hit_rate)

        if not update_fields:
            return True

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                query = f"UPDATE memory_allocation_history SET {', '.join(update_fields)} WHERE allocation_id = ?"
                values.append(allocation_id)

                cursor.execute(query, values)

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.debug(f"Updated allocation usage for {allocation_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update allocation usage {allocation_id}: {e}")
                raise
            finally:
                conn.close()

    def record_deallocation(self, allocation_id: str) -> bool:
        """
        Record memory deallocation event.

        Args:
            allocation_id: Allocation ID

        Returns:
            True if recorded successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE memory_allocation_history
                    SET deallocation_timestamp = CURRENT_TIMESTAMP
                    WHERE allocation_id = ?
                """, (allocation_id,))

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.debug(f"Recorded deallocation for {allocation_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record deallocation {allocation_id}: {e}")
                raise
            finally:
                conn.close()

    def record_performance_metric(self, session_id: str, metric_type: str, metric_value: float,
                                 memory_tier: Optional[MemoryTier] = None,
                                 measurement_unit: Optional[str] = None,
                                 aggregation_period: Optional[str] = None,
                                 context_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Record performance metric.

        Args:
            session_id: Training session ID
            metric_type: Type of metric
            metric_value: Metric value
            memory_tier: Memory tier (if applicable)
            measurement_unit: Unit of measurement
            aggregation_period: Aggregation period
            context_data: Additional context data

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memory_performance_metrics (
                        metric_id, session_id, metric_type, memory_tier,
                        metric_value, measurement_unit, aggregation_period, context_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, session_id, metric_type,
                    memory_tier.value if memory_tier else None,
                    metric_value, measurement_unit, aggregation_period,
                    json.dumps(context_data) if context_data else None
                ))

                conn.commit()
                self._logger.debug(f"Recorded performance metric {metric_type} for session {session_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record performance metric: {e}")
                raise
            finally:
                conn.close()

    def record_tier_utilization(self, session_id: str, memory_tier: MemoryTier,
                               total_capacity_mb: int, allocated_mb: int, used_mb: int,
                               free_mb: int, fragmented_mb: int = 0,
                               allocation_efficiency: Optional[float] = None,
                               throughput_mbps: Optional[float] = None,
                               latency_ms: Optional[float] = None,
                               bandwidth_utilization: Optional[float] = None) -> str:
        """
        Record memory tier utilization snapshot.

        Args:
            session_id: Training session ID
            memory_tier: Memory tier
            total_capacity_mb: Total capacity in MB
            allocated_mb: Allocated memory in MB
            used_mb: Actually used memory in MB
            free_mb: Free memory in MB
            fragmented_mb: Fragmented memory in MB
            allocation_efficiency: Allocation efficiency score
            throughput_mbps: Throughput in MB/s
            latency_ms: Latency in milliseconds
            bandwidth_utilization: Bandwidth utilization percentage

        Returns:
            Utilization ID
        """
        utilization_id = str(uuid.uuid4())

        utilization_percentage = (used_mb / total_capacity_mb * 100) if total_capacity_mb > 0 else 0
        fragmentation_percentage = (fragmented_mb / total_capacity_mb * 100) if total_capacity_mb > 0 else 0

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memory_tier_utilization (
                        utilization_id, session_id, memory_tier, total_capacity_mb,
                        allocated_mb, used_mb, free_mb, fragmented_mb,
                        utilization_percentage, fragmentation_percentage,
                        allocation_efficiency, throughput_mbps, latency_ms, bandwidth_utilization
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    utilization_id, session_id, memory_tier.value, total_capacity_mb,
                    allocated_mb, used_mb, free_mb, fragmented_mb,
                    utilization_percentage, fragmentation_percentage,
                    allocation_efficiency, throughput_mbps, latency_ms, bandwidth_utilization
                ))

                conn.commit()
                self._logger.debug(f"Recorded tier utilization for {memory_tier.value} in session {session_id}")
                return utilization_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record tier utilization: {e}")
                raise
            finally:
                conn.close()

    def record_optimization_event(self, session_id: str, event_type: str,
                                 trigger_condition: Optional[str] = None,
                                 source_tier: Optional[MemoryTier] = None,
                                 target_tier: Optional[MemoryTier] = None,
                                 affected_layers: Optional[List[str]] = None,
                                 moved_size_mb: Optional[int] = None,
                                 optimization_duration_ms: Optional[int] = None,
                                 performance_impact_score: Optional[float] = None,
                                 success_status: bool = True,
                                 error_message: Optional[str] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record allocation optimization event.

        Args:
            session_id: Training session ID
            event_type: Type of optimization event
            trigger_condition: Condition that triggered optimization
            source_tier: Source memory tier
            target_tier: Target memory tier
            affected_layers: List of affected layer groups
            moved_size_mb: Amount of memory moved in MB
            optimization_duration_ms: Duration of optimization
            performance_impact_score: Performance impact score
            success_status: Whether optimization was successful
            error_message: Error message if failed
            metadata: Additional metadata

        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO allocation_optimization_events (
                        event_id, session_id, event_type, trigger_condition,
                        source_tier, target_tier, affected_layers, moved_size_mb,
                        optimization_duration_ms, performance_impact_score,
                        success_status, error_message, optimization_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, session_id, event_type, trigger_condition,
                    source_tier.value if source_tier else None,
                    target_tier.value if target_tier else None,
                    json.dumps(affected_layers) if affected_layers else None,
                    moved_size_mb, optimization_duration_ms, performance_impact_score,
                    success_status, error_message,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Recorded optimization event {event_type} for session {session_id}")
                return event_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record optimization event: {e}")
                raise
            finally:
                conn.close()

    def get_allocation_history(self, session_id: str, memory_tier: Optional[MemoryTier] = None,
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None,
                              limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get allocation history for session.

        Args:
            session_id: Training session ID
            memory_tier: Filter by memory tier
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of records

        Returns:
            List of allocation records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT allocation_id, session_id, timestamp, layer_group, memory_tier,
                           size_mb, access_frequency, last_accessed, allocation_strategy,
                           allocation_duration_ms, deallocation_timestamp, peak_usage_mb,
                           average_usage_mb, fragmentation_score, compression_ratio,
                           swap_in_count, swap_out_count, prefetch_hit_rate, cache_hit_rate,
                           metadata_json
                    FROM memory_allocation_history
                    WHERE session_id = ?
                """
                params = [session_id]

                if memory_tier:
                    query += " AND memory_tier = ?"
                    params.append(memory_tier.value)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [self._row_to_allocation_dict(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to get allocation history for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def get_performance_metrics(self, session_id: str, metric_type: Optional[str] = None,
                               memory_tier: Optional[MemoryTier] = None,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None,
                               limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get performance metrics for session.

        Args:
            session_id: Training session ID
            metric_type: Filter by metric type
            memory_tier: Filter by memory tier
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of records

        Returns:
            List of performance metric records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT metric_id, session_id, timestamp, metric_type, memory_tier,
                           metric_value, measurement_unit, aggregation_period, context_data
                    FROM memory_performance_metrics
                    WHERE session_id = ?
                """
                params = [session_id]

                if metric_type:
                    query += " AND metric_type = ?"
                    params.append(metric_type)

                if memory_tier:
                    query += " AND memory_tier = ?"
                    params.append(memory_tier.value)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [self._row_to_metric_dict(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to get performance metrics for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def get_tier_utilization_summary(self, session_id: str, memory_tier: Optional[MemoryTier] = None,
                                    start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get memory tier utilization summary.

        Args:
            session_id: Training session ID
            memory_tier: Filter by memory tier
            start_time: Start time filter
            end_time: End time filter

        Returns:
            Utilization summary statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT memory_tier,
                           AVG(utilization_percentage) as avg_utilization,
                           MAX(utilization_percentage) as max_utilization,
                           AVG(fragmentation_percentage) as avg_fragmentation,
                           AVG(allocation_efficiency) as avg_efficiency,
                           AVG(throughput_mbps) as avg_throughput,
                           AVG(latency_ms) as avg_latency,
                           COUNT(*) as sample_count
                    FROM memory_tier_utilization
                    WHERE session_id = ?
                """
                params = [session_id]

                if memory_tier:
                    query += " AND memory_tier = ?"
                    params.append(memory_tier.value)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " GROUP BY memory_tier"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                summary = {}
                for row in rows:
                    tier = row[0]
                    summary[tier] = {
                        'avg_utilization_percentage': row[1],
                        'max_utilization_percentage': row[2],
                        'avg_fragmentation_percentage': row[3],
                        'avg_allocation_efficiency': row[4],
                        'avg_throughput_mbps': row[5],
                        'avg_latency_ms': row[6],
                        'sample_count': row[7]
                    }

                return summary

            except Exception as e:
                self._logger.error(f"Failed to get tier utilization summary for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_data(self) -> None:
        """Clean up old data based on retention policies."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate cutoff times
                detailed_cutoff = datetime.now(timezone.utc) - timedelta(hours=self._detailed_retention_hours)
                hourly_cutoff = datetime.now(timezone.utc) - timedelta(days=self._hourly_retention_days)
                daily_cutoff = datetime.now(timezone.utc) - timedelta(days=self._daily_retention_months * 30)

                # Clean up detailed metrics
                cursor.execute("""
                    DELETE FROM memory_allocation_history
                    WHERE timestamp < ?
                """, (detailed_cutoff.isoformat(),))
                deleted_allocations = cursor.rowcount

                cursor.execute("""
                    DELETE FROM memory_performance_metrics
                    WHERE timestamp < ?
                """, (detailed_cutoff.isoformat(),))
                deleted_metrics = cursor.rowcount

                cursor.execute("""
                    DELETE FROM memory_tier_utilization
                    WHERE timestamp < ?
                """, (detailed_cutoff.isoformat(),))
                deleted_utilization = cursor.rowcount

                cursor.execute("""
                    DELETE FROM allocation_optimization_events
                    WHERE timestamp < ?
                """, (detailed_cutoff.isoformat(),))
                deleted_events = cursor.rowcount

                # Clean up hourly aggregates
                cursor.execute("""
                    DELETE FROM memory_metrics_hourly
                    WHERE hour_timestamp < ?
                """, (hourly_cutoff.isoformat(),))
                deleted_hourly = cursor.rowcount

                # Clean up daily aggregates
                cursor.execute("""
                    DELETE FROM memory_metrics_daily
                    WHERE date < ?
                """, (daily_cutoff.date().isoformat(),))
                deleted_daily = cursor.rowcount

                conn.commit()

                self._logger.info(f"Cleaned up old data: {deleted_allocations} allocations, "
                                f"{deleted_metrics} metrics, {deleted_utilization} utilization records, "
                                f"{deleted_events} events, {deleted_hourly} hourly, {deleted_daily} daily")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old data: {e}")
                raise
            finally:
                conn.close()

    def _row_to_allocation_dict(self, row: Tuple) -> Dict[str, Any]:
        """Convert database row to allocation dictionary."""
        return {
            'allocation_id': row[0],
            'session_id': row[1],
            'timestamp': row[2],
            'layer_group': row[3],
            'memory_tier': row[4],
            'size_mb': row[5],
            'access_frequency': row[6],
            'last_accessed': row[7],
            'allocation_strategy': row[8],
            'allocation_duration_ms': row[9],
            'deallocation_timestamp': row[10],
            'peak_usage_mb': row[11],
            'average_usage_mb': row[12],
            'fragmentation_score': row[13],
            'compression_ratio': row[14],
            'swap_in_count': row[15],
            'swap_out_count': row[16],
            'prefetch_hit_rate': row[17],
            'cache_hit_rate': row[18],
            'metadata': json.loads(row[19]) if row[19] else None
        }

    def _row_to_metric_dict(self, row: Tuple) -> Dict[str, Any]:
        """Convert database row to metric dictionary."""
        return {
            'metric_id': row[0],
            'session_id': row[1],
            'timestamp': row[2],
            'metric_type': row[3],
            'memory_tier': row[4],
            'metric_value': row[5],
            'measurement_unit': row[6],
            'aggregation_period': row[7],
            'context_data': json.loads(row[8]) if row[8] else None
        }
