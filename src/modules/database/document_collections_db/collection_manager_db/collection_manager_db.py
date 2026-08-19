"""
Module: collection_manager_db
Description: Handles document collection organization and hierarchical grouping with SQLite database operations
Phase: 3
Location: /src/modules/database/document_collections_db/collection_manager_db/
"""

# Standard library imports
import sqlite3
import threading
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger


class CollectionManagerDB:
    """
    Collection manager database for document collection organization.
    
    Handles document collection organization and hierarchical grouping
    with SQLite database operations. Provides thread-safe operations
    with transaction support for collection CRUD operations, hierarchical
    structure management, and document-collection relationships.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the collection manager database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to collections data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "collections"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "collection_manager.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
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
                
                # Create collections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collections (
                        collection_id TEXT PRIMARY KEY,
                        collection_name TEXT NOT NULL,
                        description TEXT,
                        parent_collection_id TEXT,
                        collection_type TEXT DEFAULT 'folder',
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (parent_collection_id) REFERENCES collections(collection_id)
                    )
                """)
                
                # Create collection hierarchy table for efficient tree operations
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_hierarchy (
                        hierarchy_id TEXT PRIMARY KEY,
                        ancestor_id TEXT NOT NULL,
                        descendant_id TEXT NOT NULL,
                        depth INTEGER NOT NULL,
                        path TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (ancestor_id) REFERENCES collections(collection_id),
                        FOREIGN KEY (descendant_id) REFERENCES collections(collection_id),
                        UNIQUE(ancestor_id, descendant_id)
                    )
                """)
                
                # Create document collection mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_collection_mappings (
                        mapping_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        collection_id TEXT NOT NULL,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        added_by TEXT,
                        mapping_metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (collection_id) REFERENCES collections(collection_id),
                        UNIQUE(document_id, collection_id)
                    )
                """)
                
                # Create collection permissions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_permissions (
                        permission_id TEXT PRIMARY KEY,
                        collection_id TEXT NOT NULL,
                        user_id TEXT,
                        permission_type TEXT NOT NULL,
                        granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        granted_by TEXT,
                        FOREIGN KEY (collection_id) REFERENCES collections(collection_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_parent ON collections(parent_collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(collection_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_type ON collections(collection_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_ancestor ON collection_hierarchy(ancestor_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_descendant ON collection_hierarchy(descendant_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_depth ON collection_hierarchy(depth)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_document ON document_collection_mappings(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_collection ON document_collection_mappings(collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_collection ON collection_permissions(collection_id)")
                
                conn.commit()
                
                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = ['collections', 'collection_hierarchy', 'document_collection_mappings', 'collection_permissions']
                
                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")
                
                self._logger.info("Collection manager database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize collection manager database: {e}")
                raise
            finally:
                conn.close()
    
    def create_collection(self, collection_name: str, description: Optional[str] = None,
                         parent_collection_id: Optional[str] = None,
                         collection_type: str = "folder",
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new collection.
        
        Args:
            collection_name: Name of the collection
            description: Optional description
            parent_collection_id: Parent collection ID for hierarchical organization
            collection_type: Type of collection (folder, smart, etc.)
            metadata: Additional metadata
            
        Returns:
            Collection ID
            
        Raises:
            Exception: If collection creation fails
        """
        collection_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Validate parent collection exists if specified
                if parent_collection_id:
                    cursor.execute("SELECT collection_id FROM collections WHERE collection_id = ?", 
                                 (parent_collection_id,))
                    if not cursor.fetchone():
                        raise ValueError(f"Parent collection {parent_collection_id} does not exist")
                
                # Insert collection
                cursor.execute("""
                    INSERT INTO collections 
                    (collection_id, collection_name, description, parent_collection_id, 
                     collection_type, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (collection_id, collection_name, description, parent_collection_id,
                      collection_type, metadata_json, datetime.now(timezone.utc).isoformat()))
                
                # Update hierarchy table
                self._update_hierarchy(cursor, collection_id, parent_collection_id)
                
                conn.commit()
                self._logger.info(f"Created collection {collection_id}: {collection_name}")
                return collection_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
            finally:
                conn.close()
    
    def _update_hierarchy(self, cursor: sqlite3.Cursor, collection_id: str, 
                         parent_collection_id: Optional[str]) -> None:
        """
        Update the hierarchy table for a collection.
        
        Args:
            cursor: Database cursor
            collection_id: Collection ID
            parent_collection_id: Parent collection ID
        """
        # Add self-reference
        hierarchy_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO collection_hierarchy 
            (hierarchy_id, ancestor_id, descendant_id, depth, path)
            VALUES (?, ?, ?, 0, ?)
        """, (hierarchy_id, collection_id, collection_id, collection_id))
        
        # Add parent relationships if parent exists
        if parent_collection_id:
            cursor.execute("""
                INSERT INTO collection_hierarchy 
                (hierarchy_id, ancestor_id, descendant_id, depth, path)
                SELECT ?, ancestor_id, ?, depth + 1, path || '/' || ?
                FROM collection_hierarchy 
                WHERE descendant_id = ?
            """, (str(uuid.uuid4()), collection_id, collection_id, parent_collection_id))

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get collection by ID.

        Args:
            collection_id: Collection identifier

        Returns:
            Collection data or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT collection_id, collection_name, description, parent_collection_id,
                           collection_type, is_active, created_at, updated_at, metadata
                    FROM collections
                    WHERE collection_id = ? AND is_active = 1
                """, (collection_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'description': row[2],
                        'parent_collection_id': row[3],
                        'collection_type': row[4],
                        'is_active': bool(row[5]),
                        'created_at': row[6],
                        'updated_at': row[7],
                        'metadata': json.loads(row[8]) if row[8] else {}
                    }
                return None

            except Exception as e:
                self._logger.error(f"Failed to get collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def update_collection(self, collection_id: str, collection_name: Optional[str] = None,
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
            True if update was successful
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
                    return True  # Nothing to update

                updates.append("updated_at = ?")
                params.append(datetime.now(timezone.utc).isoformat())
                params.append(collection_id)

                cursor.execute(f"""
                    UPDATE collections
                    SET {', '.join(updates)}
                    WHERE collection_id = ? AND is_active = 1
                """, params)

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Updated collection {collection_id}")
                else:
                    self._logger.warning(f"Collection {collection_id} not found for update")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_collection(self, collection_id: str, force: bool = False) -> bool:
        """
        Delete a collection (soft delete by default).

        Args:
            collection_id: Collection identifier
            force: If True, perform hard delete

        Returns:
            True if deletion was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if collection has children
                cursor.execute("""
                    SELECT COUNT(*) FROM collections
                    WHERE parent_collection_id = ? AND is_active = 1
                """, (collection_id,))

                child_count = cursor.fetchone()[0]
                if child_count > 0 and not force:
                    raise ValueError(f"Collection {collection_id} has {child_count} child collections")

                if force:
                    # Hard delete - remove from all tables
                    cursor.execute("DELETE FROM collection_permissions WHERE collection_id = ?", (collection_id,))
                    cursor.execute("DELETE FROM document_collection_mappings WHERE collection_id = ?", (collection_id,))
                    cursor.execute("DELETE FROM collection_hierarchy WHERE ancestor_id = ? OR descendant_id = ?",
                                 (collection_id, collection_id))
                    cursor.execute("DELETE FROM collections WHERE collection_id = ?", (collection_id,))
                else:
                    # Soft delete
                    cursor.execute("""
                        UPDATE collections
                        SET is_active = 0, updated_at = ?
                        WHERE collection_id = ?
                    """, (datetime.now(timezone.utc).isoformat(), collection_id))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Deleted collection {collection_id} (force={force})")
                else:
                    self._logger.warning(f"Collection {collection_id} not found for deletion")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def get_collection_children(self, collection_id: str) -> List[Dict[str, Any]]:
        """
        Get direct children of a collection.

        Args:
            collection_id: Parent collection identifier

        Returns:
            List of child collections
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT collection_id, collection_name, description, parent_collection_id,
                           collection_type, is_active, created_at, updated_at, metadata
                    FROM collections
                    WHERE parent_collection_id = ? AND is_active = 1
                    ORDER BY collection_name
                """, (collection_id,))

                children = []
                for row in cursor.fetchall():
                    children.append({
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'description': row[2],
                        'parent_collection_id': row[3],
                        'collection_type': row[4],
                        'is_active': bool(row[5]),
                        'created_at': row[6],
                        'updated_at': row[7],
                        'metadata': json.loads(row[8]) if row[8] else {}
                    })

                return children

            except Exception as e:
                self._logger.error(f"Failed to get children for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def get_collection_path(self, collection_id: str) -> List[Dict[str, Any]]:
        """
        Get the full path from root to collection.

        Args:
            collection_id: Collection identifier

        Returns:
            List of collections from root to target
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.collection_id, c.collection_name, c.description,
                           c.parent_collection_id, c.collection_type, h.depth
                    FROM collections c
                    JOIN collection_hierarchy h ON c.collection_id = h.ancestor_id
                    WHERE h.descendant_id = ? AND c.is_active = 1
                    ORDER BY h.depth
                """, (collection_id,))

                path = []
                for row in cursor.fetchall():
                    path.append({
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'description': row[2],
                        'parent_collection_id': row[3],
                        'collection_type': row[4],
                        'depth': row[5]
                    })

                return path

            except Exception as e:
                self._logger.error(f"Failed to get path for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def add_document_to_collection(self, document_id: str, collection_id: str,
                                  added_by: Optional[str] = None,
                                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a document to a collection.

        Args:
            document_id: Document identifier
            collection_id: Collection identifier
            added_by: User who added the document
            metadata: Additional mapping metadata

        Returns:
            True if addition was successful
        """
        mapping_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Verify collection exists
                cursor.execute("SELECT collection_id FROM collections WHERE collection_id = ? AND is_active = 1",
                             (collection_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Collection {collection_id} does not exist")

                cursor.execute("""
                    INSERT INTO document_collection_mappings
                    (mapping_id, document_id, collection_id, added_by, mapping_metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (mapping_id, document_id, collection_id, added_by, metadata_json))

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

    def remove_document_from_collection(self, document_id: str, collection_id: str) -> bool:
        """
        Remove a document from a collection.

        Args:
            document_id: Document identifier
            collection_id: Collection identifier

        Returns:
            True if removal was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM document_collection_mappings
                    WHERE document_id = ? AND collection_id = ?
                """, (document_id, collection_id))

                success = cursor.rowcount > 0
                conn.commit()

                if success:
                    self._logger.info(f"Removed document {document_id} from collection {collection_id}")
                else:
                    self._logger.warning(f"Document {document_id} not found in collection {collection_id}")

                return success

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to remove document from collection: {e}")
                raise
            finally:
                conn.close()

    def get_collection_documents(self, collection_id: str, limit: Optional[int] = None,
                               offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get documents in a collection.

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

                query = """
                    SELECT mapping_id, document_id, collection_id, added_at,
                           added_by, mapping_metadata
                    FROM document_collection_mappings
                    WHERE collection_id = ?
                    ORDER BY added_at DESC
                """

                params = [collection_id]
                if limit is not None:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                cursor.execute(query, params)

                documents = []
                for row in cursor.fetchall():
                    documents.append({
                        'mapping_id': row[0],
                        'document_id': row[1],
                        'collection_id': row[2],
                        'added_at': row[3],
                        'added_by': row[4],
                        'mapping_metadata': json.loads(row[5]) if row[5] else {}
                    })

                return documents

            except Exception as e:
                self._logger.error(f"Failed to get documents for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def get_document_collections(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all collections containing a document.

        Args:
            document_id: Document identifier

        Returns:
            List of collections containing the document
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.collection_id, c.collection_name, c.description,
                           c.collection_type, m.added_at, m.added_by
                    FROM collections c
                    JOIN document_collection_mappings m ON c.collection_id = m.collection_id
                    WHERE m.document_id = ? AND c.is_active = 1
                    ORDER BY c.collection_name
                """, (document_id,))

                collections = []
                for row in cursor.fetchall():
                    collections.append({
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'description': row[2],
                        'collection_type': row[3],
                        'added_at': row[4],
                        'added_by': row[5]
                    })

                return collections

            except Exception as e:
                self._logger.error(f"Failed to get collections for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def search_collections(self, query: str, collection_type: Optional[str] = None,
                          limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search collections by name or description.

        Args:
            query: Search query
            collection_type: Filter by collection type
            limit: Maximum number of results

        Returns:
            List of matching collections
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                sql = """
                    SELECT collection_id, collection_name, description, parent_collection_id,
                           collection_type, created_at, updated_at
                    FROM collections
                    WHERE is_active = 1
                    AND (collection_name LIKE ? OR description LIKE ?)
                """

                params = [f"%{query}%", f"%{query}%"]

                if collection_type:
                    sql += " AND collection_type = ?"
                    params.append(collection_type)

                sql += " ORDER BY collection_name LIMIT ?"
                params.append(limit)

                cursor.execute(sql, params)

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'description': row[2],
                        'parent_collection_id': row[3],
                        'collection_type': row[4],
                        'created_at': row[5],
                        'updated_at': row[6]
                    })

                return results

            except Exception as e:
                self._logger.error(f"Failed to search collections: {e}")
                raise
            finally:
                conn.close()

    def get_collection_statistics(self, collection_id: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Dictionary with collection statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get document count
                cursor.execute("""
                    SELECT COUNT(*) FROM document_collection_mappings
                    WHERE collection_id = ?
                """, (collection_id,))
                document_count = cursor.fetchone()[0]

                # Get child collection count
                cursor.execute("""
                    SELECT COUNT(*) FROM collections
                    WHERE parent_collection_id = ? AND is_active = 1
                """, (collection_id,))
                child_count = cursor.fetchone()[0]

                # Get total descendant count
                cursor.execute("""
                    SELECT COUNT(*) - 1 FROM collection_hierarchy
                    WHERE ancestor_id = ?
                """, (collection_id,))
                descendant_count = cursor.fetchone()[0]

                return {
                    'collection_id': collection_id,
                    'document_count': document_count,
                    'child_collection_count': child_count,
                    'total_descendant_count': descendant_count,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                self._logger.error(f"Failed to get statistics for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("Collection manager database closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
