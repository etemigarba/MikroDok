"""
Module: base_interfaces
Description: Base interfaces and common data structures for document quality modules
Phase: 3
Location: /src/modules/logic/document_quality_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Set

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.document_extraction_lg.base_interfaces import ExtractionResult, QualityMetrics


class QualityCategory(Enum):
    """Categories for quality assessment."""
    COHERENCE = "coherence"
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    READABILITY = "readability"
    STRUCTURE = "structure"
    CONTENT_DENSITY = "content_density"
    LANGUAGE_QUALITY = "language_quality"


class QualityMetric(Enum):
    """Individual quality metrics."""
    TEXT_COHERENCE = "text_coherence"
    SEMANTIC_COMPLETENESS = "semantic_completeness"
    EXTRACTION_ACCURACY = "extraction_accuracy"
    READABILITY_SCORE = "readability_score"
    STRUCTURE_INTEGRITY = "structure_integrity"
    CONTENT_DENSITY = "content_density"
    LANGUAGE_CONSISTENCY = "language_consistency"
    FORMATTING_QUALITY = "formatting_quality"


class DuplicateType(Enum):
    """Types of duplicate content."""
    EXACT = "exact"
    NEAR_EXACT = "near_exact"
    SEMANTIC = "semantic"
    PARTIAL = "partial"
    FUZZY = "fuzzy"


class SimilarityMethod(Enum):
    """Methods for similarity calculation."""
    HASH_BASED = "hash_based"
    COSINE_SIMILARITY = "cosine_similarity"
    JACCARD_SIMILARITY = "jaccard_similarity"
    EDIT_DISTANCE = "edit_distance"
    SEMANTIC_EMBEDDING = "semantic_embedding"


@dataclass
class AnalysisConfig:
    """Configuration for content analysis."""
    check_coherence: bool = True
    check_completeness: bool = True
    check_accuracy: bool = True
    min_text_length: int = 10
    max_text_length: int = 1000000
    language: str = "en"
    coherence_threshold: float = 0.7
    completeness_threshold: float = 0.8
    accuracy_threshold: float = 0.9
    enable_detailed_analysis: bool = True
    analysis_timeout_seconds: int = 300


@dataclass
class DeduplicationConfig:
    """Configuration for deduplication."""
    similarity_threshold: float = 0.95
    hash_algorithm: str = "sha256"
    enable_semantic_dedup: bool = True
    enable_fuzzy_matching: bool = False
    chunk_size: int = 1000
    overlap_size: int = 100
    max_distance: int = 5
    similarity_methods: List[SimilarityMethod] = field(default_factory=lambda: [SimilarityMethod.HASH_BASED])
    processing_timeout_seconds: int = 600


@dataclass
class QualityScoringConfig:
    """Configuration for quality scoring."""
    weights: Dict[QualityMetric, float] = field(default_factory=lambda: {
        QualityMetric.TEXT_COHERENCE: 0.2,
        QualityMetric.SEMANTIC_COMPLETENESS: 0.2,
        QualityMetric.EXTRACTION_ACCURACY: 0.2,
        QualityMetric.READABILITY_SCORE: 0.15,
        QualityMetric.STRUCTURE_INTEGRITY: 0.1,
        QualityMetric.CONTENT_DENSITY: 0.1,
        QualityMetric.LANGUAGE_CONSISTENCY: 0.05
    })
    min_score: float = 0.0
    max_score: float = 100.0
    quality_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "excellent": 90.0,
        "good": 75.0,
        "fair": 60.0,
        "poor": 40.0
    })
    enable_detailed_breakdown: bool = True


@dataclass
class ContentAnalysisResult:
    """Result of content analysis."""
    coherence_score: float
    completeness_score: float
    accuracy_score: float
    overall_score: float
    analysis_details: Dict[str, Any] = field(default_factory=dict)
    issues_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_high_quality(self) -> bool:
        """Check if content is considered high quality."""
        return self.overall_score >= 75.0
    
    @property
    def quality_level(self) -> str:
        """Get quality level description."""
        if self.overall_score >= 90.0:
            return "excellent"
        elif self.overall_score >= 75.0:
            return "good"
        elif self.overall_score >= 60.0:
            return "fair"
        elif self.overall_score >= 40.0:
            return "poor"
        else:
            return "very_poor"


@dataclass
class DeduplicationResult:
    """Result of deduplication analysis."""
    is_duplicate: bool
    duplicate_type: DuplicateType
    similarity_score: float
    duplicate_sources: List[str] = field(default_factory=list)
    similarity_details: Dict[SimilarityMethod, float] = field(default_factory=dict)
    hash_values: Dict[str, str] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def confidence_level(self) -> str:
        """Get confidence level of duplicate detection."""
        if self.similarity_score >= 0.95:
            return "very_high"
        elif self.similarity_score >= 0.85:
            return "high"
        elif self.similarity_score >= 0.75:
            return "medium"
        elif self.similarity_score >= 0.65:
            return "low"
        else:
            return "very_low"


@dataclass
class QualityScoreResult:
    """Result of quality scoring."""
    overall_score: float
    category_scores: Dict[QualityCategory, float] = field(default_factory=dict)
    metric_scores: Dict[QualityMetric, float] = field(default_factory=dict)
    quality_level: str = ""
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_acceptable_quality(self) -> bool:
        """Check if quality meets minimum standards."""
        return self.overall_score >= 60.0
    
    def get_top_issues(self, limit: int = 3) -> List[Tuple[str, float]]:
        """Get top quality issues by lowest scores."""
        issues = [(metric.value, score) for metric, score in self.metric_scores.items()]
        return sorted(issues, key=lambda x: x[1])[:limit]


class IContentAnalyzer(ABC):
    """Base interface for content analyzers."""
    
    @abstractmethod
    def analyze_content(self, content: str, config: Optional[AnalysisConfig] = None) -> ContentAnalysisResult:
        """
        Analyze content for coherence, completeness, and accuracy.
        
        Args:
            content: Text content to analyze
            config: Analysis configuration
            
        Returns:
            ContentAnalysisResult with analysis details
        """
        pass
    
    @abstractmethod
    def analyze_extraction_result(self, extraction_result: ExtractionResult, 
                                config: Optional[AnalysisConfig] = None) -> ContentAnalysisResult:
        """
        Analyze extraction result for quality.
        
        Args:
            extraction_result: Document extraction result
            config: Analysis configuration
            
        Returns:
            ContentAnalysisResult with analysis details
        """
        pass
    
    @abstractmethod
    def get_analysis_config_schema(self) -> Dict[str, Any]:
        """
        Get schema for analysis configuration.
        
        Returns:
            JSON schema for configuration validation
        """
        pass


class IDeduplicationEngine(ABC):
    """Base interface for deduplication engines."""
    
    @abstractmethod
    def detect_duplicates(self, content: str, reference_content: List[str], 
                         config: Optional[DeduplicationConfig] = None) -> DeduplicationResult:
        """
        Detect if content is duplicate of reference content.
        
        Args:
            content: Content to check for duplicates
            reference_content: List of reference content to compare against
            config: Deduplication configuration
            
        Returns:
            DeduplicationResult with duplicate detection details
        """
        pass
    
    @abstractmethod
    def calculate_similarity(self, content1: str, content2: str, 
                           method: SimilarityMethod = SimilarityMethod.HASH_BASED) -> float:
        """
        Calculate similarity between two content pieces.
        
        Args:
            content1: First content piece
            content2: Second content piece
            method: Similarity calculation method
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        pass
    
    @abstractmethod
    def get_content_hash(self, content: str, algorithm: str = "sha256") -> str:
        """
        Generate hash for content.
        
        Args:
            content: Content to hash
            algorithm: Hash algorithm to use
            
        Returns:
            Content hash string
        """
        pass


class IQualityScorer(ABC):
    """Base interface for quality scorers."""
    
    @abstractmethod
    def calculate_quality_score(self, content: str, extraction_result: Optional[ExtractionResult] = None,
                              config: Optional[QualityScoringConfig] = None) -> QualityScoreResult:
        """
        Calculate overall quality score for content.
        
        Args:
            content: Text content to score
            extraction_result: Optional extraction result for additional context
            config: Quality scoring configuration
            
        Returns:
            QualityScoreResult with detailed scoring information
        """
        pass
    
    @abstractmethod
    def calculate_metric_score(self, content: str, metric: QualityMetric) -> float:
        """
        Calculate score for specific quality metric.
        
        Args:
            content: Text content to score
            metric: Quality metric to calculate
            
        Returns:
            Metric score between 0.0 and 100.0
        """
        pass
    
    @abstractmethod
    def get_quality_recommendations(self, score_result: QualityScoreResult) -> List[str]:
        """
        Get recommendations for improving quality.
        
        Args:
            score_result: Quality score result
            
        Returns:
            List of improvement recommendations
        """
        pass
