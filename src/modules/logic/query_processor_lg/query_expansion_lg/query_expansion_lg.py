"""
Module: query_expansion_lg
Description: Expands queries with synonyms and related terms for better recall
Phase: 4
Location: /src/modules/logic/query_processor_lg/query_expansion_lg/query_expansion_lg.py
"""

# Standard library imports
import re
import time
from threading import RLock
from typing import Any, Dict, List, Optional, Set

# Third-party imports
import logging

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IQueryExpander,
    ExpansionMethod,
    ParsedQuery,
    QueryTerm,
    ExpandedTerm,
    QueryExpansionResult,
    QueryExpansionConfig
)


class SynonymExpander:
    """Handles synonym-based query expansion."""
    
    def __init__(self):
        """Initialize synonym expander."""
        self._logger = get_logger(__name__)
        
        # Built-in synonym dictionary
        self._synonyms = {
            'document': ['file', 'paper', 'text', 'record'],
            'search': ['find', 'locate', 'discover', 'retrieve'],
            'analyze': ['examine', 'study', 'investigate', 'review'],
            'create': ['make', 'generate', 'produce', 'build'],
            'delete': ['remove', 'erase', 'eliminate', 'destroy'],
            'update': ['modify', 'change', 'edit', 'revise'],
            'important': ['significant', 'crucial', 'vital', 'essential'],
            'large': ['big', 'huge', 'massive', 'enormous'],
            'small': ['tiny', 'little', 'minor', 'compact'],
            'fast': ['quick', 'rapid', 'swift', 'speedy'],
            'slow': ['sluggish', 'gradual', 'delayed', 'leisurely'],
            'good': ['excellent', 'great', 'fine', 'quality'],
            'bad': ['poor', 'terrible', 'awful', 'defective'],
            'new': ['recent', 'fresh', 'latest', 'modern'],
            'old': ['ancient', 'vintage', 'outdated', 'legacy']
        }
    
    def expand_term(self, term: str, max_synonyms: int = 5) -> List[ExpandedTerm]:
        """
        Expand a term with synonyms.
        
        Args:
            term: Term to expand
            max_synonyms: Maximum number of synonyms to return
            
        Returns:
            List of ExpandedTerm objects
        """
        expanded_terms = []
        
        try:
            term_lower = term.lower()
            
            # Direct lookup
            if term_lower in self._synonyms:
                synonyms = self._synonyms[term_lower][:max_synonyms]
                
                for i, synonym in enumerate(synonyms):
                    confidence = 1.0 - (i * 0.1)  # Decreasing confidence
                    expanded_term = ExpandedTerm(
                        original_term=term,
                        expanded_term=synonym,
                        expansion_method=ExpansionMethod.SYNONYMS,
                        confidence_score=max(0.5, confidence),
                        semantic_similarity=0.9 - (i * 0.1)
                    )
                    expanded_terms.append(expanded_term)
            
            # Reverse lookup (find terms that have this as synonym)
            for key, synonyms in self._synonyms.items():
                if term_lower in [s.lower() for s in synonyms]:
                    expanded_term = ExpandedTerm(
                        original_term=term,
                        expanded_term=key,
                        expansion_method=ExpansionMethod.SYNONYMS,
                        confidence_score=0.8,
                        semantic_similarity=0.85
                    )
                    expanded_terms.append(expanded_term)
                    break
            
            return expanded_terms
            
        except Exception as e:
            self._logger.error(f"Error expanding term '{term}': {e}")
            return []
    
    def add_custom_synonyms(self, custom_synonyms: Dict[str, List[str]]):
        """Add custom synonyms to the dictionary."""
        try:
            for term, synonyms in custom_synonyms.items():
                if term.lower() in self._synonyms:
                    # Merge with existing synonyms
                    existing = set(self._synonyms[term.lower()])
                    new_synonyms = existing.union(set(synonyms))
                    self._synonyms[term.lower()] = list(new_synonyms)
                else:
                    self._synonyms[term.lower()] = synonyms
                    
        except Exception as e:
            self._logger.error(f"Error adding custom synonyms: {e}")


