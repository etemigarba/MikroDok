"""
Module: batch_generator_lg
Description: Generates training batches with proper tokenization and padding for memory optimization
Phase: 4
Location: /src/modules/logic/training_data_pipeline_lg/batch_generator_lg/batch_generator_lg.py
"""

# Standard library imports
import asyncio
import math
import random
import threading
import time
from collections import defaultdict
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple
import uuid

# Third-party imports
import numpy as np
import torch
import psutil

# Local imports
from src.modules.logic.training_data_pipeline_lg.base_interfaces import (
    IBatchGenerator,
    BatchConfig,
    BatchStrategy,
    DataSample,
    DataBatch,
    BatchGenerationResult,
    DataStatus
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class SimpleTokenizer:
    """Simple tokenizer for text processing."""
    
    def __init__(self, vocab_size: int = 10000, max_length: int = 512):
        """
        Initialize tokenizer.
        
        Args:
            vocab_size: Maximum vocabulary size
            max_length: Maximum sequence length
        """
        self.vocab_size = vocab_size
        self.max_length = max_length
        self._logger = get_logger(__name__)
        
        # Special tokens
        self.pad_token = "<pad>"
        self.unk_token = "<unk>"
        self.cls_token = "<cls>"
        self.sep_token = "<sep>"
        
        # Token mappings
        self.token_to_id = {
            self.pad_token: 0,
            self.unk_token: 1,
            self.cls_token: 2,
            self.sep_token: 3
        }
        self.id_to_token = {v: k for k, v in self.token_to_id.items()}
        self.next_id = 4
        
        # Vocabulary
        self.vocab = set(self.token_to_id.keys())
    
    def build_vocab(self, texts: List[str]) -> None:
        """Build vocabulary from texts."""
        word_counts = defaultdict(int)
        
        for text in texts:
            words = text.lower().split()
            for word in words:
                word_counts[word] += 1
        
        # Add most frequent words to vocabulary
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        for word, count in sorted_words:
            if len(self.vocab) >= self.vocab_size:
                break
            
            if word not in self.vocab:
                self.token_to_id[word] = self.next_id
                self.id_to_token[self.next_id] = word
                self.vocab.add(word)
                self.next_id += 1
        
        self._logger.info(f"Built vocabulary with {len(self.vocab)} tokens")
    
    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        """
        Encode text to token IDs.
        
        Args:
            text: Input text
            add_special_tokens: Whether to add special tokens
            
        Returns:
            List of token IDs
        """
        words = text.lower().split()
        token_ids = []
        
        if add_special_tokens:
            token_ids.append(self.token_to_id[self.cls_token])
        
        for word in words:
            if word in self.token_to_id:
                token_ids.append(self.token_to_id[word])
            else:
                token_ids.append(self.token_to_id[self.unk_token])
        
        if add_special_tokens:
            token_ids.append(self.token_to_id[self.sep_token])
        
        # Truncate if too long
        if len(token_ids) > self.max_length:
            token_ids = token_ids[:self.max_length-1] + [self.token_to_id[self.sep_token]]
        
        return token_ids
    
    def decode(self, token_ids: List[int]) -> str:
        """Decode token IDs to text."""
        tokens = []
        for token_id in token_ids:
            if token_id in self.id_to_token:
                token = self.id_to_token[token_id]
                if token not in [self.pad_token, self.cls_token, self.sep_token]:
                    tokens.append(token)
        
        return ' '.join(tokens)
    
    def pad_sequence(self, token_ids: List[int], max_length: Optional[int] = None) -> Tuple[List[int], List[int]]:
        """
        Pad sequence to specified length.
        
        Args:
            token_ids: Input token IDs
            max_length: Maximum length (uses self.max_length if None)
            
        Returns:
            Tuple of (padded_token_ids, attention_mask)
        """
        target_length = max_length or self.max_length
        
        # Truncate if necessary
        if len(token_ids) > target_length:
            token_ids = token_ids[:target_length]
        
        # Create attention mask
        attention_mask = [1] * len(token_ids)
        
        # Pad sequence
        while len(token_ids) < target_length:
            token_ids.append(self.token_to_id[self.pad_token])
            attention_mask.append(0)
        
        return token_ids, attention_mask


class BatchOptimizer:
    """Optimizes batch generation for memory efficiency."""
    
    def __init__(self):
        """Initialize batch optimizer."""
        self._logger = get_logger(__name__)
    
    def optimize_batch_size(self, samples: List[DataSample], config: BatchConfig) -> int:
        """
        Optimize batch size based on memory constraints.
        
        Args:
            samples: Input samples
            config: Batch configuration
            
        Returns:
            Optimized batch size
        """
        try:
            # Get available memory
            available_memory_mb = psutil.virtual_memory().available / 1024 / 1024
            
            # Estimate memory per sample
            if samples:
                avg_text_length = np.mean([len(sample.text.split()) for sample in samples])
                # Rough estimate: 4 bytes per token * sequence length * batch size
                memory_per_sample_mb = (avg_text_length * 4) / (1024 * 1024)
            else:
                memory_per_sample_mb = 0.001  # Default estimate
            
            # Calculate optimal batch size (use 50% of available memory)
            target_memory_mb = available_memory_mb * 0.5
            optimal_batch_size = int(target_memory_mb / max(memory_per_sample_mb, 0.001))
            
            # Clamp to reasonable bounds
            optimal_batch_size = max(1, min(optimal_batch_size, config.batch_size * 2))
            
            self._logger.debug(f"Optimized batch size: {optimal_batch_size} (original: {config.batch_size})")
            return optimal_batch_size
            
        except Exception as e:
            self._logger.warning(f"Failed to optimize batch size: {e}")
            return config.batch_size
    
    def group_by_length(self, samples: List[DataSample], bucket_size: int = 10) -> List[List[DataSample]]:
        """
        Group samples by text length for efficient batching.
        
        Args:
            samples: Input samples
            bucket_size: Size of length buckets
            
        Returns:
            List of sample groups
        """
        try:
            # Calculate text lengths
            sample_lengths = [(sample, len(sample.text.split())) for sample in samples]
            
            # Sort by length
            sample_lengths.sort(key=lambda x: x[1])
            
            # Group into buckets
            groups = []
            current_group = []
            current_length_range = None
            
            for sample, length in sample_lengths:
                length_bucket = length // bucket_size
                
                if current_length_range is None:
                    current_length_range = length_bucket
                
                if length_bucket == current_length_range:
                    current_group.append(sample)
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [sample]
                    current_length_range = length_bucket
            
            # Add final group
            if current_group:
                groups.append(current_group)
            
            self._logger.debug(f"Grouped {len(samples)} samples into {len(groups)} length-based groups")
            return groups
            
        except Exception as e:
            self._logger.error(f"Failed to group by length: {e}")
            return [samples]  # Return all samples as single group


class SequentialBatchGenerator:
    """Generates batches sequentially."""
    
    def __init__(self, tokenizer: SimpleTokenizer):
        """Initialize sequential batch generator."""
        self.tokenizer = tokenizer
        self._logger = get_logger(__name__)
    
    def generate_batches(self, samples: List[DataSample], config: BatchConfig) -> Iterator[DataBatch]:
        """Generate batches sequentially."""
        for i in range(0, len(samples), config.batch_size):
            batch_samples = samples[i:i + config.batch_size]
            yield self._create_batch(batch_samples, config)
    
    def _create_batch(self, samples: List[DataSample], config: BatchConfig) -> DataBatch:
        """Create a single batch from samples."""
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        
        # Tokenize all texts
        tokenized_samples = []
        for sample in samples:
            token_ids = self.tokenizer.encode(sample.text)
            tokenized_samples.append((sample, token_ids))
        
        # Determine max length for this batch
        if config.dynamic_padding:
            max_length = max(len(tokens) for _, tokens in tokenized_samples)
            max_length = min(max_length, config.max_sequence_length)
        else:
            max_length = config.max_sequence_length
        
        # Pad sequences
        input_ids = []
        attention_masks = []
        labels = []
        
        for sample, token_ids in tokenized_samples:
            padded_ids, attention_mask = self.tokenizer.pad_sequence(token_ids, max_length)
            input_ids.append(padded_ids)
            attention_masks.append(attention_mask)
            
            # Handle labels
            if sample.label is not None:
                if isinstance(sample.label, str):
                    # Convert string labels to integers (simplified)
                    label_id = hash(sample.label) % 1000  # Simple hash-based mapping
                else:
                    label_id = sample.label
                labels.append(label_id)
        
        # Convert to tensors
        input_ids_tensor = torch.tensor(input_ids, dtype=torch.long)
        attention_mask_tensor = torch.tensor(attention_masks, dtype=torch.long)
        labels_tensor = torch.tensor(labels, dtype=torch.long) if labels else None
        
        # Calculate memory usage
        memory_usage_mb = (
            input_ids_tensor.numel() * input_ids_tensor.element_size() +
            attention_mask_tensor.numel() * attention_mask_tensor.element_size()
        ) / (1024 * 1024)
        
        if labels_tensor is not None:
            memory_usage_mb += labels_tensor.numel() * labels_tensor.element_size() / (1024 * 1024)
        
        return DataBatch(
            batch_id=batch_id,
            samples=samples,
            input_ids=input_ids_tensor,
            attention_mask=attention_mask_tensor,
            labels=labels_tensor,
            batch_size=len(samples),
            sequence_length=max_length,
            memory_usage_mb=memory_usage_mb
        )


class RandomBatchGenerator(SequentialBatchGenerator):
    """Generates batches with random sampling."""

    def __init__(self, tokenizer: SimpleTokenizer, random_seed: int = 42):
        """Initialize random batch generator."""
        super().__init__(tokenizer)
        self.random_seed = random_seed
        random.seed(random_seed)

    def generate_batches(self, samples: List[DataSample], config: BatchConfig) -> Iterator[DataBatch]:
        """Generate batches with random sampling."""
        # Shuffle samples
        shuffled_samples = samples.copy()
        random.shuffle(shuffled_samples)

        # Generate batches sequentially from shuffled samples
        yield from super().generate_batches(shuffled_samples, config)


class BalancedBatchGenerator(SequentialBatchGenerator):
    """Generates balanced batches based on labels."""

    def __init__(self, tokenizer: SimpleTokenizer):
        """Initialize balanced batch generator."""
        super().__init__(tokenizer)

    def generate_batches(self, samples: List[DataSample], config: BatchConfig) -> Iterator[DataBatch]:
        """Generate balanced batches."""
        # Group samples by label
        label_groups = defaultdict(list)
        for sample in samples:
            label = sample.label if sample.label is not None else "unlabeled"
            label_groups[label].append(sample)

        # Calculate samples per label per batch
        num_labels = len(label_groups)
        if num_labels == 0:
            yield from super().generate_batches(samples, config)
            return

        samples_per_label = max(1, config.batch_size // num_labels)

        # Create balanced batches
        label_iterators = {label: iter(samples) for label, samples in label_groups.items()}

        while True:
            batch_samples = []

            # Try to get samples from each label
            for label in label_groups:
                try:
                    for _ in range(samples_per_label):
                        if len(batch_samples) < config.batch_size:
                            sample = next(label_iterators[label])
                            batch_samples.append(sample)
                except StopIteration:
                    # This label is exhausted
                    pass

            if not batch_samples:
                break

            yield self._create_batch(batch_samples, config)


class BatchGenerator(IBatchGenerator):
    """Production-ready batch generator with tokenization and memory optimization."""

    def __init__(self, vocab_size: int = 10000, max_length: int = 512):
        """
        Initialize batch generator.

        Args:
            vocab_size: Vocabulary size for tokenizer
            max_length: Maximum sequence length
        """
        self._logger = get_logger(__name__)
        self._lock = threading.Lock()

        # Initialize components
        self.tokenizer = SimpleTokenizer(vocab_size, max_length)
        self.batch_optimizer = BatchOptimizer()

        # Specialized generators
        self.sequential_generator = SequentialBatchGenerator(self.tokenizer)
        self.random_generator = RandomBatchGenerator(self.tokenizer)
        self.balanced_generator = BalancedBatchGenerator(self.tokenizer)

        # Statistics
        self._batch_stats = {
            'total_batches_generated': 0,
            'total_samples_processed': 0,
            'total_generation_time': 0.0,
            'average_batch_size': 0.0,
            'average_sequence_length': 0.0,
            'memory_usage_mb': 0.0
        }

        # Vocabulary built flag
        self._vocab_built = False

    def _ensure_vocab_built(self, samples: List[DataSample]) -> None:
        """Ensure vocabulary is built from samples."""
        if not self._vocab_built:
            texts = [sample.text for sample in samples]
            self.tokenizer.build_vocab(texts)
            self._vocab_built = True

    def generate_batch(self, samples: List[DataSample], config: BatchConfig) -> DataBatch:
        """
        Generate a single training batch.

        Args:
            samples: List of data samples
            config: Batch configuration

        Returns:
            DataBatch ready for training
        """
        try:
            start_time = time.time()

            if not samples:
                raise ValueError("No samples provided for batch generation")

            # Ensure vocabulary is built
            self._ensure_vocab_built(samples)

            # Optimize batch size if needed
            if len(samples) > config.batch_size:
                samples = samples[:config.batch_size]

            # Generate batch using sequential generator
            batch = self.sequential_generator._create_batch(samples, config)

            # Update statistics
            generation_time = time.time() - start_time
            with self._lock:
                self._batch_stats['total_batches_generated'] += 1
                self._batch_stats['total_samples_processed'] += len(samples)
                self._batch_stats['total_generation_time'] += generation_time
                self._batch_stats['average_batch_size'] = (
                    self._batch_stats['total_samples_processed'] /
                    self._batch_stats['total_batches_generated']
                )
                self._batch_stats['memory_usage_mb'] += batch.memory_usage_mb

            return batch

        except Exception as e:
            self._logger.error(f"Failed to generate batch: {e}")
            raise

    def generate_batches(self, samples: List[DataSample], config: BatchConfig) -> Iterator[DataBatch]:
        """
        Generate multiple training batches.

        Args:
            samples: List of data samples
            config: Batch configuration

        Yields:
            DataBatch objects ready for training
        """
        try:
            start_time = time.time()

            if not samples:
                self._logger.warning("No samples provided for batch generation")
                return

            # Ensure vocabulary is built
            self._ensure_vocab_built(samples)

            # Select generator based on strategy
            if config.strategy == BatchStrategy.SEQUENTIAL:
                generator = self.sequential_generator
            elif config.strategy == BatchStrategy.RANDOM:
                generator = self.random_generator
            elif config.strategy == BatchStrategy.BALANCED:
                generator = self.balanced_generator
            else:
                generator = self.sequential_generator

            # Optimize samples if needed
            if config.group_by_length:
                sample_groups = self.batch_optimizer.group_by_length(
                    samples, config.length_bucket_size
                )

                for group in sample_groups:
                    yield from generator.generate_batches(group, config)
            else:
                yield from generator.generate_batches(samples, config)

            # Update statistics
            generation_time = time.time() - start_time
            with self._lock:
                self._batch_stats['total_generation_time'] += generation_time

        except Exception as e:
            self._logger.error(f"Failed to generate batches: {e}")
            raise

    async def generate_batches_async(self, samples: List[DataSample],
                                   config: BatchConfig) -> AsyncIterator[DataBatch]:
        """
        Generate training batches asynchronously.

        Args:
            samples: List of data samples
            config: Batch configuration

        Yields:
            DataBatch objects ready for training
        """
        try:
            # Run batch generation in executor to avoid blocking
            loop = asyncio.get_event_loop()

            # Generate batches in chunks to avoid memory issues
            chunk_size = config.batch_size * 10  # Process 10 batches at a time

            for i in range(0, len(samples), chunk_size):
                chunk_samples = samples[i:i + chunk_size]

                # Generate batches for this chunk
                batches = await loop.run_in_executor(
                    None,
                    lambda: list(self.generate_batches(chunk_samples, config))
                )

                # Yield batches asynchronously
                for batch in batches:
                    yield batch
                    await asyncio.sleep(0)  # Allow other tasks to run

        except Exception as e:
            self._logger.error(f"Failed to generate batches asynchronously: {e}")
            raise

    def estimate_batch_count(self, sample_count: int, config: BatchConfig) -> int:
        """
        Estimate number of batches for given samples.

        Args:
            sample_count: Number of samples
            config: Batch configuration

        Returns:
            Estimated batch count
        """
        if sample_count == 0:
            return 0

        if config.drop_last_batch:
            return sample_count // config.batch_size
        else:
            return math.ceil(sample_count / config.batch_size)

    def get_batch_statistics(self) -> Dict[str, Any]:
        """Get batch generation statistics."""
        with self._lock:
            return self._batch_stats.copy()

    def reset_statistics(self) -> None:
        """Reset batch generation statistics."""
        with self._lock:
            self._batch_stats = {
                'total_batches_generated': 0,
                'total_samples_processed': 0,
                'total_generation_time': 0.0,
                'average_batch_size': 0.0,
                'average_sequence_length': 0.0,
                'memory_usage_mb': 0.0
            }

    def get_tokenizer_info(self) -> Dict[str, Any]:
        """Get tokenizer information."""
        return {
            'vocab_size': len(self.tokenizer.vocab),
            'max_length': self.tokenizer.max_length,
            'special_tokens': {
                'pad_token': self.tokenizer.pad_token,
                'unk_token': self.tokenizer.unk_token,
                'cls_token': self.tokenizer.cls_token,
                'sep_token': self.tokenizer.sep_token
            },
            'vocab_built': self._vocab_built
        }
