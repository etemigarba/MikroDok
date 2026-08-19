"""
Module: format_detector_lg
Description: Identifies document format through file extension and magic number verification, routes to appropriate processor
Phase: 3
Location: /src/modules/logic/document_ingestion_lg/format_detector_lg/
"""

# Standard library imports
import os
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Third-party imports
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

# Local imports
from src.modules.logic.error_handling_lg import ValidationError, ValidationResult
from src.modules.logic.logging_infrastructure_lg import get_logger


class DocumentFormat(Enum):
    """Supported document formats."""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    HTML = "html"
    HTM = "htm"
    MARKDOWN = "md"
    RTF = "rtf"
    ODT = "odt"
    UNKNOWN = "unknown"


class ProcessorType(Enum):
    """Document processor types."""
    PDF_PROCESSOR = "pdf_processor"
    DOCX_PROCESSOR = "docx_processor"
    HTML_PROCESSOR = "html_processor"
    MARKDOWN_PROCESSOR = "markdown_processor"
    TEXT_PROCESSOR = "text_processor"
    RTF_PROCESSOR = "rtf_processor"
    ODT_PROCESSOR = "odt_processor"
    UNKNOWN_PROCESSOR = "unknown_processor"


@dataclass
class FormatDetectionResult:
    """Result of document format detection."""
    format_type: DocumentFormat
    processor_type: ProcessorType
    confidence: float  # 0.0 to 1.0
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    magic_signature: Optional[str] = None
    validation_errors: Optional[List[ValidationError]] = None
    
    @property
    def is_valid(self) -> bool:
        """Check if detection result is valid."""
        return (self.format_type != DocumentFormat.UNKNOWN and 
                self.processor_type != ProcessorType.UNKNOWN_PROCESSOR and
                self.confidence > 0.5)
    
    @property
    def is_supported(self) -> bool:
        """Check if format is supported for processing."""
        supported_formats = {
            DocumentFormat.PDF,
            DocumentFormat.DOCX,
            DocumentFormat.DOC,
            DocumentFormat.TXT,
            DocumentFormat.HTML,
            DocumentFormat.HTM,
            DocumentFormat.MARKDOWN
        }
        return self.format_type in supported_formats


