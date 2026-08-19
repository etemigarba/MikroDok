"""
Module: response_generator_lg
Description: Generates text responses using loaded models with proper error handling and performance optimization
Phase: 4
Location: /src/modules/logic/inference_engine_lg/response_generator_lg/response_generator_lg.py
"""

# Standard library imports
import asyncio
import time
import threading
import uuid
from typing import Dict, Any, Optional, List, Union
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import asdict

# Third-party imports
try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import (
        AutoModelForCausalLM, 
        AutoTokenizer, 
        GenerationConfig as HFGenerationConfig,
        StoppingCriteria,
        StoppingCriteriaList
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Local imports
from src.modules.logic.inference_engine_lg.base_interfaces import (
    IResponseGenerator,
    GenerationConfig,
    GenerationResult,
    InferenceStatus,
    ModelInfo,
    TokenizerInfo,
    InferenceMetrics,
    ModelType,
    TokenizerType
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)


class GenerationError(Exception):
    """Exception raised when text generation fails."""
    pass


class ModelNotLoadedError(Exception):
    """Exception raised when attempting generation without a loaded model."""
    pass


class CustomStoppingCriteria(StoppingCriteria):
    """Custom stopping criteria for text generation."""
    
    def __init__(self, stop_tokens: List[str], tokenizer):
        self.stop_tokens = stop_tokens
        self.tokenizer = tokenizer
        self.stop_token_ids = [tokenizer.encode(token, add_special_tokens=False) for token in stop_tokens]
    
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        # Check if any stop token appears at the end of generated sequence
        for stop_ids in self.stop_token_ids:
            if len(stop_ids) > 0:
                # Check if the last tokens match any stop sequence
                if input_ids[0, -len(stop_ids):].tolist() == stop_ids:
                    return True
        return False


class ResponseGenerator(IResponseGenerator):
    """
    Production-ready response generator for text generation.
    
    Supports multiple model formats, generation strategies, and optimization
    techniques with comprehensive error handling and performance monitoring.
    """
    
    def __init__(self, model_info: Optional[ModelInfo] = None, 
                 tokenizer_info: Optional[TokenizerInfo] = None):
        """Initialize response generator with optional model and tokenizer info."""
        self._logger = get_log_manager().get_logger(__name__)
        self._model_info = model_info
        self._tokenizer_info = tokenizer_info
        self._model = None
        self._tokenizer = None
        self._device = "cpu"
        self._generation_lock = threading.RLock()
        self._active_requests: Dict[str, Future] = {}
        self._request_status: Dict[str, InferenceStatus] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="response_gen")
        self._validator = ValidationEngine()
        self._metrics = InferenceMetrics()
        
        # Performance optimization settings
        self._use_cache = True
        self._enable_attention_optimization = True
        self._batch_size = 1
        
        self._logger.info("Response generator initialized")
    
    def set_model_and_tokenizer(self, model: Any, tokenizer: Any, device: str = "cpu") -> None:
        """
        Set the model and tokenizer for generation.
        
        Args:
            model: Loaded model instance
            tokenizer: Loaded tokenizer instance
            device: Device to use for generation
        """
        try:
            self._model = model
            self._tokenizer = tokenizer
            self._device = device
            
            # Update model info if available
            if hasattr(model, 'config'):
                self._model_info = ModelInfo(
                    model_name=getattr(model.config, 'name_or_path', 'unknown'),
                    model_type=getattr(model.config, 'model_type', 'unknown'),
                    model_format='huggingface',
                    vocab_size=getattr(model.config, 'vocab_size', 0),
                    max_position_embeddings=getattr(model.config, 'max_position_embeddings', 0),
                    hidden_size=getattr(model.config, 'hidden_size', 0),
                    num_layers=getattr(model.config, 'num_hidden_layers', 0),
                    num_attention_heads=getattr(model.config, 'num_attention_heads', 0),
                    device=device,
                    precision='float32',
                    memory_usage_mb=0.0,
                    parameters_count=sum(p.numel() for p in model.parameters()),
                    is_loaded=True
                )
            
            # Update tokenizer info
            if hasattr(tokenizer, 'vocab_size'):
                self._tokenizer_info = TokenizerInfo(
                    tokenizer_name=getattr(tokenizer, 'name_or_path', 'unknown'),
                    tokenizer_type='huggingface',
                    vocab_size=tokenizer.vocab_size,
                    max_length=getattr(tokenizer, 'model_max_length', 512),
                    special_tokens={
                        'pad_token': tokenizer.pad_token_id,
                        'eos_token': tokenizer.eos_token_id,
                        'bos_token': tokenizer.bos_token_id,
                        'unk_token': tokenizer.unk_token_id
                    },
                    is_fast=getattr(tokenizer, 'is_fast', False),
                    supports_batching=True,
                    is_loaded=True
                )
            
            self._logger.info(f"Model and tokenizer set for device: {device}")
            
        except Exception as e:
            self._logger.error(f"Failed to set model and tokenizer: {str(e)}")
            raise
    
    async def generate_response(self, prompt: str, context_id: Optional[str] = None,
                              config: Optional[GenerationConfig] = None) -> GenerationResult:
        """
        Generate a text response for the given prompt.
        
        Args:
            prompt: Input prompt
            context_id: Optional context identifier
            config: Optional generation configuration
            
        Returns:
            GenerationResult with generated text and metadata
        """
        if not self._model or not self._tokenizer:
            raise ModelNotLoadedError("Model and tokenizer must be loaded before generation")
        
        # Validate inputs
        validation_result = self._validate_generation_inputs(prompt, config)
        if not validation_result.is_valid:
            error_msg = f"Invalid generation inputs: {validation_result.get_error_summary()}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
        
        request_id = str(uuid.uuid4())
        config = config or GenerationConfig()
        
        try:
            # Update request status
            self._request_status[request_id] = InferenceStatus.GENERATING
            
            # Submit generation task to executor
            future = self._executor.submit(self._generate_sync, prompt, config, request_id)
            self._active_requests[request_id] = future
            
            # Wait for completion
            result = await asyncio.wrap_future(future)
            
            # Update metrics
            self._metrics.total_requests += 1
            self._metrics.successful_requests += 1
            self._metrics.total_tokens_generated += result.output_tokens
            
            # Clean up
            self._request_status[request_id] = InferenceStatus.COMPLETED
            if request_id in self._active_requests:
                del self._active_requests[request_id]
            
            return result
            
        except Exception as e:
            self._metrics.total_requests += 1
            self._metrics.failed_requests += 1
            self._request_status[request_id] = InferenceStatus.FAILED
            
            if request_id in self._active_requests:
                del self._active_requests[request_id]
            
            self._logger.error(f"Generation failed for request {request_id}: {str(e)}")
            raise GenerationError(f"Text generation failed: {str(e)}")
    
    async def generate_response_batch(self, prompts: List[str], 
                                    context_ids: Optional[List[str]] = None,
                                    config: Optional[GenerationConfig] = None) -> List[GenerationResult]:
        """
        Generate responses for multiple prompts.
        
        Args:
            prompts: List of input prompts
            context_ids: Optional list of context identifiers
            config: Optional generation configuration
            
        Returns:
            List of GenerationResult objects
        """
        if not prompts:
            return []
        
        # Generate responses concurrently
        tasks = []
        for i, prompt in enumerate(prompts):
            context_id = context_ids[i] if context_ids and i < len(context_ids) else None
            task = self.generate_response(prompt, context_id, config)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions in results
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self._logger.error(f"Batch generation failed for prompt {i}: {str(result)}")
                    # Create error result
                    error_result = GenerationResult(
                        generated_text="",
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        generation_time_seconds=0.0,
                        tokens_per_second=0.0,
                        finish_reason="error",
                        metadata={"error": str(result)}
                    )
                    final_results.append(error_result)
                else:
                    final_results.append(result)
            
            return final_results
            
        except Exception as e:
            self._logger.error(f"Batch generation failed: {str(e)}")
            raise GenerationError(f"Batch generation failed: {str(e)}")
    
    async def cancel_generation(self, request_id: str) -> bool:
        """
        Cancel an ongoing generation request.
        
        Args:
            request_id: Generation request identifier
            
        Returns:
            True if cancellation successful
        """
        try:
            if request_id in self._active_requests:
                future = self._active_requests[request_id]
                cancelled = future.cancel()
                
                if cancelled:
                    self._request_status[request_id] = InferenceStatus.CANCELLED
                    del self._active_requests[request_id]
                    self._logger.info(f"Cancelled generation request {request_id}")
                    return True
                else:
                    self._logger.warning(f"Could not cancel request {request_id} (already running)")
                    return False
            else:
                self._logger.warning(f"Request {request_id} not found for cancellation")
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to cancel request {request_id}: {str(e)}")
            return False
    
    def get_generation_status(self, request_id: str) -> InferenceStatus:
        """
        Get status of a generation request.

        Args:
            request_id: Generation request identifier

        Returns:
            Current status of the request
        """
        return self._request_status.get(request_id, InferenceStatus.IDLE)

    def _generate_sync(self, prompt: str, config: GenerationConfig, request_id: str) -> GenerationResult:
        """
        Synchronous text generation implementation.

        Args:
            prompt: Input prompt
            config: Generation configuration
            request_id: Request identifier

        Returns:
            GenerationResult with generated text and metadata
        """
        start_time = time.time()

        try:
            with self._generation_lock:
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

                input_tokens = inputs['input_ids'].shape[1]

                # Prepare generation config
                generation_config = self._prepare_generation_config(config)

                # Prepare stopping criteria
                stopping_criteria = self._prepare_stopping_criteria(config)

                # Generate response
                with torch.no_grad():
                    outputs = self._model.generate(
                        **inputs,
                        generation_config=generation_config,
                        stopping_criteria=stopping_criteria,
                        pad_token_id=self._tokenizer.pad_token_id,
                        do_sample=config.do_sample,
                        use_cache=self._use_cache
                    )

                # Decode output
                generated_tokens = outputs[0][input_tokens:]  # Remove input tokens
                generated_text = self._tokenizer.decode(generated_tokens, skip_special_tokens=True)

                # Calculate metrics
                generation_time = time.time() - start_time
                output_tokens = len(generated_tokens)
                total_tokens = input_tokens + output_tokens
                tokens_per_second = output_tokens / generation_time if generation_time > 0 else 0

                # Determine finish reason
                finish_reason = self._determine_finish_reason(outputs, config)

                return GenerationResult(
                    generated_text=generated_text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    generation_time_seconds=generation_time,
                    tokens_per_second=tokens_per_second,
                    finish_reason=finish_reason,
                    metadata={
                        'request_id': request_id,
                        'model_name': self._model_info.model_name if self._model_info else 'unknown',
                        'device': self._device,
                        'config': asdict(config)
                    }
                )

        except Exception as e:
            self._logger.error(f"Synchronous generation failed: {str(e)}")
            raise

    def _prepare_generation_config(self, config: GenerationConfig) -> HFGenerationConfig:
        """
        Prepare HuggingFace generation configuration.

        Args:
            config: Internal generation configuration

        Returns:
            HuggingFace GenerationConfig object
        """
        try:
            if not TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers library not available")

            hf_config = HFGenerationConfig(
                max_new_tokens=config.max_new_tokens,
                min_new_tokens=config.min_new_tokens,
                temperature=config.temperature,
                top_k=config.top_k,
                top_p=config.top_p,
                repetition_penalty=config.repetition_penalty,
                length_penalty=config.length_penalty,
                num_beams=config.num_beams,
                num_return_sequences=config.num_return_sequences,
                early_stopping=config.early_stopping,
                do_sample=config.do_sample,
                use_cache=config.use_cache,
                output_scores=config.output_scores,
                return_dict_in_generate=config.return_dict_in_generate
            )

            # Set token IDs if available
            if config.pad_token_id is not None:
                hf_config.pad_token_id = config.pad_token_id
            if config.eos_token_id is not None:
                hf_config.eos_token_id = config.eos_token_id
            if config.bos_token_id is not None:
                hf_config.bos_token_id = config.bos_token_id

            return hf_config

        except Exception as e:
            self._logger.error(f"Failed to prepare generation config: {str(e)}")
            raise

    def _prepare_stopping_criteria(self, config: GenerationConfig) -> Optional[StoppingCriteriaList]:
        """
        Prepare stopping criteria for generation.

        Args:
            config: Generation configuration

        Returns:
            StoppingCriteriaList if custom criteria specified, None otherwise
        """
        try:
            if not config.custom_stopping_criteria or not TRANSFORMERS_AVAILABLE:
                return None

            criteria_list = []

            # Add custom stopping criteria
            if config.custom_stopping_criteria:
                custom_criteria = CustomStoppingCriteria(
                    config.custom_stopping_criteria,
                    self._tokenizer
                )
                criteria_list.append(custom_criteria)

            return StoppingCriteriaList(criteria_list) if criteria_list else None

        except Exception as e:
            self._logger.error(f"Failed to prepare stopping criteria: {str(e)}")
            return None

    def _determine_finish_reason(self, outputs: torch.Tensor, config: GenerationConfig) -> str:
        """
        Determine the reason generation finished.

        Args:
            outputs: Generated token tensor
            config: Generation configuration

        Returns:
            Finish reason string
        """
        try:
            # Check if we hit max tokens
            if outputs.shape[1] >= config.max_new_tokens:
                return "length"

            # Check if we hit EOS token
            if config.eos_token_id is not None:
                if config.eos_token_id in outputs[0]:
                    return "stop"

            # Check for custom stopping criteria
            if config.custom_stopping_criteria:
                return "stop"

            return "complete"

        except Exception as e:
            self._logger.error(f"Failed to determine finish reason: {str(e)}")
            return "unknown"

    def _validate_generation_inputs(self, prompt: str, config: Optional[GenerationConfig]) -> ValidationResult:
        """
        Validate generation inputs.

        Args:
            prompt: Input prompt
            config: Optional generation configuration

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
                if config.max_new_tokens <= 0:
                    result.add_error(ValidationError(
                        field_name="max_new_tokens",
                        error_message="Max new tokens must be positive",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RANGE
                    ))

                if config.temperature <= 0:
                    result.add_error(ValidationError(
                        field_name="temperature",
                        error_message="Temperature must be positive",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RANGE
                    ))

                if config.top_p <= 0 or config.top_p > 1:
                    result.add_error(ValidationError(
                        field_name="top_p",
                        error_message="Top-p must be between 0 and 1",
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

    def get_metrics(self) -> InferenceMetrics:
        """
        Get response generator metrics.

        Returns:
            InferenceMetrics with current statistics
        """
        try:
            self._metrics.metadata = {
                'active_requests': len(self._active_requests),
                'model_loaded': self._model is not None,
                'tokenizer_loaded': self._tokenizer is not None,
                'device': self._device
            }

            # Calculate error rate
            if self._metrics.total_requests > 0:
                self._metrics.error_rate = self._metrics.failed_requests / self._metrics.total_requests

            return self._metrics

        except Exception as e:
            self._logger.error(f"Failed to get metrics: {str(e)}")
            return InferenceMetrics()

    async def shutdown(self) -> bool:
        """
        Shutdown response generator and cleanup resources.

        Returns:
            True if shutdown successful
        """
        try:
            # Cancel all active requests
            for request_id in list(self._active_requests.keys()):
                await self.cancel_generation(request_id)

            # Shutdown executor
            self._executor.shutdown(wait=True)

            # Clear references
            self._model = None
            self._tokenizer = None
            self._active_requests.clear()
            self._request_status.clear()

            self._logger.info("Response generator shutdown completed")
            return True

        except Exception as e:
            self._logger.error(f"Failed to shutdown response generator: {str(e)}")
            return False
