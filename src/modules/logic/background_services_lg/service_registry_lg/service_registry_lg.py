"""
Module: service_registry_lg
Description: Manages service registration, discovery, lifecycle, and dependency tracking with thread-safe operations
Phase: 4
Location: /src/modules/logic/background_services_lg/service_registry_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any
import uuid
import weakref

# Local imports
from ..base_interfaces import (
    IServiceRegistry, ServiceInfo, ServiceDependency, ServiceConfig,
    ServiceStatus, ServiceType, ServiceRegistrationResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class DependencyResolver:
    """
    Resolves service dependencies and manages dependency graphs.
    
    Features:
    - Circular dependency detection
    - Dependency ordering
    - Dependency validation
    - Dependency impact analysis
    """
    
    def __init__(self):
        """Initialize dependency resolver."""
        self._logger = get_logger(__name__)
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
    
    def add_dependency(self, service_id: str, dependency_id: str) -> bool:
        """Add a dependency relationship."""
        try:
            with self._lock:
                # Check for circular dependencies
                if self._would_create_cycle(service_id, dependency_id):
                    self._logger.warning(f"Circular dependency detected: {service_id} -> {dependency_id}")
                    return False
                
                self._dependencies[service_id].add(dependency_id)
                self._dependents[dependency_id].add(service_id)
                
                self._logger.debug(f"Added dependency: {service_id} depends on {dependency_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding dependency {service_id} -> {dependency_id}: {e}")
            return False
    
    def remove_dependency(self, service_id: str, dependency_id: str) -> bool:
        """Remove a dependency relationship."""
        try:
            with self._lock:
                self._dependencies[service_id].discard(dependency_id)
                self._dependents[dependency_id].discard(service_id)
                
                self._logger.debug(f"Removed dependency: {service_id} -> {dependency_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error removing dependency {service_id} -> {dependency_id}: {e}")
            return False
    
    def get_dependencies(self, service_id: str) -> Set[str]:
        """Get direct dependencies of a service."""
        with self._lock:
            return self._dependencies[service_id].copy()
    
    def get_dependents(self, service_id: str) -> Set[str]:
        """Get services that depend on this service."""
        with self._lock:
            return self._dependents[service_id].copy()
    
    def get_startup_order(self, service_ids: Set[str]) -> List[str]:
        """Get the order in which services should be started."""
        try:
            with self._lock:
                # Topological sort
                in_degree = {sid: 0 for sid in service_ids}
                
                # Calculate in-degrees
                for service_id in service_ids:
                    for dep in self._dependencies[service_id]:
                        if dep in service_ids:
                            in_degree[service_id] += 1
                
                # Start with services that have no dependencies
                queue = deque([sid for sid in service_ids if in_degree[sid] == 0])
                result = []
                
                while queue:
                    current = queue.popleft()
                    result.append(current)
                    
                    # Update in-degrees of dependents
                    for dependent in self._dependents[current]:
                        if dependent in service_ids:
                            in_degree[dependent] -= 1
                            if in_degree[dependent] == 0:
                                queue.append(dependent)
                
                # Check for remaining services (circular dependencies)
                remaining = [sid for sid in service_ids if sid not in result]
                if remaining:
                    self._logger.warning(f"Circular dependencies detected for services: {remaining}")
                    result.extend(remaining)  # Add them anyway
                
                return result
                
        except Exception as e:
            self._logger.error(f"Error calculating startup order: {e}")
            return list(service_ids)
    
    def _would_create_cycle(self, service_id: str, dependency_id: str) -> bool:
        """Check if adding a dependency would create a cycle."""
        # Use DFS to check if dependency_id can reach service_id
        visited = set()
        
        def dfs(current: str) -> bool:
            if current == service_id:
                return True
            if current in visited:
                return False
            
            visited.add(current)
            for dep in self._dependencies[current]:
                if dfs(dep):
                    return True
            return False
        
        return dfs(dependency_id)


class ServiceLifecycleManager:
    """
    Manages service lifecycle operations.
    
    Features:
    - Service startup/shutdown
    - Health monitoring
    - Restart management
    - Lifecycle event handling
    """
    
    def __init__(self, registry: 'ServiceRegistry'):
        """Initialize lifecycle manager."""
        self._logger = get_logger(__name__)
        self._registry = weakref.ref(registry)
        self._lifecycle_handlers: Dict[str, Dict[str, Callable]] = defaultdict(dict)
        self._lock = threading.RLock()
    
    def register_lifecycle_handler(self, service_id: str, event: str, handler: Callable) -> bool:
        """Register a lifecycle event handler."""
        try:
            with self._lock:
                self._lifecycle_handlers[service_id][event] = handler
                self._logger.debug(f"Registered {event} handler for service {service_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error registering lifecycle handler: {e}")
            return False
    
    async def start_service(self, service_id: str) -> bool:
        """Start a service."""
        try:
            registry = self._registry()
            if not registry:
                return False
            
            service = registry.get_service(service_id)
            if not service:
                self._logger.error(f"Service {service_id} not found")
                return False
            
            if service.status == ServiceStatus.RUNNING:
                self._logger.info(f"Service {service_id} is already running")
                return True
            
            # Update status to starting
            registry.update_service_status(service_id, ServiceStatus.STARTING)
            
            # Execute start handler if available
            start_handler = self._lifecycle_handlers[service_id].get('start')
            if start_handler:
                await self._execute_handler(start_handler, service_id, 'start')
            
            # Update status to running
            registry.update_service_status(service_id, ServiceStatus.RUNNING)
            service.start_time = datetime.now()
            
            self._logger.info(f"Service {service_id} started successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Error starting service {service_id}: {e}")
            registry = self._registry()
            if registry:
                registry.update_service_status(service_id, ServiceStatus.ERROR)
            return False
    
    async def stop_service(self, service_id: str) -> bool:
        """Stop a service."""
        try:
            registry = self._registry()
            if not registry:
                return False
            
            service = registry.get_service(service_id)
            if not service:
                self._logger.error(f"Service {service_id} not found")
                return False
            
            if service.status == ServiceStatus.STOPPED:
                self._logger.info(f"Service {service_id} is already stopped")
                return True
            
            # Update status to stopping
            registry.update_service_status(service_id, ServiceStatus.STOPPING)
            
            # Execute stop handler if available
            stop_handler = self._lifecycle_handlers[service_id].get('stop')
            if stop_handler:
                await self._execute_handler(stop_handler, service_id, 'stop')
            
            # Update status to stopped
            registry.update_service_status(service_id, ServiceStatus.STOPPED)
            
            self._logger.info(f"Service {service_id} stopped successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Error stopping service {service_id}: {e}")
            registry = self._registry()
            if registry:
                registry.update_service_status(service_id, ServiceStatus.ERROR)
            return False
    
    async def _execute_handler(self, handler: Callable, service_id: str, event: str) -> None:
        """Execute a lifecycle handler."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(service_id)
            else:
                handler(service_id)
                
        except Exception as e:
            self._logger.error(f"Error executing {event} handler for service {service_id}: {e}")
            raise


