"""
Module: chunk_validator_lg
Description: Validates chunk boundaries, token counts, and semantic completeness
Phase: 3
Location: /src/modules/logic/document_chunking_lg/chunk_validator_lg/
"""

# Standard library imports
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# Third-party imports
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Local imports
from src.modules.logic.error_handling_lg import ValidationError, ValidationSeverity
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IChunkValidator,
    DocumentChunk,
    ChunkConfig,
    ChunkValidationResult
)


@dataclass
class ChunkValidationConfig:
    """Configuration for chunk validation."""
    min_token_count: int = 50
    max_token_count: int = 2048
    min_sentence_count: int = 1
    max_sentence_count: int = 50
    min_quality_score: float = 0.5
    check_semantic_completeness: bool = True
    check_boundary_integrity: bool = True
    check_content_coherence: bool = True
    language: str = "english"
    custom_validators: List[str] = field(default_factory=list)


class TokenValidator:
    """Validates token-related aspects of chunks."""
    
    def __init__(self, language: str = "english"):
        self.language = language
        self._logger = get_logger(__name__)
        
        # Download required NLTK data if not present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
    
    def validate_token_count(self, chunk: DocumentChunk, config: ChunkValidationConfig) -> List[ValidationError]:
        """
        Validate token count is within acceptable range.
        
        Args:
            chunk: Document chunk to validate
            config: Validation configuration
            
        Returns:
            List of validation errors
        """
        errors = []
        token_count = chunk.metadata.token_count
        
        if token_count < config.min_token_count:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_token_count",
                error_message=f"Token count {token_count} below minimum {config.min_token_count}",
                severity=ValidationSeverity.WARNING,
                expected_value=config.min_token_count,
                actual_value=token_count
            ))
        
        if token_count > config.max_token_count:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_token_count",
                error_message=f"Token count {token_count} exceeds maximum {config.max_token_count}",
                severity=ValidationSeverity.ERROR,
                expected_value=config.max_token_count,
                actual_value=token_count
            ))
        
        return errors
    
    def validate_token_distribution(self, chunk: DocumentChunk) -> List[ValidationError]:
        """
        Validate token distribution within chunk.
        
        Args:
            chunk: Document chunk to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        try:
            tokens = word_tokenize(chunk.content, language=self.language)
            
            if not tokens:
                errors.append(ValidationError(
                    field_name=f"chunk_{chunk.chunk_id}_tokens",
                    error_message="Chunk contains no valid tokens",
                    severity=ValidationSeverity.ERROR,
                    actual_value=0
                ))
                return errors
            
            # Check for extremely long tokens (potential parsing issues)
            long_tokens = [token for token in tokens if len(token) > 50]
            if long_tokens:
                errors.append(ValidationError(
                    field_name=f"chunk_{chunk.chunk_id}_long_tokens",
                    error_message=f"Found {len(long_tokens)} unusually long tokens",
                    severity=ValidationSeverity.WARNING,
                    actual_value=len(long_tokens)
                ))
            
            # Check for token diversity
            unique_tokens = set(tokens)
            diversity_ratio = len(unique_tokens) / len(tokens)
            
            if diversity_ratio < 0.3:  # Less than 30% unique tokens
                errors.append(ValidationError(
                    field_name=f"chunk_{chunk.chunk_id}_token_diversity",
                    error_message=f"Low token diversity: {diversity_ratio:.2f}",
                    severity=ValidationSeverity.WARNING,
                    actual_value=diversity_ratio
                ))
            
        except Exception as e:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_token_validation",
                error_message=f"Token validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR
            ))
        
        return errors


class BoundaryValidator:
    """Validates chunk boundary integrity."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def validate_boundaries(self, chunk: DocumentChunk) -> List[ValidationError]:
        """
        Validate chunk boundary positions.
        
        Args:
            chunk: Document chunk to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        metadata = chunk.metadata
        
        # Validate character positions
        if metadata.start_char < 0:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_start_char",
                error_message="Start character position cannot be negative",
                severity=ValidationSeverity.ERROR,
                actual_value=metadata.start_char
            ))
        
        if metadata.end_char <= metadata.start_char:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_end_char",
                error_message="End character position must be greater than start position",
                severity=ValidationSeverity.ERROR,
                expected_value=f"> {metadata.start_char}",
                actual_value=metadata.end_char
            ))
        
        # Validate content length matches position difference
        expected_length = metadata.end_char - metadata.start_char
        actual_length = len(chunk.content)
        
        # Allow some tolerance for whitespace normalization
        if abs(expected_length - actual_length) > 10:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_length_mismatch",
                error_message="Content length doesn't match character positions",
                severity=ValidationSeverity.WARNING,
                expected_value=expected_length,
                actual_value=actual_length
            ))
        
        return errors
    
    def validate_boundary_completeness(self, chunk: DocumentChunk) -> List[ValidationError]:
        """
        Validate that chunk boundaries preserve semantic completeness.
        
        Args:
            chunk: Document chunk to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        content = chunk.content.strip()
        
        if not content:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_empty_content",
                error_message="Chunk content is empty",
                severity=ValidationSeverity.ERROR
            ))
            return errors
        
        # Check for incomplete sentences at boundaries
        if not self._ends_with_sentence_terminator(content):
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_incomplete_sentence",
                error_message="Chunk may end with incomplete sentence",
                severity=ValidationSeverity.WARNING
            ))
        
        if not self._starts_with_capital_or_continuation(content):
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_incomplete_start",
                error_message="Chunk may start with incomplete sentence",
                severity=ValidationSeverity.WARNING
            ))
        
        return errors
    
    def _ends_with_sentence_terminator(self, content: str) -> bool:
        """Check if content ends with sentence terminator."""
        return bool(re.search(r'[.!?]\s*$', content))
    
    def _starts_with_capital_or_continuation(self, content: str) -> bool:
        """Check if content starts appropriately."""
        # Allow capital letters, numbers, or common continuation words
        return bool(re.match(r'^[A-Z0-9]|^(and|but|or|however|therefore|thus)', content))


