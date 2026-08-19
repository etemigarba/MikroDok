"""
Module: control_panel_ui
Description: Training control panel with real-time controls for managing training sessions.
            Provides comprehensive training control interface with start/stop/pause/resume functionality,
            status monitoring, session management, and resource control. Features responsive design with
            breakpoint-aware layouts, theme integration, and seamless integration with training orchestration.
Phase: 4
Location: /src/modules/ui/training_monitor_ui/control_panel_ui/control_panel_ui.py
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
    """Training control panel states."""
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
    EMERGENCY_STOP = "emergency_stop"
    RESTART = "restart"


class SessionControlAction(Enum):
    """Session control actions."""
    SAVE_SESSION = "save_session"
    LOAD_SESSION = "load_session"
    NEW_SESSION = "new_session"
    DELETE_SESSION = "delete_session"
    EXPORT_SESSION = "export_session"


@dataclass
class ControlPanelConfiguration:
    """Configuration for control panel behavior."""
    auto_save_interval_minutes: int = 5
    show_resource_monitoring: bool = True
    show_advanced_controls: bool = False
    enable_emergency_stop: bool = True
    confirm_destructive_actions: bool = True
    update_interval_seconds: float = 1.0
    show_session_management: bool = True
    enable_real_time_metrics: bool = True
    max_log_entries: int = 1000
    theme_mode: str = "auto"


class ControlPanelUI(ThemeAwareUserControl):
    """
    Comprehensive training control panel UI component.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time training control with start/stop/pause/resume functionality
    - Training status monitoring with detailed session information
    - Resource monitoring and performance metrics display
    - Session management with save/load/export capabilities
    - Theme-aware styling with accessibility compliance
    - Integration with training orchestration system
    - Emergency stop functionality for critical situations
    - Advanced controls for experienced users
    - Real-time logging and status updates
    - Cross-platform compatibility and offline operation
    """

    def __init__(self,
                 config: Optional[ControlPanelConfiguration] = None,
                 session_manager: Optional[ISessionManager] = None,
                 training_executor: Optional[ITrainingExecutor] = None,
                 training_scheduler: Optional[ITrainingScheduler] = None,
                 on_action: Optional[Callable[[TrainingControlAction, Dict[str, Any]], None]] = None,
                 **kwargs):
        """
        Initialize the control panel UI.

        Args:
            config: Control panel configuration
            session_manager: Training session manager interface
            training_executor: Training executor interface
            training_scheduler: Training scheduler interface
            on_action: Callback for control actions
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or ControlPanelConfiguration()
        
        # Training orchestration interfaces
        self._session_manager = session_manager
        self._training_executor = training_executor
        self._training_scheduler = training_scheduler
        
        # Callbacks
        self._on_action = on_action
        
        # State management
        self._current_state = TrainingControlState.IDLE
        self._current_session: Optional[TrainingSession] = None
        self._last_metrics: Optional[TrainingMetrics] = None
        self._resource_metrics: Optional[ResourceMetrics] = None
        
        # UI components
        self._control_buttons: Dict[str, ft.Control] = {}
        self._status_indicators: Dict[str, ft.Control] = {}
        self._session_controls: Dict[str, ft.Control] = {}
        self._resource_displays: Dict[str, ft.Control] = {}
        
        # Update management
        self._update_timer: Optional[asyncio.Task] = None
        self._is_updating = False
        self._last_update_time = 0.0
        
        # Logging
        self._logger = logging.getLogger(__name__)
        self._log_entries: List[Tuple[datetime, str, str]] = []
        
        # Initialize components
        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize UI components."""
        self._create_control_buttons()
        self._create_status_indicators()
        self._create_session_controls()
        if self._config.show_resource_monitoring:
            self._create_resource_displays()

    def _create_control_buttons(self) -> None:
        """Create training control buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()
        
        button_height = rlm.get_breakpoint_value(36, 40, 44, 48)
        button_width = rlm.get_breakpoint_value(100, 120, 140, 160)
        
        # Start button
        self._control_buttons['start'] = ft.ElevatedButton(
            text="Start Training",
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
        
        # Emergency stop button (if enabled)
        if self._config.enable_emergency_stop:
            self._control_buttons['emergency_stop'] = ft.ElevatedButton(
                text="Emergency Stop",
                icon=self.get_icon('EMERGENCY'),
                on_click=self._on_emergency_stop_clicked,
                height=button_height,
                width=button_width,
                style=ft.ButtonStyle(
                    bgcolor=palette.error,
                    color=palette.text_primary
                )
            )

    def _create_status_indicators(self) -> None:
        """Create status indicator components."""
        palette = self.get_palette()
        typography = self.get_typography()
        
        # Training status indicator
        self._status_indicators['training_status'] = ft.Container(
            content=ft.Row([
                ft.Icon(
                    name=self.get_icon('CIRCLE'),
                    color=palette.text_secondary,
                    size=16
                ),
                ft.Text(
                    "Idle",
                    style=typography.body_medium,
                    color=palette.text_primary
                )
            ], spacing=8),
            padding=ft.padding.all(8),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )
        
        # Session info display
        self._status_indicators['session_info'] = ft.Container(
            content=ft.Column([
                ft.Text(
                    "No Active Session",
                    style=typography.body_medium,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Ready to start training",
                    style=typography.body_small,
                    color=palette.text_secondary
                )
            ], spacing=4),
            padding=ft.padding.all(8),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )
        
        # Progress indicator
        self._status_indicators['progress'] = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Progress: 0%",
                    style=typography.body_small,
                    color=palette.text_secondary
                ),
                ft.ProgressBar(
                    value=0.0,
                    bgcolor=palette.surface_variant,
                    color=palette.primary
                )
            ], spacing=4),
            padding=ft.padding.all(8),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _create_session_controls(self) -> None:
        """Create session management controls."""
        if not self._config.show_session_management:
            return
            
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Save session button
        self._session_controls['save'] = ft.IconButton(
            icon=self.get_icon('SAVE'),
            tooltip="Save current session",
            on_click=self._on_save_session_clicked,
            icon_color=palette.primary,
            icon_size=20
        )
        
        # Load session button
        self._session_controls['load'] = ft.IconButton(
            icon=self.get_icon('FOLDER_OPEN'),
            tooltip="Load session",
            on_click=self._on_load_session_clicked,
            icon_color=palette.primary,
            icon_size=20
        )
        
        # New session button
        self._session_controls['new'] = ft.IconButton(
            icon=self.get_icon('ADD'),
            tooltip="Create new session",
            on_click=self._on_new_session_clicked,
            icon_color=palette.primary,
            icon_size=20
        )
        
        # Export session button
        self._session_controls['export'] = ft.IconButton(
            icon=self.get_icon('DOWNLOAD'),
            tooltip="Export session data",
            on_click=self._on_export_session_clicked,
            icon_color=palette.primary,
            icon_size=20
        )

    def _create_resource_displays(self) -> None:
        """Create resource monitoring displays."""
        palette = self.get_palette()
        typography = self.get_typography()
        
        # CPU usage display
        self._resource_displays['cpu'] = ft.Container(
            content=ft.Column([
                ft.Text(
                    "CPU: 0%",
                    style=typography.body_small,
                    color=palette.text_secondary
                ),
                ft.ProgressBar(
                    value=0.0,
                    bgcolor=palette.surface_variant,
                    color=palette.primary
                )
            ], spacing=4),
            padding=ft.padding.all(8),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )
        
        # Memory usage display
        self._resource_displays['memory'] = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory: 0 MB",
                    style=typography.body_small,
                    color=palette.text_secondary
                ),
                ft.ProgressBar(
                    value=0.0,
                    bgcolor=palette.surface_variant,
                    color=palette.secondary
                )
            ], spacing=4),
            padding=ft.padding.all(8),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )
        
        # GPU usage display (if available)
        self._resource_displays['gpu'] = ft.Container(
            content=ft.Column([
                ft.Text(
                    "GPU: 0%",
                    style=typography.body_small,
                    color=palette.text_secondary
                ),
                ft.ProgressBar(
                    value=0.0,
                    bgcolor=palette.surface_variant,
                    color=palette.secondary
                )
            ], spacing=4),
            padding=ft.padding.all(8),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def build(self) -> ft.Control:
        """Build the control panel UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create header
        header = self._create_header()

        # Create main control section
        control_section = self._create_control_section()

        # Create status section
        status_section = self._create_status_section()

        # Create resource section (if enabled)
        resource_section = None
        if self._config.show_resource_monitoring:
            resource_section = self._create_resource_section()

        # Create session management section (if enabled)
        session_section = None
        if self._config.show_session_management:
            session_section = self._create_session_section()

        # Create log section
        log_section = self._create_log_section()

        # Arrange sections based on screen size
        sections = [header, control_section, status_section]

        if resource_section:
            sections.append(resource_section)

        if session_section:
            sections.append(session_section)

        sections.append(log_section)

        # Add spacing between sections
        content_with_spacing = []
        for i, section in enumerate(sections):
            content_with_spacing.append(section)
            if i < len(sections) - 1:
                content_with_spacing.append(ft.Container(height=spacing.md))

        return ft.Container(
            content=ft.Column(
                content_with_spacing,
                scroll=ft.ScrollMode.AUTO,
                spacing=0
            ),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_header(self) -> ft.Control:
        """Create control panel header."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row([
                ft.Icon(
                    name=self.get_icon('SETTINGS'),
                    color=palette.primary,
                    size=24
                ),
                ft.Text(
                    "Training Control Panel",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=self.get_icon('REFRESH'),
                    tooltip="Refresh status",
                    on_click=self._on_refresh_clicked,
                    icon_color=palette.text_secondary,
                    icon_size=20
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _create_control_section(self) -> ft.Control:
        """Create main control buttons section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get visible buttons based on current state
        visible_buttons = self._get_visible_buttons()

        # Create responsive button layout
        button_rows = []
        buttons_per_row = rlm.get_breakpoint_value(2, 3, 4, 5)

        current_row = []
        for button_key in visible_buttons:
            if button_key in self._control_buttons:
                current_row.append(self._control_buttons[button_key])

                if len(current_row) >= buttons_per_row:
                    button_rows.append(ft.Row(
                        current_row,
                        spacing=spacing.md,
                        alignment=ft.MainAxisAlignment.CENTER
                    ))
                    current_row = []

        # Add remaining buttons
        if current_row:
            button_rows.append(ft.Row(
                current_row,
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.CENTER
            ))

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Training Controls",
                    style=typography.title_medium,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                ft.Column(
                    button_rows,
                    spacing=spacing.sm
                )
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _create_status_section(self) -> ft.Control:
        """Create status monitoring section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Arrange status indicators responsively
        status_items = list(self._status_indicators.values())

        if rlm.is_mobile():
            # Stack vertically on mobile
            status_layout = ft.Column(
                status_items,
                spacing=spacing.sm
            )
        else:
            # Arrange in grid on larger screens
            cols = rlm.get_breakpoint_value(1, 2, 3, 3)
            status_layout = ft.GridView(
                controls=status_items,
                runs_count=cols,
                spacing=spacing.sm,
                run_spacing=spacing.sm,
                child_aspect_ratio=2.0,
                expand=False
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Training Status",
                    style=typography.title_medium,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                status_layout
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _create_resource_section(self) -> ft.Control:
        """Create resource monitoring section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Arrange resource displays responsively
        resource_items = list(self._resource_displays.values())

        if rlm.is_mobile():
            # Stack vertically on mobile
            resource_layout = ft.Column(
                resource_items,
                spacing=spacing.sm
            )
        else:
            # Arrange in grid on larger screens
            cols = rlm.get_breakpoint_value(1, 2, 3, 3)
            resource_layout = ft.GridView(
                controls=resource_items,
                runs_count=cols,
                spacing=spacing.sm,
                run_spacing=spacing.sm,
                child_aspect_ratio=2.5,
                expand=False
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Resource Monitoring",
                    style=typography.title_medium,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                resource_layout
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _create_session_section(self) -> ft.Control:
        """Create session management section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Arrange session controls in a row
        session_controls = list(self._session_controls.values())

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Session Management",
                    style=typography.title_medium,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                ft.Row(
                    session_controls,
                    spacing=spacing.md,
                    alignment=ft.MainAxisAlignment.CENTER
                )
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _create_log_section(self) -> ft.Control:
        """Create log display section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create log display
        log_height = rlm.get_breakpoint_value(120, 150, 180, 200)

        self._log_display = ft.ListView(
            controls=[],
            height=log_height,
            spacing=spacing.xs,
            padding=ft.padding.all(spacing.sm)
        )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "Activity Log",
                        style=typography.title_medium,
                        color=palette.text_primary
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=self.get_icon('CLEAR'),
                        tooltip="Clear log",
                        on_click=self._on_clear_log_clicked,
                        icon_color=palette.text_secondary,
                        icon_size=16
                    )
                ]),
                ft.Container(height=spacing.sm),
                ft.Container(
                    content=self._log_display,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(8),
                    border=ft.border.all(1, palette.borders)
                )
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _get_visible_buttons(self) -> List[str]:
        """Get list of buttons that should be visible based on current state."""
        if self._current_state == TrainingControlState.IDLE:
            buttons = ['start']
        elif self._current_state == TrainingControlState.INITIALIZING:
            buttons = ['stop']
        elif self._current_state == TrainingControlState.RUNNING:
            buttons = ['pause', 'stop']
            if self._config.enable_emergency_stop:
                buttons.append('emergency_stop')
        elif self._current_state == TrainingControlState.PAUSED:
            buttons = ['resume', 'stop']
        elif self._current_state == TrainingControlState.STOPPING:
            buttons = []  # No controls during stopping
        elif self._current_state == TrainingControlState.COMPLETED:
            buttons = ['start']  # Allow starting new training
        elif self._current_state == TrainingControlState.ERROR:
            buttons = ['start']  # Allow restarting after error
        else:
            buttons = ['start']

        return buttons

    def _update_button_states(self) -> None:
        """Update button enabled/disabled states based on current state."""
        visible_buttons = self._get_visible_buttons()

        for button_key, button in self._control_buttons.items():
            button.visible = button_key in visible_buttons

            # Update button text and icons based on state
            if button_key == 'start':
                if self._current_state == TrainingControlState.ERROR:
                    button.text = "Restart Training"
                    button.icon = self.get_icon('RESTART_ALT')
                else:
                    button.text = "Start Training"
                    button.icon = self.get_icon('PLAY_ARROW')

        # Update the UI
        if hasattr(self, 'page') and self.page:
            self.page.update()

    def _update_status_displays(self) -> None:
        """Update status indicator displays."""
        palette = self.get_palette()

        # Update training status indicator
        if 'training_status' in self._status_indicators:
            status_container = self._status_indicators['training_status']
            status_row = status_container.content

            # Update icon color based on state
            icon_colors = {
                TrainingControlState.IDLE: palette.text_secondary,
                TrainingControlState.INITIALIZING: palette.warning,
                TrainingControlState.RUNNING: palette.success,
                TrainingControlState.PAUSED: palette.warning,
                TrainingControlState.STOPPING: palette.error,
                TrainingControlState.COMPLETED: palette.success,
                TrainingControlState.ERROR: palette.error
            }

            status_row.controls[0].color = icon_colors.get(self._current_state, palette.text_secondary)
            status_row.controls[1].value = self._current_state.value.title()

        # Update session info
        if 'session_info' in self._status_indicators and self._current_session:
            session_container = self._status_indicators['session_info']
            session_column = session_container.content

            session_column.controls[0].value = f"Session: {self._current_session.session_id[:8]}..."

            if self._current_session.duration:
                duration_str = str(self._current_session.duration).split('.')[0]  # Remove microseconds
                session_column.controls[1].value = f"Duration: {duration_str}"
            else:
                session_column.controls[1].value = "Ready to start training"

        # Update progress indicator
        if 'progress' in self._status_indicators and self._current_session:
            progress_container = self._status_indicators['progress']
            progress_column = progress_container.content

            progress_pct = self._current_session.progress_percentage
            progress_column.controls[0].value = f"Progress: {progress_pct:.1f}%"
            progress_column.controls[1].value = progress_pct / 100.0

        # Update the UI
        if hasattr(self, 'page') and self.page:
            self.page.update()

    def _update_resource_displays(self) -> None:
        """Update resource monitoring displays."""
        if not self._config.show_resource_monitoring or not self._resource_metrics:
            return

        # Update CPU display
        if 'cpu' in self._resource_displays:
            cpu_container = self._resource_displays['cpu']
            cpu_column = cpu_container.content

            cpu_usage = getattr(self._resource_metrics, 'cpu_usage_percent', 0.0)
            cpu_column.controls[0].value = f"CPU: {cpu_usage:.1f}%"
            cpu_column.controls[1].value = cpu_usage / 100.0

        # Update memory display
        if 'memory' in self._resource_displays:
            memory_container = self._resource_displays['memory']
            memory_column = memory_container.content

            memory_used = getattr(self._resource_metrics, 'memory_used_mb', 0.0)
            memory_total = getattr(self._resource_metrics, 'memory_total_mb', 1.0)
            memory_usage = (memory_used / memory_total) * 100.0 if memory_total > 0 else 0.0

            memory_column.controls[0].value = f"Memory: {memory_used:.0f} MB"
            memory_column.controls[1].value = memory_usage / 100.0

        # Update GPU display
        if 'gpu' in self._resource_displays:
            gpu_container = self._resource_displays['gpu']
            gpu_column = gpu_container.content

            gpu_usage = getattr(self._resource_metrics, 'gpu_usage_percent', 0.0)
            gpu_column.controls[0].value = f"GPU: {gpu_usage:.1f}%"
            gpu_column.controls[1].value = gpu_usage / 100.0

        # Update the UI
        if hasattr(self, 'page') and self.page:
            self.page.update()

    def _add_log_entry(self, level: str, message: str) -> None:
        """Add entry to activity log."""
        timestamp = datetime.now()
        self._log_entries.append((timestamp, level, message))

        # Limit log entries
        if len(self._log_entries) > self._config.max_log_entries:
            self._log_entries = self._log_entries[-self._config.max_log_entries:]

        # Update log display
        if hasattr(self, '_log_display'):
            palette = self.get_palette()
            typography = self.get_typography()

            # Color based on log level
            level_colors = {
                'INFO': palette.text_primary,
                'WARNING': palette.warning,
                'ERROR': palette.error,
                'SUCCESS': palette.success
            }

            log_color = level_colors.get(level.upper(), palette.text_primary)

            log_entry = ft.Container(
                content=ft.Row([
                    ft.Text(
                        timestamp.strftime("%H:%M:%S"),
                        style=typography.body_small,
                        color=palette.text_secondary,
                        width=60
                    ),
                    ft.Text(
                        f"[{level}]",
                        style=typography.body_small,
                        color=log_color,
                        width=60
                    ),
                    ft.Text(
                        message,
                        style=typography.body_small,
                        color=palette.text_primary,
                        expand=True
                    )
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=8, vertical=2)
            )

            self._log_display.controls.append(log_entry)

            # Auto-scroll to bottom
            if hasattr(self, 'page') and self.page:
                self.page.update()
                if hasattr(self._log_display, 'scroll_to'):
                    self._log_display.scroll_to(offset=-1, duration=100)

    # Event Handlers
    async def _on_start_clicked(self, e) -> None:
        """Handle start training button click."""
        try:
            self._add_log_entry("INFO", "Starting training session...")

            if self._on_action:
                await self._on_action(TrainingControlAction.START, {})

            self._current_state = TrainingControlState.INITIALIZING
            self._update_button_states()
            self._update_status_displays()

        except Exception as ex:
            self._logger.error(f"Failed to start training: {ex}")
            self._add_log_entry("ERROR", f"Failed to start training: {ex}")
            self._current_state = TrainingControlState.ERROR
            self._update_button_states()
            self._update_status_displays()

    async def _on_pause_clicked(self, e) -> None:
        """Handle pause training button click."""
        try:
            self._add_log_entry("INFO", "Pausing training session...")

            if self._on_action:
                await self._on_action(TrainingControlAction.PAUSE, {})

            self._current_state = TrainingControlState.PAUSED
            self._update_button_states()
            self._update_status_displays()

        except Exception as ex:
            self._logger.error(f"Failed to pause training: {ex}")
            self._add_log_entry("ERROR", f"Failed to pause training: {ex}")

    async def _on_resume_clicked(self, e) -> None:
        """Handle resume training button click."""
        try:
            self._add_log_entry("INFO", "Resuming training session...")

            if self._on_action:
                await self._on_action(TrainingControlAction.RESUME, {})

            self._current_state = TrainingControlState.RUNNING
            self._update_button_states()
            self._update_status_displays()

        except Exception as ex:
            self._logger.error(f"Failed to resume training: {ex}")
            self._add_log_entry("ERROR", f"Failed to resume training: {ex}")

    async def _on_stop_clicked(self, e) -> None:
        """Handle stop training button click."""
        try:
            if self._config.confirm_destructive_actions:
                # Show confirmation dialog
                confirmed = await self._show_confirmation_dialog(
                    "Stop Training",
                    "Are you sure you want to stop the current training session? This action cannot be undone."
                )
                if not confirmed:
                    return

            self._add_log_entry("INFO", "Stopping training session...")

            if self._on_action:
                await self._on_action(TrainingControlAction.STOP, {})

            self._current_state = TrainingControlState.STOPPING
            self._update_button_states()
            self._update_status_displays()

        except Exception as ex:
            self._logger.error(f"Failed to stop training: {ex}")
            self._add_log_entry("ERROR", f"Failed to stop training: {ex}")

    async def _on_emergency_stop_clicked(self, e) -> None:
        """Handle emergency stop button click."""
        try:
            self._add_log_entry("WARNING", "Emergency stop initiated!")

            if self._on_action:
                await self._on_action(TrainingControlAction.EMERGENCY_STOP, {})

            self._current_state = TrainingControlState.ERROR
            self._update_button_states()
            self._update_status_displays()

        except Exception as ex:
            self._logger.error(f"Failed to emergency stop training: {ex}")
            self._add_log_entry("ERROR", f"Failed to emergency stop training: {ex}")

    async def _on_refresh_clicked(self, e) -> None:
        """Handle refresh button click."""
        try:
            self._add_log_entry("INFO", "Refreshing status...")
            await self._refresh_status()

        except Exception as ex:
            self._logger.error(f"Failed to refresh status: {ex}")
            self._add_log_entry("ERROR", f"Failed to refresh status: {ex}")

    async def _on_clear_log_clicked(self, e) -> None:
        """Handle clear log button click."""
        try:
            self._log_entries.clear()
            if hasattr(self, '_log_display'):
                self._log_display.controls.clear()
                if hasattr(self, 'page') and self.page:
                    self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to clear log: {ex}")

    # Session management event handlers
    async def _on_save_session_clicked(self, e) -> None:
        """Handle save session button click."""
        try:
            self._add_log_entry("INFO", "Saving current session...")

            if self._on_action:
                await self._on_action(SessionControlAction.SAVE_SESSION, {})

            self._add_log_entry("SUCCESS", "Session saved successfully")

        except Exception as ex:
            self._logger.error(f"Failed to save session: {ex}")
            self._add_log_entry("ERROR", f"Failed to save session: {ex}")

    async def _on_load_session_clicked(self, e) -> None:
        """Handle load session button click."""
        try:
            self._add_log_entry("INFO", "Loading session...")

            if self._on_action:
                await self._on_action(SessionControlAction.LOAD_SESSION, {})

        except Exception as ex:
            self._logger.error(f"Failed to load session: {ex}")
            self._add_log_entry("ERROR", f"Failed to load session: {ex}")

    async def _on_new_session_clicked(self, e) -> None:
        """Handle new session button click."""
        try:
            if self._config.confirm_destructive_actions and self._current_session:
                confirmed = await self._show_confirmation_dialog(
                    "New Session",
                    "Creating a new session will discard the current session. Continue?"
                )
                if not confirmed:
                    return

            self._add_log_entry("INFO", "Creating new session...")

            if self._on_action:
                await self._on_action(SessionControlAction.NEW_SESSION, {})

        except Exception as ex:
            self._logger.error(f"Failed to create new session: {ex}")
            self._add_log_entry("ERROR", f"Failed to create new session: {ex}")

    async def _on_export_session_clicked(self, e) -> None:
        """Handle export session button click."""
        try:
            self._add_log_entry("INFO", "Exporting session data...")

            if self._on_action:
                await self._on_action(SessionControlAction.EXPORT_SESSION, {})

            self._add_log_entry("SUCCESS", "Session exported successfully")

        except Exception as ex:
            self._logger.error(f"Failed to export session: {ex}")
            self._add_log_entry("ERROR", f"Failed to export session: {ex}")

    async def _show_confirmation_dialog(self, title: str, message: str) -> bool:
        """Show confirmation dialog and return user choice."""
        if not hasattr(self, 'page') or not self.page:
            return True  # Default to confirmed if no page available

        palette = self.get_palette()
        typography = self.get_typography()

        result = {"confirmed": False}

        def on_confirm(e):
            result["confirmed"] = True
            dialog.open = False
            self.page.update()

        def on_cancel(e):
            result["confirmed"] = False
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, style=typography.title_medium),
            content=ft.Text(message, style=typography.body_medium),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton("Confirm", on_click=on_confirm, bgcolor=palette.primary)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

        # Wait for dialog to close
        while dialog.open:
            await asyncio.sleep(0.1)

        return result["confirmed"]

    async def _refresh_status(self) -> None:
        """Refresh training and resource status."""
        try:
            # Update resource metrics if monitoring is available
            if RESOURCE_MONITORING_AVAILABLE and self._config.show_resource_monitoring:
                # This would typically get metrics from hardware monitor
                # For now, we'll simulate some basic metrics
                pass

            # Update training status from session manager
            if self._session_manager and TRAINING_ORCHESTRATION_AVAILABLE:
                # Get current session status
                # This would typically query the session manager
                pass

            # Update displays
            self._update_status_displays()
            self._update_resource_displays()

        except Exception as ex:
            self._logger.error(f"Failed to refresh status: {ex}")

    # Public API methods
    def set_training_session(self, session: Optional[TrainingSession]) -> None:
        """Set the current training session."""
        self._current_session = session

        if session:
            # Map training status to control state
            status_mapping = {
                TrainingStatus.INITIALIZING: TrainingControlState.INITIALIZING,
                TrainingStatus.READY: TrainingControlState.IDLE,
                TrainingStatus.RUNNING: TrainingControlState.RUNNING,
                TrainingStatus.PAUSED: TrainingControlState.PAUSED,
                TrainingStatus.COMPLETED: TrainingControlState.COMPLETED,
                TrainingStatus.FAILED: TrainingControlState.ERROR,
                TrainingStatus.CANCELLED: TrainingControlState.ERROR,
                TrainingStatus.RESUMING: TrainingControlState.RUNNING
            }

            if TRAINING_ORCHESTRATION_AVAILABLE and hasattr(session, 'status'):
                self._current_state = status_mapping.get(session.status, TrainingControlState.IDLE)
            else:
                self._current_state = TrainingControlState.IDLE
        else:
            self._current_state = TrainingControlState.IDLE

        self._update_button_states()
        self._update_status_displays()

    def set_training_metrics(self, metrics: Optional[TrainingMetrics]) -> None:
        """Set the latest training metrics."""
        self._last_metrics = metrics
        self._update_status_displays()

    def set_resource_metrics(self, metrics: Optional[ResourceMetrics]) -> None:
        """Set the latest resource metrics."""
        self._resource_metrics = metrics
        self._update_resource_displays()

    def start_auto_update(self) -> None:
        """Start automatic status updates."""
        if self._update_timer is None:
            self._update_timer = asyncio.create_task(self._update_loop())

    def stop_auto_update(self) -> None:
        """Stop automatic status updates."""
        if self._update_timer:
            self._update_timer.cancel()
            self._update_timer = None

    async def _update_loop(self) -> None:
        """Main update loop for real-time status updates."""
        while True:
            try:
                current_time = time.time()

                # Check if enough time has passed since last update
                if current_time - self._last_update_time >= self._config.update_interval_seconds:
                    if not self._is_updating:
                        self._is_updating = True
                        await self._refresh_status()
                        self._last_update_time = current_time
                        self._is_updating = False

                # Sleep for a short interval
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as ex:
                self._logger.error(f"Error in update loop: {ex}")
                await asyncio.sleep(1.0)  # Wait longer on error

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_auto_update()
        self._log_entries.clear()

        # Clear UI components
        self._control_buttons.clear()
        self._status_indicators.clear()
        self._session_controls.clear()
        self._resource_displays.clear()