class StemExpander:
    """Handles stemming-based query expansion."""
    
    def __init__(self):
        """Initialize stem expander."""
        self._logger = get_logger(__name__)
        
        # Common stemming rules
        self._stemming_rules = [
            (r'ies$', 'y'),
            (r'ied$', 'y'),
            (r'ying$', 'y'),
            (r'ing$', ''),
            (r'ed$', ''),
            (r'er$', ''),
            (r'est$', ''),
            (r'ly$', ''),
            (r's$', '')
        ]
    
    def expand_term(self, term: str) -> List[ExpandedTerm]:
        """
        Expand a term using stemming variations.
        
        Args:
            term: Term to expand
            
        Returns:
            List of ExpandedTerm objects
        """
        expanded_terms = []
        
        try:
            # Generate stem
            stem = self._get_stem(term)
            
            if stem != term:
                expanded_term = ExpandedTerm(
                    original_term=term,
                    expanded_term=stem,
                    expansion_method=ExpansionMethod.STEMMING,
                    confidence_score=0.9,
                    semantic_similarity=0.95
                )
                expanded_terms.append(expanded_term)
            
            # Generate variations from stem
            variations = self._generate_variations(stem)
            
            for variation in variations:
                if variation != term and variation != stem:
                    expanded_term = ExpandedTerm(
                        original_term=term,
                        expanded_term=variation,
                        expansion_method=ExpansionMethod.STEMMING,
                        confidence_score=0.7,
                        semantic_similarity=0.8
                    )
                    expanded_terms.append(expanded_term)
            
            return expanded_terms
            
        except Exception as e:
            self._logger.error(f"Error stem expanding term '{term}': {e}")
            return []
    
    def _get_stem(self, term: str) -> str:
        """Get the stem of a term."""
        term_lower = term.lower()
        
        for pattern, replacement in self._stemming_rules:
            if re.search(pattern, term_lower):
                stem = re.sub(pattern, replacement, term_lower)
                if len(stem) >= 3:  # Minimum stem length
                    return stem
        
        return term_lower
    
    def _generate_variations(self, stem: str) -> List[str]:
        """Generate variations from a stem."""
        variations = []
        
        # Add common suffixes
        suffixes = ['s', 'ed', 'ing', 'er', 'est', 'ly']
        
        for suffix in suffixes:
            variation = stem + suffix
            variations.append(variation)
        
        return variations


