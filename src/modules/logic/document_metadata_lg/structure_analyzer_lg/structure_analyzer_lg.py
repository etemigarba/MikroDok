"""
Module: structure_analyzer_lg
Description: Analyzes document structure including headers, sections, and hierarchical organization
Phase: 3
Location: /src/modules/logic/document_metadata_lg/structure_analyzer_lg/structure_analyzer_lg.py
"""

# Standard library imports
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

# Third-party imports
# None required for basic structure analysis

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IStructureAnalyzer,
    DocumentStructure,
    StructureElement,
    StructureAnalysisResult,
    StructureAnalysisConfig,
    StructureType,
    ExtractionStatus
)


class HeaderAnalyzer:
    """Analyzes headers and their hierarchical levels in documents."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        
        # Header patterns for different formats
        self._markdown_header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self._html_header_pattern = re.compile(r'<h([1-6])[^>]*>(.*?)</h[1-6]>', re.IGNORECASE | re.DOTALL)
        self._text_header_patterns = [
            re.compile(r'^([A-Z][A-Z\s]{2,})\s*$', re.MULTILINE),  # ALL CAPS headers
            re.compile(r'^(\d+\.?\s+[A-Z][^.!?]*)\s*$', re.MULTILINE),  # Numbered headers
            re.compile(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*$', re.MULTILINE)  # Title Case headers
        ]
    
    def analyze_markdown_headers(self, content: str) -> List[StructureElement]:
        """Analyze headers in Markdown content."""
        headers = []
        
        try:
            for match in self._markdown_header_pattern.finditer(content):
                level = len(match.group(1))  # Number of # symbols
                title = match.group(2).strip()
                start_pos = match.start()
                
                element = StructureElement(
                    element_type=StructureType.HEADING,
                    level=level,
                    title=title,
                    start_position=start_pos,
                    element_id=str(uuid.uuid4())
                )
                headers.append(element)
        
        except Exception as e:
            self._logger.error(f"Failed to analyze Markdown headers: {e}")
        
        return headers
    
    def analyze_html_headers(self, content: str) -> List[StructureElement]:
        """Analyze headers in HTML content."""
        headers = []
        
        try:
            for match in self._html_header_pattern.finditer(content):
                level = int(match.group(1))
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()  # Remove HTML tags
                start_pos = match.start()
                
                element = StructureElement(
                    element_type=StructureType.HEADING,
                    level=level,
                    title=title,
                    start_position=start_pos,
                    element_id=str(uuid.uuid4())
                )
                headers.append(element)
        
        except Exception as e:
            self._logger.error(f"Failed to analyze HTML headers: {e}")
        
        return headers
    
    def analyze_text_headers(self, content: str) -> List[StructureElement]:
        """Analyze headers in plain text content."""
        headers = []
        
        try:
            lines = content.splitlines()
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Check various header patterns
                level = self._determine_text_header_level(line, lines, i)
                if level > 0:
                    start_pos = content.find(line)
                    
                    element = StructureElement(
                        element_type=StructureType.HEADING,
                        level=level,
                        title=line,
                        start_position=start_pos,
                        element_id=str(uuid.uuid4())
                    )
                    headers.append(element)
        
        except Exception as e:
            self._logger.error(f"Failed to analyze text headers: {e}")
        
        return headers
    
    def _determine_text_header_level(self, line: str, lines: List[str], index: int) -> int:
        """Determine if a line is a header and its level."""
        # Check for numbered headers (1., 1.1., etc.)
        numbered_match = re.match(r'^(\d+(?:\.\d+)*)\.\s+', line)
        if numbered_match:
            depth = numbered_match.group(1).count('.') + 1
            return min(depth, 6)
        
        # Check for ALL CAPS (likely header)
        if line.isupper() and len(line) > 3 and len(line) < 100:
            return 1
        
        # Check for title case with reasonable length
        if (line.istitle() and len(line) > 5 and len(line) < 100 and 
            not line.endswith('.') and not line.endswith(',')):
            
            # Check if next line is empty or different format (indicates header)
            if index + 1 < len(lines):
                next_line = lines[index + 1].strip()
                if not next_line or not next_line[0].isupper():
                    return 2
        
        # Check for underlined headers
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if next_line and all(c in '=-_~' for c in next_line) and len(next_line) >= len(line) * 0.8:
                return 1 if next_line[0] == '=' else 2
        
        return 0


class SectionDetector:
    """Detects sections and their boundaries in documents."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def detect_sections(self, content: str, headers: List[StructureElement]) -> List[StructureElement]:
        """Detect sections based on headers and content structure."""
        sections = []
        
        try:
            if not headers:
                # Create a single section for the entire document
                section = StructureElement(
                    element_type=StructureType.SECTION,
                    level=1,
                    title="Document",
                    content=content,
                    start_position=0,
                    end_position=len(content),
                    element_id=str(uuid.uuid4())
                )
                sections.append(section)
                return sections
            
            # Sort headers by position
            sorted_headers = sorted(headers, key=lambda h: h.start_position or 0)
            
            for i, header in enumerate(sorted_headers):
                start_pos = header.start_position or 0
                
                # Determine end position
                if i + 1 < len(sorted_headers):
                    end_pos = sorted_headers[i + 1].start_position or len(content)
                else:
                    end_pos = len(content)
                
                # Extract section content
                section_content = content[start_pos:end_pos].strip()
                
                section = StructureElement(
                    element_type=StructureType.SECTION,
                    level=header.level,
                    title=header.title,
                    content=section_content,
                    start_position=start_pos,
                    end_position=end_pos,
                    element_id=str(uuid.uuid4()),
                    parent_id=self._find_parent_section(header, sorted_headers[:i])
                )
                sections.append(section)
        
        except Exception as e:
            self._logger.error(f"Failed to detect sections: {e}")
        
        return sections
    
    def _find_parent_section(self, current_header: StructureElement, 
                           previous_headers: List[StructureElement]) -> Optional[str]:
        """Find the parent section for a header."""
        try:
            # Look for the most recent header with a lower level (higher in hierarchy)
            for header in reversed(previous_headers):
                if header.level < current_header.level:
                    return header.element_id
            return None
        except Exception:
            return None


