"""
Module: document_files_db
Description: Tracks original document files with hash-based deduplication
Phase: 3
Location: /src/modules/database/blob_storage_db/document_files_db/
"""

# Standard library imports
import hashlib
import json
import mimetypes
import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class DocumentFileNotFoundError(Exception):
    """Exception raised when document file is not found."""
    pass


class DocumentFileDuplicateError(Exception):
    """Exception raised when document file already exists."""
    pass


class DocumentFilesDB:
    """
    Document files database manager.
    
    Tracks original document files with hash-based deduplication.
    Provides CRUD operations for document files, deduplication logic,
    and storage optimization. Supports file versioning, metadata tracking,
    and automated cleanup of orphaned files.
    """
    
    def __init__(self, db_path: Optional[str] = None, storage_root: Optional[str] = None):
        """
        Initialize the document files database.
        
        Args:
            db_path: Path to the database file
            storage_root: Root directory for document file storage
        """
        if db_path is None:
            # Default to document files data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "document_files"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "document_files.db")
        
        if storage_root is None:
            # Default storage root for document files
            storage_root = str(Path.home() / ".mikrodok" / "storage" / "documents")
        
        self._db_path = db_path
        self._storage_root = Path(storage_root)
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._file_retention_days = 365  # Keep files for 1 year
        self._orphaned_file_retention_days = 7  # Keep orphaned files for 7 days
        self._max_file_size_mb = 500  # Maximum file size in MB
        self._supported_mime_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'text/plain',
            'text/html',
            'text/markdown',
            'application/rtf'
        }
        
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
                
                # Create document files table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL UNIQUE,
                        original_filename TEXT NOT NULL,
                        stored_filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_hash TEXT NOT NULL UNIQUE,
                        mime_type TEXT NOT NULL,
                        encoding TEXT,
                        metadata JSON,
                        status TEXT NOT NULL DEFAULT 'active',
                        reference_count INTEGER DEFAULT 0,
                        last_accessed_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create file references table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_references (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reference_id TEXT NOT NULL UNIQUE,
                        file_id TEXT NOT NULL,
                        reference_type TEXT NOT NULL,
                        reference_source TEXT NOT NULL,
                        reference_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_id) REFERENCES document_files (file_id) ON DELETE CASCADE
                    )
                """)
                
                # Create file duplicates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_duplicates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        duplicate_id TEXT NOT NULL UNIQUE,
                        primary_file_id TEXT NOT NULL,
                        duplicate_file_id TEXT NOT NULL,
                        similarity_score REAL DEFAULT 1.0,
                        duplicate_type TEXT NOT NULL,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (primary_file_id) REFERENCES document_files (file_id) ON DELETE CASCADE,
                        FOREIGN KEY (duplicate_file_id) REFERENCES document_files (file_id) ON DELETE CASCADE,
                        UNIQUE(primary_file_id, duplicate_file_id)
                    )
                """)
                
                # Create file access log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_access_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        access_id TEXT NOT NULL UNIQUE,
                        file_id TEXT NOT NULL,
                        access_type TEXT NOT NULL,
                        session_id TEXT,
                        user_agent TEXT,
                        ip_address TEXT,
                        access_duration_seconds REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_id) REFERENCES document_files (file_id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_file_hash ON document_files (file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_mime_type ON document_files (mime_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON document_files (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_created_at ON document_files (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_last_accessed ON document_files (last_accessed_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_references_file_id ON file_references (file_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_references_type ON file_references (reference_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicates_primary ON file_duplicates (primary_file_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicates_duplicate ON file_duplicates (duplicate_file_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_log_file_id ON file_access_log (file_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_log_session ON file_access_log (session_id)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_files_timestamp 
                    AFTER UPDATE ON document_files
                    BEGIN
                        UPDATE document_files SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                # Create trigger for reference count updates
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_reference_count_insert
                    AFTER INSERT ON file_references
                    BEGIN
                        UPDATE document_files 
                        SET reference_count = reference_count + 1 
                        WHERE file_id = NEW.file_id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_reference_count_delete
                    AFTER DELETE ON file_references
                    BEGIN
                        UPDATE document_files 
                        SET reference_count = reference_count - 1 
                        WHERE file_id = OLD.file_id;
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'document_files', 'file_references', 
                    'file_duplicates', 'file_access_log'
                ]

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Document files database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize document files database: {e}")
                raise
            finally:
                conn.close()

    def add_file(self, file_path: str, reference_type: str = "document",
                reference_source: str = "upload", metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new document file to the database with deduplication.

        Args:
            file_path: Path to the document file
            reference_type: Type of reference (document, attachment, etc.)
            reference_source: Source of the reference (upload, import, etc.)
            metadata: Additional file metadata

        Returns:
            File ID of the added or existing file

        Raises:
            ValueError: If file is invalid or unsupported
            DocumentFileNotFoundError: If file does not exist
        """
        file_path_obj = Path(file_path)

        # Validate file exists
        if not file_path_obj.exists():
            raise DocumentFileNotFoundError(f"File does not exist: {file_path}")

        # Get file properties
        file_size = file_path_obj.stat().st_size
        original_filename = file_path_obj.name

        # Check file size limit
        max_size_bytes = self._max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValueError(f"File size {file_size} exceeds maximum allowed size {max_size_bytes}")

        # Detect MIME type
        mime_type, encoding = mimetypes.guess_type(str(file_path_obj))
        if not mime_type:
            mime_type = 'application/octet-stream'

        # Validate MIME type
        if mime_type not in self._supported_mime_types:
            self._logger.warning(f"Unsupported MIME type: {mime_type}")

        # Calculate file hash for deduplication
        file_hash = self._calculate_file_hash(file_path_obj)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check for existing file by hash (deduplication)
                cursor.execute("SELECT file_id FROM document_files WHERE file_hash = ?", (file_hash,))
                existing = cursor.fetchone()

                if existing:
                    file_id = existing[0]
                    self._logger.info(f"File already exists (deduplicated): {file_id}")

                    # Add reference to existing file
                    self._add_file_reference(file_id, reference_type, reference_source, metadata)

                    return file_id

                # Create new file record
                file_id = str(uuid.uuid4())
                stored_filename = f"{file_id}_{original_filename}"
                stored_path = self._storage_root / stored_filename

                # Copy file to storage location
                shutil.copy2(file_path_obj, stored_path)

                # Insert file record
                cursor.execute("""
                    INSERT INTO document_files (
                        file_id, original_filename, stored_filename, file_path,
                        file_size, file_hash, mime_type, encoding, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_id, original_filename, stored_filename, str(stored_path),
                    file_size, file_hash, mime_type, encoding,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()

                # Add reference
                self._add_file_reference(file_id, reference_type, reference_source, metadata)

                self._logger.info(f"Added document file {file_id}: {original_filename}")
                return file_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add document file: {e}")
                raise
            finally:
                conn.close()

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document file by ID.

        Args:
            file_id: ID of the file to retrieve

        Returns:
            File information dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT file_id, original_filename, stored_filename, file_path,
                           file_size, file_hash, mime_type, encoding, metadata,
                           status, reference_count, last_accessed_at,
                           created_at, updated_at
                    FROM document_files WHERE file_id = ?
                """, (file_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Update last accessed time
                cursor.execute("""
                    UPDATE document_files
                    SET last_accessed_at = CURRENT_TIMESTAMP
                    WHERE file_id = ?
                """, (file_id,))
                conn.commit()

                return {
                    'file_id': row[0],
                    'original_filename': row[1],
                    'stored_filename': row[2],
                    'file_path': row[3],
                    'file_size': row[4],
                    'file_hash': row[5],
                    'mime_type': row[6],
                    'encoding': row[7],
                    'metadata': json.loads(row[8]) if row[8] else None,
                    'status': row[9],
                    'reference_count': row[10],
                    'last_accessed_at': row[11],
                    'created_at': row[12],
                    'updated_at': row[13]
                }

            except Exception as e:
                self._logger.error(f"Failed to get file {file_id}: {e}")
                return None
            finally:
                conn.close()

    def get_file_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get document file by hash.

        Args:
            file_hash: Hash of the file to retrieve

        Returns:
            File information dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT file_id FROM document_files WHERE file_hash = ?
                """, (file_hash,))

                row = cursor.fetchone()
                if not row:
                    return None

                return self.get_file(row[0])

            except Exception as e:
                self._logger.error(f"Failed to get file by hash {file_hash}: {e}")
                return None
            finally:
                conn.close()

    def delete_file(self, file_id: str, force: bool = False) -> bool:
        """
        Delete a document file from the database.

        Args:
            file_id: ID of the file to delete
            force: Whether to force deletion even with references

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            file_info = self.get_file(file_id)
            if not file_info:
                self._logger.warning(f"File not found for deletion: {file_id}")
                return False

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Check reference count
                    if file_info['reference_count'] > 0 and not force:
                        raise ValueError(f"Cannot delete file with {file_info['reference_count']} references")

                    # Delete file record (cascades to references)
                    cursor.execute("DELETE FROM document_files WHERE file_id = ?", (file_id,))

                    if cursor.rowcount == 0:
                        return False

                    conn.commit()

                    # Delete physical file
                    file_path = Path(file_info['file_path'])
                    if file_path.exists():
                        file_path.unlink()
                        self._logger.info(f"Deleted file: {file_path}")

                    self._logger.info(f"Deleted document file {file_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to delete file {file_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Error deleting file {file_id}: {e}")
            return False

    def find_duplicates(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Find duplicate files for a given file.

        Args:
            file_id: ID of the file to find duplicates for

        Returns:
            List of duplicate file information
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get file hash
                cursor.execute("SELECT file_hash FROM document_files WHERE file_id = ?", (file_id,))
                row = cursor.fetchone()
                if not row:
                    return []

                file_hash = row[0]

                # Find all files with same hash (excluding the original)
                cursor.execute("""
                    SELECT file_id, original_filename, file_size, created_at
                    FROM document_files
                    WHERE file_hash = ? AND file_id != ? AND status = 'active'
                    ORDER BY created_at
                """, (file_hash, file_id))

                duplicates = []
                for row in cursor.fetchall():
                    duplicates.append({
                        'file_id': row[0],
                        'original_filename': row[1],
                        'file_size': row[2],
                        'created_at': row[3],
                        'duplicate_type': 'exact_hash'
                    })

                return duplicates

            except Exception as e:
                self._logger.error(f"Failed to find duplicates for file {file_id}: {e}")
                return []
            finally:
                conn.close()

    def cleanup_orphaned_files(self) -> int:
        """
        Clean up orphaned files that are no longer referenced.

        Returns:
            Number of files cleaned up
        """
        cleanup_count = 0
        cutoff_date = datetime.now() - timedelta(days=self._orphaned_file_retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Find orphaned files (reference_count = 0 and old enough)
                cursor.execute("""
                    SELECT file_id, file_path FROM document_files
                    WHERE reference_count = 0 AND updated_at < ? AND status = 'active'
                """, (cutoff_date.isoformat(),))

                orphaned_files = cursor.fetchall()

                for file_id, file_path in orphaned_files:
                    try:
                        # Delete physical file
                        file_path_obj = Path(file_path)
                        if file_path_obj.exists():
                            file_path_obj.unlink()
                            self._logger.info(f"Deleted orphaned file: {file_path}")

                        # Update status to orphaned
                        cursor.execute("""
                            UPDATE document_files
                            SET status = 'orphaned'
                            WHERE file_id = ?
                        """, (file_id,))
                        cleanup_count += 1

                    except Exception as e:
                        self._logger.error(f"Failed to cleanup orphaned file {file_id}: {e}")

                conn.commit()

                if cleanup_count > 0:
                    self._logger.info(f"Cleaned up {cleanup_count} orphaned files")

                return cleanup_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup orphaned files: {e}")
                return 0
            finally:
                conn.close()

    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics for document files.

        Returns:
            Dictionary containing storage statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get total count and size
                cursor.execute("""
                    SELECT COUNT(*), SUM(file_size), AVG(file_size)
                    FROM document_files WHERE status = 'active'
                """)
                total_count, total_size, avg_size = cursor.fetchone()

                # Get count by MIME type
                cursor.execute("""
                    SELECT mime_type, COUNT(*), SUM(file_size)
                    FROM document_files WHERE status = 'active'
                    GROUP BY mime_type
                """)
                mime_stats = {}
                for mime_type, count, size in cursor.fetchall():
                    mime_stats[mime_type] = {
                        'count': count,
                        'total_size': size or 0
                    }

                # Get reference statistics
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN reference_count = 0 THEN 1 ELSE 0 END) as orphaned,
                        SUM(CASE WHEN reference_count = 1 THEN 1 ELSE 0 END) as single_ref,
                        SUM(CASE WHEN reference_count > 1 THEN 1 ELSE 0 END) as multi_ref
                    FROM document_files WHERE status = 'active'
                """)
                ref_stats = cursor.fetchone()

                return {
                    'total_files': total_count or 0,
                    'total_size_bytes': total_size or 0,
                    'average_size_bytes': avg_size or 0,
                    'files_by_mime_type': mime_stats,
                    'reference_statistics': {
                        'orphaned_files': ref_stats[0] or 0,
                        'single_reference': ref_stats[1] or 0,
                        'multiple_references': ref_stats[2] or 0
                    },
                    'storage_root': str(self._storage_root)
                }

            except Exception as e:
                self._logger.error(f"Failed to get storage statistics: {e}")
                return {}
            finally:
                conn.close()

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self._logger.error(f"Failed to calculate hash for {file_path}: {e}")
            raise

    def _add_file_reference(self, file_id: str, reference_type: str,
                           reference_source: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a reference to a file."""
        reference_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO file_references (
                        reference_id, file_id, reference_type, reference_source, reference_metadata
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    reference_id, file_id, reference_type, reference_source,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
                return reference_id
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add file reference: {e}")
                raise
            finally:
                conn.close()

    def log_file_access(self, file_id: str, access_type: str, session_id: Optional[str] = None,
                       user_agent: Optional[str] = None, ip_address: Optional[str] = None,
                       duration: Optional[float] = None) -> None:
        """Log file access for analytics."""
        access_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO file_access_log (
                        access_id, file_id, access_type, session_id,
                        user_agent, ip_address, access_duration_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (access_id, file_id, access_type, session_id, user_agent, ip_address, duration))
                conn.commit()
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log file access: {e}")
            finally:
                conn.close()
