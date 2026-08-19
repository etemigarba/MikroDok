"""
MikroDok Access Controller Package
Manages access control and permission validation with role-based security and session management.
"""

from .access_controller_lg import (
    AccessController,
    AccessControlError,
    SessionExpiredError
)

__all__ = [
    'AccessController',
    'AccessControlError',
    'SessionExpiredError'
]
