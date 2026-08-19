"""
Module: deduplication_engine_lg
Description: Identifies and handles duplicate content using SHA-256 hashing and semantic similarity
Phase: 3
Location: /src/modules/logic/document_quality_lg/deduplication_engine_lg/deduplication_engine_lg.py
"""

# Standard library imports
import hashlib
import re
import time
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

# Third-party imports
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IDeduplicationEngine,
    DeduplicationResult,
    DeduplicationConfig,
    DuplicateType,
    SimilarityMethod
)


class HashBasedDeduplicator:
    """Hash-based duplicate detection using SHA-256 and other algorithms."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        self._hash_cache = {}  # Cache for computed hashes
    
    def calculate_hash(self, content: str, algorithm: str = "sha256") -> str:
        """
        Calculate hash for content using specified algorithm.
        
        Args:
            content: Content to hash
            algorithm: Hash algorithm (sha256, md5, sha1)
            
        Returns:
            Hexadecimal hash string
        """
        try:
            # Normalize content for consistent hashing
            normalized_content = self._normalize_content(content)
            
            # Check cache first
            cache_key = f"{algorithm}:{normalized_content[:100]}"
            if cache_key in self._hash_cache:
                return self._hash_cache[cache_key]
            
            # Calculate hash
            if algorithm.lower() == "sha256":
                hash_obj = hashlib.sha256(normalized_content.encode('utf-8'))
            elif algorithm.lower() == "md5":
                hash_obj = hashlib.md5(normalized_content.encode('utf-8'))
            elif algorithm.lower() == "sha1":
                hash_obj = hashlib.sha1(normalized_content.encode('utf-8'))
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
            
            hash_value = hash_obj.hexdigest()
            
            # Cache result
            self._hash_cache[cache_key] = hash_value
            
            return hash_value
            
        except Exception as e:
            self._logger.error(f"Error calculating hash: {e}")
            return ""
    
    def detect_exact_duplicates(self, content: str, reference_hashes: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Detect exact duplicates using hash comparison.
        
        Args:
            content: Content to check
            reference_hashes: Dictionary of reference content hashes
            
        Returns:
            Tuple of (is_duplicate, list_of_duplicate_sources)
        """
        try:
            content_hash = self.calculate_hash(content)
            if not content_hash:
                return False, []
            
            duplicates = []
            for source, ref_hash in reference_hashes.items():
                if content_hash == ref_hash:
                    duplicates.append(source)
            
            return len(duplicates) > 0, duplicates
            
        except Exception as e:
            self._logger.error(f"Error detecting exact duplicates: {e}")
            return False, []
    
    def detect_near_exact_duplicates(self, content: str, reference_content: List[str], 
                                   threshold: float = 0.95) -> Tuple[bool, List[str], float]:
        """
        Detect near-exact duplicates using fuzzy hash comparison.
        
        Args:
            content: Content to check
            reference_content: List of reference content
            threshold: Similarity threshold for near-exact detection
            
        Returns:
            Tuple of (is_duplicate, duplicate_sources, max_similarity)
        """
        try:
            content_normalized = self._normalize_content(content)
            duplicates = []
            max_similarity = 0.0
            
            for i, ref_content in enumerate(reference_content):
                ref_normalized = self._normalize_content(ref_content)
                
                # Calculate character-level similarity
                similarity = SequenceMatcher(None, content_normalized, ref_normalized).ratio()
                
                if similarity > max_similarity:
                    max_similarity = similarity
                
                if similarity >= threshold:
                    duplicates.append(f"reference_{i}")
            
            return len(duplicates) > 0, duplicates, max_similarity
            
        except Exception as e:
            self._logger.error(f"Error detecting near-exact duplicates: {e}")
            return False, [], 0.0
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for consistent comparison."""
        try:
            # Convert to lowercase
            normalized = content.lower()
            
            # Remove extra whitespace
            normalized = re.sub(r'\s+', ' ', normalized)
            
            # Remove punctuation for hash comparison
            normalized = re.sub(r'[^\w\s]', '', normalized)
            
            # Strip leading/trailing whitespace
            normalized = normalized.strip()
            
            return normalized
            
        except Exception as e:
            self._logger.error(f"Error normalizing content: {e}")
            return content


class SemanticDeduplicator:
    """Semantic duplicate detection using word-based similarity."""
    
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
    
    def calculate_jaccard_similarity(self, content1: str, content2: str) -> float:
        """
        Calculate Jaccard similarity between two content pieces.
        
        Args:
            content1: First content piece
            content2: Second content piece
            
        Returns:
            Jaccard similarity score (0.0 to 1.0)
        """
        try:
            # Tokenize and normalize
            tokens1 = set(self._tokenize_and_normalize(content1))
            tokens2 = set(self._tokenize_and_normalize(content2))
            
            if not tokens1 and not tokens2:
                return 1.0
            if not tokens1 or not tokens2:
                return 0.0
            
            # Calculate Jaccard similarity
            intersection = len(tokens1.intersection(tokens2))
            union = len(tokens1.union(tokens2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            self._logger.error(f"Error calculating Jaccard similarity: {e}")
            return 0.0
    
    def calculate_cosine_similarity(self, content1: str, content2: str) -> float:
        """
        Calculate cosine similarity using word frequency vectors.
        
        Args:
            content1: First content piece
            content2: Second content piece
            
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            # Get word frequency vectors
            tokens1 = self._tokenize_and_normalize(content1)
            tokens2 = self._tokenize_and_normalize(content2)
            
            if not tokens1 or not tokens2:
                return 0.0
            
            # Create frequency dictionaries
            freq1 = defaultdict(int)
            freq2 = defaultdict(int)
            
            for token in tokens1:
                freq1[token] += 1
            for token in tokens2:
                freq2[token] += 1
            
            # Get all unique tokens
            all_tokens = set(tokens1 + tokens2)
            
            # Create vectors
            vector1 = [freq1[token] for token in all_tokens]
            vector2 = [freq2[token] for token in all_tokens]
            
            # Calculate cosine similarity
            dot_product = sum(a * b for a, b in zip(vector1, vector2))
            magnitude1 = sum(a * a for a in vector1) ** 0.5
            magnitude2 = sum(b * b for b in vector2) ** 0.5
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception as e:
            self._logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def detect_semantic_duplicates(self, content: str, reference_content: List[str], 
                                 threshold: float = 0.8, method: SimilarityMethod = SimilarityMethod.JACCARD_SIMILARITY) -> Tuple[bool, List[str], float]:
        """
        Detect semantic duplicates using specified similarity method.
        
        Args:
            content: Content to check
            reference_content: List of reference content
            threshold: Similarity threshold
            method: Similarity calculation method
            
        Returns:
            Tuple of (is_duplicate, duplicate_sources, max_similarity)
        """
        try:
            duplicates = []
            max_similarity = 0.0
            
            for i, ref_content in enumerate(reference_content):
                if method == SimilarityMethod.JACCARD_SIMILARITY:
                    similarity = self.calculate_jaccard_similarity(content, ref_content)
                elif method == SimilarityMethod.COSINE_SIMILARITY:
                    similarity = self.calculate_cosine_similarity(content, ref_content)
                else:
                    similarity = 0.0
                
                if similarity > max_similarity:
                    max_similarity = similarity
                
                if similarity >= threshold:
                    duplicates.append(f"reference_{i}")
            
            return len(duplicates) > 0, duplicates, max_similarity
            
        except Exception as e:
            self._logger.error(f"Error detecting semantic duplicates: {e}")
            return False, [], 0.0
    
    def _tokenize_and_normalize(self, content: str) -> List[str]:
        """Tokenize and normalize content for semantic analysis."""
        try:
            # Tokenize
            tokens = word_tokenize(content.lower())
            
            # Filter alphabetic tokens only
            tokens = [token for token in tokens if token.isalpha()]
            
            # Remove stopwords
            try:
                stop_words = set(stopwords.words(self.language))
                tokens = [token for token in tokens if token not in stop_words]
            except:
                pass
            
            # Filter short tokens
            tokens = [token for token in tokens if len(token) > 2]
            
            return tokens
            
        except Exception as e:
            self._logger.error(f"Error tokenizing content: {e}")
            return []