class ServiceManager:
    """
    High-level service management operations.
    
    Features:
    - Bulk service operations
    - Service group management
    - Service monitoring
    - Service health tracking
    """
    
    def __init__(self, registry: 'ServiceRegistry'):
        """Initialize service manager."""
        self._logger = get_logger(__name__)
        self._registry = weakref.ref(registry)
        self._service_groups: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
    
    def create_service_group(self, group_name: str, service_ids: List[str]) -> bool:
        """Create a service group."""
        try:
            with self._lock:
                self._service_groups[group_name] = set(service_ids)
                self._logger.info(f"Created service group '{group_name}' with {len(service_ids)} services")
                return True
                
        except Exception as e:
            self._logger.error(f"Error creating service group {group_name}: {e}")
            return False
    
    async def start_service_group(self, group_name: str) -> Dict[str, bool]:
        """Start all services in a group."""
        results = {}
        
        try:
            registry = self._registry()
            if not registry:
                return results
            
            service_ids = self._service_groups.get(group_name, set())
            if not service_ids:
                self._logger.warning(f"Service group '{group_name}' not found or empty")
                return results
            
            # Get startup order based on dependencies
            startup_order = registry._dependency_resolver.get_startup_order(service_ids)
            
            # Start services in order
            for service_id in startup_order:
                success = await registry._lifecycle_manager.start_service(service_id)
                results[service_id] = success
                
                if not success:
                    self._logger.error(f"Failed to start service {service_id} in group {group_name}")
            
            self._logger.info(f"Started service group '{group_name}': {sum(results.values())}/{len(results)} successful")
            return results
            
        except Exception as e:
            self._logger.error(f"Error starting service group {group_name}: {e}")
            return results
    
    async def stop_service_group(self, group_name: str) -> Dict[str, bool]:
        """Stop all services in a group."""
        results = {}
        
        try:
            registry = self._registry()
            if not registry:
                return results
            
            service_ids = self._service_groups.get(group_name, set())
            if not service_ids:
                self._logger.warning(f"Service group '{group_name}' not found or empty")
                return results
            
            # Stop services in reverse dependency order
            startup_order = registry._dependency_resolver.get_startup_order(service_ids)
            shutdown_order = list(reversed(startup_order))
            
            # Stop services in order
            for service_id in shutdown_order:
                success = await registry._lifecycle_manager.stop_service(service_id)
                results[service_id] = success
                
                if not success:
                    self._logger.error(f"Failed to stop service {service_id} in group {group_name}")
            
            self._logger.info(f"Stopped service group '{group_name}': {sum(results.values())}/{len(results)} successful")
            return results
            
        except Exception as e:
            self._logger.error(f"Error stopping service group {group_name}: {e}")
            return results


