"""
Module: version_tree_ui
Description: Git-style version tree visualization for model versions with comprehensive branching and merging display.
            Provides interactive version tree interface with responsive design, theme integration, and advanced
            version management capabilities including branch visualization, merge tracking, and version comparison.
Phase: 4
Location: /src/modules/ui/model_registry_ui/version_tree_ui/version_tree_ui.py
"""

# Standard library imports
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import json
import uuid

# Third-party imports
import flet as ft

# Local imports
try:
    from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
    from src.modules.database.model_repository_db.model_versions_db.model_versions_db import (
        ModelVersionsDB, ModelVersion, BranchType, VersionType
    )
    from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger
except ImportError:
    # Fallback for testing without full infrastructure
    class ThemeAwareUserControl:
        def __init__(self):
            self.page = None
        def get_palette(self): return None
        def get_spacing(self): return None
        def get_icon(self, name): return None
        def get_breakpoint_value(self, *args): return args[0] if args else 8
        def create_responsive_container(self, **kwargs): return ft.Container(**kwargs)
        def is_mobile(self): return False
        def is_tablet(self): return False
    
    @dataclass
    class ModelVersion:
        version_id: str = ""
        model_id: str = ""
        version_number: str = ""
        branch_name: str = "main"
        parent_version_id: Optional[str] = None
        created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        created_by: Optional[str] = None
        commit_message: Optional[str] = None
        is_stable: bool = False
        is_release: bool = False
        is_latest: bool = False
        tags: List[str] = field(default_factory=list)
    
    class BranchType(Enum):
        MAIN = "main"
        FEATURE = "feature"
        HOTFIX = "hotfix"
        RELEASE = "release"
    
    def get_logger(name): 
        return logging.getLogger(name)


# Initialize logger
logger = get_logger(__name__)


class TreeViewMode(Enum):
    """Version tree view modes."""
    COMPACT = "compact"
    DETAILED = "detailed"
    TIMELINE = "timeline"
    GRAPH = "graph"


class TreeSortOption(Enum):
    """Version tree sorting options."""
    CHRONOLOGICAL = "chronological"
    VERSION_NUMBER = "version_number"
    BRANCH_NAME = "branch_name"
    CREATION_DATE = "creation_date"


class TreeFilterOption(Enum):
    """Version tree filtering options."""
    ALL_VERSIONS = "all_versions"
    STABLE_ONLY = "stable_only"
    RELEASES_ONLY = "releases_only"
    CURRENT_BRANCH = "current_branch"
    TAGGED_VERSIONS = "tagged_versions"


@dataclass
class VersionNode:
    """Represents a version node in the tree."""
    version: ModelVersion
    level: int = 0
    x_position: int = 0
    y_position: int = 0
    children: List['VersionNode'] = field(default_factory=list)
    parent: Optional['VersionNode'] = None
    is_expanded: bool = True
    is_selected: bool = False
    is_highlighted: bool = False
    branch_color: str = "#6750A4"
    connection_lines: List[Tuple[int, int, int, int]] = field(default_factory=list)


@dataclass
class TreeState:
    """Version tree state management."""
    root_nodes: List[VersionNode] = field(default_factory=list)
    selected_version: Optional[str] = None
    expanded_nodes: Set[str] = field(default_factory=set)
    highlighted_path: List[str] = field(default_factory=list)
    view_mode: TreeViewMode = TreeViewMode.DETAILED
    sort_option: TreeSortOption = TreeSortOption.CHRONOLOGICAL
    filter_option: TreeFilterOption = TreeFilterOption.ALL_VERSIONS
    search_query: str = ""
    show_merge_lines: bool = True
    show_branch_labels: bool = True
    show_version_details: bool = True


@dataclass
class VersionTreeConfig:
    """Configuration for version tree UI."""
    model_id: str
    max_versions: int = 100
    auto_refresh: bool = True
    refresh_interval: int = 30
    enable_drag_drop: bool = True
    enable_context_menu: bool = True
    enable_keyboard_navigation: bool = True
    show_performance_metrics: bool = True
    show_deployment_status: bool = True
    enable_version_comparison: bool = True
    compact_mode_threshold: int = 576  # Mobile breakpoint
    animation_duration: int = 300
    node_spacing: int = 40
    level_spacing: int = 60
    line_thickness: int = 2


