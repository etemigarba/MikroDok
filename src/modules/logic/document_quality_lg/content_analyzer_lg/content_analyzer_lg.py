"""
Module: content_analyzer_lg
Description: Evaluates text coherence, completeness, and extraction accuracy
Phase: 3
Location: /src/modules/logic/document_quality_lg/content_analyzer_lg/content_analyzer_lg.py
"""

# Standard library imports
import re
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Third-party imports
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.tag import pos_tag
from nltk.chunk import ne_chunk

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_extraction_lg.base_interfaces import ExtractionResult, QualityMetrics
from ..base_interfaces import (
    IContentAnalyzer,
    ContentAnalysisResult,
    AnalysisConfig,
    QualityMetric,
    QualityCategory
)


class TextCoherenceAnalyzer:
    """Analyzes text coherence using linguistic features."""
    
    def __init__(self, language: str = "en"):
        self.language = language
        self._logger = get_logger(__name__)
        self._ensure_nltk_data()
    
    def _ensure_nltk_data(self) -> None:
        """Ensure required NLTK data is available."""
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
            nltk.data.find('taggers/averaged_perceptron_tagger')
            nltk.data.find('chunkers/maxent_ne_chunker')
            nltk.data.find('corpora/words')
        except LookupError:
            # Download required NLTK data if not available
            try:
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)
                nltk.download('averaged_perceptron_tagger', quiet=True)
                nltk.download('maxent_ne_chunker', quiet=True)
                nltk.download('words', quiet=True)
            except Exception as e:
                self._logger.warning(f"Could not download NLTK data: {e}")
    
    def analyze_coherence(self, content: str) -> Dict[str, float]:
        """
        Analyze text coherence using multiple metrics.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Dictionary with coherence metrics
        """
        try:
            if not content or len(content.strip()) < 10:
                return {"overall_coherence": 0.0, "sentence_coherence": 0.0, 
                       "lexical_coherence": 0.0, "structural_coherence": 0.0}
            
            sentences = sent_tokenize(content)
            if len(sentences) < 2:
                return {"overall_coherence": 0.5, "sentence_coherence": 0.5,
                       "lexical_coherence": 0.5, "structural_coherence": 0.5}
            
            # Calculate different coherence metrics
            sentence_coherence = self._calculate_sentence_coherence(sentences)
            lexical_coherence = self._calculate_lexical_coherence(sentences)
            structural_coherence = self._calculate_structural_coherence(sentences)
            
            # Calculate overall coherence as weighted average
            overall_coherence = (
                sentence_coherence * 0.4 +
                lexical_coherence * 0.4 +
                structural_coherence * 0.2
            )
            
            return {
                "overall_coherence": overall_coherence,
                "sentence_coherence": sentence_coherence,
                "lexical_coherence": lexical_coherence,
                "structural_coherence": structural_coherence
            }
            
        except Exception as e:
            self._logger.error(f"Error analyzing coherence: {e}")
            return {"overall_coherence": 0.0, "sentence_coherence": 0.0,
                   "lexical_coherence": 0.0, "structural_coherence": 0.0}
    
    def _calculate_sentence_coherence(self, sentences: List[str]) -> float:
        """Calculate coherence between consecutive sentences."""
        try:
            if len(sentences) < 2:
                return 0.5
            
            coherence_scores = []
            
            for i in range(len(sentences) - 1):
                current_words = set(word_tokenize(sentences[i].lower()))
                next_words = set(word_tokenize(sentences[i + 1].lower()))
                
                # Remove stopwords
                try:
                    stop_words = set(stopwords.words(self.language))
                    current_words = current_words - stop_words
                    next_words = next_words - stop_words
                except:
                    pass
                
                # Calculate Jaccard similarity
                if current_words and next_words:
                    intersection = len(current_words.intersection(next_words))
                    union = len(current_words.union(next_words))
                    similarity = intersection / union if union > 0 else 0.0
                    coherence_scores.append(similarity)
            
            return statistics.mean(coherence_scores) if coherence_scores else 0.0
            
        except Exception as e:
            self._logger.error(f"Error calculating sentence coherence: {e}")
            return 0.0
    
    def _calculate_lexical_coherence(self, sentences: List[str]) -> float:
        """Calculate lexical coherence using word repetition and semantic fields."""
        try:
            all_words = []
            for sentence in sentences:
                words = word_tokenize(sentence.lower())
                # Filter out punctuation and stopwords
                words = [w for w in words if w.isalpha()]
                try:
                    stop_words = set(stopwords.words(self.language))
                    words = [w for w in words if w not in stop_words]
                except:
                    pass
                all_words.extend(words)
            
            if not all_words:
                return 0.0
            
            # Calculate lexical diversity (Type-Token Ratio)
            unique_words = len(set(all_words))
            total_words = len(all_words)
            ttr = unique_words / total_words if total_words > 0 else 0.0
            
            # Calculate word frequency distribution
            word_freq = Counter(all_words)
            repeated_words = sum(1 for count in word_freq.values() if count > 1)
            repetition_ratio = repeated_words / unique_words if unique_words > 0 else 0.0
            
            # Combine metrics (balanced TTR indicates good lexical coherence)
            # Optimal TTR is around 0.5-0.7 for coherent text
            ttr_score = 1.0 - abs(0.6 - ttr) / 0.6 if ttr <= 1.0 else 0.0
            repetition_score = min(repetition_ratio * 2, 1.0)  # Some repetition is good
            
            return (ttr_score * 0.6 + repetition_score * 0.4)
            
        except Exception as e:
            self._logger.error(f"Error calculating lexical coherence: {e}")
            return 0.0
    
    def _calculate_structural_coherence(self, sentences: List[str]) -> float:
        """Calculate structural coherence using sentence length and complexity."""
        try:
            if not sentences:
                return 0.0
            
            sentence_lengths = [len(word_tokenize(sentence)) for sentence in sentences]
            
            # Calculate length variation (moderate variation is good)
            if len(sentence_lengths) > 1:
                length_std = statistics.stdev(sentence_lengths)
                avg_length = statistics.mean(sentence_lengths)
                cv = length_std / avg_length if avg_length > 0 else 0.0
                # Optimal coefficient of variation is around 0.3-0.5
                length_score = 1.0 - abs(0.4 - cv) / 0.4 if cv <= 1.0 else 0.0
            else:
                length_score = 0.5
            
            # Check for structural markers (transitions, connectives)
            transition_markers = [
                'however', 'therefore', 'furthermore', 'moreover', 'additionally',
                'consequently', 'nevertheless', 'meanwhile', 'subsequently',
                'first', 'second', 'finally', 'in conclusion', 'for example'
            ]
            
            marker_count = 0
            total_sentences = len(sentences)
            
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(marker in sentence_lower for marker in transition_markers):
                    marker_count += 1
            
            marker_ratio = marker_count / total_sentences if total_sentences > 0 else 0.0
            marker_score = min(marker_ratio * 3, 1.0)  # Some markers are good
            
            return (length_score * 0.7 + marker_score * 0.3)
            
        except Exception as e:
            self._logger.error(f"Error calculating structural coherence: {e}")
            return 0.0


