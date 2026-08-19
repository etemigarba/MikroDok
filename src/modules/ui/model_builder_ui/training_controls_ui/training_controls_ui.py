"""
Module: training_controls_ui
Description: Streamlined training control interface for model builder workflow.
            Provides essential training controls (start/stop/pause/resume) with status monitoring,
            session management, and progress tracking. Designed specifically for the model building
            workflow with responsive design, theme integration, and seamless integration with
            training orchestration system.
Phase: 4
Location: /src/modules/ui/model_builder_ui/training_controls_ui/training_controls_ui.py
"""

# Standard library imports
import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)

# Training orchestration imports
try:
    from src.modules.logic.training_orchestration_lg.base_interfaces import (
        TrainingStatus,
        TrainingSession,
        TrainingConfig,
        TrainingMetrics,
        ISessionManager,
        ITrainingExecutor,
        ITrainingScheduler
    )
    TRAINING_ORCHESTRATION_AVAILABLE = True
except ImportError:
    TrainingStatus = None
    TrainingSession = None
    TrainingConfig = None
    TrainingMetrics = None
    ISessionManager = None
    ITrainingExecutor = None
    ITrainingScheduler = None
    TRAINING_ORCHESTRATION_AVAILABLE = False

# Resource monitoring imports
try:
    from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import (
        HardwareMonitor, ResourceMetrics
    )
    RESOURCE_MONITORING_AVAILABLE = True
except ImportError:
    HardwareMonitor = None
    ResourceMetrics = None
    RESOURCE_MONITORING_AVAILABLE = False


