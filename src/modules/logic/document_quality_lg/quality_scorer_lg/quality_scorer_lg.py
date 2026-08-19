"""
Module: quality_scorer_lg
Description: Calculates overall document quality scores (0-100) based on multiple metrics
Phase: 3
Location: /src/modules/logic/document_quality_lg/quality_scorer_lg/quality_scorer_lg.py
"""

# Standard library imports
import re
import statistics
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_extraction_lg.base_interfaces import ExtractionResult
from ..base_interfaces import (
    IQualityScorer,
    QualityScoreResult,
    QualityScoringConfig,
    QualityMetric,
    QualityCategory
)


class MetricCalculator:
    """Calculates individual quality metrics for content."""
    
    def __init__(self, language: str = "en"):
        self.language = language
        self._logger = get_logger(__name__)
        self._ensure_nltk_data()
    
    def _ensure_nltk_data(self) -> None:
        """Ensure required NLTK data is available."""
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            try:
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)
            except Exception as e:
                self._logger.warning(f"Could not download NLTK data: {e}")
    
    def calculate_text_coherence(self, content: str) -> float:
        """
        Calculate text coherence score (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Coherence score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            sentences = sent_tokenize(content)
            if len(sentences) < 2:
                return 50.0  # Neutral score for single sentence
            
            # Calculate sentence-to-sentence coherence
            coherence_scores = []
            
            for i in range(len(sentences) - 1):
                current_words = set(word_tokenize(sentences[i].lower()))
                next_words = set(word_tokenize(sentences[i + 1].lower()))
                
                # Remove stopwords and punctuation
                try:
                    stop_words = set(stopwords.words(self.language))
                    current_words = {w for w in current_words if w.isalpha() and w not in stop_words}
                    next_words = {w for w in next_words if w.isalpha() and w not in stop_words}
                except:
                    current_words = {w for w in current_words if w.isalpha()}
                    next_words = {w for w in next_words if w.isalpha()}
                
                # Calculate Jaccard similarity
                if current_words and next_words:
                    intersection = len(current_words.intersection(next_words))
                    union = len(current_words.union(next_words))
                    similarity = intersection / union if union > 0 else 0.0
                    coherence_scores.append(similarity)
            
            if not coherence_scores:
                return 50.0
            
            # Convert to 0-100 scale
            avg_coherence = statistics.mean(coherence_scores)
            return min(avg_coherence * 100, 100.0)
            
        except Exception as e:
            self._logger.error(f"Error calculating text coherence: {e}")
            return 0.0
    
    def calculate_semantic_completeness(self, content: str) -> float:
        """
        Calculate semantic completeness score (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Completeness score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            words = word_tokenize(content.lower())
            if not words:
                return 0.0
            
            # Filter meaningful words
            meaningful_words = [w for w in words if w.isalpha() and len(w) > 2]
            
            if not meaningful_words:
                return 0.0
            
            # Calculate lexical diversity (Type-Token Ratio)
            unique_words = len(set(meaningful_words))
            total_words = len(meaningful_words)
            ttr = unique_words / total_words if total_words > 0 else 0.0
            
            # Calculate information density
            try:
                stop_words = set(stopwords.words(self.language))
                content_words = [w for w in meaningful_words if w not in stop_words]
            except:
                content_words = meaningful_words
            
            info_density = len(content_words) / len(meaningful_words) if meaningful_words else 0.0
            
            # Check for structural completeness
            sentences = sent_tokenize(content)
            has_structure = len(sentences) > 1
            
            # Combine metrics
            completeness_score = (
                ttr * 40 +  # Lexical diversity
                info_density * 40 +  # Information density
                (20 if has_structure else 10)  # Structure bonus
            )
            
            return min(completeness_score, 100.0)
            
        except Exception as e:
            self._logger.error(f"Error calculating semantic completeness: {e}")
            return 0.0
    
    def calculate_extraction_accuracy(self, content: str) -> float:
        """
        Calculate extraction accuracy score (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Accuracy score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            # Check for extraction artifacts and errors
            error_patterns = [
                r'\s{3,}',  # Multiple spaces
                r'[^\w\s]{3,}',  # Multiple special characters
                r'[A-Z]{10,}',  # Long uppercase sequences
                r'\d{10,}',  # Long number sequences
                r'[^\x00-\x7F]{5,}',  # Non-ASCII character sequences
                r'\.{3,}',  # Multiple dots
                r'\n{3,}',  # Multiple line breaks
            ]
            
            total_chars = len(content)
            error_chars = 0
            
            for pattern in error_patterns:
                matches = re.findall(pattern, content)
                error_chars += sum(len(match) for match in matches)
            
            # Calculate accuracy based on error ratio
            error_ratio = error_chars / total_chars if total_chars > 0 else 0.0
            accuracy_score = max(0.0, (1.0 - error_ratio * 2)) * 100
            
            # Check for proper sentence structure
            sentences = sent_tokenize(content)
            if sentences:
                complete_sentences = sum(1 for s in sentences if s.strip().endswith(('.', '!', '?')))
                sentence_completeness = complete_sentences / len(sentences)
                accuracy_score = (accuracy_score * 0.7 + sentence_completeness * 30)
            
            return min(accuracy_score, 100.0)
            
        except Exception as e:
            self._logger.error(f"Error calculating extraction accuracy: {e}")
            return 0.0
    
    def calculate_readability_score(self, content: str) -> float:
        """
        Calculate readability score using Flesch Reading Ease approximation (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Readability score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            sentences = sent_tokenize(content)
            words = word_tokenize(content)
            
            if not sentences or not words:
                return 0.0
            
            # Filter alphabetic words
            words = [w for w in words if w.isalpha()]
            
            if not words:
                return 0.0
            
            # Calculate basic metrics
            num_sentences = len(sentences)
            num_words = len(words)
            
            # Estimate syllables (simple approximation)
            num_syllables = sum(self._count_syllables(word) for word in words)
            
            # Calculate average sentence length and syllables per word
            avg_sentence_length = num_words / num_sentences
            avg_syllables_per_word = num_syllables / num_words
            
            # Simplified Flesch Reading Ease formula
            readability = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            
            # Normalize to 0-100 range
            readability = max(0.0, min(100.0, readability))
            
            return readability
            
        except Exception as e:
            self._logger.error(f"Error calculating readability score: {e}")
            return 50.0  # Neutral score on error
    
    def calculate_structure_integrity(self, content: str) -> float:
        """
        Calculate structure integrity score (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Structure integrity score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            lines = content.split('\n')
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            
            if not non_empty_lines:
                return 0.0
            
            structure_score = 0.0
            
            # Check for title/header (first few lines)
            has_title = any(len(line) < 100 and (line.isupper() or line.startswith('#')) 
                          for line in non_empty_lines[:3])
            if has_title:
                structure_score += 20
            
            # Check for paragraphs
            paragraphs = [line for line in non_empty_lines if len(line) > 50]
            if paragraphs:
                paragraph_ratio = len(paragraphs) / len(non_empty_lines)
                structure_score += min(paragraph_ratio * 40, 40)
            
            # Check for lists or structured elements
            list_indicators = ['•', '-', '*', '1.', '2.', '3.', 'a)', 'b)', 'c)']
            has_lists = any(any(line.strip().startswith(indicator) 
                              for indicator in list_indicators) 
                           for line in non_empty_lines)
            if has_lists:
                structure_score += 20
            
            # Check for proper sentence structure
            sentences = sent_tokenize(content)
            if sentences:
                properly_ended = sum(1 for s in sentences if s.strip().endswith(('.', '!', '?')))
                sentence_ratio = properly_ended / len(sentences)
                structure_score += sentence_ratio * 20
            
            return min(structure_score, 100.0)
            
        except Exception as e:
            self._logger.error(f"Error calculating structure integrity: {e}")
            return 0.0
    
    def calculate_content_density(self, content: str) -> float:
        """
        Calculate content density score (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Content density score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            words = word_tokenize(content.lower())
            if not words:
                return 0.0
            
            # Filter meaningful words
            meaningful_words = [w for w in words if w.isalpha() and len(w) > 2]
            
            if not meaningful_words:
                return 0.0
            
            # Remove stopwords
            try:
                stop_words = set(stopwords.words(self.language))
                content_words = [w for w in meaningful_words if w not in stop_words]
            except:
                content_words = meaningful_words
            
            # Calculate density metrics
            word_density = len(content_words) / len(meaningful_words) if meaningful_words else 0.0
            
            # Calculate unique word ratio
            unique_ratio = len(set(content_words)) / len(content_words) if content_words else 0.0
            
            # Calculate information per character
            info_per_char = len(content_words) / len(content) if content else 0.0
            
            # Combine metrics
            density_score = (
                word_density * 40 +
                unique_ratio * 40 +
                min(info_per_char * 1000, 20)  # Normalize character density
            )
            
            return min(density_score, 100.0)
            
        except Exception as e:
            self._logger.error(f"Error calculating content density: {e}")
            return 0.0
    
    def calculate_language_consistency(self, content: str) -> float:
        """
        Calculate language consistency score (0-100).
        
        Args:
            content: Text content to analyze
            
        Returns:
            Language consistency score between 0.0 and 100.0
        """
        try:
            if not content or len(content.strip()) < 10:
                return 0.0
            
            # Check for mixed scripts or encoding issues
            ascii_chars = sum(1 for c in content if ord(c) < 128)
            total_chars = len(content)
            ascii_ratio = ascii_chars / total_chars if total_chars > 0 else 0.0
            
            # Check for consistent punctuation
            sentences = sent_tokenize(content)
            if sentences:
                consistent_endings = sum(1 for s in sentences if s.strip().endswith(('.', '!', '?')))
                punctuation_consistency = consistent_endings / len(sentences)
            else:
                punctuation_consistency = 0.0
            
            # Check for consistent capitalization
            words = word_tokenize(content)
            if words:
                properly_capitalized = sum(1 for word in words 
                                         if word[0].isupper() if word and word[0].isalpha())
                # This is a rough approximation - in real text, not all words should be capitalized
                capitalization_score = 0.8  # Assume reasonable capitalization
            else:
                capitalization_score = 0.0
            
            # Combine metrics
            consistency_score = (
                ascii_ratio * 40 +
                punctuation_consistency * 40 +
                capitalization_score * 20
            )
            
            return min(consistency_score, 100.0)
            
        except Exception as e:
            self._logger.error(f"Error calculating language consistency: {e}")
            return 50.0  # Neutral score on error
    
    def _count_syllables(self, word: str) -> int:
        """Simple syllable counting approximation."""
        try:
            word = word.lower()
            vowels = 'aeiouy'
            syllable_count = 0
            prev_was_vowel = False
            
            for char in word:
                is_vowel = char in vowels
                if is_vowel and not prev_was_vowel:
                    syllable_count += 1
                prev_was_vowel = is_vowel
            
            # Handle silent 'e'
            if word.endswith('e') and syllable_count > 1:
                syllable_count -= 1
            
            # Ensure at least one syllable
            return max(1, syllable_count)
            
        except Exception:
            return 1


class ScoreAggregator:
    """Aggregates individual metric scores into overall quality scores."""

    def __init__(self):
        self._logger = get_logger(__name__)

    def aggregate_scores(self, metric_scores: Dict[QualityMetric, float],
                        weights: Dict[QualityMetric, float]) -> Dict[str, float]:
        """
        Aggregate metric scores using weighted average.

        Args:
            metric_scores: Dictionary of metric scores
            weights: Dictionary of metric weights

        Returns:
            Dictionary with aggregated scores
        """
        try:
            if not metric_scores:
                return {"overall_score": 0.0}

            # Calculate weighted overall score
            total_weighted_score = 0.0
            total_weight = 0.0

            for metric, score in metric_scores.items():
                weight = weights.get(metric, 0.0)
                total_weighted_score += score * weight
                total_weight += weight

            overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

            # Calculate category scores
            category_scores = self._calculate_category_scores(metric_scores)

            return {
                "overall_score": overall_score,
                **category_scores
            }

        except Exception as e:
            self._logger.error(f"Error aggregating scores: {e}")
            return {"overall_score": 0.0}

    def _calculate_category_scores(self, metric_scores: Dict[QualityMetric, float]) -> Dict[str, float]:
        """Calculate scores for quality categories."""
        try:
            category_mapping = {
                QualityCategory.COHERENCE: [QualityMetric.TEXT_COHERENCE],
                QualityCategory.COMPLETENESS: [QualityMetric.SEMANTIC_COMPLETENESS],
                QualityCategory.ACCURACY: [QualityMetric.EXTRACTION_ACCURACY],
                QualityCategory.READABILITY: [QualityMetric.READABILITY_SCORE],
                QualityCategory.STRUCTURE: [QualityMetric.STRUCTURE_INTEGRITY],
                QualityCategory.CONTENT_DENSITY: [QualityMetric.CONTENT_DENSITY],
                QualityCategory.LANGUAGE_QUALITY: [QualityMetric.LANGUAGE_CONSISTENCY]
            }

            category_scores = {}

            for category, metrics in category_mapping.items():
                scores = [metric_scores.get(metric, 0.0) for metric in metrics if metric in metric_scores]
                if scores:
                    category_scores[category.value] = statistics.mean(scores)
                else:
                    category_scores[category.value] = 0.0

            return category_scores

        except Exception as e:
            self._logger.error(f"Error calculating category scores: {e}")
            return {}


class QualityThresholdManager:
    """Manages quality thresholds and provides quality level assessments."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self._logger = get_logger(__name__)
        self.thresholds = thresholds or {
            "excellent": 90.0,
            "good": 75.0,
            "fair": 60.0,
            "poor": 40.0
        }

    def get_quality_level(self, score: float) -> str:
        """
        Get quality level for a given score.

        Args:
            score: Quality score (0-100)

        Returns:
            Quality level string
        """
        try:
            if score >= self.thresholds.get("excellent", 90.0):
                return "excellent"
            elif score >= self.thresholds.get("good", 75.0):
                return "good"
            elif score >= self.thresholds.get("fair", 60.0):
                return "fair"
            elif score >= self.thresholds.get("poor", 40.0):
                return "poor"
            else:
                return "very_poor"

        except Exception as e:
            self._logger.error(f"Error determining quality level: {e}")
            return "unknown"

    def get_recommendations(self, metric_scores: Dict[QualityMetric, float],
                          overall_score: float) -> List[str]:
        """
        Get quality improvement recommendations.

        Args:
            metric_scores: Dictionary of metric scores
            overall_score: Overall quality score

        Returns:
            List of improvement recommendations
        """
        try:
            recommendations = []

            # Overall recommendations
            if overall_score < 40:
                recommendations.append("Content requires significant improvement across multiple areas")
            elif overall_score < 60:
                recommendations.append("Content quality is below acceptable standards")
            elif overall_score < 75:
                recommendations.append("Content quality is fair with room for improvement")
            elif overall_score < 90:
                recommendations.append("Content quality is good with minor improvements possible")

            # Specific metric recommendations
            for metric, score in metric_scores.items():
                if score < 50:
                    if metric == QualityMetric.TEXT_COHERENCE:
                        recommendations.append("Improve text flow and logical connections between sentences")
                    elif metric == QualityMetric.SEMANTIC_COMPLETENESS:
                        recommendations.append("Add missing information and improve content coverage")
                    elif metric == QualityMetric.EXTRACTION_ACCURACY:
                        recommendations.append("Review and correct extraction errors and artifacts")
                    elif metric == QualityMetric.READABILITY_SCORE:
                        recommendations.append("Simplify sentence structure and vocabulary for better readability")
                    elif metric == QualityMetric.STRUCTURE_INTEGRITY:
                        recommendations.append("Improve document structure with clear headings and organization")
                    elif metric == QualityMetric.CONTENT_DENSITY:
                        recommendations.append("Increase information density and reduce redundant content")
                    elif metric == QualityMetric.LANGUAGE_CONSISTENCY:
                        recommendations.append("Ensure consistent language usage and formatting")

            return recommendations

        except Exception as e:
            self._logger.error(f"Error generating recommendations: {e}")
            return ["Unable to generate specific recommendations"]


class QualityScorer(IQualityScorer):
    """
    Main quality scorer that calculates overall document quality scores.

    This class provides comprehensive quality scoring using multiple metrics:
    - Text coherence analysis
    - Semantic completeness assessment
    - Extraction accuracy validation
    - Readability scoring
    - Structure integrity evaluation
    - Content density measurement
    - Language consistency checking
    """

    def __init__(self, language: str = "en"):
        """Initialize quality scorer with language support."""
        self.language = language
        self._logger = get_logger(__name__)

        # Initialize components
        self.metric_calculator = MetricCalculator(language)
        self.score_aggregator = ScoreAggregator()
        self.threshold_manager = QualityThresholdManager()

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
        start_time = time.time()

        try:
            # Use default config if none provided
            if config is None:
                config = QualityScoringConfig()

            # Validate input
            if not content or len(content.strip()) < 10:
                return QualityScoreResult(
                    overall_score=0.0,
                    quality_level="very_poor",
                    recommendations=["Content is too short or empty"],
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            # Calculate individual metric scores
            metric_scores = {}

            # Core metrics
            metric_scores[QualityMetric.TEXT_COHERENCE] = self.metric_calculator.calculate_text_coherence(content)
            metric_scores[QualityMetric.SEMANTIC_COMPLETENESS] = self.metric_calculator.calculate_semantic_completeness(content)
            metric_scores[QualityMetric.EXTRACTION_ACCURACY] = self.metric_calculator.calculate_extraction_accuracy(content)
            metric_scores[QualityMetric.READABILITY_SCORE] = self.metric_calculator.calculate_readability_score(content)
            metric_scores[QualityMetric.STRUCTURE_INTEGRITY] = self.metric_calculator.calculate_structure_integrity(content)
            metric_scores[QualityMetric.CONTENT_DENSITY] = self.metric_calculator.calculate_content_density(content)
            metric_scores[QualityMetric.LANGUAGE_CONSISTENCY] = self.metric_calculator.calculate_language_consistency(content)

            # Enhance with extraction result metrics if available
            if extraction_result and extraction_result.quality_metrics:
                # Adjust scores based on extraction confidence
                extraction_confidence = extraction_result.quality_metrics.overall_confidence
                adjustment_factor = extraction_confidence

                # Apply adjustment to accuracy-related metrics
                metric_scores[QualityMetric.EXTRACTION_ACCURACY] *= adjustment_factor
                metric_scores[QualityMetric.STRUCTURE_INTEGRITY] *= adjustment_factor

            # Aggregate scores
            aggregated_scores = self.score_aggregator.aggregate_scores(metric_scores, config.weights)
            overall_score = aggregated_scores.get("overall_score", 0.0)

            # Ensure score is within bounds
            overall_score = max(config.min_score, min(overall_score, config.max_score))

            # Calculate category scores
            category_scores = {}
            for category in QualityCategory:
                category_scores[category] = aggregated_scores.get(category.value, 0.0)

            # Get quality level
            quality_level = self.threshold_manager.get_quality_level(overall_score)

            # Generate recommendations
            recommendations = self.threshold_manager.get_recommendations(metric_scores, overall_score)

            # Create detailed breakdown
            score_breakdown = {
                "metric_scores": {metric.value: score for metric, score in metric_scores.items()},
                "category_scores": {category.value: score for category, score in category_scores.items()},
                "weights_used": {metric.value: weight for metric, weight in config.weights.items()},
                "thresholds": config.quality_thresholds
            }

            processing_time = (time.time() - start_time) * 1000

            return QualityScoreResult(
                overall_score=overall_score,
                category_scores=category_scores,
                metric_scores=metric_scores,
                quality_level=quality_level,
                score_breakdown=score_breakdown if config.enable_detailed_breakdown else {},
                recommendations=recommendations,
                processing_time_ms=processing_time,
                metadata={
                    "content_length": len(content),
                    "language": self.language,
                    "has_extraction_result": extraction_result is not None,
                    "config_weights": config.weights
                }
            )

        except Exception as e:
            self._logger.error(f"Error calculating quality score: {e}")
            processing_time = (time.time() - start_time) * 1000

            return QualityScoreResult(
                overall_score=0.0,
                quality_level="unknown",
                recommendations=[f"Quality scoring failed: {str(e)}"],
                processing_time_ms=processing_time
            )

    def calculate_metric_score(self, content: str, metric: QualityMetric) -> float:
        """
        Calculate score for specific quality metric.

        Args:
            content: Text content to score
            metric: Quality metric to calculate

        Returns:
            Metric score between 0.0 and 100.0
        """
        try:
            if metric == QualityMetric.TEXT_COHERENCE:
                return self.metric_calculator.calculate_text_coherence(content)
            elif metric == QualityMetric.SEMANTIC_COMPLETENESS:
                return self.metric_calculator.calculate_semantic_completeness(content)
            elif metric == QualityMetric.EXTRACTION_ACCURACY:
                return self.metric_calculator.calculate_extraction_accuracy(content)
            elif metric == QualityMetric.READABILITY_SCORE:
                return self.metric_calculator.calculate_readability_score(content)
            elif metric == QualityMetric.STRUCTURE_INTEGRITY:
                return self.metric_calculator.calculate_structure_integrity(content)
            elif metric == QualityMetric.CONTENT_DENSITY:
                return self.metric_calculator.calculate_content_density(content)
            elif metric == QualityMetric.LANGUAGE_CONSISTENCY:
                return self.metric_calculator.calculate_language_consistency(content)
            else:
                self._logger.warning(f"Unsupported quality metric: {metric}")
                return 0.0

        except Exception as e:
            self._logger.error(f"Error calculating metric score: {e}")
            return 0.0

    def get_quality_recommendations(self, score_result: QualityScoreResult) -> List[str]:
        """
        Get recommendations for improving quality.

        Args:
            score_result: Quality score result

        Returns:
            List of improvement recommendations
        """
        try:
            return self.threshold_manager.get_recommendations(
                score_result.metric_scores,
                score_result.overall_score
            )

        except Exception as e:
            self._logger.error(f"Error getting quality recommendations: {e}")
            return ["Unable to generate recommendations"]

    def batch_calculate_scores(self, content_list: List[str],
                             config: Optional[QualityScoringConfig] = None) -> List[QualityScoreResult]:
        """
        Calculate quality scores for multiple content pieces.

        Args:
            content_list: List of content to score
            config: Quality scoring configuration

        Returns:
            List of QualityScoreResult for each content piece
        """
        try:
            results = []

            for content in content_list:
                result = self.calculate_quality_score(content, None, config)
                results.append(result)

            return results

        except Exception as e:
            self._logger.error(f"Error in batch quality scoring: {e}")
            return []