class DuplicateDetector:
    """Advanced duplicate detection using multiple methods and fuzzy matching."""

    def __init__(self, language: str = "en"):
        self.language = language
        self._logger = get_logger(__name__)

    def calculate_edit_distance(self, content1: str, content2: str) -> float:
        """
        Calculate normalized edit distance between two content pieces.

        Args:
            content1: First content piece
            content2: Second content piece

        Returns:
            Normalized edit distance (0.0 = identical, 1.0 = completely different)
        """
        try:
            if not content1 and not content2:
                return 0.0
            if not content1 or not content2:
                return 1.0

            # Use SequenceMatcher for efficient edit distance calculation
            matcher = SequenceMatcher(None, content1, content2)
            similarity = matcher.ratio()

            # Convert similarity to distance
            return 1.0 - similarity

        except Exception as e:
            self._logger.error(f"Error calculating edit distance: {e}")
            return 1.0

    def detect_partial_duplicates(self, content: str, reference_content: List[str],
                                chunk_size: int = 100, threshold: float = 0.8) -> Tuple[bool, List[str], float]:
        """
        Detect partial duplicates by comparing content chunks.

        Args:
            content: Content to check
            reference_content: List of reference content
            chunk_size: Size of chunks for comparison
            threshold: Similarity threshold for partial duplicates

        Returns:
            Tuple of (is_duplicate, duplicate_sources, max_similarity)
        """
        try:
            content_chunks = self._create_chunks(content, chunk_size)
            if not content_chunks:
                return False, [], 0.0

            duplicates = []
            max_similarity = 0.0

            for i, ref_content in enumerate(reference_content):
                ref_chunks = self._create_chunks(ref_content, chunk_size)
                if not ref_chunks:
                    continue

                # Find best matching chunks
                chunk_similarities = []
                for content_chunk in content_chunks:
                    best_chunk_similarity = 0.0
                    for ref_chunk in ref_chunks:
                        similarity = SequenceMatcher(None, content_chunk, ref_chunk).ratio()
                        if similarity > best_chunk_similarity:
                            best_chunk_similarity = similarity
                    chunk_similarities.append(best_chunk_similarity)

                # Calculate overall similarity as average of best chunk matches
                if chunk_similarities:
                    avg_similarity = sum(chunk_similarities) / len(chunk_similarities)

                    if avg_similarity > max_similarity:
                        max_similarity = avg_similarity

                    if avg_similarity >= threshold:
                        duplicates.append(f"reference_{i}")

            return len(duplicates) > 0, duplicates, max_similarity

        except Exception as e:
            self._logger.error(f"Error detecting partial duplicates: {e}")
            return False, [], 0.0

    def detect_fuzzy_duplicates(self, content: str, reference_content: List[str],
                              max_distance: int = 5) -> Tuple[bool, List[str], float]:
        """
        Detect fuzzy duplicates using edit distance with tolerance.

        Args:
            content: Content to check
            reference_content: List of reference content
            max_distance: Maximum allowed edit distance

        Returns:
            Tuple of (is_duplicate, duplicate_sources, min_distance_ratio)
        """
        try:
            duplicates = []
            min_distance = float('inf')

            for i, ref_content in enumerate(reference_content):
                distance = self.calculate_edit_distance(content, ref_content)

                if distance < min_distance:
                    min_distance = distance

                # Convert distance to character-based threshold
                max_length = max(len(content), len(ref_content))
                if max_length > 0:
                    distance_ratio = distance * max_length
                    if distance_ratio <= max_distance:
                        duplicates.append(f"reference_{i}")

            min_distance_ratio = min_distance if min_distance != float('inf') else 1.0

            return len(duplicates) > 0, duplicates, min_distance_ratio

        except Exception as e:
            self._logger.error(f"Error detecting fuzzy duplicates: {e}")
            return False, [], 1.0

    def _create_chunks(self, content: str, chunk_size: int) -> List[str]:
        """Create overlapping chunks from content."""
        try:
            if len(content) <= chunk_size:
                return [content]

            chunks = []
            overlap = chunk_size // 4  # 25% overlap

            for i in range(0, len(content) - chunk_size + 1, chunk_size - overlap):
                chunk = content[i:i + chunk_size]
                chunks.append(chunk)

            return chunks

        except Exception as e:
            self._logger.error(f"Error creating chunks: {e}")
            return []


