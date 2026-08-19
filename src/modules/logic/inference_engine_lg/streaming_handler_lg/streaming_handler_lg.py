"""
Module: streaming_handler_lg
Description: Handles streaming text generation with real-time response delivery and proper resource management
Phase: 4
Location: /src/modules/logic/inference_engine_lg/streaming_handler_lg/streaming_handler_lg.py
"""

# Standard library imports
import asyncio
import time
import threading
import uuid
from collections import deque
from typing import Dict, Any, Optional, List, AsyncIterator
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

# Third-party imports
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import (
        AutoModelForCausalLM, 
        AutoTokenizer,
        TextIteratorStreamer,
        GenerationConfig as HFGenerationConfig
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Local imports
from src.modules.logic.inference_engine_lg.base_interfaces import (
    IStreamingHandler,
    StreamingConfig,
    StreamingChunk,
    StreamingMode,
    InferenceStatus,
    GenerationConfig,
    ModelInfo,
    TokenizerInfo,
    InferenceMetrics
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)


class StreamingError(Exception):
    """Exception raised when streaming fails."""
    pass


class StreamNotFoundError(Exception):
    """Exception raised when stream is not found."""
    pass


class StreamingSession:
    """Represents an active streaming session."""
    
    def __init__(self, stream_id: str, prompt: str, config: StreamingConfig):
        self.stream_id = stream_id
        self.prompt = prompt
        self.config = config
        self.chunks: deque = deque(maxlen=config.buffer_size)
        self.is_active = True
        self.is_complete = False
        self.error = None
        self.created_at = time.time()
        self.last_activity = time.time()
        self.total_tokens = 0
        self.lock = threading.RLock()


class StreamingHandler(IStreamingHandler):
    """
    Production-ready streaming handler for real-time text generation.
    
    Supports multiple streaming modes, buffering, and concurrent streams
    with proper resource management and error handling.
    """
    
    def __init__(self, model_info: Optional[ModelInfo] = None, 
                 tokenizer_info: Optional[TokenizerInfo] = None):
        """Initialize streaming handler with optional model and tokenizer info."""
        self._logger = get_log_manager().get_logger(__name__)
        self._model_info = model_info
        self._tokenizer_info = tokenizer_info
        self._model = None
        self._tokenizer = None
        self._device = "cpu"
        
        # Streaming management
        self._active_streams: Dict[str, StreamingSession] = {}
        self._stream_locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="streaming")
        
        # Configuration and monitoring
        self._validator = ValidationEngine()
        self._metrics = InferenceMetrics()
        self._max_concurrent_streams = 5
        self._stream_timeout = 300  # 5 minutes
        self._cleanup_interval = 60  # 1 minute
        self._last_cleanup = time.time()
        
        # Performance settings
        self._enable_buffering = True
        self._chunk_aggregation = True
        
        self._logger.info("Streaming handler initialized")
    
    def set_model_and_tokenizer(self, model: Any, tokenizer: Any, device: str = "cpu") -> None:
        """
        Set the model and tokenizer for streaming.
        
        Args:
            model: Loaded model instance
            tokenizer: Loaded tokenizer instance
            device: Device to use for generation
        """
        try:
            self._model = model
            self._tokenizer = tokenizer
            self._device = device
            
            self._logger.info(f"Model and tokenizer set for streaming on device: {device}")
            
        except Exception as e:
            self._logger.error(f"Failed to set model and tokenizer: {str(e)}")
            raise
    
    async def start_streaming(self, prompt: str, context_id: Optional[str] = None,
                            config: Optional[StreamingConfig] = None) -> str:
        """
        Start streaming text generation.
        
        Args:
            prompt: Input prompt
            context_id: Optional context identifier
            config: Optional streaming configuration
            
        Returns:
            Stream identifier
        """
        if not self._model or not self._tokenizer:
            raise StreamingError("Model and tokenizer must be loaded before streaming")
        
        # Validate inputs
        validation_result = self._validate_streaming_inputs(prompt, config)
        if not validation_result.is_valid:
            error_msg = f"Invalid streaming inputs: {validation_result.get_error_summary()}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
        
        config = config or StreamingConfig()
        stream_id = str(uuid.uuid4())
        
        try:
            with self._global_lock:
                # Check concurrent stream limit
                if len(self._active_streams) >= self._max_concurrent_streams:
                    raise StreamingError(f"Maximum concurrent streams ({self._max_concurrent_streams}) reached")
                
                # Create streaming session
                session = StreamingSession(stream_id, prompt, config)
                self._active_streams[stream_id] = session
                self._stream_locks[stream_id] = threading.RLock()
                
                # Start generation in background
                self._executor.submit(self._generate_streaming, stream_id, prompt, config, context_id)
                
                self._logger.info(f"Started streaming session {stream_id}")
                return stream_id
                
        except Exception as e:
            self._logger.error(f"Failed to start streaming: {str(e)}")
            raise StreamingError(f"Failed to start streaming: {str(e)}")
    
    async def get_stream_chunk(self, stream_id: str) -> Optional[StreamingChunk]:
        """
        Get the next chunk from a stream.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            StreamingChunk if available, None if stream ended
        """
        try:
            if stream_id not in self._active_streams:
                raise StreamNotFoundError(f"Stream {stream_id} not found")
            
            session = self._active_streams[stream_id]
            
            with session.lock:
                # Check for errors
                if session.error:
                    raise StreamingError(f"Stream error: {session.error}")
                
                # Get chunk from buffer
                if session.chunks:
                    chunk = session.chunks.popleft()
                    session.last_activity = time.time()
                    return chunk
                
                # Check if stream is complete
                if session.is_complete:
                    return None
                
                # No chunks available yet
                return None
                
        except StreamNotFoundError:
            raise
        except Exception as e:
            self._logger.error(f"Failed to get stream chunk {stream_id}: {str(e)}")
            return None
    
    async def stream_response(self, prompt: str, context_id: Optional[str] = None,
                            config: Optional[StreamingConfig] = None) -> AsyncIterator[StreamingChunk]:
        """
        Stream text generation as an async iterator.
        
        Args:
            prompt: Input prompt
            context_id: Optional context identifier
            config: Optional streaming configuration
            
        Yields:
            StreamingChunk objects
        """
        stream_id = await self.start_streaming(prompt, context_id, config)
        
        try:
            while True:
                chunk = await self.get_stream_chunk(stream_id)
                
                if chunk is None:
                    # Check if stream is complete
                    session = self._active_streams.get(stream_id)
                    if session and session.is_complete:
                        break
                    
                    # Wait a bit before checking again
                    await asyncio.sleep(0.01)
                    continue
                
                yield chunk
                
                # Break if this is the final chunk
                if chunk.is_final:
                    break
                    
        finally:
            # Clean up stream
            await self.stop_streaming(stream_id)
    
    async def stop_streaming(self, stream_id: str) -> bool:
        """
        Stop a streaming session.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            True if stream stopped successfully
        """
        try:
            with self._global_lock:
                if stream_id not in self._active_streams:
                    self._logger.warning(f"Stream {stream_id} not found for stopping")
                    return False
                
                session = self._active_streams[stream_id]
                
                with session.lock:
                    session.is_active = False
                    session.is_complete = True
                
                # Clean up
                del self._active_streams[stream_id]
                if stream_id in self._stream_locks:
                    del self._stream_locks[stream_id]
                
                self._logger.info(f"Stopped streaming session {stream_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to stop streaming {stream_id}: {str(e)}")
            return False
    
    def get_active_streams(self) -> List[str]:
        """
        Get list of active stream identifiers.
        
        Returns:
            List of active stream IDs
        """
        try:
            with self._global_lock:
                # Cleanup expired streams
                self._cleanup_expired_streams()
                return list(self._active_streams.keys())
                
        except Exception as e:
            self._logger.error(f"Failed to get active streams: {str(e)}")
            return []
    
    def _generate_streaming(self, stream_id: str, prompt: str, config: StreamingConfig, 
                          context_id: Optional[str] = None) -> None:
        """
        Generate streaming response in background thread.
        
        Args:
            stream_id: Stream identifier
            prompt: Input prompt
            config: Streaming configuration
            context_id: Optional context identifier
        """
        try:
            session = self._active_streams[stream_id]
            
            # Tokenize input
            inputs = self._tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self._tokenizer_info.max_length if self._tokenizer_info else 512
            )
            
            # Move to device
            if TORCH_AVAILABLE:
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Create streamer
            if TRANSFORMERS_AVAILABLE and config.mode == StreamingMode.TOKEN_BY_TOKEN:
                streamer = TextIteratorStreamer(
                    self._tokenizer,
                    skip_prompt=True,
                    skip_special_tokens=True
                )
            else:
                streamer = None
            
            # Prepare generation config
            generation_config = HFGenerationConfig(
                max_new_tokens=512,
                temperature=1.0,
                do_sample=True,
                pad_token_id=self._tokenizer.pad_token_id
            )
            
            # Start generation
            generation_kwargs = {
                **inputs,
                "generation_config": generation_config,
                "streamer": streamer
            }
            
            if streamer:
                # Use streamer for token-by-token streaming
                generation_thread = threading.Thread(
                    target=self._model.generate,
                    kwargs=generation_kwargs
                )
                generation_thread.start()
                
                # Process streamed tokens
                chunk_id = 0
                cumulative_text = ""
                start_time = time.time()
                
                for new_text in streamer:
                    if not session.is_active:
                        break
                    
                    cumulative_text += new_text
                    chunk_id += 1
                    
                    # Create chunk
                    chunk = StreamingChunk(
                        chunk_id=f"{stream_id}_{chunk_id}",
                        text=new_text,
                        is_final=False,
                        token_count=1,  # Approximate
                        cumulative_tokens=chunk_id,
                        generation_time_ms=(time.time() - start_time) * 1000,
                        metadata={
                            'stream_id': stream_id,
                            'mode': config.mode.value
                        }
                    )
                    
                    # Add to buffer
                    with session.lock:
                        session.chunks.append(chunk)
                        session.total_tokens += 1
                
                generation_thread.join()
                
                # Add final chunk
                if session.is_active:
                    final_chunk = StreamingChunk(
                        chunk_id=f"{stream_id}_final",
                        text="",
                        is_final=True,
                        token_count=0,
                        cumulative_tokens=session.total_tokens,
                        generation_time_ms=(time.time() - start_time) * 1000,
                        metadata={
                            'stream_id': stream_id,
                            'total_generation_time': time.time() - start_time,
                            'total_tokens': session.total_tokens
                        }
                    )
                    
                    with session.lock:
                        session.chunks.append(final_chunk)
                        session.is_complete = True
            
            else:
                # Fallback: generate complete response and chunk it
                with torch.no_grad():
                    outputs = self._model.generate(**generation_kwargs)
                
                # Decode and chunk the response
                generated_tokens = outputs[0][inputs['input_ids'].shape[1]:]
                generated_text = self._tokenizer.decode(generated_tokens, skip_special_tokens=True)
                
                # Create chunks based on mode
                chunks = self._create_chunks(generated_text, config, stream_id)
                
                # Add chunks to buffer
                with session.lock:
                    for chunk in chunks:
                        session.chunks.append(chunk)
                    session.is_complete = True
                    session.total_tokens = len(generated_tokens)
            
        except Exception as e:
            self._logger.error(f"Streaming generation failed for {stream_id}: {str(e)}")
            session.error = str(e)
            session.is_complete = True

    def _create_chunks(self, text: str, config: StreamingConfig, stream_id: str) -> List[StreamingChunk]:
        """
        Create chunks from generated text based on streaming mode.

        Args:
            text: Generated text
            config: Streaming configuration
            stream_id: Stream identifier

        Returns:
            List of StreamingChunk objects
        """
        chunks = []

        try:
            if config.mode == StreamingMode.CHUNK_BASED:
                # Split by chunk size
                chunk_size = config.chunk_size
                for i in range(0, len(text), chunk_size):
                    chunk_text = text[i:i + chunk_size]
                    is_final = (i + chunk_size) >= len(text)

                    chunk = StreamingChunk(
                        chunk_id=f"{stream_id}_{i // chunk_size}",
                        text=chunk_text,
                        is_final=is_final,
                        token_count=len(chunk_text.split()),
                        cumulative_tokens=len(text[:i + len(chunk_text)].split()),
                        generation_time_ms=0.0,
                        metadata={'mode': config.mode.value}
                    )
                    chunks.append(chunk)

            elif config.mode == StreamingMode.SENTENCE_BASED:
                # Split by sentences
                sentences = text.split('. ')
                for i, sentence in enumerate(sentences):
                    if sentence and not sentence.endswith('.') and i < len(sentences) - 1:
                        sentence += '.'

                    is_final = (i == len(sentences) - 1)

                    chunk = StreamingChunk(
                        chunk_id=f"{stream_id}_sent_{i}",
                        text=sentence,
                        is_final=is_final,
                        token_count=len(sentence.split()),
                        cumulative_tokens=len(' '.join(sentences[:i+1]).split()),
                        generation_time_ms=0.0,
                        metadata={'mode': config.mode.value}
                    )
                    chunks.append(chunk)

            else:
                # Return as single chunk
                chunk = StreamingChunk(
                    chunk_id=f"{stream_id}_0",
                    text=text,
                    is_final=True,
                    token_count=len(text.split()),
                    cumulative_tokens=len(text.split()),
                    generation_time_ms=0.0,
                    metadata={'mode': config.mode.value}
                )
                chunks.append(chunk)

        except Exception as e:
            self._logger.error(f"Failed to create chunks: {str(e)}")
            # Return single chunk as fallback
            chunk = StreamingChunk(
                chunk_id=f"{stream_id}_error",
                text=text,
                is_final=True,
                token_count=len(text.split()),
                cumulative_tokens=len(text.split()),
                generation_time_ms=0.0,
                metadata={'mode': 'error', 'error': str(e)}
            )
            chunks.append(chunk)

        return chunks

    def _validate_streaming_inputs(self, prompt: str, config: Optional[StreamingConfig]) -> ValidationResult:
        """
        Validate streaming inputs.

        Args:
            prompt: Input prompt
            config: Optional streaming configuration

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate prompt
            if not prompt or not prompt.strip():
                result.add_error(ValidationError(
                    field_name="prompt",
                    error_message="Prompt cannot be empty",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.REQUIRED
                ))

            # Validate config if provided
            if config:
                if config.chunk_size <= 0:
                    result.add_error(ValidationError(
                        field_name="chunk_size",
                        error_message="Chunk size must be positive",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RANGE
                    ))

                if config.buffer_size <= 0:
                    result.add_error(ValidationError(
                        field_name="buffer_size",
                        error_message="Buffer size must be positive",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RANGE
                    ))

                if config.timeout_seconds <= 0:
                    result.add_error(ValidationError(
                        field_name="timeout_seconds",
                        error_message="Timeout must be positive",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RANGE
                    ))

        except Exception as e:
            result.add_error(ValidationError(
                field_name="general",
                error_message=f"Validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CUSTOM
            ))

        return result

    def _cleanup_expired_streams(self) -> None:
        """Clean up expired streaming sessions."""
        try:
            current_time = time.time()

            # Only run cleanup periodically
            if current_time - self._last_cleanup < self._cleanup_interval:
                return

            expired_streams = []

            for stream_id, session in self._active_streams.items():
                # Check for timeout
                if current_time - session.last_activity > self._stream_timeout:
                    expired_streams.append(stream_id)
                # Check for completed but not cleaned up streams
                elif session.is_complete and current_time - session.last_activity > 60:
                    expired_streams.append(stream_id)

            # Remove expired streams
            for stream_id in expired_streams:
                try:
                    del self._active_streams[stream_id]
                    if stream_id in self._stream_locks:
                        del self._stream_locks[stream_id]
                except KeyError:
                    pass  # Already removed

            if expired_streams:
                self._logger.info(f"Cleaned up {len(expired_streams)} expired streams")

            self._last_cleanup = current_time

        except Exception as e:
            self._logger.error(f"Failed to cleanup expired streams: {str(e)}")

    def get_metrics(self) -> InferenceMetrics:
        """
        Get streaming handler metrics.

        Returns:
            InferenceMetrics with current statistics
        """
        try:
            with self._global_lock:
                active_count = len(self._active_streams)
                total_tokens = sum(session.total_tokens for session in self._active_streams.values())

                self._metrics.metadata = {
                    'active_streams': active_count,
                    'max_concurrent_streams': self._max_concurrent_streams,
                    'total_tokens_streamed': total_tokens,
                    'model_loaded': self._model is not None,
                    'tokenizer_loaded': self._tokenizer is not None,
                    'device': self._device
                }

                return self._metrics

        except Exception as e:
            self._logger.error(f"Failed to get metrics: {str(e)}")
            return InferenceMetrics()

    async def shutdown(self) -> bool:
        """
        Shutdown streaming handler and cleanup resources.

        Returns:
            True if shutdown successful
        """
        try:
            # Stop all active streams
            stream_ids = list(self._active_streams.keys())
            for stream_id in stream_ids:
                await self.stop_streaming(stream_id)

            # Shutdown executor
            self._executor.shutdown(wait=True)

            # Clear references
            self._model = None
            self._tokenizer = None
            self._active_streams.clear()
            self._stream_locks.clear()

            self._logger.info("Streaming handler shutdown completed")
            return True

        except Exception as e:
            self._logger.error(f"Failed to shutdown streaming handler: {str(e)}")
            return False
