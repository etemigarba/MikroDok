"""
Module: keyword_searcher_lg
Description: Implements BM25 algorithm for traditional keyword-based search
Phase: 4
Location: /src/modules/logic/hybrid_search_lg/keyword_searcher_lg/
"""

# Standard library imports
import re
import time
import math
import threading
from collections import defaultdict, Counter
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError
from ..base_interfaces import (
    IKeywordSearcher,
    KeywordSearchResult,
    KeywordSearchConfig,
    SearchResultItem,
    SearchType,
    SearchStatus
)


class TermProcessor:
    """Handles text preprocessing and term extraction for keyword search."""
    
    def __init__(self):
        """Initialize term processor."""
        self._logger = get_logger(__name__)
        self._stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 'have',
            'had', 'what', 'said', 'each', 'which', 'their', 'time', 'if'
        }
    
    def process_text(self, text: str, config: Optional[KeywordSearchConfig] = None) -> List[str]:
        """
        Process text and extract terms for indexing.
        
        Args:
            text: Input text to process
            config: Optional keyword search configuration
            
        Returns:
            List of processed terms
        """
        try:
            if not text:
                return []
            
            config = config or KeywordSearchConfig()
            
            # Convert to lowercase if not case sensitive
            if not config.case_sensitive:
                text = text.lower()
            
            # Extract words using regex
            words = re.findall(r'\b\w+\b', text)
            
            # Filter by minimum length
            words = [word for word in words if len(word) >= config.min_term_length]
            
            # Remove stopwords if enabled
            if config.enable_stopword_removal:
                words = [word for word in words if word not in self._stopwords]
            
            # Apply stemming if enabled (simple suffix removal)
            if config.enable_stemming:
                words = [self._simple_stem(word) for word in words]
            
            return words
            
        except Exception as e:
            self._logger.error(f"Error processing text: {e}")
            return []
    
    def _simple_stem(self, word: str) -> str:
        """Apply simple stemming by removing common suffixes."""
        suffixes = ['ing', 'ed', 'er', 'est', 'ly', 's']
        for suffix in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return word[:-len(suffix)]
        return word
    
    def extract_query_terms(self, query: str, config: Optional[KeywordSearchConfig] = None) -> List[str]:
        """
        Extract and process terms from search query.
        
        Args:
            query: Search query string
            config: Optional keyword search configuration
            
        Returns:
            List of processed query terms
        """
        return self.process_text(query, config)


class InvertedIndexBuilder:
    """Builds and maintains inverted index for keyword search."""
    
    def __init__(self):
        """Initialize inverted index builder."""
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Inverted index: term -> {doc_id: term_frequency}
        self._inverted_index: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        # Document statistics
        self._document_lengths: Dict[str, int] = {}
        self._document_count = 0
        self._average_document_length = 0.0
        
        # Term statistics
        self._document_frequencies: Dict[str, int] = defaultdict(int)
        self._term_processor = TermProcessor()
    
    def build_index(self, documents: List[Dict[str, Any]], 
                   config: Optional[KeywordSearchConfig] = None) -> bool:
        """
        Build inverted index from documents.
        
        Args:
            documents: List of documents to index
            config: Optional keyword search configuration
            
        Returns:
            True if index built successfully
        """
        try:
            self._logger.info(f"Building inverted index for {len(documents)} documents...")
            
            with self._lock:
                # Clear existing index
                self._inverted_index.clear()
                self._document_lengths.clear()
                self._document_frequencies.clear()
                self._document_count = 0
                
                total_length = 0
                
                for doc in documents:
                    doc_id = doc.get('chunk_id', doc.get('id', ''))
                    content = doc.get('content', '')
                    
                    if not doc_id or not content:
                        continue
                    
                    # Process document text
                    terms = self._term_processor.process_text(content, config)
                    
                    # Count term frequencies in document
                    term_counts = Counter(terms)
                    doc_length = len(terms)
                    
                    # Update inverted index
                    for term, count in term_counts.items():
                        self._inverted_index[term][doc_id] = count
                    
                    # Update document statistics
                    self._document_lengths[doc_id] = doc_length
                    total_length += doc_length
                    self._document_count += 1
                    
                    # Update document frequencies
                    unique_terms = set(terms)
                    for term in unique_terms:
                        self._document_frequencies[term] += 1
                
                # Calculate average document length
                if self._document_count > 0:
                    self._average_document_length = total_length / self._document_count
            
            self._logger.info(f"Inverted index built successfully: {len(self._inverted_index)} terms, "
                            f"{self._document_count} documents")
            return True
            
        except Exception as e:
            self._logger.error(f"Error building inverted index: {e}")
            return False
    
    def update_index(self, document: Dict[str, Any], 
                    config: Optional[KeywordSearchConfig] = None) -> bool:
        """
        Update index with new document.
        
        Args:
            document: Document to add to index
            config: Optional keyword search configuration
            
        Returns:
            True if update successful
        """
        try:
            doc_id = document.get('chunk_id', document.get('id', ''))
            content = document.get('content', '')
            
            if not doc_id or not content:
                return False
            
            with self._lock:
                # Process document text
                terms = self._term_processor.process_text(content, config)
                term_counts = Counter(terms)
                doc_length = len(terms)
                
                # Remove old document if it exists
                if doc_id in self._document_lengths:
                    self._remove_document(doc_id)
                
                # Add new document
                for term, count in term_counts.items():
                    self._inverted_index[term][doc_id] = count
                
                # Update document statistics
                old_total = self._average_document_length * self._document_count
                self._document_lengths[doc_id] = doc_length
                self._document_count += 1
                self._average_document_length = (old_total + doc_length) / self._document_count
                
                # Update document frequencies
                unique_terms = set(terms)
                for term in unique_terms:
                    self._document_frequencies[term] += 1
            
            return True
            
        except Exception as e:
            self._logger.error(f"Error updating index: {e}")
            return False
    
    def _remove_document(self, doc_id: str) -> None:
        """Remove document from index."""
        if doc_id not in self._document_lengths:
            return
        
        # Remove from inverted index and update document frequencies
        for term in list(self._inverted_index.keys()):
            if doc_id in self._inverted_index[term]:
                del self._inverted_index[term][doc_id]
                self._document_frequencies[term] -= 1
                
                # Remove term if no documents contain it
                if self._document_frequencies[term] <= 0:
                    del self._inverted_index[term]
                    del self._document_frequencies[term]
        
        # Update document statistics
        old_length = self._document_lengths[doc_id]
        del self._document_lengths[doc_id]
        
        if self._document_count > 1:
            old_total = self._average_document_length * self._document_count
            self._document_count -= 1
            self._average_document_length = (old_total - old_length) / self._document_count
        else:
            self._document_count = 0
            self._average_document_length = 0.0
    
    def get_term_documents(self, term: str) -> Dict[str, int]:
        """Get documents containing a specific term."""
        with self._lock:
            return dict(self._inverted_index.get(term, {}))
    
    def get_document_frequency(self, term: str) -> int:
        """Get document frequency for a term."""
        with self._lock:
            return self._document_frequencies.get(term, 0)
    
    def get_document_length(self, doc_id: str) -> int:
        """Get length of a specific document."""
        with self._lock:
            return self._document_lengths.get(doc_id, 0)
    
    def get_average_document_length(self) -> float:
        """Get average document length."""
        with self._lock:
            return self._average_document_length
    
    def get_document_count(self) -> int:
        """Get total number of documents."""
        with self._lock:
            return self._document_count


