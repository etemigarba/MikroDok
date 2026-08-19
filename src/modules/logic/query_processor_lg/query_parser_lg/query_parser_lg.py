"""
Module: query_parser_lg
Description: Parses user queries, extracts special operators and filters
Phase: 4
Location: /src/modules/logic/query_processor_lg/query_parser_lg/query_parser_lg.py
"""

# Standard library imports
import re
import time
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional, Set, Tuple

# Third-party imports
import logging

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IQueryParser,
    QueryType,
    QueryOperator,
    FieldType,
    QueryStatus,
    QueryFilter,
    QueryTerm,
    ParsedQuery,
    QueryParsingConfig
)


class FilterParser:
    """Handles parsing of query filters and field-specific searches."""
    
    def __init__(self):
        """Initialize filter parser."""
        self._logger = get_logger(__name__)
        
        # Field mapping patterns
        self._field_patterns = {
            FieldType.TITLE: [r'title:', r't:'],
            FieldType.CONTENT: [r'content:', r'c:', r'body:'],
            FieldType.AUTHOR: [r'author:', r'a:', r'by:'],
            FieldType.TAGS: [r'tags:', r'tag:', r'labels:'],
            FieldType.METADATA: [r'meta:', r'metadata:'],
            FieldType.DATE_CREATED: [r'created:', r'date:', r'from:'],
            FieldType.DATE_MODIFIED: [r'modified:', r'updated:', r'changed:'],
            FieldType.FILE_TYPE: [r'type:', r'format:', r'ext:'],
            FieldType.LANGUAGE: [r'lang:', r'language:']
        }
        
        # Operator patterns
        self._operator_patterns = {
            '>=': r'>=',
            '<=': r'<=',
            '!=': r'!=|<>',
            '>': r'>',
            '<': r'<',
            '=': r'=|:',
            'CONTAINS': r'contains|~',
            'STARTS_WITH': r'starts_with|\^',
            'ENDS_WITH': r'ends_with|\$',
            'IN': r'in\s*\(',
            'NOT_IN': r'not_in\s*\('
        }
    
    def parse_filters(self, query: str) -> Tuple[List[QueryFilter], str]:
        """
        Parse filters from query string.
        
        Args:
            query: Query string to parse
            
        Returns:
            Tuple of (filters, remaining_query)
        """
        filters = []
        remaining_query = query
        
        try:
            # Parse field-specific filters
            for field_type, patterns in self._field_patterns.items():
                for pattern in patterns:
                    filter_pattern = rf'({pattern})\s*([^\s]+(?:\s+[^\s]+)*?)(?:\s|$)'
                    matches = re.finditer(filter_pattern, remaining_query, re.IGNORECASE)
                    
                    for match in matches:
                        field_prefix = match.group(1)
                        field_value = match.group(2).strip()
                        
                        # Parse operator and value
                        operator, value = self._parse_operator_value(field_value)
                        
                        # Create filter
                        query_filter = QueryFilter(
                            field=field_type,
                            operator=operator,
                            value=self._convert_value(value, field_type),
                            case_sensitive=False,
                            exact_match=(operator == '=')
                        )
                        filters.append(query_filter)
                        
                        # Remove from remaining query
                        remaining_query = remaining_query.replace(match.group(0), ' ', 1)
            
            # Clean up remaining query
            remaining_query = re.sub(r'\s+', ' ', remaining_query).strip()
            
            return filters, remaining_query
            
        except Exception as e:
            self._logger.error(f"Error parsing filters: {e}")
            return [], query
    
    def _parse_operator_value(self, field_value: str) -> Tuple[str, str]:
        """Parse operator and value from field value string."""
        for operator, pattern in self._operator_patterns.items():
            match = re.search(pattern, field_value, re.IGNORECASE)
            if match:
                # Split on operator
                parts = re.split(pattern, field_value, 1, re.IGNORECASE)
                if len(parts) == 2:
                    return operator, parts[1].strip()
        
        # Default to contains if no operator found
        return 'CONTAINS', field_value
    
    def _convert_value(self, value: str, field_type: FieldType) -> Any:
        """Convert string value to appropriate type based on field type."""
        try:
            if field_type in [FieldType.DATE_CREATED, FieldType.DATE_MODIFIED]:
                # Try to parse as date
                for date_format in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']:
                    try:
                        return datetime.strptime(value, date_format)
                    except ValueError:
                        continue
                return value  # Return as string if parsing fails
            
            # Try to convert to number if it looks like one
            if re.match(r'^-?\d+$', value):
                return int(value)
            elif re.match(r'^-?\d*\.\d+$', value):
                return float(value)
            
            # Handle list values (comma-separated)
            if ',' in value:
                return [item.strip() for item in value.split(',')]
            
            return value
            
        except Exception:
            return value


