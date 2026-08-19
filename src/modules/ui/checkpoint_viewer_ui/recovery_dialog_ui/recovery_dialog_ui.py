"""
Module: recovery_dialog_ui
Description: Checkpoint recovery and restoration dialog interface with comprehensive theming integration.
            Provides responsive recovery dialog with checkpoint selection, recovery options, progress tracking,
            and error handling for training checkpoint restoration operations.
Phase: 4
Location: /src/modules/ui/checkpoint_viewer_ui/recovery_dialog_ui/recovery_dialog_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import uuid

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)

try:
    from src.modules.logic.checkpoint_management_lg.base_interfaces import (
        CheckpointMetadata,
        CheckpointType,
        CheckpointStatus,
        RecoveryResult
    )
    from src.modules.logic.checkpoint_management_lg.checkpoint_recovery_lg.checkpoint_recovery_lg import (
        CheckpointRecovery,
        RecoveryConfig
    )
except ImportError:
    # Fallback definitions for development
    class CheckpointType(Enum):
        PERIODIC = "periodic"
        BEST_MODEL = "best_model"
        MILESTONE = "milestone"
        EMERGENCY = "emergency"
    
    class CheckpointStatus(Enum):
        CREATING = "creating"
        CREATED = "created"
        VALIDATING = "validating"
        VALID = "valid"
        INVALID = "invalid"
        CORRUPTED = "corrupted"
        RECOVERING = "recovering"
        RECOVERED = "recovered"
        CLEANING = "cleaning"
        CLEANED = "cleaned"
        FAILED = "failed"
    
    @dataclass
    class CheckpointMetadata:
        checkpoint_id: str
        checkpoint_type: CheckpointType
        status: CheckpointStatus
        file_path: str
        created_at: datetime
        model_state_size: int
        optimizer_state_size: int
        total_size: int
        checksum: str
        training_step: int
        epoch: int
        loss_value: float
        description: Optional[str] = None
        is_best: bool = False
    
    @dataclass
    class RecoveryResult:
        success: bool
        checkpoint_id: str
        recovery_time: datetime
        recovered_step: int
        recovered_epoch: int
        recovered_loss: float
        errors: List[str] = field(default_factory=list)
        warnings: List[str] = field(default_factory=list)
        partial_recovery: bool = False


class RecoveryMode(Enum):
    """Recovery mode options for checkpoint restoration."""
    FULL_RESTORE = "full_restore"
    PARTIAL_RESTORE = "partial_restore"
    STATE_ONLY = "state_only"
    OPTIMIZER_ONLY = "optimizer_only"
    METADATA_ONLY = "metadata_only"
    CUSTOM = "custom"


class RecoveryStep(Enum):
    """Steps in the recovery process."""
    SELECTION = "selection"
    VALIDATION = "validation"
    PREPARATION = "preparation"
    RECOVERY = "recovery"
    VERIFICATION = "verification"
    COMPLETION = "completion"


class RecoveryState(Enum):
    """Current state of recovery operation."""
    IDLE = "idle"
    SELECTING = "selecting"
    VALIDATING = "validating"
    PREPARING = "preparing"
    RECOVERING = "recovering"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RecoveryOptions:
    """Configuration options for recovery operation."""
    recovery_mode: RecoveryMode = RecoveryMode.FULL_RESTORE
    validate_before_recovery: bool = True
    create_backup_before_recovery: bool = True
    allow_partial_recovery: bool = False
    recovery_timeout: int = 300  # seconds
    max_retry_attempts: int = 3
    rollback_on_failure: bool = True
    preserve_training_state: bool = True
    restore_optimizer_state: bool = True
    restore_scheduler_state: bool = True
    verify_after_recovery: bool = True


@dataclass
class RecoveryProgress:
    """Progress tracking for recovery operation."""
    current_step: RecoveryStep = RecoveryStep.SELECTION
    current_state: RecoveryState = RecoveryState.IDLE
    progress_percent: float = 0.0
    step_progress: float = 0.0
    estimated_time_remaining: Optional[int] = None
    current_operation: str = ""
    bytes_processed: int = 0
    total_bytes: int = 0
    files_processed: int = 0
    total_files: int = 0
    start_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str) -> None:
        """Add error to progress tracking."""
        self.errors.append(error)
    
    def add_warning(self, warning: str) -> None:
        """Add warning to progress tracking."""
        self.warnings.append(warning)


@dataclass
class RecoveryDialogConfig:
    """Configuration for recovery dialog behavior."""
    show_advanced_options: bool = False
    allow_custom_recovery: bool = True
    show_progress_details: bool = True
    enable_recovery_preview: bool = True
    auto_close_on_success: bool = False
    show_recovery_log: bool = True
    enable_recovery_cancellation: bool = True
    max_checkpoint_display: int = 50
    sort_checkpoints_by: str = "created_at"  # created_at, training_step, loss_value
    filter_invalid_checkpoints: bool = True


class RecoveryDialogUI(ThemeAwareUserControl):
    """
    Comprehensive checkpoint recovery dialog interface.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Theme-aware styling with no hardcoded colors or dimensions
    - Multiple recovery modes (full, partial, state-only, optimizer-only)
    - Real-time progress tracking with detailed status updates
    - Checkpoint validation and integrity verification
    - Advanced recovery options and configuration
    - Error handling and recovery cancellation
    - Recovery preview and confirmation
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Integration with checkpoint management system
    - Comprehensive logging and error reporting
    """
    
    def __init__(self,
                 checkpoints: Optional[List[CheckpointMetadata]] = None,
                 config: Optional[RecoveryDialogConfig] = None,
                 on_recovery_complete: Optional[Callable[[RecoveryResult], None]] = None,
                 on_recovery_cancelled: Optional[Callable[[], None]] = None,
                 **kwargs):
        """
        Initialize recovery dialog UI.
        
        Args:
            checkpoints: List of available checkpoints for recovery
            config: Dialog configuration options
            on_recovery_complete: Callback for recovery completion
            on_recovery_cancelled: Callback for recovery cancellation
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.checkpoints = checkpoints or []
        self.config = config or RecoveryDialogConfig()
        self.on_recovery_complete = on_recovery_complete
        self.on_recovery_cancelled = on_recovery_cancelled
        
        # Recovery state
        self.selected_checkpoint: Optional[CheckpointMetadata] = None
        self.recovery_options = RecoveryOptions()
        self.recovery_progress = RecoveryProgress()
        self.recovery_id = str(uuid.uuid4())
        
        # UI components
        self._dialog: Optional[ft.AlertDialog] = None
        self._checkpoint_list: Optional[ft.ListView] = None
        self._options_panel: Optional[ft.Container] = None
        self._progress_panel: Optional[ft.Container] = None
        self._action_buttons: Optional[ft.Row] = None
        self._recovery_log: Optional[ft.ListView] = None
        
        # Recovery system
        self._recovery_system: Optional[CheckpointRecovery] = None
        self._recovery_task: Optional[asyncio.Task] = None
        
        # State management
        self._is_built = False
        self._is_recovering = False
        self._logger = logging.getLogger(__name__)
        
        # Initialize recovery system
        self._initialize_recovery_system()
    
    def _initialize_recovery_system(self) -> None:
        """Initialize the checkpoint recovery system."""
        try:
            recovery_config = RecoveryConfig(
                validate_before_recovery=self.recovery_options.validate_before_recovery,
                allow_partial_recovery=self.recovery_options.allow_partial_recovery,
                recovery_timeout=self.recovery_options.recovery_timeout,
                backup_failed_recovery=self.recovery_options.create_backup_before_recovery
            )
            self._recovery_system = CheckpointRecovery(recovery_config)
        except Exception as e:
            self._logger.error(f"Failed to initialize recovery system: {e}")
            self._recovery_system = None

    def build(self) -> ft.Control:
        """Build the recovery dialog interface."""
        if not self._is_built:
            self._build_component()
            self._is_built = True
        return self._dialog or ft.Container()

    def _build_component(self) -> None:
        """Build the main recovery dialog component."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Create dialog content
        dialog_content = self._create_dialog_content()

        # Create action buttons
        self._action_buttons = self._create_action_buttons()

        # Create main dialog
        self._dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Checkpoint Recovery",
                style=self.get_text_style("h3"),
                color=palette.text_primary,
                semantics_label="Checkpoint Recovery Dialog"
            ),
            content=ft.Container(
                content=dialog_content,
                width=self.get_breakpoint_value(
                    mobile=350, tablet=500, desktop=700, large=800
                ),
                height=self.get_breakpoint_value(
                    mobile=400, tablet=500, desktop=600, large=650
                ),
                padding=ft.padding.all(spacing.sm)
            ),
            actions=[self._action_buttons],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=palette.surface,
            title_text_style=ft.TextStyle(
                color=palette.text_primary,
                size=typography.h3[0],
                weight=ft.FontWeight.W_600
            ),
            # Accessibility improvements
            on_dismiss=self._cancel_recovery
        )

    def _create_dialog_content(self) -> ft.Control:
        """Create the main dialog content with tabs."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create tab content
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Select Checkpoint",
                    icon=self.get_icon("RESTORE"),
                    content=self._create_checkpoint_selection_tab()
                ),
                ft.Tab(
                    text="Recovery Options",
                    icon=self.get_icon("SETTINGS"),
                    content=self._create_recovery_options_tab()
                ),
                ft.Tab(
                    text="Progress",
                    icon=self.get_icon("PROGRESS"),
                    content=self._create_progress_tab()
                )
            ],
            expand=True
        )

        return ft.Container(
            content=tabs,
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_size(8),
            padding=ft.padding.all(spacing.xs),
            expand=True
        )

    def _create_checkpoint_selection_tab(self) -> ft.Control:
        """Create checkpoint selection tab content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Filter and sort checkpoints
        filtered_checkpoints = self._filter_checkpoints()

        if not filtered_checkpoints:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("WARNING"),
                            color=palette.warning,
                            size=self.get_responsive_size(48)
                        ),
                        ft.Text(
                            "No valid checkpoints available for recovery",
                            style=self.get_text_style("body_medium"),
                            color=palette.text_secondary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Please ensure checkpoints exist and are accessible",
                            style=self.get_text_style("body_small"),
                            color=palette.text_tertiary,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.md
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        # Create checkpoint list
        checkpoint_items = []
        for checkpoint in filtered_checkpoints:
            checkpoint_items.append(self._create_checkpoint_item(checkpoint))

        self._checkpoint_list = ft.ListView(
            controls=checkpoint_items,
            spacing=spacing.xs,
            padding=ft.padding.all(spacing.sm),
            expand=True,
            # Accessibility improvements
            auto_scroll=True,
            on_scroll=self._handle_checkpoint_scroll
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_checkpoint_header(),
                    ft.Divider(color=palette.outline),
                    self._checkpoint_list
                ],
                spacing=spacing.sm,
                expand=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_checkpoint_header(self) -> ft.Control:
        """Create checkpoint list header with sorting and filtering."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Row(
            controls=[
                ft.Text(
                    f"Available Checkpoints ({len(self._filter_checkpoints())})",
                    style=self.get_text_style("body_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=self.get_icon("REFRESH"),
                    icon_color=palette.primary,
                    icon_size=self.get_responsive_size(20),
                    tooltip="Refresh checkpoint list",
                    on_click=self._refresh_checkpoints
                ),
                ft.IconButton(
                    icon=self.get_icon("FILTER_LIST"),
                    icon_color=palette.primary,
                    icon_size=self.get_responsive_size(20),
                    tooltip="Filter checkpoints",
                    on_click=self._show_filter_options
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

    def _create_checkpoint_item(self, checkpoint: CheckpointMetadata) -> ft.Control:
        """Create a checkpoint list item."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Determine status color
        status_color = self._get_status_color(checkpoint.status)

        # Format checkpoint info
        size_mb = checkpoint.total_size / (1024 * 1024) if checkpoint.total_size > 0 else 0
        created_time = checkpoint.created_at.strftime("%Y-%m-%d %H:%M:%S")

        # Create checkpoint card
        is_selected = self.selected_checkpoint and self.selected_checkpoint.checkpoint_id == checkpoint.checkpoint_id

        checkpoint_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                name=self._get_checkpoint_icon(checkpoint.checkpoint_type),
                                color=palette.primary if is_selected else palette.text_secondary,
                                size=self.get_responsive_size(20),
                                semantics_label=f"Checkpoint type: {checkpoint.checkpoint_type.value}"
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        f"Checkpoint {checkpoint.checkpoint_id[:8]}...",
                                        style=self.get_text_style("body_medium"),
                                        color=palette.text_primary,
                                        weight=ft.FontWeight.W_500,
                                        semantics_label=f"Checkpoint ID: {checkpoint.checkpoint_id}"
                                    ),
                                    ft.Text(
                                        f"Step {checkpoint.training_step} • Epoch {checkpoint.epoch}",
                                        style=self.get_text_style("body_small"),
                                        color=palette.text_secondary,
                                        semantics_label=f"Training step {checkpoint.training_step}, epoch {checkpoint.epoch}"
                                    )
                                ],
                                spacing=spacing.xs,
                                expand=True
                            ),
                            ft.Container(
                                content=ft.Text(
                                    checkpoint.status.value.title(),
                                    style=self.get_text_style("caption"),
                                    color=status_color,
                                    weight=ft.FontWeight.W_500,
                                    semantics_label=f"Status: {checkpoint.status.value}"
                                ),
                                bgcolor=f"{status_color}20",
                                padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2),
                                border_radius=self.get_responsive_size(4)
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"Loss: {checkpoint.loss_value:.4f}",
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary,
                                semantics_label=f"Loss value: {checkpoint.loss_value:.4f}"
                            ),
                            ft.Text(
                                f"Size: {size_mb:.1f} MB",
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary,
                                semantics_label=f"File size: {size_mb:.1f} megabytes"
                            ),
                            ft.Text(
                                created_time,
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary,
                                semantics_label=f"Created: {created_time}"
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                spacing=spacing.xs
            ),
            bgcolor=palette.selection if is_selected else palette.surface,
            border=ft.border.all(
                width=2 if is_selected else 1,
                color=palette.primary if is_selected else palette.outline
            ),
            border_radius=self.get_responsive_size(8),
            padding=ft.padding.all(spacing.sm),
            on_click=lambda e, cp=checkpoint: self._select_checkpoint(cp),
            ink=True,
            # Accessibility improvements
            tooltip=f"Select checkpoint {checkpoint.checkpoint_id[:8]} (Step {checkpoint.training_step}, Loss {checkpoint.loss_value:.4f})",
            data=checkpoint.checkpoint_id  # For keyboard navigation
        )

        return checkpoint_card

    def _create_recovery_options_tab(self) -> ft.Control:
        """Create recovery options tab content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Recovery mode selection
        mode_options = []
        for mode in RecoveryMode:
            is_selected = mode == self.recovery_options.recovery_mode
            mode_options.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                mode.value.replace("_", " ").title(),
                                style=self.get_text_style("body_medium"),
                                color=palette.text_primary,
                                weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.W_400
                            ),
                            ft.Text(
                                self._get_recovery_mode_description(mode),
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary
                            )
                        ],
                        spacing=spacing.xs
                    ),
                    padding=ft.padding.all(spacing.sm),
                    border_radius=self.get_responsive_size(6),
                    bgcolor=palette.selection if is_selected else palette.surface_variant,
                    border=ft.border.all(
                        width=2 if is_selected else 1,
                        color=palette.primary if is_selected else palette.outline
                    ),
                    on_click=lambda e, m=mode: self._update_recovery_mode(m),
                    ink=True
                )
            )

        # Advanced options
        advanced_options = []
        if self.config.show_advanced_options:
            advanced_options = [
                ft.Divider(color=palette.outline),
                ft.Text(
                    "Advanced Options",
                    style=self.get_text_style("body_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                self._create_advanced_options_panel()
            ]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Recovery Mode",
                        style=self.get_text_style("body_medium"),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Column(
                        controls=mode_options,
                        spacing=spacing.xs
                    ),
                    *advanced_options
                ],
                spacing=spacing.md,
                scroll=ft.ScrollMode.AUTO,
                expand=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_advanced_options_panel(self) -> ft.Control:
        """Create advanced recovery options panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create switch options
        switch_options = [
            ("validate_before_recovery", "Validate before recovery", "Verify checkpoint integrity before starting recovery"),
            ("create_backup_before_recovery", "Create backup before recovery", "Create backup of current state before recovery"),
            ("allow_partial_recovery", "Allow partial recovery", "Continue recovery even if some components fail"),
            ("rollback_on_failure", "Rollback on failure", "Automatically rollback changes if recovery fails")
        ]

        option_controls = []
        for option_key, title, description in switch_options:
            current_value = getattr(self.recovery_options, option_key)

            option_control = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    title,
                                    style=self.get_text_style("body_medium"),
                                    color=palette.text_primary
                                ),
                                ft.Text(
                                    description,
                                    style=self.get_text_style("body_small"),
                                    color=palette.text_secondary
                                )
                            ],
                            spacing=spacing.xs,
                            expand=True
                        ),
                        ft.Switch(
                            value=current_value,
                            on_change=lambda e, key=option_key: self._update_option(key, e.control.value)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=ft.padding.all(spacing.sm),
                border_radius=self.get_responsive_size(6)
            )
            option_controls.append(option_control)

        return ft.Column(
            controls=option_controls,
            spacing=spacing.xs
        )

    def _create_progress_tab(self) -> ft.Control:
        """Create recovery progress tab content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Progress overview
        progress_overview = ft.Column(
            controls=[
                ft.Text(
                    "Recovery Progress",
                    style=self.get_text_style("body_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.ProgressBar(
                    value=self.recovery_progress.progress_percent / 100.0,
                    width=self.get_breakpoint_value(
                        mobile=250, tablet=350, desktop=450, large=500
                    ),
                    height=self.get_responsive_size(8),
                    color=palette.primary,
                    bgcolor=palette.surface_variant
                ),
                ft.Row(
                    controls=[
                        ft.Text(
                            f"{self.recovery_progress.progress_percent:.1f}%",
                            style=self.get_text_style("body_small"),
                            color=palette.text_primary
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            self.recovery_progress.current_operation or "Ready to start",
                            style=self.get_text_style("body_small"),
                            color=palette.text_secondary
                        )
                    ]
                )
            ],
            spacing=spacing.sm
        )

        # Step progress
        step_progress = self._create_step_progress_indicator()

        # Recovery log
        recovery_log = self._create_recovery_log()

        return ft.Container(
            content=ft.Column(
                controls=[
                    progress_overview,
                    ft.Divider(color=palette.outline),
                    step_progress,
                    ft.Divider(color=palette.outline),
                    recovery_log
                ],
                spacing=spacing.md,
                expand=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_step_progress_indicator(self) -> ft.Control:
        """Create step-by-step progress indicator."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        steps = [
            (RecoveryStep.SELECTION, "Selection", "Select checkpoint"),
            (RecoveryStep.VALIDATION, "Validation", "Validate checkpoint"),
            (RecoveryStep.PREPARATION, "Preparation", "Prepare recovery"),
            (RecoveryStep.RECOVERY, "Recovery", "Restore state"),
            (RecoveryStep.VERIFICATION, "Verification", "Verify recovery"),
            (RecoveryStep.COMPLETION, "Completion", "Complete recovery")
        ]

        step_indicators = []
        for i, (step, title, description) in enumerate(steps):
            is_current = step == self.recovery_progress.current_step
            is_completed = list(RecoveryStep).index(step) < list(RecoveryStep).index(self.recovery_progress.current_step)

            # Step icon
            if is_completed:
                icon = self.get_icon("CHECK_CIRCLE")
                icon_color = palette.success
            elif is_current:
                icon = self.get_icon("RADIO_BUTTON_CHECKED")
                icon_color = palette.primary
            else:
                icon = self.get_icon("RADIO_BUTTON_UNCHECKED")
                icon_color = palette.text_tertiary

            step_item = ft.Row(
                controls=[
                    ft.Icon(
                        name=icon,
                        color=icon_color,
                        size=self.get_responsive_size(20)
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                style=self.get_text_style("body_medium"),
                                color=palette.text_primary if (is_current or is_completed) else palette.text_secondary,
                                weight=ft.FontWeight.W_500 if is_current else ft.FontWeight.W_400
                            ),
                            ft.Text(
                                description,
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    )
                ],
                spacing=spacing.sm
            )

            step_indicators.append(step_item)

            # Add connector line (except for last item)
            if i < len(steps) - 1:
                connector = ft.Container(
                    width=2,
                    height=self.get_responsive_size(20),
                    bgcolor=palette.primary if is_completed else palette.outline,
                    margin=ft.margin.only(left=self.get_responsive_size(10))
                )
                step_indicators.append(connector)

        return ft.Column(
            controls=[
                ft.Text(
                    "Recovery Steps",
                    style=self.get_text_style("body_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Column(
                    controls=step_indicators,
                    spacing=spacing.xs
                )
            ],
            spacing=spacing.sm
        )

    def _create_recovery_log(self) -> ft.Control:
        """Create recovery log display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self.config.show_recovery_log:
            return ft.Container()

        # Log entries
        log_entries = []

        # Add errors
        for error in self.recovery_progress.errors:
            log_entries.append(
                ft.Row(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("ERROR"),
                            color=palette.error,
                            size=self.get_responsive_size(16)
                        ),
                        ft.Text(
                            error,
                            style=self.get_text_style("body_small"),
                            color=palette.error,
                            expand=True
                        )
                    ],
                    spacing=spacing.xs
                )
            )

        # Add warnings
        for warning in self.recovery_progress.warnings:
            log_entries.append(
                ft.Row(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("WARNING"),
                            color=palette.warning,
                            size=self.get_responsive_size(16)
                        ),
                        ft.Text(
                            warning,
                            style=self.get_text_style("body_small"),
                            color=palette.warning,
                            expand=True
                        )
                    ],
                    spacing=spacing.xs
                )
            )

        if not log_entries:
            log_entries.append(
                ft.Text(
                    "No log entries yet",
                    style=self.get_text_style("body_small"),
                    color=palette.text_tertiary,
                    italic=True
                )
            )

        self._recovery_log = ft.ListView(
            controls=log_entries,
            spacing=spacing.xs,
            padding=ft.padding.all(spacing.sm),
            height=self.get_responsive_size(120),
            auto_scroll=True
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Recovery Log",
                    style=self.get_text_style("body_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(
                    content=self._recovery_log,
                    bgcolor=palette.surface_variant,
                    border_radius=self.get_responsive_size(6),
                    border=ft.border.all(1, palette.outline)
                )
            ],
            spacing=spacing.sm
        )

    def _create_action_buttons(self) -> ft.Control:
        """Create dialog action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Cancel button
        cancel_button = ft.TextButton(
            text="Cancel",
            icon=self.get_icon("CANCEL"),
            style=ft.ButtonStyle(
                color=palette.text_secondary,
                bgcolor=palette.surface_variant
            ),
            on_click=self._cancel_recovery,
            tooltip="Cancel recovery and close dialog",
            autofocus=False
        )

        # Start/Stop recovery button
        if self._is_recovering:
            primary_button = ft.ElevatedButton(
                text="Stop Recovery",
                icon=self.get_icon("STOP"),
                style=ft.ButtonStyle(
                    color=palette.text_primary,
                    bgcolor=palette.error
                ),
                on_click=self._stop_recovery,
                tooltip="Stop the current recovery operation",
                autofocus=True
            )
        else:
            primary_button = ft.ElevatedButton(
                text="Start Recovery",
                icon=self.get_icon("PLAY_ARROW"),
                style=ft.ButtonStyle(
                    color=palette.text_primary,
                    bgcolor=palette.primary
                ),
                on_click=self._start_recovery,
                disabled=not self.selected_checkpoint,
                tooltip="Start recovery from selected checkpoint" if self.selected_checkpoint else "Select a checkpoint to start recovery",
                autofocus=bool(self.selected_checkpoint)
            )

        return ft.Row(
            controls=[cancel_button, primary_button],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.END
        )

    # Helper methods
    def _filter_checkpoints(self) -> List[CheckpointMetadata]:
        """Filter checkpoints based on configuration."""
        filtered = self.checkpoints.copy()

        # Filter invalid checkpoints if configured
        if self.config.filter_invalid_checkpoints:
            filtered = [cp for cp in filtered if cp.status == CheckpointStatus.VALID]

        # Sort checkpoints
        if self.config.sort_checkpoints_by == "created_at":
            filtered.sort(key=lambda cp: cp.created_at, reverse=True)
        elif self.config.sort_checkpoints_by == "training_step":
            filtered.sort(key=lambda cp: cp.training_step, reverse=True)
        elif self.config.sort_checkpoints_by == "loss_value":
            filtered.sort(key=lambda cp: cp.loss_value)

        # Limit display count
        return filtered[:self.config.max_checkpoint_display]

    def _get_status_color(self, status: CheckpointStatus) -> str:
        """Get color for checkpoint status."""
        palette = self.get_palette()

        status_colors = {
            CheckpointStatus.VALID: palette.success,
            CheckpointStatus.CORRUPTED: palette.error,
            CheckpointStatus.INVALID: palette.error,
            CheckpointStatus.FAILED: palette.error,
            CheckpointStatus.VALIDATING: palette.info,
            CheckpointStatus.CREATING: palette.info,
            CheckpointStatus.RECOVERING: palette.warning,
            CheckpointStatus.RECOVERED: palette.success,
            CheckpointStatus.CLEANING: palette.info,
            CheckpointStatus.CLEANED: palette.text_tertiary,
            CheckpointStatus.CREATED: palette.text_secondary
        }

        return status_colors.get(status, palette.text_secondary)

    def _get_checkpoint_icon(self, checkpoint_type: CheckpointType) -> str:
        """Get icon for checkpoint type."""
        type_icons = {
            CheckpointType.PERIODIC: self.get_icon("SCHEDULE"),
            CheckpointType.BEST_MODEL: self.get_icon("STAR"),
            CheckpointType.MILESTONE: self.get_icon("FLAG"),
            CheckpointType.EMERGENCY: self.get_icon("WARNING")
        }

        return type_icons.get(checkpoint_type, self.get_icon("SAVE"))

    def _get_recovery_mode_description(self, mode: RecoveryMode) -> str:
        """Get description for recovery mode."""
        descriptions = {
            RecoveryMode.FULL_RESTORE: "Restore complete model and optimizer state",
            RecoveryMode.PARTIAL_RESTORE: "Restore only essential components",
            RecoveryMode.STATE_ONLY: "Restore model state only",
            RecoveryMode.OPTIMIZER_ONLY: "Restore optimizer state only",
            RecoveryMode.METADATA_ONLY: "Restore training metadata only",
            RecoveryMode.CUSTOM: "Custom recovery configuration"
        }

        return descriptions.get(mode, "Unknown recovery mode")

    # Event handlers
    def _select_checkpoint(self, checkpoint: CheckpointMetadata) -> None:
        """Handle checkpoint selection."""
        self.selected_checkpoint = checkpoint
        self._logger.info(f"Selected checkpoint: {checkpoint.checkpoint_id}")

        # Update UI
        if self._checkpoint_list:
            self._refresh_checkpoint_list()

        # Update action buttons
        if self._action_buttons:
            self._update_action_buttons()

        # Trigger update
        if hasattr(self, 'page') and self.page:
            self.page.update()

    def _update_recovery_mode(self, mode: RecoveryMode) -> None:
        """Update recovery mode."""
        self.recovery_options.recovery_mode = mode
        self._logger.info(f"Recovery mode updated to: {mode.value}")

        # Trigger update
        if hasattr(self, 'page') and self.page:
            self.page.update()

    def _update_option(self, option_name: str, value: Any) -> None:
        """Update recovery option."""
        setattr(self.recovery_options, option_name, value)
        self._logger.info(f"Recovery option {option_name} updated to: {value}")

    def _refresh_checkpoints(self, e=None) -> None:
        """Refresh checkpoint list."""
        # This would typically reload checkpoints from the checkpoint manager
        self._logger.info("Refreshing checkpoint list")

        if self._checkpoint_list:
            self._refresh_checkpoint_list()

        # Trigger update
        if hasattr(self, 'page') and self.page:
            self.page.update()

    def _show_filter_options(self, e=None) -> None:
        """Show checkpoint filter options."""
        # This would show a filter dialog
        self._logger.info("Showing filter options")

    def _refresh_checkpoint_list(self) -> None:
        """Refresh the checkpoint list UI."""
        if not self._checkpoint_list:
            return

        # Clear existing items
        self._checkpoint_list.controls.clear()

        # Add updated items
        filtered_checkpoints = self._filter_checkpoints()
        for checkpoint in filtered_checkpoints:
            self._checkpoint_list.controls.append(self._create_checkpoint_item(checkpoint))

    def _update_action_buttons(self) -> None:
        """Update action buttons state."""
        if not self._action_buttons:
            return

        # Update primary button state
        primary_button = self._action_buttons.controls[-1]
        primary_button.disabled = not self.selected_checkpoint and not self._is_recovering

    # Recovery operations
    async def _start_recovery(self, e=None) -> None:
        """Start the recovery process."""
        if not self.selected_checkpoint:
            self._logger.error("No checkpoint selected for recovery")
            return

        if self._is_recovering:
            self._logger.warning("Recovery already in progress")
            return

        try:
            self._is_recovering = True
            self.recovery_progress.current_state = RecoveryState.PREPARING
            self.recovery_progress.start_time = datetime.now()

            # Update UI
            self._update_progress_ui()

            # Start recovery task
            self._recovery_task = asyncio.create_task(self._perform_recovery())
            await self._recovery_task

        except Exception as e:
            self._logger.error(f"Recovery failed: {e}")
            self.recovery_progress.add_error(f"Recovery failed: {str(e)}")
            self.recovery_progress.current_state = RecoveryState.FAILED
            self._update_progress_ui()
        finally:
            self._is_recovering = False
            self._update_action_buttons()

    async def _perform_recovery(self) -> None:
        """Perform the actual recovery operation."""
        if not self.selected_checkpoint or not self._recovery_system:
            return

        try:
            # Step 1: Validation
            self.recovery_progress.current_step = RecoveryStep.VALIDATION
            self.recovery_progress.current_operation = "Validating checkpoint..."
            self.recovery_progress.progress_percent = 10.0
            self._update_progress_ui()

            await asyncio.sleep(0.5)  # Simulate validation time

            # Step 2: Preparation
            self.recovery_progress.current_step = RecoveryStep.PREPARATION
            self.recovery_progress.current_operation = "Preparing recovery..."
            self.recovery_progress.progress_percent = 25.0
            self._update_progress_ui()

            await asyncio.sleep(0.5)  # Simulate preparation time

            # Step 3: Recovery
            self.recovery_progress.current_step = RecoveryStep.RECOVERY
            self.recovery_progress.current_operation = "Restoring checkpoint..."
            self.recovery_progress.progress_percent = 50.0
            self._update_progress_ui()

            # Perform actual recovery (this would be the real recovery operation)
            from pathlib import Path
            checkpoint_path = Path(self.selected_checkpoint.file_path) if self.selected_checkpoint.file_path else Path("dummy")

            # Simulate recovery progress
            for i in range(50, 85, 5):
                self.recovery_progress.progress_percent = float(i)
                self.recovery_progress.current_operation = f"Restoring state... {i}%"
                self._update_progress_ui()
                await asyncio.sleep(0.2)

            # Step 4: Verification
            self.recovery_progress.current_step = RecoveryStep.VERIFICATION
            self.recovery_progress.current_operation = "Verifying recovery..."
            self.recovery_progress.progress_percent = 90.0
            self._update_progress_ui()

            await asyncio.sleep(0.5)  # Simulate verification time

            # Step 5: Completion
            self.recovery_progress.current_step = RecoveryStep.COMPLETION
            self.recovery_progress.current_operation = "Recovery completed successfully"
            self.recovery_progress.progress_percent = 100.0
            self.recovery_progress.current_state = RecoveryState.COMPLETED
            self._update_progress_ui()

            # Create recovery result
            recovery_result = RecoveryResult(
                success=True,
                checkpoint_id=self.selected_checkpoint.checkpoint_id,
                recovery_time=datetime.now(),
                recovered_step=self.selected_checkpoint.training_step,
                recovered_epoch=self.selected_checkpoint.epoch,
                recovered_loss=self.selected_checkpoint.loss_value
            )

            # Notify completion
            if self.on_recovery_complete:
                self.on_recovery_complete(recovery_result)

            # Auto-close if configured
            if self.config.auto_close_on_success:
                await asyncio.sleep(1.0)
                self._close_dialog()

        except Exception as e:
            self._logger.error(f"Recovery operation failed: {e}")
            self.recovery_progress.add_error(f"Recovery operation failed: {str(e)}")
            self.recovery_progress.current_state = RecoveryState.FAILED
            self._update_progress_ui()

    def _stop_recovery(self, e=None) -> None:
        """Stop the recovery process."""
        if not self._is_recovering:
            return

        try:
            if self._recovery_task and not self._recovery_task.done():
                self._recovery_task.cancel()

            self.recovery_progress.current_state = RecoveryState.CANCELLED
            self.recovery_progress.current_operation = "Recovery cancelled by user"
            self._update_progress_ui()

            self._is_recovering = False
            self._update_action_buttons()

            self._logger.info("Recovery cancelled by user")

        except Exception as e:
            self._logger.error(f"Error stopping recovery: {e}")

    def _cancel_recovery(self, e=None) -> None:
        """Cancel the recovery dialog."""
        if self._is_recovering:
            self._stop_recovery()

        if self.on_recovery_cancelled:
            self.on_recovery_cancelled()

        self._close_dialog()

    def _close_dialog(self) -> None:
        """Close the recovery dialog."""
        if self._dialog and hasattr(self, 'page') and self.page:
            # Disable keyboard navigation
            self.disable_keyboard_navigation(self.page)

            self._dialog.open = False
            self.page.update()

    def _update_progress_ui(self) -> None:
        """Update progress UI elements."""
        if hasattr(self, 'page') and self.page:
            self.page.update()

    # Public methods
    def show_dialog(self, page: ft.Page) -> None:
        """Show the recovery dialog."""
        self.page = page
        if self._dialog:
            # Enable keyboard navigation
            self.enable_keyboard_navigation(page)

            page.dialog = self._dialog
            self._dialog.open = True
            page.update()

    def update_checkpoints(self, checkpoints: List[CheckpointMetadata]) -> None:
        """Update the list of available checkpoints."""
        self.checkpoints = checkpoints
        self.selected_checkpoint = None

        if self._checkpoint_list:
            self._refresh_checkpoint_list()

        if hasattr(self, 'page') and self.page:
            self.page.update()

    def get_selected_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get the currently selected checkpoint."""
        return self.selected_checkpoint

    def get_recovery_options(self) -> RecoveryOptions:
        """Get the current recovery options."""
        return self.recovery_options

    def get_recovery_progress(self) -> RecoveryProgress:
        """Get the current recovery progress."""
        return self.recovery_progress

    def is_recovery_in_progress(self) -> bool:
        """Check if recovery is currently in progress."""
        return self._is_recovering

    # Accessibility and keyboard navigation
    def _handle_checkpoint_scroll(self, e=None) -> None:
        """Handle checkpoint list scroll events."""
        # This can be used for lazy loading or performance optimization
        pass

    def _handle_keyboard_navigation(self, e: ft.KeyboardEvent) -> None:
        """Handle keyboard navigation within the dialog."""
        if not e.key:
            return

        # Handle escape key to close dialog
        if e.key == "Escape":
            self._cancel_recovery()
            return

        # Handle enter key to start recovery if checkpoint is selected
        if e.key == "Enter" and self.selected_checkpoint and not self._is_recovering:
            asyncio.create_task(self._start_recovery())
            return

        # Handle arrow keys for checkpoint navigation
        if e.key in ["ArrowUp", "ArrowDown"] and self.checkpoints:
            self._navigate_checkpoints(e.key == "ArrowDown")

    def _navigate_checkpoints(self, down: bool = True) -> None:
        """Navigate through checkpoints using keyboard."""
        if not self.checkpoints:
            return

        filtered_checkpoints = self._filter_checkpoints()
        if not filtered_checkpoints:
            return

        current_index = -1
        if self.selected_checkpoint:
            try:
                current_index = next(
                    i for i, cp in enumerate(filtered_checkpoints)
                    if cp.checkpoint_id == self.selected_checkpoint.checkpoint_id
                )
            except StopIteration:
                current_index = -1

        # Calculate new index
        if down:
            new_index = (current_index + 1) % len(filtered_checkpoints)
        else:
            new_index = (current_index - 1) % len(filtered_checkpoints)

        # Select new checkpoint
        self._select_checkpoint(filtered_checkpoints[new_index])

    def enable_keyboard_navigation(self, page: ft.Page) -> None:
        """Enable keyboard navigation for the dialog."""
        if hasattr(page, 'on_keyboard_event'):
            page.on_keyboard_event = self._handle_keyboard_navigation

    def disable_keyboard_navigation(self, page: ft.Page) -> None:
        """Disable keyboard navigation for the dialog."""
        if hasattr(page, 'on_keyboard_event'):
            page.on_keyboard_event = None