class TrainingControlState(Enum):
    """Training control states for model builder."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ERROR = "error"


class TrainingControlAction(Enum):
    """Training control actions."""
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RESET = "reset"


@dataclass
class TrainingControlsConfig:
    """Configuration for training controls UI."""
    show_progress_bar: bool = True
    show_time_estimates: bool = True
    show_resource_usage: bool = True
    enable_pause_resume: bool = True
    enable_stop_confirmation: bool = True
    auto_refresh_interval: float = 1.0
    compact_mode: bool = False
    show_advanced_controls: bool = False


@dataclass
class TrainingProgressData:
    """Training progress data for display."""
    current_epoch: int = 0
    total_epochs: int = 0
    current_step: int = 0
    total_steps: int = 0
    progress_percentage: float = 0.0
    elapsed_time: timedelta = field(default_factory=lambda: timedelta())
    estimated_remaining: Optional[timedelta] = None
    current_loss: Optional[float] = None
    learning_rate: Optional[float] = None
    status_message: str = ""


class TrainingControlsUI(ThemeAwareUserControl):
    """
    Streamlined training control interface for model builder workflow.
    
    Features:
    - Essential training controls (start/stop/pause/resume)
    - Real-time progress monitoring with progress bar
    - Training status display with time estimates
    - Resource usage monitoring (optional)
    - Responsive design with theme integration
    - Integration with training orchestration system
    - Compact and expanded view modes
    - Session management capabilities
    """

    def __init__(self,
                 config: Optional[TrainingControlsConfig] = None,
                 session_manager: Optional[ISessionManager] = None,
                 training_executor: Optional[ITrainingExecutor] = None,
                 hardware_monitor: Optional[HardwareMonitor] = None,
                 on_action: Optional[Callable[[TrainingControlAction, Dict[str, Any]], None]] = None,
                 **kwargs):
        """
        Initialize the training controls UI.

        Args:
            config: Training controls configuration
            session_manager: Training session manager interface
            training_executor: Training executor interface
            hardware_monitor: Hardware monitor for resource usage
            on_action: Callback for control actions
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or TrainingControlsConfig()
        
        # External dependencies
        self._session_manager = session_manager
        self._training_executor = training_executor
        self._hardware_monitor = hardware_monitor
        self._on_action = on_action
        
        # State management
        self._current_state = TrainingControlState.IDLE
        self._current_session: Optional[TrainingSession] = None
        self._progress_data = TrainingProgressData()
        self._start_time: Optional[datetime] = None
        
        # UI components
        self._control_buttons: Dict[str, ft.Control] = {}
        self._status_display: Optional[ft.Container] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._progress_text: Optional[ft.Text] = None
        self._time_display: Optional[ft.Text] = None
        self._resource_display: Optional[ft.Container] = None
        
        # Update timer
        self._update_timer: Optional[asyncio.Task] = None
        self._is_updating = False
        
        # Logging
        self._logger = logging.getLogger(__name__)
        
        # Initialize UI
        self._initialize_ui()

    def _initialize_ui(self) -> None:
        """Initialize the user interface."""
        try:
            self._create_control_buttons()
            self._create_status_display()
            self._create_progress_display()
            if self._config.show_resource_usage:
                self._create_resource_display()
            
            self._build_layout()
            self._update_button_states()
            
        except Exception as ex:
            self._logger.error(f"Failed to initialize training controls UI: {ex}")
            self._show_error_state(f"Initialization failed: {ex}")

    def _create_control_buttons(self) -> None:
        """Create training control buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()
        
        button_height = rlm.get_breakpoint_value(36, 40, 44, 48)
        button_width = rlm.get_breakpoint_value(80, 100, 120, 140)
        
        # Start button
        self._control_buttons['start'] = ft.ElevatedButton(
            text="Start",
            icon=self.get_icon('PLAY_ARROW'),
            on_click=self._on_start_clicked,
            height=button_height,
            width=button_width,
            style=ft.ButtonStyle(
                bgcolor=palette.success,
                color=palette.text_primary
            )
        )
        
        # Pause button
        self._control_buttons['pause'] = ft.ElevatedButton(
            text="Pause",
            icon=self.get_icon('PAUSE'),
            on_click=self._on_pause_clicked,
            height=button_height,
            width=button_width,
            style=ft.ButtonStyle(
                bgcolor=palette.warning,
                color=palette.text_primary
            )
        )
        
        # Resume button
        self._control_buttons['resume'] = ft.ElevatedButton(
            text="Resume",
            icon=self.get_icon('PLAY_ARROW'),
            on_click=self._on_resume_clicked,
            height=button_height,
            width=button_width,
            style=ft.ButtonStyle(
                bgcolor=palette.success,
                color=palette.text_primary
            )
        )
        
        # Stop button
        self._control_buttons['stop'] = ft.ElevatedButton(
            text="Stop",
            icon=self.get_icon('STOP'),
            on_click=self._on_stop_clicked,
            height=button_height,
            width=button_width,
            style=ft.ButtonStyle(
                bgcolor=palette.error,
                color=palette.text_primary
            )
        )
        
        # Reset button
        self._control_buttons['reset'] = ft.OutlinedButton(
            text="Reset",
            icon=self.get_icon('REFRESH'),
            on_click=self._on_reset_clicked,
            height=button_height,
            width=button_width,
            style=ft.ButtonStyle(
                color=palette.text_secondary
            )
        )

    def _create_status_display(self) -> None:
        """Create status display component."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        status_text = ft.Text(
            value="Ready to start training",
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        status_icon = ft.Icon(
            name=self.get_icon('CIRCLE'),
            color=palette.text_secondary,
            size=12
        )

        self._status_display = ft.Container(
            content=ft.Row(
                controls=[
                    status_icon,
                    status_text
                ],
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=spacing.sm,
            border_radius=spacing.xs,
            bgcolor=palette.surface_variant,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_progress_display(self) -> None:
        """Create progress display components."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        if self._config.show_progress_bar:
            self._progress_bar = ft.ProgressBar(
                value=0.0,
                color=palette.primary,
                bgcolor=palette.surface_variant,
                height=spacing.xs
            )

        self._progress_text = ft.Text(
            value="0% (0/0 epochs, 0/0 steps)",
            style=typography.body_small,
            color=palette.text_secondary
        )

        if self._config.show_time_estimates:
            self._time_display = ft.Text(
                value="Elapsed: 00:00:00 | Remaining: --:--:--",
                style=typography.body_small,
                color=palette.text_secondary
            )

    def _create_resource_display(self) -> None:
        """Create resource usage display."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        cpu_text = ft.Text(
            value="CPU: 0%",
            style=typography.body_small,
            color=palette.text_secondary
        )

        memory_text = ft.Text(
            value="Memory: 0%",
            style=typography.body_small,
            color=palette.text_secondary
        )

        gpu_text = ft.Text(
            value="GPU: 0%",
            style=typography.body_small,
            color=palette.text_secondary
        )

        self._resource_display = ft.Container(
            content=ft.Row(
                controls=[cpu_text, memory_text, gpu_text],
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            ),
            padding=spacing.sm,
            border_radius=spacing.xs,
            bgcolor=palette.surface_variant,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _build_layout(self) -> None:
        """Build the main layout."""
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Control buttons row
        control_buttons = [
            self._control_buttons['start'],
            self._control_buttons['pause'],
            self._control_buttons['resume'],
            self._control_buttons['stop'],
            self._control_buttons['reset']
        ]

        buttons_row = ft.Row(
            controls=control_buttons,
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START,
            wrap=True
        )

        # Progress section
        progress_controls = []
        if self._status_display:
            progress_controls.append(self._status_display)

        if self._progress_bar:
            progress_controls.append(self._progress_bar)

        if self._progress_text:
            progress_controls.append(self._progress_text)

        if self._time_display:
            progress_controls.append(self._time_display)

        progress_column = ft.Column(
            controls=progress_controls,
            spacing=spacing.sm,
            tight=True
        )

        # Main content
        main_controls = [buttons_row, progress_column]

        if self._resource_display:
            main_controls.append(self._resource_display)

        main_column = ft.Column(
            controls=main_controls,
            spacing=spacing.md,
            tight=True
        )

        # Set container content
        self.content = main_column
        self.padding = spacing.md
        self.border_radius = spacing.sm

    # Public Methods
    def start_training(self, session: Optional[TrainingSession] = None) -> None:
        """
        Start training with optional session.

        Args:
            session: Training session to start
        """
        try:
            self._current_session = session
            self._current_state = TrainingControlState.INITIALIZING
            self._start_time = datetime.now()
            self._update_button_states()
            self._update_displays()
            self._start_update_timer()

            if self._on_action:
                asyncio.create_task(self._on_action(TrainingControlAction.START, {
                    'session': session
                }))

        except Exception as ex:
            self._logger.error(f"Failed to start training: {ex}")
            self._show_error_state(f"Failed to start training: {ex}")

    def pause_training(self) -> None:
        """Pause current training session."""
        try:
            if self._current_state == TrainingControlState.RUNNING:
                self._current_state = TrainingControlState.PAUSED
                self._update_button_states()
                self._update_displays()

                if self._on_action:
                    asyncio.create_task(self._on_action(TrainingControlAction.PAUSE, {}))

        except Exception as ex:
            self._logger.error(f"Failed to pause training: {ex}")

    def resume_training(self) -> None:
        """Resume paused training session."""
        try:
            if self._current_state == TrainingControlState.PAUSED:
                self._current_state = TrainingControlState.RUNNING
                self._update_button_states()
                self._update_displays()

                if self._on_action:
                    asyncio.create_task(self._on_action(TrainingControlAction.RESUME, {}))

        except Exception as ex:
            self._logger.error(f"Failed to resume training: {ex}")

    def stop_training(self) -> None:
        """Stop current training session."""
        try:
            if self._current_state in [TrainingControlState.RUNNING, TrainingControlState.PAUSED]:
                self._current_state = TrainingControlState.STOPPING
                self._update_button_states()
                self._update_displays()
                self._stop_update_timer()

                if self._on_action:
                    asyncio.create_task(self._on_action(TrainingControlAction.STOP, {}))

        except Exception as ex:
            self._logger.error(f"Failed to stop training: {ex}")

    def reset_training(self) -> None:
        """Reset training state to idle."""
        try:
            self._current_state = TrainingControlState.IDLE
            self._current_session = None
            self._progress_data = TrainingProgressData()
            self._start_time = None
            self._stop_update_timer()
            self._update_button_states()
            self._update_displays()

            if self._on_action:
                asyncio.create_task(self._on_action(TrainingControlAction.RESET, {}))

        except Exception as ex:
            self._logger.error(f"Failed to reset training: {ex}")

    def update_progress(self, progress_data: TrainingProgressData) -> None:
        """
        Update training progress data.

        Args:
            progress_data: New progress data
        """
        try:
            self._progress_data = progress_data
            self._update_displays()

        except Exception as ex:
            self._logger.error(f"Failed to update progress: {ex}")

    def set_training_state(self, state: TrainingControlState) -> None:
        """
        Set training state.

        Args:
            state: New training state
        """
        try:
            self._current_state = state
            self._update_button_states()
            self._update_displays()

            if state == TrainingControlState.COMPLETED:
                self._stop_update_timer()
            elif state == TrainingControlState.RUNNING and not self._update_timer:
                self._start_update_timer()

        except Exception as ex:
            self._logger.error(f"Failed to set training state: {ex}")

    # Event Handlers
    async def _on_start_clicked(self, e) -> None:
        """Handle start button click."""
        try:
            self.start_training()
        except Exception as ex:
            self._logger.error(f"Start button click failed: {ex}")

    async def _on_pause_clicked(self, e) -> None:
        """Handle pause button click."""
        try:
            self.pause_training()
        except Exception as ex:
            self._logger.error(f"Pause button click failed: {ex}")

    async def _on_resume_clicked(self, e) -> None:
        """Handle resume button click."""
        try:
            self.resume_training()
        except Exception as ex:
            self._logger.error(f"Resume button click failed: {ex}")

    async def _on_stop_clicked(self, e) -> None:
        """Handle stop button click."""
        try:
            if self._config.enable_stop_confirmation:
                # Show confirmation dialog
                confirmed = await self._show_confirmation_dialog(
                    "Stop Training",
                    "Are you sure you want to stop the current training session?"
                )
                if not confirmed:
                    return

            self.stop_training()
        except Exception as ex:
            self._logger.error(f"Stop button click failed: {ex}")

    async def _on_reset_clicked(self, e) -> None:
        """Handle reset button click."""
        try:
            self.reset_training()
        except Exception as ex:
            self._logger.error(f"Reset button click failed: {ex}")

    # State Management
    def _update_button_states(self) -> None:
        """Update button enabled/disabled states based on current state."""
        try:
            state = self._current_state

            # Start button
            self._control_buttons['start'].disabled = state not in [
                TrainingControlState.IDLE, TrainingControlState.COMPLETED, TrainingControlState.ERROR
            ]

            # Pause button
            self._control_buttons['pause'].disabled = state != TrainingControlState.RUNNING

            # Resume button
            self._control_buttons['resume'].disabled = state != TrainingControlState.PAUSED

            # Stop button
            self._control_buttons['stop'].disabled = state not in [
                TrainingControlState.RUNNING, TrainingControlState.PAUSED
            ]

            # Reset button
            self._control_buttons['reset'].disabled = state in [
                TrainingControlState.INITIALIZING, TrainingControlState.STOPPING
            ]

            # Update button visibility
            self._control_buttons['pause'].visible = state == TrainingControlState.RUNNING
            self._control_buttons['resume'].visible = state == TrainingControlState.PAUSED

            # Update UI
            if hasattr(self, 'page') and self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to update button states: {ex}")

    def _update_displays(self) -> None:
        """Update all display components."""
        try:
            self._update_status_display()
            self._update_progress_display()
            self._update_time_display()
            if self._config.show_resource_usage:
                self._update_resource_display()

        except Exception as ex:
            self._logger.error(f"Failed to update displays: {ex}")

    def _update_status_display(self) -> None:
        """Update status display."""
        try:
            if not self._status_display:
                return

            palette = self.get_palette()
            state = self._current_state

            # Status messages and colors
            status_info = {
                TrainingControlState.IDLE: ("Ready to start training", palette.text_secondary, 'CIRCLE'),
                TrainingControlState.INITIALIZING: ("Initializing training...", palette.warning, 'HOURGLASS_EMPTY'),
                TrainingControlState.RUNNING: ("Training in progress", palette.success, 'PLAY_CIRCLE'),
                TrainingControlState.PAUSED: ("Training paused", palette.warning, 'PAUSE_CIRCLE'),
                TrainingControlState.STOPPING: ("Stopping training...", palette.warning, 'STOP_CIRCLE'),
                TrainingControlState.COMPLETED: ("Training completed", palette.success, 'CHECK_CIRCLE'),
                TrainingControlState.ERROR: ("Training error", palette.error, 'ERROR')
            }

            message, color, icon = status_info.get(state, ("Unknown state", palette.text_secondary, 'CIRCLE'))

            # Update status text and icon
            status_row = self._status_display.content
            if isinstance(status_row, ft.Row) and len(status_row.controls) >= 2:
                # Update icon
                status_row.controls[0].name = self.get_icon(icon)
                status_row.controls[0].color = color

                # Update text
                status_row.controls[1].value = message
                status_row.controls[1].color = palette.text_primary

            # Update UI
            if hasattr(self, 'page') and self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to update status display: {ex}")

    def _update_progress_display(self) -> None:
        """Update progress display."""
        try:
            progress = self._progress_data

            # Update progress bar
            if self._progress_bar:
                self._progress_bar.value = progress.progress_percentage / 100.0

            # Update progress text
            if self._progress_text:
                self._progress_text.value = (
                    f"{progress.progress_percentage:.1f}% "
                    f"({progress.current_epoch}/{progress.total_epochs} epochs, "
                    f"{progress.current_step}/{progress.total_steps} steps)"
                )

            # Update UI
            if hasattr(self, 'page') and self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to update progress display: {ex}")

    def _update_time_display(self) -> None:
        """Update time display."""
        try:
            if not self._time_display or not self._config.show_time_estimates:
                return

            progress = self._progress_data

            # Format elapsed time
            elapsed_str = self._format_timedelta(progress.elapsed_time)

            # Format remaining time
            if progress.estimated_remaining:
                remaining_str = self._format_timedelta(progress.estimated_remaining)
            else:
                remaining_str = "--:--:--"

            self._time_display.value = f"Elapsed: {elapsed_str} | Remaining: {remaining_str}"

            # Update UI
            if hasattr(self, 'page') and self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to update time display: {ex}")

    def _update_resource_display(self) -> None:
        """Update resource usage display."""
        try:
            if not self._resource_display or not self._hardware_monitor:
                return

            # Get resource metrics
            if RESOURCE_MONITORING_AVAILABLE:
                metrics = self._hardware_monitor.get_current_metrics()
                if metrics:
                    cpu_usage = metrics.cpu_usage_percent
                    memory_usage = metrics.memory_usage_percent
                    gpu_usage = metrics.gpu_usage_percent if hasattr(metrics, 'gpu_usage_percent') else 0
                else:
                    cpu_usage = memory_usage = gpu_usage = 0
            else:
                cpu_usage = memory_usage = gpu_usage = 0

            # Update resource texts
            resource_row = self._resource_display.content
            if isinstance(resource_row, ft.Row) and len(resource_row.controls) >= 3:
                resource_row.controls[0].value = f"CPU: {cpu_usage:.1f}%"
                resource_row.controls[1].value = f"Memory: {memory_usage:.1f}%"
                resource_row.controls[2].value = f"GPU: {gpu_usage:.1f}%"

            # Update UI
            if hasattr(self, 'page') and self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to update resource display: {ex}")

    # Timer Management
    def _start_update_timer(self) -> None:
        """Start the update timer."""
        try:
            if self._update_timer and not self._update_timer.done():
                return

            self._is_updating = True
            self._update_timer = asyncio.create_task(self._update_loop())

        except Exception as ex:
            self._logger.error(f"Failed to start update timer: {ex}")

    def _stop_update_timer(self) -> None:
        """Stop the update timer."""
        try:
            self._is_updating = False
            if self._update_timer and not self._update_timer.done():
                self._update_timer.cancel()

        except Exception as ex:
            self._logger.error(f"Failed to stop update timer: {ex}")

    async def _update_loop(self) -> None:
        """Main update loop."""
        try:
            while self._is_updating:
                # Update elapsed time
                if self._start_time and self._current_state == TrainingControlState.RUNNING:
                    self._progress_data.elapsed_time = datetime.now() - self._start_time

                # Update displays
                self._update_displays()

                # Wait for next update
                await asyncio.sleep(self._config.auto_refresh_interval)

        except asyncio.CancelledError:
            pass
        except Exception as ex:
            self._logger.error(f"Update loop error: {ex}")

    # Utility Methods
    def _format_timedelta(self, td: timedelta) -> str:
        """
        Format timedelta as HH:MM:SS.

        Args:
            td: Timedelta to format

        Returns:
            Formatted time string
        """
        try:
            total_seconds = int(td.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            return "00:00:00"

    def _show_error_state(self, message: str) -> None:
        """
        Show error state.

        Args:
            message: Error message to display
        """
        try:
            self._current_state = TrainingControlState.ERROR
            self._progress_data.status_message = message
            self._update_button_states()
            self._update_displays()

        except Exception as ex:
            self._logger.error(f"Failed to show error state: {ex}")

    async def _show_confirmation_dialog(self, title: str, message: str) -> bool:
        """
        Show confirmation dialog.

        Args:
            title: Dialog title
            message: Dialog message

        Returns:
            True if confirmed, False otherwise
        """
        try:
            # Simple confirmation for now - in a real implementation,
            # this would show a proper dialog
            return True

        except Exception as ex:
            self._logger.error(f"Failed to show confirmation dialog: {ex}")
            return False

    # Theme Integration
    def on_theme_changed(self) -> None:
        """Handle theme change events."""
        try:
            super().on_theme_changed()

            # Recreate UI components with new theme
            self._create_control_buttons()
            self._create_status_display()
            self._create_progress_display()
            if self._config.show_resource_usage:
                self._create_resource_display()

            self._build_layout()
            self._update_button_states()
            self._update_displays()

        except Exception as ex:
            self._logger.error(f"Failed to handle theme change: {ex}")

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self._stop_update_timer()
            self._is_updating = False

        except Exception as ex:
            self._logger.error(f"Failed to cleanup: {ex}")
