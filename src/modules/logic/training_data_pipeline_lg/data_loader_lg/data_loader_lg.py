"""
Module: data_loader_lg
Description: Loads and batches training data from processed documents with memory optimization and thread safety
Phase: 4
Location: /src/modules/logic/training_data_pipeline_lg/data_loader_lg/data_loader_lg.py
"""

# Standard library imports
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import gzip
import pickle
import hashlib

# Third-party imports
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader as TorchDataLoader
import psutil

# Local imports
from src.modules.logic.training_data_pipeline_lg.base_interfaces import (
    IDataLoader,
    DataLoaderConfig,
    DataFormat,
    DataStatus,
    DataSample,
    LoadingResult
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class TrainingDataset(Dataset):
    """PyTorch Dataset for training data."""
    
    def __init__(self, samples: List[DataSample]):
        """
        Initialize dataset with samples.
        
        Args:
            samples: List of data samples
        """
        self.samples = samples
        self._logger = get_logger(__name__)
    
    def __len__(self) -> int:
        """Get dataset length."""
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """
        Get item by index.
        
        Args:
            idx: Sample index
            
        Returns:
            Sample data as dictionary
        """
        if idx >= len(self.samples):
            raise IndexError(f"Index {idx} out of range for dataset of size {len(self.samples)}")
        
        sample = self.samples[idx]
        return {
            'sample_id': sample.sample_id,
            'text': sample.text,
            'label': sample.label,
            'metadata': sample.metadata
        }


class CacheManager:
    """Manages data caching for improved performance."""
    
    def __init__(self, cache_dir: Path, max_cache_size_mb: int = 1024):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache files
            max_cache_size_mb: Maximum cache size in MB
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size_mb = max_cache_size_mb
        self._logger = get_logger(__name__)
        self._lock = threading.Lock()
    
    def _get_cache_key(self, data_path: Path, config: DataLoaderConfig) -> str:
        """Generate cache key for data and configuration."""
        config_str = f"{config.format.value}_{config.batch_size}_{config.validation_split}_{config.test_split}_{config.random_seed}"
        data_hash = hashlib.md5(str(data_path).encode()).hexdigest()
        return f"{data_hash}_{hashlib.md5(config_str.encode()).hexdigest()}"
    
    def get_cached_data(self, data_path: Path, config: DataLoaderConfig) -> Optional[List[DataSample]]:
        """
        Get cached data if available.
        
        Args:
            data_path: Path to original data
            config: Data loader configuration
            
        Returns:
            Cached samples if available, None otherwise
        """
        try:
            cache_key = self._get_cache_key(data_path, config)
            cache_file = self.cache_dir / f"{cache_key}.pkl.gz"
            
            if not cache_file.exists():
                return None
            
            # Check if cache is newer than source data
            if cache_file.stat().st_mtime < data_path.stat().st_mtime:
                self._logger.info(f"Cache outdated for {data_path}")
                return None
            
            with gzip.open(cache_file, 'rb') as f:
                samples = pickle.load(f)
            
            self._logger.info(f"Loaded {len(samples)} samples from cache")
            return samples
            
        except Exception as e:
            self._logger.warning(f"Failed to load cache: {e}")
            return None
    
    def cache_data(self, data_path: Path, config: DataLoaderConfig, samples: List[DataSample]) -> bool:
        """
        Cache data samples.
        
        Args:
            data_path: Path to original data
            config: Data loader configuration
            samples: Samples to cache
            
        Returns:
            True if caching successful
        """
        try:
            with self._lock:
                cache_key = self._get_cache_key(data_path, config)
                cache_file = self.cache_dir / f"{cache_key}.pkl.gz"
                
                with gzip.open(cache_file, 'wb') as f:
                    pickle.dump(samples, f)
                
                self._logger.info(f"Cached {len(samples)} samples")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to cache data: {e}")
            return False


class DataLoader(IDataLoader):
    """Production-ready data loader for training data."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize data loader.
        
        Args:
            cache_dir: Optional cache directory
        """
        self._logger = get_logger(__name__)
        self._lock = threading.Lock()
        
        # Cache management
        self.cache_manager = CacheManager(cache_dir or Path("data/cache/training_data"))
        
        # Data storage
        self._train_samples: List[DataSample] = []
        self._validation_samples: List[DataSample] = []
        self._test_samples: List[DataSample] = []
        
        # Data loaders
        self._train_loader: Optional[TorchDataLoader] = None
        self._validation_loader: Optional[TorchDataLoader] = None
        self._test_loader: Optional[TorchDataLoader] = None
        
        # Statistics
        self._loading_stats = {
            'total_samples': 0,
            'loading_time': 0.0,
            'memory_usage_mb': 0.0
        }
    
    def load_data(self, config: DataLoaderConfig) -> LoadingResult:
        """
        Load training data from specified source.
        
        Args:
            config: Data loading configuration
            
        Returns:
            LoadingResult with loading details
        """
        start_time = time.time()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            self._logger.info(f"Loading data from {config.data_path}")
            
            # Check cache first
            if config.cache_enabled:
                cached_samples = self.cache_manager.get_cached_data(config.data_path, config)
                if cached_samples:
                    self._split_data(cached_samples, config)
                    loading_time = time.time() - start_time
                    memory_usage = psutil.Process().memory_info().rss / 1024 / 1024 - initial_memory
                    
                    return LoadingResult(
                        status=DataStatus.COMPLETED,
                        total_samples=len(cached_samples),
                        loaded_samples=len(cached_samples),
                        failed_samples=0,
                        train_samples=len(self._train_samples),
                        validation_samples=len(self._validation_samples),
                        test_samples=len(self._test_samples),
                        loading_time_seconds=loading_time,
                        memory_usage_mb=memory_usage,
                        data_format=config.format
                    )
            
            # Load data based on format
            samples = self._load_by_format(config)
            
            if not samples:
                return LoadingResult(
                    status=DataStatus.FAILED,
                    total_samples=0,
                    loaded_samples=0,
                    failed_samples=0,
                    errors=["No samples loaded"]
                )
            
            # Split data
            self._split_data(samples, config)
            
            # Cache data if enabled
            if config.cache_enabled:
                self.cache_manager.cache_data(config.data_path, config, samples)
            
            # Create data loaders
            self._create_data_loaders(config)
            
            loading_time = time.time() - start_time
            memory_usage = psutil.Process().memory_info().rss / 1024 / 1024 - initial_memory
            
            # Update statistics
            self._loading_stats.update({
                'total_samples': len(samples),
                'loading_time': loading_time,
                'memory_usage_mb': memory_usage
            })
            
            self._logger.info(f"Successfully loaded {len(samples)} samples in {loading_time:.2f}s")
            
            return LoadingResult(
                status=DataStatus.COMPLETED,
                total_samples=len(samples),
                loaded_samples=len(samples),
                failed_samples=0,
                train_samples=len(self._train_samples),
                validation_samples=len(self._validation_samples),
                test_samples=len(self._test_samples),
                loading_time_seconds=loading_time,
                memory_usage_mb=memory_usage,
                data_format=config.format
            )
            
        except Exception as e:
            self._logger.error(f"Failed to load data: {e}")
            return LoadingResult(
                status=DataStatus.FAILED,
                total_samples=0,
                loaded_samples=0,
                failed_samples=0,
                errors=[str(e)]
            )

    def _load_by_format(self, config: DataLoaderConfig) -> List[DataSample]:
        """Load data based on format."""
        if config.format == DataFormat.JSON:
            return self._load_json(config)
        elif config.format == DataFormat.JSONL:
            return self._load_jsonl(config)
        elif config.format == DataFormat.CSV:
            return self._load_csv(config)
        elif config.format == DataFormat.TEXT:
            return self._load_text(config)
        else:
            raise ValueError(f"Unsupported format: {config.format}")

    def _load_json(self, config: DataLoaderConfig) -> List[DataSample]:
        """Load data from JSON file."""
        with open(config.data_path, 'r', encoding=config.encoding) as f:
            data = json.load(f)

        samples = []
        for i, item in enumerate(data):
            sample = DataSample(
                sample_id=item.get('id', f"sample_{i}"),
                text=item.get('text', ''),
                label=item.get('label'),
                metadata=item.get('metadata', {}),
                source_document=item.get('source_document'),
                chunk_index=item.get('chunk_index')
            )
            samples.append(sample)

        return samples

    def _load_jsonl(self, config: DataLoaderConfig) -> List[DataSample]:
        """Load data from JSONL file."""
        samples = []
        with open(config.data_path, 'r', encoding=config.encoding) as f:
            for i, line in enumerate(f):
                if line.strip():
                    item = json.loads(line)
                    sample = DataSample(
                        sample_id=item.get('id', f"sample_{i}"),
                        text=item.get('text', ''),
                        label=item.get('label'),
                        metadata=item.get('metadata', {}),
                        source_document=item.get('source_document'),
                        chunk_index=item.get('chunk_index')
                    )
                    samples.append(sample)

        return samples

    def _load_csv(self, config: DataLoaderConfig) -> List[DataSample]:
        """Load data from CSV file."""
        df = pd.read_csv(config.data_path, encoding=config.encoding)
        samples = []

        for i, row in df.iterrows():
            sample = DataSample(
                sample_id=row.get('id', f"sample_{i}"),
                text=row.get('text', ''),
                label=row.get('label'),
                metadata={'row_index': i},
                source_document=row.get('source_document'),
                chunk_index=row.get('chunk_index')
            )
            samples.append(sample)

        return samples

    def _load_text(self, config: DataLoaderConfig) -> List[DataSample]:
        """Load data from text file."""
        with open(config.data_path, 'r', encoding=config.encoding) as f:
            lines = f.readlines()

        samples = []
        for i, line in enumerate(lines):
            if line.strip():
                sample = DataSample(
                    sample_id=f"sample_{i}",
                    text=line.strip(),
                    metadata={'line_number': i + 1}
                )
                samples.append(sample)

        return samples

    def _split_data(self, samples: List[DataSample], config: DataLoaderConfig) -> None:
        """Split data into train, validation, and test sets."""
        # Set random seed for reproducibility
        np.random.seed(config.random_seed)

        # Shuffle samples
        if config.shuffle:
            np.random.shuffle(samples)

        total_samples = len(samples)
        test_size = int(total_samples * config.test_split)
        val_size = int(total_samples * config.validation_split)
        train_size = total_samples - test_size - val_size

        self._train_samples = samples[:train_size]
        self._validation_samples = samples[train_size:train_size + val_size]
        self._test_samples = samples[train_size + val_size:]

        self._logger.info(f"Data split: {len(self._train_samples)} train, "
                         f"{len(self._validation_samples)} validation, "
                         f"{len(self._test_samples)} test")

    def _create_data_loaders(self, config: DataLoaderConfig) -> None:
        """Create PyTorch data loaders."""
        if self._train_samples:
            train_dataset = TrainingDataset(self._train_samples)
            self._train_loader = TorchDataLoader(
                train_dataset,
                batch_size=config.batch_size,
                shuffle=config.shuffle,
                num_workers=config.num_workers,
                pin_memory=config.pin_memory,
                drop_last=config.drop_last,
                prefetch_factor=config.prefetch_factor,
                persistent_workers=config.persistent_workers
            )

        if self._validation_samples:
            val_dataset = TrainingDataset(self._validation_samples)
            self._validation_loader = TorchDataLoader(
                val_dataset,
                batch_size=config.batch_size,
                shuffle=False,
                num_workers=config.num_workers,
                pin_memory=config.pin_memory,
                drop_last=False
            )

        if self._test_samples:
            test_dataset = TrainingDataset(self._test_samples)
            self._test_loader = TorchDataLoader(
                test_dataset,
                batch_size=config.batch_size,
                shuffle=False,
                num_workers=config.num_workers,
                pin_memory=config.pin_memory,
                drop_last=False
            )

    def get_train_loader(self) -> Optional[TorchDataLoader]:
        """Get training data loader."""
        return self._train_loader

    def get_validation_loader(self) -> Optional[TorchDataLoader]:
        """Get validation data loader."""
        return self._validation_loader

    def get_test_loader(self) -> Optional[TorchDataLoader]:
        """Get test data loader."""
        return self._test_loader

    def get_sample_count(self) -> Tuple[int, int, int]:
        """Get sample counts for train, validation, and test sets."""
        return (
            len(self._train_samples),
            len(self._validation_samples),
            len(self._test_samples)
        )

    def get_data_statistics(self) -> Dict[str, Any]:
        """Get comprehensive data statistics."""
        train_texts = [s.text for s in self._train_samples]
        val_texts = [s.text for s in self._validation_samples]
        test_texts = [s.text for s in self._test_samples]

        all_texts = train_texts + val_texts + test_texts

        if not all_texts:
            return {}

        text_lengths = [len(text.split()) for text in all_texts]

        return {
            'total_samples': len(all_texts),
            'train_samples': len(train_texts),
            'validation_samples': len(val_texts),
            'test_samples': len(test_texts),
            'avg_text_length': np.mean(text_lengths),
            'min_text_length': np.min(text_lengths),
            'max_text_length': np.max(text_lengths),
            'std_text_length': np.std(text_lengths),
            'loading_time_seconds': self._loading_stats['loading_time'],
            'memory_usage_mb': self._loading_stats['memory_usage_mb']
        }

    def clear_cache(self) -> bool:
        """Clear data cache."""
        try:
            cache_files = list(self.cache_manager.cache_dir.glob("*.pkl.gz"))
            for cache_file in cache_files:
                cache_file.unlink()

            self._logger.info(f"Cleared {len(cache_files)} cache files")
            return True

        except Exception as e:
            self._logger.error(f"Failed to clear cache: {e}")
            return False


# Specialized data loaders
class TrainingDataLoader(DataLoader):
    """Specialized data loader for training data with enhanced features."""

    def __init__(self, cache_dir: Optional[Path] = None):
        super().__init__(cache_dir)
        self._logger = get_logger(__name__)


class StreamingDataLoader(DataLoader):
    """Streaming data loader for large datasets."""

    def __init__(self, cache_dir: Optional[Path] = None, chunk_size: int = 1000):
        super().__init__(cache_dir)
        self.chunk_size = chunk_size
        self._logger = get_logger(__name__)


class CachedDataLoader(DataLoader):
    """Data loader with aggressive caching for repeated access."""

    def __init__(self, cache_dir: Optional[Path] = None, max_cache_size_mb: int = 2048):
        super().__init__(cache_dir)
        self.cache_manager.max_cache_size_mb = max_cache_size_mb
        self._logger = get_logger(__name__)
