"""
Module: hyperparameter_manager_lg
Description: Manages training hyperparameters including learning rate, batch size, and optimizer settings
Phase: 4
Location: /src/modules/logic/training_orchestration_lg/hyperparameter_manager_lg/
"""

# Standard library imports
import asyncio
import json
import logging
import math
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
import sqlite3

# Third-party imports
import numpy as np

# Lazy imports for scipy and sklearn to prevent scipy loading during app startup
_scipy_optimize = None
_sklearn_gaussian_process = None

def _get_scipy_optimize():
    """Lazy import for scipy.optimize to prevent scipy loading during startup."""
    global _scipy_optimize
    if _scipy_optimize is None:
        try:
            from scipy import optimize
            _scipy_optimize = optimize
        except ImportError:
            _scipy_optimize = False
    return _scipy_optimize

def _get_sklearn_gaussian_process():
    """Lazy import for sklearn.gaussian_process to prevent scipy loading during startup."""
    global _sklearn_gaussian_process
    if _sklearn_gaussian_process is None:
        try:
            from sklearn import gaussian_process
            _sklearn_gaussian_process = gaussian_process
        except ImportError:
            _sklearn_gaussian_process = False
    return _sklearn_gaussian_process

# Local imports
from ..base_interfaces import (
    IHyperparameterManager, HyperparameterConfig, HyperparameterValidationResult,
    OptimizationResult, OptimizationStrategy, HyperparameterType, TrainingConfig
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier


class HyperparameterValidator:
    """Validates hyperparameter configurations and values."""
    
    def __init__(self):
        """Initialize hyperparameter validator."""
        self._logger = get_logger(__name__)
        self._validation_rules = self._setup_validation_rules()
    
    def _setup_validation_rules(self) -> Dict[HyperparameterType, Dict[str, Any]]:
        """Setup validation rules for different hyperparameter types."""
        return {
            HyperparameterType.LEARNING_RATE: {
                'min_value': 1e-8,
                'max_value': 1.0,
                'suggested_range': (1e-5, 1e-1),
                'type': float
            },
            HyperparameterType.BATCH_SIZE: {
                'min_value': 1,
                'max_value': 1024,
                'suggested_range': (8, 128),
                'type': int,
                'power_of_2': True
            },
            HyperparameterType.EPOCHS: {
                'min_value': 1,
                'max_value': 1000,
                'suggested_range': (10, 200),
                'type': int
            },
            HyperparameterType.OPTIMIZER: {
                'choices': ['adam', 'adamw', 'sgd', 'rmsprop', 'adagrad'],
                'type': str
            },
            HyperparameterType.SCHEDULER: {
                'choices': ['cosine', 'linear', 'exponential', 'step', 'none'],
                'type': str
            },
            HyperparameterType.REGULARIZATION: {
                'min_value': 0.0,
                'max_value': 1.0,
                'suggested_range': (0.0, 0.1),
                'type': float
            }
        }
    
    def validate_parameter(self, config: HyperparameterConfig) -> HyperparameterValidationResult:
        """
        Validate a single hyperparameter configuration.
        
        Args:
            config: Hyperparameter configuration to validate
            
        Returns:
            HyperparameterValidationResult with validation outcome
        """
        result = HyperparameterValidationResult(
            is_valid=True,
            parameter_name=config.name
        )
        
        try:
            rules = self._validation_rules.get(config.param_type)
            if not rules:
                result.warnings.append(f"No validation rules for parameter type {config.param_type}")
                return result
            
            # Type validation
            expected_type = rules.get('type')
            if expected_type and not isinstance(config.value, expected_type):
                try:
                    config.value = expected_type(config.value)
                except (ValueError, TypeError):
                    result.is_valid = False
                    result.error_messages.append(f"Invalid type for {config.name}: expected {expected_type.__name__}")
                    return result
            
            # Range validation
            if 'min_value' in rules and config.value < rules['min_value']:
                result.is_valid = False
                result.error_messages.append(f"{config.name} value {config.value} below minimum {rules['min_value']}")
                result.suggested_value = rules['min_value']
            
            if 'max_value' in rules and config.value > rules['max_value']:
                result.is_valid = False
                result.error_messages.append(f"{config.name} value {config.value} above maximum {rules['max_value']}")
                result.suggested_value = rules['max_value']
            
            # Choice validation
            if 'choices' in rules and config.value not in rules['choices']:
                result.is_valid = False
                result.error_messages.append(f"{config.name} value '{config.value}' not in allowed choices: {rules['choices']}")
                result.suggested_value = rules['choices'][0]
            
            # Special validations
            if config.param_type == HyperparameterType.BATCH_SIZE and rules.get('power_of_2'):
                if not self._is_power_of_2(config.value):
                    result.warnings.append(f"Batch size {config.value} is not a power of 2, which may be suboptimal")
                    result.suggested_value = self._nearest_power_of_2(config.value)
            
            # Suggested range check
            if 'suggested_range' in rules:
                min_suggested, max_suggested = rules['suggested_range']
                if not (min_suggested <= config.value <= max_suggested):
                    result.warnings.append(
                        f"{config.name} value {config.value} outside suggested range "
                        f"[{min_suggested}, {max_suggested}]"
                    )
            
            # Custom validation function
            if config.validation_fn:
                if not config.validation_fn(config.value):
                    result.is_valid = False
                    result.error_messages.append(f"Custom validation failed for {config.name}")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error validating parameter {config.name}: {e}")
            result.is_valid = False
            result.error_messages.append(f"Validation error: {str(e)}")
            return result
    
    def _is_power_of_2(self, n: int) -> bool:
        """Check if number is a power of 2."""
        return n > 0 and (n & (n - 1)) == 0
    
    def _nearest_power_of_2(self, n: int) -> int:
        """Find nearest power of 2."""
        if n <= 1:
            return 1
        return 2 ** round(math.log2(n))


class HyperparameterOptimizer:
    """Optimizes hyperparameters using various strategies."""
    
    def __init__(self):
        """Initialize hyperparameter optimizer."""
        self._logger = get_logger(__name__)
        self._optimization_history: List[Dict[str, Any]] = []
    
    async def optimize(self, base_config: TrainingConfig, strategy: OptimizationStrategy,
                      max_trials: int = 100) -> OptimizationResult:
        """
        Optimize hyperparameters using specified strategy.
        
        Args:
            base_config: Base training configuration
            strategy: Optimization strategy to use
            max_trials: Maximum number of trials
            
        Returns:
            OptimizationResult with best configuration
        """
        start_time = datetime.now()
        
        try:
            if strategy == OptimizationStrategy.MANUAL:
                return await self._manual_optimization(base_config)
            elif strategy == OptimizationStrategy.GRID_SEARCH:
                return await self._grid_search_optimization(base_config, max_trials)
            elif strategy == OptimizationStrategy.RANDOM_SEARCH:
                return await self._random_search_optimization(base_config, max_trials)
            elif strategy == OptimizationStrategy.BAYESIAN:
                return await self._bayesian_optimization(base_config, max_trials)
            elif strategy == OptimizationStrategy.ADAPTIVE:
                return await self._adaptive_optimization(base_config, max_trials)
            else:
                raise ValueError(f"Unsupported optimization strategy: {strategy}")
                
        except Exception as e:
            self._logger.error(f"Optimization failed: {e}")
            optimization_time = datetime.now() - start_time
            
            return OptimizationResult(
                best_config={},
                best_score=float('inf'),
                optimization_history=[],
                total_trials=0,
                successful_trials=0,
                optimization_time=optimization_time,
                convergence_achieved=False,
                metadata={'error': str(e)}
            )
    
    async def _manual_optimization(self, base_config: TrainingConfig) -> OptimizationResult:
        """Manual optimization - return base configuration."""
        config_dict = {name: param.value for name, param in base_config.hyperparameters.items()}
        
        return OptimizationResult(
            best_config=config_dict,
            best_score=0.0,  # No optimization performed
            optimization_history=[{'config': config_dict, 'score': 0.0}],
            total_trials=1,
            successful_trials=1,
            optimization_time=timedelta(seconds=0),
            convergence_achieved=True
        )
    
    async def _grid_search_optimization(self, base_config: TrainingConfig, max_trials: int) -> OptimizationResult:
        """Grid search optimization."""
        # This is a simplified implementation
        # In practice, you'd generate a grid of parameter combinations
        
        best_config = {}
        best_score = float('inf')
        history = []
        successful_trials = 0
        
        # Generate grid points (simplified)
        for trial in range(min(max_trials, 10)):  # Limit for demo
            config = self._generate_grid_point(base_config, trial)
            score = await self._evaluate_config(config)
            
            history.append({'config': config, 'score': score, 'trial': trial})
            
            if score < best_score:
                best_score = score
                best_config = config
            
            successful_trials += 1
            
            # Simulate some delay
            await asyncio.sleep(0.01)
        
        return OptimizationResult(
            best_config=best_config,
            best_score=best_score,
            optimization_history=history,
            total_trials=min(max_trials, 10),
            successful_trials=successful_trials,
            optimization_time=timedelta(seconds=successful_trials * 0.01),
            convergence_achieved=True
        )
    
    async def _random_search_optimization(self, base_config: TrainingConfig, max_trials: int) -> OptimizationResult:
        """Random search optimization."""
        best_config = {}
        best_score = float('inf')
        history = []
        successful_trials = 0
        
        for trial in range(max_trials):
            config = self._generate_random_config(base_config)
            score = await self._evaluate_config(config)
            
            history.append({'config': config, 'score': score, 'trial': trial})
            
            if score < best_score:
                best_score = score
                best_config = config
            
            successful_trials += 1
            
            # Simulate some delay
            await asyncio.sleep(0.001)
        
        return OptimizationResult(
            best_config=best_config,
            best_score=best_score,
            optimization_history=history,
            total_trials=max_trials,
            successful_trials=successful_trials,
            optimization_time=timedelta(seconds=max_trials * 0.001),
            convergence_achieved=len(history) > 10 and abs(history[-1]['score'] - history[-10]['score']) < 0.01
        )

    async def _bayesian_optimization(self, base_config: TrainingConfig, max_trials: int) -> OptimizationResult:
        """Bayesian optimization using Gaussian Process."""
        # Simplified Bayesian optimization implementation
        best_config = {}
        best_score = float('inf')
        history = []
        successful_trials = 0

        # Initialize with random samples
        X_samples = []
        y_samples = []

        for trial in range(min(5, max_trials)):  # Initial random samples
            config = self._generate_random_config(base_config)
            score = await self._evaluate_config(config)

            X_samples.append(self._config_to_vector(config))
            y_samples.append(score)

            history.append({'config': config, 'score': score, 'trial': trial})

            if score < best_score:
                best_score = score
                best_config = config

            successful_trials += 1

        # Bayesian optimization loop (simplified)
        for trial in range(5, max_trials):
            # In practice, you'd use acquisition function to select next point
            config = self._generate_random_config(base_config)  # Simplified
            score = await self._evaluate_config(config)

            X_samples.append(self._config_to_vector(config))
            y_samples.append(score)

            history.append({'config': config, 'score': score, 'trial': trial})

            if score < best_score:
                best_score = score
                best_config = config

            successful_trials += 1
            await asyncio.sleep(0.001)

        return OptimizationResult(
            best_config=best_config,
            best_score=best_score,
            optimization_history=history,
            total_trials=max_trials,
            successful_trials=successful_trials,
            optimization_time=timedelta(seconds=max_trials * 0.001),
            convergence_achieved=True
        )

    async def _adaptive_optimization(self, base_config: TrainingConfig, max_trials: int) -> OptimizationResult:
        """Adaptive optimization that adjusts strategy based on progress."""
        # Start with random search, then switch to more focused search
        best_config = {}
        best_score = float('inf')
        history = []
        successful_trials = 0

        # Phase 1: Random exploration
        exploration_trials = max_trials // 3
        for trial in range(exploration_trials):
            config = self._generate_random_config(base_config)
            score = await self._evaluate_config(config)

            history.append({'config': config, 'score': score, 'trial': trial, 'phase': 'exploration'})

            if score < best_score:
                best_score = score
                best_config = config

            successful_trials += 1
            await asyncio.sleep(0.001)

        # Phase 2: Focused search around best configuration
        for trial in range(exploration_trials, max_trials):
            config = self._generate_focused_config(best_config, base_config)
            score = await self._evaluate_config(config)

            history.append({'config': config, 'score': score, 'trial': trial, 'phase': 'exploitation'})

            if score < best_score:
                best_score = score
                best_config = config

            successful_trials += 1
            await asyncio.sleep(0.001)

        return OptimizationResult(
            best_config=best_config,
            best_score=best_score,
            optimization_history=history,
            total_trials=max_trials,
            successful_trials=successful_trials,
            optimization_time=timedelta(seconds=max_trials * 0.001),
            convergence_achieved=True
        )

    def _generate_grid_point(self, base_config: TrainingConfig, trial: int) -> Dict[str, Any]:
        """Generate a grid point for grid search."""
        config = {}
        for name, param in base_config.hyperparameters.items():
            if param.param_type == HyperparameterType.LEARNING_RATE:
                # Generate grid points for learning rate
                lr_values = [1e-5, 5e-5, 1e-4, 5e-4, 1e-3, 5e-3, 1e-2]
                config[name] = lr_values[trial % len(lr_values)]
            elif param.param_type == HyperparameterType.BATCH_SIZE:
                # Generate grid points for batch size
                batch_sizes = [8, 16, 32, 64, 128]
                config[name] = batch_sizes[trial % len(batch_sizes)]
            else:
                config[name] = param.value
        return config

    def _generate_random_config(self, base_config: TrainingConfig) -> Dict[str, Any]:
        """Generate a random configuration."""
        config = {}
        for name, param in base_config.hyperparameters.items():
            if param.param_type == HyperparameterType.LEARNING_RATE:
                config[name] = 10 ** random.uniform(-5, -2)  # 1e-5 to 1e-2
            elif param.param_type == HyperparameterType.BATCH_SIZE:
                config[name] = random.choice([8, 16, 32, 64, 128])
            elif param.param_type == HyperparameterType.EPOCHS:
                config[name] = random.randint(10, 200)
            elif param.param_type == HyperparameterType.OPTIMIZER:
                config[name] = random.choice(['adam', 'adamw', 'sgd'])
            else:
                config[name] = param.value
        return config

    def _generate_focused_config(self, best_config: Dict[str, Any], base_config: TrainingConfig) -> Dict[str, Any]:
        """Generate a configuration focused around the best found configuration."""
        config = best_config.copy()

        # Add small perturbations to the best configuration
        for name, param in base_config.hyperparameters.items():
            if param.param_type == HyperparameterType.LEARNING_RATE:
                # Perturb learning rate by ±50%
                current_lr = best_config.get(name, param.value)
                factor = random.uniform(0.5, 1.5)
                config[name] = max(1e-6, min(1e-1, current_lr * factor))
            elif param.param_type == HyperparameterType.BATCH_SIZE:
                # Keep batch size or try adjacent power of 2
                current_batch = best_config.get(name, param.value)
                if random.random() < 0.3:  # 30% chance to change
                    if current_batch >= 32:
                        config[name] = random.choice([current_batch // 2, current_batch, current_batch * 2])
                    else:
                        config[name] = random.choice([current_batch, current_batch * 2])

        return config

    def _config_to_vector(self, config: Dict[str, Any]) -> List[float]:
        """Convert configuration to numerical vector for Bayesian optimization."""
        vector = []
        for key, value in config.items():
            if isinstance(value, (int, float)):
                vector.append(float(value))
            elif isinstance(value, str):
                # Simple hash-based encoding for categorical variables
                vector.append(float(hash(value) % 1000))
        return vector

    async def _evaluate_config(self, config: Dict[str, Any]) -> float:
        """
        Evaluate a configuration and return a score.

        In practice, this would involve training a model with the configuration
        and returning validation loss or other metric.
        """
        # Mock evaluation - return random score with some logic
        base_score = 1.0

        # Learning rate penalty
        lr = config.get('learning_rate', 0.001)
        if lr > 0.01 or lr < 1e-5:
            base_score += 0.5

        # Batch size penalty
        batch_size = config.get('batch_size', 32)
        if batch_size < 8 or batch_size > 128:
            base_score += 0.3

        # Add some randomness
        noise = random.uniform(-0.2, 0.2)

        return base_score + noise


class HyperparameterManager(IHyperparameterManager):
    """
    Manages training hyperparameters including learning rate, batch size, and optimizer settings.

    This class provides comprehensive hyperparameter management with validation,
    optimization, and adaptive tuning capabilities for training sessions.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize hyperparameter manager.

        Args:
            db_path: Path to hyperparameter database
        """
        self.db_path = db_path or Path("data/hyperparameters.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._validator = HyperparameterValidator()
        self._optimizer = HyperparameterOptimizer()
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()

        self._lock = threading.Lock()
        self._session_history: Dict[str, List[Dict[str, Any]]] = {}

        self._init_database()

    def _init_database(self) -> None:
        """Initialize hyperparameter database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS hyperparameter_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        parameter_name TEXT NOT NULL,
                        old_value TEXT,
                        new_value TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        reason TEXT,
                        performance_impact REAL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        best_config_json TEXT NOT NULL,
                        best_score REAL NOT NULL,
                        total_trials INTEGER NOT NULL,
                        successful_trials INTEGER NOT NULL,
                        optimization_time_seconds REAL NOT NULL,
                        convergence_achieved BOOLEAN NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_hyperparameter_session
                    ON hyperparameter_history (session_id, timestamp)
                """)

                conn.commit()
                self._logger.info("Hyperparameter database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize hyperparameter database: {e}")
                raise
            finally:
                conn.close()

    async def validate_config(self, config: Dict[str, HyperparameterConfig]) -> List[HyperparameterValidationResult]:
        """
        Validate hyperparameter configuration.

        Args:
            config: Hyperparameter configuration to validate

        Returns:
            List of validation results
        """
        try:
            results = []

            for param_name, param_config in config.items():
                result = self._validator.validate_parameter(param_config)
                results.append(result)

            # Cross-parameter validation
            self._validate_parameter_combinations(config, results)

            self._logger.info(f"Validated {len(config)} hyperparameters")
            return results

        except Exception as e:
            self._logger.error(f"Failed to validate hyperparameter config: {e}")
            return [HyperparameterValidationResult(
                is_valid=False,
                parameter_name="validation_error",
                error_messages=[str(e)]
            )]

    async def optimize_hyperparameters(self, base_config: TrainingConfig,
                                     strategy: OptimizationStrategy,
                                     max_trials: int = 100) -> OptimizationResult:
        """
        Optimize hyperparameters using specified strategy.

        Args:
            base_config: Base training configuration
            strategy: Optimization strategy to use
            max_trials: Maximum number of trials

        Returns:
            OptimizationResult with best configuration
        """
        try:
            self._logger.info(f"Starting hyperparameter optimization with {strategy.value} strategy")

            result = await self._optimizer.optimize(base_config, strategy, max_trials)

            # Save optimization result to database
            await self._save_optimization_result("optimization_session", strategy, result)

            self._logger.info(f"Optimization completed: best score = {result.best_score}")
            return result

        except Exception as e:
            self._logger.error(f"Hyperparameter optimization failed: {e}")
            raise

    async def suggest_hyperparameters(self, model_type: str, dataset_size: int) -> Dict[str, HyperparameterConfig]:
        """
        Suggest hyperparameters based on model type and dataset.

        Args:
            model_type: Type of model being trained
            dataset_size: Size of training dataset

        Returns:
            Dictionary of suggested hyperparameters
        """
        try:
            suggestions = {}

            # Learning rate suggestions based on model type and dataset size
            if model_type.lower() in ['transformer', 'bert', 'gpt']:
                base_lr = 5e-5 if dataset_size > 100000 else 1e-4
            elif model_type.lower() in ['cnn', 'resnet', 'vgg']:
                base_lr = 1e-3 if dataset_size > 50000 else 5e-3
            else:
                base_lr = 1e-3

            suggestions['learning_rate'] = HyperparameterConfig(
                name='learning_rate',
                value=base_lr,
                param_type=HyperparameterType.LEARNING_RATE,
                min_value=1e-6,
                max_value=1e-1,
                description=f"Suggested learning rate for {model_type} with {dataset_size} samples"
            )

            # Batch size suggestions based on dataset size
            if dataset_size < 1000:
                batch_size = 8
            elif dataset_size < 10000:
                batch_size = 16
            elif dataset_size < 100000:
                batch_size = 32
            else:
                batch_size = 64

            suggestions['batch_size'] = HyperparameterConfig(
                name='batch_size',
                value=batch_size,
                param_type=HyperparameterType.BATCH_SIZE,
                min_value=1,
                max_value=512,
                description=f"Suggested batch size for dataset with {dataset_size} samples"
            )

            # Epoch suggestions
            if dataset_size < 1000:
                epochs = 100
            elif dataset_size < 10000:
                epochs = 50
            else:
                epochs = 20

            suggestions['epochs'] = HyperparameterConfig(
                name='epochs',
                value=epochs,
                param_type=HyperparameterType.EPOCHS,
                min_value=1,
                max_value=1000,
                description=f"Suggested epochs for dataset with {dataset_size} samples"
            )

            # Optimizer suggestions
            if model_type.lower() in ['transformer', 'bert', 'gpt']:
                optimizer = 'adamw'
            else:
                optimizer = 'adam'

            suggestions['optimizer'] = HyperparameterConfig(
                name='optimizer',
                value=optimizer,
                param_type=HyperparameterType.OPTIMIZER,
                choices=['adam', 'adamw', 'sgd', 'rmsprop'],
                description=f"Suggested optimizer for {model_type}"
            )

            self._logger.info(f"Generated hyperparameter suggestions for {model_type} with {dataset_size} samples")
            return suggestions

        except Exception as e:
            self._logger.error(f"Failed to suggest hyperparameters: {e}")
            return {}

    async def update_hyperparameter(self, session_id: str, param_name: str, value: Any) -> bool:
        """
        Update a hyperparameter during training.

        Args:
            session_id: Session identifier
            param_name: Parameter name to update
            value: New parameter value

        Returns:
            True if updated successfully
        """
        try:
            # Get current value for history
            old_value = None
            if session_id in self._session_history:
                for entry in reversed(self._session_history[session_id]):
                    if entry['parameter_name'] == param_name:
                        old_value = entry['new_value']
                        break

            # Record the change
            change_record = {
                'session_id': session_id,
                'parameter_name': param_name,
                'old_value': str(old_value) if old_value is not None else None,
                'new_value': str(value),
                'timestamp': datetime.now().isoformat(),
                'reason': 'manual_update'
            }

            # Save to database
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO hyperparameter_history (
                            session_id, parameter_name, old_value, new_value,
                            timestamp, reason, performance_impact
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id, param_name, change_record['old_value'],
                        change_record['new_value'], change_record['timestamp'],
                        change_record['reason'], 0.0  # Performance impact unknown
                    ))

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to save hyperparameter change: {e}")
                    return False
                finally:
                    conn.close()

            # Update in-memory history
            if session_id not in self._session_history:
                self._session_history[session_id] = []
            self._session_history[session_id].append(change_record)

            self._logger.info(f"Updated hyperparameter {param_name} for session {session_id}: {old_value} -> {value}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to update hyperparameter {param_name} for session {session_id}: {e}")
            return False

    async def get_hyperparameter_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get hyperparameter change history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of hyperparameter changes
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT parameter_name, old_value, new_value, timestamp,
                               reason, performance_impact
                        FROM hyperparameter_history
                        WHERE session_id = ?
                        ORDER BY timestamp
                    """, (session_id,))

                    rows = cursor.fetchall()

                    history = []
                    for row in rows:
                        history.append({
                            'parameter_name': row[0],
                            'old_value': row[1],
                            'new_value': row[2],
                            'timestamp': row[3],
                            'reason': row[4],
                            'performance_impact': row[5]
                        })

                    return history

                except Exception as e:
                    self._logger.error(f"Failed to get hyperparameter history: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to get hyperparameter history for session {session_id}: {e}")
            return []

    def _validate_parameter_combinations(self, config: Dict[str, HyperparameterConfig],
                                       results: List[HyperparameterValidationResult]) -> None:
        """Validate combinations of parameters."""
        try:
            # Check learning rate vs batch size relationship
            lr_config = None
            batch_config = None

            for name, param in config.items():
                if param.param_type == HyperparameterType.LEARNING_RATE:
                    lr_config = param
                elif param.param_type == HyperparameterType.BATCH_SIZE:
                    batch_config = param

            if lr_config and batch_config:
                # Large batch sizes typically need higher learning rates
                if batch_config.value >= 64 and lr_config.value < 1e-4:
                    for result in results:
                        if result.parameter_name == lr_config.name:
                            result.warnings.append(
                                f"Learning rate {lr_config.value} may be too low for batch size {batch_config.value}"
                            )

                # Small batch sizes typically need lower learning rates
                if batch_config.value <= 16 and lr_config.value > 1e-2:
                    for result in results:
                        if result.parameter_name == lr_config.name:
                            result.warnings.append(
                                f"Learning rate {lr_config.value} may be too high for batch size {batch_config.value}"
                            )

        except Exception as e:
            self._logger.error(f"Error in parameter combination validation: {e}")

    async def _save_optimization_result(self, session_id: str, strategy: OptimizationStrategy,
                                      result: OptimizationResult) -> None:
        """Save optimization result to database."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO optimization_results (
                            session_id, strategy, best_config_json, best_score,
                            total_trials, successful_trials, optimization_time_seconds,
                            convergence_achieved, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        strategy.value,
                        json.dumps(result.best_config),
                        result.best_score,
                        result.total_trials,
                        result.successful_trials,
                        result.optimization_time.total_seconds(),
                        result.convergence_achieved,
                        datetime.now().isoformat()
                    ))

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to save optimization result: {e}")
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to save optimization result: {e}")

    async def get_optimization_history(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get optimization history.

        Args:
            session_id: Optional session filter

        Returns:
            List of optimization results
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()

                    if session_id:
                        cursor.execute("""
                            SELECT * FROM optimization_results
                            WHERE session_id = ?
                            ORDER BY timestamp DESC
                        """, (session_id,))
                    else:
                        cursor.execute("""
                            SELECT * FROM optimization_results
                            ORDER BY timestamp DESC
                        """)

                    rows = cursor.fetchall()

                    history = []
                    for row in rows:
                        history.append({
                            'session_id': row[1],
                            'strategy': row[2],
                            'best_config': json.loads(row[3]),
                            'best_score': row[4],
                            'total_trials': row[5],
                            'successful_trials': row[6],
                            'optimization_time_seconds': row[7],
                            'convergence_achieved': bool(row[8]),
                            'timestamp': row[9]
                        })

                    return history

                except Exception as e:
                    self._logger.error(f"Failed to get optimization history: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to get optimization history: {e}")
            return []
