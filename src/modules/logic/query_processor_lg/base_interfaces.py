"""
Module: base_interfaces
Description: Base interfaces and data structures for query processing functionality
Phase: 4
Location: /src/modules/logic/query_processor_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Third-party imports
import numpy as np


class QueryType(Enum):
    """Types of queries supported by the system."""
    SIMPLE = "simple"
    BOOLEAN = "boolean"
    PHRASE = "phrase"
    WILDCARD = "wildcard"
    FUZZY = "fuzzy"
    RANGE = "range"
    FIELD_SPECIFIC = "field_specific"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class QueryOperator(Enum):
    """Query operators for boolean and complex queries."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    NEAR = "NEAR"
    WITHIN = "WITHIN"
    BEFORE = "BEFORE"
    AFTER = "AFTER"


class FieldType(Enum):
    """Types of document fields that can be searched."""
    TITLE = "title"
    CONTENT = "content"
    AUTHOR = "author"
    TAGS = "tags"
    METADATA = "metadata"
    DATE_CREATED = "date_created"
    DATE_MODIFIED = "date_modified"
    FILE_TYPE = "file_type"
    LANGUAGE = "language"


class ExpansionMethod(Enum):
    """Methods for query expansion."""
    SYNONYMS = "synonyms"
    STEMMING = "stemming"
    LEMMATIZATION = "lemmatization"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    WORD_EMBEDDINGS = "word_embeddings"
    CONTEXTUAL_EXPANSION = "contextual_expansion"
    DOMAIN_SPECIFIC = "domain_specific"


class OptimizationStrategy(Enum):
    """Query optimization strategies."""
    COST_BASED = "cost_based"
    RULE_BASED = "rule_based"
    ADAPTIVE = "adaptive"
    INDEX_AWARE = "index_aware"
    STATISTICS_DRIVEN = "statistics_driven"


class QueryStatus(Enum):
    """Status of query processing operations."""
    PENDING = "pending"
    PARSING = "parsing"
    EXPANDING = "expanding"
    OPTIMIZING = "optimizing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueryFilter:
    """Represents a filter condition in a query."""
    field: FieldType
    operator: str  # =, !=, <, >, <=, >=, CONTAINS, STARTS_WITH, ENDS_WITH
    value: Union[str, int, float, datetime, List[Any]]
    case_sensitive: bool = False
    exact_match: bool = False
    
    def __post_init__(self):
        """Validate filter configuration."""
        if self.operator not in ['=', '!=', '<', '>', '<=', '>=', 'CONTAINS', 'STARTS_WITH', 'ENDS_WITH', 'IN', 'NOT_IN']:
            raise ValueError(f"Unsupported filter operator: {self.operator}")


@dataclass
class QueryTerm:
    """Represents a single term in a query."""
    text: str
    field: Optional[FieldType] = None
    weight: float = 1.0
    is_required: bool = False
    is_excluded: bool = False
    is_phrase: bool = False
    proximity_distance: Optional[int] = None
    fuzzy_threshold: Optional[float] = None
    
    def __post_init__(self):
        """Validate term configuration."""
        if self.weight < 0:
            raise ValueError("Term weight cannot be negative")
        if self.fuzzy_threshold is not None and not (0.0 <= self.fuzzy_threshold <= 1.0):
            raise ValueError("Fuzzy threshold must be between 0.0 and 1.0")