class ServiceRegistry(IServiceRegistry):
    """
    Main service registry implementation with thread-safe operations.

    Features:
    - Service registration and discovery
    - Dependency management
    - Lifecycle management
    - Health monitoring integration
    - Thread-safe operations
    """

    def __init__(self):
        """Initialize service registry."""
        self._logger = get_logger(__name__)

        # Service storage
        self._services: Dict[str, ServiceInfo] = {}
        self._service_configs: Dict[str, ServiceConfig] = {}
        self._dependencies: Dict[str, List[ServiceDependency]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

        # Component managers
        self._dependency_resolver = DependencyResolver()
        self._lifecycle_manager = ServiceLifecycleManager(self)
        self._service_manager = ServiceManager(self)

        # Heartbeat tracking
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_running = False

        self._logger.info("Service registry initialized")

    def register_service(self, service_info: ServiceInfo, config: Optional[ServiceConfig] = None) -> ServiceRegistrationResult:
        """Register a new service."""
        try:
            with self._lock:
                if service_info.service_id in self._services:
                    message = f"Service {service_info.service_id} is already registered"
                    self._logger.warning(message)
                    return ServiceRegistrationResult(
                        success=False,
                        service_id=service_info.service_id,
                        message=message
                    )

                # Set default config if not provided
                if config is None:
                    config = ServiceConfig()

                # Store service and config
                self._services[service_info.service_id] = service_info
                self._service_configs[service_info.service_id] = config

                # Add dependencies to resolver
                for dep_id in service_info.dependencies:
                    self._dependency_resolver.add_dependency(service_info.service_id, dep_id)

                # Start heartbeat monitoring if not running
                if not self._heartbeat_running:
                    self._start_heartbeat_monitoring()

                message = f"Service {service_info.service_id} registered successfully"
                self._logger.info(message)

                return ServiceRegistrationResult(
                    success=True,
                    service_id=service_info.service_id,
                    message=message,
                    metadata={'service_type': service_info.service_type.value}
                )

        except Exception as e:
            error_msg = f"Error registering service {service_info.service_id}: {e}"
            self._logger.error(error_msg)
            return ServiceRegistrationResult(
                success=False,
                service_id=service_info.service_id,
                message=error_msg
            )

    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service."""
        try:
            with self._lock:
                if service_id not in self._services:
                    self._logger.warning(f"Service {service_id} not found for unregistration")
                    return False

                # Remove from storage
                service = self._services.pop(service_id)
                self._service_configs.pop(service_id, None)
                self._dependencies.pop(service_id, None)

                # Remove dependencies
                for dep_id in service.dependencies:
                    self._dependency_resolver.remove_dependency(service_id, dep_id)

                self._logger.info(f"Service {service_id} unregistered successfully")
                return True

        except Exception as e:
            self._logger.error(f"Error unregistering service {service_id}: {e}")
            return False

    def get_service(self, service_id: str) -> Optional[ServiceInfo]:
        """Get service information."""
        with self._lock:
            return self._services.get(service_id)

    def list_services(self, service_type: Optional[ServiceType] = None, status: Optional[ServiceStatus] = None) -> List[ServiceInfo]:
        """List registered services."""
        with self._lock:
            services = list(self._services.values())

            if service_type:
                services = [s for s in services if s.service_type == service_type]

            if status:
                services = [s for s in services if s.status == status]

            return services

    def update_service_status(self, service_id: str, status: ServiceStatus) -> bool:
        """Update service status."""
        try:
            with self._lock:
                service = self._services.get(service_id)
                if not service:
                    self._logger.warning(f"Service {service_id} not found for status update")
                    return False

                old_status = service.status
                service.status = status
                service.last_heartbeat = datetime.now()

                self._logger.debug(f"Service {service_id} status updated: {old_status.value} -> {status.value}")
                return True

        except Exception as e:
            self._logger.error(f"Error updating service status for {service_id}: {e}")
            return False

    def add_dependency(self, dependency: ServiceDependency) -> bool:
        """Add service dependency."""
        try:
            with self._lock:
                # Add to dependency resolver
                success = self._dependency_resolver.add_dependency(
                    dependency.dependent_service_id,
                    dependency.service_id
                )

                if success:
                    self._dependencies[dependency.dependent_service_id].append(dependency)
                    self._logger.debug(f"Added dependency: {dependency.dependent_service_id} -> {dependency.service_id}")

                return success

        except Exception as e:
            self._logger.error(f"Error adding dependency: {e}")
            return False

    def get_dependencies(self, service_id: str) -> List[ServiceDependency]:
        """Get service dependencies."""
        with self._lock:
            return self._dependencies.get(service_id, []).copy()

    def start_service(self, service_id: str) -> bool:
        """Start a service."""
        try:
            # Use async wrapper for sync interface
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._lifecycle_manager.start_service(service_id))
            finally:
                loop.close()

        except Exception as e:
            self._logger.error(f"Error starting service {service_id}: {e}")
            return False

    def stop_service(self, service_id: str) -> bool:
        """Stop a service."""
        try:
            # Use async wrapper for sync interface
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._lifecycle_manager.stop_service(service_id))
            finally:
                loop.close()

        except Exception as e:
            self._logger.error(f"Error stopping service {service_id}: {e}")
            return False

    def _start_heartbeat_monitoring(self) -> None:
        """Start heartbeat monitoring thread."""
        if self._heartbeat_running:
            return

        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_monitor, daemon=True)
        self._heartbeat_thread.start()
        self._logger.info("Heartbeat monitoring started")

    def _heartbeat_monitor(self) -> None:
        """Monitor service heartbeats."""
        while self._heartbeat_running:
            try:
                current_time = datetime.now()

                with self._lock:
                    for service_id, service in self._services.items():
                        config = self._service_configs.get(service_id, ServiceConfig())

                        # Check if heartbeat is overdue
                        if (service.last_heartbeat and
                            current_time - service.last_heartbeat > config.heartbeat_interval * 2):

                            if service.status == ServiceStatus.RUNNING:
                                self._logger.warning(f"Service {service_id} heartbeat overdue")
                                service.status = ServiceStatus.ERROR

                # Sleep for heartbeat interval
                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self._logger.error(f"Error in heartbeat monitor: {e}")
                time.sleep(30)

    def shutdown(self) -> None:
        """Shutdown the service registry."""
        self._heartbeat_running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        self._logger.info("Service registry shutdown complete")
