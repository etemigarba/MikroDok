"""
Module: document_chunks_db
Description: Manages storage and retrieval of processed text chunks with indexing
Phase: 3
Location: /src/modules/database/documents_db/document_chunks_db/
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


class DocumentChunksDB:
    """
    Document chunks database manager.
    
    Handles storage and retrieval of processed text chunks with position mappings,
    quality metrics, and efficient indexing for fast retrieval. Supports chunk
    deduplication and metadata tracking.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the document chunks database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to documents data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "documents"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "document_chunks.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._chunk_retention_days = 365  # Keep chunks for 1 year
        self._orphaned_chunk_retention_days = 7  # Keep orphaned chunks for 7 days
        
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
                
                # Create document chunks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chunk_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        start_char INTEGER,
                        end_char INTEGER,
                        token_count INTEGER,
                        chunk_hash TEXT NOT NULL,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create chunk quality metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_quality_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_id TEXT NOT NULL UNIQUE,
                        chunk_id TEXT NOT NULL,
                        quality_score REAL NOT NULL,
                        readability_score REAL,
                        coherence_score REAL,
                        information_density REAL,
                        language_confidence REAL,
                        contains_code BOOLEAN DEFAULT 0,
                        contains_tables BOOLEAN DEFAULT 0,
                        contains_formulas BOOLEAN DEFAULT 0,
                        word_count INTEGER,
                        sentence_count INTEGER,
                        paragraph_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chunk_id) REFERENCES document_chunks (chunk_id) ON DELETE CASCADE
                    )
                """)
                
                # Create chunk embeddings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        embedding_id TEXT NOT NULL UNIQUE,
                        chunk_id TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        embedding_vector BLOB,
                        dimension INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chunk_id) REFERENCES document_chunks (chunk_id) ON DELETE CASCADE
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
                        confidence_score REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (source_chunk_id) REFERENCES document_chunks (chunk_id) ON DELETE CASCADE,
                        FOREIGN KEY (target_chunk_id) REFERENCES document_chunks (chunk_id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON document_chunks (chunk_index)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON document_chunks (chunk_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_token_count ON document_chunks (token_count)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_chunk_id ON chunk_quality_metrics (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_score ON chunk_quality_metrics (quality_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON chunk_embeddings (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON chunk_embeddings (model_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_source ON chunk_relationships (source_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_target ON chunk_relationships (target_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_type ON chunk_relationships (relationship_type)")
                
                # Create unique constraints
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_document_index ON document_chunks (document_id, chunk_index)")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_chunk_model ON chunk_embeddings (chunk_id, model_name)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_chunks_timestamp 
                    AFTER UPDATE ON document_chunks
                    BEGIN
                        UPDATE document_chunks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                # Create full-text search index
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        content,
                        content='document_chunks',
                        content_rowid='id'
                    )
                """)
                
                # Create triggers to maintain FTS index
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON document_chunks BEGIN
                        INSERT INTO chunks_fts(rowid, chunk_id, content) VALUES (new.id, new.chunk_id, new.content);
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON document_chunks BEGIN
                        INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, content) VALUES('delete', old.id, old.chunk_id, old.content);
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE ON document_chunks BEGIN
                        INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, content) VALUES('delete', old.id, old.chunk_id, old.content);
                        INSERT INTO chunks_fts(rowid, chunk_id, content) VALUES (new.id, new.chunk_id, new.content);
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = ['document_chunks', 'chunk_quality_metrics', 'chunk_embeddings', 'chunk_relationships', 'chunks_fts']

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Document chunks database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize document chunks database: {e}")
                raise
            finally:
                conn.close()
    
    def add_chunk(self, document_id: str, chunk_index: int, content: str,
                  start_char: Optional[int] = None, end_char: Optional[int] = None,
                  token_count: Optional[int] = None, 
                  metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new document chunk.
        
        Args:
            document_id: Parent document identifier
            chunk_index: Sequential chunk number within document
            content: Text content of the chunk
            start_char: Starting character position in original document
            end_char: Ending character position in original document
            token_count: Number of tokens in chunk
            metadata: Additional chunk properties
            
        Returns:
            Chunk ID of the added chunk
        """
        chunk_id = str(uuid.uuid4())
        chunk_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Check for duplicate chunk in same document
                cursor.execute("""
                    SELECT chunk_id FROM document_chunks 
                    WHERE document_id = ? AND chunk_index = ?
                """, (document_id, chunk_index))
                existing = cursor.fetchone()
                if existing:
                    raise ValueError(f"Chunk at index {chunk_index} already exists for document {document_id}")
                
                # Insert new chunk
                cursor.execute("""
                    INSERT INTO document_chunks (
                        chunk_id, document_id, chunk_index, content, start_char,
                        end_char, token_count, chunk_hash, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_id,
                    document_id,
                    chunk_index,
                    content,
                    start_char,
                    end_char,
                    token_count,
                    chunk_hash,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                self._logger.info(f"Added chunk {chunk_id} for document {document_id}")
                return chunk_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Chunk data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT chunk_id, document_id, chunk_index, content, start_char,
                           end_char, token_count, chunk_hash, metadata, created_at, updated_at
                    FROM document_chunks WHERE chunk_id = ?
                """, (chunk_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'chunk_id': row[0],
                    'document_id': row[1],
                    'chunk_index': row[2],
                    'content': row[3],
                    'start_char': row[4],
                    'end_char': row[5],
                    'token_count': row[6],
                    'chunk_hash': row[7],
                    'metadata': json.loads(row[8]) if row[8] else None,
                    'created_at': row[9],
                    'updated_at': row[10]
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_document_chunks(self, document_id: str,
                           limit: Optional[int] = None,
                           offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document.

        Args:
            document_id: Document identifier
            limit: Maximum number of chunks to return
            offset: Number of chunks to skip

        Returns:
            List of chunk data dictionaries ordered by chunk_index
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if limit:
                    cursor.execute("""
                        SELECT chunk_id, document_id, chunk_index, content, start_char,
                               end_char, token_count, chunk_hash, metadata, created_at, updated_at
                        FROM document_chunks
                        WHERE document_id = ?
                        ORDER BY chunk_index
                        LIMIT ? OFFSET ?
                    """, (document_id, limit, offset))
                else:
                    cursor.execute("""
                        SELECT chunk_id, document_id, chunk_index, content, start_char,
                               end_char, token_count, chunk_hash, metadata, created_at, updated_at
                        FROM document_chunks
                        WHERE document_id = ?
                        ORDER BY chunk_index
                        OFFSET ?
                    """, (document_id, offset))

                rows = cursor.fetchall()
                chunks = []

                for row in rows:
                    chunks.append({
                        'chunk_id': row[0],
                        'document_id': row[1],
                        'chunk_index': row[2],
                        'content': row[3],
                        'start_char': row[4],
                        'end_char': row[5],
                        'token_count': row[6],
                        'chunk_hash': row[7],
                        'metadata': json.loads(row[8]) if row[8] else None,
                        'created_at': row[9],
                        'updated_at': row[10]
                    })

                return chunks

            except Exception as e:
                self._logger.error(f"Failed to get chunks for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def search_chunks(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search chunks using full-text search.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            List of matching chunk data dictionaries with relevance scores
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT dc.chunk_id, dc.document_id, dc.chunk_index, dc.content,
                           dc.start_char, dc.end_char, dc.token_count, dc.chunk_hash,
                           dc.metadata, dc.created_at, dc.updated_at, fts.rank
                    FROM chunks_fts fts
                    JOIN document_chunks dc ON dc.chunk_id = fts.chunk_id
                    WHERE chunks_fts MATCH ?
                    ORDER BY fts.rank
                    LIMIT ?
                """, (query, limit))

                rows = cursor.fetchall()
                chunks = []

                for row in rows:
                    chunks.append({
                        'chunk_id': row[0],
                        'document_id': row[1],
                        'chunk_index': row[2],
                        'content': row[3],
                        'start_char': row[4],
                        'end_char': row[5],
                        'token_count': row[6],
                        'chunk_hash': row[7],
                        'metadata': json.loads(row[8]) if row[8] else None,
                        'created_at': row[9],
                        'updated_at': row[10],
                        'relevance_score': row[11]
                    })

                return chunks

            except Exception as e:
                self._logger.error(f"Failed to search chunks with query '{query}': {e}")
                raise
            finally:
                conn.close()

    def add_quality_metrics(self, chunk_id: str, quality_score: float,
                           readability_score: Optional[float] = None,
                           coherence_score: Optional[float] = None,
                           information_density: Optional[float] = None,
                           language_confidence: Optional[float] = None,
                           contains_code: bool = False,
                           contains_tables: bool = False,
                           contains_formulas: bool = False,
                           word_count: Optional[int] = None,
                           sentence_count: Optional[int] = None,
                           paragraph_count: Optional[int] = None) -> str:
        """
        Add quality metrics for a chunk.

        Args:
            chunk_id: Chunk identifier
            quality_score: Overall quality score (0.0-1.0)
            readability_score: Readability score (0.0-1.0)
            coherence_score: Coherence score (0.0-1.0)
            information_density: Information density score (0.0-1.0)
            language_confidence: Language detection confidence (0.0-1.0)
            contains_code: Whether chunk contains code
            contains_tables: Whether chunk contains tables
            contains_formulas: Whether chunk contains formulas
            word_count: Number of words
            sentence_count: Number of sentences
            paragraph_count: Number of paragraphs

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chunk_quality_metrics (
                        metric_id, chunk_id, quality_score, readability_score,
                        coherence_score, information_density, language_confidence,
                        contains_code, contains_tables, contains_formulas,
                        word_count, sentence_count, paragraph_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, chunk_id, quality_score, readability_score,
                    coherence_score, information_density, language_confidence,
                    contains_code, contains_tables, contains_formulas,
                    word_count, sentence_count, paragraph_count
                ))

                conn.commit()
                self._logger.info(f"Added quality metrics {metric_id} for chunk {chunk_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add quality metrics for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_quality_metrics(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get quality metrics for a chunk.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Quality metrics dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT metric_id, quality_score, readability_score, coherence_score,
                           information_density, language_confidence, contains_code,
                           contains_tables, contains_formulas, word_count,
                           sentence_count, paragraph_count, created_at
                    FROM chunk_quality_metrics WHERE chunk_id = ?
                """, (chunk_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'metric_id': row[0],
                    'quality_score': row[1],
                    'readability_score': row[2],
                    'coherence_score': row[3],
                    'information_density': row[4],
                    'language_confidence': row[5],
                    'contains_code': bool(row[6]),
                    'contains_tables': bool(row[7]),
                    'contains_formulas': bool(row[8]),
                    'word_count': row[9],
                    'sentence_count': row[10],
                    'paragraph_count': row[11],
                    'created_at': row[12]
                }

            except Exception as e:
                self._logger.error(f"Failed to get quality metrics for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def add_embedding(self, chunk_id: str, model_name: str,
                     embedding_vector: bytes, dimension: int) -> str:
        """
        Add embedding vector for a chunk.

        Args:
            chunk_id: Chunk identifier
            model_name: Name of the embedding model
            embedding_vector: Serialized embedding vector
            dimension: Vector dimension

        Returns:
            Embedding ID
        """
        embedding_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO chunk_embeddings (
                        embedding_id, chunk_id, model_name, embedding_vector, dimension
                    ) VALUES (?, ?, ?, ?, ?)
                """, (embedding_id, chunk_id, model_name, embedding_vector, dimension))

                conn.commit()
                self._logger.info(f"Added embedding {embedding_id} for chunk {chunk_id}")
                return embedding_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add embedding for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_embedding(self, chunk_id: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get embedding for a chunk and model.

        Args:
            chunk_id: Chunk identifier
            model_name: Name of the embedding model

        Returns:
            Embedding data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT embedding_id, embedding_vector, dimension, created_at
                    FROM chunk_embeddings
                    WHERE chunk_id = ? AND model_name = ?
                """, (chunk_id, model_name))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'embedding_id': row[0],
                    'embedding_vector': row[1],
                    'dimension': row[2],
                    'created_at': row[3]
                }

            except Exception as e:
                self._logger.error(f"Failed to get embedding for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def add_relationship(self, source_chunk_id: str, target_chunk_id: str,
                        relationship_type: str, confidence_score: float = 1.0) -> str:
        """
        Add relationship between chunks.

        Args:
            source_chunk_id: Source chunk identifier
            target_chunk_id: Target chunk identifier
            relationship_type: Type of relationship (e.g., 'follows', 'references', 'similar')
            confidence_score: Confidence in the relationship (0.0-1.0)

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
                        relationship_type, confidence_score
                    ) VALUES (?, ?, ?, ?, ?)
                """, (relationship_id, source_chunk_id, target_chunk_id,
                      relationship_type, confidence_score))

                conn.commit()
                self._logger.info(f"Added relationship {relationship_id} between chunks")
                return relationship_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add chunk relationship: {e}")
                raise
            finally:
                conn.close()

    def get_chunk_relationships(self, chunk_id: str,
                               relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get relationships for a chunk.

        Args:
            chunk_id: Chunk identifier
            relationship_type: Filter by relationship type (optional)

        Returns:
            List of relationship data dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if relationship_type:
                    cursor.execute("""
                        SELECT relationship_id, source_chunk_id, target_chunk_id,
                               relationship_type, confidence_score, created_at
                        FROM chunk_relationships
                        WHERE (source_chunk_id = ? OR target_chunk_id = ?)
                        AND relationship_type = ?
                        ORDER BY confidence_score DESC
                    """, (chunk_id, chunk_id, relationship_type))
                else:
                    cursor.execute("""
                        SELECT relationship_id, source_chunk_id, target_chunk_id,
                               relationship_type, confidence_score, created_at
                        FROM chunk_relationships
                        WHERE source_chunk_id = ? OR target_chunk_id = ?
                        ORDER BY confidence_score DESC
                    """, (chunk_id, chunk_id))

                rows = cursor.fetchall()
                relationships = []

                for row in rows:
                    relationships.append({
                        'relationship_id': row[0],
                        'source_chunk_id': row[1],
                        'target_chunk_id': row[2],
                        'relationship_type': row[3],
                        'confidence_score': row[4],
                        'created_at': row[5]
                    })

                return relationships

            except Exception as e:
                self._logger.error(f"Failed to get relationships for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_chunk(self, chunk_id: str) -> bool:
        """
        Delete a chunk and all associated data.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deletion was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM document_chunks WHERE chunk_id = ?", (chunk_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    self._logger.info(f"Deleted chunk {chunk_id}")
                    return True
                else:
                    self._logger.warning(f"Chunk {chunk_id} not found for deletion")
                    return False

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_document_chunks(self, document_id: str) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of chunks deleted
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
                conn.commit()

                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self._logger.info(f"Deleted {deleted_count} chunks for document {document_id}")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete chunks for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def find_similar_chunks(self, chunk_hash: str, exclude_chunk_id: Optional[str] = None) -> List[str]:
        """
        Find chunks with similar content based on hash.

        Args:
            chunk_hash: Hash to search for
            exclude_chunk_id: Chunk ID to exclude from results

        Returns:
            List of similar chunk IDs
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if exclude_chunk_id:
                    cursor.execute("""
                        SELECT chunk_id FROM document_chunks
                        WHERE chunk_hash = ? AND chunk_id != ?
                    """, (chunk_hash, exclude_chunk_id))
                else:
                    cursor.execute("""
                        SELECT chunk_id FROM document_chunks
                        WHERE chunk_hash = ?
                    """, (chunk_hash,))

                rows = cursor.fetchall()
                return [row[0] for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to find similar chunks: {e}")
                raise
            finally:
                conn.close()

    def get_chunks_by_quality(self, min_quality_score: float = 0.0,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get chunks filtered by quality score.

        Args:
            min_quality_score: Minimum quality score threshold
            limit: Maximum number of chunks to return

        Returns:
            List of chunk data dictionaries with quality metrics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT dc.chunk_id, dc.document_id, dc.chunk_index, dc.content,
                           dc.start_char, dc.end_char, dc.token_count, dc.chunk_hash,
                           dc.metadata, dc.created_at, dc.updated_at,
                           qm.quality_score, qm.readability_score, qm.coherence_score
                    FROM document_chunks dc
                    JOIN chunk_quality_metrics qm ON dc.chunk_id = qm.chunk_id
                    WHERE qm.quality_score >= ?
                    ORDER BY qm.quality_score DESC
                    LIMIT ?
                """, (min_quality_score, limit))

                rows = cursor.fetchall()
                chunks = []

                for row in rows:
                    chunks.append({
                        'chunk_id': row[0],
                        'document_id': row[1],
                        'chunk_index': row[2],
                        'content': row[3],
                        'start_char': row[4],
                        'end_char': row[5],
                        'token_count': row[6],
                        'chunk_hash': row[7],
                        'metadata': json.loads(row[8]) if row[8] else None,
                        'created_at': row[9],
                        'updated_at': row[10],
                        'quality_score': row[11],
                        'readability_score': row[12],
                        'coherence_score': row[13]
                    })

                return chunks

            except Exception as e:
                self._logger.error(f"Failed to get chunks by quality: {e}")
                raise
            finally:
                conn.close()

    def cleanup_orphaned_chunks(self) -> int:
        """
        Clean up chunks that no longer have associated documents.

        Returns:
            Number of orphaned chunks cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Find orphaned chunks (chunks without corresponding documents)
                cutoff_date = datetime.now() - timedelta(days=self._orphaned_chunk_retention_days)

                cursor.execute("""
                    DELETE FROM document_chunks
                    WHERE document_id NOT IN (
                        SELECT DISTINCT document_id FROM documents
                    ) AND created_at < ?
                """, (cutoff_date.isoformat(),))

                orphaned_count = cursor.rowcount
                conn.commit()

                if orphaned_count > 0:
                    self._logger.info(f"Cleaned up {orphaned_count} orphaned chunks")

                return orphaned_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup orphaned chunks: {e}")
                raise
            finally:
                conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get chunks database statistics.

        Returns:
            Dictionary with database statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get total chunk count
                cursor.execute("SELECT COUNT(*) FROM document_chunks")
                total_chunks = cursor.fetchone()[0]

                # Get chunks with quality metrics
                cursor.execute("SELECT COUNT(*) FROM chunk_quality_metrics")
                chunks_with_quality = cursor.fetchone()[0]

                # Get chunks with embeddings
                cursor.execute("SELECT COUNT(DISTINCT chunk_id) FROM chunk_embeddings")
                chunks_with_embeddings = cursor.fetchone()[0]

                # Get average quality score
                cursor.execute("SELECT AVG(quality_score) FROM chunk_quality_metrics")
                avg_quality = cursor.fetchone()[0] or 0.0

                # Get total relationships
                cursor.execute("SELECT COUNT(*) FROM chunk_relationships")
                total_relationships = cursor.fetchone()[0]

                # Get token count statistics
                cursor.execute("""
                    SELECT AVG(token_count), MIN(token_count), MAX(token_count)
                    FROM document_chunks WHERE token_count IS NOT NULL
                """)
                token_stats = cursor.fetchone()

                return {
                    'total_chunks': total_chunks,
                    'chunks_with_quality_metrics': chunks_with_quality,
                    'chunks_with_embeddings': chunks_with_embeddings,
                    'average_quality_score': round(avg_quality, 3),
                    'total_relationships': total_relationships,
                    'average_token_count': round(token_stats[0], 1) if token_stats[0] else 0,
                    'min_token_count': token_stats[1] or 0,
                    'max_token_count': token_stats[2] or 0,
                    'database_path': self._db_path
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunks statistics: {e}")
                raise
            finally:
                conn.close()