@dataclass
class ParsedQuery:
    """Result of query parsing operation."""
    original_query: str
    query_type: QueryType
    terms: List[QueryTerm] = field(default_factory=list)
    filters: List[QueryFilter] = field(default_factory=list)
    operators: List[QueryOperator] = field(default_factory=list)
    boost_fields: Dict[FieldType, float] = field(default_factory=dict)
    sort_criteria: List[Tuple[FieldType, str]] = field(default_factory=list)  # (field, direction)
    limit: Optional[int] = None
    offset: int = 0
    enable_highlighting: bool = True
    enable_faceting: bool = False
    facet_fields: List[FieldType] = field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complex_query(self) -> bool:
        """Check if this is a complex query requiring special handling."""
        return (
            len(self.operators) > 0 or
            len(self.filters) > 0 or
            any(term.is_phrase for term in self.terms) or
            any(term.proximity_distance is not None for term in self.terms)
        )
    
    @property
    def required_terms(self) -> List[QueryTerm]:
        """Get all required terms."""
        return [term for term in self.terms if term.is_required]
    
    @property
    def excluded_terms(self) -> List[QueryTerm]:
        """Get all excluded terms."""
        return [term for term in self.terms if term.is_excluded]


@dataclass
class ExpandedTerm:
    """Represents an expanded query term."""
    original_term: str
    expanded_term: str
    expansion_method: ExpansionMethod
    confidence_score: float
    semantic_similarity: float = 0.0
    frequency_weight: float = 1.0
    context_relevance: float = 1.0
    
    def __post_init__(self):
        """Validate expanded term configuration."""
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")


@dataclass
class QueryExpansionResult:
    """Result of query expansion operation."""
    original_query: ParsedQuery
    expanded_terms: List[ExpandedTerm] = field(default_factory=list)
    expansion_methods_used: Set[ExpansionMethod] = field(default_factory=set)
    total_expansion_score: float = 0.0
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def expansion_ratio(self) -> float:
        """Calculate the expansion ratio (expanded terms / original terms)."""
        original_term_count = len(self.original_query.terms)
        if original_term_count == 0:
            return 0.0
        return len(self.expanded_terms) / original_term_count
    
    @property
    def high_confidence_expansions(self) -> List[ExpandedTerm]:
        """Get expansions with high confidence scores (>= 0.7)."""
        return [term for term in self.expanded_terms if term.confidence_score >= 0.7]


@dataclass
class ExecutionPlan:
    """Represents a query execution plan."""
    plan_id: str
    estimated_cost: float
    estimated_time_ms: float
    index_usage: Dict[str, str] = field(default_factory=dict)
    join_order: List[str] = field(default_factory=list)
    filter_order: List[QueryFilter] = field(default_factory=list)
    optimization_notes: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate execution plan."""
        if self.estimated_cost < 0:
            raise ValueError("Estimated cost cannot be negative")
        if self.estimated_time_ms < 0:
            raise ValueError("Estimated time cannot be negative")


@dataclass
class IndexStatistics:
    """Statistics about available indices."""
    index_name: str
    field_name: str
    cardinality: int
    selectivity: float
    size_bytes: int
    last_updated: datetime
    usage_frequency: int = 0
    average_query_time_ms: float = 0.0

    @property
    def efficiency_score(self) -> float:
        """Calculate index efficiency score."""
        if self.usage_frequency == 0:
            return 0.0
        return min(1.0, (self.selectivity * self.usage_frequency) / max(1.0, self.average_query_time_ms))


@dataclass
class QueryOptimizationResult:
    """Result of query optimization operation."""
    original_query: ParsedQuery
    optimized_query: ParsedQuery
    execution_plan: ExecutionPlan
    optimization_strategy: OptimizationStrategy
    performance_improvement_estimate: float = 0.0
    optimization_confidence: float = 0.0
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_beneficial_optimization(self) -> bool:
        """Check if optimization provides significant benefit."""
        return self.performance_improvement_estimate > 0.1  # 10% improvement threshold


@dataclass
class QueryParsingConfig:
    """Configuration for query parsing operations."""
    enable_stemming: bool = True
    enable_lemmatization: bool = False
    enable_stopword_removal: bool = True
    enable_phrase_detection: bool = True
    enable_fuzzy_matching: bool = False
    default_fuzzy_threshold: float = 0.8
    max_query_terms: int = 100
    max_filters: int = 20
    case_sensitive: bool = False
    enable_wildcard_expansion: bool = True
    proximity_window_size: int = 5
    custom_operators: Dict[str, QueryOperator] = field(default_factory=dict)


@dataclass
class QueryExpansionConfig:
    """Configuration for query expansion operations."""
    enable_synonym_expansion: bool = True
    enable_stemming_expansion: bool = True
    enable_semantic_expansion: bool = False
    max_expansions_per_term: int = 5
    min_confidence_threshold: float = 0.5
    semantic_similarity_threshold: float = 0.7
    expansion_weight_decay: float = 0.8
    enable_domain_specific_expansion: bool = False
    domain_vocabulary_path: Optional[str] = None
    custom_synonym_dict: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class QueryOptimizationConfig:
    """Configuration for query optimization operations."""
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.ADAPTIVE
    enable_index_hints: bool = True
    enable_cost_estimation: bool = True
    enable_statistics_collection: bool = True
    max_optimization_time_ms: int = 1000
    cost_threshold: float = 100.0
    enable_query_rewriting: bool = True
    enable_filter_pushdown: bool = True
    enable_join_reordering: bool = True
    cache_execution_plans: bool = True
    plan_cache_size: int = 1000


# Base Interfaces

class IQueryParser(ABC):
    """Base interface for query parsers."""

    @abstractmethod
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
        pass

    @abstractmethod
    def validate_query(self, query: str) -> Tuple[bool, List[str]]:
        """
        Validate query syntax and structure.

        Args:
            query: Query string to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        pass

    @abstractmethod
    def get_supported_operators(self) -> List[QueryOperator]:
        """
        Get list of supported query operators.

        Returns:
            List of supported QueryOperator values
        """
        pass

    @abstractmethod
    def get_supported_fields(self) -> List[FieldType]:
        """
        Get list of supported search fields.

        Returns:
            List of supported FieldType values
        """
        pass