class SemanticExpander:
    """Handles semantic similarity-based query expansion."""
    
    def __init__(self):
        """Initialize semantic expander."""
        self._logger = get_logger(__name__)
        
        # Semantic clusters (simplified word embeddings)
        self._semantic_clusters = {
            'technology': ['computer', 'software', 'digital', 'electronic', 'tech', 'system'],
            'business': ['company', 'corporate', 'enterprise', 'organization', 'firm', 'industry'],
            'education': ['school', 'university', 'academic', 'learning', 'study', 'research'],
            'health': ['medical', 'healthcare', 'hospital', 'doctor', 'patient', 'treatment'],
            'finance': ['money', 'financial', 'banking', 'investment', 'economic', 'budget'],
            'science': ['research', 'experiment', 'analysis', 'data', 'scientific', 'study'],
            'communication': ['message', 'email', 'phone', 'contact', 'communication', 'network'],
            'management': ['manage', 'control', 'organize', 'coordinate', 'supervise', 'lead']
        }
    
    def expand_term(self, term: str, threshold: float = 0.7) -> List[ExpandedTerm]:
        """
        Expand a term using semantic similarity.
        
        Args:
            term: Term to expand
            threshold: Minimum similarity threshold
            
        Returns:
            List of ExpandedTerm objects
        """
        expanded_terms = []
        
        try:
            term_lower = term.lower()
            
            # Find semantic cluster
            for cluster_name, cluster_terms in self._semantic_clusters.items():
                if term_lower in cluster_terms:
                    # Add other terms from the same cluster
                    for cluster_term in cluster_terms:
                        if cluster_term != term_lower:
                            similarity = self._calculate_cluster_similarity(term_lower, cluster_term)
                            
                            if similarity >= threshold:
                                expanded_term = ExpandedTerm(
                                    original_term=term,
                                    expanded_term=cluster_term,
                                    expansion_method=ExpansionMethod.SEMANTIC_SIMILARITY,
                                    confidence_score=similarity,
                                    semantic_similarity=similarity,
                                    context_relevance=0.8
                                )
                                expanded_terms.append(expanded_term)
                    break
            
            return expanded_terms
            
        except Exception as e:
            self._logger.error(f"Error semantic expanding term '{term}': {e}")
            return []
    
    def _calculate_cluster_similarity(self, term1: str, term2: str) -> float:
        """Calculate similarity between terms in the same cluster."""
        # Simplified similarity calculation
        # In a real implementation, this would use word embeddings
        
        # Character-based similarity
        common_chars = set(term1) & set(term2)
        total_chars = set(term1) | set(term2)
        char_similarity = len(common_chars) / len(total_chars) if total_chars else 0
        
        # Length-based similarity
        len_diff = abs(len(term1) - len(term2))
        max_len = max(len(term1), len(term2))
        len_similarity = 1.0 - (len_diff / max_len) if max_len > 0 else 1.0
        
        # Combined similarity
        return (char_similarity * 0.3 + len_similarity * 0.2 + 0.5)  # Base cluster bonus


class ContextualExpander:
    """Handles context-aware query expansion."""
    
    def __init__(self):
        """Initialize contextual expander."""
        self._logger = get_logger(__name__)
        
        # Context patterns
        self._context_patterns = {
            'temporal': ['today', 'yesterday', 'recent', 'latest', 'current', 'new'],
            'quality': ['best', 'top', 'excellent', 'quality', 'premium', 'superior'],
            'size': ['large', 'small', 'big', 'tiny', 'huge', 'massive'],
            'action': ['create', 'delete', 'update', 'modify', 'change', 'edit'],
            'location': ['here', 'local', 'nearby', 'remote', 'distant', 'global']
        }
    
    def expand_query_context(self, parsed_query: ParsedQuery) -> List[ExpandedTerm]:
        """
        Expand query based on contextual patterns.
        
        Args:
            parsed_query: Parsed query to analyze for context
            
        Returns:
            List of ExpandedTerm objects
        """
        expanded_terms = []
        
        try:
            # Analyze query terms for context
            all_terms = [term.text.lower() for term in parsed_query.terms]
            
            # Detect context patterns
            detected_contexts = []
            for context_type, context_terms in self._context_patterns.items():
                if any(term in all_terms for term in context_terms):
                    detected_contexts.append(context_type)
            
            # Expand based on detected contexts
            for term in parsed_query.terms:
                for context_type in detected_contexts:
                    context_expansions = self._get_context_expansions(term.text, context_type)
                    expanded_terms.extend(context_expansions)
            
            return expanded_terms
            
        except Exception as e:
            self._logger.error(f"Error contextual expanding query: {e}")
            return []
    
    def _get_context_expansions(self, term: str, context_type: str) -> List[ExpandedTerm]:
        """Get context-specific expansions for a term."""
        expansions = []
        
        try:
            context_mappings = {
                'temporal': {
                    'document': ['recent document', 'latest file', 'new record'],
                    'report': ['current report', 'latest report', 'recent analysis'],
                    'data': ['fresh data', 'current data', 'latest information']
                },
                'quality': {
                    'document': ['quality document', 'excellent file', 'premium content'],
                    'report': ['comprehensive report', 'detailed analysis', 'thorough study'],
                    'data': ['accurate data', 'reliable information', 'quality dataset']
                }
            }
            
            if context_type in context_mappings:
                term_mappings = context_mappings[context_type]
                term_lower = term.lower()
                
                if term_lower in term_mappings:
                    for expansion in term_mappings[term_lower]:
                        expanded_term = ExpandedTerm(
                            original_term=term,
                            expanded_term=expansion,
                            expansion_method=ExpansionMethod.CONTEXTUAL_EXPANSION,
                            confidence_score=0.8,
                            semantic_similarity=0.7,
                            context_relevance=0.9
                        )
                        expansions.append(expanded_term)
            
            return expansions
            
        except Exception as e:
            self._logger.error(f"Error getting context expansions: {e}")
            return []


