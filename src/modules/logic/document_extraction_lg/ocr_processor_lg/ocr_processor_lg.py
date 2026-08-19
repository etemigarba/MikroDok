"""
Module: ocr_processor_lg
Description: Performs optical character recognition on images and scanned documents using Tesseract
Phase: 3
Location: /src/modules/logic/document_extraction_lg/ocr_processor_lg/ocr_processor_lg.py
"""

# Standard library imports
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

# Third-party imports
try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

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
class OCRConfig:
    """Configuration for OCR processing."""
    language: str = 'eng'  # Tesseract language code
    additional_languages: List[str] = field(default_factory=list)
    page_segmentation_mode: int = 6  # PSM mode (0-13)
    ocr_engine_mode: int = 3  # OEM mode (0-3)
    preprocessing_enabled: bool = True
    deskew_enabled: bool = True
    noise_removal_enabled: bool = True
    contrast_enhancement: bool = True
    resize_factor: float = 2.0  # Scale factor for image resizing
    confidence_threshold: float = 30.0  # Minimum confidence for text
    whitelist_chars: Optional[str] = None  # Character whitelist
    blacklist_chars: Optional[str] = None  # Character blacklist
    extract_tables: bool = True
    extract_images: bool = True
    extract_metadata: bool = True
    quality_threshold: float = 0.5
    timeout_seconds: int = 600


class ImagePreprocessor:
    """Specialized image preprocessor for OCR optimization."""
    
    def __init__(self, config: OCRConfig):
        """Initialize image preprocessor."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def preprocess_image(self, image):
        """Preprocess image for better OCR results."""
        try:
            processed_image = image.copy()
            
            # Convert to grayscale if not already
            if processed_image.mode != 'L':
                processed_image = processed_image.convert('L')
            
            # Resize image for better OCR
            if self._config.resize_factor != 1.0:
                width, height = processed_image.size
                new_size = (int(width * self._config.resize_factor), 
                           int(height * self._config.resize_factor))
                processed_image = processed_image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Enhance contrast
            if self._config.contrast_enhancement:
                enhancer = ImageEnhance.Contrast(processed_image)
                processed_image = enhancer.enhance(1.5)
            
            # Apply noise removal
            if self._config.noise_removal_enabled:
                processed_image = processed_image.filter(ImageFilter.MedianFilter(size=3))
            
            # Deskew if OpenCV is available
            if self._config.deskew_enabled and OPENCV_AVAILABLE:
                processed_image = self._deskew_image(processed_image)
            
            return processed_image
            
        except Exception as e:
            self._logger.warning(f"Image preprocessing failed: {e}")
            return image
    
    def _deskew_image(self, image):
        """Deskew image using OpenCV."""
        try:
            # Convert PIL image to OpenCV format
            img_array = np.array(image)
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Find contours and get skew angle
            coords = np.column_stack(np.where(binary > 0))
            angle = cv2.minAreaRect(coords)[-1]
            
            # Correct angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            # Rotate image if angle is significant
            if abs(angle) > 0.5:  # Only rotate if angle > 0.5 degrees
                (h, w) = img_array.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(img_array, M, (w, h), 
                                       flags=cv2.INTER_CUBIC, 
                                       borderMode=cv2.BORDER_REPLICATE)
                
                return Image.fromarray(rotated)
            
            return image
            
        except Exception as e:
            self._logger.warning(f"Image deskewing failed: {e}")
            return image


class LanguageDetector:
    """Language detection for OCR processing."""
    
    def __init__(self, config: OCRConfig):
        """Initialize language detector."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def detect_language(self, image) -> str:
        """Detect language from image text."""
        try:
            if not TESSERACT_AVAILABLE:
                return self._config.language
            
            # Get available languages
            available_langs = pytesseract.get_languages()
            
            # Try to detect language using Tesseract's OSD (Orientation and Script Detection)
            try:
                osd_data = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
                detected_script = osd_data.get('script', '')
                
                # Map script to language (simplified mapping)
                script_to_lang = {
                    'Latin': 'eng',
                    'Arabic': 'ara',
                    'Chinese': 'chi_sim',
                    'Cyrillic': 'rus',
                    'Devanagari': 'hin'
                }
                
                detected_lang = script_to_lang.get(detected_script, self._config.language)
                
                # Verify language is available
                if detected_lang in available_langs:
                    return detected_lang
                    
            except Exception:
                # OSD failed, fall back to default
                pass
            
            return self._config.language
            
        except Exception as e:
            self._logger.warning(f"Language detection failed: {e}")
            return self._config.language


