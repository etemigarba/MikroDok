"""
Module: retrieval_history_db
Description: Tracks RAG retrieval operations, query history, performance metrics, and retrieval patterns
Phase: 4
Location: /src/modules/database/rag_metadata_db/retrieval_history_db/
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


class RetrievalHistoryDB:
    """
    Retrieval history database manager.
    
    Tracks RAG retrieval operations, query history, performance metrics,
    and retrieval patterns for optimization. Provides analytics capabilities
    for improving retrieval performance and understanding usage patterns.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the retrieval history database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to RAG metadata data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "rag_metadata"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "retrieval_history.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._history_retention_days = 90  # Keep history for 3 months
        self._detailed_metrics_retention_days = 30  # Keep detailed metrics for 1 month
        self._aggregated_metrics_retention_days = 365  # Keep aggregated metrics for 1 year
        
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
                
                # Create retrieval sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retrieval_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL UNIQUE,
                        user_id TEXT,
                        session_type TEXT DEFAULT 'rag_query',
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        total_queries INTEGER DEFAULT 0,
                        total_chunks_retrieved INTEGER DEFAULT 0,
                        average_response_time REAL,
                        session_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create query history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_id TEXT NOT NULL UNIQUE,
                        session_id TEXT,
                        query_text TEXT NOT NULL,
                        query_type TEXT DEFAULT 'semantic',
                        query_hash TEXT,
                        embedding_model TEXT,
                        similarity_threshold REAL,
                        max_results INTEGER,
                        filters JSON,
                        query_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES retrieval_sessions (session_id) ON DELETE SET NULL
                    )
                """)
                
                # Create retrieval results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retrieval_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        result_id TEXT NOT NULL UNIQUE,
                        query_id TEXT NOT NULL,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT,
                        similarity_score REAL,
                        rank_position INTEGER,
                        retrieval_method TEXT,
                        chunk_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (query_id) REFERENCES query_history (query_id) ON DELETE CASCADE
                    )
                """)
                
                # Create performance metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_id TEXT NOT NULL UNIQUE,
                        query_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        measurement_unit TEXT,
                        measurement_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metric_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (query_id) REFERENCES query_history (query_id) ON DELETE CASCADE
                    )
                """)
                
                # Create user feedback table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        feedback_id TEXT NOT NULL UNIQUE,
                        query_id TEXT NOT NULL,
                        result_id TEXT,
                        feedback_type TEXT NOT NULL,
                        relevance_score REAL,
                        usefulness_score REAL,
                        feedback_text TEXT,
                        feedback_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (query_id) REFERENCES query_history (query_id) ON DELETE CASCADE,
                        FOREIGN KEY (result_id) REFERENCES retrieval_results (result_id) ON DELETE CASCADE
                    )
                """)
                
                # Create query patterns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_id TEXT NOT NULL UNIQUE,
                        pattern_type TEXT NOT NULL,
                        pattern_description TEXT,
                        query_template TEXT,
                        frequency_count INTEGER DEFAULT 1,
                        average_performance REAL,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        pattern_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON retrieval_sessions (user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_type ON retrieval_sessions (session_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON retrieval_sessions (start_time)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_session_id ON query_history (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_type ON query_history (query_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_hash ON query_history (query_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_created_at ON query_history (created_at)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_query_id ON retrieval_results (query_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_chunk_id ON retrieval_results (chunk_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_document_id ON retrieval_results (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_similarity ON retrieval_results (similarity_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_rank ON retrieval_results (rank_position)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_method ON retrieval_results (retrieval_method)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_query_id ON performance_metrics (query_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_type ON performance_metrics (metric_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON performance_metrics (metric_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics (measurement_timestamp)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_query_id ON user_feedback (query_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_result_id ON user_feedback (result_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_type ON user_feedback (feedback_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_relevance ON user_feedback (relevance_score)")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON query_patterns (pattern_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_frequency ON query_patterns (frequency_count)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_performance ON query_patterns (average_performance)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_last_seen ON query_patterns (last_seen)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_patterns_timestamp 
                    AFTER UPDATE ON query_patterns
                    BEGIN
                        UPDATE query_patterns SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                # Create full-text search index for queries
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS queries_fts USING fts5(
                        query_id UNINDEXED,
                        query_text,
                        content='query_history',
                        content_rowid='id'
                    )
                """)
                
                # Create triggers to maintain FTS index
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS queries_fts_insert AFTER INSERT ON query_history BEGIN
                        INSERT INTO queries_fts(rowid, query_id, query_text) VALUES (new.id, new.query_id, new.query_text);
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS queries_fts_delete AFTER DELETE ON query_history BEGIN
                        INSERT INTO queries_fts(queries_fts, rowid, query_id, query_text) VALUES('delete', old.id, old.query_id, old.query_text);
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS queries_fts_update AFTER UPDATE ON query_history BEGIN
                        INSERT INTO queries_fts(queries_fts, rowid, query_id, query_text) VALUES('delete', old.id, old.query_id, old.query_text);
                        INSERT INTO queries_fts(rowid, query_id, query_text) VALUES (new.id, new.query_id, new.query_text);
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'retrieval_sessions', 'query_history', 'retrieval_results',
                    'performance_metrics', 'user_feedback', 'query_patterns', 'queries_fts'
                ]

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Retrieval history database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize retrieval history database: {e}")
                raise
            finally:
                conn.close()

    def start_session(self, user_id: Optional[str] = None, session_type: str = 'rag_query',
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new retrieval session.

        Args:
            user_id: User identifier
            session_type: Type of session (rag_query, batch_retrieval, etc.)
            metadata: Additional session properties

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO retrieval_sessions (
                        session_id, user_id, session_type, session_metadata
                    ) VALUES (?, ?, ?, ?)
                """, (session_id, user_id, session_type, json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Started retrieval session {session_id}")
                return session_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to start retrieval session: {e}")
                raise
            finally:
                conn.close()

    def end_session(self, session_id: str) -> bool:
        """
        End a retrieval session and calculate statistics.

        Args:
            session_id: Session identifier

        Returns:
            True if session was successfully ended
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate session statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_queries,
                           SUM(CASE WHEN rr.query_id IS NOT NULL THEN 1 ELSE 0 END) as total_chunks,
                           AVG(pm.metric_value) as avg_response_time
                    FROM query_history qh
                    LEFT JOIN retrieval_results rr ON qh.query_id = rr.query_id
                    LEFT JOIN performance_metrics pm ON qh.query_id = pm.query_id
                        AND pm.metric_name = 'response_time'
                    WHERE qh.session_id = ?
                """, (session_id,))

                stats = cursor.fetchone()
                total_queries = stats[0] or 0
                total_chunks = stats[1] or 0
                avg_response_time = stats[2] or 0.0

                # Update session with end time and statistics
                cursor.execute("""
                    UPDATE retrieval_sessions
                    SET end_time = CURRENT_TIMESTAMP,
                        total_queries = ?,
                        total_chunks_retrieved = ?,
                        average_response_time = ?
                    WHERE session_id = ?
                """, (total_queries, total_chunks, avg_response_time, session_id))

                conn.commit()

                if cursor.rowcount > 0:
                    self._logger.info(f"Ended retrieval session {session_id}")
                    return True
                else:
                    self._logger.warning(f"Session {session_id} not found")
                    return False

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to end retrieval session {session_id}: {e}")
                raise
            finally:
                conn.close()

    def log_query(self, query_text: str, session_id: Optional[str] = None,
                  query_type: str = 'semantic', embedding_model: Optional[str] = None,
                  similarity_threshold: Optional[float] = None, max_results: Optional[int] = None,
                  filters: Optional[Dict[str, Any]] = None,
                  metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a retrieval query.

        Args:
            query_text: The query text
            session_id: Session identifier (optional)
            query_type: Type of query (semantic, keyword, hybrid)
            embedding_model: Model used for embeddings
            similarity_threshold: Similarity threshold used
            max_results: Maximum results requested
            filters: Query filters applied
            metadata: Additional query properties

        Returns:
            Query ID
        """
        import hashlib

        query_id = str(uuid.uuid4())
        query_hash = hashlib.sha256(query_text.encode('utf-8')).hexdigest()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO query_history (
                        query_id, session_id, query_text, query_type, query_hash,
                        embedding_model, similarity_threshold, max_results, filters, query_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (query_id, session_id, query_text, query_type, query_hash,
                      embedding_model, similarity_threshold, max_results,
                      json.dumps(filters) if filters else None,
                      json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Logged query {query_id}")
                return query_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log query: {e}")
                raise
            finally:
                conn.close()

    def log_retrieval_results(self, query_id: str, results: List[Dict[str, Any]]) -> List[str]:
        """
        Log retrieval results for a query.

        Args:
            query_id: Query identifier
            results: List of retrieval results with chunk_id, similarity_score, etc.

        Returns:
            List of result IDs
        """
        result_ids = []

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                for rank, result in enumerate(results):
                    result_id = str(uuid.uuid4())
                    result_ids.append(result_id)

                    cursor.execute("""
                        INSERT INTO retrieval_results (
                            result_id, query_id, chunk_id, document_id, similarity_score,
                            rank_position, retrieval_method, chunk_metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        result_id, query_id, result.get('chunk_id'),
                        result.get('document_id'), result.get('similarity_score'),
                        rank + 1, result.get('retrieval_method'),
                        json.dumps(result.get('metadata')) if result.get('metadata') else None
                    ))

                conn.commit()
                self._logger.info(f"Logged {len(results)} retrieval results for query {query_id}")
                return result_ids

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log retrieval results: {e}")
                raise
            finally:
                conn.close()

    def log_performance_metric(self, query_id: str, metric_type: str, metric_name: str,
                              metric_value: float, measurement_unit: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a performance metric for a query.

        Args:
            query_id: Query identifier
            metric_type: Type of metric (timing, accuracy, resource_usage)
            metric_name: Name of the metric (response_time, precision, memory_usage)
            metric_value: Metric value
            measurement_unit: Unit of measurement (ms, seconds, bytes, etc.)
            metadata: Additional metric properties

        Returns:
            Metric ID
        """
        metric_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO performance_metrics (
                        metric_id, query_id, metric_type, metric_name, metric_value,
                        measurement_unit, metric_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (metric_id, query_id, metric_type, metric_name, metric_value,
                      measurement_unit, json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Logged performance metric {metric_name} for query {query_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log performance metric: {e}")
                raise
            finally:
                conn.close()

    def log_user_feedback(self, query_id: str, feedback_type: str,
                         result_id: Optional[str] = None, relevance_score: Optional[float] = None,
                         usefulness_score: Optional[float] = None, feedback_text: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log user feedback for a query or result.

        Args:
            query_id: Query identifier
            feedback_type: Type of feedback (relevance, usefulness, quality)
            result_id: Specific result identifier (optional)
            relevance_score: Relevance score (0.0-1.0)
            usefulness_score: Usefulness score (0.0-1.0)
            feedback_text: Free-form feedback text
            metadata: Additional feedback properties

        Returns:
            Feedback ID
        """
        feedback_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_feedback (
                        feedback_id, query_id, result_id, feedback_type, relevance_score,
                        usefulness_score, feedback_text, feedback_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (feedback_id, query_id, result_id, feedback_type, relevance_score,
                      usefulness_score, feedback_text, json.dumps(metadata) if metadata else None))

                conn.commit()
                self._logger.info(f"Logged user feedback {feedback_id} for query {query_id}")
                return feedback_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log user feedback: {e}")
                raise
            finally:
                conn.close()

    def get_query_history(self, session_id: Optional[str] = None, user_id: Optional[str] = None,
                         query_type: Optional[str] = None, days: int = 30,
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get query history with optional filters.

        Args:
            session_id: Filter by session ID
            user_id: Filter by user ID
            query_type: Filter by query type
            days: Number of days of history to retrieve
            limit: Maximum number of queries to return

        Returns:
            List of query history dictionaries
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with optional filters
                query = """
                    SELECT qh.query_id, qh.session_id, qh.query_text, qh.query_type,
                           qh.query_hash, qh.embedding_model, qh.similarity_threshold,
                           qh.max_results, qh.filters, qh.query_metadata, qh.created_at,
                           rs.user_id
                    FROM query_history qh
                    LEFT JOIN retrieval_sessions rs ON qh.session_id = rs.session_id
                    WHERE qh.created_at >= ?
                """
                params = [cutoff_time.isoformat()]

                if session_id:
                    query += " AND qh.session_id = ?"
                    params.append(session_id)

                if user_id:
                    query += " AND rs.user_id = ?"
                    params.append(user_id)

                if query_type:
                    query += " AND qh.query_type = ?"
                    params.append(query_type)

                query += " ORDER BY qh.created_at DESC"

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                history = []

                for row in rows:
                    history.append({
                        'query_id': row[0],
                        'session_id': row[1],
                        'query_text': row[2],
                        'query_type': row[3],
                        'query_hash': row[4],
                        'embedding_model': row[5],
                        'similarity_threshold': row[6],
                        'max_results': row[7],
                        'filters': json.loads(row[8]) if row[8] else None,
                        'query_metadata': json.loads(row[9]) if row[9] else None,
                        'created_at': row[10],
                        'user_id': row[11]
                    })

                return history

            except Exception as e:
                self._logger.error(f"Failed to get query history: {e}")
                raise
            finally:
                conn.close()

    def get_performance_analytics(self, days: int = 30,
                                 metric_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance analytics for the specified time period.

        Args:
            days: Number of days to analyze
            metric_type: Filter by metric type (optional)

        Returns:
            Dictionary with performance analytics
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build base query with optional filter
                base_where = "WHERE pm.measurement_timestamp >= ?"
                params = [cutoff_time.isoformat()]

                if metric_type:
                    base_where += " AND pm.metric_type = ?"
                    params.append(metric_type)

                # Get average response times
                cursor.execute(f"""
                    SELECT AVG(pm.metric_value) as avg_response_time
                    FROM performance_metrics pm
                    {base_where} AND pm.metric_name = 'response_time'
                """, params + ['response_time'] if metric_type else params)
                avg_response_time = cursor.fetchone()[0] or 0.0

                # Get query volume by day
                cursor.execute(f"""
                    SELECT DATE(qh.created_at) as query_date, COUNT(*) as query_count
                    FROM query_history qh
                    WHERE qh.created_at >= ?
                    GROUP BY DATE(qh.created_at)
                    ORDER BY query_date
                """, [cutoff_time.isoformat()])
                daily_volume = dict(cursor.fetchall())

                # Get most common query types
                cursor.execute(f"""
                    SELECT qh.query_type, COUNT(*) as count
                    FROM query_history qh
                    WHERE qh.created_at >= ?
                    GROUP BY qh.query_type
                    ORDER BY count DESC
                """, [cutoff_time.isoformat()])
                query_types = dict(cursor.fetchall())

                # Get average similarity scores
                cursor.execute(f"""
                    SELECT AVG(rr.similarity_score) as avg_similarity
                    FROM retrieval_results rr
                    JOIN query_history qh ON rr.query_id = qh.query_id
                    WHERE qh.created_at >= ? AND rr.similarity_score IS NOT NULL
                """, [cutoff_time.isoformat()])
                avg_similarity = cursor.fetchone()[0] or 0.0

                # Get user feedback summary
                cursor.execute(f"""
                    SELECT AVG(uf.relevance_score) as avg_relevance,
                           AVG(uf.usefulness_score) as avg_usefulness,
                           COUNT(*) as feedback_count
                    FROM user_feedback uf
                    JOIN query_history qh ON uf.query_id = qh.query_id
                    WHERE qh.created_at >= ?
                """, [cutoff_time.isoformat()])
                feedback_stats = cursor.fetchone()

                return {
                    'time_period_days': days,
                    'average_response_time_ms': round(avg_response_time, 2),
                    'daily_query_volume': daily_volume,
                    'query_type_distribution': query_types,
                    'average_similarity_score': round(avg_similarity, 3),
                    'user_feedback': {
                        'average_relevance_score': round(feedback_stats[0], 3) if feedback_stats[0] else None,
                        'average_usefulness_score': round(feedback_stats[1], 3) if feedback_stats[1] else None,
                        'total_feedback_count': feedback_stats[2] or 0
                    }
                }

            except Exception as e:
                self._logger.error(f"Failed to get performance analytics: {e}")
                raise
            finally:
                conn.close()

    def search_queries(self, search_text: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search queries using full-text search.

        Args:
            search_text: Text to search for in queries
            limit: Maximum number of results to return

        Returns:
            List of matching query dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT qh.query_id, qh.session_id, qh.query_text, qh.query_type,
                           qh.query_hash, qh.embedding_model, qh.similarity_threshold,
                           qh.max_results, qh.filters, qh.query_metadata, qh.created_at
                    FROM queries_fts fts
                    JOIN query_history qh ON qh.query_id = fts.query_id
                    WHERE queries_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (search_text, limit))

                rows = cursor.fetchall()
                queries = []

                for row in rows:
                    queries.append({
                        'query_id': row[0],
                        'session_id': row[1],
                        'query_text': row[2],
                        'query_type': row[3],
                        'query_hash': row[4],
                        'embedding_model': row[5],
                        'similarity_threshold': row[6],
                        'max_results': row[7],
                        'filters': json.loads(row[8]) if row[8] else None,
                        'query_metadata': json.loads(row[9]) if row[9] else None,
                        'created_at': row[10]
                    })

                return queries

            except Exception as e:
                self._logger.error(f"Failed to search queries: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old data based on retention policies.

        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            'sessions_cleaned': 0,
            'queries_cleaned': 0,
            'results_cleaned': 0,
            'metrics_cleaned': 0,
            'feedback_cleaned': 0
        }

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate cutoff dates
                history_cutoff = datetime.now() - timedelta(days=self._history_retention_days)
                metrics_cutoff = datetime.now() - timedelta(days=self._detailed_metrics_retention_days)

                # Clean up old sessions
                cursor.execute("""
                    DELETE FROM retrieval_sessions
                    WHERE start_time < ?
                """, (history_cutoff.isoformat(),))
                cleanup_stats['sessions_cleaned'] = cursor.rowcount

                # Clean up old queries (cascades to results and metrics)
                cursor.execute("""
                    DELETE FROM query_history
                    WHERE created_at < ?
                """, (history_cutoff.isoformat(),))
                cleanup_stats['queries_cleaned'] = cursor.rowcount

                # Clean up old detailed metrics (keep aggregated ones longer)
                cursor.execute("""
                    DELETE FROM performance_metrics
                    WHERE measurement_timestamp < ? AND metric_type = 'detailed'
                """, (metrics_cutoff.isoformat(),))
                cleanup_stats['metrics_cleaned'] = cursor.rowcount

                conn.commit()

                total_cleaned = sum(cleanup_stats.values())
                if total_cleaned > 0:
                    self._logger.info(f"Cleaned up {total_cleaned} old records")

                return cleanup_stats

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old data: {e}")
                raise
            finally:
                conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get retrieval history database statistics.

        Returns:
            Dictionary with database statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get total counts
                cursor.execute("SELECT COUNT(*) FROM retrieval_sessions")
                total_sessions = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM query_history")
                total_queries = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM retrieval_results")
                total_results = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM performance_metrics")
                total_metrics = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM user_feedback")
                total_feedback = cursor.fetchone()[0]

                # Get active sessions (not ended)
                cursor.execute("SELECT COUNT(*) FROM retrieval_sessions WHERE end_time IS NULL")
                active_sessions = cursor.fetchone()[0]

                # Get average results per query
                cursor.execute("""
                    SELECT AVG(result_count) FROM (
                        SELECT COUNT(*) as result_count
                        FROM retrieval_results
                        GROUP BY query_id
                    )
                """)
                avg_results_per_query = cursor.fetchone()[0] or 0.0

                # Get most recent activity
                cursor.execute("SELECT MAX(created_at) FROM query_history")
                last_query_time = cursor.fetchone()[0]

                return {
                    'total_sessions': total_sessions,
                    'active_sessions': active_sessions,
                    'total_queries': total_queries,
                    'total_results': total_results,
                    'total_performance_metrics': total_metrics,
                    'total_user_feedback': total_feedback,
                    'average_results_per_query': round(avg_results_per_query, 2),
                    'last_query_time': last_query_time,
                    'database_path': self._db_path
                }

            except Exception as e:
                self._logger.error(f"Failed to get retrieval history statistics: {e}")
                raise
            finally:
                conn.close()