class IQueryExpander(ABC):
    """Base interface for query expanders."""

    @abstractmethod
    def expand_query(self, parsed_query: ParsedQuery,
                    config: Optional[QueryExpansionConfig] = None) -> QueryExpansionResult:
        """
        Expand query terms with synonyms and related terms.

        Args:
            parsed_query: Parsed query to expand
            config: Optional expansion configuration

        Returns:
            QueryExpansionResult with expanded terms
        """
        pass

    @abstractmethod
    def get_synonyms(self, term: str, max_synonyms: int = 5) -> List[str]:
        """
        Get synonyms for a given term.

        Args:
            term: Term to find synonyms for
            max_synonyms: Maximum number of synonyms to return

        Returns:
            List of synonym terms
        """
        pass

    @abstractmethod
    def calculate_term_similarity(self, term1: str, term2: str) -> float:
        """
        Calculate semantic similarity between two terms.

        Args:
            term1: First term
            term2: Second term

        Returns:
            Similarity score between 0.0 and 1.0
        """
        pass


class IQueryOptimizer(ABC):
    """Base interface for query optimizers."""

    @abstractmethod
    def optimize_query(self, parsed_query: ParsedQuery,
                      config: Optional[QueryOptimizationConfig] = None) -> QueryOptimizationResult:
        """
        Optimize query execution plan based on index statistics.

        Args:
            parsed_query: Parsed query to optimize
            config: Optional optimization configuration

        Returns:
            QueryOptimizationResult with optimized query and execution plan
        """
        pass

    @abstractmethod
    def estimate_query_cost(self, parsed_query: ParsedQuery) -> float:
        """
        Estimate execution cost for a query.

        Args:
            parsed_query: Query to estimate cost for

        Returns:
            Estimated cost value
        """
        pass

    @abstractmethod
    def get_index_statistics(self) -> List[IndexStatistics]:
        """
        Get current index statistics for optimization.

        Returns:
            List of IndexStatistics for available indices
        """
        pass

    @abstractmethod
    def update_statistics(self, query_performance: Dict[str, Any]) -> bool:
        """
        Update optimization statistics with query performance data.

        Args:
            query_performance: Performance metrics from executed queries

        Returns:
            True if statistics updated successfully
        """
        pass
