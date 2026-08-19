"""
Module: chunk_mapping_db
Description: Maps document chunks to their source documents and positions
Phase: 4
Location: /src/modules/database/rag_metadata_db/chunk_mapping_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ChunkMappingDB:
    """
    Chunk mapping database manager.
    
    Maps document chunks to their source documents and positions, providing
    efficient lookup capabilities for RAG operations. Tracks chunk relationships,
    hierarchical structures, and metadata for optimal retrieval performance.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the chunk mapping database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to RAG metadata data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "rag_metadata"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "chunk_mapping.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._mapping_retention_days = 365  # Keep mappings for 1 year
        self._orphaned_mapping_retention_days = 7  # Keep orphaned mappings for 7 days
        
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
                
                # Create chunk mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mapping_id TEXT NOT NULL UNIQUE,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source_file_path TEXT,
                        chunk_index INTEGER NOT NULL,
                        start_position INTEGER,
                        end_position INTEGER,
                        start_line INTEGER,
                        end_line INTEGER,
                        start_page INTEGER,
                        end_page INTEGER,
                        section_title TEXT,
                        section_level INTEGER,
                        parent_section_id TEXT,
                        chunk_type TEXT DEFAULT 'text',
                        content_hash TEXT,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create document hierarchy table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_hierarchy (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hierarchy_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        parent_document_id TEXT,
                        hierarchy_level INTEGER DEFAULT 0,
                        section_path TEXT,
                        title TEXT,
                        document_type TEXT,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create chunk relationships table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_relationships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        relationship_id TEXT NOT NULL UNIQUE,
                        source_chunk_id TEXT NOT NULL,
                        target_chunk_id TEXT NOT NULL,
                        relationship_type TEXT NOT NULL,
                        relationship_strength REAL DEFAULT 1.0,
                        distance_metric REAL,
                        context_window INTEGER,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create chunk position index table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_position_index (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        index_id TEXT NOT NULL UNIQUE,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        position_type TEXT NOT NULL,
                        position_value INTEGER NOT NULL,
                        position_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chunk_id) REFERENCES chunk_mappings (chunk_id) ON DELETE CASCADE
                    )
                """)
                
                # Create chunk collection mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_collection_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_mapping_id TEXT NOT NULL UNIQUE,
                        chunk_id TEXT NOT NULL,
                        collection_id TEXT NOT NULL,
                        collection_name TEXT,
                        priority_score REAL DEFAULT 1.0,
                        inclusion_reason TEXT,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chunk_id) REFERENCES chunk_mappings (chunk_id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_chunk_id ON chunk_mappings (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_document_id ON chunk_mappings (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_chunk_index ON chunk_mappings (chunk_index)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_position ON chunk_mappings (start_position, end_position)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_page ON chunk_mappings (start_page, end_page)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_section ON chunk_mappings (section_title)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_type ON chunk_mappings (chunk_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mappings_hash ON chunk_mappings (content_hash)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_document_id ON document_hierarchy (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_parent ON document_hierarchy (parent_document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_level ON document_hierarchy (hierarchy_level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_path ON document_hierarchy (section_path)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_source ON chunk_relationships (source_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_target ON chunk_relationships (target_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_type ON chunk_relationships (relationship_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_strength ON chunk_relationships (relationship_strength)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_chunk_id ON chunk_position_index (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_document_id ON chunk_position_index (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_type ON chunk_position_index (position_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_value ON chunk_position_index (position_value)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_chunk_id ON chunk_collection_mappings (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_collection_id ON chunk_collection_mappings (collection_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_priority ON chunk_collection_mappings (priority_score)")
                
                # Create unique constraints
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mappings_chunk_document ON chunk_mappings (chunk_id, document_id)")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_hierarchy_document_parent ON document_hierarchy (document_id, parent_document_id)")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_position_chunk_type ON chunk_position_index (chunk_id, position_type)")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_chunk_collection ON chunk_collection_mappings (chunk_id, collection_id)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_mappings_timestamp 
                    AFTER UPDATE ON chunk_mappings
                    BEGIN
                        UPDATE chunk_mappings SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'chunk_mappings', 'document_hierarchy', 'chunk_relationships',
                    'chunk_position_index', 'chunk_collection_mappings'
                ]

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Chunk mapping database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize chunk mapping database: {e}")
                raise
            finally:
                conn.close()

    def add_chunk_mapping(self, chunk_id: str, document_id: str, chunk_index: int,
                         source_file_path: Optional[str] = None,
                         start_position: Optional[int] = None, end_position: Optional[int] = None,
                         start_line: Optional[int] = None, end_line: Optional[int] = None,
                         start_page: Optional[int] = None, end_page: Optional[int] = None,
                         section_title: Optional[str] = None, section_level: Optional[int] = None,
                         parent_section_id: Optional[str] = None, chunk_type: str = 'text',
                         content_hash: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new chunk mapping.

        Args:
            chunk_id: Unique chunk identifier
            document_id: Parent document identifier
            chunk_index: Sequential chunk number within document
            source_file_path: Original file path
            start_position: Starting character position
            end_position: Ending character position
            start_line: Starting line number
            end_line: Ending line number
            start_page: Starting page number
            end_page: Ending page number
            section_title: Section or heading title
            section_level: Hierarchical section level
            parent_section_id: Parent section identifier
            chunk_type: Type of chunk (text, table, image, etc.)
            content_hash: Hash of chunk content
            metadata: Additional mapping properties

        Returns:
            Mapping ID of the added mapping
        """
        mapping_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check for duplicate mapping
                cursor.execute("""
                    SELECT mapping_id FROM chunk_mappings
                    WHERE chunk_id = ? AND document_id = ?
                """, (chunk_id, document_id))
                existing = cursor.fetchone()
                if existing:
                    raise ValueError(f"Mapping already exists for chunk {chunk_id} in document {document_id}")

                # Insert new mapping
                cursor.execute("""
                    INSERT INTO chunk_mappings (
                        mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                        start_position, end_position, start_line, end_line, start_page,
                        end_page, section_title, section_level, parent_section_id,
                        chunk_type, content_hash, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                    start_position, end_position, start_line, end_line, start_page,
                    end_page, section_title, section_level, parent_section_id,
                    chunk_type, content_hash, json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Added chunk mapping {mapping_id} for chunk {chunk_id}")
                return mapping_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk mapping for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_chunk_mapping(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve chunk mapping by chunk ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Mapping data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                           start_position, end_position, start_line, end_line, start_page,
                           end_page, section_title, section_level, parent_section_id,
                           chunk_type, content_hash, metadata, created_at, updated_at
                    FROM chunk_mappings WHERE chunk_id = ?
                """, (chunk_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'mapping_id': row[0],
                    'chunk_id': row[1],
                    'document_id': row[2],
                    'source_file_path': row[3],
                    'chunk_index': row[4],
                    'start_position': row[5],
                    'end_position': row[6],
                    'start_line': row[7],
                    'end_line': row[8],
                    'start_page': row[9],
                    'end_page': row[10],
                    'section_title': row[11],
                    'section_level': row[12],
                    'parent_section_id': row[13],
                    'chunk_type': row[14],
                    'content_hash': row[15],
                    'metadata': json.loads(row[16]) if row[16] else None,
                    'created_at': row[17],
                    'updated_at': row[18]
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunk mapping for {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_document_chunks(self, document_id: str,
                           chunk_type: Optional[str] = None,
                           section_title: Optional[str] = None,
                           limit: Optional[int] = None,
                           offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all chunk mappings for a document.

        Args:
            document_id: Document identifier
            chunk_type: Filter by chunk type (optional)
            section_title: Filter by section title (optional)
            limit: Maximum number of mappings to return
            offset: Number of mappings to skip

        Returns:
            List of mapping data dictionaries ordered by chunk_index
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with optional filters
                query = """
                    SELECT mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                           start_position, end_position, start_line, end_line, start_page,
                           end_page, section_title, section_level, parent_section_id,
                           chunk_type, content_hash, metadata, created_at, updated_at
                    FROM chunk_mappings
                    WHERE document_id = ?
                """
                params = [document_id]

                if chunk_type:
                    query += " AND chunk_type = ?"
                    params.append(chunk_type)

                if section_title:
                    query += " AND section_title = ?"
                    params.append(section_title)

                query += " ORDER BY chunk_index"

                if limit:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])
                else:
                    query += " OFFSET ?"
                    params.append(offset)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                mappings = []

                for row in rows:
                    mappings.append({
                        'mapping_id': row[0],
                        'chunk_id': row[1],
                        'document_id': row[2],
                        'source_file_path': row[3],
                        'chunk_index': row[4],
                        'start_position': row[5],
                        'end_position': row[6],
                        'start_line': row[7],
                        'end_line': row[8],
                        'start_page': row[9],
                        'end_page': row[10],
                        'section_title': row[11],
                        'section_level': row[12],
                        'parent_section_id': row[13],
                        'chunk_type': row[14],
                        'content_hash': row[15],
                        'metadata': json.loads(row[16]) if row[16] else None,
                        'created_at': row[17],
                        'updated_at': row[18]
                    })

                return mappings

            except Exception as e:
                self._logger.error(f"Failed to get chunk mappings for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def find_chunks_by_position(self, document_id: str, position: int,
                               position_type: str = 'character') -> List[Dict[str, Any]]:
        """
        Find chunks that contain a specific position.

        Args:
            document_id: Document identifier
            position: Position value to search for
            position_type: Type of position (character, line, page)

        Returns:
            List of chunk mappings that contain the position
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if position_type == 'character':
                    cursor.execute("""
                        SELECT mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                               start_position, end_position, start_line, end_line, start_page,
                               end_page, section_title, section_level, parent_section_id,
                               chunk_type, content_hash, metadata, created_at, updated_at
                        FROM chunk_mappings
                        WHERE document_id = ? AND start_position <= ? AND end_position >= ?
                        ORDER BY chunk_index
                    """, (document_id, position, position))
                elif position_type == 'line':
                    cursor.execute("""
                        SELECT mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                               start_position, end_position, start_line, end_line, start_page,
                               end_page, section_title, section_level, parent_section_id,
                               chunk_type, content_hash, metadata, created_at, updated_at
                        FROM chunk_mappings
                        WHERE document_id = ? AND start_line <= ? AND end_line >= ?
                        ORDER BY chunk_index
                    """, (document_id, position, position))
                elif position_type == 'page':
                    cursor.execute("""
                        SELECT mapping_id, chunk_id, document_id, source_file_path, chunk_index,
                               start_position, end_position, start_line, end_line, start_page,
                               end_page, section_title, section_level, parent_section_id,
                               chunk_type, content_hash, metadata, created_at, updated_at
                        FROM chunk_mappings
                        WHERE document_id = ? AND start_page <= ? AND end_page >= ?
                        ORDER BY chunk_index
                    """, (document_id, position, position))
                else:
                    raise ValueError(f"Unsupported position type: {position_type}")

                rows = cursor.fetchall()
                mappings = []

                for row in rows:
                    mappings.append({
                        'mapping_id': row[0],
                        'chunk_id': row[1],
                        'document_id': row[2],
                        'source_file_path': row[3],
                        'chunk_index': row[4],
                        'start_position': row[5],
                        'end_position': row[6],
                        'start_line': row[7],
                        'end_line': row[8],
                        'start_page': row[9],
                        'end_page': row[10],
                        'section_title': row[11],
                        'section_level': row[12],
                        'parent_section_id': row[13],
                        'chunk_type': row[14],
                        'content_hash': row[15],
                        'metadata': json.loads(row[16]) if row[16] else None,
                        'created_at': row[17],
                        'updated_at': row[18]
                    })

                return mappings

            except Exception as e:
                self._logger.error(f"Failed to find chunks by position: {e}")
                raise
            finally:
                conn.close()

    def add_chunk_relationship(self, source_chunk_id: str, target_chunk_id: str,
                              relationship_type: str, relationship_strength: float = 1.0,
                              distance_metric: Optional[float] = None,
                              context_window: Optional[int] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add relationship between chunks.

        Args:
            source_chunk_id: Source chunk identifier
            target_chunk_id: Target chunk identifier
            relationship_type: Type of relationship (e.g., 'follows', 'references', 'similar')
            relationship_strength: Strength of the relationship (0.0-1.0)
            distance_metric: Distance metric value
            context_window: Context window size
            metadata: Additional relationship properties

        Returns:
            Relationship ID
        """
        relationship_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chunk_relationships (
                        relationship_id, source_chunk_id, target_chunk_id,
                        relationship_type, relationship_strength, distance_metric,
                        context_window, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (relationship_id, source_chunk_id, target_chunk_id,
                      relationship_type, relationship_strength, distance_metric,
                      context_window, json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Added chunk relationship {relationship_id}")
                return relationship_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk relationship: {e}")
                raise
            finally:
                conn.close()

    def get_chunk_relationships(self, chunk_id: str,
                               relationship_type: Optional[str] = None,
                               direction: str = 'both') -> List[Dict[str, Any]]:
        """
        Get relationships for a chunk.

        Args:
            chunk_id: Chunk identifier
            relationship_type: Filter by relationship type (optional)
            direction: Relationship direction ('source', 'target', 'both')

        Returns:
            List of relationship data dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query based on direction
                if direction == 'source':
                    where_clause = "source_chunk_id = ?"
                elif direction == 'target':
                    where_clause = "target_chunk_id = ?"
                else:  # both
                    where_clause = "(source_chunk_id = ? OR target_chunk_id = ?)"

                query = f"""
                    SELECT relationship_id, source_chunk_id, target_chunk_id,
                           relationship_type, relationship_strength, distance_metric,
                           context_window, metadata, created_at
                    FROM chunk_relationships
                    WHERE {where_clause}
                """
                params = [chunk_id] if direction != 'both' else [chunk_id, chunk_id]

                if relationship_type:
                    query += " AND relationship_type = ?"
                    params.append(relationship_type)

                query += " ORDER BY relationship_strength DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                relationships = []

                for row in rows:
                    relationships.append({
                        'relationship_id': row[0],
                        'source_chunk_id': row[1],
                        'target_chunk_id': row[2],
                        'relationship_type': row[3],
                        'relationship_strength': row[4],
                        'distance_metric': row[5],
                        'context_window': row[6],
                        'metadata': json.loads(row[7]) if row[7] else None,
                        'created_at': row[8]
                    })

                return relationships

            except Exception as e:
                self._logger.error(f"Failed to get relationships for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def add_to_collection(self, chunk_id: str, collection_id: str, collection_name: str,
                         priority_score: float = 1.0, inclusion_reason: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add chunk to a collection.

        Args:
            chunk_id: Chunk identifier
            collection_id: Collection identifier
            collection_name: Collection name
            priority_score: Priority score for the chunk in this collection
            inclusion_reason: Reason for including chunk in collection
            metadata: Additional collection mapping properties

        Returns:
            Collection mapping ID
        """
        collection_mapping_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO chunk_collection_mappings (
                        collection_mapping_id, chunk_id, collection_id, collection_name,
                        priority_score, inclusion_reason, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (collection_mapping_id, chunk_id, collection_id, collection_name,
                      priority_score, inclusion_reason, json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Added chunk {chunk_id} to collection {collection_id}")
                return collection_mapping_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk to collection: {e}")
                raise
            finally:
                conn.close()

    def get_collection_chunks(self, collection_id: str,
                             min_priority: float = 0.0,
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get chunks in a collection.

        Args:
            collection_id: Collection identifier
            min_priority: Minimum priority score threshold
            limit: Maximum number of chunks to return

        Returns:
            List of chunk mapping data with collection metadata
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT cm.mapping_id, cm.chunk_id, cm.document_id, cm.source_file_path,
                           cm.chunk_index, cm.start_position, cm.end_position, cm.start_line,
                           cm.end_line, cm.start_page, cm.end_page, cm.section_title,
                           cm.section_level, cm.parent_section_id, cm.chunk_type,
                           cm.content_hash, cm.metadata, cm.created_at, cm.updated_at,
                           ccm.priority_score, ccm.inclusion_reason, ccm.metadata as collection_metadata
                    FROM chunk_mappings cm
                    JOIN chunk_collection_mappings ccm ON cm.chunk_id = ccm.chunk_id
                    WHERE ccm.collection_id = ? AND ccm.priority_score >= ?
                    ORDER BY ccm.priority_score DESC, cm.chunk_index
                """
                params = [collection_id, min_priority]

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                chunks = []

                for row in rows:
                    chunks.append({
                        'mapping_id': row[0],
                        'chunk_id': row[1],
                        'document_id': row[2],
                        'source_file_path': row[3],
                        'chunk_index': row[4],
                        'start_position': row[5],
                        'end_position': row[6],
                        'start_line': row[7],
                        'end_line': row[8],
                        'start_page': row[9],
                        'end_page': row[10],
                        'section_title': row[11],
                        'section_level': row[12],
                        'parent_section_id': row[13],
                        'chunk_type': row[14],
                        'content_hash': row[15],
                        'metadata': json.loads(row[16]) if row[16] else None,
                        'created_at': row[17],
                        'updated_at': row[18],
                        'priority_score': row[19],
                        'inclusion_reason': row[20],
                        'collection_metadata': json.loads(row[21]) if row[21] else None
                    })

                return chunks

            except Exception as e:
                self._logger.error(f"Failed to get chunks for collection {collection_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_chunk_mapping(self, chunk_id: str) -> bool:
        """
        Delete a chunk mapping and all associated data.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deletion was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chunk_mappings WHERE chunk_id = ?", (chunk_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    self._logger.info(f"Deleted chunk mapping for {chunk_id}")
                    return True
                else:
                    self._logger.warning(f"Chunk mapping {chunk_id} not found for deletion")
                    return False

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete chunk mapping {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get chunk mapping database statistics.

        Returns:
            Dictionary with database statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get total mapping count
                cursor.execute("SELECT COUNT(*) FROM chunk_mappings")
                total_mappings = cursor.fetchone()[0]

                # Get unique documents count
                cursor.execute("SELECT COUNT(DISTINCT document_id) FROM chunk_mappings")
                unique_documents = cursor.fetchone()[0]

                # Get unique chunks count
                cursor.execute("SELECT COUNT(DISTINCT chunk_id) FROM chunk_mappings")
                unique_chunks = cursor.fetchone()[0]

                # Get chunk type distribution
                cursor.execute("""
                    SELECT chunk_type, COUNT(*)
                    FROM chunk_mappings
                    GROUP BY chunk_type
                """)
                chunk_types = dict(cursor.fetchall())

                # Get total relationships
                cursor.execute("SELECT COUNT(*) FROM chunk_relationships")
                total_relationships = cursor.fetchone()[0]

                # Get total collection mappings
                cursor.execute("SELECT COUNT(*) FROM chunk_collection_mappings")
                total_collection_mappings = cursor.fetchone()[0]

                # Get average chunks per document
                cursor.execute("""
                    SELECT AVG(chunk_count) FROM (
                        SELECT COUNT(*) as chunk_count
                        FROM chunk_mappings
                        GROUP BY document_id
                    )
                """)
                avg_chunks_per_doc = cursor.fetchone()[0] or 0.0

                return {
                    'total_mappings': total_mappings,
                    'unique_documents': unique_documents,
                    'unique_chunks': unique_chunks,
                    'chunk_type_distribution': chunk_types,
                    'total_relationships': total_relationships,
                    'total_collection_mappings': total_collection_mappings,
                    'average_chunks_per_document': round(avg_chunks_per_doc, 2),
                    'database_path': self._db_path
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunk mapping statistics: {e}")
                raise
            finally:
                conn.close()
