"""
Module: document_processing_service_lg
Description: Orchestrates complete document processing pipeline from upload to training-ready chunks
Phase: 3
Location: /src/modules/logic/document_processing_service_lg/
"""

# Standard library imports
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError, ErrorSeverity
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager

# Document processing imports
from src.modules.logic.document_ingestion_lg.format_detector_lg.format_detector_lg import FormatDetector
from src.modules.logic.document_ingestion_lg.file_validator_lg.file_validator_lg import FileValidator
from src.modules.logic.document_ingestion_lg.batch_processor_lg.batch_processor_lg import BatchProcessor

from src.modules.logic.document_extraction_lg.pdf_extractor_lg.pdf_extractor_lg import PDFExtractor
from src.modules.logic.document_extraction_lg.docx_extractor_lg.docx_extractor_lg import DOCXExtractor
from src.modules.logic.document_extraction_lg.html_extractor_lg.html_extractor_lg import HTMLExtractor
from src.modules.logic.document_extraction_lg.markdown_extractor_lg.markdown_extractor_lg import MarkdownExtractor
from src.modules.logic.document_extraction_lg.ocr_processor_lg.ocr_processor_lg import OCRProcessor

from src.modules.logic.document_chunking_lg.semantic_chunker_lg.semantic_chunker_lg import SemanticChunker
from src.modules.logic.document_chunking_lg.overlap_manager_lg.overlap_manager_lg import OverlapManager
from src.modules.logic.document_chunking_lg.chunk_validator_lg.chunk_validator_lg import ChunkValidator

from src.modules.logic.document_quality_lg.content_analyzer_lg.content_analyzer_lg import ContentAnalyzer
from src.modules.logic.document_quality_lg.deduplication_engine_lg.deduplication_engine_lg import DeduplicationEngine
from src.modules.logic.document_quality_lg.quality_scorer_lg.quality_scorer_lg import QualityScorer

from src.modules.logic.document_metadata_lg.metadata_extractor_lg.metadata_extractor_lg import MetadataExtractor
from src.modules.logic.document_metadata_lg.structure_analyzer_lg.structure_analyzer_lg import StructureAnalyzer

# Database imports
from src.modules.database.documents_db.document_repository_db.document_repository_db import DocumentRepositoryDB
from src.modules.database.documents_db.document_chunks_db.document_chunks_db import DocumentChunksDB
from src.modules.database.documents_db.extraction_results_db.extraction_results_db import ExtractionResultsDB
from src.modules.database.document_queue_db.processing_queue_db.processing_queue_db import ProcessingQueueDB
from src.modules.database.document_quality_db.quality_metrics_db.quality_metrics_db import QualityMetricsDB


