"""
Module: typography_ui
Description: Typography management and preview UI component for MikroDok application.
            Provides comprehensive typography system interface including font family selection,
            text style demonstrations, responsive typography samples, and real-time preview
            capabilities. Integrates with theme system for consistent styling and supports
            Inter and JetBrains Mono font configurations with adaptive scaling.

Phase: 1
Location: /src/modules/ui/theme_system_ui/typography_ui/typography_ui.py
"""

# Standard library imports
import logging
from typing import Dict, List, Optional, Tuple, Any

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    TypographyScale
)

# Configure logging
logger = logging.getLogger(__name__)


class TypographyUI(ThemeAwareUserControl):
    """
    Typography management and preview UI component.
    
    Provides comprehensive typography system interface including:
    - Font family selection and preview
    - Text style demonstrations with live preview
    - Responsive typography samples across breakpoints
    - Typography scale visualization
    - Real-time theme integration
    - Accessibility-compliant typography settings
    """
    
    def __init__(self, **kwargs):
        """
        Initialize typography UI component.
        
        Args:
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Component state
        self._selected_font_family = "Inter"
        self._selected_text_style = "body_medium"
        self._preview_text = "The quick brown fox jumps over the lazy dog"
        self._show_responsive_preview = True
        
        # UI components
        self._font_selector = None
        self._style_selector = None
        self._preview_container = None
        self._responsive_preview = None
        self._typography_scale_display = None
        
        # Initialize component
        self._build_component()
    
    def _build_component(self) -> None:
        """Build the typography UI component."""
        try:
            # Ensure theme manager is available
            self._ensure_theme_manager()
            self._ensure_responsive_manager()

            # Get theme components
            typography = self.get_typography()
            spacing = self.get_spacing()
            
            # Create main container with responsive layout
            self.content = self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        self._create_header(),
                        self._create_font_family_selector(),
                        self._create_text_style_selector(),
                        self._create_preview_section(),
                        self._create_responsive_preview_section(),
                        self._create_typography_scale_display()
                    ],
                    spacing=spacing.lg,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=spacing.lg
            )
            
        except Exception as e:
            logger.error(f"Error building typography UI component: {e}")
            self._create_error_fallback()
    
    def _create_header(self) -> ft.Control:
        """Create typography UI header."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Typography System",
                        style=self.get_text_style("h2"),
                        color=self.get_palette().text_primary
                    ),
                    ft.Text(
                        "Configure and preview typography settings for the MikroDok application",
                        style=self.get_text_style("body_medium"),
                        color=self.get_palette().text_secondary
                    )
                ],
                spacing=self.get_spacing().sm
            ),
            padding=ft.padding.only(bottom=self.get_spacing().md)
        )
    
    def _create_font_family_selector(self) -> ft.Control:
        """Create font family selection interface."""
        typography = self.get_typography()
        
        font_options = [
            ft.dropdown.Option(
                key="Inter",
                text="Inter (Primary)",
                content=ft.Text(
                    "Inter - Primary UI Font",
                    style=ft.TextStyle(font_family="Inter"),
                    color=self.get_palette().text_primary
                )
            ),
            ft.dropdown.Option(
                key="JetBrains Mono",
                text="JetBrains Mono (Monospace)",
                content=ft.Text(
                    "JetBrains Mono - Code & Data",
                    style=ft.TextStyle(font_family="JetBrains Mono"),
                    color=self.get_palette().text_primary
                )
            )
        ]
        
        self._font_selector = ft.Dropdown(
            label="Font Family",
            value=self._selected_font_family,
            options=font_options,
            on_change=self._on_font_family_changed,
            border_color=self.get_palette().outline,
            bgcolor=self.get_palette().surface_variant,
            color=self.get_palette().text_primary,
            width=self.get_breakpoint_value(
                mobile=280, tablet=320, desktop=360, large=400
            )
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Font Family Selection",
                        style=self.get_text_style("h4"),
                        color=self.get_palette().text_primary
                    ),
                    self._font_selector
                ],
                spacing=self.get_spacing().sm
            ),
            padding=ft.padding.symmetric(vertical=self.get_spacing().md)
        )

    def _create_text_style_selector(self) -> ft.Control:
        """Create text style selection interface."""
        typography = self.get_typography()

        # Define style categories with their options
        style_categories = {
            "Display": ["display_large", "display_medium", "display_small"],
            "Headings": ["h1", "h2", "h3", "h4"],
            "Body Text": ["body_large", "body_medium", "body_small"],
            "Supporting": ["caption", "overline", "label"],
            "Data/Code": ["metric_large", "metric_medium", "code_block", "inline_code"]
        }

        style_options = []
        for category, styles in style_categories.items():
            for style in styles:
                style_options.append(
                    ft.dropdown.Option(
                        key=style,
                        text=f"{category}: {style.replace('_', ' ').title()}"
                    )
                )

        self._style_selector = ft.Dropdown(
            label="Text Style",
            value=self._selected_text_style,
            options=style_options,
            on_change=self._on_text_style_changed,
            border_color=self.get_palette().outline,
            bgcolor=self.get_palette().surface_variant,
            color=self.get_palette().text_primary,
            width=self.get_breakpoint_value(
                mobile=280, tablet=320, desktop=360, large=400
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Text Style Selection",
                        style=self.get_text_style("h4"),
                        color=self.get_palette().text_primary
                    ),
                    self._style_selector
                ],
                spacing=self.get_spacing().sm
            ),
            padding=ft.padding.symmetric(vertical=self.get_spacing().md)
        )

    def _create_preview_section(self) -> ft.Control:
        """Create typography preview section."""
        self._preview_container = ft.Container(
            content=self._create_preview_content(),
            bgcolor=self.get_palette().surface_variant,
            border=ft.border.all(1, self.get_palette().borders),
            border_radius=self.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=12
            ),
            padding=self.get_spacing().lg,
            width=self.get_breakpoint_value(
                mobile=None, tablet=500, desktop=600, large=700
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Typography Preview",
                        style=self.get_text_style("h4"),
                        color=self.get_palette().text_primary
                    ),
                    self._preview_container
                ],
                spacing=self.get_spacing().sm
            ),
            padding=ft.padding.symmetric(vertical=self.get_spacing().md)
        )

    def _create_preview_content(self) -> ft.Control:
        """Create the actual preview content."""
        # Get current style configuration
        text_style = self.get_text_style(self._selected_text_style)

        # Adjust font family based on selection
        if self._selected_font_family == "JetBrains Mono":
            text_style.font_family = "JetBrains Mono"
        else:
            text_style.font_family = "Inter"

        # Create preview text with responsive length
        preview_text = self._get_responsive_preview_text()

        return ft.Column(
            controls=[
                ft.Text(
                    preview_text,
                    style=text_style,
                    color=self.get_palette().text_primary,
                    selectable=True
                ),
                ft.Divider(color=self.get_palette().borders),
                self._create_style_info_display()
            ],
            spacing=self.get_spacing().md
        )

    def _get_responsive_preview_text(self) -> str:
        """Get preview text with responsive length based on screen size."""
        base_text = self._preview_text

        # Adjust text length based on breakpoint
        if self.is_mobile():
            # Shorter text for mobile
            return base_text[:30] + "..." if len(base_text) > 30 else base_text
        elif self.is_tablet():
            # Medium text for tablet
            return base_text[:50] + "..." if len(base_text) > 50 else base_text
        else:
            # Full text for desktop and large screens
            return base_text

    def _create_style_info_display(self) -> ft.Control:
        """Create style information display."""
        typography = self.get_typography()

        # Get style information
        style_info = getattr(typography, self._selected_text_style, (14, 20, 400, 0.0))
        if len(style_info) == 3:
            size, line_height, weight = style_info
            letter_spacing = 0.0
        else:
            size, line_height, weight, letter_spacing = style_info

        info_items = [
            f"Font: {self._selected_font_family}",
            f"Size: {size}px",
            f"Line Height: {line_height}px",
            f"Weight: {weight}",
            f"Letter Spacing: {letter_spacing}%"
        ]

        return ft.Row(
            controls=[
                ft.Text(
                    " • ".join(info_items),
                    style=self.get_text_style("caption"),
                    color=self.get_palette().text_secondary
                )
            ],
            wrap=True
        )

    def _create_responsive_preview_section(self) -> ft.Control:
        """Create responsive typography preview section."""
        if not self._show_responsive_preview:
            return ft.Container()

        self._responsive_preview = ft.Container(
            content=self._create_responsive_preview_content(),
            bgcolor=self.get_palette().surface_variant,
            border=ft.border.all(1, self.get_palette().borders),
            border_radius=self.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=12
            ),
            padding=self.get_spacing().lg
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Responsive Preview",
                                style=self.get_text_style("h4"),
                                color=self.get_palette().text_primary
                            ),
                            ft.Switch(
                                value=self._show_responsive_preview,
                                on_change=self._on_responsive_preview_toggle,
                                active_color=self.get_palette().primary
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    self._responsive_preview
                ],
                spacing=self.get_spacing().sm
            ),
            padding=ft.padding.symmetric(vertical=self.get_spacing().md)
        )

    def _create_responsive_preview_content(self) -> ft.Control:
        """Create responsive preview content showing different breakpoints."""
        breakpoints = ["Mobile", "Tablet", "Desktop", "Large Desktop"]
        preview_controls = []

        for breakpoint in breakpoints:
            # Get responsive text style for this breakpoint
            responsive_style = self._get_responsive_text_style_for_breakpoint(breakpoint.lower().replace(" ", "_"))

            preview_controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                breakpoint,
                                style=self.get_text_style("label"),
                                color=self.get_palette().primary,
                                weight=ft.FontWeight.W_600
                            ),
                            ft.Text(
                                self._get_responsive_preview_text_for_breakpoint(breakpoint),
                                style=responsive_style,
                                color=self.get_palette().text_primary
                            )
                        ],
                        spacing=self.get_spacing().xs
                    ),
                    padding=self.get_spacing().md,
                    bgcolor=self.get_palette().surface,
                    border_radius=8,
                    border=ft.border.all(1, self.get_palette().borders)
                )
            )

        return ft.Column(
            controls=preview_controls,
            spacing=self.get_spacing().md
        )

    def _get_responsive_text_style_for_breakpoint(self, breakpoint: str) -> ft.TextStyle:
        """Get text style adjusted for specific breakpoint."""
        base_style = self.get_text_style(self._selected_text_style)

        # Apply responsive scaling based on breakpoint
        scale_factors = {
            "mobile": 0.9,
            "tablet": 0.95,
            "desktop": 1.0,
            "large_desktop": 1.1
        }

        scale = scale_factors.get(breakpoint, 1.0)

        # Create scaled style
        scaled_style = ft.TextStyle(
            size=int(base_style.size * scale) if base_style.size else 14,
            font_family=self._selected_font_family,
            weight=base_style.weight,
            color=base_style.color
        )

        return scaled_style

    def _get_responsive_preview_text_for_breakpoint(self, breakpoint: str) -> str:
        """Get preview text appropriate for breakpoint."""
        text_lengths = {
            "Mobile": 25,
            "Tablet": 40,
            "Desktop": 60,
            "Large Desktop": 80
        }

        max_length = text_lengths.get(breakpoint, 60)
        if len(self._preview_text) > max_length:
            return self._preview_text[:max_length] + "..."
        return self._preview_text

    def _create_typography_scale_display(self) -> ft.Control:
        """Create typography scale visualization."""
        typography = self.get_typography()

        # Define typography scale items to display
        scale_items = [
            ("Display Large", "display_large", "The quick brown fox"),
            ("Display Medium", "display_medium", "The quick brown fox"),
            ("Display Small", "display_small", "The quick brown fox"),
            ("Heading 1", "h1", "The quick brown fox jumps"),
            ("Heading 2", "h2", "The quick brown fox jumps"),
            ("Heading 3", "h3", "The quick brown fox jumps over"),
            ("Heading 4", "h4", "The quick brown fox jumps over the lazy"),
            ("Body Large", "body_large", "The quick brown fox jumps over the lazy dog"),
            ("Body Medium", "body_medium", "The quick brown fox jumps over the lazy dog"),
            ("Body Small", "body_small", "The quick brown fox jumps over the lazy dog"),
            ("Caption", "caption", "The quick brown fox jumps over the lazy dog"),
            ("Label", "label", "The quick brown fox jumps over the lazy dog")
        ]

        scale_controls = []
        for label, style_name, sample_text in scale_items:
            text_style = self.get_text_style(style_name)

            # Adjust font family for monospace styles
            if style_name in ["code_block", "inline_code", "metric_large", "metric_medium"]:
                text_style.font_family = "JetBrains Mono"
            else:
                text_style.font_family = "Inter"

            scale_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    label,
                                    style=self.get_text_style("label"),
                                    color=self.get_palette().text_secondary,
                                    weight=ft.FontWeight.W_500
                                ),
                                width=self.get_breakpoint_value(
                                    mobile=100, tablet=120, desktop=140, large=160
                                )
                            ),
                            ft.Container(
                                content=ft.Text(
                                    sample_text,
                                    style=text_style,
                                    color=self.get_palette().text_primary
                                ),
                                expand=True
                            )
                        ],
                        alignment=ft.MainAxisAlignment.START
                    ),
                    padding=ft.padding.symmetric(
                        vertical=self.get_spacing().sm,
                        horizontal=self.get_spacing().md
                    ),
                    border=ft.border.only(
                        bottom=ft.BorderSide(1, self.get_palette().borders)
                    )
                )
            )

        self._typography_scale_display = ft.Container(
            content=ft.Column(
                controls=scale_controls,
                spacing=0
            ),
            bgcolor=self.get_palette().surface_variant,
            border=ft.border.all(1, self.get_palette().borders),
            border_radius=self.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=12
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Typography Scale",
                        style=self.get_text_style("h4"),
                        color=self.get_palette().text_primary
                    ),
                    ft.Text(
                        "Complete typography hierarchy with Inter and JetBrains Mono fonts",
                        style=self.get_text_style("body_small"),
                        color=self.get_palette().text_secondary
                    ),
                    self._typography_scale_display
                ],
                spacing=self.get_spacing().sm
            ),
            padding=ft.padding.symmetric(vertical=self.get_spacing().md)
        )

    def _on_font_family_changed(self, e) -> None:
        """Handle font family selection change."""
        try:
            self._selected_font_family = e.control.value
            self._update_preview()
            logger.info(f"Font family changed to: {self._selected_font_family}")
        except Exception as ex:
            logger.error(f"Error changing font family: {ex}")

    def _on_text_style_changed(self, e) -> None:
        """Handle text style selection change."""
        try:
            self._selected_text_style = e.control.value
            self._update_preview()
            logger.info(f"Text style changed to: {self._selected_text_style}")
        except Exception as ex:
            logger.error(f"Error changing text style: {ex}")

    def _on_responsive_preview_toggle(self, e) -> None:
        """Handle responsive preview toggle."""
        try:
            self._show_responsive_preview = e.control.value
            self._update_responsive_preview()
            logger.info(f"Responsive preview toggled: {self._show_responsive_preview}")
        except Exception as ex:
            logger.error(f"Error toggling responsive preview: {ex}")

    def _update_preview(self) -> None:
        """Update the typography preview."""
        try:
            if self._preview_container:
                self._preview_container.content = self._create_preview_content()
                self._preview_container.update()
        except Exception as e:
            logger.error(f"Error updating preview: {e}")

    def _update_responsive_preview(self) -> None:
        """Update the responsive preview section."""
        try:
            if self._responsive_preview:
                if self._show_responsive_preview:
                    self._responsive_preview.content = self._create_responsive_preview_content()
                    self._responsive_preview.visible = True
                else:
                    self._responsive_preview.visible = False
                self._responsive_preview.update()
        except Exception as e:
            logger.error(f"Error updating responsive preview: {e}")

    def _create_error_fallback(self) -> None:
        """Create error fallback UI."""
        self.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        size=48,
                        color=ft.Colors.RED_400
                    ),
                    ft.Text(
                        "Typography UI Error",
                        size=18,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.RED_400
                    ),
                    ft.Text(
                        "Unable to load typography interface. Please check the theme system.",
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            padding=32,
            alignment=ft.alignment.center
        )

    def on_theme_changed(self) -> None:
        """Handle theme change events."""
        try:
            # Rebuild component with new theme
            self._build_component()
            self.update()
            logger.info("Typography UI updated for theme change")
        except Exception as e:
            logger.error(f"Error handling theme change in typography UI: {e}")

    def on_responsive_change(self, screen_size) -> None:
        """Handle responsive layout changes."""
        try:
            # Update responsive elements
            self._update_preview()
            self._update_responsive_preview()
            self.update()
            logger.info(f"Typography UI updated for screen size: {screen_size}")
        except Exception as e:
            logger.error(f"Error handling responsive change in typography UI: {e}")

    def set_preview_text(self, text: str) -> None:
        """
        Set custom preview text.

        Args:
            text: Custom text to display in preview
        """
        try:
            self._preview_text = text
            self._update_preview()
            self._update_responsive_preview()
            logger.info(f"Preview text updated: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error setting preview text: {e}")

    def get_current_font_family(self) -> str:
        """
        Get currently selected font family.

        Returns:
            Current font family name
        """
        return self._selected_font_family

    def get_current_text_style(self) -> str:
        """
        Get currently selected text style.

        Returns:
            Current text style name
        """
        return self._selected_text_style

    def set_font_family(self, font_family: str) -> None:
        """
        Set font family programmatically.

        Args:
            font_family: Font family to set ("Inter" or "JetBrains Mono")
        """
        try:
            if font_family in ["Inter", "JetBrains Mono"]:
                self._selected_font_family = font_family
                if self._font_selector:
                    self._font_selector.value = font_family
                    self._font_selector.update()
                self._update_preview()
                logger.info(f"Font family set to: {font_family}")
            else:
                logger.warning(f"Invalid font family: {font_family}")
        except Exception as e:
            logger.error(f"Error setting font family: {e}")

    def set_text_style(self, text_style: str) -> None:
        """
        Set text style programmatically.

        Args:
            text_style: Text style to set
        """
        try:
            self._selected_text_style = text_style
            if self._style_selector:
                self._style_selector.value = text_style
                self._style_selector.update()
            self._update_preview()
            logger.info(f"Text style set to: {text_style}")
        except Exception as e:
            logger.error(f"Error setting text style: {e}")

    def toggle_responsive_preview(self, show: Optional[bool] = None) -> None:
        """
        Toggle responsive preview visibility.

        Args:
            show: Optional boolean to explicitly set visibility
        """
        try:
            if show is not None:
                self._show_responsive_preview = show
            else:
                self._show_responsive_preview = not self._show_responsive_preview

            self._update_responsive_preview()
            logger.info(f"Responsive preview toggled: {self._show_responsive_preview}")
        except Exception as e:
            logger.error(f"Error toggling responsive preview: {e}")

    def get_typography_info(self) -> Dict[str, Any]:
        """
        Get comprehensive typography information.

        Returns:
            Dictionary containing typography configuration
        """
        try:
            typography = self.get_typography()

            return {
                "current_font_family": self._selected_font_family,
                "current_text_style": self._selected_text_style,
                "preview_text": self._preview_text,
                "responsive_preview_enabled": self._show_responsive_preview,
                "typography_scale": {
                    "primary_font": typography.primary_font,
                    "secondary_font": typography.secondary_font,
                    "fallback_fonts": typography.fallback_fonts,
                    "mono_fallback_fonts": typography.mono_fallback_fonts
                }
            }
        except Exception as e:
            logger.error(f"Error getting typography info: {e}")
            return {}

    def build(self) -> ft.Control:
        """
        Build the typography UI component.

        Returns:
            Built Flet control
        """
        return self.content if self.content else ft.Container()
