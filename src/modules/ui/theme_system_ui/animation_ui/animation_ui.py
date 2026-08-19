"""
Module: animation_ui
Description: Animation management and preview UI component for MikroDok application.
            Provides comprehensive animation system interface including timing controls,
            easing curve demonstrations, animation previews, and real-time testing
            capabilities. Integrates with theme system for consistent styling and supports
            Material Design 3 animation specifications with accessibility compliance.

Phase: 1
Location: /src/modules/ui/theme_system_ui/animation_ui/animation_ui.py
"""

# Standard library imports
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    AnimationConfig
)


class AnimationType(Enum):
    """Animation type enumeration for different animation categories."""
    FADE = "fade"
    SLIDE = "slide"
    SCALE = "scale"
    ROTATE = "rotate"
    BOUNCE = "bounce"
    ELASTIC = "elastic"
    THEME_TRANSITION = "theme_transition"


@dataclass
class AnimationDemo:
    """Animation demonstration configuration."""
    name: str
    animation_type: AnimationType
    duration: int
    easing: str
    description: str
    demo_element: Optional[ft.Control] = None


class AnimationUI(ThemeAwareUserControl):
    """
    Animation management and preview UI component.
    
    Provides comprehensive animation system interface including:
    - Animation timing controls and duration settings
    - Easing curve demonstrations with visual previews
    - Real-time animation testing and preview capabilities
    - Material Design 3 animation specifications
    - Accessibility-compliant animation settings
    - Reduced motion support and preferences
    """

    def __init__(self, **kwargs):
        """
        Initialize the animation UI component.
        
        Args:
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(**kwargs)
        
        # Initialize logger
        self._logger = logging.getLogger(__name__)
        
        # Animation state
        self._current_animation: Optional[AnimationDemo] = None
        self._is_playing: bool = False
        self._animation_callbacks: List[Callable] = []
        
        # UI components
        self._duration_slider: Optional[ft.Slider] = None
        self._easing_dropdown: Optional[ft.Dropdown] = None
        self._animation_selector: Optional[ft.Dropdown] = None
        self._preview_container: Optional[ft.Container] = None
        self._demo_element: Optional[ft.Container] = None
        self._play_button: Optional[ft.IconButton] = None
        self._reduced_motion_switch: Optional[ft.Switch] = None
        
        # Animation demonstrations
        self._animation_demos: List[AnimationDemo] = []
        
        # Initialize theme manager first
        self._ensure_theme_manager()
        self._ensure_responsive_manager()

        # Initialize component
        self._initialize_animations()
        self._build_component()

    def _initialize_animations(self) -> None:
        """Initialize animation demonstrations."""
        try:
            animation_config = self.get_animation_config()
            
            self._animation_demos = [
                AnimationDemo(
                    name="Fast Transition",
                    animation_type=AnimationType.FADE,
                    duration=animation_config.fast,
                    easing=animation_config.ease_standard,
                    description="Quick fade transition for immediate feedback"
                ),
                AnimationDemo(
                    name="Normal Transition",
                    animation_type=AnimationType.SLIDE,
                    duration=animation_config.normal,
                    easing=animation_config.ease_decelerate,
                    description="Standard slide animation for content changes"
                ),
                AnimationDemo(
                    name="Slow Transition",
                    animation_type=AnimationType.SCALE,
                    duration=animation_config.slow,
                    easing=animation_config.ease_accelerate_decelerate,
                    description="Deliberate scale animation for emphasis"
                ),
                AnimationDemo(
                    name="Bounce Effect",
                    animation_type=AnimationType.BOUNCE,
                    duration=animation_config.slower,
                    easing=animation_config.bounce,
                    description="Playful bounce animation for interactive elements"
                ),
                AnimationDemo(
                    name="Elastic Effect",
                    animation_type=AnimationType.ELASTIC,
                    duration=animation_config.slower,
                    easing=animation_config.elastic,
                    description="Elastic animation for dynamic interactions"
                ),
                AnimationDemo(
                    name="Theme Transition",
                    animation_type=AnimationType.THEME_TRANSITION,
                    duration=animation_config.theme_transition_duration,
                    easing=animation_config.theme_transition_easing,
                    description="Smooth theme switching animation"
                )
            ]
            
            # Set default animation
            if self._animation_demos:
                self._current_animation = self._animation_demos[0]
                
        except Exception as e:
            self._logger.error(f"Failed to initialize animations: {str(e)}")
            self._animation_demos = []

    def _build_component(self) -> None:
        """Build the animation UI component."""
        try:
            # Ensure theme manager is available
            self._ensure_theme_manager()
            self._ensure_responsive_manager()

            # Get theme components
            spacing = self.get_spacing()
            
            # Create main container with responsive layout
            self.content = self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        self._create_header(),
                        self._create_animation_controls(),
                        self._create_preview_section(),
                        self._create_easing_curves_section(),
                        self._create_accessibility_section()
                    ],
                    spacing=spacing.lg,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=spacing.lg
            )
            
        except Exception as e:
            self._logger.error(f"Failed to build animation UI: {str(e)}")
            self.content = ft.Text(f"Error building animation UI: {str(e)}")

    def _create_header(self) -> ft.Control:
        """Create the header section."""
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        return ft.Column(
            controls=[
                ft.Text(
                    "Animation System",
                    style=self.get_text_style("h1"),
                    weight=ft.FontWeight.W_600
                ),
                ft.Text(
                    "Configure and preview animation timing, easing curves, and motion design patterns",
                    style=self.get_text_style("body_medium"),
                    opacity=0.7
                )
            ],
            spacing=spacing.xs
        )

    def _create_animation_controls(self) -> ft.Control:
        """Create animation control section."""
        spacing = self.get_spacing()
        typography = self.get_typography()
        
        # Animation selector dropdown
        self._animation_selector = ft.Dropdown(
            label="Animation Type",
            options=[
                ft.dropdown.Option(key=str(i), text=demo.name)
                for i, demo in enumerate(self._animation_demos)
            ],
            value="0" if self._animation_demos else None,
            on_change=self._on_animation_changed,
            expand=True
        )
        
        # Duration slider
        self._duration_slider = ft.Slider(
            min=0,
            max=1000,
            value=self._current_animation.duration if self._current_animation else 200,
            label="Duration: {value}ms",
            on_change=self._on_duration_changed,
            expand=True
        )
        
        # Easing dropdown
        animation_config = self.get_animation_config()
        self._easing_dropdown = ft.Dropdown(
            label="Easing Curve",
            options=[
                ft.dropdown.Option(key="ease_standard", text="Standard"),
                ft.dropdown.Option(key="ease_decelerate", text="Decelerate"),
                ft.dropdown.Option(key="ease_accelerate", text="Accelerate"),
                ft.dropdown.Option(key="ease_accelerate_decelerate", text="Accelerate Decelerate"),
                ft.dropdown.Option(key="ease_in", text="Ease In"),
                ft.dropdown.Option(key="ease_out", text="Ease Out"),
                ft.dropdown.Option(key="ease_in_out", text="Ease In Out"),
                ft.dropdown.Option(key="bounce", text="Bounce"),
                ft.dropdown.Option(key="elastic", text="Elastic")
            ],
            value="ease_standard",
            on_change=self._on_easing_changed,
            expand=True
        )
        
        # Play button
        self._play_button = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            tooltip="Play Animation",
            on_click=self._on_play_animation
        )
        
        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Animation Controls",
                        style=self.get_text_style("h3"),
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Row(
                        controls=[
                            self._animation_selector,
                            self._play_button
                        ],
                        spacing=spacing.md
                    ),
                    ft.Text("Duration", style=self.get_text_style("label")),
                    self._duration_slider,
                    ft.Text("Easing Curve", style=self.get_text_style("label")),
                    self._easing_dropdown
                ],
                spacing=spacing.md
            ),
            padding=spacing.md
        )

    def _create_preview_section(self) -> ft.Control:
        """Create animation preview section."""
        spacing = self.get_spacing()
        typography = self.get_typography()
        colors = self.get_palette()

        # Create demo element for animation
        self._demo_element = ft.Container(
            content=ft.Icon(
                ft.Icons.ANIMATION,
                size=48,
                color=colors.primary
            ),
            width=80,
            height=80,
            border_radius=ft.border_radius.all(8),
            bgcolor=colors.surface_variant,
            alignment=ft.alignment.center
        )

        # Preview container
        self._preview_container = ft.Container(
            content=ft.Stack(
                controls=[self._demo_element],
                alignment=ft.alignment.center
            ),
            width=300,
            height=200,
            border=ft.border.all(1, colors.outline_variant),
            border_radius=ft.border_radius.all(8),
            bgcolor=colors.surface,
            alignment=ft.alignment.center
        )

        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Animation Preview",
                        style=self.get_text_style("h3")
                    ),
                    ft.Text(
                        "Watch the animation demonstration in real-time",
                        style=self.get_text_style("body_small"),
                        opacity=0.7
                    ),
                    ft.Row(
                        controls=[self._preview_container],
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                ],
                spacing=spacing.md,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.md
        )

    def _create_easing_curves_section(self) -> ft.Control:
        """Create easing curves demonstration section."""
        spacing = self.get_spacing()
        typography = self.get_typography()
        colors = self.get_palette()

        # Create easing curve examples
        easing_examples = [
            ("Linear", "linear", "Constant speed throughout"),
            ("Ease In", "ease-in", "Slow start, fast finish"),
            ("Ease Out", "ease-out", "Fast start, slow finish"),
            ("Ease In Out", "ease-in-out", "Slow start and finish"),
            ("Bounce", "bounce", "Bouncing effect at the end"),
            ("Elastic", "elastic", "Elastic spring effect")
        ]

        easing_cards = []
        for name, curve, description in easing_examples:
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                name,
                                style=self.get_text_style("h4")
                            ),
                            ft.Text(
                                description,
                                style=self.get_text_style("body_small"),
                                opacity=0.7
                            ),
                            ft.Container(
                                content=ft.Text(curve, style=self.get_text_style("caption")),
                                bgcolor=colors.surface_variant,
                                padding=ft.padding.all(spacing.xs),
                                border_radius=ft.border_radius.all(4)
                            )
                        ],
                        spacing=spacing.xs
                    ),
                    padding=spacing.md
                ),
                elevation=1
            )
            easing_cards.append(card)

        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Easing Curves",
                        style=self.get_text_style("h3")
                    ),
                    ft.Text(
                        "Different easing curves create various animation feels",
                        style=self.get_text_style("body_small"),
                        opacity=0.7
                    ),
                    ft.GridView(
                        controls=easing_cards,
                        runs_count=self.get_responsive_layout().get_breakpoint_value(1, 2, 3, 3),
                        spacing=spacing.md,
                        run_spacing=spacing.md,
                        child_aspect_ratio=1.2,
                        height=400
                    )
                ],
                spacing=spacing.md
            ),
            padding=spacing.md
        )

    def _create_accessibility_section(self) -> ft.Control:
        """Create accessibility settings section."""
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Reduced motion switch
        self._reduced_motion_switch = ft.Switch(
            label="Respect reduced motion preference",
            value=self.get_accessibility_manager().is_reduced_motion_enabled(),
            on_change=self._on_reduced_motion_changed
        )

        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Accessibility Settings",
                        style=self.get_text_style("h3")
                    ),
                    ft.Text(
                        "Configure animation accessibility preferences",
                        style=self.get_text_style("body_small"),
                        opacity=0.7
                    ),
                    self._reduced_motion_switch,
                    ft.Text(
                        "When enabled, animations will be disabled or significantly reduced for users who prefer reduced motion.",
                        style=self.get_text_style("body_small"),
                        opacity=0.6
                    )
                ],
                spacing=spacing.md
            ),
            padding=spacing.md
        )

    # Event Handlers
    def _on_animation_changed(self, e: ft.ControlEvent) -> None:
        """Handle animation type selection change."""
        try:
            if e.control.value is not None:
                index = int(e.control.value)
                if 0 <= index < len(self._animation_demos):
                    self._current_animation = self._animation_demos[index]

                    # Update controls to match selected animation
                    if self._duration_slider:
                        self._duration_slider.value = self._current_animation.duration

                    # Update the page
                    if self.page:
                        self.page.update()

        except Exception as ex:
            self._logger.error(f"Error changing animation: {str(ex)}")

    def _on_duration_changed(self, e: ft.ControlEvent) -> None:
        """Handle duration slider change."""
        try:
            if self._current_animation and e.control.value is not None:
                self._current_animation.duration = int(e.control.value)

        except Exception as ex:
            self._logger.error(f"Error changing duration: {str(ex)}")

    def _on_easing_changed(self, e: ft.ControlEvent) -> None:
        """Handle easing curve selection change."""
        try:
            if self._current_animation and e.control.value:
                animation_config = self.get_animation_config()
                easing_map = {
                    "ease_standard": animation_config.ease_standard,
                    "ease_decelerate": animation_config.ease_decelerate,
                    "ease_accelerate": animation_config.ease_accelerate,
                    "ease_accelerate_decelerate": animation_config.ease_accelerate_decelerate,
                    "ease_in": animation_config.ease_in,
                    "ease_out": animation_config.ease_out,
                    "ease_in_out": animation_config.ease_in_out,
                    "bounce": animation_config.bounce,
                    "elastic": animation_config.elastic
                }

                if e.control.value in easing_map:
                    self._current_animation.easing = easing_map[e.control.value]

        except Exception as ex:
            self._logger.error(f"Error changing easing: {str(ex)}")

    def _on_reduced_motion_changed(self, e: ft.ControlEvent) -> None:
        """Handle reduced motion preference change."""
        try:
            if e.control.value is not None:
                accessibility_manager = self.get_accessibility_manager()
                accessibility_manager.set_reduced_motion(e.control.value)

                # Update play button state
                if self._play_button:
                    self._play_button.disabled = e.control.value

                # Update the page
                if self.page:
                    self.page.update()

        except Exception as ex:
            self._logger.error(f"Error changing reduced motion: {str(ex)}")

    async def _on_play_animation(self, e: ft.ControlEvent) -> None:
        """Handle play animation button click."""
        try:
            if not self._current_animation or not self._demo_element:
                return

            if self._is_playing:
                return

            self._is_playing = True

            # Update button state
            if self._play_button:
                self._play_button.icon = ft.Icons.STOP
                self._play_button.tooltip = "Stop Animation"

            # Get animation duration (respect reduced motion)
            accessibility_manager = self.get_accessibility_manager()
            duration = accessibility_manager.get_reduced_motion_duration(self._current_animation.duration)

            # Perform animation based on type
            await self._perform_animation(self._current_animation.animation_type, duration)

            # Reset button state
            self._is_playing = False
            if self._play_button:
                self._play_button.icon = ft.Icons.PLAY_ARROW
                self._play_button.tooltip = "Play Animation"

            # Update the page
            if self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Error playing animation: {str(ex)}")
            self._is_playing = False

    async def _perform_animation(self, animation_type: AnimationType, duration: int) -> None:
        """Perform the specified animation."""
        try:
            if not self._demo_element or duration == 0:
                return

            # Simple animation demonstration without complex Flet animations
            if animation_type == AnimationType.FADE:
                # Fade animation
                self._demo_element.opacity = 0.3
                if self.page:
                    self.page.update()
                await asyncio.sleep(duration / 1000)
                self._demo_element.opacity = 1.0

            elif animation_type == AnimationType.SCALE:
                # Scale animation (simulate with size change)
                original_width = self._demo_element.width
                original_height = self._demo_element.height
                self._demo_element.width = int(original_width * 1.2)
                self._demo_element.height = int(original_height * 1.2)
                if self.page:
                    self.page.update()
                await asyncio.sleep(duration / 1000)
                self._demo_element.width = original_width
                self._demo_element.height = original_height

            elif animation_type == AnimationType.ROTATE:
                # Rotation animation (simulate with border radius change)
                self._demo_element.border_radius = ft.border_radius.all(40)
                if self.page:
                    self.page.update()
                await asyncio.sleep(duration / 1000)
                self._demo_element.border_radius = ft.border_radius.all(8)

            elif animation_type == AnimationType.SLIDE:
                # Slide animation (simulate with margin change)
                self._demo_element.margin = ft.margin.only(left=50)
                if self.page:
                    self.page.update()
                await asyncio.sleep(duration / 1000)
                self._demo_element.margin = ft.margin.all(0)

            # Update the page
            if self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Error performing animation: {str(ex)}")

    # Public Methods
    def get_animation_config(self) -> AnimationConfig:
        """Get the current animation configuration."""
        try:
            # Ensure theme manager is available
            self._ensure_theme_manager()
            if self._theme_manager:
                return self._theme_manager.get_animation_config()
            else:
                # Fallback to global theme manager
                theme_manager = get_theme_manager()
                return theme_manager.get_animation_config()
        except Exception as e:
            self._logger.error(f"Failed to get animation config: {str(e)}")
            return AnimationConfig()

    def add_animation_callback(self, callback: Callable) -> None:
        """Add callback for animation events."""
        if callback not in self._animation_callbacks:
            self._animation_callbacks.append(callback)

    def remove_animation_callback(self, callback: Callable) -> None:
        """Remove animation callback."""
        if callback in self._animation_callbacks:
            self._animation_callbacks.remove(callback)

    def get_current_animation(self) -> Optional[AnimationDemo]:
        """Get the currently selected animation."""
        return self._current_animation

    def set_animation_by_type(self, animation_type: AnimationType) -> None:
        """Set animation by type."""
        try:
            for i, demo in enumerate(self._animation_demos):
                if demo.animation_type == animation_type:
                    self._current_animation = demo
                    if self._animation_selector:
                        self._animation_selector.value = str(i)
                        if self.page:
                            self.page.update()
                    break
        except Exception as e:
            self._logger.error(f"Failed to set animation by type: {str(e)}")

    def refresh_animations(self) -> None:
        """Refresh animation demonstrations."""
        try:
            self._initialize_animations()
            self._build_component()
            if self.page:
                self.page.update()
        except Exception as e:
            self._logger.error(f"Failed to refresh animations: {str(e)}")
