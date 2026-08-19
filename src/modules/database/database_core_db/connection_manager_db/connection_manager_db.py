"""
Module: connection_manager_db
Description: Manages SQLite database connections with WAL mode, connection pooling, and thread-safe access patterns
Phase: 4
Location: /src/modules/database/database_core_db/connection_manager_db/
"""

# Standard library imports
import sqlite3
import threading
import time
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple, Any, Union, ContextManager
from datetime import datetime, timezone

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ConnectionType(Enum):
    """Database connection types."""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    EXCLUSIVE = "exclusive"


class ConnectionState(Enum):
    """Connection state tracking."""
    IDLE = "idle"
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """Connection information tracking."""
    connection_id: str
    connection_type: ConnectionType
    state: ConnectionState
    created_at: datetime
    last_used_at: datetime
    thread_id: int
    query_count: int
    error_count: int
    database_path: str


class ConnectionManagerDB:
    """
    Database connection manager with pooling and thread-safe access.
    
    Manages SQLite database connections with WAL mode, connection pooling,
    and thread-safe access patterns. Provides connection lifecycle management,
    automatic cleanup, and performance optimization for concurrent access.
    """
    
    def __init__(self, 
                 db_path: Optional[str] = None,
                 max_read_connections: int = 5,
                 max_write_connections: int = 1,
                 connection_timeout: float = 30.0,
                 idle_timeout: float = 300.0):
        """
        Initialize the connection manager.
        
        Args:
            db_path: Path to the database file
            max_read_connections: Maximum number of read connections
            max_write_connections: Maximum number of write connections
            connection_timeout: Timeout for acquiring connections (seconds)
            idle_timeout: Timeout for idle connections (seconds)
        """
        if db_path is None:
            # Default to core database directory
            data_dir = Path.home() / ".mikrodok" / "data" / "core"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "mikrodok_core.db")
        
        self._db_path = db_path
        self._max_read_connections = max_read_connections
        self._max_write_connections = max_write_connections
        self._connection_timeout = connection_timeout
        self._idle_timeout = idle_timeout
        
        # Thread safety
        self._lock = threading.RLock()
        self._read_pool_lock = threading.Lock()
        self._write_pool_lock = threading.Lock()
        
        # Connection pools
        self._read_pool: Queue = Queue(maxsize=max_read_connections)
        self._write_pool: Queue = Queue(maxsize=max_write_connections)
        
        # Connection tracking
        self._active_connections: Dict[str, ConnectionInfo] = {}
        self._connection_refs: Dict[str, weakref.ref] = {}
        self._thread_local = threading.local()
        
        # Statistics
        self._total_connections_created = 0
        self._total_queries_executed = 0
        self._total_errors = 0
        
        # Logger
        self._logger = get_logger(__name__)
        
        # Initialize database and pools
        self._initialize_database()
        self._initialize_pools()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_idle_connections, daemon=True)
        self._cleanup_thread.start()
        
        self._logger.info(f"ConnectionManagerDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database with optimal settings."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            
            # Set auto-checkpoint
            cursor.execute("PRAGMA wal_autocheckpoint=1000")
            
            conn.commit()
            conn.close()
            
            self._logger.info("Database initialized with WAL mode and optimal settings")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _initialize_pools(self) -> None:
        """Initialize connection pools."""
        try:
            # Create initial read connections
            for _ in range(self._max_read_connections):
                conn = self._create_connection(ConnectionType.READ_ONLY)
                self._read_pool.put(conn)
            
            # Create initial write connection
            for _ in range(self._max_write_connections):
                conn = self._create_connection(ConnectionType.READ_WRITE)
                self._write_pool.put(conn)
            
            self._logger.info(f"Connection pools initialized: {self._max_read_connections} read, {self._max_write_connections} write")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize connection pools: {e}")
            raise

    def _create_connection(self, connection_type: ConnectionType) -> sqlite3.Connection:
        """
        Create a new database connection.

        Args:
            connection_type: Type of connection to create

        Returns:
            SQLite connection object
        """
        try:
            if connection_type == ConnectionType.READ_ONLY:
                conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            else:
                conn = sqlite3.connect(self._db_path)

            # Configure connection
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")

            if connection_type != ConnectionType.READ_ONLY:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")

            # Track connection
            connection_id = f"{connection_type.value}_{self._total_connections_created}"
            self._total_connections_created += 1

            # Store connection info
            info = ConnectionInfo(
                connection_id=connection_id,
                connection_type=connection_type,
                state=ConnectionState.IDLE,
                created_at=datetime.now(timezone.utc),
                last_used_at=datetime.now(timezone.utc),
                thread_id=threading.get_ident(),
                query_count=0,
                error_count=0,
                database_path=self._db_path
            )

            with self._lock:
                self._active_connections[connection_id] = info
                self._connection_refs[connection_id] = weakref.ref(conn, self._connection_cleanup)

            self._logger.debug(f"Created connection: {connection_id}")
            return conn

        except Exception as e:
            self._logger.error(f"Failed to create connection: {e}")
            self._total_errors += 1
            raise

    def _connection_cleanup(self, ref: weakref.ref) -> None:
        """Cleanup callback for garbage collected connections."""
        with self._lock:
            # Find and remove connection info
            for conn_id, conn_ref in list(self._connection_refs.items()):
                if conn_ref is ref:
                    self._active_connections.pop(conn_id, None)
                    self._connection_refs.pop(conn_id, None)
                    self._logger.debug(f"Cleaned up connection: {conn_id}")
                    break

    @contextmanager
    def get_connection(self, connection_type: ConnectionType = ConnectionType.READ_ONLY) -> ContextManager[sqlite3.Connection]:
        """
        Get a database connection from the pool.

        Args:
            connection_type: Type of connection needed

        Yields:
            SQLite connection object

        Raises:
            TimeoutError: If connection cannot be acquired within timeout
        """
        conn = None
        start_time = time.time()

        try:
            # Get connection from appropriate pool
            if connection_type == ConnectionType.READ_ONLY:
                with self._read_pool_lock:
                    try:
                        conn = self._read_pool.get(timeout=self._connection_timeout)
                    except Empty:
                        raise TimeoutError(f"Failed to acquire read connection within {self._connection_timeout}s")
            else:
                with self._write_pool_lock:
                    try:
                        conn = self._write_pool.get(timeout=self._connection_timeout)
                    except Empty:
                        raise TimeoutError(f"Failed to acquire write connection within {self._connection_timeout}s")

            # Update connection info
            self._update_connection_usage(conn, ConnectionState.ACTIVE)

            yield conn

        except Exception as e:
            self._logger.error(f"Connection error: {e}")
            self._total_errors += 1

            # Mark connection as error state
            if conn:
                self._update_connection_usage(conn, ConnectionState.ERROR)

            raise

        finally:
            # Return connection to pool
            if conn:
                try:
                    # Update usage stats
                    self._update_connection_usage(conn, ConnectionState.IDLE)

                    # Return to appropriate pool
                    if connection_type == ConnectionType.READ_ONLY:
                        with self._read_pool_lock:
                            self._read_pool.put(conn)
                    else:
                        with self._write_pool_lock:
                            self._write_pool.put(conn)

                except Exception as e:
                    self._logger.error(f"Failed to return connection to pool: {e}")
                    # Close the connection if we can't return it
                    try:
                        conn.close()
                    except:
                        pass

    def _update_connection_usage(self, conn: sqlite3.Connection, state: ConnectionState) -> None:
        """Update connection usage statistics."""
        try:
            with self._lock:
                # Find connection info by object reference
                for info in self._active_connections.values():
                    # Use a simple heuristic to match connections
                    if info.state != ConnectionState.CLOSED:
                        info.state = state
                        info.last_used_at = datetime.now(timezone.utc)
                        if state == ConnectionState.ACTIVE:
                            info.query_count += 1
                            self._total_queries_executed += 1
                        elif state == ConnectionState.ERROR:
                            info.error_count += 1
                        break

        except Exception as e:
            self._logger.warning(f"Failed to update connection usage: {e}")

    def _cleanup_idle_connections(self) -> None:
        """Background thread to cleanup idle connections."""
        while True:
            try:
                time.sleep(60)  # Check every minute

                current_time = datetime.now(timezone.utc)
                connections_to_close = []

                with self._lock:
                    for conn_id, info in self._active_connections.items():
                        if (info.state == ConnectionState.IDLE and
                            (current_time - info.last_used_at).total_seconds() > self._idle_timeout):
                            connections_to_close.append(conn_id)

                # Close idle connections
                for conn_id in connections_to_close:
                    self._close_connection(conn_id)

                if connections_to_close:
                    self._logger.debug(f"Cleaned up {len(connections_to_close)} idle connections")

            except Exception as e:
                self._logger.error(f"Error in connection cleanup: {e}")

    def _close_connection(self, connection_id: str) -> None:
        """Close a specific connection."""
        try:
            with self._lock:
                info = self._active_connections.get(connection_id)
                if info:
                    info.state = ConnectionState.CLOSED

                # Remove from tracking
                conn_ref = self._connection_refs.pop(connection_id, None)
                if conn_ref and conn_ref():
                    try:
                        conn_ref().close()
                    except:
                        pass

                self._active_connections.pop(connection_id, None)

        except Exception as e:
            self._logger.warning(f"Error closing connection {connection_id}: {e}")

    def execute_query(self, query: str, params: Optional[Tuple] = None,
                     connection_type: ConnectionType = ConnectionType.READ_ONLY) -> List[sqlite3.Row]:
        """
        Execute a query with automatic connection management.

        Args:
            query: SQL query to execute
            params: Query parameters
            connection_type: Type of connection needed

        Returns:
            Query results
        """
        with self.get_connection(connection_type) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if connection_type != ConnectionType.READ_ONLY:
                conn.commit()

            return cursor.fetchall()

    def execute_many(self, query: str, params_list: List[Tuple],
                    connection_type: ConnectionType = ConnectionType.READ_WRITE) -> None:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
            connection_type: Type of connection needed
        """
        with self.get_connection(connection_type) as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with connection statistics
        """
        with self._lock:
            active_count = len([info for info in self._active_connections.values()
                              if info.state == ConnectionState.ACTIVE])
            idle_count = len([info for info in self._active_connections.values()
                            if info.state == ConnectionState.IDLE])
            error_count = len([info for info in self._active_connections.values()
                             if info.state == ConnectionState.ERROR])

            return {
                'total_connections_created': self._total_connections_created,
                'active_connections': active_count,
                'idle_connections': idle_count,
                'error_connections': error_count,
                'total_queries_executed': self._total_queries_executed,
                'total_errors': self._total_errors,
                'read_pool_size': self._read_pool.qsize(),
                'write_pool_size': self._write_pool.qsize(),
                'database_path': self._db_path
            }

    def close_all_connections(self) -> None:
        """Close all connections and cleanup resources."""
        try:
            with self._lock:
                # Close all tracked connections
                for conn_id in list(self._active_connections.keys()):
                    self._close_connection(conn_id)

                # Clear pools
                while not self._read_pool.empty():
                    try:
                        conn = self._read_pool.get_nowait()
                        conn.close()
                    except:
                        pass

                while not self._write_pool.empty():
                    try:
                        conn = self._write_pool.get_nowait()
                        conn.close()
                    except:
                        pass

                self._logger.info("All connections closed")

        except Exception as e:
            self._logger.error(f"Error closing connections: {e}")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.close_all_connections()
        except:
            pass
