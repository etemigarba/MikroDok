"""
Module: document_database_integration
Description: Integrates all Phase 3 database modules with existing database infrastructure
Phase: 3
Location: /src/modules/database/document_database_integration.py
"""

# Standard library imports
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError, ErrorSeverity

# Phase 3 database modules
from src.modules.database.documents_db.document_repository_db.document_repository_db import DocumentRepositoryDB
from src.modules.database.documents_db.document_chunks_db.document_chunks_db import DocumentChunksDB
from src.modules.database.documents_db.extraction_results_db.extraction_results_db import ExtractionResultsDB

from src.modules.database.document_collections_db.collection_manager_db.collection_manager_db import CollectionManagerDB
from src.modules.database.document_collections_db.collection_metadata_db.collection_metadata_db import CollectionMetadataDB

from src.modules.database.document_queue_db.processing_queue_db.processing_queue_db import ProcessingQueueDB
from src.modules.database.document_queue_db.queue_status_db.queue_status_db import QueueStatusDB

from src.modules.database.document_quality_db.quality_metrics_db.quality_metrics_db import QualityMetricsDB
from src.modules.database.document_quality_db.deduplication_cache_db.deduplication_cache_db import DeduplicationCacheDB


@dataclass
class DatabaseIntegrationConfig:
    """Configuration for database integration."""
    database_path: str = "data/mikrodok.db"
    enable_wal_mode: bool = True
    enable_foreign_keys: bool = True
    connection_timeout: int = 30
    max_connections: int = 10
    backup_interval_hours: int = 24
    vacuum_interval_hours: int = 168  # Weekly
    enable_connection_pooling: bool = True