class OperatorParser:
    """Handles parsing of boolean and logical operators."""
    
    def __init__(self):
        """Initialize operator parser."""
        self._logger = get_logger(__name__)
        
        # Operator patterns (order matters for precedence)
        self._operator_patterns = [
            (QueryOperator.NOT, [r'\bNOT\b', r'-', r'!']),
            (QueryOperator.AND, [r'\bAND\b', r'\+', r'&']),
            (QueryOperator.OR, [r'\bOR\b', r'\|']),
            (QueryOperator.NEAR, [r'\bNEAR\b', r'~']),
            (QueryOperator.WITHIN, [r'\bWITHIN\b']),
            (QueryOperator.BEFORE, [r'\bBEFORE\b']),
            (QueryOperator.AFTER, [r'\bAFTER\b'])
        ]
    
    def parse_operators(self, query: str) -> Tuple[List[QueryOperator], str]:
        """
        Parse operators from query string.
        
        Args:
            query: Query string to parse
            
        Returns:
            Tuple of (operators, query_without_operators)
        """
        operators = []
        processed_query = query
        
        try:
            for operator, patterns in self._operator_patterns:
                for pattern in patterns:
                    matches = list(re.finditer(pattern, processed_query, re.IGNORECASE))
                    if matches:
                        operators.extend([operator] * len(matches))
                        # Replace operators with spaces to maintain word boundaries
                        processed_query = re.sub(pattern, ' ', processed_query, flags=re.IGNORECASE)
            
            # Clean up extra spaces
            processed_query = re.sub(r'\s+', ' ', processed_query).strip()
            
            return operators, processed_query
            
        except Exception as e:
            self._logger.error(f"Error parsing operators: {e}")
            return [], query


class PhraseQueryParser:
    """Handles parsing of phrase queries and quoted strings."""
    
    def __init__(self):
        """Initialize phrase query parser."""
        self._logger = get_logger(__name__)
    
    def parse_phrases(self, query: str) -> Tuple[List[QueryTerm], str]:
        """
        Parse phrase queries from query string.
        
        Args:
            query: Query string to parse
            
        Returns:
            Tuple of (phrase_terms, remaining_query)
        """
        phrase_terms = []
        remaining_query = query
        
        try:
            # Find quoted phrases
            phrase_pattern = r'"([^"]+)"'
            matches = re.finditer(phrase_pattern, query)
            
            for match in matches:
                phrase_text = match.group(1).strip()
                if phrase_text:
                    phrase_term = QueryTerm(
                        text=phrase_text,
                        is_phrase=True,
                        weight=1.2  # Boost phrase queries
                    )
                    phrase_terms.append(phrase_term)
                    
                    # Remove from remaining query
                    remaining_query = remaining_query.replace(match.group(0), ' ', 1)
            
            # Clean up remaining query
            remaining_query = re.sub(r'\s+', ' ', remaining_query).strip()
            
            return phrase_terms, remaining_query
            
        except Exception as e:
            self._logger.error(f"Error parsing phrases: {e}")
            return [], query


class BooleanQueryParser:
    """Handles parsing of boolean query expressions."""
    
    def __init__(self):
        """Initialize boolean query parser."""
        self._logger = get_logger(__name__)
    
    def parse_boolean_terms(self, query: str) -> List[QueryTerm]:
        """
        Parse boolean terms with required/excluded modifiers.
        
        Args:
            query: Query string to parse
            
        Returns:
            List of QueryTerm objects
        """
        terms = []
        
        try:
            # Split query into tokens
            tokens = re.findall(r'[+\-]?[^\s+\-]+', query)
            
            for token in tokens:
                if not token.strip():
                    continue
                
                is_required = False
                is_excluded = False
                term_text = token
                
                # Check for required term (+)
                if token.startswith('+'):
                    is_required = True
                    term_text = token[1:]
                
                # Check for excluded term (-)
                elif token.startswith('-'):
                    is_excluded = True
                    term_text = token[1:]
                
                # Skip empty terms
                if not term_text.strip():
                    continue
                
                # Create term
                term = QueryTerm(
                    text=term_text.strip(),
                    is_required=is_required,
                    is_excluded=is_excluded,
                    weight=1.5 if is_required else 0.5 if is_excluded else 1.0
                )
                terms.append(term)
            
            return terms
            
        except Exception as e:
            self._logger.error(f"Error parsing boolean terms: {e}")
            return []