class ConfidenceAnalyzer:
    """Confidence analysis for OCR results."""
    
    def __init__(self, config: OCRConfig):
        """Initialize confidence analyzer."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def analyze_confidence(self, ocr_data: Dict[str, Any]) -> Dict[str, float]:
        """Analyze confidence scores from OCR data."""
        try:
            confidences = ocr_data.get('conf', [])
            texts = ocr_data.get('text', [])
            
            if not confidences or not texts:
                return {'overall': 0.0, 'word_level': 0.0, 'line_level': 0.0}
            
            # Filter out invalid confidences and empty text
            valid_confidences = []
            for conf, text in zip(confidences, texts):
                if conf >= 0 and text.strip():  # Valid confidence and non-empty text
                    valid_confidences.append(conf)
            
            if not valid_confidences:
                return {'overall': 0.0, 'word_level': 0.0, 'line_level': 0.0}
            
            # Calculate metrics
            overall_confidence = sum(valid_confidences) / len(valid_confidences)
            
            # Word-level confidence (percentage of words above threshold)
            high_conf_words = sum(1 for conf in valid_confidences 
                                if conf >= self._config.confidence_threshold)
            word_level_confidence = (high_conf_words / len(valid_confidences)) * 100
            
            # Line-level confidence (simplified)
            line_level_confidence = overall_confidence
            
            return {
                'overall': overall_confidence,
                'word_level': word_level_confidence,
                'line_level': line_level_confidence,
                'total_words': len(valid_confidences),
                'high_confidence_words': high_conf_words
            }
            
        except Exception as e:
            self._logger.warning(f"Confidence analysis failed: {e}")
            return {'overall': 0.0, 'word_level': 0.0, 'line_level': 0.0}


class OCRProcessor(IDocumentExtractor):
    """
    OCR processor using Tesseract for optical character recognition.

    Features:
    - Text extraction from images and scanned documents
    - Image preprocessing for better OCR results
    - Multi-language support
    - Confidence scoring and quality analysis
    - Table detection in images
    - Metadata extraction from OCR results
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        """Initialize OCR processor."""
        self._config = config or OCRConfig()
        self._logger = get_logger(__name__)
        self._preprocessor = ImagePreprocessor(self._config)
        self._language_detector = LanguageDetector(self._config)
        self._confidence_analyzer = ConfidenceAnalyzer(self._config)

        if not TESSERACT_AVAILABLE:
            raise ImportError("pytesseract and PIL are required for OCR processing")

    def extract(self, file_path: Union[str, Path], config: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract content from image using OCR.

        Args:
            file_path: Path to the image file
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
                metadata=self._create_metadata(path_obj, start_time),
                quality_metrics=QualityMetrics(overall_confidence=0.0),
                validation_errors=validation_errors
            )

        # Override config if provided
        extraction_config = self._config
        if config:
            extraction_config = self._merge_config(config)

        try:
            # Load image
            image = Image.open(str(path_obj))

            return self._extract_from_image(image, path_obj, start_time, extraction_config)

        except Exception as e:
            self._logger.error(f"OCR extraction failed for {file_path}: {e}")

            error = ValidationError(
                field_name="ocr_extraction",
                error_message=f"OCR extraction error: {str(e)}",
                severity="ERROR",
                validation_type="PROCESSING"
            )

            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                content="",
                metadata=self._create_metadata(path_obj, start_time),
                quality_metrics=QualityMetrics(overall_confidence=0.0),
                validation_errors=[error]
            )

    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """Check if file format is supported by this extractor."""
        path_obj = Path(file_path)
        supported_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
        return path_obj.suffix.lower() in supported_extensions

    def get_supported_formats(self) -> List[DocumentFormat]:
        """Get list of supported document formats."""
        # OCR processor works with images, not document formats per se
        return []

    def validate_file(self, file_path: Union[str, Path]) -> List[ValidationError]:
        """Validate image file before OCR processing."""
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
                error_message=f"Unsupported image format: {path_obj.suffix}",
                severity="ERROR",
                validation_type="FORMAT"
            ))

        # Check file size (100MB limit for images)
        file_size = path_obj.stat().st_size
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            errors.append(ValidationError(
                field_name="file_size",
                error_message=f"Image file size exceeds maximum limit: {file_size} bytes",
                severity="ERROR",
                validation_type="CONSTRAINT"
            ))

        # Try to open image to check for corruption
        if not errors:  # Only if no previous errors
            try:
                with Image.open(str(path_obj)) as img:
                    # Try to access image properties to verify integrity
                    _ = img.size
                    _ = img.mode
            except Exception as e:
                errors.append(ValidationError(
                    field_name="image_integrity",
                    error_message=f"Image file appears to be corrupted: {str(e)}",
                    severity="ERROR",
                    validation_type="INTEGRITY"
                ))

        return errors

    def get_extraction_config_schema(self) -> Dict[str, Any]:
        """Get schema for extraction configuration."""
        return {
            "type": "object",
            "properties": {
                "language": {"type": "string", "default": "eng"},
                "additional_languages": {"type": "array", "items": {"type": "string"}},
                "page_segmentation_mode": {"type": "integer", "minimum": 0, "maximum": 13, "default": 6},
                "ocr_engine_mode": {"type": "integer", "minimum": 0, "maximum": 3, "default": 3},
                "preprocessing_enabled": {"type": "boolean", "default": True},
                "deskew_enabled": {"type": "boolean", "default": True},
                "noise_removal_enabled": {"type": "boolean", "default": True},
                "contrast_enhancement": {"type": "boolean", "default": True},
                "resize_factor": {"type": "number", "minimum": 0.5, "maximum": 5.0, "default": 2.0},
                "confidence_threshold": {"type": "number", "minimum": 0.0, "maximum": 100.0, "default": 30.0},
                "quality_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.5}
            }
        }

    def estimate_processing_time(self, file_path: Union[str, Path]) -> float:
        """Estimate processing time for OCR processing."""
        path_obj = Path(file_path)

        if not path_obj.exists():
            return 0.0

        try:
            # Load image to get dimensions
            with Image.open(str(path_obj)) as img:
                width, height = img.size
                pixel_count = width * height

                # Base time estimates (OCR is generally slow)
                base_time = 2.0  # Base processing time
                pixel_time = pixel_count / 1000000 * 3.0  # 3 seconds per megapixel

                # Additional time for preprocessing
                preprocessing_time = 1.0 if self._config.preprocessing_enabled else 0.0

                total_time = base_time + pixel_time + preprocessing_time

                return max(2.0, total_time)  # Minimum 2 seconds

        except Exception:
            # Fallback estimation based on file size
            file_size_mb = path_obj.stat().st_size / (1024 * 1024)
            return max(2.0, file_size_mb * 2.0)  # 2 seconds per MB

    def _merge_config(self, override_config: Dict[str, Any]) -> OCRConfig:
        """Merge override configuration with default config."""
        config_dict = {
            'language': override_config.get('language', self._config.language),
            'additional_languages': override_config.get('additional_languages', self._config.additional_languages),
            'page_segmentation_mode': override_config.get('page_segmentation_mode', self._config.page_segmentation_mode),
            'ocr_engine_mode': override_config.get('ocr_engine_mode', self._config.ocr_engine_mode),
            'preprocessing_enabled': override_config.get('preprocessing_enabled', self._config.preprocessing_enabled),
            'deskew_enabled': override_config.get('deskew_enabled', self._config.deskew_enabled),
            'noise_removal_enabled': override_config.get('noise_removal_enabled', self._config.noise_removal_enabled),
            'contrast_enhancement': override_config.get('contrast_enhancement', self._config.contrast_enhancement),
            'resize_factor': override_config.get('resize_factor', self._config.resize_factor),
            'confidence_threshold': override_config.get('confidence_threshold', self._config.confidence_threshold),
            'quality_threshold': override_config.get('quality_threshold', self._config.quality_threshold)
        }

        return OCRConfig(**config_dict)

    def _extract_from_image(self, image, path_obj: Path, start_time: datetime,
                           config: OCRConfig) -> ExtractionResult:
        """Extract content from image using OCR."""
        try:
            # Preprocess image if enabled
            processed_image = image
            if config.preprocessing_enabled:
                processed_image = self._preprocessor.preprocess_image(image)

            # Detect language
            detected_language = self._language_detector.detect_language(processed_image)

            # Prepare language string for Tesseract
            languages = [detected_language]
            if config.additional_languages:
                languages.extend(config.additional_languages)
            lang_string = '+'.join(languages)

            # Configure Tesseract
            custom_config = f'--oem {config.ocr_engine_mode} --psm {config.page_segmentation_mode}'

            if config.whitelist_chars:
                custom_config += f' -c tessedit_char_whitelist={config.whitelist_chars}'
            if config.blacklist_chars:
                custom_config += f' -c tessedit_char_blacklist={config.blacklist_chars}'

            # Perform OCR
            text_content = pytesseract.image_to_string(
                processed_image,
                lang=lang_string,
                config=custom_config
            ).strip()

            # Get detailed OCR data for confidence analysis
            ocr_data = pytesseract.image_to_data(
                processed_image,
                lang=lang_string,
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )

            # Analyze confidence
            confidence_metrics = self._confidence_analyzer.analyze_confidence(ocr_data)

            # Extract tables if enabled (simplified table detection)
            tables = []
            if config.extract_tables:
                tables = self._extract_tables_from_ocr(ocr_data)

            # Create document structure
            structure = self._analyze_document_structure(text_content, ocr_data)

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(
                text_content, confidence_metrics, tables, image, start_time
            )

            # Create extraction metadata
            extraction_metadata = self._create_metadata(
                path_obj, start_time, detected_language, confidence_metrics, config
            )

            # Determine status
            status = self._determine_extraction_status(quality_metrics, confidence_metrics)

            return ExtractionResult(
                status=status,
                content=text_content,
                metadata=extraction_metadata,
                quality_metrics=quality_metrics,
                document_structure=structure,
                tables=tables
            )

        except Exception as e:
            self._logger.error(f"Failed to extract from image: {e}")

            error = ValidationError(
                field_name="ocr_processing",
                error_message=f"OCR processing error: {str(e)}",
                severity="ERROR",
                validation_type="PROCESSING"
            )

            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                content="",
                metadata=self._create_metadata(path_obj, start_time),
                quality_metrics=QualityMetrics(overall_confidence=0.0),
                validation_errors=[error]
            )

    def _extract_tables_from_ocr(self, ocr_data: Dict[str, Any]) -> List[TableData]:
        """Extract tables from OCR data (simplified implementation)."""
        # This is a simplified table extraction - in practice, you'd need
        # more sophisticated algorithms to detect table structures in OCR data
        return []

    def _analyze_document_structure(self, text: str, ocr_data: Dict[str, Any]) -> DocumentStructure:
        """Analyze document structure from OCR results."""
        structure = DocumentStructure()

        try:
            structure.word_count = len(text.split()) if text else 0
            structure.character_count = len(text) if text else 0

            # Simple heading detection based on text formatting
            lines = text.split('\n')
            headings = []
            for i, line in enumerate(lines):
                line = line.strip()
                if line and (line.isupper() or len(line) < 50):
                    headings.append({
                        'text': line,
                        'level': 1,
                        'line_number': i + 1
                    })

            structure.headings = headings[:10]  # Limit to first 10 headings

        except Exception as e:
            self._logger.warning(f"Failed to analyze document structure: {e}")

        return structure

    def _calculate_quality_metrics(self, text: str, confidence_metrics: Dict[str, float],
                                 tables: List[TableData], image,
                                 start_time: datetime) -> QualityMetrics:
        """Calculate quality metrics for OCR extraction."""
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Text confidence from OCR confidence scores
        text_confidence = confidence_metrics.get('overall', 0.0) / 100.0

        # Structure confidence based on text organization
        structure_confidence = 0.5 if text and '\n' in text else 0.2

        # Table confidence (simplified)
        table_confidence = 1.0 if tables else 0.0

        # Overall confidence
        overall_confidence = text_confidence * 0.8 + structure_confidence * 0.2

        # Completeness score based on confidence
        completeness_score = confidence_metrics.get('word_level', 0.0)

        return QualityMetrics(
            overall_confidence=overall_confidence,
            text_confidence=text_confidence,
            structure_confidence=structure_confidence,
            table_confidence=table_confidence,
            completeness_score=completeness_score,
            readability_score=min(100.0, text_confidence * 100),
            processing_time_ms=processing_time
        )

    def _create_metadata(self, path_obj: Path, start_time: datetime,
                        detected_language: Optional[str] = None,
                        confidence_metrics: Optional[Dict[str, float]] = None,
                        config: Optional[OCRConfig] = None) -> ExtractionMetadata:
        """Create extraction metadata."""
        processing_duration = (datetime.now() - start_time).total_seconds() * 1000

        return ExtractionMetadata(
            document_format=DocumentFormat.UNKNOWN,  # OCR works on images
            file_size=path_obj.stat().st_size,
            extraction_timestamp=start_time,
            extractor_version="1.0.0",
            processing_duration_ms=processing_duration,
            extraction_config={
                'language': config.language if config else 'eng',
                'preprocessing_enabled': config.preprocessing_enabled if config else True,
                'confidence_threshold': config.confidence_threshold if config else 30.0
            },
            document_properties={
                'detected_language': detected_language or 'unknown',
                'confidence_metrics': confidence_metrics or {}
            },
            technical_metadata={
                'tesseract_available': TESSERACT_AVAILABLE,
                'opencv_available': OPENCV_AVAILABLE,
                'file_extension': path_obj.suffix.lower()
            }
        )

    def _determine_extraction_status(self, quality_metrics: QualityMetrics,
                                   confidence_metrics: Dict[str, float]) -> ExtractionStatus:
        """Determine extraction status based on quality metrics."""
        overall_conf = confidence_metrics.get('overall', 0.0)

        if overall_conf >= self._config.confidence_threshold:
            return ExtractionStatus.SUCCESS
        elif overall_conf > 0.0:
            return ExtractionStatus.PARTIAL_SUCCESS
        else:
            return ExtractionStatus.FAILED