class DocumentDatabaseIntegration:
    """
    Integrates all Phase 3 database modules with centralized connection management.
    
    Provides:
    - Centralized database connection management
    - Transaction coordination across modules
    - Database schema initialization and migration
    - Performance optimization and maintenance
    - Backup and recovery coordination
    - Connection pooling and resource management
    """
    
    def __init__(self, config: Optional[DatabaseIntegrationConfig] = None):
        """Initialize the database integration."""
        self.config = config or DatabaseIntegrationConfig()
        self._logger = get_logger(__name__)
        
        # Database connection management
        self._connection_lock = threading.RLock()
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._connection_count = 0
        
        # Database modules
        self.document_repository: Optional[DocumentRepositoryDB] = None
        self.document_chunks: Optional[DocumentChunksDB] = None
        self.extraction_results: Optional[ExtractionResultsDB] = None
        self.collection_manager: Optional[CollectionManagerDB] = None
        self.collection_metadata: Optional[CollectionMetadataDB] = None
        self.processing_queue: Optional[ProcessingQueueDB] = None
        self.queue_status: Optional[QueueStatusDB] = None
        self.quality_metrics: Optional[QualityMetricsDB] = None
        self.deduplication_cache: Optional[DeduplicationCacheDB] = None
        
        # Initialize database
        self._initialize_database()
        
        self._logger.info("Document database integration initialized")
    
    def _initialize_database(self):
        """Initialize database and all modules."""
        try:
            # Ensure database directory exists
            db_path = Path(self.config.database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Initialize database modules
            self._initialize_database_modules()
            
            # Configure database settings
            self._configure_database()
            
            # Initialize schemas
            self._initialize_schemas()
            
            self._logger.info("Database initialization completed")
            
        except Exception as e:
            self._logger.error(f"Database initialization failed: {e}")
            raise
    
    def _initialize_database_modules(self):
        """Initialize all database modules."""
        try:
            # Documents database modules
            self.document_repository = DocumentRepositoryDB()
            self.document_chunks = DocumentChunksDB()
            self.extraction_results = ExtractionResultsDB()
            
            # Collections database modules
            self.collection_manager = CollectionManagerDB()
            self.collection_metadata = CollectionMetadataDB()
            
            # Queue database modules
            self.processing_queue = ProcessingQueueDB()
            self.queue_status = QueueStatusDB()
            
            # Quality database modules
            self.quality_metrics = QualityMetricsDB()
            self.deduplication_cache = DeduplicationCacheDB()
            
            self._logger.info("All database modules initialized")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize database modules: {e}")
            raise
    
    def _configure_database(self):
        """Configure database settings."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                if self.config.enable_wal_mode:
                    cursor.execute("PRAGMA journal_mode=WAL")
                
                # Enable foreign key constraints
                if self.config.enable_foreign_keys:
                    cursor.execute("PRAGMA foreign_keys=ON")
                
                # Set connection timeout
                cursor.execute(f"PRAGMA busy_timeout={self.config.connection_timeout * 1000}")
                
                # Optimize for performance
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                
                conn.commit()
                
            self._logger.info("Database configuration completed")
            
        except Exception as e:
            self._logger.error(f"Database configuration failed: {e}")
            raise
    
    def _initialize_schemas(self):
        """Initialize database schemas for all modules."""
        try:
            with self.get_connection() as conn:
                # Initialize each module's schema
                modules = [
                    self.document_repository,
                    self.document_chunks,
                    self.extraction_results,
                    self.collection_manager,
                    self.collection_metadata,
                    self.processing_queue,
                    self.queue_status,
                    self.quality_metrics,
                    self.deduplication_cache
                ]
                
                for module in modules:
                    if hasattr(module, 'initialize_schema'):
                        module.initialize_schema(conn)
                
                conn.commit()
                
            self._logger.info("Database schemas initialized")
            
        except Exception as e:
            self._logger.error(f"Schema initialization failed: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with automatic cleanup."""
        thread_id = threading.get_ident()
        
        with self._connection_lock:
            if thread_id not in self._connections:
                conn = sqlite3.connect(
                    self.config.database_path,
                    timeout=self.config.connection_timeout,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                self._connections[thread_id] = conn
                self._connection_count += 1
        
        try:
            yield self._connections[thread_id]
        finally:
            # Connection cleanup is handled by close_connections()
            pass
    
    @contextmanager
    def transaction(self):
        """Execute operations within a database transaction."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def store_document_complete(self, document_data: Dict[str, Any], 
                              chunks: List[Dict[str, Any]], 
                              extraction_metadata: Dict[str, Any],
                              quality_metrics: Dict[str, Any]) -> str:
        """
        Store complete document processing results in a single transaction.
        
        Args:
            document_data: Document metadata and content
            chunks: Document chunks
            extraction_metadata: Extraction results
            quality_metrics: Quality analysis results
            
        Returns:
            Document ID
        """
        try:
            with self.transaction() as conn:
                # Store document
                document_id = self.document_repository.store_document(document_data, conn)
                
                # Store chunks
                for chunk in chunks:
                    chunk['document_id'] = document_id
                    self.document_chunks.store_chunk(chunk, conn)
                
                # Store extraction results
                extraction_metadata['document_id'] = document_id
                self.extraction_results.store_extraction_result(extraction_metadata, conn)
                
                # Store quality metrics
                quality_metrics['document_id'] = document_id
                self.quality_metrics.store_quality_metrics(quality_metrics, conn)
                
                self._logger.info(f"Stored complete document: {document_id}")
                return document_id
                
        except Exception as e:
            self._logger.error(f"Failed to store complete document: {e}")
            raise
    
    def delete_document_complete(self, document_id: str) -> bool:
        """
        Delete document and all related data in a single transaction.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if deletion was successful
        """
        try:
            with self.transaction() as conn:
                # Delete in reverse dependency order
                self.quality_metrics.delete_quality_metrics(document_id, conn)
                self.extraction_results.delete_extraction_result(document_id, conn)
                self.document_chunks.delete_chunks_by_document(document_id, conn)
                self.document_repository.delete_document(document_id, conn)
                
                self._logger.info(f"Deleted complete document: {document_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to delete complete document {document_id}: {e}")
            return False
    
    def get_document_complete(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete document data including chunks, extraction results, and quality metrics.
        
        Args:
            document_id: Document ID
            
        Returns:
            Complete document data or None if not found
        """
        try:
            with self.get_connection() as conn:
                # Get document data
                document_data = self.document_repository.get_document(document_id, conn)
                if not document_data:
                    return None
                
                # Get related data
                chunks = self.document_chunks.get_chunks_by_document(document_id, conn)
                extraction_results = self.extraction_results.get_extraction_result(document_id, conn)
                quality_metrics = self.quality_metrics.get_quality_metrics(document_id, conn)
                
                return {
                    'document': document_data,
                    'chunks': chunks,
                    'extraction_results': extraction_results,
                    'quality_metrics': quality_metrics
                }
                
        except Exception as e:
            self._logger.error(f"Failed to get complete document {document_id}: {e}")
            return None
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Get table counts
                tables = [
                    'documents', 'document_chunks', 'extraction_results',
                    'collections', 'collection_metadata', 'processing_queue',
                    'queue_status', 'quality_metrics', 'deduplication_cache'
                ]
                
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        stats[f"{table}_count"] = count
                    except sqlite3.OperationalError:
                        stats[f"{table}_count"] = 0
                
                # Get database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                stats['database_size_bytes'] = page_count * page_size
                
                # Get connection count
                stats['active_connections'] = self._connection_count
                
                return stats
                
        except Exception as e:
            self._logger.error(f"Failed to get database statistics: {e}")
            return {}
    
    def vacuum_database(self) -> bool:
        """Vacuum the database to reclaim space and optimize performance."""
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                
            self._logger.info("Database vacuum completed")
            return True
            
        except Exception as e:
            self._logger.error(f"Database vacuum failed: {e}")
            return False
    
    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database."""
        try:
            backup_path_obj = Path(backup_path)
            backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
            
            self._logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Database backup failed: {e}")
            return False
    
    def close_connections(self):
        """Close all database connections."""
        with self._connection_lock:
            for conn in self._connections.values():
                try:
                    conn.close()
                except Exception as e:
                    self._logger.warning(f"Error closing connection: {e}")
            
            self._connections.clear()
            self._connection_count = 0
            
        self._logger.info("All database connections closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_connections()
