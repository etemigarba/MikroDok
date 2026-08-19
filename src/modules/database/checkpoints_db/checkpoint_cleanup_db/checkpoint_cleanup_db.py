"""
Module: checkpoint_cleanup_db
Description: Tracks checkpoint retention and cleanup operations, providing comprehensive retention policy management, cleanup scheduling, and storage optimization for checkpoint lifecycle management
Phase: 4
Location: /src/modules/database/checkpoints_db/checkpoint_cleanup_db/
"""

# Standard library imports
import sqlite3
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
from src.modules.logic.checkpoint_management_lg.base_interfaces import RetentionPolicy


class CleanupStatus(Enum):
    """Status of cleanup operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CleanupReason(Enum):
    """Reasons for checkpoint cleanup."""
    RETENTION_POLICY = "retention_policy"
    STORAGE_LIMIT = "storage_limit"
    MANUAL_REQUEST = "manual_request"
    CORRUPTION_DETECTED = "corruption_detected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


@dataclass
class CleanupOperation:
    """Represents a cleanup operation."""
    operation_id: str
    checkpoint_id: str
    cleanup_reason: CleanupReason
    status: CleanupStatus
    scheduled_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: str
    retention_policy: str
    storage_freed_bytes: int
    error_message: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class RetentionRule:
    """Represents a retention rule."""
    rule_id: str
    rule_name: str
    policy_type: RetentionPolicy
    max_count: Optional[int]
    max_age_days: Optional[int]
    max_size_bytes: Optional[int]
    priority: int
    is_active: bool
    applies_to_tags: Set[str]
    applies_to_branches: Set[str]
    created_at: datetime
    created_by: str
    metadata: Dict[str, Any]


class CheckpointCleanupDB:
    """
    Database layer for checkpoint cleanup and retention management.
    
    Provides comprehensive cleanup tracking, retention policy enforcement,
    and storage optimization with support for scheduled cleanup operations
    and detailed audit trails.
    """
    
    def __init__(self, db_path: str = "data/checkpoint_cleanup.db"):
        """
        Initialize checkpoint cleanup database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Initialize database schema
        self._init_database()
        
        self._logger.info(f"CheckpointCleanupDB initialized with database: {self.db_path}")
    
    def _init_database(self) -> None:
        """Initialize database schema with cleanup tables and indexes."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                
                # Create cleanup operations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_operations (
                        operation_id TEXT PRIMARY KEY,
                        checkpoint_id TEXT NOT NULL,
                        cleanup_reason TEXT NOT NULL,
                        status TEXT NOT NULL,
                        scheduled_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        created_by TEXT NOT NULL,
                        retention_policy TEXT NOT NULL,
                        storage_freed_bytes INTEGER DEFAULT 0,
                        error_message TEXT,
                        metadata_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create retention rules table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retention_rules (
                        rule_id TEXT PRIMARY KEY,
                        rule_name TEXT NOT NULL UNIQUE,
                        policy_type TEXT NOT NULL,
                        max_count INTEGER,
                        max_age_days INTEGER,
                        max_size_bytes INTEGER,
                        priority INTEGER NOT NULL DEFAULT 1,
                        is_active BOOLEAN DEFAULT TRUE,
                        applies_to_tags_json TEXT,
                        applies_to_branches_json TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        metadata_json TEXT,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create cleanup schedule table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_schedule (
                        schedule_id TEXT PRIMARY KEY,
                        rule_id TEXT NOT NULL,
                        schedule_type TEXT NOT NULL,
                        cron_expression TEXT,
                        interval_minutes INTEGER,
                        next_run_at TEXT NOT NULL,
                        last_run_at TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        metadata_json TEXT,
                        FOREIGN KEY (rule_id) REFERENCES retention_rules(rule_id)
                    )
                """)
                
                # Create cleanup audit table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_audit (
                        audit_id TEXT PRIMARY KEY,
                        operation_id TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        old_status TEXT,
                        new_status TEXT,
                        performed_at TEXT NOT NULL,
                        performed_by TEXT NOT NULL,
                        details_json TEXT,
                        FOREIGN KEY (operation_id) REFERENCES cleanup_operations(operation_id)
                    )
                """)
                
                # Create storage statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS storage_statistics (
                        stat_id TEXT PRIMARY KEY,
                        measurement_date TEXT NOT NULL,
                        total_checkpoints INTEGER NOT NULL,
                        total_size_bytes INTEGER NOT NULL,
                        cleaned_checkpoints INTEGER DEFAULT 0,
                        freed_size_bytes INTEGER DEFAULT 0,
                        storage_tier TEXT DEFAULT 'local',
                        metadata_json TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create performance-optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cleanup_status_scheduled 
                    ON cleanup_operations(status, scheduled_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cleanup_checkpoint 
                    ON cleanup_operations(checkpoint_id, status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cleanup_reason 
                    ON cleanup_operations(cleanup_reason, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retention_active_priority 
                    ON retention_rules(is_active, priority ASC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_schedule_next_run 
                    ON cleanup_schedule(is_active, next_run_at ASC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_operation 
                    ON cleanup_audit(operation_id, performed_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_storage_date 
                    ON storage_statistics(measurement_date DESC)
                """)
                
                conn.commit()
                
                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'cleanup_operations', 'retention_rules', 'cleanup_schedule',
                    'cleanup_audit', 'storage_statistics'
                ]
                
                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")
                
                self._logger.info("Checkpoint cleanup database initialized successfully")
                
            except Exception as e:
                self._logger.error(f"Failed to initialize checkpoint cleanup database: {e}")
                raise
            finally:
                conn.close()

    def schedule_cleanup(self, operation: CleanupOperation) -> bool:
        """
        Schedule a cleanup operation.

        Args:
            operation: CleanupOperation to schedule

        Returns:
            True if scheduling successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Convert operation to database format
                    data = (
                        operation.operation_id,
                        operation.checkpoint_id,
                        operation.cleanup_reason.value,
                        operation.status.value,
                        operation.scheduled_at.isoformat(),
                        operation.started_at.isoformat() if operation.started_at else None,
                        operation.completed_at.isoformat() if operation.completed_at else None,
                        operation.created_by,
                        operation.retention_policy,
                        operation.storage_freed_bytes,
                        operation.error_message,
                        json.dumps(operation.metadata) if operation.metadata else None,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat()
                    )

                    # Insert cleanup operation
                    cursor.execute("""
                        INSERT INTO cleanup_operations (
                            operation_id, checkpoint_id, cleanup_reason, status, scheduled_at,
                            started_at, completed_at, created_by, retention_policy,
                            storage_freed_bytes, error_message, metadata_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, data)

                    # Create audit entry
                    self._create_audit_entry(cursor, operation.operation_id, operation.checkpoint_id,
                                           "scheduled", None, operation.status.value, operation.created_by)

                    conn.commit()

                    self._logger.info(f"Cleanup operation scheduled: {operation.operation_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to schedule cleanup operation {operation.operation_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during cleanup scheduling: {e}")
            return False

    def update_cleanup_status(self, operation_id: str, status: CleanupStatus,
                             error_message: Optional[str] = None,
                             storage_freed: int = 0) -> bool:
        """
        Update cleanup operation status.

        Args:
            operation_id: Cleanup operation ID
            status: New status
            error_message: Optional error message
            storage_freed: Amount of storage freed in bytes

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get current status for audit
                    cursor.execute("""
                        SELECT status FROM cleanup_operations WHERE operation_id = ?
                    """, (operation_id,))

                    row = cursor.fetchone()
                    if not row:
                        self._logger.warning(f"Cleanup operation not found: {operation_id}")
                        return False

                    old_status = row[0]

                    # Update operation
                    update_fields = ["status = ?", "updated_at = ?"]
                    update_values = [status.value, datetime.now(timezone.utc).isoformat()]

                    if status == CleanupStatus.IN_PROGRESS:
                        update_fields.append("started_at = ?")
                        update_values.append(datetime.now(timezone.utc).isoformat())
                    elif status in [CleanupStatus.COMPLETED, CleanupStatus.FAILED, CleanupStatus.CANCELLED]:
                        update_fields.append("completed_at = ?")
                        update_values.append(datetime.now(timezone.utc).isoformat())

                    if error_message:
                        update_fields.append("error_message = ?")
                        update_values.append(error_message)

                    if storage_freed > 0:
                        update_fields.append("storage_freed_bytes = ?")
                        update_values.append(storage_freed)

                    update_values.append(operation_id)

                    cursor.execute(f"""
                        UPDATE cleanup_operations
                        SET {', '.join(update_fields)}
                        WHERE operation_id = ?
                    """, update_values)

                    # Create audit entry
                    self._create_audit_entry(cursor, operation_id, "", "status_update",
                                           old_status, status.value, "system")

                    conn.commit()

                    self._logger.info(f"Cleanup operation status updated: {operation_id} -> {status.value}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update cleanup operation {operation_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during status update: {e}")
            return False

    def create_retention_rule(self, rule: RetentionRule) -> bool:
        """
        Create a new retention rule.

        Args:
            rule: RetentionRule to create

        Returns:
            True if creation successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Convert rule to database format
                    data = (
                        rule.rule_id,
                        rule.rule_name,
                        rule.policy_type.value,
                        rule.max_count,
                        rule.max_age_days,
                        rule.max_size_bytes,
                        rule.priority,
                        rule.is_active,
                        json.dumps(list(rule.applies_to_tags)) if rule.applies_to_tags else None,
                        json.dumps(list(rule.applies_to_branches)) if rule.applies_to_branches else None,
                        rule.created_at.isoformat(),
                        rule.created_by,
                        json.dumps(rule.metadata) if rule.metadata else None,
                        datetime.now(timezone.utc).isoformat()
                    )

                    # Insert retention rule
                    cursor.execute("""
                        INSERT INTO retention_rules (
                            rule_id, rule_name, policy_type, max_count, max_age_days, max_size_bytes,
                            priority, is_active, applies_to_tags_json, applies_to_branches_json,
                            created_at, created_by, metadata_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, data)

                    conn.commit()

                    self._logger.info(f"Retention rule created: {rule.rule_name}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create retention rule {rule.rule_name}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during rule creation: {e}")
            return False

    def get_pending_cleanups(self, limit: int = 100) -> List[CleanupOperation]:
        """
        Get pending cleanup operations.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of pending cleanup operations
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get pending operations
                    cursor.execute("""
                        SELECT * FROM cleanup_operations
                        WHERE status = ? AND scheduled_at <= ?
                        ORDER BY scheduled_at ASC
                        LIMIT ?
                    """, (CleanupStatus.PENDING.value, datetime.now(timezone.utc).isoformat(), limit))

                    rows = cursor.fetchall()

                    # Convert to operation objects
                    operations = []
                    for row in rows:
                        operation = self._db_format_to_operation(row)
                        if operation:
                            operations.append(operation)

                    self._logger.debug(f"Retrieved {len(operations)} pending cleanup operations")
                    return operations

                except Exception as e:
                    self._logger.error(f"Failed to get pending cleanups: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during pending cleanups retrieval: {e}")
            return []

    def get_cleanup_history(self, checkpoint_id: Optional[str] = None,
                           limit: int = 100) -> List[CleanupOperation]:
        """
        Get cleanup operation history.

        Args:
            checkpoint_id: Filter by checkpoint ID
            limit: Maximum number of operations to return

        Returns:
            List of cleanup operations
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Build query
                    query = "SELECT * FROM cleanup_operations WHERE 1=1"
                    params = []

                    if checkpoint_id:
                        query += " AND checkpoint_id = ?"
                        params.append(checkpoint_id)

                    query += " ORDER BY created_at DESC LIMIT ?"
                    params.append(limit)

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Convert to operation objects
                    operations = []
                    for row in rows:
                        operation = self._db_format_to_operation(row)
                        if operation:
                            operations.append(operation)

                    self._logger.debug(f"Retrieved {len(operations)} cleanup operations")
                    return operations

                except Exception as e:
                    self._logger.error(f"Failed to get cleanup history: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during history retrieval: {e}")
            return []

    def get_active_retention_rules(self) -> List[RetentionRule]:
        """
        Get all active retention rules.

        Returns:
            List of active retention rules
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get active rules
                    cursor.execute("""
                        SELECT * FROM retention_rules
                        WHERE is_active = TRUE
                        ORDER BY priority ASC, created_at ASC
                    """)

                    rows = cursor.fetchall()

                    # Convert to rule objects
                    rules = []
                    for row in rows:
                        rule = self._db_format_to_rule(row)
                        if rule:
                            rules.append(rule)

                    self._logger.debug(f"Retrieved {len(rules)} active retention rules")
                    return rules

                except Exception as e:
                    self._logger.error(f"Failed to get active retention rules: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during rules retrieval: {e}")
            return []

    def record_storage_statistics(self, total_checkpoints: int, total_size_bytes: int,
                                 cleaned_checkpoints: int = 0, freed_size_bytes: int = 0,
                                 storage_tier: str = "local") -> bool:
        """
        Record storage statistics.

        Args:
            total_checkpoints: Total number of checkpoints
            total_size_bytes: Total storage size in bytes
            cleaned_checkpoints: Number of cleaned checkpoints
            freed_size_bytes: Amount of storage freed in bytes
            storage_tier: Storage tier identifier

        Returns:
            True if recording successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Create statistics record
                    stat_id = f"stat_{datetime.now().timestamp()}"
                    cursor.execute("""
                        INSERT INTO storage_statistics (
                            stat_id, measurement_date, total_checkpoints, total_size_bytes,
                            cleaned_checkpoints, freed_size_bytes, storage_tier
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        stat_id,
                        datetime.now(timezone.utc).date().isoformat(),
                        total_checkpoints,
                        total_size_bytes,
                        cleaned_checkpoints,
                        freed_size_bytes,
                        storage_tier
                    ))

                    conn.commit()

                    self._logger.debug(f"Storage statistics recorded: {total_checkpoints} checkpoints, {total_size_bytes} bytes")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to record storage statistics: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during statistics recording: {e}")
            return False

    def get_cleanup_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cleanup statistics.

        Returns:
            Dictionary with various statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    stats = {}

                    # Total operations count
                    cursor.execute("SELECT COUNT(*) FROM cleanup_operations")
                    stats['total_operations'] = cursor.fetchone()[0]

                    # Count by status
                    cursor.execute("""
                        SELECT status, COUNT(*) FROM cleanup_operations
                        GROUP BY status
                    """)
                    stats['by_status'] = dict(cursor.fetchall())

                    # Count by reason
                    cursor.execute("""
                        SELECT cleanup_reason, COUNT(*) FROM cleanup_operations
                        GROUP BY cleanup_reason
                    """)
                    stats['by_reason'] = dict(cursor.fetchall())

                    # Storage freed
                    cursor.execute("""
                        SELECT SUM(storage_freed_bytes) FROM cleanup_operations
                        WHERE status = ?
                    """, (CleanupStatus.COMPLETED.value,))
                    stats['total_storage_freed'] = cursor.fetchone()[0] or 0

                    # Active retention rules
                    cursor.execute("SELECT COUNT(*) FROM retention_rules WHERE is_active = TRUE")
                    stats['active_rules'] = cursor.fetchone()[0]

                    # Recent activity (last 7 days)
                    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                    cursor.execute("""
                        SELECT COUNT(*) FROM cleanup_operations
                        WHERE created_at > ?
                    """, (week_ago,))
                    stats['recent_operations'] = cursor.fetchone()[0]

                    self._logger.debug("Retrieved cleanup statistics")
                    return stats

                except Exception as e:
                    self._logger.error(f"Failed to get cleanup statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during statistics retrieval: {e}")
            return {}

    def _create_audit_entry(self, cursor, operation_id: str, checkpoint_id: str,
                           action: str, old_status: Optional[str], new_status: str,
                           performed_by: str) -> None:
        """Create an audit entry for cleanup operations."""
        audit_id = f"audit_{datetime.now().timestamp()}"
        cursor.execute("""
            INSERT INTO cleanup_audit (
                audit_id, operation_id, checkpoint_id, action, old_status, new_status,
                performed_at, performed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id, operation_id, checkpoint_id, action, old_status, new_status,
            datetime.now(timezone.utc).isoformat(), performed_by
        ))

    def _db_format_to_operation(self, row: Tuple) -> Optional[CleanupOperation]:
        """Convert database row to CleanupOperation object."""
        try:
            if not row:
                return None

            # Parse JSON fields safely
            metadata = json.loads(row[11]) if row[11] else {}

            # Create operation object
            operation = CleanupOperation(
                operation_id=row[0],
                checkpoint_id=row[1],
                cleanup_reason=CleanupReason(row[2]),
                status=CleanupStatus(row[3]),
                scheduled_at=datetime.fromisoformat(row[4]),
                started_at=datetime.fromisoformat(row[5]) if row[5] else None,
                completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                created_by=row[7],
                retention_policy=row[8],
                storage_freed_bytes=row[9],
                error_message=row[10],
                metadata=metadata
            )

            return operation

        except Exception as e:
            self._logger.error(f"Failed to convert database row to operation: {e}")
            return None

    def _db_format_to_rule(self, row: Tuple) -> Optional[RetentionRule]:
        """Convert database row to RetentionRule object."""
        try:
            if not row:
                return None

            # Parse JSON fields safely
            applies_to_tags = set(json.loads(row[8])) if row[8] else set()
            applies_to_branches = set(json.loads(row[9])) if row[9] else set()
            metadata = json.loads(row[12]) if row[12] else {}

            # Create rule object
            rule = RetentionRule(
                rule_id=row[0],
                rule_name=row[1],
                policy_type=RetentionPolicy(row[2]),
                max_count=row[3],
                max_age_days=row[4],
                max_size_bytes=row[5],
                priority=row[6],
                is_active=bool(row[7]),
                applies_to_tags=applies_to_tags,
                applies_to_branches=applies_to_branches,
                created_at=datetime.fromisoformat(row[10]),
                created_by=row[11],
                metadata=metadata
            )

            return rule

        except Exception as e:
            self._logger.error(f"Failed to convert database row to rule: {e}")
            return None

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("CheckpointCleanupDB closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
