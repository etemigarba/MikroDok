"""
Module: access_controller_lg
Description: Manages access control and permission validation with role-based security and session management
Phase: 4
Location: /src/modules/logic/security_infrastructure_lg/access_controller_lg/access_controller_lg.py
"""

# Standard library imports
import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import threading

# Local imports
from src.modules.logic.security_infrastructure_lg.base_interfaces import (
    IAccessController, AccessControlConfig, AccessSession, AccessRequest, 
    AccessResult, AccessLevel, SessionStatus
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager


class AccessControlError(Exception):
    """Exception raised for access control-related errors."""
    pass


class SessionExpiredError(Exception):
    """Exception raised when session has expired."""
    pass


class AccessController(IAccessController):
    """
    Manages access control and permission validation for MikroDok.
    
    Provides role-based access control, session management, permission validation,
    and comprehensive audit logging for security events.
    """
    
    def __init__(self, config: Optional[AccessControlConfig] = None):
        """
        Initialize access controller.
        
        Args:
            config: Access control configuration
        """
        self._config = config or AccessControlConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._lock = threading.RLock()
        
        # Session storage
        self._sessions: Dict[str, AccessSession] = {}
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> session_ids
        
        # Failed attempt tracking
        self._failed_attempts: Dict[str, List[datetime]] = {}
        self._locked_users: Dict[str, datetime] = {}
        
        # Audit log
        self._audit_log: List[Dict[str, Any]] = []
        self._audit_file: Optional[Path] = None
        
        # Role hierarchy (higher levels include lower level permissions)
        self._role_hierarchy = {
            AccessLevel.NONE: 0,
            AccessLevel.READ_ONLY: 1,
            AccessLevel.STANDARD: 2,
            AccessLevel.ADMIN: 3,
            AccessLevel.SUPER_ADMIN: 4
        }
        
        self._logger.info("AccessController initialized")
    
    def create_session(self, user_id: str, access_level: AccessLevel, 
                      config: Optional[AccessControlConfig] = None) -> AccessSession:
        """
        Create a new access session.
        
        Args:
            user_id: User identifier
            access_level: Requested access level
            config: Access control configuration
            
        Returns:
            AccessSession with session details
        """
        try:
            # Validate user is not locked out
            if self._is_user_locked(user_id):
                lockout_end = self._locked_users[user_id] + self._config.lockout_duration
                raise AccessControlError(f"User locked out until {lockout_end}")
            
            # Use provided config or default
            access_config = config or self._config
            
            # Create session
            session = AccessSession(
                user_id=user_id,
                access_level=access_level,
                expires_at=datetime.utcnow() + access_config.session_timeout
            )
            
            with self._lock:
                # Store session
                self._sessions[session.session_id] = session
                
                # Track user sessions
                if user_id not in self._user_sessions:
                    self._user_sessions[user_id] = set()
                self._user_sessions[user_id].add(session.session_id)
            
            # Log session creation
            self._log_audit_event("session_created", {
                'user_id': user_id,
                'session_id': session.session_id,
                'access_level': access_level.value,
                'expires_at': session.expires_at.isoformat()
            })
            
            self._logger.info(f"Session created for user {user_id}: {session.session_id}")
            
            return session
            
        except Exception as e:
            self._logger.error(f"Session creation failed: {str(e)}")
            raise AccessControlError(f"Session creation failed: {str(e)}")
    
    def validate_access(self, request: AccessRequest) -> AccessResult:
        """
        Validate access request against permissions.
        
        Args:
            request: Access request to validate
            
        Returns:
            AccessResult with validation outcome
        """
        try:
            # Get session if provided
            session = None
            if request.session_id:
                session = self.get_session(request.session_id)
                if not session:
                    return AccessResult(
                        granted=False,
                        reason="Invalid session ID"
                    )
                
                # Check session expiry
                if session.status != SessionStatus.ACTIVE or session.expires_at < datetime.utcnow():
                    self._expire_session(session.session_id)
                    return AccessResult(
                        granted=False,
                        reason="Session expired"
                    )
                
                # Update last activity
                session.last_activity = datetime.utcnow()
            
            # Check if user is locked out
            if self._is_user_locked(request.user_id):
                self._record_failed_attempt(request.user_id)
                return AccessResult(
                    granted=False,
                    reason="User account locked"
                )
            
            # Determine user's access level
            user_level = session.access_level if session else AccessLevel.NONE
            
            # Check permission hierarchy
            required_level_value = self._role_hierarchy.get(request.requested_level, 0)
            user_level_value = self._role_hierarchy.get(user_level, 0)
            
            granted = user_level_value >= required_level_value
            
            # Create result
            result = AccessResult(
                granted=granted,
                session=session,
                required_level=request.requested_level,
                actual_level=user_level,
                reason="Access granted" if granted else "Insufficient permissions"
            )
            
            # Log access attempt
            audit_entry_id = self.audit_access(request, result)
            result.audit_entry_id = audit_entry_id
            
            # Record failed attempt if access denied
            if not granted:
                self._record_failed_attempt(request.user_id)
            
            return result
            
        except Exception as e:
            self._logger.error(f"Access validation failed: {str(e)}")
            return AccessResult(
                granted=False,
                reason=f"Validation error: {str(e)}"
            )
    
    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke an active session.
        
        Args:
            session_id: Session identifier to revoke
            
        Returns:
            True if revocation successful, False otherwise
        """
        try:
            with self._lock:
                session = self._sessions.get(session_id)
                if not session:
                    return False
                
                # Update session status
                session.status = SessionStatus.REVOKED
                
                # Remove from user sessions
                user_sessions = self._user_sessions.get(session.user_id, set())
                user_sessions.discard(session_id)
                
                # Remove from active sessions
                del self._sessions[session_id]
            
            # Log session revocation
            self._log_audit_event("session_revoked", {
                'session_id': session_id,
                'user_id': session.user_id,
                'revoked_at': datetime.utcnow().isoformat()
            })
            
            self._logger.info(f"Session revoked: {session_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Session revocation failed: {str(e)}")
            return False
    
    def get_session(self, session_id: str) -> Optional[AccessSession]:
        """
        Get session information.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AccessSession if found, None otherwise
        """
        with self._lock:
            return self._sessions.get(session_id)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            current_time = datetime.utcnow()
            expired_sessions = []
            
            with self._lock:
                for session_id, session in self._sessions.items():
                    if session.expires_at < current_time:
                        expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                self._expire_session(session_id)
            
            self._logger.debug(f"Cleaned up {len(expired_sessions)} expired sessions")
            return len(expired_sessions)
            
        except Exception as e:
            self._logger.error(f"Session cleanup failed: {str(e)}")
            return 0
    
    def audit_access(self, request: AccessRequest, result: AccessResult) -> str:
        """
        Log access attempt for audit trail.
        
        Args:
            request: Access request
            result: Access result
            
        Returns:
            Audit entry identifier
        """
        try:
            audit_entry_id = str(uuid.uuid4())
            
            audit_entry = {
                'audit_id': audit_entry_id,
                'timestamp': request.timestamp.isoformat(),
                'user_id': request.user_id,
                'resource_id': request.resource_id,
                'requested_level': request.requested_level.value,
                'actual_level': result.actual_level.value,
                'granted': result.granted,
                'reason': result.reason,
                'session_id': request.session_id,
                'context': request.context
            }
            
            with self._lock:
                self._audit_log.append(audit_entry)
                
                # Write to audit file if configured
                if self._audit_file:
                    self._write_audit_entry(audit_entry)
            
            return audit_entry_id
            
        except Exception as e:
            self._logger.error(f"Audit logging failed: {str(e)}")
            return ""

    def set_audit_file(self, audit_file_path: Path) -> None:
        """Set audit log file path."""
        self._audit_file = audit_file_path
        self._audit_file.parent.mkdir(parents=True, exist_ok=True)

    def get_audit_log(self, user_id: Optional[str] = None,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get audit log entries with optional filtering.

        Args:
            user_id: Filter by user ID
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of audit log entries
        """
        with self._lock:
            filtered_log = []

            for entry in self._audit_log:
                # Filter by user ID
                if user_id and entry.get('user_id') != user_id:
                    continue

                # Filter by time range
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if start_time and entry_time < start_time:
                    continue
                if end_time and entry_time > end_time:
                    continue

                filtered_log.append(entry.copy())

            return filtered_log

    def _is_user_locked(self, user_id: str) -> bool:
        """Check if user is currently locked out."""
        if user_id not in self._locked_users:
            return False

        lockout_end = self._locked_users[user_id] + self._config.lockout_duration
        if datetime.utcnow() > lockout_end:
            # Lockout expired, remove from locked users
            del self._locked_users[user_id]
            if user_id in self._failed_attempts:
                del self._failed_attempts[user_id]
            return False

        return True

    def _record_failed_attempt(self, user_id: str) -> None:
        """Record a failed access attempt."""
        current_time = datetime.utcnow()

        if user_id not in self._failed_attempts:
            self._failed_attempts[user_id] = []

        # Add current attempt
        self._failed_attempts[user_id].append(current_time)

        # Remove attempts older than lockout duration
        cutoff_time = current_time - self._config.lockout_duration
        self._failed_attempts[user_id] = [
            attempt for attempt in self._failed_attempts[user_id]
            if attempt > cutoff_time
        ]

        # Check if user should be locked out
        if len(self._failed_attempts[user_id]) >= self._config.max_failed_attempts:
            self._locked_users[user_id] = current_time
            self._logger.warning(f"User locked out due to failed attempts: {user_id}")

            # Log lockout event
            self._log_audit_event("user_locked", {
                'user_id': user_id,
                'failed_attempts': len(self._failed_attempts[user_id]),
                'locked_at': current_time.isoformat()
            })

    def _expire_session(self, session_id: str) -> None:
        """Mark session as expired and remove from active sessions."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = SessionStatus.EXPIRED

                # Remove from user sessions
                user_sessions = self._user_sessions.get(session.user_id, set())
                user_sessions.discard(session_id)

                # Remove from active sessions
                del self._sessions[session_id]

                # Log session expiry
                self._log_audit_event("session_expired", {
                    'session_id': session_id,
                    'user_id': session.user_id,
                    'expired_at': datetime.utcnow().isoformat()
                })

    def _log_audit_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log an audit event."""
        audit_entry = {
            'audit_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'event_data': event_data
        }

        with self._lock:
            self._audit_log.append(audit_entry)

            # Write to audit file if configured
            if self._audit_file:
                self._write_audit_entry(audit_entry)

    def _write_audit_entry(self, audit_entry: Dict[str, Any]) -> None:
        """Write audit entry to file."""
        try:
            with open(self._audit_file, 'a') as f:
                f.write(json.dumps(audit_entry) + '\n')
        except Exception as e:
            self._logger.error(f"Failed to write audit entry: {str(e)}")

    def get_active_sessions(self, user_id: Optional[str] = None) -> List[AccessSession]:
        """
        Get list of active sessions.

        Args:
            user_id: Filter by user ID

        Returns:
            List of active sessions
        """
        with self._lock:
            sessions = []
            for session in self._sessions.values():
                if user_id and session.user_id != user_id:
                    continue
                if session.status == SessionStatus.ACTIVE:
                    sessions.append(session)
            return sessions

    def revoke_user_sessions(self, user_id: str) -> int:
        """
        Revoke all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions revoked
        """
        try:
            user_sessions = self._user_sessions.get(user_id, set()).copy()
            revoked_count = 0

            for session_id in user_sessions:
                if self.revoke_session(session_id):
                    revoked_count += 1

            self._logger.info(f"Revoked {revoked_count} sessions for user {user_id}")
            return revoked_count

        except Exception as e:
            self._logger.error(f"Failed to revoke user sessions: {str(e)}")
            return 0
