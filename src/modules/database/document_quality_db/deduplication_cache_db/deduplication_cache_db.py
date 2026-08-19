"""
Module: deduplication_cache_db
Description: Manages deduplication cache with hash-based and semantic similarity storage for efficient duplicate detection
Phase: 3
Location: /src/modules/database/document_quality_db/deduplication_cache_db/
"""

# Standard library imports
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
from src.modules.logic.document_quality_lg.base_interfaces import (
    DuplicateType, SimilarityMethod, DeduplicationResult
)


class CacheStatus(Enum):
    """Cache entry status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    PENDING = "pending"


class DeduplicationCacheDB:
    """
    Deduplication cache database manager.
    
    Manages deduplication cache with hash-based and semantic similarity storage
    for efficient duplicate detection and content similarity analysis.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the deduplication cache database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to document quality data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "document_quality"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "deduplication_cache.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Cache settings
        self._cache_retention_days = 90  # Keep cache entries for 90 days
        self._max_cache_entries = 1000000  # Maximum cache entries
        self._similarity_threshold = 0.95  # Default similarity threshold
        self._batch_size = 1000
        
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Content hashes table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS content_hashes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hash_id TEXT UNIQUE NOT NULL,
                        document_id TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        hash_algorithm TEXT NOT NULL,
                        content_length INTEGER,
                        content_type TEXT,
                        chunk_index INTEGER,
                        chunk_size INTEGER,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        metadata TEXT
                    )
                """)
                
                # Similarity cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS similarity_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cache_id TEXT UNIQUE NOT NULL,
                        document_id_1 TEXT NOT NULL,
                        document_id_2 TEXT NOT NULL,
                        similarity_method TEXT NOT NULL,
                        similarity_score REAL NOT NULL,
                        is_duplicate BOOLEAN DEFAULT FALSE,
                        duplicate_type TEXT,
                        confidence_level TEXT,
                        processing_time_ms REAL,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        metadata TEXT
                    )
                """)
                
                # Duplicate groups table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS duplicate_groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id TEXT UNIQUE NOT NULL,
                        group_name TEXT,
                        representative_document_id TEXT,
                        duplicate_type TEXT NOT NULL,
                        similarity_threshold REAL,
                        document_count INTEGER DEFAULT 0,
                        total_size_bytes INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT
                    )
                """)
                
                # Duplicate group members table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS duplicate_group_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        member_id TEXT UNIQUE NOT NULL,
                        group_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        similarity_score REAL,
                        is_representative BOOLEAN DEFAULT FALSE,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (group_id) REFERENCES duplicate_groups (group_id)
                    )
                """)
                
                # Deduplication results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS deduplication_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        result_id TEXT UNIQUE NOT NULL,
                        document_id TEXT NOT NULL,
                        is_duplicate BOOLEAN NOT NULL,
                        duplicate_type TEXT,
                        similarity_score REAL,
                        duplicate_sources TEXT,
                        similarity_details TEXT,
                        hash_values TEXT,
                        processing_time_ms REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_hashes_document_id ON content_hashes (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_hashes_hash ON content_hashes (content_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_hashes_algorithm ON content_hashes (hash_algorithm)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_hashes_status ON content_hashes (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_docs ON similarity_cache (document_id_1, document_id_2)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_method ON similarity_cache (similarity_method)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_similarity_cache_score ON similarity_cache (similarity_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_groups_type ON duplicate_groups (duplicate_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_members_group ON duplicate_group_members (group_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_members_document ON duplicate_group_members (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dedup_results_document ON deduplication_results (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dedup_results_duplicate ON deduplication_results (is_duplicate)")
                
                conn.commit()
                self._logger.info("Deduplication cache database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize deduplication cache database: {e}")
                raise
            finally:
                conn.close()

    def store_content_hash(self, document_id: str, content: str,
                          hash_algorithm: str = "sha256",
                          content_type: Optional[str] = None,
                          chunk_index: Optional[int] = None,
                          chunk_size: Optional[int] = None,
                          expires_at: Optional[datetime] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store content hash for duplicate detection.

        Args:
            document_id: Document identifier
            content: Content to hash
            hash_algorithm: Hash algorithm to use
            content_type: Type of content
            chunk_index: Chunk index if applicable
            chunk_size: Size of chunk
            expires_at: Expiration timestamp
            metadata: Additional metadata

        Returns:
            Hash ID for the stored hash
        """
        hash_id = str(uuid.uuid4())

        # Generate content hash
        if hash_algorithm == "sha256":
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        elif hash_algorithm == "md5":
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        elif hash_algorithm == "sha1":
            content_hash = hashlib.sha1(content.encode('utf-8')).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {hash_algorithm}")

        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=self._cache_retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO content_hashes (
                        hash_id, document_id, content_hash, hash_algorithm,
                        content_length, content_type, chunk_index, chunk_size,
                        expires_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    hash_id, document_id, content_hash, hash_algorithm,
                    len(content), content_type, chunk_index, chunk_size,
                    expires_at.isoformat(),
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.debug(f"Stored content hash {hash_id} for document {document_id}")
                return hash_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store content hash for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def find_duplicate_by_hash(self, content: str, hash_algorithm: str = "sha256",
                              exclude_document_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Find duplicates by content hash.

        Args:
            content: Content to check for duplicates
            hash_algorithm: Hash algorithm to use
            exclude_document_id: Document ID to exclude from results

        Returns:
            List of duplicate documents or None if no duplicates found
        """
        # Generate content hash
        if hash_algorithm == "sha256":
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        elif hash_algorithm == "md5":
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        elif hash_algorithm == "sha1":
            content_hash = hashlib.sha1(content.encode('utf-8')).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {hash_algorithm}")

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT hash_id, document_id, content_length, content_type,
                           chunk_index, chunk_size, created_at, metadata
                    FROM content_hashes
                    WHERE content_hash = ? AND hash_algorithm = ? AND status = 'active'
                """
                params = [content_hash, hash_algorithm]

                if exclude_document_id:
                    query += " AND document_id != ?"
                    params.append(exclude_document_id)

                cursor.execute(query, params)

                duplicates = []
                for row in cursor.fetchall():
                    duplicates.append({
                        'hash_id': row[0],
                        'document_id': row[1],
                        'content_length': row[2],
                        'content_type': row[3],
                        'chunk_index': row[4],
                        'chunk_size': row[5],
                        'created_at': row[6],
                        'metadata': json.loads(row[7]) if row[7] else {}
                    })

                return duplicates if duplicates else None

            except Exception as e:
                self._logger.error(f"Failed to find duplicates by hash: {e}")
                raise
            finally:
                conn.close()

    def store_similarity_result(self, document_id_1: str, document_id_2: str,
                              similarity_method: SimilarityMethod, similarity_score: float,
                              is_duplicate: bool = False, duplicate_type: Optional[DuplicateType] = None,
                              processing_time_ms: Optional[float] = None,
                              expires_at: Optional[datetime] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store similarity calculation result.

        Args:
            document_id_1: First document ID
            document_id_2: Second document ID
            similarity_method: Similarity calculation method
            similarity_score: Similarity score (0.0-1.0)
            is_duplicate: Whether documents are duplicates
            duplicate_type: Type of duplicate if applicable
            processing_time_ms: Processing time in milliseconds
            expires_at: Expiration timestamp
            metadata: Additional metadata

        Returns:
            Cache ID for the stored result
        """
        cache_id = str(uuid.uuid4())

        # Determine confidence level
        if similarity_score >= 0.95:
            confidence_level = "very_high"
        elif similarity_score >= 0.85:
            confidence_level = "high"
        elif similarity_score >= 0.75:
            confidence_level = "medium"
        elif similarity_score >= 0.65:
            confidence_level = "low"
        else:
            confidence_level = "very_low"

        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=self._cache_retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO similarity_cache (
                        cache_id, document_id_1, document_id_2, similarity_method,
                        similarity_score, is_duplicate, duplicate_type, confidence_level,
                        processing_time_ms, expires_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_id, document_id_1, document_id_2, similarity_method.value,
                    similarity_score, is_duplicate,
                    duplicate_type.value if duplicate_type else None,
                    confidence_level, processing_time_ms, expires_at.isoformat(),
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                return cache_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store similarity result: {e}")
                raise
            finally:
                conn.close()

    def get_cached_similarity(self, document_id_1: str, document_id_2: str,
                            similarity_method: SimilarityMethod) -> Optional[Dict[str, Any]]:
        """
        Get cached similarity result.

        Args:
            document_id_1: First document ID
            document_id_2: Second document ID
            similarity_method: Similarity calculation method

        Returns:
            Cached similarity result or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cache_id, similarity_score, is_duplicate, duplicate_type,
                           confidence_level, processing_time_ms, created_at, metadata
                    FROM similarity_cache
                    WHERE ((document_id_1 = ? AND document_id_2 = ?) OR
                           (document_id_1 = ? AND document_id_2 = ?))
                      AND similarity_method = ? AND status = 'active'
                      AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (document_id_1, document_id_2, document_id_2, document_id_1, similarity_method.value))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'cache_id': row[0],
                    'similarity_score': row[1],
                    'is_duplicate': bool(row[2]),
                    'duplicate_type': row[3],
                    'confidence_level': row[4],
                    'processing_time_ms': row[5],
                    'created_at': row[6],
                    'metadata': json.loads(row[7]) if row[7] else {}
                }

            except Exception as e:
                self._logger.error(f"Failed to get cached similarity: {e}")
                raise
            finally:
                conn.close()

    def store_deduplication_result(self, document_id: str, result: DeduplicationResult) -> str:
        """
        Store deduplication result.

        Args:
            document_id: Document identifier
            result: Deduplication result object

        Returns:
            Result ID for the stored result
        """
        result_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO deduplication_results (
                        result_id, document_id, is_duplicate, duplicate_type,
                        similarity_score, duplicate_sources, similarity_details,
                        hash_values, processing_time_ms, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result_id, document_id, result.is_duplicate,
                    result.duplicate_type.value if result.duplicate_type else None,
                    result.similarity_score,
                    json.dumps(result.duplicate_sources),
                    json.dumps({method.value: score for method, score in result.similarity_details.items()}),
                    json.dumps(result.hash_values),
                    result.processing_time_ms,
                    json.dumps(result.metadata)
                ))

                conn.commit()
                return result_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store deduplication result for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def create_duplicate_group(self, representative_document_id: str,
                             duplicate_type: DuplicateType,
                             similarity_threshold: float,
                             group_name: Optional[str] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new duplicate group.

        Args:
            representative_document_id: Representative document for the group
            duplicate_type: Type of duplicates in the group
            similarity_threshold: Similarity threshold for the group
            group_name: Optional group name
            metadata: Additional metadata

        Returns:
            Group ID for the created group
        """
        group_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO duplicate_groups (
                        group_id, group_name, representative_document_id,
                        duplicate_type, similarity_threshold, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    group_id, group_name, representative_document_id,
                    duplicate_type.value, similarity_threshold,
                    json.dumps(metadata) if metadata else None
                ))

                # Add representative document as first member
                self._add_group_member(cursor, group_id, representative_document_id,
                                     1.0, is_representative=True)

                conn.commit()
                self._logger.info(f"Created duplicate group {group_id}")
                return group_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create duplicate group: {e}")
                raise
            finally:
                conn.close()

    def _add_group_member(self, cursor, group_id: str, document_id: str,
                         similarity_score: float, is_representative: bool = False) -> str:
        """Add a member to a duplicate group."""
        member_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO duplicate_group_members (
                member_id, group_id, document_id, similarity_score, is_representative
            ) VALUES (?, ?, ?, ?, ?)
        """, (member_id, group_id, document_id, similarity_score, is_representative))
        return member_id

    def add_to_duplicate_group(self, group_id: str, document_id: str,
                             similarity_score: float) -> str:
        """
        Add document to existing duplicate group.

        Args:
            group_id: Group identifier
            document_id: Document to add
            similarity_score: Similarity score to representative

        Returns:
            Member ID for the added document
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if group exists
                cursor.execute("SELECT group_id FROM duplicate_groups WHERE group_id = ?", (group_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Duplicate group {group_id} not found")

                member_id = self._add_group_member(cursor, group_id, document_id, similarity_score)

                # Update group statistics
                cursor.execute("""
                    UPDATE duplicate_groups
                    SET document_count = document_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE group_id = ?
                """, (group_id,))

                conn.commit()
                return member_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add document to duplicate group: {e}")
                raise
            finally:
                conn.close()

    def get_duplicate_groups(self, duplicate_type: Optional[DuplicateType] = None,
                           min_similarity: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get duplicate groups with optional filtering.

        Args:
            duplicate_type: Filter by duplicate type
            min_similarity: Minimum similarity threshold

        Returns:
            List of duplicate groups
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                query = """
                    SELECT group_id, group_name, representative_document_id,
                           duplicate_type, similarity_threshold, document_count,
                           total_size_bytes, created_at, updated_at, metadata
                    FROM duplicate_groups
                    WHERE 1=1
                """
                params = []

                if duplicate_type:
                    query += " AND duplicate_type = ?"
                    params.append(duplicate_type.value)

                if min_similarity:
                    query += " AND similarity_threshold >= ?"
                    params.append(min_similarity)

                query += " ORDER BY document_count DESC, created_at DESC"

                cursor.execute(query, params)

                groups = []
                for row in cursor.fetchall():
                    group = {
                        'group_id': row[0],
                        'group_name': row[1],
                        'representative_document_id': row[2],
                        'duplicate_type': row[3],
                        'similarity_threshold': row[4],
                        'document_count': row[5],
                        'total_size_bytes': row[6],
                        'created_at': row[7],
                        'updated_at': row[8],
                        'metadata': json.loads(row[9]) if row[9] else {}
                    }

                    # Get group members
                    group['members'] = self._get_group_members(cursor, row[0])
                    groups.append(group)

                return groups

            except Exception as e:
                self._logger.error(f"Failed to get duplicate groups: {e}")
                raise
            finally:
                conn.close()

    def _get_group_members(self, cursor, group_id: str) -> List[Dict[str, Any]]:
        """Get members of a duplicate group."""
        cursor.execute("""
            SELECT member_id, document_id, similarity_score, is_representative, added_at
            FROM duplicate_group_members
            WHERE group_id = ?
            ORDER BY similarity_score DESC, added_at ASC
        """, (group_id,))

        members = []
        for row in cursor.fetchall():
            members.append({
                'member_id': row[0],
                'document_id': row[1],
                'similarity_score': row[2],
                'is_representative': bool(row[3]),
                'added_at': row[4]
            })

        return members

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get deduplication cache statistics.

        Returns:
            Cache statistics dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Hash statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_hashes,
                           COUNT(DISTINCT document_id) as unique_documents,
                           COUNT(CASE WHEN status = 'active' THEN 1 END) as active_hashes,
                           AVG(content_length) as avg_content_length
                    FROM content_hashes
                """)
                hash_stats = cursor.fetchone()

                # Similarity cache statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_similarities,
                           COUNT(CASE WHEN is_duplicate = 1 THEN 1 END) as duplicate_pairs,
                           AVG(similarity_score) as avg_similarity,
                           COUNT(CASE WHEN status = 'active' THEN 1 END) as active_similarities
                    FROM similarity_cache
                """)
                similarity_stats = cursor.fetchone()

                # Duplicate group statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_groups,
                           SUM(document_count) as total_duplicates,
                           AVG(document_count) as avg_group_size,
                           MAX(document_count) as max_group_size
                    FROM duplicate_groups
                """)
                group_stats = cursor.fetchone()

                return {
                    'hash_cache': {
                        'total_hashes': hash_stats[0],
                        'unique_documents': hash_stats[1],
                        'active_hashes': hash_stats[2],
                        'avg_content_length': hash_stats[3] or 0.0
                    },
                    'similarity_cache': {
                        'total_similarities': similarity_stats[0],
                        'duplicate_pairs': similarity_stats[1],
                        'avg_similarity': similarity_stats[2] or 0.0,
                        'active_similarities': similarity_stats[3]
                    },
                    'duplicate_groups': {
                        'total_groups': group_stats[0],
                        'total_duplicates': group_stats[1] or 0,
                        'avg_group_size': group_stats[2] or 0.0,
                        'max_group_size': group_stats[3] or 0
                    }
                }

            except Exception as e:
                self._logger.error(f"Failed to get cache statistics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries.

        Returns:
            Number of entries cleaned up
        """
        current_time = datetime.now(timezone.utc)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Clean up expired hashes
                cursor.execute("""
                    DELETE FROM content_hashes
                    WHERE expires_at < ? OR status = 'expired'
                """, (current_time.isoformat(),))
                hash_cleanup_count = cursor.rowcount

                # Clean up expired similarity cache
                cursor.execute("""
                    DELETE FROM similarity_cache
                    WHERE expires_at < ? OR status = 'expired'
                """, (current_time.isoformat(),))
                similarity_cleanup_count = cursor.rowcount

                # Clean up old deduplication results
                cutoff_date = current_time - timedelta(days=self._cache_retention_days)
                cursor.execute("""
                    DELETE FROM deduplication_results
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                result_cleanup_count = cursor.rowcount

                total_cleaned = hash_cleanup_count + similarity_cleanup_count + result_cleanup_count

                conn.commit()
                self._logger.info(f"Cleaned up {total_cleaned} expired cache entries")
                return total_cleaned

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup expired cache: {e}")
                raise
            finally:
                conn.close()

    def invalidate_document_cache(self, document_id: str) -> int:
        """
        Invalidate all cache entries for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Invalidate content hashes
                cursor.execute("""
                    UPDATE content_hashes
                    SET status = 'invalidated', updated_at = CURRENT_TIMESTAMP
                    WHERE document_id = ? AND status = 'active'
                """, (document_id,))
                hash_count = cursor.rowcount

                # Invalidate similarity cache
                cursor.execute("""
                    UPDATE similarity_cache
                    SET status = 'invalidated'
                    WHERE (document_id_1 = ? OR document_id_2 = ?) AND status = 'active'
                """, (document_id, document_id))
                similarity_count = cursor.rowcount

                total_invalidated = hash_count + similarity_count

                conn.commit()
                self._logger.info(f"Invalidated {total_invalidated} cache entries for document {document_id}")
                return total_invalidated

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to invalidate cache for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close the database connection and cleanup resources."""
        with self._lock:
            self._logger.info("Deduplication cache database closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
