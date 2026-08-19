"""
Module: dependency_resolver_lg
Description: Resolves and validates module dependencies
Phase: 1
Location: /src/modules/logic/system_initialization_lg/dependency_resolver_lg/
"""

# Standard library imports
import os
import sys
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from collections import defaultdict, deque
import weakref

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import (
    ErrorClassifier, ErrorSeverity, ErrorCategory
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class DependencyType(Enum):
    """Types of dependencies."""
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    WEAK = "WEAK"
    CIRCULAR = "CIRCULAR"


class NodeStatus(Enum):
    """Dependency node status."""
    UNRESOLVED = "UNRESOLVED"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
    CIRCULAR_DETECTED = "CIRCULAR_DETECTED"


@dataclass
class DependencyNode:
    """Represents a node in the dependency graph."""
    name: str
    module_path: str
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    dependency_types: Dict[str, DependencyType] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.UNRESOLVED
    resolution_order: int = -1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_dependency(self, dependency_name: str, dep_type: DependencyType = DependencyType.REQUIRED) -> None:
        """Add a dependency to this node."""
        self.dependencies.add(dependency_name)
        self.dependency_types[dependency_name] = dep_type
    
    def add_dependent(self, dependent_name: str) -> None:
        """Add a dependent to this node."""
        self.dependents.add(dependent_name)
    
    def is_resolved(self) -> bool:
        """Check if node is resolved."""
        return self.status == NodeStatus.RESOLVED


class CircularDependencyError(Exception):
    """Exception raised when circular dependencies are detected."""
    
    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        super().__init__(f"Circular dependency detected: {' -> '.join(cycle + [cycle[0]])}")


@dataclass
class ResolutionResult:
    """Result of dependency resolution."""
    success: bool
    resolution_order: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    circular_dependencies: List[List[str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    resolution_time: float = 0.0
    total_nodes: int = 0
    resolved_nodes: int = 0


class DependencyGraph:
    """
    Represents a dependency graph with nodes and edges.
    
    Provides methods for graph manipulation, cycle detection,
    and topological sorting.
    """
    
    def __init__(self):
        """Initialize the dependency graph."""
        self._nodes: Dict[str, DependencyNode] = {}
        self._lock = threading.RLock()
    
    def add_node(self, node: DependencyNode) -> None:
        """
        Add a node to the graph.
        
        Args:
            node: Dependency node to add
        """
        with self._lock:
            self._nodes[node.name] = node
            
            # Update dependents for existing nodes
            for dep_name in node.dependencies:
                if dep_name in self._nodes:
                    self._nodes[dep_name].add_dependent(node.name)
            
            # Update dependencies for existing nodes
            for existing_node in self._nodes.values():
                if node.name in existing_node.dependencies:
                    existing_node.add_dependent(node.name)
    
    def get_node(self, name: str) -> Optional[DependencyNode]:
        """
        Get a node by name.
        
        Args:
            name: Node name
            
        Returns:
            DependencyNode or None if not found
        """
        with self._lock:
            return self._nodes.get(name)
    
    def get_all_nodes(self) -> Dict[str, DependencyNode]:
        """
        Get all nodes in the graph.
        
        Returns:
            Dictionary of all nodes
        """
        with self._lock:
            return self._nodes.copy()
    
    def has_node(self, name: str) -> bool:
        """
        Check if node exists in graph.
        
        Args:
            name: Node name
            
        Returns:
            True if node exists
        """
        with self._lock:
            return name in self._nodes
    
    def remove_node(self, name: str) -> bool:
        """
        Remove a node from the graph.
        
        Args:
            name: Node name to remove
            
        Returns:
            True if node was removed
        """
        with self._lock:
            if name not in self._nodes:
                return False
            
            node = self._nodes[name]
            
            # Remove from dependents
            for dep_name in node.dependencies:
                if dep_name in self._nodes:
                    self._nodes[dep_name].dependents.discard(name)
            
            # Remove from dependencies
            for dependent_name in node.dependents:
                if dependent_name in self._nodes:
                    self._nodes[dependent_name].dependencies.discard(name)
                    self._nodes[dependent_name].dependency_types.pop(name, None)
            
            del self._nodes[name]
            return True
    
    def detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies in the graph.
        
        Returns:
            List of cycles (each cycle is a list of node names)
        """
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node_name: str, path: List[str]) -> None:
            if node_name in rec_stack:
                # Found a cycle
                cycle_start = path.index(node_name)
                cycle = path[cycle_start:] + [node_name]
                cycles.append(cycle)
                return
            
            if node_name in visited:
                return
            
            visited.add(node_name)
            rec_stack.add(node_name)
            path.append(node_name)
            
            node = self._nodes.get(node_name)
            if node:
                for dep_name in node.dependencies:
                    if dep_name in self._nodes:
                        dfs(dep_name, path.copy())
            
            rec_stack.remove(node_name)
        
        with self._lock:
            for node_name in self._nodes:
                if node_name not in visited:
                    dfs(node_name, [])
        
        return cycles
    
    def topological_sort(self) -> List[str]:
        """
        Perform topological sort of the dependency graph.
        
        Returns:
            List of node names in topological order
            
        Raises:
            CircularDependencyError: If circular dependencies exist
        """
        # Check for cycles first
        cycles = self.detect_cycles()
        if cycles:
            raise CircularDependencyError(cycles[0])
        
        with self._lock:
            # Kahn's algorithm
            in_degree = defaultdict(int)
            
            # Calculate in-degrees
            for node in self._nodes.values():
                for dep_name in node.dependencies:
                    if dep_name in self._nodes:
                        in_degree[node.name] += 1
            
            # Initialize queue with nodes having no dependencies
            queue = deque()
            for node_name in self._nodes:
                if in_degree[node_name] == 0:
                    queue.append(node_name)
            
            result = []
            
            while queue:
                node_name = queue.popleft()
                result.append(node_name)
                
                node = self._nodes[node_name]
                for dependent_name in node.dependents:
                    if dependent_name in self._nodes:
                        in_degree[dependent_name] -= 1
                        if in_degree[dependent_name] == 0:
                            queue.append(dependent_name)
            
            return result


class DependencyResolver:
    """
    Resolves and validates module dependencies with circular dependency detection.

    Manages dependency graphs, performs resolution ordering, handles dependency
    injection, and provides comprehensive dependency analysis.
    """

    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the dependency resolver."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("dependency_resolver")
        self._error_classifier = ErrorClassifier()

        # Dependency management
        self._dependency_graph = DependencyGraph()
        self._resolved_instances: Dict[str, Any] = {}
        self._resolution_cache: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

        # Configuration
        self._max_resolution_depth = 100
        self._cache_enabled = True
        self._strict_mode = True

        self._logger.info("DependencyResolver initialized successfully")

    def register_dependency(self, name: str, module_path: str,
                           dependencies: List[str] = None,
                           dependency_types: Dict[str, DependencyType] = None,
                           metadata: Dict[str, Any] = None) -> None:
        """
        Register a module dependency.

        Args:
            name: Module name
            module_path: Path to the module
            dependencies: List of dependency names
            dependency_types: Types of dependencies
            metadata: Additional metadata
        """
        dependencies = dependencies or []
        dependency_types = dependency_types or {}
        metadata = metadata or {}

        # Create dependency node
        node = DependencyNode(
            name=name,
            module_path=module_path,
            metadata=metadata
        )

        # Add dependencies
        for dep_name in dependencies:
            dep_type = dependency_types.get(dep_name, DependencyType.REQUIRED)
            node.add_dependency(dep_name, dep_type)

        # Add to graph
        self._dependency_graph.add_node(node)

        # Clear resolution cache
        with self._lock:
            self._resolution_cache.clear()

        self._logger.info(f"Registered dependency: {name} with {len(dependencies)} dependencies")

    def resolve_dependencies(self, target_modules: List[str] = None) -> ResolutionResult:
        """
        Resolve dependencies for target modules or all modules.

        Args:
            target_modules: List of target module names (None for all)

        Returns:
            ResolutionResult with resolution outcome
        """
        import time
        start_time = time.time()

        self._logger.info("Starting dependency resolution")

        try:
            # Get all nodes if no targets specified
            if target_modules is None:
                all_nodes = self._dependency_graph.get_all_nodes()
                target_modules = list(all_nodes.keys())

            # Check cache
            cache_key = ','.join(sorted(target_modules))
            if self._cache_enabled:
                with self._lock:
                    if cache_key in self._resolution_cache:
                        cached_order = self._resolution_cache[cache_key]
                        self._logger.debug("Using cached resolution order")
                        return ResolutionResult(
                            success=True,
                            resolution_order=cached_order,
                            resolution_time=time.time() - start_time,
                            total_nodes=len(target_modules),
                            resolved_nodes=len(cached_order)
                        )

            # Detect circular dependencies
            cycles = self._dependency_graph.detect_cycles()
            if cycles:
                self._logger.error(f"Circular dependencies detected: {len(cycles)} cycles")
                return ResolutionResult(
                    success=False,
                    circular_dependencies=cycles,
                    resolution_time=time.time() - start_time,
                    total_nodes=len(target_modules)
                )

            # Perform topological sort
            try:
                resolution_order = self._dependency_graph.topological_sort()

                # Filter to target modules if specified
                if target_modules:
                    target_set = set(target_modules)
                    resolution_order = [name for name in resolution_order if name in target_set]

                # Update node resolution order
                for i, node_name in enumerate(resolution_order):
                    node = self._dependency_graph.get_node(node_name)
                    if node:
                        node.resolution_order = i
                        node.status = NodeStatus.RESOLVED

                # Cache result
                if self._cache_enabled:
                    with self._lock:
                        self._resolution_cache[cache_key] = resolution_order

                resolution_time = time.time() - start_time
                self._logger.info(f"Dependency resolution completed: {len(resolution_order)} modules "
                                f"resolved in {resolution_time:.3f}s")

                return ResolutionResult(
                    success=True,
                    resolution_order=resolution_order,
                    resolution_time=resolution_time,
                    total_nodes=len(target_modules),
                    resolved_nodes=len(resolution_order)
                )

            except CircularDependencyError as e:
                self._logger.error(f"Circular dependency error: {str(e)}")
                return ResolutionResult(
                    success=False,
                    circular_dependencies=[e.cycle],
                    resolution_time=time.time() - start_time,
                    total_nodes=len(target_modules)
                )

        except Exception as e:
            self._logger.error(f"Dependency resolution failed: {str(e)}")
            return ResolutionResult(
                success=False,
                warnings=[str(e)],
                resolution_time=time.time() - start_time,
                total_nodes=len(target_modules) if target_modules else 0
            )

    def get_dependency_chain(self, module_name: str) -> List[str]:
        """
        Get the dependency chain for a specific module.

        Args:
            module_name: Name of the module

        Returns:
            List of dependencies in resolution order
        """
        chain = []
        visited = set()

        def collect_dependencies(name: str) -> None:
            if name in visited:
                return

            visited.add(name)
            node = self._dependency_graph.get_node(name)

            if node:
                # Add dependencies first
                for dep_name in node.dependencies:
                    if dep_name not in visited:
                        collect_dependencies(dep_name)

                # Add current node
                if name not in chain:
                    chain.append(name)

        collect_dependencies(module_name)
        return chain

    def validate_dependencies(self) -> ResolutionResult:
        """
        Validate all registered dependencies.

        Returns:
            ResolutionResult with validation outcome
        """
        import time
        start_time = time.time()

        self._logger.info("Starting dependency validation")

        try:
            all_nodes = self._dependency_graph.get_all_nodes()
            warnings = []
            failed_nodes = []

            # Check for missing dependencies
            for node_name, node in all_nodes.items():
                for dep_name in node.dependencies:
                    if not self._dependency_graph.has_node(dep_name):
                        if node.dependency_types.get(dep_name) == DependencyType.REQUIRED:
                            failed_nodes.append(node_name)
                            self._logger.error(f"Missing required dependency: {dep_name} for {node_name}")
                        else:
                            warnings.append(f"Missing optional dependency: {dep_name} for {node_name}")

            # Check for circular dependencies
            cycles = self._dependency_graph.detect_cycles()

            success = len(failed_nodes) == 0 and len(cycles) == 0

            validation_time = time.time() - start_time
            self._logger.info(f"Dependency validation completed: {'SUCCESS' if success else 'FAILED'} "
                            f"({validation_time:.3f}s)")

            return ResolutionResult(
                success=success,
                failed_nodes=failed_nodes,
                circular_dependencies=cycles,
                warnings=warnings,
                resolution_time=validation_time,
                total_nodes=len(all_nodes)
            )

        except Exception as e:
            self._logger.error(f"Dependency validation failed: {str(e)}")
            return ResolutionResult(
                success=False,
                warnings=[str(e)],
                resolution_time=time.time() - start_time
            )

    def get_dependency_graph_info(self) -> Dict[str, Any]:
        """
        Get information about the dependency graph.

        Returns:
            Dictionary with graph statistics
        """
        all_nodes = self._dependency_graph.get_all_nodes()

        total_dependencies = sum(len(node.dependencies) for node in all_nodes.values())
        max_dependencies = max((len(node.dependencies) for node in all_nodes.values()), default=0)

        # Calculate depth
        max_depth = 0
        for node_name in all_nodes:
            chain = self.get_dependency_chain(node_name)
            max_depth = max(max_depth, len(chain))

        return {
            "total_nodes": len(all_nodes),
            "total_dependencies": total_dependencies,
            "max_dependencies_per_node": max_dependencies,
            "max_dependency_depth": max_depth,
            "has_cycles": len(self._dependency_graph.detect_cycles()) > 0,
            "cache_size": len(self._resolution_cache)
        }

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        with self._lock:
            self._resolution_cache.clear()

        self._logger.debug("Resolution cache cleared")

    def remove_dependency(self, name: str) -> bool:
        """
        Remove a dependency from the graph.

        Args:
            name: Name of the dependency to remove

        Returns:
            True if dependency was removed
        """
        success = self._dependency_graph.remove_node(name)

        if success:
            # Clear cache and resolved instances
            with self._lock:
                self._resolution_cache.clear()
                self._resolved_instances.pop(name, None)

            self._logger.info(f"Removed dependency: {name}")

        return success

    def get_dependents(self, module_name: str) -> List[str]:
        """
        Get modules that depend on the specified module.

        Args:
            module_name: Name of the module

        Returns:
            List of dependent module names
        """
        node = self._dependency_graph.get_node(module_name)
        if node:
            return list(node.dependents)
        return []

    def get_dependencies(self, module_name: str) -> List[str]:
        """
        Get dependencies of the specified module.

        Args:
            module_name: Name of the module

        Returns:
            List of dependency names
        """
        node = self._dependency_graph.get_node(module_name)
        if node:
            return list(node.dependencies)
        return []

    def is_dependency_optional(self, module_name: str, dependency_name: str) -> bool:
        """
        Check if a dependency is optional.

        Args:
            module_name: Name of the module
            dependency_name: Name of the dependency

        Returns:
            True if dependency is optional
        """
        node = self._dependency_graph.get_node(module_name)
        if node and dependency_name in node.dependency_types:
            dep_type = node.dependency_types[dependency_name]
            return dep_type in (DependencyType.OPTIONAL, DependencyType.WEAK)
        return False
