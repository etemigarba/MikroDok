"""
Module: checkpoint_details_ui
Description: Comprehensive checkpoint details display interface with responsive design and theme integration.
            Provides detailed checkpoint information, metrics visualization, technical specifications,
            and comparison capabilities with modern UI/UX patterns and accessibility compliance.
Phase: 4
Location: /src/modules/ui/checkpoint_viewer_ui/checkpoint_details_ui/checkpoint_details_ui.py
"""

# Standard library imports
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Third-party imports - make flet optional for testing
try:
    import flet as ft
except ImportError:
    # Mock flet for testing
    class MockFlet:
        class Icons:
            ANALYTICS = "analytics"
            REFRESH = "refresh"
            BOOKMARK = "bookmark"
            COMPARE_ARROWS = "compare_arrows"
            DOWNLOAD = "download"
            SETTINGS = "settings"
            DASHBOARD = "dashboard"
            HISTORY = "history"
            INFO = "info"
            CHECK_CIRCLE = "check_circle"
            ERROR = "error"
            WARNING = "warning"
            HOURGLASS_EMPTY = "hourglass_empty"
            ARCHIVE = "archive"
            HELP = "help"
            TARGET = "target"
            PRECISION_MANUFACTURING = "precision_manufacturing"
            MEMORY = "memory"
            FUNCTIONS = "functions"
            SPEED = "speed"
            PSYCHOLOGY = "psychology"
            TRANSLATE = "translate"
            RATE_REVIEW = "rate_review"
            TRENDING_DOWN = "trending_down"
            ERROR_OUTLINE = "error_outline"
            ANALYTICS_OUTLINED = "analytics_outlined"
            BOOKMARK_BORDER = "bookmark_border"
            SEARCH = "search"
            FOLDER = "folder"
            LABEL = "label"
            SCHOOL = "school"
            INFO_OUTLINED = "info_outlined"

        class Colors:
            BLUE_400 = "#42A5F5"

        class FontWeight:
            W_400 = "400"
            W_500 = "500"
            W_600 = "600"
            W_700 = "700"

        class TextAlign:
            CENTER = "center"
            LEFT = "left"

        class CrossAxisAlignment:
            CENTER = "center"
            START = "start"

        class MainAxisAlignment:
            START = "start"
            SPACE_BETWEEN = "space_between"

        class ScrollMode:
            AUTO = "auto"

        class TextOverflow:
            ELLIPSIS = "ellipsis"

        class TextStyle:
            def __init__(self, **kwargs):
                pass

        class Container:
            def __init__(self, **kwargs):
                pass

        class Column:
            def __init__(self, **kwargs):
                pass

        class Row:
            def __init__(self, **kwargs):
                pass

        class Text:
            def __init__(self, *args, **kwargs):
                pass

        class Icon:
            def __init__(self, *args, **kwargs):
                pass

        class IconButton:
            def __init__(self, **kwargs):
                pass

        class ElevatedButton:
            def __init__(self, **kwargs):
                pass

        class Divider:
            def __init__(self, **kwargs):
                pass

        class Expanded:
            def __init__(self, **kwargs):
                pass

        class ResponsiveRow:
            def __init__(self, **kwargs):
                pass

        class Card:
            def __init__(self, **kwargs):
                pass

        class Checkbox:
            def __init__(self, **kwargs):
                pass

        class ProgressRing:
            def __init__(self, **kwargs):
                pass

        class border:
            @staticmethod
            def all(width, color):
                return f"border: {width}px solid {color}"

        class padding:
            @staticmethod
            def symmetric(**kwargs):
                return "padding"

            @staticmethod
            def only(**kwargs):
                return "padding"

        class alignment:
            center = "center"

    ft = MockFlet()

# Local imports - make theme system optional for testing
try:
    from src.modules.ui.theme_system_ui.theme_system_ui import (
        ThemeAwareUserControl,
        ColorPalette,
        SpacingSystem,
        TypographyScale,
        IconSystem,
        get_theme_manager
    )
except ImportError:
    # Fallback for testing without full theme system
    class ThemeAwareUserControl:
        def __init__(self):
            self.page = None

        def get_palette(self):
            # Mock palette
            class MockPalette:
                primary = "#6750A4"
                on_surface = "#1C1B1F"
                surface = "#FFFBFE"
                surface_variant = "#E7E0EC"
                on_surface_variant = "#49454F"
                outline_variant = "#CAC4D0"
                error = "#BA1A1A"
                success = "#006D3B"
                warning = "#8B5000"
                info = "#0061A4"
                secondary = "#625B71"
                primary_container = "#EADDFF"
                borders = "#CAC4D0"
            return MockPalette()

        def get_spacing(self):
            # Mock spacing
            class MockSpacing:
                xs = 4
                small = 8
                medium = 16
                large = 24
                extra_large = 32
            return MockSpacing()

        def get_text_style(self, style_name):
            return ft.TextStyle()

        def get_responsive_size(self, base_size):
            return base_size

        def build(self):
            return ft.Container()

        async def update_async(self):
            pass

    def get_theme_manager():
        return None

