"""
Quantization Engine Module
Applies quantization techniques (INT4, INT8, FP16) to trained models for deployment optimization.
"""

from .quantization_engine_lg import QuantizationEngine

__all__ = [
    'QuantizationEngine'
]
