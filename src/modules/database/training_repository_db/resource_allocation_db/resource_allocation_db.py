"""
Module: resource_allocation_db
Description: Stores IDRAlloc configurations and memory distribution strategies
Phase: 4
Location: /src/modules/database/training_repository_db/resource_allocation_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class AllocationStrategy(Enum):
    """Memory allocation strategy enumeration."""
    AUTO = "auto"
    MANUAL = "manual"
    FREQUENCY_BASED = "frequency_based"
    SIZE_BASED = "size_based"
    HYBRID = "hybrid"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    MEMORY_OPTIMIZED = "memory_optimized"


class MemoryTier(Enum):
    """Memory tier enumeration for IDRAlloc."""
    GPU_MEMORY = "gpu_memory"
    CPU_MEMORY = "cpu_memory"
    NVME_SWAP = "nvme_swap"
    DISK_CACHE = "disk_cache"


class AllocationStatus(Enum):
    """Allocation status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FAILED = "failed"
    OPTIMIZING = "optimizing"


@dataclass
class ResourceAllocation:
    """Resource allocation configuration data structure."""
    allocation_id: str
    session_id: str
    strategy: AllocationStrategy
    gpu_memory_limit_mb: int
    cpu_memory_limit_mb: int
    nvme_swap_limit_mb: int
    layer_distribution: Dict[str, MemoryTier]
    reallocation_threshold: float = 0.8
    swap_threshold: float = 0.9
    prefetch_enabled: bool = True
    compression_enabled: bool = True
    batch_size_optimization: bool = True
    gradient_checkpointing: bool = False
    mixed_precision: bool = False
    status: AllocationStatus = AllocationStatus.PENDING
    created_at: datetime = None
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    optimization_history: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class AllocationEvent:
    """Memory allocation event data structure."""
    event_id: str
    allocation_id: str
    session_id: str
    event_type: str  # allocation, deallocation, reallocation, swap
    layer_group: str
    source_tier: Optional[MemoryTier]
    target_tier: MemoryTier
    size_mb: int
    duration_ms: int
    success: bool
    timestamp: datetime
    error_message: Optional[str] = None
    performance_impact: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ResourceAllocationDB:
    """
    Database manager for IDRAlloc configurations and memory distribution strategies.
    
    Provides comprehensive tracking of resource allocation configurations, memory tier
    distributions, allocation events, and performance optimization strategies for
    training sessions with automatic cleanup and performance analytics.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the resource allocation database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "resource_allocation.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._allocation_retention_days = 90  # Keep allocations for 3 months
        self._event_retention_days = 30  # Keep events for 1 month
        self._max_allocations_per_session = 100  # Maximum allocations per session
        self._batch_size = 1000  # Batch size for bulk operations
        
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
                
                # Create resource allocations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS resource_allocations (
                        allocation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        gpu_memory_limit_mb INTEGER NOT NULL,
                        cpu_memory_limit_mb INTEGER NOT NULL,
                        nvme_swap_limit_mb INTEGER NOT NULL,
                        layer_distribution_json TEXT NOT NULL,
                        reallocation_threshold REAL DEFAULT 0.8,
                        swap_threshold REAL DEFAULT 0.9,
                        prefetch_enabled BOOLEAN DEFAULT 1,
                        compression_enabled BOOLEAN DEFAULT 1,
                        batch_size_optimization BOOLEAN DEFAULT 1,
                        gradient_checkpointing BOOLEAN DEFAULT 0,
                        mixed_precision BOOLEAN DEFAULT 0,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        activated_at TEXT,
                        deactivated_at TEXT,
                        performance_metrics_json TEXT,
                        optimization_history_json TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_resource_allocations_session_id 
                    ON resource_allocations(session_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_resource_allocations_strategy 
                    ON resource_allocations(strategy)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_resource_allocations_status 
                    ON resource_allocations(status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_resource_allocations_created_at 
                    ON resource_allocations(created_at)
                """)
                
                # Create allocation events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS allocation_events (
                        event_id TEXT PRIMARY KEY,
                        allocation_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        layer_group TEXT NOT NULL,
                        source_tier TEXT,
                        target_tier TEXT NOT NULL,
                        size_mb INTEGER NOT NULL,
                        duration_ms INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        timestamp TEXT NOT NULL,
                        error_message TEXT,
                        performance_impact_json TEXT,
                        metadata_json TEXT,
                        FOREIGN KEY (allocation_id) REFERENCES resource_allocations(allocation_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_allocation_events_allocation_id 
                    ON allocation_events(allocation_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_allocation_events_session_id 
                    ON allocation_events(session_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_allocation_events_timestamp 
                    ON allocation_events(timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_allocation_events_event_type 
                    ON allocation_events(event_type)
                """)
                
                # Create allocation statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS allocation_statistics (
                        allocation_id TEXT PRIMARY KEY,
                        total_allocations INTEGER DEFAULT 0,
                        total_deallocations INTEGER DEFAULT 0,
                        total_reallocations INTEGER DEFAULT 0,
                        total_swap_events INTEGER DEFAULT 0,
                        avg_allocation_time_ms REAL DEFAULT 0.0,
                        avg_deallocation_time_ms REAL DEFAULT 0.0,
                        avg_reallocation_time_ms REAL DEFAULT 0.0,
                        peak_gpu_usage_mb INTEGER DEFAULT 0,
                        peak_cpu_usage_mb INTEGER DEFAULT 0,
                        peak_nvme_usage_mb INTEGER DEFAULT 0,
                        efficiency_score REAL DEFAULT 0.0,
                        fragmentation_score REAL DEFAULT 0.0,
                        last_updated TEXT NOT NULL,
                        FOREIGN KEY (allocation_id) REFERENCES resource_allocations(allocation_id) ON DELETE CASCADE
                    )
                """)
                
                conn.commit()
                self._logger.info("Resource allocation database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize resource allocation database: {e}")
                raise
            finally:
                conn.close()

    def create_allocation(self, session_id: str, strategy: AllocationStrategy,
                         gpu_memory_limit_mb: int, cpu_memory_limit_mb: int,
                         nvme_swap_limit_mb: int, layer_distribution: Dict[str, MemoryTier],
                         reallocation_threshold: float = 0.8, swap_threshold: float = 0.9,
                         prefetch_enabled: bool = True, compression_enabled: bool = True,
                         batch_size_optimization: bool = True,
                         gradient_checkpointing: bool = False,
                         mixed_precision: bool = False,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new resource allocation configuration.

        Args:
            session_id: Training session identifier
            strategy: Allocation strategy
            gpu_memory_limit_mb: GPU memory limit in MB
            cpu_memory_limit_mb: CPU memory limit in MB
            nvme_swap_limit_mb: NVMe swap limit in MB
            layer_distribution: Layer to memory tier mapping
            reallocation_threshold: Threshold for reallocation
            swap_threshold: Threshold for swapping
            prefetch_enabled: Enable prefetching
            compression_enabled: Enable compression
            batch_size_optimization: Enable batch size optimization
            gradient_checkpointing: Enable gradient checkpointing
            mixed_precision: Enable mixed precision
            metadata: Additional metadata

        Returns:
            Allocation ID

        Raises:
            ValueError: If allocation limit exceeded
        """
        allocation_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check allocation limit per session
                cursor.execute("SELECT COUNT(*) FROM resource_allocations WHERE session_id = ?", (session_id,))
                allocation_count = cursor.fetchone()[0]

                if allocation_count >= self._max_allocations_per_session:
                    raise ValueError(f"Maximum allocations per session ({self._max_allocations_per_session}) exceeded")

                cursor.execute("""
                    INSERT INTO resource_allocations (
                        allocation_id, session_id, strategy, gpu_memory_limit_mb,
                        cpu_memory_limit_mb, nvme_swap_limit_mb, layer_distribution_json,
                        reallocation_threshold, swap_threshold, prefetch_enabled,
                        compression_enabled, batch_size_optimization, gradient_checkpointing,
                        mixed_precision, status, created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    allocation_id, session_id, strategy.value, gpu_memory_limit_mb,
                    cpu_memory_limit_mb, nvme_swap_limit_mb,
                    json.dumps({k: v.value for k, v in layer_distribution.items()}),
                    reallocation_threshold, swap_threshold, prefetch_enabled,
                    compression_enabled, batch_size_optimization, gradient_checkpointing,
                    mixed_precision, AllocationStatus.PENDING.value, current_time,
                    json.dumps(metadata) if metadata else None
                ))

                # Initialize statistics
                cursor.execute("""
                    INSERT INTO allocation_statistics (
                        allocation_id, last_updated
                    ) VALUES (?, ?)
                """, (allocation_id, current_time))

                conn.commit()
                self._logger.info(f"Created resource allocation {allocation_id} for session {session_id}")
                return allocation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create resource allocation: {e}")
                raise
            finally:
                conn.close()

    def get_allocation(self, allocation_id: str) -> Optional[ResourceAllocation]:
        """
        Retrieve a resource allocation by ID.

        Args:
            allocation_id: Allocation identifier

        Returns:
            ResourceAllocation object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT allocation_id, session_id, strategy, gpu_memory_limit_mb,
                           cpu_memory_limit_mb, nvme_swap_limit_mb, layer_distribution_json,
                           reallocation_threshold, swap_threshold, prefetch_enabled,
                           compression_enabled, batch_size_optimization, gradient_checkpointing,
                           mixed_precision, status, created_at, activated_at, deactivated_at,
                           performance_metrics_json, optimization_history_json, metadata_json
                    FROM resource_allocations WHERE allocation_id = ?
                """, (allocation_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Parse layer distribution
                layer_distribution = {}
                if row[6]:
                    layer_dist_data = json.loads(row[6])
                    layer_distribution = {k: MemoryTier(v) for k, v in layer_dist_data.items()}

                return ResourceAllocation(
                    allocation_id=row[0],
                    session_id=row[1],
                    strategy=AllocationStrategy(row[2]),
                    gpu_memory_limit_mb=row[3],
                    cpu_memory_limit_mb=row[4],
                    nvme_swap_limit_mb=row[5],
                    layer_distribution=layer_distribution,
                    reallocation_threshold=row[7],
                    swap_threshold=row[8],
                    prefetch_enabled=bool(row[9]),
                    compression_enabled=bool(row[10]),
                    batch_size_optimization=bool(row[11]),
                    gradient_checkpointing=bool(row[12]),
                    mixed_precision=bool(row[13]),
                    status=AllocationStatus(row[14]),
                    created_at=datetime.fromisoformat(row[15]),
                    activated_at=datetime.fromisoformat(row[16]) if row[16] else None,
                    deactivated_at=datetime.fromisoformat(row[17]) if row[17] else None,
                    performance_metrics=json.loads(row[18]) if row[18] else None,
                    optimization_history=json.loads(row[19]) if row[19] else None,
                    metadata=json.loads(row[20]) if row[20] else None
                )

            except Exception as e:
                self._logger.error(f"Failed to get resource allocation {allocation_id}: {e}")
                return None
            finally:
                conn.close()

    def update_allocation_status(self, allocation_id: str, status: AllocationStatus,
                                performance_metrics: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update allocation status and performance metrics.

        Args:
            allocation_id: Allocation identifier
            status: New allocation status
            performance_metrics: Performance metrics

        Returns:
            True if updated successfully
        """
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                updates = ["status = ?"]
                params = [status.value]

                if status == AllocationStatus.ACTIVE:
                    updates.append("activated_at = ?")
                    params.append(current_time)
                elif status in [AllocationStatus.INACTIVE, AllocationStatus.FAILED]:
                    updates.append("deactivated_at = ?")
                    params.append(current_time)

                if performance_metrics:
                    updates.append("performance_metrics_json = ?")
                    params.append(json.dumps(performance_metrics))

                params.append(allocation_id)

                query = f"UPDATE resource_allocations SET {', '.join(updates)} WHERE allocation_id = ?"
                cursor.execute(query, params)

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update allocation status {allocation_id}: {e}")
                return False
            finally:
                conn.close()

    def record_allocation_event(self, allocation_id: str, session_id: str,
                               event_type: str, layer_group: str, target_tier: MemoryTier,
                               size_mb: int, duration_ms: int, success: bool,
                               source_tier: Optional[MemoryTier] = None,
                               error_message: Optional[str] = None,
                               performance_impact: Optional[Dict[str, Any]] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record an allocation event.

        Args:
            allocation_id: Allocation identifier
            session_id: Session identifier
            event_type: Type of event (allocation, deallocation, reallocation, swap)
            layer_group: Layer group identifier
            target_tier: Target memory tier
            size_mb: Size in MB
            duration_ms: Duration in milliseconds
            success: Whether the event was successful
            source_tier: Source memory tier (for reallocations)
            error_message: Error message if failed
            performance_impact: Performance impact metrics
            metadata: Additional metadata

        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO allocation_events (
                        event_id, allocation_id, session_id, event_type, layer_group,
                        source_tier, target_tier, size_mb, duration_ms, success,
                        timestamp, error_message, performance_impact_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, allocation_id, session_id, event_type, layer_group,
                    source_tier.value if source_tier else None, target_tier.value,
                    size_mb, duration_ms, success, current_time, error_message,
                    json.dumps(performance_impact) if performance_impact else None,
                    json.dumps(metadata) if metadata else None
                ))

                # Update allocation statistics
                self._update_allocation_statistics(cursor, allocation_id, event_type, duration_ms, success)

                conn.commit()
                return event_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record allocation event: {e}")
                raise
            finally:
                conn.close()

    def _update_allocation_statistics(self, cursor: sqlite3.Cursor, allocation_id: str,
                                     event_type: str, duration_ms: int, success: bool) -> None:
        """Update allocation statistics."""
        current_time = datetime.now(timezone.utc).isoformat()

        if success:
            if event_type == "allocation":
                cursor.execute("""
                    UPDATE allocation_statistics SET
                        total_allocations = total_allocations + 1,
                        avg_allocation_time_ms = (avg_allocation_time_ms * total_allocations + ?) / (total_allocations + 1),
                        last_updated = ?
                    WHERE allocation_id = ?
                """, (duration_ms, current_time, allocation_id))
            elif event_type == "deallocation":
                cursor.execute("""
                    UPDATE allocation_statistics SET
                        total_deallocations = total_deallocations + 1,
                        avg_deallocation_time_ms = (avg_deallocation_time_ms * total_deallocations + ?) / (total_deallocations + 1),
                        last_updated = ?
                    WHERE allocation_id = ?
                """, (duration_ms, current_time, allocation_id))
            elif event_type == "reallocation":
                cursor.execute("""
                    UPDATE allocation_statistics SET
                        total_reallocations = total_reallocations + 1,
                        avg_reallocation_time_ms = (avg_reallocation_time_ms * total_reallocations + ?) / (total_reallocations + 1),
                        last_updated = ?
                    WHERE allocation_id = ?
                """, (duration_ms, current_time, allocation_id))
            elif event_type == "swap":
                cursor.execute("""
                    UPDATE allocation_statistics SET
                        total_swap_events = total_swap_events + 1,
                        last_updated = ?
                    WHERE allocation_id = ?
                """, (current_time, allocation_id))

    def get_allocation_events(self, allocation_id: str, event_type: Optional[str] = None,
                             limit: int = 1000, offset: int = 0) -> List[AllocationEvent]:
        """
        Get allocation events for an allocation.

        Args:
            allocation_id: Allocation identifier
            event_type: Filter by event type
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of AllocationEvent objects
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT event_id, allocation_id, session_id, event_type, layer_group,
                           source_tier, target_tier, size_mb, duration_ms, success,
                           timestamp, error_message, performance_impact_json, metadata_json
                    FROM allocation_events
                    WHERE allocation_id = ?
                """
                params = [allocation_id]

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)

                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    events.append(AllocationEvent(
                        event_id=row[0],
                        allocation_id=row[1],
                        session_id=row[2],
                        event_type=row[3],
                        layer_group=row[4],
                        source_tier=MemoryTier(row[5]) if row[5] else None,
                        target_tier=MemoryTier(row[6]),
                        size_mb=row[7],
                        duration_ms=row[8],
                        success=bool(row[9]),
                        timestamp=datetime.fromisoformat(row[10]),
                        error_message=row[11],
                        performance_impact=json.loads(row[12]) if row[12] else None,
                        metadata=json.loads(row[13]) if row[13] else None
                    ))

                return events

            except Exception as e:
                self._logger.error(f"Failed to get allocation events: {e}")
                return []
            finally:
                conn.close()

    def get_allocation_statistics(self, allocation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get allocation statistics.

        Args:
            allocation_id: Allocation identifier

        Returns:
            Dictionary with statistics or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT total_allocations, total_deallocations, total_reallocations,
                           total_swap_events, avg_allocation_time_ms, avg_deallocation_time_ms,
                           avg_reallocation_time_ms, peak_gpu_usage_mb, peak_cpu_usage_mb,
                           peak_nvme_usage_mb, efficiency_score, fragmentation_score, last_updated
                    FROM allocation_statistics WHERE allocation_id = ?
                """, (allocation_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'total_allocations': row[0],
                    'total_deallocations': row[1],
                    'total_reallocations': row[2],
                    'total_swap_events': row[3],
                    'avg_allocation_time_ms': row[4],
                    'avg_deallocation_time_ms': row[5],
                    'avg_reallocation_time_ms': row[6],
                    'peak_gpu_usage_mb': row[7],
                    'peak_cpu_usage_mb': row[8],
                    'peak_nvme_usage_mb': row[9],
                    'efficiency_score': row[10],
                    'fragmentation_score': row[11],
                    'last_updated': row[12]
                }

            except Exception as e:
                self._logger.error(f"Failed to get allocation statistics {allocation_id}: {e}")
                return None
            finally:
                conn.close()

    def cleanup_old_data(self, allocation_retention_days: Optional[int] = None,
                        event_retention_days: Optional[int] = None) -> Tuple[int, int]:
        """
        Clean up old allocation data based on retention policy.

        Args:
            allocation_retention_days: Number of days to retain allocations
            event_retention_days: Number of days to retain events

        Returns:
            Tuple of (allocations_deleted, events_deleted)
        """
        if allocation_retention_days is None:
            allocation_retention_days = self._allocation_retention_days
        if event_retention_days is None:
            event_retention_days = self._event_retention_days

        allocation_cutoff = datetime.now(timezone.utc) - timedelta(days=allocation_retention_days)
        event_cutoff = datetime.now(timezone.utc) - timedelta(days=event_retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old events first
                cursor.execute("""
                    DELETE FROM allocation_events WHERE timestamp < ?
                """, (event_cutoff.isoformat(),))
                events_deleted = cursor.rowcount

                # Delete old allocations
                cursor.execute("""
                    DELETE FROM resource_allocations
                    WHERE created_at < ? AND status IN ('inactive', 'failed')
                """, (allocation_cutoff.isoformat(),))
                allocations_deleted = cursor.rowcount

                conn.commit()

                if allocations_deleted > 0 or events_deleted > 0:
                    self._logger.info(f"Cleaned up {allocations_deleted} allocations and {events_deleted} events")

                return allocations_deleted, events_deleted

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old data: {e}")
                return 0, 0
            finally:
                conn.close()
