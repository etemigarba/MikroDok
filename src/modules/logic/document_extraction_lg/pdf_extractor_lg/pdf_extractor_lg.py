"""
Module: pdf_extractor_lg
Description: Extracts text, tables, and metadata from PDF documents using PDFPlumber integration
Phase: 3
Location: /src/modules/logic/document_extraction_lg/pdf_extractor_lg/pdf_extractor_lg.py
"""

# Standard library imports
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

# Third-party imports
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_ingestion_lg.format_detector_lg import DocumentFormat
from ..base_interfaces import (
    IDocumentExtractor,
    ExtractionResult,
    ExtractionMetadata,
    QualityMetrics,
    ExtractionStatus,
    TableData,
    ImageData,
    DocumentStructure
)


@dataclass
class PDFExtractionConfig:
    """Configuration for PDF extraction."""
    extract_text: bool = True
    extract_tables: bool = True
    extract_images: bool = True
    extract_metadata: bool = True
    extract_annotations: bool = False
    extract_form_fields: bool = False
    table_detection_strategy: str = "lattice"  # "lattice", "stream", "auto"
    image_min_size: Tuple[int, int] = (50, 50)  # Minimum image size (width, height)
    text_extraction_method: str = "layout"  # "layout", "simple"
    preserve_layout: bool = True
    merge_rotated_text: bool = True
    password: Optional[str] = None
    max_pages: Optional[int] = None
    page_range: Optional[Tuple[int, int]] = None
    quality_threshold: float = 0.5
    timeout_seconds: int = 300


class PDFTableExtractor:
    """Specialized table extractor for PDF documents."""
    
    def __init__(self, config: PDFExtractionConfig):
        """Initialize table extractor."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def extract_tables(self, page, page_number: int) -> List[TableData]:
        """Extract tables from a PDF page."""
        tables = []
        
        try:
            # Extract tables using specified strategy
            if self._config.table_detection_strategy == "lattice":
                page_tables = page.extract_tables(table_settings={"vertical_strategy": "lines"})
            elif self._config.table_detection_strategy == "stream":
                page_tables = page.extract_tables(table_settings={"vertical_strategy": "text"})
            else:  # auto
                # Try lattice first, fall back to stream
                page_tables = page.extract_tables()
                if not page_tables:
                    page_tables = page.extract_tables(table_settings={"vertical_strategy": "text"})
            
            for i, table in enumerate(page_tables or []):
                if not table or len(table) < 2:  # Skip empty or single-row tables
                    continue
                
                # Clean and process table data
                cleaned_table = self._clean_table_data(table)
                if not cleaned_table:
                    continue
                
                # Extract headers and rows
                headers = cleaned_table[0] if cleaned_table else []
                rows = cleaned_table[1:] if len(cleaned_table) > 1 else []
                
                # Calculate confidence based on data quality
                confidence = self._calculate_table_confidence(cleaned_table)
                
                table_data = TableData(
                    headers=headers,
                    rows=rows,
                    page_number=page_number,
                    confidence=confidence,
                    metadata={
                        "table_index": i,
                        "extraction_method": self._config.table_detection_strategy,
                        "row_count": len(rows),
                        "column_count": len(headers)
                    }
                )
                tables.append(table_data)
                
        except Exception as e:
            self._logger.warning(f"Failed to extract tables from page {page_number}: {e}")
        
        return tables
    
    def _clean_table_data(self, table: List[List[str]]) -> List[List[str]]:
        """Clean and normalize table data."""
        if not table:
            return []
        
        cleaned = []
        for row in table:
            if not row:
                continue
            
            cleaned_row = []
            for cell in row:
                # Clean cell content
                if cell is None:
                    cleaned_cell = ""
                else:
                    cleaned_cell = str(cell).strip()
                    # Remove excessive whitespace
                    cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell)
                
                cleaned_row.append(cleaned_cell)
            
            # Only add non-empty rows
            if any(cell.strip() for cell in cleaned_row):
                cleaned.append(cleaned_row)
        
        return cleaned
    
    def _calculate_table_confidence(self, table: List[List[str]]) -> float:
        """Calculate confidence score for extracted table."""
        if not table:
            return 0.0
        
        total_cells = sum(len(row) for row in table)
        if total_cells == 0:
            return 0.0
        
        # Count non-empty cells
        non_empty_cells = sum(1 for row in table for cell in row if cell.strip())
        
        # Calculate fill ratio
        fill_ratio = non_empty_cells / total_cells
        
        # Bonus for consistent column count
        column_counts = [len(row) for row in table]
        consistency_bonus = 0.2 if len(set(column_counts)) == 1 else 0.0
        
        # Bonus for having headers (first row different from others)
        header_bonus = 0.1 if len(table) > 1 and table[0] != table[1] else 0.0
        
        confidence = min(1.0, fill_ratio + consistency_bonus + header_bonus)
        return confidence


class PDFImageExtractor:
    """Specialized image extractor for PDF documents."""
    
    def __init__(self, config: PDFExtractionConfig):
        """Initialize image extractor."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def extract_images(self, page, page_number: int) -> List[ImageData]:
        """Extract images from a PDF page."""
        images = []
        
        if not PIL_AVAILABLE:
            self._logger.warning("PIL not available, skipping image extraction")
            return images
        
        try:
            # Get images from page
            page_images = page.images
            
            for i, img in enumerate(page_images):
                try:
                    # Check minimum size requirements
                    width = img.get('width', 0)
                    height = img.get('height', 0)
                    
                    if (width < self._config.image_min_size[0] or 
                        height < self._config.image_min_size[1]):
                        continue
                    
                    # Extract image data
                    image_obj = page.crop(img['bbox']).to_image()
                    
                    # Convert to bytes
                    img_buffer = io.BytesIO()
                    image_obj.save(img_buffer, format='PNG')
                    image_data = img_buffer.getvalue()
                    
                    # Generate unique image ID
                    image_id = hashlib.md5(image_data).hexdigest()[:16]
                    
                    image_info = ImageData(
                        image_id=image_id,
                        image_data=image_data,
                        format='PNG',
                        width=int(width),
                        height=int(height),
                        page_number=page_number,
                        bounding_box={
                            'x0': img['x0'],
                            'y0': img['y0'],
                            'x1': img['x1'],
                            'y1': img['y1']
                        },
                        metadata={
                            'image_index': i,
                            'original_format': img.get('stream', {}).get('Filter', 'Unknown'),
                            'size_bytes': len(image_data)
                        }
                    )
                    images.append(image_info)
                    
                except Exception as e:
                    self._logger.warning(f"Failed to extract image {i} from page {page_number}: {e}")
                    continue
                    
        except Exception as e:
            self._logger.warning(f"Failed to extract images from page {page_number}: {e}")
        
        return images


