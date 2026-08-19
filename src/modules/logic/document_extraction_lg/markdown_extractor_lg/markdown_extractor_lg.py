"""
Module: markdown_extractor_lg
Description: Processes Markdown files while preserving formatting and code blocks
Phase: 3
Location: /src/modules/logic/document_extraction_lg/markdown_extractor_lg/markdown_extractor_lg.py
"""

# Standard library imports
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

# Third-party imports
try:
    import markdown
    from markdown.extensions import codehilite, fenced_code, tables, toc
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

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
class MarkdownExtractionConfig:
    """Configuration for Markdown extraction."""
    extract_text: bool = True
    extract_tables: bool = True
    extract_images: bool = True
    extract_metadata: bool = True
    extract_frontmatter: bool = True
    extract_code_blocks: bool = True
    extract_links: bool = True
    preserve_formatting: bool = True
    convert_to_html: bool = False
    enable_extensions: List[str] = field(default_factory=lambda: [
        'tables', 'fenced_code', 'codehilite', 'toc', 'footnotes'
    ])
    encoding: str = 'utf-8'
    quality_threshold: float = 0.5
    timeout_seconds: int = 300


class FrontmatterExtractor:
    """Specialized frontmatter extractor for Markdown documents."""
    
    def __init__(self, config: MarkdownExtractionConfig):
        """Initialize frontmatter extractor."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def extract_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Extract frontmatter from Markdown content."""
        frontmatter = {}
        remaining_content = content
        
        try:
            # Check for YAML frontmatter (--- ... ---)
            yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
            yaml_match = re.match(yaml_pattern, content, re.DOTALL)
            
            if yaml_match and YAML_AVAILABLE:
                try:
                    frontmatter = yaml.safe_load(yaml_match.group(1))
                    remaining_content = content[yaml_match.end():]
                except yaml.YAMLError as e:
                    self._logger.warning(f"Failed to parse YAML frontmatter: {e}")
            
            # Check for TOML frontmatter (+++ ... +++)
            elif content.startswith('+++'):
                toml_pattern = r'^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n'
                toml_match = re.match(toml_pattern, content, re.DOTALL)
                
                if toml_match:
                    # Simple TOML parsing (basic key=value pairs)
                    toml_content = toml_match.group(1)
                    for line in toml_content.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip().strip('"\'')
                            value = value.strip().strip('"\'')
                            frontmatter[key] = value
                    
                    remaining_content = content[toml_match.end():]
            
            # Check for JSON frontmatter ({ ... })
            elif content.strip().startswith('{'):
                try:
                    import json
                    # Find the end of the JSON block
                    brace_count = 0
                    json_end = 0
                    
                    for i, char in enumerate(content):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    
                    if json_end > 0:
                        json_content = content[:json_end]
                        frontmatter = json.loads(json_content)
                        remaining_content = content[json_end:].lstrip('\n')
                        
                except (json.JSONDecodeError, ImportError) as e:
                    self._logger.warning(f"Failed to parse JSON frontmatter: {e}")
            
        except Exception as e:
            self._logger.warning(f"Failed to extract frontmatter: {e}")
        
        return frontmatter, remaining_content