class HierarchyParser:
    """Parses hierarchical structure from document elements."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def build_hierarchy(self, elements: List[StructureElement]) -> StructureElement:
        """Build hierarchical structure from flat list of elements."""
        try:
            if not elements:
                return StructureElement(
                    element_type=StructureType.DOCUMENT,
                    level=0,
                    title="Empty Document",
                    element_id=str(uuid.uuid4())
                )
            
            # Create root element
            root = StructureElement(
                element_type=StructureType.DOCUMENT,
                level=0,
                title="Document",
                element_id=str(uuid.uuid4())
            )
            
            # Sort elements by position and level
            sorted_elements = sorted(elements, key=lambda e: (e.start_position or 0, e.level))
            
            # Build parent-child relationships
            element_stack = [root]
            
            for element in sorted_elements:
                # Find appropriate parent
                while (len(element_stack) > 1 and 
                       element_stack[-1].level >= element.level):
                    element_stack.pop()
                
                # Set parent relationship
                parent = element_stack[-1]
                element.parent_id = parent.element_id
                parent.children.append(element)
                
                # Add to stack if it can have children
                if element.element_type in [StructureType.SECTION, StructureType.CHAPTER, StructureType.HEADING]:
                    element_stack.append(element)
            
            return root
        
        except Exception as e:
            self._logger.error(f"Failed to build hierarchy: {e}")
            return StructureElement(
                element_type=StructureType.DOCUMENT,
                level=0,
                title="Document",
                element_id=str(uuid.uuid4())
            )
    
    def calculate_hierarchy_depth(self, root: StructureElement) -> int:
        """Calculate the maximum depth of the hierarchy."""
        try:
            def get_depth(element: StructureElement) -> int:
                if not element.children:
                    return element.level
                return max(get_depth(child) for child in element.children)
            
            return get_depth(root)
        except Exception:
            return 0
    
    def flatten_hierarchy(self, root: StructureElement) -> List[StructureElement]:
        """Flatten hierarchical structure to a list."""
        try:
            elements = []
            
            def traverse(element: StructureElement):
                elements.append(element)
                for child in element.children:
                    traverse(child)
            
            traverse(root)
            return elements[1:]  # Exclude root document element
        
        except Exception as e:
            self._logger.error(f"Failed to flatten hierarchy: {e}")
            return []


class StructureAnalyzer(IStructureAnalyzer):
    """
    Main structure analyzer that analyzes document structure including headers, sections, and hierarchical organization.

    Features:
    - Header detection and level analysis
    - Section boundary detection
    - Hierarchical structure parsing
    - Multi-format support (Markdown, HTML, plain text)
    - Table of contents extraction
    - List and table detection
    - Confidence scoring and validation
    """

    def __init__(self, config: Optional[StructureAnalysisConfig] = None):
        """Initialize structure analyzer."""
        self._config = config or StructureAnalysisConfig()
        self._logger = get_logger(__name__)
        self._header_analyzer = HeaderAnalyzer()
        self._section_detector = SectionDetector()
        self._hierarchy_parser = HierarchyParser()

    def analyze_structure(self, file_path: Path, content: Optional[str] = None) -> StructureAnalysisResult:
        """
        Analyze the structure of a document.

        Args:
            file_path: Path to the document file
            content: Optional pre-extracted content

        Returns:
            StructureAnalysisResult with document structure
        """
        start_time = time.time()
        errors = []
        warnings = []
        detected_elements = []
        confidence_scores = {}

        try:
            # Read content if not provided
            if content is None:
                content = self._read_file_content(file_path)

            if not content:
                raise ValueError("No content available for analysis")

            # Analyze headers
            headers = []
            if self._config.analyze_headers:
                headers = self._analyze_headers_by_format(file_path, content)
                if headers:
                    detected_elements.append(StructureType.HEADING)
                    confidence_scores['headers'] = self._calculate_header_confidence(headers, content)

            # Detect sections
            sections = []
            if self._config.detect_sections:
                sections = self._section_detector.detect_sections(content, headers)
                if sections:
                    detected_elements.append(StructureType.SECTION)
                    confidence_scores['sections'] = 0.8

            # Detect other structural elements
            if self._config.detect_lists:
                lists = self._detect_lists(content)
                if lists:
                    detected_elements.append(StructureType.LIST)
                    confidence_scores['lists'] = 0.7

            if self._config.analyze_tables:
                tables = self._detect_tables(content)
                if tables:
                    detected_elements.append(StructureType.TABLE)
                    confidence_scores['tables'] = 0.6

            # Build hierarchical structure
            all_elements = headers + sections
            if self._config.analyze_hierarchy and all_elements:
                root_element = self._hierarchy_parser.build_hierarchy(all_elements)
                hierarchy_depth = self._hierarchy_parser.calculate_hierarchy_depth(root_element)

                # Validate hierarchy depth
                if hierarchy_depth > self._config.max_depth:
                    warnings.append(f"Hierarchy depth ({hierarchy_depth}) exceeds maximum ({self._config.max_depth})")
                    hierarchy_depth = self._config.max_depth
            else:
                # Create simple root structure
                root_element = StructureElement(
                    element_type=StructureType.DOCUMENT,
                    level=0,
                    title=file_path.stem,
                    content=content[:500] + "..." if len(content) > 500 else content,
                    element_id=str(uuid.uuid4())
                )
                hierarchy_depth = 1

            # Create document structure
            structure = DocumentStructure(
                root_element=root_element,
                elements=all_elements,
                hierarchy_depth=hierarchy_depth,
                total_elements=len(all_elements),
                structure_confidence=sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.5
            )

            processing_duration = (time.time() - start_time) * 1000

            return StructureAnalysisResult(
                status=ExtractionStatus.SUCCESS if not errors else ExtractionStatus.PARTIAL,
                structure=structure,
                analysis_duration_ms=processing_duration,
                errors=errors,
                warnings=warnings,
                detected_elements=detected_elements,
                confidence_scores=confidence_scores
            )

        except Exception as e:
            self._logger.error(f"Structure analysis failed: {e}")
            processing_duration = (time.time() - start_time) * 1000

            return StructureAnalysisResult(
                status=ExtractionStatus.FAILED,
                structure=DocumentStructure(
                    root_element=StructureElement(
                        element_type=StructureType.DOCUMENT,
                        level=0,
                        title="Failed Analysis",
                        element_id=str(uuid.uuid4())
                    )
                ),
                analysis_duration_ms=processing_duration,
                errors=[str(e)],
                warnings=warnings,
                detected_elements=[],
                confidence_scores={}
            )

    def extract_hierarchy(self, content: str) -> List[StructureElement]:
        """
        Extract hierarchical structure from document content.

        Args:
            content: Document content to analyze

        Returns:
            List of structure elements in hierarchical order
        """
        try:
            # Analyze headers first
            headers = self._analyze_headers_by_format(Path("unknown.txt"), content)

            # Build hierarchy
            if headers:
                root = self._hierarchy_parser.build_hierarchy(headers)
                return self._hierarchy_parser.flatten_hierarchy(root)
            else:
                return []

        except Exception as e:
            self._logger.error(f"Hierarchy extraction failed: {e}")
            return []

    def detect_sections(self, content: str) -> List[StructureElement]:
        """
        Detect sections and their boundaries in document content.

        Args:
            content: Document content to analyze

        Returns:
            List of detected sections
        """
        try:
            # First analyze headers
            headers = self._analyze_headers_by_format(Path("unknown.txt"), content)

            # Then detect sections based on headers
            return self._section_detector.detect_sections(content, headers)

        except Exception as e:
            self._logger.error(f"Section detection failed: {e}")
            return []

    def analyze_headers(self, content: str) -> List[StructureElement]:
        """
        Analyze headers and their levels in document content.

        Args:
            content: Document content to analyze

        Returns:
            List of detected headers with their levels
        """
        try:
            return self._analyze_headers_by_format(Path("unknown.txt"), content)

        except Exception as e:
            self._logger.error(f"Header analysis failed: {e}")
            return []

    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content with encoding detection."""
        try:
            # Try UTF-8 first
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                # Fallback to other encodings
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            return f.read()
                    except UnicodeDecodeError:
                        continue

                # Last resort: read as binary and decode with errors='ignore'
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

        except Exception as e:
            self._logger.error(f"Failed to read file content: {e}")
            return None

    def _analyze_headers_by_format(self, file_path: Path, content: str) -> List[StructureElement]:
        """Analyze headers based on file format."""
        try:
            file_ext = file_path.suffix.lower()

            if file_ext == '.md':
                return self._header_analyzer.analyze_markdown_headers(content)
            elif file_ext in ['.html', '.htm']:
                return self._header_analyzer.analyze_html_headers(content)
            else:
                return self._header_analyzer.analyze_text_headers(content)

        except Exception as e:
            self._logger.error(f"Format-specific header analysis failed: {e}")
            return []

    def _calculate_header_confidence(self, headers: List[StructureElement], content: str) -> float:
        """Calculate confidence score for header detection."""
        try:
            if not headers:
                return 0.0

            # Factors that increase confidence:
            # 1. Reasonable number of headers relative to content length
            # 2. Consistent level progression
            # 3. Headers have reasonable titles

            content_length = len(content)
            header_count = len(headers)

            # Reasonable header density (1 header per 500-2000 characters)
            density_score = 1.0
            if content_length > 0:
                density = content_length / header_count
                if 500 <= density <= 2000:
                    density_score = 1.0
                elif density < 500:
                    density_score = 0.7  # Too many headers
                else:
                    density_score = 0.8  # Too few headers

            # Level consistency (headers should have reasonable level progression)
            level_score = 1.0
            if len(headers) > 1:
                level_jumps = 0
                for i in range(1, len(headers)):
                    level_diff = headers[i].level - headers[i-1].level
                    if level_diff > 2:  # Jumping more than 2 levels
                        level_jumps += 1

                level_score = max(0.5, 1.0 - (level_jumps / len(headers)))

            # Title quality (headers should have reasonable titles)
            title_score = 1.0
            valid_titles = sum(1 for h in headers if h.title and 5 <= len(h.title) <= 100)
            if headers:
                title_score = valid_titles / len(headers)

            return (density_score + level_score + title_score) / 3

        except Exception as e:
            self._logger.error(f"Failed to calculate header confidence: {e}")
            return 0.5

    def _detect_lists(self, content: str) -> List[StructureElement]:
        """Detect list structures in content."""
        lists = []

        try:
            lines = content.splitlines()
            current_list = None
            list_items = []

            for i, line in enumerate(lines):
                line = line.strip()

                # Check for list indicators
                list_match = re.match(r'^([•\-\*]|\d+\.)\s+(.+)', line)
                if list_match:
                    if current_list is None:
                        # Start new list
                        current_list = {
                            'start_line': i,
                            'type': 'ordered' if list_match.group(1).endswith('.') else 'unordered',
                            'items': []
                        }

                    # Add item to current list
                    item = StructureElement(
                        element_type=StructureType.LIST_ITEM,
                        level=1,
                        title=list_match.group(2),
                        start_position=content.find(line),
                        element_id=str(uuid.uuid4())
                    )
                    current_list['items'].append(item)

                elif current_list and (not line or not line[0].isspace()):
                    # End current list
                    if len(current_list['items']) >= 2:  # At least 2 items to be a list
                        list_element = StructureElement(
                            element_type=StructureType.LIST,
                            level=1,
                            title=f"{current_list['type'].title()} List",
                            children=current_list['items'],
                            element_id=str(uuid.uuid4())
                        )
                        lists.append(list_element)

                    current_list = None

            # Handle list at end of document
            if current_list and len(current_list['items']) >= 2:
                list_element = StructureElement(
                    element_type=StructureType.LIST,
                    level=1,
                    title=f"{current_list['type'].title()} List",
                    children=current_list['items'],
                    element_id=str(uuid.uuid4())
                )
                lists.append(list_element)

        except Exception as e:
            self._logger.error(f"Failed to detect lists: {e}")

        return lists

    def _detect_tables(self, content: str) -> List[StructureElement]:
        """Detect table structures in content."""
        tables = []

        try:
            # Look for markdown-style tables
            table_pattern = re.compile(r'^\|.+\|$', re.MULTILINE)
            table_matches = list(table_pattern.finditer(content))

            if len(table_matches) >= 2:  # At least header and one data row
                # Group consecutive table rows
                current_table_rows = []

                for match in table_matches:
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_end = content.find('\n', match.end())
                    if line_end == -1:
                        line_end = len(content)

                    if not current_table_rows or line_start - current_table_rows[-1][1] <= 2:
                        current_table_rows.append((line_start, line_end))
                    else:
                        # Create table from current rows
                        if len(current_table_rows) >= 2:
                            table = self._create_table_element(content, current_table_rows)
                            if table:
                                tables.append(table)
                        current_table_rows = [(line_start, line_end)]

                # Handle last table
                if len(current_table_rows) >= 2:
                    table = self._create_table_element(content, current_table_rows)
                    if table:
                        tables.append(table)

        except Exception as e:
            self._logger.error(f"Failed to detect tables: {e}")

        return tables

    def _create_table_element(self, content: str, row_positions: List[Tuple[int, int]]) -> Optional[StructureElement]:
        """Create a table element from row positions."""
        try:
            if not row_positions:
                return None

            start_pos = row_positions[0][0]
            end_pos = row_positions[-1][1]
            table_content = content[start_pos:end_pos]

            # Count columns from first row
            first_row = content[row_positions[0][0]:row_positions[0][1]]
            column_count = first_row.count('|') - 1  # Subtract 1 for leading/trailing |

            return StructureElement(
                element_type=StructureType.TABLE,
                level=1,
                title=f"Table ({len(row_positions)} rows, {column_count} columns)",
                content=table_content,
                start_position=start_pos,
                end_position=end_pos,
                element_id=str(uuid.uuid4()),
                attributes={
                    'row_count': len(row_positions),
                    'column_count': column_count
                }
            )

        except Exception as e:
            self._logger.error(f"Failed to create table element: {e}")
            return None