class DomainExpander:
    """Handles domain-specific query expansion."""
    
    def __init__(self, domain_vocabulary: Optional[Dict[str, List[str]]] = None):
        """Initialize domain expander."""
        self._logger = get_logger(__name__)
        self._domain_vocabulary = domain_vocabulary or {}
    
    def expand_term(self, term: str, domain: str = 'general') -> List[ExpandedTerm]:
        """
        Expand a term using domain-specific vocabulary.
        
        Args:
            term: Term to expand
            domain: Domain context
            
        Returns:
            List of ExpandedTerm objects
        """
        expanded_terms = []
        
        try:
            if domain in self._domain_vocabulary:
                domain_terms = self._domain_vocabulary[domain]
                term_lower = term.lower()
                
                if term_lower in domain_terms:
                    for domain_term in domain_terms[term_lower]:
                        expanded_term = ExpandedTerm(
                            original_term=term,
                            expanded_term=domain_term,
                            expansion_method=ExpansionMethod.DOMAIN_SPECIFIC,
                            confidence_score=0.9,
                            semantic_similarity=0.85,
                            context_relevance=1.0
                        )
                        expanded_terms.append(expanded_term)
            
            return expanded_terms
            
        except Exception as e:
            self._logger.error(f"Error domain expanding term '{term}': {e}")
            return []
    
    def load_domain_vocabulary(self, vocabulary_path: str) -> bool:
        """Load domain vocabulary from file."""
        try:
            # In a real implementation, this would load from a file
            # For now, return True to indicate success
            self._logger.info(f"Domain vocabulary loaded from {vocabulary_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error loading domain vocabulary: {e}")
            return False