class MarkdownStructureParser:
    """Specialized structure parser for Markdown documents."""
    
    def __init__(self, config: MarkdownExtractionConfig):
        """Initialize structure parser."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def parse_structure(self, content: str, frontmatter: Dict[str, Any]) -> DocumentStructure:
        """Parse document structure from Markdown content."""
        structure = DocumentStructure()
        
        try:
            # Extract title from frontmatter or first heading
            if frontmatter.get('title'):
                structure.title = str(frontmatter['title'])
            else:
                # Look for first H1 heading
                h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                if h1_match:
                    structure.title = h1_match.group(1).strip()
            
            # Extract headings
            headings = []
            heading_pattern = r'^(#{1,6})\s+(.+)$'
            
            for match in re.finditer(heading_pattern, content, re.MULTILINE):
                level = len(match.group(1))
                text = match.group(2).strip()
                
                headings.append({
                    'text': text,
                    'level': level,
                    'line_number': content[:match.start()].count('\n') + 1,
                    'anchor': self._generate_anchor(text)
                })
            
            structure.headings = headings
            
            # Create sections based on headings
            sections = []
            current_section = None
            
            for heading in headings:
                if heading['level'] == 1:  # New top-level section
                    if current_section:
                        sections.append(current_section)
                    
                    current_section = {
                        'title': heading['text'],
                        'level': heading['level'],
                        'start_line': heading['line_number'],
                        'content_length': 0
                    }
                elif current_section:
                    # Calculate content length for current section
                    # This is a simplified calculation
                    current_section['content_length'] += len(heading['text'])
            
            if current_section:
                sections.append(current_section)
            
            structure.sections = sections
            
            # Calculate document statistics
            structure.word_count = len(content.split()) if content else 0
            structure.character_count = len(content) if content else 0
            
            # Extract language from frontmatter
            if frontmatter.get('lang') or frontmatter.get('language'):
                structure.language = str(frontmatter.get('lang') or frontmatter.get('language'))
            
        except Exception as e:
            self._logger.warning(f"Failed to parse Markdown structure: {e}")
        
        return structure
    
    def _generate_anchor(self, text: str) -> str:
        """Generate anchor ID from heading text."""
        # Convert to lowercase and replace spaces with hyphens
        anchor = re.sub(r'[^\w\s-]', '', text.lower())
        anchor = re.sub(r'[-\s]+', '-', anchor)
        return anchor.strip('-')


class MarkdownExtractor(IDocumentExtractor):
    """
    Markdown document extractor for comprehensive content extraction.

    Features:
    - Text extraction with formatting preservation
    - Table extraction from Markdown tables
    - Image reference extraction
    - Code block extraction
    - Frontmatter extraction (YAML, TOML, JSON)
    - Link extraction
    - Structure analysis with headings and sections
    """

    def __init__(self, config: Optional[MarkdownExtractionConfig] = None):
        """Initialize Markdown extractor."""
        self._config = config or MarkdownExtractionConfig()
        self._logger = get_logger(__name__)
        self._frontmatter_extractor = FrontmatterExtractor(self._config)
        self._structure_parser = MarkdownStructureParser(self._config)

    def extract(self, file_path: Union[str, Path], config: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract content from Markdown document.

        Args:
            file_path: Path to the Markdown file
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
            # Read Markdown content
            with open(path_obj, 'r', encoding=extraction_config.encoding, errors='replace') as f:
                raw_content = f.read()

            return self._extract_from_content(raw_content, path_obj, start_time, extraction_config)

        except Exception as e:
            self._logger.error(f"Markdown extraction failed for {file_path}: {e}")

            error = ValidationError(
                field_name="markdown_extraction",
                error_message=f"Markdown extraction error: {str(e)}",
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
        return path_obj.suffix.lower() in ['.md', '.markdown', '.mdown', '.mkd']

    def get_supported_formats(self) -> List[DocumentFormat]:
        """Get list of supported document formats."""
        return [DocumentFormat.MARKDOWN]

    def validate_file(self, file_path: Union[str, Path]) -> List[ValidationError]:
        """Validate Markdown file before extraction."""
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

        # Try to read file to check for encoding issues
        if not errors:  # Only if no previous errors
            try:
                with open(path_obj, 'r', encoding=self._config.encoding, errors='replace') as f:
                    content = f.read()

                # Basic content validation
                if not content.strip():
                    errors.append(ValidationError(
                        field_name="markdown_content",
                        error_message="Markdown file is empty",
                        severity="ERROR",
                        validation_type="CONTENT"
                    ))

            except UnicodeDecodeError:
                errors.append(ValidationError(
                    field_name="markdown_encoding",
                    error_message=f"Cannot decode Markdown file with encoding: {self._config.encoding}",
                    severity="ERROR",
                    validation_type="ENCODING"
                ))
            except Exception as e:
                errors.append(ValidationError(
                    field_name="markdown_integrity",
                    error_message=f"Markdown file appears to be corrupted: {str(e)}",
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
                "extract_frontmatter": {"type": "boolean", "default": True},
                "extract_code_blocks": {"type": "boolean", "default": True},
                "extract_links": {"type": "boolean", "default": True},
                "preserve_formatting": {"type": "boolean", "default": True},
                "convert_to_html": {"type": "boolean", "default": False},
                "enable_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["tables", "fenced_code", "codehilite", "toc", "footnotes"]
                },
                "encoding": {"type": "string", "default": "utf-8"},
                "quality_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0}
            }
        }

    def estimate_processing_time(self, file_path: Union[str, Path]) -> float:
        """Estimate processing time for Markdown document."""
        path_obj = Path(file_path)

        if not path_obj.exists():
            return 0.0

        try:
            file_size_mb = path_obj.stat().st_size / (1024 * 1024)

            # Base time estimates
            base_time = 0.05  # Base processing time
            size_time = file_size_mb * 0.01  # 0.01 seconds per MB

            # Additional time for complex operations
            table_time = 0.02 if self._config.extract_tables else 0.0
            code_time = 0.01 if self._config.extract_code_blocks else 0.0

            total_time = base_time + size_time + table_time + code_time

            return max(0.05, total_time)  # Minimum 0.05 seconds

        except Exception:
            return 0.5  # Fallback estimate

    def _merge_config(self, override_config: Dict[str, Any]) -> MarkdownExtractionConfig:
        """Merge override configuration with default config."""
        config_dict = {
            'extract_text': override_config.get('extract_text', self._config.extract_text),
            'extract_tables': override_config.get('extract_tables', self._config.extract_tables),
            'extract_images': override_config.get('extract_images', self._config.extract_images),
            'extract_metadata': override_config.get('extract_metadata', self._config.extract_metadata),
            'extract_frontmatter': override_config.get('extract_frontmatter', self._config.extract_frontmatter),
            'extract_code_blocks': override_config.get('extract_code_blocks', self._config.extract_code_blocks),
            'extract_links': override_config.get('extract_links', self._config.extract_links),
            'preserve_formatting': override_config.get('preserve_formatting', self._config.preserve_formatting),
            'convert_to_html': override_config.get('convert_to_html', self._config.convert_to_html),
            'enable_extensions': override_config.get('enable_extensions', self._config.enable_extensions),
            'encoding': override_config.get('encoding', self._config.encoding),
            'quality_threshold': override_config.get('quality_threshold', self._config.quality_threshold)
        }

        return MarkdownExtractionConfig(**config_dict)

    def _extract_from_content(self, raw_content: str, path_obj: Path, start_time: datetime,
                             config: MarkdownExtractionConfig) -> ExtractionResult:
        """Extract content from Markdown text."""
        all_text = []
        all_tables = []
        all_images = []
        all_hyperlinks = []

        try:
            # Extract frontmatter
            frontmatter = {}
            content = raw_content

            if config.extract_frontmatter:
                frontmatter, content = self._frontmatter_extractor.extract_frontmatter(raw_content)

            # Extract main text content
            if config.extract_text:
                if config.convert_to_html and MARKDOWN_AVAILABLE:
                    text_content = self._convert_to_html(content, config)
                else:
                    text_content = content

                if text_content:
                    all_text.append(text_content)

            # Extract tables
            if config.extract_tables:
                tables = self._extract_tables(content)
                all_tables.extend(tables)

            # Extract images
            if config.extract_images:
                images = self._extract_images(content)
                all_images.extend(images)

            # Extract hyperlinks
            if config.extract_links:
                hyperlinks = self._extract_hyperlinks(content)
                all_hyperlinks.extend(hyperlinks)

            # Combine all text content
            final_content = "\n".join(all_text)

            # Create document metadata
            doc_metadata = frontmatter if config.extract_metadata else {}

            # Parse document structure
            structure = self._structure_parser.parse_structure(content, frontmatter)

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(
                final_content, all_tables, all_images, frontmatter, start_time
            )

            # Create extraction metadata
            extraction_metadata = self._create_metadata(
                path_obj, start_time, doc_metadata, config
            )

            # Determine status
            status = self._determine_extraction_status(quality_metrics)

            return ExtractionResult(
                status=status,
                content=final_content,
                metadata=extraction_metadata,
                quality_metrics=quality_metrics,
                document_structure=structure,
                tables=all_tables,
                images=all_images,
                hyperlinks=all_hyperlinks
            )

        except Exception as e:
            self._logger.error(f"Failed to extract from Markdown content: {e}")

            error = ValidationError(
                field_name="markdown_processing",
                error_message=f"Markdown processing error: {str(e)}",
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

    def _convert_to_html(self, content: str, config: MarkdownExtractionConfig) -> str:
        """Convert Markdown to HTML using python-markdown."""
        try:
            md = markdown.Markdown(extensions=config.enable_extensions)
            html_content = md.convert(content)
            return html_content

        except Exception as e:
            self._logger.warning(f"Failed to convert Markdown to HTML: {e}")
            return content

    def _extract_tables(self, content: str) -> List[TableData]:
        """Extract tables from Markdown content."""
        tables = []

        try:
            # Pattern for Markdown tables
            table_pattern = r'(\|.+\|\s*\n\|[-\s|:]+\|\s*\n(?:\|.+\|\s*\n)*)'

            for i, match in enumerate(re.finditer(table_pattern, content, re.MULTILINE)):
                try:
                    table_text = match.group(1).strip()
                    lines = [line.strip() for line in table_text.split('\n') if line.strip()]

                    if len(lines) < 2:  # Need at least header and separator
                        continue

                    # Parse header row
                    header_line = lines[0]
                    headers = [cell.strip() for cell in header_line.split('|')[1:-1]]

                    # Skip separator line (lines[1])

                    # Parse data rows
                    rows = []
                    for line in lines[2:]:
                        if line.startswith('|') and line.endswith('|'):
                            row_data = [cell.strip() for cell in line.split('|')[1:-1]]
                            if len(row_data) == len(headers):  # Ensure consistent column count
                                rows.append(row_data)

                    if not rows:  # No valid data rows
                        continue

                    # Calculate confidence
                    confidence = self._calculate_table_confidence(headers, rows)

                    table_info = TableData(
                        headers=headers,
                        rows=rows,
                        confidence=confidence,
                        metadata={
                            'table_index': i,
                            'row_count': len(rows),
                            'column_count': len(headers),
                            'table_format': 'markdown'
                        }
                    )
                    tables.append(table_info)

                except Exception as e:
                    self._logger.warning(f"Failed to extract table {i}: {e}")
                    continue

        except Exception as e:
            self._logger.warning(f"Failed to extract tables: {e}")

        return tables

    def _extract_images(self, content: str) -> List[ImageData]:
        """Extract image references from Markdown content."""
        images = []

        try:
            # Pattern for Markdown images: ![alt text](url "title")
            image_pattern = r'!\[([^\]]*)\]\(([^)]+)(?:\s+"([^"]*)")?\)'

            for i, match in enumerate(re.finditer(image_pattern, content)):
                try:
                    alt_text = match.group(1)
                    src = match.group(2)
                    title = match.group(3) if match.group(3) else ""

                    # Generate image ID from src
                    import hashlib
                    image_id = hashlib.md5(src.encode()).hexdigest()[:16]

                    # Create ImageData (without actual image bytes for Markdown)
                    image_info = ImageData(
                        image_id=image_id,
                        image_data=b'',  # Markdown doesn't contain image data
                        format='unknown',
                        width=0,
                        height=0,
                        alt_text=alt_text,
                        caption=title,
                        metadata={
                            'src': src,
                            'image_index': i,
                            'markdown_syntax': match.group(0)
                        }
                    )
                    images.append(image_info)

                except Exception as e:
                    self._logger.warning(f"Failed to extract image {i}: {e}")
                    continue

        except Exception as e:
            self._logger.warning(f"Failed to extract images: {e}")

        return images

    def _extract_hyperlinks(self, content: str) -> List[Dict[str, str]]:
        """Extract hyperlinks from Markdown content."""
        hyperlinks = []

        try:
            # Pattern for Markdown links: [text](url "title")
            link_pattern = r'\[([^\]]+)\]\(([^)]+)(?:\s+"([^"]*)")?\)'

            for i, match in enumerate(re.finditer(link_pattern, content)):
                try:
                    text = match.group(1)
                    url = match.group(2)
                    title = match.group(3) if match.group(3) else ""

                    # Determine link type
                    link_type = 'external'
                    if url.startswith('#'):
                        link_type = 'internal'
                    elif url.startswith('mailto:'):
                        link_type = 'email'
                    elif url.startswith('tel:'):
                        link_type = 'phone'
                    elif not url.startswith(('http://', 'https://')):
                        link_type = 'relative'

                    hyperlinks.append({
                        'url': url,
                        'text': text,
                        'title': title,
                        'type': link_type,
                        'link_index': str(i),
                        'markdown_syntax': match.group(0)
                    })

                except Exception as e:
                    self._logger.warning(f"Failed to extract link {i}: {e}")
                    continue

        except Exception as e:
            self._logger.warning(f"Failed to extract hyperlinks: {e}")

        return hyperlinks

    def _calculate_table_confidence(self, headers: List[str], rows: List[List[str]]) -> float:
        """Calculate confidence score for extracted table."""
        if not headers or not rows:
            return 0.0

        # Check column consistency
        expected_cols = len(headers)
        consistent_rows = sum(1 for row in rows if len(row) == expected_cols)
        consistency_ratio = consistent_rows / len(rows) if rows else 0.0

        # Check for non-empty content
        total_cells = sum(len(row) for row in rows)
        non_empty_cells = sum(1 for row in rows for cell in row if cell.strip())
        fill_ratio = non_empty_cells / total_cells if total_cells > 0 else 0.0

        # Combine metrics
        confidence = (consistency_ratio * 0.6 + fill_ratio * 0.4)
        return confidence

    def _calculate_quality_metrics(self, content: str, tables: List[TableData],
                                 images: List[ImageData], frontmatter: Dict[str, Any],
                                 start_time: datetime) -> QualityMetrics:
        """Calculate quality metrics for extraction."""
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Text confidence based on content structure
        text_confidence = 0.0
        if content:
            # Check for Markdown structure indicators
            has_headings = bool(re.search(r'^#{1,6}\s+', content, re.MULTILINE))
            has_lists = bool(re.search(r'^[-*+]\s+', content, re.MULTILINE))
            has_code_blocks = bool(re.search(r'```', content))
            has_emphasis = bool(re.search(r'[*_]{1,2}[^*_]+[*_]{1,2}', content))

            structure_indicators = sum([has_headings, has_lists, has_code_blocks, has_emphasis])
            structure_score = min(1.0, structure_indicators / 4)

            word_count = len(content.split())
            length_score = min(1.0, word_count / 50)  # Normalize by expected minimum words

            text_confidence = (structure_score * 0.7 + length_score * 0.3)

        # Table confidence (average of all table confidences)
        table_confidence = 0.0
        if tables:
            table_confidence = sum(table.confidence for table in tables) / len(tables)

        # Image confidence (simple presence check)
        image_confidence = 1.0 if images else 0.0

        # Structure confidence based on frontmatter and headings
        structure_confidence = 0.3  # Base score
        if frontmatter:
            structure_confidence += 0.3
        if re.search(r'^#{1,3}\s+', content, re.MULTILINE):
            structure_confidence += 0.4

        structure_confidence = min(1.0, structure_confidence)

        # Overall confidence (weighted average)
        overall_confidence = (
            text_confidence * 0.5 +
            table_confidence * 0.2 +
            image_confidence * 0.1 +
            structure_confidence * 0.2
        )

        # Completeness score (Markdown extraction is typically complete)
        completeness_score = 95.0 if content else 0.0

        # Readability score
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
                        doc_metadata: Optional[Dict[str, Any]] = None,
                        config: Optional[MarkdownExtractionConfig] = None) -> ExtractionMetadata:
        """Create extraction metadata."""
        processing_duration = (datetime.now() - start_time).total_seconds() * 1000

        return ExtractionMetadata(
            document_format=DocumentFormat.MARKDOWN,
            file_size=path_obj.stat().st_size,
            extraction_timestamp=start_time,
            extractor_version="1.0.0",
            processing_duration_ms=processing_duration,
            extraction_config={
                'extract_text': config.extract_text if config else True,
                'extract_tables': config.extract_tables if config else True,
                'extract_images': config.extract_images if config else True,
                'extract_frontmatter': config.extract_frontmatter if config else True,
                'preserve_formatting': config.preserve_formatting if config else True
            },
            document_properties=doc_metadata or {},
            technical_metadata={
                'markdown_available': MARKDOWN_AVAILABLE,
                'yaml_available': YAML_AVAILABLE,
                'file_extension': path_obj.suffix.lower()
            }
        )

    def _determine_extraction_status(self, quality_metrics: QualityMetrics) -> ExtractionStatus:
        """Determine extraction status based on quality metrics."""
        if quality_metrics.overall_confidence >= self._config.quality_threshold:
            return ExtractionStatus.SUCCESS
        elif quality_metrics.overall_confidence > 0.0:
            return ExtractionStatus.PARTIAL_SUCCESS
        else:
            return ExtractionStatus.FAILED