class BM25Calculator:
    """Implements BM25 scoring algorithm for keyword search."""
    
    def __init__(self, index_builder: InvertedIndexBuilder):
        """Initialize BM25 calculator."""
        self._index_builder = index_builder
        self._logger = get_logger(__name__)
    
    def calculate_bm25_score(self, query_terms: List[str], doc_id: str,
                           config: Optional[KeywordSearchConfig] = None) -> float:
        """
        Calculate BM25 score for a document given query terms.
        
        Args:
            query_terms: List of query terms
            doc_id: Document identifier
            config: Optional keyword search configuration
            
        Returns:
            BM25 score for the document
        """
        try:
            config = config or KeywordSearchConfig()
            
            score = 0.0
            doc_length = self._index_builder.get_document_length(doc_id)
            avg_doc_length = self._index_builder.get_average_document_length()
            total_docs = self._index_builder.get_document_count()
            
            if doc_length == 0 or avg_doc_length == 0 or total_docs == 0:
                return 0.0
            
            for term in query_terms:
                # Get term frequency in document
                term_docs = self._index_builder.get_term_documents(term)
                tf = term_docs.get(doc_id, 0)
                
                if tf == 0:
                    continue
                
                # Get document frequency
                df = self._index_builder.get_document_frequency(term)
                
                if df == 0:
                    continue
                
                # Calculate IDF
                idf = math.log((total_docs - df + 0.5) / (df + 0.5))
                
                # Calculate BM25 component
                numerator = tf * (config.k1 + 1)
                denominator = tf + config.k1 * (1 - config.b + config.b * (doc_length / avg_doc_length))
                
                score += idf * (numerator / denominator)
            
            return max(0.0, score)
            
        except Exception as e:
            self._logger.error(f"Error calculating BM25 score: {e}")
            return 0.0
    
    def calculate_scores_for_query(self, query_terms: List[str],
                                 config: Optional[KeywordSearchConfig] = None) -> Dict[str, float]:
        """
        Calculate BM25 scores for all documents matching query terms.
        
        Args:
            query_terms: List of query terms
            config: Optional keyword search configuration
            
        Returns:
            Dictionary mapping document IDs to BM25 scores
        """
        try:
            scores = {}
            candidate_docs = set()
            
            # Find all documents containing any query term
            for term in query_terms:
                term_docs = self._index_builder.get_term_documents(term)
                candidate_docs.update(term_docs.keys())
            
            # Calculate BM25 score for each candidate document
            for doc_id in candidate_docs:
                score = self.calculate_bm25_score(query_terms, doc_id, config)
                if score > 0:
                    scores[doc_id] = score
            
            return scores
            
        except Exception as e:
            self._logger.error(f"Error calculating query scores: {e}")
            return {}


