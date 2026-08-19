"""
Module: augmentation_engine_lg
Description: Augments prompts with retrieved context for LLM input
Phase: 4
Location: /src/modules/logic/rag_orchestrator_lg/augmentation_engine_lg/
"""

# Standard library imports
import re
import time
from typing import List, Dict, Any, Optional, Tuple
import logging
import threading
from string import Template
import textwrap

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.rag_orchestrator_lg.base_interfaces import (
    IAugmentationEngine, AugmentationConfig, AugmentationResult, AugmentationStrategy
)
from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk
from src.modules.logic.logging_infrastructure_lg import get_logger


class ContextCompressor:
    """Compresses context while preserving important information."""
    
    def __init__(self):
        self._importance_patterns = [
            r'\b(?:important|critical|key|essential|main|primary)\b',
            r'\b(?:definition|meaning|concept)\b',
            r'\b(?:result|conclusion|summary)\b',
            r'\b(?:first|second|third|finally)\b',
            r'\b(?:because|therefore|thus|hence)\b'
        ]
        self._compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self._importance_patterns]
    
    def compress(self, text: str, target_length: int) -> Tuple[str, float]:
        """
        Compress text to target length while preserving important information.
        
        Args:
            text: Original text to compress
            target_length: Target length in characters
            
        Returns:
            Tuple of (compressed_text, compression_ratio)
        """
        if len(text) <= target_length:
            return text, 1.0
        
        # Split into sentences
        sentences = self._split_into_sentences(text)
        
        # Score sentences by importance
        scored_sentences = []
        for sentence in sentences:
            score = self._calculate_importance_score(sentence)
            scored_sentences.append((sentence, score))
        
        # Sort by importance score
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # Select sentences until target length is reached
        compressed_text = ""
        for sentence, score in scored_sentences:
            if len(compressed_text) + len(sentence) <= target_length:
                compressed_text += sentence + " "
            else:
                break
        
        compression_ratio = len(compressed_text) / len(text) if text else 0.0
        return compressed_text.strip(), compression_ratio
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _calculate_importance_score(self, sentence: str) -> float:
        """Calculate importance score for a sentence."""
        score = 0.0
        
        # Check for importance patterns
        for pattern in self._compiled_patterns:
            if pattern.search(sentence):
                score += 1.0
        
        # Length bonus (moderate length sentences are often more informative)
        length_score = min(len(sentence) / 100, 1.0)
        score += length_score * 0.5
        
        # Position bonus (first and last sentences often important)
        # This would need context about sentence position
        
        return score


class TemplateValidator:
    """Validates and processes augmentation templates."""
    
    def __init__(self):
        self._required_placeholders = {'query', 'context'}
        self._optional_placeholders = {'metadata', 'source', 'timestamp'}
    
    def validate_template(self, template: str) -> bool:
        """
        Validate augmentation template.
        
        Args:
            template: Template string to validate
            
        Returns:
            True if template is valid, False otherwise
        """
        try:
            # Check if template is a valid string template
            template_obj = Template(template)
            
            # Extract placeholders
            placeholders = set(re.findall(r'\{(\w+)\}', template))
            
            # Check required placeholders
            if not self._required_placeholders.issubset(placeholders):
                return False
            
            # Check for unknown placeholders
            all_valid = self._required_placeholders | self._optional_placeholders
            if not placeholders.issubset(all_valid):
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_placeholders(self, template: str) -> List[str]:
        """Extract placeholders from template."""
        return re.findall(r'\{(\w+)\}', template)


