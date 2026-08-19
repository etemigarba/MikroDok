"""
Module: transaction_coordinator_db
Description: Coordinates complex transactions across multiple tables with ACID compliance and deadlock prevention
Phase: 4
Location: /src/modules/database/database_core_db/transaction_coordinator_db/
"""

# Standard library imports
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, ContextManager, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class TransactionState(Enum):
    """Transaction state tracking."""
    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class IsolationLevel(Enum):
    """Transaction isolation levels."""
    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
    EXCLUSIVE = "EXCLUSIVE"


class LockType(Enum):
    """Database lock types."""
    SHARED = "shared"
    RESERVED = "reserved"
    PENDING = "pending"
    EXCLUSIVE = "exclusive"


@dataclass
class TransactionInfo:
    """Transaction information tracking."""
    transaction_id: str
    thread_id: int
    isolation_level: IsolationLevel
    state: TransactionState
    started_at: datetime
    completed_at: Optional[datetime]
    operations_count: int
    tables_accessed: List[str]
    savepoints: List[str]
    error_message: Optional[str]


@dataclass
class SavepointInfo:
    """Savepoint information tracking."""
    savepoint_id: str
    transaction_id: str
    name: str
    created_at: datetime
    operations_since_savepoint: int


class TransactionCoordinatorDB:
    """
    Transaction coordinator for complex multi-table operations.
    
    Coordinates complex transactions across multiple tables with ACID compliance
    and deadlock prevention. Provides transaction lifecycle management,
    savepoint support, and comprehensive transaction monitoring.
    """
    
    def __init__(self, db_path: Optional[str] = None, deadlock_timeout: float = 30.0):
        """
        Initialize the transaction coordinator.
        
        Args:
            db_path: Path to the database file
            deadlock_timeout: Timeout for deadlock detection (seconds)
        """
        if db_path is None:
            # Default to core database directory
            data_dir = Path.home() / ".mikrodok" / "data" / "core"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "mikrodok_core.db")
        
        self._db_path = db_path
        self._deadlock_timeout = deadlock_timeout
        
        # Thread safety
        self._lock = threading.RLock()
        self._transaction_locks: Dict[str, threading.Lock] = {}
        
        # Transaction tracking
        self._active_transactions: Dict[str, TransactionInfo] = {}
        self._transaction_connections: Dict[str, sqlite3.Connection] = {}
        self._savepoints: Dict[str, SavepointInfo] = {}
        
        # Thread-local storage for current transaction
        self._thread_local = threading.local()
        
        # Statistics
        self._total_transactions = 0
        self._successful_transactions = 0
        self._failed_transactions = 0
        self._deadlock_count = 0
        
        # Logger
        self._logger = get_logger(__name__)
        
        # Initialize transaction tracking
        self._initialize_transaction_tracking()
        
        self._logger.info(f"TransactionCoordinatorDB initialized with database: {self._db_path}")
    
    def _initialize_transaction_tracking(self) -> None:
        """Initialize transaction tracking tables."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Create transaction log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transaction_log (
                    transaction_id TEXT PRIMARY KEY,
                    thread_id INTEGER NOT NULL,
                    isolation_level TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    operations_count INTEGER DEFAULT 0,
                    tables_accessed TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create savepoint log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS savepoint_log (
                    savepoint_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    operations_since_savepoint INTEGER DEFAULT 0,
                    FOREIGN KEY (transaction_id) REFERENCES transaction_log(transaction_id)
                )
            """)
            
            # Create deadlock detection table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deadlock_log (
                    deadlock_id TEXT PRIMARY KEY,
                    transaction_ids TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    resolution_strategy TEXT NOT NULL,
                    resolved_at TEXT,
                    victim_transaction_id TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            
            self._logger.info("Transaction tracking tables initialized")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize transaction tracking: {e}")
            raise
    
    @contextmanager
    def begin_transaction(self, isolation_level: IsolationLevel = IsolationLevel.IMMEDIATE,
                         timeout: Optional[float] = None) -> ContextManager[str]:
        """
        Begin a new transaction with specified isolation level.
        
        Args:
            isolation_level: Transaction isolation level
            timeout: Transaction timeout (uses deadlock_timeout if None)
            
        Yields:
            Transaction ID
            
        Raises:
            TimeoutError: If transaction cannot be started within timeout
        """
        transaction_id = str(uuid.uuid4())
        timeout = timeout or self._deadlock_timeout
        start_time = time.time()
        
        try:
            # Create connection for this transaction
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            
            # Set busy timeout
            conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
            
            # Begin transaction with specified isolation level
            conn.execute(f"BEGIN {isolation_level.value}")
            
            # Create transaction info
            transaction_info = TransactionInfo(
                transaction_id=transaction_id,
                thread_id=threading.get_ident(),
                isolation_level=isolation_level,
                state=TransactionState.ACTIVE,
                started_at=datetime.now(timezone.utc),
                completed_at=None,
                operations_count=0,
                tables_accessed=[],
                savepoints=[],
                error_message=None
            )
            
            with self._lock:
                self._active_transactions[transaction_id] = transaction_info
                self._transaction_connections[transaction_id] = conn
                self._transaction_locks[transaction_id] = threading.Lock()
                self._total_transactions += 1
            
            # Store in thread-local storage
            self._thread_local.current_transaction = transaction_id
            
            # Log transaction start
            self._log_transaction_event(transaction_info)
            
            self._logger.debug(f"Started transaction: {transaction_id}")
            
            yield transaction_id
            
            # Commit transaction if no exception occurred
            self._commit_transaction(transaction_id)
            
        except Exception as e:
            # Rollback transaction on any exception
            self._rollback_transaction(transaction_id, str(e))
            raise
            
        finally:
            # Cleanup transaction resources
            self._cleanup_transaction(transaction_id)
    
    def _commit_transaction(self, transaction_id: str) -> None:
        """Commit a transaction."""
        try:
            with self._lock:
                transaction_info = self._active_transactions.get(transaction_id)
                conn = self._transaction_connections.get(transaction_id)
                
                if not transaction_info or not conn:
                    raise ValueError(f"Transaction {transaction_id} not found")
                
                if transaction_info.state != TransactionState.ACTIVE:
                    raise ValueError(f"Transaction {transaction_id} not in active state")
                
                # Commit the transaction
                conn.commit()
                
                # Update transaction info
                transaction_info.state = TransactionState.COMMITTED
                transaction_info.completed_at = datetime.now(timezone.utc)
                
                self._successful_transactions += 1
                
                # Log transaction completion
                self._log_transaction_event(transaction_info)
                
                self._logger.debug(f"Committed transaction: {transaction_id}")
                
        except Exception as e:
            self._logger.error(f"Failed to commit transaction {transaction_id}: {e}")
            self._rollback_transaction(transaction_id, str(e))
            raise
    
    def _rollback_transaction(self, transaction_id: str, error_message: str = "") -> None:
        """Rollback a transaction."""
        try:
            with self._lock:
                transaction_info = self._active_transactions.get(transaction_id)
                conn = self._transaction_connections.get(transaction_id)
                
                if transaction_info:
                    transaction_info.state = TransactionState.ROLLED_BACK
                    transaction_info.completed_at = datetime.now(timezone.utc)
                    transaction_info.error_message = error_message
                    
                    self._failed_transactions += 1
                    
                    # Log transaction rollback
                    self._log_transaction_event(transaction_info)
                
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass  # Connection might already be closed
                
                self._logger.debug(f"Rolled back transaction: {transaction_id}")
                
        except Exception as e:
            self._logger.error(f"Error during rollback of transaction {transaction_id}: {e}")
    
    def _cleanup_transaction(self, transaction_id: str) -> None:
        """Cleanup transaction resources."""
        try:
            with self._lock:
                # Close connection
                conn = self._transaction_connections.pop(transaction_id, None)
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
                
                # Remove from active transactions
                self._active_transactions.pop(transaction_id, None)
                
                # Remove transaction lock
                self._transaction_locks.pop(transaction_id, None)
                
                # Clear savepoints for this transaction
                savepoints_to_remove = [sp_id for sp_id, sp_info in self._savepoints.items() 
                                      if sp_info.transaction_id == transaction_id]
                for sp_id in savepoints_to_remove:
                    self._savepoints.pop(sp_id, None)
            
            # Clear thread-local storage
            if hasattr(self._thread_local, 'current_transaction'):
                if self._thread_local.current_transaction == transaction_id:
                    self._thread_local.current_transaction = None
                    
        except Exception as e:
            self._logger.error(f"Error cleaning up transaction {transaction_id}: {e}")

    def execute_in_transaction(self, transaction_id: str, query: str,
                              params: Optional[Tuple] = None, table_name: Optional[str] = None) -> List[sqlite3.Row]:
        """
        Execute a query within a transaction.

        Args:
            transaction_id: Transaction ID
            query: SQL query to execute
            params: Query parameters
            table_name: Table name for tracking (optional)

        Returns:
            Query results

        Raises:
            ValueError: If transaction not found or not active
        """
        try:
            with self._lock:
                transaction_info = self._active_transactions.get(transaction_id)
                conn = self._transaction_connections.get(transaction_id)

                if not transaction_info or not conn:
                    raise ValueError(f"Transaction {transaction_id} not found")

                if transaction_info.state != TransactionState.ACTIVE:
                    raise ValueError(f"Transaction {transaction_id} not in active state")

                # Get transaction lock to prevent concurrent access
                transaction_lock = self._transaction_locks.get(transaction_id)
                if not transaction_lock:
                    raise ValueError(f"Transaction lock not found for {transaction_id}")

            with transaction_lock:
                cursor = conn.cursor()

                # Execute query
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                # Update transaction info
                with self._lock:
                    transaction_info.operations_count += 1
                    if table_name and table_name not in transaction_info.tables_accessed:
                        transaction_info.tables_accessed.append(table_name)

                # Return results
                return cursor.fetchall()

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                self._handle_deadlock(transaction_id, str(e))
            raise
        except Exception as e:
            self._logger.error(f"Error executing query in transaction {transaction_id}: {e}")
            raise

    def create_savepoint(self, transaction_id: str, savepoint_name: str) -> str:
        """
        Create a savepoint within a transaction.

        Args:
            transaction_id: Transaction ID
            savepoint_name: Name for the savepoint

        Returns:
            Savepoint ID

        Raises:
            ValueError: If transaction not found or not active
        """
        try:
            with self._lock:
                transaction_info = self._active_transactions.get(transaction_id)
                conn = self._transaction_connections.get(transaction_id)

                if not transaction_info or not conn:
                    raise ValueError(f"Transaction {transaction_id} not found")

                if transaction_info.state != TransactionState.ACTIVE:
                    raise ValueError(f"Transaction {transaction_id} not in active state")

                # Generate savepoint ID
                savepoint_id = f"sp_{uuid.uuid4().hex[:8]}"

                # Create savepoint
                conn.execute(f"SAVEPOINT {savepoint_id}")

                # Create savepoint info
                savepoint_info = SavepointInfo(
                    savepoint_id=savepoint_id,
                    transaction_id=transaction_id,
                    name=savepoint_name,
                    created_at=datetime.now(timezone.utc),
                    operations_since_savepoint=0
                )

                self._savepoints[savepoint_id] = savepoint_info
                transaction_info.savepoints.append(savepoint_id)

                # Log savepoint creation
                self._log_savepoint_event(savepoint_info)

                self._logger.debug(f"Created savepoint: {savepoint_id} in transaction {transaction_id}")
                return savepoint_id

        except Exception as e:
            self._logger.error(f"Failed to create savepoint in transaction {transaction_id}: {e}")
            raise

    def rollback_to_savepoint(self, transaction_id: str, savepoint_id: str) -> None:
        """
        Rollback to a specific savepoint.

        Args:
            transaction_id: Transaction ID
            savepoint_id: Savepoint ID to rollback to

        Raises:
            ValueError: If transaction or savepoint not found
        """
        try:
            with self._lock:
                transaction_info = self._active_transactions.get(transaction_id)
                conn = self._transaction_connections.get(transaction_id)
                savepoint_info = self._savepoints.get(savepoint_id)

                if not transaction_info or not conn:
                    raise ValueError(f"Transaction {transaction_id} not found")

                if not savepoint_info or savepoint_info.transaction_id != transaction_id:
                    raise ValueError(f"Savepoint {savepoint_id} not found in transaction {transaction_id}")

                # Rollback to savepoint
                conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_id}")

                # Remove savepoints created after this one
                savepoints_to_remove = []
                for sp_id, sp_info in self._savepoints.items():
                    if (sp_info.transaction_id == transaction_id and
                        sp_info.created_at > savepoint_info.created_at):
                        savepoints_to_remove.append(sp_id)

                for sp_id in savepoints_to_remove:
                    self._savepoints.pop(sp_id, None)
                    if sp_id in transaction_info.savepoints:
                        transaction_info.savepoints.remove(sp_id)

                self._logger.debug(f"Rolled back to savepoint: {savepoint_id} in transaction {transaction_id}")

        except Exception as e:
            self._logger.error(f"Failed to rollback to savepoint {savepoint_id}: {e}")
            raise

    def release_savepoint(self, transaction_id: str, savepoint_id: str) -> None:
        """
        Release a savepoint (commit changes up to that point).

        Args:
            transaction_id: Transaction ID
            savepoint_id: Savepoint ID to release

        Raises:
            ValueError: If transaction or savepoint not found
        """
        try:
            with self._lock:
                transaction_info = self._active_transactions.get(transaction_id)
                conn = self._transaction_connections.get(transaction_id)
                savepoint_info = self._savepoints.get(savepoint_id)

                if not transaction_info or not conn:
                    raise ValueError(f"Transaction {transaction_id} not found")

                if not savepoint_info or savepoint_info.transaction_id != transaction_id:
                    raise ValueError(f"Savepoint {savepoint_id} not found in transaction {transaction_id}")

                # Release savepoint
                conn.execute(f"RELEASE SAVEPOINT {savepoint_id}")

                # Remove savepoint from tracking
                self._savepoints.pop(savepoint_id, None)
                if savepoint_id in transaction_info.savepoints:
                    transaction_info.savepoints.remove(savepoint_id)

                self._logger.debug(f"Released savepoint: {savepoint_id} in transaction {transaction_id}")

        except Exception as e:
            self._logger.error(f"Failed to release savepoint {savepoint_id}: {e}")
            raise

    def _handle_deadlock(self, transaction_id: str, error_message: str) -> None:
        """Handle deadlock detection and resolution."""
        try:
            self._deadlock_count += 1

            # Log deadlock
            deadlock_id = str(uuid.uuid4())
            self._log_deadlock_event(deadlock_id, [transaction_id], error_message)

            # For now, just raise the error - more sophisticated deadlock resolution
            # could be implemented here (e.g., choosing victim transaction)
            self._logger.warning(f"Deadlock detected in transaction {transaction_id}: {error_message}")

        except Exception as e:
            self._logger.error(f"Error handling deadlock: {e}")

    def _log_transaction_event(self, transaction_info: TransactionInfo) -> None:
        """Log transaction event to database."""
        try:
            # Use a separate connection for logging to avoid conflicts
            log_conn = sqlite3.connect(self._db_path)
            cursor = log_conn.cursor()

            now = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO transaction_log (
                    transaction_id, thread_id, isolation_level, state, started_at,
                    completed_at, operations_count, tables_accessed, error_message,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction_info.transaction_id,
                transaction_info.thread_id,
                transaction_info.isolation_level.value,
                transaction_info.state.value,
                transaction_info.started_at.isoformat(),
                transaction_info.completed_at.isoformat() if transaction_info.completed_at else None,
                transaction_info.operations_count,
                ','.join(transaction_info.tables_accessed),
                transaction_info.error_message,
                now, now
            ))

            log_conn.commit()
            log_conn.close()

        except Exception as e:
            self._logger.warning(f"Failed to log transaction event: {e}")

    def _log_savepoint_event(self, savepoint_info: SavepointInfo) -> None:
        """Log savepoint event to database."""
        try:
            log_conn = sqlite3.connect(self._db_path)
            cursor = log_conn.cursor()

            cursor.execute("""
                INSERT INTO savepoint_log (
                    savepoint_id, transaction_id, name, created_at, operations_since_savepoint
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                savepoint_info.savepoint_id,
                savepoint_info.transaction_id,
                savepoint_info.name,
                savepoint_info.created_at.isoformat(),
                savepoint_info.operations_since_savepoint
            ))

            log_conn.commit()
            log_conn.close()

        except Exception as e:
            self._logger.warning(f"Failed to log savepoint event: {e}")

    def _log_deadlock_event(self, deadlock_id: str, transaction_ids: List[str], error_message: str) -> None:
        """Log deadlock event to database."""
        try:
            log_conn = sqlite3.connect(self._db_path)
            cursor = log_conn.cursor()

            cursor.execute("""
                INSERT INTO deadlock_log (
                    deadlock_id, transaction_ids, detected_at, resolution_strategy
                ) VALUES (?, ?, ?, ?)
            """, (
                deadlock_id,
                ','.join(transaction_ids),
                datetime.now(timezone.utc).isoformat(),
                "rollback_victim"
            ))

            log_conn.commit()
            log_conn.close()

        except Exception as e:
            self._logger.warning(f"Failed to log deadlock event: {e}")

    def get_active_transactions(self) -> List[TransactionInfo]:
        """
        Get list of currently active transactions.

        Returns:
            List of active transaction info objects
        """
        with self._lock:
            return [info for info in self._active_transactions.values()
                   if info.state == TransactionState.ACTIVE]

    def get_transaction_stats(self) -> Dict[str, Any]:
        """
        Get transaction coordinator statistics.

        Returns:
            Dictionary with transaction statistics
        """
        with self._lock:
            active_count = len([info for info in self._active_transactions.values()
                              if info.state == TransactionState.ACTIVE])

            return {
                'total_transactions': self._total_transactions,
                'successful_transactions': self._successful_transactions,
                'failed_transactions': self._failed_transactions,
                'active_transactions': active_count,
                'deadlock_count': self._deadlock_count,
                'total_savepoints': len(self._savepoints),
                'database_path': self._db_path
            }

    def cleanup_completed_transactions(self, older_than_hours: int = 24) -> int:
        """
        Cleanup completed transaction records older than specified hours.

        Args:
            older_than_hours: Remove records older than this many hours

        Returns:
            Number of records cleaned up
        """
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (older_than_hours * 3600)

            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Clean up transaction log
            cursor.execute("""
                DELETE FROM transaction_log
                WHERE state IN ('committed', 'rolled_back', 'failed')
                AND datetime(completed_at) < datetime(?, 'unixepoch')
            """, (cutoff_time,))

            transaction_count = cursor.rowcount

            # Clean up savepoint log
            cursor.execute("""
                DELETE FROM savepoint_log
                WHERE transaction_id NOT IN (SELECT transaction_id FROM transaction_log)
            """)

            savepoint_count = cursor.rowcount

            # Clean up deadlock log
            cursor.execute("""
                DELETE FROM deadlock_log
                WHERE datetime(detected_at) < datetime(?, 'unixepoch')
            """, (cutoff_time,))

            deadlock_count = cursor.rowcount

            conn.commit()
            conn.close()

            total_cleaned = transaction_count + savepoint_count + deadlock_count
            self._logger.info(f"Cleaned up {total_cleaned} transaction records")

            return total_cleaned

        except Exception as e:
            self._logger.error(f"Failed to cleanup transaction records: {e}")
            return 0
