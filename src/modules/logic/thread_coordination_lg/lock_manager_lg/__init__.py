"""
MikroDok Lock Manager Package
Provides lock management functionality for coordinating thread-safe access to shared resources.
"""

from .lock_manager_lg import (
    LockManager,
    ResourceLockManager,
    DeadlockDetector,
    LockRegistry
)

__all__ = [
    'LockManager',
    'ResourceLockManager',
    'DeadlockDetector',
    'LockRegistry'
]
