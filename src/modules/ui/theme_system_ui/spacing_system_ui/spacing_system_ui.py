"""
Module: spacing_system_ui
Description: Comprehensive spacing system management and preview UI component for MikroDok application.
            Provides interactive spacing scale demonstrations, responsive spacing controls, layout grid
            examples, semantic spacing management, and real-time spacing preview capabilities.
            Integrates fully with theme_system_ui.py for consistent styling and responsive design.
Phase: 1
Location: /src/modules/ui/theme_system_ui/spacing_system_ui/spacing_system_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    SpacingSystem,
    calculate_responsive_spacing,
    get_responsive_value
)


class SpacingCategory(Enum):
    """Spacing category enumeration for organization."""
    BASE = "base"
    COMPONENT = "component"
    SEMANTIC = "semantic"
    RESPONSIVE = "responsive"


@dataclass
class SpacingDemonstration:
    """Data class for spacing demonstration items."""
    name: str
    value: int
    category: SpacingCategory
    description: str
    use_case: str


class SpacingSystemUI(ThemeAwareUserControl):
    """
    Comprehensive spacing system management and preview UI component.
    
    Features:
    - Interactive spacing scale demonstrations with visual examples
    - Responsive spacing controls and breakpoint management
    - Layout grid examples and component spacing samples
    - Semantic spacing management with contextual previews
    - Real-time spacing adjustments and live preview capabilities
    - Full integration with ResponsiveLayoutManager and theme system
    - Accessibility-compliant spacing demonstrations
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._spacing_system: Optional[SpacingSystem] = None
        self._current_category = SpacingCategory.BASE
        self._spacing_demonstrations: List[SpacingDemonstration] = []
        self._preview_controls: Dict[str, ft.Control] = {}
        self._is_live_preview = True
        self._custom_spacing_values: Dict[str, int] = {}
        
        # Initialize spacing demonstrations
        self._initialize_spacing_demonstrations()
        
        # Set responsive properties
        self.expand = True
        
    def _initialize_spacing_demonstrations(self):
        """Initialize spacing demonstration data."""
        self._spacing_demonstrations = [
            # Base spacing scale
            SpacingDemonstration(
                "Extra Small (xs)", 4, SpacingCategory.BASE,
                "Minimal spacing for tight layouts", "Icon margins, small gaps"
            ),
            SpacingDemonstration(
                "Small (sm)", 8, SpacingCategory.BASE,
                "Compact spacing for dense interfaces", "Button padding, form field gaps"
            ),
            SpacingDemonstration(
                "Medium (md)", 12, SpacingCategory.BASE,
                "Standard spacing for most components", "Card padding, list item spacing"
            ),
            SpacingDemonstration(
                "Large (lg)", 16, SpacingCategory.BASE,
                "Comfortable spacing for readability", "Section padding, content margins"
            ),
            SpacingDemonstration(
                "Extra Large (xl)", 24, SpacingCategory.BASE,
                "Generous spacing for emphasis", "Page sections, major components"
            ),
            SpacingDemonstration(
                "2X Large (xxl)", 32, SpacingCategory.BASE,
                "Wide spacing for visual separation", "Page margins, hero sections"
            ),
            SpacingDemonstration(
                "3X Large (xxxl)", 48, SpacingCategory.BASE,
                "Maximum spacing for dramatic effect", "Landing page sections"
            ),
            SpacingDemonstration(
                "4X Large (xxxxl)", 64, SpacingCategory.BASE,
                "Ultra-wide spacing for special layouts", "Full-page separators"
            ),
            
            # Component-specific spacing
            SpacingDemonstration(
                "Component Padding", 16, SpacingCategory.COMPONENT,
                "Standard padding for UI components", "Cards, panels, containers"
            ),
            SpacingDemonstration(
                "Section Padding", 24, SpacingCategory.COMPONENT,
                "Padding for major page sections", "Main content areas"
            ),
            SpacingDemonstration(
                "Icon-Text Gap", 8, SpacingCategory.COMPONENT,
                "Space between icons and text", "Buttons, menu items"
            ),
            SpacingDemonstration(
                "Button Horizontal", 16, SpacingCategory.COMPONENT,
                "Horizontal padding for buttons", "Action buttons, form controls"
            ),
            SpacingDemonstration(
                "Button Vertical", 8, SpacingCategory.COMPONENT,
                "Vertical padding for buttons", "Action buttons, form controls"
            ),
            
            # Semantic spacing
            SpacingDemonstration(
                "Tight Spacing", 8, SpacingCategory.SEMANTIC,
                "Minimal spacing for related content", "Form groups, related items"
            ),
            SpacingDemonstration(
                "Loose Spacing", 24, SpacingCategory.SEMANTIC,
                "Generous spacing for separation", "Unrelated content sections"
            ),
        ]

    def build(self) -> ft.Control:
        """Build the spacing system UI."""
        # Get current spacing system
        self._spacing_system = self.get_spacing()
        
        # Create main layout
        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    self._build_header(),
                    self._build_category_tabs(),
                    self._build_content_area(),
                ],
                spacing=0,
                expand=True
            ),
            padding=self.get_responsive_padding()
        )

    def _build_header(self) -> ft.Control:
        """Build the header section."""
        theme = self.get_theme()
        typography = self.get_typography()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Spacing System",
                        size=typography.heading_large[0],
                        weight=ft.FontWeight.W_600,
                        color=theme.get_color("text-primary")
                    ),
                    ft.Text(
                        "Consistent spacing scale and layout grid definitions for responsive design",
                        size=typography.body_large[0],
                        color=theme.get_color("text-secondary")
                    ),
                ],
                spacing=self._spacing_system.sm if self._spacing_system else 8
            ),
            padding=ft.padding.only(bottom=self._spacing_system.lg if self._spacing_system else 16)
        )

    def _build_category_tabs(self) -> ft.Control:
        """Build category selection tabs."""
        theme = self.get_theme()
        
        tabs = []
        for category in SpacingCategory:
            tabs.append(
                ft.Tab(
                    text=category.value.title(),
                    content=ft.Container()  # Content will be built separately
                )
            )
        
        return ft.Tabs(
            selected_index=list(SpacingCategory).index(self._current_category),
            on_change=self._on_category_change,
            tabs=tabs,
            expand=True
        )

    def _build_content_area(self) -> ft.Control:
        """Build the main content area based on selected category."""
        if self._current_category == SpacingCategory.BASE:
            return self._build_base_spacing_content()
        elif self._current_category == SpacingCategory.COMPONENT:
            return self._build_component_spacing_content()
        elif self._current_category == SpacingCategory.SEMANTIC:
            return self._build_semantic_spacing_content()
        elif self._current_category == SpacingCategory.RESPONSIVE:
            return self._build_responsive_spacing_content()
        else:
            return ft.Container()

    def _on_category_change(self, e):
        """Handle category tab change."""
        if e.control.selected_index is not None:
            categories = list(SpacingCategory)
            if 0 <= e.control.selected_index < len(categories):
                self._current_category = categories[e.control.selected_index]
                self.update()

    def _build_base_spacing_content(self) -> ft.Control:
        """Build base spacing scale content."""
        base_demonstrations = [
            demo for demo in self._spacing_demonstrations 
            if demo.category == SpacingCategory.BASE
        ]
        
        return self._build_spacing_grid(base_demonstrations)

    def _build_component_spacing_content(self) -> ft.Control:
        """Build component spacing content."""
        component_demonstrations = [
            demo for demo in self._spacing_demonstrations 
            if demo.category == SpacingCategory.COMPONENT
        ]
        
        return self._build_spacing_grid(component_demonstrations)

    def _build_semantic_spacing_content(self) -> ft.Control:
        """Build semantic spacing content."""
        semantic_demonstrations = [
            demo for demo in self._spacing_demonstrations 
            if demo.category == SpacingCategory.SEMANTIC
        ]
        
        return self._build_spacing_grid(semantic_demonstrations)

    def _build_responsive_spacing_content(self) -> ft.Control:
        """Build responsive spacing content."""
        return self._build_responsive_demonstrations()

    def _build_spacing_grid(self, demonstrations: List[SpacingDemonstration]) -> ft.Control:
        """Build a grid of spacing demonstrations."""
        spacing_cards = []
        
        for demo in demonstrations:
            spacing_cards.append(self._build_spacing_card(demo))
        
        return self.create_responsive_grid(
            children=spacing_cards,
            mobile_cols=1,
            tablet_cols=2,
            desktop_cols=3,
            large_cols=4,
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def _build_spacing_card(self, demo: SpacingDemonstration) -> ft.Control:
        """Build a spacing demonstration card."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Create visual spacing demonstration
        spacing_visual = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        bgcolor=theme.get_color("primary"),
                        width=20,
                        height=20,
                        border_radius=4
                    ),
                    ft.Container(width=demo.value),  # The actual spacing
                    ft.Container(
                        bgcolor=theme.get_color("primary"),
                        width=20,
                        height=20,
                        border_radius=4
                    ),
                ],
                alignment=ft.MainAxisAlignment.START
            ),
            height=40,
            padding=ft.padding.all(self._spacing_system.sm if self._spacing_system else 8)
        )

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            demo.name,
                            size=typography.body_medium[0],
                            weight=ft.FontWeight.W_600,
                            color=theme.get_color("text-primary")
                        ),
                        ft.Text(
                            f"{demo.value}px",
                            size=typography.body_small[0],
                            color=theme.get_color("text-secondary")
                        ),
                        spacing_visual,
                        ft.Text(
                            demo.description,
                            size=typography.caption[0],
                            color=theme.get_color("text-secondary")
                        ),
                        ft.Text(
                            f"Use case: {demo.use_case}",
                            size=typography.caption[0],
                            color=theme.get_color("text-muted"),
                            italic=True
                        ),
                    ],
                    spacing=self._spacing_system.xs if self._spacing_system else 4,
                    tight=True
                ),
                padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12)
            ),
            elevation=2
        )

    def _build_responsive_demonstrations(self) -> ft.Control:
        """Build responsive spacing demonstrations."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Get responsive spacing values
        base_spacing = 16
        mobile_spacing = calculate_responsive_spacing(base_spacing, 0.75, 0.875, 1.0, 1.25)
        tablet_spacing = calculate_responsive_spacing(base_spacing, 0.75, 0.875, 1.0, 1.25)
        desktop_spacing = calculate_responsive_spacing(base_spacing, 0.75, 0.875, 1.0, 1.25)
        large_spacing = calculate_responsive_spacing(base_spacing, 0.75, 0.875, 1.0, 1.25)

        # Current responsive values
        current_padding = self.get_responsive_padding()
        current_columns = self.get_responsive_columns()
        current_screen = self.get_current_screen_size()

        return ft.Column(
            controls=[
                ft.Text(
                    "Responsive Spacing Demonstrations",
                    size=typography.heading_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=theme.get_color("text-primary")
                ),

                # Current breakpoint info
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    f"Current Screen: {current_screen.title()}",
                                    size=typography.body_large[0],
                                    weight=ft.FontWeight.W_500,
                                    color=theme.get_color("text-primary")
                                ),
                                ft.Text(
                                    f"Responsive Padding: {current_padding}px",
                                    size=typography.body_medium[0],
                                    color=theme.get_color("text-secondary")
                                ),
                                ft.Text(
                                    f"Grid Columns: {current_columns}",
                                    size=typography.body_medium[0],
                                    color=theme.get_color("text-secondary")
                                ),
                            ],
                            spacing=self._spacing_system.xs if self._spacing_system else 4
                        ),
                        padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12)
                    ),
                    elevation=1
                ),

                # Responsive spacing examples
                self._build_responsive_spacing_examples(),

                # Breakpoint demonstrations
                self._build_breakpoint_demonstrations(),
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def _build_responsive_spacing_examples(self) -> ft.Control:
        """Build responsive spacing examples."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Create containers with different responsive spacing
        examples = []
        spacing_values = [8, 12, 16, 24, 32]

        for i, base_value in enumerate(spacing_values):
            responsive_value = calculate_responsive_spacing(base_value)

            example_container = ft.Container(
                content=ft.Text(
                    f"Base: {base_value}px → Responsive: {responsive_value}px",
                    size=typography.body_small[0],
                    color=theme.get_color("text-primary"),
                    text_align=ft.TextAlign.CENTER
                ),
                bgcolor=theme.get_color("surface-variant"),
                padding=ft.padding.all(responsive_value),
                border_radius=8,
                border=ft.border.all(1, theme.get_color("outline"))
            )

            examples.append(example_container)

        return ft.Column(
            controls=[
                ft.Text(
                    "Responsive Spacing Examples",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "These containers show how spacing adapts to different screen sizes",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),
                *examples
            ],
            spacing=self._spacing_system.sm if self._spacing_system else 8
        )

    def _build_breakpoint_demonstrations(self) -> ft.Control:
        """Build breakpoint-specific spacing demonstrations."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Breakpoint information
        breakpoints = [
            ("Mobile", "0-575px", "Compact spacing for touch interfaces"),
            ("Tablet", "576-991px", "Balanced spacing for medium screens"),
            ("Desktop", "992-1599px", "Comfortable spacing for large screens"),
            ("Large Desktop", "1600px+", "Generous spacing for ultra-wide displays")
        ]

        breakpoint_cards = []
        for name, range_text, description in breakpoints:
            # Get breakpoint-specific values
            if name == "Mobile":
                padding = self.get_breakpoint_value(12, 16, 24, 32)
                columns = self.get_breakpoint_value(1, 2, 3, 4)
            elif name == "Tablet":
                padding = self.get_breakpoint_value(12, 16, 24, 32)
                columns = self.get_breakpoint_value(1, 2, 3, 4)
            elif name == "Desktop":
                padding = self.get_breakpoint_value(12, 16, 24, 32)
                columns = self.get_breakpoint_value(1, 2, 3, 4)
            else:  # Large Desktop
                padding = self.get_breakpoint_value(12, 16, 24, 32)
                columns = self.get_breakpoint_value(1, 2, 3, 4)

            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                name,
                                size=typography.body_large[0],
                                weight=ft.FontWeight.W_600,
                                color=theme.get_color("text-primary")
                            ),
                            ft.Text(
                                range_text,
                                size=typography.body_small[0],
                                color=theme.get_color("text-secondary")
                            ),
                            ft.Text(
                                description,
                                size=typography.caption[0],
                                color=theme.get_color("text-muted")
                            ),
                            ft.Divider(height=1, color=theme.get_color("outline")),
                            ft.Text(
                                f"Padding: {padding}px",
                                size=typography.body_small[0],
                                color=theme.get_color("text-secondary")
                            ),
                            ft.Text(
                                f"Grid Columns: {columns}",
                                size=typography.body_small[0],
                                color=theme.get_color("text-secondary")
                            ),
                        ],
                        spacing=self._spacing_system.xs if self._spacing_system else 4
                    ),
                    padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12)
                ),
                elevation=1
            )
            breakpoint_cards.append(card)

        return ft.Column(
            controls=[
                ft.Text(
                    "Breakpoint Spacing",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Spacing values automatically adjust based on screen size breakpoints",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),
                self.create_responsive_grid(
                    children=breakpoint_cards,
                    mobile_cols=1,
                    tablet_cols=2,
                    desktop_cols=2,
                    large_cols=4,
                    spacing=self._spacing_system.md if self._spacing_system else 12
                )
            ],
            spacing=self._spacing_system.sm if self._spacing_system else 8
        )

    def _build_layout_grid_examples(self) -> ft.Control:
        """Build layout grid examples with different spacing."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Create grid items
        grid_items = []
        for i in range(12):
            grid_items.append(
                ft.Container(
                    content=ft.Text(
                        f"{i+1}",
                        size=typography.body_small[0],
                        color=theme.get_color("on-primary"),
                        text_align=ft.TextAlign.CENTER
                    ),
                    bgcolor=theme.get_color("primary"),
                    height=60,
                    border_radius=4,
                    alignment=ft.alignment.center
                )
            )

        return ft.Column(
            controls=[
                ft.Text(
                    "Layout Grid Examples",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Responsive grid layouts with consistent spacing",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),

                # Tight spacing grid
                ft.Text(
                    "Tight Spacing (8px)",
                    size=typography.body_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                self.create_responsive_grid(
                    children=grid_items[:6],
                    mobile_cols=2,
                    tablet_cols=3,
                    desktop_cols=6,
                    large_cols=6,
                    spacing=8
                ),

                # Normal spacing grid
                ft.Text(
                    "Normal Spacing (16px)",
                    size=typography.body_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                self.create_responsive_grid(
                    children=grid_items[6:],
                    mobile_cols=2,
                    tablet_cols=3,
                    desktop_cols=6,
                    large_cols=6,
                    spacing=16
                ),
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def get_spacing_value(self, spacing_name: str) -> int:
        """Get spacing value by name."""
        if not self._spacing_system:
            return 16  # Default fallback

        spacing_map = {
            "xs": self._spacing_system.xs,
            "sm": self._spacing_system.sm,
            "md": self._spacing_system.md,
            "lg": self._spacing_system.lg,
            "xl": self._spacing_system.xl,
            "xxl": self._spacing_system.xxl,
            "xxxl": self._spacing_system.xxxl,
            "xxxxl": self._spacing_system.xxxxl,
            "component": self._spacing_system.component_padding,
            "section": self._spacing_system.section_padding,
            "icon_text": self._spacing_system.icon_text_gap,
            "button_h": self._spacing_system.button_padding_horizontal,
            "button_v": self._spacing_system.button_padding_vertical,
        }

        return spacing_map.get(spacing_name, self._spacing_system.md)

    def update_spacing_value(self, spacing_name: str, value: int):
        """Update a custom spacing value."""
        self._custom_spacing_values[spacing_name] = value
        if self._is_live_preview:
            self.update()

    def toggle_live_preview(self):
        """Toggle live preview mode."""
        self._is_live_preview = not self._is_live_preview

    def reset_spacing_values(self):
        """Reset all custom spacing values to defaults."""
        self._custom_spacing_values.clear()
        self.update()

    def export_spacing_config(self) -> Dict[str, Any]:
        """Export current spacing configuration."""
        config = {
            "base_spacing": {
                "xs": self._spacing_system.xs if self._spacing_system else 4,
                "sm": self._spacing_system.sm if self._spacing_system else 8,
                "md": self._spacing_system.md if self._spacing_system else 12,
                "lg": self._spacing_system.lg if self._spacing_system else 16,
                "xl": self._spacing_system.xl if self._spacing_system else 24,
                "xxl": self._spacing_system.xxl if self._spacing_system else 32,
                "xxxl": self._spacing_system.xxxl if self._spacing_system else 48,
                "xxxxl": self._spacing_system.xxxxl if self._spacing_system else 64,
            },
            "component_spacing": {
                "component_padding": self._spacing_system.component_padding if self._spacing_system else 16,
                "section_padding": self._spacing_system.section_padding if self._spacing_system else 24,
                "icon_text_gap": self._spacing_system.icon_text_gap if self._spacing_system else 8,
                "button_padding_horizontal": self._spacing_system.button_padding_horizontal if self._spacing_system else 16,
                "button_padding_vertical": self._spacing_system.button_padding_vertical if self._spacing_system else 8,
            },
            "custom_values": self._custom_spacing_values.copy(),
            "responsive_settings": {
                "current_screen": self.get_current_screen_size(),
                "current_padding": self.get_responsive_padding(),
                "current_columns": self.get_responsive_columns(),
            }
        }
        return config

    def _build_interactive_spacing_preview(self) -> ft.Control:
        """Build interactive spacing preview with live adjustments."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Create preview containers
        preview_items = []
        for i in range(3):
            preview_items.append(
                ft.Container(
                    content=ft.Text(
                        f"Item {i+1}",
                        size=typography.body_medium[0],
                        color=theme.get_color("on-surface-variant"),
                        text_align=ft.TextAlign.CENTER
                    ),
                    bgcolor=theme.get_color("surface-variant"),
                    height=80,
                    border_radius=8,
                    alignment=ft.alignment.center,
                    border=ft.border.all(1, theme.get_color("outline"))
                )
            )

        # Spacing controls
        spacing_slider = ft.Slider(
            min=0,
            max=64,
            value=16,
            divisions=16,
            label="Spacing: {value}px",
            on_change=self._on_preview_spacing_change
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Interactive Spacing Preview",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Adjust the slider to see how spacing affects layout",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),
                spacing_slider,
                ft.Container(
                    content=ft.Column(
                        controls=preview_items,
                        spacing=16,  # This will be updated by the slider
                        tight=True
                    ),
                    padding=ft.padding.all(self._spacing_system.lg if self._spacing_system else 16),
                    bgcolor=theme.get_color("surface"),
                    border_radius=8,
                    border=ft.border.all(1, theme.get_color("outline"))
                )
            ],
            spacing=self._spacing_system.md if self._spacing_system else 12
        )

    def _on_preview_spacing_change(self, e):
        """Handle spacing preview slider change."""
        if e.control.value is not None:
            # Update the preview spacing
            # This would need to be implemented with proper state management
            pass

    def _build_component_spacing_samples(self) -> ft.Control:
        """Build component spacing samples with different configurations."""
        theme = self.get_theme()
        typography = self.get_typography()
        icons = self.get_icons()

        # Button samples with different spacing
        button_samples = ft.Column(
            controls=[
                ft.Text(
                    "Button Spacing Samples",
                    size=typography.body_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            text="Tight",
                            icon=icons.SETTINGS,
                            style=ft.ButtonStyle(
                                padding=ft.padding.symmetric(horizontal=8, vertical=4)
                            )
                        ),
                        ft.ElevatedButton(
                            text="Normal",
                            icon=icons.SETTINGS,
                            style=ft.ButtonStyle(
                                padding=ft.padding.symmetric(horizontal=16, vertical=8)
                            )
                        ),
                        ft.ElevatedButton(
                            text="Loose",
                            icon=icons.SETTINGS,
                            style=ft.ButtonStyle(
                                padding=ft.padding.symmetric(horizontal=24, vertical=12)
                            )
                        ),
                    ],
                    spacing=self._spacing_system.md if self._spacing_system else 12
                )
            ],
            spacing=self._spacing_system.sm if self._spacing_system else 8
        )

        # Card samples with different padding
        card_samples = ft.Column(
            controls=[
                ft.Text(
                    "Card Padding Samples",
                    size=typography.body_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Row(
                    controls=[
                        ft.Card(
                            content=ft.Container(
                                content=ft.Text(
                                    "Compact\n8px padding",
                                    size=typography.body_small[0],
                                    color=theme.get_color("text-primary"),
                                    text_align=ft.TextAlign.CENTER
                                ),
                                padding=ft.padding.all(8),
                                width=120,
                                height=80
                            ),
                            elevation=2
                        ),
                        ft.Card(
                            content=ft.Container(
                                content=ft.Text(
                                    "Standard\n16px padding",
                                    size=typography.body_small[0],
                                    color=theme.get_color("text-primary"),
                                    text_align=ft.TextAlign.CENTER
                                ),
                                padding=ft.padding.all(16),
                                width=120,
                                height=80
                            ),
                            elevation=2
                        ),
                        ft.Card(
                            content=ft.Container(
                                content=ft.Text(
                                    "Spacious\n24px padding",
                                    size=typography.body_small[0],
                                    color=theme.get_color("text-primary"),
                                    text_align=ft.TextAlign.CENTER
                                ),
                                padding=ft.padding.all(24),
                                width=120,
                                height=80
                            ),
                            elevation=2
                        ),
                    ],
                    spacing=self._spacing_system.md if self._spacing_system else 12,
                    wrap=True
                )
            ],
            spacing=self._spacing_system.sm if self._spacing_system else 8
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Component Spacing Samples",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Examples of how spacing affects different UI components",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),
                button_samples,
                ft.Divider(height=1, color=theme.get_color("outline")),
                card_samples,
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def _build_spacing_comparison_tool(self) -> ft.Control:
        """Build spacing comparison tool for side-by-side comparisons."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Create comparison containers
        comparison_content = ft.Row(
            controls=[
                # Left side - Original spacing
                ft.Expanded(
                    child=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Original Spacing",
                                    size=typography.body_medium[0],
                                    weight=ft.FontWeight.W_500,
                                    color=theme.get_color("text-primary")
                                ),
                                self._build_sample_layout(16),  # Standard spacing
                            ],
                            spacing=self._spacing_system.sm if self._spacing_system else 8
                        ),
                        padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12),
                        bgcolor=theme.get_color("surface"),
                        border_radius=8,
                        border=ft.border.all(1, theme.get_color("outline"))
                    )
                ),

                # Right side - Modified spacing
                ft.Expanded(
                    child=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Modified Spacing",
                                    size=typography.body_medium[0],
                                    weight=ft.FontWeight.W_500,
                                    color=theme.get_color("text-primary")
                                ),
                                self._build_sample_layout(24),  # Larger spacing
                            ],
                            spacing=self._spacing_system.sm if self._spacing_system else 8
                        ),
                        padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12),
                        bgcolor=theme.get_color("surface-variant"),
                        border_radius=8,
                        border=ft.border.all(1, theme.get_color("outline"))
                    )
                ),
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Spacing Comparison Tool",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Compare different spacing values side by side",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),
                comparison_content,
            ],
            spacing=self._spacing_system.md if self._spacing_system else 12
        )

    def _build_sample_layout(self, spacing_value: int) -> ft.Control:
        """Build a sample layout with specified spacing."""
        theme = self.get_theme()
        typography = self.get_typography()

        sample_items = []
        for i in range(4):
            sample_items.append(
                ft.Container(
                    content=ft.Text(
                        f"Item {i+1}",
                        size=typography.caption[0],
                        color=theme.get_color("on-primary"),
                        text_align=ft.TextAlign.CENTER
                    ),
                    bgcolor=theme.get_color("primary"),
                    height=40,
                    border_radius=4,
                    alignment=ft.alignment.center
                )
            )

        return ft.Column(
            controls=sample_items,
            spacing=spacing_value,
            tight=True
        )

    def _build_spacing_configuration_panel(self) -> ft.Control:
        """Build spacing configuration and customization panel."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Base spacing controls
        base_spacing_controls = self._build_base_spacing_controls()

        # Component spacing controls
        component_spacing_controls = self._build_component_spacing_controls()

        # Responsive controls
        responsive_controls = self._build_responsive_controls()

        # Live preview toggle
        live_preview_toggle = ft.Switch(
            label="Live Preview",
            value=self._is_live_preview,
            on_change=self._on_live_preview_toggle
        )

        # Reset button
        reset_button = ft.ElevatedButton(
            text="Reset to Defaults",
            icon=ft.Icons.REFRESH,
            on_click=self._on_reset_spacing,
            style=ft.ButtonStyle(
                color=theme.get_color("on-surface"),
                bgcolor=theme.get_color("surface-variant")
            )
        )

        # Export button
        export_button = ft.ElevatedButton(
            text="Export Config",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_export_config,
            style=ft.ButtonStyle(
                color=theme.get_color("on-primary"),
                bgcolor=theme.get_color("primary")
            )
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Spacing Configuration",
                    size=typography.heading_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Customize spacing values and see changes in real-time",
                    size=typography.body_medium[0],
                    color=theme.get_color("text-secondary")
                ),

                # Controls section
                ft.Row(
                    controls=[live_preview_toggle, reset_button, export_button],
                    spacing=self._spacing_system.md if self._spacing_system else 12
                ),

                ft.Divider(height=1, color=theme.get_color("outline")),

                # Configuration tabs
                ft.Tabs(
                    selected_index=0,
                    tabs=[
                        ft.Tab(text="Base Spacing", content=base_spacing_controls),
                        ft.Tab(text="Component Spacing", content=component_spacing_controls),
                        ft.Tab(text="Responsive Settings", content=responsive_controls),
                    ],
                    expand=True
                ),
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16,
            expand=True
        )

    def _build_base_spacing_controls(self) -> ft.Control:
        """Build base spacing value controls."""
        theme = self.get_theme()
        typography = self.get_typography()

        spacing_controls = []
        base_spacings = [
            ("xs", "Extra Small", 4, 0, 16),
            ("sm", "Small", 8, 0, 24),
            ("md", "Medium", 12, 0, 32),
            ("lg", "Large", 16, 0, 48),
            ("xl", "Extra Large", 24, 0, 64),
            ("xxl", "2X Large", 32, 0, 96),
            ("xxxl", "3X Large", 48, 0, 128),
            ("xxxxl", "4X Large", 64, 0, 160),
        ]

        for key, label, default_value, min_val, max_val in base_spacings:
            current_value = self._custom_spacing_values.get(key, default_value)

            control_row = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            label,
                            size=typography.body_medium[0],
                            color=theme.get_color("text-primary")
                        ),
                        width=120
                    ),
                    ft.Expanded(
                        child=ft.Slider(
                            min=min_val,
                            max=max_val,
                            value=current_value,
                            divisions=max_val // 4,
                            label=f"{current_value}px",
                            on_change=lambda e, k=key: self._on_spacing_value_change(k, e.control.value)
                        )
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{current_value}px",
                            size=typography.body_small[0],
                            color=theme.get_color("text-secondary")
                        ),
                        width=60
                    ),
                ],
                spacing=self._spacing_system.sm if self._spacing_system else 8
            )
            spacing_controls.append(control_row)

        return ft.Column(
            controls=spacing_controls,
            spacing=self._spacing_system.md if self._spacing_system else 12,
            scroll=ft.ScrollMode.AUTO
        )

    def _build_component_spacing_controls(self) -> ft.Control:
        """Build component-specific spacing controls."""
        theme = self.get_theme()
        typography = self.get_typography()

        component_controls = []
        component_spacings = [
            ("component_padding", "Component Padding", 16, 4, 48),
            ("section_padding", "Section Padding", 24, 8, 64),
            ("icon_text_gap", "Icon-Text Gap", 8, 2, 24),
            ("button_padding_h", "Button Horizontal", 16, 4, 32),
            ("button_padding_v", "Button Vertical", 8, 2, 20),
        ]

        for key, label, default_value, min_val, max_val in component_spacings:
            current_value = self._custom_spacing_values.get(key, default_value)

            control_row = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            label,
                            size=typography.body_medium[0],
                            color=theme.get_color("text-primary")
                        ),
                        width=150
                    ),
                    ft.Expanded(
                        child=ft.Slider(
                            min=min_val,
                            max=max_val,
                            value=current_value,
                            divisions=(max_val - min_val) // 2,
                            label=f"{current_value}px",
                            on_change=lambda e, k=key: self._on_spacing_value_change(k, e.control.value)
                        )
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{current_value}px",
                            size=typography.body_small[0],
                            color=theme.get_color("text-secondary")
                        ),
                        width=60
                    ),
                ],
                spacing=self._spacing_system.sm if self._spacing_system else 8
            )
            component_controls.append(control_row)

        return ft.Column(
            controls=component_controls,
            spacing=self._spacing_system.md if self._spacing_system else 12,
            scroll=ft.ScrollMode.AUTO
        )

    def _build_responsive_controls(self) -> ft.Control:
        """Build responsive spacing controls."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Current responsive information
        current_info = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Current Responsive State",
                            size=typography.body_large[0],
                            weight=ft.FontWeight.W_500,
                            color=theme.get_color("text-primary")
                        ),
                        ft.Text(
                            f"Screen Size: {self.get_current_screen_size().title()}",
                            size=typography.body_medium[0],
                            color=theme.get_color("text-secondary")
                        ),
                        ft.Text(
                            f"Window Dimensions: {self.get_current_dimensions()}",
                            size=typography.body_medium[0],
                            color=theme.get_color("text-secondary")
                        ),
                        ft.Text(
                            f"Responsive Padding: {self.get_responsive_padding()}px",
                            size=typography.body_medium[0],
                            color=theme.get_color("text-secondary")
                        ),
                        ft.Text(
                            f"Grid Columns: {self.get_responsive_columns()}",
                            size=typography.body_medium[0],
                            color=theme.get_color("text-secondary")
                        ),
                    ],
                    spacing=self._spacing_system.xs if self._spacing_system else 4
                ),
                padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12)
            ),
            elevation=1
        )

        # Responsive factor controls
        factor_controls = ft.Column(
            controls=[
                ft.Text(
                    "Responsive Scaling Factors",
                    size=typography.body_large[0],
                    weight=ft.FontWeight.W_500,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Adjust how spacing scales across different screen sizes",
                    size=typography.body_small[0],
                    color=theme.get_color("text-secondary")
                ),

                # Mobile factor
                ft.Row(
                    controls=[
                        ft.Text("Mobile Factor:", size=typography.body_medium[0]),
                        ft.Slider(min=0.5, max=1.5, value=0.75, divisions=20, label="0.75"),
                    ],
                    spacing=self._spacing_system.md if self._spacing_system else 12
                ),

                # Tablet factor
                ft.Row(
                    controls=[
                        ft.Text("Tablet Factor:", size=typography.body_medium[0]),
                        ft.Slider(min=0.5, max=1.5, value=0.875, divisions=20, label="0.875"),
                    ],
                    spacing=self._spacing_system.md if self._spacing_system else 12
                ),

                # Desktop factor
                ft.Row(
                    controls=[
                        ft.Text("Desktop Factor:", size=typography.body_medium[0]),
                        ft.Slider(min=0.5, max=1.5, value=1.0, divisions=20, label="1.0"),
                    ],
                    spacing=self._spacing_system.md if self._spacing_system else 12
                ),

                # Large factor
                ft.Row(
                    controls=[
                        ft.Text("Large Factor:", size=typography.body_medium[0]),
                        ft.Slider(min=0.5, max=1.5, value=1.25, divisions=20, label="1.25"),
                    ],
                    spacing=self._spacing_system.md if self._spacing_system else 12
                ),
            ],
            spacing=self._spacing_system.sm if self._spacing_system else 8
        )

        return ft.Column(
            controls=[
                current_info,
                factor_controls,
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16,
            scroll=ft.ScrollMode.AUTO
        )

    def _on_spacing_value_change(self, spacing_key: str, value: float):
        """Handle spacing value change."""
        if value is not None:
            self._custom_spacing_values[spacing_key] = int(value)
            if self._is_live_preview:
                self.update()

    def _on_live_preview_toggle(self, e):
        """Handle live preview toggle."""
        self._is_live_preview = e.control.value
        if self._is_live_preview:
            self.update()

    def _on_reset_spacing(self, e):
        """Handle reset spacing to defaults."""
        self._custom_spacing_values.clear()
        self.update()

    def _on_export_config(self, e):
        """Handle export configuration."""
        config = self.export_spacing_config()
        # In a real implementation, this would save to file or copy to clipboard
        print("Spacing configuration exported:", config)

    def _build_semantic_spacing_editor(self) -> ft.Control:
        """Build semantic spacing editor for contextual spacing management."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Semantic spacing categories
        semantic_categories = [
            ("tight", "Tight Spacing", "For closely related content", 8),
            ("normal", "Normal Spacing", "For standard content separation", 16),
            ("loose", "Loose Spacing", "For distinct content sections", 24),
            ("section", "Section Spacing", "For major page sections", 32),
            ("page", "Page Spacing", "For page-level margins", 48),
        ]

        semantic_controls = []
        for key, label, description, default_value in semantic_categories:
            current_value = self._custom_spacing_values.get(f"semantic_{key}", default_value)

            # Preview container
            preview_container = ft.Container(
                content=ft.Text(
                    "Preview",
                    size=typography.caption[0],
                    color=theme.get_color("on-primary"),
                    text_align=ft.TextAlign.CENTER
                ),
                bgcolor=theme.get_color("primary"),
                height=30,
                border_radius=4,
                alignment=ft.alignment.center,
                margin=ft.margin.all(current_value)
            )

            control_card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                label,
                                size=typography.body_medium[0],
                                weight=ft.FontWeight.W_500,
                                color=theme.get_color("text-primary")
                            ),
                            ft.Text(
                                description,
                                size=typography.body_small[0],
                                color=theme.get_color("text-secondary")
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Value:",
                                        size=typography.body_small[0],
                                        color=theme.get_color("text-primary")
                                    ),
                                    ft.Slider(
                                        min=4,
                                        max=64,
                                        value=current_value,
                                        divisions=15,
                                        label=f"{current_value}px",
                                        on_change=lambda e, k=f"semantic_{key}": self._on_spacing_value_change(k, e.control.value),
                                        expand=True
                                    ),
                                    ft.Text(
                                        f"{current_value}px",
                                        size=typography.body_small[0],
                                        color=theme.get_color("text-secondary"),
                                        width=50
                                    ),
                                ],
                                spacing=self._spacing_system.sm if self._spacing_system else 8
                            ),
                            ft.Container(
                                content=preview_container,
                                bgcolor=theme.get_color("surface-variant"),
                                height=60,
                                border_radius=4,
                                alignment=ft.alignment.center
                            ),
                        ],
                        spacing=self._spacing_system.xs if self._spacing_system else 4
                    ),
                    padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12)
                ),
                elevation=1
            )
            semantic_controls.append(control_card)

        return ft.Column(
            controls=[
                ft.Text(
                    "Semantic Spacing Editor",
                    size=typography.heading_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Define contextual spacing values for different content relationships",
                    size=typography.body_medium[0],
                    color=theme.get_color("text-secondary")
                ),
                self.create_responsive_grid(
                    children=semantic_controls,
                    mobile_cols=1,
                    tablet_cols=2,
                    desktop_cols=3,
                    large_cols=3,
                    spacing=self._spacing_system.md if self._spacing_system else 12
                )
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def _build_accessibility_spacing_guide(self) -> ft.Control:
        """Build accessibility spacing guidelines and recommendations."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Accessibility guidelines
        guidelines = [
            {
                "title": "Touch Target Spacing",
                "description": "Minimum 44px spacing between interactive elements for touch accessibility",
                "recommendation": "Use at least 44px spacing for buttons and clickable elements",
                "spacing_value": 44,
                "compliance": "WCAG 2.1 AA"
            },
            {
                "title": "Text Line Spacing",
                "description": "Adequate line spacing improves readability for users with dyslexia",
                "recommendation": "Use 1.5x line height minimum for body text",
                "spacing_value": 24,  # For 16px text
                "compliance": "WCAG 2.1 AA"
            },
            {
                "title": "Focus Indicator Spacing",
                "description": "Clear spacing around focus indicators for keyboard navigation",
                "recommendation": "Minimum 2px spacing around focus outlines",
                "spacing_value": 2,
                "compliance": "WCAG 2.1 AA"
            },
            {
                "title": "Content Grouping",
                "description": "Logical spacing helps screen readers understand content structure",
                "recommendation": "Use consistent spacing to group related content",
                "spacing_value": 16,
                "compliance": "WCAG 2.1 AA"
            },
        ]

        guideline_cards = []
        for guideline in guidelines:
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        guideline["title"],
                                        size=typography.body_large[0],
                                        weight=ft.FontWeight.W_600,
                                        color=theme.get_color("text-primary"),
                                        expand=True
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            guideline["compliance"],
                                            size=typography.caption[0],
                                            color=theme.get_color("on-primary"),
                                            text_align=ft.TextAlign.CENTER
                                        ),
                                        bgcolor=theme.get_color("primary"),
                                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                        border_radius=12
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            ),
                            ft.Text(
                                guideline["description"],
                                size=typography.body_medium[0],
                                color=theme.get_color("text-secondary")
                            ),
                            ft.Text(
                                guideline["recommendation"],
                                size=typography.body_small[0],
                                color=theme.get_color("text-primary"),
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"Recommended: {guideline['spacing_value']}px",
                                    size=typography.body_small[0],
                                    color=theme.get_color("on-surface-variant"),
                                    text_align=ft.TextAlign.CENTER
                                ),
                                bgcolor=theme.get_color("surface-variant"),
                                padding=ft.padding.all(8),
                                border_radius=4,
                                alignment=ft.alignment.center
                            ),
                        ],
                        spacing=self._spacing_system.sm if self._spacing_system else 8
                    ),
                    padding=ft.padding.all(self._spacing_system.md if self._spacing_system else 12)
                ),
                elevation=2
            )
            guideline_cards.append(card)

        return ft.Column(
            controls=[
                ft.Text(
                    "Accessibility Spacing Guidelines",
                    size=typography.heading_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "Follow these spacing guidelines to ensure accessibility compliance",
                    size=typography.body_medium[0],
                    color=theme.get_color("text-secondary")
                ),
                self.create_responsive_grid(
                    children=guideline_cards,
                    mobile_cols=1,
                    tablet_cols=2,
                    desktop_cols=2,
                    large_cols=2,
                    spacing=self._spacing_system.md if self._spacing_system else 12
                )
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def _on_responsive_change(self):
        """Handle responsive layout changes."""
        super()._on_responsive_change()
        # Update spacing demonstrations when screen size changes
        if hasattr(self, '_spacing_system') and self._spacing_system:
            self.update()

    def get_responsive_spacing_for_breakpoint(self, base_value: int, breakpoint: str) -> int:
        """Get responsive spacing value for specific breakpoint."""
        factors = {
            "mobile": 0.75,
            "tablet": 0.875,
            "desktop": 1.0,
            "large": 1.25
        }

        factor = factors.get(breakpoint.lower(), 1.0)
        return int(base_value * factor)

    def demonstrate_responsive_behavior(self) -> ft.Control:
        """Demonstrate responsive spacing behavior across breakpoints."""
        theme = self.get_theme()
        typography = self.get_typography()

        # Create demonstration for each breakpoint
        breakpoint_demos = []
        base_spacing = 16

        for breakpoint in ["mobile", "tablet", "desktop", "large"]:
            responsive_value = self.get_responsive_spacing_for_breakpoint(base_spacing, breakpoint)

            demo_container = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"{breakpoint.title()}",
                            size=typography.body_medium[0],
                            weight=ft.FontWeight.W_500,
                            color=theme.get_color("text-primary")
                        ),
                        ft.Text(
                            f"{base_spacing}px → {responsive_value}px",
                            size=typography.body_small[0],
                            color=theme.get_color("text-secondary")
                        ),
                        ft.Container(
                            content=ft.Text(
                                "Sample",
                                size=typography.caption[0],
                                color=theme.get_color("on-primary"),
                                text_align=ft.TextAlign.CENTER
                            ),
                            bgcolor=theme.get_color("primary"),
                            height=40,
                            border_radius=4,
                            alignment=ft.alignment.center,
                            margin=ft.margin.all(responsive_value // 2)
                        ),
                    ],
                    spacing=self._spacing_system.xs if self._spacing_system else 4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.all(self._spacing_system.sm if self._spacing_system else 8),
                bgcolor=theme.get_color("surface-variant"),
                border_radius=8,
                border=ft.border.all(1, theme.get_color("outline"))
            )
            breakpoint_demos.append(demo_container)

        return ft.Column(
            controls=[
                ft.Text(
                    "Responsive Spacing Behavior",
                    size=typography.heading_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=theme.get_color("text-primary")
                ),
                ft.Text(
                    "How spacing adapts across different screen sizes",
                    size=typography.body_medium[0],
                    color=theme.get_color("text-secondary")
                ),
                self.create_responsive_grid(
                    children=breakpoint_demos,
                    mobile_cols=1,
                    tablet_cols=2,
                    desktop_cols=4,
                    large_cols=4,
                    spacing=self._spacing_system.md if self._spacing_system else 12
                )
            ],
            spacing=self._spacing_system.lg if self._spacing_system else 16
        )

    def create_spacing_aware_layout(self, content: List[ft.Control],
                                  spacing_type: str = "normal") -> ft.Control:
        """Create a layout with spacing-aware responsive behavior."""
        # Get appropriate spacing based on type and current breakpoint
        spacing_values = {
            "tight": self.get_breakpoint_value(6, 8, 10, 12),
            "normal": self.get_breakpoint_value(12, 16, 20, 24),
            "loose": self.get_breakpoint_value(18, 24, 30, 36),
            "section": self.get_breakpoint_value(24, 32, 40, 48)
        }

        spacing = spacing_values.get(spacing_type, spacing_values["normal"])

        return ft.Column(
            controls=content,
            spacing=spacing,
            tight=True
        )

    def get_breakpoint_aware_padding(self, component_type: str = "default") -> ft.Padding:
        """Get breakpoint-aware padding for different component types."""
        padding_configs = {
            "default": {
                "mobile": ft.padding.all(12),
                "tablet": ft.padding.all(16),
                "desktop": ft.padding.all(20),
                "large": ft.padding.all(24)
            },
            "card": {
                "mobile": ft.padding.all(8),
                "tablet": ft.padding.all(12),
                "desktop": ft.padding.all(16),
                "large": ft.padding.all(20)
            },
            "section": {
                "mobile": ft.padding.all(16),
                "tablet": ft.padding.all(24),
                "desktop": ft.padding.all(32),
                "large": ft.padding.all(40)
            },
            "button": {
                "mobile": ft.padding.symmetric(horizontal=12, vertical=6),
                "tablet": ft.padding.symmetric(horizontal=16, vertical=8),
                "desktop": ft.padding.symmetric(horizontal=20, vertical=10),
                "large": ft.padding.symmetric(horizontal=24, vertical=12)
            }
        }

        config = padding_configs.get(component_type, padding_configs["default"])
        current_screen = self.get_current_screen_size()

        return config.get(current_screen, config["desktop"])

    def validate_spacing_accessibility(self, spacing_value: int,
                                     context: str = "general") -> Dict[str, Any]:
        """Validate spacing value against accessibility guidelines."""
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "recommendations": [],
            "compliance_level": "AA"
        }

        # Touch target spacing validation
        if context in ["button", "interactive", "touch"]:
            if spacing_value < 44:
                validation_result["warnings"].append(
                    f"Spacing {spacing_value}px is below WCAG 2.1 AA minimum of 44px for touch targets"
                )
                validation_result["is_valid"] = False
                validation_result["compliance_level"] = "Fail"
                validation_result["recommendations"].append(
                    "Increase spacing to at least 44px for touch accessibility"
                )

        # Text spacing validation
        if context in ["text", "paragraph", "content"]:
            if spacing_value < 12:
                validation_result["warnings"].append(
                    f"Text spacing {spacing_value}px may be too tight for readability"
                )
                validation_result["recommendations"].append(
                    "Consider increasing to at least 12px for better readability"
                )

        # Focus indicator spacing
        if context in ["focus", "outline"]:
            if spacing_value < 2:
                validation_result["warnings"].append(
                    f"Focus spacing {spacing_value}px is below recommended 2px minimum"
                )
                validation_result["recommendations"].append(
                    "Increase to at least 2px for clear focus indication"
                )

        return validation_result

    def generate_spacing_documentation(self) -> Dict[str, Any]:
        """Generate comprehensive spacing system documentation."""
        current_spacing = self._spacing_system or SpacingSystem()

        documentation = {
            "spacing_system": {
                "base_unit": current_spacing.base_unit,
                "scale": {
                    "xs": current_spacing.xs,
                    "sm": current_spacing.sm,
                    "md": current_spacing.md,
                    "lg": current_spacing.lg,
                    "xl": current_spacing.xl,
                    "xxl": current_spacing.xxl,
                    "xxxl": current_spacing.xxxl,
                    "xxxxl": current_spacing.xxxxl,
                }
            },
            "component_spacing": {
                "component_padding": current_spacing.component_padding,
                "section_padding": current_spacing.section_padding,
                "icon_text_gap": current_spacing.icon_text_gap,
                "button_padding_horizontal": current_spacing.button_padding_horizontal,
                "button_padding_vertical": current_spacing.button_padding_vertical,
            },
            "responsive_behavior": {
                "current_screen": self.get_current_screen_size(),
                "breakpoints": {
                    "mobile": "0-575px",
                    "tablet": "576-991px",
                    "desktop": "992-1599px",
                    "large": "1600px+"
                },
                "scaling_factors": {
                    "mobile": 0.75,
                    "tablet": 0.875,
                    "desktop": 1.0,
                    "large": 1.25
                }
            },
            "accessibility_guidelines": {
                "touch_targets": "Minimum 44px spacing",
                "text_spacing": "Minimum 12px for readability",
                "focus_indicators": "Minimum 2px clear space",
                "compliance": "WCAG 2.1 AA"
            },
            "custom_values": self._custom_spacing_values.copy(),
            "usage_examples": {
                "tight_spacing": "Use for closely related content (8px)",
                "normal_spacing": "Use for standard content separation (16px)",
                "loose_spacing": "Use for distinct sections (24px)",
                "section_spacing": "Use for major page divisions (32px)"
            }
        }

        return documentation
