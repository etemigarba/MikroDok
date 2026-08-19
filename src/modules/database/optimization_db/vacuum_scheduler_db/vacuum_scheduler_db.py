"""
Module: vacuum_scheduler_db
Description: Implements incremental auto-vacuum with fragmentation monitoring
Phase: 4
Location: /src/modules/database/optimization_db/vacuum_scheduler_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import time
import uuid
# import schedule  # Optional dependency for advanced scheduling
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Set

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class VacuumType(Enum):
    """Types of vacuum operations."""
    INCREMENTAL = "incremental"
    FULL = "full"
    AUTO = "auto"
    MANUAL = "manual"


class VacuumStatus(Enum):
    """Status of vacuum operations."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FragmentationLevel(Enum):
    """Fragmentation severity levels."""
    LOW = "low"          # < 10%
    MODERATE = "moderate"  # 10-25%
    HIGH = "high"        # 25-50%
    CRITICAL = "critical"  # > 50%


@dataclass
class DatabaseInfo:
    """Information about a database file."""
    db_id: str
    db_path: str
    db_name: str
    file_size_bytes: int
    page_count: int
    page_size: int
    freelist_count: int
    fragmentation_percent: float
    last_vacuum: Optional[datetime]
    last_analyzed: Optional[datetime]
    auto_vacuum_mode: str
    journal_mode: str
    metadata: Dict[str, Any]


@dataclass
class VacuumTask:
    """Vacuum operation task."""
    task_id: str
    db_id: str
    vacuum_type: VacuumType
    status: VacuumStatus
    priority: int
    scheduled_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    pages_freed: Optional[int]
    size_reduction_bytes: Optional[int]
    fragmentation_before: Optional[float]
    fragmentation_after: Optional[float]
    error_details: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class FragmentationReport:
    """Database fragmentation analysis report."""
    report_id: str
    db_id: str
    analyzed_at: datetime
    total_pages: int
    used_pages: int
    free_pages: int
    fragmentation_percent: float
    fragmentation_level: FragmentationLevel
    recommended_action: str
    estimated_benefit: str
    file_size_mb: float
    wasted_space_mb: float
    tables_analyzed: int
    indexes_analyzed: int