class PDFExtractor(IDocumentExtractor):
    """
    PDF document extractor using PDFPlumber for comprehensive content extraction.

    Features:
    - Text extraction with layout preservation
    - Table detection and extraction
    - Image extraction and processing
    - Metadata extraction
    - Quality assessment and confidence scoring
    - Error handling for corrupted PDFs
    """

    def __init__(self, config: Optional[PDFExtractionConfig] = None):
        """Initialize PDF extractor."""
        self._config = config or PDFExtractionConfig()
        self._logger = get_logger(__name__)
        self._table_extractor = PDFTableExtractor(self._config)
        self._image_extractor = PDFImageExtractor(self._config)

        if not PDFPLUMBER_AVAILABLE:
            raise ImportError("pdfplumber is required for PDF extraction")

    def extract(self, file_path: Union[str, Path], config: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract content from PDF document.

        Args:
            file_path: Path to the PDF file
            config: Optional extraction configuration override

        Returns:
            ExtractionResult with extracted content and metadata
        """
        start_time = datetime.now()
        path_obj = Path(file_path)

        # Validate file
        validation_errors = self.validate_file(path_obj)
        if validation_errors:
            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                content="",
                metadata=self._create_metadata(path_obj, start_time, 0, 0),
                quality_metrics=QualityMetrics(overall_confidence=0.0),
                validation_errors=validation_errors
            )

        # Override config if provided
        extraction_config = self._config
        if config:
            extraction_config = self._merge_config(config)

        try:
            with pdfplumber.open(str(path_obj), password=extraction_config.password) as pdf:
                return self._extract_from_pdf(pdf, path_obj, start_time, extraction_config)

        except Exception as e:
            self._logger.error(f"PDF extraction failed for {file_path}: {e}")

            error = ValidationError(
                field_name="pdf_extraction",
                error_message=f"PDF extraction error: {str(e)}",
                severity="ERROR",
                validation_type="PROCESSING"
            )

            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                content="",
                metadata=self._create_metadata(path_obj, start_time, 0, 0),
                quality_metrics=QualityMetrics(overall_confidence=0.0),
                validation_errors=[error]
            )

    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """Check if file format is supported by this extractor."""
        path_obj = Path(file_path)
        return path_obj.suffix.lower() == '.pdf'

    def get_supported_formats(self) -> List[DocumentFormat]:
        """Get list of supported document formats."""
        return [DocumentFormat.PDF]

    def validate_file(self, file_path: Union[str, Path]) -> List[ValidationError]:
        """Validate PDF file before extraction."""
        errors = []
        path_obj = Path(file_path)

        # Check file existence
        if not path_obj.exists():
            errors.append(ValidationError(
                field_name="file_path",
                error_message=f"File does not exist: {file_path}",
                severity="ERROR",
                validation_type="CONSTRAINT"
            ))
            return errors

        # Check file extension
        if not self.is_supported_format(path_obj):
            errors.append(ValidationError(
                field_name="file_format",
                error_message=f"Unsupported file format: {path_obj.suffix}",
                severity="ERROR",
                validation_type="FORMAT"
            ))

        # Check file size (10GB limit)
        file_size = path_obj.stat().st_size
        max_size = 10 * 1024 * 1024 * 1024  # 10GB
        if file_size > max_size:
            errors.append(ValidationError(
                field_name="file_size",
                error_message=f"File size exceeds maximum limit: {file_size} bytes",
                severity="ERROR",
                validation_type="CONSTRAINT"
            ))

        # Try to open PDF to check for corruption
        if not errors:  # Only if no previous errors
            try:
                with pdfplumber.open(str(path_obj), password=self._config.password) as pdf:
                    # Try to access first page to verify PDF integrity
                    if len(pdf.pages) == 0:
                        errors.append(ValidationError(
                            field_name="pdf_content",
                            error_message="PDF contains no pages",
                            severity="ERROR",
                            validation_type="CONTENT"
                        ))
            except Exception as e:
                errors.append(ValidationError(
                    field_name="pdf_integrity",
                    error_message=f"PDF file appears to be corrupted: {str(e)}",
                    severity="ERROR",
                    validation_type="INTEGRITY"
                ))

        return errors

    def get_extraction_config_schema(self) -> Dict[str, Any]:
        """Get schema for extraction configuration."""
        return {
            "type": "object",
            "properties": {
                "extract_text": {"type": "boolean", "default": True},
                "extract_tables": {"type": "boolean", "default": True},
                "extract_images": {"type": "boolean", "default": True},
                "extract_metadata": {"type": "boolean", "default": True},
                "table_detection_strategy": {
                    "type": "string",
                    "enum": ["lattice", "stream", "auto"],
                    "default": "lattice"
                },
                "text_extraction_method": {
                    "type": "string",
                    "enum": ["layout", "simple"],
                    "default": "layout"
                },
                "preserve_layout": {"type": "boolean", "default": True},
                "password": {"type": "string"},
                "max_pages": {"type": "integer", "minimum": 1},
                "quality_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0}
            }
        }

    def estimate_processing_time(self, file_path: Union[str, Path]) -> float:
        """Estimate processing time for PDF document."""
        path_obj = Path(file_path)

        if not path_obj.exists():
            return 0.0

        try:
            with pdfplumber.open(str(path_obj), password=self._config.password) as pdf:
                page_count = len(pdf.pages)
                file_size_mb = path_obj.stat().st_size / (1024 * 1024)

                # Base time estimates (seconds per page)
                base_time_per_page = 0.5
                table_time_per_page = 1.0 if self._config.extract_tables else 0.0
                image_time_per_page = 0.3 if self._config.extract_images else 0.0

                # Size factor (larger files take longer per page)
                size_factor = min(2.0, 1.0 + (file_size_mb / 100))

                total_time = page_count * (base_time_per_page + table_time_per_page + image_time_per_page) * size_factor

                return max(1.0, total_time)  # Minimum 1 second

        except Exception:
            # Fallback estimation based on file size
            file_size_mb = path_obj.stat().st_size / (1024 * 1024)
            return max(1.0, file_size_mb * 0.1)  # 0.1 seconds per MB

    def _merge_config(self, override_config: Dict[str, Any]) -> PDFExtractionConfig:
        """Merge override configuration with default config."""
        config_dict = {
            'extract_text': override_config.get('extract_text', self._config.extract_text),
            'extract_tables': override_config.get('extract_tables', self._config.extract_tables),
            'extract_images': override_config.get('extract_images', self._config.extract_images),
            'extract_metadata': override_config.get('extract_metadata', self._config.extract_metadata),
            'table_detection_strategy': override_config.get('table_detection_strategy', self._config.table_detection_strategy),
            'text_extraction_method': override_config.get('text_extraction_method', self._config.text_extraction_method),
            'preserve_layout': override_config.get('preserve_layout', self._config.preserve_layout),
            'password': override_config.get('password', self._config.password),
            'max_pages': override_config.get('max_pages', self._config.max_pages),
            'page_range': override_config.get('page_range', self._config.page_range),
            'quality_threshold': override_config.get('quality_threshold', self._config.quality_threshold)
        }

        return PDFExtractionConfig(**config_dict)

    def _extract_from_pdf(self, pdf, path_obj: Path, start_time: datetime,
                         config: PDFExtractionConfig) -> ExtractionResult:
        """Extract content from opened PDF."""
        all_text = []
        all_tables = []
        all_images = []
        all_hyperlinks = []
        pages_processed = 0
        total_pages = len(pdf.pages)

        # Determine page range
        start_page = 0
        end_page = total_pages

        if config.page_range:
            start_page = max(0, config.page_range[0] - 1)  # Convert to 0-based
            end_page = min(total_pages, config.page_range[1])

        if config.max_pages:
            end_page = min(end_page, start_page + config.max_pages)

        # Process pages
        for page_num in range(start_page, end_page):
            try:
                page = pdf.pages[page_num]
                page_number = page_num + 1  # Convert back to 1-based

                # Extract text
                if config.extract_text:
                    page_text = self._extract_page_text(page, config)
                    if page_text.strip():
                        all_text.append(f"[Page {page_number}]\n{page_text}\n")

                # Extract tables
                if config.extract_tables:
                    page_tables = self._table_extractor.extract_tables(page, page_number)
                    all_tables.extend(page_tables)

                # Extract images
                if config.extract_images:
                    page_images = self._image_extractor.extract_images(page, page_number)
                    all_images.extend(page_images)

                # Extract hyperlinks
                if hasattr(page, 'hyperlinks'):
                    page_links = self._extract_hyperlinks(page, page_number)
                    all_hyperlinks.extend(page_links)

                pages_processed += 1

            except Exception as e:
                self._logger.warning(f"Failed to process page {page_number}: {e}")
                continue

        # Combine text content
        content = "\n".join(all_text)

        # Extract document metadata
        doc_metadata = self._extract_document_metadata(pdf) if config.extract_metadata else {}

        # Create document structure
        structure = self._analyze_document_structure(content, all_tables, total_pages)

        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(
            content, all_tables, all_images, pages_processed, total_pages, start_time
        )

        # Create extraction metadata
        extraction_metadata = self._create_metadata(
            path_obj, start_time, pages_processed, total_pages, doc_metadata, config
        )

        # Determine status
        status = self._determine_extraction_status(quality_metrics, pages_processed, total_pages)

        return ExtractionResult(
            status=status,
            content=content,
            metadata=extraction_metadata,
            quality_metrics=quality_metrics,
            document_structure=structure,
            tables=all_tables,
            images=all_images,
            hyperlinks=all_hyperlinks
        )

    def _extract_page_text(self, page, config: PDFExtractionConfig) -> str:
        """Extract text from a PDF page."""
        try:
            if config.text_extraction_method == "layout":
                # Extract text with layout preservation
                text = page.extract_text(layout=config.preserve_layout)
            else:
                # Simple text extraction
                text = page.extract_text()

            if text:
                # Clean up text
                text = re.sub(r'\s+', ' ', text.strip())
                return text

        except Exception as e:
            self._logger.warning(f"Failed to extract text from page: {e}")

        return ""

    def _extract_hyperlinks(self, page, page_number: int) -> List[Dict[str, str]]:
        """Extract hyperlinks from a PDF page."""
        links = []

        try:
            # Extract annotations that are links
            if hasattr(page, 'annots'):
                for annot in page.annots:
                    if annot.get('Subtype') == 'Link' and 'uri' in annot:
                        links.append({
                            'url': annot['uri'],
                            'page_number': str(page_number),
                            'text': annot.get('contents', ''),
                            'type': 'external'
                        })
        except Exception as e:
            self._logger.warning(f"Failed to extract hyperlinks from page {page_number}: {e}")

        return links

    def _extract_document_metadata(self, pdf) -> Dict[str, Any]:
        """Extract metadata from PDF document."""
        metadata = {}

        try:
            if hasattr(pdf, 'metadata') and pdf.metadata:
                # Standard PDF metadata
                for key, value in pdf.metadata.items():
                    if value:
                        metadata[key.lower().replace('/', '')] = str(value)

            # Additional document properties
            metadata.update({
                'page_count': len(pdf.pages),
                'pdf_version': getattr(pdf, 'pdf_version', 'Unknown'),
                'encrypted': getattr(pdf, 'is_encrypted', False)
            })

        except Exception as e:
            self._logger.warning(f"Failed to extract PDF metadata: {e}")

        return metadata

    def _analyze_document_structure(self, content: str, tables: List[TableData],
                                  total_pages: int) -> DocumentStructure:
        """Analyze document structure from extracted content."""
        structure = DocumentStructure()

        try:
            # Basic statistics
            structure.page_count = total_pages
            structure.word_count = len(content.split()) if content else 0
            structure.character_count = len(content) if content else 0

            # Extract headings (simple heuristic based on formatting)
            headings = []
            lines = content.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                if line and (line.isupper() or line.endswith(':') or
                           (len(line) < 100 and not line.endswith('.'))):
                    headings.append({
                        'text': line,
                        'level': 1,  # Simple level detection
                        'line_number': i + 1
                    })

            structure.headings = headings[:20]  # Limit to first 20 headings

            # Create sections based on page breaks
            sections = []
            page_texts = content.split('[Page ')
            for i, page_text in enumerate(page_texts[1:], 1):  # Skip first empty split
                if page_text.strip():
                    sections.append({
                        'title': f'Page {i}',
                        'content_length': len(page_text),
                        'page_number': i
                    })

            structure.sections = sections

        except Exception as e:
            self._logger.warning(f"Failed to analyze document structure: {e}")

        return structure

    def _calculate_quality_metrics(self, content: str, tables: List[TableData],
                                 images: List[ImageData], pages_processed: int,
                                 total_pages: int, start_time: datetime) -> QualityMetrics:
        """Calculate quality metrics for extraction."""
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Text confidence based on content length and readability
        text_confidence = 0.0
        if content:
            # Basic heuristics for text quality
            word_count = len(content.split())
            char_count = len(content)

            if word_count > 0:
                avg_word_length = char_count / word_count
                text_confidence = min(1.0, max(0.3, (avg_word_length - 2) / 8))

        # Table confidence (average of all table confidences)
        table_confidence = 0.0
        if tables:
            table_confidence = sum(table.confidence for table in tables) / len(tables)

        # Image confidence (simple presence check)
        image_confidence = 1.0 if images else 0.0

        # Structure confidence based on content organization
        structure_confidence = 0.8 if content and len(content.split('\n')) > 5 else 0.3

        # Overall confidence (weighted average)
        overall_confidence = (
            text_confidence * 0.5 +
            table_confidence * 0.2 +
            image_confidence * 0.1 +
            structure_confidence * 0.2
        )

        # Completeness score
        completeness_score = (pages_processed / total_pages) * 100 if total_pages > 0 else 0.0

        # Readability score (simple heuristic)
        readability_score = min(100.0, text_confidence * 100) if content else 0.0

        return QualityMetrics(
            overall_confidence=overall_confidence,
            text_confidence=text_confidence,
            structure_confidence=structure_confidence,
            table_confidence=table_confidence,
            image_confidence=image_confidence,
            completeness_score=completeness_score,
            readability_score=readability_score,
            processing_time_ms=processing_time
        )

    def _create_metadata(self, path_obj: Path, start_time: datetime,
                        pages_processed: int, total_pages: int,
                        doc_metadata: Optional[Dict[str, Any]] = None,
                        config: Optional[PDFExtractionConfig] = None) -> ExtractionMetadata:
        """Create extraction metadata."""
        processing_duration = (datetime.now() - start_time).total_seconds() * 1000

        return ExtractionMetadata(
            document_format=DocumentFormat.PDF,
            file_size=path_obj.stat().st_size,
            extraction_timestamp=start_time,
            extractor_version="1.0.0",
            processing_duration_ms=processing_duration,
            pages_processed=pages_processed,
            total_pages=total_pages,
            extraction_config={
                'extract_text': config.extract_text if config else True,
                'extract_tables': config.extract_tables if config else True,
                'extract_images': config.extract_images if config else True,
                'table_detection_strategy': config.table_detection_strategy if config else 'lattice'
            },
            document_properties=doc_metadata or {},
            technical_metadata={
                'pdfplumber_available': PDFPLUMBER_AVAILABLE,
                'pil_available': PIL_AVAILABLE,
                'file_extension': path_obj.suffix.lower()
            }
        )

    def _determine_extraction_status(self, quality_metrics: QualityMetrics,
                                   pages_processed: int, total_pages: int) -> ExtractionStatus:
        """Determine extraction status based on quality metrics."""
        if pages_processed == 0:
            return ExtractionStatus.FAILED

        if quality_metrics.overall_confidence >= self._config.quality_threshold:
            if pages_processed == total_pages:
                return ExtractionStatus.SUCCESS
            else:
                return ExtractionStatus.PARTIAL_SUCCESS
        else:
            if pages_processed == total_pages:
                return ExtractionStatus.PARTIAL_SUCCESS
            else:
                return ExtractionStatus.FAILED
