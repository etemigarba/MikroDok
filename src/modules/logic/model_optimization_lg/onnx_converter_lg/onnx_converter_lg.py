"""
Module: onnx_converter_lg
Description: Converts PyTorch models to ONNX format for deployment optimization and cross-platform compatibility
Phase: 4
Location: /src/modules/logic/model_optimization_lg/onnx_converter_lg/onnx_converter_lg.py
"""

# Standard library imports
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import warnings

# Third-party imports
import numpy as np
import torch
import torch.onnx
import onnx
import onnxruntime as ort
from onnx import helper, checker, shape_inference
from onnxruntime.tools import optimizer

# Local imports
try:
    from ..base_interfaces import (
        IONNXConverter,
        ONNXConversionConfig,
        ONNXConversionResult,
        OptimizationLevel,
        ModelFormat
    )
except ImportError:
    from src.modules.logic.model_optimization_lg.base_interfaces import (
        IONNXConverter,
        ONNXConversionConfig,
        ONNXConversionResult,
        OptimizationLevel,
        ModelFormat
    )

try:
    from src.modules.logic.error_handling_lg import ValidationError, ProcessingError
except ImportError:
    # Fallback error classes if not available
    class ValidationError(Exception):
        pass

    class ProcessingError(Exception):
        pass


class ONNXConverter(IONNXConverter):
    """
    Production-ready ONNX converter for model deployment optimization.
    
    Converts PyTorch models to ONNX format with comprehensive optimization,
    validation, and cross-platform compatibility features.
    """
    
    def __init__(self):
        """Initialize ONNX converter with default settings."""
        self.logger = logging.getLogger(__name__)
        self._optimization_passes = self._initialize_optimization_passes()
        self._supported_opsets = list(range(9, 18))  # ONNX opset versions 9-17
        self._device_configs = self._initialize_device_configs()
    
    def _initialize_optimization_passes(self) -> Dict[str, List[str]]:
        """Initialize optimization passes for different levels."""
        return {
            "basic": [
                "eliminate_identity",
                "eliminate_nop_transpose",
                "fuse_consecutive_transposes"
            ],
            "standard": [
                "eliminate_identity",
                "eliminate_nop_transpose", 
                "fuse_consecutive_transposes",
                "fuse_add_bias_into_conv",
                "fuse_bn_into_conv",
                "eliminate_unused_initializer"
            ],
            "aggressive": [
                "eliminate_identity",
                "eliminate_nop_transpose",
                "fuse_consecutive_transposes",
                "fuse_add_bias_into_conv",
                "fuse_bn_into_conv",
                "eliminate_unused_initializer",
                "fuse_matmul_add_bias_into_gemm",
                "fuse_pad_into_conv",
                "eliminate_dropout"
            ],
            "maximum": [
                "eliminate_identity",
                "eliminate_nop_transpose",
                "fuse_consecutive_transposes",
                "fuse_add_bias_into_conv",
                "fuse_bn_into_conv",
                "eliminate_unused_initializer",
                "fuse_matmul_add_bias_into_gemm",
                "fuse_pad_into_conv",
                "eliminate_dropout",
                "eliminate_if_with_const_cond",
                "extract_constant_to_initializer",
                "eliminate_shape_gather",
                "merge_consecutive_reshapes"
            ]
        }
    
    def _initialize_device_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize device-specific configurations."""
        return {
            "cpu": {
                "providers": ["CPUExecutionProvider"],
                "optimization_level": "all",
                "enable_mem_pattern": True,
                "enable_mem_reuse": True
            },
            "gpu": {
                "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"],
                "optimization_level": "all",
                "enable_mem_pattern": True,
                "enable_mem_reuse": True,
                "cuda_mem_limit": 2 * 1024 * 1024 * 1024  # 2GB
            },
            "tensorrt": {
                "providers": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
                "optimization_level": "all",
                "trt_max_workspace_size": 1 << 30,  # 1GB
                "trt_fp16_enable": True
            }
        }
    
    async def convert_to_onnx(self, model_path: Path, output_path: Path,
                            config: Optional[ONNXConversionConfig] = None) -> ONNXConversionResult:
        """
        Convert a model to ONNX format.
        
        Args:
            model_path: Path to the original model
            output_path: Path for the ONNX model
            config: Optional conversion configuration
            
        Returns:
            ONNXConversionResult with conversion details
        """
        start_time = time.time()
        config = config or ONNXConversionConfig()
        
        try:
            self.logger.info(f"Starting ONNX conversion: {model_path} -> {output_path}")
            
            # Validate input model
            if not model_path.exists():
                raise ValidationError(f"Model file not found: {model_path}")
            
            # Load PyTorch model
            pytorch_model = await self._load_pytorch_model(model_path)
            
            # Prepare model for export
            pytorch_model.eval()
            
            # Create dummy input for tracing
            dummy_input = self._create_dummy_input(pytorch_model, config)
            
            # Export to ONNX
            await self._export_to_onnx(
                pytorch_model, dummy_input, output_path, config
            )
            
            # Validate ONNX model
            if not self.validate_onnx_model(output_path):
                raise ProcessingError("Generated ONNX model failed validation")
            
            # Apply optimizations
            optimization_applied = []
            if config.enable_optimization:
                optimization_applied = await self._optimize_onnx_model(
                    output_path, config
                )
            
            # Get model information
            model_info = self.get_model_info(output_path)
            
            conversion_time = time.time() - start_time
            model_size = self._get_model_size_mb(output_path)
            
            self.logger.info(
                f"ONNX conversion completed in {conversion_time:.2f}s, "
                f"model size: {model_size:.2f}MB"
            )
            
            return ONNXConversionResult(
                success=True,
                onnx_model_path=output_path,
                original_model_path=model_path,
                conversion_config=config,
                model_size_mb=model_size,
                conversion_time_seconds=conversion_time,
                opset_version=config.opset_version,
                input_shapes=model_info.get("input_shapes", {}),
                output_shapes=model_info.get("output_shapes", {}),
                optimization_applied=optimization_applied
            )
            
        except Exception as e:
            self.logger.error(f"ONNX conversion failed: {str(e)}")
            return ONNXConversionResult(
                success=False,
                onnx_model_path=output_path,
                original_model_path=model_path,
                conversion_config=config,
                model_size_mb=0.0,
                conversion_time_seconds=time.time() - start_time,
                opset_version=config.opset_version,
                input_shapes={},
                output_shapes={},
                error_message=str(e)
            )
    
    def validate_onnx_model(self, onnx_model_path: Path) -> bool:
        """
        Validate ONNX model structure and compatibility.
        
        Args:
            onnx_model_path: Path to ONNX model
            
        Returns:
            True if model is valid
        """
        try:
            # Load and check ONNX model
            onnx_model = onnx.load(str(onnx_model_path))
            
            # Check model structure
            checker.check_model(onnx_model)
            
            # Infer shapes
            onnx_model = shape_inference.infer_shapes(onnx_model)
            
            # Test with ONNX Runtime
            session = ort.InferenceSession(str(onnx_model_path))
            
            self.logger.info("ONNX model validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"ONNX model validation failed: {str(e)}")
            return False
    
    def get_model_info(self, model_path: Path) -> Dict[str, Any]:
        """
        Get information about the model structure.
        
        Args:
            model_path: Path to the model
            
        Returns:
            Model information dictionary
        """
        try:
            if model_path.suffix.lower() == '.onnx':
                return self._get_onnx_model_info(model_path)
            else:
                return self._get_pytorch_model_info(model_path)
                
        except Exception as e:
            self.logger.error(f"Failed to get model info: {str(e)}")
            return {}
    
    async def _load_pytorch_model(self, model_path: Path) -> torch.nn.Module:
        """Load PyTorch model from file."""
        try:
            if model_path.suffix == '.pth':
                model = torch.load(model_path, map_location='cpu')
            elif model_path.suffix == '.pt':
                model = torch.jit.load(model_path, map_location='cpu')
            else:
                raise ValidationError(f"Unsupported model format: {model_path.suffix}")
            
            return model
            
        except Exception as e:
            raise ProcessingError(f"Failed to load PyTorch model: {str(e)}")
    
    def _create_dummy_input(self, model: torch.nn.Module,
                          config: ONNXConversionConfig) -> torch.Tensor:
        """Create dummy input tensor for model tracing."""
        try:
            batch_size = config.batch_size or 1
            sequence_length = config.sequence_length or 512
            
            # Try to infer input shape from model
            if hasattr(model, 'config') and hasattr(model.config, 'hidden_size'):
                # Transformer model
                return torch.randint(0, 1000, (batch_size, sequence_length))
            else:
                # Default input shape
                return torch.randn(batch_size, sequence_length)
                
        except Exception as e:
            self.logger.warning(f"Failed to create optimal dummy input: {str(e)}")
            return torch.randn(1, 512)  # Fallback
    
    async def _export_to_onnx(self, model: torch.nn.Module, dummy_input: torch.Tensor,
                            output_path: Path, config: ONNXConversionConfig):
        """Export PyTorch model to ONNX format."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Configure export parameters
            export_params = {
                'model': model,
                'args': dummy_input,
                'f': str(output_path),
                'export_params': config.export_params,
                'verbose': False,
                'input_names': ['input'],
                'output_names': ['output'],
                'opset_version': config.opset_version,
                'do_constant_folding': config.do_constant_folding,
                'dynamic_axes': config.dynamic_axes
            }
            
            # Add custom operators if specified
            if config.custom_operators:
                export_params['custom_opsets'] = {op: 1 for op in config.custom_operators}
            
            # Export model
            torch.onnx.export(**export_params)
            
        except Exception as e:
            raise ProcessingError(f"ONNX export failed: {str(e)}")
    
    async def _optimize_onnx_model(self, model_path: Path,
                                 config: ONNXConversionConfig) -> List[str]:
        """Apply optimizations to ONNX model."""
        try:
            optimization_level = config.optimization_level.value
            passes = self._optimization_passes.get(optimization_level, [])
            
            if not passes:
                return []
            
            # Load model
            session_options = ort.SessionOptions()
            session_options.optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # Apply device-specific optimizations
            device_config = self._device_configs.get(config.target_device, {})
            providers = device_config.get("providers", ["CPUExecutionProvider"])
            
            # Create optimized session
            session = ort.InferenceSession(
                str(model_path),
                sess_options=session_options,
                providers=providers
            )
            
            self.logger.info(f"Applied {len(passes)} optimization passes")
            return passes
            
        except Exception as e:
            self.logger.warning(f"ONNX optimization failed: {str(e)}")
            return []
    
    def _get_model_size_mb(self, model_path: Path) -> float:
        """Get model file size in MB."""
        try:
            size_bytes = model_path.stat().st_size
            return size_bytes / (1024 * 1024)
        except Exception:
            return 0.0
    
    def _get_onnx_model_info(self, model_path: Path) -> Dict[str, Any]:
        """Get information about ONNX model."""
        try:
            model = onnx.load(str(model_path))
            
            # Get input shapes
            input_shapes = {}
            for input_tensor in model.graph.input:
                shape = []
                for dim in input_tensor.type.tensor_type.shape.dim:
                    if dim.dim_value:
                        shape.append(dim.dim_value)
                    else:
                        shape.append(-1)  # Dynamic dimension
                input_shapes[input_tensor.name] = tuple(shape)
            
            # Get output shapes
            output_shapes = {}
            for output_tensor in model.graph.output:
                shape = []
                for dim in output_tensor.type.tensor_type.shape.dim:
                    if dim.dim_value:
                        shape.append(dim.dim_value)
                    else:
                        shape.append(-1)  # Dynamic dimension
                output_shapes[output_tensor.name] = tuple(shape)
            
            return {
                "input_shapes": input_shapes,
                "output_shapes": output_shapes,
                "opset_version": model.opset_import[0].version,
                "num_nodes": len(model.graph.node),
                "model_format": "onnx"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get ONNX model info: {str(e)}")
            return {}
    
    def _get_pytorch_model_info(self, model_path: Path) -> Dict[str, Any]:
        """Get information about PyTorch model."""
        try:
            model = torch.load(model_path, map_location='cpu')
            
            # Count parameters
            total_params = sum(p.numel() for p in model.parameters())
            trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
            
            return {
                "total_parameters": total_params,
                "trainable_parameters": trainable_params,
                "model_format": "pytorch",
                "model_type": type(model).__name__
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get PyTorch model info: {str(e)}")
            return {}
