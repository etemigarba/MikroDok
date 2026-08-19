"""
Module: model_loader_lg
Description: Loads and manages language models with support for different formats and memory optimization
Phase: 4
Location: /src/modules/logic/inference_engine_lg/model_loader_lg/model_loader_lg.py
"""

# Standard library imports
import asyncio
import gc
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import logging
import psutil

# Third-party imports
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoModel,
        AutoConfig,
        BitsAndBytesConfig
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

# Local imports
from src.modules.logic.inference_engine_lg.base_interfaces import (
    IModelLoader,
    ModelConfig,
    ModelInfo,
    ModelType,
    ModelFormat,
    InferenceMetrics
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)


class ModelLoadingError(Exception):
    """Exception raised when model loading fails."""
    pass


class UnsupportedModelFormatError(Exception):
    """Exception raised when model format is not supported."""
    pass


class InsufficientMemoryError(Exception):
    """Exception raised when insufficient memory for model loading."""
    pass


class ModelLoader(IModelLoader):
    """
    Production-ready model loader for language models.
    
    Supports multiple model formats (PyTorch, HuggingFace, ONNX, SafeTensors)
    with memory optimization, device management, and comprehensive error handling.
    """
    
    def __init__(self):
        """Initialize model loader."""
        self._logger = get_log_manager().get_logger(__name__)
        self._model = None
        self._model_info: Optional[ModelInfo] = None
        self._config: Optional[ModelConfig] = None
        self._loading_lock = threading.RLock()
        self._validator = ValidationEngine()
        self._metrics = InferenceMetrics()
        
        # Memory management
        self._memory_monitor = psutil.Process()
        self._initial_memory = self._memory_monitor.memory_info().rss / 1024 / 1024  # MB
        
        # Device management
        self._available_devices = self._detect_available_devices()
        self._current_device = "cpu"
        
        self._logger.info(f"Model loader initialized with devices: {self._available_devices}")
    
    async def load_model(self, config: ModelConfig) -> bool:
        """
        Load a model with the specified configuration.
        
        Args:
            config: Model configuration
            
        Returns:
            True if model loaded successfully
        """
        # Validate configuration
        validation_result = self._validate_model_config(config)
        if not validation_result.is_valid:
            error_msg = f"Invalid model configuration: {validation_result.get_error_summary()}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate model file exists
        if not await self.validate_model(config.model_path):
            raise ModelLoadingError(f"Model validation failed: {config.model_path}")
        
        with self._loading_lock:
            try:
                # Unload existing model if any
                if self._model is not None:
                    await self.unload_model()
                
                self._logger.info(f"Loading model from {config.model_path}")
                start_time = time.time()
                
                # Check memory requirements
                await self._check_memory_requirements(config)
                
                # Load model based on format
                if config.model_format == ModelFormat.HUGGINGFACE:
                    model = await self._load_huggingface_model(config)
                elif config.model_format == ModelFormat.PYTORCH:
                    model = await self._load_pytorch_model(config)
                elif config.model_format == ModelFormat.ONNX:
                    model = await self._load_onnx_model(config)
                elif config.model_format == ModelFormat.SAFETENSORS:
                    model = await self._load_safetensors_model(config)
                else:
                    raise UnsupportedModelFormatError(f"Unsupported model format: {config.model_format}")
                
                # Move to specified device
                if config.device != "cpu" and TORCH_AVAILABLE:
                    model = model.to(config.device)
                
                # Create model info
                load_time = time.time() - start_time
                current_memory = self._memory_monitor.memory_info().rss / 1024 / 1024
                memory_usage = current_memory - self._initial_memory
                
                self._model = model
                self._config = config
                self._current_device = config.device
                
                # Create model info
                self._model_info = await self._create_model_info(model, config, load_time, memory_usage)
                
                self._logger.info(f"Model loaded successfully in {load_time:.2f}s, "
                                f"using {memory_usage:.1f}MB memory")
                
                # Update metrics
                self._metrics.memory_usage_mb = memory_usage
                self._metrics.successful_requests += 1
                
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to load model: {str(e)}")
                self._metrics.failed_requests += 1
                
                # Clean up on failure
                self._model = None
                self._model_info = None
                self._config = None
                
                if isinstance(e, (ModelLoadingError, UnsupportedModelFormatError, InsufficientMemoryError)):
                    raise
                else:
                    raise ModelLoadingError(f"Model loading failed: {str(e)}")
    
    async def unload_model(self) -> bool:
        """
        Unload the currently loaded model.
        
        Returns:
            True if model unloaded successfully
        """
        with self._loading_lock:
            try:
                if self._model is None:
                    self._logger.warning("No model to unload")
                    return True
                
                self._logger.info("Unloading model")
                
                # Clear model reference
                self._model = None
                self._model_info = None
                self._config = None
                
                # Force garbage collection
                if TORCH_AVAILABLE:
                    torch.cuda.empty_cache() if torch.cuda.is_available() else None
                gc.collect()
                
                # Update memory metrics
                current_memory = self._memory_monitor.memory_info().rss / 1024 / 1024
                self._metrics.memory_usage_mb = current_memory - self._initial_memory
                
                self._logger.info("Model unloaded successfully")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to unload model: {str(e)}")
                return False
    
    def get_model_info(self) -> Optional[ModelInfo]:
        """
        Get information about the currently loaded model.
        
        Returns:
            ModelInfo if model is loaded, None otherwise
        """
        return self._model_info
    
    def is_model_loaded(self) -> bool:
        """
        Check if a model is currently loaded.
        
        Returns:
            True if model is loaded
        """
        return self._model is not None
    
    async def validate_model(self, model_path: Path) -> bool:
        """
        Validate a model file before loading.
        
        Args:
            model_path: Path to model file
            
        Returns:
            True if model is valid
        """
        try:
            # Check if path exists
            if not model_path.exists():
                self._logger.error(f"Model path does not exist: {model_path}")
                return False
            
            # Check if it's a file or directory
            if model_path.is_file():
                # Single file model
                if not model_path.suffix in ['.pt', '.pth', '.bin', '.onnx', '.safetensors']:
                    self._logger.error(f"Unsupported model file extension: {model_path.suffix}")
                    return False
                
                # Check file size (basic validation)
                file_size = model_path.stat().st_size
                if file_size < 1024:  # Less than 1KB is suspicious
                    self._logger.error(f"Model file too small: {file_size} bytes")
                    return False
                    
            elif model_path.is_dir():
                # Directory-based model (HuggingFace format)
                config_file = model_path / "config.json"
                if not config_file.exists():
                    self._logger.error(f"No config.json found in model directory: {model_path}")
                    return False
                
                # Check for model files
                model_files = list(model_path.glob("*.bin")) + list(model_path.glob("*.safetensors"))
                if not model_files:
                    self._logger.error(f"No model files found in directory: {model_path}")
                    return False
            
            else:
                self._logger.error(f"Model path is neither file nor directory: {model_path}")
                return False
            
            self._logger.debug(f"Model validation passed: {model_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Model validation failed: {str(e)}")
            return False
    
    def get_model(self) -> Optional[Any]:
        """
        Get the currently loaded model instance.
        
        Returns:
            Model instance if loaded, None otherwise
        """
        return self._model
    
    def get_device(self) -> str:
        """
        Get the current device.
        
        Returns:
            Current device string
        """
        return self._current_device
    
    def get_available_devices(self) -> List[str]:
        """
        Get list of available devices.
        
        Returns:
            List of available device strings
        """
        return self._available_devices.copy()
    
    def _detect_available_devices(self) -> List[str]:
        """
        Detect available devices for model loading.
        
        Returns:
            List of available devices
        """
        devices = ["cpu"]
        
        try:
            if TORCH_AVAILABLE and torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    devices.append(f"cuda:{i}")
                devices.append("cuda")  # Default CUDA device
            
            # Check for MPS (Apple Silicon)
            if TORCH_AVAILABLE and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                devices.append("mps")
                
        except Exception as e:
            self._logger.warning(f"Error detecting devices: {str(e)}")
        
        return devices

    async def _check_memory_requirements(self, config: ModelConfig) -> None:
        """
        Check if sufficient memory is available for model loading.

        Args:
            config: Model configuration

        Raises:
            InsufficientMemoryError: If insufficient memory available
        """
        try:
            # Get current memory usage
            memory_info = psutil.virtual_memory()
            available_memory_gb = memory_info.available / (1024 ** 3)

            # Estimate model memory requirements (rough approximation)
            if config.model_path.is_file():
                model_size_gb = config.model_path.stat().st_size / (1024 ** 3)
            else:
                # For directory-based models, sum all model files
                model_files = list(config.model_path.glob("*.bin")) + list(config.model_path.glob("*.safetensors"))
                total_size = sum(f.stat().st_size for f in model_files)
                model_size_gb = total_size / (1024 ** 3)

            # Add overhead for loading (typically 2-3x model size)
            estimated_memory_gb = model_size_gb * 2.5

            # Check against configured limit
            if config.max_memory_gb and estimated_memory_gb > config.max_memory_gb:
                raise InsufficientMemoryError(
                    f"Estimated memory requirement ({estimated_memory_gb:.1f}GB) "
                    f"exceeds configured limit ({config.max_memory_gb}GB)"
                )

            # Check against available system memory
            if estimated_memory_gb > available_memory_gb:
                raise InsufficientMemoryError(
                    f"Estimated memory requirement ({estimated_memory_gb:.1f}GB) "
                    f"exceeds available memory ({available_memory_gb:.1f}GB)"
                )

            self._logger.info(f"Memory check passed: estimated {estimated_memory_gb:.1f}GB, "
                            f"available {available_memory_gb:.1f}GB")

        except InsufficientMemoryError:
            raise
        except Exception as e:
            self._logger.warning(f"Memory check failed: {str(e)}")

    async def _load_huggingface_model(self, config: ModelConfig) -> Any:
        """
        Load HuggingFace model.

        Args:
            config: Model configuration

        Returns:
            Loaded model instance
        """
        try:
            if not TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers library not available")

            # Prepare loading arguments
            load_kwargs = {
                "pretrained_model_name_or_path": str(config.model_path),
                "trust_remote_code": config.trust_remote_code,
                "low_cpu_mem_usage": config.low_cpu_mem_usage,
                "cache_dir": str(config.cache_dir) if config.cache_dir else None,
                "revision": config.revision,
                "use_auth_token": config.use_auth_token
            }

            # Add device map if specified
            if config.device_map:
                load_kwargs["device_map"] = config.device_map

            # Add torch dtype if specified
            if config.torch_dtype:
                if TORCH_AVAILABLE:
                    dtype_map = {
                        "float32": torch.float32,
                        "float16": torch.float16,
                        "bfloat16": torch.bfloat16
                    }
                    if config.torch_dtype in dtype_map:
                        load_kwargs["torch_dtype"] = dtype_map[config.torch_dtype]

            # Handle quantization for memory optimization
            if config.precision in ["int8", "int4"]:
                if TORCH_AVAILABLE:
                    quantization_config = BitsAndBytesConfig(
                        load_in_8bit=(config.precision == "int8"),
                        load_in_4bit=(config.precision == "int4")
                    )
                    load_kwargs["quantization_config"] = quantization_config

            # Load model based on type
            if config.model_type == ModelType.CAUSAL_LM:
                model = AutoModelForCausalLM.from_pretrained(**load_kwargs)
            else:
                model = AutoModel.from_pretrained(**load_kwargs)

            return model

        except Exception as e:
            self._logger.error(f"Failed to load HuggingFace model: {str(e)}")
            raise ModelLoadingError(f"HuggingFace model loading failed: {str(e)}")

    async def _load_pytorch_model(self, config: ModelConfig) -> Any:
        """
        Load PyTorch model.

        Args:
            config: Model configuration

        Returns:
            Loaded model instance
        """
        try:
            if not TORCH_AVAILABLE:
                raise ImportError("torch library not available")

            # Load model based on file extension
            if config.model_path.suffix == '.pth':
                model = torch.load(config.model_path, map_location='cpu')
            elif config.model_path.suffix == '.pt':
                model = torch.jit.load(config.model_path, map_location='cpu')
            else:
                raise UnsupportedModelFormatError(f"Unsupported PyTorch format: {config.model_path.suffix}")

            # Set to evaluation mode
            if hasattr(model, 'eval'):
                model.eval()

            return model

        except Exception as e:
            self._logger.error(f"Failed to load PyTorch model: {str(e)}")
            raise ModelLoadingError(f"PyTorch model loading failed: {str(e)}")

    async def _load_onnx_model(self, config: ModelConfig) -> Any:
        """
        Load ONNX model.

        Args:
            config: Model configuration

        Returns:
            Loaded model instance
        """
        try:
            if not ONNX_AVAILABLE:
                raise ImportError("onnxruntime library not available")

            # Prepare session options
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            # Set providers based on device
            if config.device.startswith("cuda"):
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            else:
                providers = ['CPUExecutionProvider']

            # Create inference session
            model = ort.InferenceSession(
                str(config.model_path),
                sess_options=session_options,
                providers=providers
            )

            return model

        except Exception as e:
            self._logger.error(f"Failed to load ONNX model: {str(e)}")
            raise ModelLoadingError(f"ONNX model loading failed: {str(e)}")

    async def _load_safetensors_model(self, config: ModelConfig) -> Any:
        """
        Load SafeTensors model.

        Args:
            config: Model configuration

        Returns:
            Loaded model instance
        """
        try:
            # SafeTensors models are typically loaded through HuggingFace
            # with safetensors as the storage format
            return await self._load_huggingface_model(config)

        except Exception as e:
            self._logger.error(f"Failed to load SafeTensors model: {str(e)}")
            raise ModelLoadingError(f"SafeTensors model loading failed: {str(e)}")

    async def _create_model_info(self, model: Any, config: ModelConfig,
                               load_time: float, memory_usage: float) -> ModelInfo:
        """
        Create model information object.

        Args:
            model: Loaded model instance
            config: Model configuration
            load_time: Time taken to load model
            memory_usage: Memory used by model

        Returns:
            ModelInfo object
        """
        try:
            # Extract model information
            model_name = str(config.model_path.name)
            vocab_size = 0
            max_position_embeddings = 0
            hidden_size = 0
            num_layers = 0
            num_attention_heads = 0
            parameters_count = 0

            # Get information from HuggingFace models
            if hasattr(model, 'config'):
                model_config = model.config
                model_name = getattr(model_config, 'name_or_path', model_name)
                vocab_size = getattr(model_config, 'vocab_size', 0)
                max_position_embeddings = getattr(model_config, 'max_position_embeddings', 0)
                hidden_size = getattr(model_config, 'hidden_size', 0)
                num_layers = getattr(model_config, 'num_hidden_layers', 0)
                num_attention_heads = getattr(model_config, 'num_attention_heads', 0)

            # Count parameters for PyTorch models
            if hasattr(model, 'parameters'):
                parameters_count = sum(p.numel() for p in model.parameters())

            return ModelInfo(
                model_name=model_name,
                model_type=config.model_type,
                model_format=config.model_format,
                vocab_size=vocab_size,
                max_position_embeddings=max_position_embeddings,
                hidden_size=hidden_size,
                num_layers=num_layers,
                num_attention_heads=num_attention_heads,
                device=config.device,
                precision=config.precision,
                memory_usage_mb=memory_usage,
                parameters_count=parameters_count,
                is_loaded=True,
                load_time_seconds=load_time,
                metadata={
                    'model_path': str(config.model_path),
                    'trust_remote_code': config.trust_remote_code,
                    'low_cpu_mem_usage': config.low_cpu_mem_usage
                }
            )

        except Exception as e:
            self._logger.error(f"Failed to create model info: {str(e)}")
            # Return basic info on error
            return ModelInfo(
                model_name=str(config.model_path.name),
                model_type=config.model_type,
                model_format=config.model_format,
                vocab_size=0,
                max_position_embeddings=0,
                hidden_size=0,
                num_layers=0,
                num_attention_heads=0,
                device=config.device,
                precision=config.precision,
                memory_usage_mb=memory_usage,
                parameters_count=0,
                is_loaded=True,
                load_time_seconds=load_time
            )

    def _validate_model_config(self, config: ModelConfig) -> ValidationResult:
        """
        Validate model configuration.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate model path
            if not config.model_path:
                result.add_error(ValidationError(
                    field_name="model_path",
                    error_message="Model path is required",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.REQUIRED
                ))

            # Validate device
            if config.device not in self._available_devices:
                result.add_error(ValidationError(
                    field_name="device",
                    error_message=f"Device {config.device} not available. Available: {self._available_devices}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT
                ))

            # Validate memory limit
            if config.max_memory_gb is not None and config.max_memory_gb <= 0:
                result.add_error(ValidationError(
                    field_name="max_memory_gb",
                    error_message="Max memory must be positive",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate precision
            valid_precisions = ["float32", "float16", "bfloat16", "int8", "int4"]
            if config.precision not in valid_precisions:
                result.add_error(ValidationError(
                    field_name="precision",
                    error_message=f"Invalid precision. Valid options: {valid_precisions}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT
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
        Get model loader metrics.

        Returns:
            InferenceMetrics with current statistics
        """
        try:
            current_memory = self._memory_monitor.memory_info().rss / 1024 / 1024
            memory_usage = current_memory - self._initial_memory

            self._metrics.memory_usage_mb = memory_usage
            self._metrics.metadata = {
                'model_loaded': self.is_model_loaded(),
                'current_device': self._current_device,
                'available_devices': self._available_devices,
                'model_name': self._model_info.model_name if self._model_info else None,
                'model_parameters': self._model_info.parameters_count if self._model_info else 0
            }

            return self._metrics

        except Exception as e:
            self._logger.error(f"Failed to get metrics: {str(e)}")
            return InferenceMetrics()

    async def shutdown(self) -> bool:
        """
        Shutdown model loader and cleanup resources.

        Returns:
            True if shutdown successful
        """
        try:
            # Unload model if loaded
            if self.is_model_loaded():
                await self.unload_model()

            self._logger.info("Model loader shutdown completed")
            return True

        except Exception as e:
            self._logger.error(f"Failed to shutdown model loader: {str(e)}")
            return False
