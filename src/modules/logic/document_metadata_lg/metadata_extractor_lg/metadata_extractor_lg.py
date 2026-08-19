"""
Module: metadata_extractor_lg
Description: Extracts document properties including author, creation date, and custom metadata
Phase: 3
Location: /src/modules/logic/document_metadata_lg/metadata_extractor_lg/metadata_extractor_lg.py
"""

# Standard library imports
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import mimetypes
import json

# Third-party imports
try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

try:
    from langdetect import detect, LangDetectError
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IMetadataExtractor,
    DocumentMetadata,
    MetadataExtractionResult,
    MetadataExtractionConfig,
    MetadataType,
    ExtractionStatus
)


class DocumentPropertyExtractor:
    """Extracts standard document properties from various file formats."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        self._supported_formats = {'.pdf', '.docx', '.txt', '.html', '.md', '.json', '.xml'}
    
    def extract_file_properties(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract basic file properties.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary of file properties
        """
        try:
            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            return {
                'file_size': stat.st_size,
                'creation_date': datetime.fromtimestamp(stat.st_ctime),
                'modification_date': datetime.fromtimestamp(stat.st_mtime),
                'file_format': file_path.suffix.lower(),
                'mime_type': mime_type,
                'file_name': file_path.name,
                'file_stem': file_path.stem
            }
        except Exception as e:
            self._logger.error(f"Failed to extract file properties: {e}")
            return {}
    
    def detect_encoding(self, file_path: Path) -> Optional[str]:
        """
        Detect file encoding.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Detected encoding or None
        """
        if not CHARDET_AVAILABLE:
            return 'utf-8'  # Default fallback
        
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Read first 10KB
                result = chardet.detect(raw_data)
                return result.get('encoding', 'utf-8')
        except Exception as e:
            self._logger.warning(f"Failed to detect encoding: {e}")
            return 'utf-8'
    
    def extract_text_statistics(self, content: str) -> Dict[str, int]:
        """
        Calculate text statistics.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Dictionary of text statistics
        """
        try:
            # Basic counts
            character_count = len(content)
            word_count = len(content.split())
            line_count = len(content.splitlines())
            
            # Paragraph count (empty lines separate paragraphs)
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            paragraph_count = len(paragraphs)
            
            # Sentence count (rough estimation)
            sentence_endings = re.findall(r'[.!?]+', content)
            sentence_count = len(sentence_endings)
            
            return {
                'character_count': character_count,
                'word_count': word_count,
                'line_count': line_count,
                'paragraph_count': paragraph_count,
                'sentence_count': sentence_count
            }
        except Exception as e:
            self._logger.error(f"Failed to calculate text statistics: {e}")
            return {
                'character_count': 0,
                'word_count': 0,
                'line_count': 0,
                'paragraph_count': 0,
                'sentence_count': 0
            }
    
    def detect_language(self, content: str) -> Optional[str]:
        """
        Detect document language.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Detected language code or None
        """
        if not LANGDETECT_AVAILABLE or not content.strip():
            return None
        
        try:
            # Use first 1000 characters for language detection
            sample = content[:1000].strip()
            if len(sample) < 50:  # Too short for reliable detection
                return None
            
            detected_lang = detect(sample)
            return detected_lang
        except (LangDetectError, Exception) as e:
            self._logger.debug(f"Language detection failed: {e}")
            return None