# Fallback definitions to avoid heavy import chains during development
class CheckpointType(Enum):
    PERIODIC = "periodic"
    BEST = "best"
    MILESTONE = "milestone"
    MANUAL = "manual"
    EMERGENCY = "emergency"

class CheckpointStatus(Enum):
    VALID = "valid"
    CORRUPTED = "corrupted"
    INCOMPLETE = "incomplete"
    VALIDATING = "validating"
    ARCHIVED = "archived"

@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    checkpoint_type: CheckpointType
    status: CheckpointStatus
    file_path: Path
    created_at: datetime
    model_state_size: int
    optimizer_state_size: int
    total_size: int
    checksum: str
    training_step: int
    epoch: int
    loss_value: float
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    description: Optional[str] = None
    parent_checkpoint_id: Optional[str] = None
    is_best: bool = False

# Mock database class for development
class CheckpointRegistryDB:
    def get_checkpoint_by_id(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        # Return a sample checkpoint for testing
        if checkpoint_id:
            return CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                checkpoint_type=CheckpointType.BEST,
                status=CheckpointStatus.VALID,
                file_path=Path(f"/checkpoints/{checkpoint_id}.pt"),
                created_at=datetime.now(),
                model_state_size=1024*1024*100,  # 100MB
                optimizer_state_size=1024*1024*50,  # 50MB
                total_size=1024*1024*150,  # 150MB
                checksum="abc123def456",
                training_step=1000,
                epoch=10,
                loss_value=0.234,
                metrics={"accuracy": 0.95, "f1_score": 0.92, "perplexity": 2.1},
                tags={"best", "milestone"},
                description="Best checkpoint from training run",
                is_best=True
            )
        return None

# Try to import real implementations, fall back to mocks
try:
    from src.modules.logic.checkpoint_management_lg.base_interfaces import (
        CheckpointMetadata as RealCheckpointMetadata,
        CheckpointType as RealCheckpointType,
        CheckpointStatus as RealCheckpointStatus
    )
    # Use real implementations if available
    CheckpointMetadata = RealCheckpointMetadata
    CheckpointType = RealCheckpointType
    CheckpointStatus = RealCheckpointStatus
except ImportError:
    # Use fallback definitions
    pass

try:
    from src.modules.database.checkpoints_db.checkpoint_registry_db.checkpoint_registry_db import CheckpointRegistryDB as RealCheckpointRegistryDB
    CheckpointRegistryDB = RealCheckpointRegistryDB
except ImportError:
    # Use mock implementation
    pass

# Configure logging
logger = logging.getLogger(__name__)


class CheckpointDetailsMode(Enum):
    """Checkpoint details display modes."""
    OVERVIEW = "overview"
    TECHNICAL = "technical"
    METRICS = "metrics"
    COMPARISON = "comparison"
    HISTORY = "history"


@dataclass
class CheckpointDetailsConfig:
    """Configuration for checkpoint details display."""
    mode: CheckpointDetailsMode = CheckpointDetailsMode.OVERVIEW
    show_technical_details: bool = True
    show_metrics_charts: bool = True
    show_file_info: bool = True
    show_validation_status: bool = True
    enable_comparison: bool = True
    enable_export: bool = True
    auto_refresh: bool = False
    refresh_interval: int = 30  # seconds


@dataclass
class CheckpointDetailsState:
    """State management for checkpoint details."""
    current_checkpoint: Optional[CheckpointMetadata] = None
    comparison_checkpoint: Optional[CheckpointMetadata] = None
    is_loading: bool = False
    error_message: Optional[str] = None
    last_updated: Optional[datetime] = None
    validation_results: Dict[str, Any] = field(default_factory=dict)
    metrics_history: List[Dict[str, Any]] = field(default_factory=list)


