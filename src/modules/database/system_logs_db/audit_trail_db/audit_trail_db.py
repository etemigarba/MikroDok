"""
Module: audit_trail_db
Description: Maintains tamper-proof audit trail records with comprehensive tracking and compliance features for security and regulatory requirements
Phase: 4
Location: /src/modules/database/system_logs_db/audit_trail_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import hashlib
import hmac
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class AuditAction(Enum):
    """Audit action enumeration."""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_IMPORT = "DATA_IMPORT"
    BACKUP_CREATED = "BACKUP_CREATED"
    BACKUP_RESTORED = "BACKUP_RESTORED"
    SYSTEM_START = "SYSTEM_START"
    SYSTEM_STOP = "SYSTEM_STOP"
    TRAINING_START = "TRAINING_START"
    TRAINING_STOP = "TRAINING_STOP"
    MODEL_DEPLOYED = "MODEL_DEPLOYED"
    MODEL_RETIRED = "MODEL_RETIRED"


class ResourceType(Enum):
    """Resource type enumeration."""
    USER = "USER"
    DOCUMENT = "DOCUMENT"
    MODEL = "MODEL"
    CONFIGURATION = "CONFIGURATION"
    SYSTEM = "SYSTEM"
    DATABASE = "DATABASE"
    FILE = "FILE"
    SESSION = "SESSION"
    TRAINING_JOB = "TRAINING_JOB"
    INFERENCE_SESSION = "INFERENCE_SESSION"
    BACKUP = "BACKUP"
    LOG = "LOG"


class AuditSeverity(Enum):
    """Audit severity enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AuditTrailEntry:
    """Audit trail entry data structure."""
    audit_id: str
    timestamp: datetime
    user_id: str
    action: AuditAction
    resource_type: ResourceType
    resource_id: str
    severity: AuditSeverity
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None
    checksum: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class AuditTrailDB:
    """
    Audit trail database manager.
    
    Maintains tamper-proof audit trail records with comprehensive tracking,
    integrity verification, and compliance features for security auditing
    and regulatory requirements.
    """
    
    def __init__(self, db_path: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Initialize the audit trail database.
        
        Args:
            db_path: Path to the database file
            secret_key: Secret key for integrity verification
        """
        if db_path is None:
            # Default to system logs data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "system_logs"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "audit_trail.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Secret key for integrity verification
        self._secret_key = secret_key or "mikrodok_audit_secret_2024"
        
        # Retention settings
        self._retention_years = 7  # Keep audit trails for 7 years (compliance requirement)
        self._archive_threshold_months = 12  # Archive after 12 months
        
        # Performance settings
        self._batch_size = 500
        self._integrity_check_interval = 1000  # Check integrity every 1000 entries
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Create audit trail table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    audit_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    correlation_id TEXT,
                    additional_context TEXT,
                    checksum TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create audit summary table for reporting
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_summary (
                    summary_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    first_occurrence TEXT NOT NULL,
                    last_occurrence TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create integrity verification table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS integrity_verification (
                    verification_id TEXT PRIMARY KEY,
                    verification_date TEXT NOT NULL,
                    start_audit_id TEXT NOT NULL,
                    end_audit_id TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    hash_chain TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_user_id ON audit_trail(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_action ON audit_trail(action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_resource_type ON audit_trail(resource_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_resource_id ON audit_trail(resource_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_severity ON audit_trail(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_session_id ON audit_trail(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_correlation_id ON audit_trail(correlation_id)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_summary_date ON audit_summary(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_summary_user_id ON audit_summary(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_summary_action ON audit_summary(action)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrity_verification_date ON integrity_verification(verification_date)")
            
            conn.commit()
            conn.close()
            
            self._logger.info("Audit trail database initialized successfully")
    
    def _calculate_checksum(self, entry_data: Dict[str, Any]) -> str:
        """Calculate integrity checksum for an audit entry."""
        # Create a deterministic string representation
        sorted_data = json.dumps(entry_data, sort_keys=True, default=str)
        
        # Calculate HMAC-SHA256
        checksum = hmac.new(
            self._secret_key.encode('utf-8'),
            sorted_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return checksum
    
    def add_audit_entry(self, user_id: str, action: AuditAction, resource_type: ResourceType,
                       resource_id: str, severity: AuditSeverity = AuditSeverity.MEDIUM,
                       old_values: Optional[Dict[str, Any]] = None,
                       new_values: Optional[Dict[str, Any]] = None,
                       ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                       session_id: Optional[str] = None, correlation_id: Optional[str] = None,
                       additional_context: Optional[Dict[str, Any]] = None,
                       success: bool = True, error_message: Optional[str] = None) -> str:
        """
        Add a new audit trail entry.
        
        Args:
            user_id: ID of the user performing the action
            action: Action being performed
            resource_type: Type of resource being acted upon
            resource_id: ID of the resource
            severity: Severity level of the action
            old_values: Optional old values before change
            new_values: Optional new values after change
            ip_address: Optional IP address of the user
            user_agent: Optional user agent string
            session_id: Optional session ID
            correlation_id: Optional correlation ID for tracking related events
            additional_context: Optional additional context information
            success: Whether the action was successful
            error_message: Optional error message if action failed
            
        Returns:
            Audit entry ID
        """
        audit_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Prepare entry data for checksum calculation
        entry_data = {
            'audit_id': audit_id,
            'timestamp': timestamp.isoformat(),
            'user_id': user_id,
            'action': action.value,
            'resource_type': resource_type.value,
            'resource_id': resource_id,
            'severity': severity.value,
            'old_values': old_values,
            'new_values': new_values,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_id': session_id,
            'correlation_id': correlation_id,
            'additional_context': additional_context,
            'success': success,
            'error_message': error_message
        }
        
        # Calculate integrity checksum
        checksum = self._calculate_checksum(entry_data)
        
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO audit_trail (
                        audit_id, timestamp, user_id, action, resource_type, resource_id,
                        severity, old_values, new_values, ip_address, user_agent,
                        session_id, correlation_id, additional_context, checksum,
                        success, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_id, timestamp.isoformat(), user_id, action.value,
                    resource_type.value, resource_id, severity.value,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    ip_address, user_agent, session_id, correlation_id,
                    json.dumps(additional_context) if additional_context else None,
                    checksum, 1 if success else 0, error_message
                ))
                
                conn.commit()
                conn.close()
                
                # Update summary asynchronously
                self._update_audit_summary(timestamp, user_id, action, resource_type, success)
                
                # Log the audit action
                status = "SUCCESS" if success else "FAILURE"
                self._logger.info(f"Audit [{status}]: {user_id} performed {action.value} on {resource_type.value}:{resource_id}")
                
                return audit_id
                
            except Exception as e:
                self._logger.error(f"Failed to add audit entry: {e}")
                raise

    def _update_audit_summary(self, timestamp: datetime, user_id: str, action: AuditAction,
                             resource_type: ResourceType, success: bool) -> None:
        """Update audit summary statistics."""
        try:
            date_str = timestamp.date().isoformat()
            summary_id = f"{date_str}_{user_id}_{action.value}_{resource_type.value}"

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Check if summary exists
                cursor.execute("""
                    SELECT count, success_count, failure_count
                    FROM audit_summary
                    WHERE summary_id = ?
                """, (summary_id,))

                result = cursor.fetchone()

                if result:
                    # Update existing summary
                    count, success_count, failure_count = result
                    new_count = count + 1
                    new_success_count = success_count + (1 if success else 0)
                    new_failure_count = failure_count + (0 if success else 1)

                    cursor.execute("""
                        UPDATE audit_summary
                        SET count = ?, success_count = ?, failure_count = ?,
                            last_occurrence = ?
                        WHERE summary_id = ?
                    """, (new_count, new_success_count, new_failure_count,
                          timestamp.isoformat(), summary_id))
                else:
                    # Create new summary
                    cursor.execute("""
                        INSERT INTO audit_summary (
                            summary_id, date, user_id, action, resource_type,
                            count, success_count, failure_count,
                            first_occurrence, last_occurrence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        summary_id, date_str, user_id, action.value, resource_type.value,
                        1, 1 if success else 0, 0 if success else 1,
                        timestamp.isoformat(), timestamp.isoformat()
                    ))

                conn.commit()
                conn.close()

        except Exception as e:
            self._logger.error(f"Failed to update audit summary: {e}")

    def get_audit_entries(self, start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         user_id: Optional[str] = None,
                         action: Optional[AuditAction] = None,
                         resource_type: Optional[ResourceType] = None,
                         resource_id: Optional[str] = None,
                         severity: Optional[AuditSeverity] = None,
                         session_id: Optional[str] = None,
                         correlation_id: Optional[str] = None,
                         success_only: Optional[bool] = None,
                         limit: int = 1000) -> List[AuditTrailEntry]:
        """
        Retrieve audit trail entries with filtering options.

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            user_id: Optional user ID filter
            action: Optional action filter
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter
            severity: Optional severity filter
            session_id: Optional session ID filter
            correlation_id: Optional correlation ID filter
            success_only: Optional filter for successful actions only
            limit: Maximum number of entries to return

        Returns:
            List of audit trail entries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Build query with filters
                query = "SELECT * FROM audit_trail WHERE 1=1"
                params = []

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                if action:
                    query += " AND action = ?"
                    params.append(action.value)

                if resource_type:
                    query += " AND resource_type = ?"
                    params.append(resource_type.value)

                if resource_id:
                    query += " AND resource_id = ?"
                    params.append(resource_id)

                if severity:
                    query += " AND severity = ?"
                    params.append(severity.value)

                if session_id:
                    query += " AND session_id = ?"
                    params.append(session_id)

                if correlation_id:
                    query += " AND correlation_id = ?"
                    params.append(correlation_id)

                if success_only is not None:
                    query += " AND success = ?"
                    params.append(1 if success_only else 0)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                # Convert rows to AuditTrailEntry objects
                entries = []
                for row in rows:
                    entry = AuditTrailEntry(
                        audit_id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        user_id=row[2],
                        action=AuditAction(row[3]),
                        resource_type=ResourceType(row[4]),
                        resource_id=row[5],
                        severity=AuditSeverity(row[6]),
                        old_values=json.loads(row[7]) if row[7] else None,
                        new_values=json.loads(row[8]) if row[8] else None,
                        ip_address=row[9],
                        user_agent=row[10],
                        session_id=row[11],
                        correlation_id=row[12],
                        additional_context=json.loads(row[13]) if row[13] else None,
                        checksum=row[14],
                        success=bool(row[15]),
                        error_message=row[16]
                    )
                    entries.append(entry)

                return entries

            except Exception as e:
                self._logger.error(f"Failed to get audit entries: {e}")
                raise

    def verify_integrity(self, start_audit_id: Optional[str] = None,
                        end_audit_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify the integrity of audit trail entries.

        Args:
            start_audit_id: Optional starting audit ID for verification
            end_audit_id: Optional ending audit ID for verification

        Returns:
            Integrity verification results
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get entries to verify
                query = "SELECT * FROM audit_trail"
                params = []

                if start_audit_id and end_audit_id:
                    query += " WHERE audit_id BETWEEN ? AND ?"
                    params = [start_audit_id, end_audit_id]
                elif start_audit_id:
                    query += " WHERE audit_id >= ?"
                    params = [start_audit_id]
                elif end_audit_id:
                    query += " WHERE audit_id <= ?"
                    params = [end_audit_id]

                query += " ORDER BY timestamp"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                if not rows:
                    return {'status': 'NO_ENTRIES', 'verified_count': 0, 'corrupted_count': 0}

                verified_count = 0
                corrupted_entries = []
                hash_chain = ""

                for row in rows:
                    # Reconstruct entry data
                    entry_data = {
                        'audit_id': row[0],
                        'timestamp': row[1],
                        'user_id': row[2],
                        'action': row[3],
                        'resource_type': row[4],
                        'resource_id': row[5],
                        'severity': row[6],
                        'old_values': json.loads(row[7]) if row[7] else None,
                        'new_values': json.loads(row[8]) if row[8] else None,
                        'ip_address': row[9],
                        'user_agent': row[10],
                        'session_id': row[11],
                        'correlation_id': row[12],
                        'additional_context': json.loads(row[13]) if row[13] else None,
                        'success': bool(row[15]),
                        'error_message': row[16]
                    }

                    # Calculate expected checksum
                    expected_checksum = self._calculate_checksum(entry_data)
                    stored_checksum = row[14]

                    if expected_checksum == stored_checksum:
                        verified_count += 1
                        hash_chain += expected_checksum
                    else:
                        corrupted_entries.append({
                            'audit_id': row[0],
                            'timestamp': row[1],
                            'expected_checksum': expected_checksum,
                            'stored_checksum': stored_checksum
                        })

                # Calculate overall hash chain
                overall_hash = hashlib.sha256(hash_chain.encode('utf-8')).hexdigest()

                # Store verification result
                verification_id = str(uuid4())
                verification_date = datetime.now(timezone.utc).isoformat()
                status = 'VERIFIED' if len(corrupted_entries) == 0 else 'CORRUPTED'

                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO integrity_verification (
                        verification_id, verification_date, start_audit_id, end_audit_id,
                        entry_count, hash_chain, verification_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    verification_id, verification_date,
                    start_audit_id or rows[0][0], end_audit_id or rows[-1][0],
                    len(rows), overall_hash, status
                ))

                conn.commit()
                conn.close()

                result = {
                    'verification_id': verification_id,
                    'status': status,
                    'verified_count': verified_count,
                    'corrupted_count': len(corrupted_entries),
                    'total_count': len(rows),
                    'overall_hash': overall_hash,
                    'corrupted_entries': corrupted_entries
                }

                if corrupted_entries:
                    self._logger.warning(f"Integrity verification found {len(corrupted_entries)} corrupted entries")
                else:
                    self._logger.info(f"Integrity verification successful: {verified_count} entries verified")

                return result

            except Exception as e:
                self._logger.error(f"Failed to verify integrity: {e}")
                raise

    def get_audit_summaries(self, start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           user_id: Optional[str] = None,
                           action: Optional[AuditAction] = None) -> List[Dict[str, Any]]:
        """
        Get audit summaries for reporting.

        Args:
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            user_id: Optional user ID filter
            action: Optional action filter

        Returns:
            List of summary dictionaries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = "SELECT * FROM audit_summary WHERE 1=1"
                params = []

                if start_date:
                    query += " AND date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND date <= ?"
                    params.append(end_date)

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                if action:
                    query += " AND action = ?"
                    params.append(action.value)

                query += " ORDER BY date DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                summaries = []
                for row in rows:
                    summary = {
                        'summary_id': row[0],
                        'date': row[1],
                        'user_id': row[2],
                        'action': row[3],
                        'resource_type': row[4],
                        'count': row[5],
                        'success_count': row[6],
                        'failure_count': row[7],
                        'success_rate': row[6] / row[5] if row[5] > 0 else 0,
                        'first_occurrence': row[8],
                        'last_occurrence': row[9]
                    }
                    summaries.append(summary)

                return summaries

            except Exception as e:
                self._logger.error(f"Failed to get audit summaries: {e}")
                raise

    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old data based on retention policies.

        Returns:
            Cleanup statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Clean up old audit entries (keep for retention period)
                retention_cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_years * 365)
                cursor.execute("""
                    DELETE FROM audit_trail
                    WHERE timestamp < ?
                """, (retention_cutoff.isoformat(),))
                deleted_entries = cursor.rowcount

                # Clean up old summaries
                summary_cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_years * 365)
                cursor.execute("""
                    DELETE FROM audit_summary
                    WHERE date < ?
                """, (summary_cutoff.date().isoformat(),))
                deleted_summaries = cursor.rowcount

                # Clean up old verification records
                cursor.execute("""
                    DELETE FROM integrity_verification
                    WHERE verification_date < ?
                """, (summary_cutoff.isoformat(),))
                deleted_verifications = cursor.rowcount

                conn.commit()
                conn.close()

                stats = {
                    'deleted_entries': deleted_entries,
                    'deleted_summaries': deleted_summaries,
                    'deleted_verifications': deleted_verifications
                }

                self._logger.info(f"Cleanup completed: {deleted_entries} entries, {deleted_summaries} summaries, {deleted_verifications} verifications deleted")
                return stats

            except Exception as e:
                self._logger.error(f"Failed to cleanup old data: {e}")
                raise

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Database statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get audit entries count
                cursor.execute("SELECT COUNT(*) FROM audit_trail")
                entries_count = cursor.fetchone()[0]

                # Get success/failure counts
                cursor.execute("SELECT COUNT(*) FROM audit_trail WHERE success = 1")
                success_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM audit_trail WHERE success = 0")
                failure_count = cursor.fetchone()[0]

                # Get summaries count
                cursor.execute("SELECT COUNT(*) FROM audit_summary")
                summaries_count = cursor.fetchone()[0]

                # Get verification count
                cursor.execute("SELECT COUNT(*) FROM integrity_verification")
                verifications_count = cursor.fetchone()[0]

                # Get database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                db_size_mb = (page_count * page_size) / (1024 * 1024)

                # Get oldest and newest entries
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM audit_trail")
                result = cursor.fetchone()
                oldest_entry = result[0] if result[0] else None
                newest_entry = result[1] if result[1] else None

                # Get most active users
                cursor.execute("""
                    SELECT user_id, COUNT(*) as count
                    FROM audit_trail
                    GROUP BY user_id
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_users = [{'user_id': row[0], 'count': row[1]} for row in cursor.fetchall()]

                conn.close()

                return {
                    'entries_count': entries_count,
                    'success_count': success_count,
                    'failure_count': failure_count,
                    'success_rate': success_count / entries_count if entries_count > 0 else 0,
                    'summaries_count': summaries_count,
                    'verifications_count': verifications_count,
                    'database_size_mb': db_size_mb,
                    'oldest_entry': oldest_entry,
                    'newest_entry': newest_entry,
                    'retention_years': self._retention_years,
                    'top_users': top_users
                }

            except Exception as e:
                self._logger.error(f"Failed to get statistics: {e}")
                raise
