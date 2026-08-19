"""
Module: document_dao_db
Description: Manages document metadata, processing status, and file references with deduplication
Phase: 3
Location: /src/modules/database/document_repository_db/document_dao_db/
"""

# Standard library imports
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class DocumentDAODB:
    """
    Document Data Access Object database manager.
    
    Provides comprehensive data access layer for document CRUD operations with
    transaction support, deduplication management, and metadata handling. Implements
    repository pattern for document persistence with optimized queries and batch operations.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the document DAO database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to document repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "document_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "document_dao.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._document_retention_days = 365  # Keep documents for 1 year
        self._failed_document_retention_days = 30  # Keep failed documents for 30 days
        self._max_documents_per_collection = 10000  # Maximum documents per collection
        self._batch_size = 100  # Batch size for bulk operations
        
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
                
                # Create documents table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT NOT NULL UNIQUE,
                        collection_id TEXT,
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_hash TEXT NOT NULL UNIQUE,
                        mime_type TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        processing_started_at TIMESTAMP,
                        processing_completed_at TIMESTAMP,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'archived'))
                    )
                """)
                
                # Create document versions table for version control
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        version_number INTEGER NOT NULL,
                        file_path TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        changes_description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE
                    )
                """)
                
                # Create document relationships table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_relationships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        relationship_id TEXT NOT NULL UNIQUE,
                        source_document_id TEXT NOT NULL,
                        target_document_id TEXT NOT NULL,
                        relationship_type TEXT NOT NULL,
                        strength REAL DEFAULT 1.0,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (source_document_id) REFERENCES documents (document_id) ON DELETE CASCADE,
                        FOREIGN KEY (target_document_id) REFERENCES documents (document_id) ON DELETE CASCADE,
                        CONSTRAINT chk_relationship_type CHECK (relationship_type IN ('similar', 'duplicate', 'reference', 'derived', 'related'))
                    )
                """)
                
                # Create document tags table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        tag_name TEXT NOT NULL,
                        tag_value TEXT,
                        tag_type TEXT NOT NULL DEFAULT 'user',
                        confidence REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE,
                        CONSTRAINT chk_tag_type CHECK (tag_type IN ('user', 'auto', 'system'))
                    )
                """)
                
                # Create document access log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_access_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        access_type TEXT NOT NULL,
                        access_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id TEXT,
                        session_id TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        metadata JSON,
                        FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE,
                        CONSTRAINT chk_access_type CHECK (access_type IN ('read', 'write', 'delete', 'download', 'preview'))
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents (collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents (file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents (updated_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_relationships_source ON document_relationships (source_document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_relationships_target ON document_relationships (target_document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_tags_document_id ON document_tags (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_tags_name ON document_tags (tag_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_access_log_document_id ON document_access_log (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_access_log_timestamp ON document_access_log (access_timestamp)")
                
                conn.commit()
                self._logger.info("Document DAO database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize document DAO database: {e}")
                raise
            finally:
                conn.close()

    def create_document(self, filename: str, file_path: str, file_size: int,
                       file_hash: str, mime_type: Optional[str] = None,
                       collection_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new document record.

        Args:
            filename: Original filename
            file_path: Path to the document file
            file_size: Size of the file in bytes
            file_hash: SHA256 hash of the file content
            mime_type: MIME type of the document
            collection_id: Collection identifier
            metadata: Additional document metadata

        Returns:
            Document ID of the created document

        Raises:
            ValueError: If document with same hash already exists
        """
        document_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check for duplicate by hash
                cursor.execute("SELECT document_id FROM documents WHERE file_hash = ?", (file_hash,))
                existing = cursor.fetchone()
                if existing:
                    raise ValueError(f"Document with hash {file_hash} already exists: {existing[0]}")

                # Insert new document
                cursor.execute("""
                    INSERT INTO documents (
                        document_id, collection_id, filename, file_path, file_size,
                        file_hash, mime_type, metadata, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (
                    document_id,
                    collection_id,
                    filename,
                    file_path,
                    file_size,
                    file_hash,
                    mime_type,
                    json.dumps(metadata) if metadata else None
                ))

                # Log access
                self._log_document_access(cursor, document_id, 'write')

                conn.commit()
                self._logger.info(f"Created document {document_id}: {filename}")
                return document_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create document {filename}: {e}")
                raise
            finally:
                conn.close()

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT document_id, collection_id, filename, file_path, file_size,
                           file_hash, mime_type, status, processing_started_at,
                           processing_completed_at, error_message, retry_count,
                           metadata, created_at, updated_at
                    FROM documents WHERE document_id = ?
                """, (document_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Log access
                self._log_document_access(cursor, document_id, 'read')
                conn.commit()

                return {
                    'document_id': row[0],
                    'collection_id': row[1],
                    'filename': row[2],
                    'file_path': row[3],
                    'file_size': row[4],
                    'file_hash': row[5],
                    'mime_type': row[6],
                    'status': row[7],
                    'processing_started_at': row[8],
                    'processing_completed_at': row[9],
                    'error_message': row[10],
                    'retry_count': row[11],
                    'metadata': json.loads(row[12]) if row[12] else None,
                    'created_at': row[13],
                    'updated_at': row[14]
                }

            except Exception as e:
                self._logger.error(f"Failed to get document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def update_document_status(self, document_id: str, status: str,
                              error_message: Optional[str] = None) -> bool:
        """
        Update document processing status.

        Args:
            document_id: Document identifier
            status: New status ('pending', 'processing', 'completed', 'failed', 'archived')
            error_message: Error message if status is 'failed'

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update status and timestamps
                if status == 'processing':
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, processing_started_at = ?, updated_at = ?
                        WHERE document_id = ?
                    """, (status, datetime.now(timezone.utc).isoformat(),
                          datetime.now(timezone.utc).isoformat(), document_id))
                elif status in ['completed', 'failed']:
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, processing_completed_at = ?, error_message = ?, updated_at = ?
                        WHERE document_id = ?
                    """, (status, datetime.now(timezone.utc).isoformat(),
                          error_message, datetime.now(timezone.utc).isoformat(), document_id))
                else:
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, error_message = ?, updated_at = ?
                        WHERE document_id = ?
                    """, (status, error_message, datetime.now(timezone.utc).isoformat(), document_id))

                # Log access
                self._log_document_access(cursor, document_id, 'write')

                conn.commit()
                self._logger.info(f"Updated document {document_id} status to {status}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update document {document_id} status: {e}")
                raise
            finally:
                conn.close()

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document record.

        Args:
            document_id: Document identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Log access before deletion
                self._log_document_access(cursor, document_id, 'delete')

                # Delete document (cascades to related tables)
                cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

                conn.commit()
                self._logger.info(f"Deleted document {document_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def list_documents(self, collection_id: Optional[str] = None,
                      status: Optional[str] = None,
                      limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List documents with optional filtering.

        Args:
            collection_id: Filter by collection ID
            status: Filter by status
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of document dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT document_id, collection_id, filename, file_path, file_size,
                           file_hash, mime_type, status, processing_started_at,
                           processing_completed_at, error_message, retry_count,
                           metadata, created_at, updated_at
                    FROM documents
                """
                params = []

                conditions = []
                if collection_id:
                    conditions.append("collection_id = ?")
                    params.append(collection_id)
                if status:
                    conditions.append("status = ?")
                    params.append(status)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                documents = []
                for row in rows:
                    documents.append({
                        'document_id': row[0],
                        'collection_id': row[1],
                        'filename': row[2],
                        'file_path': row[3],
                        'file_size': row[4],
                        'file_hash': row[5],
                        'mime_type': row[6],
                        'status': row[7],
                        'processing_started_at': row[8],
                        'processing_completed_at': row[9],
                        'error_message': row[10],
                        'retry_count': row[11],
                        'metadata': json.loads(row[12]) if row[12] else None,
                        'created_at': row[13],
                        'updated_at': row[14]
                    })

                return documents

            except Exception as e:
                self._logger.error(f"Failed to list documents: {e}")
                raise
            finally:
                conn.close()

    def find_duplicates(self, file_hash: str) -> List[str]:
        """
        Find documents with the same file hash.

        Args:
            file_hash: File hash to search for

        Returns:
            List of document IDs with matching hash
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT document_id FROM documents WHERE file_hash = ?", (file_hash,))
                rows = cursor.fetchall()
                return [row[0] for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to find duplicates for hash {file_hash}: {e}")
                raise
            finally:
                conn.close()

    def add_document_tag(self, document_id: str, tag_name: str,
                        tag_value: Optional[str] = None,
                        tag_type: str = 'user',
                        confidence: float = 1.0,
                        created_by: Optional[str] = None) -> str:
        """
        Add a tag to a document.

        Args:
            document_id: Document identifier
            tag_name: Name of the tag
            tag_value: Optional tag value
            tag_type: Type of tag ('user', 'auto', 'system')
            confidence: Confidence score for the tag
            created_by: User who created the tag

        Returns:
            Tag ID
        """
        tag_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO document_tags (
                        tag_id, document_id, tag_name, tag_value, tag_type,
                        confidence, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (tag_id, document_id, tag_name, tag_value, tag_type, confidence, created_by))

                conn.commit()
                self._logger.info(f"Added tag {tag_name} to document {document_id}")
                return tag_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add tag to document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_document_tags(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all tags for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of tag dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT tag_id, tag_name, tag_value, tag_type, confidence,
                           created_at, created_by
                    FROM document_tags WHERE document_id = ?
                    ORDER BY created_at DESC
                """, (document_id,))

                rows = cursor.fetchall()
                tags = []
                for row in rows:
                    tags.append({
                        'tag_id': row[0],
                        'tag_name': row[1],
                        'tag_value': row[2],
                        'tag_type': row[3],
                        'confidence': row[4],
                        'created_at': row[5],
                        'created_by': row[6]
                    })

                return tags

            except Exception as e:
                self._logger.error(f"Failed to get tags for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def create_document_relationship(self, source_document_id: str,
                                   target_document_id: str,
                                   relationship_type: str,
                                   strength: float = 1.0,
                                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a relationship between two documents.

        Args:
            source_document_id: Source document ID
            target_document_id: Target document ID
            relationship_type: Type of relationship
            strength: Relationship strength (0.0-1.0)
            metadata: Additional relationship metadata

        Returns:
            Relationship ID
        """
        relationship_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO document_relationships (
                        relationship_id, source_document_id, target_document_id,
                        relationship_type, strength, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (relationship_id, source_document_id, target_document_id,
                      relationship_type, strength, json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Created relationship {relationship_type} between {source_document_id} and {target_document_id}")
                return relationship_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create document relationship: {e}")
                raise
            finally:
                conn.close()

    def get_document_statistics(self, collection_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get document statistics.

        Args:
            collection_id: Optional collection ID to filter by

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Base query conditions
                where_clause = ""
                params = []
                if collection_id:
                    where_clause = "WHERE collection_id = ?"
                    params.append(collection_id)

                # Total documents
                cursor.execute(f"SELECT COUNT(*) FROM documents {where_clause}", params)
                total_documents = cursor.fetchone()[0]

                # Documents by status
                cursor.execute(f"""
                    SELECT status, COUNT(*) FROM documents {where_clause}
                    GROUP BY status
                """, params)
                status_counts = dict(cursor.fetchall())

                # Total file size
                cursor.execute(f"SELECT SUM(file_size) FROM documents {where_clause}", params)
                total_size = cursor.fetchone()[0] or 0

                # Average file size
                cursor.execute(f"SELECT AVG(file_size) FROM documents {where_clause}", params)
                avg_size = cursor.fetchone()[0] or 0

                # Documents by MIME type
                cursor.execute(f"""
                    SELECT mime_type, COUNT(*) FROM documents {where_clause}
                    GROUP BY mime_type
                """, params)
                mime_type_counts = dict(cursor.fetchall())

                return {
                    'total_documents': total_documents,
                    'status_counts': status_counts,
                    'total_size_bytes': total_size,
                    'average_size_bytes': avg_size,
                    'mime_type_counts': mime_type_counts
                }

            except Exception as e:
                self._logger.error(f"Failed to get document statistics: {e}")
                raise
            finally:
                conn.close()

    def _log_document_access(self, cursor: sqlite3.Cursor, document_id: str,
                           access_type: str, user_id: Optional[str] = None,
                           session_id: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Log document access for audit trail.

        Args:
            cursor: Database cursor
            document_id: Document identifier
            access_type: Type of access
            user_id: User identifier
            session_id: Session identifier
            metadata: Additional metadata
        """
        log_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO document_access_log (
                log_id, document_id, access_type, user_id, session_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (log_id, document_id, access_type, user_id, session_id,
              json.dumps(metadata) if metadata else None))

    def cleanup_old_documents(self) -> int:
        """
        Clean up old documents based on retention policies.

        Returns:
            Number of documents cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate cutoff dates
                document_cutoff = datetime.now(timezone.utc) - timedelta(days=self._document_retention_days)
                failed_cutoff = datetime.now(timezone.utc) - timedelta(days=self._failed_document_retention_days)

                # Delete old failed documents
                cursor.execute("""
                    DELETE FROM documents
                    WHERE status = 'failed' AND created_at < ?
                """, (failed_cutoff.isoformat(),))

                failed_deleted = cursor.rowcount

                # Archive old completed documents
                cursor.execute("""
                    UPDATE documents
                    SET status = 'archived', updated_at = ?
                    WHERE status = 'completed' AND created_at < ?
                """, (datetime.now(timezone.utc).isoformat(), document_cutoff.isoformat()))

                archived_count = cursor.rowcount

                conn.commit()
                total_cleaned = failed_deleted + archived_count
                self._logger.info(f"Cleaned up {total_cleaned} documents ({failed_deleted} deleted, {archived_count} archived)")
                return total_cleaned

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old documents: {e}")
                raise
            finally:
                conn.close()
