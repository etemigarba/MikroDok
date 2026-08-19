"""
Module: state_snapshots_db
Description: Stores application state snapshots for recovery, maintains state history with timestamps
Phase: 1
Location: /src/modules/database/app_state_db/state_snapshots_db/state_snapshots_db.py
"""

# Standard library imports
import sqlite3
import json
import os
import hashlib
import gzip
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime, timezone
import threading


class StateSnapshotsDB:
    """
    State snapshots database manager.
    
    Handles storage and retrieval of application state snapshots for crash recovery,
    maintains state history with timestamps, and provides efficient snapshot management.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the state snapshots database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to user data directory
            data_dir = Path.home() / ".mikrodok" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "state_snapshots.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._max_snapshots = 100  # Maximum number of snapshots to keep
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Create state snapshots table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS state_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id TEXT NOT NULL UNIQUE,
                        state_data TEXT NOT NULL,
                        metadata TEXT,
                        checksum TEXT,
                        format TEXT DEFAULT 'JSON',
                        compressed BOOLEAN DEFAULT 0,
                        encrypted BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        size_bytes INTEGER,
                        description TEXT
                    )
                """)
                
                # Create index for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_created_at 
                    ON state_snapshots(created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_snapshot_id 
                    ON state_snapshots(snapshot_id)
                """)
                
                # Create snapshot metadata table for additional information
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS snapshot_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (snapshot_id) REFERENCES state_snapshots(snapshot_id) ON DELETE CASCADE,
                        UNIQUE(snapshot_id, key)
                    )
                """)
                
                conn.commit()
            finally:
                conn.close()
    
    def save_snapshot(self, snapshot_data: Dict[str, Any]) -> bool:
        """
        Save a state snapshot to the database.
        
        Args:
            snapshot_data: Dictionary containing snapshot information
                - snapshot_id: Unique identifier for the snapshot
                - state_data: The actual state data (as JSON string or dict)
                - metadata: Optional metadata dictionary
                - checksum: Optional checksum for integrity verification
                - format: Data format (default: 'JSON')
                - compressed: Whether data is compressed
                - encrypted: Whether data is encrypted
                - description: Optional description
                
        Returns:
            bool: True if snapshot was saved successfully
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Prepare data
                    snapshot_id = snapshot_data['snapshot_id']
                    state_data = snapshot_data['state_data']
                    
                    # Convert state_data to JSON string if it's a dict
                    if isinstance(state_data, dict):
                        state_data = json.dumps(state_data)
                    
                    # Calculate size
                    size_bytes = len(state_data.encode('utf-8'))
                    
                    # Generate checksum if not provided
                    checksum = snapshot_data.get('checksum')
                    if not checksum:
                        checksum = hashlib.sha256(state_data.encode('utf-8')).hexdigest()
                    
                    # Prepare metadata
                    metadata = snapshot_data.get('metadata', {})
                    metadata_json = json.dumps(metadata) if isinstance(metadata, dict) else metadata
                    
                    # Insert snapshot
                    cursor.execute("""
                        INSERT OR REPLACE INTO state_snapshots 
                        (snapshot_id, state_data, metadata, checksum, format, compressed, 
                         encrypted, size_bytes, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        state_data,
                        metadata_json,
                        checksum,
                        snapshot_data.get('format', 'JSON'),
                        snapshot_data.get('compressed', False),
                        snapshot_data.get('encrypted', False),
                        size_bytes,
                        snapshot_data.get('description', '')
                    ))
                    
                    # Save additional metadata if provided
                    if isinstance(metadata, dict):
                        for key, value in metadata.items():
                            cursor.execute("""
                                INSERT OR REPLACE INTO snapshot_metadata 
                                (snapshot_id, key, value)
                                VALUES (?, ?, ?)
                            """, (snapshot_id, key, json.dumps(value)))
                    
                    conn.commit()
                    
                    # Clean up old snapshots if we exceed the limit
                    self._cleanup_old_snapshots(cursor, conn)
                    
                    return True
                    
                except Exception as e:
                    conn.rollback()
                    raise e
                finally:
                    conn.close()
                    
        except Exception as e:
            print(f"Error saving snapshot: {e}")
            return False
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific snapshot by ID.
        
        Args:
            snapshot_id: Unique identifier for the snapshot
            
        Returns:
            Dictionary containing snapshot data or None if not found
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT snapshot_id, state_data, metadata, checksum, format, 
                               compressed, encrypted, created_at, size_bytes, description
                        FROM state_snapshots 
                        WHERE snapshot_id = ?
                    """, (snapshot_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        return {
                            'snapshot_id': row[0],
                            'state_data': row[1],
                            'metadata': row[2],
                            'checksum': row[3],
                            'format': row[4],
                            'compressed': bool(row[5]),
                            'encrypted': bool(row[6]),
                            'created_at': row[7],
                            'size_bytes': row[8],
                            'description': row[9]
                        }
                    return None
                finally:
                    conn.close()
                    
        except Exception as e:
            print(f"Error retrieving snapshot: {e}")
            return None
    
    def list_snapshots(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List all available snapshots, ordered by creation time (newest first).
        
        Args:
            limit: Maximum number of snapshots to return
            
        Returns:
            List of snapshot dictionaries
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    query = """
                        SELECT snapshot_id, metadata, checksum, format, compressed, 
                               encrypted, created_at, size_bytes, description
                        FROM state_snapshots 
                        ORDER BY created_at DESC
                    """
                    
                    if limit:
                        query += f" LIMIT {limit}"
                    
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    
                    snapshots = []
                    for row in rows:
                        snapshots.append({
                            'snapshot_id': row[0],
                            'metadata': row[1],
                            'checksum': row[2],
                            'format': row[3],
                            'compressed': bool(row[4]),
                            'encrypted': bool(row[5]),
                            'created_at': row[6],
                            'size_bytes': row[7],
                            'description': row[8]
                        })
                    
                    return snapshots
                finally:
                    conn.close()
                    
        except Exception as e:
            print(f"Error listing snapshots: {e}")
            return []
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        Delete a specific snapshot.
        
        Args:
            snapshot_id: Unique identifier for the snapshot to delete
            
        Returns:
            bool: True if snapshot was deleted successfully
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM state_snapshots WHERE snapshot_id = ?", (snapshot_id,))
                    conn.commit()
                    return cursor.rowcount > 0
                finally:
                    conn.close()
                    
        except Exception as e:
            print(f"Error deleting snapshot: {e}")
            return False

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent snapshot.

        Returns:
            Dictionary containing the latest snapshot data or None if no snapshots exist
        """
        snapshots = self.list_snapshots(limit=1)
        return snapshots[0] if snapshots else None

    def verify_snapshot_integrity(self, snapshot_id: str) -> bool:
        """
        Verify the integrity of a snapshot using its checksum.

        Args:
            snapshot_id: Unique identifier for the snapshot

        Returns:
            bool: True if snapshot integrity is verified
        """
        try:
            snapshot = self.get_snapshot(snapshot_id)
            if not snapshot:
                return False

            # Calculate checksum of current data
            state_data = snapshot['state_data']
            calculated_checksum = hashlib.sha256(state_data.encode('utf-8')).hexdigest()

            # Compare with stored checksum
            stored_checksum = snapshot.get('checksum')
            return calculated_checksum == stored_checksum

        except Exception as e:
            print(f"Error verifying snapshot integrity: {e}")
            return False

    def get_snapshots_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get snapshots within a specific date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            List of snapshot dictionaries within the date range
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT snapshot_id, metadata, checksum, format, compressed,
                               encrypted, created_at, size_bytes, description
                        FROM state_snapshots
                        WHERE created_at BETWEEN ? AND ?
                        ORDER BY created_at DESC
                    """, (start_date.isoformat(), end_date.isoformat()))

                    rows = cursor.fetchall()
                    snapshots = []
                    for row in rows:
                        snapshots.append({
                            'snapshot_id': row[0],
                            'metadata': row[1],
                            'checksum': row[2],
                            'format': row[3],
                            'compressed': bool(row[4]),
                            'encrypted': bool(row[5]),
                            'created_at': row[6],
                            'size_bytes': row[7],
                            'description': row[8]
                        })

                    return snapshots
                finally:
                    conn.close()

        except Exception as e:
            print(f"Error getting snapshots by date range: {e}")
            return []

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics including total snapshots, size, etc.

        Returns:
            Dictionary containing database statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get total count
                    cursor.execute("SELECT COUNT(*) FROM state_snapshots")
                    total_count = cursor.fetchone()[0]

                    # Get total size
                    cursor.execute("SELECT SUM(size_bytes) FROM state_snapshots")
                    total_size = cursor.fetchone()[0] or 0

                    # Get oldest and newest snapshots
                    cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM state_snapshots")
                    date_range = cursor.fetchone()

                    # Get database file size
                    db_file_size = os.path.getsize(self._db_path) if os.path.exists(self._db_path) else 0

                    return {
                        'total_snapshots': total_count,
                        'total_data_size_bytes': total_size,
                        'database_file_size_bytes': db_file_size,
                        'oldest_snapshot': date_range[0],
                        'newest_snapshot': date_range[1],
                        'max_snapshots_limit': self._max_snapshots
                    }
                finally:
                    conn.close()

        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {}

    def cleanup_old_snapshots(self, keep_count: Optional[int] = None) -> int:
        """
        Clean up old snapshots, keeping only the most recent ones.

        Args:
            keep_count: Number of snapshots to keep (uses default if None)

        Returns:
            Number of snapshots deleted
        """
        if keep_count is None:
            keep_count = self._max_snapshots

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    return self._cleanup_old_snapshots(cursor, conn, keep_count)
                finally:
                    conn.close()

        except Exception as e:
            print(f"Error cleaning up old snapshots: {e}")
            return 0

    def _cleanup_old_snapshots(self, cursor: sqlite3.Cursor, conn: sqlite3.Connection,
                              keep_count: Optional[int] = None) -> int:
        """
        Internal method to clean up old snapshots.

        Args:
            cursor: Database cursor
            conn: Database connection
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots deleted
        """
        if keep_count is None:
            keep_count = self._max_snapshots

        try:
            # Get count of current snapshots
            cursor.execute("SELECT COUNT(*) FROM state_snapshots")
            current_count = cursor.fetchone()[0]

            if current_count <= keep_count:
                return 0

            # Delete oldest snapshots beyond the limit
            delete_count = current_count - keep_count
            cursor.execute("""
                DELETE FROM state_snapshots
                WHERE id IN (
                    SELECT id FROM state_snapshots
                    ORDER BY created_at ASC
                    LIMIT ?
                )
            """, (delete_count,))

            conn.commit()
            return cursor.rowcount

        except Exception as e:
            print(f"Error in cleanup operation: {e}")
            return 0

    def export_snapshots(self, output_path: str, snapshot_ids: Optional[List[str]] = None) -> bool:
        """
        Export snapshots to a JSON file for backup purposes.

        Args:
            output_path: Path to the output JSON file
            snapshot_ids: List of specific snapshot IDs to export (exports all if None)

        Returns:
            bool: True if export was successful
        """
        try:
            snapshots_data = []

            if snapshot_ids:
                # Export specific snapshots
                for snapshot_id in snapshot_ids:
                    snapshot = self.get_snapshot(snapshot_id)
                    if snapshot:
                        snapshots_data.append(snapshot)
            else:
                # Export all snapshots
                with self._lock:
                    conn = sqlite3.connect(self._db_path)
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT snapshot_id, state_data, metadata, checksum, format,
                                   compressed, encrypted, created_at, size_bytes, description
                            FROM state_snapshots
                            ORDER BY created_at DESC
                        """)

                        rows = cursor.fetchall()
                        for row in rows:
                            snapshots_data.append({
                                'snapshot_id': row[0],
                                'state_data': row[1],
                                'metadata': row[2],
                                'checksum': row[3],
                                'format': row[4],
                                'compressed': bool(row[5]),
                                'encrypted': bool(row[6]),
                                'created_at': row[7],
                                'size_bytes': row[8],
                                'description': row[9]
                            })
                    finally:
                        conn.close()

            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'snapshots': snapshots_data
                }, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Error exporting snapshots: {e}")
            return False

    def import_snapshots(self, input_path: str, overwrite_existing: bool = False) -> int:
        """
        Import snapshots from a JSON file.

        Args:
            input_path: Path to the input JSON file
            overwrite_existing: Whether to overwrite existing snapshots with same ID

        Returns:
            Number of snapshots imported
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            snapshots = data.get('snapshots', [])
            imported_count = 0

            for snapshot in snapshots:
                # Check if snapshot already exists
                if not overwrite_existing and self.get_snapshot(snapshot['snapshot_id']):
                    continue

                # Import the snapshot
                if self.save_snapshot(snapshot):
                    imported_count += 1

            return imported_count

        except Exception as e:
            print(f"Error importing snapshots: {e}")
            return 0
