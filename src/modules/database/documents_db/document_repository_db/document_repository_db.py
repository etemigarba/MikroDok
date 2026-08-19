"""
Module: document_repository_db
Description: Data access layer for document CRUD operations with transaction support
Phase: 3
Location: /src/modules/database/documents_db/document_repository_db/
"""

# Standard library imports
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class DocumentRepositoryDB:
    """
    Document repository database manager.
    
    Handles document metadata persistence, processing status tracking,
    and file references with deduplication support. Provides CRUD operations
    with transaction support and referential integrity.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the document repository database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to documents data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "documents"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "document_repository.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._failed_document_retention_days = 30  # Keep failed documents for 30 days
        self._processed_document_retention_days = 365  # Keep processed documents for 1 year
        
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
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_hash TEXT NOT NULL,
                        mime_type TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        processing_started_at TIMESTAMP,
                        processing_completed_at TIMESTAMP,
                        error_message TEXT,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create document processing history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_processing_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        history_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        processing_stage TEXT,
                        progress_percent REAL DEFAULT 0.0,
                        error_details TEXT,
                        processing_time_seconds REAL,
                        resource_usage JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE
                    )
                """)
                
                # Create document collections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_id TEXT NOT NULL UNIQUE,
                        collection_name TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create document collection mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_collection_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mapping_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        collection_id TEXT NOT NULL,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE,
                        FOREIGN KEY (collection_id) REFERENCES document_collections (collection_id) ON DELETE CASCADE,
                        UNIQUE(document_id, collection_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents (file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_history_document_id ON document_processing_history (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_history_status ON document_processing_history (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_mappings_document_id ON document_collection_mappings (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_mappings_collection_id ON document_collection_mappings (collection_id)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_documents_timestamp 
                    AFTER UPDATE ON documents
                    BEGIN
                        UPDATE documents SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_collections_timestamp 
                    AFTER UPDATE ON document_collections
                    BEGIN
                        UPDATE document_collections SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = ['documents', 'document_processing_history', 'document_collections', 'document_collection_mappings']

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Document repository database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize document repository database: {e}")
                raise
            finally:
                conn.close()
    
    def add_document(self, filename: str, file_path: str, file_size: int, 
                    file_hash: str, mime_type: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new document to the repository.
        
        Args:
            filename: Original filename
            file_path: Path to the document file
            file_size: Size of the file in bytes
            file_hash: SHA256 hash of the file content
            mime_type: MIME type of the document
            metadata: Additional document metadata
            
        Returns:
            Document ID of the added document
            
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
                        document_id, filename, file_path, file_size, file_hash,
                        mime_type, metadata, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (
                    document_id,
                    filename,
                    file_path,
                    file_size,
                    file_hash,
                    mime_type,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                self._logger.info(f"Added document {document_id}: {filename}")
                return document_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add document {filename}: {e}")
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
                    SELECT document_id, filename, file_path, file_size, file_hash,
                           mime_type, status, processing_started_at, processing_completed_at,
                           error_message, metadata, created_at, updated_at
                    FROM documents WHERE document_id = ?
                """, (document_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'document_id': row[0],
                    'filename': row[1],
                    'file_path': row[2],
                    'file_size': row[3],
                    'file_hash': row[4],
                    'mime_type': row[5],
                    'status': row[6],
                    'processing_started_at': row[7],
                    'processing_completed_at': row[8],
                    'error_message': row[9],
                    'metadata': json.loads(row[10]) if row[10] else None,
                    'created_at': row[11],
                    'updated_at': row[12]
                }

            except Exception as e:
                self._logger.error(f"Failed to get document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def update_document_status(self, document_id: str, status: str,
                              error_message: Optional[str] = None,
                              processing_time: Optional[float] = None) -> bool:
        """
        Update document processing status.

        Args:
            document_id: Document identifier
            status: New status (pending, processing, completed, failed)
            error_message: Error message if status is failed
            processing_time: Processing time in seconds

        Returns:
            True if update was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update document status
                if status == 'processing':
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, processing_started_at = CURRENT_TIMESTAMP,
                            error_message = NULL
                        WHERE document_id = ?
                    """, (status, document_id))
                elif status in ['completed', 'failed']:
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, processing_completed_at = CURRENT_TIMESTAMP,
                            error_message = ?
                        WHERE document_id = ?
                    """, (status, error_message, document_id))
                else:
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, error_message = ?
                        WHERE document_id = ?
                    """, (status, error_message, document_id))

                # Add to processing history
                history_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO document_processing_history (
                        history_id, document_id, status, processing_time_seconds
                    ) VALUES (?, ?, ?, ?)
                """, (history_id, document_id, status, processing_time))

                conn.commit()

                if cursor.rowcount > 0:
                    self._logger.info(f"Updated document {document_id} status to {status}")
                    return True
                else:
                    self._logger.warning(f"Document {document_id} not found for status update")
                    return False

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update document status {document_id}: {e}")
                raise
            finally:
                conn.close()

    def list_documents(self, status: Optional[str] = None,
                      limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List documents with optional filtering.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of document data dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if status:
                    cursor.execute("""
                        SELECT document_id, filename, file_path, file_size, file_hash,
                               mime_type, status, processing_started_at, processing_completed_at,
                               error_message, metadata, created_at, updated_at
                        FROM documents
                        WHERE status = ?
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                    """, (status, limit, offset))
                else:
                    cursor.execute("""
                        SELECT document_id, filename, file_path, file_size, file_hash,
                               mime_type, status, processing_started_at, processing_completed_at,
                               error_message, metadata, created_at, updated_at
                        FROM documents
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                    """, (limit, offset))

                rows = cursor.fetchall()
                documents = []

                for row in rows:
                    documents.append({
                        'document_id': row[0],
                        'filename': row[1],
                        'file_path': row[2],
                        'file_size': row[3],
                        'file_hash': row[4],
                        'mime_type': row[5],
                        'status': row[6],
                        'processing_started_at': row[7],
                        'processing_completed_at': row[8],
                        'error_message': row[9],
                        'metadata': json.loads(row[10]) if row[10] else None,
                        'created_at': row[11],
                        'updated_at': row[12]
                    })

                return documents

            except Exception as e:
                self._logger.error(f"Failed to list documents: {e}")
                raise
            finally:
                conn.close()

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the repository.

        Args:
            document_id: Document identifier

        Returns:
            True if deletion was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    self._logger.info(f"Deleted document {document_id}")
                    return True
                else:
                    self._logger.warning(f"Document {document_id} not found for deletion")
                    return False

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def find_duplicate_by_hash(self, file_hash: str) -> Optional[str]:
        """
        Find document with matching hash for deduplication.

        Args:
            file_hash: SHA256 hash to search for

        Returns:
            Document ID if duplicate found, None otherwise
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT document_id FROM documents WHERE file_hash = ?", (file_hash,))
                row = cursor.fetchone()
                return row[0] if row else None

            except Exception as e:
                self._logger.error(f"Failed to find duplicate by hash {file_hash}: {e}")
                raise
            finally:
                conn.close()

    def get_processing_history(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get processing history for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of processing history entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT history_id, status, processing_stage, progress_percent,
                           error_details, processing_time_seconds, resource_usage, created_at
                    FROM document_processing_history
                    WHERE document_id = ?
                    ORDER BY created_at DESC
                """, (document_id,))

                rows = cursor.fetchall()
                history = []

                for row in rows:
                    history.append({
                        'history_id': row[0],
                        'status': row[1],
                        'processing_stage': row[2],
                        'progress_percent': row[3],
                        'error_details': row[4],
                        'processing_time_seconds': row[5],
                        'resource_usage': json.loads(row[6]) if row[6] else None,
                        'created_at': row[7]
                    })

                return history

            except Exception as e:
                self._logger.error(f"Failed to get processing history for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def create_collection(self, collection_name: str,
                         description: Optional[str] = None) -> str:
        """
        Create a new document collection.

        Args:
            collection_name: Name of the collection
            description: Optional description

        Returns:
            Collection ID
        """
        collection_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO document_collections (collection_id, collection_name, description)
                    VALUES (?, ?, ?)
                """, (collection_id, collection_name, description))

                conn.commit()
                self._logger.info(f"Created collection {collection_id}: {collection_name}")
                return collection_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
            finally:
                conn.close()

    def add_document_to_collection(self, document_id: str, collection_id: str) -> bool:
        """
        Add a document to a collection.

        Args:
            document_id: Document identifier
            collection_id: Collection identifier

        Returns:
            True if addition was successful
        """
        mapping_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO document_collection_mappings (mapping_id, document_id, collection_id)
                    VALUES (?, ?, ?)
                """, (mapping_id, document_id, collection_id))

                conn.commit()
                self._logger.info(f"Added document {document_id} to collection {collection_id}")
                return True

            except sqlite3.IntegrityError:
                # Document already in collection
                self._logger.warning(f"Document {document_id} already in collection {collection_id}")
                return False
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add document to collection: {e}")
                raise
            finally:
                conn.close()

    def get_collection_documents(self, collection_id: str) -> List[Dict[str, Any]]:
        """
        Get all documents in a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            List of document data dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.document_id, d.filename, d.file_path, d.file_size, d.file_hash,
                           d.mime_type, d.status, d.processing_started_at, d.processing_completed_at,
                           d.error_message, d.metadata, d.created_at, d.updated_at
                    FROM documents d
                    JOIN document_collection_mappings dcm ON d.document_id = dcm.document_id
                    WHERE dcm.collection_id = ?
                    ORDER BY d.created_at DESC
                """, (collection_id,))

                rows = cursor.fetchall()
                documents = []

                for row in rows:
                    documents.append({
                        'document_id': row[0],
                        'filename': row[1],
                        'file_path': row[2],
                        'file_size': row[3],
                        'file_hash': row[4],
                        'mime_type': row[5],
                        'status': row[6],
                        'processing_started_at': row[7],
                        'processing_completed_at': row[8],
                        'error_message': row[9],
                        'metadata': json.loads(row[10]) if row[10] else None,
                        'created_at': row[11],
                        'updated_at': row[12]
                    })

                return documents

            except Exception as e:
                self._logger.error(f"Failed to get collection documents {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_documents(self) -> int:
        """
        Clean up old failed and processed documents based on retention policies.

        Returns:
            Number of documents cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate cutoff dates
                failed_cutoff = datetime.now() - timedelta(days=self._failed_document_retention_days)
                processed_cutoff = datetime.now() - timedelta(days=self._processed_document_retention_days)

                # Delete old failed documents
                cursor.execute("""
                    DELETE FROM documents
                    WHERE status = 'failed' AND created_at < ?
                """, (failed_cutoff.isoformat(),))

                failed_count = cursor.rowcount

                # Delete old processed documents
                cursor.execute("""
                    DELETE FROM documents
                    WHERE status = 'completed' AND created_at < ?
                """, (processed_cutoff.isoformat(),))

                processed_count = cursor.rowcount
                total_cleaned = failed_count + processed_count

                conn.commit()

                if total_cleaned > 0:
                    self._logger.info(f"Cleaned up {total_cleaned} old documents "
                                    f"({failed_count} failed, {processed_count} processed)")

                return total_cleaned

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old documents: {e}")
                raise
            finally:
                conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics.

        Returns:
            Dictionary with repository statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get document counts by status
                cursor.execute("""
                    SELECT status, COUNT(*)
                    FROM documents
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())

                # Get total file size
                cursor.execute("SELECT SUM(file_size) FROM documents")
                total_size = cursor.fetchone()[0] or 0

                # Get collection count
                cursor.execute("SELECT COUNT(*) FROM document_collections")
                collection_count = cursor.fetchone()[0]

                # Get processing history count
                cursor.execute("SELECT COUNT(*) FROM document_processing_history")
                history_count = cursor.fetchone()[0]

                return {
                    'total_documents': sum(status_counts.values()),
                    'status_counts': status_counts,
                    'total_file_size_bytes': total_size,
                    'collection_count': collection_count,
                    'processing_history_entries': history_count,
                    'database_path': self._db_path
                }

            except Exception as e:
                self._logger.error(f"Failed to get repository statistics: {e}")
                raise
            finally:
                conn.close()