class FieldQueryParser:
    """Handles parsing of field-specific query terms."""
    
    def __init__(self):
        """Initialize field query parser."""
        self._logger = get_logger(__name__)
    
    def parse_field_terms(self, query: str, filters: List[QueryFilter]) -> List[QueryTerm]:
        """
        Parse field-specific terms that aren't filters.
        
        Args:
            query: Query string to parse
            filters: Already parsed filters to avoid duplication
            
        Returns:
            List of QueryTerm objects with field assignments
        """
        terms = []
        
        try:
            # Extract field-specific terms that aren't already in filters
            field_pattern = r'(\w+):([^\s:]+(?:\s+[^\s:]+)*?)(?:\s|$)'
            matches = re.finditer(field_pattern, query)
            
            for match in matches:
                field_name = match.group(1).lower()
                term_text = match.group(2).strip()
                
                # Map field name to FieldType
                field_type = self._map_field_name(field_name)
                if field_type:
                    # Check if this is already a filter
                    is_filter = any(
                        f.field == field_type and str(f.value).lower() == term_text.lower()
                        for f in filters
                    )
                    
                    if not is_filter:
                        term = QueryTerm(
                            text=term_text,
                            field=field_type,
                            weight=1.3  # Boost field-specific terms
                        )
                        terms.append(term)
            
            return terms
            
        except Exception as e:
            self._logger.error(f"Error parsing field terms: {e}")
            return []
    
    def _map_field_name(self, field_name: str) -> Optional[FieldType]:
        """Map field name string to FieldType enum."""
        field_mapping = {
            'title': FieldType.TITLE,
            't': FieldType.TITLE,
            'content': FieldType.CONTENT,
            'c': FieldType.CONTENT,
            'body': FieldType.CONTENT,
            'author': FieldType.AUTHOR,
            'a': FieldType.AUTHOR,
            'by': FieldType.AUTHOR,
            'tags': FieldType.TAGS,
            'tag': FieldType.TAGS,
            'labels': FieldType.TAGS,
            'meta': FieldType.METADATA,
            'metadata': FieldType.METADATA,
            'created': FieldType.DATE_CREATED,
            'date': FieldType.DATE_CREATED,
            'from': FieldType.DATE_CREATED,
            'modified': FieldType.DATE_MODIFIED,
            'updated': FieldType.DATE_MODIFIED,
            'changed': FieldType.DATE_MODIFIED,
            'type': FieldType.FILE_TYPE,
            'format': FieldType.FILE_TYPE,
            'ext': FieldType.FILE_TYPE,
            'lang': FieldType.LANGUAGE,
            'language': FieldType.LANGUAGE
        }
        
        return field_mapping.get(field_name.lower())


