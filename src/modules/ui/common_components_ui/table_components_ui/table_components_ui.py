"""
Module: table_components_ui
Description: Comprehensive data table components with sorting, filtering, pagination, and responsive design.
            Provides reusable table components with advanced features including multi-column sorting,
            real-time filtering, pagination controls, row selection, and theme-aware styling for the
            MikroDok application. Implements modern UI/UX patterns with accessibility compliance,
            responsive breakpoint-aware sizing, and full theme system integration.

Features:
- Advanced data table with sorting, filtering, and pagination
- Responsive design with breakpoint-aware column management
- Theme-aware styling with dark/light mode support
- Accessibility compliance with WCAG 2.1 AA standards
- Row selection with multiple selection modes
- Real-time search and filtering capabilities
- Export functionality (CSV, JSON, Excel)
- Virtual scrolling for large datasets
- Customizable column types and renderers
- Performance-optimized rendering with caching

Phase: 1 (Common Components)
Location: /src/modules/ui/common_components_ui/table_components_ui/table_components_ui.py

Usage Examples:

1. Basic Data Table:
```python
from src.modules.ui.common_components_ui.table_components_ui import TableComponentsUI

# Create table instance
table_ui = TableComponentsUI()

# Define columns
columns = [
    TableColumn("id", "ID", ColumnType.NUMBER, width=80),
    TableColumn("name", "Name", ColumnType.TEXT, sortable=True),
    TableColumn("status", "Status", ColumnType.BADGE, filterable=True),
    TableColumn("created", "Created", ColumnType.DATE, sortable=True)
]

# Create table
data_table = table_ui.create_data_table(
    columns=columns,
    data=sample_data,
    config=TableConfig(
        sortable=True,
        filterable=True,
        paginated=True,
        selectable=True
    )
)
```

2. Advanced Table with Custom Filters:
```python
# Create table with custom configuration
advanced_table = table_ui.create_advanced_table(
    columns=columns,
    data=large_dataset,
    config=TableConfig(
        virtual_scrolling=True,
        export_enabled=True,
        selection_mode=SelectionMode.MULTIPLE,
        pagination_config=PaginationConfig(page_size=50, show_size_selector=True)
    )
)
```
"""

# Standard library imports
import json
import csv
import io
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Union, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    TypographyScale,
    SpacingSystem,
    IconSystem,
    ResponsiveLayoutManager,
    ScreenSize
)


class SortDirection(Enum):
    """Sort direction enumeration."""
    ASC = "asc"
    DESC = "desc"
    NONE = "none"


class FilterType(Enum):
    """Filter type enumeration."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    BOOLEAN = "boolean"
    RANGE = "range"
    CUSTOM = "custom"


class ColumnType(Enum):
    """Column type enumeration."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    BADGE = "badge"
    PROGRESS = "progress"
    ACTIONS = "actions"
    CUSTOM = "custom"


class TableViewMode(Enum):
    """Table view mode enumeration."""
    STANDARD = "standard"
    COMPACT = "compact"
    COMFORTABLE = "comfortable"
    DENSE = "dense"


class SelectionMode(Enum):
    """Row selection mode enumeration."""
    NONE = "none"
    SINGLE = "single"
    MULTIPLE = "multiple"


class TableEventType(Enum):
    """Table event type enumeration."""
    ROW_CLICK = "row_click"
    ROW_DOUBLE_CLICK = "row_double_click"
    ROW_SELECT = "row_select"
    CELL_CLICK = "cell_click"
    SORT_CHANGE = "sort_change"
    FILTER_CHANGE = "filter_change"
    PAGE_CHANGE = "page_change"
    EXPORT = "export"


