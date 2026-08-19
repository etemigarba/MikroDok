"""
Module: document_chunks_db
Description: Stores processed text chunks with position mappings and quality metrics
Phase: 3
Location: /src/modules/database/document_repository_db/document_chunks_db/
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


class DocumentChunksDB:
    """
    Document chunks database manager for the document repository.
    
    Manages storage and retrieval of processed text chunks with position mappings,
    quality metrics, and efficient indexing for fast retrieval. Supports chunk
    deduplication, metadata tracking, and batch operations for performance.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the document chunks database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to document repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "document_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "document_chunks.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._chunk_retention_days = 365  # Keep chunks for 1 year
        self._orphaned_chunk_retention_days = 7  # Keep orphaned chunks for 7 days
        self._max_chunks_per_document = 10000  # Maximum chunks per document
        self._batch_size = 500  # Batch size for bulk operations
        
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
                        start_line INTEGER,
                        end_line INTEGER,
                        token_count INTEGER,
                        word_count INTEGER,
                        sentence_count INTEGER,
                        paragraph_count INTEGER,
                        chunk_hash TEXT NOT NULL,
                        chunk_type TEXT NOT NULL DEFAULT 'text',
                        language TEXT,
                        encoding TEXT DEFAULT 'utf-8',
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT chk_chunk_type CHECK (chunk_type IN ('text', 'code', 'table', 'formula', 'header', 'footer'))
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
                        contains_urls BOOLEAN DEFAULT 0,
                        contains_emails BOOLEAN DEFAULT 0,
                        special_characters_ratio REAL,
                        uppercase_ratio REAL,
                        punctuation_ratio REAL,
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
                        norm REAL,
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
                        similarity_score REAL,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (source_chunk_id) REFERENCES document_chunks (chunk_id) ON DELETE CASCADE,
                        FOREIGN KEY (target_chunk_id) REFERENCES document_chunks (chunk_id) ON DELETE CASCADE,
                        CONSTRAINT chk_relationship_type CHECK (relationship_type IN ('similar', 'sequential', 'reference', 'duplicate'))
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON document_chunks (chunk_index)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON document_chunks (chunk_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_type ON document_chunks (chunk_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON document_chunks (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_quality_chunk_id ON chunk_quality_metrics (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_quality_score ON chunk_quality_metrics (quality_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk_id ON chunk_embeddings (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings (model_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_relationships_source ON chunk_relationships (source_chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_relationships_target ON chunk_relationships (target_chunk_id)")
                
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
                self._logger.info("Document chunks database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize document chunks database: {e}")
                raise
            finally:
                conn.close()

    def create_chunk(self, document_id: str, chunk_index: int, content: str,
                    start_char: Optional[int] = None, end_char: Optional[int] = None,
                    start_line: Optional[int] = None, end_line: Optional[int] = None,
                    token_count: Optional[int] = None, word_count: Optional[int] = None,
                    sentence_count: Optional[int] = None, paragraph_count: Optional[int] = None,
                    chunk_type: str = 'text', language: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new document chunk.

        Args:
            document_id: Parent document identifier
            chunk_index: Sequential index within document
            content: Text content of the chunk
            start_char: Starting character position
            end_char: Ending character position
            start_line: Starting line number
            end_line: Ending line number
            token_count: Number of tokens
            word_count: Number of words
            sentence_count: Number of sentences
            paragraph_count: Number of paragraphs
            chunk_type: Type of chunk content
            language: Detected language
            metadata: Additional metadata

        Returns:
            Chunk ID
        """
        chunk_id = str(uuid.uuid4())
        chunk_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Insert chunk
                cursor.execute("""
                    INSERT INTO document_chunks (
                        chunk_id, document_id, chunk_index, content, start_char, end_char,
                        start_line, end_line, token_count, word_count, sentence_count,
                        paragraph_count, chunk_hash, chunk_type, language, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_id, document_id, chunk_index, content, start_char, end_char,
                    start_line, end_line, token_count, word_count, sentence_count,
                    paragraph_count, chunk_hash, chunk_type, language,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Created chunk {chunk_id} for document {document_id}")
                return chunk_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create chunk for document {document_id}: {e}")
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
                    SELECT chunk_id, document_id, chunk_index, content, start_char, end_char,
                           start_line, end_line, token_count, word_count, sentence_count,
                           paragraph_count, chunk_hash, chunk_type, language, encoding,
                           metadata, created_at, updated_at
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
                    'start_line': row[6],
                    'end_line': row[7],
                    'token_count': row[8],
                    'word_count': row[9],
                    'sentence_count': row[10],
                    'paragraph_count': row[11],
                    'chunk_hash': row[12],
                    'chunk_type': row[13],
                    'language': row[14],
                    'encoding': row[15],
                    'metadata': json.loads(row[16]) if row[16] else None,
                    'created_at': row[17],
                    'updated_at': row[18]
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_document_chunks(self, document_id: str,
                           chunk_type: Optional[str] = None,
                           limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document.

        Args:
            document_id: Document identifier
            chunk_type: Optional filter by chunk type
            limit: Maximum number of chunks to return
            offset: Number of chunks to skip

        Returns:
            List of chunk dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with optional filter
                query = """
                    SELECT chunk_id, document_id, chunk_index, content, start_char, end_char,
                           start_line, end_line, token_count, word_count, sentence_count,
                           paragraph_count, chunk_hash, chunk_type, language, encoding,
                           metadata, created_at, updated_at
                    FROM document_chunks WHERE document_id = ?
                """
                params = [document_id]

                if chunk_type:
                    query += " AND chunk_type = ?"
                    params.append(chunk_type)

                query += " ORDER BY chunk_index LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
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
                        'start_line': row[6],
                        'end_line': row[7],
                        'token_count': row[8],
                        'word_count': row[9],
                        'sentence_count': row[10],
                        'paragraph_count': row[11],
                        'chunk_hash': row[12],
                        'chunk_type': row[13],
                        'language': row[14],
                        'encoding': row[15],
                        'metadata': json.loads(row[16]) if row[16] else None,
                        'created_at': row[17],
                        'updated_at': row[18]
                    })

                return chunks

            except Exception as e:
                self._logger.error(f"Failed to get chunks for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def update_chunk_content(self, chunk_id: str, content: str,
                           token_count: Optional[int] = None,
                           word_count: Optional[int] = None,
                           sentence_count: Optional[int] = None,
                           paragraph_count: Optional[int] = None) -> bool:
        """
        Update chunk content and statistics.

        Args:
            chunk_id: Chunk identifier
            content: New content
            token_count: Updated token count
            word_count: Updated word count
            sentence_count: Updated sentence count
            paragraph_count: Updated paragraph count

        Returns:
            True if updated successfully
        """
        chunk_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE document_chunks
                    SET content = ?, chunk_hash = ?, token_count = ?, word_count = ?,
                        sentence_count = ?, paragraph_count = ?, updated_at = ?
                    WHERE chunk_id = ?
                """, (content, chunk_hash, token_count, word_count, sentence_count,
                      paragraph_count, datetime.now(timezone.utc).isoformat(), chunk_id))

                conn.commit()
                self._logger.info(f"Updated chunk {chunk_id} content")
                return cursor.rowcount > 0

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to update chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_chunk(self, chunk_id: str) -> bool:
        """
        Delete a chunk.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete chunk (cascades to related tables)
                cursor.execute("DELETE FROM document_chunks WHERE chunk_id = ?", (chunk_id,))

                conn.commit()
                self._logger.info(f"Deleted chunk {chunk_id}")
                return cursor.rowcount > 0

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

                # Delete all chunks for document
                cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))

                deleted_count = cursor.rowcount
                conn.commit()
                self._logger.info(f"Deleted {deleted_count} chunks for document {document_id}")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete chunks for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def add_chunk_quality_metrics(self, chunk_id: str, quality_score: float,
                                 readability_score: Optional[float] = None,
                                 coherence_score: Optional[float] = None,
                                 information_density: Optional[float] = None,
                                 language_confidence: Optional[float] = None,
                                 contains_code: bool = False,
                                 contains_tables: bool = False,
                                 contains_formulas: bool = False,
                                 contains_urls: bool = False,
                                 contains_emails: bool = False,
                                 special_characters_ratio: Optional[float] = None,
                                 uppercase_ratio: Optional[float] = None,
                                 punctuation_ratio: Optional[float] = None) -> str:
        """
        Add quality metrics for a chunk.

        Args:
            chunk_id: Chunk identifier
            quality_score: Overall quality score
            readability_score: Readability score
            coherence_score: Coherence score
            information_density: Information density score
            language_confidence: Language detection confidence
            contains_code: Whether chunk contains code
            contains_tables: Whether chunk contains tables
            contains_formulas: Whether chunk contains formulas
            contains_urls: Whether chunk contains URLs
            contains_emails: Whether chunk contains email addresses
            special_characters_ratio: Ratio of special characters
            uppercase_ratio: Ratio of uppercase characters
            punctuation_ratio: Ratio of punctuation characters

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
                        contains_urls, contains_emails, special_characters_ratio,
                        uppercase_ratio, punctuation_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, chunk_id, quality_score, readability_score,
                    coherence_score, information_density, language_confidence,
                    contains_code, contains_tables, contains_formulas,
                    contains_urls, contains_emails, special_characters_ratio,
                    uppercase_ratio, punctuation_ratio
                ))

                conn.commit()
                self._logger.info(f"Added quality metrics for chunk {chunk_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add quality metrics for chunk {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def search_chunks(self, query: str, document_id: Optional[str] = None,
                     chunk_type: Optional[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search chunks using full-text search.

        Args:
            query: Search query
            document_id: Optional filter by document ID
            chunk_type: Optional filter by chunk type
            limit: Maximum number of results

        Returns:
            List of matching chunks with relevance scores
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build FTS query
                fts_query = """
                    SELECT c.chunk_id, c.document_id, c.chunk_index, c.content,
                           c.start_char, c.end_char, c.chunk_type, c.language,
                           c.metadata, c.created_at, fts.rank
                    FROM chunks_fts fts
                    JOIN document_chunks c ON c.chunk_id = fts.chunk_id
                    WHERE chunks_fts MATCH ?
                """
                params = [query]

                if document_id:
                    fts_query += " AND c.document_id = ?"
                    params.append(document_id)

                if chunk_type:
                    fts_query += " AND c.chunk_type = ?"
                    params.append(chunk_type)

                fts_query += " ORDER BY fts.rank LIMIT ?"
                params.append(limit)

                cursor.execute(fts_query, params)
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    results.append({
                        'chunk_id': row[0],
                        'document_id': row[1],
                        'chunk_index': row[2],
                        'content': row[3],
                        'start_char': row[4],
                        'end_char': row[5],
                        'chunk_type': row[6],
                        'language': row[7],
                        'metadata': json.loads(row[8]) if row[8] else None,
                        'created_at': row[9],
                        'relevance_score': row[10]
                    })

                return results

            except Exception as e:
                self._logger.error(f"Failed to search chunks: {e}")
                raise
            finally:
                conn.close()

    def find_similar_chunks(self, chunk_id: str, similarity_threshold: float = 0.8,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find chunks similar to the given chunk.

        Args:
            chunk_id: Reference chunk ID
            similarity_threshold: Minimum similarity score
            limit: Maximum number of results

        Returns:
            List of similar chunks with similarity scores
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get similar chunks from relationships
                cursor.execute("""
                    SELECT c.chunk_id, c.document_id, c.chunk_index, c.content,
                           c.chunk_type, c.language, c.metadata, c.created_at,
                           r.similarity_score
                    FROM chunk_relationships r
                    JOIN document_chunks c ON c.chunk_id = r.target_chunk_id
                    WHERE r.source_chunk_id = ?
                      AND r.relationship_type = 'similar'
                      AND r.similarity_score >= ?
                    ORDER BY r.similarity_score DESC
                    LIMIT ?
                """, (chunk_id, similarity_threshold, limit))

                rows = cursor.fetchall()

                similar_chunks = []
                for row in rows:
                    similar_chunks.append({
                        'chunk_id': row[0],
                        'document_id': row[1],
                        'chunk_index': row[2],
                        'content': row[3],
                        'chunk_type': row[4],
                        'language': row[5],
                        'metadata': json.loads(row[6]) if row[6] else None,
                        'created_at': row[7],
                        'similarity_score': row[8]
                    })

                return similar_chunks

            except Exception as e:
                self._logger.error(f"Failed to find similar chunks for {chunk_id}: {e}")
                raise
            finally:
                conn.close()

    def get_chunk_statistics(self, document_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get chunk statistics.

        Args:
            document_id: Optional filter by document ID

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
                if document_id:
                    where_clause = "WHERE document_id = ?"
                    params.append(document_id)

                # Total chunks
                cursor.execute(f"SELECT COUNT(*) FROM document_chunks {where_clause}", params)
                total_chunks = cursor.fetchone()[0]

                # Chunks by type
                cursor.execute(f"""
                    SELECT chunk_type, COUNT(*) FROM document_chunks {where_clause}
                    GROUP BY chunk_type
                """, params)
                type_counts = dict(cursor.fetchall())

                # Average chunk size
                cursor.execute(f"SELECT AVG(LENGTH(content)) FROM document_chunks {where_clause}", params)
                avg_size = cursor.fetchone()[0] or 0

                # Average token count
                cursor.execute(f"SELECT AVG(token_count) FROM document_chunks {where_clause}", params)
                avg_tokens = cursor.fetchone()[0] or 0

                # Language distribution
                cursor.execute(f"""
                    SELECT language, COUNT(*) FROM document_chunks {where_clause}
                    GROUP BY language
                """, params)
                language_counts = dict(cursor.fetchall())

                return {
                    'total_chunks': total_chunks,
                    'type_counts': type_counts,
                    'average_size_chars': avg_size,
                    'average_token_count': avg_tokens,
                    'language_counts': language_counts
                }

            except Exception as e:
                self._logger.error(f"Failed to get chunk statistics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_orphaned_chunks(self) -> int:
        """
        Clean up orphaned chunks that no longer have parent documents.

        Returns:
            Number of chunks cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate cutoff date
                cutoff = datetime.now(timezone.utc) - timedelta(days=self._orphaned_chunk_retention_days)

                # Delete orphaned chunks
                cursor.execute("""
                    DELETE FROM document_chunks
                    WHERE document_id NOT IN (
                        SELECT DISTINCT document_id FROM documents
                    ) AND created_at < ?
                """, (cutoff.isoformat(),))

                deleted_count = cursor.rowcount
                conn.commit()
                self._logger.info(f"Cleaned up {deleted_count} orphaned chunks")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup orphaned chunks: {e}")
                raise
            finally:
                conn.close()
