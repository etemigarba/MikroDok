"""
MikroDok Query Processor Package
Provides comprehensive query processing functionality including parsing, expansion, and optimization.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IQueryParser,
        IQueryExpander,
        IQueryOptimizer,
        QueryType,
        QueryOperator,
        FieldType,
        ExpansionMethod,
        OptimizationStrategy,
        QueryStatus,
        QueryFilter,
        QueryTerm,
        ParsedQuery,
        ExpandedTerm,
        QueryExpansionResult,
        ExecutionPlan,
        IndexStatistics,
        QueryOptimizationResult,
        QueryParsingConfig,
        QueryExpansionConfig,
        QueryOptimizationConfig
    )
except ImportError:
    pass

# Import query parser components
try:
    from .query_parser_lg import (
        QueryParser,
        BooleanQueryParser,
        PhraseQueryParser,
        FieldQueryParser,
        FilterParser,
        OperatorParser
    )
except ImportError:
    pass

# Import query expansion components
try:
    from .query_expansion_lg import (
        QueryExpander,
        SynonymExpander,
        SemanticExpander,
        StemExpander,
        ContextualExpander,
        DomainExpander
    )
except ImportError:
    pass

# Import query optimization components
try:
    from .query_optimizer_lg import (
        QueryOptimizer,
        CostEstimator,
        ExecutionPlanner,
        IndexAnalyzer,
        StatisticsCollector,
        QueryRewriter
    )
except ImportError:
    pass

__all__ = [
    # Base Interfaces
    'IQueryParser',
    'IQueryExpander',
    'IQueryOptimizer',
    'QueryType',
    'QueryOperator',
    'FieldType',
    'ExpansionMethod',
    'OptimizationStrategy',
    'QueryStatus',
    'QueryFilter',
    'QueryTerm',
    'ParsedQuery',
    'ExpandedTerm',
    'QueryExpansionResult',
    'ExecutionPlan',
    'IndexStatistics',
    'QueryOptimizationResult',
    'QueryParsingConfig',
    'QueryExpansionConfig',
    'QueryOptimizationConfig',
    
    # Query Parser
    'QueryParser',
    'BooleanQueryParser',
    'PhraseQueryParser',
    'FieldQueryParser',
    'FilterParser',
    'OperatorParser',
    
    # Query Expansion
    'QueryExpander',
    'SynonymExpander',
    'SemanticExpander',
    'StemExpander',
    'ContextualExpander',
    'DomainExpander',
    
    # Query Optimization
    'QueryOptimizer',
    'CostEstimator',
    'ExecutionPlanner',
    'IndexAnalyzer',
    'StatisticsCollector',
    'QueryRewriter'
]