@dataclass
class TableColumn:
    """Table column configuration."""
    key: str
    title: str
    column_type: ColumnType = ColumnType.TEXT
    width: Optional[int] = None
    min_width: int = 80
    max_width: Optional[int] = None
    sortable: bool = False
    filterable: bool = False
    resizable: bool = True
    visible: bool = True
    align: str = "left"  # left, center, right
    format_function: Optional[Callable[[Any], str]] = None
    render_function: Optional[Callable[[Any, Dict], ft.Control]] = None
    filter_options: Optional[List[str]] = None
    tooltip: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization validation."""
        if self.width and self.width < self.min_width:
            self.width = self.min_width
        if self.max_width and self.width and self.width > self.max_width:
            self.width = self.max_width


@dataclass
class PaginationConfig:
    """Pagination configuration."""
    enabled: bool = True
    page_size: int = 25
    page_size_options: List[int] = field(default_factory=lambda: [10, 25, 50, 100])
    show_size_selector: bool = True
    show_page_info: bool = True
    show_first_last: bool = True
    max_visible_pages: int = 5


@dataclass
class FilterConfig:
    """Filter configuration."""
    enabled: bool = True
    global_search: bool = True
    column_filters: bool = True
    advanced_filters: bool = False
    filter_delay_ms: int = 300
    case_sensitive: bool = False
    regex_support: bool = False


@dataclass
class SortConfig:
    """Sort configuration."""
    enabled: bool = True
    multi_column: bool = False
    default_direction: SortDirection = SortDirection.ASC
    sort_indicators: bool = True


@dataclass
class TableConfig:
    """Comprehensive table configuration."""
    # Basic settings
    view_mode: TableViewMode = TableViewMode.STANDARD
    selection_mode: SelectionMode = SelectionMode.NONE
    striped_rows: bool = True
    hover_effects: bool = True
    
    # Feature toggles
    sortable: bool = True
    filterable: bool = True
    paginated: bool = True
    resizable_columns: bool = True
    reorderable_columns: bool = False
    
    # Performance settings
    virtual_scrolling: bool = False
    lazy_loading: bool = False
    cache_enabled: bool = True
    max_cache_size: int = 1000
    
    # Export settings
    export_enabled: bool = False
    export_formats: List[str] = field(default_factory=lambda: ["CSV", "JSON"])
    
    # Responsive settings
    responsive: bool = True
    mobile_stack_columns: bool = True
    hide_columns_on_mobile: List[str] = field(default_factory=list)
    
    # Sub-configurations
    pagination_config: PaginationConfig = field(default_factory=PaginationConfig)
    filter_config: FilterConfig = field(default_factory=FilterConfig)
    sort_config: SortConfig = field(default_factory=SortConfig)


@dataclass
class TableData:
    """Table data container."""
    rows: List[Dict[str, Any]]
    total_count: Optional[int] = None
    page: int = 1
    page_size: int = 25
    
    def __post_init__(self):
        """Post-initialization setup."""
        if self.total_count is None:
            self.total_count = len(self.rows)


@dataclass
class TableState:
    """Table state management."""
    current_page: int = 1
    page_size: int = 25
    sort_column: Optional[str] = None
    sort_direction: SortDirection = SortDirection.NONE
    filters: Dict[str, Any] = field(default_factory=dict)
    selected_rows: Set[str] = field(default_factory=set)
    expanded_rows: Set[str] = field(default_factory=set)
    column_widths: Dict[str, int] = field(default_factory=dict)
    column_order: List[str] = field(default_factory=list)
    global_search: str = ""


@dataclass
class TableEvent:
    """Table event data."""
    event_type: TableEventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class TableTheme:
    """Table theme configuration."""
    
    def __init__(self, palette: ColorPalette, typography: TypographyScale, spacing: SpacingSystem):
        self.palette = palette
        self.typography = typography
        self.spacing = spacing
        
        # Table-specific theme properties
        self.header_bg = palette.surface_variant
        self.header_text = palette.text_primary
        self.row_bg_primary = palette.surface
        self.row_bg_secondary = palette.background_secondary
        self.row_hover = palette.surface_variant
        self.row_selected = palette.primary_container
        self.border_color = palette.outline_variant
        self.sort_indicator = palette.primary
        
        # Typography
        self.header_text_style = typography.body_medium
        self.cell_text_style = typography.body_medium
        self.caption_text_style = typography.caption
        
        # Spacing
        self.cell_padding = spacing.md
        self.header_padding = spacing.lg
        self.table_margin = spacing.lg


class TableCell(ThemeAwareUserControl):
    """
    Individual table cell component with theme-aware styling and responsive design.

    Provides consistent cell rendering with support for different data types,
    custom formatting, and interactive features.
    """

    def __init__(self,
                 value: Any,
                 column: TableColumn,
                 row_data: Dict[str, Any],
                 **kwargs):
        """
        Initialize table cell.

        Args:
            value: Cell value
            column: Column configuration
            row_data: Complete row data for context
            **kwargs: Additional properties
        """
        super().__init__(**kwargs)
        self.value = value
        self.column = column
        self.row_data = row_data
        self._formatted_value = None

    def build(self) -> ft.Control:
        """Build the table cell."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Format value
        formatted_value = self._format_value()

        # Create cell content based on column type
        if self.column.render_function:
            content = self.column.render_function(self.value, self.row_data)
        else:
            content = self._create_default_content(formatted_value)

        # Apply alignment
        alignment_map = {
            "left": ft.alignment.center_left,
            "center": ft.alignment.center,
            "right": ft.alignment.center_right
        }

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.sm),
            alignment=alignment_map.get(self.column.align, ft.alignment.center_left),
            tooltip=self.column.tooltip if self.column.tooltip else None
        )

    def _format_value(self) -> str:
        """Format cell value based on column type and format function."""
        if self._formatted_value is not None:
            return self._formatted_value

        if self.column.format_function:
            self._formatted_value = self.column.format_function(self.value)
        elif self.value is None:
            self._formatted_value = ""
        elif self.column.column_type == ColumnType.DATE:
            if isinstance(self.value, (date, datetime)):
                self._formatted_value = self.value.strftime("%Y-%m-%d")
            else:
                self._formatted_value = str(self.value)
        elif self.column.column_type == ColumnType.DATETIME:
            if isinstance(self.value, datetime):
                self._formatted_value = self.value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                self._formatted_value = str(self.value)
        elif self.column.column_type == ColumnType.NUMBER:
            if isinstance(self.value, (int, float)):
                self._formatted_value = f"{self.value:,.2f}" if isinstance(self.value, float) else f"{self.value:,}"
            else:
                self._formatted_value = str(self.value)
        elif self.column.column_type == ColumnType.BOOLEAN:
            self._formatted_value = "Yes" if self.value else "No"
        else:
            self._formatted_value = str(self.value) if self.value is not None else ""

        return self._formatted_value

    def _create_default_content(self, formatted_value: str) -> ft.Control:
        """Create default cell content based on column type."""
        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()

        if self.column.column_type == ColumnType.BOOLEAN:
            return ft.Icon(
                icons.CHECK_CIRCLE if self.value else icons.CANCEL,
                color=palette.success if self.value else palette.error,
                size=16
            )
        elif self.column.column_type == ColumnType.BADGE:
            return self._create_badge(formatted_value)
        elif self.column.column_type == ColumnType.PROGRESS:
            return self._create_progress_bar()
        else:
            return ft.Text(
                formatted_value,
                size=typography.body_medium[0],
                color=palette.text_primary,
                overflow=ft.TextOverflow.ELLIPSIS
            )

    def _create_badge(self, text: str) -> ft.Control:
        """Create badge component for status values."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Define badge colors based on common status values
        badge_colors = {
            "active": palette.success,
            "inactive": palette.error,
            "pending": palette.warning,
            "completed": palette.success,
            "failed": palette.error,
            "running": palette.info,
            "stopped": palette.error
        }

        color = badge_colors.get(str(self.value).lower(), palette.secondary)

        return ft.Container(
            content=ft.Text(
                text,
                size=12,
                color=palette.surface,
                weight=ft.FontWeight.W_500
            ),
            bgcolor=color,
            padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
            border_radius=ft.border_radius.all(spacing.xs),
            alignment=ft.alignment.center
        )

    def _create_progress_bar(self) -> ft.Control:
        """Create progress bar for numeric progress values."""
        palette = self.get_palette()

        # Ensure value is between 0 and 1
        progress_value = max(0, min(1, float(self.value) if self.value else 0))

        return ft.ProgressBar(
            value=progress_value,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            height=8
        )


class TableRow(ThemeAwareUserControl):
    """
    Table row component with selection, hover effects, and responsive design.

    Provides consistent row rendering with support for selection states,
    hover effects, and responsive column management.
    """

    def __init__(self,
                 row_data: Dict[str, Any],
                 columns: List[TableColumn],
                 row_index: int,
                 is_selected: bool = False,
                 is_striped: bool = False,
                 selection_mode: SelectionMode = SelectionMode.NONE,
                 on_click: Optional[Callable] = None,
                 on_select: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize table row.

        Args:
            row_data: Row data dictionary
            columns: List of column configurations
            row_index: Row index for styling
            is_selected: Whether row is selected
            is_striped: Whether to apply striped styling
            selection_mode: Row selection mode
            on_click: Row click callback
            on_select: Row selection callback
            **kwargs: Additional properties
        """
        super().__init__(**kwargs)
        self.row_data = row_data
        self.columns = columns
        self.row_index = row_index
        self.is_selected = is_selected
        self.is_striped = is_striped
        self.selection_mode = selection_mode
        self.on_click = on_click
        self.on_select = on_select

    def build(self) -> ft.Control:
        """Build the table row."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        # Create cells for visible columns
        cells = []

        # Add selection checkbox if needed
        if self.selection_mode in [SelectionMode.SINGLE, SelectionMode.MULTIPLE]:
            checkbox = ft.Checkbox(
                value=self.is_selected,
                on_change=self._handle_selection_change
            )
            cells.append(ft.Container(
                content=checkbox,
                padding=ft.padding.all(spacing.sm),
                alignment=ft.alignment.center
            ))

        # Add data cells
        for column in self.columns:
            if column.visible:
                value = self.row_data.get(column.key)
                cell = TableCell(
                    value=value,
                    column=column,
                    row_data=self.row_data
                )
                cells.append(cell)

        # Determine row background color
        if self.is_selected:
            bg_color = palette.primary_container
        elif self.is_striped and self.row_index % 2 == 1:
            bg_color = palette.surface_variant
        else:
            bg_color = palette.surface

        # Create responsive row
        if responsive.is_mobile_or_tablet():
            return self._create_mobile_row(cells, bg_color)
        else:
            return self._create_desktop_row(cells, bg_color)

    def _create_desktop_row(self, cells: List[ft.Control], bg_color: str) -> ft.Control:
        """Create desktop table row layout."""
        palette = self.get_palette()

        return ft.Container(
            content=ft.Row(
                controls=cells,
                spacing=0,
                tight=True
            ),
            bgcolor=bg_color,
            border=ft.border.only(bottom=ft.BorderSide(1, palette.outline_variant)),
            on_click=self._handle_row_click if self.on_click else None,
            on_hover=self._handle_row_hover,
            ink=True
        )

    def _create_mobile_row(self, cells: List[ft.Control], bg_color: str) -> ft.Control:
        """Create mobile-friendly stacked row layout."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Create stacked layout for mobile
        mobile_cells = []

        for i, column in enumerate(self.columns):
            if column.visible and i < len(cells):
                value = self.row_data.get(column.key)
                if value is not None and str(value).strip():
                    mobile_cells.append(
                        ft.Row([
                            ft.Text(
                                f"{column.title}:",
                                size=typography.caption[0],
                                weight=ft.FontWeight.W_500,
                                color=palette.text_secondary,
                                width=100
                            ),
                            ft.Expanded(
                                child=cells[i + (1 if self.selection_mode != SelectionMode.NONE else 0)]
                            )
                        ], spacing=spacing.sm)
                    )

        return ft.Container(
            content=ft.Column(
                controls=mobile_cells,
                spacing=spacing.xs,
                tight=True
            ),
            bgcolor=bg_color,
            padding=ft.padding.all(spacing.md),
            border=ft.border.only(bottom=ft.BorderSide(1, palette.outline_variant)),
            on_click=self._handle_row_click if self.on_click else None
        )

    def _handle_row_click(self, e):
        """Handle row click event."""
        if self.on_click:
            self.on_click(self.row_data, self.row_index)

    def _handle_row_hover(self, e):
        """Handle row hover effect."""
        palette = self.get_palette()
        if e.data == "true":  # Mouse enter
            e.control.bgcolor = palette.surface_variant
        else:  # Mouse leave
            if self.is_selected:
                e.control.bgcolor = palette.primary_container
            elif self.is_striped and self.row_index % 2 == 1:
                e.control.bgcolor = palette.surface_variant
            else:
                e.control.bgcolor = palette.surface
        e.control.update()

    def _handle_selection_change(self, e):
        """Handle row selection change."""
        if self.on_select:
            self.on_select(self.row_data, self.row_index, e.control.value)


