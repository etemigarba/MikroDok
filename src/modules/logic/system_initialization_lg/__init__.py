"""
MikroDok System Initialization Package
Provides comprehensive system initialization and startup management functionality.
"""

# Import all system initialization components
from .startup_orchestrator_lg.startup_orchestrator_lg import (
    StartupOrchestrator,
    InitializationPhase,
    StartupResult,
    ComponentStatus,
    StartupContext
)

from .preflight_checker_lg.preflight_checker_lg import (
    PreflightChecker,
    SystemRequirement,
    ValidationReport,
    RequirementStatus,
    HardwareCapability
)

from .shutdown_coordinator_lg.shutdown_coordinator_lg import (
    ShutdownCoordinator,
    ShutdownPhase,
    ShutdownResult,
    CleanupStatus,
    ShutdownContext
)

from .dependency_resolver_lg.dependency_resolver_lg import (
    DependencyResolver,
    DependencyNode,
    DependencyGraph,
    ResolutionResult,
    CircularDependencyError
)

from .system_coordinator_lg.system_coordinator_lg import (
    SystemInitializationCoordinator,
    SystemInitializationMode,
    SystemInitializationConfig,
    SystemInitializationStats,
    SystemInitializationResult,
    get_system_coordinator,
    initialize_system,
    shutdown_system
)

__all__ = [
    # Startup Orchestration
    'StartupOrchestrator',
    'InitializationPhase',
    'StartupResult',
    'ComponentStatus',
    'StartupContext',
    
    # Preflight Checking
    'PreflightChecker',
    'SystemRequirement',
    'ValidationReport',
    'RequirementStatus',
    'HardwareCapability',
    
    # Shutdown Coordination
    'ShutdownCoordinator',
    'ShutdownPhase',
    'ShutdownResult',
    'CleanupStatus',
    'ShutdownContext',
    
    # Dependency Resolution
    'DependencyResolver',
    'DependencyNode',
    'DependencyGraph',
    'ResolutionResult',
    'CircularDependencyError',

    # System Coordination
    'SystemInitializationCoordinator',
    'SystemInitializationMode',
    'SystemInitializationConfig',
    'SystemInitializationStats',
    'SystemInitializationResult',
    'get_system_coordinator',
    'initialize_system',
    'shutdown_system'
]
