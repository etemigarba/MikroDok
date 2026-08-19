"""
Module: document_collection_db
Description: Document collection organization and hierarchical grouping functionality
Phase: 3
Location: /src/modules/database/document_repository_db/document_collection_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class DocumentCollectionDB:
    """
    Document collection database manager.
    
    Handles document collection organization and hierarchical grouping with
    support for nested collections, metadata management, and efficient
    querying. Provides collection-level statistics and batch operations.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the document collection database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to document repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "document_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "document_collection.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._collection_retention_days = 365  # Keep collections for 1 year
        self._max_nesting_depth = 10  # Maximum collection nesting depth
        self._max_collections_per_parent = 1000  # Maximum subcollections per parent
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
                
                # Create document collections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_id TEXT NOT NULL UNIQUE,
                        parent_collection_id TEXT,
                        collection_name TEXT NOT NULL,
                        description TEXT,
                        collection_type TEXT NOT NULL DEFAULT 'folder',
                        status TEXT NOT NULL DEFAULT 'active',
                        path TEXT NOT NULL,
                        depth_level INTEGER NOT NULL DEFAULT 0,
                        sort_order INTEGER DEFAULT 0,
                        is_system BOOLEAN DEFAULT 0,
                        is_readonly BOOLEAN DEFAULT 0,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        FOREIGN KEY (parent_collection_id) REFERENCES document_collections (collection_id) ON DELETE CASCADE,
                        CONSTRAINT chk_collection_type CHECK (collection_type IN ('folder', 'smart', 'tag', 'search', 'system')),
                        CONSTRAINT chk_status CHECK (status IN ('active', 'archived', 'deleted'))
                    )
                """)
                
                # Create collection statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stat_id TEXT NOT NULL UNIQUE,
                        collection_id TEXT NOT NULL,
                        document_count INTEGER DEFAULT 0,
                        total_size_bytes INTEGER DEFAULT 0,
                        chunk_count INTEGER DEFAULT 0,
                        last_document_added TIMESTAMP,
                        last_document_processed TIMESTAMP,
                        processing_status TEXT DEFAULT 'idle',
                        error_count INTEGER DEFAULT 0,
                        warning_count INTEGER DEFAULT 0,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES document_collections (collection_id) ON DELETE CASCADE,
                        CONSTRAINT chk_processing_status CHECK (processing_status IN ('idle', 'processing', 'completed', 'error'))
                    )
                """)
                
                # Create collection permissions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        permission_id TEXT NOT NULL UNIQUE,
                        collection_id TEXT NOT NULL,
                        user_id TEXT,
                        role TEXT NOT NULL DEFAULT 'viewer',
                        permissions JSON,
                        granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        granted_by TEXT,
                        expires_at TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES document_collections (collection_id) ON DELETE CASCADE,
                        CONSTRAINT chk_role CHECK (role IN ('owner', 'editor', 'viewer', 'contributor'))
                    )
                """)
                
                # Create collection tags table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_id TEXT NOT NULL UNIQUE,
                        collection_id TEXT NOT NULL,
                        tag_name TEXT NOT NULL,
                        tag_value TEXT,
                        tag_color TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        FOREIGN KEY (collection_id) REFERENCES document_collections (collection_id) ON DELETE CASCADE
                    )
                """)
                
                # Create collection document mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mapping_id TEXT NOT NULL UNIQUE,
                        collection_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        added_by TEXT,
                        sort_order INTEGER DEFAULT 0,
                        is_pinned BOOLEAN DEFAULT 0,
                        metadata JSON,
                        FOREIGN KEY (collection_id) REFERENCES document_collections (collection_id) ON DELETE CASCADE,
                        UNIQUE(collection_id, document_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_parent_id ON document_collections (parent_collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_type ON document_collections (collection_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_status ON document_collections (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_path ON document_collections (path)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_depth ON document_collections (depth_level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_created_at ON document_collections (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_stats_collection_id ON collection_statistics (collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_permissions_collection_id ON collection_permissions (collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_permissions_user_id ON collection_permissions (user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_tags_collection_id ON collection_tags (collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_tags_name ON collection_tags (tag_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_documents_collection_id ON collection_documents (collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_documents_document_id ON collection_documents (document_id)")
                
                # Create triggers for automatic statistics updates
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_collection_stats_on_document_add 
                    AFTER INSERT ON collection_documents
                    BEGIN
                        UPDATE collection_statistics 
                        SET document_count = document_count + 1,
                            last_document_added = CURRENT_TIMESTAMP,
                            calculated_at = CURRENT_TIMESTAMP
                        WHERE collection_id = NEW.collection_id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_collection_stats_on_document_remove 
                    AFTER DELETE ON collection_documents
                    BEGIN
                        UPDATE collection_statistics 
                        SET document_count = document_count - 1,
                            calculated_at = CURRENT_TIMESTAMP
                        WHERE collection_id = OLD.collection_id;
                    END
                """)
                
                conn.commit()
                self._logger.info("Document collection database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize document collection database: {e}")
                raise
            finally:
                conn.close()

    def create_collection(self, collection_name: str,
                         parent_collection_id: Optional[str] = None,
                         description: Optional[str] = None,
                         collection_type: str = 'folder',
                         metadata: Optional[Dict[str, Any]] = None,
                         created_by: Optional[str] = None) -> str:
        """
        Create a new document collection.

        Args:
            collection_name: Name of the collection
            parent_collection_id: Parent collection ID for hierarchical organization
            description: Optional description
            collection_type: Type of collection
            metadata: Additional metadata
            created_by: User who created the collection

        Returns:
            Collection ID
        """
        collection_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate depth and path
                depth_level = 0
                path = collection_name

                if parent_collection_id:
                    # Get parent collection info
                    cursor.execute("""
                        SELECT depth_level, path FROM document_collections
                        WHERE collection_id = ?
                    """, (parent_collection_id,))
                    parent_info = cursor.fetchone()

                    if parent_info:
                        depth_level = parent_info[0] + 1
                        path = f"{parent_info[1]}/{collection_name}"

                        # Check depth limit
                        if depth_level > self._max_nesting_depth:
                            raise ValueError(f"Maximum nesting depth ({self._max_nesting_depth}) exceeded")

                # Insert collection
                cursor.execute("""
                    INSERT INTO document_collections (
                        collection_id, parent_collection_id, collection_name, description,
                        collection_type, path, depth_level, metadata, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    collection_id, parent_collection_id, collection_name, description,
                    collection_type, path, depth_level,
                    json.dumps(metadata) if metadata else None, created_by
                ))

                # Initialize statistics
                stat_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO collection_statistics (stat_id, collection_id)
                    VALUES (?, ?)
                """, (stat_id, collection_id))

                conn.commit()
                self._logger.info(f"Created collection {collection_id}: {collection_name}")
                return collection_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
            finally:
                conn.close()

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a collection by ID.

        Args:
            collection_id: Collection identifier

        Returns:
            Collection data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT collection_id, parent_collection_id, collection_name, description,
                           collection_type, status, path, depth_level, sort_order,
                           is_system, is_readonly, metadata, created_at, updated_at, created_by
                    FROM document_collections WHERE collection_id = ?
                """, (collection_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'collection_id': row[0],
                    'parent_collection_id': row[1],
                    'collection_name': row[2],
                    'description': row[3],
                    'collection_type': row[4],
                    'status': row[5],
                    'path': row[6],
                    'depth_level': row[7],
                    'sort_order': row[8],
                    'is_system': bool(row[9]),
                    'is_readonly': bool(row[10]),
                    'metadata': json.loads(row[11]) if row[11] else None,
                    'created_at': row[12],
                    'updated_at': row[13],
                    'created_by': row[14]
                }

            except Exception as e:
                self._logger.error(f"Failed to get collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def update_collection(self, collection_id: str,
                         collection_name: Optional[str] = None,
                         description: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update collection information.

        Args:
            collection_id: Collection identifier
            collection_name: New collection name
            description: New description
            metadata: New metadata

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build update query dynamically
                updates = []
                params = []

                if collection_name is not None:
                    updates.append("collection_name = ?")
                    params.append(collection_name)

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)

                if metadata is not None:
                    updates.append("metadata = ?")
                    params.append(json.dumps(metadata))

                if not updates:
                    return False

                updates.append("updated_at = ?")
                params.append(datetime.now(timezone.utc).isoformat())
                params.append(collection_id)

                query = f"UPDATE document_collections SET {', '.join(updates)} WHERE collection_id = ?"
                cursor.execute(query, params)

                conn.commit()
                self._logger.info(f"Updated collection {collection_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_collection(self, collection_id: str, force: bool = False) -> bool:
        """
        Delete a collection.

        Args:
            collection_id: Collection identifier
            force: Force deletion even if collection has documents

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if collection has documents
                if not force:
                    cursor.execute("""
                        SELECT COUNT(*) FROM collection_documents WHERE collection_id = ?
                    """, (collection_id,))
                    doc_count = cursor.fetchone()[0]

                    if doc_count > 0:
                        raise ValueError(f"Collection has {doc_count} documents. Use force=True to delete anyway.")

                # Delete collection (cascades to related tables)
                cursor.execute("DELETE FROM document_collections WHERE collection_id = ?", (collection_id,))

                conn.commit()
                self._logger.info(f"Deleted collection {collection_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def list_collections(self, parent_collection_id: Optional[str] = None,
                        collection_type: Optional[str] = None,
                        status: str = 'active',
                        limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List collections with optional filtering.

        Args:
            parent_collection_id: Filter by parent collection
            collection_type: Filter by collection type
            status: Filter by status
            limit: Maximum number of collections to return
            offset: Number of collections to skip

        Returns:
            List of collection dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT collection_id, parent_collection_id, collection_name, description,
                           collection_type, status, path, depth_level, sort_order,
                           is_system, is_readonly, metadata, created_at, updated_at, created_by
                    FROM document_collections
                    WHERE status = ?
                """
                params = [status]

                if parent_collection_id is not None:
                    query += " AND parent_collection_id = ?"
                    params.append(parent_collection_id)

                if collection_type:
                    query += " AND collection_type = ?"
                    params.append(collection_type)

                query += " ORDER BY sort_order, collection_name LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                collections = []
                for row in rows:
                    collections.append({
                        'collection_id': row[0],
                        'parent_collection_id': row[1],
                        'collection_name': row[2],
                        'description': row[3],
                        'collection_type': row[4],
                        'status': row[5],
                        'path': row[6],
                        'depth_level': row[7],
                        'sort_order': row[8],
                        'is_system': bool(row[9]),
                        'is_readonly': bool(row[10]),
                        'metadata': json.loads(row[11]) if row[11] else None,
                        'created_at': row[12],
                        'updated_at': row[13],
                        'created_by': row[14]
                    })

                return collections

            except Exception as e:
                self._logger.error(f"Failed to list collections: {e}")
                raise
            finally:
                conn.close()

    def add_document_to_collection(self, collection_id: str, document_id: str,
                                  added_by: Optional[str] = None,
                                  sort_order: int = 0,
                                  is_pinned: bool = False,
                                  metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a document to a collection.

        Args:
            collection_id: Collection identifier
            document_id: Document identifier
            added_by: User who added the document
            sort_order: Sort order within collection
            is_pinned: Whether document is pinned
            metadata: Additional metadata

        Returns:
            Mapping ID
        """
        mapping_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Insert document mapping
                cursor.execute("""
                    INSERT INTO collection_documents (
                        mapping_id, collection_id, document_id, added_by,
                        sort_order, is_pinned, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    mapping_id, collection_id, document_id, added_by,
                    sort_order, is_pinned, json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Added document {document_id} to collection {collection_id}")
                return mapping_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add document to collection: {e}")
                raise
            finally:
                conn.close()

    def remove_document_from_collection(self, collection_id: str, document_id: str) -> bool:
        """
        Remove a document from a collection.

        Args:
            collection_id: Collection identifier
            document_id: Document identifier

        Returns:
            True if removed successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    DELETE FROM collection_documents
                    WHERE collection_id = ? AND document_id = ?
                """, (collection_id, document_id))

                conn.commit()
                self._logger.info(f"Removed document {document_id} from collection {collection_id}")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to remove document from collection: {e}")
                raise
            finally:
                conn.close()

    def get_collection_documents(self, collection_id: str,
                               limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all documents in a collection.

        Args:
            collection_id: Collection identifier
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of document mappings
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT mapping_id, collection_id, document_id, added_at, added_by,
                           sort_order, is_pinned, metadata
                    FROM collection_documents
                    WHERE collection_id = ?
                    ORDER BY is_pinned DESC, sort_order, added_at DESC
                    LIMIT ? OFFSET ?
                """, (collection_id, limit, offset))

                rows = cursor.fetchall()

                documents = []
                for row in rows:
                    documents.append({
                        'mapping_id': row[0],
                        'collection_id': row[1],
                        'document_id': row[2],
                        'added_at': row[3],
                        'added_by': row[4],
                        'sort_order': row[5],
                        'is_pinned': bool(row[6]),
                        'metadata': json.loads(row[7]) if row[7] else None
                    })

                return documents

            except Exception as e:
                self._logger.error(f"Failed to get documents for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def get_collection_hierarchy(self, collection_id: str) -> Dict[str, Any]:
        """
        Get the full hierarchy for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Hierarchical collection structure
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get collection and its children recursively
                def get_children(parent_id: Optional[str]) -> List[Dict[str, Any]]:
                    cursor.execute("""
                        SELECT collection_id, collection_name, description, collection_type,
                               path, depth_level, sort_order, metadata, created_at
                        FROM document_collections
                        WHERE parent_collection_id = ? AND status = 'active'
                        ORDER BY sort_order, collection_name
                    """, (parent_id,))

                    children = []
                    for row in cursor.fetchall():
                        child = {
                            'collection_id': row[0],
                            'collection_name': row[1],
                            'description': row[2],
                            'collection_type': row[3],
                            'path': row[4],
                            'depth_level': row[5],
                            'sort_order': row[6],
                            'metadata': json.loads(row[7]) if row[7] else None,
                            'created_at': row[8],
                            'children': get_children(row[0])
                        }
                        children.append(child)

                    return children

                # Get root collection
                cursor.execute("""
                    SELECT collection_id, collection_name, description, collection_type,
                           path, depth_level, sort_order, metadata, created_at
                    FROM document_collections
                    WHERE collection_id = ?
                """, (collection_id,))

                row = cursor.fetchone()
                if not row:
                    return {}

                hierarchy = {
                    'collection_id': row[0],
                    'collection_name': row[1],
                    'description': row[2],
                    'collection_type': row[3],
                    'path': row[4],
                    'depth_level': row[5],
                    'sort_order': row[6],
                    'metadata': json.loads(row[7]) if row[7] else None,
                    'created_at': row[8],
                    'children': get_children(collection_id)
                }

                return hierarchy

            except Exception as e:
                self._logger.error(f"Failed to get hierarchy for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def get_collection_statistics(self, collection_id: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Collection statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT document_count, total_size_bytes, chunk_count,
                           last_document_added, last_document_processed,
                           processing_status, error_count, warning_count,
                           calculated_at
                    FROM collection_statistics
                    WHERE collection_id = ?
                """, (collection_id,))

                row = cursor.fetchone()
                if not row:
                    return {}

                return {
                    'document_count': row[0],
                    'total_size_bytes': row[1],
                    'chunk_count': row[2],
                    'last_document_added': row[3],
                    'last_document_processed': row[4],
                    'processing_status': row[5],
                    'error_count': row[6],
                    'warning_count': row[7],
                    'calculated_at': row[8]
                }

            except Exception as e:
                self._logger.error(f"Failed to get statistics for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def update_collection_statistics(self, collection_id: str,
                                   document_count: Optional[int] = None,
                                   total_size_bytes: Optional[int] = None,
                                   chunk_count: Optional[int] = None) -> bool:
        """
        Update collection statistics.

        Args:
            collection_id: Collection identifier
            document_count: Updated document count
            total_size_bytes: Updated total size
            chunk_count: Updated chunk count

        Returns:
            True if updated successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build update query dynamically
                updates = []
                params = []

                if document_count is not None:
                    updates.append("document_count = ?")
                    params.append(document_count)

                if total_size_bytes is not None:
                    updates.append("total_size_bytes = ?")
                    params.append(total_size_bytes)

                if chunk_count is not None:
                    updates.append("chunk_count = ?")
                    params.append(chunk_count)

                if not updates:
                    return False

                updates.append("calculated_at = ?")
                params.append(datetime.now(timezone.utc).isoformat())
                params.append(collection_id)

                query = f"UPDATE collection_statistics SET {', '.join(updates)} WHERE collection_id = ?"
                cursor.execute(query, params)

                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update statistics for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def cleanup_empty_collections(self) -> int:
        """
        Clean up empty collections that have no documents.

        Returns:
            Number of collections cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Find empty collections (excluding system collections)
                cursor.execute("""
                    SELECT c.collection_id
                    FROM document_collections c
                    LEFT JOIN collection_documents cd ON c.collection_id = cd.collection_id
                    WHERE cd.collection_id IS NULL
                      AND c.is_system = 0
                      AND c.status = 'active'
                      AND c.created_at < datetime('now', '-7 days')
                """)

                empty_collections = [row[0] for row in cursor.fetchall()]

                # Archive empty collections
                for collection_id in empty_collections:
                    cursor.execute("""
                        UPDATE document_collections
                        SET status = 'archived', updated_at = ?
                        WHERE collection_id = ?
                    """, (datetime.now(timezone.utc).isoformat(), collection_id))

                conn.commit()
                self._logger.info(f"Archived {len(empty_collections)} empty collections")
                return len(empty_collections)

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup empty collections: {e}")
                raise
            finally:
                conn.close()