class CompletenessAnalyzer:
    """Analyzes content completeness and semantic coverage."""
    
    def __init__(self, language: str = "en"):
        self.language = language
        self._logger = get_logger(__name__)
    
    def analyze_completeness(self, content: str, expected_elements: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Analyze content completeness.
        
        Args:
            content: Text content to analyze
            expected_elements: Optional list of expected content elements
            
        Returns:
            Dictionary with completeness metrics
        """
        try:
            if not content or len(content.strip()) < 10:
                return {"overall_completeness": 0.0, "semantic_completeness": 0.0,
                       "structural_completeness": 0.0, "information_density": 0.0}
            
            semantic_completeness = self._calculate_semantic_completeness(content)
            structural_completeness = self._calculate_structural_completeness(content)
            information_density = self._calculate_information_density(content)
            
            # Calculate element completeness if expected elements provided
            element_completeness = 1.0
            if expected_elements:
                element_completeness = self._calculate_element_completeness(content, expected_elements)
            
            # Calculate overall completeness
            overall_completeness = (
                semantic_completeness * 0.3 +
                structural_completeness * 0.3 +
                information_density * 0.2 +
                element_completeness * 0.2
            )
            
            return {
                "overall_completeness": overall_completeness,
                "semantic_completeness": semantic_completeness,
                "structural_completeness": structural_completeness,
                "information_density": information_density,
                "element_completeness": element_completeness
            }
            
        except Exception as e:
            self._logger.error(f"Error analyzing completeness: {e}")
            return {"overall_completeness": 0.0, "semantic_completeness": 0.0,
                   "structural_completeness": 0.0, "information_density": 0.0}
    
    def _calculate_semantic_completeness(self, content: str) -> float:
        """Calculate semantic completeness using entity and concept coverage."""
        try:
            sentences = sent_tokenize(content)
            if not sentences:
                return 0.0
            
            # Tokenize and tag parts of speech
            words = word_tokenize(content)
            pos_tags = pos_tag(words)
            
            # Count different types of semantic elements
            nouns = sum(1 for word, pos in pos_tags if pos.startswith('NN'))
            verbs = sum(1 for word, pos in pos_tags if pos.startswith('VB'))
            adjectives = sum(1 for word, pos in pos_tags if pos.startswith('JJ'))
            
            total_content_words = nouns + verbs + adjectives
            total_words = len([word for word in words if word.isalpha()])
            
            if total_words == 0:
                return 0.0
            
            # Calculate semantic density
            semantic_density = total_content_words / total_words
            
            # Check for named entities
            try:
                chunks = ne_chunk(pos_tags)
                entity_count = sum(1 for chunk in chunks if hasattr(chunk, 'label'))
                entity_density = min(entity_count / len(sentences), 1.0)
            except:
                entity_density = 0.0
            
            # Combine metrics
            return (semantic_density * 0.7 + entity_density * 0.3)
            
        except Exception as e:
            self._logger.error(f"Error calculating semantic completeness: {e}")
            return 0.0

    def _calculate_structural_completeness(self, content: str) -> float:
        """Calculate structural completeness using document organization."""
        try:
            lines = content.split('\n')
            non_empty_lines = [line.strip() for line in lines if line.strip()]

            if not non_empty_lines:
                return 0.0

            # Check for structural elements
            has_title = any(len(line) < 100 and line.isupper() or
                          line.startswith('#') for line in non_empty_lines[:3])

            # Check for paragraphs (lines with substantial content)
            paragraphs = [line for line in non_empty_lines if len(line) > 50]
            paragraph_ratio = len(paragraphs) / len(non_empty_lines)

            # Check for lists or structured content
            list_indicators = ['•', '-', '*', '1.', '2.', '3.', 'a)', 'b)', 'c)']
            has_lists = any(any(line.strip().startswith(indicator)
                              for indicator in list_indicators)
                           for line in non_empty_lines)

            # Calculate structural score
            title_score = 0.3 if has_title else 0.0
            paragraph_score = min(paragraph_ratio * 1.5, 0.5)
            list_score = 0.2 if has_lists else 0.0

            return title_score + paragraph_score + list_score

        except Exception as e:
            self._logger.error(f"Error calculating structural completeness: {e}")
            return 0.0

    def _calculate_information_density(self, content: str) -> float:
        """Calculate information density using content-to-noise ratio."""
        try:
            words = word_tokenize(content.lower())
            if not words:
                return 0.0

            # Filter meaningful words
            meaningful_words = [w for w in words if w.isalpha() and len(w) > 2]

            try:
                stop_words = set(stopwords.words(self.language))
                content_words = [w for w in meaningful_words if w not in stop_words]
            except:
                content_words = meaningful_words

            if not meaningful_words:
                return 0.0

            # Calculate information density
            density = len(content_words) / len(meaningful_words)

            # Check for repetitive content
            word_freq = Counter(content_words)
            unique_ratio = len(set(content_words)) / len(content_words) if content_words else 0.0

            # Combine metrics
            return (density * 0.6 + unique_ratio * 0.4)

        except Exception as e:
            self._logger.error(f"Error calculating information density: {e}")
            return 0.0

    def _calculate_element_completeness(self, content: str, expected_elements: List[str]) -> float:
        """Calculate completeness based on expected elements."""
        try:
            content_lower = content.lower()
            found_elements = 0

            for element in expected_elements:
                if element.lower() in content_lower:
                    found_elements += 1

            return found_elements / len(expected_elements) if expected_elements else 1.0

        except Exception as e:
            self._logger.error(f"Error calculating element completeness: {e}")
            return 0.0


class ExtractionAccuracyAnalyzer:
    """Analyzes extraction accuracy and quality."""

    def __init__(self, language: str = "en"):
        self.language = language
        self._logger = get_logger(__name__)

    def analyze_accuracy(self, content: str, extraction_result: Optional[ExtractionResult] = None) -> Dict[str, float]:
        """
        Analyze extraction accuracy.

        Args:
            content: Original or extracted text content
            extraction_result: Optional extraction result for comparison

        Returns:
            Dictionary with accuracy metrics
        """
        try:
            if not content or len(content.strip()) < 10:
                return {"overall_accuracy": 0.0, "text_accuracy": 0.0,
                       "format_accuracy": 0.0, "structure_accuracy": 0.0}

            text_accuracy = self._calculate_text_accuracy(content, extraction_result)
            format_accuracy = self._calculate_format_accuracy(content, extraction_result)
            structure_accuracy = self._calculate_structure_accuracy(content, extraction_result)

            # Calculate overall accuracy
            overall_accuracy = (
                text_accuracy * 0.5 +
                format_accuracy * 0.3 +
                structure_accuracy * 0.2
            )

            return {
                "overall_accuracy": overall_accuracy,
                "text_accuracy": text_accuracy,
                "format_accuracy": format_accuracy,
                "structure_accuracy": structure_accuracy
            }

        except Exception as e:
            self._logger.error(f"Error analyzing accuracy: {e}")
            return {"overall_accuracy": 0.0, "text_accuracy": 0.0,
                   "format_accuracy": 0.0, "structure_accuracy": 0.0}

    def _calculate_text_accuracy(self, content: str, extraction_result: Optional[ExtractionResult]) -> float:
        """Calculate text extraction accuracy."""
        try:
            # Check for common extraction errors
            error_indicators = [
                r'\s{3,}',  # Multiple spaces
                r'[^\w\s]{3,}',  # Multiple special characters
                r'[A-Z]{10,}',  # Long uppercase sequences
                r'\d{10,}',  # Long number sequences
                r'[^\x00-\x7F]{5,}'  # Non-ASCII character sequences
            ]

            error_count = 0
            total_chars = len(content)

            for pattern in error_indicators:
                matches = re.findall(pattern, content)
                error_count += sum(len(match) for match in matches)

            if total_chars == 0:
                return 0.0

            error_ratio = error_count / total_chars
            text_accuracy = max(0.0, 1.0 - error_ratio * 2)  # Penalize errors

            # Check extraction quality metrics if available
            if extraction_result and extraction_result.quality_metrics:
                extraction_confidence = extraction_result.quality_metrics.text_confidence
                text_accuracy = (text_accuracy * 0.7 + extraction_confidence * 0.3)

            return text_accuracy

        except Exception as e:
            self._logger.error(f"Error calculating text accuracy: {e}")
            return 0.0

    def _calculate_format_accuracy(self, content: str, extraction_result: Optional[ExtractionResult]) -> float:
        """Calculate format preservation accuracy."""
        try:
            # Check for preserved formatting elements
            format_elements = {
                'paragraphs': len(content.split('\n\n')),
                'line_breaks': content.count('\n'),
                'bullet_points': len(re.findall(r'[•\-\*]\s', content)),
                'numbers': len(re.findall(r'\d+\.?\s', content)),
                'quotes': content.count('"') + content.count("'")
            }

            # Calculate format preservation score
            format_score = 0.0

            # Paragraph structure
            if format_elements['paragraphs'] > 1:
                format_score += 0.3

            # Line breaks (reasonable amount)
            line_break_ratio = format_elements['line_breaks'] / len(content.split())
            if 0.05 <= line_break_ratio <= 0.2:
                format_score += 0.2

            # Lists and structure
            if format_elements['bullet_points'] > 0 or format_elements['numbers'] > 0:
                format_score += 0.3

            # Text formatting
            if format_elements['quotes'] > 0:
                format_score += 0.2

            return min(format_score, 1.0)

        except Exception as e:
            self._logger.error(f"Error calculating format accuracy: {e}")
            return 0.0

    def _calculate_structure_accuracy(self, content: str, extraction_result: Optional[ExtractionResult]) -> float:
        """Calculate structural accuracy."""
        try:
            # Check for logical structure
            sentences = sent_tokenize(content)
            if not sentences:
                return 0.0

            # Check sentence completeness
            complete_sentences = sum(1 for s in sentences if s.strip().endswith(('.', '!', '?')))
            sentence_completeness = complete_sentences / len(sentences)

            # Check for proper capitalization
            properly_capitalized = sum(1 for s in sentences if s.strip() and s.strip()[0].isupper())
            capitalization_score = properly_capitalized / len(sentences)

            # Check for reasonable sentence length
            avg_sentence_length = statistics.mean([len(word_tokenize(s)) for s in sentences])
            length_score = 1.0 if 5 <= avg_sentence_length <= 30 else 0.5

            # Combine metrics
            structure_accuracy = (
                sentence_completeness * 0.4 +
                capitalization_score * 0.3 +
                length_score * 0.3
            )

            return structure_accuracy

        except Exception as e:
            self._logger.error(f"Error calculating structure accuracy: {e}")
            return 0.0


class ContentAnalyzer(IContentAnalyzer):
    """
    Main content analyzer that evaluates text coherence, completeness, and extraction accuracy.

    This class provides comprehensive content analysis using multiple specialized analyzers:
    - TextCoherenceAnalyzer: Evaluates text flow and linguistic coherence
    - CompletenessAnalyzer: Assesses semantic coverage and information completeness
    - ExtractionAccuracyAnalyzer: Validates extraction quality and accuracy
    """

    def __init__(self, language: str = "en"):
        """Initialize content analyzer with language support."""
        self.language = language
        self._logger = get_logger(__name__)

        # Initialize specialized analyzers
        self.coherence_analyzer = TextCoherenceAnalyzer(language)
        self.completeness_analyzer = CompletenessAnalyzer(language)
        self.accuracy_analyzer = ExtractionAccuracyAnalyzer(language)

    def analyze_content(self, content: str, config: Optional[AnalysisConfig] = None) -> ContentAnalysisResult:
        """
        Analyze content for coherence, completeness, and accuracy.

        Args:
            content: Text content to analyze
            config: Analysis configuration

        Returns:
            ContentAnalysisResult with comprehensive analysis details
        """
        start_time = time.time()

        try:
            # Use default config if none provided
            if config is None:
                config = AnalysisConfig()

            # Validate input
            if not content or len(content.strip()) < config.min_text_length:
                return ContentAnalysisResult(
                    coherence_score=0.0,
                    completeness_score=0.0,
                    accuracy_score=0.0,
                    overall_score=0.0,
                    issues_found=["Content too short or empty"],
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            if len(content) > config.max_text_length:
                content = content[:config.max_text_length]

            # Perform analysis
            analysis_details = {}
            issues_found = []
            recommendations = []

            # Coherence analysis
            coherence_score = 0.0
            if config.check_coherence:
                coherence_results = self.coherence_analyzer.analyze_coherence(content)
                coherence_score = coherence_results.get("overall_coherence", 0.0)
                analysis_details["coherence"] = coherence_results

                if coherence_score < config.coherence_threshold:
                    issues_found.append(f"Low text coherence: {coherence_score:.2f}")
                    recommendations.append("Improve sentence flow and logical connections")

            # Completeness analysis
            completeness_score = 0.0
            if config.check_completeness:
                completeness_results = self.completeness_analyzer.analyze_completeness(content)
                completeness_score = completeness_results.get("overall_completeness", 0.0)
                analysis_details["completeness"] = completeness_results

                if completeness_score < config.completeness_threshold:
                    issues_found.append(f"Low content completeness: {completeness_score:.2f}")
                    recommendations.append("Add missing information and improve content coverage")

            # Accuracy analysis
            accuracy_score = 0.0
            if config.check_accuracy:
                accuracy_results = self.accuracy_analyzer.analyze_accuracy(content)
                accuracy_score = accuracy_results.get("overall_accuracy", 0.0)
                analysis_details["accuracy"] = accuracy_results

                if accuracy_score < config.accuracy_threshold:
                    issues_found.append(f"Low extraction accuracy: {accuracy_score:.2f}")
                    recommendations.append("Review and correct extraction errors")

            # Calculate overall score
            scores = [s for s in [coherence_score, completeness_score, accuracy_score] if s > 0]
            overall_score = statistics.mean(scores) if scores else 0.0

            # Convert to 0-100 scale
            coherence_score *= 100
            completeness_score *= 100
            accuracy_score *= 100
            overall_score *= 100

            # Add general recommendations
            if overall_score < 60:
                recommendations.append("Consider reviewing and improving content quality")
            elif overall_score < 80:
                recommendations.append("Good quality with room for improvement")

            processing_time = (time.time() - start_time) * 1000

            return ContentAnalysisResult(
                coherence_score=coherence_score,
                completeness_score=completeness_score,
                accuracy_score=accuracy_score,
                overall_score=overall_score,
                analysis_details=analysis_details,
                issues_found=issues_found,
                recommendations=recommendations,
                processing_time_ms=processing_time,
                metadata={
                    "content_length": len(content),
                    "language": self.language,
                    "analysis_config": {
                        "check_coherence": config.check_coherence,
                        "check_completeness": config.check_completeness,
                        "check_accuracy": config.check_accuracy
                    }
                }
            )

        except Exception as e:
            self._logger.error(f"Error analyzing content: {e}")
            processing_time = (time.time() - start_time) * 1000

            return ContentAnalysisResult(
                coherence_score=0.0,
                completeness_score=0.0,
                accuracy_score=0.0,
                overall_score=0.0,
                issues_found=[f"Analysis failed: {str(e)}"],
                processing_time_ms=processing_time
            )

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
        try:
            # Analyze the extracted content
            content_analysis = self.analyze_content(extraction_result.content, config)

            # Enhance analysis with extraction-specific metrics
            if extraction_result.quality_metrics:
                # Incorporate extraction quality metrics
                extraction_confidence = extraction_result.quality_metrics.overall_confidence

                # Adjust scores based on extraction confidence
                adjustment_factor = extraction_confidence
                content_analysis.coherence_score *= adjustment_factor
                content_analysis.completeness_score *= adjustment_factor
                content_analysis.accuracy_score *= adjustment_factor
                content_analysis.overall_score *= adjustment_factor

                # Add extraction-specific details
                content_analysis.analysis_details["extraction_metrics"] = {
                    "extraction_confidence": extraction_confidence,
                    "text_confidence": extraction_result.quality_metrics.text_confidence,
                    "structure_confidence": extraction_result.quality_metrics.structure_confidence,
                    "completeness_score": extraction_result.quality_metrics.completeness_score
                }

                # Add extraction-specific issues
                if extraction_result.quality_metrics.corruption_indicators:
                    content_analysis.issues_found.extend(
                        f"Extraction issue: {indicator}"
                        for indicator in extraction_result.quality_metrics.corruption_indicators
                    )

                if extraction_result.quality_metrics.warnings:
                    content_analysis.issues_found.extend(
                        f"Extraction warning: {warning}"
                        for warning in extraction_result.quality_metrics.warnings
                    )

            # Add extraction result metadata
            content_analysis.metadata.update({
                "extraction_status": extraction_result.status.value,
                "has_tables": len(extraction_result.tables) > 0,
                "has_images": len(extraction_result.images) > 0,
                "validation_errors": len(extraction_result.validation_errors)
            })

            return content_analysis

        except Exception as e:
            self._logger.error(f"Error analyzing extraction result: {e}")
            return ContentAnalysisResult(
                coherence_score=0.0,
                completeness_score=0.0,
                accuracy_score=0.0,
                overall_score=0.0,
                issues_found=[f"Extraction analysis failed: {str(e)}"]
            )

    def get_analysis_config_schema(self) -> Dict[str, Any]:
        """
        Get schema for analysis configuration.

        Returns:
            JSON schema for configuration validation
        """
        return {
            "type": "object",
            "properties": {
                "check_coherence": {"type": "boolean", "default": True},
                "check_completeness": {"type": "boolean", "default": True},
                "check_accuracy": {"type": "boolean", "default": True},
                "min_text_length": {"type": "integer", "minimum": 1, "default": 10},
                "max_text_length": {"type": "integer", "minimum": 100, "default": 1000000},
                "language": {"type": "string", "default": "en"},
                "coherence_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.7},
                "completeness_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.8},
                "accuracy_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.9},
                "enable_detailed_analysis": {"type": "boolean", "default": True},
                "analysis_timeout_seconds": {"type": "integer", "minimum": 10, "default": 300}
            },
            "required": [],
            "additionalProperties": False
        }