class CheckpointMetricsDisplay(ThemeAwareUserControl):
    """Component for displaying checkpoint metrics with visualizations."""
    
    def __init__(self, checkpoint: Optional[CheckpointMetadata] = None):
        super().__init__()
        self.checkpoint = checkpoint
        self._metrics_container = None
        
    def build(self) -> ft.Control:
        """Build the metrics display component."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._create_metrics_header(),
                        ft.Divider(height=1, color=palette.outline_variant),
                        self._create_metrics_content()
                    ],
                    spacing=0,
                    expand=True
                ),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=self.get_responsive_size(8),
                padding=0,
                expand=True
            )
            
        except Exception as e:
            logger.error(f"Error building metrics display: {e}")
            return self._create_error_state(str(e))
    
    def _create_metrics_header(self) -> ft.Container:
        """Create the metrics header."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.ANALYTICS,
                        color=palette.primary,
                        size=self.get_responsive_size(20)
                    ),
                    ft.Text(
                        "Training Metrics",
                        style=self.get_text_style('title_medium'),
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=palette.on_surface_variant,
                        icon_size=self.get_responsive_size(16),
                        tooltip="Refresh metrics",
                        on_click=self._on_refresh_metrics
                    )
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )
    
    def _create_metrics_content(self) -> ft.Control:
        """Create the metrics content area."""
        if not self.checkpoint:
            return self._create_empty_metrics_state()
        
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create metrics cards
        metrics_cards = []
        
        # Loss metric
        loss_card = self._create_metric_card(
            "Training Loss",
            f"{self.checkpoint.loss_value:.6f}",
            ft.Icons.TRENDING_DOWN,
            palette.error if self.checkpoint.loss_value > 1.0 else palette.success
        )
        metrics_cards.append(loss_card)
        
        # Additional metrics from checkpoint
        for metric_name, metric_value in self.checkpoint.metrics.items():
            if isinstance(metric_value, (int, float)):
                icon = self._get_metric_icon(metric_name)
                color = self._get_metric_color(metric_name, metric_value)
                
                metric_card = self._create_metric_card(
                    metric_name.replace('_', ' ').title(),
                    f"{metric_value:.4f}" if isinstance(metric_value, float) else str(metric_value),
                    icon,
                    color
                )
                metrics_cards.append(metric_card)
        
        # Arrange metrics in responsive grid
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ResponsiveRow(
                        controls=metrics_cards,
                        spacing=spacing.small,
                        run_spacing=spacing.small
                    )
                ],
                spacing=spacing.medium,
                expand=True
            ),
            padding=spacing.medium,
            expand=True
        )
    
    def _create_metric_card(self, title: str, value: str, icon: str, color: str) -> ft.Control:
        """Create a metric card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                icon,
                                color=color,
                                size=self.get_responsive_size(24)
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                value,
                                style=self.get_text_style('headline_small'),
                                color=palette.on_surface,
                                weight=ft.FontWeight.W_700
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    ft.Text(
                        title,
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.LEFT
                    )
                ],
                spacing=spacing.small,
                horizontal_alignment=ft.CrossAxisAlignment.START
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant,
            border=ft.border.all(1, palette.outline_variant),
            border_radius=self.get_responsive_size(8),
            col={"xs": 12, "sm": 6, "md": 4, "lg": 3}
        )
    
    def _create_empty_metrics_state(self) -> ft.Control:
        """Create empty state for metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ANALYTICS_OUTLINED,
                        color=palette.on_surface_variant,
                        size=self.get_responsive_size(48)
                    ),
                    ft.Text(
                        "No Metrics Available",
                        style=self.get_text_style('title_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Select a checkpoint to view training metrics",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            padding=spacing.large,
            alignment=ft.alignment.center,
            expand=True
        )
    
    def _get_metric_icon(self, metric_name: str) -> str:
        """Get appropriate icon for metric."""
        metric_icons = {
            'accuracy': ft.Icons.TARGET,
            'precision': ft.Icons.PRECISION_MANUFACTURING,
            'recall': ft.Icons.MEMORY,
            'f1_score': ft.Icons.FUNCTIONS,
            'learning_rate': ft.Icons.SPEED,
            'perplexity': ft.Icons.PSYCHOLOGY,
            'bleu_score': ft.Icons.TRANSLATE,
            'rouge_score': ft.Icons.RATE_REVIEW
        }
        return metric_icons.get(metric_name.lower(), ft.Icons.ANALYTICS)
    
    def _get_metric_color(self, metric_name: str, value: Union[int, float]) -> str:
        """Get appropriate color for metric value."""
        palette = self.get_palette()
        
        # Define good/bad ranges for different metrics
        if 'accuracy' in metric_name.lower() or 'f1' in metric_name.lower():
            return palette.success if value > 0.8 else palette.warning if value > 0.6 else palette.error
        elif 'loss' in metric_name.lower() or 'perplexity' in metric_name.lower():
            return palette.success if value < 0.5 else palette.warning if value < 1.0 else palette.error
        else:
            return palette.primary
    
    async def _on_refresh_metrics(self, e):
        """Handle metrics refresh."""
        try:
            # Implement metrics refresh logic
            logger.info("Refreshing checkpoint metrics")
            # Add refresh implementation here
            
        except Exception as ex:
            logger.error(f"Error refreshing metrics: {ex}")
    
    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        color=palette.error,
                        size=self.get_responsive_size(48)
                    ),
                    ft.Text(
                        "Error Loading Metrics",
                        style=self.get_text_style('title_medium'),
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        error_message,
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            padding=spacing.large,
            alignment=ft.alignment.center,
            expand=True
        )
    
    async def update_checkpoint(self, checkpoint: Optional[CheckpointMetadata]):
        """Update the displayed checkpoint."""
        self.checkpoint = checkpoint
        if self.page:
            await self.update_async()