class KeywordSearcher(IKeywordSearcher):
    """Main keyword search implementation using BM25 algorithm."""
    
    def __init__(self):
        """Initialize keyword searcher."""
        self._index_builder = InvertedIndexBuilder()
        self._bm25_calculator = BM25Calculator(self._index_builder)
        self._term_processor = TermProcessor()
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Document store for content retrieval
        self._document_store: Dict[str, Dict[str, Any]] = {}
    
    def search(self, query: str, config: Optional[KeywordSearchConfig] = None) -> KeywordSearchResult:
        """
        Perform keyword-based search using BM25 algorithm.
        
        Args:
            query: Search query string
            config: Optional search configuration
            
        Returns:
            KeywordSearchResult with search results and metadata
        """
        start_time = time.time()
        config = config or KeywordSearchConfig()
        
        try:
            self._logger.info(f"Starting keyword search for query: {query[:100]}...")
            
            # Extract query terms
            query_terms = self._term_processor.extract_query_terms(query, config)
            
            if not query_terms:
                return KeywordSearchResult(
                    status=SearchStatus.COMPLETED,
                    query=query,
                    query_terms=query_terms,
                    search_time_ms=(time.time() - start_time) * 1000,
                    metadata={"message": "No valid query terms found"}
                )
            
            # Calculate BM25 scores
            doc_scores = self._bm25_calculator.calculate_scores_for_query(query_terms, config)
            
            # Sort by score and limit results
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
            sorted_docs = sorted_docs[:config.max_results]
            
            # Build search results
            results = []
            for rank, (doc_id, score) in enumerate(sorted_docs, 1):
                doc_info = self._document_store.get(doc_id, {})
                
                search_item = SearchResultItem(
                    chunk_id=doc_id,
                    document_id=doc_info.get("document_id", "unknown"),
                    score=score,
                    content=doc_info.get("content", ""),
                    search_type=SearchType.KEYWORD,
                    rank=rank,
                    metadata=doc_info.get("metadata", {}),
                    timestamp=datetime.now()
                )
                results.append(search_item)
            
            # Calculate term frequencies for metadata
            term_frequencies = Counter(query_terms)
            document_frequencies = {
                term: self._index_builder.get_document_frequency(term)
                for term in query_terms
            }
            
            search_time = (time.time() - start_time) * 1000
            
            self._logger.info(f"Keyword search completed in {search_time:.2f}ms, found {len(results)} results")
            
            return KeywordSearchResult(
                status=SearchStatus.COMPLETED,
                query=query,
                query_terms=query_terms,
                results=results,
                total_documents=self._index_builder.get_document_count(),
                search_time_ms=search_time,
                algorithm_used="BM25",
                term_frequencies=dict(term_frequencies),
                document_frequencies=document_frequencies,
                metadata={
                    "config": config.__dict__,
                    "candidate_documents": len(doc_scores)
                }
            )
            
        except Exception as e:
            self._logger.error(f"Error in keyword search: {e}")
            return KeywordSearchResult(
                status=SearchStatus.FAILED,
                query=query,
                search_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )
    
    def build_index(self, documents: List[Dict[str, Any]]) -> bool:
        """
        Build inverted index for keyword search.
        
        Args:
            documents: List of documents to index
            
        Returns:
            True if index built successfully
        """
        try:
            # Store documents for content retrieval
            with self._lock:
                self._document_store.clear()
                for doc in documents:
                    doc_id = doc.get('chunk_id', doc.get('id', ''))
                    if doc_id:
                        self._document_store[doc_id] = doc
            
            # Build inverted index
            return self._index_builder.build_index(documents)
            
        except Exception as e:
            self._logger.error(f"Error building index: {e}")
            return False
    
    def update_index(self, document: Dict[str, Any]) -> bool:
        """
        Update index with new document.
        
        Args:
            document: Document to add to index
            
        Returns:
            True if update successful
        """
        try:
            doc_id = document.get('chunk_id', document.get('id', ''))
            if not doc_id:
                return False
            
            # Store document for content retrieval
            with self._lock:
                self._document_store[doc_id] = document
            
            # Update inverted index
            return self._index_builder.update_index(document)
            
        except Exception as e:
            self._logger.error(f"Error updating index: {e}")
            return False
    
    def get_term_statistics(self, term: str) -> Dict[str, Any]:
        """
        Get statistics for a specific term.
        
        Args:
            term: Term to get statistics for
            
        Returns:
            Dictionary with term frequency, document frequency, etc.
        """
        try:
            term_docs = self._index_builder.get_term_documents(term)
            doc_frequency = self._index_builder.get_document_frequency(term)
            total_frequency = sum(term_docs.values())
            
            return {
                "term": term,
                "document_frequency": doc_frequency,
                "total_frequency": total_frequency,
                "documents": len(term_docs),
                "average_frequency": total_frequency / max(1, len(term_docs)),
                "document_ids": list(term_docs.keys())
            }
            
        except Exception as e:
            self._logger.error(f"Error getting term statistics: {e}")
            return {"term": term, "error": str(e)}
