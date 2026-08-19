"""
Module: search_filters_ui
Description: Advanced search filters UI component for MikroDok's Interactive Search (RAG) interface.
            Provides comprehensive filtering capabilities including document type, date range, relevance threshold,
            file size, language, and tag filters. Features responsive design with collapsible sections,
            filter chips, and full theme system integration.
Phase: 4
Location: /src/modules/ui/search_interface_ui/search_filters_ui/search_filters_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable, Union, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class FilterType(Enum):
    """Filter type enumeration for different search filter categories."""
    DOCUMENT_TYPE = "document_type"
    DATE_RANGE = "date_range"
    RELEVANCE = "relevance"
    FILE_SIZE = "file_size"
    LANGUAGE = "language"
    TAGS = "tags"
    AUTHOR = "author"
    COLLECTION = "collection"
    CUSTOM = "custom"


@dataclass
class FilterValue:
    """Filter value data structure for storing filter state."""
    filter_type: FilterType
    key: str
    label: str
    value: Any
    display_value: str = ""
    is_active: bool = False
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize display value if not provided."""
        if not self.display_value:
            self.display_value = str(self.value) if self.value is not None else ""


@dataclass
class FilterGroup:
    """Filter group data structure for organizing related filters."""
    group_id: str
    title: str
    filters: List[FilterValue] = field(default_factory=list)
    is_expanded: bool = True
    is_collapsible: bool = True
    order: int = 0
    icon: Optional[str] = None


class DateRangeFilter:
    """Date range filter component for filtering by document dates."""
    
    def __init__(self, 
                 start_date: Optional[date] = None,
                 end_date: Optional[date] = None,
                 preset_ranges: Optional[List[Tuple[str, int]]] = None):
        """
        Initialize date range filter.
        
        Args:
            start_date: Initial start date
            end_date: Initial end date
            preset_ranges: List of (label, days_ago) tuples for quick selection
        """
        self.start_date = start_date
        self.end_date = end_date
        self.preset_ranges = preset_ranges or [
            ("Last 7 days", 7),
            ("Last 30 days", 30),
            ("Last 90 days", 90),
            ("Last year", 365)
        ]


class RelevanceFilter:
    """Relevance threshold filter component for semantic search."""
    
    def __init__(self,
                 min_threshold: float = 0.0,
                 max_threshold: float = 1.0,
                 current_value: float = 0.5,
                 step: float = 0.1):
        """
        Initialize relevance filter.
        
        Args:
            min_threshold: Minimum relevance threshold
            max_threshold: Maximum relevance threshold
            current_value: Current threshold value
            step: Step size for slider
        """
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.current_value = current_value
        self.step = step


class DocumentTypeFilter:
    """Document type filter component for filtering by file format."""
    
    def __init__(self, selected_types: Optional[Set[str]] = None):
        """
        Initialize document type filter.
        
        Args:
            selected_types: Set of selected document types
        """
        self.available_types = {
            "pdf": "PDF Documents",
            "docx": "Word Documents", 
            "txt": "Text Files",
            "html": "HTML Files",
            "md": "Markdown Files",
            "pptx": "PowerPoint Files",
            "xlsx": "Excel Files"
        }
        self.selected_types = selected_types or set()


class FileSizeFilter:
    """File size filter component for filtering by document size."""
    
    def __init__(self,
                 min_size: int = 0,
                 max_size: int = 100 * 1024 * 1024,  # 100MB
                 current_min: int = 0,
                 current_max: Optional[int] = None):
        """
        Initialize file size filter.
        
        Args:
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes
            current_min: Current minimum size
            current_max: Current maximum size
        """
        self.min_size = min_size
        self.max_size = max_size
        self.current_min = current_min
        self.current_max = current_max or max_size


class LanguageFilter:
    """Language filter component for filtering by document language."""
    
    def __init__(self, selected_languages: Optional[Set[str]] = None):
        """
        Initialize language filter.
        
        Args:
            selected_languages: Set of selected language codes
        """
        self.available_languages = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean"
        }
        self.selected_languages = selected_languages or set()


class TagFilter:
    """Tag filter component for filtering by document tags."""
    
    def __init__(self, 
                 available_tags: Optional[List[str]] = None,
                 selected_tags: Optional[Set[str]] = None):
        """
        Initialize tag filter.
        
        Args:
            available_tags: List of available tags
            selected_tags: Set of selected tags
        """
        self.available_tags = available_tags or []
        self.selected_tags = selected_tags or set()


