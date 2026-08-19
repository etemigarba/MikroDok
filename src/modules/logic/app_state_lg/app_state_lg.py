"""
Module: app_state_lg
Description: Application state management for MikroDok application
Phase: 1
Location: /src/modules/logic/app_state_lg/app_state_lg.py
"""

# Standard library imports
from typing import Dict, Any, Optional
from dataclasses import dataclass
import threading


@dataclass
class AppState:
    """Application state data structure."""
    is_initialized: bool = False
    current_view: str = "dashboard"
    user_preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.user_preferences is None:
            self.user_preferences = {}


class AppStateManager:
    """
    Application state manager for centralized state control.
    
    Manages global application state including current view,
    user preferences, and initialization status.
    """
    
    def __init__(self):
        """Initialize the application state manager."""
        self._state = AppState()
        self._lock = threading.RLock()
        self._observers = []
    
    def get_state(self) -> AppState:
        """
        Get current application state.
        
        Returns:
            Current application state
        """
        with self._lock:
            return self._state
    
    def update_state(self, **kwargs) -> None:
        """
        Update application state.
        
        Args:
            **kwargs: State properties to update
        """
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._notify_observers()
    
    def add_observer(self, callback) -> None:
        """
        Add state change observer.
        
        Args:
            callback: Function to call on state changes
        """
        if callback not in self._observers:
            self._observers.append(callback)
    
    def remove_observer(self, callback) -> None:
        """
        Remove state change observer.
        
        Args:
            callback: Function to remove from observers
        """
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self) -> None:
        """Notify all observers of state changes."""
        for observer in self._observers:
            try:
                observer(self._state)
            except Exception:
                # Silently ignore observer errors
                pass
    
    def set_current_view(self, view: str) -> None:
        """
        Set the current application view.
        
        Args:
            view: Name of the current view
        """
        self.update_state(current_view=view)
    
    def get_current_view(self) -> str:
        """
        Get the current application view.
        
        Returns:
            Current view name
        """
        return self._state.current_view
    
    def set_user_preference(self, key: str, value: Any) -> None:
        """
        Set a user preference.
        
        Args:
            key: Preference key
            value: Preference value
        """
        with self._lock:
            self._state.user_preferences[key] = value
            self._notify_observers()
    
    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """
        Get a user preference.
        
        Args:
            key: Preference key
            default: Default value if key not found
            
        Returns:
            Preference value or default
        """
        return self._state.user_preferences.get(key, default)
    
    def is_initialized(self) -> bool:
        """
        Check if application is initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._state.is_initialized
    
    def set_initialized(self, initialized: bool = True) -> None:
        """
        Set application initialization status.
        
        Args:
            initialized: Initialization status
        """
        self.update_state(is_initialized=initialized)
