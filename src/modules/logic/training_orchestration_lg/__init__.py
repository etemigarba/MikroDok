"""
MikroDok Training Orchestration Package
Provides comprehensive training orchestration functionality including session management, training execution, hyperparameter management, and job scheduling.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ISessionManager,
        ITrainingExecutor,
        IHyperparameterManager,
        ITrainingScheduler,
        TrainingStatus,
        TrainingPriority,
        HyperparameterType,
        OptimizationStrategy,
        TrainingMetrics,
        HyperparameterConfig,
        TrainingConfig,
        TrainingSession,
        TrainingJob,
        SchedulerStatus,
        ExecutionResult,
        HyperparameterValidationResult,
        OptimizationResult
    )
except ImportError:
    pass

# Import session manager components
try:
    from .session_manager_lg.session_manager_lg import (
        SessionManager,
        SessionStateManager
    )
except ImportError:
    pass

# Import training executor components
try:
    from .training_executor_lg.training_executor_lg import (
        TrainingExecutor,
        TrainingDataManager,
        ModelManager
    )
except ImportError:
    pass

# Import hyperparameter manager components
try:
    from .hyperparameter_manager_lg.hyperparameter_manager_lg import (
        HyperparameterManager,
        HyperparameterValidator,
        HyperparameterOptimizer
    )
except ImportError:
    pass

# Import training scheduler components
try:
    from .training_scheduler_lg.training_scheduler_lg import (
        TrainingScheduler,
        JobQueue,
        ResourceEstimator
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'ISessionManager',
    'ITrainingExecutor',
    'IHyperparameterManager',
    'ITrainingScheduler',
    'TrainingStatus',
    'TrainingPriority',
    'HyperparameterType',
    'OptimizationStrategy',
    'TrainingMetrics',
    'HyperparameterConfig',
    'TrainingConfig',
    'TrainingSession',
    'TrainingJob',
    'SchedulerStatus',
    'ExecutionResult',
    'HyperparameterValidationResult',
    'OptimizationResult',
    
    # Session Manager
    'SessionManager',
    'SessionStateManager',
    
    # Training Executor
    'TrainingExecutor',
    'TrainingDataManager',
    'ModelManager',
    
    # Hyperparameter Manager
    'HyperparameterManager',
    'HyperparameterValidator',
    'HyperparameterOptimizer',
    
    # Training Scheduler
    'TrainingScheduler',
    'JobQueue',
    'ResourceEstimator'
]
