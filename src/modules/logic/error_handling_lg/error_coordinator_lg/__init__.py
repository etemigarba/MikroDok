"""
Error Coordinator Module
Provides centralized error handling coordination functionality.
"""

from .error_coordinator_lg import (
    ErrorHandlingCoordinator,
    ErrorHandlingMode,
    ErrorHandlingConfig,
    ErrorHandlingStats,
    get_error_coordinator,
    handle_error,
    validate_input
)

__all__ = [
    'ErrorHandlingCoordinator',
    'ErrorHandlingMode',
    'ErrorHandlingConfig',
    'ErrorHandlingStats',
    'get_error_coordinator',
    'handle_error',
    'validate_input'
]
