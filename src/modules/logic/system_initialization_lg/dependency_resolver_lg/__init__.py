"""
Dependency Resolver Module
Resolves and validates module dependencies with circular dependency detection.
"""

from .dependency_resolver_lg import (
    DependencyResolver,
    DependencyNode,
    DependencyGraph,
    ResolutionResult,
    CircularDependencyError
)

__all__ = [
    'DependencyResolver',
    'DependencyNode',
    'DependencyGraph',
    'ResolutionResult',
    'CircularDependencyError'
]