class VacuumSchedulerDB:
    """
    Database vacuum scheduler with incremental auto-vacuum and fragmentation monitoring.
    
    Implements intelligent vacuum scheduling based on fragmentation levels, usage patterns,
    and system load. Provides comprehensive monitoring of database health and automatic
    optimization to maintain optimal performance while minimizing disruption.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the vacuum scheduler database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to optimization data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "optimization"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "vacuum_scheduler.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._fragmentation_thresholds = {
            FragmentationLevel.LOW: 10.0,
            FragmentationLevel.MODERATE: 25.0,
            FragmentationLevel.HIGH: 50.0,
            FragmentationLevel.CRITICAL: 75.0
        }
        self._auto_vacuum_threshold = 25.0  # Trigger auto-vacuum at 25% fragmentation
        self._analysis_interval_hours = 6   # Analyze fragmentation every 6 hours
        self._max_concurrent_vacuums = 1    # Only one vacuum at a time
        
        # Runtime state
        self._active_vacuums: Set[str] = set()
        self._monitored_databases: Dict[str, str] = {}  # db_id -> db_path mapping
        self._scheduler_running = False
        
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
                
                # Create databases table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS databases (
                        db_id TEXT PRIMARY KEY,
                        db_path TEXT NOT NULL UNIQUE,
                        db_name TEXT NOT NULL,
                        file_size_bytes INTEGER DEFAULT 0,
                        page_count INTEGER DEFAULT 0,
                        page_size INTEGER DEFAULT 4096,
                        freelist_count INTEGER DEFAULT 0,
                        fragmentation_percent REAL DEFAULT 0.0,
                        last_vacuum TIMESTAMP,
                        last_analyzed TIMESTAMP,
                        auto_vacuum_mode TEXT DEFAULT 'NONE',
                        journal_mode TEXT DEFAULT 'DELETE',
                        metadata_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create vacuum tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vacuum_tasks (
                        task_id TEXT PRIMARY KEY,
                        db_id TEXT NOT NULL,
                        vacuum_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        priority INTEGER DEFAULT 5,
                        scheduled_at TIMESTAMP NOT NULL,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        duration_seconds INTEGER,
                        pages_freed INTEGER,
                        size_reduction_bytes INTEGER,
                        fragmentation_before REAL,
                        fragmentation_after REAL,
                        error_details TEXT,
                        metadata_json TEXT,
                        FOREIGN KEY (db_id) REFERENCES databases (db_id)
                    )
                """)
                
                # Create fragmentation reports table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fragmentation_reports (
                        report_id TEXT PRIMARY KEY,
                        db_id TEXT NOT NULL,
                        analyzed_at TIMESTAMP NOT NULL,
                        total_pages INTEGER NOT NULL,
                        used_pages INTEGER NOT NULL,
                        free_pages INTEGER NOT NULL,
                        fragmentation_percent REAL NOT NULL,
                        fragmentation_level TEXT NOT NULL,
                        recommended_action TEXT NOT NULL,
                        estimated_benefit TEXT,
                        file_size_mb REAL DEFAULT 0.0,
                        wasted_space_mb REAL DEFAULT 0.0,
                        tables_analyzed INTEGER DEFAULT 0,
                        indexes_analyzed INTEGER DEFAULT 0,
                        FOREIGN KEY (db_id) REFERENCES databases (db_id)
                    )
                """)
                
                # Create performance indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_databases_fragmentation ON databases (fragmentation_percent)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_databases_last_vacuum ON databases (last_vacuum)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_scheduled ON vacuum_tasks (status, scheduled_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_db_status ON vacuum_tasks (db_id, status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_db_analyzed ON fragmentation_reports (db_id, analyzed_at)")
                
                conn.commit()
                conn.close()
                
                self._logger.info("Vacuum scheduler database initialized successfully")
                
        except Exception as e:
            self._logger.error(f"Failed to initialize vacuum scheduler database: {e}")
            raise

    def register_database(self, db_path: str, db_name: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Register a database for vacuum monitoring.

        Args:
            db_path: Path to the database file
            db_name: Optional display name for the database
            metadata: Additional metadata

        Returns:
            Database ID
        """
        db_id = str(uuid.uuid4())
        db_name = db_name or Path(db_path).stem

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if database already registered
                cursor.execute("SELECT db_id FROM databases WHERE db_path = ?", (db_path,))
                if cursor.fetchone():
                    raise ValueError(f"Database {db_path} already registered")

                # Get initial database info
                db_info = self._analyze_database_file(db_path)

                # Register the database
                cursor.execute("""
                    INSERT INTO databases (
                        db_id, db_path, db_name, file_size_bytes, page_count,
                        page_size, freelist_count, fragmentation_percent,
                        auto_vacuum_mode, journal_mode, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    db_id, db_path, db_name, db_info['file_size_bytes'],
                    db_info['page_count'], db_info['page_size'], db_info['freelist_count'],
                    db_info['fragmentation_percent'], db_info['auto_vacuum_mode'],
                    db_info['journal_mode'], json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._monitored_databases[db_id] = db_path
                self._logger.info(f"Registered database {db_name} with ID {db_id}")
                return db_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to register database {db_path}: {e}")
                raise
            finally:
                conn.close()

    def _analyze_database_file(self, db_path: str) -> Dict[str, Any]:
        """
        Analyze a database file to get current statistics.

        Args:
            db_path: Path to the database file

        Returns:
            Dictionary with database statistics
        """
        try:
            # Get file size
            file_size = Path(db_path).stat().st_size

            # Connect to database and get PRAGMA info
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get page info
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            cursor.execute("PRAGMA freelist_count")
            freelist_count = cursor.fetchone()[0]

            cursor.execute("PRAGMA auto_vacuum")
            auto_vacuum_mode = cursor.fetchone()[0]
            auto_vacuum_modes = {0: 'NONE', 1: 'FULL', 2: 'INCREMENTAL'}
            auto_vacuum_mode = auto_vacuum_modes.get(auto_vacuum_mode, 'UNKNOWN')

            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]

            # Calculate fragmentation
            total_pages = page_count
            free_pages = freelist_count
            fragmentation_percent = (free_pages / total_pages * 100) if total_pages > 0 else 0.0

            conn.close()

            return {
                'file_size_bytes': file_size,
                'page_count': page_count,
                'page_size': page_size,
                'freelist_count': freelist_count,
                'fragmentation_percent': fragmentation_percent,
                'auto_vacuum_mode': auto_vacuum_mode,
                'journal_mode': journal_mode
            }

        except Exception as e:
            self._logger.error(f"Failed to analyze database file {db_path}: {e}")
            return {
                'file_size_bytes': 0,
                'page_count': 0,
                'page_size': 4096,
                'freelist_count': 0,
                'fragmentation_percent': 0.0,
                'auto_vacuum_mode': 'UNKNOWN',
                'journal_mode': 'UNKNOWN'
            }

    def analyze_fragmentation(self, db_id: str) -> str:
        """
        Analyze database fragmentation and generate a report.

        Args:
            db_id: Database identifier

        Returns:
            Report ID
        """
        report_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get database info
                cursor.execute("SELECT db_path, db_name FROM databases WHERE db_id = ?", (db_id,))
                db_row = cursor.fetchone()
                if not db_row:
                    raise ValueError(f"Database {db_id} not found")

                db_path, db_name = db_row

                # Analyze the database file
                analysis = self._perform_fragmentation_analysis(db_path)

                # Determine fragmentation level
                fragmentation_level = self._get_fragmentation_level(analysis['fragmentation_percent'])

                # Generate recommendations
                recommended_action, estimated_benefit = self._generate_vacuum_recommendation(
                    analysis['fragmentation_percent'], fragmentation_level
                )

                # Create fragmentation report
                cursor.execute("""
                    INSERT INTO fragmentation_reports (
                        report_id, db_id, analyzed_at, total_pages, used_pages,
                        free_pages, fragmentation_percent, fragmentation_level,
                        recommended_action, estimated_benefit, file_size_mb,
                        wasted_space_mb, tables_analyzed, indexes_analyzed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id, db_id, datetime.now(timezone.utc),
                    analysis['total_pages'], analysis['used_pages'], analysis['free_pages'],
                    analysis['fragmentation_percent'], fragmentation_level.value,
                    recommended_action, estimated_benefit, analysis['file_size_mb'],
                    analysis['wasted_space_mb'], analysis['tables_analyzed'],
                    analysis['indexes_analyzed']
                ))

                # Update database record
                cursor.execute("""
                    UPDATE databases SET
                        fragmentation_percent = ?,
                        last_analyzed = ?,
                        updated_at = ?
                    WHERE db_id = ?
                """, (
                    analysis['fragmentation_percent'],
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    db_id
                ))

                conn.commit()
                self._logger.info(f"Generated fragmentation report {report_id} for database {db_name}")
                return report_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to analyze fragmentation for database {db_id}: {e}")
                raise
            finally:
                conn.close()

    def _perform_fragmentation_analysis(self, db_path: str) -> Dict[str, Any]:
        """
        Perform detailed fragmentation analysis on a database.

        Args:
            db_path: Path to the database file

        Returns:
            Dictionary with analysis results
        """
        try:
            # Get file size
            file_size = Path(db_path).stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            # Connect and analyze
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get page statistics
            cursor.execute("PRAGMA page_count")
            total_pages = cursor.fetchone()[0]

            cursor.execute("PRAGMA freelist_count")
            free_pages = cursor.fetchone()[0]

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            used_pages = total_pages - free_pages
            fragmentation_percent = (free_pages / total_pages * 100) if total_pages > 0 else 0.0
            wasted_space_mb = (free_pages * page_size) / (1024 * 1024)

            # Count tables and indexes
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            tables_analyzed = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
            indexes_analyzed = cursor.fetchone()[0]

            conn.close()

            return {
                'total_pages': total_pages,
                'used_pages': used_pages,
                'free_pages': free_pages,
                'fragmentation_percent': fragmentation_percent,
                'file_size_mb': file_size_mb,
                'wasted_space_mb': wasted_space_mb,
                'tables_analyzed': tables_analyzed,
                'indexes_analyzed': indexes_analyzed
            }

        except Exception as e:
            self._logger.error(f"Failed to perform fragmentation analysis on {db_path}: {e}")
            return {
                'total_pages': 0,
                'used_pages': 0,
                'free_pages': 0,
                'fragmentation_percent': 0.0,
                'file_size_mb': 0.0,
                'wasted_space_mb': 0.0,
                'tables_analyzed': 0,
                'indexes_analyzed': 0
            }

    def _get_fragmentation_level(self, fragmentation_percent: float) -> FragmentationLevel:
        """
        Determine fragmentation level based on percentage.

        Args:
            fragmentation_percent: Fragmentation percentage

        Returns:
            FragmentationLevel enum
        """
        if fragmentation_percent >= self._fragmentation_thresholds[FragmentationLevel.CRITICAL]:
            return FragmentationLevel.CRITICAL
        elif fragmentation_percent >= self._fragmentation_thresholds[FragmentationLevel.HIGH]:
            return FragmentationLevel.HIGH
        elif fragmentation_percent >= self._fragmentation_thresholds[FragmentationLevel.MODERATE]:
            return FragmentationLevel.MODERATE
        else:
            return FragmentationLevel.LOW

    def _generate_vacuum_recommendation(self, fragmentation_percent: float,
                                      fragmentation_level: FragmentationLevel) -> Tuple[str, str]:
        """
        Generate vacuum recommendation based on fragmentation analysis.

        Args:
            fragmentation_percent: Current fragmentation percentage
            fragmentation_level: Fragmentation severity level

        Returns:
            Tuple of (recommended_action, estimated_benefit)
        """
        if fragmentation_level == FragmentationLevel.CRITICAL:
            return (
                "immediate_full_vacuum",
                f"Critical fragmentation ({fragmentation_percent:.1f}%) - immediate full vacuum recommended for significant performance improvement"
            )
        elif fragmentation_level == FragmentationLevel.HIGH:
            return (
                "schedule_full_vacuum",
                f"High fragmentation ({fragmentation_percent:.1f}%) - schedule full vacuum during maintenance window"
            )
        elif fragmentation_level == FragmentationLevel.MODERATE:
            return (
                "incremental_vacuum",
                f"Moderate fragmentation ({fragmentation_percent:.1f}%) - incremental vacuum recommended"
            )
        else:
            return (
                "monitor",
                f"Low fragmentation ({fragmentation_percent:.1f}%) - continue monitoring"
            )

    def schedule_vacuum(self, db_id: str, vacuum_type: VacuumType,
                       priority: int = 5, scheduled_at: Optional[datetime] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Schedule a vacuum operation.

        Args:
            db_id: Database identifier
            vacuum_type: Type of vacuum operation
            priority: Task priority (1-10, higher = more urgent)
            scheduled_at: When to execute the vacuum
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

                # Verify database exists
                cursor.execute("SELECT db_name FROM databases WHERE db_id = ?", (db_id,))
                db_row = cursor.fetchone()
                if not db_row:
                    raise ValueError(f"Database {db_id} not found")

                db_name = db_row[0]

                # Create vacuum task
                cursor.execute("""
                    INSERT INTO vacuum_tasks (
                        task_id, db_id, vacuum_type, status, priority,
                        scheduled_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, db_id, vacuum_type.value, VacuumStatus.SCHEDULED.value,
                    priority, scheduled_at, json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Scheduled {vacuum_type.value} vacuum for database {db_name}")
                return task_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to schedule vacuum for database {db_id}: {e}")
                raise
            finally:
                conn.close()

    def execute_vacuum_task(self, task_id: str) -> bool:
        """
        Execute a scheduled vacuum task.

        Args:
            task_id: Task identifier

        Returns:
            True if task executed successfully
        """
        if task_id in self._active_vacuums:
            self._logger.warning(f"Vacuum task {task_id} already running")
            return False

        if len(self._active_vacuums) >= self._max_concurrent_vacuums:
            self._logger.warning("Maximum concurrent vacuums reached")
            return False

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get task details
                cursor.execute("""
                    SELECT vt.db_id, vt.vacuum_type, d.db_path, d.db_name
                    FROM vacuum_tasks vt
                    JOIN databases d ON vt.db_id = d.db_id
                    WHERE vt.task_id = ? AND vt.status = ?
                """, (task_id, VacuumStatus.SCHEDULED.value))

                task_row = cursor.fetchone()
                if not task_row:
                    self._logger.warning(f"Task {task_id} not found or not scheduled")
                    return False

                db_id, vacuum_type, db_path, db_name = task_row

                # Get fragmentation before vacuum
                fragmentation_before = self._get_current_fragmentation(db_path)

                # Mark task as running
                start_time = datetime.now(timezone.utc)
                cursor.execute("""
                    UPDATE vacuum_tasks SET
                        status = ?,
                        started_at = ?,
                        fragmentation_before = ?
                    WHERE task_id = ?
                """, (VacuumStatus.RUNNING.value, start_time, fragmentation_before, task_id))

                conn.commit()
                self._active_vacuums.add(task_id)

                # Execute the vacuum
                success = False
                error_details = None
                pages_freed = 0
                size_reduction = 0

                try:
                    if vacuum_type == VacuumType.INCREMENTAL.value:
                        success, pages_freed, size_reduction = self._execute_incremental_vacuum(db_path)
                    elif vacuum_type == VacuumType.FULL.value:
                        success, pages_freed, size_reduction = self._execute_full_vacuum(db_path)
                    elif vacuum_type == VacuumType.AUTO.value:
                        success, pages_freed, size_reduction = self._execute_auto_vacuum(db_path)
                    else:
                        raise ValueError(f"Unknown vacuum type: {vacuum_type}")

                except Exception as e:
                    success = False
                    error_details = str(e)
                    self._logger.error(f"Vacuum task {task_id} failed: {e}")

                # Get fragmentation after vacuum
                fragmentation_after = self._get_current_fragmentation(db_path)

                # Update task completion
                end_time = datetime.now(timezone.utc)
                duration = int((end_time - start_time).total_seconds())

                cursor.execute("""
                    UPDATE vacuum_tasks SET
                        status = ?,
                        completed_at = ?,
                        duration_seconds = ?,
                        pages_freed = ?,
                        size_reduction_bytes = ?,
                        fragmentation_after = ?,
                        error_details = ?
                    WHERE task_id = ?
                """, (
                    VacuumStatus.COMPLETED.value if success else VacuumStatus.FAILED.value,
                    end_time, duration, pages_freed, size_reduction,
                    fragmentation_after, error_details, task_id
                ))

                # Update database record
                if success:
                    cursor.execute("""
                        UPDATE databases SET
                            last_vacuum = ?,
                            fragmentation_percent = ?,
                            updated_at = ?
                        WHERE db_id = ?
                    """, (end_time, fragmentation_after, end_time, db_id))

                conn.commit()
                self._active_vacuums.discard(task_id)

                self._logger.info(f"Vacuum task {task_id} {'completed' if success else 'failed'} for database {db_name}")
                return success

            except Exception as e:
                self._logger.error(f"Failed to execute vacuum task {task_id}: {e}")
                self._active_vacuums.discard(task_id)
                return False
            finally:
                conn.close()

    def _get_current_fragmentation(self, db_path: str) -> float:
        """
        Get current fragmentation percentage for a database.

        Args:
            db_path: Path to the database file

        Returns:
            Fragmentation percentage
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            cursor.execute("PRAGMA freelist_count")
            freelist_count = cursor.fetchone()[0]

            conn.close()

            return (freelist_count / page_count * 100) if page_count > 0 else 0.0

        except Exception as e:
            self._logger.error(f"Failed to get fragmentation for {db_path}: {e}")
            return 0.0

    def _execute_incremental_vacuum(self, db_path: str) -> Tuple[bool, int, int]:
        """
        Execute incremental vacuum operation.

        Args:
            db_path: Path to the database file

        Returns:
            Tuple of (success, pages_freed, size_reduction_bytes)
        """
        try:
            # Get initial size
            initial_size = Path(db_path).stat().st_size

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get initial freelist count
            cursor.execute("PRAGMA freelist_count")
            initial_freelist = cursor.fetchone()[0]

            # Execute incremental vacuum
            cursor.execute("PRAGMA incremental_vacuum")

            # Get final freelist count
            cursor.execute("PRAGMA freelist_count")
            final_freelist = cursor.fetchone()[0]

            conn.close()

            # Calculate results
            pages_freed = initial_freelist - final_freelist
            final_size = Path(db_path).stat().st_size
            size_reduction = initial_size - final_size

            return True, pages_freed, size_reduction

        except Exception as e:
            self._logger.error(f"Failed to execute incremental vacuum on {db_path}: {e}")
            return False, 0, 0

    def _execute_full_vacuum(self, db_path: str) -> Tuple[bool, int, int]:
        """
        Execute full vacuum operation.

        Args:
            db_path: Path to the database file

        Returns:
            Tuple of (success, pages_freed, size_reduction_bytes)
        """
        try:
            # Get initial size and stats
            initial_size = Path(db_path).stat().st_size

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA freelist_count")
            initial_freelist = cursor.fetchone()[0]

            # Execute full vacuum
            cursor.execute("VACUUM")

            cursor.execute("PRAGMA freelist_count")
            final_freelist = cursor.fetchone()[0]

            conn.close()

            # Calculate results
            pages_freed = initial_freelist - final_freelist
            final_size = Path(db_path).stat().st_size
            size_reduction = initial_size - final_size

            return True, pages_freed, size_reduction

        except Exception as e:
            self._logger.error(f"Failed to execute full vacuum on {db_path}: {e}")
            return False, 0, 0

    def _execute_auto_vacuum(self, db_path: str) -> Tuple[bool, int, int]:
        """
        Execute auto vacuum based on current fragmentation.

        Args:
            db_path: Path to the database file

        Returns:
            Tuple of (success, pages_freed, size_reduction_bytes)
        """
        try:
            fragmentation = self._get_current_fragmentation(db_path)

            if fragmentation >= 50.0:
                # High fragmentation - use full vacuum
                return self._execute_full_vacuum(db_path)
            elif fragmentation >= 25.0:
                # Moderate fragmentation - use incremental vacuum
                return self._execute_incremental_vacuum(db_path)
            else:
                # Low fragmentation - no vacuum needed
                return True, 0, 0

        except Exception as e:
            self._logger.error(f"Failed to execute auto vacuum on {db_path}: {e}")
            return False, 0, 0

    def get_vacuum_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get vacuum recommendations for all monitored databases.

        Returns:
            List of vacuum recommendations
        """
        recommendations = []

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get databases that need attention
                cursor.execute("""
                    SELECT db_id, db_name, db_path, fragmentation_percent, last_vacuum
                    FROM databases
                    WHERE fragmentation_percent >= ?
                    ORDER BY fragmentation_percent DESC
                """, (self._auto_vacuum_threshold,))

                rows = cursor.fetchall()

                for row in rows:
                    db_id, db_name, db_path, fragmentation_percent, last_vacuum = row

                    # Determine recommendation
                    fragmentation_level = self._get_fragmentation_level(fragmentation_percent)
                    recommended_action, estimated_benefit = self._generate_vacuum_recommendation(
                        fragmentation_percent, fragmentation_level
                    )

                    # Calculate priority
                    priority = 'high' if fragmentation_percent >= 50 else 'medium' if fragmentation_percent >= 25 else 'low'

                    # Check if vacuum is overdue
                    days_since_vacuum = 999
                    if last_vacuum:
                        last_vacuum_date = datetime.fromisoformat(last_vacuum)
                        days_since_vacuum = (datetime.now(timezone.utc) - last_vacuum_date).days

                    recommendations.append({
                        'db_id': db_id,
                        'db_name': db_name,
                        'db_path': db_path,
                        'fragmentation_percent': fragmentation_percent,
                        'fragmentation_level': fragmentation_level.value,
                        'recommended_action': recommended_action,
                        'estimated_benefit': estimated_benefit,
                        'priority': priority,
                        'days_since_vacuum': days_since_vacuum,
                        'last_vacuum': last_vacuum
                    })

                return recommendations

            except Exception as e:
                self._logger.error(f"Failed to get vacuum recommendations: {e}")
                return []
            finally:
                conn.close()

    def get_database_info(self, db_id: str) -> Optional[DatabaseInfo]:
        """
        Get information about a monitored database.

        Args:
            db_id: Database identifier

        Returns:
            DatabaseInfo object or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT db_id, db_path, db_name, file_size_bytes, page_count,
                           page_size, freelist_count, fragmentation_percent,
                           last_vacuum, last_analyzed, auto_vacuum_mode,
                           journal_mode, metadata_json
                    FROM databases WHERE db_id = ?
                """, (db_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return DatabaseInfo(
                    db_id=row[0],
                    db_path=row[1],
                    db_name=row[2],
                    file_size_bytes=row[3] or 0,
                    page_count=row[4] or 0,
                    page_size=row[5] or 4096,
                    freelist_count=row[6] or 0,
                    fragmentation_percent=row[7] or 0.0,
                    last_vacuum=datetime.fromisoformat(row[8]) if row[8] else None,
                    last_analyzed=datetime.fromisoformat(row[9]) if row[9] else None,
                    auto_vacuum_mode=row[10] or 'UNKNOWN',
                    journal_mode=row[11] or 'UNKNOWN',
                    metadata=json.loads(row[12]) if row[12] else {}
                )

            except Exception as e:
                self._logger.error(f"Failed to get database info for {db_id}: {e}")
                return None
            finally:
                conn.close()

    def cleanup_old_reports(self, retention_days: int = 90) -> int:
        """
        Clean up old fragmentation reports and completed tasks.

        Args:
            retention_days: Number of days to retain reports

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old reports
                cursor.execute("""
                    DELETE FROM fragmentation_reports WHERE analyzed_at < ?
                """, (cutoff_date,))

                deleted_count = cursor.rowcount

                # Delete old completed tasks
                cursor.execute("""
                    DELETE FROM vacuum_tasks
                    WHERE status IN (?, ?) AND completed_at < ?
                """, (VacuumStatus.COMPLETED.value, VacuumStatus.FAILED.value, cutoff_date))

                deleted_count += cursor.rowcount

                conn.commit()
                self._logger.info(f"Cleaned up {deleted_count} old vacuum records")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old reports: {e}")
                return 0
            finally:
                conn.close()
