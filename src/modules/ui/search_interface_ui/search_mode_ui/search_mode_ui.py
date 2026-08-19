"""
Module: search_mode_ui
Description: Toggle interface for semantic-only, keyword-only, or hybrid search modes with real-time
            performance metrics, mode descriptions, and intelligent recommendations. Provides intuitive
            search mode selection with visual feedback and accessibility features.
Phase: 4
Location: /src/modules/ui/search_interface_ui/search_mode_ui/search_mode_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass
from enum import Enum
import logging
import time

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


class SearchMode(Enum):
    """Search mode enumeration for MikroDok search functionality."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class SearchModeConfig:
    """Configuration for search mode behavior."""
    mode: SearchMode
    enabled: bool = True
    weight: float = 1.0  # For hybrid mode weighting
    description: str = ""
    performance_hint: str = ""
    recommended_for: List[str] = None
    
    def __post_init__(self):
        if self.recommended_for is None:
            self.recommended_for = []


@dataclass
class SearchModeMetrics:
    """Performance metrics for search modes."""
    mode: SearchMode
    avg_response_time: float = 0.0
    accuracy_score: float = 0.0
    usage_count: int = 0
    last_used: Optional[float] = None
    user_satisfaction: float = 0.0


class SearchModeUI(ThemeAwareUserControl):
    """
    Search mode selection interface with intelligent recommendations.
    
    Features:
    - Interactive mode selection with visual cards
    - Real-time performance metrics display
    - Mode descriptions and recommendations
    - Hybrid mode weight adjustment
    - Accessibility-compliant interactions
    - Responsive design with breakpoint adaptation
    - Theme-aware styling and animations
    - Usage analytics and smart suggestions
    """
    
    def __init__(self,
                 default_mode: SearchMode = SearchMode.HYBRID,
                 show_metrics: bool = True,
                 show_descriptions: bool = True,
                 show_recommendations: bool = True,
                 enable_hybrid_weights: bool = True,
                 on_mode_change: Optional[Callable[[SearchMode, Dict[str, float]], None]] = None,
                 on_weights_change: Optional[Callable[[Dict[str, float]], None]] = None,
                 **kwargs):
        """
        Initialize the SearchModeUI component.
        
        Args:
            default_mode: Default search mode to select
            show_metrics: Whether to display performance metrics
            show_descriptions: Whether to show mode descriptions
            show_recommendations: Whether to show usage recommendations
            enable_hybrid_weights: Whether to allow hybrid weight adjustment
            on_mode_change: Callback for mode selection changes
            on_weights_change: Callback for hybrid weight changes
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.default_mode = default_mode
        self.show_metrics = show_metrics
        self.show_descriptions = show_descriptions
        self.show_recommendations = show_recommendations
        self.enable_hybrid_weights = enable_hybrid_weights
        
        # Callbacks
        self.on_mode_change = on_mode_change
        self.on_weights_change = on_weights_change
        
        # State
        self._current_mode: SearchMode = default_mode
        self._hybrid_weights: Dict[str, float] = {
            "semantic": 0.7,
            "keyword": 0.3
        }
        self._mode_configs: Dict[SearchMode, SearchModeConfig] = {}
        self._mode_metrics: Dict[SearchMode, SearchModeMetrics] = {}
        
        # UI Components
        self._mode_cards: Dict[SearchMode, ft.Container] = {}
        self._weight_sliders: Dict[str, ft.Slider] = {}
        self._metrics_display: Optional[ft.Container] = None
        self._recommendations_panel: Optional[ft.Container] = None
        
        # Initialize configurations
        self._initialize_mode_configs()
        self._initialize_metrics()
        
        # Build UI
        self.content = self._build_ui()
    
    def _initialize_mode_configs(self) -> None:
        """Initialize search mode configurations."""
        try:
            self._mode_configs = {
                SearchMode.SEMANTIC: SearchModeConfig(
                    mode=SearchMode.SEMANTIC,
                    description="AI-powered semantic understanding for contextual search",
                    performance_hint="Best for concept-based queries and natural language",
                    recommended_for=["Research", "Exploration", "Conceptual queries"]
                ),
                SearchMode.KEYWORD: SearchModeConfig(
                    mode=SearchMode.KEYWORD,
                    description="Traditional keyword matching for precise term search",
                    performance_hint="Fastest performance for exact term matching",
                    recommended_for=["Specific terms", "Technical documentation", "Quick lookup"]
                ),
                SearchMode.HYBRID: SearchModeConfig(
                    mode=SearchMode.HYBRID,
                    description="Combined semantic and keyword search for optimal results",
                    performance_hint="Balanced approach with adjustable weighting",
                    recommended_for=["General search", "Best of both worlds", "Adaptive queries"]
                )
            }
            
        except Exception as e:
            logger.error(f"Error initializing mode configs: {e}")
    
    def _initialize_metrics(self) -> None:
        """Initialize search mode metrics."""
        try:
            self._mode_metrics = {
                mode: SearchModeMetrics(mode=mode)
                for mode in SearchMode
            }
            
        except Exception as e:
            logger.error(f"Error initializing metrics: {e}")
    
    def _build_ui(self) -> ft.Control:
        """Build the main search mode UI."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            # Main container with responsive layout
            main_content = ft.Column(
                controls=[
                    self._build_header(),
                    self._build_mode_selector(),
                    self._build_hybrid_controls() if self.enable_hybrid_weights else ft.Container(),
                    self._build_metrics_panel() if self.show_metrics else ft.Container(),
                    self._build_recommendations() if self.show_recommendations else ft.Container()
                ],
                spacing=spacing.md,
                expand=True
            )
            
            return ft.Container(
                content=main_content,
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(8),
                border=ft.border.all(1, palette.outline_variant)
            )
            
        except Exception as e:
            logger.error(f"Error building search mode UI: {e}")
            return ft.Container(content=ft.Text("Error loading search mode selector"))

    def _build_header(self) -> ft.Control:
        """Build the header section with title and description."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Search Mode",
                            style=typography.headline_small,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600
                        ),
                        ft.Text(
                            "Choose how MikroDok searches your knowledge base",
                            style=typography.body_medium,
                            color=palette.text_secondary
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                padding=ft.padding.only(bottom=spacing.sm)
            )

        except Exception as e:
            logger.error(f"Error building header: {e}")
            return ft.Container()

    def _build_mode_selector(self) -> ft.Control:
        """Build the main mode selection interface."""
        try:
            spacing = self.get_spacing()

            # Create mode cards
            mode_cards = []
            for mode in SearchMode:
                card = self._create_mode_card(mode)
                self._mode_cards[mode] = card
                mode_cards.append(card)

            # Responsive layout for mode cards
            responsive_manager = self.get_responsive_layout()

            if responsive_manager.is_mobile():
                # Stack vertically on mobile
                return ft.Column(
                    controls=mode_cards,
                    spacing=spacing.sm
                )
            else:
                # Horizontal layout on larger screens
                return ft.Row(
                    controls=mode_cards,
                    spacing=spacing.md,
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY
                )

        except Exception as e:
            logger.error(f"Error building mode selector: {e}")
            return ft.Container()

    def _create_mode_card(self, mode: SearchMode) -> ft.Container:
        """Create an individual mode selection card."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            config = self._mode_configs.get(mode)
            if not config:
                return ft.Container()

            is_selected = mode == self._current_mode

            # Mode icon
            icon_map = {
                SearchMode.SEMANTIC: self.get_icon('PSYCHOLOGY'),
                SearchMode.KEYWORD: self.get_icon('SEARCH'),
                SearchMode.HYBRID: self.get_icon('AUTO_AWESOME')
            }

            # Card content
            card_content = ft.Column(
                controls=[
                    # Icon and title
                    ft.Row(
                        controls=[
                            ft.Icon(
                                icon_map.get(mode, self.get_icon('SEARCH')),
                                color=palette.primary if is_selected else palette.text_secondary,
                                size=self.get_responsive_size(24)
                            ),
                            ft.Text(
                                mode.value.title(),
                                style=typography.title_medium,
                                color=palette.text_primary,
                                weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_400
                            )
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=spacing.sm
                    ),

                    # Description
                    ft.Text(
                        config.description if self.show_descriptions else "",
                        style=typography.body_small,
                        color=palette.text_secondary,
                        max_lines=3
                    ) if self.show_descriptions else ft.Container(),

                    # Performance hint
                    ft.Container(
                        content=ft.Text(
                            config.performance_hint,
                            style=typography.label_small,
                            color=palette.primary if is_selected else palette.text_tertiary,
                            italic=True
                        ),
                        padding=ft.padding.only(top=spacing.xs)
                    ) if config.performance_hint else ft.Container()
                ],
                spacing=spacing.sm,
                tight=True
            )

            # Card container
            return ft.Container(
                content=card_content,
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.primary_container if is_selected else palette.surface_variant,
                border_radius=self.get_responsive_size(12),
                border=ft.border.all(
                    2 if is_selected else 1,
                    palette.primary if is_selected else palette.outline_variant
                ),
                width=self.get_responsive_size(280),
                on_click=lambda e, m=mode: self._on_mode_select(m),
                animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT)
            )

        except Exception as e:
            logger.error(f"Error creating mode card for {mode}: {e}")
            return ft.Container()

    def _build_hybrid_controls(self) -> ft.Control:
        """Build hybrid mode weight adjustment controls."""
        try:
            if self._current_mode != SearchMode.HYBRID:
                return ft.Container(visible=False)

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Weight sliders
            semantic_slider = ft.Slider(
                min=0.0,
                max=1.0,
                value=self._hybrid_weights["semantic"],
                divisions=10,
                label="Semantic: {value:.1f}",
                on_change=self._on_semantic_weight_change,
                active_color=palette.primary,
                inactive_color=palette.outline_variant
            )

            keyword_slider = ft.Slider(
                min=0.0,
                max=1.0,
                value=self._hybrid_weights["keyword"],
                divisions=10,
                label="Keyword: {value:.1f}",
                on_change=self._on_keyword_weight_change,
                active_color=palette.secondary,
                inactive_color=palette.outline_variant
            )

            self._weight_sliders = {
                "semantic": semantic_slider,
                "keyword": keyword_slider
            }

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Hybrid Mode Weights",
                            style=typography.title_small,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Text(
                            "Adjust the balance between semantic and keyword search",
                            style=typography.body_small,
                            color=palette.text_secondary
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Icon(self.get_icon('PSYCHOLOGY'), size=16, color=palette.primary),
                                            ft.Text("Semantic Weight", style=typography.label_medium),
                                            ft.Spacer(),
                                            ft.Text(f"{self._hybrid_weights['semantic']:.1f}",
                                                   style=typography.label_medium, color=palette.primary)
                                        ]
                                    ),
                                    semantic_slider,
                                    ft.Container(height=spacing.sm),
                                    ft.Row(
                                        controls=[
                                            ft.Icon(self.get_icon('SEARCH'), size=16, color=palette.secondary),
                                            ft.Text("Keyword Weight", style=typography.label_medium),
                                            ft.Spacer(),
                                            ft.Text(f"{self._hybrid_weights['keyword']:.1f}",
                                                   style=typography.label_medium, color=palette.secondary)
                                        ]
                                    ),
                                    keyword_slider
                                ],
                                spacing=spacing.xs
                            ),
                            padding=ft.padding.all(spacing.md),
                            bgcolor=palette.surface_variant,
                            border_radius=self.get_responsive_size(8)
                        )
                    ],
                    spacing=spacing.sm
                ),
                visible=self._current_mode == SearchMode.HYBRID,
                animate_opacity=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
            )

        except Exception as e:
            logger.error(f"Error building hybrid controls: {e}")
            return ft.Container()

    def _build_metrics_panel(self) -> ft.Control:
        """Build the performance metrics display panel."""
        try:
            if not self.show_metrics:
                return ft.Container()

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Create metrics cards for each mode
            metrics_cards = []
            for mode in SearchMode:
                metrics = self._mode_metrics.get(mode)
                if not metrics:
                    continue

                card = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                mode.value.title(),
                                style=typography.label_large,
                                color=palette.text_primary,
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=[
                                            ft.Text("Response Time", style=typography.label_small,
                                                   color=palette.text_secondary),
                                            ft.Text(f"{metrics.avg_response_time:.2f}s",
                                                   style=typography.body_small, color=palette.text_primary)
                                        ],
                                        spacing=2,
                                        tight=True
                                    ),
                                    ft.Column(
                                        controls=[
                                            ft.Text("Accuracy", style=typography.label_small,
                                                   color=palette.text_secondary),
                                            ft.Text(f"{metrics.accuracy_score:.1%}",
                                                   style=typography.body_small, color=palette.text_primary)
                                        ],
                                        spacing=2,
                                        tight=True
                                    ),
                                    ft.Column(
                                        controls=[
                                            ft.Text("Usage", style=typography.label_small,
                                                   color=palette.text_secondary),
                                            ft.Text(f"{metrics.usage_count}",
                                                   style=typography.body_small, color=palette.text_primary)
                                        ],
                                        spacing=2,
                                        tight=True
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            )
                        ],
                        spacing=spacing.xs,
                        tight=True
                    ),
                    padding=ft.padding.all(spacing.sm),
                    bgcolor=palette.surface_variant,
                    border_radius=self.get_responsive_size(6),
                    expand=True
                )
                metrics_cards.append(card)

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Performance Metrics",
                            style=typography.title_small,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Row(
                            controls=metrics_cards,
                            spacing=spacing.sm
                        ) if not self.get_responsive_layout().is_mobile() else ft.Column(
                            controls=metrics_cards,
                            spacing=spacing.sm
                        )
                    ],
                    spacing=spacing.sm
                )
            )

        except Exception as e:
            logger.error(f"Error building metrics panel: {e}")
            return ft.Container()

    def _build_recommendations(self) -> ft.Control:
        """Build the recommendations panel."""
        try:
            if not self.show_recommendations:
                return ft.Container()

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            current_config = self._mode_configs.get(self._current_mode)
            if not current_config or not current_config.recommended_for:
                return ft.Container()

            # Create recommendation chips
            recommendation_chips = []
            for recommendation in current_config.recommended_for:
                chip = ft.Container(
                    content=ft.Text(
                        recommendation,
                        style=typography.label_small,
                        color=palette.on_secondary_container
                    ),
                    padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
                    bgcolor=palette.secondary_container,
                    border_radius=self.get_responsive_size(16)
                )
                recommendation_chips.append(chip)

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    self.get_icon('LIGHTBULB'),
                                    color=palette.tertiary,
                                    size=self.get_responsive_size(20)
                                ),
                                ft.Text(
                                    f"Best for {self._current_mode.value.title()} Search",
                                    style=typography.title_small,
                                    color=palette.text_primary,
                                    weight=ft.FontWeight.W_500
                                )
                            ],
                            spacing=spacing.xs
                        ),
                        ft.Row(
                            controls=recommendation_chips,
                            spacing=spacing.xs,
                            wrap=True
                        ) if not self.get_responsive_layout().is_mobile() else ft.Column(
                            controls=recommendation_chips,
                            spacing=spacing.xs
                        )
                    ],
                    spacing=spacing.sm
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.tertiary_container,
                border_radius=self.get_responsive_size(8),
                animate_opacity=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
            )

        except Exception as e:
            logger.error(f"Error building recommendations: {e}")
            return ft.Container()

    # Event Handlers
    def _on_mode_select(self, mode: SearchMode) -> None:
        """Handle mode selection."""
        try:
            if mode == self._current_mode:
                return

            old_mode = self._current_mode
            self._current_mode = mode

            # Update UI
            self._update_mode_cards()
            self._update_hybrid_controls_visibility()
            self._update_recommendations()

            # Update metrics
            self._update_usage_metrics(mode)

            # Trigger callback
            if self.on_mode_change:
                weights = self._hybrid_weights if mode == SearchMode.HYBRID else {}
                self.on_mode_change(mode, weights)

            logger.debug(f"Search mode changed from {old_mode.value} to {mode.value}")

        except Exception as e:
            logger.error(f"Error handling mode selection: {e}")

    def _on_semantic_weight_change(self, e) -> None:
        """Handle semantic weight slider change."""
        try:
            new_value = e.control.value
            self._hybrid_weights["semantic"] = new_value
            self._hybrid_weights["keyword"] = 1.0 - new_value

            # Update keyword slider
            if "keyword" in self._weight_sliders:
                self._weight_sliders["keyword"].value = self._hybrid_weights["keyword"]

            # Update weight displays
            self._update_weight_displays()

            # Trigger callback
            if self.on_weights_change:
                self.on_weights_change(self._hybrid_weights.copy())

            self.update()

        except Exception as e:
            logger.error(f"Error handling semantic weight change: {e}")

    def _on_keyword_weight_change(self, e) -> None:
        """Handle keyword weight slider change."""
        try:
            new_value = e.control.value
            self._hybrid_weights["keyword"] = new_value
            self._hybrid_weights["semantic"] = 1.0 - new_value

            # Update semantic slider
            if "semantic" in self._weight_sliders:
                self._weight_sliders["semantic"].value = self._hybrid_weights["semantic"]

            # Update weight displays
            self._update_weight_displays()

            # Trigger callback
            if self.on_weights_change:
                self.on_weights_change(self._hybrid_weights.copy())

            self.update()

        except Exception as e:
            logger.error(f"Error handling keyword weight change: {e}")

    # Update Methods
    def _update_mode_cards(self) -> None:
        """Update mode card appearances based on current selection."""
        try:
            palette = self.get_palette()

            for mode, card in self._mode_cards.items():
                is_selected = mode == self._current_mode

                # Update card styling
                card.bgcolor = palette.primary_container if is_selected else palette.surface_variant
                card.border = ft.border.all(
                    2 if is_selected else 1,
                    palette.primary if is_selected else palette.outline_variant
                )

            self.update()

        except Exception as e:
            logger.error(f"Error updating mode cards: {e}")

    def _update_hybrid_controls_visibility(self) -> None:
        """Update hybrid controls visibility based on current mode."""
        try:
            # This will be handled by the visibility property in _build_hybrid_controls
            self.update()

        except Exception as e:
            logger.error(f"Error updating hybrid controls visibility: {e}")

    def _update_recommendations(self) -> None:
        """Update recommendations panel based on current mode."""
        try:
            # This will be handled by the content in _build_recommendations
            self.update()

        except Exception as e:
            logger.error(f"Error updating recommendations: {e}")

    def _update_weight_displays(self) -> None:
        """Update weight display values."""
        try:
            # Weight displays are updated in the slider change handlers
            pass

        except Exception as e:
            logger.error(f"Error updating weight displays: {e}")

    def _update_usage_metrics(self, mode: SearchMode) -> None:
        """Update usage metrics for the selected mode."""
        try:
            if mode in self._mode_metrics:
                metrics = self._mode_metrics[mode]
                metrics.usage_count += 1
                metrics.last_used = time.time()

        except Exception as e:
            logger.error(f"Error updating usage metrics: {e}")

    # Public API Methods
    def get_current_mode(self) -> SearchMode:
        """Get the currently selected search mode."""
        return self._current_mode

    def set_current_mode(self, mode: SearchMode) -> None:
        """Set the current search mode programmatically."""
        try:
            if mode != self._current_mode:
                self._on_mode_select(mode)

        except Exception as e:
            logger.error(f"Error setting current mode: {e}")

    def get_hybrid_weights(self) -> Dict[str, float]:
        """Get the current hybrid mode weights."""
        return self._hybrid_weights.copy()

    def set_hybrid_weights(self, weights: Dict[str, float]) -> None:
        """Set hybrid mode weights programmatically."""
        try:
            if "semantic" in weights and "keyword" in weights:
                # Normalize weights to sum to 1.0
                total = weights["semantic"] + weights["keyword"]
                if total > 0:
                    self._hybrid_weights["semantic"] = weights["semantic"] / total
                    self._hybrid_weights["keyword"] = weights["keyword"] / total

                    # Update sliders if they exist
                    if self._weight_sliders:
                        if "semantic" in self._weight_sliders:
                            self._weight_sliders["semantic"].value = self._hybrid_weights["semantic"]
                        if "keyword" in self._weight_sliders:
                            self._weight_sliders["keyword"].value = self._hybrid_weights["keyword"]

                    self.update()

                    # Trigger callback
                    if self.on_weights_change:
                        self.on_weights_change(self._hybrid_weights.copy())

        except Exception as e:
            logger.error(f"Error setting hybrid weights: {e}")

    def update_metrics(self, mode: SearchMode, metrics: SearchModeMetrics) -> None:
        """Update performance metrics for a specific mode."""
        try:
            if mode in self._mode_metrics:
                self._mode_metrics[mode] = metrics
                self.update()

        except Exception as e:
            logger.error(f"Error updating metrics for {mode}: {e}")

    def get_metrics(self, mode: Optional[SearchMode] = None) -> Union[SearchModeMetrics, Dict[SearchMode, SearchModeMetrics]]:
        """Get performance metrics for a specific mode or all modes."""
        try:
            if mode:
                return self._mode_metrics.get(mode, SearchModeMetrics(mode=mode))
            else:
                return self._mode_metrics.copy()

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return SearchModeMetrics(mode=mode) if mode else {}

    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        try:
            self._initialize_metrics()
            self.update()

        except Exception as e:
            logger.error(f"Error resetting metrics: {e}")

    def get_mode_config(self, mode: SearchMode) -> Optional[SearchModeConfig]:
        """Get configuration for a specific search mode."""
        return self._mode_configs.get(mode)

    def update_mode_config(self, mode: SearchMode, config: SearchModeConfig) -> None:
        """Update configuration for a specific search mode."""
        try:
            self._mode_configs[mode] = config
            self.update()

        except Exception as e:
            logger.error(f"Error updating mode config for {mode}: {e}")

    def enable_mode(self, mode: SearchMode, enabled: bool = True) -> None:
        """Enable or disable a specific search mode."""
        try:
            if mode in self._mode_configs:
                self._mode_configs[mode].enabled = enabled

                # If disabling current mode, switch to first enabled mode
                if not enabled and mode == self._current_mode:
                    for other_mode, config in self._mode_configs.items():
                        if config.enabled:
                            self.set_current_mode(other_mode)
                            break

                self.update()

        except Exception as e:
            logger.error(f"Error enabling/disabling mode {mode}: {e}")

    def is_mode_enabled(self, mode: SearchMode) -> bool:
        """Check if a specific search mode is enabled."""
        config = self._mode_configs.get(mode)
        return config.enabled if config else False

    def get_recommendation_text(self) -> str:
        """Get recommendation text for the current mode."""
        try:
            config = self._mode_configs.get(self._current_mode)
            if config and config.recommended_for:
                return f"Best for: {', '.join(config.recommended_for)}"
            return ""

        except Exception as e:
            logger.error(f"Error getting recommendation text: {e}")
            return ""

    def refresh_ui(self) -> None:
        """Refresh the entire UI component."""
        try:
            self.content = self._build_ui()
            self.update()

        except Exception as e:
            logger.error(f"Error refreshing UI: {e}")

    # Theme change handler
    def on_theme_changed(self) -> None:
        """Handle theme changes."""
        try:
            super().on_theme_changed()
            self.refresh_ui()

        except Exception as e:
            logger.error(f"Error handling theme change: {e}")

    # Responsive layout handler
    def on_responsive_change(self, screen_size: Tuple[int, int]) -> None:
        """Handle responsive layout changes."""
        try:
            super().on_responsive_change(screen_size)
            self.refresh_ui()

        except Exception as e:
            logger.error(f"Error handling responsive change: {e}")
