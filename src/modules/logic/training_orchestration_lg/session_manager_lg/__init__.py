"""
MikroDok Session Manager Package
Provides training session lifecycle management including creation, execution, pause, resume, and termination.
"""

from .session_manager_lg import SessionManager, SessionStateManager

__all__ = [
    'SessionManager',
    'SessionStateManager'
]