class AugmentationEngine(IAugmentationEngine):
    """
    Augments prompts with retrieved context for LLM input.
    
    Provides:
    - Multiple augmentation strategies
    - Template-based prompt formatting
    - Context compression and optimization
    - Metadata integration
    - Hierarchical context organization
    - Adaptive formatting based on content
    - Quality validation and optimization
    - Performance monitoring
    """
    
    def __init__(self):
        """Initialize augmentation engine."""
        self._compressor = ContextCompressor()
        self._validator = TemplateValidator()
        self._metrics = {}
        self._lock = threading.RLock()
        self._initialized = False
        
        self._default_templates = {
            AugmentationStrategy.SIMPLE_CONCATENATION: "{context}\n\n{query}",
            AugmentationStrategy.TEMPLATE_BASED: "Context: {context}\n\nQuestion: {query}\n\nAnswer:",
            AugmentationStrategy.CONTEXT_AWARE: "Based on the following information:\n{context}\n\nPlease answer: {query}",
            AugmentationStrategy.HIERARCHICAL: "## Context\n{context}\n\n## Question\n{query}\n\n## Answer",
            AugmentationStrategy.ADAPTIVE_FORMATTING: "Relevant Information:\n{context}\n\nQuery: {query}\n\nResponse:"
        }
        
        self._logger = get_logger(__name__)
    
    async def initialize(self) -> bool:
        """
        Initialize the augmentation engine.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Validate default templates
                for strategy, template in self._default_templates.items():
                    if not self._validator.validate_template(template):
                        self._logger.warning(f"Invalid default template for strategy {strategy}")
                
                self._initialized = True
                self._logger.info("Augmentation engine initialized successfully")
                return True
                
        except Exception as e:
            self._logger.error(f"Error initializing augmentation engine: {e}")
            return False
    
    async def augment_prompt(self, query: str, context_chunks: List[DocumentChunk],
                           config: Optional[AugmentationConfig] = None) -> AugmentationResult:
        """
        Augment prompt with retrieved context.
        
        Args:
            query: Original query string
            context_chunks: Retrieved context chunks
            config: Optional augmentation configuration
            
        Returns:
            AugmentationResult with augmented prompt and metadata
        """
        if not self._initialized:
            raise RuntimeError("Augmentation engine not initialized")
        
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        config = config or AugmentationConfig()
        start_time = time.time()
        
        try:
            # Prepare context
            context_text = self._prepare_context(context_chunks, config)
            
            # Apply compression if needed
            compression_applied = False
            if config.enable_compression and len(context_text) > config.max_context_length:
                context_text, compression_ratio = await self.compress_context(
                    context_text, int(config.max_context_length * config.compression_ratio)
                )
                compression_applied = True
            
            # Apply augmentation strategy
            augmented_prompt = await self._apply_augmentation_strategy(
                query, context_text, config
            )
            
            # Validate result length
            if len(augmented_prompt) > config.max_context_length:
                # Truncate if still too long
                augmented_prompt = augmented_prompt[:config.max_context_length]
                self._logger.warning("Augmented prompt truncated to max length")
            
            processing_time = (time.time() - start_time) * 1000
            
            return AugmentationResult(
                augmented_prompt=augmented_prompt,
                original_query=query,
                context_chunks=context_chunks,
                context_length=len(context_text),
                compression_applied=compression_applied,
                processing_time_ms=processing_time,
                metadata={
                    'strategy': config.strategy.value,
                    'num_chunks': len(context_chunks),
                    'template_used': config.context_template
                }
            )
            
        except Exception as e:
            self._logger.error(f"Error augmenting prompt: {e}")
            processing_time = (time.time() - start_time) * 1000
            
            # Return minimal result on error
            return AugmentationResult(
                augmented_prompt=query,  # Fallback to original query
                original_query=query,
                context_chunks=[],
                context_length=0,
                compression_applied=False,
                processing_time_ms=processing_time,
                metadata={'error': str(e)}
            )
    
    def get_supported_strategies(self) -> List[AugmentationStrategy]:
        """
        Get list of supported augmentation strategies.
        
        Returns:
            List of supported AugmentationStrategy enums
        """
        return list(AugmentationStrategy)
    
    async def compress_context(self, context: str, target_length: int) -> Tuple[str, float]:
        """
        Compress context to target length.
        
        Args:
            context: Original context string
            target_length: Target length in characters
            
        Returns:
            Tuple of (compressed_context, compression_ratio)
        """
        try:
            return self._compressor.compress(context, target_length)
        except Exception as e:
            self._logger.error(f"Error compressing context: {e}")
            # Fallback to simple truncation
            if len(context) > target_length:
                compressed = context[:target_length]
                ratio = target_length / len(context)
                return compressed, ratio
            return context, 1.0
    
    def validate_template(self, template: str) -> bool:
        """
        Validate augmentation template.
        
        Args:
            template: Template string to validate
            
        Returns:
            True if template is valid, False otherwise
        """
        return self._validator.validate_template(template)

    def _prepare_context(self, chunks: List[DocumentChunk], config: AugmentationConfig) -> str:
        """Prepare context text from chunks."""
        if not chunks:
            return ""

        context_parts = []

        for i, chunk in enumerate(chunks):
            chunk_text = chunk.content

            # Add metadata if enabled
            if config.include_metadata and chunk.metadata:
                metadata_info = []
                if 'source' in chunk.metadata:
                    metadata_info.append(f"Source: {chunk.metadata['source']}")
                if 'page' in chunk.metadata:
                    metadata_info.append(f"Page: {chunk.metadata['page']}")

                if metadata_info:
                    chunk_text = f"[{', '.join(metadata_info)}] {chunk_text}"

            # Preserve formatting if enabled
            if config.preserve_formatting:
                chunk_text = chunk_text.strip()
            else:
                # Normalize whitespace
                chunk_text = ' '.join(chunk_text.split())

            context_parts.append(chunk_text)

        # Join chunks with appropriate separator
        if config.strategy == AugmentationStrategy.HIERARCHICAL:
            return '\n\n'.join(f"### Context {i+1}\n{part}" for i, part in enumerate(context_parts))
        else:
            return '\n\n'.join(context_parts)

    async def _apply_augmentation_strategy(self, query: str, context: str,
                                         config: AugmentationConfig) -> str:
        """Apply specific augmentation strategy."""
        try:
            if config.strategy == AugmentationStrategy.SIMPLE_CONCATENATION:
                return f"{context}\n\n{query}"

            elif config.strategy == AugmentationStrategy.TEMPLATE_BASED:
                template = config.context_template
                return template.format(context=context, query=query)

            elif config.strategy == AugmentationStrategy.CONTEXT_AWARE:
                return self._apply_context_aware_strategy(query, context)

            elif config.strategy == AugmentationStrategy.HIERARCHICAL:
                return self._apply_hierarchical_strategy(query, context)

            elif config.strategy == AugmentationStrategy.ADAPTIVE_FORMATTING:
                return self._apply_adaptive_formatting(query, context)

            else:
                # Fallback to template-based
                return config.context_template.format(context=context, query=query)

        except Exception as e:
            self._logger.error(f"Error applying augmentation strategy: {e}")
            # Fallback to simple concatenation
            return f"{context}\n\n{query}"

    def _apply_context_aware_strategy(self, query: str, context: str) -> str:
        """Apply context-aware augmentation strategy."""
        # Analyze query type and adapt accordingly
        query_lower = query.lower()

        if any(word in query_lower for word in ['what', 'define', 'explain']):
            return f"Based on the following information, please provide a clear explanation:\n\n{context}\n\nQuestion: {query}\n\nExplanation:"

        elif any(word in query_lower for word in ['how', 'steps', 'process']):
            return f"Using the following context as reference:\n\n{context}\n\nPlease explain the process for: {query}\n\nStep-by-step answer:"

        elif any(word in query_lower for word in ['why', 'reason', 'cause']):
            return f"Consider the following information:\n\n{context}\n\nAnalyze and explain: {query}\n\nAnalysis:"

        else:
            return f"Based on the following information:\n\n{context}\n\nPlease answer: {query}\n\nAnswer:"

    def _apply_hierarchical_strategy(self, query: str, context: str) -> str:
        """Apply hierarchical augmentation strategy."""
        return f"""# Information Analysis

## Relevant Context
{context}

## Query
{query}

## Response
Please provide a comprehensive answer based on the context above:"""

    def _apply_adaptive_formatting(self, query: str, context: str) -> str:
        """Apply adaptive formatting based on content characteristics."""
        # Analyze context length and complexity
        context_length = len(context)

        if context_length < 500:
            # Short context - simple format
            return f"Context: {context}\n\nQ: {query}\nA:"

        elif context_length < 2000:
            # Medium context - structured format
            return f"## Relevant Information\n{context}\n\n## Question\n{query}\n\n## Answer"

        else:
            # Long context - detailed format
            wrapped_context = textwrap.fill(context, width=80)
            return f"""## Background Information
{wrapped_context}

## Question
{query}

## Detailed Response
Based on the information provided above, please give a comprehensive answer:"""
