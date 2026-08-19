"""
Module: document_collection_ui
Description: Document collection tree view interface for organizing imported documents in the search interface.
            Provides hierarchical display of document collections with management features, storage indicators,
            and seamless integration with the RAG search functionality.
Phase: 4
Location: /src/modules/ui/search_interface_ui/document_collection_ui/document_collection_ui.py
"""

# Standard library imports
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import uuid

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


class CollectionStatus(Enum):
    """Document collection status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROCESSING = "processing"
    ERROR = "error"
    ARCHIVED = "archived"


class CollectionType(Enum):
    """Document collection type enumeration."""
    FOLDER = "folder"
    SMART_COLLECTION = "smart_collection"
    TAG_COLLECTION = "tag_collection"
    SEARCH_COLLECTION = "search_collection"
    SYSTEM = "system"
    TEMPORARY = "temporary"


class CollectionViewMode(Enum):
    """Collection view mode enumeration."""
    TREE = "tree"
    LIST = "list"
    COMPACT = "compact"
    DETAILED = "detailed"


class CollectionSortOption(Enum):
    """Collection sorting options."""
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"
    SIZE_ASC = "size_asc"
    SIZE_DESC = "size_desc"
    TYPE_ASC = "type_asc"
    TYPE_DESC = "type_desc"
    DOCUMENT_COUNT_ASC = "document_count_asc"
    DOCUMENT_COUNT_DESC = "document_count_desc"


class CollectionFilterOption(Enum):
    """Collection filter options."""
    ALL = "all"
    ACTIVE_ONLY = "active_only"
    FOLDERS_ONLY = "folders_only"
    SMART_COLLECTIONS_ONLY = "smart_collections_only"
    NON_EMPTY_ONLY = "non_empty_only"
    RECENT = "recent"
    FAVORITES = "favorites"


@dataclass
class CollectionStatistics:
    """Collection statistics data structure."""
    document_count: int = 0
    total_size_bytes: int = 0
    indexed_documents: int = 0
    processing_documents: int = 0
    failed_documents: int = 0
    last_updated: Optional[datetime] = None
    storage_usage_mb: float = 0.0
    vector_count: int = 0
    embedding_dimension: int = 0


@dataclass
class DocumentCollection:
    """Document collection data structure."""
    collection_id: str
    collection_name: str
    description: str = ""
    collection_type: CollectionType = CollectionType.FOLDER
    status: CollectionStatus = CollectionStatus.ACTIVE
    parent_collection_id: Optional[str] = None
    path: str = ""
    depth_level: int = 0
    sort_order: int = 0
    is_system: bool = False
    is_readonly: bool = False
    is_favorite: bool = False
    is_expanded: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    statistics: CollectionStatistics = field(default_factory=CollectionStatistics)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    color: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class CollectionNode:
    """Tree node for collection hierarchy."""
    collection: DocumentCollection
    children: List['CollectionNode'] = field(default_factory=list)
    parent: Optional['CollectionNode'] = None
    is_expanded: bool = False
    is_selected: bool = False
    is_loading: bool = False
    level: int = 0


@dataclass
class CollectionTreeState:
    """State management for collection tree."""
    root_nodes: List[CollectionNode] = field(default_factory=list)
    selected_collections: Set[str] = field(default_factory=set)
    expanded_collections: Set[str] = field(default_factory=set)
    loading_collections: Set[str] = field(default_factory=set)
    search_query: str = ""
    current_filter: CollectionFilterOption = CollectionFilterOption.ALL
    current_sort: CollectionSortOption = CollectionSortOption.NAME_ASC
    view_mode: CollectionViewMode = CollectionViewMode.TREE
    show_statistics: bool = True
    show_storage_indicator: bool = True


@dataclass
class CollectionOperation:
    """Collection operation data structure."""
    operation_type: str
    collection_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class StorageInfo:
    """Storage information for collections."""
    total_capacity_gb: float = 10.0
    used_space_gb: float = 0.0
    available_space_gb: float = 10.0
    vector_db_size_gb: float = 0.0
    document_storage_gb: float = 0.0
    cache_size_gb: float = 0.0
    usage_percentage: float = 0.0
    warning_threshold: float = 80.0
    critical_threshold: float = 95.0


class CollectionEventType(Enum):
    """Collection event types."""
    COLLECTION_SELECTED = "collection_selected"
    COLLECTION_EXPANDED = "collection_expanded"
    COLLECTION_COLLAPSED = "collection_collapsed"
    COLLECTION_CREATED = "collection_created"
    COLLECTION_RENAMED = "collection_renamed"
    COLLECTION_DELETED = "collection_deleted"
    COLLECTION_MOVED = "collection_moved"
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_REMOVED = "document_removed"
    SEARCH_PERFORMED = "search_performed"
    FILTER_CHANGED = "filter_changed"
    SORT_CHANGED = "sort_changed"
    VIEW_MODE_CHANGED = "view_mode_changed"


@dataclass
class CollectionEvent:
    """Collection event data structure."""
    event_type: CollectionEventType
    collection_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class DocumentCollectionUI(ThemeAwareUserControl):
    """
    Document collection tree view interface with responsive design and theme integration.

    Features:
    - Hierarchical tree view of document collections with expand/collapse
    - Collection management (create, rename, delete, organize)
    - Search and filtering capabilities with real-time updates
    - Storage usage visualization and statistics display
    - Drag-and-drop collection organization
    - Context menus for collection operations
    - Keyboard navigation and accessibility support
    - Theme-aware styling with responsive breakpoints
    - Integration with document database and vector storage
    - Real-time collection statistics and status updates
    """

    def __init__(self,
                 on_collection_selected: Optional[Callable[[str], None]] = None,
                 on_collection_changed: Optional[Callable[[CollectionEvent], None]] = None,
                 show_storage_indicator: bool = True,
                 show_statistics: bool = True,
                 enable_drag_drop: bool = True,
                 enable_context_menu: bool = True,
                 max_depth_levels: int = 10,
                 **kwargs):
        """
        Initialize document collection UI.

        Args:
            on_collection_selected: Callback for collection selection
            on_collection_changed: Callback for collection changes
            show_storage_indicator: Whether to show storage usage indicator
            show_statistics: Whether to show collection statistics
            enable_drag_drop: Whether to enable drag-and-drop
            enable_context_menu: Whether to enable context menus
            max_depth_levels: Maximum tree depth levels
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)

        # Callbacks
        self._on_collection_selected = on_collection_selected
        self._on_collection_changed = on_collection_changed

        # Configuration
        self._show_storage_indicator = show_storage_indicator
        self._show_statistics = show_statistics
        self._enable_drag_drop = enable_drag_drop
        self._enable_context_menu = enable_context_menu
        self._max_depth_levels = max_depth_levels

        # State management
        self._tree_state = CollectionTreeState()
        self._storage_info = StorageInfo()
        self._collections_cache: Dict[str, DocumentCollection] = {}
        self._tree_nodes_cache: Dict[str, CollectionNode] = {}

        # UI components
        self._search_field: Optional[ft.TextField] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._sort_dropdown: Optional[ft.Dropdown] = None
        self._view_mode_buttons: Optional[ft.Row] = None
        self._tree_view: Optional[ft.Column] = None
        self._storage_indicator: Optional[ft.Container] = None
        self._statistics_panel: Optional[ft.Container] = None
        self._context_menu: Optional[ft.MenuBar] = None

        # Event handling
        self._debounce_timer: Optional[asyncio.Task] = None
        self._refresh_timer: Optional[asyncio.Task] = None

        # Performance optimization
        self._visible_nodes: Set[str] = set()
        self._rendered_nodes: Dict[str, ft.Control] = {}
        self._last_render_time = datetime.now()

        logger.info("DocumentCollectionUI initialized")

    def build(self) -> ft.Control:
        """Build the responsive document collection interface."""
        try:
            # Get responsive values
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_breakpoint_value(8, 12, 16, 20)

            # Create main layout
            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        self._build_header_section(),
                        self._build_toolbar_section(),
                        self._build_tree_section(),
                        self._build_footer_section()
                    ],
                    spacing=responsive_spacing,
                    expand=True,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=responsive_padding
            )

        except Exception as e:
            logger.error(f"Error building document collection UI: {e}")
            return self._build_error_state(str(e))

    def _build_header_section(self) -> ft.Control:
        """Build the header section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Title with collection count
        title_text = "Document Collections"
        if self._tree_state.root_nodes:
            total_collections = self._count_total_collections()
            title_text += f" ({total_collections})"

        title = ft.Text(
            title_text,
            style=self.get_text_style('h4'),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )

        # Header actions
        actions = ft.Row([
            ft.IconButton(
                icon=self.get_icon('ADD'),
                tooltip="Create New Collection",
                on_click=self._on_create_collection,
                icon_color=palette.primary
            ),
            ft.IconButton(
                icon=self.get_icon('REFRESH'),
                tooltip="Refresh Collections",
                on_click=self._on_refresh_collections,
                icon_color=palette.text_secondary
            ),
            ft.IconButton(
                icon=self.get_icon('SETTINGS'),
                tooltip="Collection Settings",
                on_click=self._on_show_settings,
                icon_color=palette.text_secondary
            )
        ], spacing=spacing.md)

        return ft.Container(
            content=ft.Row([
                title,
                actions
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.only(bottom=spacing.xl)
        )

    def _build_toolbar_section(self) -> ft.Control:
        """Build the toolbar section with search, filter, and view controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        responsive_width = self.get_breakpoint_value(200, 250, 300, 350)

        # Search field
        self._search_field = ft.TextField(
            hint_text="Search collections...",
            prefix_icon=self.get_icon('SEARCH'),
            on_change=self._on_search_changed,
            expand=True,
            bgcolor=palette.surface,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8)
        )

        # Filter dropdown
        self._filter_dropdown = ft.Dropdown(
            label="Filter",
            hint_text="All Collections",
            options=[
                ft.dropdown.Option(key=option.value, text=option.value.replace('_', ' ').title())
                for option in CollectionFilterOption
            ],
            value=self._tree_state.current_filter.value,
            on_change=self._on_filter_changed,
            width=responsive_width * 0.6,
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        # Sort dropdown
        self._sort_dropdown = ft.Dropdown(
            label="Sort",
            hint_text="Name A-Z",
            options=[
                ft.dropdown.Option(key=option.value, text=option.value.replace('_', ' ').title())
                for option in CollectionSortOption
            ],
            value=self._tree_state.current_sort.value,
            on_change=self._on_sort_changed,
            width=responsive_width * 0.6,
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        # View mode buttons
        self._view_mode_buttons = ft.Row([
            ft.IconButton(
                icon=self.get_icon('LIST'),
                tooltip="Tree View",
                selected=self._tree_state.view_mode == CollectionViewMode.TREE,
                on_click=lambda _: self._on_view_mode_changed(CollectionViewMode.TREE),
                icon_color=palette.primary if self._tree_state.view_mode == CollectionViewMode.TREE else palette.text_secondary
            ),
            ft.IconButton(
                icon=self.get_icon('VIEW_LIST'),
                tooltip="List View",
                selected=self._tree_state.view_mode == CollectionViewMode.LIST,
                on_click=lambda _: self._on_view_mode_changed(CollectionViewMode.LIST),
                icon_color=palette.primary if self._tree_state.view_mode == CollectionViewMode.LIST else palette.text_secondary
            ),
            ft.IconButton(
                icon=self.get_icon('VIEW_COMPACT'),
                tooltip="Compact View",
                selected=self._tree_state.view_mode == CollectionViewMode.COMPACT,
                on_click=lambda _: self._on_view_mode_changed(CollectionViewMode.COMPACT),
                icon_color=palette.primary if self._tree_state.view_mode == CollectionViewMode.COMPACT else palette.text_secondary
            )
        ], spacing=spacing.md)

        # Responsive toolbar layout
        mobile_layout = ft.Column([
            self._search_field,
            ft.Row([
                self._filter_dropdown,
                self._sort_dropdown
            ], spacing=spacing.md),
            self._view_mode_buttons
        ], spacing=spacing.md)

        desktop_layout = ft.Row([
            self._search_field,
            self._filter_dropdown,
            self._sort_dropdown,
            self._view_mode_buttons
        ], spacing=spacing.md)

        # Use responsive layout
        responsive_manager = self.get_responsive_layout()
        is_mobile = responsive_manager.is_mobile()

        return ft.Container(
            content=mobile_layout if is_mobile else desktop_layout,
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(8, 10, 12, 14),
            padding=ft.padding.all(spacing.component_padding),
            margin=ft.margin.only(bottom=spacing.xl)
        )

    def _build_tree_section(self) -> ft.Control:
        """Build the main tree view section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create tree view container
        self._tree_view = ft.Column(
            controls=[],
            spacing=spacing.md,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        # Build tree nodes
        self._rebuild_tree_view()

        # Empty state
        if not self._tree_state.root_nodes:
            empty_state = self._build_empty_state()
            return ft.Container(
                content=empty_state,
                expand=True,
                alignment=ft.alignment.center
            )

        return ft.Container(
            content=self._tree_view,
            expand=True,
            bgcolor=palette.surface,
            border_radius=self.get_breakpoint_value(8, 10, 12, 14),
            padding=ft.padding.all(spacing.component_padding),
            border=ft.border.all(1, palette.outline)
        )

    def _build_footer_section(self) -> ft.Control:
        """Build the footer section with storage indicator and statistics."""
        if not (self._show_storage_indicator or self._show_statistics):
            return ft.Container(height=0)

        controls = []

        if self._show_storage_indicator:
            controls.append(self._build_storage_indicator())

        if self._show_statistics:
            controls.append(self._build_statistics_panel())

        spacing = self.get_spacing()
        return ft.Container(
            content=ft.Column(
                controls=controls,
                spacing=spacing.md
            ),
            padding=ft.padding.only(top=spacing.xl)
        )

    def _build_storage_indicator(self) -> ft.Control:
        """Build storage usage indicator."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Calculate usage percentage
        usage_percent = (self._storage_info.used_space_gb / self._storage_info.total_capacity_gb) * 100

        # Determine color based on usage
        if usage_percent >= self._storage_info.critical_threshold:
            progress_color = palette.error
        elif usage_percent >= self._storage_info.warning_threshold:
            progress_color = palette.warning
        else:
            progress_color = palette.primary

        # Storage text
        storage_text = f"{self._storage_info.used_space_gb:.1f}GB of {self._storage_info.total_capacity_gb:.1f}GB used"

        # Progress bar
        progress_bar = ft.ProgressBar(
            value=usage_percent / 100,
            color=progress_color,
            bgcolor=palette.surface_variant,
            height=8
        )

        # Storage details
        details = ft.Row([
            ft.Icon(
                self.get_icon('STORAGE'),
                color=palette.text_secondary,
                size=16
            ),
            ft.Text(
                storage_text,
                style=self.get_text_style('body_small'),
                color=palette.text_secondary
            ),
            ft.Text(
                f"{usage_percent:.1f}%",
                style=self.get_text_style('body_small'),
                color=progress_color,
                weight=ft.FontWeight.W_500
            )
        ], spacing=spacing.md)

        return ft.Container(
            content=ft.Column([
                details,
                progress_bar
            ], spacing=spacing.md // 2),
            padding=ft.padding.all(spacing.component_padding),
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(6, 8, 10, 12)
        )

    def _build_statistics_panel(self) -> ft.Control:
        """Build collection statistics panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Calculate statistics
        total_collections = self._count_total_collections()
        total_documents = sum(
            collection.statistics.document_count
            for collection in self._collections_cache.values()
        )
        total_size_mb = sum(
            collection.statistics.storage_usage_mb
            for collection in self._collections_cache.values()
        )

        # Statistics items
        stats = [
            ("Collections", str(total_collections), self.get_icon('FOLDER')),
            ("Documents", str(total_documents), self.get_icon('DESCRIPTION')),
            ("Size", f"{total_size_mb:.1f}MB", self.get_icon('STORAGE'))
        ]

        stat_items = []
        for label, value, icon in stats:
            stat_item = ft.Row([
                ft.Icon(icon, color=palette.primary, size=16),
                ft.Column([
                    ft.Text(
                        value,
                        style=self.get_text_style('h6'),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Text(
                        label,
                        style=self.get_text_style('body_small'),
                        color=palette.text_secondary
                    )
                ], spacing=2)
            ], spacing=spacing.md // 2)
            stat_items.append(stat_item)

        return ft.Container(
            content=ft.Row(
                stat_items,
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            ),
            padding=ft.padding.all(spacing.component_padding),
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(6, 8, 10, 12)
        )

    def _rebuild_tree_view(self) -> None:
        """Rebuild the tree view with current state."""
        if not self._tree_view:
            return

        try:
            # Clear existing controls
            self._tree_view.controls.clear()
            self._rendered_nodes.clear()

            # Filter and sort root nodes
            filtered_nodes = self._filter_nodes(self._tree_state.root_nodes)
            sorted_nodes = self._sort_nodes(filtered_nodes)

            # Render visible nodes
            for node in sorted_nodes:
                node_control = self._build_tree_node(node)
                if node_control:
                    self._tree_view.controls.append(node_control)

            # Update UI
            if self._tree_view.page:
                self._tree_view.update()

            logger.debug(f"Rebuilt tree view with {len(sorted_nodes)} root nodes")

        except Exception as e:
            logger.error(f"Error rebuilding tree view: {e}")

    def _build_tree_node(self, node: CollectionNode, level: int = 0) -> Optional[ft.Control]:
        """Build a tree node control."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            collection = node.collection

            # Calculate indentation
            indent_size = level * self.get_breakpoint_value(16, 20, 24, 28)

            # Node icon based on type and state
            if collection.collection_type == CollectionType.FOLDER:
                icon_name = 'FOLDER_OPEN' if node.is_expanded else 'FOLDER'
            elif collection.collection_type == CollectionType.SMART_COLLECTION:
                icon_name = 'AUTO_AWESOME'
            elif collection.collection_type == CollectionType.TAG_COLLECTION:
                icon_name = 'LABEL'
            elif collection.collection_type == CollectionType.SEARCH_COLLECTION:
                icon_name = 'SEARCH'
            else:
                icon_name = 'FOLDER'

            # Status indicator
            status_color = self._get_status_color(collection.status)

            # Expand/collapse button
            expand_button = None
            if node.children or collection.statistics.document_count > 0:
                expand_button = ft.IconButton(
                    icon=self.get_icon('EXPAND_MORE' if node.is_expanded else 'CHEVRON_RIGHT'),
                    icon_size=16,
                    on_click=lambda _: self._on_node_toggle(node),
                    icon_color=palette.text_secondary
                )
            else:
                expand_button = ft.Container(width=40)  # Spacer

            # Collection icon
            collection_icon = ft.Icon(
                self.get_icon(icon_name),
                color=collection.color or palette.primary,
                size=18
            )

            # Collection name and info
            name_text = ft.Text(
                collection.collection_name,
                style=self.get_text_style('body_medium'),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500 if node.is_selected else ft.FontWeight.NORMAL,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=True
            )

            # Document count badge
            count_badge = None
            if collection.statistics.document_count > 0:
                count_badge = ft.Container(
                    content=ft.Text(
                        str(collection.statistics.document_count),
                        style=self.get_text_style('caption'),
                        color=palette.text_primary
                    ),
                    bgcolor=palette.surface_variant,
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2)
                )

            # Status indicator
            status_indicator = ft.Container(
                width=8,
                height=8,
                bgcolor=status_color,
                border_radius=4
            )

            # Node content
            node_content = ft.Row([
                expand_button,
                collection_icon,
                name_text,
                count_badge or ft.Container(),
                status_indicator
            ], spacing=spacing.md)

            # Node container
            node_container = ft.Container(
                content=node_content,
                padding=ft.padding.only(left=indent_size, right=spacing.component_padding),
                bgcolor=palette.surface_variant if node.is_selected else None,
                border_radius=self.get_breakpoint_value(4, 6, 8, 10),
                on_click=lambda _: self._on_node_selected(node),
                ink=True
            )

            # Build result with children
            result_controls = [node_container]

            # Add children if expanded
            if node.is_expanded and node.children:
                for child_node in node.children:
                    child_control = self._build_tree_node(child_node, level + 1)
                    if child_control:
                        result_controls.append(child_control)

            return ft.Column(
                controls=result_controls,
                spacing=spacing.md // 2
            )

        except Exception as e:
            logger.error(f"Error building tree node for {node.collection.collection_name}: {e}")
            return None

    def _build_empty_state(self) -> ft.Control:
        """Build empty state when no collections exist."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Column([
            ft.Icon(
                self.get_icon('FOLDER_OFF'),
                color=palette.text_secondary,
                size=64
            ),
            ft.Text(
                "No Collections Found",
                style=self.get_text_style('h4'),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            ),
            ft.Text(
                "Create your first collection to organize documents",
                style=self.get_text_style('body_medium'),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            ),
            ft.ElevatedButton(
                text="Create Collection",
                icon=self.get_icon('ADD'),
                on_click=self._on_create_collection,
                bgcolor=palette.primary,
                color=palette.text_primary
            )
        ],
        spacing=spacing.xl,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    self.get_icon('ERROR'),
                    color=palette.error,
                    size=48
                ),
                ft.Text(
                    "Error Loading Collections",
                    style=self.get_text_style('h4'),
                    color=palette.error,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    error_message,
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.ElevatedButton(
                    text="Retry",
                    icon=self.get_icon('REFRESH'),
                    on_click=self._on_refresh_collections,
                    bgcolor=palette.primary,
                    color=palette.text_primary
                )
            ],
            spacing=spacing.xl,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True
        )

    # Event Handlers
    def _on_search_changed(self, e: ft.ControlEvent) -> None:
        """Handle search query changes."""
        try:
            query = e.control.value.strip()
            self._tree_state.search_query = query

            # Debounce search
            if self._debounce_timer:
                self._debounce_timer.cancel()

            self._debounce_timer = asyncio.create_task(
                self._debounced_search(query)
            )

        except Exception as e:
            logger.error(f"Error handling search change: {e}")

    async def _debounced_search(self, query: str) -> None:
        """Debounced search implementation."""
        try:
            await asyncio.sleep(0.3)  # 300ms debounce
            self._rebuild_tree_view()
            self._emit_event(CollectionEventType.SEARCH_PERFORMED, data={"query": query})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in debounced search: {e}")

    def _on_filter_changed(self, e: ft.ControlEvent) -> None:
        """Handle filter changes."""
        try:
            filter_value = e.control.value
            self._tree_state.current_filter = CollectionFilterOption(filter_value)
            self._rebuild_tree_view()
            self._emit_event(CollectionEventType.FILTER_CHANGED, data={"filter": filter_value})

        except Exception as e:
            logger.error(f"Error handling filter change: {e}")

    def _on_sort_changed(self, e: ft.ControlEvent) -> None:
        """Handle sort changes."""
        try:
            sort_value = e.control.value
            self._tree_state.current_sort = CollectionSortOption(sort_value)
            self._rebuild_tree_view()
            self._emit_event(CollectionEventType.SORT_CHANGED, data={"sort": sort_value})

        except Exception as e:
            logger.error(f"Error handling sort change: {e}")

    def _on_view_mode_changed(self, mode: CollectionViewMode) -> None:
        """Handle view mode changes."""
        try:
            self._tree_state.view_mode = mode
            self._rebuild_tree_view()
            self._emit_event(CollectionEventType.VIEW_MODE_CHANGED, data={"mode": mode.value})

            # Update button states
            if self._view_mode_buttons:
                for i, button in enumerate(self._view_mode_buttons.controls):
                    if isinstance(button, ft.IconButton):
                        palette = self.get_palette()
                        is_selected = (
                            (i == 0 and mode == CollectionViewMode.TREE) or
                            (i == 1 and mode == CollectionViewMode.LIST) or
                            (i == 2 and mode == CollectionViewMode.COMPACT)
                        )
                        button.icon_color = palette.primary if is_selected else palette.text_secondary
                        button.update()

        except Exception as e:
            logger.error(f"Error handling view mode change: {e}")

    def _on_node_toggle(self, node: CollectionNode) -> None:
        """Handle node expand/collapse."""
        try:
            node.is_expanded = not node.is_expanded
            collection_id = node.collection.collection_id

            if node.is_expanded:
                self._tree_state.expanded_collections.add(collection_id)
                self._emit_event(CollectionEventType.COLLECTION_EXPANDED, collection_id=collection_id)
            else:
                self._tree_state.expanded_collections.discard(collection_id)
                self._emit_event(CollectionEventType.COLLECTION_COLLAPSED, collection_id=collection_id)

            self._rebuild_tree_view()

        except Exception as e:
            logger.error(f"Error toggling node: {e}")

    def _on_node_selected(self, node: CollectionNode) -> None:
        """Handle node selection."""
        try:
            collection_id = node.collection.collection_id

            # Update selection state
            self._tree_state.selected_collections.clear()
            self._tree_state.selected_collections.add(collection_id)

            # Update node states
            self._update_node_selection_states()

            # Emit events
            self._emit_event(CollectionEventType.COLLECTION_SELECTED, collection_id=collection_id)

            if self._on_collection_selected:
                self._on_collection_selected(collection_id)

            self._rebuild_tree_view()

        except Exception as e:
            logger.error(f"Error handling node selection: {e}")

    def _on_create_collection(self, e: ft.ControlEvent = None) -> None:
        """Handle create collection action."""
        try:
            # Show create collection dialog
            self._show_create_collection_dialog()

        except Exception as e:
            logger.error(f"Error creating collection: {e}")

    def _on_refresh_collections(self, e: ft.ControlEvent = None) -> None:
        """Handle refresh collections action."""
        try:
            # Refresh collections from database
            self._refresh_collections_from_database()
            self._rebuild_tree_view()

        except Exception as e:
            logger.error(f"Error refreshing collections: {e}")

    def _on_show_settings(self, e: ft.ControlEvent = None) -> None:
        """Handle show settings action."""
        try:
            # Show collection settings dialog
            self._show_settings_dialog()

        except Exception as e:
            logger.error(f"Error showing settings: {e}")

    # Collection Management Methods
    def _show_create_collection_dialog(self) -> None:
        """Show create collection dialog."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Dialog fields
        name_field = ft.TextField(
            label="Collection Name",
            hint_text="Enter collection name",
            autofocus=True,
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        description_field = ft.TextField(
            label="Description",
            hint_text="Optional description",
            multiline=True,
            max_lines=3,
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        type_dropdown = ft.Dropdown(
            label="Collection Type",
            options=[
                ft.dropdown.Option(key=CollectionType.FOLDER.value, text="Folder"),
                ft.dropdown.Option(key=CollectionType.SMART_COLLECTION.value, text="Smart Collection"),
                ft.dropdown.Option(key=CollectionType.TAG_COLLECTION.value, text="Tag Collection")
            ],
            value=CollectionType.FOLDER.value,
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        parent_dropdown = ft.Dropdown(
            label="Parent Collection",
            hint_text="None (Root Level)",
            options=[
                ft.dropdown.Option(key="", text="None (Root Level)")
            ] + [
                ft.dropdown.Option(key=collection.collection_id, text=collection.collection_name)
                for collection in self._collections_cache.values()
                if collection.collection_type == CollectionType.FOLDER
            ],
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        def create_collection(e):
            try:
                name = name_field.value.strip()
                if not name:
                    self._show_error_snackbar("Collection name is required")
                    return

                # Create collection
                collection = DocumentCollection(
                    collection_id=str(uuid.uuid4()),
                    collection_name=name,
                    description=description_field.value.strip(),
                    collection_type=CollectionType(type_dropdown.value),
                    parent_collection_id=parent_dropdown.value if parent_dropdown.value else None,
                    created_at=datetime.now(),
                    created_by="current_user"  # TODO: Get from auth
                )

                # Add to cache and tree
                self._add_collection_to_tree(collection)

                # Emit event
                self._emit_event(
                    CollectionEventType.COLLECTION_CREATED,
                    collection_id=collection.collection_id,
                    data={"collection": collection}
                )

                # Close dialog
                dialog.open = False
                dialog.update()

                # Show success message
                self._show_success_snackbar(f"Collection '{name}' created successfully")

            except Exception as ex:
                logger.error(f"Error creating collection: {ex}")
                self._show_error_snackbar(f"Failed to create collection: {str(ex)}")

        # Dialog
        dialog = ft.AlertDialog(
            title=ft.Text("Create New Collection", style=self.get_text_style('h4')),
            content=ft.Column([
                name_field,
                description_field,
                type_dropdown,
                parent_dropdown
            ], spacing=spacing.md, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(dialog, 'open', False) or dialog.update()),
                ft.ElevatedButton("Create", on_click=create_collection)
            ]
        )

        # Show dialog
        if self.page:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()

    def _add_collection_to_tree(self, collection: DocumentCollection) -> None:
        """Add collection to tree structure."""
        try:
            # Add to cache
            self._collections_cache[collection.collection_id] = collection

            # Create tree node
            node = CollectionNode(
                collection=collection,
                level=collection.depth_level
            )
            self._tree_nodes_cache[collection.collection_id] = node

            # Add to tree hierarchy
            if collection.parent_collection_id:
                parent_node = self._tree_nodes_cache.get(collection.parent_collection_id)
                if parent_node:
                    parent_node.children.append(node)
                    node.parent = parent_node
                    node.level = parent_node.level + 1
                else:
                    # Parent not found, add to root
                    self._tree_state.root_nodes.append(node)
            else:
                self._tree_state.root_nodes.append(node)

            # Rebuild tree view
            self._rebuild_tree_view()

            logger.info(f"Added collection {collection.collection_name} to tree")

        except Exception as e:
            logger.error(f"Error adding collection to tree: {e}")
            raise

    # Search and Filter Methods
    def _filter_nodes(self, nodes: List[CollectionNode]) -> List[CollectionNode]:
        """Filter nodes based on current filter settings."""
        try:
            filtered_nodes = []

            for node in nodes:
                if self._should_include_node(node):
                    # Create filtered copy with filtered children
                    filtered_node = CollectionNode(
                        collection=node.collection,
                        is_expanded=node.is_expanded,
                        is_selected=node.is_selected,
                        level=node.level
                    )

                    # Recursively filter children
                    if node.children:
                        filtered_children = self._filter_nodes(node.children)
                        filtered_node.children = filtered_children

                        # Update parent references
                        for child in filtered_children:
                            child.parent = filtered_node

                    filtered_nodes.append(filtered_node)

            return filtered_nodes

        except Exception as e:
            logger.error(f"Error filtering nodes: {e}")
            return nodes

    def _should_include_node(self, node: CollectionNode) -> bool:
        """Check if node should be included based on filters."""
        try:
            collection = node.collection

            # Search query filter
            if self._tree_state.search_query:
                query = self._tree_state.search_query.lower()
                if (query not in collection.collection_name.lower() and
                    query not in collection.description.lower() and
                    not any(query in tag.lower() for tag in collection.tags)):
                    return False

            # Collection filter
            filter_option = self._tree_state.current_filter

            if filter_option == CollectionFilterOption.ACTIVE_ONLY:
                return collection.status == CollectionStatus.ACTIVE
            elif filter_option == CollectionFilterOption.FOLDERS_ONLY:
                return collection.collection_type == CollectionType.FOLDER
            elif filter_option == CollectionFilterOption.SMART_COLLECTIONS_ONLY:
                return collection.collection_type == CollectionType.SMART_COLLECTION
            elif filter_option == CollectionFilterOption.NON_EMPTY_ONLY:
                return collection.statistics.document_count > 0
            elif filter_option == CollectionFilterOption.RECENT:
                # Show collections modified in last 7 days
                if collection.updated_at:
                    days_ago = (datetime.now() - collection.updated_at).days
                    return days_ago <= 7
                return False
            elif filter_option == CollectionFilterOption.FAVORITES:
                return collection.is_favorite

            return True

        except Exception as e:
            logger.error(f"Error checking node inclusion: {e}")
            return True

    def _sort_nodes(self, nodes: List[CollectionNode]) -> List[CollectionNode]:
        """Sort nodes based on current sort settings."""
        try:
            sort_option = self._tree_state.current_sort

            def get_sort_key(node: CollectionNode):
                collection = node.collection

                if sort_option == CollectionSortOption.NAME_ASC:
                    return collection.collection_name.lower()
                elif sort_option == CollectionSortOption.NAME_DESC:
                    return collection.collection_name.lower()
                elif sort_option == CollectionSortOption.DATE_ASC:
                    return collection.created_at or datetime.min
                elif sort_option == CollectionSortOption.DATE_DESC:
                    return collection.created_at or datetime.min
                elif sort_option == CollectionSortOption.SIZE_ASC:
                    return collection.statistics.storage_usage_mb
                elif sort_option == CollectionSortOption.SIZE_DESC:
                    return collection.statistics.storage_usage_mb
                elif sort_option == CollectionSortOption.TYPE_ASC:
                    return collection.collection_type.value
                elif sort_option == CollectionSortOption.TYPE_DESC:
                    return collection.collection_type.value
                elif sort_option == CollectionSortOption.DOCUMENT_COUNT_ASC:
                    return collection.statistics.document_count
                elif sort_option == CollectionSortOption.DOCUMENT_COUNT_DESC:
                    return collection.statistics.document_count
                else:
                    return collection.collection_name.lower()

            # Determine reverse order
            reverse = sort_option.value.endswith('_desc')

            # Sort nodes
            sorted_nodes = sorted(nodes, key=get_sort_key, reverse=reverse)

            # Recursively sort children
            for node in sorted_nodes:
                if node.children:
                    node.children = self._sort_nodes(node.children)

            return sorted_nodes

        except Exception as e:
            logger.error(f"Error sorting nodes: {e}")
            return nodes

    # Utility Methods
    def _get_status_color(self, status: CollectionStatus) -> str:
        """Get color for collection status."""
        palette = self.get_palette()

        status_colors = {
            CollectionStatus.ACTIVE: palette.success,
            CollectionStatus.INACTIVE: palette.text_secondary,
            CollectionStatus.PROCESSING: palette.warning,
            CollectionStatus.ERROR: palette.error,
            CollectionStatus.ARCHIVED: palette.outline
        }

        return status_colors.get(status, palette.text_secondary)

    def _count_total_collections(self) -> int:
        """Count total number of collections."""
        return len(self._collections_cache)

    def _update_node_selection_states(self) -> None:
        """Update selection states for all nodes."""
        try:
            def update_node(node: CollectionNode):
                node.is_selected = node.collection.collection_id in self._tree_state.selected_collections
                for child in node.children:
                    update_node(child)

            for root_node in self._tree_state.root_nodes:
                update_node(root_node)

        except Exception as e:
            logger.error(f"Error updating node selection states: {e}")

    def _emit_event(self, event_type: CollectionEventType, collection_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit collection event."""
        try:
            if self._on_collection_changed:
                event = CollectionEvent(
                    event_type=event_type,
                    collection_id=collection_id,
                    data=data or {}
                )
                self._on_collection_changed(event)

        except Exception as e:
            logger.error(f"Error emitting event: {e}")

    def _show_success_snackbar(self, message: str) -> None:
        """Show success snackbar message."""
        if self.page:
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=self.get_palette().success
                )
            )

    def _show_error_snackbar(self, message: str) -> None:
        """Show error snackbar message."""
        if self.page:
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=self.get_palette().error
                )
            )

    def _refresh_collections_from_database(self) -> None:
        """Refresh collections from database."""
        try:
            # TODO: Implement database integration
            # This would typically load collections from the database
            # For now, create some sample data

            sample_collections = [
                DocumentCollection(
                    collection_id="root-1",
                    collection_name="Research Papers",
                    description="Academic research papers and publications",
                    collection_type=CollectionType.FOLDER,
                    statistics=CollectionStatistics(document_count=15, storage_usage_mb=45.2)
                ),
                DocumentCollection(
                    collection_id="root-2",
                    collection_name="Technical Documentation",
                    description="Software and technical documentation",
                    collection_type=CollectionType.FOLDER,
                    statistics=CollectionStatistics(document_count=8, storage_usage_mb=23.1)
                ),
                DocumentCollection(
                    collection_id="smart-1",
                    collection_name="Recent PDFs",
                    description="PDFs added in the last 30 days",
                    collection_type=CollectionType.SMART_COLLECTION,
                    statistics=CollectionStatistics(document_count=5, storage_usage_mb=12.8)
                )
            ]

            # Clear existing data
            self._collections_cache.clear()
            self._tree_nodes_cache.clear()
            self._tree_state.root_nodes.clear()

            # Add sample collections
            for collection in sample_collections:
                self._add_collection_to_tree(collection)

            logger.info(f"Refreshed {len(sample_collections)} collections from database")

        except Exception as e:
            logger.error(f"Error refreshing collections from database: {e}")
            raise

    def _show_settings_dialog(self) -> None:
        """Show collection settings dialog."""
        # TODO: Implement settings dialog
        self._show_success_snackbar("Settings dialog not yet implemented")

    # Public API Methods
    def refresh_collections(self) -> None:
        """Public method to refresh collections."""
        self._refresh_collections_from_database()

    def select_collection(self, collection_id: str) -> None:
        """Public method to select a collection."""
        if collection_id in self._collections_cache:
            self._tree_state.selected_collections.clear()
            self._tree_state.selected_collections.add(collection_id)
            self._update_node_selection_states()
            self._rebuild_tree_view()

    def get_selected_collection(self) -> Optional[DocumentCollection]:
        """Get currently selected collection."""
        if self._tree_state.selected_collections:
            collection_id = next(iter(self._tree_state.selected_collections))
            return self._collections_cache.get(collection_id)
        return None

    def set_storage_info(self, storage_info: StorageInfo) -> None:
        """Update storage information."""
        self._storage_info = storage_info
        if self._storage_indicator:
            self._storage_indicator = self._build_storage_indicator()
            self.update()

    # Context Menu and Keyboard Navigation
    def _build_context_menu(self, node: CollectionNode) -> ft.MenuBar:
        """Build context menu for collection node."""
        if not self._enable_context_menu:
            return None

        palette = self.get_palette()
        collection = node.collection

        menu_items = []

        # Rename option
        if not collection.is_readonly:
            menu_items.append(
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(self.get_icon('EDIT'), size=16),
                        ft.Text("Rename")
                    ]),
                    on_click=lambda _: self._show_rename_dialog(node)
                )
            )

        # Delete option
        if not collection.is_system and not collection.is_readonly:
            menu_items.append(
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(self.get_icon('DELETE'), size=16, color=palette.error),
                        ft.Text("Delete", color=palette.error)
                    ]),
                    on_click=lambda _: self._show_delete_confirmation(node)
                )
            )

        # Separator
        if menu_items:
            menu_items.append(ft.Divider())

        # Properties option
        menu_items.append(
            ft.MenuItemButton(
                content=ft.Row([
                    ft.Icon(self.get_icon('INFO'), size=16),
                    ft.Text("Properties")
                ]),
                on_click=lambda _: self._show_properties_dialog(node)
            )
        )

        return ft.MenuBar(
            controls=[
                ft.SubmenuButton(
                    content=ft.Text(""),
                    controls=menu_items
                )
            ]
        )

    def _show_rename_dialog(self, node: CollectionNode) -> None:
        """Show rename collection dialog."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        collection = node.collection

        name_field = ft.TextField(
            label="Collection Name",
            value=collection.collection_name,
            autofocus=True,
            bgcolor=palette.surface,
            border_color=palette.outline
        )

        def rename_collection(e):
            try:
                new_name = name_field.value.strip()
                if not new_name:
                    self._show_error_snackbar("Collection name is required")
                    return

                if new_name == collection.collection_name:
                    dialog.open = False
                    dialog.update()
                    return

                # Update collection
                old_name = collection.collection_name
                collection.collection_name = new_name
                collection.updated_at = datetime.now()

                # Emit event
                self._emit_event(
                    CollectionEventType.COLLECTION_RENAMED,
                    collection_id=collection.collection_id,
                    data={"old_name": old_name, "new_name": new_name}
                )

                # Close dialog
                dialog.open = False
                dialog.update()

                # Rebuild tree
                self._rebuild_tree_view()

                # Show success message
                self._show_success_snackbar(f"Collection renamed to '{new_name}'")

            except Exception as ex:
                logger.error(f"Error renaming collection: {ex}")
                self._show_error_snackbar(f"Failed to rename collection: {str(ex)}")

        dialog = ft.AlertDialog(
            title=ft.Text("Rename Collection", style=self.get_text_style('h4')),
            content=name_field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(dialog, 'open', False) or dialog.update()),
                ft.ElevatedButton("Rename", on_click=rename_collection)
            ]
        )

        if self.page:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()

    def _show_delete_confirmation(self, node: CollectionNode) -> None:
        """Show delete collection confirmation dialog."""
        palette = self.get_palette()
        typography = self.get_typography()

        collection = node.collection

        def delete_collection(e):
            try:
                # Remove from tree
                self._remove_collection_from_tree(collection.collection_id)

                # Emit event
                self._emit_event(
                    CollectionEventType.COLLECTION_DELETED,
                    collection_id=collection.collection_id,
                    data={"collection_name": collection.collection_name}
                )

                # Close dialog
                dialog.open = False
                dialog.update()

                # Show success message
                self._show_success_snackbar(f"Collection '{collection.collection_name}' deleted")

            except Exception as ex:
                logger.error(f"Error deleting collection: {ex}")
                self._show_error_snackbar(f"Failed to delete collection: {str(ex)}")

        dialog = ft.AlertDialog(
            title=ft.Text("Delete Collection", style=self.get_text_style('h4')),
            content=ft.Text(
                f"Are you sure you want to delete '{collection.collection_name}'?\n\n"
                f"This action cannot be undone. All documents in this collection will be moved to the root level.",
                style=self.get_text_style('body_medium')
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(dialog, 'open', False) or dialog.update()),
                ft.ElevatedButton(
                    "Delete",
                    on_click=delete_collection,
                    bgcolor=palette.error,
                    color=palette.on_error
                )
            ]
        )

        if self.page:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()

    def _show_properties_dialog(self, node: CollectionNode) -> None:
        """Show collection properties dialog."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        collection = node.collection
        stats = collection.statistics

        # Properties content
        properties = [
            ("Name", collection.collection_name),
            ("Type", collection.collection_type.value.replace('_', ' ').title()),
            ("Status", collection.status.value.title()),
            ("Documents", str(stats.document_count)),
            ("Size", f"{stats.storage_usage_mb:.1f} MB"),
            ("Created", collection.created_at.strftime("%Y-%m-%d %H:%M") if collection.created_at else "Unknown"),
            ("Updated", collection.updated_at.strftime("%Y-%m-%d %H:%M") if collection.updated_at else "Never"),
            ("Path", collection.path or "/"),
            ("ID", collection.collection_id)
        ]

        property_controls = []
        for label, value in properties:
            property_controls.append(
                ft.Row([
                    ft.Text(
                        f"{label}:",
                        style=self.get_text_style('body_medium'),
                        weight=ft.FontWeight.W_500,
                        width=100
                    ),
                    ft.Text(
                        str(value),
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary,
                        expand=True
                    )
                ])
            )

        dialog = ft.AlertDialog(
            title=ft.Text("Collection Properties", style=self.get_text_style('h4')),
            content=ft.Column(
                property_controls,
                spacing=spacing.md,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                height=400
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: setattr(dialog, 'open', False) or dialog.update())
            ]
        )

        if self.page:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()

    def _remove_collection_from_tree(self, collection_id: str) -> None:
        """Remove collection from tree structure."""
        try:
            # Remove from cache
            if collection_id in self._collections_cache:
                del self._collections_cache[collection_id]

            if collection_id in self._tree_nodes_cache:
                node = self._tree_nodes_cache[collection_id]

                # Remove from parent's children
                if node.parent:
                    node.parent.children = [
                        child for child in node.parent.children
                        if child.collection.collection_id != collection_id
                    ]
                else:
                    # Remove from root nodes
                    self._tree_state.root_nodes = [
                        root_node for root_node in self._tree_state.root_nodes
                        if root_node.collection.collection_id != collection_id
                    ]

                # Move children to parent or root
                for child in node.children:
                    if node.parent:
                        child.parent = node.parent
                        node.parent.children.append(child)
                    else:
                        child.parent = None
                        self._tree_state.root_nodes.append(child)

                del self._tree_nodes_cache[collection_id]

            # Remove from selection
            self._tree_state.selected_collections.discard(collection_id)
            self._tree_state.expanded_collections.discard(collection_id)

            # Rebuild tree view
            self._rebuild_tree_view()

            logger.info(f"Removed collection {collection_id} from tree")

        except Exception as e:
            logger.error(f"Error removing collection from tree: {e}")
            raise

    # Keyboard Navigation
    def on_key_down(self, e: ft.KeyboardEvent) -> None:
        """Handle keyboard navigation."""
        try:
            if e.key == "Delete" and self._tree_state.selected_collections:
                # Delete selected collection
                collection_id = next(iter(self._tree_state.selected_collections))
                node = self._tree_nodes_cache.get(collection_id)
                if node and not node.collection.is_system and not node.collection.is_readonly:
                    self._show_delete_confirmation(node)

            elif e.key == "F2" and self._tree_state.selected_collections:
                # Rename selected collection
                collection_id = next(iter(self._tree_state.selected_collections))
                node = self._tree_nodes_cache.get(collection_id)
                if node and not node.collection.is_readonly:
                    self._show_rename_dialog(node)

            elif e.key == "Enter" and self._tree_state.selected_collections:
                # Toggle expansion of selected collection
                collection_id = next(iter(self._tree_state.selected_collections))
                node = self._tree_nodes_cache.get(collection_id)
                if node:
                    self._on_node_toggle(node)

            elif e.key == "Escape":
                # Clear selection
                self._tree_state.selected_collections.clear()
                self._update_node_selection_states()
                self._rebuild_tree_view()

        except Exception as ex:
            logger.error(f"Error handling keyboard event: {ex}")

    # Cleanup
    def will_unmount(self) -> None:
        """Cleanup when component is unmounted."""
        try:
            # Cancel timers
            if self._debounce_timer:
                self._debounce_timer.cancel()

            if self._refresh_timer:
                self._refresh_timer.cancel()

            # Clear caches
            self._collections_cache.clear()
            self._tree_nodes_cache.clear()
            self._rendered_nodes.clear()

            logger.info("DocumentCollectionUI cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        super().will_unmount()
