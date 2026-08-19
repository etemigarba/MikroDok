#!/usr/bin/env python3
"""
Lazy Loading System
Implements global best practices for lazy module loading to optimize startup performance.
"""

import importlib
import sys
import threading
import time
from typing import Any, Dict, Optional, Callable
from functools import wraps


class LazyModule:
    """Lazy module loader that imports modules only when accessed."""
    
    def __init__(self, module_name: str, package: Optional[str] = None):
        self.module_name = module_name
        self.package = package
        self._module = None
        self._loading = False
        self._lock = threading.Lock()
    
    def __getattr__(self, name: str) -> Any:
        """Load module on first attribute access."""
        if self._module is None:
            self._load_module()
        return getattr(self._module, name)
    
    def _load_module(self):
        """Thread-safe module loading."""
        with self._lock:
            if self._module is None and not self._loading:
                self._loading = True
                try:
                    self._module = importlib.import_module(self.module_name, self.package)
                except ImportError as e:
                    print(f"Warning: Failed to lazy load {self.module_name}: {e}")
                    # Create a dummy module to prevent repeated import attempts
                    self._module = type('DummyModule', (), {})()
                finally:
                    self._loading = False


class LazyImportManager:
    """Manages lazy imports with global best practices."""
    
    def __init__(self):
        self._lazy_modules: Dict[str, LazyModule] = {}
        self._import_times: Dict[str, float] = {}
        self._preload_queue = []
        self._preload_thread = None
    
    def register_lazy_import(self, name: str, module_path: str, package: Optional[str] = None) -> LazyModule:
        """Register a module for lazy loading."""
        if name not in self._lazy_modules:
            self._lazy_modules[name] = LazyModule(module_path, package)
        return self._lazy_modules[name]
    
    def get_lazy_module(self, name: str) -> Optional[LazyModule]:
        """Get a registered lazy module."""
        return self._lazy_modules.get(name)
    
    def preload_module(self, name: str, priority: int = 0):
        """Queue a module for background preloading."""
        if name in self._lazy_modules:
            self._preload_queue.append((priority, name))
            self._preload_queue.sort(reverse=True)  # Higher priority first
    
    def start_background_preloading(self):
        """Start background preloading of queued modules."""
        if self._preload_thread is None or not self._preload_thread.is_alive():
            self._preload_thread = threading.Thread(target=self._preload_worker, daemon=True)
            self._preload_thread.start()
    
    def _preload_worker(self):
        """Background worker for preloading modules."""
        while self._preload_queue:
            try:
                priority, name = self._preload_queue.pop(0)
                if name in self._lazy_modules:
                    start_time = time.time()
                    # Trigger loading by accessing a dummy attribute
                    try:
                        _ = getattr(self._lazy_modules[name], '__name__', None)
                    except:
                        pass
                    self._import_times[name] = time.time() - start_time
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.1)
            except Exception as e:
                print(f"Warning: Error preloading {name}: {e}")
    
    def get_import_stats(self) -> Dict[str, float]:
        """Get import timing statistics."""
        return self._import_times.copy()


# Global lazy import manager
_lazy_manager = LazyImportManager()


def lazy_import(module_path: str, package: Optional[str] = None, name: Optional[str] = None) -> LazyModule:
    """
    Create a lazy import for a module.
    
    Args:
        module_path: Full module path (e.g., 'flet')
        package: Package name for relative imports
        name: Custom name for the lazy module (defaults to module_path)
    
    Returns:
        LazyModule instance
    """
    module_name = name or module_path.split('.')[-1]
    return _lazy_manager.register_lazy_import(module_name, module_path, package)


def preload_module(name: str, priority: int = 0):
    """Queue a module for background preloading."""
    _lazy_manager.preload_module(name, priority)


def start_preloading():
    """Start background preloading of queued modules."""
    _lazy_manager.start_background_preloading()


def get_import_stats() -> Dict[str, float]:
    """Get import timing statistics."""
    return _lazy_manager.get_import_stats()


def lazy_function(module_path: str, function_name: str, package: Optional[str] = None):
    """
    Decorator for lazy function loading.
    
    Args:
        module_path: Module containing the function
        function_name: Name of the function to load
        package: Package for relative imports
    """
    def decorator(func):
        lazy_mod = lazy_import(module_path, package)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            actual_func = getattr(lazy_mod, function_name)
            return actual_func(*args, **kwargs)
        
        return wrapper
    return decorator


def lazy_class(module_path: str, class_name: str, package: Optional[str] = None):
    """
    Create a lazy class loader.
    
    Args:
        module_path: Module containing the class
        class_name: Name of the class to load
        package: Package for relative imports
    """
    lazy_mod = lazy_import(module_path, package)
    
    class LazyClassWrapper:
        def __new__(cls, *args, **kwargs):
            actual_class = getattr(lazy_mod, class_name)
            return actual_class(*args, **kwargs)
    
    return LazyClassWrapper


# Commonly used lazy imports for MikroDok
def setup_mikrodok_lazy_imports():
    """Setup lazy imports for MikroDok application."""
    
    # Critical UI framework (highest priority)
    flet = lazy_import('flet', name='flet')
    preload_module('flet', priority=100)
    
    # Core infrastructure (high priority)
    logging_infra = lazy_import(
        'src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg',
        name='logging_infrastructure'
    )
    preload_module('logging_infrastructure', priority=90)
    
    # Theme system (medium priority)
    theme_system = lazy_import(
        'src.modules.ui.theme_system_ui.theme_system_ui',
        name='theme_system'
    )
    preload_module('theme_system', priority=80)
    
    # Document processing (lower priority)
    doc_processing = lazy_import(
        'src.modules.logic.document_processing_service_lg',
        name='document_processing'
    )
    preload_module('document_processing', priority=50)
    
    # Resource dashboard (lowest priority)
    resource_dashboard = lazy_import(
        'src.modules.ui.resource_dashboard_integration_ui',
        name='resource_dashboard'
    )
    preload_module('resource_dashboard', priority=30)
    
    return {
        'flet': flet,
        'logging_infrastructure': logging_infra,
        'theme_system': theme_system,
        'document_processing': doc_processing,
        'resource_dashboard': resource_dashboard
    }


if __name__ == "__main__":
    # Test the lazy loading system
    print("Testing lazy loading system...")
    
    # Setup lazy imports
    lazy_modules = setup_mikrodok_lazy_imports()
    
    print("Lazy imports registered. Starting preloading...")
    start_preloading()
    
    # Wait a bit for preloading
    time.sleep(2)
    
    print("Import stats:", get_import_stats())
