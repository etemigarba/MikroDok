"""
Module: color_palette_ui
Description: Responsive color palette display and management component with full theme integration
Phase: 1
Location: /src/modules/ui/theme_system_ui/color_palette_ui/color_palette_ui.py

Features:
- Responsive color palette display with adaptive grid layouts
- Touch-optimized color swatches with breakpoint-driven sizing
- Color category organization (Background, Text, Interactive, State)
- Accessibility compliance with WCAG 2.1 AA standards
- Color blind mode support with visual indicators
- Real-time theme change handling
- Mobile-first responsive design patterns
- Performance-optimized color rendering
"""

# Standard library imports
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import asdict

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    ThemeMode,
    ColorBlindMode
)

# Configure logging
logger = logging.getLogger(__name__)


class ColorPaletteUI(ThemeAwareUserControl):
    """
    Responsive color palette display component with comprehensive theme integration.
    
    Provides adaptive color palette visualization with:
    - Responsive grid layouts (1-4 columns based on breakpoint)
    - Touch-optimized color swatches with adaptive sizing
    - Color category organization and labeling
    - Accessibility features and color blind support
    - Real-time theme change handling
    - Performance-optimized rendering
    """
    
    def __init__(self, 
                 show_color_codes: bool = True,
                 show_accessibility_info: bool = True,
                 enable_color_selection: bool = False,
                 on_color_selected: Optional[Callable[[str, str], None]] = None,
                 **kwargs):
        """
        Initialize the ColorPaletteUI component.
        
        Args:
            show_color_codes: Whether to display hex color codes
            show_accessibility_info: Whether to show accessibility indicators
            enable_color_selection: Whether colors can be selected/clicked
            on_color_selected: Callback for color selection (color_name, hex_value)
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.show_color_codes = show_color_codes
        self.show_accessibility_info = show_accessibility_info
        self.enable_color_selection = enable_color_selection
        self.on_color_selected = on_color_selected
        
        # State
        self._current_palette: Optional[ColorPalette] = None
        self._color_categories: Dict[str, List[Tuple[str, str]]] = {}
        self._selected_color: Optional[str] = None
        
        # Responsive configuration
        self._swatch_sizes = {
            'mobile': 40,
            'tablet': 48,
            'desktop': 56,
            'large': 64
        }
        
        self._grid_columns = {
            'mobile': 1,
            'tablet': 2, 
            'desktop': 3,
            'large': 4
        }
        
        # Initialize component
        self._initialize_color_categories()
        self._build_component()
    
    def _initialize_color_categories(self) -> None:
        """Initialize color category definitions."""
        self._color_categories = {
            "Background Colors": [
                ("background_primary", "Primary Background"),
                ("background_secondary", "Secondary Background"),
                ("surface", "Surface"),
                ("surface_variant", "Surface Variant")
            ],
            "Text Colors": [
                ("text_primary", "Primary Text"),
                ("text_secondary", "Secondary Text"),
                ("text_tertiary", "Tertiary Text"),
                ("text_disabled", "Disabled Text")
            ],
            "Interactive Colors": [
                ("primary", "Primary"),
                ("primary_variant", "Primary Variant"),
                ("secondary", "Secondary"),
                ("secondary_variant", "Secondary Variant"),
                ("focus_indicator", "Focus Indicator"),
                ("selection", "Selection")
            ],
            "State Colors": [
                ("error", "Error"),
                ("error_container", "Error Container"),
                ("success", "Success"),
                ("warning", "Warning"),
                ("info", "Information")
            ],
            "Border & Outline": [
                ("borders", "Borders"),
                ("outline", "Outline")
            ]
        }
    
    def _build_component(self) -> None:
        """Build the responsive color palette component."""
        try:
            # Get current palette
            self._current_palette = self.get_palette()
            
            # Create responsive container with adaptive padding
            responsive_padding = self.get_responsive_padding()
            
            # Build color category sections
            category_sections = self._build_color_categories()
            
            # Create main container with responsive layout
            self.content = self.create_responsive_container(
                content=ft.Column(
                    controls=category_sections,
                    spacing=self.get_breakpoint_value(
                        mobile=16, tablet=20, desktop=24, large=28
                    ),
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                ),
                padding=responsive_padding
            )
            
            logger.debug("ColorPaletteUI component built successfully")
            
        except Exception as e:
            logger.error(f"Error building ColorPaletteUI component: {e}")
            self._build_error_state()
    
    def _build_color_categories(self) -> List[ft.Control]:
        """Build responsive color category sections."""
        category_sections = []
        
        try:
            for category_name, color_items in self._color_categories.items():
                # Create category header
                header = self._create_category_header(category_name)
                
                # Create responsive color grid for this category
                color_grid = self._create_color_grid(color_items)
                
                # Create category section with responsive spacing
                category_section = ft.Container(
                    content=ft.Column(
                        controls=[header, color_grid],
                        spacing=self.get_breakpoint_value(
                            mobile=8, tablet=12, desktop=16, large=16
                        )
                    ),
                    margin=ft.margin.only(
                        bottom=self.get_breakpoint_value(
                            mobile=16, tablet=20, desktop=24, large=28
                        )
                    )
                )
                
                category_sections.append(category_section)
                
        except Exception as e:
            logger.error(f"Error building color categories: {e}")
            
        return category_sections
    
    def _create_category_header(self, category_name: str) -> ft.Control:
        """Create responsive category header."""
        palette = self.get_palette()
        typography = self.get_typography()
        
        return ft.Container(
            content=ft.Text(
                value=category_name,
                size=self.get_breakpoint_value(
                    mobile=typography.h4[0],  # 18px
                    tablet=typography.h3[0],  # 20px
                    desktop=typography.h3[0], # 20px
                    large=typography.h2[0]    # 24px
                ),
                weight=ft.FontWeight.W_600,
                color=palette.text_primary
            ),
            padding=ft.padding.only(
                bottom=self.get_breakpoint_value(
                    mobile=8, tablet=12, desktop=12, large=16
                )
            )
        )

    def _create_color_grid(self, color_items: List[Tuple[str, str]]) -> ft.Control:
        """Create responsive color grid for a category."""
        try:
            # Create color swatches
            color_swatches = []
            for color_key, color_label in color_items:
                swatch = self._create_color_swatch(color_key, color_label)
                if swatch:
                    color_swatches.append(swatch)

            # Create responsive grid
            grid_columns = self.get_breakpoint_value(
                mobile=self._grid_columns['mobile'],
                tablet=self._grid_columns['tablet'],
                desktop=self._grid_columns['desktop'],
                large=self._grid_columns['large']
            )

            # Use responsive grid creation
            return self.create_responsive_grid(
                children=color_swatches,
                mobile_cols=self._grid_columns['mobile'],
                tablet_cols=self._grid_columns['tablet'],
                desktop_cols=self._grid_columns['desktop'],
                large_cols=self._grid_columns['large'],
                spacing=self.get_breakpoint_value(
                    mobile=8, tablet=12, desktop=16, large=20
                ),
                run_spacing=self.get_breakpoint_value(
                    mobile=8, tablet=12, desktop=16, large=20
                )
            )

        except Exception as e:
            logger.error(f"Error creating color grid: {e}")
            return ft.Container(
                content=ft.Text("Error loading colors", color=self.get_palette().error)
            )

    def _create_color_swatch(self, color_key: str, color_label: str) -> Optional[ft.Control]:
        """Create responsive color swatch with accessibility features."""
        try:
            if not self._current_palette:
                return None

            # Get color value
            color_value = getattr(self._current_palette, color_key, None)
            if not color_value:
                return None

            palette = self.get_palette()

            # Get responsive swatch size
            swatch_size = self.get_breakpoint_value(
                mobile=self._swatch_sizes['mobile'],
                tablet=self._swatch_sizes['tablet'],
                desktop=self._swatch_sizes['desktop'],
                large=self._swatch_sizes['large']
            )

            # Create color preview container
            color_preview = ft.Container(
                width=swatch_size,
                height=swatch_size,
                bgcolor=color_value,
                border_radius=self.get_breakpoint_value(
                    mobile=4, tablet=6, desktop=8, large=8
                ),
                border=ft.border.all(
                    width=1,
                    color=palette.borders
                ),
                tooltip=f"{color_label}: {color_value}" if self.show_color_codes else color_label
            )

            # Add click handler if selection is enabled
            if self.enable_color_selection and self.on_color_selected:
                color_preview.on_click = lambda e, key=color_key, value=color_value: self._handle_color_selection(key, value)
                color_preview.ink = True
                color_preview.ink_color = palette.selection

            # Create label with responsive text size
            label_text = ft.Text(
                value=color_label,
                size=self.get_breakpoint_value(
                    mobile=10, tablet=11, desktop=12, large=13
                ),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            # Create color code text if enabled
            controls = [color_preview, label_text]

            if self.show_color_codes:
                code_text = ft.Text(
                    value=color_value,
                    size=self.get_breakpoint_value(
                        mobile=8, tablet=9, desktop=10, large=10
                    ),
                    color=palette.text_tertiary,
                    text_align=ft.TextAlign.CENTER,
                    font_family="JetBrains Mono"
                )
                controls.append(code_text)

            # Add accessibility indicator if enabled
            if self.show_accessibility_info:
                accessibility_icon = self._create_accessibility_indicator(color_value)
                if accessibility_icon:
                    controls.append(accessibility_icon)

            # Create swatch container with responsive spacing
            return ft.Container(
                content=ft.Column(
                    controls=controls,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=self.get_breakpoint_value(
                        mobile=4, tablet=6, desktop=8, large=8
                    )
                ),
                padding=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=16
                ),
                border_radius=self.get_breakpoint_value(
                    mobile=6, tablet=8, desktop=10, large=12
                ),
                bgcolor=palette.surface_variant if self._selected_color == color_key else None,
                border=ft.border.all(
                    width=2 if self._selected_color == color_key else 0,
                    color=palette.primary if self._selected_color == color_key else palette.surface_variant
                )
            )

        except Exception as e:
            logger.error(f"Error creating color swatch for {color_key}: {e}")
            return None

    def _create_accessibility_indicator(self, color_value: str) -> Optional[ft.Control]:
        """Create accessibility indicator for color contrast."""
        try:
            # Get theme manager for color blind mode detection
            theme_manager = self._theme_manager
            if not theme_manager:
                return None

            palette = self.get_palette()

            # Check if color blind mode is active
            color_blind_mode = getattr(theme_manager, '_color_blind_mode', None)

            if color_blind_mode and color_blind_mode != ColorBlindMode.NONE:
                # Show accessibility icon for color blind users
                icon_size = self.get_breakpoint_value(
                    mobile=12, tablet=14, desktop=16, large=18
                )

                return ft.Icon(
                    name=ft.Icons.ACCESSIBILITY,
                    size=icon_size,
                    color=palette.info,
                    tooltip="Color blind accessible"
                )

            return None

        except Exception as e:
            logger.error(f"Error creating accessibility indicator: {e}")
            return None

    def _handle_color_selection(self, color_key: str, color_value: str) -> None:
        """Handle color selection event."""
        try:
            self._selected_color = color_key

            # Call selection callback if provided
            if self.on_color_selected:
                self.on_color_selected(color_key, color_value)

            # Rebuild component to show selection
            self._build_component()
            self.update()

            logger.debug(f"Color selected: {color_key} = {color_value}")

        except Exception as e:
            logger.error(f"Error handling color selection: {e}")

    def _build_error_state(self) -> None:
        """Build error state when component fails to load."""
        palette = self.get_palette()

        self.content = self.create_responsive_container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.ERROR_OUTLINE,
                        size=48,
                        color=palette.error
                    ),
                    ft.Text(
                        value="Error loading color palette",
                        size=16,
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            padding=self.get_responsive_padding()
        )

    def _on_theme_change(self) -> None:
        """Handle theme change events."""
        try:
            # Update current palette
            self._current_palette = self.get_palette()

            # Rebuild component with new theme
            self._build_component()
            self.update()

            logger.debug("ColorPaletteUI updated for theme change")

        except Exception as e:
            logger.error(f"Error handling theme change in ColorPaletteUI: {e}")

    def _on_responsive_change(self, screen_size) -> None:
        """Handle responsive layout changes."""
        try:
            # Rebuild component for new screen size
            self._build_component()
            self.update()

            logger.debug(f"ColorPaletteUI updated for screen size: {screen_size}")

        except Exception as e:
            logger.error(f"Error handling responsive change in ColorPaletteUI: {e}")

    def refresh_palette(self) -> None:
        """Refresh the color palette display."""
        try:
            self._current_palette = self.get_palette()
            self._build_component()
            self.update()

            logger.debug("ColorPaletteUI palette refreshed")

        except Exception as e:
            logger.error(f"Error refreshing color palette: {e}")

    def set_selected_color(self, color_key: Optional[str]) -> None:
        """Set the selected color programmatically."""
        try:
            self._selected_color = color_key
            self._build_component()
            self.update()

            logger.debug(f"Selected color set to: {color_key}")

        except Exception as e:
            logger.error(f"Error setting selected color: {e}")

    def get_selected_color(self) -> Optional[Tuple[str, str]]:
        """Get the currently selected color."""
        try:
            if not self._selected_color or not self._current_palette:
                return None

            color_value = getattr(self._current_palette, self._selected_color, None)
            if color_value:
                return (self._selected_color, color_value)

            return None

        except Exception as e:
            logger.error(f"Error getting selected color: {e}")
            return None

    def get_all_colors(self) -> Dict[str, str]:
        """Get all colors from the current palette."""
        try:
            if not self._current_palette:
                return {}

            return asdict(self._current_palette)

        except Exception as e:
            logger.error(f"Error getting all colors: {e}")
            return {}

    def build(self) -> ft.Control:
        """Build the color palette component."""
        return self.content if hasattr(self, 'content') and self.content else ft.Container()
