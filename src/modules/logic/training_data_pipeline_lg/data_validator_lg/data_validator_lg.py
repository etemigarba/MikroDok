"""
Module: data_validator_lg
Description: Validates training data quality and completeness with comprehensive checks
Phase: 4
Location: /src/modules/logic/training_data_pipeline_lg/data_validator_lg/data_validator_lg.py
"""

# Standard library imports
import json
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.training_data_pipeline_lg.base_interfaces import (
    IDataValidator,
    ValidationConfig,
    ValidationLevel,
    DataSample,
    ValidationResult,
    DataStatus
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class FormatValidator:
    """Handles format validation for data samples."""
    
    def __init__(self):
        """Initialize format validator."""
        self._logger = get_logger(__name__)
    
    def validate_text_format(self, text: str, config: ValidationConfig) -> Tuple[bool, List[str]]:
        """
        Validate text format.
        
        Args:
            text: Text to validate
            config: Validation configuration
            
        Returns:
            Tuple of (is_valid, issues)
        """
        issues = []
        
        # Check text length
        if len(text) < config.min_text_length:
            issues.append(f"Text too short: {len(text)} < {config.min_text_length}")
        
        if len(text) > config.max_text_length:
            issues.append(f"Text too long: {len(text)} > {config.max_text_length}")
        
        # Check encoding
        if config.check_encoding:
            try:
                text.encode('utf-8')
            except UnicodeEncodeError as e:
                issues.append(f"Encoding error: {e}")
        
        # Check for forbidden patterns
        for pattern in config.forbidden_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Forbidden pattern found: {pattern}")
        
        # Check for required fields (if text represents structured data)
        if config.required_fields:
            # This is a simplified check - in practice, you'd parse the text
            for field in config.required_fields:
                if field.lower() not in text.lower():
                    issues.append(f"Required field missing: {field}")
        
        return len(issues) == 0, issues
    
    def validate_encoding(self, text: str) -> Tuple[bool, List[str]]:
        """Validate text encoding."""
        issues = []
        
        try:
            # Check UTF-8 encoding
            text.encode('utf-8').decode('utf-8')
            
            # Check for control characters
            control_chars = [c for c in text if ord(c) < 32 and c not in '\t\n\r']
            if control_chars:
                issues.append(f"Control characters found: {len(control_chars)}")
            
            # Check for null bytes
            if '\x00' in text:
                issues.append("Null bytes found in text")
                
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            issues.append(f"Encoding validation failed: {e}")
        
        return len(issues) == 0, issues


class QualityValidator:
    """Handles quality validation for data samples."""
    
    def __init__(self):
        """Initialize quality validator."""
        self._logger = get_logger(__name__)
    
    def calculate_quality_score(self, text: str, config: ValidationConfig) -> float:
        """
        Calculate quality score for text.
        
        Args:
            text: Text to evaluate
            config: Validation configuration
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not text.strip():
            return 0.0
        
        scores = []
        
        # Readability score (simplified)
        readability_score = self._calculate_readability(text)
        scores.append(readability_score)
        
        # Coherence score (simplified)
        coherence_score = self._calculate_coherence(text)
        scores.append(coherence_score)
        
        # Completeness score
        completeness_score = self._calculate_completeness(text)
        scores.append(completeness_score)
        
        # Language consistency score
        if config.allowed_languages:
            language_score = self._calculate_language_consistency(text, config.allowed_languages)
            scores.append(language_score)
        
        return np.mean(scores) if scores else 0.0
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score (simplified Flesch-Kincaid)."""
        try:
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            words = text.split()
            syllables = sum(self._count_syllables(word) for word in words)
            
            if not sentences or not words:
                return 0.0
            
            avg_sentence_length = len(words) / len(sentences)
            avg_syllables_per_word = syllables / len(words)
            
            # Simplified Flesch Reading Ease
            score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            
            # Normalize to 0-1 range
            return max(0.0, min(1.0, score / 100.0))
            
        except Exception as e:
            self._logger.warning(f"Failed to calculate readability: {e}")
            return 0.5
    
    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (simplified)."""
        word = word.lower().strip()
        if not word:
            return 0
        
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
        
        return max(1, syllable_count)
    
    def _calculate_coherence(self, text: str) -> float:
        """Calculate coherence score (simplified)."""
        try:
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) < 2:
                return 1.0
            
            # Calculate word overlap between adjacent sentences
            overlaps = []
            for i in range(len(sentences) - 1):
                words1 = set(sentences[i].lower().split())
                words2 = set(sentences[i + 1].lower().split())
                
                if words1 and words2:
                    overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                    overlaps.append(overlap)
            
            return np.mean(overlaps) if overlaps else 0.5
            
        except Exception as e:
            self._logger.warning(f"Failed to calculate coherence: {e}")
            return 0.5
    
    def _calculate_completeness(self, text: str) -> float:
        """Calculate completeness score."""
        try:
            # Check for incomplete sentences
            incomplete_indicators = ['...', '..', 'etc.', 'and so on', '[truncated]', '[...]']
            
            for indicator in incomplete_indicators:
                if indicator in text.lower():
                    return 0.7  # Partially complete
            
            # Check if text ends properly
            if text.strip() and text.strip()[-1] in '.!?':
                return 1.0
            
            return 0.8  # Mostly complete
            
        except Exception as e:
            self._logger.warning(f"Failed to calculate completeness: {e}")
            return 0.5
    
    def _calculate_language_consistency(self, text: str, allowed_languages: List[str]) -> float:
        """Calculate language consistency score (simplified)."""
        try:
            # This is a very simplified language detection
            # In production, you'd use a proper language detection library
            
            # Check for common English words
            english_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            words = set(text.lower().split())
            english_score = len(words.intersection(english_words)) / len(words) if words else 0
            
            if 'en' in allowed_languages and english_score > 0.1:
                return 1.0
            
            return 0.5  # Default score for unknown language
            
        except Exception as e:
            self._logger.warning(f"Failed to calculate language consistency: {e}")
            return 0.5


class ConsistencyValidator:
    """Handles consistency validation across data samples."""
    
    def __init__(self):
        """Initialize consistency validator."""
        self._logger = get_logger(__name__)
    
    def check_duplicates(self, samples: List[DataSample]) -> Tuple[float, List[str]]:
        """
        Check for duplicate samples.
        
        Args:
            samples: List of samples to check
            
        Returns:
            Tuple of (duplicate_ratio, duplicate_ids)
        """
        if not samples:
            return 0.0, []
        
        # Create hash for each sample text
        text_hashes = {}
        duplicates = []
        
        for sample in samples:
            text_hash = hashlib.md5(sample.text.encode()).hexdigest()
            
            if text_hash in text_hashes:
                duplicates.append(sample.sample_id)
            else:
                text_hashes[text_hash] = sample.sample_id
        
        duplicate_ratio = len(duplicates) / len(samples)
        return duplicate_ratio, duplicates
    
    def check_label_consistency(self, samples: List[DataSample]) -> Tuple[bool, List[str]]:
        """Check label consistency across samples."""
        issues = []
        
        # Check for missing labels
        samples_with_labels = [s for s in samples if s.label is not None]
        samples_without_labels = [s for s in samples if s.label is None]
        
        if samples_with_labels and samples_without_labels:
            issues.append(f"Inconsistent labeling: {len(samples_without_labels)} samples missing labels")
        
        # Check label distribution
        if samples_with_labels:
            label_counts = Counter(s.label for s in samples_with_labels)
            
            # Check for severely imbalanced labels
            max_count = max(label_counts.values())
            min_count = min(label_counts.values())
            
            if max_count > min_count * 10:  # 10:1 ratio threshold
                issues.append(f"Severely imbalanced labels: max={max_count}, min={min_count}")
        
        return len(issues) == 0, issues


class DataValidator(IDataValidator):
    """Production-ready data validator for training data quality and completeness."""

    def __init__(self, max_workers: int = 4):
        """
        Initialize data validator.

        Args:
            max_workers: Maximum number of worker threads
        """
        self._logger = get_logger(__name__)
        self.max_workers = max_workers
        self._lock = threading.Lock()

        # Initialize validation components
        self.format_validator = FormatValidator()
        self.quality_validator = QualityValidator()
        self.consistency_validator = ConsistencyValidator()

        # Validation statistics
        self._validation_stats = {
            'total_validated': 0,
            'total_valid': 0,
            'total_invalid': 0,
            'validation_time': 0.0,
            'common_issues': defaultdict(int)
        }

    def validate_sample(self, sample: DataSample, config: ValidationConfig) -> bool:
        """
        Validate a single data sample.

        Args:
            sample: Data sample to validate
            config: Validation configuration

        Returns:
            True if sample is valid
        """
        try:
            # Format validation
            if config.check_format:
                format_valid, format_issues = self.format_validator.validate_text_format(
                    sample.text, config
                )
                if not format_valid:
                    return False

            # Encoding validation
            if config.check_encoding:
                encoding_valid, encoding_issues = self.format_validator.validate_encoding(
                    sample.text
                )
                if not encoding_valid:
                    return False

            # Quality validation
            if config.check_quality:
                quality_score = self.quality_validator.calculate_quality_score(
                    sample.text, config
                )
                if quality_score < config.min_quality_score:
                    return False

            return True

        except Exception as e:
            self._logger.error(f"Failed to validate sample {sample.sample_id}: {e}")
            return False

    def validate_batch(self, samples: List[DataSample], config: ValidationConfig) -> ValidationResult:
        """
        Validate a batch of data samples.

        Args:
            samples: List of samples to validate
            config: Validation configuration

        Returns:
            ValidationResult with validation details
        """
        start_time = time.time()

        try:
            self._logger.info(f"Validating batch of {len(samples)} samples")

            valid_samples = 0
            invalid_samples = 0
            all_issues = []
            quality_scores = []

            # Validate samples in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_sample = {
                    executor.submit(self._validate_sample_detailed, sample, config): sample
                    for sample in samples
                }

                for future in as_completed(future_to_sample):
                    try:
                        is_valid, issues, quality_score = future.result()

                        if is_valid:
                            valid_samples += 1
                        else:
                            invalid_samples += 1
                            all_issues.extend(issues)

                        if quality_score is not None:
                            quality_scores.append(quality_score)

                    except Exception as e:
                        invalid_samples += 1
                        all_issues.append(f"Validation error: {e}")

            # Consistency validation
            consistency_issues = []
            if config.check_consistency:
                consistency_valid, consistency_issues = self._validate_consistency(samples, config)

            # Duplicate validation
            duplicate_ratio = 0.0
            if config.check_duplicates:
                duplicate_ratio, duplicate_ids = self.consistency_validator.check_duplicates(samples)
                if duplicate_ratio > config.max_duplicate_ratio:
                    consistency_issues.append(f"High duplicate ratio: {duplicate_ratio:.2%}")

            # Calculate overall scores
            overall_quality = np.mean(quality_scores) if quality_scores else 0.0
            completeness_score = valid_samples / len(samples) if samples else 0.0
            consistency_score = 1.0 - len(consistency_issues) / max(1, len(samples))

            validation_time = time.time() - start_time

            # Update statistics
            with self._lock:
                self._validation_stats['total_validated'] += len(samples)
                self._validation_stats['total_valid'] += valid_samples
                self._validation_stats['total_invalid'] += invalid_samples
                self._validation_stats['validation_time'] += validation_time

                # Count common issues
                for issue in all_issues:
                    issue_type = issue.split(':')[0] if ':' in issue else issue
                    self._validation_stats['common_issues'][issue_type] += 1

            # Determine overall status
            status = DataStatus.COMPLETED
            if invalid_samples > 0 or consistency_issues:
                if invalid_samples > len(samples) * 0.5:  # More than 50% invalid
                    status = DataStatus.FAILED

            self._logger.info(f"Validation completed: {valid_samples}/{len(samples)} valid in {validation_time:.2f}s")

            return ValidationResult(
                status=status,
                total_samples=len(samples),
                valid_samples=valid_samples,
                invalid_samples=invalid_samples,
                validation_level=config.validation_level,
                quality_score=overall_quality,
                completeness_score=completeness_score,
                consistency_score=consistency_score,
                duplicate_ratio=duplicate_ratio,
                validation_time_seconds=validation_time,
                issues_found=all_issues + consistency_issues,
                recommendations=self._generate_recommendations(all_issues, consistency_issues)
            )

        except Exception as e:
            self._logger.error(f"Failed to validate batch: {e}")
            return ValidationResult(
                status=DataStatus.FAILED,
                total_samples=len(samples),
                valid_samples=0,
                invalid_samples=len(samples),
                validation_level=config.validation_level,
                errors=[str(e)]
            )

    def _validate_sample_detailed(self, sample: DataSample,
                                config: ValidationConfig) -> Tuple[bool, List[str], Optional[float]]:
        """Validate sample with detailed results."""
        issues = []
        quality_score = None

        try:
            # Format validation
            if config.check_format:
                format_valid, format_issues = self.format_validator.validate_text_format(
                    sample.text, config
                )
                if not format_valid:
                    issues.extend(format_issues)

            # Encoding validation
            if config.check_encoding:
                encoding_valid, encoding_issues = self.format_validator.validate_encoding(
                    sample.text
                )
                if not encoding_valid:
                    issues.extend(encoding_issues)

            # Quality validation
            if config.check_quality:
                quality_score = self.quality_validator.calculate_quality_score(
                    sample.text, config
                )
                if quality_score < config.min_quality_score:
                    issues.append(f"Low quality score: {quality_score:.2f} < {config.min_quality_score}")

            return len(issues) == 0, issues, quality_score

        except Exception as e:
            return False, [f"Validation error: {e}"], None

    def _validate_consistency(self, samples: List[DataSample],
                            config: ValidationConfig) -> Tuple[bool, List[str]]:
        """Validate consistency across samples."""
        issues = []

        try:
            # Label consistency
            label_consistent, label_issues = self.consistency_validator.check_label_consistency(samples)
            if not label_consistent:
                issues.extend(label_issues)

            # Check metadata consistency
            if samples:
                metadata_keys = set()
                for sample in samples:
                    metadata_keys.update(sample.metadata.keys())

                # Check if all samples have similar metadata structure
                for sample in samples[:min(100, len(samples))]:  # Sample check
                    missing_keys = metadata_keys - set(sample.metadata.keys())
                    if len(missing_keys) > len(metadata_keys) * 0.5:
                        issues.append(f"Inconsistent metadata structure in sample {sample.sample_id}")
                        break

            return len(issues) == 0, issues

        except Exception as e:
            return False, [f"Consistency validation error: {e}"]

    def _generate_recommendations(self, issues: List[str],
                                consistency_issues: List[str]) -> List[str]:
        """Generate recommendations based on validation issues."""
        recommendations = []

        # Analyze common issue patterns
        issue_types = defaultdict(int)
        for issue in issues:
            issue_type = issue.split(':')[0] if ':' in issue else issue
            issue_types[issue_type] += 1

        # Generate specific recommendations
        if issue_types.get('Text too short', 0) > 0:
            recommendations.append("Consider filtering out very short texts or combining related short texts")

        if issue_types.get('Text too long', 0) > 0:
            recommendations.append("Consider chunking long texts into smaller segments")

        if issue_types.get('Low quality score', 0) > 0:
            recommendations.append("Review and improve text quality through preprocessing or filtering")

        if issue_types.get('Encoding error', 0) > 0:
            recommendations.append("Fix encoding issues by standardizing to UTF-8")

        if any('duplicate' in issue.lower() for issue in consistency_issues):
            recommendations.append("Remove or reduce duplicate samples to improve data quality")

        if any('imbalanced' in issue.lower() for issue in consistency_issues):
            recommendations.append("Consider data augmentation or resampling to balance labels")

        return recommendations

    def validate_dataset(self, data_path: Path, config: ValidationConfig) -> ValidationResult:
        """
        Validate entire dataset.

        Args:
            data_path: Path to dataset
            config: Validation configuration

        Returns:
            ValidationResult with validation details
        """
        try:
            self._logger.info(f"Validating dataset at {data_path}")

            # Load samples from dataset
            # This is a simplified implementation - in practice, you'd use the data loader
            samples = self._load_samples_for_validation(data_path)

            if not samples:
                return ValidationResult(
                    status=DataStatus.FAILED,
                    total_samples=0,
                    valid_samples=0,
                    invalid_samples=0,
                    validation_level=config.validation_level,
                    errors=["No samples found in dataset"]
                )

            # Validate the loaded samples
            return self.validate_batch(samples, config)

        except Exception as e:
            self._logger.error(f"Failed to validate dataset: {e}")
            return ValidationResult(
                status=DataStatus.FAILED,
                total_samples=0,
                valid_samples=0,
                invalid_samples=0,
                validation_level=config.validation_level,
                errors=[str(e)]
            )

    def _load_samples_for_validation(self, data_path: Path) -> List[DataSample]:
        """Load samples from dataset for validation."""
        samples = []

        try:
            if data_path.suffix.lower() == '.json':
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for i, item in enumerate(data):
                    sample = DataSample(
                        sample_id=item.get('id', f"sample_{i}"),
                        text=item.get('text', ''),
                        label=item.get('label'),
                        metadata=item.get('metadata', {})
                    )
                    samples.append(sample)

            elif data_path.suffix.lower() == '.jsonl':
                with open(data_path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if line.strip():
                            item = json.loads(line)
                            sample = DataSample(
                                sample_id=item.get('id', f"sample_{i}"),
                                text=item.get('text', ''),
                                label=item.get('label'),
                                metadata=item.get('metadata', {})
                            )
                            samples.append(sample)

            elif data_path.suffix.lower() == '.txt':
                with open(data_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for i, line in enumerate(lines):
                    if line.strip():
                        sample = DataSample(
                            sample_id=f"sample_{i}",
                            text=line.strip(),
                            metadata={'line_number': i + 1}
                        )
                        samples.append(sample)

        except Exception as e:
            self._logger.error(f"Failed to load samples from {data_path}: {e}")

        return samples

    def get_validation_rules(self) -> Dict[str, Any]:
        """Get current validation rules."""
        return {
            'format_validation': {
                'min_text_length': 'Configurable minimum text length',
                'max_text_length': 'Configurable maximum text length',
                'encoding_check': 'UTF-8 encoding validation',
                'forbidden_patterns': 'Regex patterns to avoid'
            },
            'quality_validation': {
                'readability_score': 'Simplified Flesch-Kincaid readability',
                'coherence_score': 'Word overlap between sentences',
                'completeness_score': 'Check for incomplete text indicators',
                'language_consistency': 'Basic language detection'
            },
            'consistency_validation': {
                'duplicate_detection': 'MD5 hash-based duplicate detection',
                'label_consistency': 'Check for missing or imbalanced labels',
                'metadata_consistency': 'Validate metadata structure'
            },
            'validation_levels': {
                'BASIC': 'Format and encoding checks only',
                'STANDARD': 'Format, encoding, and basic quality checks',
                'STRICT': 'All checks with higher thresholds',
                'COMPREHENSIVE': 'All checks with detailed analysis'
            }
        }

    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        with self._lock:
            total_validated = self._validation_stats['total_validated']

            return {
                'total_validated': total_validated,
                'total_valid': self._validation_stats['total_valid'],
                'total_invalid': self._validation_stats['total_invalid'],
                'validation_success_rate': (
                    self._validation_stats['total_valid'] / max(1, total_validated)
                ),
                'total_validation_time': self._validation_stats['validation_time'],
                'average_validation_time': (
                    self._validation_stats['validation_time'] / max(1, total_validated)
                ),
                'common_issues': dict(self._validation_stats['common_issues'])
            }

    def reset_statistics(self) -> None:
        """Reset validation statistics."""
        with self._lock:
            self._validation_stats = {
                'total_validated': 0,
                'total_valid': 0,
                'total_invalid': 0,
                'validation_time': 0.0,
                'common_issues': defaultdict(int)
            }