class SemanticValidator:
    """Validates semantic aspects of chunks."""
    
    def __init__(self, language: str = "english"):
        self.language = language
        self._logger = get_logger(__name__)
        
        # Common stop words for coherence analysis
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being'
        }
    
    def validate_semantic_completeness(self, chunk: DocumentChunk) -> List[ValidationError]:
        """
        Validate semantic completeness of chunk.
        
        Args:
            chunk: Document chunk to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        try:
            content = chunk.content.strip()
            
            if not content:
                return errors
            
            # Check for balanced punctuation
            if not self._has_balanced_punctuation(content):
                errors.append(ValidationError(
                    field_name=f"chunk_{chunk.chunk_id}_unbalanced_punctuation",
                    error_message="Chunk has unbalanced punctuation (quotes, parentheses, etc.)",
                    severity=ValidationSeverity.WARNING
                ))
            
            # Check for coherent sentence structure
            sentences = sent_tokenize(content, language=self.language)
            if len(sentences) == 0:
                errors.append(ValidationError(
                    field_name=f"chunk_{chunk.chunk_id}_no_sentences",
                    error_message="Chunk contains no recognizable sentences",
                    severity=ValidationSeverity.WARNING
                ))
            
            # Check for topic coherence (simple heuristic)
            coherence_score = self._calculate_topic_coherence(content)
            if coherence_score < 0.3:
                errors.append(ValidationError(
                    field_name=f"chunk_{chunk.chunk_id}_low_coherence",
                    error_message=f"Low topic coherence score: {coherence_score:.2f}",
                    severity=ValidationSeverity.WARNING,
                    actual_value=coherence_score
                ))
            
        except Exception as e:
            errors.append(ValidationError(
                field_name=f"chunk_{chunk.chunk_id}_semantic_validation",
                error_message=f"Semantic validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR
            ))
        
        return errors
    
    def calculate_quality_score(self, chunk: DocumentChunk) -> float:
        """
        Calculate overall quality score for chunk.
        
        Args:
            chunk: Document chunk to evaluate
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        try:
            content = chunk.content.strip()
            
            if not content:
                return 0.0
            
            scores = []
            
            # Length score (prefer chunks near target size)
            length_score = self._calculate_length_score(chunk)
            scores.append(length_score)
            
            # Completeness score
            completeness_score = self._calculate_completeness_score(content)
            scores.append(completeness_score)
            
            # Coherence score
            coherence_score = self._calculate_topic_coherence(content)
            scores.append(coherence_score)
            
            # Readability score
            readability_score = self._calculate_readability_score(content)
            scores.append(readability_score)
            
            # Return weighted average
            return sum(scores) / len(scores)
            
        except Exception as e:
            self._logger.warning(f"Quality score calculation failed: {e}")
            return 0.5  # Default neutral score
    
    def _has_balanced_punctuation(self, content: str) -> bool:
        """Check for balanced punctuation marks."""
        # Check quotes
        quote_count = content.count('"')
        if quote_count % 2 != 0:
            return False
        
        # Check parentheses
        open_parens = content.count('(')
        close_parens = content.count(')')
        if open_parens != close_parens:
            return False
        
        # Check brackets
        open_brackets = content.count('[')
        close_brackets = content.count(']')
        if open_brackets != close_brackets:
            return False
        
        return True
    
    def _calculate_topic_coherence(self, content: str) -> float:
        """Calculate simple topic coherence score."""
        try:
            words = word_tokenize(content.lower(), language=self.language)
            content_words = [word for word in words if word.isalpha() and word not in self.stop_words]
            
            if len(content_words) < 5:
                return 0.5  # Neutral score for very short content
            
            # Calculate word repetition as coherence indicator
            word_freq = {}
            for word in content_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Higher repetition of content words suggests coherence
            repeated_words = sum(1 for freq in word_freq.values() if freq > 1)
            coherence_ratio = repeated_words / len(word_freq)
            
            return min(1.0, coherence_ratio * 2)  # Scale to 0-1 range
            
        except Exception:
            return 0.5
    
    def _calculate_length_score(self, chunk: DocumentChunk) -> float:
        """Calculate score based on chunk length relative to target."""
        token_count = chunk.metadata.token_count
        target_size = 512  # Default target
        
        if token_count == 0:
            return 0.0
        
        # Optimal range is 80-120% of target
        optimal_min = target_size * 0.8
        optimal_max = target_size * 1.2
        
        if optimal_min <= token_count <= optimal_max:
            return 1.0
        elif token_count < optimal_min:
            return token_count / optimal_min
        else:
            # Penalize oversized chunks more heavily
            return max(0.1, optimal_max / token_count)
    
    def _calculate_completeness_score(self, content: str) -> float:
        """Calculate completeness score based on sentence structure."""
        try:
            sentences = sent_tokenize(content, language=self.language)
            
            if not sentences:
                return 0.0
            
            complete_sentences = 0
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and re.search(r'[.!?]$', sentence):
                    complete_sentences += 1
            
            return complete_sentences / len(sentences)
            
        except Exception:
            return 0.5
    
    def _calculate_readability_score(self, content: str) -> float:
        """Calculate simple readability score."""
        try:
            sentences = sent_tokenize(content, language=self.language)
            words = word_tokenize(content, language=self.language)
            
            if not sentences or not words:
                return 0.0
            
            avg_sentence_length = len(words) / len(sentences)
            
            # Prefer moderate sentence lengths (10-20 words)
            if 10 <= avg_sentence_length <= 20:
                return 1.0
            elif avg_sentence_length < 10:
                return avg_sentence_length / 10
            else:
                return max(0.1, 20 / avg_sentence_length)
                
        except Exception:
            return 0.5