class SearchFiltersUI(ThemeAwareUserControl):
    """
    Advanced search filters UI component with comprehensive filtering capabilities.
    
    Features:
    - Multiple filter types: document type, date range, relevance, file size, language, tags
    - Responsive design with collapsible filter groups
    - Filter chips showing active filters with remove functionality
    - Preset filter combinations for common use cases
    - Real-time filter validation and error handling
    - Filter state persistence and restoration
    - Accessibility-compliant filter interactions
    - Full integration with ResponsiveLayoutManager and theme system
    - Advanced filter logic with AND/OR operations
    - Custom filter creation and management
    """
    
    def __init__(self,
                 show_filter_chips: bool = True,
                 show_preset_filters: bool = True,
                 collapsible_groups: bool = True,
                 max_visible_chips: int = 5,
                 on_filters_changed: Optional[Callable[[List[FilterValue]], None]] = None,
                 on_filter_reset: Optional[Callable[[], None]] = None,
                 on_preset_applied: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the SearchFiltersUI component.
        
        Args:
            show_filter_chips: Whether to show active filter chips
            show_preset_filters: Whether to show preset filter options
            collapsible_groups: Whether filter groups are collapsible
            max_visible_chips: Maximum number of visible filter chips
            on_filters_changed: Callback when filters change
            on_filter_reset: Callback when filters are reset
            on_preset_applied: Callback when preset is applied
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.show_filter_chips = show_filter_chips
        self.show_preset_filters = show_preset_filters
        self.collapsible_groups = collapsible_groups
        self.max_visible_chips = max_visible_chips
        
        # Callbacks
        self.on_filters_changed = on_filters_changed
        self.on_filter_reset = on_filter_reset
        self.on_preset_applied = on_preset_applied
        
        # State
        self._filter_groups: List[FilterGroup] = []
        self._active_filters: List[FilterValue] = []
        self._is_expanded = True
        self._search_text = ""
        
        # Filter components
        self._date_range_filter = DateRangeFilter()
        self._relevance_filter = RelevanceFilter()
        self._document_type_filter = DocumentTypeFilter()
        self._file_size_filter = FileSizeFilter()
        self._language_filter = LanguageFilter()
        self._tag_filter = TagFilter()
        
        # UI components
        self._filter_chips_container = None
        self._filter_groups_container = None
        self._preset_buttons_container = None
        self._search_field = None
        
        # Initialize filter groups
        self._initialize_filter_groups()
        
        logger.debug("SearchFiltersUI initialized")

    def _initialize_filter_groups(self) -> None:
        """Initialize default filter groups."""
        try:
            # Document Type Group
            doc_type_group = FilterGroup(
                group_id="document_type",
                title="Document Type",
                icon=ft.Icons.DESCRIPTION,
                order=1
            )
            
            # Date Range Group
            date_group = FilterGroup(
                group_id="date_range", 
                title="Date Range",
                icon=ft.Icons.DATE_RANGE,
                order=2
            )
            
            # Quality & Relevance Group
            quality_group = FilterGroup(
                group_id="quality",
                title="Quality & Relevance",
                icon=ft.Icons.STAR,
                order=3
            )
            
            # Properties Group
            properties_group = FilterGroup(
                group_id="properties",
                title="Document Properties",
                icon=ft.Icons.SETTINGS,
                order=4
            )
            
            self._filter_groups = [doc_type_group, date_group, quality_group, properties_group]
            
        except Exception as e:
            logger.error(f"Error initializing filter groups: {e}")
            self._filter_groups = []

    def build(self) -> ft.Control:
        """Build the search filters UI component."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Main container with responsive layout
            main_content = ft.Column(
                controls=[
                    self._build_header_section(),
                    self._build_filter_chips_section() if self.show_filter_chips else ft.Container(),
                    self._build_preset_filters_section() if self.show_preset_filters else ft.Container(),
                    self._build_filter_groups_section(),
                    self._build_actions_section()
                ],
                spacing=spacing.md,
                expand=True
            )

            return self.create_responsive_container(
                content=main_content,
                padding=self.get_breakpoint_value(
                    mobile=spacing.sm, tablet=spacing.md, desktop=spacing.lg, large=spacing.xl
                )
            )

        except Exception as e:
            logger.error(f"Error building SearchFiltersUI: {e}")
            return ft.Container(
                content=ft.Text("Error loading filters", color=palette.error),
                padding=spacing.md
            )

    def _build_header_section(self) -> ft.Control:
        """Build the header section with title and search."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Title with expand/collapse button
            title_row = ft.Row(
                controls=[
                    ft.Icon(
                        name=ft.Icons.FILTER_LIST,
                        color=palette.primary,
                        size=self.get_breakpoint_value(
                            mobile=20, tablet=22, desktop=24, large=24
                        )
                    ),
                    ft.Text(
                        "Search Filters",
                        style=self.get_text_style("headline6"),
                        color=palette.text_primary,
                        expand=True
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EXPAND_LESS if self._is_expanded else ft.Icons.EXPAND_MORE,
                        tooltip="Expand/Collapse Filters",
                        on_click=self._on_toggle_expansion,
                        icon_color=palette.text_secondary
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

            # Search field for filtering filter options
            self._search_field = ft.TextField(
                hint_text="Search filter options...",
                prefix_icon=ft.Icons.SEARCH,
                value=self._search_text,
                on_change=self._on_search_change,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                hint_style=ft.TextStyle(color=palette.text_secondary),
                height=self.get_breakpoint_value(
                    mobile=40, tablet=44, desktop=48, large=48
                ),
                visible=self._is_expanded
            )

            return ft.Column(
                controls=[title_row, self._search_field],
                spacing=spacing.sm
            )

        except Exception as e:
            logger.error(f"Error building header section: {e}")
            return ft.Container()

    def _build_filter_chips_section(self) -> ft.Control:
        """Build the active filter chips section."""
        try:
            if not self._active_filters or not self._is_expanded:
                return ft.Container()

            palette = self.get_palette()
            spacing = self.get_spacing()

            # Filter chips
            chips = []
            visible_filters = self._active_filters[:self.max_visible_chips]

            for filter_value in visible_filters:
                chip = ft.Chip(
                    label=ft.Text(
                        f"{filter_value.label}: {filter_value.display_value}",
                        style=self.get_text_style("body2")
                    ),
                    leading=ft.Icon(
                        name=self._get_filter_icon(filter_value.filter_type),
                        size=16,
                        color=palette.primary
                    ),
                    delete_icon=ft.Icons.CLOSE,
                    on_delete=lambda e, fv=filter_value: self._on_remove_filter(fv),
                    bgcolor=palette.surface_variant,
                    selected_color=palette.primary_container
                )
                chips.append(chip)

            # Show more indicator if needed
            if len(self._active_filters) > self.max_visible_chips:
                more_chip = ft.Chip(
                    label=ft.Text(
                        f"+{len(self._active_filters) - self.max_visible_chips} more",
                        style=self.get_text_style("body2")
                    ),
                    bgcolor=palette.surface_variant,
                    on_click=self._on_show_all_filters
                )
                chips.append(more_chip)

            # Clear all button
            if chips:
                clear_button = ft.TextButton(
                    text="Clear All",
                    icon=ft.Icons.CLEAR_ALL,
                    on_click=self._on_clear_all_filters,
                    style=ft.ButtonStyle(color=palette.error)
                )
                chips.append(clear_button)

            self._filter_chips_container = ft.Row(
                controls=chips,
                spacing=spacing.xs,
                wrap=True,
                scroll=ft.ScrollMode.AUTO
            )

            return ft.Container(
                content=self._filter_chips_container,
                padding=ft.padding.symmetric(vertical=spacing.sm),
                border=ft.border.only(bottom=ft.BorderSide(1, palette.borders))
            )

        except Exception as e:
            logger.error(f"Error building filter chips: {e}")
            return ft.Container()

    def _build_preset_filters_section(self) -> ft.Control:
        """Build the preset filters section."""
        try:
            if not self._is_expanded:
                return ft.Container()

            palette = self.get_palette()
            spacing = self.get_spacing()

            # Preset filter buttons
            presets = [
                ("Recent Documents", "recent", ft.Icons.SCHEDULE),
                ("High Relevance", "high_relevance", ft.Icons.STAR),
                ("PDF Only", "pdf_only", ft.Icons.PICTURE_AS_PDF),
                ("Large Files", "large_files", ft.Icons.FOLDER),
                ("This Week", "this_week", ft.Icons.DATE_RANGE)
            ]

            preset_buttons = []
            for label, preset_id, icon in presets:
                button = ft.OutlinedButton(
                    text=label,
                    icon=icon,
                    on_click=lambda e, pid=preset_id: self._on_apply_preset(pid),
                    style=ft.ButtonStyle(
                        color=palette.primary,
                        side=ft.BorderSide(1, palette.primary)
                    )
                )
                preset_buttons.append(button)

            self._preset_buttons_container = ft.Row(
                controls=preset_buttons,
                spacing=spacing.sm,
                wrap=True,
                scroll=ft.ScrollMode.AUTO
            )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Quick Filters",
                            style=self.get_text_style("subtitle2"),
                            color=palette.text_secondary
                        ),
                        self._preset_buttons_container
                    ],
                    spacing=spacing.xs
                ),
                padding=ft.padding.symmetric(vertical=spacing.sm),
                border=ft.border.only(bottom=ft.BorderSide(1, palette.borders))
            )

        except Exception as e:
            logger.error(f"Error building preset filters: {e}")
            return ft.Container()

    def _build_filter_groups_section(self) -> ft.Control:
        """Build the filter groups section."""
        try:
            if not self._is_expanded:
                return ft.Container()

            spacing = self.get_spacing()

            # Build filter group controls
            group_controls = []
            for group in sorted(self._filter_groups, key=lambda g: g.order):
                if self._should_show_group(group):
                    group_control = self._build_filter_group(group)
                    if group_control:
                        group_controls.append(group_control)

            self._filter_groups_container = ft.Column(
                controls=group_controls,
                spacing=spacing.md,
                expand=True
            )

            return self._filter_groups_container

        except Exception as e:
            logger.error(f"Error building filter groups: {e}")
            return ft.Container()

    def _build_filter_group(self, group: FilterGroup) -> ft.Control:
        """Build a single filter group."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Group header
            header_controls = [
                ft.Icon(
                    name=group.icon or ft.Icons.FOLDER,
                    color=palette.primary,
                    size=18
                ),
                ft.Text(
                    group.title,
                    style=self.get_text_style("subtitle1"),
                    color=palette.text_primary,
                    expand=True
                )
            ]

            if group.is_collapsible:
                toggle_button = ft.IconButton(
                    icon=ft.Icons.EXPAND_LESS if group.is_expanded else ft.Icons.EXPAND_MORE,
                    tooltip=f"{'Collapse' if group.is_expanded else 'Expand'} {group.title}",
                    on_click=lambda e, g=group: self._on_toggle_group(g),
                    icon_color=palette.text_secondary,
                    icon_size=16
                )
                header_controls.append(toggle_button)

            header = ft.Row(
                controls=header_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

            # Group content
            content_controls = []
            if group.is_expanded:
                if group.group_id == "document_type":
                    content_controls.append(self._build_document_type_filter())
                elif group.group_id == "date_range":
                    content_controls.append(self._build_date_range_filter())
                elif group.group_id == "quality":
                    content_controls.extend([
                        self._build_relevance_filter(),
                        self._build_file_size_filter()
                    ])
                elif group.group_id == "properties":
                    content_controls.extend([
                        self._build_language_filter(),
                        self._build_tag_filter()
                    ])

            content = ft.Column(
                controls=content_controls,
                spacing=spacing.sm,
                visible=group.is_expanded
            )

            return ft.Container(
                content=ft.Column(
                    controls=[header, content],
                    spacing=spacing.sm
                ),
                padding=spacing.md,
                border=ft.border.all(1, palette.borders),
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                ),
                bgcolor=palette.surface
            )

        except Exception as e:
            logger.error(f"Error building filter group {group.group_id}: {e}")
            return ft.Container()

    def _build_document_type_filter(self) -> ft.Control:
        """Build document type filter controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Document type checkboxes
            type_controls = []
            for doc_type, label in self._document_type_filter.available_types.items():
                checkbox = ft.Checkbox(
                    label=label,
                    value=doc_type in self._document_type_filter.selected_types,
                    on_change=lambda e, dt=doc_type: self._on_document_type_change(dt, e.control.value),
                    label_style=ft.TextStyle(color=palette.text_primary)
                )
                type_controls.append(checkbox)

            return ft.Column(
                controls=[
                    ft.Text(
                        "Select document types:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary
                    ),
                    ft.Column(
                        controls=type_controls,
                        spacing=spacing.xs
                    )
                ],
                spacing=spacing.xs
            )

        except Exception as e:
            logger.error(f"Error building document type filter: {e}")
            return ft.Container()

    def _build_date_range_filter(self) -> ft.Control:
        """Build date range filter controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Preset date ranges
            preset_buttons = []
            for label, days_ago in self._date_range_filter.preset_ranges:
                button = ft.TextButton(
                    text=label,
                    on_click=lambda e, days=days_ago: self._on_date_preset_click(days),
                    style=ft.ButtonStyle(color=palette.primary)
                )
                preset_buttons.append(button)

            # Custom date pickers
            start_date_picker = ft.DatePicker(
                help_text="Start date",
                value=self._date_range_filter.start_date,
                on_change=self._on_start_date_change
            )

            end_date_picker = ft.DatePicker(
                help_text="End date",
                value=self._date_range_filter.end_date,
                on_change=self._on_end_date_change
            )

            return ft.Column(
                controls=[
                    ft.Text(
                        "Quick ranges:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary
                    ),
                    ft.Row(
                        controls=preset_buttons,
                        spacing=spacing.xs,
                        wrap=True
                    ),
                    ft.Divider(color=palette.borders),
                    ft.Text(
                        "Custom range:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary
                    ),
                    ft.Row(
                        controls=[start_date_picker, end_date_picker],
                        spacing=spacing.sm
                    )
                ],
                spacing=spacing.sm
            )

        except Exception as e:
            logger.error(f"Error building date range filter: {e}")
            return ft.Container()

    def _build_relevance_filter(self) -> ft.Control:
        """Build relevance threshold filter controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Relevance slider
            relevance_slider = ft.Slider(
                min=self._relevance_filter.min_threshold,
                max=self._relevance_filter.max_threshold,
                value=self._relevance_filter.current_value,
                divisions=int((self._relevance_filter.max_threshold - self._relevance_filter.min_threshold) / self._relevance_filter.step),
                label="{value:.1f}",
                on_change=self._on_relevance_change,
                active_color=palette.primary,
                inactive_color=palette.surface_variant
            )

            return ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Minimum Relevance:",
                                style=self.get_text_style("body2"),
                                color=palette.text_secondary
                            ),
                            ft.Text(
                                f"{self._relevance_filter.current_value:.1f}",
                                style=self.get_text_style("body2"),
                                color=palette.primary,
                                weight=ft.FontWeight.BOLD
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    relevance_slider
                ],
                spacing=spacing.xs
            )

        except Exception as e:
            logger.error(f"Error building relevance filter: {e}")
            return ft.Container()

    def _build_file_size_filter(self) -> ft.Control:
        """Build file size filter controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # File size range slider
            size_slider = ft.RangeSlider(
                min=0,
                max=self._file_size_filter.max_size / (1024 * 1024),  # Convert to MB
                start_value=self._file_size_filter.current_min / (1024 * 1024),
                end_value=self._file_size_filter.current_max / (1024 * 1024),
                divisions=20,
                labels="{value:.0f} MB",
                on_change=self._on_file_size_change,
                active_color=palette.primary,
                inactive_color=palette.surface_variant
            )

            return ft.Column(
                controls=[
                    ft.Text(
                        "File Size Range:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary
                    ),
                    size_slider,
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"{self._file_size_filter.current_min / (1024 * 1024):.0f} MB",
                                style=self.get_text_style("caption"),
                                color=palette.text_secondary
                            ),
                            ft.Text(
                                f"{self._file_size_filter.current_max / (1024 * 1024):.0f} MB",
                                style=self.get_text_style("caption"),
                                color=palette.text_secondary
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                spacing=spacing.xs
            )

        except Exception as e:
            logger.error(f"Error building file size filter: {e}")
            return ft.Container()

    def _build_language_filter(self) -> ft.Control:
        """Build language filter controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Language dropdown
            language_options = [
                ft.dropdown.Option(key="all", text="All Languages")
            ]
            for lang_code, lang_name in self._language_filter.available_languages.items():
                language_options.append(
                    ft.dropdown.Option(key=lang_code, text=lang_name)
                )

            language_dropdown = ft.Dropdown(
                options=language_options,
                value="all",
                on_change=self._on_language_change,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                width=self.get_breakpoint_value(
                    mobile=200, tablet=250, desktop=300, large=300
                )
            )

            return ft.Column(
                controls=[
                    ft.Text(
                        "Document Language:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary
                    ),
                    language_dropdown
                ],
                spacing=spacing.xs
            )

        except Exception as e:
            logger.error(f"Error building language filter: {e}")
            return ft.Container()

    def _build_tag_filter(self) -> ft.Control:
        """Build tag filter controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Tag input field
            tag_input = ft.TextField(
                hint_text="Enter tags (comma-separated)",
                on_submit=self._on_tag_submit,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                hint_style=ft.TextStyle(color=palette.text_secondary)
            )

            # Selected tags chips
            tag_chips = []
            for tag in self._tag_filter.selected_tags:
                chip = ft.Chip(
                    label=ft.Text(tag, style=self.get_text_style("body2")),
                    delete_icon=ft.Icons.CLOSE,
                    on_delete=lambda e, t=tag: self._on_remove_tag(t),
                    bgcolor=palette.primary_container
                )
                tag_chips.append(chip)

            return ft.Column(
                controls=[
                    ft.Text(
                        "Tags:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary
                    ),
                    tag_input,
                    ft.Row(
                        controls=tag_chips,
                        spacing=spacing.xs,
                        wrap=True
                    ) if tag_chips else ft.Container()
                ],
                spacing=spacing.xs
            )

        except Exception as e:
            logger.error(f"Error building tag filter: {e}")
            return ft.Container()

    def _build_actions_section(self) -> ft.Control:
        """Build the actions section with reset and apply buttons."""
        try:
            if not self._is_expanded:
                return ft.Container()

            palette = self.get_palette()
            spacing = self.get_spacing()

            # Action buttons
            reset_button = ft.OutlinedButton(
                text="Reset Filters",
                icon=ft.Icons.REFRESH,
                on_click=self._on_reset_filters,
                style=ft.ButtonStyle(
                    color=palette.text_secondary,
                    side=ft.BorderSide(1, palette.borders)
                )
            )

            apply_button = ft.ElevatedButton(
                text="Apply Filters",
                icon=ft.Icons.CHECK,
                on_click=self._on_apply_filters,
                style=ft.ButtonStyle(
                    bgcolor=palette.primary,
                    color=palette.on_primary
                )
            )

            return ft.Container(
                content=ft.Row(
                    controls=[reset_button, apply_button],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=ft.padding.only(top=spacing.md),
                border=ft.border.only(top=ft.BorderSide(1, palette.borders))
            )

        except Exception as e:
            logger.error(f"Error building actions section: {e}")
            return ft.Container()

    # Event Handlers
    def _on_toggle_expansion(self, e) -> None:
        """Handle filter panel expansion toggle."""
        try:
            self._is_expanded = not self._is_expanded
            self.content = self.build()
            self.update()
            logger.debug(f"Filter panel {'expanded' if self._is_expanded else 'collapsed'}")
        except Exception as ex:
            logger.error(f"Error toggling expansion: {ex}")

    def _on_search_change(self, e) -> None:
        """Handle search text change for filtering filter options."""
        try:
            self._search_text = e.control.value
            # Rebuild filter groups with search filtering
            self._filter_groups_container.controls = []
            for group in sorted(self._filter_groups, key=lambda g: g.order):
                if self._should_show_group(group):
                    group_control = self._build_filter_group(group)
                    if group_control:
                        self._filter_groups_container.controls.append(group_control)
            self.update()
        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _on_toggle_group(self, group: FilterGroup) -> None:
        """Handle filter group expansion toggle."""
        try:
            group.is_expanded = not group.is_expanded
            self.content = self.build()
            self.update()
            logger.debug(f"Filter group {group.group_id} {'expanded' if group.is_expanded else 'collapsed'}")
        except Exception as e:
            logger.error(f"Error toggling group {group.group_id}: {e}")

    def _on_remove_filter(self, filter_value: FilterValue) -> None:
        """Handle removing an active filter."""
        try:
            if filter_value in self._active_filters:
                self._active_filters.remove(filter_value)
                filter_value.is_active = False
                self._update_filter_state(filter_value)
                self._notify_filters_changed()
                self.content = self.build()
                self.update()
                logger.debug(f"Removed filter: {filter_value.key}")
        except Exception as e:
            logger.error(f"Error removing filter: {e}")

    def _on_clear_all_filters(self, e) -> None:
        """Handle clearing all active filters."""
        try:
            for filter_value in self._active_filters:
                filter_value.is_active = False
                self._update_filter_state(filter_value)
            self._active_filters.clear()
            self._reset_all_filter_states()
            self._notify_filters_changed()
            self.content = self.build()
            self.update()
            logger.debug("Cleared all filters")
        except Exception as ex:
            logger.error(f"Error clearing all filters: {ex}")

    def _on_show_all_filters(self, e) -> None:
        """Handle showing all active filters."""
        try:
            # Temporarily increase max visible chips
            original_max = self.max_visible_chips
            self.max_visible_chips = len(self._active_filters)
            self.content = self.build()
            self.update()
            # Reset after a delay
            asyncio.create_task(self._reset_max_chips(original_max))
        except Exception as ex:
            logger.error(f"Error showing all filters: {ex}")

    async def _reset_max_chips(self, original_max: int) -> None:
        """Reset max visible chips after delay."""
        await asyncio.sleep(5)  # Show all for 5 seconds
        self.max_visible_chips = original_max
        self.content = self.build()
        self.update()

    def _on_apply_preset(self, preset_id: str) -> None:
        """Handle applying a preset filter combination."""
        try:
            if preset_id == "recent":
                # Last 7 days
                self._apply_date_preset(7)
            elif preset_id == "high_relevance":
                # Relevance > 0.8
                self._relevance_filter.current_value = 0.8
                self._add_relevance_filter()
            elif preset_id == "pdf_only":
                # PDF documents only
                self._document_type_filter.selected_types = {"pdf"}
                self._add_document_type_filter()
            elif preset_id == "large_files":
                # Files > 10MB
                self._file_size_filter.current_min = 10 * 1024 * 1024
                self._add_file_size_filter()
            elif preset_id == "this_week":
                # Last 7 days
                self._apply_date_preset(7)

            self._notify_filters_changed()
            if self.on_preset_applied:
                self.on_preset_applied(preset_id)

            self.content = self.build()
            self.update()
            logger.debug(f"Applied preset: {preset_id}")
        except Exception as e:
            logger.error(f"Error applying preset {preset_id}: {e}")

    def _on_document_type_change(self, doc_type: str, is_selected: bool) -> None:
        """Handle document type selection change."""
        try:
            if is_selected:
                self._document_type_filter.selected_types.add(doc_type)
            else:
                self._document_type_filter.selected_types.discard(doc_type)

            self._add_document_type_filter()
            self._notify_filters_changed()
            logger.debug(f"Document type {doc_type} {'selected' if is_selected else 'deselected'}")
        except Exception as e:
            logger.error(f"Error handling document type change: {e}")

    def _on_date_preset_click(self, days_ago: int) -> None:
        """Handle date preset button click."""
        try:
            self._apply_date_preset(days_ago)
            self._notify_filters_changed()
            self.content = self.build()
            self.update()
        except Exception as e:
            logger.error(f"Error applying date preset: {e}")

    def _on_start_date_change(self, e) -> None:
        """Handle start date change."""
        try:
            self._date_range_filter.start_date = e.control.value
            self._add_date_range_filter()
            self._notify_filters_changed()
        except Exception as ex:
            logger.error(f"Error handling start date change: {ex}")

    def _on_end_date_change(self, e) -> None:
        """Handle end date change."""
        try:
            self._date_range_filter.end_date = e.control.value
            self._add_date_range_filter()
            self._notify_filters_changed()
        except Exception as ex:
            logger.error(f"Error handling end date change: {ex}")

    def _on_relevance_change(self, e) -> None:
        """Handle relevance threshold change."""
        try:
            self._relevance_filter.current_value = e.control.value
            self._add_relevance_filter()
            self._notify_filters_changed()
        except Exception as ex:
            logger.error(f"Error handling relevance change: {ex}")

    def _on_file_size_change(self, e) -> None:
        """Handle file size range change."""
        try:
            self._file_size_filter.current_min = int(e.control.start_value * 1024 * 1024)
            self._file_size_filter.current_max = int(e.control.end_value * 1024 * 1024)
            self._add_file_size_filter()
            self._notify_filters_changed()
        except Exception as ex:
            logger.error(f"Error handling file size change: {ex}")

    def _on_language_change(self, e) -> None:
        """Handle language selection change."""
        try:
            selected_lang = e.control.value
            if selected_lang == "all":
                self._language_filter.selected_languages.clear()
            else:
                self._language_filter.selected_languages = {selected_lang}

            self._add_language_filter()
            self._notify_filters_changed()
        except Exception as ex:
            logger.error(f"Error handling language change: {ex}")

    def _on_tag_submit(self, e) -> None:
        """Handle tag input submission."""
        try:
            tag_text = e.control.value.strip()
            if tag_text:
                # Parse comma-separated tags
                new_tags = [tag.strip() for tag in tag_text.split(",") if tag.strip()]
                self._tag_filter.selected_tags.update(new_tags)
                e.control.value = ""  # Clear input
                self._add_tag_filter()
                self._notify_filters_changed()
                self.content = self.build()
                self.update()
        except Exception as ex:
            logger.error(f"Error handling tag submit: {ex}")

    def _on_remove_tag(self, tag: str) -> None:
        """Handle tag removal."""
        try:
            self._tag_filter.selected_tags.discard(tag)
            self._add_tag_filter()
            self._notify_filters_changed()
            self.content = self.build()
            self.update()
        except Exception as ex:
            logger.error(f"Error removing tag: {ex}")

    def _on_reset_filters(self, e) -> None:
        """Handle filter reset."""
        try:
            self._reset_all_filter_states()
            self._active_filters.clear()
            if self.on_filter_reset:
                self.on_filter_reset()
            self._notify_filters_changed()
            self.content = self.build()
            self.update()
            logger.debug("Reset all filters")
        except Exception as ex:
            logger.error(f"Error resetting filters: {ex}")

    def _on_apply_filters(self, e) -> None:
        """Handle filter application."""
        try:
            self._notify_filters_changed()
            logger.debug(f"Applied {len(self._active_filters)} filters")
        except Exception as ex:
            logger.error(f"Error applying filters: {ex}")

    # Utility Methods
    def _should_show_group(self, group: FilterGroup) -> bool:
        """Check if a filter group should be shown based on search text."""
        if not self._search_text:
            return True

        search_lower = self._search_text.lower()
        return (
            search_lower in group.title.lower() or
            any(search_lower in filter_val.label.lower() for filter_val in group.filters)
        )

    def _get_filter_icon(self, filter_type: FilterType) -> str:
        """Get icon for filter type."""
        icon_map = {
            FilterType.DOCUMENT_TYPE: ft.Icons.DESCRIPTION,
            FilterType.DATE_RANGE: ft.Icons.DATE_RANGE,
            FilterType.RELEVANCE: ft.Icons.STAR,
            FilterType.FILE_SIZE: ft.Icons.FOLDER,
            FilterType.LANGUAGE: ft.Icons.LANGUAGE,
            FilterType.TAGS: ft.Icons.TAG,
            FilterType.AUTHOR: ft.Icons.PERSON,
            FilterType.COLLECTION: ft.Icons.COLLECTIONS,
            FilterType.CUSTOM: ft.Icons.TUNE
        }
        return icon_map.get(filter_type, ft.Icons.FILTER_LIST)

    def _apply_date_preset(self, days_ago: int) -> None:
        """Apply a date preset filter."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_ago)
        self._date_range_filter.start_date = start_date
        self._date_range_filter.end_date = end_date
        self._add_date_range_filter()

    def _add_document_type_filter(self) -> None:
        """Add or update document type filter."""
        if self._document_type_filter.selected_types:
            types_str = ", ".join(self._document_type_filter.selected_types)
            filter_value = FilterValue(
                filter_type=FilterType.DOCUMENT_TYPE,
                key="document_type",
                label="Document Type",
                value=list(self._document_type_filter.selected_types),
                display_value=types_str,
                is_active=True
            )
            self._update_active_filter(filter_value)

    def _add_date_range_filter(self) -> None:
        """Add or update date range filter."""
        if self._date_range_filter.start_date or self._date_range_filter.end_date:
            start_str = self._date_range_filter.start_date.strftime("%Y-%m-%d") if self._date_range_filter.start_date else "..."
            end_str = self._date_range_filter.end_date.strftime("%Y-%m-%d") if self._date_range_filter.end_date else "..."
            display_value = f"{start_str} to {end_str}"

            filter_value = FilterValue(
                filter_type=FilterType.DATE_RANGE,
                key="date_range",
                label="Date Range",
                value=(self._date_range_filter.start_date, self._date_range_filter.end_date),
                display_value=display_value,
                is_active=True
            )
            self._update_active_filter(filter_value)

    def _add_relevance_filter(self) -> None:
        """Add or update relevance filter."""
        if self._relevance_filter.current_value > self._relevance_filter.min_threshold:
            filter_value = FilterValue(
                filter_type=FilterType.RELEVANCE,
                key="relevance",
                label="Min Relevance",
                value=self._relevance_filter.current_value,
                display_value=f"{self._relevance_filter.current_value:.1f}",
                is_active=True
            )
            self._update_active_filter(filter_value)

    def _add_file_size_filter(self) -> None:
        """Add or update file size filter."""
        if (self._file_size_filter.current_min > self._file_size_filter.min_size or
            self._file_size_filter.current_max < self._file_size_filter.max_size):
            min_mb = self._file_size_filter.current_min / (1024 * 1024)
            max_mb = self._file_size_filter.current_max / (1024 * 1024)
            display_value = f"{min_mb:.0f} - {max_mb:.0f} MB"

            filter_value = FilterValue(
                filter_type=FilterType.FILE_SIZE,
                key="file_size",
                label="File Size",
                value=(self._file_size_filter.current_min, self._file_size_filter.current_max),
                display_value=display_value,
                is_active=True
            )
            self._update_active_filter(filter_value)

    def _add_language_filter(self) -> None:
        """Add or update language filter."""
        if self._language_filter.selected_languages:
            lang_names = [self._language_filter.available_languages.get(lang, lang)
                         for lang in self._language_filter.selected_languages]
            display_value = ", ".join(lang_names)

            filter_value = FilterValue(
                filter_type=FilterType.LANGUAGE,
                key="language",
                label="Language",
                value=list(self._language_filter.selected_languages),
                display_value=display_value,
                is_active=True
            )
            self._update_active_filter(filter_value)

    def _add_tag_filter(self) -> None:
        """Add or update tag filter."""
        if self._tag_filter.selected_tags:
            display_value = ", ".join(sorted(self._tag_filter.selected_tags))

            filter_value = FilterValue(
                filter_type=FilterType.TAGS,
                key="tags",
                label="Tags",
                value=list(self._tag_filter.selected_tags),
                display_value=display_value,
                is_active=True
            )
            self._update_active_filter(filter_value)

    def _update_active_filter(self, filter_value: FilterValue) -> None:
        """Update or add a filter to active filters list."""
        # Remove existing filter of same type
        self._active_filters = [f for f in self._active_filters if f.key != filter_value.key]
        # Add new filter
        self._active_filters.append(filter_value)

    def _update_filter_state(self, filter_value: FilterValue) -> None:
        """Update filter component state when filter is removed."""
        if filter_value.filter_type == FilterType.DOCUMENT_TYPE:
            self._document_type_filter.selected_types.clear()
        elif filter_value.filter_type == FilterType.DATE_RANGE:
            self._date_range_filter.start_date = None
            self._date_range_filter.end_date = None
        elif filter_value.filter_type == FilterType.RELEVANCE:
            self._relevance_filter.current_value = 0.5
        elif filter_value.filter_type == FilterType.FILE_SIZE:
            self._file_size_filter.current_min = self._file_size_filter.min_size
            self._file_size_filter.current_max = self._file_size_filter.max_size
        elif filter_value.filter_type == FilterType.LANGUAGE:
            self._language_filter.selected_languages.clear()
        elif filter_value.filter_type == FilterType.TAGS:
            self._tag_filter.selected_tags.clear()

    def _reset_all_filter_states(self) -> None:
        """Reset all filter components to default state."""
        self._document_type_filter.selected_types.clear()
        self._date_range_filter.start_date = None
        self._date_range_filter.end_date = None
        self._relevance_filter.current_value = 0.5
        self._file_size_filter.current_min = self._file_size_filter.min_size
        self._file_size_filter.current_max = self._file_size_filter.max_size
        self._language_filter.selected_languages.clear()
        self._tag_filter.selected_tags.clear()

    def _notify_filters_changed(self) -> None:
        """Notify listeners that filters have changed."""
        if self.on_filters_changed:
            try:
                self.on_filters_changed(self._active_filters.copy())
            except Exception as e:
                logger.error(f"Error in filters changed callback: {e}")

    # Public API Methods
    def get_active_filters(self) -> List[FilterValue]:
        """Get list of currently active filters."""
        return self._active_filters.copy()

    def set_filters(self, filters: List[FilterValue]) -> None:
        """Set active filters programmatically."""
        try:
            self._active_filters = filters.copy()
            for filter_value in filters:
                self._apply_filter_value(filter_value)
            self.content = self.build()
            self.update()
            logger.debug(f"Set {len(filters)} filters programmatically")
        except Exception as e:
            logger.error(f"Error setting filters: {e}")

    def _apply_filter_value(self, filter_value: FilterValue) -> None:
        """Apply a filter value to the appropriate filter component."""
        if filter_value.filter_type == FilterType.DOCUMENT_TYPE:
            self._document_type_filter.selected_types = set(filter_value.value)
        elif filter_value.filter_type == FilterType.DATE_RANGE:
            start_date, end_date = filter_value.value
            self._date_range_filter.start_date = start_date
            self._date_range_filter.end_date = end_date
        elif filter_value.filter_type == FilterType.RELEVANCE:
            self._relevance_filter.current_value = filter_value.value
        elif filter_value.filter_type == FilterType.FILE_SIZE:
            min_size, max_size = filter_value.value
            self._file_size_filter.current_min = min_size
            self._file_size_filter.current_max = max_size
        elif filter_value.filter_type == FilterType.LANGUAGE:
            self._language_filter.selected_languages = set(filter_value.value)
        elif filter_value.filter_type == FilterType.TAGS:
            self._tag_filter.selected_tags = set(filter_value.value)

    def clear_filters(self) -> None:
        """Clear all active filters."""
        self._on_clear_all_filters(None)

    def expand_filters(self) -> None:
        """Expand the filters panel."""
        if not self._is_expanded:
            self._on_toggle_expansion(None)

    def collapse_filters(self) -> None:
        """Collapse the filters panel."""
        if self._is_expanded:
            self._on_toggle_expansion(None)

    # Accessibility Methods
    def _add_accessibility_attributes(self, control: ft.Control,
                                    label: str = None,
                                    description: str = None,
                                    role: str = None) -> ft.Control:
        """Add accessibility attributes to a control."""
        try:
            if hasattr(control, 'semantics_label') and label:
                control.semantics_label = label
            if hasattr(control, 'tooltip') and description:
                control.tooltip = description
            # Add keyboard navigation support
            if hasattr(control, 'on_focus'):
                control.on_focus = self._on_control_focus
            if hasattr(control, 'on_blur'):
                control.on_blur = self._on_control_blur
            return control
        except Exception as e:
            logger.error(f"Error adding accessibility attributes: {e}")
            return control

    def _on_control_focus(self, e) -> None:
        """Handle control focus for accessibility."""
        try:
            # Announce focus change for screen readers
            if hasattr(e.control, 'semantics_label'):
                logger.debug(f"Focus: {e.control.semantics_label}")
        except Exception as ex:
            logger.error(f"Error handling control focus: {ex}")

    def _on_control_blur(self, e) -> None:
        """Handle control blur for accessibility."""
        try:
            # Handle blur events if needed
            pass
        except Exception as ex:
            logger.error(f"Error handling control blur: {ex}")

    def _create_accessible_button(self, text: str, icon: str = None,
                                tooltip: str = None, on_click=None, **kwargs) -> ft.Control:
        """Create an accessible button with proper ARIA attributes."""
        try:
            button = ft.ElevatedButton(
                text=text,
                icon=icon,
                tooltip=tooltip or text,
                on_click=on_click,
                **kwargs
            )
            return self._add_accessibility_attributes(
                button,
                label=text,
                description=tooltip or f"Button: {text}",
                role="button"
            )
        except Exception as e:
            logger.error(f"Error creating accessible button: {e}")
            return ft.ElevatedButton(text=text, on_click=on_click)

    def _create_accessible_checkbox(self, label: str, value: bool = False,
                                  on_change=None, **kwargs) -> ft.Control:
        """Create an accessible checkbox with proper ARIA attributes."""
        try:
            checkbox = ft.Checkbox(
                label=label,
                value=value,
                on_change=on_change,
                **kwargs
            )
            return self._add_accessibility_attributes(
                checkbox,
                label=f"Checkbox: {label}",
                description=f"{'Checked' if value else 'Unchecked'} checkbox for {label}",
                role="checkbox"
            )
        except Exception as e:
            logger.error(f"Error creating accessible checkbox: {e}")
            return ft.Checkbox(label=label, value=value, on_change=on_change)

    def _create_accessible_slider(self, min_val: float, max_val: float,
                                current_val: float, label: str,
                                on_change=None, **kwargs) -> ft.Control:
        """Create an accessible slider with proper ARIA attributes."""
        try:
            slider = ft.Slider(
                min=min_val,
                max=max_val,
                value=current_val,
                on_change=on_change,
                **kwargs
            )
            return self._add_accessibility_attributes(
                slider,
                label=f"Slider: {label}",
                description=f"{label} slider, current value: {current_val}, range: {min_val} to {max_val}",
                role="slider"
            )
        except Exception as e:
            logger.error(f"Error creating accessible slider: {e}")
            return ft.Slider(min=min_val, max=max_val, value=current_val, on_change=on_change)

    def _create_accessible_dropdown(self, options: List[ft.dropdown.Option],
                                  value: str, label: str,
                                  on_change=None, **kwargs) -> ft.Control:
        """Create an accessible dropdown with proper ARIA attributes."""
        try:
            dropdown = ft.Dropdown(
                options=options,
                value=value,
                on_change=on_change,
                **kwargs
            )
            return self._add_accessibility_attributes(
                dropdown,
                label=f"Dropdown: {label}",
                description=f"{label} dropdown, current selection: {value}",
                role="combobox"
            )
        except Exception as e:
            logger.error(f"Error creating accessible dropdown: {e}")
            return ft.Dropdown(options=options, value=value, on_change=on_change)

    def _create_accessible_text_field(self, hint_text: str, label: str = None,
                                    on_change=None, on_submit=None, **kwargs) -> ft.Control:
        """Create an accessible text field with proper ARIA attributes."""
        try:
            text_field = ft.TextField(
                hint_text=hint_text,
                label=label,
                on_change=on_change,
                on_submit=on_submit,
                **kwargs
            )
            return self._add_accessibility_attributes(
                text_field,
                label=f"Text field: {label or hint_text}",
                description=f"Text input for {label or hint_text}",
                role="textbox"
            )
        except Exception as e:
            logger.error(f"Error creating accessible text field: {e}")
            return ft.TextField(hint_text=hint_text, on_change=on_change, on_submit=on_submit)

    def _announce_filter_change(self, action: str, filter_name: str, value: str = None) -> None:
        """Announce filter changes for screen readers."""
        try:
            if value:
                message = f"{action} {filter_name} filter: {value}"
            else:
                message = f"{action} {filter_name} filter"

            # Log for accessibility tools
            logger.info(f"Accessibility: {message}")

            # In a real implementation, you might use a live region or
            # accessibility API to announce changes

        except Exception as e:
            logger.error(f"Error announcing filter change: {e}")

    def _get_filter_summary(self) -> str:
        """Get a summary of active filters for screen readers."""
        try:
            if not self._active_filters:
                return "No active filters"

            filter_descriptions = []
            for filter_val in self._active_filters:
                filter_descriptions.append(f"{filter_val.label}: {filter_val.display_value}")

            return f"{len(self._active_filters)} active filters: " + ", ".join(filter_descriptions)

        except Exception as e:
            logger.error(f"Error getting filter summary: {e}")
            return "Error getting filter summary"

    def _handle_keyboard_navigation(self, e) -> None:
        """Handle keyboard navigation within the filter interface."""
        try:
            if e.key == "Escape":
                # Close expanded sections or clear focus
                if self._is_expanded:
                    self.collapse_filters()
            elif e.key == "Enter" or e.key == " ":
                # Activate focused element
                if hasattr(e.control, 'on_click'):
                    e.control.on_click(e)
            elif e.key == "Tab":
                # Tab navigation is handled by Flet automatically
                pass
            elif e.key == "F1":
                # Show help/instructions
                self._show_filter_help()

        except Exception as ex:
            logger.error(f"Error handling keyboard navigation: {ex}")

    def _show_filter_help(self) -> None:
        """Show help dialog for filter usage."""
        try:
            help_text = """
Filter Help:
- Use document type checkboxes to filter by file format
- Set date range using preset buttons or custom date pickers
- Adjust relevance threshold with the slider
- Set file size range using the range slider
- Select language from the dropdown
- Add tags by typing and pressing Enter
- Use Escape key to collapse sections
- Use Tab to navigate between controls
- Click 'Reset Filters' to clear all filters
"""

            # In a real implementation, you would show a dialog
            logger.info(f"Filter Help: {help_text}")

        except Exception as e:
            logger.error(f"Error showing filter help: {e}")

    def get_accessibility_summary(self) -> Dict[str, Any]:
        """Get accessibility information about the current state."""
        try:
            return {
                "total_filters": len(self._active_filters),
                "filter_summary": self._get_filter_summary(),
                "is_expanded": self._is_expanded,
                "available_filter_types": [group.title for group in self._filter_groups],
                "keyboard_shortcuts": {
                    "Escape": "Collapse filters",
                    "Tab": "Navigate between controls",
                    "Enter/Space": "Activate focused element",
                    "F1": "Show help"
                }
            }
        except Exception as e:
            logger.error(f"Error getting accessibility summary: {e}")
            return {"error": "Unable to get accessibility summary"}
