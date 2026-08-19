"""
Crash Handler Module
Provides application crash handling with state preservation and recovery.
"""

from .crash_handler_lg import (
    CrashHandler,
    CrashType,
    CrashContext,
    RecoveryPoint
)

__all__ = [
    'CrashHandler',
    'CrashType',
    'CrashContext',
    'RecoveryPoint'
]
