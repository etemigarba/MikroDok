"""
Module: data_augmentation_lg
Description: Applies data augmentation techniques for training improvement with quality preservation
Phase: 4
Location: /src/modules/logic/training_data_pipeline_lg/data_augmentation_lg/data_augmentation_lg.py
"""

# Standard library imports
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set
import uuid

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.training_data_pipeline_lg.base_interfaces import (
    IDataAugmentation,
    AugmentationConfig,
    AugmentationType,
    DataSample,
    AugmentationResult,
    DataStatus
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class SynonymReplacer:
    """Handles synonym replacement augmentation."""
    
    def __init__(self):
        """Initialize synonym replacer."""
        self._logger = get_logger(__name__)
        self._synonyms = self._load_synonyms()
    
    def _load_synonyms(self) -> Dict[str, List[str]]:
        """Load synonym dictionary."""
        # Basic synonym dictionary - in production, this would be loaded from a file
        return {
            'good': ['excellent', 'great', 'fine', 'nice', 'wonderful'],
            'bad': ['terrible', 'awful', 'poor', 'horrible', 'dreadful'],
            'big': ['large', 'huge', 'enormous', 'massive', 'giant'],
            'small': ['tiny', 'little', 'miniature', 'compact', 'minor'],
            'fast': ['quick', 'rapid', 'swift', 'speedy', 'hasty'],
            'slow': ['sluggish', 'gradual', 'leisurely', 'delayed', 'unhurried'],
            'happy': ['joyful', 'cheerful', 'delighted', 'pleased', 'content'],
            'sad': ['unhappy', 'sorrowful', 'depressed', 'melancholy', 'gloomy']
        }
    
    def replace_synonyms(self, text: str, replacement_ratio: float) -> str:
        """
        Replace words with synonyms.
        
        Args:
            text: Input text
            replacement_ratio: Ratio of words to replace
            
        Returns:
            Text with synonym replacements
        """
        words = text.split()
        num_replacements = max(1, int(len(words) * replacement_ratio))
        
        # Get indices of words that can be replaced
        replaceable_indices = []
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in self._synonyms:
                replaceable_indices.append(i)
        
        if not replaceable_indices:
            return text
        
        # Randomly select words to replace
        indices_to_replace = random.sample(
            replaceable_indices,
            min(num_replacements, len(replaceable_indices))
        )
        
        for idx in indices_to_replace:
            word = words[idx]
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            if clean_word in self._synonyms:
                synonym = random.choice(self._synonyms[clean_word])
                # Preserve original case
                if word.isupper():
                    synonym = synonym.upper()
                elif word.istitle():
                    synonym = synonym.capitalize()
                
                # Preserve punctuation
                punctuation = re.findall(r'[^\w]', word)
                if punctuation:
                    synonym += ''.join(punctuation)
                
                words[idx] = synonym
        
        return ' '.join(words)


class NoiseInjector:
    """Handles noise injection augmentation."""
    
    def __init__(self):
        """Initialize noise injector."""
        self._logger = get_logger(__name__)
    
    def inject_noise(self, text: str, noise_level: float) -> str:
        """
        Inject character-level noise into text.
        
        Args:
            text: Input text
            noise_level: Level of noise to inject (0.0 to 1.0)
            
        Returns:
            Text with injected noise
        """
        if noise_level <= 0:
            return text
        
        chars = list(text)
        num_changes = max(1, int(len(chars) * noise_level))
        
        for _ in range(num_changes):
            if not chars:
                break
            
            idx = random.randint(0, len(chars) - 1)
            operation = random.choice(['substitute', 'insert', 'delete'])
            
            if operation == 'substitute' and chars[idx].isalpha():
                # Substitute with a similar character
                if chars[idx].islower():
                    chars[idx] = random.choice('abcdefghijklmnopqrstuvwxyz')
                else:
                    chars[idx] = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
            
            elif operation == 'insert':
                # Insert a random character
                char_to_insert = random.choice('abcdefghijklmnopqrstuvwxyz ')
                chars.insert(idx, char_to_insert)
            
            elif operation == 'delete' and len(chars) > 1:
                # Delete character
                chars.pop(idx)
        
        return ''.join(chars)


class TextAugmenter:
    """Handles various text augmentation techniques."""
    
    def __init__(self):
        """Initialize text augmenter."""
        self._logger = get_logger(__name__)
        self.synonym_replacer = SynonymReplacer()
        self.noise_injector = NoiseInjector()
    
    def random_insertion(self, text: str, insertion_ratio: float) -> str:
        """
        Randomly insert words into text.
        
        Args:
            text: Input text
            insertion_ratio: Ratio of words to insert
            
        Returns:
            Text with random insertions
        """
        words = text.split()
        if not words:
            return text
        
        num_insertions = max(1, int(len(words) * insertion_ratio))
        
        # Common words for insertion
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        
        for _ in range(num_insertions):
            insert_idx = random.randint(0, len(words))
            word_to_insert = random.choice(common_words)
            words.insert(insert_idx, word_to_insert)
        
        return ' '.join(words)
    
    def random_swap(self, text: str, swap_ratio: float) -> str:
        """
        Randomly swap adjacent words.
        
        Args:
            text: Input text
            swap_ratio: Ratio of words to swap
            
        Returns:
            Text with random swaps
        """
        words = text.split()
        if len(words) < 2:
            return text
        
        num_swaps = max(1, int(len(words) * swap_ratio))
        
        for _ in range(num_swaps):
            idx = random.randint(0, len(words) - 2)
            words[idx], words[idx + 1] = words[idx + 1], words[idx]
        
        return ' '.join(words)
    
    def random_deletion(self, text: str, deletion_ratio: float) -> str:
        """
        Randomly delete words from text.
        
        Args:
            text: Input text
            deletion_ratio: Ratio of words to delete
            
        Returns:
            Text with random deletions
        """
        words = text.split()
        if len(words) <= 1:
            return text
        
        num_deletions = max(1, int(len(words) * deletion_ratio))
        num_deletions = min(num_deletions, len(words) - 1)  # Keep at least one word
        
        indices_to_delete = random.sample(range(len(words)), num_deletions)
        
        # Remove words in reverse order to maintain indices
        for idx in sorted(indices_to_delete, reverse=True):
            words.pop(idx)
        
        return ' '.join(words)
    
    def context_shuffling(self, text: str, window_size: int = 3) -> str:
        """
        Shuffle words within local context windows.
        
        Args:
            text: Input text
            window_size: Size of context window
            
        Returns:
            Text with shuffled contexts
        """
        words = text.split()
        if len(words) <= window_size:
            return text
        
        result = []
        i = 0
        
        while i < len(words):
            window_end = min(i + window_size, len(words))
            window = words[i:window_end]
            
            # Shuffle words in window
            random.shuffle(window)
            result.extend(window)
            
            i = window_end
        
        return ' '.join(result)


class DataAugmentation(IDataAugmentation):
    """Production-ready data augmentation for training improvement."""
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize data augmentation.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self._logger = get_logger(__name__)
        self.max_workers = max_workers
        self._lock = threading.Lock()
        
        # Initialize augmentation components
        self.text_augmenter = TextAugmenter()
        
        # Statistics
        self._augmentation_stats = {
            'total_augmented': 0,
            'augmentation_time': 0.0,
            'techniques_used': set()
        }
    
    def augment_sample(self, sample: DataSample, config: AugmentationConfig) -> List[DataSample]:
        """
        Augment a single data sample.
        
        Args:
            sample: Original data sample
            config: Augmentation configuration
            
        Returns:
            List of augmented samples (including original if preserve_original=True)
        """
        try:
            augmented_samples = []
            
            # Add original sample if requested
            if config.preserve_original:
                augmented_samples.append(sample)
            
            # Apply augmentation techniques
            for technique in config.enabled_techniques:
                if random.random() < config.augmentation_probability:
                    augmented_text = self._apply_technique(sample.text, technique, config)
                    
                    if augmented_text and augmented_text != sample.text:
                        augmented_sample = DataSample(
                            sample_id=f"{sample.sample_id}_aug_{technique.value}_{uuid.uuid4().hex[:8]}",
                            text=augmented_text,
                            label=sample.label,
                            metadata=sample.metadata.copy(),
                            source_document=sample.source_document,
                            chunk_index=sample.chunk_index,
                            augmented=True,
                            augmentation_type=technique
                        )
                        augmented_samples.append(augmented_sample)
                        
                        # Limit augmentations per sample
                        if len(augmented_samples) - (1 if config.preserve_original else 0) >= config.max_augmentations_per_sample:
                            break
            
            return augmented_samples
            
        except Exception as e:
            self._logger.error(f"Failed to augment sample {sample.sample_id}: {e}")
            return [sample] if config.preserve_original else []

    def _apply_technique(self, text: str, technique: AugmentationType, config: AugmentationConfig) -> str:
        """Apply specific augmentation technique."""
        try:
            if technique == AugmentationType.SYNONYM_REPLACEMENT:
                return self.text_augmenter.synonym_replacer.replace_synonyms(
                    text, config.synonym_replacement_ratio
                )

            elif technique == AugmentationType.RANDOM_INSERTION:
                return self.text_augmenter.random_insertion(
                    text, config.random_insertion_ratio
                )

            elif technique == AugmentationType.RANDOM_SWAP:
                return self.text_augmenter.random_swap(
                    text, config.random_swap_ratio
                )

            elif technique == AugmentationType.RANDOM_DELETION:
                return self.text_augmenter.random_deletion(
                    text, config.random_deletion_ratio
                )

            elif technique == AugmentationType.NOISE_INJECTION:
                return self.text_augmenter.noise_injector.inject_noise(
                    text, config.noise_level
                )

            elif technique == AugmentationType.CONTEXT_SHUFFLING:
                return self.text_augmenter.context_shuffling(
                    text, config.context_window_size
                )

            else:
                self._logger.warning(f"Unsupported augmentation technique: {technique}")
                return text

        except Exception as e:
            self._logger.error(f"Failed to apply {technique}: {e}")
            return text

    def augment_batch(self, samples: List[DataSample], config: AugmentationConfig) -> AugmentationResult:
        """
        Augment a batch of data samples.

        Args:
            samples: List of original samples
            config: Augmentation configuration

        Returns:
            AugmentationResult with augmentation details
        """
        start_time = time.time()

        try:
            self._logger.info(f"Augmenting batch of {len(samples)} samples")

            augmented_samples = []
            failed_count = 0

            # Process samples in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_sample = {
                    executor.submit(self.augment_sample, sample, config): sample
                    for sample in samples
                }

                for future in as_completed(future_to_sample):
                    try:
                        sample_results = future.result()
                        augmented_samples.extend(sample_results)
                    except Exception as e:
                        failed_count += 1
                        self._logger.error(f"Failed to process sample: {e}")

            # Calculate statistics
            original_count = len(samples)
            total_count = len(augmented_samples)
            augmented_count = total_count - (original_count if config.preserve_original else 0)

            augmentation_time = time.time() - start_time

            # Update global statistics
            with self._lock:
                self._augmentation_stats['total_augmented'] += augmented_count
                self._augmentation_stats['augmentation_time'] += augmentation_time
                self._augmentation_stats['techniques_used'].update(config.enabled_techniques)

            self._logger.info(f"Augmentation completed: {original_count} -> {total_count} samples in {augmentation_time:.2f}s")

            return AugmentationResult(
                status=DataStatus.COMPLETED,
                original_samples=original_count,
                augmented_samples=augmented_count,
                total_samples=total_count,
                augmentation_techniques=config.enabled_techniques,
                augmentation_time_seconds=augmentation_time,
                quality_improvement=self._calculate_quality_improvement(samples, augmented_samples),
                diversity_score=self._calculate_diversity_score(augmented_samples)
            )

        except Exception as e:
            self._logger.error(f"Failed to augment batch: {e}")
            return AugmentationResult(
                status=DataStatus.FAILED,
                original_samples=len(samples),
                augmented_samples=0,
                total_samples=len(samples),
                errors=[str(e)]
            )

    def _calculate_quality_improvement(self, original_samples: List[DataSample],
                                     augmented_samples: List[DataSample]) -> float:
        """Calculate quality improvement score."""
        try:
            # Simple heuristic: diversity in text length and vocabulary
            original_lengths = [len(s.text.split()) for s in original_samples]
            augmented_lengths = [len(s.text.split()) for s in augmented_samples]

            original_std = np.std(original_lengths) if original_lengths else 0
            augmented_std = np.std(augmented_lengths) if augmented_lengths else 0

            # Higher standard deviation indicates more diversity
            if original_std == 0:
                return 1.0 if augmented_std > 0 else 0.0

            return min(1.0, augmented_std / original_std)

        except Exception as e:
            self._logger.error(f"Failed to calculate quality improvement: {e}")
            return 0.0

    def _calculate_diversity_score(self, samples: List[DataSample]) -> float:
        """Calculate diversity score for samples."""
        try:
            if not samples:
                return 0.0

            # Calculate vocabulary diversity
            all_words = set()
            total_words = 0

            for sample in samples:
                words = sample.text.lower().split()
                all_words.update(words)
                total_words += len(words)

            # Diversity score: unique words / total words
            if total_words == 0:
                return 0.0

            return len(all_words) / total_words

        except Exception as e:
            self._logger.error(f"Failed to calculate diversity score: {e}")
            return 0.0

    def get_available_techniques(self) -> List[AugmentationType]:
        """Get list of available augmentation techniques."""
        return [
            AugmentationType.SYNONYM_REPLACEMENT,
            AugmentationType.RANDOM_INSERTION,
            AugmentationType.RANDOM_SWAP,
            AugmentationType.RANDOM_DELETION,
            AugmentationType.NOISE_INJECTION,
            AugmentationType.CONTEXT_SHUFFLING
        ]

    def estimate_augmentation_time(self, sample_count: int, config: AugmentationConfig) -> float:
        """
        Estimate time required for augmentation.

        Args:
            sample_count: Number of samples to augment
            config: Augmentation configuration

        Returns:
            Estimated time in seconds
        """
        # Base time per sample (in seconds)
        base_time_per_sample = 0.01

        # Time multiplier based on techniques
        technique_multipliers = {
            AugmentationType.SYNONYM_REPLACEMENT: 1.5,
            AugmentationType.RANDOM_INSERTION: 1.2,
            AugmentationType.RANDOM_SWAP: 1.1,
            AugmentationType.RANDOM_DELETION: 1.1,
            AugmentationType.NOISE_INJECTION: 1.3,
            AugmentationType.CONTEXT_SHUFFLING: 1.4,
            AugmentationType.BACK_TRANSLATION: 5.0,  # Much slower
            AugmentationType.PARAPHRASING: 3.0       # Slower
        }

        total_multiplier = 1.0
        for technique in config.enabled_techniques:
            total_multiplier += technique_multipliers.get(technique, 1.0) - 1.0

        # Account for augmentation probability and max augmentations
        effective_augmentations = min(
            len(config.enabled_techniques) * config.augmentation_probability,
            config.max_augmentations_per_sample
        )

        estimated_time = (
            sample_count *
            base_time_per_sample *
            total_multiplier *
            effective_augmentations
        )

        # Account for parallel processing
        estimated_time /= min(self.max_workers, sample_count)

        return estimated_time

    def get_augmentation_statistics(self) -> Dict[str, Any]:
        """Get augmentation statistics."""
        with self._lock:
            return {
                'total_augmented': self._augmentation_stats['total_augmented'],
                'total_augmentation_time': self._augmentation_stats['augmentation_time'],
                'techniques_used': list(self._augmentation_stats['techniques_used']),
                'average_time_per_sample': (
                    self._augmentation_stats['augmentation_time'] /
                    max(1, self._augmentation_stats['total_augmented'])
                )
            }
