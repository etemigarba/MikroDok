"""
Module: allocation_state_db
Description: Maintains current memory distribution state and layer placement mappings for IDRAlloc system
Phase: 2
Location: /src/modules/database/resource_allocation_db/allocation_state_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class LayerState(Enum):
    """Layer allocation states."""
    ALLOCATED = "allocated"
    SWAPPED_OUT = "swapped_out"
    PREFETCHING = "prefetching"
    MIGRATING = "migrating"
    DEALLOCATED = "deallocated"


class MemoryTier(Enum):
    """Memory tier types for IDRAlloc."""
    GPU_VRAM = "gpu_vram"
    SYSTEM_RAM = "system_ram"
    NVME_SWAP = "nvme_swap"


class AllocationStateDB:
    """
    Allocation state database manager.
    
    Maintains current memory distribution state and layer placement mappings.
    Tracks real-time allocation state for the IDRAlloc system, enabling
    efficient memory management and optimization decisions.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the allocation state database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to resource allocation data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "resource_allocation"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "allocation_state.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # State tracking
        self._active_sessions: Set[str] = set()
        self._state_cache = {}  # In-memory cache for fast access
        self._cache_lock = threading.Lock()
        
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
                
                # Create current allocation state table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS current_allocation_state (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        allocation_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        layer_group TEXT NOT NULL,
                        layer_name TEXT NOT NULL,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')) NOT NULL,
                        size_mb INTEGER NOT NULL,
                        offset_mb INTEGER DEFAULT 0,
                        state TEXT CHECK(state IN ('allocated','swapped_out','prefetching','migrating','deallocated')) NOT NULL,
                        priority_score REAL DEFAULT 0.5,
                        access_frequency INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP,
                        allocation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_pinned BOOLEAN DEFAULT 0,
                        is_compressed BOOLEAN DEFAULT 0,
                        compression_ratio REAL,
                        prefetch_scheduled BOOLEAN DEFAULT 0,
                        migration_target_tier TEXT,
                        metadata_json TEXT
                    )
                """)
                
                # Create memory tier capacity table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_tier_capacity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        memory_tier TEXT CHECK(memory_tier IN ('gpu_vram','system_ram','nvme_swap')) NOT NULL,
                        total_capacity_mb INTEGER NOT NULL,
                        allocated_mb INTEGER DEFAULT 0,
                        reserved_mb INTEGER DEFAULT 0,
                        free_mb INTEGER NOT NULL,
                        fragmented_mb INTEGER DEFAULT 0,
                        largest_free_block_mb INTEGER DEFAULT 0,
                        allocation_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(session_id, memory_tier)
                    )
                """)
                
                # Create layer placement mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS layer_placement_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mapping_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        layer_group TEXT NOT NULL,
                        layer_index INTEGER NOT NULL,
                        layer_type TEXT NOT NULL,
                        layer_size_mb INTEGER NOT NULL,
                        preferred_tier TEXT CHECK(preferred_tier IN ('gpu_vram','system_ram','nvme_swap')),
                        current_tier TEXT CHECK(current_tier IN ('gpu_vram','system_ram','nvme_swap')),
                        access_pattern TEXT,
                        dependency_layers TEXT,
                        placement_strategy TEXT DEFAULT 'auto',
                        placement_score REAL DEFAULT 0.5,
                        is_critical BOOLEAN DEFAULT 0,
                        can_swap BOOLEAN DEFAULT 1,
                        can_compress BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create allocation sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS allocation_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        model_name TEXT NOT NULL,
                        model_size_mb INTEGER NOT NULL,
                        allocation_mode TEXT NOT NULL,
                        profile_id TEXT,
                        total_layers INTEGER NOT NULL,
                        allocated_layers INTEGER DEFAULT 0,
                        gpu_allocation_mb INTEGER DEFAULT 0,
                        cpu_allocation_mb INTEGER DEFAULT 0,
                        nvme_allocation_mb INTEGER DEFAULT 0,
                        session_state TEXT DEFAULT 'initializing',
                        optimization_enabled BOOLEAN DEFAULT 1,
                        auto_migration_enabled BOOLEAN DEFAULT 1,
                        compression_enabled BOOLEAN DEFAULT 1,
                        prefetch_enabled BOOLEAN DEFAULT 1,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        configuration_json TEXT
                    )
                """)
                
                # Create allocation locks table for concurrency control
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS allocation_locks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lock_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_identifier TEXT NOT NULL,
                        lock_type TEXT CHECK(lock_type IN ('read','write','exclusive')) NOT NULL,
                        acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        holder_thread TEXT,
                        lock_metadata TEXT
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_state_session ON current_allocation_state(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_state_layer ON current_allocation_state(layer_group, layer_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_state_tier ON current_allocation_state(memory_tier)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_state_state ON current_allocation_state(state)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_state_priority ON current_allocation_state(priority_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tier_capacity_session ON memory_tier_capacity(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_layer_mappings_session ON layer_placement_mappings(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_layer_mappings_model ON layer_placement_mappings(model_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_layer_mappings_group ON layer_placement_mappings(layer_group)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_state ON allocation_sessions(session_state)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_locks_session ON allocation_locks(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_locks_resource ON allocation_locks(resource_type, resource_identifier)")
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'current_allocation_state', 'memory_tier_capacity', 
                    'layer_placement_mappings', 'allocation_sessions', 'allocation_locks'
                ]

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Allocation state database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize allocation state database: {e}")
                raise
            finally:
                conn.close()
    
    def create_session(self, session_id: str, model_name: str, model_size_mb: int,
                      allocation_mode: str, total_layers: int,
                      profile_id: Optional[str] = None,
                      configuration: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a new allocation session.
        
        Args:
            session_id: Unique session identifier
            model_name: Name of the model
            model_size_mb: Total model size in MB
            allocation_mode: Allocation mode (Legacy, Hybrid, Auto)
            total_layers: Total number of layers
            profile_id: Associated profile ID
            configuration: Session configuration
            
        Returns:
            True if created successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO allocation_sessions (
                        session_id, model_name, model_size_mb, allocation_mode,
                        total_layers, profile_id, configuration_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, model_name, model_size_mb, allocation_mode,
                    total_layers, profile_id,
                    json.dumps(configuration) if configuration else None
                ))

                conn.commit()
                
                with self._cache_lock:
                    self._active_sessions.add(session_id)
                
                self._logger.info(f"Created allocation session: {session_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create allocation session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def initialize_tier_capacity(self, session_id: str, memory_tier: MemoryTier,
                                total_capacity_mb: int, reserved_mb: int = 0) -> bool:
        """
        Initialize memory tier capacity for session.

        Args:
            session_id: Session identifier
            memory_tier: Memory tier
            total_capacity_mb: Total capacity in MB
            reserved_mb: Reserved memory in MB

        Returns:
            True if initialized successfully
        """
        free_mb = total_capacity_mb - reserved_mb

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO memory_tier_capacity (
                        session_id, memory_tier, total_capacity_mb, reserved_mb,
                        free_mb, largest_free_block_mb
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id, memory_tier.value, total_capacity_mb, reserved_mb,
                    free_mb, free_mb
                ))

                conn.commit()
                self._logger.info(f"Initialized {memory_tier.value} capacity for session {session_id}: {total_capacity_mb}MB")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize tier capacity: {e}")
                raise
            finally:
                conn.close()

    def allocate_layer(self, session_id: str, layer_group: str, layer_name: str,
                      memory_tier: MemoryTier, size_mb: int, offset_mb: int = 0,
                      priority_score: float = 0.5, is_pinned: bool = False,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Allocate a layer to a memory tier.

        Args:
            session_id: Session identifier
            layer_group: Layer group identifier
            layer_name: Layer name
            memory_tier: Target memory tier
            size_mb: Allocation size in MB
            offset_mb: Offset within tier
            priority_score: Priority score for allocation
            is_pinned: Whether allocation is pinned
            metadata: Additional metadata

        Returns:
            Allocation ID
        """
        allocation_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check available capacity
                cursor.execute("""
                    SELECT free_mb FROM memory_tier_capacity
                    WHERE session_id = ? AND memory_tier = ?
                """, (session_id, memory_tier.value))

                row = cursor.fetchone()
                if not row or row[0] < size_mb:
                    raise ValueError(f"Insufficient capacity in {memory_tier.value}: need {size_mb}MB, available {row[0] if row else 0}MB")

                # Create allocation record
                cursor.execute("""
                    INSERT INTO current_allocation_state (
                        allocation_id, session_id, layer_group, layer_name,
                        memory_tier, size_mb, offset_mb, state, priority_score,
                        is_pinned, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    allocation_id, session_id, layer_group, layer_name,
                    memory_tier.value, size_mb, offset_mb, LayerState.ALLOCATED.value,
                    priority_score, is_pinned,
                    json.dumps(metadata) if metadata else None
                ))

                # Update tier capacity
                cursor.execute("""
                    UPDATE memory_tier_capacity
                    SET allocated_mb = allocated_mb + ?,
                        free_mb = free_mb - ?,
                        allocation_count = allocation_count + 1,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND memory_tier = ?
                """, (size_mb, size_mb, session_id, memory_tier.value))

                # Update session allocation count
                if memory_tier == MemoryTier.GPU_VRAM:
                    cursor.execute("""
                        UPDATE allocation_sessions
                        SET gpu_allocation_mb = gpu_allocation_mb + ?,
                            allocated_layers = allocated_layers + 1,
                            last_activity = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (size_mb, session_id))
                elif memory_tier == MemoryTier.SYSTEM_RAM:
                    cursor.execute("""
                        UPDATE allocation_sessions
                        SET cpu_allocation_mb = cpu_allocation_mb + ?,
                            allocated_layers = allocated_layers + 1,
                            last_activity = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (size_mb, session_id))
                elif memory_tier == MemoryTier.NVME_SWAP:
                    cursor.execute("""
                        UPDATE allocation_sessions
                        SET nvme_allocation_mb = nvme_allocation_mb + ?,
                            allocated_layers = allocated_layers + 1,
                            last_activity = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (size_mb, session_id))

                conn.commit()
                self._logger.info(f"Allocated layer {layer_name} to {memory_tier.value}: {allocation_id}")
                return allocation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to allocate layer {layer_name}: {e}")
                raise
            finally:
                conn.close()

    def deallocate_layer(self, allocation_id: str) -> bool:
        """
        Deallocate a layer.

        Args:
            allocation_id: Allocation identifier

        Returns:
            True if deallocated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get allocation details
                cursor.execute("""
                    SELECT session_id, memory_tier, size_mb, state
                    FROM current_allocation_state
                    WHERE allocation_id = ?
                """, (allocation_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                session_id, memory_tier, size_mb, current_state = row

                if current_state == LayerState.DEALLOCATED.value:
                    return True  # Already deallocated

                # Update allocation state
                cursor.execute("""
                    UPDATE current_allocation_state
                    SET state = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE allocation_id = ?
                """, (LayerState.DEALLOCATED.value, allocation_id))

                # Update tier capacity
                cursor.execute("""
                    UPDATE memory_tier_capacity
                    SET allocated_mb = allocated_mb - ?,
                        free_mb = free_mb + ?,
                        allocation_count = allocation_count - 1,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND memory_tier = ?
                """, (size_mb, size_mb, session_id, memory_tier))

                # Update session allocation count
                if memory_tier == MemoryTier.GPU_VRAM.value:
                    cursor.execute("""
                        UPDATE allocation_sessions
                        SET gpu_allocation_mb = gpu_allocation_mb - ?,
                            allocated_layers = allocated_layers - 1,
                            last_activity = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (size_mb, session_id))
                elif memory_tier == MemoryTier.SYSTEM_RAM.value:
                    cursor.execute("""
                        UPDATE allocation_sessions
                        SET cpu_allocation_mb = cpu_allocation_mb - ?,
                            allocated_layers = allocated_layers - 1,
                            last_activity = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (size_mb, session_id))
                elif memory_tier == MemoryTier.NVME_SWAP.value:
                    cursor.execute("""
                        UPDATE allocation_sessions
                        SET nvme_allocation_mb = nvme_allocation_mb - ?,
                            allocated_layers = allocated_layers - 1,
                            last_activity = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (size_mb, session_id))

                conn.commit()
                self._logger.info(f"Deallocated layer: {allocation_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to deallocate layer {allocation_id}: {e}")
                raise
            finally:
                conn.close()

    def migrate_layer(self, allocation_id: str, target_tier: MemoryTier,
                     target_offset: int = 0) -> bool:
        """
        Migrate a layer to a different memory tier.

        Args:
            allocation_id: Allocation identifier
            target_tier: Target memory tier
            target_offset: Target offset within tier

        Returns:
            True if migration initiated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get current allocation details
                cursor.execute("""
                    SELECT session_id, memory_tier, size_mb, state
                    FROM current_allocation_state
                    WHERE allocation_id = ?
                """, (allocation_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                session_id, current_tier, size_mb, current_state = row

                if current_tier == target_tier.value:
                    return True  # Already in target tier

                # Check target tier capacity
                cursor.execute("""
                    SELECT free_mb FROM memory_tier_capacity
                    WHERE session_id = ? AND memory_tier = ?
                """, (session_id, target_tier.value))

                target_row = cursor.fetchone()
                if not target_row or target_row[0] < size_mb:
                    raise ValueError(f"Insufficient capacity in target tier {target_tier.value}")

                # Update allocation state to migrating
                cursor.execute("""
                    UPDATE current_allocation_state
                    SET state = ?, migration_target_tier = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE allocation_id = ?
                """, (LayerState.MIGRATING.value, target_tier.value, allocation_id))

                conn.commit()
                self._logger.info(f"Initiated migration of {allocation_id} to {target_tier.value}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to migrate layer {allocation_id}: {e}")
                raise
            finally:
                conn.close()

    def complete_migration(self, allocation_id: str) -> bool:
        """
        Complete layer migration.

        Args:
            allocation_id: Allocation identifier

        Returns:
            True if migration completed successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get migration details
                cursor.execute("""
                    SELECT session_id, memory_tier, migration_target_tier, size_mb
                    FROM current_allocation_state
                    WHERE allocation_id = ? AND state = ?
                """, (allocation_id, LayerState.MIGRATING.value))

                row = cursor.fetchone()
                if not row:
                    return False

                session_id, source_tier, target_tier, size_mb = row

                # Update source tier capacity
                cursor.execute("""
                    UPDATE memory_tier_capacity
                    SET allocated_mb = allocated_mb - ?,
                        free_mb = free_mb + ?,
                        allocation_count = allocation_count - 1,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND memory_tier = ?
                """, (size_mb, size_mb, session_id, source_tier))

                # Update target tier capacity
                cursor.execute("""
                    UPDATE memory_tier_capacity
                    SET allocated_mb = allocated_mb + ?,
                        free_mb = free_mb - ?,
                        allocation_count = allocation_count + 1,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND memory_tier = ?
                """, (size_mb, size_mb, session_id, target_tier))

                # Update allocation state
                cursor.execute("""
                    UPDATE current_allocation_state
                    SET memory_tier = ?, state = ?, migration_target_tier = NULL,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE allocation_id = ?
                """, (target_tier, LayerState.ALLOCATED.value, allocation_id))

                conn.commit()
                self._logger.info(f"Completed migration of {allocation_id} from {source_tier} to {target_tier}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to complete migration {allocation_id}: {e}")
                raise
            finally:
                conn.close()

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current session state.

        Args:
            session_id: Session identifier

        Returns:
            Session state data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, model_name, model_size_mb, allocation_mode,
                           total_layers, allocated_layers, gpu_allocation_mb,
                           cpu_allocation_mb, nvme_allocation_mb, session_state,
                           started_at, last_activity, configuration_json
                    FROM allocation_sessions
                    WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'session_id': row[0],
                        'model_name': row[1],
                        'model_size_mb': row[2],
                        'allocation_mode': row[3],
                        'total_layers': row[4],
                        'allocated_layers': row[5],
                        'gpu_allocation_mb': row[6],
                        'cpu_allocation_mb': row[7],
                        'nvme_allocation_mb': row[8],
                        'session_state': row[9],
                        'started_at': row[10],
                        'last_activity': row[11],
                        'configuration': json.loads(row[12]) if row[12] else None
                    }
                return None

            except Exception as e:
                self._logger.error(f"Failed to get session state {session_id}: {e}")
                raise
            finally:
                conn.close()

    def get_tier_capacity(self, session_id: str, memory_tier: Optional[MemoryTier] = None) -> Dict[str, Any]:
        """
        Get memory tier capacity information.

        Args:
            session_id: Session identifier
            memory_tier: Specific tier (if None, returns all tiers)

        Returns:
            Capacity information
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if memory_tier:
                    cursor.execute("""
                        SELECT memory_tier, total_capacity_mb, allocated_mb, reserved_mb,
                               free_mb, fragmented_mb, largest_free_block_mb, allocation_count
                        FROM memory_tier_capacity
                        WHERE session_id = ? AND memory_tier = ?
                    """, (session_id, memory_tier.value))

                    row = cursor.fetchone()
                    if row:
                        return {
                            'memory_tier': row[0],
                            'total_capacity_mb': row[1],
                            'allocated_mb': row[2],
                            'reserved_mb': row[3],
                            'free_mb': row[4],
                            'fragmented_mb': row[5],
                            'largest_free_block_mb': row[6],
                            'allocation_count': row[7],
                            'utilization_percentage': (row[2] / row[1] * 100) if row[1] > 0 else 0
                        }
                    return {}
                else:
                    cursor.execute("""
                        SELECT memory_tier, total_capacity_mb, allocated_mb, reserved_mb,
                               free_mb, fragmented_mb, largest_free_block_mb, allocation_count
                        FROM memory_tier_capacity
                        WHERE session_id = ?
                    """, (session_id,))

                    rows = cursor.fetchall()
                    capacity_info = {}
                    for row in rows:
                        tier = row[0]
                        capacity_info[tier] = {
                            'total_capacity_mb': row[1],
                            'allocated_mb': row[2],
                            'reserved_mb': row[3],
                            'free_mb': row[4],
                            'fragmented_mb': row[5],
                            'largest_free_block_mb': row[6],
                            'allocation_count': row[7],
                            'utilization_percentage': (row[2] / row[1] * 100) if row[1] > 0 else 0
                        }
                    return capacity_info

            except Exception as e:
                self._logger.error(f"Failed to get tier capacity for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def get_layer_allocations(self, session_id: str, memory_tier: Optional[MemoryTier] = None,
                             state: Optional[LayerState] = None) -> List[Dict[str, Any]]:
        """
        Get layer allocations for session.

        Args:
            session_id: Session identifier
            memory_tier: Filter by memory tier
            state: Filter by allocation state

        Returns:
            List of allocation records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT allocation_id, layer_group, layer_name, memory_tier,
                           size_mb, offset_mb, state, priority_score, access_frequency,
                           last_accessed, allocation_timestamp, last_updated,
                           is_pinned, is_compressed, compression_ratio, metadata_json
                    FROM current_allocation_state
                    WHERE session_id = ?
                """
                params = [session_id]

                if memory_tier:
                    query += " AND memory_tier = ?"
                    params.append(memory_tier.value)

                if state:
                    query += " AND state = ?"
                    params.append(state.value)

                query += " ORDER BY layer_group, layer_name"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                allocations = []
                for row in rows:
                    allocations.append({
                        'allocation_id': row[0],
                        'layer_group': row[1],
                        'layer_name': row[2],
                        'memory_tier': row[3],
                        'size_mb': row[4],
                        'offset_mb': row[5],
                        'state': row[6],
                        'priority_score': row[7],
                        'access_frequency': row[8],
                        'last_accessed': row[9],
                        'allocation_timestamp': row[10],
                        'last_updated': row[11],
                        'is_pinned': bool(row[12]),
                        'is_compressed': bool(row[13]),
                        'compression_ratio': row[14],
                        'metadata': json.loads(row[15]) if row[15] else None
                    })

                return allocations

            except Exception as e:
                self._logger.error(f"Failed to get layer allocations for session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up session data.

        Args:
            session_id: Session identifier

        Returns:
            True if cleaned up successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete allocation state
                cursor.execute("DELETE FROM current_allocation_state WHERE session_id = ?", (session_id,))

                # Delete tier capacity
                cursor.execute("DELETE FROM memory_tier_capacity WHERE session_id = ?", (session_id,))

                # Delete layer mappings
                cursor.execute("DELETE FROM layer_placement_mappings WHERE session_id = ?", (session_id,))

                # Delete locks
                cursor.execute("DELETE FROM allocation_locks WHERE session_id = ?", (session_id,))

                # Update session state
                cursor.execute("""
                    UPDATE allocation_sessions
                    SET session_state = 'completed', last_activity = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """, (session_id,))

                conn.commit()

                with self._cache_lock:
                    self._active_sessions.discard(session_id)

                self._logger.info(f"Cleaned up session: {session_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup session {session_id}: {e}")
                raise
            finally:
                conn.close()
