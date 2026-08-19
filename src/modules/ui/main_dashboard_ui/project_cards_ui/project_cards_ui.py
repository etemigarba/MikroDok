"""
Module: project_cards_ui
Description: Interactive project card components displaying project metadata, status, and quick actions.
            Provides responsive grid layout for project management with comprehensive filtering, sorting,
            and action capabilities. Fully integrated with theme_system_ui.py for consistent styling
            and responsive design across all screen sizes.
Phase: 1
Location: /src/modules/ui/main_dashboard_ui/project_cards_ui/project_cards_ui.py
"""

# Standard library imports
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    ResponsiveLayoutManager,
    ScreenSize
)

# Configure logging
logger = logging.getLogger(__name__)


class ProjectCardLayout(Enum):
    """Project card layout modes."""
    GRID = "grid"
    LIST = "list"
    COMPACT = "compact"


class ProjectStatus(Enum):
    """Project status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ProjectType(Enum):
    """Project type enumeration."""
    FINE_TUNING = "fine_tuning"
    RAG_TRAINING = "rag_training"
    CUSTOM_MODEL = "custom_model"
    INFERENCE_ONLY = "inference_only"


class SortOption(Enum):
    """Sorting options for project cards."""
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_CREATED_ASC = "date_created_asc"
    DATE_CREATED_DESC = "date_created_desc"
    DATE_MODIFIED_ASC = "date_modified_asc"
    DATE_MODIFIED_DESC = "date_modified_desc"
    PROGRESS_ASC = "progress_asc"
    PROGRESS_DESC = "progress_desc"
    STATUS_ASC = "status_asc"
    STATUS_DESC = "status_desc"


@dataclass
class ProjectCardData:
    """Data structure for project card information."""
    id: str
    name: str
    description: str
    project_type: ProjectType
    status: ProjectStatus
    progress: float = 0.0  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    document_count: int = 0
    model_count: int = 0
    training_session_count: int = 0
    total_size_mb: float = 0.0
    tags: List[str] = field(default_factory=list)
    priority: int = 0  # 0-10 scale
    estimated_duration_hours: Optional[float] = None
    complexity_score: Optional[float] = None  # 0.0-1.0 scale
    last_activity: Optional[datetime] = None
    thumbnail_path: Optional[str] = None
    
    @property
    def progress_percentage(self) -> int:
        """Get progress as percentage."""
        return int(self.progress * 100)
    
    @property
    def status_color(self) -> str:
        """Get status-appropriate color."""
        status_colors = {
            ProjectStatus.ACTIVE: "primary",
            ProjectStatus.COMPLETED: "success", 
            ProjectStatus.PAUSED: "warning",
            ProjectStatus.ARCHIVED: "text_disabled",
            ProjectStatus.ERROR: "error"
        }
        return status_colors.get(self.status, "text_secondary")
    
    @property
    def type_icon(self) -> str:
        """Get type-appropriate icon."""
        type_icons = {
            ProjectType.FINE_TUNING: "TUNE",
            ProjectType.RAG_TRAINING: "SEARCH",
            ProjectType.CUSTOM_MODEL: "PSYCHOLOGY",
            ProjectType.INFERENCE_ONLY: "PLAY_ARROW"
        }
        return type_icons.get(self.project_type, "FOLDER")


@dataclass
class ProjectCardConfig:
    """Configuration for project cards display."""
    layout: ProjectCardLayout = ProjectCardLayout.GRID
    show_thumbnails: bool = True
    show_progress: bool = True
    show_metadata: bool = True
    show_actions: bool = True
    show_tags: bool = True
    max_description_length: int = 100
    max_tags_displayed: int = 3
    enable_hover_effects: bool = True
    enable_selection: bool = True
    enable_drag_drop: bool = False


class ProjectCardsUI(ThemeAwareUserControl):
    """
    Interactive project card components with responsive grid layout.
    
    Features:
    - Responsive grid layout adapting to screen size
    - Project filtering by status, type, and tags
    - Sorting by various criteria (name, date, progress, status)
    - Interactive project cards with hover effects and actions
    - Empty state and loading state handling
    - Full theme system integration with responsive design
    - Accessibility compliance with keyboard navigation
    - Project action callbacks (open, edit, delete, archive, duplicate)
    """
    
    def __init__(self,
                 projects: Optional[List[ProjectCardData]] = None,
                 config: Optional[ProjectCardConfig] = None,
                 on_project_open: Optional[Callable[[str], None]] = None,
                 on_project_edit: Optional[Callable[[str], None]] = None,
                 on_project_delete: Optional[Callable[[str], None]] = None,
                 on_project_archive: Optional[Callable[[str], None]] = None,
                 on_project_duplicate: Optional[Callable[[str], None]] = None,
                 on_create_new: Optional[Callable[[], None]] = None,
                 **kwargs):
        """
        Initialize project cards UI.
        
        Args:
            projects: List of project data to display
            config: Display configuration options
            on_project_open: Callback for opening a project
            on_project_edit: Callback for editing a project
            on_project_delete: Callback for deleting a project
            on_project_archive: Callback for archiving a project
            on_project_duplicate: Callback for duplicating a project
            on_create_new: Callback for creating new project
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Data and configuration
        self._projects = projects or []
        self._config = config or ProjectCardConfig()
        self._filtered_projects = self._projects.copy()
        self._selected_projects: List[str] = []
        
        # Callbacks
        self._on_project_open = on_project_open
        self._on_project_edit = on_project_edit
        self._on_project_delete = on_project_delete
        self._on_project_archive = on_project_archive
        self._on_project_duplicate = on_project_duplicate
        self._on_create_new = on_create_new
        
        # State management
        self._is_loading = False
        self._current_sort = SortOption.DATE_MODIFIED_DESC
        self._status_filter: Optional[ProjectStatus] = None
        self._type_filter: Optional[ProjectType] = None
        self._tag_filter: Optional[str] = None
        self._search_query = ""
        
        # UI components
        self._search_field: Optional[ft.TextField] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._sort_dropdown: Optional[ft.Dropdown] = None
        self._layout_toggle: Optional[ft.SegmentedButton] = None
        self._project_grid: Optional[ft.Control] = None
        self._loading_indicator: Optional[ft.ProgressRing] = None
        self._empty_state: Optional[ft.Control] = None
        
        # Performance optimization
        self._card_cache: Dict[str, ft.Control] = {}
        self._last_update_time = datetime.now()
        
        logger.info("ProjectCardsUI initialized")

    def build(self) -> ft.Control:
        """Build the project cards interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Main container with responsive layout
            return ft.Container(
                content=ft.Column([
                    self._create_header_section(),
                    ft.Container(height=spacing.md),
                    self._create_filter_section(),
                    ft.Container(height=spacing.lg),
                    self._create_content_section()
                ], scroll=ft.ScrollMode.AUTO),
                bgcolor=palette.background_primary,
                padding=ft.padding.all(self.get_responsive_padding()),
                expand=True
            )

        except Exception as e:
            logger.error(f"Failed to build project cards UI: {e}")
            return self._create_error_display(str(e))

    def _create_header_section(self) -> ft.Control:
        """Create header section with title and create button."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Row([
                ft.Text(
                    "Projects",
                    style=self.get_text_style("headlineMedium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600,
                    expand=True
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Text(
                            f"{len(self._filtered_projects)} projects",
                            style=self.get_text_style("bodyMedium"),
                            color=palette.text_secondary
                        ),
                        ft.Container(width=spacing.md),
                        ft.ElevatedButton(
                            text="New Project",
                            icon=self.get_icon("ADD"),
                            on_click=self._handle_create_new,
                            style=ft.ButtonStyle(
                                bgcolor=palette.primary,
                                color=palette.text_primary,
                                padding=ft.padding.symmetric(
                                    horizontal=self.get_breakpoint_value(16, 20, 24, 28),
                                    vertical=self.get_breakpoint_value(8, 10, 12, 14)
                                )
                            )
                        )
                    ], tight=True)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        except Exception as e:
            logger.error(f"Error creating header section: {e}")
            return ft.Container()

    def _create_filter_section(self) -> ft.Control:
        """Create filter and search controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Search field
            self._search_field = ft.TextField(
                hint_text="Search projects...",
                prefix_icon=self.get_icon("SEARCH"),
                border_radius=self.get_breakpoint_value(8, 10, 12, 14),
                bgcolor=palette.surface,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=self.get_text_style("bodyMedium"),
                hint_style=self.get_text_style("bodyMedium"),
                on_change=self._handle_search_change,
                expand=True
            )

            # Filter dropdown
            self._filter_dropdown = ft.Dropdown(
                hint_text="Filter by status",
                options=[
                    ft.dropdown.Option("all", "All Status"),
                    ft.dropdown.Option("active", "Active"),
                    ft.dropdown.Option("completed", "Completed"),
                    ft.dropdown.Option("paused", "Paused"),
                    ft.dropdown.Option("archived", "Archived"),
                    ft.dropdown.Option("error", "Error")
                ],
                value="all",
                bgcolor=palette.surface,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=self.get_text_style("bodyMedium"),
                on_change=self._handle_filter_change,
                width=self.get_breakpoint_value(120, 140, 160, 180)
            )

            # Sort dropdown
            self._sort_dropdown = ft.Dropdown(
                hint_text="Sort by",
                options=[
                    ft.dropdown.Option("date_modified_desc", "Recently Modified"),
                    ft.dropdown.Option("date_created_desc", "Recently Created"),
                    ft.dropdown.Option("name_asc", "Name A-Z"),
                    ft.dropdown.Option("name_desc", "Name Z-A"),
                    ft.dropdown.Option("progress_desc", "Progress High-Low"),
                    ft.dropdown.Option("progress_asc", "Progress Low-High")
                ],
                value="date_modified_desc",
                bgcolor=palette.surface,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=self.get_text_style("bodyMedium"),
                on_change=self._handle_sort_change,
                width=self.get_breakpoint_value(140, 160, 180, 200)
            )

            # Layout toggle (only show on larger screens)
            layout_controls = []
            if not self.is_mobile():
                self._layout_toggle = ft.SegmentedButton(
                    segments=[
                        ft.Segment(
                            value="grid",
                            icon=self.get_icon("GRID_VIEW"),
                            tooltip="Grid View"
                        ),
                        ft.Segment(
                            value="list",
                            icon=self.get_icon("LIST"),
                            tooltip="List View"
                        )
                    ],
                    selected={"grid"},
                    on_change=self._handle_layout_change,
                    style=ft.ButtonStyle(
                        bgcolor=palette.surface,
                        side=ft.BorderSide(1, palette.outline)
                    )
                )
                layout_controls.append(self._layout_toggle)

            # Responsive layout for filter controls
            if self.is_mobile():
                return ft.Column([
                    self._search_field,
                    ft.Container(height=spacing.sm),
                    ft.Row([
                        self._filter_dropdown,
                        ft.Container(width=spacing.sm),
                        self._sort_dropdown
                    ], expand=True)
                ], spacing=0)
            else:
                return ft.Row([
                    self._search_field,
                    ft.Container(width=spacing.md),
                    self._filter_dropdown,
                    ft.Container(width=spacing.sm),
                    self._sort_dropdown,
                    ft.Container(width=spacing.md),
                    *layout_controls
                ], alignment=ft.MainAxisAlignment.START)

        except Exception as e:
            logger.error(f"Error creating filter section: {e}")
            return ft.Container()

    def _create_content_section(self) -> ft.Control:
        """Create main content section with project cards or empty state."""
        try:
            if self._is_loading:
                return self._create_loading_state()
            elif not self._filtered_projects:
                return self._create_empty_state()
            else:
                return self._create_project_grid()

        except Exception as e:
            logger.error(f"Error creating content section: {e}")
            return self._create_error_display(str(e))

    def _create_project_grid(self) -> ft.Control:
        """Create responsive grid of project cards."""
        try:
            spacing = self.get_spacing()

            # Create project cards
            project_cards = []
            for project in self._filtered_projects:
                card = self._create_project_card(project)
                project_cards.append(card)

            # Create responsive grid
            if self._config.layout == ProjectCardLayout.LIST or self.is_mobile():
                # List layout for mobile or when list mode is selected
                return ft.Column(
                    controls=project_cards,
                    spacing=spacing.md,
                    scroll=ft.ScrollMode.AUTO
                )
            else:
                # Grid layout for larger screens
                return self.create_responsive_grid(
                    children=project_cards,
                    mobile_cols=1,
                    tablet_cols=2,
                    desktop_cols=3,
                    large_cols=4,
                    spacing=spacing.md,
                    run_spacing=spacing.md
                )

        except Exception as e:
            logger.error(f"Error creating project grid: {e}")
            return ft.Container()

    def _create_project_card(self, project: ProjectCardData) -> ft.Control:
        """Create individual project card."""
        try:
            # Check cache first for performance
            cache_key = f"{project.id}_{project.updated_at.isoformat()}"
            if cache_key in self._card_cache:
                return self._card_cache[cache_key]

            palette = self.get_palette()
            spacing = self.get_spacing()

            # Card content based on layout
            if self._config.layout == ProjectCardLayout.COMPACT:
                card_content = self._create_compact_card_content(project)
            elif self._config.layout == ProjectCardLayout.LIST:
                card_content = self._create_list_card_content(project)
            else:
                card_content = self._create_grid_card_content(project)

            # Main card container
            card = ft.Container(
                content=card_content,
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline),
                border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 10, 12, 14)),
                padding=ft.padding.all(spacing.md),
                ink=True,
                on_click=lambda e, pid=project.id: self._handle_project_click(pid),
                on_hover=self._handle_card_hover if self._config.enable_hover_effects else None,
                animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
                data=project.id,
                # Accessibility
                tooltip=f"{project.name} - {project.status.value.title()} - {project.progress_percentage}% complete"
            )

            # Cache the card for performance
            self._card_cache[cache_key] = card

            return card

        except Exception as e:
            logger.error(f"Error creating project card for {project.id}: {e}")
            return ft.Container()

    def _create_grid_card_content(self, project: ProjectCardData) -> ft.Control:
        """Create grid layout card content."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Column([
                # Header with icon and actions
                ft.Row([
                    ft.Icon(
                        self.get_icon(project.type_icon),
                        size=self.get_breakpoint_value(20, 22, 24, 26),
                        color=getattr(palette, project.status_color, palette.primary)
                    ),
                    ft.Container(expand=True),
                    self._create_card_actions_menu(project.id) if self._config.show_actions else ft.Container()
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=spacing.sm),

                # Project name
                ft.Text(
                    project.name,
                    style=self.get_text_style("titleMedium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=1
                ),

                # Project description
                ft.Text(
                    self._truncate_text(project.description, self._config.max_description_length),
                    style=self.get_text_style("bodyMedium"),
                    color=palette.text_secondary,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=2
                ),

                ft.Container(height=spacing.sm),

                # Progress bar (if enabled)
                self._create_progress_indicator(project) if self._config.show_progress else ft.Container(),

                ft.Container(height=spacing.sm),

                # Metadata row
                self._create_metadata_row(project) if self._config.show_metadata else ft.Container(),

                # Tags (if enabled)
                self._create_tags_row(project) if self._config.show_tags and project.tags else ft.Container()

            ], spacing=0, tight=True)

        except Exception as e:
            logger.error(f"Error creating grid card content: {e}")
            return ft.Container()

    def _create_list_card_content(self, project: ProjectCardData) -> ft.Control:
        """Create list layout card content."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Row([
                # Left section - Icon and basic info
                ft.Row([
                    ft.Icon(
                        self.get_icon(project.type_icon),
                        size=self.get_breakpoint_value(24, 26, 28, 30),
                        color=getattr(palette, project.status_color, palette.primary)
                    ),
                    ft.Container(width=spacing.md),
                    ft.Column([
                        ft.Text(
                            project.name,
                            style=self.get_text_style("titleMedium"),
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1
                        ),
                        ft.Text(
                            self._truncate_text(project.description, 80),
                            style=self.get_text_style("bodySmall"),
                            color=palette.text_secondary,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1
                        )
                    ], spacing=2, tight=True)
                ], tight=True),

                # Center section - Progress and metadata
                ft.Container(
                    content=ft.Column([
                        self._create_progress_indicator(project, compact=True) if self._config.show_progress else ft.Container(),
                        self._create_status_badge(project)
                    ], spacing=4, tight=True),
                    expand=True
                ),

                # Right section - Actions
                self._create_card_actions_menu(project.id) if self._config.show_actions else ft.Container()

            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        except Exception as e:
            logger.error(f"Error creating list card content: {e}")
            return ft.Container()

    def _create_compact_card_content(self, project: ProjectCardData) -> ft.Control:
        """Create compact layout card content."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Row([
                ft.Icon(
                    self.get_icon(project.type_icon),
                    size=self.get_breakpoint_value(18, 20, 22, 24),
                    color=getattr(palette, project.status_color, palette.primary)
                ),
                ft.Container(width=spacing.sm),
                ft.Expanded(
                    child=ft.Text(
                        project.name,
                        style=self.get_text_style("bodyMedium"),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_500,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1
                    )
                ),
                ft.Text(
                    f"{project.progress_percentage}%",
                    style=self.get_text_style("bodySmall"),
                    color=palette.text_secondary
                ),
                ft.Container(width=spacing.sm),
                self._create_status_badge(project, compact=True)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        except Exception as e:
            logger.error(f"Error creating compact card content: {e}")
            return ft.Container()

    def _create_progress_indicator(self, project: ProjectCardData, compact: bool = False) -> ft.Control:
        """Create progress indicator for project."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            if compact:
                return ft.Container(
                    content=ft.ProgressBar(
                        value=project.progress,
                        color=getattr(palette, project.status_color, palette.primary),
                        bgcolor=palette.surface_variant,
                        height=self.get_breakpoint_value(3, 4, 5, 6)
                    ),
                    width=self.get_breakpoint_value(60, 80, 100, 120)
                )
            else:
                return ft.Column([
                    ft.Row([
                        ft.Text(
                            "Progress",
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_secondary
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            f"{project.progress_percentage}%",
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_500
                        )
                    ]),
                    ft.Container(height=spacing.xs),
                    ft.ProgressBar(
                        value=project.progress,
                        color=getattr(palette, project.status_color, palette.primary),
                        bgcolor=palette.surface_variant,
                        height=self.get_breakpoint_value(4, 5, 6, 8)
                    )
                ], spacing=0, tight=True)

        except Exception as e:
            logger.error(f"Error creating progress indicator: {e}")
            return ft.Container()

    def _create_status_badge(self, project: ProjectCardData, compact: bool = False) -> ft.Control:
        """Create status badge for project."""
        try:
            palette = self.get_palette()

            status_colors = {
                ProjectStatus.ACTIVE: palette.primary,
                ProjectStatus.COMPLETED: palette.success,
                ProjectStatus.PAUSED: palette.warning,
                ProjectStatus.ARCHIVED: palette.text_disabled,
                ProjectStatus.ERROR: palette.error
            }

            badge_color = status_colors.get(project.status, palette.text_secondary)

            return ft.Container(
                content=ft.Text(
                    project.status.value.title(),
                    style=self.get_text_style("labelSmall" if compact else "labelMedium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                bgcolor=self.get_color_with_opacity(badge_color, 0.2),
                border=ft.border.all(1, badge_color),
                border_radius=ft.border_radius.all(self.get_breakpoint_value(4, 6, 8, 10)),
                padding=ft.padding.symmetric(
                    horizontal=self.get_breakpoint_value(6, 8, 10, 12),
                    vertical=self.get_breakpoint_value(2, 3, 4, 5)
                )
            )

        except Exception as e:
            logger.error(f"Error creating status badge: {e}")
            return ft.Container()

    def _create_metadata_row(self, project: ProjectCardData) -> ft.Control:
        """Create metadata row with document count, models, etc."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            metadata_items = []

            # Document count
            if project.document_count > 0:
                metadata_items.append(
                    ft.Row([
                        ft.Icon(
                            self.get_icon("DESCRIPTION"),
                            size=self.get_breakpoint_value(14, 16, 18, 20),
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            str(project.document_count),
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_secondary
                        )
                    ], spacing=4, tight=True)
                )

            # Model count
            if project.model_count > 0:
                metadata_items.append(
                    ft.Row([
                        ft.Icon(
                            self.get_icon("PSYCHOLOGY"),
                            size=self.get_breakpoint_value(14, 16, 18, 20),
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            str(project.model_count),
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_secondary
                        )
                    ], spacing=4, tight=True)
                )

            # Last activity
            if project.last_activity:
                time_ago = self._format_time_ago(project.last_activity)
                metadata_items.append(
                    ft.Row([
                        ft.Icon(
                            self.get_icon("SCHEDULE"),
                            size=self.get_breakpoint_value(14, 16, 18, 20),
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            time_ago,
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_secondary
                        )
                    ], spacing=4, tight=True)
                )

            if not metadata_items:
                return ft.Container()

            return ft.Row(
                controls=metadata_items,
                spacing=spacing.md,
                wrap=True
            )

        except Exception as e:
            logger.error(f"Error creating metadata row: {e}")
            return ft.Container()

    def _create_tags_row(self, project: ProjectCardData) -> ft.Control:
        """Create tags row for project."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            if not project.tags:
                return ft.Container()

            # Limit number of tags displayed
            displayed_tags = project.tags[:self._config.max_tags_displayed]
            remaining_count = len(project.tags) - len(displayed_tags)

            tag_widgets = []
            for tag in displayed_tags:
                tag_widgets.append(
                    ft.Container(
                        content=ft.Text(
                            tag,
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_primary
                        ),
                        bgcolor=palette.surface_variant,
                        border_radius=ft.border_radius.all(self.get_breakpoint_value(4, 6, 8, 10)),
                        padding=ft.padding.symmetric(
                            horizontal=self.get_breakpoint_value(6, 8, 10, 12),
                            vertical=self.get_breakpoint_value(2, 3, 4, 5)
                        )
                    )
                )

            # Add "more" indicator if there are additional tags
            if remaining_count > 0:
                tag_widgets.append(
                    ft.Container(
                        content=ft.Text(
                            f"+{remaining_count}",
                            style=self.get_text_style("labelSmall"),
                            color=palette.text_secondary
                        ),
                        bgcolor=palette.surface_variant,
                        border_radius=ft.border_radius.all(self.get_breakpoint_value(4, 6, 8, 10)),
                        padding=ft.padding.symmetric(
                            horizontal=self.get_breakpoint_value(6, 8, 10, 12),
                            vertical=self.get_breakpoint_value(2, 3, 4, 5)
                        )
                    )
                )

            return ft.Row(
                controls=tag_widgets,
                spacing=spacing.xs,
                wrap=True
            )

        except Exception as e:
            logger.error(f"Error creating tags row: {e}")
            return ft.Container()

    def _create_card_actions_menu(self, project_id: str) -> ft.Control:
        """Create actions menu for project card."""
        try:
            palette = self.get_palette()

            menu_items = [
                ft.PopupMenuItem(
                    text="Open",
                    icon=self.get_icon("OPEN_IN_NEW"),
                    on_click=lambda e, pid=project_id: self._handle_project_action("open", pid)
                ),
                ft.PopupMenuItem(
                    text="Edit",
                    icon=self.get_icon("EDIT"),
                    on_click=lambda e, pid=project_id: self._handle_project_action("edit", pid)
                ),
                ft.PopupMenuItem(),  # Divider
                ft.PopupMenuItem(
                    text="Duplicate",
                    icon=self.get_icon("CONTENT_COPY"),
                    on_click=lambda e, pid=project_id: self._handle_project_action("duplicate", pid)
                ),
                ft.PopupMenuItem(
                    text="Archive",
                    icon=self.get_icon("ARCHIVE"),
                    on_click=lambda e, pid=project_id: self._handle_project_action("archive", pid)
                ),
                ft.PopupMenuItem(),  # Divider
                ft.PopupMenuItem(
                    text="Delete",
                    icon=self.get_icon("DELETE"),
                    on_click=lambda e, pid=project_id: self._handle_project_action("delete", pid)
                )
            ]

            return ft.PopupMenuButton(
                icon=self.get_icon("MORE_VERT"),
                icon_size=self.get_breakpoint_value(18, 20, 22, 24),
                icon_color=palette.text_secondary,
                items=menu_items,
                tooltip="Project actions"
            )

        except Exception as e:
            logger.error(f"Error creating card actions menu: {e}")
            return ft.Container()

    def _create_loading_state(self) -> ft.Control:
        """Create loading state display."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column([
                    ft.ProgressRing(
                        width=self.get_breakpoint_value(40, 50, 60, 70),
                        height=self.get_breakpoint_value(40, 50, 60, 70),
                        color=palette.primary
                    ),
                    ft.Container(height=spacing.md),
                    ft.Text(
                        "Loading projects...",
                        style=self.get_text_style("bodyLarge"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                height=300
            )

        except Exception as e:
            logger.error(f"Error creating loading state: {e}")
            return ft.Container()

    def _create_empty_state(self) -> ft.Control:
        """Create empty state display."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column([
                    ft.Icon(
                        self.get_icon("FOLDER_OPEN"),
                        size=self.get_breakpoint_value(60, 70, 80, 90),
                        color=palette.text_disabled
                    ),
                    ft.Container(height=spacing.lg),
                    ft.Text(
                        "No projects found" if self._search_query or self._status_filter else "No projects yet",
                        style=self.get_text_style("headlineSmall"),
                        color=palette.text_primary,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Container(height=spacing.sm),
                    ft.Text(
                        "Try adjusting your filters or search terms" if self._search_query or self._status_filter
                        else "Create your first project to get started with MikroDok",
                        style=self.get_text_style("bodyLarge"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=spacing.xl),
                    ft.ElevatedButton(
                        text="Clear Filters" if self._search_query or self._status_filter else "Create Project",
                        icon=self.get_icon("CLEAR_ALL") if self._search_query or self._status_filter else self.get_icon("ADD"),
                        on_click=self._handle_clear_filters if self._search_query or self._status_filter else self._handle_create_new,
                        style=ft.ButtonStyle(
                            bgcolor=palette.primary,
                            color=palette.text_primary,
                            padding=ft.padding.symmetric(
                                horizontal=self.get_breakpoint_value(20, 24, 28, 32),
                                vertical=self.get_breakpoint_value(12, 14, 16, 18)
                            )
                        )
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                height=400
            )

        except Exception as e:
            logger.error(f"Error creating empty state: {e}")
            return ft.Container()

    def _create_error_display(self, error_message: str) -> ft.Control:
        """Create error display."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column([
                    ft.Icon(
                        self.get_icon("ERROR"),
                        size=self.get_breakpoint_value(50, 60, 70, 80),
                        color=palette.error
                    ),
                    ft.Container(height=spacing.lg),
                    ft.Text(
                        "Error loading projects",
                        style=self.get_text_style("headlineSmall"),
                        color=palette.text_primary,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Container(height=spacing.sm),
                    ft.Text(
                        error_message,
                        style=self.get_text_style("bodyMedium"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                height=300
            )

        except Exception as e:
            logger.error(f"Error creating error display: {e}")
            return ft.Container()

    # Event Handlers
    def _handle_search_change(self, e: ft.ControlEvent) -> None:
        """Handle search query change."""
        try:
            self._search_query = e.control.value.lower() if e.control.value else ""
            self._apply_filters()

        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _handle_filter_change(self, e: ft.ControlEvent) -> None:
        """Handle filter dropdown change."""
        try:
            filter_value = e.control.value
            if filter_value == "all":
                self._status_filter = None
            else:
                self._status_filter = ProjectStatus(filter_value)

            self._apply_filters()

        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _handle_sort_change(self, e: ft.ControlEvent) -> None:
        """Handle sort dropdown change."""
        try:
            self._current_sort = SortOption(e.control.value)
            self._apply_filters()

        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _handle_layout_change(self, e: ft.ControlEvent) -> None:
        """Handle layout toggle change."""
        try:
            selected_layout = list(e.control.selected)[0] if e.control.selected else "grid"
            self._config.layout = ProjectCardLayout(selected_layout)
            self._refresh_display()

        except Exception as ex:
            logger.error(f"Error handling layout change: {ex}")

    def _handle_project_click(self, project_id: str) -> None:
        """Handle project card click."""
        try:
            if self._on_project_open:
                self._on_project_open(project_id)
            else:
                logger.info(f"Project clicked: {project_id}")

        except Exception as e:
            logger.error(f"Error handling project click: {e}")

    def _handle_project_action(self, action: str, project_id: str) -> None:
        """Handle project action from menu."""
        try:
            if action == "open" and self._on_project_open:
                self._on_project_open(project_id)
            elif action == "edit" and self._on_project_edit:
                self._on_project_edit(project_id)
            elif action == "delete" and self._on_project_delete:
                self._on_project_delete(project_id)
            elif action == "archive" and self._on_project_archive:
                self._on_project_archive(project_id)
            elif action == "duplicate" and self._on_project_duplicate:
                self._on_project_duplicate(project_id)
            else:
                logger.info(f"Project action '{action}' for project {project_id}")

        except Exception as e:
            logger.error(f"Error handling project action '{action}': {e}")

    def _handle_create_new(self, e: ft.ControlEvent = None) -> None:
        """Handle create new project button."""
        try:
            if self._on_create_new:
                self._on_create_new()
            else:
                logger.info("Create new project clicked")

        except Exception as ex:
            logger.error(f"Error handling create new: {ex}")

    def _handle_clear_filters(self, e: ft.ControlEvent = None) -> None:
        """Handle clear filters button."""
        try:
            self._search_query = ""
            self._status_filter = None
            self._type_filter = None
            self._tag_filter = None

            # Reset UI controls
            if self._search_field:
                self._search_field.value = ""
            if self._filter_dropdown:
                self._filter_dropdown.value = "all"

            self._apply_filters()

        except Exception as ex:
            logger.error(f"Error handling clear filters: {ex}")

    def _handle_card_hover(self, e: ft.ControlEvent) -> None:
        """Handle card hover effects."""
        try:
            if e.data == "true":  # Mouse enter
                e.control.elevation = self.get_breakpoint_value(2, 3, 4, 5)
                e.control.scale = 1.02
            else:  # Mouse leave
                e.control.elevation = 0
                e.control.scale = 1.0
            e.control.update()

        except Exception as ex:
            logger.error(f"Error handling card hover: {ex}")

    # Utility Methods
    def _apply_filters(self) -> None:
        """Apply current filters and sorting to projects."""
        try:
            filtered = self._projects.copy()

            # Apply search filter
            if self._search_query:
                filtered = [
                    p for p in filtered
                    if (self._search_query in p.name.lower() or
                        self._search_query in p.description.lower() or
                        any(self._search_query in tag.lower() for tag in p.tags))
                ]

            # Apply status filter
            if self._status_filter:
                filtered = [p for p in filtered if p.status == self._status_filter]

            # Apply type filter
            if self._type_filter:
                filtered = [p for p in filtered if p.project_type == self._type_filter]

            # Apply tag filter
            if self._tag_filter:
                filtered = [p for p in filtered if self._tag_filter in p.tags]

            # Apply sorting
            filtered = self._sort_projects(filtered)

            self._filtered_projects = filtered
            self._clear_card_cache()
            self._refresh_display()

        except Exception as e:
            logger.error(f"Error applying filters: {e}")

    def _sort_projects(self, projects: List[ProjectCardData]) -> List[ProjectCardData]:
        """Sort projects based on current sort option."""
        try:
            if self._current_sort == SortOption.NAME_ASC:
                return sorted(projects, key=lambda p: p.name.lower())
            elif self._current_sort == SortOption.NAME_DESC:
                return sorted(projects, key=lambda p: p.name.lower(), reverse=True)
            elif self._current_sort == SortOption.DATE_CREATED_ASC:
                return sorted(projects, key=lambda p: p.created_at)
            elif self._current_sort == SortOption.DATE_CREATED_DESC:
                return sorted(projects, key=lambda p: p.created_at, reverse=True)
            elif self._current_sort == SortOption.DATE_MODIFIED_ASC:
                return sorted(projects, key=lambda p: p.updated_at)
            elif self._current_sort == SortOption.DATE_MODIFIED_DESC:
                return sorted(projects, key=lambda p: p.updated_at, reverse=True)
            elif self._current_sort == SortOption.PROGRESS_ASC:
                return sorted(projects, key=lambda p: p.progress)
            elif self._current_sort == SortOption.PROGRESS_DESC:
                return sorted(projects, key=lambda p: p.progress, reverse=True)
            elif self._current_sort == SortOption.STATUS_ASC:
                return sorted(projects, key=lambda p: p.status.value)
            elif self._current_sort == SortOption.STATUS_DESC:
                return sorted(projects, key=lambda p: p.status.value, reverse=True)
            else:
                return projects

        except Exception as e:
            logger.error(f"Error sorting projects: {e}")
            return projects

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format timestamp as time ago string."""
        try:
            now = datetime.now()
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=now.tzinfo)

            delta = now - timestamp

            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                return f"{hours}h ago"
            elif delta.seconds > 60:
                minutes = delta.seconds // 60
                return f"{minutes}m ago"
            else:
                return "Just now"

        except Exception as e:
            logger.error(f"Error formatting time ago: {e}")
            return "Unknown"

    def _clear_card_cache(self) -> None:
        """Clear the card cache to force rebuild."""
        self._card_cache.clear()

    def _refresh_display(self) -> None:
        """Refresh the display with current data."""
        try:
            if hasattr(self, 'content') and self.content:
                self.content = self.build()
                self.update()

        except Exception as e:
            logger.error(f"Error refreshing display: {e}")

    # Public API Methods
    def set_projects(self, projects: List[ProjectCardData]) -> None:
        """
        Set the list of projects to display.

        Args:
            projects: List of project data
        """
        try:
            self._projects = projects or []
            self._apply_filters()

        except Exception as e:
            logger.error(f"Error setting projects: {e}")

    def add_project(self, project: ProjectCardData) -> None:
        """
        Add a new project to the display.

        Args:
            project: Project data to add
        """
        try:
            self._projects.append(project)
            self._apply_filters()

        except Exception as e:
            logger.error(f"Error adding project: {e}")

    def update_project(self, project: ProjectCardData) -> None:
        """
        Update an existing project in the display.

        Args:
            project: Updated project data
        """
        try:
            for i, p in enumerate(self._projects):
                if p.id == project.id:
                    self._projects[i] = project
                    break

            self._apply_filters()

        except Exception as e:
            logger.error(f"Error updating project: {e}")

    def remove_project(self, project_id: str) -> None:
        """
        Remove a project from the display.

        Args:
            project_id: ID of project to remove
        """
        try:
            self._projects = [p for p in self._projects if p.id != project_id]
            self._apply_filters()

        except Exception as e:
            logger.error(f"Error removing project: {e}")

    def set_loading(self, loading: bool) -> None:
        """
        Set loading state.

        Args:
            loading: Whether to show loading state
        """
        try:
            self._is_loading = loading
            self._refresh_display()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def get_selected_projects(self) -> List[str]:
        """
        Get list of selected project IDs.

        Returns:
            List of selected project IDs
        """
        return self._selected_projects.copy()

    def clear_selection(self) -> None:
        """Clear project selection."""
        self._selected_projects.clear()
        self._refresh_display()

    def set_filter(self, status: Optional[ProjectStatus] = None,
                   project_type: Optional[ProjectType] = None,
                   tag: Optional[str] = None) -> None:
        """
        Set filters programmatically.

        Args:
            status: Status filter to apply
            project_type: Type filter to apply
            tag: Tag filter to apply
        """
        try:
            self._status_filter = status
            self._type_filter = project_type
            self._tag_filter = tag
            self._apply_filters()

        except Exception as e:
            logger.error(f"Error setting filters: {e}")

    def set_search_query(self, query: str) -> None:
        """
        Set search query programmatically.

        Args:
            query: Search query to apply
        """
        try:
            self._search_query = query.lower() if query else ""
            if self._search_field:
                self._search_field.value = query
            self._apply_filters()

        except Exception as e:
            logger.error(f"Error setting search query: {e}")

    def set_sort_option(self, sort_option: SortOption) -> None:
        """
        Set sort option programmatically.

        Args:
            sort_option: Sort option to apply
        """
        try:
            self._current_sort = sort_option
            if self._sort_dropdown:
                self._sort_dropdown.value = sort_option.value
            self._apply_filters()

        except Exception as e:
            logger.error(f"Error setting sort option: {e}")

    def set_layout(self, layout: ProjectCardLayout) -> None:
        """
        Set layout mode programmatically.

        Args:
            layout: Layout mode to apply
        """
        try:
            self._config.layout = layout
            if self._layout_toggle:
                self._layout_toggle.selected = {layout.value}
            self._refresh_display()

        except Exception as e:
            logger.error(f"Error setting layout: {e}")

    def get_project_count(self) -> int:
        """
        Get total number of projects.

        Returns:
            Total project count
        """
        return len(self._projects)

    def get_filtered_project_count(self) -> int:
        """
        Get number of filtered projects.

        Returns:
            Filtered project count
        """
        return len(self._filtered_projects)

    # Accessibility Methods
    def _setup_keyboard_navigation(self) -> None:
        """Setup keyboard navigation for accessibility."""
        try:
            # This would be implemented with proper focus management
            # and keyboard event handling in a real application
            pass

        except Exception as e:
            logger.error(f"Error setting up keyboard navigation: {e}")

    def _get_accessibility_label(self, project: ProjectCardData) -> str:
        """
        Get accessibility label for project card.

        Args:
            project: Project data

        Returns:
            Accessibility label string
        """
        try:
            status_text = project.status.value.replace("_", " ").title()
            type_text = project.project_type.value.replace("_", " ").title()

            label_parts = [
                f"Project: {project.name}",
                f"Type: {type_text}",
                f"Status: {status_text}",
                f"Progress: {project.progress_percentage} percent"
            ]

            if project.document_count > 0:
                label_parts.append(f"{project.document_count} documents")

            if project.model_count > 0:
                label_parts.append(f"{project.model_count} models")

            if project.tags:
                label_parts.append(f"Tags: {', '.join(project.tags[:3])}")

            return ". ".join(label_parts)

        except Exception as e:
            logger.error(f"Error creating accessibility label: {e}")
            return f"Project: {project.name}"

    def _get_card_semantic_label(self, project: ProjectCardData) -> str:
        """
        Get semantic label for screen readers.

        Args:
            project: Project data

        Returns:
            Semantic label for screen readers
        """
        try:
            return (f"Project card for {project.name}. "
                   f"Click to open, or use menu for more actions. "
                   f"Current status: {project.status.value.replace('_', ' ').title()}. "
                   f"Progress: {project.progress_percentage} percent complete.")

        except Exception as e:
            logger.error(f"Error creating semantic label: {e}")
            return f"Project card for {project.name}"

    def _create_accessible_card(self, project: ProjectCardData, content: ft.Control) -> ft.Control:
        """
        Wrap card content with accessibility features.

        Args:
            project: Project data
            content: Card content control

        Returns:
            Accessible card control
        """
        try:
            palette = self.get_palette()

            return ft.Container(
                content=content,
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline),
                border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 10, 12, 14)),
                ink=True,
                on_click=lambda e, pid=project.id: self._handle_project_click(pid),
                on_hover=self._handle_card_hover if self._config.enable_hover_effects else None,
                animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
                data=project.id,
                # Accessibility attributes
                tooltip=self._get_accessibility_label(project),
                # These would be implemented with proper ARIA support in Flet
                # aria_label=self._get_card_semantic_label(project),
                # role="button",
                # tabindex=0
            )

        except Exception as e:
            logger.error(f"Error creating accessible card: {e}")
            return content

    def _announce_filter_results(self) -> None:
        """Announce filter results for screen readers."""
        try:
            count = len(self._filtered_projects)
            total = len(self._projects)

            if count == total:
                message = f"Showing all {count} projects"
            else:
                message = f"Showing {count} of {total} projects"

            # In a real implementation, this would use proper screen reader announcements
            logger.info(f"Filter results: {message}")

        except Exception as e:
            logger.error(f"Error announcing filter results: {e}")

    def _create_accessible_button(self, text: str, icon: str, on_click: Callable,
                                 variant: str = "elevated") -> ft.Control:
        """
        Create accessible button with proper labeling.

        Args:
            text: Button text
            icon: Button icon
            on_click: Click handler
            variant: Button variant

        Returns:
            Accessible button control
        """
        try:
            palette = self.get_palette()

            if variant == "elevated":
                return ft.ElevatedButton(
                    text=text,
                    icon=icon,
                    on_click=on_click,
                    style=ft.ButtonStyle(
                        bgcolor=palette.primary,
                        color=palette.text_primary,
                        padding=ft.padding.symmetric(
                            horizontal=self.get_breakpoint_value(16, 20, 24, 28),
                            vertical=self.get_breakpoint_value(8, 10, 12, 14)
                        )
                    ),
                    tooltip=f"{text} button",
                    # aria_label=f"{text}. Button."
                )
            else:
                return ft.TextButton(
                    text=text,
                    icon=icon,
                    on_click=on_click,
                    style=ft.ButtonStyle(
                        color=palette.primary,
                        padding=ft.padding.symmetric(
                            horizontal=self.get_breakpoint_value(12, 16, 20, 24),
                            vertical=self.get_breakpoint_value(6, 8, 10, 12)
                        )
                    ),
                    tooltip=f"{text} button"
                )

        except Exception as e:
            logger.error(f"Error creating accessible button: {e}")
            return ft.TextButton(text=text, icon=icon, on_click=on_click)

    def _create_accessible_dropdown(self, hint_text: str, options: List[ft.dropdown.Option],
                                   value: str, on_change: Callable) -> ft.Control:
        """
        Create accessible dropdown with proper labeling.

        Args:
            hint_text: Dropdown hint text
            options: Dropdown options
            value: Current value
            on_change: Change handler

        Returns:
            Accessible dropdown control
        """
        try:
            palette = self.get_palette()

            return ft.Dropdown(
                hint_text=hint_text,
                options=options,
                value=value,
                bgcolor=palette.surface,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=self.get_text_style("bodyMedium"),
                on_change=on_change,
                tooltip=f"{hint_text} dropdown",
                # aria_label=f"{hint_text}. Dropdown menu."
            )

        except Exception as e:
            logger.error(f"Error creating accessible dropdown: {e}")
            return ft.Dropdown(hint_text=hint_text, options=options, value=value, on_change=on_change)

    def _create_accessible_search_field(self, hint_text: str, on_change: Callable) -> ft.Control:
        """
        Create accessible search field with proper labeling.

        Args:
            hint_text: Search field hint text
            on_change: Change handler

        Returns:
            Accessible search field control
        """
        try:
            palette = self.get_palette()

            return ft.TextField(
                hint_text=hint_text,
                prefix_icon=self.get_icon("SEARCH"),
                border_radius=self.get_breakpoint_value(8, 10, 12, 14),
                bgcolor=palette.surface,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=self.get_text_style("bodyMedium"),
                hint_style=self.get_text_style("bodyMedium"),
                on_change=on_change,
                tooltip="Search projects by name, description, or tags",
                # aria_label="Search projects. Text input field."
            )

        except Exception as e:
            logger.error(f"Error creating accessible search field: {e}")
            return ft.TextField(hint_text=hint_text, on_change=on_change)
