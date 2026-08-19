"""
Module: app_state_manager_lg
Description: Maintains global application state, manages state transitions, and ensures state consistency across modules
Phase: 1
Location: /src/modules/logic/state_management_lg/app_state_manager_lg/app_state_manager_lg.py
"""

# Standard library imports
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
import logging

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppState


class ApplicationStateType(Enum):
    """Application state types."""
    INITIALIZING = "INITIALIZING"
    IDLE = "IDLE"
    PROCESSING_DOCUMENTS = "PROCESSING_DOCUMENTS"
    TRAINING_MODEL = "TRAINING_MODEL"
    LOADING_MODEL = "LOADING_MODEL"
    INFERENCING = "INFERENCING"
    OPTIMIZING = "OPTIMIZING"
    ERROR = "ERROR"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class StateTransitionType(Enum):
    """State transition types."""
    STARTUP_COMPLETE = "STARTUP_COMPLETE"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    TRAINING_START = "TRAINING_START"
    TRAINING_COMPLETE = "TRAINING_COMPLETE"
    CHAT_ACTIVATE = "CHAT_ACTIVATE"
    INFERENCE_START = "INFERENCE_START"
    INFERENCE_COMPLETE = "INFERENCE_COMPLETE"
    OPTIMIZATION_START = "OPTIMIZATION_START"
    OPTIMIZATION_COMPLETE = "OPTIMIZATION_COMPLETE"
    ERROR_OCCURRED = "ERROR_OCCURRED"
    ERROR_RECOVERED = "ERROR_RECOVERED"
    SHUTDOWN_INITIATED = "SHUTDOWN_INITIATED"


@dataclass
class StateTransition:
    """State transition definition."""
    from_state: ApplicationStateType
    to_state: ApplicationStateType
    trigger: StateTransitionType
    condition: Optional[Callable[[], bool]] = None
    action: Optional[Callable[[], None]] = None


@dataclass
class ApplicationState:
    """Enhanced application state structure."""
    # Core state
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_state: ApplicationStateType = ApplicationStateType.INITIALIZING
    previous_state: Optional[ApplicationStateType] = None
    state_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Session information
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    startup_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Application context
    active_project: Optional[Dict[str, Any]] = None
    loaded_models: List[str] = field(default_factory=list)
    resource_allocation: Dict[str, Any] = field(default_factory=dict)
    ui_state: Dict[str, Any] = field(default_factory=dict)
    background_tasks: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # State metadata
    transition_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Flags
    is_initialized: bool = False
    is_shutting_down: bool = False
    recovery_mode: bool = False


@dataclass
class StateValidator:
    """State validation configuration."""
    validate_transitions: bool = True
    validate_conditions: bool = True
    strict_mode: bool = False
    allowed_states: Optional[Set[ApplicationStateType]] = None


@dataclass
class StateManagerConfiguration:
    """Configuration for state manager."""
    enable_history: bool = True
    max_history_entries: int = 1000
    enable_validation: bool = True
    enable_observers: bool = True
    auto_save_interval: float = 60.0  # seconds
    state_timeout: float = 300.0  # 5 minutes
    validator: StateValidator = field(default_factory=StateValidator)


@dataclass
class StateManagerMetrics:
    """Metrics for state manager operations."""
    total_transitions: int = 0
    successful_transitions: int = 0
    failed_transitions: int = 0
    validation_errors: int = 0
    observer_notifications: int = 0
    state_changes_per_minute: float = 0.0
    average_transition_time: float = 0.0
    uptime_seconds: float = 0.0