class DeduplicationEngine(IDeduplicationEngine):
    """
    Main deduplication engine that identifies and handles duplicate content.

    This class provides comprehensive duplicate detection using multiple methods:
    - Hash-based exact duplicate detection (O(1) lookup)
    - Near-exact duplicate detection using fuzzy matching
    - Semantic duplicate detection using NLP techniques
    - Partial duplicate detection using chunk comparison
    - Fuzzy duplicate detection with edit distance tolerance
    """

    def __init__(self, language: str = "en"):
        """Initialize deduplication engine with language support."""
        self.language = language
        self._logger = get_logger(__name__)

        # Initialize specialized deduplicators
        self.hash_deduplicator = HashBasedDeduplicator()
        self.semantic_deduplicator = SemanticDeduplicator(language)
        self.duplicate_detector = DuplicateDetector(language)

        # Cache for reference content hashes
        self._reference_hashes = {}

    def detect_duplicates(self, content: str, reference_content: List[str],
                         config: Optional[DeduplicationConfig] = None) -> DeduplicationResult:
        """
        Detect if content is duplicate of reference content using multiple methods.

        Args:
            content: Content to check for duplicates
            reference_content: List of reference content to compare against
            config: Deduplication configuration

        Returns:
            DeduplicationResult with comprehensive duplicate detection details
        """
        start_time = time.time()

        try:
            # Use default config if none provided
            if config is None:
                config = DeduplicationConfig()

            # Validate input
            if not content or not content.strip():
                return DeduplicationResult(
                    is_duplicate=False,
                    duplicate_type=DuplicateType.EXACT,
                    similarity_score=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            if not reference_content:
                return DeduplicationResult(
                    is_duplicate=False,
                    duplicate_type=DuplicateType.EXACT,
                    similarity_score=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            # Prepare reference hashes for exact duplicate detection
            reference_hashes = {}
            for i, ref_content in enumerate(reference_content):
                hash_value = self.hash_deduplicator.calculate_hash(ref_content, config.hash_algorithm)
                reference_hashes[f"reference_{i}"] = hash_value

            # Try different detection methods in order of efficiency
            similarity_details = {}
            duplicate_sources = []
            max_similarity = 0.0
            duplicate_type = DuplicateType.EXACT

            # 1. Exact duplicate detection (fastest)
            is_exact, exact_sources = self.hash_deduplicator.detect_exact_duplicates(content, reference_hashes)
            if is_exact:
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type=DuplicateType.EXACT,
                    similarity_score=1.0,
                    duplicate_sources=exact_sources,
                    similarity_details={SimilarityMethod.HASH_BASED: 1.0},
                    hash_values={
                        "content_hash": self.hash_deduplicator.calculate_hash(content, config.hash_algorithm),
                        "algorithm": config.hash_algorithm
                    },
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            # 2. Near-exact duplicate detection
            is_near_exact, near_exact_sources, near_exact_similarity = self.hash_deduplicator.detect_near_exact_duplicates(
                content, reference_content, config.similarity_threshold
            )
            if is_near_exact:
                max_similarity = near_exact_similarity
                duplicate_sources = near_exact_sources
                duplicate_type = DuplicateType.NEAR_EXACT
                similarity_details[SimilarityMethod.EDIT_DISTANCE] = near_exact_similarity

            # 3. Semantic duplicate detection (if enabled)
            if config.enable_semantic_dedup and SimilarityMethod.JACCARD_SIMILARITY in config.similarity_methods:
                is_semantic, semantic_sources, semantic_similarity = self.semantic_deduplicator.detect_semantic_duplicates(
                    content, reference_content, config.similarity_threshold, SimilarityMethod.JACCARD_SIMILARITY
                )
                similarity_details[SimilarityMethod.JACCARD_SIMILARITY] = semantic_similarity

                if is_semantic and semantic_similarity > max_similarity:
                    max_similarity = semantic_similarity
                    duplicate_sources = semantic_sources
                    duplicate_type = DuplicateType.SEMANTIC

            # 4. Cosine similarity (if enabled)
            if config.enable_semantic_dedup and SimilarityMethod.COSINE_SIMILARITY in config.similarity_methods:
                is_cosine, cosine_sources, cosine_similarity = self.semantic_deduplicator.detect_semantic_duplicates(
                    content, reference_content, config.similarity_threshold, SimilarityMethod.COSINE_SIMILARITY
                )
                similarity_details[SimilarityMethod.COSINE_SIMILARITY] = cosine_similarity

                if is_cosine and cosine_similarity > max_similarity:
                    max_similarity = cosine_similarity
                    duplicate_sources = cosine_sources
                    duplicate_type = DuplicateType.SEMANTIC

            # 5. Partial duplicate detection
            is_partial, partial_sources, partial_similarity = self.duplicate_detector.detect_partial_duplicates(
                content, reference_content, config.chunk_size, config.similarity_threshold
            )
            if is_partial and partial_similarity > max_similarity:
                max_similarity = partial_similarity
                duplicate_sources = partial_sources
                duplicate_type = DuplicateType.PARTIAL

            # 6. Fuzzy duplicate detection (if enabled)
            if config.enable_fuzzy_matching:
                is_fuzzy, fuzzy_sources, fuzzy_distance = self.duplicate_detector.detect_fuzzy_duplicates(
                    content, reference_content, config.max_distance
                )
                fuzzy_similarity = 1.0 - fuzzy_distance
                similarity_details[SimilarityMethod.EDIT_DISTANCE] = fuzzy_similarity

                if is_fuzzy and fuzzy_similarity > max_similarity:
                    max_similarity = fuzzy_similarity
                    duplicate_sources = fuzzy_sources
                    duplicate_type = DuplicateType.FUZZY

            # Determine if content is considered duplicate
            is_duplicate = max_similarity >= config.similarity_threshold

            processing_time = (time.time() - start_time) * 1000

            return DeduplicationResult(
                is_duplicate=is_duplicate,
                duplicate_type=duplicate_type,
                similarity_score=max_similarity,
                duplicate_sources=duplicate_sources,
                similarity_details=similarity_details,
                hash_values={
                    "content_hash": self.hash_deduplicator.calculate_hash(content, config.hash_algorithm),
                    "algorithm": config.hash_algorithm
                },
                processing_time_ms=processing_time,
                metadata={
                    "content_length": len(content),
                    "reference_count": len(reference_content),
                    "methods_used": [method.value for method in config.similarity_methods],
                    "semantic_enabled": config.enable_semantic_dedup,
                    "fuzzy_enabled": config.enable_fuzzy_matching
                }
            )

        except Exception as e:
            self._logger.error(f"Error detecting duplicates: {e}")
            processing_time = (time.time() - start_time) * 1000

            return DeduplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.EXACT,
                similarity_score=0.0,
                processing_time_ms=processing_time,
                metadata={"error": str(e)}
            )

    def calculate_similarity(self, content1: str, content2: str,
                           method: SimilarityMethod = SimilarityMethod.HASH_BASED) -> float:
        """
        Calculate similarity between two content pieces using specified method.

        Args:
            content1: First content piece
            content2: Second content piece
            method: Similarity calculation method

        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            if not content1 or not content2:
                return 0.0

            if method == SimilarityMethod.HASH_BASED:
                hash1 = self.hash_deduplicator.calculate_hash(content1)
                hash2 = self.hash_deduplicator.calculate_hash(content2)
                return 1.0 if hash1 == hash2 else 0.0

            elif method == SimilarityMethod.JACCARD_SIMILARITY:
                return self.semantic_deduplicator.calculate_jaccard_similarity(content1, content2)

            elif method == SimilarityMethod.COSINE_SIMILARITY:
                return self.semantic_deduplicator.calculate_cosine_similarity(content1, content2)

            elif method == SimilarityMethod.EDIT_DISTANCE:
                distance = self.duplicate_detector.calculate_edit_distance(content1, content2)
                return 1.0 - distance  # Convert distance to similarity

            else:
                self._logger.warning(f"Unsupported similarity method: {method}")
                return 0.0

        except Exception as e:
            self._logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def get_content_hash(self, content: str, algorithm: str = "sha256") -> str:
        """
        Generate hash for content using specified algorithm.

        Args:
            content: Content to hash
            algorithm: Hash algorithm to use (sha256, md5, sha1)

        Returns:
            Content hash string
        """
        try:
            return self.hash_deduplicator.calculate_hash(content, algorithm)

        except Exception as e:
            self._logger.error(f"Error generating content hash: {e}")
            return ""

    def batch_detect_duplicates(self, content_list: List[str],
                              config: Optional[DeduplicationConfig] = None) -> List[DeduplicationResult]:
        """
        Detect duplicates for multiple content pieces efficiently.

        Args:
            content_list: List of content to check for duplicates
            config: Deduplication configuration

        Returns:
            List of DeduplicationResult for each content piece
        """
        try:
            if not content_list:
                return []

            results = []

            # Use each content as reference for others (O(n²) but optimized)
            for i, content in enumerate(content_list):
                # Use all other content as reference
                reference_content = content_list[:i] + content_list[i+1:]

                if reference_content:
                    result = self.detect_duplicates(content, reference_content, config)
                    results.append(result)
                else:
                    # First item has no reference
                    results.append(DeduplicationResult(
                        is_duplicate=False,
                        duplicate_type=DuplicateType.EXACT,
                        similarity_score=0.0
                    ))

            return results

        except Exception as e:
            self._logger.error(f"Error in batch duplicate detection: {e}")
            return []

    def get_duplicate_clusters(self, content_list: List[str],
                             config: Optional[DeduplicationConfig] = None) -> List[List[int]]:
        """
        Group content into duplicate clusters.

        Args:
            content_list: List of content to cluster
            config: Deduplication configuration

        Returns:
            List of clusters, where each cluster is a list of content indices
        """
        try:
            if not content_list:
                return []

            if config is None:
                config = DeduplicationConfig()

            # Build similarity matrix
            n = len(content_list)
            similarity_matrix = [[0.0] * n for _ in range(n)]

            for i in range(n):
                for j in range(i + 1, n):
                    similarity = self.calculate_similarity(
                        content_list[i],
                        content_list[j],
                        SimilarityMethod.JACCARD_SIMILARITY
                    )
                    similarity_matrix[i][j] = similarity
                    similarity_matrix[j][i] = similarity

            # Find clusters using threshold-based grouping
            clusters = []
            visited = [False] * n

            for i in range(n):
                if visited[i]:
                    continue

                # Start new cluster
                cluster = [i]
                visited[i] = True

                # Find all similar items
                for j in range(i + 1, n):
                    if not visited[j] and similarity_matrix[i][j] >= config.similarity_threshold:
                        cluster.append(j)
                        visited[j] = True

                clusters.append(cluster)

            return clusters

        except Exception as e:
            self._logger.error(f"Error creating duplicate clusters: {e}")
            return []