class ProcessingStage(Enum):
    """Document processing pipeline stages."""
    QUEUED = "queued"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingPriority(Enum):
    """Document processing priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ProcessingConfig:
    """Configuration for document processing service."""
    max_concurrent_documents: int = 5
    max_file_size_mb: int = 100
    supported_formats: List[str] = field(default_factory=lambda: ['.pdf', '.docx', '.html', '.md', '.txt'])
    enable_ocr: bool = True
    enable_quality_analysis: bool = True
    enable_deduplication: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 50
    quality_threshold: float = 0.7
    max_retries: int = 3
    processing_timeout_seconds: int = 300


@dataclass
class ProcessingJob:
    """Document processing job information."""
    job_id: str
    file_path: Path
    priority: ProcessingPriority
    stage: ProcessingStage
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Document processing result."""
    job_id: str
    success: bool
    document_id: Optional[str] = None
    chunks_created: int = 0
    quality_score: float = 0.0
    processing_time: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentProcessingService:
    """
    Orchestrates complete document processing pipeline.
    
    This service coordinates all Phase 3 modules to provide:
    - Document ingestion and validation
    - Multi-format content extraction
    - Semantic chunking with overlap management
    - Quality analysis and scoring
    - Metadata extraction and structure analysis
    - Deduplication and content optimization
    - Database persistence and indexing
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None, 
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the document processing service."""
        self.config = config or ProcessingConfig()
        self.app_state_manager = app_state_manager
        self._logger = get_logger(__name__)
        
        # Processing state
        self._active_jobs: Dict[str, ProcessingJob] = {}
        self._completed_jobs: Dict[str, ProcessingJob] = {}
        self._job_callbacks: Dict[str, List[Callable]] = {}
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_documents)
        self._shutdown_requested = False
        
        # Initialize processing components
        self._initialize_components()
        
        self._logger.info("Document processing service initialized")
    
    def _initialize_components(self):
        """Initialize all document processing components."""
        try:
            # Document ingestion components
            self.format_detector = FormatDetector()
            self.file_validator = FileValidator()
            self.batch_processor = BatchProcessor()
            
            # Document extraction components
            self.pdf_extractor = PDFExtractor()
            self.docx_extractor = DOCXExtractor()
            self.html_extractor = HTMLExtractor()
            self.markdown_extractor = MarkdownExtractor()
            self.ocr_processor = OCRProcessor()
            
            # Document chunking components
            self.semantic_chunker = SemanticChunker()
            self.overlap_manager = OverlapManager()
            self.chunk_validator = ChunkValidator()
            
            # Document quality components
            self.content_analyzer = ContentAnalyzer()
            self.deduplication_engine = DeduplicationEngine()
            self.quality_scorer = QualityScorer()
            
            # Document metadata components
            self.metadata_extractor = MetadataExtractor()
            self.structure_analyzer = StructureAnalyzer()
            
            # Database components
            self.document_repository = DocumentRepositoryDB()
            self.document_chunks_db = DocumentChunksDB()
            self.extraction_results_db = ExtractionResultsDB()
            self.processing_queue_db = ProcessingQueueDB()
            self.quality_metrics_db = QualityMetricsDB()
            
            self._logger.info("All document processing components initialized")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize processing components: {e}")
            raise
    
    async def process_document(self, file_path: Union[str, Path], 
                             priority: ProcessingPriority = ProcessingPriority.NORMAL,
                             callback: Optional[Callable] = None) -> str:
        """
        Process a single document through the complete pipeline.
        
        Args:
            file_path: Path to the document file
            priority: Processing priority level
            callback: Optional callback function for progress updates
            
        Returns:
            Job ID for tracking processing status
        """
        try:
            # Create processing job
            job_id = str(uuid.uuid4())
            file_path = Path(file_path)
            
            job = ProcessingJob(
                job_id=job_id,
                file_path=file_path,
                priority=priority,
                stage=ProcessingStage.QUEUED,
                created_at=datetime.now(timezone.utc)
            )
            
            self._active_jobs[job_id] = job
            
            if callback:
                if job_id not in self._job_callbacks:
                    self._job_callbacks[job_id] = []
                self._job_callbacks[job_id].append(callback)
            
            # Submit job for processing
            future = self._executor.submit(self._process_document_sync, job)
            
            self._logger.info(f"Document processing job created: {job_id}")
            return job_id
            
        except Exception as e:
            self._logger.error(f"Failed to create processing job: {e}")
            raise
    
    def _process_document_sync(self, job: ProcessingJob) -> ProcessingResult:
        """
        Synchronous document processing pipeline.
        
        Args:
            job: Processing job information
            
        Returns:
            Processing result
        """
        start_time = datetime.now(timezone.utc)
        job.started_at = start_time
        
        try:
            self._logger.info(f"Starting document processing: {job.job_id}")
            
            # Stage 1: Validation
            job.stage = ProcessingStage.VALIDATING
            job.progress = 10.0
            self._notify_callbacks(job)
            
            validation_result = self._validate_document(job.file_path)
            if not validation_result.success:
                raise Exception(f"Document validation failed: {validation_result.error_message}")
            
            # Stage 2: Extraction
            job.stage = ProcessingStage.EXTRACTING
            job.progress = 30.0
            self._notify_callbacks(job)
            
            extraction_result = self._extract_content(job.file_path)
            if not extraction_result.success:
                raise Exception(f"Content extraction failed: {extraction_result.error_message}")
            
            # Stage 3: Chunking
            job.stage = ProcessingStage.CHUNKING
            job.progress = 60.0
            self._notify_callbacks(job)
            
            chunking_result = self._chunk_content(extraction_result.content)
            if not chunking_result.success:
                raise Exception(f"Content chunking failed: {chunking_result.error_message}")
            
            # Stage 4: Quality Analysis
            job.stage = ProcessingStage.ANALYZING
            job.progress = 80.0
            self._notify_callbacks(job)
            
            quality_result = self._analyze_quality(extraction_result.content, chunking_result.chunks)
            
            # Stage 5: Database Storage
            job.progress = 90.0
            self._notify_callbacks(job)
            
            document_id = self._store_results(job, extraction_result, chunking_result, quality_result)
            
            # Complete processing
            job.stage = ProcessingStage.COMPLETED
            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            self._notify_callbacks(job)
            
            processing_time = (job.completed_at - start_time).total_seconds()
            
            result = ProcessingResult(
                job_id=job.job_id,
                success=True,
                document_id=document_id,
                chunks_created=len(chunking_result.chunks),
                quality_score=quality_result.overall_score,
                processing_time=processing_time
            )
            
            self._completed_jobs[job.job_id] = job
            if job.job_id in self._active_jobs:
                del self._active_jobs[job.job_id]
            
            self._logger.info(f"Document processing completed: {job.job_id} ({processing_time:.2f}s)")
            return result
            
        except Exception as e:
            job.stage = ProcessingStage.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            self._notify_callbacks(job)
            
            processing_time = (job.completed_at - start_time).total_seconds()
            
            result = ProcessingResult(
                job_id=job.job_id,
                success=False,
                error_message=str(e),
                processing_time=processing_time
            )
            
            self._completed_jobs[job.job_id] = job
            if job.job_id in self._active_jobs:
                del self._active_jobs[job.job_id]
            
            self._logger.error(f"Document processing failed: {job.job_id}: {e}")
            return result

    def _validate_document(self, file_path: Path) -> Any:
        """Validate document file."""
        try:
            # Use format detector to identify file type
            format_result = self.format_detector.detect_format(file_path)

            # Use file validator to check file integrity
            validation_result = self.file_validator.validate_file(file_path)

            return validation_result

        except Exception as e:
            self._logger.error(f"Document validation failed: {e}")
            raise

    def _extract_content(self, file_path: Path) -> Any:
        """Extract content from document."""
        try:
            # Determine file format
            format_result = self.format_detector.detect_format(file_path)

            # Route to appropriate extractor
            if format_result.format == 'pdf':
                return self.pdf_extractor.extract_content(file_path)
            elif format_result.format == 'docx':
                return self.docx_extractor.extract_content(file_path)
            elif format_result.format == 'html':
                return self.html_extractor.extract_content(file_path)
            elif format_result.format == 'markdown':
                return self.markdown_extractor.extract_content(file_path)
            else:
                # Use OCR for images or unknown formats
                return self.ocr_processor.process_document(file_path)

        except Exception as e:
            self._logger.error(f"Content extraction failed: {e}")
            raise

    def _chunk_content(self, content: str) -> Any:
        """Chunk document content."""
        try:
            # Create chunk configuration
            from src.modules.logic.document_chunking_lg.base_interfaces import ChunkConfig

            chunk_config = ChunkConfig(
                target_chunk_size=self.config.chunk_size,
                overlap_size=self.config.chunk_overlap
            )

            # Perform semantic chunking
            chunks = self.semantic_chunker.chunk_document(content, chunk_config)

            # Apply overlap management
            overlapped_chunks = self.overlap_manager.calculate_overlap(chunks, chunk_config)

            # Validate chunks
            for chunk in overlapped_chunks:
                validation_result = self.chunk_validator.validate_chunk(chunk)
                if not validation_result.is_valid:
                    self._logger.warning(f"Chunk validation issues: {validation_result.errors}")

            return type('ChunkingResult', (), {
                'success': True,
                'chunks': overlapped_chunks,
                'error_message': None
            })()

        except Exception as e:
            self._logger.error(f"Content chunking failed: {e}")
            return type('ChunkingResult', (), {
                'success': False,
                'chunks': [],
                'error_message': str(e)
            })()

    def _analyze_quality(self, content: str, chunks: List) -> Any:
        """Analyze document and chunk quality."""
        try:
            # Analyze content quality
            content_analysis = self.content_analyzer.analyze_content(content)

            # Calculate quality score
            quality_score = self.quality_scorer.calculate_quality_score(content)

            # Check for duplicates if enabled
            duplicate_result = None
            if self.config.enable_deduplication:
                duplicate_result = self.deduplication_engine.check_duplicates(content)

            return type('QualityResult', (), {
                'success': True,
                'overall_score': quality_score.overall_score,
                'content_analysis': content_analysis,
                'duplicate_result': duplicate_result,
                'error_message': None
            })()

        except Exception as e:
            self._logger.error(f"Quality analysis failed: {e}")
            return type('QualityResult', (), {
                'success': False,
                'overall_score': 0.0,
                'error_message': str(e)
            })()

    def _store_results(self, job: ProcessingJob, extraction_result: Any,
                      chunking_result: Any, quality_result: Any) -> str:
        """Store processing results in database."""
        try:
            # Store document in repository
            document_id = str(uuid.uuid4())

            # Store document metadata
            document_data = {
                'document_id': document_id,
                'file_path': str(job.file_path),
                'file_name': job.file_path.name,
                'file_size': job.file_path.stat().st_size,
                'content': extraction_result.content,
                'quality_score': quality_result.overall_score,
                'chunk_count': len(chunking_result.chunks),
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            self.document_repository.store_document(document_data)

            # Store chunks
            for chunk in chunking_result.chunks:
                chunk.document_id = document_id
                self.document_chunks_db.store_chunk(chunk)

            # Store extraction results
            self.extraction_results_db.store_extraction_result({
                'document_id': document_id,
                'extraction_metadata': extraction_result.metadata,
                'extraction_time': datetime.now(timezone.utc).isoformat()
            })

            # Store quality metrics
            self.quality_metrics_db.store_quality_metrics({
                'document_id': document_id,
                'quality_score': quality_result.overall_score,
                'content_analysis': quality_result.content_analysis,
                'analysis_time': datetime.now(timezone.utc).isoformat()
            })

            return document_id

        except Exception as e:
            self._logger.error(f"Failed to store processing results: {e}")
            raise

    def _notify_callbacks(self, job: ProcessingJob):
        """Notify registered callbacks of job progress."""
        if job.job_id in self._job_callbacks:
            for callback in self._job_callbacks[job.job_id]:
                try:
                    callback(job)
                except Exception as e:
                    self._logger.warning(f"Callback notification failed: {e}")

    def get_job_status(self, job_id: str) -> Optional[ProcessingJob]:
        """Get status of a processing job."""
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]
        elif job_id in self._completed_jobs:
            return self._completed_jobs[job_id]
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a processing job."""
        if job_id in self._active_jobs:
            job = self._active_jobs[job_id]
            job.stage = ProcessingStage.FAILED
            job.error_message = "Job cancelled by user"
            job.completed_at = datetime.now(timezone.utc)

            self._completed_jobs[job_id] = job
            del self._active_jobs[job_id]

            self._logger.info(f"Processing job cancelled: {job_id}")
            return True
        return False

    def get_active_jobs(self) -> List[ProcessingJob]:
        """Get list of active processing jobs."""
        return list(self._active_jobs.values())

    def get_completed_jobs(self) -> List[ProcessingJob]:
        """Get list of completed processing jobs."""
        return list(self._completed_jobs.values())

    async def shutdown(self):
        """Shutdown the document processing service."""
        self._shutdown_requested = True
        self._logger.info("Shutting down document processing service...")

        # Wait for active jobs to complete or timeout
        if self._active_jobs:
            self._logger.info(f"Waiting for {len(self._active_jobs)} active jobs to complete...")
            # In a real implementation, you'd wait for jobs with a timeout

        # Shutdown executor
        self._executor.shutdown(wait=True)
        self._logger.info("Document processing service shutdown complete")
