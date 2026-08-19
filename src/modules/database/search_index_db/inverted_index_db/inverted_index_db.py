"""
Module: inverted_index_db
Description: Manages inverted index for keyword search functionality with SQLite backend
Phase: 4
Location: /src/modules/database/search_index_db/inverted_index_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class InvertedIndexDB:
    """
    Repository pattern for managing inverted index persistence.
    
    Provides keyword search functionality through inverted index storage with SQLite backend.
    Manages term-to-document mappings, term frequencies, and position information for
    efficient text search operations. Designed for offline operation with optimized
    indexing and query performance.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the inverted index database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self._db_path = db_path or Path("data/search_index/inverted_index.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Threading and synchronization
        self._lock = threading.RLock()
        
        # Logging
        self._logger = get_logger("inverted_index_db")
        
        # In-memory cache for frequently accessed terms
        self._term_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_size_limit = 10000
        
        # Initialize database
        self._initialize_database()
        
        self._logger.info(f"InvertedIndexDB initialized with database: {self._db_path}")
    
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
                
                # Create inverted index table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS inverted_index (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        term TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        term_frequency INTEGER NOT NULL DEFAULT 1,
                        positions TEXT,  -- JSON array of term positions
                        field_name TEXT,  -- Field where term appears (title, content, etc.)
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(term, document_id, field_name)
                    )
                """)
                
                # Create term statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS term_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        term TEXT UNIQUE NOT NULL,
                        document_frequency INTEGER NOT NULL DEFAULT 0,
                        total_frequency INTEGER NOT NULL DEFAULT 0,
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_inverted_term ON inverted_index(term)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_inverted_document ON inverted_index(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_inverted_field ON inverted_index(field_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_inverted_term_doc ON inverted_index(term, document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_term_stats_term ON term_statistics(term)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_term_stats_df ON term_statistics(document_frequency)")
                
                # Create triggers for automatic timestamp updates
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_inverted_index_timestamp
                    AFTER UPDATE ON inverted_index
                    BEGIN
                        UPDATE inverted_index SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_term_stats_timestamp
                    AFTER UPDATE ON term_statistics
                    BEGIN
                        UPDATE term_statistics SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()
                self._logger.info("Inverted index database schema initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize database schema: {e}")
                raise
            finally:
                conn.close()
    
    def add_document_terms(self, document_id: str, terms: Dict[str, Dict[str, Any]]) -> bool:
        """
        Add terms from a document to the inverted index.
        
        Args:
            document_id: Unique identifier for the document
            terms: Dictionary mapping terms to their metadata
                  Format: {term: {frequency: int, positions: List[int], field: str}}
        
        Returns:
            True if successful, False otherwise
        """
        if not document_id or not terms:
            return False
        
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()
                    
                    for term, metadata in terms.items():
                        if not term.strip():
                            continue
                        
                        term = term.lower().strip()
                        frequency = metadata.get('frequency', 1)
                        positions = metadata.get('positions', [])
                        field_name = metadata.get('field', 'content')
                        
                        # Insert or update inverted index entry
                        cursor.execute("""
                            INSERT OR REPLACE INTO inverted_index 
                            (term, document_id, term_frequency, positions, field_name)
                            VALUES (?, ?, ?, ?, ?)
                        """, (term, document_id, frequency, json.dumps(positions), field_name))
                        
                        # Update term statistics
                        self._update_term_statistics(cursor, term, document_id)
                    
                    conn.commit()
                    
                    # Clear cache for updated terms
                    for term in terms.keys():
                        self._term_cache.pop(term.lower().strip(), None)
                    
                    self._logger.debug(f"Added {len(terms)} terms for document {document_id}")
                    return True
                    
                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to add document terms: {e}")
                    return False
                finally:
                    conn.close()
                    
        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return False
    
    def _update_term_statistics(self, cursor: sqlite3.Cursor, term: str, document_id: str) -> None:
        """Update term statistics for document frequency tracking."""
        # Check if this is a new document for this term
        cursor.execute("""
            SELECT COUNT(*) FROM inverted_index 
            WHERE term = ? AND document_id = ?
        """, (term, document_id))
        
        existing_count = cursor.fetchone()[0]
        
        # Get current term statistics
        cursor.execute("SELECT document_frequency, total_frequency FROM term_statistics WHERE term = ?", (term,))
        result = cursor.fetchone()
        
        if result:
            doc_freq, total_freq = result
            if existing_count == 1:  # New document for this term
                doc_freq += 1
            total_freq += 1
            
            cursor.execute("""
                UPDATE term_statistics 
                SET document_frequency = ?, total_frequency = ?
                WHERE term = ?
            """, (doc_freq, total_freq, term))
        else:
            # New term
            cursor.execute("""
                INSERT INTO term_statistics (term, document_frequency, total_frequency)
                VALUES (?, 1, 1)
            """, (term,))

    def search_terms(self, terms: List[str], limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for documents containing the specified terms.

        Args:
            terms: List of terms to search for
            limit: Maximum number of results per term

        Returns:
            Dictionary mapping terms to lists of document matches
        """
        if not terms:
            return {}

        results = {}

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    for term in terms:
                        term = term.lower().strip()
                        if not term:
                            continue

                        # Check cache first
                        if term in self._term_cache:
                            results[term] = self._term_cache[term]
                            continue

                        cursor.execute("""
                            SELECT document_id, term_frequency, positions, field_name
                            FROM inverted_index
                            WHERE term = ?
                            ORDER BY term_frequency DESC
                            LIMIT ?
                        """, (term, limit))

                        term_results = []
                        for row in cursor.fetchall():
                            doc_id, freq, positions_json, field = row
                            positions = json.loads(positions_json) if positions_json else []

                            term_results.append({
                                'document_id': doc_id,
                                'term_frequency': freq,
                                'positions': positions,
                                'field_name': field
                            })

                        results[term] = term_results

                        # Cache results if within limit
                        if len(self._term_cache) < self._cache_size_limit:
                            self._term_cache[term] = term_results

                    return results

                except Exception as e:
                    self._logger.error(f"Failed to search terms: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return {}

    def get_term_statistics(self, terms: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Get statistics for specified terms.

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
                        SELECT term, document_frequency, total_frequency
                        FROM term_statistics
                        WHERE term IN ({placeholders})
                    """, normalized_terms)

                    results = {}
                    for row in cursor.fetchall():
                        term, doc_freq, total_freq = row
                        results[term] = {
                            'document_frequency': doc_freq,
                            'total_frequency': total_freq
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

    def remove_document(self, document_id: str) -> bool:
        """
        Remove all terms for a document from the inverted index.

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

                    # Get terms for this document before deletion
                    cursor.execute("SELECT DISTINCT term FROM inverted_index WHERE document_id = ?", (document_id,))
                    terms_to_update = [row[0] for row in cursor.fetchall()]

                    # Remove document entries
                    cursor.execute("DELETE FROM inverted_index WHERE document_id = ?", (document_id,))

                    # Update term statistics
                    for term in terms_to_update:
                        cursor.execute("""
                            SELECT COUNT(DISTINCT document_id), COUNT(*)
                            FROM inverted_index WHERE term = ?
                        """, (term,))

                        result = cursor.fetchone()
                        if result:
                            doc_freq, total_freq = result
                            if doc_freq > 0:
                                cursor.execute("""
                                    UPDATE term_statistics
                                    SET document_frequency = ?, total_frequency = ?
                                    WHERE term = ?
                                """, (doc_freq, total_freq, term))
                            else:
                                # Remove term if no documents contain it
                                cursor.execute("DELETE FROM term_statistics WHERE term = ?", (term,))

                        # Clear from cache
                        self._term_cache.pop(term, None)

                    conn.commit()
                    self._logger.debug(f"Removed document {document_id} from inverted index")
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

    def get_document_terms(self, document_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all terms for a specific document.

        Args:
            document_id: Document identifier

        Returns:
            Dictionary mapping terms to their metadata
        """
        if not document_id:
            return {}

        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT term, term_frequency, positions, field_name
                        FROM inverted_index
                        WHERE document_id = ?
                        ORDER BY term_frequency DESC
                    """, (document_id,))

                    results = {}
                    for row in cursor.fetchall():
                        term, freq, positions_json, field = row
                        positions = json.loads(positions_json) if positions_json else []

                        results[term] = {
                            'term_frequency': freq,
                            'positions': positions,
                            'field_name': field
                        }

                    return results

                except Exception as e:
                    self._logger.error(f"Failed to get document terms: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return {}

    def get_index_statistics(self) -> Dict[str, Any]:
        """
        Get overall index statistics.

        Returns:
            Dictionary containing index statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Get total terms
                    cursor.execute("SELECT COUNT(*) FROM term_statistics")
                    total_terms = cursor.fetchone()[0]

                    # Get total documents
                    cursor.execute("SELECT COUNT(DISTINCT document_id) FROM inverted_index")
                    total_documents = cursor.fetchone()[0]

                    # Get total index entries
                    cursor.execute("SELECT COUNT(*) FROM inverted_index")
                    total_entries = cursor.fetchone()[0]

                    # Get average document frequency
                    cursor.execute("SELECT AVG(document_frequency) FROM term_statistics")
                    avg_doc_freq = cursor.fetchone()[0] or 0

                    # Get database size
                    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                    db_size = cursor.fetchone()[0]

                    return {
                        'total_terms': total_terms,
                        'total_documents': total_documents,
                        'total_entries': total_entries,
                        'average_document_frequency': round(avg_doc_freq, 2),
                        'database_size_bytes': db_size,
                        'cache_size': len(self._term_cache)
                    }

                except Exception as e:
                    self._logger.error(f"Failed to get index statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return {}

    def clear_cache(self) -> None:
        """Clear the in-memory term cache."""
        with self._lock:
            self._term_cache.clear()
            self._logger.debug("Inverted index cache cleared")

    def optimize_index(self) -> bool:
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

                    conn.commit()
                    self._logger.info("Inverted index optimization completed")
                    return True

                except Exception as e:
                    self._logger.error(f"Failed to optimize index: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error: {e}")
            return False

    def close(self) -> None:
        """Close the database connection and cleanup resources."""
        with self._lock:
            self.clear_cache()
            self._logger.info("InvertedIndexDB closed")
