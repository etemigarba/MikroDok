"""
Module: allocation_profiles_db
Description: Stores reusable resource allocation configurations with mode settings and limits for IDRAlloc system
Phase: 2
Location: /src/modules/database/resource_allocation_db/allocation_profiles_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class AllocationMode(Enum):
    """IDRAlloc allocation modes."""
    LEGACY = "Legacy"
    HYBRID = "Hybrid"
    AUTO = "Auto"


class AllocationProfilesDB:
    """
    Allocation profiles database manager.
    
    Stores reusable resource allocation configurations with mode settings and limits.
    Manages IDRAlloc profiles for different training scenarios and hardware configurations.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the allocation profiles database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to resource allocation data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "resource_allocation"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "allocation_profiles.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Profile settings
        self._max_profiles = 100  # Maximum number of profiles
        self._default_gpu_limit_mb = 8192  # Default GPU memory limit
        self._default_cpu_limit_mb = 16384  # Default CPU memory limit
        self._default_nvme_limit_mb = 32768  # Default NVMe swap limit
        
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
                
                # Create allocation profiles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS allocation_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_id TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        allocation_mode TEXT CHECK(allocation_mode IN ('Legacy','Hybrid','Auto')) NOT NULL,
                        gpu_memory_limit_mb INTEGER NOT NULL,
                        cpu_memory_limit_mb INTEGER NOT NULL,
                        nvme_swap_limit_mb INTEGER NOT NULL,
                        layer_distribution_strategy TEXT DEFAULT 'frequency',
                        reallocation_threshold REAL DEFAULT 0.8,
                        swap_threshold REAL DEFAULT 0.9,
                        prefetch_enabled BOOLEAN DEFAULT 1,
                        compression_enabled BOOLEAN DEFAULT 1,
                        is_default BOOLEAN DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP,
                        usage_count INTEGER DEFAULT 0,
                        configuration_json TEXT,
                        tags TEXT
                    )
                """)
                
                # Create profile usage history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS profile_usage_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        usage_id TEXT UNIQUE NOT NULL,
                        profile_id TEXT NOT NULL,
                        session_id TEXT,
                        model_name TEXT,
                        model_size_mb INTEGER,
                        training_duration_minutes INTEGER,
                        peak_gpu_usage_mb INTEGER,
                        peak_cpu_usage_mb INTEGER,
                        peak_nvme_usage_mb INTEGER,
                        swap_events_count INTEGER DEFAULT 0,
                        reallocation_events_count INTEGER DEFAULT 0,
                        performance_score REAL,
                        efficiency_score REAL,
                        memory_utilization_score REAL,
                        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (profile_id) REFERENCES allocation_profiles(profile_id)
                    )
                """)
                
                # Create profile performance metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS profile_performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_id TEXT UNIQUE NOT NULL,
                        profile_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        measurement_unit TEXT,
                        measurement_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        session_context TEXT,
                        hardware_context TEXT,
                        FOREIGN KEY (profile_id) REFERENCES allocation_profiles(profile_id)
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_profiles_name ON allocation_profiles(name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_profiles_mode ON allocation_profiles(allocation_mode)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_profiles_active ON allocation_profiles(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocation_profiles_default ON allocation_profiles(is_default)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile_usage_profile_id ON profile_usage_history(profile_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile_usage_session ON profile_usage_history(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile_metrics_profile_id ON profile_performance_metrics(profile_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile_metrics_type ON profile_performance_metrics(metric_type)")
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = ['allocation_profiles', 'profile_usage_history', 'profile_performance_metrics']

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Allocation profiles database initialized successfully")
                
                # Create default profile if none exists
                self._create_default_profile_if_needed()
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize allocation profiles database: {e}")
                raise
            finally:
                conn.close()
    
    def _create_default_profile_if_needed(self) -> None:
        """Create a default allocation profile if none exists."""
        try:
            profiles = self.get_all_profiles()
            if not profiles:
                self.create_profile(
                    name="Default Auto",
                    description="Default automatic allocation profile with balanced settings",
                    allocation_mode=AllocationMode.AUTO,
                    gpu_memory_limit_mb=self._default_gpu_limit_mb,
                    cpu_memory_limit_mb=self._default_cpu_limit_mb,
                    nvme_swap_limit_mb=self._default_nvme_limit_mb,
                    is_default=True
                )
                self._logger.info("Created default allocation profile")
        except Exception as e:
            self._logger.error(f"Failed to create default profile: {e}")
    
    def create_profile(self, name: str, description: Optional[str] = None,
                      allocation_mode: AllocationMode = AllocationMode.AUTO,
                      gpu_memory_limit_mb: int = None,
                      cpu_memory_limit_mb: int = None,
                      nvme_swap_limit_mb: int = None,
                      layer_distribution_strategy: str = "frequency",
                      reallocation_threshold: float = 0.8,
                      swap_threshold: float = 0.9,
                      prefetch_enabled: bool = True,
                      compression_enabled: bool = True,
                      is_default: bool = False,
                      configuration: Optional[Dict[str, Any]] = None,
                      tags: Optional[List[str]] = None) -> str:
        """
        Create a new allocation profile.
        
        Args:
            name: Profile name
            description: Profile description
            allocation_mode: IDRAlloc mode
            gpu_memory_limit_mb: GPU memory limit in MB
            cpu_memory_limit_mb: CPU memory limit in MB
            nvme_swap_limit_mb: NVMe swap limit in MB
            layer_distribution_strategy: Strategy for layer distribution
            reallocation_threshold: Threshold for triggering reallocation
            swap_threshold: Threshold for triggering swap
            prefetch_enabled: Enable prefetching
            compression_enabled: Enable compression
            is_default: Whether this is the default profile
            configuration: Additional configuration as JSON
            tags: Profile tags
            
        Returns:
            Profile ID
        """
        profile_id = str(uuid.uuid4())
        
        # Use defaults if not provided
        if gpu_memory_limit_mb is None:
            gpu_memory_limit_mb = self._default_gpu_limit_mb
        if cpu_memory_limit_mb is None:
            cpu_memory_limit_mb = self._default_cpu_limit_mb
        if nvme_swap_limit_mb is None:
            nvme_swap_limit_mb = self._default_nvme_limit_mb

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # If setting as default, unset other defaults
                if is_default:
                    cursor.execute("UPDATE allocation_profiles SET is_default = 0")
                
                cursor.execute("""
                    INSERT INTO allocation_profiles (
                        profile_id, name, description, allocation_mode,
                        gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                        layer_distribution_strategy, reallocation_threshold, swap_threshold,
                        prefetch_enabled, compression_enabled, is_default,
                        configuration_json, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id, name, description, allocation_mode.value,
                    gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                    layer_distribution_strategy, reallocation_threshold, swap_threshold,
                    prefetch_enabled, compression_enabled, is_default,
                    json.dumps(configuration) if configuration else None,
                    json.dumps(tags) if tags else None
                ))

                conn.commit()
                self._logger.info(f"Created allocation profile: {name} ({profile_id})")
                return profile_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create allocation profile: {e}")
                raise
            finally:
                conn.close()

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Get allocation profile by ID.

        Args:
            profile_id: Profile ID

        Returns:
            Profile data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT profile_id, name, description, allocation_mode,
                           gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                           layer_distribution_strategy, reallocation_threshold, swap_threshold,
                           prefetch_enabled, compression_enabled, is_default, is_active,
                           created_at, updated_at, last_used_at, usage_count,
                           configuration_json, tags
                    FROM allocation_profiles
                    WHERE profile_id = ? AND is_active = 1
                """, (profile_id,))

                row = cursor.fetchone()
                if row:
                    return self._row_to_profile_dict(row)
                return None

            except Exception as e:
                self._logger.error(f"Failed to get allocation profile {profile_id}: {e}")
                raise
            finally:
                conn.close()

    def get_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get allocation profile by name.

        Args:
            name: Profile name

        Returns:
            Profile data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT profile_id, name, description, allocation_mode,
                           gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                           layer_distribution_strategy, reallocation_threshold, swap_threshold,
                           prefetch_enabled, compression_enabled, is_default, is_active,
                           created_at, updated_at, last_used_at, usage_count,
                           configuration_json, tags
                    FROM allocation_profiles
                    WHERE name = ? AND is_active = 1
                """, (name,))

                row = cursor.fetchone()
                if row:
                    return self._row_to_profile_dict(row)
                return None

            except Exception as e:
                self._logger.error(f"Failed to get allocation profile by name {name}: {e}")
                raise
            finally:
                conn.close()

    def get_default_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get the default allocation profile.

        Returns:
            Default profile data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT profile_id, name, description, allocation_mode,
                           gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                           layer_distribution_strategy, reallocation_threshold, swap_threshold,
                           prefetch_enabled, compression_enabled, is_default, is_active,
                           created_at, updated_at, last_used_at, usage_count,
                           configuration_json, tags
                    FROM allocation_profiles
                    WHERE is_default = 1 AND is_active = 1
                """)

                row = cursor.fetchone()
                if row:
                    return self._row_to_profile_dict(row)
                return None

            except Exception as e:
                self._logger.error(f"Failed to get default allocation profile: {e}")
                raise
            finally:
                conn.close()

    def get_all_profiles(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all allocation profiles.

        Args:
            include_inactive: Whether to include inactive profiles

        Returns:
            List of profile data
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if include_inactive:
                    cursor.execute("""
                        SELECT profile_id, name, description, allocation_mode,
                               gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                               layer_distribution_strategy, reallocation_threshold, swap_threshold,
                               prefetch_enabled, compression_enabled, is_default, is_active,
                               created_at, updated_at, last_used_at, usage_count,
                               configuration_json, tags
                        FROM allocation_profiles
                        ORDER BY is_default DESC, name ASC
                    """)
                else:
                    cursor.execute("""
                        SELECT profile_id, name, description, allocation_mode,
                               gpu_memory_limit_mb, cpu_memory_limit_mb, nvme_swap_limit_mb,
                               layer_distribution_strategy, reallocation_threshold, swap_threshold,
                               prefetch_enabled, compression_enabled, is_default, is_active,
                               created_at, updated_at, last_used_at, usage_count,
                               configuration_json, tags
                        FROM allocation_profiles
                        WHERE is_active = 1
                        ORDER BY is_default DESC, name ASC
                    """)

                rows = cursor.fetchall()
                return [self._row_to_profile_dict(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to get allocation profiles: {e}")
                raise
            finally:
                conn.close()

    def update_profile(self, profile_id: str, **kwargs) -> bool:
        """
        Update allocation profile.

        Args:
            profile_id: Profile ID
            **kwargs: Fields to update

        Returns:
            True if updated successfully
        """
        if not kwargs:
            return True

        # Build update query dynamically
        update_fields = []
        values = []

        allowed_fields = {
            'name', 'description', 'allocation_mode', 'gpu_memory_limit_mb',
            'cpu_memory_limit_mb', 'nvme_swap_limit_mb', 'layer_distribution_strategy',
            'reallocation_threshold', 'swap_threshold', 'prefetch_enabled',
            'compression_enabled', 'is_default', 'is_active', 'configuration_json', 'tags'
        }

        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'allocation_mode' and isinstance(value, AllocationMode):
                    value = value.value
                elif field in ['configuration_json', 'tags'] and value is not None:
                    value = json.dumps(value)

                update_fields.append(f"{field} = ?")
                values.append(value)

        if not update_fields:
            return True

        # Always update the updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # If setting as default, unset other defaults
                if kwargs.get('is_default'):
                    cursor.execute("UPDATE allocation_profiles SET is_default = 0")

                query = f"UPDATE allocation_profiles SET {', '.join(update_fields)} WHERE profile_id = ?"
                values.append(profile_id)

                cursor.execute(query, values)

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.info(f"Updated allocation profile: {profile_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update allocation profile {profile_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_profile(self, profile_id: str, soft_delete: bool = True) -> bool:
        """
        Delete allocation profile.

        Args:
            profile_id: Profile ID
            soft_delete: Whether to soft delete (mark inactive) or hard delete

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if soft_delete:
                    cursor.execute("""
                        UPDATE allocation_profiles
                        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE profile_id = ?
                    """, (profile_id,))
                else:
                    # Hard delete - also delete related records
                    cursor.execute("DELETE FROM profile_performance_metrics WHERE profile_id = ?", (profile_id,))
                    cursor.execute("DELETE FROM profile_usage_history WHERE profile_id = ?", (profile_id,))
                    cursor.execute("DELETE FROM allocation_profiles WHERE profile_id = ?", (profile_id,))

                if cursor.rowcount == 0:
                    return False

                conn.commit()
                self._logger.info(f"{'Soft' if soft_delete else 'Hard'} deleted allocation profile: {profile_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete allocation profile {profile_id}: {e}")
                raise
            finally:
                conn.close()

    def record_usage(self, profile_id: str, session_id: Optional[str] = None,
                    model_name: Optional[str] = None, model_size_mb: Optional[int] = None,
                    training_duration_minutes: Optional[int] = None,
                    peak_gpu_usage_mb: Optional[int] = None,
                    peak_cpu_usage_mb: Optional[int] = None,
                    peak_nvme_usage_mb: Optional[int] = None,
                    swap_events_count: int = 0,
                    reallocation_events_count: int = 0,
                    performance_score: Optional[float] = None,
                    efficiency_score: Optional[float] = None,
                    memory_utilization_score: Optional[float] = None,
                    notes: Optional[str] = None) -> str:
        """
        Record profile usage.

        Args:
            profile_id: Profile ID
            session_id: Training session ID
            model_name: Model name
            model_size_mb: Model size in MB
            training_duration_minutes: Training duration
            peak_gpu_usage_mb: Peak GPU usage
            peak_cpu_usage_mb: Peak CPU usage
            peak_nvme_usage_mb: Peak NVMe usage
            swap_events_count: Number of swap events
            reallocation_events_count: Number of reallocation events
            performance_score: Performance score
            efficiency_score: Efficiency score
            memory_utilization_score: Memory utilization score
            notes: Additional notes

        Returns:
            Usage ID
        """
        usage_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Record usage
                cursor.execute("""
                    INSERT INTO profile_usage_history (
                        usage_id, profile_id, session_id, model_name, model_size_mb,
                        training_duration_minutes, peak_gpu_usage_mb, peak_cpu_usage_mb,
                        peak_nvme_usage_mb, swap_events_count, reallocation_events_count,
                        performance_score, efficiency_score, memory_utilization_score, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    usage_id, profile_id, session_id, model_name, model_size_mb,
                    training_duration_minutes, peak_gpu_usage_mb, peak_cpu_usage_mb,
                    peak_nvme_usage_mb, swap_events_count, reallocation_events_count,
                    performance_score, efficiency_score, memory_utilization_score, notes
                ))

                # Update profile usage count and last used timestamp
                cursor.execute("""
                    UPDATE allocation_profiles
                    SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP
                    WHERE profile_id = ?
                """, (profile_id,))

                conn.commit()
                self._logger.info(f"Recorded usage for profile {profile_id}: {usage_id}")
                return usage_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record usage for profile {profile_id}: {e}")
                raise
            finally:
                conn.close()

    def record_performance_metric(self, profile_id: str, metric_type: str,
                                 metric_value: float, measurement_unit: Optional[str] = None,
                                 session_context: Optional[str] = None,
                                 hardware_context: Optional[str] = None) -> str:
        """
        Record performance metric for profile.

        Args:
            profile_id: Profile ID
            metric_type: Type of metric
            metric_value: Metric value
            measurement_unit: Unit of measurement
            session_context: Session context
            hardware_context: Hardware context

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO profile_performance_metrics (
                        metric_id, profile_id, metric_type, metric_value,
                        measurement_unit, session_context, hardware_context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (metric_id, profile_id, metric_type, metric_value,
                      measurement_unit, session_context, hardware_context))

                conn.commit()
                self._logger.info(f"Recorded performance metric for profile {profile_id}: {metric_type}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record performance metric for profile {profile_id}: {e}")
                raise
            finally:
                conn.close()

    def get_usage_history(self, profile_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get usage history for profile.

        Args:
            profile_id: Profile ID
            limit: Maximum number of records

        Returns:
            List of usage records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT usage_id, profile_id, session_id, model_name, model_size_mb,
                           training_duration_minutes, peak_gpu_usage_mb, peak_cpu_usage_mb,
                           peak_nvme_usage_mb, swap_events_count, reallocation_events_count,
                           performance_score, efficiency_score, memory_utilization_score,
                           used_at, notes
                    FROM profile_usage_history
                    WHERE profile_id = ?
                    ORDER BY used_at DESC
                    LIMIT ?
                """, (profile_id, limit))

                rows = cursor.fetchall()
                return [self._row_to_usage_dict(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to get usage history for profile {profile_id}: {e}")
                raise
            finally:
                conn.close()

    def _row_to_profile_dict(self, row: Tuple) -> Dict[str, Any]:
        """Convert database row to profile dictionary."""
        return {
            'profile_id': row[0],
            'name': row[1],
            'description': row[2],
            'allocation_mode': row[3],
            'gpu_memory_limit_mb': row[4],
            'cpu_memory_limit_mb': row[5],
            'nvme_swap_limit_mb': row[6],
            'layer_distribution_strategy': row[7],
            'reallocation_threshold': row[8],
            'swap_threshold': row[9],
            'prefetch_enabled': bool(row[10]),
            'compression_enabled': bool(row[11]),
            'is_default': bool(row[12]),
            'is_active': bool(row[13]),
            'created_at': row[14],
            'updated_at': row[15],
            'last_used_at': row[16],
            'usage_count': row[17],
            'configuration': json.loads(row[18]) if row[18] else None,
            'tags': json.loads(row[19]) if row[19] else None
        }

    def _row_to_usage_dict(self, row: Tuple) -> Dict[str, Any]:
        """Convert database row to usage dictionary."""
        return {
            'usage_id': row[0],
            'profile_id': row[1],
            'session_id': row[2],
            'model_name': row[3],
            'model_size_mb': row[4],
            'training_duration_minutes': row[5],
            'peak_gpu_usage_mb': row[6],
            'peak_cpu_usage_mb': row[7],
            'peak_nvme_usage_mb': row[8],
            'swap_events_count': row[9],
            'reallocation_events_count': row[10],
            'performance_score': row[11],
            'efficiency_score': row[12],
            'memory_utilization_score': row[13],
            'used_at': row[14],
            'notes': row[15]
        }
