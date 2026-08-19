"""
Module: quality_metrics_db
Description: Persists document quality scores, validation results, and assessment history
Phase: 3
Location: /src/modules/database/document_quality_db/quality_metrics_db/
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
from src.modules.logic.document_quality_lg.base_interfaces import (
    QualityCategory, QualityMetric, ContentAnalysisResult, 
    QualityScoreResult, DeduplicationResult
)


class QualityStatus(Enum):
    """Quality assessment status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class QualityMetricsDB:
    """
    Quality metrics database manager.
    
    Handles storage and retrieval of document quality scores, validation results,
    and assessment history with comprehensive tracking and analysis capabilities.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the quality metrics database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to document quality data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "document_quality"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "quality_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._metrics_retention_days = 365  # Keep metrics for 1 year
        self._detailed_retention_days = 90   # Keep detailed analysis for 90 days
        self._batch_size = 1000
        
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Document quality metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_quality_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_id TEXT UNIQUE NOT NULL,
                        document_id TEXT NOT NULL,
                        document_path TEXT,
                        overall_score REAL NOT NULL,
                        text_quality REAL,
                        ocr_confidence REAL,
                        completeness_score REAL,
                        duplicate_content_ratio REAL,
                        validation_warnings TEXT,
                        validation_errors TEXT,
                        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'completed',
                        processing_time_ms REAL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Quality category scores table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quality_category_scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        score_id TEXT UNIQUE NOT NULL,
                        metric_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        score REAL NOT NULL,
                        weight REAL DEFAULT 1.0,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (metric_id) REFERENCES document_quality_metrics (metric_id)
                    )
                """)
                
                # Quality metric scores table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quality_metric_scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        score_id TEXT UNIQUE NOT NULL,
                        metric_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        score REAL NOT NULL,
                        threshold REAL,
                        passed BOOLEAN DEFAULT TRUE,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (metric_id) REFERENCES document_quality_metrics (metric_id)
                    )
                """)
                
                # Quality assessment history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quality_assessment_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assessment_id TEXT UNIQUE NOT NULL,
                        document_id TEXT NOT NULL,
                        assessment_type TEXT NOT NULL,
                        previous_score REAL,
                        new_score REAL,
                        score_change REAL,
                        reason TEXT,
                        assessor TEXT,
                        assessment_details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Quality validation results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quality_validation_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        validation_id TEXT UNIQUE NOT NULL,
                        metric_id TEXT NOT NULL,
                        validation_type TEXT NOT NULL,
                        validation_rule TEXT,
                        result TEXT NOT NULL,
                        severity TEXT DEFAULT 'info',
                        message TEXT,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (metric_id) REFERENCES document_quality_metrics (metric_id)
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_metrics_document_id ON document_quality_metrics (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_metrics_evaluated_at ON document_quality_metrics (evaluated_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_metrics_overall_score ON document_quality_metrics (overall_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_metrics_status ON document_quality_metrics (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_scores_metric_id ON quality_category_scores (metric_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_scores_metric_id ON quality_metric_scores (metric_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_assessment_history_document_id ON quality_assessment_history (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_results_metric_id ON quality_validation_results (metric_id)")
                
                conn.commit()
                self._logger.info("Quality metrics database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize quality metrics database: {e}")
                raise
            finally:
                conn.close()

    def store_quality_metrics(self, document_id: str, overall_score: float,
                            text_quality: Optional[float] = None,
                            ocr_confidence: Optional[float] = None,
                            completeness_score: Optional[float] = None,
                            duplicate_content_ratio: Optional[float] = None,
                            validation_warnings: Optional[List[str]] = None,
                            validation_errors: Optional[List[str]] = None,
                            document_path: Optional[str] = None,
                            processing_time_ms: Optional[float] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store document quality metrics.

        Args:
            document_id: Document identifier
            overall_score: Overall quality score (0.0-100.0)
            text_quality: Text extraction quality score
            ocr_confidence: OCR confidence if applicable
            completeness_score: Document completeness metric
            duplicate_content_ratio: Percentage of duplicate content
            validation_warnings: List of validation warnings
            validation_errors: List of validation errors
            document_path: Path to the document file
            processing_time_ms: Processing time in milliseconds
            metadata: Additional metadata

        Returns:
            Metric ID for the stored metrics
        """
        metric_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO document_quality_metrics (
                        metric_id, document_id, document_path, overall_score,
                        text_quality, ocr_confidence, completeness_score,
                        duplicate_content_ratio, validation_warnings, validation_errors,
                        processing_time_ms, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, document_id, document_path, overall_score,
                    text_quality, ocr_confidence, completeness_score,
                    duplicate_content_ratio,
                    json.dumps(validation_warnings) if validation_warnings else None,
                    json.dumps(validation_errors) if validation_errors else None,
                    processing_time_ms,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                self._logger.info(f"Stored quality metrics {metric_id} for document {document_id}")
                return metric_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store quality metrics for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def store_quality_score_result(self, document_id: str, score_result: QualityScoreResult,
                                 document_path: Optional[str] = None) -> str:
        """
        Store quality score result from quality analysis.

        Args:
            document_id: Document identifier
            score_result: Quality score result object
            document_path: Path to the document file

        Returns:
            Metric ID for the stored result
        """
        # Store main quality metrics
        metric_id = self.store_quality_metrics(
            document_id=document_id,
            overall_score=score_result.overall_score,
            document_path=document_path,
            processing_time_ms=score_result.processing_time_ms,
            metadata=score_result.metadata
        )

        # Store category scores
        for category, score in score_result.category_scores.items():
            self.store_category_score(metric_id, category, score)

        # Store metric scores
        for metric, score in score_result.metric_scores.items():
            self.store_metric_score(metric_id, metric, score)

        return metric_id

    def store_category_score(self, metric_id: str, category: QualityCategory,
                           score: float, weight: float = 1.0,
                           details: Optional[Dict[str, Any]] = None) -> str:
        """
        Store quality category score.

        Args:
            metric_id: Parent metric ID
            category: Quality category
            score: Category score
            weight: Category weight
            details: Additional details

        Returns:
            Score ID for the stored category score
        """
        score_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO quality_category_scores (
                        score_id, metric_id, category, score, weight, details
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    score_id, metric_id, category.value, score, weight,
                    json.dumps(details) if details else None
                ))

                conn.commit()
                return score_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store category score for {metric_id}: {e}")
                raise
            finally:
                conn.close()

    def store_metric_score(self, metric_id: str, metric: QualityMetric,
                         score: float, threshold: Optional[float] = None,
                         details: Optional[Dict[str, Any]] = None) -> str:
        """
        Store quality metric score.

        Args:
            metric_id: Parent metric ID
            metric: Quality metric
            score: Metric score
            threshold: Score threshold
            details: Additional details

        Returns:
            Score ID for the stored metric score
        """
        score_id = str(uuid.uuid4())
        passed = threshold is None or score >= threshold

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO quality_metric_scores (
                        score_id, metric_id, metric_name, score, threshold, passed, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    score_id, metric_id, metric.value, score, threshold, passed,
                    json.dumps(details) if details else None
                ))

                conn.commit()
                return score_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store metric score for {metric_id}: {e}")
                raise
            finally:
                conn.close()

    def store_validation_result(self, metric_id: str, validation_type: str,
                              validation_rule: str, result: str,
                              severity: str = "info", message: Optional[str] = None,
                              details: Optional[Dict[str, Any]] = None) -> str:
        """
        Store quality validation result.

        Args:
            metric_id: Parent metric ID
            validation_type: Type of validation
            validation_rule: Validation rule applied
            result: Validation result
            severity: Result severity
            message: Validation message
            details: Additional details

        Returns:
            Validation ID for the stored result
        """
        validation_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO quality_validation_results (
                        validation_id, metric_id, validation_type, validation_rule,
                        result, severity, message, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    validation_id, metric_id, validation_type, validation_rule,
                    result, severity, message,
                    json.dumps(details) if details else None
                ))

                conn.commit()
                return validation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to store validation result for {metric_id}: {e}")
                raise
            finally:
                conn.close()

    def get_quality_metrics(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get quality metrics for a document.

        Args:
            document_id: Document identifier

        Returns:
            Quality metrics dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT metric_id, document_id, document_path, overall_score,
                           text_quality, ocr_confidence, completeness_score,
                           duplicate_content_ratio, validation_warnings, validation_errors,
                           evaluated_at, status, processing_time_ms, metadata
                    FROM document_quality_metrics
                    WHERE document_id = ?
                    ORDER BY evaluated_at DESC
                    LIMIT 1
                """, (document_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                metrics = {
                    'metric_id': row[0],
                    'document_id': row[1],
                    'document_path': row[2],
                    'overall_score': row[3],
                    'text_quality': row[4],
                    'ocr_confidence': row[5],
                    'completeness_score': row[6],
                    'duplicate_content_ratio': row[7],
                    'validation_warnings': json.loads(row[8]) if row[8] else [],
                    'validation_errors': json.loads(row[9]) if row[9] else [],
                    'evaluated_at': row[10],
                    'status': row[11],
                    'processing_time_ms': row[12],
                    'metadata': json.loads(row[13]) if row[13] else {}
                }

                # Get category scores
                metrics['category_scores'] = self._get_category_scores(row[0])

                # Get metric scores
                metrics['metric_scores'] = self._get_metric_scores(row[0])

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get quality metrics for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def _get_category_scores(self, metric_id: str) -> Dict[str, float]:
        """Get category scores for a metric."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, score
                FROM quality_category_scores
                WHERE metric_id = ?
            """, (metric_id,))

            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def _get_metric_scores(self, metric_id: str) -> Dict[str, float]:
        """Get metric scores for a metric."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT metric_name, score
                FROM quality_metric_scores
                WHERE metric_id = ?
            """, (metric_id,))

            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_quality_history(self, document_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get quality assessment history for a document.

        Args:
            document_id: Document identifier
            limit: Maximum number of history entries

        Returns:
            List of quality history entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT assessment_id, assessment_type, previous_score, new_score,
                           score_change, reason, assessor, assessment_details, created_at
                    FROM quality_assessment_history
                    WHERE document_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (document_id, limit))

                history = []
                for row in cursor.fetchall():
                    history.append({
                        'assessment_id': row[0],
                        'assessment_type': row[1],
                        'previous_score': row[2],
                        'new_score': row[3],
                        'score_change': row[4],
                        'reason': row[5],
                        'assessor': row[6],
                        'assessment_details': json.loads(row[7]) if row[7] else {},
                        'created_at': row[8]
                    })

                return history

            except Exception as e:
                self._logger.error(f"Failed to get quality history for {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_quality_statistics(self, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get quality statistics for a date range.

        Args:
            start_date: Start date for statistics
            end_date: End date for statistics

        Returns:
            Quality statistics dictionary
        """
        if start_date is None:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Overall statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_documents,
                           AVG(overall_score) as avg_score,
                           MIN(overall_score) as min_score,
                           MAX(overall_score) as max_score,
                           COUNT(CASE WHEN overall_score >= 90 THEN 1 END) as excellent_count,
                           COUNT(CASE WHEN overall_score >= 75 THEN 1 END) as good_count,
                           COUNT(CASE WHEN overall_score >= 60 THEN 1 END) as fair_count,
                           COUNT(CASE WHEN overall_score < 60 THEN 1 END) as poor_count
                    FROM document_quality_metrics
                    WHERE evaluated_at BETWEEN ? AND ?
                """, (start_date.isoformat(), end_date.isoformat()))

                row = cursor.fetchone()
                stats = {
                    'total_documents': row[0],
                    'average_score': row[1] or 0.0,
                    'min_score': row[2] or 0.0,
                    'max_score': row[3] or 0.0,
                    'quality_distribution': {
                        'excellent': row[4],
                        'good': row[5],
                        'fair': row[6],
                        'poor': row[7]
                    }
                }

                return stats

            except Exception as e:
                self._logger.error(f"Failed to get quality statistics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_metrics(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old quality metrics.

        Args:
            retention_days: Number of days to retain metrics

        Returns:
            Number of metrics cleaned up
        """
        if retention_days is None:
            retention_days = self._metrics_retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get metrics to delete
                cursor.execute("""
                    SELECT metric_id FROM document_quality_metrics
                    WHERE evaluated_at < ?
                """, (cutoff_date.isoformat(),))

                metric_ids = [row[0] for row in cursor.fetchall()]

                if not metric_ids:
                    return 0

                # Delete related records
                placeholders = ','.join(['?'] * len(metric_ids))

                cursor.execute(f"""
                    DELETE FROM quality_validation_results
                    WHERE metric_id IN ({placeholders})
                """, metric_ids)

                cursor.execute(f"""
                    DELETE FROM quality_metric_scores
                    WHERE metric_id IN ({placeholders})
                """, metric_ids)

                cursor.execute(f"""
                    DELETE FROM quality_category_scores
                    WHERE metric_id IN ({placeholders})
                """, metric_ids)

                cursor.execute(f"""
                    DELETE FROM document_quality_metrics
                    WHERE metric_id IN ({placeholders})
                """, metric_ids)

                conn.commit()
                self._logger.info(f"Cleaned up {len(metric_ids)} old quality metrics")
                return len(metric_ids)

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old metrics: {e}")
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close the database connection and cleanup resources."""
        with self._lock:
            self._logger.info("Quality metrics database closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