@dataclass
class StateManagerResult:
    """Result of state manager operations."""
    success: bool
    message: str
    state_id: Optional[str] = None
    previous_state: Optional[ApplicationStateType] = None
    current_state: Optional[ApplicationStateType] = None
    transition_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class AppStateManager:
    """
    Enhanced application state manager for centralized state control.

    Manages global application state including state transitions, validation,
    observer pattern, and state consistency across modules.
    """

    def __init__(self, configuration: Optional[StateManagerConfiguration] = None):
        """Initialize the enhanced application state manager."""
        self._config = configuration or StateManagerConfiguration()
        self._state = ApplicationState()
        self._lock = threading.RLock()
        self._observers: List[Callable[[ApplicationState], None]] = []
        self._state_observers: Dict[ApplicationStateType, List[Callable]] = {}
        self._transitions: Dict[ApplicationStateType, List[StateTransition]] = {}
        self._metrics = StateManagerMetrics()
        self._logger = logging.getLogger(__name__)

        # Add missing attributes expected by other modules
        self.thresholds = None  # Will be set by monitoring modules
        self.historical_window_hours = 24  # Default historical window
        self.initial_batch_size = 32  # Default initial batch size
        self.max_history_size = 1000  # Default max history size

        # Initialize state transitions
        self._initialize_state_transitions()

        # Start metrics tracking
        self._start_time = datetime.now(timezone.utc)

    def _initialize_state_transitions(self) -> None:
        """Initialize valid state transitions."""
        transitions = [
            # Startup transitions
            StateTransition(
                ApplicationStateType.INITIALIZING,
                ApplicationStateType.IDLE,
                StateTransitionType.STARTUP_COMPLETE
            ),

            # Document processing transitions
            StateTransition(
                ApplicationStateType.IDLE,
                ApplicationStateType.PROCESSING_DOCUMENTS,
                StateTransitionType.DOCUMENT_UPLOAD
            ),
            StateTransition(
                ApplicationStateType.PROCESSING_DOCUMENTS,
                ApplicationStateType.IDLE,
                StateTransitionType.TRAINING_COMPLETE
            ),

            # Training transitions
            StateTransition(
                ApplicationStateType.IDLE,
                ApplicationStateType.TRAINING_MODEL,
                StateTransitionType.TRAINING_START
            ),
            StateTransition(
                ApplicationStateType.TRAINING_MODEL,
                ApplicationStateType.IDLE,
                StateTransitionType.TRAINING_COMPLETE
            ),

            # Inference transitions
            StateTransition(
                ApplicationStateType.IDLE,
                ApplicationStateType.LOADING_MODEL,
                StateTransitionType.CHAT_ACTIVATE
            ),
            StateTransition(
                ApplicationStateType.LOADING_MODEL,
                ApplicationStateType.INFERENCING,
                StateTransitionType.INFERENCE_START
            ),
            StateTransition(
                ApplicationStateType.INFERENCING,
                ApplicationStateType.IDLE,
                StateTransitionType.INFERENCE_COMPLETE
            ),

            # Optimization transitions
            StateTransition(
                ApplicationStateType.IDLE,
                ApplicationStateType.OPTIMIZING,
                StateTransitionType.OPTIMIZATION_START
            ),
            StateTransition(
                ApplicationStateType.OPTIMIZING,
                ApplicationStateType.IDLE,
                StateTransitionType.OPTIMIZATION_COMPLETE
            ),

            # Error transitions (from any state)
            StateTransition(
                ApplicationStateType.IDLE,
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED
            ),
            StateTransition(
                ApplicationStateType.PROCESSING_DOCUMENTS,
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED
            ),
            StateTransition(
                ApplicationStateType.TRAINING_MODEL,
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED
            ),
            StateTransition(
                ApplicationStateType.LOADING_MODEL,
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED
            ),
            StateTransition(
                ApplicationStateType.INFERENCING,
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED
            ),
            StateTransition(
                ApplicationStateType.OPTIMIZING,
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED
            ),

            # Recovery transitions
            StateTransition(
                ApplicationStateType.ERROR,
                ApplicationStateType.IDLE,
                StateTransitionType.ERROR_RECOVERED
            ),

            # Shutdown transitions (from any state)
            StateTransition(
                ApplicationStateType.IDLE,
                ApplicationStateType.SHUTTING_DOWN,
                StateTransitionType.SHUTDOWN_INITIATED
            ),
            StateTransition(
                ApplicationStateType.ERROR,
                ApplicationStateType.SHUTTING_DOWN,
                StateTransitionType.SHUTDOWN_INITIATED
            )
        ]

        # Group transitions by from_state
        for transition in transitions:
            if transition.from_state not in self._transitions:
                self._transitions[transition.from_state] = []
            self._transitions[transition.from_state].append(transition)

    def get_state(self) -> ApplicationState:
        """
        Get current application state.

        Returns:
            Current application state
        """
        with self._lock:
            return self._state

    def get_current_state_type(self) -> ApplicationStateType:
        """
        Get current state type.

        Returns:
            Current state type
        """
        with self._lock:
            return self._state.current_state

    def transition_to_state(
        self,
        new_state: ApplicationStateType,
        trigger: StateTransitionType,
        context: Optional[Dict[str, Any]] = None
    ) -> StateManagerResult:
        """
        Transition to a new state with validation.

        Args:
            new_state: Target state
            trigger: Transition trigger
            context: Additional context data

        Returns:
            Result of the transition operation
        """
        start_time = datetime.now(timezone.utc)

        with self._lock:
            try:
                current_state = self._state.current_state

                # Validate transition
                if self._config.enable_validation:
                    validation_result = self._validate_transition(current_state, new_state, trigger)
                    if not validation_result.success:
                        self._metrics.failed_transitions += 1
                        self._metrics.validation_errors += 1
                        return validation_result

                # Execute transition
                previous_state = self._state.current_state
                self._state.previous_state = previous_state
                self._state.current_state = new_state
                self._state.state_timestamp = start_time
                self._state.transition_count += 1

                # Update state history
                if self._config.enable_history:
                    self._add_to_history(previous_state, new_state, trigger, context)

                # Execute transition action if defined
                transition = self._find_transition(previous_state, new_state, trigger)
                if transition and transition.action:
                    try:
                        transition.action()
                    except Exception as e:
                        self._logger.warning(f"Transition action failed: {e}")

                # Notify observers
                if self._config.enable_observers:
                    self._notify_observers()
                    self._notify_state_observers(new_state)

                # Update metrics
                transition_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self._metrics.total_transitions += 1
                self._metrics.successful_transitions += 1
                self._update_transition_metrics(transition_time)

                self._logger.info(f"State transition: {previous_state.value} -> {new_state.value}")

                return StateManagerResult(
                    success=True,
                    message=f"Successfully transitioned from {previous_state.value} to {new_state.value}",
                    state_id=self._state.state_id,
                    previous_state=previous_state,
                    current_state=new_state,
                    transition_time=transition_time
                )

            except Exception as e:
                self._metrics.failed_transitions += 1
                error_msg = f"State transition failed: {e}"
                self._logger.error(error_msg)

                return StateManagerResult(
                    success=False,
                    message=error_msg,
                    errors=[str(e)]
                )

    def _validate_transition(
        self,
        from_state: ApplicationStateType,
        to_state: ApplicationStateType,
        trigger: StateTransitionType
    ) -> StateManagerResult:
        """Validate state transition."""
        try:
            # Check if transition is allowed
            if from_state not in self._transitions:
                return StateManagerResult(
                    success=False,
                    message=f"No transitions defined from state {from_state.value}"
                )

            # Find matching transition
            transition = self._find_transition(from_state, to_state, trigger)
            if not transition:
                return StateManagerResult(
                    success=False,
                    message=f"Invalid transition: {from_state.value} -> {to_state.value} with trigger {trigger.value}"
                )

            # Check transition condition
            if transition.condition and not transition.condition():
                return StateManagerResult(
                    success=False,
                    message=f"Transition condition not met for {from_state.value} -> {to_state.value}"
                )

            # Check validator constraints
            validator = self._config.validator
            if validator.allowed_states and to_state not in validator.allowed_states:
                return StateManagerResult(
                    success=False,
                    message=f"State {to_state.value} not in allowed states"
                )

            return StateManagerResult(success=True, message="Transition validation passed")

        except Exception as e:
            return StateManagerResult(
                success=False,
                message=f"Validation error: {e}",
                errors=[str(e)]
            )

    def _find_transition(
        self,
        from_state: ApplicationStateType,
        to_state: ApplicationStateType,
        trigger: StateTransitionType
    ) -> Optional[StateTransition]:
        """Find matching transition."""
        if from_state not in self._transitions:
            return None

        for transition in self._transitions[from_state]:
            if transition.to_state == to_state and transition.trigger == trigger:
                return transition

        return None

    def _add_to_history(
        self,
        from_state: ApplicationStateType,
        to_state: ApplicationStateType,
        trigger: StateTransitionType,
        context: Optional[Dict[str, Any]]
    ) -> None:
        """Add transition to state history."""
        history_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'from_state': from_state.value,
            'to_state': to_state.value,
            'trigger': trigger.value,
            'context': context or {}
        }

        self._state.state_history.append(history_entry)

        # Limit history size
        if len(self._state.state_history) > self._config.max_history_entries:
            self._state.state_history = self._state.state_history[-self._config.max_history_entries:]

    def add_observer(self, callback: Callable[[ApplicationState], None]) -> None:
        """
        Add state change observer.

        Args:
            callback: Function to call on state changes
        """
        with self._lock:
            if callback not in self._observers:
                self._observers.append(callback)

    def remove_observer(self, callback: Callable[[ApplicationState], None]) -> None:
        """
        Remove state change observer.

        Args:
            callback: Function to remove from observers
        """
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def add_state_observer(
        self,
        state: ApplicationStateType,
        callback: Callable[[ApplicationState], None]
    ) -> None:
        """
        Add observer for specific state.

        Args:
            state: State to observe
            callback: Function to call when entering this state
        """
        with self._lock:
            if state not in self._state_observers:
                self._state_observers[state] = []
            if callback not in self._state_observers[state]:
                self._state_observers[state].append(callback)

    def _notify_observers(self) -> None:
        """Notify all general observers of state changes."""
        for observer in self._observers:
            try:
                observer(self._state)
                self._metrics.observer_notifications += 1
            except Exception as e:
                self._logger.warning(f"Observer notification failed: {e}")

    def _notify_state_observers(self, state: ApplicationStateType) -> None:
        """Notify state-specific observers."""
        if state in self._state_observers:
            for observer in self._state_observers[state]:
                try:
                    observer(self._state)
                    self._metrics.observer_notifications += 1
                except Exception as e:
                    self._logger.warning(f"State observer notification failed: {e}")

    def _update_transition_metrics(self, transition_time: float) -> None:
        """Update transition timing metrics."""
        total_time = self._metrics.average_transition_time * (self._metrics.successful_transitions - 1)
        self._metrics.average_transition_time = (total_time + transition_time) / self._metrics.successful_transitions

        # Update transitions per minute
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        self._metrics.uptime_seconds = uptime
        if uptime > 0:
            self._metrics.state_changes_per_minute = (self._metrics.total_transitions / uptime) * 60

    def update_context(self, **kwargs) -> None:
        """
        Update application context.

        Args:
            **kwargs: Context properties to update
        """
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._notify_observers()

    def set_error(self, error_message: str) -> StateManagerResult:
        """
        Set error state with message.

        Args:
            error_message: Error description

        Returns:
            Result of error state transition
        """
        with self._lock:
            self._state.error_count += 1
            self._state.last_error = error_message

            return self.transition_to_state(
                ApplicationStateType.ERROR,
                StateTransitionType.ERROR_OCCURRED,
                {'error_message': error_message}
            )

    def clear_error(self) -> StateManagerResult:
        """
        Clear error state and return to idle.

        Returns:
            Result of error recovery transition
        """
        return self.transition_to_state(
            ApplicationStateType.IDLE,
            StateTransitionType.ERROR_RECOVERED
        )

    def get_metrics(self) -> StateManagerMetrics:
        """
        Get state manager metrics.

        Returns:
            Current metrics
        """
        with self._lock:
            # Update uptime
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            self._metrics.uptime_seconds = uptime
            return self._metrics

    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get state transition history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of state history entries
        """
        with self._lock:
            history = self._state.state_history
            if limit:
                return history[-limit:]
            return history.copy()

    def is_in_state(self, state: ApplicationStateType) -> bool:
        """
        Check if currently in specified state.

        Args:
            state: State to check

        Returns:
            True if in specified state
        """
        with self._lock:
            return self._state.current_state == state

    def can_transition_to(self, state: ApplicationStateType, trigger: StateTransitionType) -> bool:
        """
        Check if transition to state is valid.

        Args:
            state: Target state
            trigger: Transition trigger

        Returns:
            True if transition is valid
        """
        with self._lock:
            validation_result = self._validate_transition(
                self._state.current_state,
                state,
                trigger
            )
            return validation_result.success

    def set_initialized(self, initialized: bool = True) -> None:
        """
        Set application initialization status.

        Args:
            initialized: Initialization status
        """
        with self._lock:
            self._state.is_initialized = initialized
            self._notify_observers()

    def is_initialized(self) -> bool:
        """
        Check if application is initialized.

        Returns:
            True if initialized, False otherwise
        """
        with self._lock:
            return self._state.is_initialized

    def reset_state(self) -> None:
        """Reset state manager to initial state."""
        with self._lock:
            self._state = ApplicationState()
            self._metrics = StateManagerMetrics()
            self._start_time = datetime.now(timezone.utc)
            self._logger.info("State manager reset to initial state")
