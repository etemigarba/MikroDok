"""
Module: extraction_results_db
Description: Stores structured extraction results including tables, images, and metadata
Phase: 3
Location: /src/modules/database/documents_db/extraction_results_db/
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


class ExtractionResultsDB:
    """
    Extraction results database manager.
    
    Handles storage and retrieval of structured data extracted from documents
    including tables, images, metadata, and other structured content with
    confidence scores and spatial positioning information.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the extraction results database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to documents data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "documents"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "extraction_results.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._extraction_retention_days = 365  # Keep extractions for 1 year
        self._failed_extraction_retention_days = 30  # Keep failed extractions for 30 days
        
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
                
                # Create extraction results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        extraction_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        extraction_type TEXT NOT NULL,
                        content JSON NOT NULL,
                        confidence_score REAL NOT NULL,
                        page_number INTEGER,
                        bounding_box JSON,
                        metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create extraction validation table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_validation (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        validation_id TEXT NOT NULL UNIQUE,
                        extraction_id TEXT NOT NULL,
                        validation_status TEXT NOT NULL,
                        validation_score REAL,
                        validation_notes TEXT,
                        validated_by TEXT,
                        validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (extraction_id) REFERENCES extraction_results (extraction_id) ON DELETE CASCADE
                    )
                """)
                
                # Create extraction processing log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_processing_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        extraction_type TEXT NOT NULL,
                        processing_stage TEXT NOT NULL,
                        status TEXT NOT NULL,
                        processing_time_seconds REAL,
                        error_message TEXT,
                        resource_usage JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create extraction templates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_id TEXT NOT NULL UNIQUE,
                        template_name TEXT NOT NULL,
                        extraction_type TEXT NOT NULL,
                        template_config JSON NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create extraction statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stats_id TEXT NOT NULL UNIQUE,
                        document_id TEXT NOT NULL,
                        extraction_type TEXT NOT NULL,
                        total_extractions INTEGER DEFAULT 0,
                        successful_extractions INTEGER DEFAULT 0,
                        failed_extractions INTEGER DEFAULT 0,
                        average_confidence REAL DEFAULT 0.0,
                        processing_time_total REAL DEFAULT 0.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_extractions_document_id ON extraction_results (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_extractions_type ON extraction_results (extraction_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_extractions_confidence ON extraction_results (confidence_score)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_extractions_page ON extraction_results (page_number)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_extraction_id ON extraction_validation (extraction_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_status ON extraction_validation (validation_status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_log_document_id ON extraction_processing_log (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_log_type ON extraction_processing_log (extraction_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_log_status ON extraction_processing_log (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_templates_type ON extraction_templates (extraction_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_templates_active ON extraction_templates (is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_document_id ON extraction_statistics (document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_type ON extraction_statistics (extraction_type)")
                
                # Create unique constraints
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_statistics_document_type ON extraction_statistics (document_id, extraction_type)")
                
                # Create triggers for updated_at timestamps
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_extractions_timestamp 
                    AFTER UPDATE ON extraction_results
                    BEGIN
                        UPDATE extraction_results SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_templates_timestamp 
                    AFTER UPDATE ON extraction_templates
                    BEGIN
                        UPDATE extraction_templates SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                # Create trigger to update statistics
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_extraction_statistics 
                    AFTER INSERT ON extraction_results
                    BEGIN
                        INSERT OR REPLACE INTO extraction_statistics (
                            stats_id, document_id, extraction_type, total_extractions,
                            successful_extractions, average_confidence, last_updated
                        )
                        SELECT 
                            COALESCE(es.stats_id, lower(hex(randomblob(16)))),
                            NEW.document_id,
                            NEW.extraction_type,
                            COALESCE(es.total_extractions, 0) + 1,
                            COALESCE(es.successful_extractions, 0) + 1,
                            (COALESCE(es.average_confidence * es.successful_extractions, 0) + NEW.confidence_score) / 
                            (COALESCE(es.successful_extractions, 0) + 1),
                            CURRENT_TIMESTAMP
                        FROM (
                            SELECT * FROM extraction_statistics 
                            WHERE document_id = NEW.document_id AND extraction_type = NEW.extraction_type
                        ) es;
                    END
                """)
                
                conn.commit()

                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = ['extraction_results', 'extraction_validation', 'extraction_processing_log', 'extraction_templates', 'extraction_statistics']

                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")

                self._logger.info("Extraction results database initialized successfully")
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize extraction results database: {e}")
                raise
            finally:
                conn.close()
    
    def add_extraction_result(self, document_id: str, extraction_type: str,
                             content: Dict[str, Any], confidence_score: float,
                             page_number: Optional[int] = None,
                             bounding_box: Optional[Dict[str, Any]] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new extraction result.
        
        Args:
            document_id: Parent document identifier
            extraction_type: Type of extraction (table, image, metadata, text, etc.)
            content: Extracted structured content
            confidence_score: Extraction confidence (0.0-1.0)
            page_number: Source page number if applicable
            bounding_box: Location coordinates in document
            metadata: Additional extraction metadata
            
        Returns:
            Extraction ID of the added result
        """
        extraction_id = str(uuid.uuid4())
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Insert new extraction result
                cursor.execute("""
                    INSERT INTO extraction_results (
                        extraction_id, document_id, extraction_type, content,
                        confidence_score, page_number, bounding_box, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    extraction_id,
                    document_id,
                    extraction_type,
                    json.dumps(content),
                    confidence_score,
                    page_number,
                    json.dumps(bounding_box) if bounding_box else None,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                self._logger.info(f"Added extraction result {extraction_id} for document {document_id}")
                return extraction_id
                
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add extraction result for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_extraction_result(self, extraction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an extraction result by ID.

        Args:
            extraction_id: Extraction identifier

        Returns:
            Extraction result dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT extraction_id, document_id, extraction_type, content,
                           confidence_score, page_number, bounding_box, metadata,
                           created_at, updated_at
                    FROM extraction_results WHERE extraction_id = ?
                """, (extraction_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'extraction_id': row[0],
                    'document_id': row[1],
                    'extraction_type': row[2],
                    'content': json.loads(row[3]),
                    'confidence_score': row[4],
                    'page_number': row[5],
                    'bounding_box': json.loads(row[6]) if row[6] else None,
                    'metadata': json.loads(row[7]) if row[7] else None,
                    'created_at': row[8],
                    'updated_at': row[9]
                }

            except Exception as e:
                self._logger.error(f"Failed to get extraction result {extraction_id}: {e}")
                raise
            finally:
                conn.close()

    def get_document_extractions(self, document_id: str,
                                extraction_type: Optional[str] = None,
                                min_confidence: float = 0.0,
                                limit: Optional[int] = None,
                                offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all extraction results for a document.

        Args:
            document_id: Document identifier
            extraction_type: Filter by extraction type (optional)
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of extraction result dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                base_query = """
                    SELECT extraction_id, document_id, extraction_type, content,
                           confidence_score, page_number, bounding_box, metadata,
                           created_at, updated_at
                    FROM extraction_results
                    WHERE document_id = ? AND confidence_score >= ?
                """
                params = [document_id, min_confidence]

                if extraction_type:
                    base_query += " AND extraction_type = ?"
                    params.append(extraction_type)

                base_query += " ORDER BY page_number, confidence_score DESC"

                if limit:
                    base_query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])
                else:
                    base_query += " OFFSET ?"
                    params.append(offset)

                cursor.execute(base_query, params)
                rows = cursor.fetchall()
                extractions = []

                for row in rows:
                    extractions.append({
                        'extraction_id': row[0],
                        'document_id': row[1],
                        'extraction_type': row[2],
                        'content': json.loads(row[3]),
                        'confidence_score': row[4],
                        'page_number': row[5],
                        'bounding_box': json.loads(row[6]) if row[6] else None,
                        'metadata': json.loads(row[7]) if row[7] else None,
                        'created_at': row[8],
                        'updated_at': row[9]
                    })

                return extractions

            except Exception as e:
                self._logger.error(f"Failed to get extractions for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_extractions_by_type(self, extraction_type: str,
                               min_confidence: float = 0.0,
                               limit: int = 100,
                               offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get extraction results by type across all documents.

        Args:
            extraction_type: Type of extraction to retrieve
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of extraction result dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT extraction_id, document_id, extraction_type, content,
                           confidence_score, page_number, bounding_box, metadata,
                           created_at, updated_at
                    FROM extraction_results
                    WHERE extraction_type = ? AND confidence_score >= ?
                    ORDER BY confidence_score DESC
                    LIMIT ? OFFSET ?
                """, (extraction_type, min_confidence, limit, offset))

                rows = cursor.fetchall()
                extractions = []

                for row in rows:
                    extractions.append({
                        'extraction_id': row[0],
                        'document_id': row[1],
                        'extraction_type': row[2],
                        'content': json.loads(row[3]),
                        'confidence_score': row[4],
                        'page_number': row[5],
                        'bounding_box': json.loads(row[6]) if row[6] else None,
                        'metadata': json.loads(row[7]) if row[7] else None,
                        'created_at': row[8],
                        'updated_at': row[9]
                    })

                return extractions

            except Exception as e:
                self._logger.error(f"Failed to get extractions by type {extraction_type}: {e}")
                raise
            finally:
                conn.close()

    def add_validation(self, extraction_id: str, validation_status: str,
                      validation_score: Optional[float] = None,
                      validation_notes: Optional[str] = None,
                      validated_by: str = "system") -> str:
        """
        Add validation result for an extraction.

        Args:
            extraction_id: Extraction identifier
            validation_status: Validation status (valid, invalid, uncertain)
            validation_score: Validation confidence score (0.0-1.0)
            validation_notes: Additional validation notes
            validated_by: Who performed the validation

        Returns:
            Validation ID
        """
        validation_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO extraction_validation (
                        validation_id, extraction_id, validation_status,
                        validation_score, validation_notes, validated_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (validation_id, extraction_id, validation_status,
                      validation_score, validation_notes, validated_by))

                conn.commit()
                self._logger.info(f"Added validation {validation_id} for extraction {extraction_id}")
                return validation_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add validation for extraction {extraction_id}: {e}")
                raise
            finally:
                conn.close()

    def get_validation(self, extraction_id: str) -> Optional[Dict[str, Any]]:
        """
        Get validation result for an extraction.

        Args:
            extraction_id: Extraction identifier

        Returns:
            Validation data dictionary or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT validation_id, validation_status, validation_score,
                           validation_notes, validated_by, validated_at
                    FROM extraction_validation WHERE extraction_id = ?
                    ORDER BY validated_at DESC LIMIT 1
                """, (extraction_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'validation_id': row[0],
                    'validation_status': row[1],
                    'validation_score': row[2],
                    'validation_notes': row[3],
                    'validated_by': row[4],
                    'validated_at': row[5]
                }

            except Exception as e:
                self._logger.error(f"Failed to get validation for extraction {extraction_id}: {e}")
                raise
            finally:
                conn.close()

    def log_processing_event(self, document_id: str, extraction_type: str,
                            processing_stage: str, status: str,
                            processing_time: Optional[float] = None,
                            error_message: Optional[str] = None,
                            resource_usage: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a processing event.

        Args:
            document_id: Document identifier
            extraction_type: Type of extraction being processed
            processing_stage: Current processing stage
            status: Processing status (started, completed, failed)
            processing_time: Processing time in seconds
            error_message: Error message if status is failed
            resource_usage: Resource usage metrics

        Returns:
            Log ID
        """
        log_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO extraction_processing_log (
                        log_id, document_id, extraction_type, processing_stage,
                        status, processing_time_seconds, error_message, resource_usage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (log_id, document_id, extraction_type, processing_stage,
                      status, processing_time, error_message,
                      json.dumps(resource_usage) if resource_usage else None))

                conn.commit()
                self._logger.info(f"Logged processing event {log_id} for document {document_id}")
                return log_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to log processing event: {e}")
                raise
            finally:
                conn.close()

    def create_extraction_template(self, template_name: str, extraction_type: str,
                                  template_config: Dict[str, Any],
                                  description: Optional[str] = None) -> str:
        """
        Create an extraction template.

        Args:
            template_name: Name of the template
            extraction_type: Type of extraction this template handles
            template_config: Template configuration parameters
            description: Optional description

        Returns:
            Template ID
        """
        template_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO extraction_templates (
                        template_id, template_name, extraction_type,
                        template_config, description
                    ) VALUES (?, ?, ?, ?, ?)
                """, (template_id, template_name, extraction_type,
                      json.dumps(template_config), description))

                conn.commit()
                self._logger.info(f"Created extraction template {template_id}: {template_name}")
                return template_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create extraction template: {e}")
                raise
            finally:
                conn.close()

    def get_extraction_templates(self, extraction_type: Optional[str] = None,
                                active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get extraction templates.

        Args:
            extraction_type: Filter by extraction type (optional)
            active_only: Only return active templates

        Returns:
            List of template data dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                base_query = """
                    SELECT template_id, template_name, extraction_type,
                           template_config, description, is_active,
                           created_at, updated_at
                    FROM extraction_templates
                """
                params = []
                conditions = []

                if active_only:
                    conditions.append("is_active = 1")

                if extraction_type:
                    conditions.append("extraction_type = ?")
                    params.append(extraction_type)

                if conditions:
                    base_query += " WHERE " + " AND ".join(conditions)

                base_query += " ORDER BY template_name"

                cursor.execute(base_query, params)
                rows = cursor.fetchall()
                templates = []

                for row in rows:
                    templates.append({
                        'template_id': row[0],
                        'template_name': row[1],
                        'extraction_type': row[2],
                        'template_config': json.loads(row[3]),
                        'description': row[4],
                        'is_active': bool(row[5]),
                        'created_at': row[6],
                        'updated_at': row[7]
                    })

                return templates

            except Exception as e:
                self._logger.error(f"Failed to get extraction templates: {e}")
                raise
            finally:
                conn.close()

    def delete_extraction_result(self, extraction_id: str) -> bool:
        """
        Delete an extraction result and all associated data.

        Args:
            extraction_id: Extraction identifier

        Returns:
            True if deletion was successful
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM extraction_results WHERE extraction_id = ?", (extraction_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    self._logger.info(f"Deleted extraction result {extraction_id}")
                    return True
                else:
                    self._logger.warning(f"Extraction result {extraction_id} not found for deletion")
                    return False

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete extraction result {extraction_id}: {e}")
                raise
            finally:
                conn.close()

    def delete_document_extractions(self, document_id: str) -> int:
        """
        Delete all extraction results for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of extraction results deleted
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM extraction_results WHERE document_id = ?", (document_id,))
                conn.commit()

                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self._logger.info(f"Deleted {deleted_count} extraction results for document {document_id}")

                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to delete extractions for document {document_id}: {e}")
                raise
            finally:
                conn.close()

    def get_extraction_statistics(self, document_id: Optional[str] = None,
                                 extraction_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get extraction statistics.

        Args:
            document_id: Filter by document (optional)
            extraction_type: Filter by extraction type (optional)

        Returns:
            Dictionary with extraction statistics
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build base query
                base_conditions = []
                params = []

                if document_id:
                    base_conditions.append("document_id = ?")
                    params.append(document_id)

                if extraction_type:
                    base_conditions.append("extraction_type = ?")
                    params.append(extraction_type)

                where_clause = " WHERE " + " AND ".join(base_conditions) if base_conditions else ""

                # Get total extractions
                cursor.execute(f"SELECT COUNT(*) FROM extraction_results{where_clause}", params)
                total_extractions = cursor.fetchone()[0]

                # Get extractions by type
                cursor.execute(f"""
                    SELECT extraction_type, COUNT(*), AVG(confidence_score)
                    FROM extraction_results{where_clause}
                    GROUP BY extraction_type
                """, params)
                type_stats = cursor.fetchall()

                # Get confidence distribution
                cursor.execute(f"""
                    SELECT
                        COUNT(CASE WHEN confidence_score >= 0.9 THEN 1 END) as high_confidence,
                        COUNT(CASE WHEN confidence_score >= 0.7 AND confidence_score < 0.9 THEN 1 END) as medium_confidence,
                        COUNT(CASE WHEN confidence_score < 0.7 THEN 1 END) as low_confidence,
                        AVG(confidence_score) as average_confidence
                    FROM extraction_results{where_clause}
                """, params)
                confidence_stats = cursor.fetchone()

                # Get validation statistics
                cursor.execute(f"""
                    SELECT
                        COUNT(CASE WHEN ev.validation_status = 'valid' THEN 1 END) as valid_count,
                        COUNT(CASE WHEN ev.validation_status = 'invalid' THEN 1 END) as invalid_count,
                        COUNT(CASE WHEN ev.validation_status = 'uncertain' THEN 1 END) as uncertain_count
                    FROM extraction_results er
                    LEFT JOIN extraction_validation ev ON er.extraction_id = ev.extraction_id{where_clause}
                """, params)
                validation_stats = cursor.fetchone()

                return {
                    'total_extractions': total_extractions,
                    'extractions_by_type': {
                        row[0]: {'count': row[1], 'avg_confidence': round(row[2], 3)}
                        for row in type_stats
                    },
                    'confidence_distribution': {
                        'high_confidence': confidence_stats[0] or 0,
                        'medium_confidence': confidence_stats[1] or 0,
                        'low_confidence': confidence_stats[2] or 0,
                        'average_confidence': round(confidence_stats[3], 3) if confidence_stats[3] else 0.0
                    },
                    'validation_statistics': {
                        'valid_count': validation_stats[0] or 0,
                        'invalid_count': validation_stats[1] or 0,
                        'uncertain_count': validation_stats[2] or 0
                    },
                    'database_path': self._db_path
                }

            except Exception as e:
                self._logger.error(f"Failed to get extraction statistics: {e}")
                raise
            finally:
                conn.close()

    def cleanup_old_extractions(self) -> int:
        """
        Clean up old extraction results based on retention policies.

        Returns:
            Number of extraction results cleaned up
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Calculate cutoff dates
                extraction_cutoff = datetime.now() - timedelta(days=self._extraction_retention_days)
                failed_cutoff = datetime.now() - timedelta(days=self._failed_extraction_retention_days)

                # Delete old extraction results
                cursor.execute("""
                    DELETE FROM extraction_results
                    WHERE created_at < ?
                """, (extraction_cutoff.isoformat(),))

                extraction_count = cursor.rowcount

                # Delete old failed processing logs
                cursor.execute("""
                    DELETE FROM extraction_processing_log
                    WHERE status = 'failed' AND created_at < ?
                """, (failed_cutoff.isoformat(),))

                log_count = cursor.rowcount
                total_cleaned = extraction_count + log_count

                conn.commit()

                if total_cleaned > 0:
                    self._logger.info(f"Cleaned up {total_cleaned} old extraction records "
                                    f"({extraction_count} results, {log_count} logs)")

                return total_cleaned

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old extractions: {e}")
                raise
            finally:
                conn.close()

    def get_processing_history(self, document_id: str,
                              extraction_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get processing history for a document.

        Args:
            document_id: Document identifier
            extraction_type: Filter by extraction type (optional)

        Returns:
            List of processing log entries
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                if extraction_type:
                    cursor.execute("""
                        SELECT log_id, extraction_type, processing_stage, status,
                               processing_time_seconds, error_message, resource_usage, created_at
                        FROM extraction_processing_log
                        WHERE document_id = ? AND extraction_type = ?
                        ORDER BY created_at DESC
                    """, (document_id, extraction_type))
                else:
                    cursor.execute("""
                        SELECT log_id, extraction_type, processing_stage, status,
                               processing_time_seconds, error_message, resource_usage, created_at
                        FROM extraction_processing_log
                        WHERE document_id = ?
                        ORDER BY created_at DESC
                    """, (document_id,))

                rows = cursor.fetchall()
                history = []

                for row in rows:
                    history.append({
                        'log_id': row[0],
                        'extraction_type': row[1],
                        'processing_stage': row[2],
                        'status': row[3],
                        'processing_time_seconds': row[4],
                        'error_message': row[5],
                        'resource_usage': json.loads(row[6]) if row[6] else None,
                        'created_at': row[7]
                    })

                return history

            except Exception as e:
                self._logger.error(f"Failed to get processing history for document {document_id}: {e}")
                raise
            finally:
                conn.close()