class CheckpointInfoPanel(ThemeAwareUserControl):
    """Component for displaying checkpoint metadata and technical information."""

    def __init__(self, checkpoint: Optional[CheckpointMetadata] = None):
        super().__init__()
        self.checkpoint = checkpoint
        self._info_container = None

    def build(self) -> ft.Control:
        """Build the info panel component."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._create_info_header(),
                        ft.Divider(height=1, color=palette.outline_variant),
                        self._create_info_content()
                    ],
                    spacing=0,
                    expand=True
                ),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=self.get_responsive_size(8),
                padding=0,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building info panel: {e}")
            return self._create_error_state(str(e))

    def _create_info_header(self) -> ft.Container:
        """Create the info panel header."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.INFO,
                        color=palette.primary,
                        size=self.get_responsive_size(20)
                    ),
                    ft.Text(
                        "Checkpoint Information",
                        style=self.get_text_style('title_medium'),
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Container(expand=True),
                    self._create_status_indicator() if self.checkpoint else ft.Container()
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_status_indicator(self) -> ft.Container:
        """Create status indicator for checkpoint."""
        if not self.checkpoint:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()

        status_colors = {
            CheckpointStatus.VALID: palette.success,
            CheckpointStatus.CORRUPTED: palette.error,
            CheckpointStatus.INCOMPLETE: palette.warning,
            CheckpointStatus.VALIDATING: palette.info,
            CheckpointStatus.ARCHIVED: palette.on_surface_variant
        }

        status_icons = {
            CheckpointStatus.VALID: ft.Icons.CHECK_CIRCLE,
            CheckpointStatus.CORRUPTED: ft.Icons.ERROR,
            CheckpointStatus.INCOMPLETE: ft.Icons.WARNING,
            CheckpointStatus.VALIDATING: ft.Icons.HOURGLASS_EMPTY,
            CheckpointStatus.ARCHIVED: ft.Icons.ARCHIVE
        }

        status_color = status_colors.get(self.checkpoint.status, palette.on_surface_variant)
        status_icon = status_icons.get(self.checkpoint.status, ft.Icons.HELP)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        status_icon,
                        color=status_color,
                        size=self.get_responsive_size(16)
                    ),
                    ft.Text(
                        self.checkpoint.status.value.title(),
                        style=self.get_text_style('body_small'),
                        color=status_color,
                        weight=ft.FontWeight.W_500
                    )
                ],
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.symmetric(horizontal=spacing.small, vertical=spacing.xs),
            bgcolor=status_color + "20",  # 20% opacity
            border=ft.border.all(1, status_color),
            border_radius=self.get_responsive_size(12)
        )

    def _create_info_content(self) -> ft.Control:
        """Create the info content area."""
        if not self.checkpoint:
            return self._create_empty_info_state()

        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create info sections
        sections = [
            self._create_basic_info_section(),
            self._create_training_info_section(),
            self._create_file_info_section(),
            self._create_metadata_section()
        ]

        return ft.Container(
            content=ft.Column(
                controls=sections,
                spacing=spacing.medium,
                expand=True,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=spacing.medium,
            expand=True
        )

    def _create_basic_info_section(self) -> ft.Container:
        """Create basic information section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        info_rows = [
            self._create_info_row("Checkpoint ID", self.checkpoint.checkpoint_id),
            self._create_info_row("Type", self.checkpoint.checkpoint_type.value.title()),
            self._create_info_row("Created", self.checkpoint.created_at.strftime("%Y-%m-%d %H:%M:%S")),
            self._create_info_row("Description", self.checkpoint.description or "No description")
        ]

        if self.checkpoint.is_best:
            info_rows.append(
                self._create_info_row("Best Checkpoint", "Yes", highlight=True)
            )

        return self._create_section("Basic Information", info_rows, ft.Icons.BOOKMARK)

    def _create_training_info_section(self) -> ft.Container:
        """Create training information section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        info_rows = [
            self._create_info_row("Epoch", str(self.checkpoint.epoch)),
            self._create_info_row("Training Step", f"{self.checkpoint.training_step:,}"),
            self._create_info_row("Loss Value", f"{self.checkpoint.loss_value:.6f}"),
        ]

        if self.checkpoint.parent_checkpoint_id:
            info_rows.append(
                self._create_info_row("Parent Checkpoint", self.checkpoint.parent_checkpoint_id[:8] + "...")
            )

        return self._create_section("Training Information", info_rows, ft.Icons.SCHOOL)

    def _create_file_info_section(self) -> ft.Container:
        """Create file information section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Format file sizes
        model_size = self._format_file_size(self.checkpoint.model_state_size)
        optimizer_size = self._format_file_size(self.checkpoint.optimizer_state_size)
        total_size = self._format_file_size(self.checkpoint.total_size)

        info_rows = [
            self._create_info_row("File Path", str(self.checkpoint.file_path)),
            self._create_info_row("Model State Size", model_size),
            self._create_info_row("Optimizer State Size", optimizer_size),
            self._create_info_row("Total Size", total_size),
            self._create_info_row("Checksum", self.checkpoint.checksum[:16] + "...")
        ]

        return self._create_section("File Information", info_rows, ft.Icons.FOLDER)

    def _create_metadata_section(self) -> ft.Container:
        """Create metadata section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        info_rows = []

        # Tags
        if self.checkpoint.tags:
            tags_text = ", ".join(sorted(self.checkpoint.tags))
            info_rows.append(self._create_info_row("Tags", tags_text))

        # Additional metrics (non-numeric)
        for key, value in self.checkpoint.metrics.items():
            if not isinstance(value, (int, float)):
                info_rows.append(self._create_info_row(key.replace('_', ' ').title(), str(value)))

        if not info_rows:
            info_rows.append(
                ft.Container(
                    content=ft.Text(
                        "No additional metadata available",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant,
                        italic=True
                    ),
                    padding=spacing.small
                )
            )

        return self._create_section("Metadata", info_rows, ft.Icons.LABEL)

    def _create_section(self, title: str, content: List[ft.Control], icon: str) -> ft.Container:
        """Create a section with title and content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                icon,
                                color=palette.primary,
                                size=self.get_responsive_size(18)
                            ),
                            ft.Text(
                                title,
                                style=self.get_text_style('title_small'),
                                color=palette.on_surface,
                                weight=ft.FontWeight.W_600
                            )
                        ],
                        spacing=spacing.small
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=content,
                            spacing=spacing.xs
                        ),
                        padding=ft.padding.only(left=spacing.large)
                    )
                ],
                spacing=spacing.small
            ),
            padding=spacing.small,
            bgcolor=palette.surface_variant + "40",  # 40% opacity
            border_radius=self.get_responsive_size(6)
        )

    def _create_info_row(self, label: str, value: str, highlight: bool = False) -> ft.Container:
        """Create an information row."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        label_color = palette.primary if highlight else palette.on_surface_variant
        value_color = palette.on_surface if not highlight else palette.primary

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            label + ":",
                            style=self.get_text_style('body_small'),
                            color=label_color,
                            weight=ft.FontWeight.W_500
                        ),
                        width=self.get_responsive_size(120)
                    ),
                    ft.Expanded(
                        child=ft.Text(
                            value,
                            style=self.get_text_style('body_small'),
                            color=value_color,
                            selectable=True
                        )
                    )
                ],
                spacing=spacing.small
            ),
            padding=ft.padding.symmetric(vertical=spacing.xs, horizontal=spacing.small)
        )

    def _create_empty_info_state(self) -> ft.Control:
        """Create empty state for info panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.INFO_OUTLINED,
                        color=palette.on_surface_variant,
                        size=self.get_responsive_size(48)
                    ),
                    ft.Text(
                        "No Checkpoint Selected",
                        style=self.get_text_style('title_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Select a checkpoint to view detailed information",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            padding=spacing.large,
            alignment=ft.alignment.center,
            expand=True
        )

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        color=palette.error,
                        size=self.get_responsive_size(48)
                    ),
                    ft.Text(
                        "Error Loading Information",
                        style=self.get_text_style('title_medium'),
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        error_message,
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            padding=spacing.large,
            alignment=ft.alignment.center,
            expand=True
        )

    async def update_checkpoint(self, checkpoint: Optional[CheckpointMetadata]):
        """Update the displayed checkpoint."""
        self.checkpoint = checkpoint
        if self.page:
            await self.update_async()


class CheckpointDetailsUI(ThemeAwareUserControl):
    """
    Comprehensive checkpoint details display interface.

    Features:
    - Responsive checkpoint details view with breakpoint-aware layouts
    - Multiple display modes (overview, technical, metrics, comparison)
    - Interactive metrics visualization with charts and graphs
    - Technical information panel with file details and validation status
    - Checkpoint comparison capabilities
    - Export and backup operations
    - Theme-aware styling with accessibility compliance
    - Integration with checkpoint database and management system
    - Modern UI/UX with smooth animations and transitions
    - Real-time updates and validation status monitoring
    """

    def __init__(
        self,
        checkpoint_id: Optional[str] = None,
        config: Optional[CheckpointDetailsConfig] = None,
        on_checkpoint_action: Optional[Callable[[str, str], None]] = None
    ):
        super().__init__()
        self.checkpoint_id = checkpoint_id
        self.config = config or CheckpointDetailsConfig()
        self.on_checkpoint_action = on_checkpoint_action

        # State management
        self._state = CheckpointDetailsState()

        # UI components
        self._toolbar = None
        self._mode_tabs = None
        self._content_area = None
        self._metrics_display = None
        self._info_panel = None

        # Database connection
        try:
            self._db = CheckpointRegistryDB()
        except Exception:
            self._db = None
            logger.warning("Could not initialize checkpoint database")

    def build(self) -> ft.Control:
        """Build the checkpoint details interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._create_toolbar(),
                        ft.Divider(height=1, color=palette.outline_variant),
                        self._create_mode_tabs(),
                        ft.Expanded(
                            child=self._create_content_area()
                        )
                    ],
                    spacing=0,
                    expand=True
                ),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=self.get_responsive_size(8),
                padding=0,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building checkpoint details UI: {e}")
            return self._create_error_state(str(e))

    def _create_toolbar(self) -> ft.Container:
        """Create the toolbar with actions."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Checkpoint title
        title_text = "Checkpoint Details"
        if self._state.current_checkpoint:
            title_text = f"Checkpoint {self._state.current_checkpoint.checkpoint_id[:8]}"

        # Action buttons
        action_buttons = []

        if self.config.enable_comparison:
            action_buttons.append(
                ft.IconButton(
                    icon=ft.Icons.COMPARE_ARROWS,
                    icon_color=palette.on_surface_variant,
                    icon_size=self.get_responsive_size(20),
                    tooltip="Compare checkpoints",
                    on_click=self._on_compare_click
                )
            )

        if self.config.enable_export:
            action_buttons.append(
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    icon_color=palette.on_surface_variant,
                    icon_size=self.get_responsive_size(20),
                    tooltip="Export checkpoint",
                    on_click=self._on_export_click
                )
            )

        action_buttons.extend([
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                icon_color=palette.on_surface_variant,
                icon_size=self.get_responsive_size(20),
                tooltip="Refresh details",
                on_click=self._on_refresh_click
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                icon_color=palette.on_surface_variant,
                icon_size=self.get_responsive_size(20),
                tooltip="Settings",
                on_click=self._on_settings_click
            )
        ])

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.BOOKMARK,
                        color=palette.primary,
                        size=self.get_responsive_size(24)
                    ),
                    ft.Text(
                        title_text,
                        style=self.get_text_style('title_large'),
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Container(expand=True),
                    *action_buttons
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_mode_tabs(self) -> ft.Container:
        """Create mode selection tabs."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        tabs = []

        mode_configs = [
            (CheckpointDetailsMode.OVERVIEW, "Overview", ft.Icons.DASHBOARD),
            (CheckpointDetailsMode.TECHNICAL, "Technical", ft.Icons.SETTINGS),
            (CheckpointDetailsMode.METRICS, "Metrics", ft.Icons.ANALYTICS),
            (CheckpointDetailsMode.COMPARISON, "Compare", ft.Icons.COMPARE_ARROWS),
            (CheckpointDetailsMode.HISTORY, "History", ft.Icons.HISTORY)
        ]

        for mode, label, icon in mode_configs:
            is_active = self.config.mode == mode

            tab = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icon,
                            color=palette.primary if is_active else palette.on_surface_variant,
                            size=self.get_responsive_size(16)
                        ),
                        ft.Text(
                            label,
                            style=self.get_text_style('body_medium'),
                            color=palette.primary if is_active else palette.on_surface_variant,
                            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                padding=ft.padding.symmetric(horizontal=spacing.medium, vertical=spacing.small),
                bgcolor=palette.primary_container if is_active else None,
                border=ft.border.all(
                    1,
                    palette.primary if is_active else palette.outline_variant
                ),
                border_radius=self.get_responsive_size(20),
                on_click=lambda e, m=mode: self._on_mode_change(m),
                ink=True
            )
            tabs.append(tab)

        return ft.Container(
            content=ft.Row(
                controls=tabs,
                spacing=spacing.small,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=spacing.medium,
            bgcolor=palette.surface
        )

    def _create_content_area(self) -> ft.Control:
        """Create the main content area based on current mode."""
        try:
            if self._state.is_loading:
                return self._create_loading_state()

            if self._state.error_message:
                return self._create_error_state(self._state.error_message)

            if not self._state.current_checkpoint:
                return self._create_empty_state()

            # Create content based on mode
            if self.config.mode == CheckpointDetailsMode.OVERVIEW:
                return self._create_overview_content()
            elif self.config.mode == CheckpointDetailsMode.TECHNICAL:
                return self._create_technical_content()
            elif self.config.mode == CheckpointDetailsMode.METRICS:
                return self._create_metrics_content()
            elif self.config.mode == CheckpointDetailsMode.COMPARISON:
                return self._create_comparison_content()
            elif self.config.mode == CheckpointDetailsMode.HISTORY:
                return self._create_history_content()
            else:
                return self._create_overview_content()

        except Exception as e:
            logger.error(f"Error creating content area: {e}")
            return self._create_error_state(str(e))

    def _create_overview_content(self) -> ft.Control:
        """Create overview content with key information and metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create metrics display
        self._metrics_display = CheckpointMetricsDisplay(self._state.current_checkpoint)

        # Create info panel
        self._info_panel = CheckpointInfoPanel(self._state.current_checkpoint)

        return ft.Container(
            content=ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        content=self._metrics_display,
                        col={"xs": 12, "md": 6},
                        padding=spacing.small
                    ),
                    ft.Container(
                        content=self._info_panel,
                        col={"xs": 12, "md": 6},
                        padding=spacing.small
                    )
                ],
                spacing=spacing.medium,
                run_spacing=spacing.medium
            ),
            padding=spacing.medium,
            expand=True
        )

    def _create_technical_content(self) -> ft.Control:
        """Create technical details content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create detailed info panel
        self._info_panel = CheckpointInfoPanel(self._state.current_checkpoint)

        return ft.Container(
            content=self._info_panel,
            padding=spacing.medium,
            expand=True
        )

    def _create_metrics_content(self) -> ft.Control:
        """Create metrics visualization content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create detailed metrics display
        self._metrics_display = CheckpointMetricsDisplay(self._state.current_checkpoint)

        return ft.Container(
            content=self._metrics_display,
            padding=spacing.medium,
            expand=True
        )

    def _create_comparison_content(self) -> ft.Control:
        """Create checkpoint comparison content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self._state.comparison_checkpoint:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.COMPARE_ARROWS,
                            color=palette.on_surface_variant,
                            size=self.get_responsive_size(48)
                        ),
                        ft.Text(
                            "No Comparison Checkpoint",
                            style=self.get_text_style('title_medium'),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Select a checkpoint to compare with the current one",
                            style=self.get_text_style('body_medium'),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Select Checkpoint",
                            icon=ft.Icons.SEARCH,
                            on_click=self._on_select_comparison_checkpoint
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.medium
                ),
                padding=spacing.large,
                alignment=ft.alignment.center,
                expand=True
            )

        # Create side-by-side comparison
        current_panel = CheckpointInfoPanel(self._state.current_checkpoint)
        comparison_panel = CheckpointInfoPanel(self._state.comparison_checkpoint)

        return ft.Container(
            content=ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Current Checkpoint",
                                    style=self.get_text_style('title_medium'),
                                    color=palette.primary,
                                    text_align=ft.TextAlign.CENTER
                                ),
                                current_panel
                            ],
                            spacing=spacing.small
                        ),
                        col={"xs": 12, "md": 6},
                        padding=spacing.small
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Comparison Checkpoint",
                                    style=self.get_text_style('title_medium'),
                                    color=palette.secondary,
                                    text_align=ft.TextAlign.CENTER
                                ),
                                comparison_panel
                            ],
                            spacing=spacing.small
                        ),
                        col={"xs": 12, "md": 6},
                        padding=spacing.small
                    )
                ],
                spacing=spacing.medium,
                run_spacing=spacing.medium
            ),
            padding=spacing.medium,
            expand=True
        )

    def _create_history_content(self) -> ft.Control:
        """Create checkpoint history content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.HISTORY,
                        color=palette.on_surface_variant,
                        size=self.get_responsive_size(48)
                    ),
                    ft.Text(
                        "Checkpoint History",
                        style=self.get_text_style('title_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "History view coming soon",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            padding=spacing.large,
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_loading_state(self) -> ft.Control:
        """Create loading state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(
                        color=palette.primary,
                        width=self.get_responsive_size(48),
                        height=self.get_responsive_size(48)
                    ),
                    ft.Text(
                        "Loading checkpoint details...",
                        style=self.get_text_style('title_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            padding=spacing.large,
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_empty_state(self) -> ft.Control:
        """Create empty state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.BOOKMARK_BORDER,
                        color=palette.on_surface_variant,
                        size=self.get_responsive_size(64)
                    ),
                    ft.Text(
                        "No Checkpoint Selected",
                        style=self.get_text_style('title_large'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Select a checkpoint from the list to view its details",
                        style=self.get_text_style('body_large'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.large
            ),
            padding=spacing.extra_large,
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        color=palette.error,
                        size=self.get_responsive_size(64)
                    ),
                    ft.Text(
                        "Error Loading Checkpoint",
                        style=self.get_text_style('title_large'),
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        error_message,
                        style=self.get_text_style('body_large'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.ElevatedButton(
                        text="Retry",
                        icon=ft.Icons.REFRESH,
                        on_click=self._on_refresh_click
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.large
            ),
            padding=spacing.extra_large,
            alignment=ft.alignment.center,
            expand=True
        )

    # Event handlers
    async def _on_mode_change(self, mode: CheckpointDetailsMode):
        """Handle mode change."""
        try:
            self.config.mode = mode
            if self.page:
                await self.update_async()

        except Exception as e:
            logger.error(f"Error changing mode: {e}")

    async def _on_compare_click(self, e):
        """Handle compare button click."""
        try:
            if self.on_checkpoint_action:
                self.on_checkpoint_action("compare", self.checkpoint_id or "")

        except Exception as ex:
            logger.error(f"Error handling compare click: {ex}")

    async def _on_export_click(self, e):
        """Handle export button click."""
        try:
            if self.on_checkpoint_action:
                self.on_checkpoint_action("export", self.checkpoint_id or "")

        except Exception as ex:
            logger.error(f"Error handling export click: {ex}")

    async def _on_refresh_click(self, e):
        """Handle refresh button click."""
        try:
            await self.load_checkpoint(self.checkpoint_id)

        except Exception as ex:
            logger.error(f"Error handling refresh click: {ex}")

    async def _on_settings_click(self, e):
        """Handle settings button click."""
        try:
            if self.on_checkpoint_action:
                self.on_checkpoint_action("settings", self.checkpoint_id or "")

        except Exception as ex:
            logger.error(f"Error handling settings click: {ex}")

    async def _on_select_comparison_checkpoint(self, e):
        """Handle select comparison checkpoint."""
        try:
            if self.on_checkpoint_action:
                self.on_checkpoint_action("select_comparison", self.checkpoint_id or "")

        except Exception as ex:
            logger.error(f"Error selecting comparison checkpoint: {ex}")

    # Public API methods
    async def load_checkpoint(self, checkpoint_id: Optional[str]):
        """Load checkpoint data."""
        try:
            self._state.is_loading = True
            self._state.error_message = None
            self.checkpoint_id = checkpoint_id

            if self.page:
                await self.update_async()

            if not checkpoint_id or not self._db:
                self._state.current_checkpoint = None
                self._state.is_loading = False
                if self.page:
                    await self.update_async()
                return

            # Load checkpoint from database
            checkpoint = self._db.get_checkpoint_by_id(checkpoint_id)

            if checkpoint:
                self._state.current_checkpoint = checkpoint
                self._state.last_updated = datetime.now()

                # Update child components
                if self._metrics_display:
                    await self._metrics_display.update_checkpoint(checkpoint)
                if self._info_panel:
                    await self._info_panel.update_checkpoint(checkpoint)
            else:
                self._state.error_message = f"Checkpoint {checkpoint_id} not found"

            self._state.is_loading = False

            if self.page:
                await self.update_async()

        except Exception as e:
            logger.error(f"Error loading checkpoint {checkpoint_id}: {e}")
            self._state.is_loading = False
            self._state.error_message = str(e)

            if self.page:
                await self.update_async()

    async def set_comparison_checkpoint(self, checkpoint_id: Optional[str]):
        """Set comparison checkpoint."""
        try:
            if not checkpoint_id or not self._db:
                self._state.comparison_checkpoint = None
                if self.page:
                    await self.update_async()
                return

            checkpoint = self._db.get_checkpoint_by_id(checkpoint_id)
            self._state.comparison_checkpoint = checkpoint

            if self.page:
                await self.update_async()

        except Exception as e:
            logger.error(f"Error setting comparison checkpoint {checkpoint_id}: {e}")

    async def refresh_data(self):
        """Refresh checkpoint data."""
        await self.load_checkpoint(self.checkpoint_id)

    def get_current_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get currently displayed checkpoint."""
        return self._state.current_checkpoint

    def get_comparison_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get comparison checkpoint."""
        return self._state.comparison_checkpoint

    def set_config(self, config: CheckpointDetailsConfig):
        """Update configuration."""
        self.config = config
        if self.page:
            asyncio.create_task(self.update_async())

    def get_state(self) -> CheckpointDetailsState:
        """Get current state."""
        return self._state