class CustomMetadataParser:
    """Parses custom metadata from various document formats."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """
        Parse YAML frontmatter from markdown documents.
        
        Args:
            content: Document content
            
        Returns:
            Dictionary of frontmatter metadata
        """
        try:
            # Check for YAML frontmatter
            if content.startswith('---'):
                end_marker = content.find('---', 3)
                if end_marker != -1:
                    frontmatter = content[3:end_marker].strip()
                    return self._parse_yaml_like(frontmatter)
            return {}
        except Exception as e:
            self._logger.warning(f"Failed to parse frontmatter: {e}")
            return {}
    
    def parse_html_meta(self, content: str) -> Dict[str, Any]:
        """
        Parse HTML meta tags.
        
        Args:
            content: HTML content
            
        Returns:
            Dictionary of meta tag metadata
        """
        try:
            metadata = {}
            
            # Extract title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if title_match:
                metadata['title'] = title_match.group(1).strip()
            
            # Extract meta tags
            meta_pattern = r'<meta\s+([^>]+)>'
            for match in re.finditer(meta_pattern, content, re.IGNORECASE):
                attrs = self._parse_html_attributes(match.group(1))
                
                name = attrs.get('name') or attrs.get('property') or attrs.get('http-equiv')
                content_val = attrs.get('content')
                
                if name and content_val:
                    metadata[f'meta_{name.lower()}'] = content_val
            
            return metadata
        except Exception as e:
            self._logger.warning(f"Failed to parse HTML meta: {e}")
            return {}
    
    def parse_json_metadata(self, content: str) -> Dict[str, Any]:
        """
        Parse metadata from JSON documents.
        
        Args:
            content: JSON content
            
        Returns:
            Dictionary of JSON metadata
        """
        try:
            data = json.loads(content)
            
            # Extract common metadata fields
            metadata = {}
            common_fields = ['title', 'author', 'description', 'version', 'created', 'modified']
            
            for field in common_fields:
                if field in data:
                    metadata[field] = data[field]
            
            # Look for nested metadata objects
            if 'metadata' in data and isinstance(data['metadata'], dict):
                metadata.update(data['metadata'])
            
            return metadata
        except (json.JSONDecodeError, Exception) as e:
            self._logger.warning(f"Failed to parse JSON metadata: {e}")
            return {}
    
    def _parse_yaml_like(self, content: str) -> Dict[str, Any]:
        """Parse simple YAML-like key-value pairs."""
        metadata = {}
        
        for line in content.splitlines():
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                
                # Try to convert to appropriate type
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif self._is_float(value):
                    value = float(value)
                
                metadata[key] = value
        
        return metadata
    
    def _parse_html_attributes(self, attr_string: str) -> Dict[str, str]:
        """Parse HTML attributes from attribute string."""
        attrs = {}
        attr_pattern = r'(\w+)=(["\'])(.*?)\2'
        
        for match in re.finditer(attr_pattern, attr_string):
            name, _, value = match.groups()
            attrs[name.lower()] = value
        
        return attrs
    
    def _is_float(self, value: str) -> bool:
        """Check if string represents a float."""
        try:
            float(value)
            return True
        except ValueError:
            return False


class MetadataExtractor(IMetadataExtractor):
    """
    Main metadata extractor that extracts document properties including author, creation date, and custom metadata.
    
    Features:
    - Standard metadata extraction (author, title, dates, etc.)
    - Custom metadata parsing from various formats
    - File property extraction
    - Text statistics calculation
    - Language detection
    - Encoding detection
    - Validation and confidence scoring
    """
    
    def __init__(self, config: Optional[MetadataExtractionConfig] = None):
        """Initialize metadata extractor."""
        self._config = config or MetadataExtractionConfig()
        self._logger = get_logger(__name__)
        self._property_extractor = DocumentPropertyExtractor()
        self._custom_parser = CustomMetadataParser()
    
    def extract_metadata(self, file_path: Path, content: Optional[str] = None) -> MetadataExtractionResult:
        """
        Extract metadata from a document.
        
        Args:
            file_path: Path to the document file
            content: Optional pre-extracted content
            
        Returns:
            MetadataExtractionResult with extracted metadata
        """
        start_time = time.time()
        errors = []
        warnings = []
        extracted_fields = []
        confidence_scores = {}
        
        try:
            # Initialize metadata container
            metadata = DocumentMetadata()
            
            # Extract file properties
            if self._config.extract_technical_metadata:
                file_props = self._property_extractor.extract_file_properties(file_path)
                if file_props:
                    metadata.file_format = file_props.get('file_format')
                    metadata.file_size = file_props.get('file_size')
                    metadata.creation_date = file_props.get('creation_date')
                    metadata.modification_date = file_props.get('modification_date')
                    metadata.encoding = self._property_extractor.detect_encoding(file_path)
                    extracted_fields.extend([MetadataType.CREATION_DATE, MetadataType.MODIFICATION_DATE])
                    confidence_scores['file_properties'] = 1.0
            
            # Read content if not provided
            if content is None:
                content = self._read_file_content(file_path)
            
            if content:
                # Extract text statistics
                if self._config.calculate_statistics:
                    stats = self._property_extractor.extract_text_statistics(content)
                    metadata.word_count = stats.get('word_count')
                    metadata.character_count = stats.get('character_count')
                    extracted_fields.extend([MetadataType.WORD_COUNT, MetadataType.CHARACTER_COUNT])
                    confidence_scores['statistics'] = 1.0
                
                # Detect language
                if self._config.language_detection:
                    detected_lang = self._property_extractor.detect_language(content)
                    if detected_lang:
                        metadata.language = detected_lang
                        extracted_fields.append(MetadataType.LANGUAGE)
                        confidence_scores['language'] = 0.8
                
                # Extract custom metadata based on file format
                if self._config.extract_custom_metadata:
                    custom_metadata = self._extract_format_specific_metadata(file_path, content)
                    if custom_metadata:
                        self._merge_custom_metadata(metadata, custom_metadata)
                        confidence_scores['custom_metadata'] = 0.7
            
            # Validate extracted metadata
            if self._config.validate_dates:
                self._validate_dates(metadata, warnings)
            
            # Calculate overall confidence
            overall_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.5
            metadata.confidence_score = overall_confidence
            
            processing_duration = (time.time() - start_time) * 1000
            
            return MetadataExtractionResult(
                status=ExtractionStatus.SUCCESS if not errors else ExtractionStatus.PARTIAL,
                metadata=metadata,
                extraction_duration_ms=processing_duration,
                errors=errors,
                warnings=warnings,
                extracted_fields=extracted_fields,
                confidence_scores=confidence_scores
            )
            
        except Exception as e:
            self._logger.error(f"Metadata extraction failed: {e}")
            processing_duration = (time.time() - start_time) * 1000
            
            return MetadataExtractionResult(
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                extraction_duration_ms=processing_duration,
                errors=[str(e)],
                warnings=warnings,
                extracted_fields=[],
                confidence_scores={}
            )

    def extract_specific_metadata(self, file_path: Path, metadata_types: List[MetadataType]) -> MetadataExtractionResult:
        """
        Extract specific types of metadata from a document.

        Args:
            file_path: Path to the document file
            metadata_types: List of metadata types to extract

        Returns:
            MetadataExtractionResult with requested metadata
        """
        start_time = time.time()
        errors = []
        warnings = []
        extracted_fields = []
        confidence_scores = {}

        try:
            metadata = DocumentMetadata()

            # Read content if needed
            content = None
            if any(mt in [MetadataType.WORD_COUNT, MetadataType.CHARACTER_COUNT, MetadataType.LANGUAGE]
                   for mt in metadata_types):
                content = self._read_file_content(file_path)

            # Extract requested metadata types
            for metadata_type in metadata_types:
                try:
                    if metadata_type == MetadataType.CREATION_DATE:
                        file_props = self._property_extractor.extract_file_properties(file_path)
                        metadata.creation_date = file_props.get('creation_date')
                        extracted_fields.append(metadata_type)
                        confidence_scores['creation_date'] = 1.0

                    elif metadata_type == MetadataType.MODIFICATION_DATE:
                        file_props = self._property_extractor.extract_file_properties(file_path)
                        metadata.modification_date = file_props.get('modification_date')
                        extracted_fields.append(metadata_type)
                        confidence_scores['modification_date'] = 1.0

                    elif metadata_type == MetadataType.WORD_COUNT and content:
                        stats = self._property_extractor.extract_text_statistics(content)
                        metadata.word_count = stats.get('word_count')
                        extracted_fields.append(metadata_type)
                        confidence_scores['word_count'] = 1.0

                    elif metadata_type == MetadataType.CHARACTER_COUNT and content:
                        stats = self._property_extractor.extract_text_statistics(content)
                        metadata.character_count = stats.get('character_count')
                        extracted_fields.append(metadata_type)
                        confidence_scores['character_count'] = 1.0

                    elif metadata_type == MetadataType.LANGUAGE and content:
                        detected_lang = self._property_extractor.detect_language(content)
                        if detected_lang:
                            metadata.language = detected_lang
                            extracted_fields.append(metadata_type)
                            confidence_scores['language'] = 0.8

                    elif metadata_type == MetadataType.PAGE_COUNT:
                        # This would need format-specific extraction
                        warnings.append(f"Page count extraction not implemented for {file_path.suffix}")

                    elif metadata_type == MetadataType.CUSTOM and content:
                        custom_metadata = self._extract_format_specific_metadata(file_path, content)
                        if custom_metadata:
                            self._merge_custom_metadata(metadata, custom_metadata)
                            extracted_fields.append(metadata_type)
                            confidence_scores['custom_metadata'] = 0.7

                except Exception as e:
                    errors.append(f"Failed to extract {metadata_type.value}: {str(e)}")

            # Calculate overall confidence
            overall_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.5
            metadata.confidence_score = overall_confidence

            processing_duration = (time.time() - start_time) * 1000

            return MetadataExtractionResult(
                status=ExtractionStatus.SUCCESS if not errors else ExtractionStatus.PARTIAL,
                metadata=metadata,
                extraction_duration_ms=processing_duration,
                errors=errors,
                warnings=warnings,
                extracted_fields=extracted_fields,
                confidence_scores=confidence_scores
            )

        except Exception as e:
            self._logger.error(f"Specific metadata extraction failed: {e}")
            processing_duration = (time.time() - start_time) * 1000

            return MetadataExtractionResult(
                status=ExtractionStatus.FAILED,
                metadata=DocumentMetadata(),
                extraction_duration_ms=processing_duration,
                errors=[str(e)],
                warnings=warnings,
                extracted_fields=[],
                confidence_scores={}
            )

    def validate_metadata(self, metadata: DocumentMetadata) -> Tuple[bool, List[str]]:
        """
        Validate extracted metadata for completeness and accuracy.

        Args:
            metadata: Metadata to validate

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        try:
            # Validate dates
            if metadata.creation_date and metadata.modification_date:
                if metadata.creation_date > metadata.modification_date:
                    errors.append("Creation date is after modification date")

            # Validate counts
            if metadata.word_count is not None and metadata.word_count < 0:
                errors.append("Word count cannot be negative")

            if metadata.character_count is not None and metadata.character_count < 0:
                errors.append("Character count cannot be negative")

            if metadata.page_count is not None and metadata.page_count < 1:
                errors.append("Page count must be at least 1")

            # Validate text fields
            if metadata.title and len(metadata.title.strip()) == 0:
                errors.append("Title cannot be empty")

            if metadata.author and len(metadata.author.strip()) == 0:
                errors.append("Author cannot be empty")

            # Validate language code
            if metadata.language and len(metadata.language) not in [2, 3]:
                errors.append("Language code should be 2 or 3 characters")

            # Validate confidence score
            if not (0.0 <= metadata.confidence_score <= 1.0):
                errors.append("Confidence score must be between 0.0 and 1.0")

            return len(errors) == 0, errors

        except Exception as e:
            self._logger.error(f"Metadata validation failed: {e}")
            return False, [f"Validation error: {str(e)}"]

    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content with encoding detection."""
        try:
            encoding = self._property_extractor.detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            self._logger.error(f"Failed to read file content: {e}")
            return None

    def _extract_format_specific_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Extract metadata specific to file format."""
        try:
            file_ext = file_path.suffix.lower()

            if file_ext == '.md':
                return self._custom_parser.parse_frontmatter(content)
            elif file_ext in ['.html', '.htm']:
                return self._custom_parser.parse_html_meta(content)
            elif file_ext == '.json':
                return self._custom_parser.parse_json_metadata(content)
            else:
                # Try to extract basic metadata from text
                return self._extract_text_metadata(content)

        except Exception as e:
            self._logger.warning(f"Format-specific metadata extraction failed: {e}")
            return {}

    def _extract_text_metadata(self, content: str) -> Dict[str, Any]:
        """Extract basic metadata from plain text."""
        metadata = {}

        try:
            lines = content.splitlines()
            if lines:
                # First non-empty line might be title
                for line in lines:
                    line = line.strip()
                    if line and len(line) < 200:  # Reasonable title length
                        metadata['title'] = line
                        break

            # Look for common patterns
            author_patterns = [
                r'(?i)author[:\s]+(.+)',
                r'(?i)by[:\s]+(.+)',
                r'(?i)written by[:\s]+(.+)'
            ]

            for pattern in author_patterns:
                match = re.search(pattern, content)
                if match:
                    metadata['author'] = match.group(1).strip()
                    break

            # Look for date patterns
            date_patterns = [
                r'(?i)date[:\s]+(\d{4}-\d{2}-\d{2})',
                r'(?i)created[:\s]+(\d{4}-\d{2}-\d{2})',
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{4}/\d{1,2}/\d{1,2})'
            ]

            for pattern in date_patterns:
                match = re.search(pattern, content)
                if match:
                    try:
                        date_str = match.group(1)
                        # Try to parse the date
                        if '-' in date_str:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        elif '/' in date_str:
                            # Try different formats
                            for fmt in ['%m/%d/%Y', '%Y/%m/%d', '%d/%m/%Y']:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                continue

                        metadata['creation_date'] = date_obj
                        break
                    except ValueError:
                        continue

        except Exception as e:
            self._logger.warning(f"Text metadata extraction failed: {e}")

        return metadata

    def _merge_custom_metadata(self, metadata: DocumentMetadata, custom_metadata: Dict[str, Any]) -> None:
        """Merge custom metadata into the main metadata object."""
        try:
            # Map common fields
            field_mapping = {
                'title': 'title',
                'author': 'author',
                'subject': 'subject',
                'description': 'subject',
                'keywords': 'keywords',
                'creator': 'creator',
                'producer': 'producer',
                'language': 'language',
                'lang': 'language'
            }

            for custom_key, value in custom_metadata.items():
                if custom_key.lower() in field_mapping:
                    field_name = field_mapping[custom_key.lower()]

                    # Set the field if not already set
                    if not getattr(metadata, field_name, None):
                        if field_name == 'keywords' and isinstance(value, str):
                            # Convert comma-separated keywords to list
                            setattr(metadata, field_name, [k.strip() for k in value.split(',')])
                        else:
                            setattr(metadata, field_name, value)
                else:
                    # Add to custom properties
                    if len(metadata.custom_properties) < self._config.max_custom_fields:
                        metadata.custom_properties[custom_key] = value

        except Exception as e:
            self._logger.warning(f"Failed to merge custom metadata: {e}")

    def _validate_dates(self, metadata: DocumentMetadata, warnings: List[str]) -> None:
        """Validate date fields and add warnings if needed."""
        try:
            current_time = datetime.now()

            # Check if dates are in the future
            if metadata.creation_date and metadata.creation_date > current_time:
                warnings.append("Creation date is in the future")

            if metadata.modification_date and metadata.modification_date > current_time:
                warnings.append("Modification date is in the future")

            # Check if creation date is after modification date
            if (metadata.creation_date and metadata.modification_date and
                metadata.creation_date > metadata.modification_date):
                warnings.append("Creation date is after modification date")

        except Exception as e:
            self._logger.warning(f"Date validation failed: {e}")