class QueryParser(IQueryParser):
    """
    Main query parser that orchestrates parsing of user queries.
    Extracts special operators, filters, and structures query components.
    """

    def __init__(self, config: Optional[QueryParsingConfig] = None):
        """Initialize query parser."""
        self._config = config or QueryParsingConfig()
        self._logger = get_logger(__name__)
        self._lock = RLock()

        # Initialize sub-parsers
        self._filter_parser = FilterParser()
        self._operator_parser = OperatorParser()
        self._phrase_parser = PhraseQueryParser()
        self._boolean_parser = BooleanQueryParser()
        self._field_parser = FieldQueryParser()

        # Parsing statistics
        self._parsing_stats = {
            'total_queries_parsed': 0,
            'average_parsing_time_ms': 0.0,
            'complex_queries_count': 0,
            'parsing_errors_count': 0
        }

        self._logger.info("QueryParser initialized successfully")

    def parse_query(self, query: str, config: Optional[QueryParsingConfig] = None) -> ParsedQuery:
        """
        Parse a user query into structured components.

        Args:
            query: Raw query string from user
            config: Optional parsing configuration

        Returns:
            ParsedQuery with structured query components

        Raises:
            ValidationError: If query is invalid or malformed
        """
        start_time = time.time()

        try:
            with self._lock:
                # Use provided config or default
                parse_config = config or self._config

                # Validate query
                is_valid, errors = self.validate_query(query)
                if not is_valid:
                    raise ValidationError(f"Invalid query: {'; '.join(errors)}")

                # Initialize parsed query
                parsed_query = ParsedQuery(
                    original_query=query,
                    query_type=self._determine_query_type(query)
                )

                # Parse components in order
                current_query = query.strip()

                # 1. Parse filters first
                filters, current_query = self._filter_parser.parse_filters(current_query)
                parsed_query.filters = filters

                # 2. Parse operators
                operators, current_query = self._operator_parser.parse_operators(current_query)
                parsed_query.operators = operators

                # 3. Parse phrases
                phrase_terms, current_query = self._phrase_parser.parse_phrases(current_query)
                parsed_query.terms.extend(phrase_terms)

                # 4. Parse field-specific terms
                field_terms = self._field_parser.parse_field_terms(current_query, filters)
                parsed_query.terms.extend(field_terms)

                # 5. Parse remaining terms as boolean terms
                boolean_terms = self._boolean_parser.parse_boolean_terms(current_query)
                parsed_query.terms.extend(boolean_terms)

                # 6. Apply parsing configuration
                self._apply_parsing_config(parsed_query, parse_config)

                # 7. Extract additional query features
                self._extract_query_features(parsed_query, query)

                # Calculate processing time
                processing_time = (time.time() - start_time) * 1000
                parsed_query.processing_time_ms = processing_time

                # Update statistics
                self._update_parsing_stats(parsed_query, processing_time)

                self._logger.debug(f"Successfully parsed query: {query[:100]}...")
                return parsed_query

        except ValidationError:
            raise
        except Exception as e:
            self._parsing_stats['parsing_errors_count'] += 1
            self._logger.error(f"Error parsing query '{query}': {e}")
            raise ValidationError(f"Failed to parse query: {str(e)}")

    def validate_query(self, query: str) -> Tuple[bool, List[str]]:
        """
        Validate query syntax and structure.

        Args:
            query: Query string to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        try:
            # Check basic requirements
            if not query or not query.strip():
                errors.append("Query cannot be empty")
                return False, errors

            # Check length limits
            if len(query) > 1000:
                errors.append("Query too long (max 1000 characters)")

            # Check for balanced quotes
            quote_count = query.count('"')
            if quote_count % 2 != 0:
                errors.append("Unbalanced quotes in query")

            # Check for balanced parentheses
            paren_count = query.count('(') - query.count(')')
            if paren_count != 0:
                errors.append("Unbalanced parentheses in query")

            # Check for valid characters (basic validation)
            if re.search(r'[<>{}[\]\\]', query):
                errors.append("Query contains invalid characters")

            # Check term count limits
            terms = re.findall(r'\S+', query)
            if len(terms) > self._config.max_query_terms:
                errors.append(f"Too many terms (max {self._config.max_query_terms})")

            return len(errors) == 0, errors

        except Exception as e:
            self._logger.error(f"Error validating query: {e}")
            errors.append(f"Validation error: {str(e)}")
            return False, errors

    def get_supported_operators(self) -> List[QueryOperator]:
        """
        Get list of supported query operators.

        Returns:
            List of supported QueryOperator values
        """
        return list(QueryOperator)

    def get_supported_fields(self) -> List[FieldType]:
        """
        Get list of supported search fields.

        Returns:
            List of supported FieldType values
        """
        return list(FieldType)

    def _determine_query_type(self, query: str) -> QueryType:
        """Determine the type of query based on its content."""
        query_lower = query.lower()

        # Check for phrase query
        if '"' in query:
            return QueryType.PHRASE

        # Check for boolean operators
        if any(op in query_lower for op in ['and', 'or', 'not', '+', '-']):
            return QueryType.BOOLEAN

        # Check for wildcard characters
        if any(char in query for char in ['*', '?']):
            return QueryType.WILDCARD

        # Check for field-specific search
        if ':' in query:
            return QueryType.FIELD_SPECIFIC

        # Check for range queries
        if any(op in query for op in ['>', '<', '>=', '<=', '..']):
            return QueryType.RANGE

        # Default to simple query
        return QueryType.SIMPLE

    def _apply_parsing_config(self, parsed_query: ParsedQuery, config: QueryParsingConfig):
        """Apply parsing configuration to the parsed query."""
        try:
            # Apply stemming if enabled
            if config.enable_stemming:
                for term in parsed_query.terms:
                    # Simple stemming (remove common suffixes)
                    term.text = self._apply_simple_stemming(term.text)

            # Remove stopwords if enabled
            if config.enable_stopword_removal:
                stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
                parsed_query.terms = [
                    term for term in parsed_query.terms
                    if term.text.lower() not in stopwords
                ]

            # Apply case sensitivity
            if not config.case_sensitive:
                for term in parsed_query.terms:
                    term.text = term.text.lower()

        except Exception as e:
            self._logger.warning(f"Error applying parsing config: {e}")

    def _apply_simple_stemming(self, text: str) -> str:
        """Apply simple stemming rules."""
        # Basic stemming rules
        suffixes = ['ing', 'ed', 'er', 'est', 'ly', 's']

        for suffix in suffixes:
            if text.endswith(suffix) and len(text) > len(suffix) + 2:
                return text[:-len(suffix)]

        return text

    def _extract_query_features(self, parsed_query: ParsedQuery, original_query: str):
        """Extract additional features from the query."""
        try:
            # Extract sort criteria from query
            sort_pattern = r'sort:(\w+)(?:\s+(asc|desc))?'
            sort_matches = re.finditer(sort_pattern, original_query, re.IGNORECASE)

            for match in sort_matches:
                field_name = match.group(1).lower()
                direction = match.group(2).lower() if match.group(2) else 'asc'

                # Map field name to FieldType
                field_type = self._map_sort_field(field_name)
                if field_type:
                    parsed_query.sort_criteria.append((field_type, direction))

            # Extract limit and offset
            limit_match = re.search(r'limit:(\d+)', original_query, re.IGNORECASE)
            if limit_match:
                parsed_query.limit = int(limit_match.group(1))

            offset_match = re.search(r'offset:(\d+)', original_query, re.IGNORECASE)
            if offset_match:
                parsed_query.offset = int(offset_match.group(1))

            # Extract boost fields
            boost_pattern = r'boost:(\w+)(?:\s*\*\s*(\d+(?:\.\d+)?))?'
            boost_matches = re.finditer(boost_pattern, original_query, re.IGNORECASE)

            for match in boost_matches:
                field_name = match.group(1).lower()
                boost_value = float(match.group(2)) if match.group(2) else 2.0

                field_type = self._map_sort_field(field_name)
                if field_type:
                    parsed_query.boost_fields[field_type] = boost_value

        except Exception as e:
            self._logger.warning(f"Error extracting query features: {e}")

    def _map_sort_field(self, field_name: str) -> Optional[FieldType]:
        """Map sort field name to FieldType."""
        field_mapping = {
            'title': FieldType.TITLE,
            'content': FieldType.CONTENT,
            'author': FieldType.AUTHOR,
            'date': FieldType.DATE_CREATED,
            'created': FieldType.DATE_CREATED,
            'modified': FieldType.DATE_MODIFIED,
            'type': FieldType.FILE_TYPE,
            'language': FieldType.LANGUAGE
        }

        return field_mapping.get(field_name)

    def _update_parsing_stats(self, parsed_query: ParsedQuery, processing_time: float):
        """Update parsing statistics."""
        try:
            self._parsing_stats['total_queries_parsed'] += 1

            # Update average processing time
            total_count = self._parsing_stats['total_queries_parsed']
            current_avg = self._parsing_stats['average_parsing_time_ms']
            self._parsing_stats['average_parsing_time_ms'] = (
                (current_avg * (total_count - 1) + processing_time) / total_count
            )

            # Count complex queries
            if parsed_query.is_complex_query:
                self._parsing_stats['complex_queries_count'] += 1

        except Exception as e:
            self._logger.warning(f"Error updating parsing stats: {e}")

    def get_parsing_statistics(self) -> Dict[str, Any]:
        """Get current parsing statistics."""
        with self._lock:
            return self._parsing_stats.copy()