class ChunkValidator(IChunkValidator):
    """Comprehensive chunk validator."""
    
    def __init__(self, config: Optional[ChunkValidationConfig] = None):
        self.config = config or ChunkValidationConfig()
        self.token_validator = TokenValidator(self.config.language)
        self.boundary_validator = BoundaryValidator()
        self.semantic_validator = SemanticValidator(self.config.language)
        self._logger = get_logger(__name__)
    
    def validate_chunk(self, chunk: DocumentChunk, config: ChunkConfig) -> ChunkValidationResult:
        """
        Validate a single document chunk.
        
        Args:
            chunk: Document chunk to validate
            config: Chunking configuration
            
        Returns:
            Validation result with errors and recommendations
        """
        try:
            errors = []
            warnings = []
            recommendations = []
            
            # Token validation
            token_errors = self.token_validator.validate_token_count(chunk, self.config)
            errors.extend(token_errors)
            
            token_dist_errors = self.token_validator.validate_token_distribution(chunk)
            errors.extend(token_dist_errors)
            
            # Boundary validation
            if self.config.check_boundary_integrity:
                boundary_errors = self.boundary_validator.validate_boundaries(chunk)
                errors.extend(boundary_errors)
                
                completeness_errors = self.boundary_validator.validate_boundary_completeness(chunk)
                errors.extend(completeness_errors)
            
            # Semantic validation
            if self.config.check_semantic_completeness:
                semantic_errors = self.semantic_validator.validate_semantic_completeness(chunk)
                errors.extend(semantic_errors)
            
            # Calculate quality score
            quality_score = self.calculate_quality_score(chunk)
            
            # Generate recommendations
            if quality_score < self.config.min_quality_score:
                recommendations.append(f"Quality score {quality_score:.2f} below threshold {self.config.min_quality_score}")
            
            if chunk.metadata.token_count < config.min_chunk_size:
                recommendations.append("Consider merging with adjacent chunks to meet minimum size")
            
            if chunk.metadata.token_count > config.max_chunk_size:
                recommendations.append("Consider splitting chunk to reduce size")
            
            # Separate errors and warnings
            validation_errors = [err for err in errors if err.severity == ValidationSeverity.ERROR]
            validation_warnings = [err.error_message for err in errors if err.severity == ValidationSeverity.WARNING]
            
            is_valid = len(validation_errors) == 0 and quality_score >= self.config.min_quality_score
            
            return ChunkValidationResult(
                is_valid=is_valid,
                chunk_id=chunk.chunk_id,
                validation_errors=validation_errors,
                warnings=validation_warnings,
                quality_score=quality_score,
                recommendations=recommendations
            )
            
        except Exception as e:
            self._logger.error(f"Chunk validation failed: {e}")
            return ChunkValidationResult(
                is_valid=False,
                chunk_id=chunk.chunk_id,
                validation_errors=[ValidationError(
                    field_name="chunk_validation",
                    error_message=f"Validation failed: {str(e)}",
                    severity=ValidationSeverity.ERROR
                )],
                quality_score=0.0
            )
    
    def validate_chunks(self, chunks: List[DocumentChunk], config: ChunkConfig) -> List[ChunkValidationResult]:
        """
        Validate a list of document chunks.
        
        Args:
            chunks: List of document chunks
            config: Chunking configuration
            
        Returns:
            List of validation results
        """
        results = []
        
        for chunk in chunks:
            result = self.validate_chunk(chunk, config)
            results.append(result)
        
        return results
    
    def check_semantic_completeness(self, chunk: DocumentChunk) -> bool:
        """
        Check if chunk is semantically complete.
        
        Args:
            chunk: Document chunk to check
            
        Returns:
            True if chunk is semantically complete
        """
        errors = self.semantic_validator.validate_semantic_completeness(chunk)
        return len([err for err in errors if err.severity == ValidationSeverity.ERROR]) == 0
    
    def calculate_quality_score(self, chunk: DocumentChunk) -> float:
        """
        Calculate quality score for a chunk.
        
        Args:
            chunk: Document chunk to score
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        return self.semantic_validator.calculate_quality_score(chunk)