class VersionTreeUI(ThemeAwareUserControl):
    """
    Git-style version tree visualization for model versions with responsive design and theme integration.

    Features:
    - Interactive git-style version tree with branching and merging visualization
    - Multiple view modes (compact, detailed, timeline, graph)
    - Advanced filtering and sorting with real-time search
    - Version comparison and diff visualization
    - Branch management with color-coded branches
    - Drag-and-drop version operations
    - Context menus for version actions
    - Keyboard navigation and accessibility support
    - Theme-aware styling with responsive breakpoints
    - Integration with model version database
    - Real-time version updates and notifications
    - Performance metrics and deployment status display
    """

    def __init__(self, config: VersionTreeConfig, **kwargs):
        super().__init__(**kwargs)
        self._config = config
        self._tree_state = TreeState()
        self._version_db = None
        self._versions_cache: Dict[str, ModelVersion] = {}
        self._tree_nodes_cache: Dict[str, VersionNode] = {}
        self._rendered_nodes: Dict[str, ft.Control] = {}
        
        # UI components
        self._tree_view: Optional[ft.Column] = None
        self._toolbar: Optional[ft.Row] = None
        self._search_field: Optional[ft.TextField] = None
        self._view_mode_dropdown: Optional[ft.Dropdown] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._sort_dropdown: Optional[ft.Dropdown] = None
        self._refresh_button: Optional[ft.IconButton] = None
        self._status_bar: Optional[ft.Row] = None
        
        # Event handlers
        self._on_version_selected: Optional[Callable[[str], None]] = None
        self._on_version_compared: Optional[Callable[[str, str], None]] = None
        self._on_branch_created: Optional[Callable[[str, str], None]] = None
        self._on_version_tagged: Optional[Callable[[str, str], None]] = None
        
        # State management
        self._is_loading = False
        self._last_refresh = datetime.now(timezone.utc)
        self._refresh_timer: Optional[asyncio.Task] = None
        
        # Initialize database connection
        self._initialize_database()
        
        logger.info(f"VersionTreeUI initialized for model {config.model_id}")

    def _initialize_database(self) -> None:
        """Initialize database connection."""
        try:
            self._version_db = ModelVersionsDB()
            logger.debug("Version database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize version database: {e}")
            self._version_db = None

    async def load_versions(self, force_refresh: bool = False) -> None:
        """Load model versions from database."""
        if self._is_loading and not force_refresh:
            return
            
        self._is_loading = True
        
        try:
            if not self._version_db:
                logger.warning("Version database not available")
                return
            
            # Get versions from database
            versions = self._version_db.list_versions(
                self._config.model_id,
                limit=self._config.max_versions
            )
            
            # Update cache
            self._versions_cache.clear()
            for version in versions:
                self._versions_cache[version.version_id] = version
            
            # Build tree structure
            await self._build_version_tree()
            
            # Update UI
            await self._refresh_tree_view()
            
            self._last_refresh = datetime.now(timezone.utc)
            logger.debug(f"Loaded {len(versions)} versions for model {self._config.model_id}")
            
        except Exception as e:
            logger.error(f"Failed to load versions: {e}")
        finally:
            self._is_loading = False

    async def _build_version_tree(self) -> None:
        """Build the version tree structure."""
        try:
            # Clear existing tree
            self._tree_state.root_nodes.clear()
            self._tree_nodes_cache.clear()
            
            # Create nodes for all versions
            for version in self._versions_cache.values():
                node = VersionNode(version=version)
                self._tree_nodes_cache[version.version_id] = node
            
            # Build parent-child relationships
            for version_id, node in self._tree_nodes_cache.items():
                version = node.version
                
                if version.parent_version_id and version.parent_version_id in self._tree_nodes_cache:
                    parent_node = self._tree_nodes_cache[version.parent_version_id]
                    parent_node.children.append(node)
                    node.parent = parent_node
                    node.level = parent_node.level + 1
                else:
                    # Root node
                    self._tree_state.root_nodes.append(node)
            
            # Calculate positions and colors
            await self._calculate_tree_layout()
            
            logger.debug(f"Built version tree with {len(self._tree_state.root_nodes)} root nodes")
            
        except Exception as e:
            logger.error(f"Failed to build version tree: {e}")

    async def _calculate_tree_layout(self) -> None:
        """Calculate positions and layout for tree nodes."""
        try:
            # Assign branch colors
            branch_colors = self._get_branch_colors()
            
            # Calculate positions
            y_position = 0
            for root_node in self._tree_state.root_nodes:
                y_position = await self._calculate_node_positions(root_node, 0, y_position, branch_colors)
            
            # Calculate connection lines
            for node in self._tree_nodes_cache.values():
                if node.parent:
                    self._calculate_connection_lines(node)
            
        except Exception as e:
            logger.error(f"Failed to calculate tree layout: {e}")

    def _get_branch_colors(self) -> Dict[str, str]:
        """Get color mapping for branches."""
        palette = self.get_palette()
        if not palette:
            return {}
        
        # Default branch colors
        default_colors = [
            palette.primary,
            palette.secondary,
            "#FF6B6B",  # Red
            "#4ECDC4",  # Teal
            "#45B7D1",  # Blue
            "#96CEB4",  # Green
            "#FFEAA7",  # Yellow
            "#DDA0DD",  # Plum
            "#98D8C8",  # Mint
            "#F7DC6F"   # Light Yellow
        ]
        
        # Get unique branch names
        branches = set()
        for version in self._versions_cache.values():
            branches.add(version.branch_name)
        
        # Assign colors
        branch_colors = {}
        for i, branch in enumerate(sorted(branches)):
            branch_colors[branch] = default_colors[i % len(default_colors)]
        
        return branch_colors

    async def _calculate_node_positions(self, node: VersionNode, x_pos: int, y_pos: int, 
                                      branch_colors: Dict[str, str]) -> int:
        """Calculate positions for a node and its children."""
        try:
            # Set node position
            node.x_position = x_pos
            node.y_position = y_pos
            
            # Set branch color
            branch_name = node.version.branch_name
            node.branch_color = branch_colors.get(branch_name, "#6750A4")
            
            # Move to next row
            y_pos += self._config.node_spacing
            
            # Process children
            for child in node.children:
                y_pos = await self._calculate_node_positions(
                    child, x_pos + self._config.level_spacing, y_pos, branch_colors
                )
            
            return y_pos
            
        except Exception as e:
            logger.error(f"Failed to calculate node positions: {e}")
            return y_pos

    def _calculate_connection_lines(self, node: VersionNode) -> None:
        """Calculate connection lines between parent and child nodes."""
        if not node.parent:
            return
        
        try:
            parent = node.parent
            
            # Calculate line coordinates
            start_x = parent.x_position + 20  # Node width offset
            start_y = parent.y_position + 10  # Node height offset
            end_x = node.x_position
            end_y = node.y_position + 10
            
            # Add connection line
            node.connection_lines.append((start_x, start_y, end_x, end_y))
            
        except Exception as e:
            logger.error(f"Failed to calculate connection lines: {e}")

    def build(self) -> ft.Control:
        """Build the version tree UI."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create main container
            main_container = self.create_responsive_container(
                content=ft.Column([
                    self._build_toolbar(),
                    ft.Divider(height=1, color=palette.outline if palette else None),
                    self._build_tree_section(),
                    self._build_status_bar()
                ], spacing=0, expand=True),
                padding=spacing.component_padding if spacing else 16
            )

            # Start auto-refresh if enabled
            if self._config.auto_refresh:
                self._start_auto_refresh()

            # Load initial data
            asyncio.create_task(self.load_versions())

            return main_container

        except Exception as e:
            logger.error(f"Failed to build version tree UI: {e}")
            return ft.Container(
                content=ft.Text("Error loading version tree"),
                alignment=ft.alignment.center
            )

    def _build_toolbar(self) -> ft.Control:
        """Build the toolbar with controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Search field
        self._search_field = ft.TextField(
            hint_text="Search versions...",
            prefix_icon=self.get_icon('SEARCH'),
            on_change=self._on_search_changed,
            expand=True,
            dense=True
        )

        # View mode dropdown
        self._view_mode_dropdown = ft.Dropdown(
            label="View",
            value=self._tree_state.view_mode.value,
            options=[
                ft.dropdown.Option(TreeViewMode.COMPACT.value, "Compact"),
                ft.dropdown.Option(TreeViewMode.DETAILED.value, "Detailed"),
                ft.dropdown.Option(TreeViewMode.TIMELINE.value, "Timeline"),
                ft.dropdown.Option(TreeViewMode.GRAPH.value, "Graph")
            ],
            on_change=self._on_view_mode_changed,
            dense=True,
            width=self.get_breakpoint_value(120, 140, 160, 180)
        )

        # Filter dropdown
        self._filter_dropdown = ft.Dropdown(
            label="Filter",
            value=self._tree_state.filter_option.value,
            options=[
                ft.dropdown.Option(TreeFilterOption.ALL_VERSIONS.value, "All Versions"),
                ft.dropdown.Option(TreeFilterOption.STABLE_ONLY.value, "Stable Only"),
                ft.dropdown.Option(TreeFilterOption.RELEASES_ONLY.value, "Releases Only"),
                ft.dropdown.Option(TreeFilterOption.CURRENT_BRANCH.value, "Current Branch"),
                ft.dropdown.Option(TreeFilterOption.TAGGED_VERSIONS.value, "Tagged Versions")
            ],
            on_change=self._on_filter_changed,
            dense=True,
            width=self.get_breakpoint_value(140, 160, 180, 200)
        )

        # Sort dropdown
        self._sort_dropdown = ft.Dropdown(
            label="Sort",
            value=self._tree_state.sort_option.value,
            options=[
                ft.dropdown.Option(TreeSortOption.CHRONOLOGICAL.value, "Chronological"),
                ft.dropdown.Option(TreeSortOption.VERSION_NUMBER.value, "Version Number"),
                ft.dropdown.Option(TreeSortOption.BRANCH_NAME.value, "Branch Name"),
                ft.dropdown.Option(TreeSortOption.CREATION_DATE.value, "Creation Date")
            ],
            on_change=self._on_sort_changed,
            dense=True,
            width=self.get_breakpoint_value(120, 140, 160, 180)
        )

        # Refresh button
        self._refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh versions",
            on_click=self._on_refresh_clicked
        )

        # Settings button
        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Tree settings",
            on_click=self._on_settings_clicked
        )

        # Build responsive toolbar
        if self.is_mobile():
            # Mobile layout - stack controls vertically
            return ft.Column([
                ft.Row([
                    self._search_field,
                    self._refresh_button,
                    settings_button
                ], spacing=spacing.md),
                ft.Row([
                    self._view_mode_dropdown,
                    self._filter_dropdown,
                    self._sort_dropdown
                ], spacing=spacing.md)
            ], spacing=spacing.sm)
        else:
            # Desktop layout - single row
            return ft.Row([
                self._search_field,
                self._view_mode_dropdown,
                self._filter_dropdown,
                self._sort_dropdown,
                self._refresh_button,
                settings_button
            ], spacing=spacing.md)

    def _build_tree_section(self) -> ft.Control:
        """Build the main tree view section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create tree view container
        self._tree_view = ft.Column(
            controls=[],
            spacing=spacing.sm if spacing else 8,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        # Empty state
        empty_state = self._build_empty_state()

        return ft.Container(
            content=ft.Stack([
                self._tree_view,
                empty_state
            ]),
            expand=True,
            bgcolor=palette.surface if palette else None,
            border_radius=self.get_breakpoint_value(8, 10, 12, 14),
            padding=ft.padding.all(spacing.component_padding if spacing else 16),
            border=ft.border.all(1, palette.outline if palette else "#E0E0E0")
        )

    def _build_empty_state(self) -> ft.Control:
        """Build empty state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    self.get_icon('ACCOUNT_TREE'),
                    size=self.get_breakpoint_value(48, 56, 64, 72),
                    color=palette.on_surface_variant if palette else None
                ),
                ft.Text(
                    "No versions found",
                    size=self.get_breakpoint_value(16, 18, 20, 22),
                    color=palette.on_surface_variant if palette else None,
                    weight=ft.FontWeight.W_500
                ),
                ft.Text(
                    "Model versions will appear here when available",
                    size=self.get_breakpoint_value(12, 13, 14, 15),
                    color=palette.on_surface_variant if palette else None,
                    text_align=ft.TextAlign.CENTER
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.md if spacing else 16),
            alignment=ft.alignment.center,
            visible=len(self._versions_cache) == 0
        )

    def _build_status_bar(self) -> ft.Control:
        """Build status bar with information."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Version count
        version_count = len(self._versions_cache)
        count_text = ft.Text(
            f"{version_count} version{'s' if version_count != 1 else ''}",
            size=self.get_breakpoint_value(11, 12, 13, 14),
            color=palette.on_surface_variant if palette else None
        )

        # Last refresh time
        refresh_text = ft.Text(
            f"Last updated: {self._last_refresh.strftime('%H:%M:%S')}",
            size=self.get_breakpoint_value(11, 12, 13, 14),
            color=palette.on_surface_variant if palette else None
        )

        # Loading indicator
        loading_indicator = ft.ProgressRing(
            width=16,
            height=16,
            visible=self._is_loading
        )

        self._status_bar = ft.Row([
            count_text,
            ft.VerticalDivider(width=1),
            refresh_text,
            loading_indicator
        ], spacing=spacing.md if spacing else 16)

        return ft.Container(
            content=self._status_bar,
            padding=ft.padding.symmetric(horizontal=spacing.component_padding if spacing else 16, vertical=spacing.sm if spacing else 8),
            bgcolor=palette.surface_variant if palette else None,
            border_radius=ft.border_radius.only(
                bottom_left=self.get_breakpoint_value(8, 10, 12, 14),
                bottom_right=self.get_breakpoint_value(8, 10, 12, 14)
            )
        )

    async def _refresh_tree_view(self) -> None:
        """Refresh the tree view with current data."""
        if not self._tree_view:
            return

        try:
            # Clear existing controls
            self._tree_view.controls.clear()
            self._rendered_nodes.clear()

            # Filter and sort nodes
            filtered_nodes = self._filter_nodes(self._tree_state.root_nodes)
            sorted_nodes = self._sort_nodes(filtered_nodes)

            # Render visible nodes
            for node in sorted_nodes:
                node_control = await self._build_tree_node(node)
                if node_control:
                    self._tree_view.controls.append(node_control)

            # Update UI
            if self._tree_view.page:
                self._tree_view.update()

            # Update empty state visibility
            await self._update_empty_state()

            logger.debug(f"Refreshed tree view with {len(sorted_nodes)} root nodes")

        except Exception as e:
            logger.error(f"Error refreshing tree view: {e}")

    def _filter_nodes(self, nodes: List[VersionNode]) -> List[VersionNode]:
        """Filter nodes based on current filter settings."""
        try:
            filtered = []

            for node in nodes:
                version = node.version
                include_node = True

                # Apply filter
                if self._tree_state.filter_option == TreeFilterOption.STABLE_ONLY:
                    include_node = version.is_stable
                elif self._tree_state.filter_option == TreeFilterOption.RELEASES_ONLY:
                    include_node = version.is_release
                elif self._tree_state.filter_option == TreeFilterOption.TAGGED_VERSIONS:
                    include_node = len(version.tags) > 0
                elif self._tree_state.filter_option == TreeFilterOption.CURRENT_BRANCH:
                    include_node = version.branch_name == "main"  # Default to main branch

                # Apply search filter
                if self._tree_state.search_query and include_node:
                    query = self._tree_state.search_query.lower()
                    include_node = (
                        query in version.version_number.lower() or
                        query in version.branch_name.lower() or
                        (version.commit_message and query in version.commit_message.lower()) or
                        (version.created_by and query in version.created_by.lower()) or
                        any(query in tag.lower() for tag in version.tags)
                    )

                if include_node:
                    # Recursively filter children
                    filtered_children = self._filter_nodes(node.children)
                    filtered_node = VersionNode(
                        version=node.version,
                        level=node.level,
                        x_position=node.x_position,
                        y_position=node.y_position,
                        children=filtered_children,
                        parent=node.parent,
                        is_expanded=node.is_expanded,
                        is_selected=node.is_selected,
                        is_highlighted=node.is_highlighted,
                        branch_color=node.branch_color,
                        connection_lines=node.connection_lines
                    )
                    filtered.append(filtered_node)

            return filtered

        except Exception as e:
            logger.error(f"Error filtering nodes: {e}")
            return nodes

    def _sort_nodes(self, nodes: List[VersionNode]) -> List[VersionNode]:
        """Sort nodes based on current sort settings."""
        try:
            if self._tree_state.sort_option == TreeSortOption.CHRONOLOGICAL:
                return sorted(nodes, key=lambda n: n.version.created_at, reverse=True)
            elif self._tree_state.sort_option == TreeSortOption.VERSION_NUMBER:
                return sorted(nodes, key=lambda n: n.version.version_number)
            elif self._tree_state.sort_option == TreeSortOption.BRANCH_NAME:
                return sorted(nodes, key=lambda n: n.version.branch_name)
            elif self._tree_state.sort_option == TreeSortOption.CREATION_DATE:
                return sorted(nodes, key=lambda n: n.version.created_at, reverse=True)
            else:
                return nodes

        except Exception as e:
            logger.error(f"Error sorting nodes: {e}")
            return nodes

    async def _build_tree_node(self, node: VersionNode, level: int = 0) -> Optional[ft.Control]:
        """Build a tree node control."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            version = node.version

            # Calculate indentation
            indent_size = level * self.get_breakpoint_value(20, 24, 28, 32)

            # Expand/collapse button
            expand_button = ft.IconButton(
                icon=self.get_icon('EXPAND_MORE') if node.is_expanded else self.get_icon('CHEVRON_RIGHT'),
                icon_size=self.get_breakpoint_value(16, 18, 20, 22),
                on_click=lambda _: self._on_node_expanded(node),
                visible=len(node.children) > 0,
                tooltip="Expand/Collapse"
            ) if not self.is_mobile() else ft.Container(width=24)

            # Version icon based on type
            version_icon = self._get_version_icon(version)

            # Version number and branch
            version_text = ft.Text(
                version.version_number,
                size=self.get_breakpoint_value(13, 14, 15, 16),
                weight=ft.FontWeight.W_600,
                color=palette.on_surface if palette else None
            )

            branch_chip = ft.Container(
                content=ft.Text(
                    version.branch_name,
                    size=self.get_breakpoint_value(10, 11, 12, 13),
                    color=palette.on_primary_container if palette else None
                ),
                bgcolor=node.branch_color,
                padding=ft.padding.symmetric(horizontal=spacing.xs if spacing else 6, vertical=spacing.xs if spacing else 2),
                border_radius=self.get_breakpoint_value(8, 10, 12, 14)
            )

            # Status indicators
            status_indicators = self._build_status_indicators(version)

            # Commit message (if detailed view)
            commit_message = None
            if (self._tree_state.view_mode == TreeViewMode.DETAILED and
                version.commit_message and not self.is_mobile()):
                commit_message = ft.Text(
                    version.commit_message[:50] + "..." if len(version.commit_message) > 50 else version.commit_message,
                    size=self.get_breakpoint_value(11, 12, 13, 14),
                    color=palette.on_surface_variant if palette else None,
                    italic=True
                )

            # Creation info
            creation_info = ft.Text(
                f"by {version.created_by or 'Unknown'} • {version.created_at.strftime('%Y-%m-%d %H:%M')}",
                size=self.get_breakpoint_value(10, 11, 12, 13),
                color=palette.on_surface_variant if palette else None
            )

            # Build node content based on view mode
            if self._tree_state.view_mode == TreeViewMode.COMPACT or self.is_mobile():
                node_content = ft.Row([
                    expand_button,
                    version_icon,
                    ft.Column([
                        ft.Row([version_text, branch_chip] + status_indicators, spacing=spacing.sm if spacing else 8),
                        creation_info
                    ], spacing=spacing.xs if spacing else 4, tight=True)
                ], spacing=spacing.sm if spacing else 8)
            else:
                # Detailed view
                content_column = [
                    ft.Row([version_text, branch_chip] + status_indicators, spacing=spacing.sm if spacing else 8)
                ]
                if commit_message:
                    content_column.append(commit_message)
                content_column.append(creation_info)

                node_content = ft.Row([
                    expand_button,
                    version_icon,
                    ft.Column(content_column, spacing=spacing.xs if spacing else 4, tight=True)
                ], spacing=spacing.sm if spacing else 8)

            # Node container
            node_container = ft.Container(
                content=node_content,
                padding=ft.padding.only(
                    left=indent_size + (spacing.component_padding if spacing else 16),
                    right=spacing.component_padding if spacing else 16,
                    top=spacing.sm if spacing else 8,
                    bottom=spacing.sm if spacing else 8
                ),
                bgcolor=palette.primary_container if node.is_selected and palette else (
                    palette.surface_variant if node.is_highlighted and palette else None
                ),
                border_radius=self.get_breakpoint_value(6, 8, 10, 12),
                on_click=lambda _: self._on_node_selected(node),
                ink=True
            )

            # Store rendered node
            self._rendered_nodes[version.version_id] = node_container

            # Build result with children
            result_controls = [node_container]

            # Add children if expanded
            if node.is_expanded and node.children:
                for child_node in node.children:
                    child_control = await self._build_tree_node(child_node, level + 1)
                    if child_control:
                        result_controls.append(child_control)

            return ft.Column(result_controls, spacing=0) if len(result_controls) > 1 else result_controls[0]

        except Exception as e:
            logger.error(f"Error building tree node: {e}")
            return None

    def _get_version_icon(self, version: ModelVersion) -> ft.Control:
        """Get icon for version based on its properties."""
        palette = self.get_palette()

        if version.is_release:
            icon = self.get_icon('STAR')
            color = palette.warning if palette else "#FFA726"
        elif version.is_stable:
            icon = self.get_icon('VERIFIED')
            color = palette.success if palette else "#66BB6A"
        elif version.tags:
            icon = self.get_icon('LABEL')
            color = palette.info if palette else "#42A5F5"
        else:
            icon = self.get_icon('COMMIT')
            color = palette.on_surface_variant if palette else "#9E9E9E"

        return ft.Icon(
            icon,
            size=self.get_breakpoint_value(16, 18, 20, 22),
            color=color
        )

    def _build_status_indicators(self, version: ModelVersion) -> List[ft.Control]:
        """Build status indicator chips for a version."""
        indicators = []
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Latest indicator
        if version.is_latest:
            indicators.append(ft.Container(
                content=ft.Text(
                    "LATEST",
                    size=self.get_breakpoint_value(9, 10, 11, 12),
                    weight=ft.FontWeight.W_600,
                    color=palette.on_primary if palette else None
                ),
                bgcolor=palette.primary if palette else "#6750A4",
                padding=ft.padding.symmetric(horizontal=spacing.xs if spacing else 6, vertical=spacing.xs if spacing else 2),
                border_radius=self.get_breakpoint_value(6, 8, 10, 12)
            ))

        # Stable indicator
        if version.is_stable:
            indicators.append(ft.Container(
                content=ft.Text(
                    "STABLE",
                    size=self.get_breakpoint_value(9, 10, 11, 12),
                    weight=ft.FontWeight.W_600,
                    color=palette.on_success if palette else None
                ),
                bgcolor=palette.success if palette else "#66BB6A",
                padding=ft.padding.symmetric(horizontal=spacing.xs if spacing else 6, vertical=spacing.xs if spacing else 2),
                border_radius=self.get_breakpoint_value(6, 8, 10, 12)
            ))

        # Release indicator
        if version.is_release:
            indicators.append(ft.Container(
                content=ft.Text(
                    "RELEASE",
                    size=self.get_breakpoint_value(9, 10, 11, 12),
                    weight=ft.FontWeight.W_600,
                    color=palette.on_warning if palette else None
                ),
                bgcolor=palette.warning if palette else "#FFA726",
                padding=ft.padding.symmetric(horizontal=spacing.xs if spacing else 6, vertical=spacing.xs if spacing else 2),
                border_radius=self.get_breakpoint_value(6, 8, 10, 12)
            ))

        # Tags indicator
        if version.tags and not self.is_mobile():
            for tag in version.tags[:2]:  # Show max 2 tags
                indicators.append(ft.Container(
                    content=ft.Text(
                        tag,
                        size=self.get_breakpoint_value(9, 10, 11, 12),
                        color=palette.on_surface_variant if palette else None
                    ),
                    bgcolor=palette.surface_variant if palette else "#F5F5F5",
                    padding=ft.padding.symmetric(horizontal=spacing.xs if spacing else 6, vertical=spacing.xs if spacing else 2),
                    border_radius=self.get_breakpoint_value(6, 8, 10, 12),
                    border=ft.border.all(1, palette.outline if palette else "#E0E0E0")
                ))

        return indicators

    async def _update_empty_state(self) -> None:
        """Update empty state visibility."""
        try:
            # This would be implemented to show/hide empty state
            # based on whether there are any versions to display
            pass
        except Exception as e:
            logger.error(f"Error updating empty state: {e}")

    # Event Handlers
    def _on_search_changed(self, e: ft.ControlEvent) -> None:
        """Handle search query changes."""
        try:
            self._tree_state.search_query = e.control.value or ""
            asyncio.create_task(self._refresh_tree_view())
        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _on_view_mode_changed(self, e: ft.ControlEvent) -> None:
        """Handle view mode changes."""
        try:
            self._tree_state.view_mode = TreeViewMode(e.control.value)
            asyncio.create_task(self._refresh_tree_view())
        except Exception as ex:
            logger.error(f"Error handling view mode change: {ex}")

    def _on_filter_changed(self, e: ft.ControlEvent) -> None:
        """Handle filter changes."""
        try:
            self._tree_state.filter_option = TreeFilterOption(e.control.value)
            asyncio.create_task(self._refresh_tree_view())
        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _on_sort_changed(self, e: ft.ControlEvent) -> None:
        """Handle sort changes."""
        try:
            self._tree_state.sort_option = TreeSortOption(e.control.value)
            asyncio.create_task(self._refresh_tree_view())
        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _on_refresh_clicked(self, e: ft.ControlEvent) -> None:
        """Handle refresh button clicks."""
        try:
            asyncio.create_task(self.load_versions(force_refresh=True))
        except Exception as ex:
            logger.error(f"Error handling refresh click: {ex}")

    def _on_settings_clicked(self, e: ft.ControlEvent) -> None:
        """Handle settings button clicks."""
        try:
            # This would open a settings dialog
            logger.debug("Settings clicked - not implemented yet")
        except Exception as ex:
            logger.error(f"Error handling settings click: {ex}")

    def _on_node_expanded(self, node: VersionNode) -> None:
        """Handle node expand/collapse."""
        try:
            node.is_expanded = not node.is_expanded

            # Update expanded nodes set
            if node.is_expanded:
                self._tree_state.expanded_nodes.add(node.version.version_id)
            else:
                self._tree_state.expanded_nodes.discard(node.version.version_id)

            asyncio.create_task(self._refresh_tree_view())
        except Exception as ex:
            logger.error(f"Error handling node expansion: {ex}")

    def _on_node_selected(self, node: VersionNode) -> None:
        """Handle node selection."""
        try:
            # Clear previous selection
            for cached_node in self._tree_nodes_cache.values():
                cached_node.is_selected = False

            # Set new selection
            node.is_selected = True
            self._tree_state.selected_version = node.version.version_id

            # Trigger callback
            if self._on_version_selected:
                self._on_version_selected(node.version.version_id)

            asyncio.create_task(self._refresh_tree_view())
        except Exception as ex:
            logger.error(f"Error handling node selection: {ex}")

    # Auto-refresh functionality
    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.cancel()

        self._refresh_timer = asyncio.create_task(self._auto_refresh_loop())

    async def _auto_refresh_loop(self) -> None:
        """Auto-refresh loop."""
        try:
            while True:
                await asyncio.sleep(self._config.refresh_interval)
                if not self._is_loading:
                    await self.load_versions()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in auto-refresh loop: {e}")

    def stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None

    # Public API methods
    def set_version_selected_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for version selection events."""
        self._on_version_selected = callback

    def set_version_compared_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for version comparison events."""
        self._on_version_compared = callback

    def set_branch_created_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for branch creation events."""
        self._on_branch_created = callback

    def set_version_tagged_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for version tagging events."""
        self._on_version_tagged = callback

    def get_selected_version(self) -> Optional[str]:
        """Get currently selected version ID."""
        return self._tree_state.selected_version

    def select_version(self, version_id: str) -> None:
        """Programmatically select a version."""
        try:
            if version_id in self._tree_nodes_cache:
                node = self._tree_nodes_cache[version_id]
                self._on_node_selected(node)
        except Exception as e:
            logger.error(f"Error selecting version {version_id}: {e}")

    def expand_version(self, version_id: str) -> None:
        """Expand a specific version node."""
        try:
            if version_id in self._tree_nodes_cache:
                node = self._tree_nodes_cache[version_id]
                if not node.is_expanded:
                    self._on_node_expanded(node)
        except Exception as e:
            logger.error(f"Error expanding version {version_id}: {e}")

    def collapse_version(self, version_id: str) -> None:
        """Collapse a specific version node."""
        try:
            if version_id in self._tree_nodes_cache:
                node = self._tree_nodes_cache[version_id]
                if node.is_expanded:
                    self._on_node_expanded(node)
        except Exception as e:
            logger.error(f"Error collapsing version {version_id}: {e}")

    def highlight_version_path(self, version_id: str) -> None:
        """Highlight the path to a specific version."""
        try:
            if version_id not in self._tree_nodes_cache:
                return

            # Clear previous highlights
            for node in self._tree_nodes_cache.values():
                node.is_highlighted = False

            # Highlight path to version
            current_node = self._tree_nodes_cache[version_id]
            path = []

            while current_node:
                current_node.is_highlighted = True
                path.append(current_node.version.version_id)
                current_node = current_node.parent

            self._tree_state.highlighted_path = path
            asyncio.create_task(self._refresh_tree_view())

        except Exception as e:
            logger.error(f"Error highlighting version path {version_id}: {e}")

    def clear_highlights(self) -> None:
        """Clear all version highlights."""
        try:
            for node in self._tree_nodes_cache.values():
                node.is_highlighted = False

            self._tree_state.highlighted_path.clear()
            asyncio.create_task(self._refresh_tree_view())

        except Exception as e:
            logger.error(f"Error clearing highlights: {e}")

    def get_version_info(self, version_id: str) -> Optional[ModelVersion]:
        """Get version information by ID."""
        return self._versions_cache.get(version_id)

    def get_all_versions(self) -> List[ModelVersion]:
        """Get all loaded versions."""
        return list(self._versions_cache.values())

    def get_branch_versions(self, branch_name: str) -> List[ModelVersion]:
        """Get all versions for a specific branch."""
        return [v for v in self._versions_cache.values() if v.branch_name == branch_name]

    def get_stable_versions(self) -> List[ModelVersion]:
        """Get all stable versions."""
        return [v for v in self._versions_cache.values() if v.is_stable]

    def get_release_versions(self) -> List[ModelVersion]:
        """Get all release versions."""
        return [v for v in self._versions_cache.values() if v.is_release]

    # Theme Integration
    def on_theme_changed(self) -> None:
        """Handle theme change events."""
        try:
            super().on_theme_changed()

            # Recalculate branch colors with new theme
            branch_colors = self._get_branch_colors()
            for node in self._tree_nodes_cache.values():
                branch_name = node.version.branch_name
                node.branch_color = branch_colors.get(branch_name, "#6750A4")

            # Refresh UI with new theme
            asyncio.create_task(self._refresh_tree_view())

        except Exception as e:
            logger.error(f"Failed to handle theme change: {e}")

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self.stop_auto_refresh()
            self._versions_cache.clear()
            self._tree_nodes_cache.clear()
            self._rendered_nodes.clear()

        except Exception as e:
            logger.error(f"Failed to cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except:
            pass
