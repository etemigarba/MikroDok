"""
Module: html_extractor_lg
Description: Parses HTML content while maintaining semantic structure using BeautifulSoup
Phase: 3
Location: /src/modules/logic/document_extraction_lg/html_extractor_lg/html_extractor_lg.py
"""

# Standard library imports
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urljoin, urlparse

# Third-party imports
try:
    from bs4 import BeautifulSoup, Comment
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False

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
class HTMLExtractionConfig:
    """Configuration for HTML extraction."""
    extract_text: bool = True
    extract_tables: bool = True
    extract_images: bool = True
    extract_metadata: bool = True
    extract_links: bool = True
    extract_scripts: bool = False
    extract_styles: bool = False
    extract_comments: bool = False
    preserve_structure: bool = True
    convert_to_markdown: bool = False
    remove_empty_elements: bool = True
    base_url: Optional[str] = None  # For resolving relative URLs
    encoding: str = 'utf-8'
    parser: str = 'html.parser'  # 'html.parser', 'lxml', 'html5lib'
    quality_threshold: float = 0.5
    timeout_seconds: int = 300


class HTMLStructureParser:
    """Specialized structure parser for HTML documents."""
    
    def __init__(self, config: HTMLExtractionConfig):
        """Initialize structure parser."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def parse_structure(self, soup) -> DocumentStructure:
        """Parse document structure from HTML."""
        structure = DocumentStructure()
        
        try:
            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                structure.title = title_tag.get_text().strip()
            
            # Extract headings (h1-h6)
            headings = []
            for level in range(1, 7):
                heading_tags = soup.find_all(f'h{level}')
                for i, tag in enumerate(heading_tags):
                    text = tag.get_text().strip()
                    if text:
                        headings.append({
                            'text': text,
                            'level': level,
                            'tag_index': i,
                            'tag_name': f'h{level}',
                            'id': tag.get('id', ''),
                            'class': ' '.join(tag.get('class', []))
                        })
            
            structure.headings = headings
            
            # Extract sections based on semantic HTML5 elements
            sections = []
            semantic_tags = ['section', 'article', 'aside', 'nav', 'main', 'header', 'footer']
            
            for tag_name in semantic_tags:
                elements = soup.find_all(tag_name)
                for i, element in enumerate(elements):
                    text_content = element.get_text().strip()
                    if text_content:
                        sections.append({
                            'title': tag_name.title(),
                            'tag_name': tag_name,
                            'content_length': len(text_content),
                            'element_index': i,
                            'id': element.get('id', ''),
                            'class': ' '.join(element.get('class', []))
                        })
            
            structure.sections = sections
            
            # Calculate document statistics
            all_text = soup.get_text()
            structure.word_count = len(all_text.split()) if all_text else 0
            structure.character_count = len(all_text) if all_text else 0
            
            # Detect language
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                structure.language = html_tag.get('lang')
            
        except Exception as e:
            self._logger.warning(f"Failed to parse HTML structure: {e}")
        
        return structure


class HTMLMetadataExtractor:
    """Specialized metadata extractor for HTML documents."""
    
    def __init__(self, config: HTMLExtractionConfig):
        """Initialize metadata extractor."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def extract_metadata(self, soup) -> Dict[str, Any]:
        """Extract metadata from HTML document."""
        metadata = {}
        
        try:
            # Extract meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
                content = meta.get('content')
                
                if name and content:
                    # Normalize meta tag names
                    name = name.lower().replace('-', '_')
                    metadata[f'meta_{name}'] = content
            
            # Extract specific important meta tags
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text().strip()
            
            # Extract Open Graph and Twitter Card metadata
            og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
            for tag in og_tags:
                prop = tag.get('property', '').replace('og:', '')
                content = tag.get('content', '')
                if prop and content:
                    metadata[f'og_{prop}'] = content
            
            twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
            for tag in twitter_tags:
                name = tag.get('name', '').replace('twitter:', '')
                content = tag.get('content', '')
                if name and content:
                    metadata[f'twitter_{name}'] = content
            
            # Extract document structure information
            metadata.update({
                'heading_count': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                'paragraph_count': len(soup.find_all('p')),
                'link_count': len(soup.find_all('a')),
                'image_count': len(soup.find_all('img')),
                'table_count': len(soup.find_all('table')),
                'form_count': len(soup.find_all('form')),
                'script_count': len(soup.find_all('script')),
                'style_count': len(soup.find_all('style'))
            })
            
            # Extract language information
            html_tag = soup.find('html')
            if html_tag:
                lang = html_tag.get('lang')
                if lang:
                    metadata['language'] = lang
            
            # Extract charset information
            charset_meta = soup.find('meta', charset=True)
            if charset_meta:
                metadata['charset'] = charset_meta.get('charset')
            else:
                # Check for http-equiv charset
                charset_meta = soup.find('meta', {'http-equiv': 'Content-Type'})
                if charset_meta:
                    content = charset_meta.get('content', '')
                    charset_match = re.search(r'charset=([^;]+)', content)
                    if charset_match:
                        metadata['charset'] = charset_match.group(1)
            
        except Exception as e:
            self._logger.warning(f"Failed to extract HTML metadata: {e}")
        
        return metadata


