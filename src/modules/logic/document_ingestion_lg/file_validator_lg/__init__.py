"""
File Validator Module
Validates file integrity, size limits (10GB max), and format compatibility before processing.
"""

from .file_validator_lg import (
    FileValidator,
    IFileValidator,
    FileValidationResult,
    FileValidationError,
    ValidationSeverity,
    ValidationCategory
)

__all__ = [
    'FileValidator',
    'IFileValidator',
    'FileValidationResult',
    'FileValidationError',
    'ValidationSeverity',
    'ValidationCategory'
]