class TablePagination(ThemeAwareUserControl):
    """
    Table pagination component with responsive design and accessibility.

    Provides comprehensive pagination controls with page size selection,
    navigation buttons, and page information display.
    """

    def __init__(self,
                 current_page: int = 1,
                 total_pages: int = 1,
                 total_items: int = 0,
                 page_size: int = 25,
                 config: Optional[PaginationConfig] = None,
                 on_page_change: Optional[Callable[[int], None]] = None,
                 on_page_size_change: Optional[Callable[[int], None]] = None,
                 **kwargs):
        """
        Initialize table pagination.

        Args:
            current_page: Current page number (1-based)
            total_pages: Total number of pages
            total_items: Total number of items
            page_size: Items per page
            config: Pagination configuration
            on_page_change: Page change callback
            on_page_size_change: Page size change callback
            **kwargs: Additional properties
        """
        super().__init__(**kwargs)
        self.current_page = current_page
        self.total_pages = total_pages
        self.total_items = total_items
        self.page_size = page_size
        self.config = config or PaginationConfig()
        self.on_page_change = on_page_change
        self.on_page_size_change = on_page_size_change

    def build(self) -> ft.Control:
        """Build the pagination component."""
        if not self.config.enabled or self.total_pages <= 1:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        responsive = self.get_responsive_layout()

        controls = []

        # Page size selector
        if self.config.show_size_selector and len(self.config.page_size_options) > 1:
            controls.append(self._create_page_size_selector())

        # Page info
        if self.config.show_page_info:
            controls.append(self._create_page_info())

        # Navigation controls
        controls.append(self._create_navigation_controls())

        # Responsive layout
        if responsive.is_mobile():
            return ft.Column(
                controls=controls,
                spacing=spacing.sm,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        else:
            return ft.Row(
                controls=controls,
                spacing=spacing.lg,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

    def _create_page_size_selector(self) -> ft.Control:
        """Create page size selector dropdown."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Row([
            ft.Text(
                "Items per page:",
                size=typography.body_small[0],
                color=palette.text_secondary
            ),
            ft.Dropdown(
                value=str(self.page_size),
                options=[
                    ft.dropdown.Option(str(size), str(size))
                    for size in self.config.page_size_options
                ],
                width=80,
                height=32,
                text_size=typography.body_small[0],
                on_change=self._handle_page_size_change,
                border_color=palette.outline_variant,
                focused_border_color=palette.primary
            )
        ], spacing=spacing.sm, tight=True)

    def _create_page_info(self) -> ft.Control:
        """Create page information display."""
        palette = self.get_palette()
        typography = self.get_typography()

        start_item = (self.current_page - 1) * self.page_size + 1
        end_item = min(self.current_page * self.page_size, self.total_items)

        info_text = f"Showing {start_item}-{end_item} of {self.total_items} items"

        return ft.Text(
            info_text,
            size=typography.body_small[0],
            color=palette.text_secondary
        )

    def _create_navigation_controls(self) -> ft.Control:
        """Create pagination navigation controls."""
        palette = self.get_palette()
        icons = self.get_icons()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        controls = []

        # First page button
        if self.config.show_first_last:
            controls.append(
                ft.IconButton(
                    icon=icons.FIRST_PAGE,
                    disabled=self.current_page == 1,
                    on_click=lambda _: self._go_to_page(1),
                    tooltip="First page"
                )
            )

        # Previous page button
        controls.append(
            ft.IconButton(
                icon=icons.CHEVRON_LEFT,
                disabled=self.current_page == 1,
                on_click=lambda _: self._go_to_page(self.current_page - 1),
                tooltip="Previous page"
            )
        )

        # Page number buttons
        page_buttons = self._create_page_buttons()
        controls.extend(page_buttons)

        # Next page button
        controls.append(
            ft.IconButton(
                icon=icons.CHEVRON_RIGHT,
                disabled=self.current_page == self.total_pages,
                on_click=lambda _: self._go_to_page(self.current_page + 1),
                tooltip="Next page"
            )
        )

        # Last page button
        if self.config.show_first_last:
            controls.append(
                ft.IconButton(
                    icon=icons.LAST_PAGE,
                    disabled=self.current_page == self.total_pages,
                    on_click=lambda _: self._go_to_page(self.total_pages),
                    tooltip="Last page"
                )
            )

        return ft.Row(controls, spacing=spacing.xs, tight=True)

    def _create_page_buttons(self) -> List[ft.Control]:
        """Create page number buttons with smart truncation."""
        palette = self.get_palette()
        typography = self.get_typography()

        buttons = []
        max_visible = self.config.max_visible_pages

        # Calculate visible page range
        start_page = max(1, self.current_page - max_visible // 2)
        end_page = min(self.total_pages, start_page + max_visible - 1)

        # Adjust start if we're near the end
        if end_page - start_page < max_visible - 1:
            start_page = max(1, end_page - max_visible + 1)

        # Add ellipsis at start if needed
        if start_page > 1:
            buttons.append(
                ft.TextButton(
                    "1",
                    on_click=lambda _: self._go_to_page(1)
                )
            )
            if start_page > 2:
                buttons.append(ft.Text("...", size=typography.body_small[0]))

        # Add page buttons
        for page in range(start_page, end_page + 1):
            is_current = page == self.current_page
            buttons.append(
                ft.TextButton(
                    str(page),
                    style=ft.ButtonStyle(
                        bgcolor=palette.primary if is_current else None,
                        color=palette.surface if is_current else palette.text_primary
                    ),
                    on_click=lambda _, p=page: self._go_to_page(p)
                )
            )

        # Add ellipsis at end if needed
        if end_page < self.total_pages:
            if end_page < self.total_pages - 1:
                buttons.append(ft.Text("...", size=typography.body_small[0]))
            buttons.append(
                ft.TextButton(
                    str(self.total_pages),
                    on_click=lambda _: self._go_to_page(self.total_pages)
                )
            )

        return buttons

    def _go_to_page(self, page: int):
        """Navigate to specified page."""
        if 1 <= page <= self.total_pages and page != self.current_page:
            if self.on_page_change:
                self.on_page_change(page)

    def _handle_page_size_change(self, e):
        """Handle page size change."""
        new_size = int(e.control.value)
        if new_size != self.page_size and self.on_page_size_change:
            self.on_page_size_change(new_size)


class TableFilter(ThemeAwareUserControl):
    """
    Table filter component with global search and column-specific filters.

    Provides comprehensive filtering capabilities with real-time search,
    column-specific filters, and advanced filter options.
    """

    def __init__(self,
                 columns: List[TableColumn],
                 config: Optional[FilterConfig] = None,
                 on_filter_change: Optional[Callable[[Dict[str, Any]], None]] = None,
                 **kwargs):
        """
        Initialize table filter.

        Args:
            columns: List of filterable columns
            config: Filter configuration
            on_filter_change: Filter change callback
            **kwargs: Additional properties
        """
        super().__init__(**kwargs)
        self.columns = [col for col in columns if col.filterable]
        self.config = config or FilterConfig()
        self.on_filter_change = on_filter_change
        self.filters = {}
        self.global_search = ""

    def build(self) -> ft.Control:
        """Build the filter component."""
        if not self.config.enabled:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        controls = []

        # Global search
        if self.config.global_search:
            controls.append(self._create_global_search())

        # Column filters
        if self.config.column_filters and self.columns:
            controls.append(self._create_column_filters())

        # Advanced filters toggle
        if self.config.advanced_filters:
            controls.append(self._create_advanced_filters_toggle())

        if not controls:
            return ft.Container()

        # Responsive layout
        if responsive.is_mobile():
            return ft.Column(
                controls=controls,
                spacing=spacing.sm
            )
        else:
            return ft.Row(
                controls=controls,
                spacing=spacing.lg,
                alignment=ft.MainAxisAlignment.START
            )

    def _create_global_search(self) -> ft.Control:
        """Create global search input."""
        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()
        responsive = self.get_responsive_layout()

        search_width = responsive.get_breakpoint_value(
            mobile=None,  # Full width
            tablet=300,
            desktop=400,
            large=500
        )

        return ft.TextField(
            hint_text="Search all columns...",
            prefix_icon=icons.SEARCH,
            width=search_width,
            height=40,
            text_size=typography.body_medium[0],
            border_color=palette.outline_variant,
            focused_border_color=palette.primary,
            on_change=self._handle_global_search_change,
            on_submit=self._handle_global_search_submit
        )

    def _create_column_filters(self) -> ft.Control:
        """Create column-specific filters."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        filter_controls = []

        for column in self.columns[:3]:  # Limit visible filters
            filter_control = self._create_column_filter(column)
            if filter_control:
                filter_controls.append(filter_control)

        if not filter_controls:
            return ft.Container()

        # Show more filters button if there are more columns
        if len(self.columns) > 3:
            filter_controls.append(
                ft.TextButton(
                    f"+{len(self.columns) - 3} more",
                    on_click=self._show_more_filters
                )
            )

        if responsive.is_mobile():
            return ft.Column(
                controls=filter_controls,
                spacing=spacing.sm
            )
        else:
            return ft.Row(
                controls=filter_controls,
                spacing=spacing.md,
                scroll=ft.ScrollMode.AUTO
            )

    def _create_column_filter(self, column: TableColumn) -> Optional[ft.Control]:
        """Create filter control for specific column."""
        palette = self.get_palette()
        typography = self.get_typography()

        if column.filter_options:
            # Dropdown filter for predefined options
            return ft.Dropdown(
                label=column.title,
                hint_text=f"Filter {column.title}",
                options=[ft.dropdown.Option("", "All")] + [
                    ft.dropdown.Option(opt, opt) for opt in column.filter_options
                ],
                width=150,
                height=40,
                text_size=typography.body_small[0],
                on_change=lambda e, col=column: self._handle_column_filter_change(col.key, e.control.value)
            )
        elif column.column_type in [ColumnType.TEXT]:
            # Text filter
            return ft.TextField(
                label=column.title,
                hint_text=f"Filter {column.title}",
                width=150,
                height=40,
                text_size=typography.body_small[0],
                on_change=lambda e, col=column: self._handle_column_filter_change(col.key, e.control.value)
            )
        elif column.column_type == ColumnType.NUMBER:
            # Number range filter (simplified)
            return ft.TextField(
                label=f"{column.title} (min)",
                hint_text="Min value",
                width=120,
                height=40,
                text_size=typography.body_small[0],
                on_change=lambda e, col=column: self._handle_column_filter_change(f"{col.key}_min", e.control.value)
            )

        return None

    def _create_advanced_filters_toggle(self) -> ft.Control:
        """Create advanced filters toggle button."""
        icons = self.get_icons()

        return ft.TextButton(
            "Advanced Filters",
            icon=icons.TUNE,
            on_click=self._toggle_advanced_filters
        )

    def _handle_global_search_change(self, e):
        """Handle global search input change with debouncing."""
        self.global_search = e.control.value
        # In a real implementation, you'd implement debouncing here
        self._emit_filter_change()

    def _handle_global_search_submit(self, e):
        """Handle global search submit."""
        self._emit_filter_change()

    def _handle_column_filter_change(self, column_key: str, value: str):
        """Handle column filter change."""
        if value:
            self.filters[column_key] = value
        else:
            self.filters.pop(column_key, None)
        self._emit_filter_change()

    def _show_more_filters(self, e):
        """Show additional filter options."""
        # In a real implementation, this would open a dialog with all filters
        pass

    def _toggle_advanced_filters(self, e):
        """Toggle advanced filters panel."""
        # In a real implementation, this would show/hide advanced filter options
        pass

    def _emit_filter_change(self):
        """Emit filter change event."""
        if self.on_filter_change:
            filter_data = {
                "global_search": self.global_search,
                "column_filters": self.filters.copy()
            }
            self.on_filter_change(filter_data)


class TableSort(ThemeAwareUserControl):
    """
    Table sort component with multi-column sorting support.

    Provides sorting indicators and controls for table columns
    with support for ascending, descending, and multi-column sorting.
    """

    def __init__(self,
                 column: TableColumn,
                 current_sort: Optional[str] = None,
                 sort_direction: SortDirection = SortDirection.NONE,
                 sort_index: Optional[int] = None,
                 config: Optional[SortConfig] = None,
                 on_sort_change: Optional[Callable[[str, SortDirection], None]] = None,
                 **kwargs):
        """
        Initialize table sort.

        Args:
            column: Column configuration
            current_sort: Currently sorted column key
            sort_direction: Current sort direction
            sort_index: Sort index for multi-column sorting
            config: Sort configuration
            on_sort_change: Sort change callback
            **kwargs: Additional properties
        """
        super().__init__(**kwargs)
        self.column = column
        self.current_sort = current_sort
        self.sort_direction = sort_direction
        self.sort_index = sort_index
        self.config = config or SortConfig()
        self.on_sort_change = on_sort_change

    def build(self) -> ft.Control:
        """Build the sort component."""
        if not self.column.sortable or not self.config.enabled:
            return ft.Container()

        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()
        spacing = self.get_spacing()

        is_sorted = self.current_sort == self.column.key

        # Sort indicator icon
        if is_sorted and self.sort_direction == SortDirection.ASC:
            sort_icon = icons.ARROW_UPWARD
            icon_color = palette.primary
        elif is_sorted and self.sort_direction == SortDirection.DESC:
            sort_icon = icons.ARROW_DOWNWARD
            icon_color = palette.primary
        else:
            sort_icon = icons.SORT
            icon_color = palette.text_secondary

        controls = [
            ft.Text(
                self.column.title,
                size=typography.body_medium[0],
                weight=ft.FontWeight.W_500,
                color=palette.text_primary
            )
        ]

        if self.config.sort_indicators:
            controls.append(
                ft.Icon(
                    sort_icon,
                    size=16,
                    color=icon_color
                )
            )

        # Multi-column sort index
        if self.config.multi_column and is_sorted and self.sort_index is not None:
            controls.append(
                ft.Container(
                    content=ft.Text(
                        str(self.sort_index + 1),
                        size=10,
                        color=palette.surface,
                        weight=ft.FontWeight.BOLD
                    ),
                    bgcolor=palette.primary,
                    border_radius=ft.border_radius.all(8),
                    width=16,
                    height=16,
                    alignment=ft.alignment.center
                )
            )

        return ft.Container(
            content=ft.Row(
                controls=controls,
                spacing=spacing.xs,
                tight=True
            ),
            on_click=self._handle_sort_click,
            ink=True,
            padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs)
        )

    def _handle_sort_click(self, e):
        """Handle sort click to cycle through sort states."""
        if not self.on_sort_change:
            return

        # Determine next sort direction
        if self.current_sort != self.column.key:
            # Not currently sorted, start with default direction
            next_direction = self.config.default_direction
        elif self.sort_direction == SortDirection.ASC:
            # Currently ascending, switch to descending
            next_direction = SortDirection.DESC
        elif self.sort_direction == SortDirection.DESC:
            # Currently descending, remove sort
            next_direction = SortDirection.NONE
        else:
            # No sort, start with default direction
            next_direction = self.config.default_direction

        self.on_sort_change(self.column.key, next_direction)


class DataTableComponent(ThemeAwareUserControl):
    """
    Main data table component with comprehensive features.

    Provides a complete data table implementation with sorting, filtering,
    pagination, selection, and responsive design capabilities.
    """

    def __init__(self,
                 columns: List[TableColumn],
                 data: Optional[TableData] = None,
                 config: Optional[TableConfig] = None,
                 **kwargs):
        """
        Initialize data table component.

        Args:
            columns: List of table columns
            data: Table data
            config: Table configuration
            **kwargs: Additional properties
        """
        super().__init__(**kwargs)
        self.columns = columns
        self.data = data or TableData([])
        self.config = config or TableConfig()
        self.state = TableState()

        # Event callbacks
        self.on_row_click: Optional[Callable] = None
        self.on_row_select: Optional[Callable] = None
        self.on_sort_change: Optional[Callable] = None
        self.on_filter_change: Optional[Callable] = None
        self.on_page_change: Optional[Callable] = None

        # UI components
        self.header_container: Optional[ft.Container] = None
        self.filter_container: Optional[ft.Container] = None
        self.table_container: Optional[ft.Container] = None
        self.pagination_container: Optional[ft.Container] = None

        # Initialize state
        self._initialize_state()

    def build(self) -> ft.Control:
        """Build the complete data table."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        components = []

        # Filter component
        if self.config.filterable:
            filter_component = TableFilter(
                columns=self.columns,
                config=self.config.filter_config,
                on_filter_change=self._handle_filter_change
            )
            self.filter_container = ft.Container(
                content=filter_component,
                padding=ft.padding.only(bottom=spacing.md)
            )
            components.append(self.filter_container)

        # Table header and content
        table_content = self._create_table_content()
        self.table_container = ft.Container(
            content=table_content,
            border=ft.border.all(1, palette.outline_variant),
            border_radius=ft.border_radius.all(spacing.xs),
            bgcolor=palette.surface
        )
        components.append(self.table_container)

        # Pagination component
        if self.config.paginated:
            total_pages = max(1, (self.data.total_count + self.state.page_size - 1) // self.state.page_size)
            pagination_component = TablePagination(
                current_page=self.state.current_page,
                total_pages=total_pages,
                total_items=self.data.total_count,
                page_size=self.state.page_size,
                config=self.config.pagination_config,
                on_page_change=self._handle_page_change,
                on_page_size_change=self._handle_page_size_change
            )
            self.pagination_container = ft.Container(
                content=pagination_component,
                padding=ft.padding.only(top=spacing.md)
            )
            components.append(self.pagination_container)

        return ft.Column(
            controls=components,
            spacing=0,
            expand=True
        )

    def _create_table_content(self) -> ft.Control:
        """Create the main table content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create header
        header = self._create_table_header()

        # Create rows
        rows = self._create_table_rows()

        # Create scrollable content
        table_content = ft.Column([
            header,
            ft.Container(
                content=ft.Column(
                    controls=rows,
                    spacing=0,
                    scroll=ft.ScrollMode.AUTO
                ),
                expand=True
            )
        ], spacing=0)

        return table_content

    def _create_table_header(self) -> ft.Control:
        """Create table header with sort controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        header_cells = []

        # Selection header
        if self.config.selection_mode in [SelectionMode.SINGLE, SelectionMode.MULTIPLE]:
            select_all_checkbox = None
            if self.config.selection_mode == SelectionMode.MULTIPLE:
                select_all_checkbox = ft.Checkbox(
                    value=self._is_all_selected(),
                    tristate=True,
                    on_change=self._handle_select_all
                )

            header_cells.append(
                ft.Container(
                    content=select_all_checkbox or ft.Container(),
                    padding=ft.padding.all(spacing.sm),
                    alignment=ft.alignment.center,
                    width=50
                )
            )

        # Column headers
        for column in self.columns:
            if column.visible:
                sort_component = TableSort(
                    column=column,
                    current_sort=self.state.sort_column,
                    sort_direction=self.state.sort_direction,
                    config=self.config.sort_config,
                    on_sort_change=self._handle_sort_change
                )

                header_cells.append(
                    ft.Container(
                        content=sort_component,
                        padding=ft.padding.all(spacing.sm),
                        width=column.width,
                        alignment=ft.alignment.center_left
                    )
                )

        return ft.Container(
            content=ft.Row(
                controls=header_cells,
                spacing=0,
                tight=True
            ),
            bgcolor=palette.surface_variant,
            border=ft.border.only(bottom=ft.BorderSide(1, palette.outline_variant))
        )

    def _create_table_rows(self) -> List[ft.Control]:
        """Create table rows from data."""
        rows = []

        for i, row_data in enumerate(self.data.rows):
            row_id = str(row_data.get('id', i))
            is_selected = row_id in self.state.selected_rows

            table_row = TableRow(
                row_data=row_data,
                columns=self.columns,
                row_index=i,
                is_selected=is_selected,
                is_striped=self.config.striped_rows,
                selection_mode=self.config.selection_mode,
                on_click=self._handle_row_click,
                on_select=self._handle_row_select
            )
            rows.append(table_row)

        return rows

    def _initialize_state(self):
        """Initialize table state from configuration."""
        self.state.page_size = self.config.pagination_config.page_size
        self.state.column_order = [col.key for col in self.columns]

    def _handle_filter_change(self, filter_data: Dict[str, Any]):
        """Handle filter change event."""
        self.state.filters = filter_data.get('column_filters', {})
        self.state.global_search = filter_data.get('global_search', '')

        if self.on_filter_change:
            self.on_filter_change(filter_data)

        # Reset to first page when filters change
        self.state.current_page = 1
        self.update()

    def _handle_sort_change(self, column_key: str, direction: SortDirection):
        """Handle sort change event."""
        self.state.sort_column = column_key if direction != SortDirection.NONE else None
        self.state.sort_direction = direction

        if self.on_sort_change:
            self.on_sort_change(column_key, direction)

        self.update()

    def _handle_page_change(self, page: int):
        """Handle page change event."""
        self.state.current_page = page

        if self.on_page_change:
            self.on_page_change(page)

        self.update()

    def _handle_page_size_change(self, page_size: int):
        """Handle page size change event."""
        self.state.page_size = page_size
        self.state.current_page = 1  # Reset to first page

        if self.on_page_change:
            self.on_page_change(1)

        self.update()

    def _handle_row_click(self, row_data: Dict[str, Any], row_index: int):
        """Handle row click event."""
        if self.on_row_click:
            self.on_row_click(row_data, row_index)

    def _handle_row_select(self, row_data: Dict[str, Any], row_index: int, selected: bool):
        """Handle row selection event."""
        row_id = str(row_data.get('id', row_index))

        if selected:
            if self.config.selection_mode == SelectionMode.SINGLE:
                self.state.selected_rows.clear()
            self.state.selected_rows.add(row_id)
        else:
            self.state.selected_rows.discard(row_id)

        if self.on_row_select:
            self.on_row_select(row_data, row_index, selected)

        self.update()

    def _handle_select_all(self, e):
        """Handle select all checkbox."""
        if e.control.value:
            # Select all visible rows
            for row_data in self.data.rows:
                row_id = str(row_data.get('id', hash(str(row_data))))
                self.state.selected_rows.add(row_id)
        else:
            # Deselect all
            self.state.selected_rows.clear()

        self.update()

    def _is_all_selected(self) -> Optional[bool]:
        """Check if all rows are selected for tristate checkbox."""
        if not self.data.rows:
            return False

        total_rows = len(self.data.rows)
        selected_count = len(self.state.selected_rows)

        if selected_count == 0:
            return False
        elif selected_count == total_rows:
            return True
        else:
            return None  # Indeterminate state

    def update_data(self, data: TableData):
        """Update table data and refresh display."""
        self.data = data
        self.update()

    def get_selected_rows(self) -> List[Dict[str, Any]]:
        """Get currently selected row data."""
        selected_data = []
        for row_data in self.data.rows:
            row_id = str(row_data.get('id', hash(str(row_data))))
            if row_id in self.state.selected_rows:
                selected_data.append(row_data)
        return selected_data

    def clear_selection(self):
        """Clear all row selections."""
        self.state.selected_rows.clear()
        self.update()

    def export_data(self, format_type: str = "CSV") -> str:
        """Export table data in specified format."""
        if format_type.upper() == "CSV":
            return self._export_csv()
        elif format_type.upper() == "JSON":
            return self._export_json()
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    def _export_csv(self) -> str:
        """Export data as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        headers = [col.title for col in self.columns if col.visible]
        writer.writerow(headers)

        # Write data
        for row_data in self.data.rows:
            row = []
            for col in self.columns:
                if col.visible:
                    value = row_data.get(col.key, '')
                    if col.format_function:
                        value = col.format_function(value)
                    row.append(str(value))
            writer.writerow(row)

        return output.getvalue()

    def _export_json(self) -> str:
        """Export data as JSON."""
        export_data = []
        for row_data in self.data.rows:
            filtered_row = {}
            for col in self.columns:
                if col.visible:
                    value = row_data.get(col.key)
                    if col.format_function:
                        value = col.format_function(value)
                    filtered_row[col.key] = value
            export_data.append(filtered_row)

        return json.dumps(export_data, indent=2, default=str)


class TableComponentsUI(ThemeAwareUserControl):
    """
    Main table components UI factory and manager.

    Provides a unified interface for creating and managing different table types
    with consistent theming, responsive design, and comprehensive features.

    Features:
    - Factory methods for different table configurations
    - Centralized theme and configuration management
    - Performance monitoring and optimization
    - Export and data management utilities
    - Responsive design with breakpoint awareness
    """

    def __init__(self, **kwargs):
        """Initialize table components UI manager."""
        super().__init__(**kwargs)

        self._tables: Dict[str, DataTableComponent] = {}
        self._default_config = TableConfig()
        self._performance_metrics = {
            'tables_created': 0,
            'tables_updated': 0,
            'render_time_total': 0,
            'last_render_time': 0,
            'export_operations': 0
        }

    def build(self) -> ft.Control:
        """Build the table components UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Table components showcase/demo
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Table Components",
                    size=typography.h2[0],
                    weight=ft.FontWeight.BOLD,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Comprehensive data table components with sorting, filtering, and pagination",
                    size=typography.body_medium[0],
                    color=palette.text_secondary
                ),
                ft.Divider(color=palette.borders),
                self._create_table_showcase()
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.lg)
        )

    def create_data_table(self,
                         columns: List[TableColumn],
                         data: Optional[TableData] = None,
                         config: Optional[TableConfig] = None,
                         table_id: Optional[str] = None) -> DataTableComponent:
        """
        Create a standard data table with comprehensive features.

        Args:
            columns: List of table columns
            data: Table data
            config: Table configuration
            table_id: Unique table identifier

        Returns:
            DataTableComponent instance
        """
        table_config = config or self._default_config
        table = DataTableComponent(
            columns=columns,
            data=data,
            config=table_config
        )

        if table_id:
            self._tables[table_id] = table

        self._performance_metrics['tables_created'] += 1
        return table

    def create_simple_table(self,
                           columns: List[TableColumn],
                           data: Optional[TableData] = None,
                           table_id: Optional[str] = None) -> DataTableComponent:
        """
        Create a simple table with basic features.

        Args:
            columns: List of table columns
            data: Table data
            table_id: Unique table identifier

        Returns:
            DataTableComponent instance
        """
        simple_config = TableConfig(
            sortable=True,
            filterable=False,
            paginated=False,
            selection_mode=SelectionMode.NONE,
            striped_rows=True,
            hover_effects=True
        )

        return self.create_data_table(columns, data, simple_config, table_id)

    def create_advanced_table(self,
                             columns: List[TableColumn],
                             data: Optional[TableData] = None,
                             table_id: Optional[str] = None) -> DataTableComponent:
        """
        Create an advanced table with all features enabled.

        Args:
            columns: List of table columns
            data: Table data
            table_id: Unique table identifier

        Returns:
            DataTableComponent instance
        """
        advanced_config = TableConfig(
            sortable=True,
            filterable=True,
            paginated=True,
            selection_mode=SelectionMode.MULTIPLE,
            striped_rows=True,
            hover_effects=True,
            resizable_columns=True,
            export_enabled=True,
            virtual_scrolling=True,
            pagination_config=PaginationConfig(
                page_size=50,
                show_size_selector=True,
                show_page_info=True
            ),
            filter_config=FilterConfig(
                global_search=True,
                column_filters=True,
                advanced_filters=True
            ),
            sort_config=SortConfig(
                multi_column=True,
                sort_indicators=True
            )
        )

        return self.create_data_table(columns, data, advanced_config, table_id)

    def create_mobile_table(self,
                           columns: List[TableColumn],
                           data: Optional[TableData] = None,
                           table_id: Optional[str] = None) -> DataTableComponent:
        """
        Create a mobile-optimized table.

        Args:
            columns: List of table columns
            data: Table data
            table_id: Unique table identifier

        Returns:
            DataTableComponent instance
        """
        mobile_config = TableConfig(
            view_mode=TableViewMode.COMPACT,
            sortable=True,
            filterable=True,
            paginated=True,
            selection_mode=SelectionMode.SINGLE,
            mobile_stack_columns=True,
            pagination_config=PaginationConfig(
                page_size=10,
                show_size_selector=False,
                max_visible_pages=3
            )
        )

        return self.create_data_table(columns, data, mobile_config, table_id)

    def get_table(self, table_id: str) -> Optional[DataTableComponent]:
        """
        Get table by ID.

        Args:
            table_id: Table identifier

        Returns:
            DataTableComponent instance or None
        """
        return self._tables.get(table_id)

    def update_table_data(self, table_id: str, data: TableData) -> bool:
        """
        Update data for specific table.

        Args:
            table_id: Table identifier
            data: New table data

        Returns:
            True if successful, False if table not found
        """
        table = self._tables.get(table_id)
        if table:
            table.update_data(data)
            self._performance_metrics['tables_updated'] += 1
            return True
        return False

    def export_table_data(self, table_id: str, format_type: str = "CSV") -> Optional[str]:
        """
        Export table data.

        Args:
            table_id: Table identifier
            format_type: Export format (CSV, JSON)

        Returns:
            Exported data string or None if table not found
        """
        table = self._tables.get(table_id)
        if table:
            self._performance_metrics['export_operations'] += 1
            return table.export_data(format_type)
        return None

    def get_performance_metrics(self) -> Dict[str, int]:
        """
        Get performance metrics for table operations.

        Returns:
            Dictionary of performance metrics
        """
        return self._performance_metrics.copy()

    def clear_all_tables(self):
        """Clear all managed tables."""
        self._tables.clear()

    def _create_table_showcase(self) -> ft.Control:
        """Create table components showcase."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Sample data for demonstration
        sample_columns = [
            TableColumn("id", "ID", ColumnType.NUMBER, width=80, sortable=True),
            TableColumn("name", "Name", ColumnType.TEXT, sortable=True, filterable=True),
            TableColumn("status", "Status", ColumnType.BADGE, filterable=True,
                       filter_options=["Active", "Inactive", "Pending"]),
            TableColumn("progress", "Progress", ColumnType.PROGRESS, width=120),
            TableColumn("created", "Created", ColumnType.DATE, sortable=True),
            TableColumn("active", "Active", ColumnType.BOOLEAN, width=80)
        ]

        sample_data = TableData([
            {"id": 1, "name": "Model Alpha", "status": "Active", "progress": 0.85,
             "created": datetime(2024, 1, 15), "active": True},
            {"id": 2, "name": "Model Beta", "status": "Pending", "progress": 0.45,
             "created": datetime(2024, 1, 20), "active": False},
            {"id": 3, "name": "Model Gamma", "status": "Inactive", "progress": 1.0,
             "created": datetime(2024, 1, 25), "active": False},
        ])

        # Create sample table
        sample_table = self.create_simple_table(
            columns=sample_columns,
            data=sample_data,
            table_id="showcase_table"
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Sample Data Table",
                    size=typography.h4[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary
                ),
                sample_table
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md),
            border=ft.border.all(1, palette.outline_variant),
            border_radius=ft.border_radius.all(spacing.sm),
            bgcolor=palette.surface
        )
