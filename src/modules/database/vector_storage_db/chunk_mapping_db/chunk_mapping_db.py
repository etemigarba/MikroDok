"""
Module: chunk_mapping_db
Description: Maintains relationships between document chunks and their embeddings
Phase: 4
Location: /src/modules/database/vector_storage_db/chunk_mapping_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ChunkType(Enum):
    """Types of document chunks."""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    HEADER = "header"
    FOOTER = "footer"
    METADATA = "metadata"


class MappingStatus(Enum):
    """Status of chunk mapping."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROCESSING = "processing"
    ERROR = "error"


class VectorChunkMappingDB:
    """
    Maintains relationships between document chunks and their embeddings.

    Provides efficient lookup capabilities for RAG operations by mapping document
    chunks to their vector embeddings. Tracks chunk hierarchies, relationships,
    and metadata for optimal retrieval performance with SQLite backend.

    Note: This is different from rag_metadata_db.ChunkMappingDB which maps chunks
    to documents. This class specifically handles chunk-to-embedding relationships.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the chunk mapping database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to vector storage data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "chunk_mappings"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "chunk_mapping.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._mapping_retention_days = 365  # Keep mappings for 1 year
        self._max_batch_size = 1000  # Maximum batch size for operations
        self._cache_size = 10000  # SQLite cache size
        
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
                        mapping_id TEXT PRIMARY KEY,
                        chunk_id TEXT UNIQUE NOT NULL,
                        document_id TEXT NOT NULL,
                        embedding_id TEXT,
                        chunk_index INTEGER NOT NULL,
                        chunk_type TEXT NOT NULL DEFAULT 'text',
                        chunk_content_hash TEXT,
                        start_position INTEGER,
                        end_position INTEGER,
                        start_line INTEGER,
                        end_line INTEGER,
                        start_page INTEGER,
                        end_page INTEGER,
                        section_title TEXT,
                        section_level INTEGER,
                        parent_chunk_id TEXT,
                        child_chunk_ids TEXT,
                        source_file_path TEXT,
                        extraction_method TEXT,
                        confidence_score REAL DEFAULT 1.0,
                        status TEXT NOT NULL DEFAULT 'active',
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """)
                
                # Create chunk relationships table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_relationships (
                        relationship_id TEXT PRIMARY KEY,
                        source_chunk_id TEXT NOT NULL,
                        target_chunk_id TEXT NOT NULL,
                        relationship_type TEXT NOT NULL,
                        relationship_strength REAL DEFAULT 1.0,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (source_chunk_id) REFERENCES chunk_mappings(chunk_id),
                        FOREIGN KEY (target_chunk_id) REFERENCES chunk_mappings(chunk_id)
                    )
                """)
                
                # Create chunk statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_statistics (
                        stat_id TEXT PRIMARY KEY,
                        chunk_id TEXT NOT NULL,
                        stat_type TEXT NOT NULL,
                        stat_name TEXT NOT NULL,
                        stat_value REAL NOT NULL,
                        stat_metadata TEXT,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chunk_id) REFERENCES chunk_mappings(chunk_id)
                    )
                """)
                
                # Create embedding mappings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_mappings (
                        mapping_id TEXT PRIMARY KEY,
                        chunk_id TEXT NOT NULL,
                        embedding_id TEXT NOT NULL,
                        vector_index_id TEXT,
                        similarity_threshold REAL DEFAULT 0.7,
                        mapping_confidence REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chunk_id) REFERENCES chunk_mappings(chunk_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_chunk_id ON chunk_mappings(chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_document_id ON chunk_mappings(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_embedding_id ON chunk_mappings(embedding_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_chunk_index ON chunk_mappings(chunk_index)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_chunk_type ON chunk_mappings(chunk_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_status ON chunk_mappings(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_parent ON chunk_mappings(parent_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_section ON chunk_mappings(section_title)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_mappings_created_at ON chunk_mappings(created_at)")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_relationships_source ON chunk_relationships(source_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_relationships_target ON chunk_relationships(target_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_relationships_type ON chunk_relationships(relationship_type)")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_statistics_chunk ON chunk_statistics(chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_statistics_type ON chunk_statistics(stat_type, stat_name)")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_mappings_chunk ON embedding_mappings(chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_mappings_embedding ON embedding_mappings(embedding_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_mappings_index ON embedding_mappings(vector_index_id)")

                conn.commit()
                self._logger.info("Chunk mapping database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize chunk mapping database: {e}")
                raise
            finally:
                conn.close()

    def add_chunk_mapping(self, chunk_id: str, document_id: str, chunk_index: int,
                         chunk_type: ChunkType = ChunkType.TEXT,
                         embedding_id: Optional[str] = None,
                         chunk_content_hash: Optional[str] = None,
                         start_position: Optional[int] = None,
                         end_position: Optional[int] = None,
                         start_line: Optional[int] = None,
                         end_line: Optional[int] = None,
                         start_page: Optional[int] = None,
                         end_page: Optional[int] = None,
                         section_title: Optional[str] = None,
                         section_level: Optional[int] = None,
                         parent_chunk_id: Optional[str] = None,
                         source_file_path: Optional[str] = None,
                         extraction_method: Optional[str] = None,
                         confidence_score: float = 1.0,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new chunk mapping.

        Args:
            chunk_id: Unique chunk identifier
            document_id: Document identifier
            chunk_index: Position of chunk in document
            chunk_type: Type of chunk
            embedding_id: Associated embedding ID
            chunk_content_hash: Hash of chunk content
            start_position: Start character position
            end_position: End character position
            start_line: Start line number
            end_line: End line number
            start_page: Start page number
            end_page: End page number
            section_title: Section title
            section_level: Section hierarchy level
            parent_chunk_id: Parent chunk ID
            source_file_path: Source file path
            extraction_method: Method used for extraction
            confidence_score: Confidence in mapping
            metadata: Additional metadata

        Returns:
            Mapping ID

        Raises:
            ValueError: If chunk_id already exists or parameters are invalid
        """
        if not chunk_id or not chunk_id.strip():
            raise ValueError("Chunk ID cannot be empty")

        if not document_id or not document_id.strip():
            raise ValueError("Document ID cannot be empty")

        if chunk_index < 0:
            raise ValueError("Chunk index must be non-negative")

        if not (0.0 <= confidence_score <= 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")

        mapping_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if chunk_id already exists
                cursor.execute("SELECT mapping_id FROM chunk_mappings WHERE chunk_id = ?", (chunk_id,))
                if cursor.fetchone():
                    raise ValueError(f"Chunk with ID '{chunk_id}' already exists")

                # Insert new mapping
                cursor.execute("""
                    INSERT INTO chunk_mappings (
                        mapping_id, chunk_id, document_id, embedding_id, chunk_index,
                        chunk_type, chunk_content_hash, start_position, end_position,
                        start_line, end_line, start_page, end_page, section_title,
                        section_level, parent_chunk_id, source_file_path,
                        extraction_method, confidence_score, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mapping_id, chunk_id, document_id, embedding_id, chunk_index,
                    chunk_type.value, chunk_content_hash, start_position, end_position,
                    start_line, end_line, start_page, end_page, section_title,
                    section_level, parent_chunk_id, source_file_path,
                    extraction_method, confidence_score,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.debug(f"Added chunk mapping: {chunk_id} -> {mapping_id}")
                return mapping_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk mapping: {e}")
                raise
            finally:
                conn.close()

    def get_chunk_mapping(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chunk mapping by chunk ID.

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
                    SELECT mapping_id, chunk_id, document_id, embedding_id, chunk_index,
                           chunk_type, chunk_content_hash, start_position, end_position,
                           start_line, end_line, start_page, end_page, section_title,
                           section_level, parent_chunk_id, child_chunk_ids, source_file_path,
                           extraction_method, confidence_score, status, metadata,
                           created_at, updated_at, expires_at
                    FROM chunk_mappings WHERE chunk_id = ?
                """, (chunk_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'mapping_id': row[0],
                    'chunk_id': row[1],
                    'document_id': row[2],
                    'embedding_id': row[3],
                    'chunk_index': row[4],
                    'chunk_type': row[5],
                    'chunk_content_hash': row[6],
                    'start_position': row[7],
                    'end_position': row[8],
                    'start_line': row[9],
                    'end_line': row[10],
                    'start_page': row[11],
                    'end_page': row[12],
                    'section_title': row[13],
                    'section_level': row[14],
                    'parent_chunk_id': row[15],
                    'child_chunk_ids': json.loads(row[16]) if row[16] else [],
                    'source_file_path': row[17],
                    'extraction_method': row[18],
                    'confidence_score': row[19],
                    'status': row[20],
                    'metadata': json.loads(row[21]) if row[21] else None,
                    'created_at': row[22],
                    'updated_at': row[23],
                    'expires_at': row[24]
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunk mapping: {e}")
                raise
            finally:
                conn.close()

    def get_document_chunks(self, document_id: str,
                           chunk_type: Optional[ChunkType] = None,
                           section_title: Optional[str] = None,
                           status: Optional[MappingStatus] = None,
                           limit: Optional[int] = None,
                           offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all chunk mappings for a document.

        Args:
            document_id: Document identifier
            chunk_type: Filter by chunk type
            section_title: Filter by section title
            status: Filter by status
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
                    SELECT mapping_id, chunk_id, document_id, embedding_id, chunk_index,
                           chunk_type, chunk_content_hash, start_position, end_position,
                           start_line, end_line, start_page, end_page, section_title,
                           section_level, parent_chunk_id, source_file_path,
                           extraction_method, confidence_score, status, metadata,
                           created_at, updated_at
                    FROM chunk_mappings
                    WHERE document_id = ?
                """
                params = [document_id]

                if chunk_type:
                    query += " AND chunk_type = ?"
                    params.append(chunk_type.value)

                if section_title:
                    query += " AND section_title = ?"
                    params.append(section_title)

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                query += " ORDER BY chunk_index"

                if limit:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [
                    {
                        'mapping_id': row[0],
                        'chunk_id': row[1],
                        'document_id': row[2],
                        'embedding_id': row[3],
                        'chunk_index': row[4],
                        'chunk_type': row[5],
                        'chunk_content_hash': row[6],
                        'start_position': row[7],
                        'end_position': row[8],
                        'start_line': row[9],
                        'end_line': row[10],
                        'start_page': row[11],
                        'end_page': row[12],
                        'section_title': row[13],
                        'section_level': row[14],
                        'parent_chunk_id': row[15],
                        'source_file_path': row[16],
                        'extraction_method': row[17],
                        'confidence_score': row[18],
                        'status': row[19],
                        'metadata': json.loads(row[20]) if row[20] else None,
                        'created_at': row[21],
                        'updated_at': row[22]
                    }
                    for row in rows
                ]

            except Exception as e:
                self._logger.error(f"Failed to get document chunks: {e}")
                raise
            finally:
                conn.close()

    def update_embedding_mapping(self, chunk_id: str, embedding_id: str,
                                vector_index_id: Optional[str] = None,
                                similarity_threshold: float = 0.7,
                                mapping_confidence: float = 1.0) -> bool:
        """
        Update or create embedding mapping for a chunk.

        Args:
            chunk_id: Chunk identifier
            embedding_id: Embedding identifier
            vector_index_id: Vector index identifier
            similarity_threshold: Similarity threshold for retrieval
            mapping_confidence: Confidence in the mapping

        Returns:
            True if updated successfully
        """
        if not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")

        if not (0.0 <= mapping_confidence <= 1.0):
            raise ValueError("Mapping confidence must be between 0.0 and 1.0")

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Update chunk mapping with embedding ID
                cursor.execute("""
                    UPDATE chunk_mappings
                    SET embedding_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE chunk_id = ?
                """, (embedding_id, chunk_id))

                if cursor.rowcount == 0:
                    return False

                # Check if embedding mapping already exists
                cursor.execute("""
                    SELECT mapping_id FROM embedding_mappings
                    WHERE chunk_id = ? AND embedding_id = ?
                """, (chunk_id, embedding_id))

                existing = cursor.fetchone()

                if existing:
                    # Update existing mapping
                    cursor.execute("""
                        UPDATE embedding_mappings
                        SET vector_index_id = ?, similarity_threshold = ?,
                            mapping_confidence = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE chunk_id = ? AND embedding_id = ?
                    """, (vector_index_id, similarity_threshold, mapping_confidence,
                          chunk_id, embedding_id))
                else:
                    # Create new mapping
                    mapping_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO embedding_mappings (
                            mapping_id, chunk_id, embedding_id, vector_index_id,
                            similarity_threshold, mapping_confidence
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (mapping_id, chunk_id, embedding_id, vector_index_id,
                          similarity_threshold, mapping_confidence))

                conn.commit()
                self._logger.debug(f"Updated embedding mapping: {chunk_id} -> {embedding_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update embedding mapping: {e}")
                raise
            finally:
                conn.close()

    def get_chunks_by_embedding(self, embedding_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks associated with an embedding.

        Args:
            embedding_id: Embedding identifier

        Returns:
            List of chunk mapping dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cm.mapping_id, cm.chunk_id, cm.document_id, cm.chunk_index,
                           cm.chunk_type, cm.section_title, cm.confidence_score,
                           em.similarity_threshold, em.mapping_confidence
                    FROM chunk_mappings cm
                    JOIN embedding_mappings em ON cm.chunk_id = em.chunk_id
                    WHERE em.embedding_id = ?
                    ORDER BY cm.chunk_index
                """, (embedding_id,))

                rows = cursor.fetchall()

                return [
                    {
                        'mapping_id': row[0],
                        'chunk_id': row[1],
                        'document_id': row[2],
                        'chunk_index': row[3],
                        'chunk_type': row[4],
                        'section_title': row[5],
                        'confidence_score': row[6],
                        'similarity_threshold': row[7],
                        'mapping_confidence': row[8]
                    }
                    for row in rows
                ]

            except Exception as e:
                self._logger.error(f"Failed to get chunks by embedding: {e}")
                raise
            finally:
                conn.close()

    def add_chunk_relationship(self, source_chunk_id: str, target_chunk_id: str,
                              relationship_type: str, relationship_strength: float = 1.0,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a relationship between two chunks.

        Args:
            source_chunk_id: Source chunk identifier
            target_chunk_id: Target chunk identifier
            relationship_type: Type of relationship (e.g., 'parent', 'sibling', 'reference')
            relationship_strength: Strength of the relationship (0.0 to 1.0)
            metadata: Additional metadata

        Returns:
            Relationship ID
        """
        if not (0.0 <= relationship_strength <= 1.0):
            raise ValueError("Relationship strength must be between 0.0 and 1.0")

        relationship_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Verify both chunks exist
                cursor.execute("SELECT chunk_id FROM chunk_mappings WHERE chunk_id IN (?, ?)",
                             (source_chunk_id, target_chunk_id))
                existing_chunks = {row[0] for row in cursor.fetchall()}

                if source_chunk_id not in existing_chunks:
                    raise ValueError(f"Source chunk {source_chunk_id} not found")
                if target_chunk_id not in existing_chunks:
                    raise ValueError(f"Target chunk {target_chunk_id} not found")

                # Insert relationship
                cursor.execute("""
                    INSERT INTO chunk_relationships (
                        relationship_id, source_chunk_id, target_chunk_id,
                        relationship_type, relationship_strength, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (relationship_id, source_chunk_id, target_chunk_id,
                      relationship_type, relationship_strength,
                      json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.debug(f"Added chunk relationship: {source_chunk_id} -> {target_chunk_id}")
                return relationship_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk relationship: {e}")
                raise
            finally:
                conn.close()

    def delete_chunk_mapping(self, chunk_id: str) -> bool:
        """
        Delete a chunk mapping and all related data.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if chunk exists
                cursor.execute("SELECT mapping_id FROM chunk_mappings WHERE chunk_id = ?", (chunk_id,))
                if not cursor.fetchone():
                    return False

                # Delete related data
                cursor.execute("DELETE FROM chunk_relationships WHERE source_chunk_id = ? OR target_chunk_id = ?",
                             (chunk_id, chunk_id))
                cursor.execute("DELETE FROM chunk_statistics WHERE chunk_id = ?", (chunk_id,))
                cursor.execute("DELETE FROM embedding_mappings WHERE chunk_id = ?", (chunk_id,))

                # Delete chunk mapping
                cursor.execute("DELETE FROM chunk_mappings WHERE chunk_id = ?", (chunk_id,))

                conn.commit()
                self._logger.info(f"Deleted chunk mapping: {chunk_id}")
                return True

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete chunk mapping: {e}")
                raise
            finally:
                conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get basic counts
                cursor.execute("SELECT COUNT(*) FROM chunk_mappings")
                total_mappings = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM chunk_relationships")
                total_relationships = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM embedding_mappings")
                total_embedding_mappings = cursor.fetchone()[0]

                # Get type distribution
                cursor.execute("SELECT chunk_type, COUNT(*) FROM chunk_mappings GROUP BY chunk_type")
                type_distribution = dict(cursor.fetchall())

                # Get status distribution
                cursor.execute("SELECT status, COUNT(*) FROM chunk_mappings GROUP BY status")
                status_distribution = dict(cursor.fetchall())

                return {
                    'total_mappings': total_mappings,
                    'total_relationships': total_relationships,
                    'total_embedding_mappings': total_embedding_mappings,
                    'type_distribution': type_distribution,
                    'status_distribution': status_distribution
                }

            except Exception as e:
                self._logger.error(f"Failed to get statistics: {e}")
                return {}
            finally:
                conn.close()