class HTMLExtractor(IDocumentExtractor):
    """
    HTML document extractor using BeautifulSoup for comprehensive content extraction.

    Features:
    - Text extraction with semantic structure preservation
    - Table extraction with proper formatting
    - Image metadata extraction
    - Link extraction and URL resolution
    - Metadata extraction from meta tags
    - Support for malformed HTML
    - Optional conversion to Markdown
    """

    def __init__(self, config: Optional[HTMLExtractionConfig] = None):
        """Initialize HTML extractor."""
        self._config = config or HTMLExtractionConfig()
        self._logger = get_logger(__name__)
        self._structure_parser = HTMLStructureParser(self._config)
        self._metadata_extractor = HTMLMetadataExtractor(self._config)

        if not BEAUTIFULSOUP_AVAILABLE:
            raise ImportError("BeautifulSoup4 is required for HTML extraction")

    def extract(self, file_path: Union[str, Path], config: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract content from HTML document.

        Args:
            file_path: Path to the HTML file
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
            # Read HTML content
            with open(path_obj, 'r', encoding=extraction_config.encoding, errors='replace') as f:
                html_content = f.read()

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, extraction_config.parser)

            return self._extract_from_soup(soup, path_obj, start_time, extraction_config)

        except Exception as e:
            self._logger.error(f"HTML extraction failed for {file_path}: {e}")

            error = ValidationError(
                field_name="html_extraction",
                error_message=f"HTML extraction error: {str(e)}",
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
        return path_obj.suffix.lower() in ['.html', '.htm', '.xhtml']

    def get_supported_formats(self) -> List[DocumentFormat]:
        """Get list of supported document formats."""
        return [DocumentFormat.HTML, DocumentFormat.HTM]

    def validate_file(self, file_path: Union[str, Path]) -> List[ValidationError]:
        """Validate HTML file before extraction."""
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

        # Try to read and parse HTML to check for major issues
        if not errors:  # Only if no previous errors
            try:
                with open(path_obj, 'r', encoding=self._config.encoding, errors='replace') as f:
                    html_content = f.read()

                # Basic HTML validation
                if not html_content.strip():
                    errors.append(ValidationError(
                        field_name="html_content",
                        error_message="HTML file is empty",
                        severity="ERROR",
                        validation_type="CONTENT"
                    ))
                elif '<html' not in html_content.lower() and '<body' not in html_content.lower():
                    # Warning for files that might not be proper HTML
                    errors.append(ValidationError(
                        field_name="html_structure",
                        error_message="File may not contain valid HTML structure",
                        severity="WARNING",
                        validation_type="FORMAT"
                    ))

            except UnicodeDecodeError:
                errors.append(ValidationError(
                    field_name="html_encoding",
                    error_message=f"Cannot decode HTML file with encoding: {self._config.encoding}",
                    severity="ERROR",
                    validation_type="ENCODING"
                ))
            except Exception as e:
                errors.append(ValidationError(
                    field_name="html_integrity",
                    error_message=f"HTML file appears to be corrupted: {str(e)}",
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
                "extract_links": {"type": "boolean", "default": True},
                "preserve_structure": {"type": "boolean", "default": True},
                "convert_to_markdown": {"type": "boolean", "default": False},
                "remove_empty_elements": {"type": "boolean", "default": True},
                "base_url": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
                "parser": {
                    "type": "string",
                    "enum": ["html.parser", "lxml", "html5lib"],
                    "default": "html.parser"
                },
                "quality_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0}
            }
        }

    def estimate_processing_time(self, file_path: Union[str, Path]) -> float:
        """Estimate processing time for HTML document."""
        path_obj = Path(file_path)

        if not path_obj.exists():
            return 0.0

        try:
            file_size_mb = path_obj.stat().st_size / (1024 * 1024)

            # Base time estimates
            base_time = 0.1  # Base processing time
            size_time = file_size_mb * 0.02  # 0.02 seconds per MB

            # Additional time for complex operations
            table_time = 0.1 if self._config.extract_tables else 0.0
            link_time = 0.05 if self._config.extract_links else 0.0

            total_time = base_time + size_time + table_time + link_time

            return max(0.1, total_time)  # Minimum 0.1 seconds

        except Exception:
            return 1.0  # Fallback estimate

    def _merge_config(self, override_config: Dict[str, Any]) -> HTMLExtractionConfig:
        """Merge override configuration with default config."""
        config_dict = {
            'extract_text': override_config.get('extract_text', self._config.extract_text),
            'extract_tables': override_config.get('extract_tables', self._config.extract_tables),
            'extract_images': override_config.get('extract_images', self._config.extract_images),
            'extract_metadata': override_config.get('extract_metadata', self._config.extract_metadata),
            'extract_links': override_config.get('extract_links', self._config.extract_links),
            'preserve_structure': override_config.get('preserve_structure', self._config.preserve_structure),
            'convert_to_markdown': override_config.get('convert_to_markdown', self._config.convert_to_markdown),
            'remove_empty_elements': override_config.get('remove_empty_elements', self._config.remove_empty_elements),
            'base_url': override_config.get('base_url', self._config.base_url),
            'encoding': override_config.get('encoding', self._config.encoding),
            'parser': override_config.get('parser', self._config.parser),
            'quality_threshold': override_config.get('quality_threshold', self._config.quality_threshold)
        }

        return HTMLExtractionConfig(**config_dict)

    def _extract_from_soup(self, soup, path_obj: Path, start_time: datetime,
                          config: HTMLExtractionConfig) -> ExtractionResult:
        """Extract content from parsed HTML soup."""
        all_text = []
        all_tables = []
        all_images = []
        all_hyperlinks = []

        try:
            # Remove unwanted elements
            if config.remove_empty_elements:
                self._clean_soup(soup)

            # Extract main text content
            if config.extract_text:
                if config.convert_to_markdown and HTML2TEXT_AVAILABLE:
                    text_content = self._convert_to_markdown(soup)
                else:
                    text_content = self._extract_text_content(soup, config)

                if text_content:
                    all_text.append(text_content)

            # Extract tables
            if config.extract_tables:
                tables = self._extract_tables(soup)
                all_tables.extend(tables)

            # Extract images
            if config.extract_images:
                images = self._extract_images(soup, config)
                all_images.extend(images)

            # Extract hyperlinks
            if config.extract_links:
                hyperlinks = self._extract_hyperlinks(soup, config)
                all_hyperlinks.extend(hyperlinks)

            # Combine all text content
            content = "\n".join(all_text)

            # Extract document metadata
            doc_metadata = self._metadata_extractor.extract_metadata(soup) if config.extract_metadata else {}

            # Parse document structure
            structure = self._structure_parser.parse_structure(soup)

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(
                content, all_tables, all_images, soup, start_time
            )

            # Create extraction metadata
            extraction_metadata = self._create_metadata(
                path_obj, start_time, doc_metadata, config
            )

            # Determine status
            status = self._determine_extraction_status(quality_metrics)

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

        except Exception as e:
            self._logger.error(f"Failed to extract from HTML soup: {e}")

            error = ValidationError(
                field_name="html_processing",
                error_message=f"HTML processing error: {str(e)}",
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

    def _clean_soup(self, soup) -> None:
        """Clean soup by removing unwanted elements."""
        try:
            # Remove script and style elements
            for element in soup(['script', 'style', 'noscript']):
                element.decompose()

            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # Remove empty elements
            for element in soup.find_all():
                if not element.get_text().strip() and not element.find_all(['img', 'br', 'hr']):
                    element.decompose()

        except Exception as e:
            self._logger.warning(f"Failed to clean HTML soup: {e}")

    def _extract_text_content(self, soup, config: HTMLExtractionConfig) -> str:
        """Extract text content from HTML soup."""
        try:
            if config.preserve_structure:
                # Extract text with some structure preservation
                text_parts = []

                # Process headings
                for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    text = heading.get_text().strip()
                    if text:
                        level = int(heading.name[1])
                        text_parts.append(f"\n{'#' * level} {text}\n")

                # Process paragraphs
                for p in soup.find_all('p'):
                    text = p.get_text().strip()
                    if text:
                        text_parts.append(f"{text}\n")

                # Process lists
                for ul in soup.find_all(['ul', 'ol']):
                    for li in ul.find_all('li'):
                        text = li.get_text().strip()
                        if text:
                            text_parts.append(f"• {text}")
                    text_parts.append("")

                return '\n'.join(text_parts)
            else:
                # Simple text extraction
                return soup.get_text(separator=' ', strip=True)

        except Exception as e:
            self._logger.warning(f"Failed to extract text content: {e}")
            return ""

    def _convert_to_markdown(self, soup) -> str:
        """Convert HTML to Markdown using html2text."""
        try:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # Don't wrap lines

            return h.handle(str(soup))

        except Exception as e:
            self._logger.warning(f"Failed to convert HTML to Markdown: {e}")
            return soup.get_text(separator=' ', strip=True)

    def _extract_tables(self, soup) -> List[TableData]:
        """Extract tables from HTML soup."""
        tables = []

        try:
            for i, table in enumerate(soup.find_all('table')):
                try:
                    # Extract table data
                    table_data = []

                    # Process table rows
                    rows = table.find_all('tr')
                    for row in rows:
                        row_data = []
                        cells = row.find_all(['td', 'th'])
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            row_data.append(cell_text)

                        if row_data:  # Only add non-empty rows
                            table_data.append(row_data)

                    if not table_data:
                        continue

                    # Determine headers (first row or th elements)
                    headers = table_data[0] if table_data else []
                    rows_data = table_data[1:] if len(table_data) > 1 else []

                    # Check if first row contains th elements (proper headers)
                    first_row = table.find('tr')
                    if first_row and first_row.find_all('th'):
                        # First row has th elements, use as headers
                        pass
                    elif len(table_data) > 1:
                        # Use first row as headers only if it looks different from data rows
                        pass
                    else:
                        # Single row table, treat as data
                        headers = []
                        rows_data = table_data

                    # Calculate confidence
                    confidence = self._calculate_table_confidence(table_data)

                    # Extract table caption
                    caption = None
                    caption_tag = table.find('caption')
                    if caption_tag:
                        caption = caption_tag.get_text().strip()

                    table_info = TableData(
                        headers=headers,
                        rows=rows_data,
                        caption=caption,
                        confidence=confidence,
                        metadata={
                            'table_index': i,
                            'row_count': len(rows_data),
                            'column_count': len(headers) if headers else (len(rows_data[0]) if rows_data else 0),
                            'has_thead': bool(table.find('thead')),
                            'has_tbody': bool(table.find('tbody')),
                            'has_tfoot': bool(table.find('tfoot')),
                            'table_id': table.get('id', ''),
                            'table_class': ' '.join(table.get('class', []))
                        }
                    )
                    tables.append(table_info)

                except Exception as e:
                    self._logger.warning(f"Failed to extract table {i}: {e}")
                    continue

        except Exception as e:
            self._logger.warning(f"Failed to extract tables: {e}")

        return tables

    def _extract_images(self, soup, config: HTMLExtractionConfig) -> List[ImageData]:
        """Extract image metadata from HTML soup."""
        images = []

        try:
            for i, img in enumerate(soup.find_all('img')):
                try:
                    src = img.get('src', '')
                    if not src:
                        continue

                    # Resolve relative URLs if base_url is provided
                    if config.base_url and not src.startswith(('http://', 'https://', 'data:')):
                        src = urljoin(config.base_url, src)

                    # Extract image attributes
                    alt_text = img.get('alt', '')
                    title = img.get('title', '')
                    width = img.get('width', '')
                    height = img.get('height', '')

                    # Generate image ID from src
                    image_id = hashlib.md5(src.encode()).hexdigest()[:16]

                    # Create ImageData (without actual image bytes for HTML)
                    image_info = ImageData(
                        image_id=image_id,
                        image_data=b'',  # HTML doesn't contain image data
                        format='unknown',
                        width=int(width) if width.isdigit() else 0,
                        height=int(height) if height.isdigit() else 0,
                        alt_text=alt_text,
                        caption=title,
                        metadata={
                            'src': src,
                            'image_index': i,
                            'img_id': img.get('id', ''),
                            'img_class': ' '.join(img.get('class', [])),
                            'loading': img.get('loading', ''),
                            'srcset': img.get('srcset', '')
                        }
                    )
                    images.append(image_info)

                except Exception as e:
                    self._logger.warning(f"Failed to extract image {i}: {e}")
                    continue

        except Exception as e:
            self._logger.warning(f"Failed to extract images: {e}")

        return images

    def _extract_hyperlinks(self, soup, config: HTMLExtractionConfig) -> List[Dict[str, str]]:
        """Extract hyperlinks from HTML soup."""
        hyperlinks = []

        try:
            for i, link in enumerate(soup.find_all('a')):
                try:
                    href = link.get('href', '')
                    if not href:
                        continue

                    # Resolve relative URLs if base_url is provided
                    if config.base_url and not href.startswith(('http://', 'https://', 'mailto:', 'tel:', '#')):
                        href = urljoin(config.base_url, href)

                    text = link.get_text().strip()
                    title = link.get('title', '')

                    # Determine link type
                    link_type = 'external'
                    if href.startswith('#'):
                        link_type = 'internal'
                    elif href.startswith('mailto:'):
                        link_type = 'email'
                    elif href.startswith('tel:'):
                        link_type = 'phone'
                    elif config.base_url and href.startswith(config.base_url):
                        link_type = 'internal'

                    hyperlinks.append({
                        'url': href,
                        'text': text,
                        'title': title,
                        'type': link_type,
                        'link_index': str(i),
                        'target': link.get('target', ''),
                        'rel': ' '.join(link.get('rel', []))
                    })

                except Exception as e:
                    self._logger.warning(f"Failed to extract link {i}: {e}")
                    continue

        except Exception as e:
            self._logger.warning(f"Failed to extract hyperlinks: {e}")

        return hyperlinks

    def _calculate_table_confidence(self, table_data: List[List[str]]) -> float:
        """Calculate confidence score for extracted table."""
        if not table_data:
            return 0.0

        total_cells = sum(len(row) for row in table_data)
        if total_cells == 0:
            return 0.0

        # Count non-empty cells
        non_empty_cells = sum(1 for row in table_data for cell in row if cell.strip())

        # Calculate fill ratio
        fill_ratio = non_empty_cells / total_cells

        # Bonus for consistent column count
        column_counts = [len(row) for row in table_data]
        consistency_bonus = 0.2 if len(set(column_counts)) == 1 else 0.0

        confidence = min(1.0, fill_ratio + consistency_bonus)
        return confidence

    def _calculate_quality_metrics(self, content: str, tables: List[TableData],
                                 images: List[ImageData], soup,
                                 start_time: datetime) -> QualityMetrics:
        """Calculate quality metrics for extraction."""
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Text confidence based on content structure
        text_confidence = 0.0
        if content:
            # Check for proper HTML structure indicators
            has_headings = bool(soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
            has_paragraphs = bool(soup.find('p'))
            has_semantic_tags = bool(soup.find(['article', 'section', 'nav', 'main']))

            structure_score = sum([has_headings, has_paragraphs, has_semantic_tags]) / 3

            word_count = len(content.split())
            length_score = min(1.0, word_count / 100)  # Normalize by expected minimum words

            text_confidence = (structure_score * 0.6 + length_score * 0.4)

        # Table confidence (average of all table confidences)
        table_confidence = 0.0
        if tables:
            table_confidence = sum(table.confidence for table in tables) / len(tables)

        # Image confidence based on proper alt text and metadata
        image_confidence = 0.0
        if images:
            images_with_alt = sum(1 for img in images if img.alt_text)
            image_confidence = images_with_alt / len(images)

        # Structure confidence based on HTML semantic structure
        structure_confidence = 0.5  # Base score
        if soup.find('title'):
            structure_confidence += 0.1
        if soup.find(['h1', 'h2', 'h3']):
            structure_confidence += 0.2
        if soup.find(['article', 'section', 'main']):
            structure_confidence += 0.2

        structure_confidence = min(1.0, structure_confidence)

        # Overall confidence (weighted average)
        overall_confidence = (
            text_confidence * 0.5 +
            table_confidence * 0.2 +
            image_confidence * 0.1 +
            structure_confidence * 0.2
        )

        # Completeness score (HTML extraction is typically complete)
        completeness_score = 90.0 if content else 0.0

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
                        config: Optional[HTMLExtractionConfig] = None) -> ExtractionMetadata:
        """Create extraction metadata."""
        processing_duration = (datetime.now() - start_time).total_seconds() * 1000

        return ExtractionMetadata(
            document_format=DocumentFormat.HTML,
            file_size=path_obj.stat().st_size,
            extraction_timestamp=start_time,
            extractor_version="1.0.0",
            processing_duration_ms=processing_duration,
            extraction_config={
                'extract_text': config.extract_text if config else True,
                'extract_tables': config.extract_tables if config else True,
                'extract_images': config.extract_images if config else True,
                'extract_links': config.extract_links if config else True,
                'preserve_structure': config.preserve_structure if config else True,
                'parser': config.parser if config else 'html.parser'
            },
            document_properties=doc_metadata or {},
            technical_metadata={
                'beautifulsoup_available': BEAUTIFULSOUP_AVAILABLE,
                'html2text_available': HTML2TEXT_AVAILABLE,
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
