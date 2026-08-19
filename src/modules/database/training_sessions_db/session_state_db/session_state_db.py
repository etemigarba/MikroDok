"""
Module: session_state_db
Description: Manages training session state persistence with state transitions and validation
Phase: 4
Location: /src/modules/database/training_sessions_db/session_state_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class SessionState(Enum):
    """Training session state enumeration."""
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"
    RECOVERING = "recovering"


class StateTransition(Enum):
    """State transition types."""
    INITIALIZE = "initialize"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"
    ERROR = "error"
    RECOVER = "recover"


class SessionStateDB:
    """
    Session state database for training session state management.
    
    Manages training session state persistence with state transitions,
    validation, and history tracking. Provides thread-safe operations
    with transaction support for state management, transition logging,
    and state validation with configurable state machine rules.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the session state database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to training sessions data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "training_sessions"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "session_state.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # State machine configuration
        self._valid_transitions = self._initialize_state_machine()
        self._terminal_states = {SessionState.COMPLETED, SessionState.FAILED, SessionState.CANCELLED}
        self._active_states = {SessionState.RUNNING, SessionState.PAUSING, SessionState.RESUMING}
        
        # Configuration settings
        self._state_retention_days = 90  # Keep state history for 90 days
        self._max_transitions_per_session = 1000  # Maximum transitions per session
        
        self._initialize_database()
    
    def _initialize_state_machine(self) -> Dict[SessionState, Set[SessionState]]:
        """Initialize valid state transitions."""
        return {
            SessionState.CREATED: {SessionState.INITIALIZING, SessionState.CANCELLED},
            SessionState.INITIALIZING: {SessionState.INITIALIZED, SessionState.FAILED, SessionState.CANCELLED},
            SessionState.INITIALIZED: {SessionState.STARTING, SessionState.CANCELLED},
            SessionState.STARTING: {SessionState.RUNNING, SessionState.FAILED, SessionState.CANCELLED},
            SessionState.RUNNING: {SessionState.PAUSING, SessionState.STOPPING, SessionState.COMPLETED, 
                                  SessionState.FAILED, SessionState.ERROR},
            SessionState.PAUSING: {SessionState.PAUSED, SessionState.FAILED, SessionState.ERROR},
            SessionState.PAUSED: {SessionState.RESUMING, SessionState.STOPPING, SessionState.CANCELLED},
            SessionState.RESUMING: {SessionState.RUNNING, SessionState.FAILED, SessionState.ERROR},
            SessionState.STOPPING: {SessionState.COMPLETED, SessionState.FAILED},
            SessionState.ERROR: {SessionState.RECOVERING, SessionState.FAILED, SessionState.CANCELLED},
            SessionState.RECOVERING: {SessionState.RUNNING, SessionState.PAUSED, SessionState.FAILED},
            SessionState.COMPLETED: set(),  # Terminal state
            SessionState.FAILED: set(),     # Terminal state
            SessionState.CANCELLED: set()   # Terminal state
        }
    
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
                
                # Create session states table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_states (
                        state_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        current_state TEXT NOT NULL,
                        previous_state TEXT,
                        transition_type TEXT,
                        transition_reason TEXT,
                        transition_timestamp TEXT NOT NULL,
                        transition_metadata_json TEXT,
                        is_current BOOLEAN DEFAULT TRUE,
                        created_by TEXT,
                        error_details TEXT,
                        recovery_attempts INTEGER DEFAULT 0,
                        state_duration_seconds REAL,
                        resource_snapshot_json TEXT,
                        checkpoint_reference TEXT,
                        notes TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_states_session_id ON session_states (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_states_current ON session_states (is_current)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_states_timestamp ON session_states (transition_timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_states_session_current ON session_states (session_id, is_current)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_states_state ON session_states (current_state)")
                
                # Create state transitions table for detailed transition tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS state_transitions (
                        transition_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        from_state TEXT NOT NULL,
                        to_state TEXT NOT NULL,
                        transition_type TEXT NOT NULL,
                        transition_timestamp TEXT NOT NULL,
                        transition_duration_ms INTEGER,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        validation_errors_json TEXT,
                        preconditions_json TEXT,
                        postconditions_json TEXT,
                        triggered_by TEXT,
                        metadata_json TEXT
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_session_id ON state_transitions (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_timestamp ON state_transitions (transition_timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_success ON state_transitions (success)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_type ON state_transitions (transition_type)")
                
                # Create state validation rules table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS state_validation_rules (
                        rule_id TEXT PRIMARY KEY,
                        from_state TEXT NOT NULL,
                        to_state TEXT NOT NULL,
                        rule_name TEXT NOT NULL,
                        rule_description TEXT,
                        validation_function TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        priority INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_states ON state_validation_rules (from_state, to_state)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_active ON state_validation_rules (is_active)")
                
                conn.commit()
                self._logger.info("Session state database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize session state database: {e}")
                raise
            finally:
                conn.close()
    
    def get_current_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a training session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current state data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT state_id, session_id, current_state, previous_state,
                           transition_type, transition_reason, transition_timestamp,
                           transition_metadata_json, created_by, error_details,
                           recovery_attempts, state_duration_seconds,
                           resource_snapshot_json, checkpoint_reference, notes
                    FROM session_states
                    WHERE session_id = ? AND is_current = TRUE
                    ORDER BY transition_timestamp DESC
                    LIMIT 1
                """, (session_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    'state_id': row[0],
                    'session_id': row[1],
                    'current_state': row[2],
                    'previous_state': row[3],
                    'transition_type': row[4],
                    'transition_reason': row[5],
                    'transition_timestamp': row[6],
                    'transition_metadata': json.loads(row[7]) if row[7] else None,
                    'created_by': row[8],
                    'error_details': row[9],
                    'recovery_attempts': row[10],
                    'state_duration_seconds': row[11],
                    'resource_snapshot': json.loads(row[12]) if row[12] else None,
                    'checkpoint_reference': row[13],
                    'notes': row[14]
                }
                
            except Exception as e:
                self._logger.error(f"Failed to get current state for session {session_id}: {e}")
                return None
            finally:
                conn.close()

    def transition_state(self, session_id: str, to_state: SessionState,
                        transition_type: StateTransition, reason: Optional[str] = None,
                        triggered_by: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
                        resource_snapshot: Optional[Dict[str, Any]] = None,
                        checkpoint_reference: Optional[str] = None) -> bool:
        """
        Transition a session to a new state with validation.

        Args:
            session_id: Session identifier
            to_state: Target state
            transition_type: Type of transition
            reason: Reason for transition
            triggered_by: Who/what triggered the transition
            metadata: Additional metadata
            resource_snapshot: Current resource state
            checkpoint_reference: Associated checkpoint

        Returns:
            True if transition was successful
        """
        start_time = datetime.now(timezone.utc)
        transition_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get current state
                current_state_data = self.get_current_state(session_id)
                if current_state_data:
                    from_state = SessionState(current_state_data['current_state'])
                else:
                    # First state transition
                    from_state = None

                # Validate transition
                validation_errors = self._validate_transition(from_state, to_state, session_id)
                if validation_errors:
                    self._logger.warning(f"Invalid transition for session {session_id}: {validation_errors}")

                    # Record failed transition
                    self._record_transition(cursor, transition_id, session_id, from_state, to_state,
                                          transition_type, start_time, False, validation_errors,
                                          triggered_by, metadata)
                    conn.commit()
                    return False

                # Calculate state duration if there was a previous state
                state_duration = None
                if current_state_data:
                    prev_timestamp = datetime.fromisoformat(current_state_data['transition_timestamp'])
                    state_duration = (start_time - prev_timestamp).total_seconds()

                    # Mark previous state as not current
                    cursor.execute("""
                        UPDATE session_states
                        SET is_current = FALSE, state_duration_seconds = ?
                        WHERE session_id = ? AND is_current = TRUE
                    """, (state_duration, session_id))

                # Create new state record
                state_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO session_states (
                        state_id, session_id, current_state, previous_state,
                        transition_type, transition_reason, transition_timestamp,
                        transition_metadata_json, is_current, created_by,
                        resource_snapshot_json, checkpoint_reference
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    state_id, session_id, to_state.value,
                    from_state.value if from_state else None,
                    transition_type.value, reason, start_time.isoformat(),
                    json.dumps(metadata) if metadata else None, True, triggered_by,
                    json.dumps(resource_snapshot) if resource_snapshot else None,
                    checkpoint_reference
                ))

                # Record successful transition
                end_time = datetime.now(timezone.utc)
                transition_duration = int((end_time - start_time).total_seconds() * 1000)

                self._record_transition(cursor, transition_id, session_id, from_state, to_state,
                                      transition_type, start_time, True, None,
                                      triggered_by, metadata, transition_duration)

                conn.commit()
                self._logger.info(f"Session {session_id} transitioned from {from_state} to {to_state}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to transition session {session_id} to {to_state}: {e}")
                return False
            finally:
                conn.close()

    def _validate_transition(self, from_state: Optional[SessionState], to_state: SessionState,
                           session_id: str) -> Optional[List[str]]:
        """
        Validate a state transition.

        Args:
            from_state: Current state (None for initial state)
            to_state: Target state
            session_id: Session identifier

        Returns:
            List of validation errors or None if valid
        """
        errors = []

        # Check if transition is allowed by state machine
        if from_state is None:
            # Initial state must be CREATED
            if to_state != SessionState.CREATED:
                errors.append(f"Initial state must be CREATED, not {to_state.value}")
        else:
            # Check if transition is valid
            if to_state not in self._valid_transitions.get(from_state, set()):
                errors.append(f"Invalid transition from {from_state.value} to {to_state.value}")

            # Check if trying to transition from terminal state
            if from_state in self._terminal_states:
                errors.append(f"Cannot transition from terminal state {from_state.value}")

        return errors if errors else None

    def _record_transition(self, cursor, transition_id: str, session_id: str,
                          from_state: Optional[SessionState], to_state: SessionState,
                          transition_type: StateTransition, timestamp: datetime,
                          success: bool, error_message: Optional[List[str]] = None,
                          triggered_by: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None,
                          duration_ms: Optional[int] = None) -> None:
        """Record a state transition in the transitions table."""
        cursor.execute("""
            INSERT INTO state_transitions (
                transition_id, session_id, from_state, to_state, transition_type,
                transition_timestamp, transition_duration_ms, success, error_message,
                validation_errors_json, triggered_by, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transition_id, session_id,
            from_state.value if from_state else None, to_state.value,
            transition_type.value, timestamp.isoformat(), duration_ms, success,
            str(error_message) if error_message else None,
            json.dumps(error_message) if error_message else None,
            triggered_by, json.dumps(metadata) if metadata else None
        ))

    def get_state_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get state history for a training session.

        Args:
            session_id: Session identifier
            limit: Maximum number of states to return

        Returns:
            List of state records ordered by timestamp
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT state_id, session_id, current_state, previous_state,
                           transition_type, transition_reason, transition_timestamp,
                           transition_metadata_json, is_current, created_by,
                           error_details, recovery_attempts, state_duration_seconds,
                           resource_snapshot_json, checkpoint_reference, notes
                    FROM session_states
                    WHERE session_id = ?
                    ORDER BY transition_timestamp DESC
                    LIMIT ?
                """, (session_id, limit))

                states = []
                for row in cursor.fetchall():
                    state_data = {
                        'state_id': row[0],
                        'session_id': row[1],
                        'current_state': row[2],
                        'previous_state': row[3],
                        'transition_type': row[4],
                        'transition_reason': row[5],
                        'transition_timestamp': row[6],
                        'transition_metadata': json.loads(row[7]) if row[7] else None,
                        'is_current': bool(row[8]),
                        'created_by': row[9],
                        'error_details': row[10],
                        'recovery_attempts': row[11],
                        'state_duration_seconds': row[12],
                        'resource_snapshot': json.loads(row[13]) if row[13] else None,
                        'checkpoint_reference': row[14],
                        'notes': row[15]
                    }
                    states.append(state_data)

                return states

            except Exception as e:
                self._logger.error(f"Failed to get state history for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def get_transition_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get transition history for a training session.

        Args:
            session_id: Session identifier
            limit: Maximum number of transitions to return

        Returns:
            List of transition records ordered by timestamp
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT transition_id, session_id, from_state, to_state,
                           transition_type, transition_timestamp, transition_duration_ms,
                           success, error_message, validation_errors_json,
                           triggered_by, metadata_json
                    FROM state_transitions
                    WHERE session_id = ?
                    ORDER BY transition_timestamp DESC
                    LIMIT ?
                """, (session_id, limit))

                transitions = []
                for row in cursor.fetchall():
                    transition_data = {
                        'transition_id': row[0],
                        'session_id': row[1],
                        'from_state': row[2],
                        'to_state': row[3],
                        'transition_type': row[4],
                        'transition_timestamp': row[5],
                        'transition_duration_ms': row[6],
                        'success': bool(row[7]),
                        'error_message': row[8],
                        'validation_errors': json.loads(row[9]) if row[9] else None,
                        'triggered_by': row[10],
                        'metadata': json.loads(row[11]) if row[11] else None
                    }
                    transitions.append(transition_data)

                return transitions

            except Exception as e:
                self._logger.error(f"Failed to get transition history for session {session_id}: {e}")
                return []
            finally:
                conn.close()

    def get_sessions_by_state(self, state: SessionState, limit: int = 100) -> List[str]:
        """
        Get sessions currently in a specific state.

        Args:
            state: Session state to filter by
            limit: Maximum number of sessions to return

        Returns:
            List of session IDs
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_id
                    FROM session_states
                    WHERE current_state = ? AND is_current = TRUE
                    ORDER BY transition_timestamp DESC
                    LIMIT ?
                """, (state.value, limit))

                return [row[0] for row in cursor.fetchall()]

            except Exception as e:
                self._logger.error(f"Failed to get sessions by state {state.value}: {e}")
                return []
            finally:
                conn.close()

    def update_state_metadata(self, session_id: str, metadata: Dict[str, Any],
                             error_details: Optional[str] = None,
                             recovery_attempts: Optional[int] = None,
                             notes: Optional[str] = None) -> bool:
        """
        Update metadata for the current state of a session.

        Args:
            session_id: Session identifier
            metadata: Metadata to update
            error_details: Error details if applicable
            recovery_attempts: Number of recovery attempts
            notes: Additional notes

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build update query
                update_fields = ["transition_metadata_json = ?"]
                update_values = [json.dumps(metadata)]

                if error_details is not None:
                    update_fields.append("error_details = ?")
                    update_values.append(error_details)

                if recovery_attempts is not None:
                    update_fields.append("recovery_attempts = ?")
                    update_values.append(recovery_attempts)

                if notes is not None:
                    update_fields.append("notes = ?")
                    update_values.append(notes)

                update_values.append(session_id)

                query = f"""
                    UPDATE session_states
                    SET {', '.join(update_fields)}
                    WHERE session_id = ? AND is_current = TRUE
                """

                cursor.execute(query, update_values)

                if cursor.rowcount == 0:
                    self._logger.warning(f"No current state found for session {session_id}")
                    return False

                conn.commit()
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update state metadata for session {session_id}: {e}")
                return False
            finally:
                conn.close()

    def cleanup_old_states(self) -> int:
        """
        Clean up old state records based on retention policy.

        Returns:
            Number of state records cleaned up
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=self._state_retention_days)).isoformat()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old state records (keep current states)
                cursor.execute("""
                    DELETE FROM session_states
                    WHERE transition_timestamp < ? AND is_current = FALSE
                """, (cutoff_date,))

                state_count = cursor.rowcount

                # Delete old transition records
                cursor.execute("""
                    DELETE FROM state_transitions
                    WHERE transition_timestamp < ?
                """, (cutoff_date,))

                transition_count = cursor.rowcount

                conn.commit()

                total_cleaned = state_count + transition_count
                self._logger.info(f"Cleaned up {total_cleaned} old state records")
                return total_cleaned

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old states: {e}")
                return 0
            finally:
                conn.close()

    def get_state_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about session states.

        Returns:
            Dictionary with state statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get current state distribution
                cursor.execute("""
                    SELECT current_state, COUNT(*)
                    FROM session_states
                    WHERE is_current = TRUE
                    GROUP BY current_state
                """)
                current_state_counts = dict(cursor.fetchall())

                # Get transition success rate
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_transitions,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_transitions
                    FROM state_transitions
                """)
                transition_stats = cursor.fetchone()
                total_transitions = transition_stats[0] if transition_stats else 0
                successful_transitions = transition_stats[1] if transition_stats else 0

                success_rate = (successful_transitions / total_transitions * 100) if total_transitions > 0 else 0

                # Get average transition duration
                cursor.execute("""
                    SELECT AVG(transition_duration_ms)
                    FROM state_transitions
                    WHERE success = 1 AND transition_duration_ms IS NOT NULL
                """)
                avg_transition_duration = cursor.fetchone()[0]

                # Get most common transition types
                cursor.execute("""
                    SELECT transition_type, COUNT(*)
                    FROM state_transitions
                    GROUP BY transition_type
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                """)
                common_transitions = dict(cursor.fetchall())

                return {
                    'current_state_counts': current_state_counts,
                    'total_transitions': total_transitions,
                    'successful_transitions': successful_transitions,
                    'transition_success_rate': success_rate,
                    'average_transition_duration_ms': avg_transition_duration,
                    'common_transition_types': common_transitions
                }

            except Exception as e:
                self._logger.error(f"Failed to get state statistics: {e}")
                return {}
            finally:
                conn.close()