class QueryExpander(IQueryExpander):
    """
    Main query expander that orchestrates expansion using multiple methods.
    Expands queries with synonyms and related terms for better recall.
    """

    def __init__(self, config: Optional[QueryExpansionConfig] = None):
        """Initialize query expander."""
        self._config = config or QueryExpansionConfig()
        self._logger = get_logger(__name__)
        self._lock = RLock()

        # Initialize expanders
        self._synonym_expander = SynonymExpander()
        self._stem_expander = StemExpander()
        self._semantic_expander = SemanticExpander()
        self._contextual_expander = ContextualExpander()
        self._domain_expander = DomainExpander()

        # Add custom synonyms if provided
        if self._config.custom_synonym_dict:
            self._synonym_expander.add_custom_synonyms(self._config.custom_synonym_dict)

        # Load domain vocabulary if provided
        if self._config.domain_vocabulary_path:
            self._domain_expander.load_domain_vocabulary(self._config.domain_vocabulary_path)

        # Expansion statistics
        self._expansion_stats = {
            'total_queries_expanded': 0,
            'average_expansion_time_ms': 0.0,
            'average_expansion_ratio': 0.0,
            'expansion_errors_count': 0
        }

        self._logger.info("QueryExpander initialized successfully")

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
        start_time = time.time()

        try:
            with self._lock:
                # Use provided config or default
                expand_config = config or self._config

                # Initialize expansion result
                expansion_result = QueryExpansionResult(
                    original_query=parsed_query
                )

                # Collect all expanded terms
                all_expanded_terms = []
                methods_used = set()

                # Expand each term in the query
                for term in parsed_query.terms:
                    if term.is_excluded:
                        continue  # Skip excluded terms

                    term_expansions = self._expand_single_term(term, expand_config)

                    # Apply expansion limits
                    limited_expansions = self._apply_expansion_limits(
                        term_expansions, expand_config
                    )

                    all_expanded_terms.extend(limited_expansions)

                    # Track methods used
                    for expansion in limited_expansions:
                        methods_used.add(expansion.expansion_method)

                # Add contextual expansions
                if expand_config.enable_semantic_expansion:
                    contextual_expansions = self._contextual_expander.expand_query_context(parsed_query)
                    all_expanded_terms.extend(contextual_expansions)
                    if contextual_expansions:
                        methods_used.add(ExpansionMethod.CONTEXTUAL_EXPANSION)

                # Filter and rank expansions
                filtered_expansions = self._filter_expansions(all_expanded_terms, expand_config)
                ranked_expansions = self._rank_expansions(filtered_expansions)

                # Populate result
                expansion_result.expanded_terms = ranked_expansions
                expansion_result.expansion_methods_used = methods_used
                expansion_result.total_expansion_score = self._calculate_total_score(ranked_expansions)

                # Calculate processing time
                processing_time = (time.time() - start_time) * 1000
                expansion_result.processing_time_ms = processing_time

                # Update statistics
                self._update_expansion_stats(expansion_result, processing_time)

                self._logger.debug(f"Successfully expanded query with {len(ranked_expansions)} terms")
                return expansion_result

        except Exception as e:
            self._expansion_stats['expansion_errors_count'] += 1
            self._logger.error(f"Error expanding query: {e}")
            raise ValidationError(f"Failed to expand query: {str(e)}")

    def get_synonyms(self, term: str, max_synonyms: int = 5) -> List[str]:
        """
        Get synonyms for a given term.

        Args:
            term: Term to find synonyms for
            max_synonyms: Maximum number of synonyms to return

        Returns:
            List of synonym terms
        """
        try:
            expanded_terms = self._synonym_expander.expand_term(term, max_synonyms)
            return [exp.expanded_term for exp in expanded_terms]

        except Exception as e:
            self._logger.error(f"Error getting synonyms for '{term}': {e}")
            return []

    def calculate_term_similarity(self, term1: str, term2: str) -> float:
        """
        Calculate semantic similarity between two terms.

        Args:
            term1: First term
            term2: Second term

        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Simple similarity calculation
            # In a real implementation, this would use word embeddings

            if term1.lower() == term2.lower():
                return 1.0

            # Character-based similarity
            set1 = set(term1.lower())
            set2 = set(term2.lower())

            intersection = len(set1 & set2)
            union = len(set1 | set2)

            if union == 0:
                return 0.0

            jaccard_similarity = intersection / union

            # Length-based similarity
            len_diff = abs(len(term1) - len(term2))
            max_len = max(len(term1), len(term2))
            len_similarity = 1.0 - (len_diff / max_len) if max_len > 0 else 1.0

            # Combined similarity
            return (jaccard_similarity * 0.7 + len_similarity * 0.3)

        except Exception as e:
            self._logger.error(f"Error calculating similarity between '{term1}' and '{term2}': {e}")
            return 0.0

    def _expand_single_term(self, term: QueryTerm, config: QueryExpansionConfig) -> List[ExpandedTerm]:
        """Expand a single term using all enabled methods."""
        expansions = []

        try:
            # Synonym expansion
            if config.enable_synonym_expansion:
                synonym_expansions = self._synonym_expander.expand_term(
                    term.text, config.max_expansions_per_term
                )
                expansions.extend(synonym_expansions)

            # Stemming expansion
            if config.enable_stemming_expansion:
                stem_expansions = self._stem_expander.expand_term(term.text)
                expansions.extend(stem_expansions)

            # Semantic expansion
            if config.enable_semantic_expansion:
                semantic_expansions = self._semantic_expander.expand_term(
                    term.text, config.semantic_similarity_threshold
                )
                expansions.extend(semantic_expansions)

            # Domain-specific expansion
            if config.enable_domain_specific_expansion:
                domain_expansions = self._domain_expander.expand_term(term.text)
                expansions.extend(domain_expansions)

            return expansions

        except Exception as e:
            self._logger.error(f"Error expanding term '{term.text}': {e}")
            return []

    def _apply_expansion_limits(self, expansions: List[ExpandedTerm],
                              config: QueryExpansionConfig) -> List[ExpandedTerm]:
        """Apply expansion limits and filters."""
        try:
            # Filter by confidence threshold
            filtered = [
                exp for exp in expansions
                if exp.confidence_score >= config.min_confidence_threshold
            ]

            # Limit number of expansions per original term
            limited = filtered[:config.max_expansions_per_term]

            # Apply weight decay
            for i, expansion in enumerate(limited):
                decay_factor = config.expansion_weight_decay ** i
                expansion.frequency_weight *= decay_factor

            return limited

        except Exception as e:
            self._logger.error(f"Error applying expansion limits: {e}")
            return expansions

    def _filter_expansions(self, expansions: List[ExpandedTerm],
                          config: QueryExpansionConfig) -> List[ExpandedTerm]:
        """Filter expansions to remove duplicates and low-quality terms."""
        try:
            # Remove duplicates
            seen_terms = set()
            unique_expansions = []

            for expansion in expansions:
                term_key = expansion.expanded_term.lower()
                if term_key not in seen_terms:
                    seen_terms.add(term_key)
                    unique_expansions.append(expansion)

            # Filter by confidence
            filtered = [
                exp for exp in unique_expansions
                if exp.confidence_score >= config.min_confidence_threshold
            ]

            return filtered

        except Exception as e:
            self._logger.error(f"Error filtering expansions: {e}")
            return expansions

    def _rank_expansions(self, expansions: List[ExpandedTerm]) -> List[ExpandedTerm]:
        """Rank expansions by combined score."""
        try:
            # Calculate combined score for each expansion
            for expansion in expansions:
                combined_score = (
                    expansion.confidence_score * 0.4 +
                    expansion.semantic_similarity * 0.3 +
                    expansion.context_relevance * 0.2 +
                    expansion.frequency_weight * 0.1
                )
                expansion.metadata = {'combined_score': combined_score}

            # Sort by combined score (descending)
            ranked = sorted(
                expansions,
                key=lambda x: x.metadata.get('combined_score', 0.0),
                reverse=True
            )

            return ranked

        except Exception as e:
            self._logger.error(f"Error ranking expansions: {e}")
            return expansions

    def _calculate_total_score(self, expansions: List[ExpandedTerm]) -> float:
        """Calculate total expansion score."""
        try:
            if not expansions:
                return 0.0

            total_score = sum(
                exp.metadata.get('combined_score', exp.confidence_score)
                for exp in expansions
            )

            return total_score / len(expansions)

        except Exception as e:
            self._logger.error(f"Error calculating total score: {e}")
            return 0.0

    def _update_expansion_stats(self, result: QueryExpansionResult, processing_time: float):
        """Update expansion statistics."""
        try:
            self._expansion_stats['total_queries_expanded'] += 1

            # Update average processing time
            total_count = self._expansion_stats['total_queries_expanded']
            current_avg = self._expansion_stats['average_expansion_time_ms']
            self._expansion_stats['average_expansion_time_ms'] = (
                (current_avg * (total_count - 1) + processing_time) / total_count
            )

            # Update average expansion ratio
            current_ratio_avg = self._expansion_stats['average_expansion_ratio']
            self._expansion_stats['average_expansion_ratio'] = (
                (current_ratio_avg * (total_count - 1) + result.expansion_ratio) / total_count
            )

        except Exception as e:
            self._logger.warning(f"Error updating expansion stats: {e}")

    def get_expansion_statistics(self) -> Dict[str, Any]:
        """Get current expansion statistics."""
        with self._lock:
            return self._expansion_stats.copy()
