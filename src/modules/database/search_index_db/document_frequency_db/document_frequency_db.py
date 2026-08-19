"""
Module: document_frequency_db
Description: Stores document frequency statistics for BM25 ranking with SQLite backend
Phase: 4
Location: /src/modules/database/search_index_db/document_frequency_db/
"""

# Standard library imports
import json
import math
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class DocumentFrequencyDB:
    """
    Repository pattern for managing document frequency statistics persistence.
    
    Provides BM25 ranking support through document frequency storage with SQLite backend.
    Manages term document frequencies, collection statistics, and scoring parameters for
    efficient relevance ranking in search operations. Designed for offline operation with
    optimized statistical computations and caching.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the document frequency database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self._db_path = db_path or Path("data/search_index/document_frequency.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Threading and synchronization
        self._lock = threading.RLock()
        
        # Logging
        self._logger = get_logger("document_frequency_db")
        
        # BM25 parameters
        self._k1 = 1.2  # Term frequency saturation parameter
        self._b = 0.75  # Length normalization parameter
        
        # In-memory cache for frequently accessed statistics
        self._stats_cache: Dict[str, Any] = {}
        self._cache_size_limit = 5000
        
        # Collection statistics cache
        self._collection_stats: Optional[Dict[str, Any]] = None
        self._stats_cache_ttl = 300  # 5 minutes
        self._last_stats_update = 0
        
        # Initialize database
        self._initialize_database()
        
        self._logger.info(f"DocumentFrequencyDB initialized with database: {self._db_path}")
    
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
                
                # Create document frequency table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_frequency (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        term TEXT UNIQUE NOT NULL,
                        document_frequency INTEGER NOT NULL DEFAULT 0,
                        collection_frequency INTEGER NOT NULL DEFAULT 0,
                        idf_score REAL,  -- Inverse Document Frequency
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create document statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT UNIQUE NOT NULL,
                        document_length INTEGER NOT NULL DEFAULT 0,
                        unique_terms INTEGER NOT NULL DEFAULT 0,
                        avg_term_frequency REAL DEFAULT 0.0,
                        max_term_frequency INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create collection statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS collection_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        total_documents INTEGER NOT NULL DEFAULT 0,
                        total_terms INTEGER NOT NULL DEFAULT 0,
                        unique_terms INTEGER NOT NULL DEFAULT 0,
                        avg_document_length REAL DEFAULT 0.0,
                        total_collection_frequency INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create BM25 scores cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bm25_scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        term TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        tf_score REAL NOT NULL,
                        idf_score REAL NOT NULL,
                        bm25_score REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(term, document_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_df_term ON document_frequency(term)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_df_frequency ON document_frequency(document_frequency)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_df_idf ON document_frequency(idf_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_stats_id ON document_statistics(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_stats_length ON document_statistics(document_length)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm25_term ON bm25_scores(term)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm25_document ON bm25_scores(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm25_score ON bm25_scores(bm25_score)")
                
                # Create triggers for automatic timestamp updates
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_df_timestamp
                    AFTER UPDATE ON document_frequency
                    BEGIN
                        UPDATE document_frequency SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_doc_stats_timestamp
                    AFTER UPDATE ON document_statistics
                    BEGIN
                        UPDATE document_statistics SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                # Initialize collection statistics if empty
                cursor.execute("SELECT COUNT(*) FROM collection_statistics")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO collection_statistics 
                        (total_documents, total_terms, unique_terms, avg_document_length, total_collection_frequency)
                        VALUES (0, 0, 0, 0.0, 0)
                    """)
                
                conn.commit()
                self._logger.info("Document frequency database schema initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize database schema: {e}")
                raise
            finally:
                conn.close()
    
    def update_term_frequency(self, term: str, document_frequency: int, collection_frequency: int) -> bool:
        """
        Update document frequency statistics for a term.
        
        Args:
            term: The term to update
            document_frequency: Number of documents containing the term
            collection_frequency: Total occurrences of the term in collection
        
        Returns:
            True if successful, False otherwise
        """
        if not term or document_frequency < 0 or collection_frequency < 0:
            return False
        
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    # Get total documents for IDF calculation
                    total_docs = self._get_total_documents(cursor)
                    
                    # Calculate IDF score
                    idf_score = self._calculate_idf(document_frequency, total_docs)
                    
                    # Insert or update term frequency
                    cursor.execute("""
                        INSERT OR REPLACE INTO document_frequency 
                        (term, document_frequency, collection_frequency, idf_score)
                        VALUES (?, ?, ?, ?)
                    """, (term.lower().strip(), document_frequency, collection_frequency, idf_score))
                    
                    conn.commit()
                    
                    # Clear cache for this term
                    self._stats_cache.pop(term.lower().strip(), None)
                    self._collection_stats = None  # Invalidate collection stats cache
                    
                    self._logger.debug(f"Updated frequency for term '{term}': df={document_frequency}, cf={collection_frequency}")
                    return True
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update term frequency: {e}")
                    return False
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return False

    def _calculate_idf(self, document_frequency: int, total_documents: int) -> float:
        """
        Calculate Inverse Document Frequency (IDF) score.

        Args:
            document_frequency: Number of documents containing the term
            total_documents: Total number of documents in collection

        Returns:
            IDF score
        """
        if document_frequency == 0 or total_documents == 0:
            return 0.0

        # Standard IDF formula: log(N/df)
        return math.log(total_documents / document_frequency)

    def _get_total_documents(self, cursor: sqlite3.Cursor) -> int:
        """Get total number of documents in the collection."""
        cursor.execute("SELECT total_documents FROM collection_statistics ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 0

    def calculate_bm25_score(self, term: str, document_id: str, term_frequency: int) -> float:
        """
        Calculate BM25 score for a term in a document.

        Args:
            term: The search term
            document_id: Document identifier
            term_frequency: Frequency of term in the document

        Returns:
            BM25 score
        """
        if not term or not document_id or term_frequency <= 0:
            return 0.0

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get term's IDF score
                    cursor.execute("SELECT idf_score FROM document_frequency WHERE term = ?", (term.lower().strip(),))
                    idf_result = cursor.fetchone()
                    if not idf_result:
                        return 0.0

                    idf_score = idf_result[0]

                    # Get document length
                    cursor.execute("SELECT document_length FROM document_statistics WHERE document_id = ?", (document_id,))
                    doc_result = cursor.fetchone()
                    if not doc_result:
                        return 0.0

                    doc_length = doc_result[0]

                    # Get average document length
                    avg_doc_length = self._get_average_document_length(cursor)

                    # Calculate BM25 score
                    tf_component = (term_frequency * (self._k1 + 1)) / (
                        term_frequency + self._k1 * (1 - self._b + self._b * (doc_length / avg_doc_length))
                    )

                    bm25_score = idf_score * tf_component

                    # Cache the score
                    cursor.execute("""
                        INSERT OR REPLACE INTO bm25_scores
                        (term, document_id, tf_score, idf_score, bm25_score)
                        VALUES (?, ?, ?, ?, ?)
                    """, (term.lower().strip(), document_id, tf_component, idf_score, bm25_score))

                    conn.commit()
                    return bm25_score

                except Exception as e:
                    self._logger.error(f"Failed to calculate BM25 score: {e}")
                    return 0.0
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return 0.0

    def _get_average_document_length(self, cursor: sqlite3.Cursor) -> float:
        """Get average document length from collection statistics."""
        cursor.execute("SELECT avg_document_length FROM collection_statistics ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 1.0

    def update_document_statistics(self, document_id: str, document_length: int,
                                 unique_terms: int, term_frequencies: Dict[str, int]) -> bool:
        """
        Update statistics for a document.

        Args:
            document_id: Document identifier
            document_length: Total number of terms in document
            unique_terms: Number of unique terms in document
            term_frequencies: Dictionary mapping terms to their frequencies

        Returns:
            True if successful, False otherwise
        """
        if not document_id or document_length <= 0:
            return False

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Calculate statistics
                    avg_tf = sum(term_frequencies.values()) / len(term_frequencies) if term_frequencies else 0.0
                    max_tf = max(term_frequencies.values()) if term_frequencies else 0

                    # Insert or update document statistics
                    cursor.execute("""
                        INSERT OR REPLACE INTO document_statistics
                        (document_id, document_length, unique_terms, avg_term_frequency, max_term_frequency)
                        VALUES (?, ?, ?, ?, ?)
                    """, (document_id, document_length, unique_terms, avg_tf, max_tf))

                    # Update collection statistics
                    self._update_collection_statistics(cursor)

                    conn.commit()
                    self._collection_stats = None  # Invalidate cache

                    self._logger.debug(f"Updated statistics for document {document_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update document statistics: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return False

    def _update_collection_statistics(self, cursor: sqlite3.Cursor) -> None:
        """Update collection-wide statistics."""
        # Count total documents
        cursor.execute("SELECT COUNT(*) FROM document_statistics")
        total_docs = cursor.fetchone()[0]

        # Count unique terms
        cursor.execute("SELECT COUNT(*) FROM document_frequency")
        unique_terms = cursor.fetchone()[0]

        # Calculate average document length
        cursor.execute("SELECT AVG(document_length) FROM document_statistics")
        avg_doc_length = cursor.fetchone()[0] or 0.0

        # Calculate total terms and collection frequency
        cursor.execute("SELECT SUM(document_length) FROM document_statistics")
        total_terms = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(collection_frequency) FROM document_frequency")
        total_cf = cursor.fetchone()[0] or 0

        # Update collection statistics
        cursor.execute("""
            UPDATE collection_statistics SET
                total_documents = ?,
                total_terms = ?,
                unique_terms = ?,
                avg_document_length = ?,
                total_collection_frequency = ?,
                last_updated = CURRENT_TIMESTAMP
        """, (total_docs, total_terms, unique_terms, avg_doc_length, total_cf))

    def get_term_statistics(self, terms: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get frequency statistics for specified terms.

        Args:
            terms: List of terms to get statistics for

        Returns:
            Dictionary mapping terms to their statistics
        """
        if not terms:
            return {}

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    placeholders = ','.join(['?' for _ in terms])
                    normalized_terms = [term.lower().strip() for term in terms]

                    cursor.execute(f"""
                        SELECT term, document_frequency, collection_frequency, idf_score
                        FROM document_frequency
                        WHERE term IN ({placeholders})
                    """, normalized_terms)

                    results = {}
                    for row in cursor.fetchall():
                        term, doc_freq, coll_freq, idf = row
                        results[term] = {
                            'document_frequency': doc_freq,
                            'collection_frequency': coll_freq,
                            'idf_score': idf
                        }

                    return results

                except Exception as e:
                    self._logger.error(f"Failed to get term statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return {}

    def get_collection_statistics(self) -> Dict[str, Any]:
        """
        Get collection-wide statistics.

        Returns:
            Dictionary containing collection statistics
        """
        current_time = datetime.now().timestamp()

        # Return cached stats if still valid
        if (self._collection_stats and
            current_time - self._last_stats_update < self._stats_cache_ttl):
            return self._collection_stats

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT total_documents, total_terms, unique_terms,
                               avg_document_length, total_collection_frequency
                        FROM collection_statistics
                        ORDER BY id DESC LIMIT 1
                    """)

                    result = cursor.fetchone()
                    if result:
                        stats = {
                            'total_documents': result[0],
                            'total_terms': result[1],
                            'unique_terms': result[2],
                            'average_document_length': result[3],
                            'total_collection_frequency': result[4]
                        }

                        # Cache the results
                        self._collection_stats = stats
                        self._last_stats_update = current_time

                        return stats
                    else:
                        return {}

                except Exception as e:
                    self._logger.error(f"Failed to get collection statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return {}

    def remove_document(self, document_id: str) -> bool:
        """
        Remove document statistics and update collection stats.

        Args:
            document_id: Document identifier to remove

        Returns:
            True if successful, False otherwise
        """
        if not document_id:
            return False

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Remove document statistics
                    cursor.execute("DELETE FROM document_statistics WHERE document_id = ?", (document_id,))

                    # Remove BM25 scores for this document
                    cursor.execute("DELETE FROM bm25_scores WHERE document_id = ?", (document_id,))

                    # Update collection statistics
                    self._update_collection_statistics(cursor)

                    conn.commit()
                    self._collection_stats = None  # Invalidate cache

                    self._logger.debug(f"Removed document {document_id} from frequency database")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to remove document: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return False

    def get_bm25_parameters(self) -> Dict[str, float]:
        """
        Get current BM25 parameters.

        Returns:
            Dictionary containing BM25 parameters
        """
        return {
            'k1': self._k1,
            'b': self._b
        }

    def set_bm25_parameters(self, k1: float, b: float) -> bool:
        """
        Set BM25 parameters.

        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter

        Returns:
            True if parameters are valid and set
        """
        if k1 <= 0 or not (0 <= b <= 1):
            self._logger.error("Invalid BM25 parameters")
            return False

        with self._lock:
            self._k1 = k1
            self._b = b

            # Clear BM25 scores cache as parameters changed
            try:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM bm25_scores")
                    conn.commit()
                    self._logger.info(f"BM25 parameters updated: k1={k1}, b={b}")
                    return True
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to clear BM25 cache: {e}")
                    return False
                finally:
                    conn.close()
            except Exception as e:
                self._logger.error(f"Database connection error: {e}")
                return False

    def clear_cache(self) -> None:
        """Clear all in-memory caches."""
        with self._lock:
            self._stats_cache.clear()
            self._collection_stats = None
            self._last_stats_update = 0
            self._logger.debug("Document frequency caches cleared")

    def optimize_database(self) -> bool:
        """
        Optimize the database for better performance.

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Analyze tables for query optimization
                    cursor.execute("ANALYZE")

                    # Vacuum to reclaim space
                    cursor.execute("VACUUM")

                    # Reindex for performance
                    cursor.execute("REINDEX")

                    # Update all IDF scores
                    self._recalculate_idf_scores(cursor)

                    conn.commit()
                    self._logger.info("Document frequency database optimization completed")
                    return True

                except Exception as e:
                    self._logger.error(f"Failed to optimize database: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return False

    def _recalculate_idf_scores(self, cursor: sqlite3.Cursor) -> None:
        """Recalculate all IDF scores based on current collection statistics."""
        total_docs = self._get_total_documents(cursor)

        if total_docs == 0:
            return

        cursor.execute("SELECT term, document_frequency FROM document_frequency")
        terms = cursor.fetchall()

        for term, doc_freq in terms:
            idf_score = self._calculate_idf(doc_freq, total_docs)
            cursor.execute("""
                UPDATE document_frequency SET idf_score = ? WHERE term = ?
            """, (idf_score, term))

    def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get database-level statistics.

        Returns:
            Dictionary containing database statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get table sizes
                    cursor.execute("SELECT COUNT(*) FROM document_frequency")
                    df_count = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM document_statistics")
                    doc_count = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM bm25_scores")
                    bm25_count = cursor.fetchone()[0]

                    # Get database size
                    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                    db_size = cursor.fetchone()[0]

                    return {
                        'document_frequency_entries': df_count,
                        'document_statistics_entries': doc_count,
                        'bm25_scores_cached': bm25_count,
                        'database_size_bytes': db_size,
                        'stats_cache_size': len(self._stats_cache),
                        'bm25_parameters': self.get_bm25_parameters()
                    }

                except Exception as e:
                    self._logger.error(f"Failed to get database statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return {}

    def close(self) -> None:
        """Close the database connection and cleanup resources."""
        with self._lock:
            self.clear_cache()
            self._logger.info("DocumentFrequencyDB closed")