class IFormatDetector(ABC):
    """Interface for document format detectors."""
    
    @abstractmethod
    def detect_format(self, file_path: Union[str, Path]) -> FormatDetectionResult:
        """
        Detect document format from file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            FormatDetectionResult with detection details
        """
        pass
    
    @abstractmethod
    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """
        Check if file format is supported.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            True if format is supported, False otherwise
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[DocumentFormat]:
        """
        Get list of supported document formats.
        
        Returns:
            List of supported DocumentFormat enums
        """
        pass
    
    @abstractmethod
    def get_processor_for_format(self, format_type: DocumentFormat) -> ProcessorType:
        """
        Get appropriate processor for document format.
        
        Args:
            format_type: Document format
            
        Returns:
            ProcessorType for handling the format
        """
        pass


class FormatDetector(IFormatDetector):
    """
    Document format detector using file extension and magic number verification.
    
    This class identifies document formats through multiple detection methods:
    1. File extension analysis
    2. Magic number verification (if python-magic is available)
    3. MIME type detection
    4. Content-based heuristics
    """
    
    def __init__(self):
        """Initialize the format detector."""
        self._logger = get_logger(__name__)
        
        # Magic number signatures for common document formats
        self._magic_signatures = {
            b'%PDF': DocumentFormat.PDF,
            b'PK\x03\x04': DocumentFormat.DOCX,  # Also ZIP-based formats
            b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': DocumentFormat.DOC,  # OLE2 format
            b'<!DOCTYPE html': DocumentFormat.HTML,
            b'<html': DocumentFormat.HTML,
            b'<HTML': DocumentFormat.HTML,
            b'{\\rtf': DocumentFormat.RTF,
        }
        
        # File extension to format mapping
        self._extension_mapping = {
            '.pdf': DocumentFormat.PDF,
            '.docx': DocumentFormat.DOCX,
            '.doc': DocumentFormat.DOC,
            '.txt': DocumentFormat.TXT,
            '.text': DocumentFormat.TXT,
            '.html': DocumentFormat.HTML,
            '.htm': DocumentFormat.HTM,
            '.md': DocumentFormat.MARKDOWN,
            '.markdown': DocumentFormat.MARKDOWN,
            '.rtf': DocumentFormat.RTF,
            '.odt': DocumentFormat.ODT,
        }
        
        # Format to processor mapping
        self._processor_mapping = {
            DocumentFormat.PDF: ProcessorType.PDF_PROCESSOR,
            DocumentFormat.DOCX: ProcessorType.DOCX_PROCESSOR,
            DocumentFormat.DOC: ProcessorType.DOCX_PROCESSOR,  # Use DOCX processor for DOC
            DocumentFormat.TXT: ProcessorType.TEXT_PROCESSOR,
            DocumentFormat.HTML: ProcessorType.HTML_PROCESSOR,
            DocumentFormat.HTM: ProcessorType.HTML_PROCESSOR,
            DocumentFormat.MARKDOWN: ProcessorType.MARKDOWN_PROCESSOR,
            DocumentFormat.RTF: ProcessorType.RTF_PROCESSOR,
            DocumentFormat.ODT: ProcessorType.ODT_PROCESSOR,
            DocumentFormat.UNKNOWN: ProcessorType.UNKNOWN_PROCESSOR,
        }
        
        # Supported formats for processing
        self._supported_formats = {
            DocumentFormat.PDF,
            DocumentFormat.DOCX,
            DocumentFormat.DOC,
            DocumentFormat.TXT,
            DocumentFormat.HTML,
            DocumentFormat.HTM,
            DocumentFormat.MARKDOWN
        }
        
        # Initialize magic detector if available
        self._magic_detector = None
        if MAGIC_AVAILABLE:
            try:
                self._magic_detector = magic.Magic(mime=True)
                self._logger.info("Magic number detection initialized successfully")
            except Exception as e:
                self._logger.warning(f"Failed to initialize magic detector: {e}")
                self._magic_detector = None
        else:
            self._logger.warning("python-magic not available, using fallback detection")

    def detect_format(self, file_path: Union[str, Path]) -> FormatDetectionResult:
        """
        Detect document format from file using multiple detection methods.

        Args:
            file_path: Path to the document file

        Returns:
            FormatDetectionResult with detection details
        """
        path_obj = Path(file_path)
        validation_errors = []

        try:
            # Validate file exists
            if not path_obj.exists():
                error = ValidationError(
                    field_name="file_path",
                    error_message=f"File does not exist: {file_path}",
                    severity="ERROR",
                    validation_type="CONSTRAINT",
                    actual_value=str(file_path)
                )
                validation_errors.append(error)
                return FormatDetectionResult(
                    format_type=DocumentFormat.UNKNOWN,
                    processor_type=ProcessorType.UNKNOWN_PROCESSOR,
                    confidence=0.0,
                    validation_errors=validation_errors
                )

            # Get file size
            file_size = path_obj.stat().st_size

            # Check file size limit (10GB)
            max_size = 10 * 1024 * 1024 * 1024  # 10GB in bytes
            if file_size > max_size:
                error = ValidationError(
                    field_name="file_size",
                    error_message=f"File size exceeds maximum limit of 10GB: {file_size} bytes",
                    severity="ERROR",
                    validation_type="CONSTRAINT",
                    expected_value=max_size,
                    actual_value=file_size
                )
                validation_errors.append(error)

            # Detect format using multiple methods
            extension_result = self._detect_by_extension(path_obj)
            magic_result = self._detect_by_magic_number(path_obj)
            mime_result = self._detect_by_mime_type(path_obj)

            # Combine results and calculate confidence
            final_format, confidence = self._combine_detection_results(
                extension_result, magic_result, mime_result
            )

            # Get processor type
            processor_type = self.get_processor_for_format(final_format)

            # Get MIME type
            mime_type = mime_result.get('mime_type') if mime_result else None

            # Get magic signature
            magic_signature = magic_result.get('signature') if magic_result else None

            self._logger.info(
                f"Format detection completed for {file_path}: "
                f"format={final_format.value}, confidence={confidence:.2f}"
            )

            return FormatDetectionResult(
                format_type=final_format,
                processor_type=processor_type,
                confidence=confidence,
                mime_type=mime_type,
                file_size=file_size,
                magic_signature=magic_signature,
                validation_errors=validation_errors if validation_errors else None
            )

        except Exception as e:
            self._logger.error(f"Format detection failed for {file_path}: {e}")
            error = ValidationError(
                field_name="format_detection",
                error_message=f"Format detection error: {str(e)}",
                severity="ERROR",
                validation_type="PROCESSING"
            )
            validation_errors.append(error)

            return FormatDetectionResult(
                format_type=DocumentFormat.UNKNOWN,
                processor_type=ProcessorType.UNKNOWN_PROCESSOR,
                confidence=0.0,
                validation_errors=validation_errors
            )

    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """
        Check if file format is supported for processing.

        Args:
            file_path: Path to the document file

        Returns:
            True if format is supported, False otherwise
        """
        try:
            result = self.detect_format(file_path)
            return result.is_supported
        except Exception as e:
            self._logger.error(f"Error checking format support for {file_path}: {e}")
            return False

    def get_supported_formats(self) -> List[DocumentFormat]:
        """
        Get list of supported document formats.

        Returns:
            List of supported DocumentFormat enums
        """
        return list(self._supported_formats)

    def get_processor_for_format(self, format_type: DocumentFormat) -> ProcessorType:
        """
        Get appropriate processor for document format.

        Args:
            format_type: Document format

        Returns:
            ProcessorType for handling the format
        """
        return self._processor_mapping.get(format_type, ProcessorType.UNKNOWN_PROCESSOR)

    def _detect_by_extension(self, file_path: Path) -> Optional[Dict]:
        """
        Detect format by file extension.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with detection result or None
        """
        try:
            extension = file_path.suffix.lower()
            format_type = self._extension_mapping.get(extension, DocumentFormat.UNKNOWN)

            if format_type != DocumentFormat.UNKNOWN:
                return {
                    'format': format_type,
                    'confidence': 0.7,  # Medium confidence for extension-based detection
                    'method': 'extension'
                }

            return None

        except Exception as e:
            self._logger.error(f"Extension detection failed for {file_path}: {e}")
            return None

    def _detect_by_magic_number(self, file_path: Path) -> Optional[Dict]:
        """
        Detect format by magic number (file signature).

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with detection result or None
        """
        try:
            # Read first 1024 bytes for magic number detection
            with open(file_path, 'rb') as f:
                header = f.read(1024)

            # Check against known magic signatures
            for signature, format_type in self._magic_signatures.items():
                if header.startswith(signature):
                    return {
                        'format': format_type,
                        'confidence': 0.9,  # High confidence for magic number detection
                        'method': 'magic_number',
                        'signature': signature.hex()
                    }

            # Special handling for ZIP-based formats (DOCX, ODT)
            if header.startswith(b'PK\x03\x04'):
                # Try to determine if it's DOCX or ODT by checking internal structure
                format_type = self._detect_zip_based_format(file_path)
                if format_type != DocumentFormat.UNKNOWN:
                    return {
                        'format': format_type,
                        'confidence': 0.8,
                        'method': 'magic_number_zip',
                        'signature': header[:4].hex()
                    }

            return None

        except Exception as e:
            self._logger.error(f"Magic number detection failed for {file_path}: {e}")
            return None

    def _detect_by_mime_type(self, file_path: Path) -> Optional[Dict]:
        """
        Detect format by MIME type.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with detection result or None
        """
        try:
            # Use mimetypes module
            mime_type, _ = mimetypes.guess_type(str(file_path))

            # Use python-magic if available
            if self._magic_detector:
                try:
                    magic_mime = self._magic_detector.from_file(str(file_path))
                    if magic_mime:
                        mime_type = magic_mime
                except Exception as e:
                    self._logger.warning(f"Magic MIME detection failed: {e}")

            if mime_type:
                format_type = self._mime_to_format(mime_type)
                if format_type != DocumentFormat.UNKNOWN:
                    return {
                        'format': format_type,
                        'confidence': 0.6,  # Lower confidence for MIME type detection
                        'method': 'mime_type',
                        'mime_type': mime_type
                    }

            return None

        except Exception as e:
            self._logger.error(f"MIME type detection failed for {file_path}: {e}")
            return None

    def _detect_zip_based_format(self, file_path: Path) -> DocumentFormat:
        """
        Detect specific format for ZIP-based files (DOCX, ODT).

        Args:
            file_path: Path to the ZIP-based file

        Returns:
            Detected DocumentFormat
        """
        try:
            import zipfile

            with zipfile.ZipFile(file_path, 'r') as zip_file:
                file_list = zip_file.namelist()

                # Check for DOCX structure
                if any(name.startswith('word/') for name in file_list):
                    return DocumentFormat.DOCX

                # Check for ODT structure
                if 'META-INF/manifest.xml' in file_list:
                    return DocumentFormat.ODT

            return DocumentFormat.UNKNOWN

        except Exception as e:
            self._logger.warning(f"ZIP-based format detection failed for {file_path}: {e}")
            return DocumentFormat.UNKNOWN

    def _mime_to_format(self, mime_type: str) -> DocumentFormat:
        """
        Convert MIME type to DocumentFormat.

        Args:
            mime_type: MIME type string

        Returns:
            Corresponding DocumentFormat
        """
        mime_mapping = {
            'application/pdf': DocumentFormat.PDF,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocumentFormat.DOCX,
            'application/msword': DocumentFormat.DOC,
            'text/plain': DocumentFormat.TXT,
            'text/html': DocumentFormat.HTML,
            'text/markdown': DocumentFormat.MARKDOWN,
            'application/rtf': DocumentFormat.RTF,
            'application/vnd.oasis.opendocument.text': DocumentFormat.ODT,
        }

        return mime_mapping.get(mime_type, DocumentFormat.UNKNOWN)

    def _combine_detection_results(self, extension_result: Optional[Dict],
                                 magic_result: Optional[Dict],
                                 mime_result: Optional[Dict]) -> Tuple[DocumentFormat, float]:
        """
        Combine results from different detection methods.

        Args:
            extension_result: Result from extension detection
            magic_result: Result from magic number detection
            mime_result: Result from MIME type detection

        Returns:
            Tuple of (final_format, confidence_score)
        """
        results = []

        # Collect all valid results
        if extension_result:
            results.append(extension_result)
        if magic_result:
            results.append(magic_result)
        if mime_result:
            results.append(mime_result)

        if not results:
            return DocumentFormat.UNKNOWN, 0.0

        # If all methods agree, high confidence
        formats = [r['format'] for r in results]
        if len(set(formats)) == 1:
            # All methods agree
            max_confidence = max(r['confidence'] for r in results)
            return formats[0], min(max_confidence + 0.1, 1.0)  # Boost confidence but cap at 1.0

        # If methods disagree, use weighted voting
        format_scores = {}
        for result in results:
            format_type = result['format']
            confidence = result['confidence']

            # Weight magic number detection higher
            if result.get('method') == 'magic_number':
                confidence *= 1.2
            elif result.get('method') == 'magic_number_zip':
                confidence *= 1.1

            if format_type in format_scores:
                format_scores[format_type] += confidence
            else:
                format_scores[format_type] = confidence

        # Return format with highest weighted score
        if format_scores:
            best_format = max(format_scores.items(), key=lambda x: x[1])
            # Normalize confidence based on number of agreeing methods
            normalized_confidence = min(best_format[1] / len(results), 1.0)
            return best_format[0], normalized_confidence

        return DocumentFormat.UNKNOWN, 0.0
