"""
Module: refresh_rate_ui
Description: Controls for adjusting monitoring update frequencies and data retention periods.
            Provides comprehensive refresh rate management with real-time validation, preset configurations,
            and theme-aware responsive design for optimal monitoring performance.
Phase: 2
Location: /src/modules/ui/monitoring_controls_ui/refresh_rate_ui/refresh_rate_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Optional database imports
try:
    from src.modules.database.resource_monitoring_db.monitoring_metrics_db.monitoring_metrics_db import MonitoringMetricsDB
    from src.modules.database.app_state_db.user_preferences_db.user_preferences_db import UserPreferencesDB
    DATABASE_AVAILABLE = True
except ImportError:
    MonitoringMetricsDB = None
    UserPreferencesDB = None
    DATABASE_AVAILABLE = False


class RefreshRatePreset(Enum):
    """Predefined refresh rate presets."""
    REAL_TIME = "real_time"
    HIGH_FREQUENCY = "high_frequency"
    STANDARD = "standard"
    POWER_SAVING = "power_saving"
    CUSTOM = "custom"


@dataclass
class RefreshRateConfiguration:
    """Configuration for refresh rate settings."""
    preset: RefreshRatePreset = RefreshRatePreset.STANDARD
    refresh_interval_seconds: float = 1.0
    data_retention_minutes: int = 60
    auto_adjust_enabled: bool = False
    performance_mode: bool = False
    batch_updates: bool = True
    max_history_points: int = 1000
    enable_adaptive_rate: bool = False
    min_refresh_rate: float = 0.1
    max_refresh_rate: float = 10.0


@dataclass
class RefreshRateMetrics:
    """Metrics for refresh rate performance."""
    current_rate: float
    target_rate: float
    actual_update_time: float
    missed_updates: int
    performance_impact: float
    memory_usage_mb: float
    cpu_usage_percent: float
    last_update: datetime


class RefreshRateUI(ThemeAwareUserControl):
    """
    Refresh rate configuration UI component.
    
    Provides comprehensive refresh rate management with:
    - Interactive refresh rate controls with real-time preview
    - Preset configuration templates for different use cases
    - Data retention period management
    - Performance impact visualization
    - Auto-adjustment based on system performance
    - Theme-aware responsive design
    - Integration with monitoring databases
    """

    def __init__(self,
                 config: Optional[RefreshRateConfiguration] = None,
                 on_config_change: Optional[Callable[[RefreshRateConfiguration], None]] = None,
                 on_preset_change: Optional[Callable[[RefreshRatePreset], None]] = None,
                 show_performance_metrics: bool = True,
                 enable_advanced_settings: bool = True,
                 monitoring_metrics_db: Optional[Any] = None,
                 user_preferences_db: Optional[Any] = None,
                 **kwargs):
        """
        Initialize the RefreshRateUI component.
        
        Args:
            config: Initial refresh rate configuration
            on_config_change: Callback for configuration changes
            on_preset_change: Callback for preset changes
            show_performance_metrics: Whether to show performance impact metrics
            enable_advanced_settings: Whether to show advanced configuration options
            monitoring_metrics_db: Database for storing monitoring metrics
            user_preferences_db: Database for storing user preferences
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or RefreshRateConfiguration()
        self._original_config = RefreshRateConfiguration(**self._config.__dict__)
        
        # Callbacks
        self._on_config_change = on_config_change
        self._on_preset_change = on_preset_change
        
        # Settings
        self._show_performance_metrics = show_performance_metrics
        self._enable_advanced_settings = enable_advanced_settings
        
        # Database connections
        self._monitoring_metrics_db = monitoring_metrics_db
        self._user_preferences_db = user_preferences_db
        
        # UI components
        self._preset_dropdown: Optional[ft.Dropdown] = None
        self._refresh_rate_slider: Optional[ft.Slider] = None
        self._refresh_rate_input: Optional[ft.TextField] = None
        self._retention_slider: Optional[ft.Slider] = None
        self._retention_input: Optional[ft.TextField] = None
        self._auto_adjust_switch: Optional[ft.Switch] = None
        self._performance_switch: Optional[ft.Switch] = None
        self._batch_updates_switch: Optional[ft.Switch] = None
        self._adaptive_rate_switch: Optional[ft.Switch] = None
        
        # Performance metrics
        self._current_metrics: Optional[RefreshRateMetrics] = None
        self._metrics_display: Optional[ft.Container] = None
        self._performance_chart: Optional[ft.Container] = None
        
        # Control buttons
        self._apply_button: Optional[ft.ElevatedButton] = None
        self._reset_button: Optional[ft.OutlinedButton] = None
        self._save_preset_button: Optional[ft.OutlinedButton] = None
        
        # Monitoring
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Preset definitions
        self._preset_configs = self._initialize_preset_configs()
        
        # Build component
        self._build_component()

    def _initialize_preset_configs(self) -> Dict[RefreshRatePreset, RefreshRateConfiguration]:
        """Initialize predefined refresh rate configurations."""
        return {
            RefreshRatePreset.REAL_TIME: RefreshRateConfiguration(
                preset=RefreshRatePreset.REAL_TIME,
                refresh_interval_seconds=0.1,
                data_retention_minutes=30,
                auto_adjust_enabled=False,
                performance_mode=True,
                batch_updates=False,
                max_history_points=500,
                enable_adaptive_rate=False
            ),
            RefreshRatePreset.HIGH_FREQUENCY: RefreshRateConfiguration(
                preset=RefreshRatePreset.HIGH_FREQUENCY,
                refresh_interval_seconds=0.5,
                data_retention_minutes=60,
                auto_adjust_enabled=True,
                performance_mode=True,
                batch_updates=True,
                max_history_points=1000,
                enable_adaptive_rate=True
            ),
            RefreshRatePreset.STANDARD: RefreshRateConfiguration(
                preset=RefreshRatePreset.STANDARD,
                refresh_interval_seconds=1.0,
                data_retention_minutes=120,
                auto_adjust_enabled=True,
                performance_mode=False,
                batch_updates=True,
                max_history_points=1500,
                enable_adaptive_rate=True
            ),
            RefreshRatePreset.POWER_SAVING: RefreshRateConfiguration(
                preset=RefreshRatePreset.POWER_SAVING,
                refresh_interval_seconds=5.0,
                data_retention_minutes=240,
                auto_adjust_enabled=True,
                performance_mode=False,
                batch_updates=True,
                max_history_points=2000,
                enable_adaptive_rate=False
            )
        }

    def _build_component(self) -> None:
        """Build the refresh rate configuration component."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            
            # Create main sections
            header_section = self._create_header_section()
            preset_section = self._create_preset_section()
            rate_controls_section = self._create_rate_controls_section()
            retention_section = self._create_retention_section()
            
            sections = [header_section, preset_section, rate_controls_section, retention_section]
            
            # Add advanced settings if enabled
            if self._enable_advanced_settings:
                advanced_section = self._create_advanced_settings_section()
                sections.append(advanced_section)
            
            # Add performance metrics if enabled
            if self._show_performance_metrics:
                metrics_section = self._create_performance_metrics_section()
                sections.append(metrics_section)
            
            # Add control buttons
            controls_section = self._create_controls_section()
            sections.append(controls_section)
            
            # Create responsive container
            self.content = self.create_responsive_container(
                content=ft.Column(
                    controls=sections,
                    spacing=self.get_breakpoint_value(
                        mobile=16, tablet=20, desktop=24, large=28
                    ),
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                ),
                padding=self.get_responsive_padding()
            )
            
        except Exception as e:
            # Create error display
            self.content = ft.Container(
                content=ft.Text(
                    f"Error building refresh rate UI: {str(e)}",
                    color=self.get_palette().error,
                    size=self.get_typography().body_medium[0]
                ),
                padding=ft.padding.all(self.get_spacing().lg)
            )

    def _create_header_section(self) -> ft.Control:
        """Create the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Refresh Rate Configuration",
                    size=typography.headline_small[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Configure monitoring update frequencies and data retention settings",
                    size=typography.body_medium[0],
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            padding=ft.padding.only(bottom=spacing.md)
        )

    def _create_preset_section(self) -> ft.Control:
        """Create the preset selection section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Preset dropdown
        self._preset_dropdown = ft.Dropdown(
            label="Refresh Rate Preset",
            value=self._config.preset.value,
            options=[
                ft.dropdown.Option("real_time", "Real-time (0.1s)"),
                ft.dropdown.Option("high_frequency", "High Frequency (0.5s)"),
                ft.dropdown.Option("standard", "Standard (1.0s)"),
                ft.dropdown.Option("power_saving", "Power Saving (5.0s)"),
                ft.dropdown.Option("custom", "Custom Configuration")
            ],
            on_change=self._on_preset_change_handler,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            expand=True
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Preset Configuration",
                    size=typography.title_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary
                ),
                self._preset_dropdown
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.borders)
        )

    def _create_rate_controls_section(self) -> ft.Control:
        """Create the refresh rate controls section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Refresh rate slider
        self._refresh_rate_slider = ft.Slider(
            min=0.1,
            max=10.0,
            value=self._config.refresh_interval_seconds,
            divisions=99,
            label=f"{self._config.refresh_interval_seconds:.1f}s",
            on_change=self._on_refresh_rate_slider_change,
            active_color=palette.primary,
            inactive_color=palette.surface_variant,
            thumb_color=palette.primary
        )

        # Refresh rate input field
        self._refresh_rate_input = ft.TextField(
            label="Refresh Rate (seconds)",
            value=str(self._config.refresh_interval_seconds),
            suffix_text="seconds",
            on_change=self._on_refresh_rate_input_change,
            on_blur=self._validate_refresh_rate_input,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            width=self.get_breakpoint_value(
                mobile=120, tablet=140, desktop=160, large=180
            )
        )

        # Rate display
        rate_display = ft.Container(
            content=ft.Column([
                ft.Text(
                    f"{1.0 / self._config.refresh_interval_seconds:.1f} Hz",
                    size=typography.headline_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.primary
                ),
                ft.Text(
                    "Updates per second",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            width=self.get_breakpoint_value(
                mobile=100, tablet=120, desktop=140, large=160
            )
        )

        # Create responsive layout
        controls_row = self.create_responsive_row(
            controls=[self._refresh_rate_input, rate_display],
            mobile_wrap=True,
            spacing=spacing.md
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Refresh Rate",
                    size=typography.title_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary
                ),
                self._refresh_rate_slider,
                controls_row
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.borders)
        )

    def _create_retention_section(self) -> ft.Control:
        """Create the data retention controls section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Retention slider
        self._retention_slider = ft.Slider(
            min=5,
            max=1440,  # 24 hours
            value=self._config.data_retention_minutes,
            divisions=287,
            label=f"{self._config.data_retention_minutes} min",
            on_change=self._on_retention_slider_change,
            active_color=palette.primary,
            inactive_color=palette.surface_variant,
            thumb_color=palette.primary
        )

        # Retention input field
        self._retention_input = ft.TextField(
            label="Data Retention (minutes)",
            value=str(self._config.data_retention_minutes),
            suffix_text="minutes",
            on_change=self._on_retention_input_change,
            on_blur=self._validate_retention_input,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            width=self.get_breakpoint_value(
                mobile=140, tablet=160, desktop=180, large=200
            )
        )

        # Retention display
        hours = self._config.data_retention_minutes / 60
        retention_display = ft.Container(
            content=ft.Column([
                ft.Text(
                    f"{hours:.1f}h" if hours >= 1 else f"{self._config.data_retention_minutes}m",
                    size=typography.headline_medium[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.secondary
                ),
                ft.Text(
                    "Data retention",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            width=self.get_breakpoint_value(
                mobile=100, tablet=120, desktop=140, large=160
            )
        )

        # Create responsive layout
        controls_row = self.create_responsive_row(
            controls=[self._retention_input, retention_display],
            mobile_wrap=True,
            spacing=spacing.md
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Data Retention",
                    size=typography.title_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary
                ),
                self._retention_slider,
                controls_row
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.borders)
        )

    def _create_advanced_settings_section(self) -> ft.Control:
        """Create the advanced settings section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Auto-adjust switch
        self._auto_adjust_switch = ft.Switch(
            label="Auto-adjust refresh rate",
            value=self._config.auto_adjust_enabled,
            on_change=self._on_auto_adjust_change,
            active_color=palette.primary
        )

        # Performance mode switch
        self._performance_switch = ft.Switch(
            label="Performance mode",
            value=self._config.performance_mode,
            on_change=self._on_performance_mode_change,
            active_color=palette.primary
        )

        # Batch updates switch
        self._batch_updates_switch = ft.Switch(
            label="Batch updates",
            value=self._config.batch_updates,
            on_change=self._on_batch_updates_change,
            active_color=palette.primary
        )

        # Adaptive rate switch
        self._adaptive_rate_switch = ft.Switch(
            label="Adaptive refresh rate",
            value=self._config.enable_adaptive_rate,
            on_change=self._on_adaptive_rate_change,
            active_color=palette.primary
        )

        # Create responsive grid for switches
        switches_grid = self.create_responsive_grid(
            children=[
                self._auto_adjust_switch,
                self._performance_switch,
                self._batch_updates_switch,
                self._adaptive_rate_switch
            ],
            mobile_cols=1,
            tablet_cols=2,
            desktop_cols=2,
            large_cols=2,
            spacing=spacing.sm
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Advanced Settings",
                    size=typography.title_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary
                ),
                switches_grid
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.borders)
        )

    def _create_performance_metrics_section(self) -> ft.Control:
        """Create the performance metrics section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Initialize metrics if not available
        if not self._current_metrics:
            self._current_metrics = RefreshRateMetrics(
                current_rate=self._config.refresh_interval_seconds,
                target_rate=self._config.refresh_interval_seconds,
                actual_update_time=0.0,
                missed_updates=0,
                performance_impact=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                last_update=datetime.now()
            )

        # Create metric cards
        metric_cards = []

        # Current rate card
        current_rate_card = ft.Container(
            content=ft.Column([
                ft.Text(
                    f"{1.0 / self._current_metrics.current_rate:.1f}",
                    size=typography.headline_small[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.primary
                ),
                ft.Text(
                    "Current Hz",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(spacing.xs),
            expand=True
        )
        metric_cards.append(current_rate_card)

        # Performance impact card
        impact_color = palette.success if self._current_metrics.performance_impact < 5.0 else \
                     palette.warning if self._current_metrics.performance_impact < 15.0 else palette.error

        impact_card = ft.Container(
            content=ft.Column([
                ft.Text(
                    f"{self._current_metrics.performance_impact:.1f}%",
                    size=typography.headline_small[0],
                    weight=ft.FontWeight.W_600,
                    color=impact_color
                ),
                ft.Text(
                    "CPU Impact",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(spacing.xs),
            expand=True
        )
        metric_cards.append(impact_card)

        # Memory usage card
        memory_card = ft.Container(
            content=ft.Column([
                ft.Text(
                    f"{self._current_metrics.memory_usage_mb:.1f}",
                    size=typography.headline_small[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.secondary
                ),
                ft.Text(
                    "Memory MB",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(spacing.xs),
            expand=True
        )
        metric_cards.append(memory_card)

        # Missed updates card
        missed_color = palette.success if self._current_metrics.missed_updates == 0 else \
                     palette.warning if self._current_metrics.missed_updates < 5 else palette.error

        missed_card = ft.Container(
            content=ft.Column([
                ft.Text(
                    str(self._current_metrics.missed_updates),
                    size=typography.headline_small[0],
                    weight=ft.FontWeight.W_600,
                    color=missed_color
                ),
                ft.Text(
                    "Missed Updates",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(spacing.xs),
            expand=True
        )
        metric_cards.append(missed_card)

        # Create responsive grid for metrics
        metrics_grid = self.create_responsive_grid(
            children=metric_cards,
            mobile_cols=2,
            tablet_cols=4,
            desktop_cols=4,
            large_cols=4,
            spacing=spacing.sm
        )

        self._metrics_display = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Performance Metrics",
                    size=typography.title_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary
                ),
                metrics_grid
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.borders)
        )

        return self._metrics_display

    def _create_controls_section(self) -> ft.Control:
        """Create the control buttons section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Apply button
        self._apply_button = ft.ElevatedButton(
            text="Apply Changes",
            icon=self.get_icon('CHECK'),
            on_click=self._apply_changes,
            bgcolor=palette.primary,
            color=palette.text_primary,
            disabled=not self._has_changes()
        )

        # Reset button
        self._reset_button = ft.OutlinedButton(
            text="Reset",
            icon=self.get_icon('REFRESH'),
            on_click=self._reset_changes,
            color=palette.text_secondary
        )

        # Save preset button
        self._save_preset_button = ft.OutlinedButton(
            text="Save as Preset",
            icon=self.get_icon('SAVE'),
            on_click=self._save_as_preset,
            color=palette.text_secondary
        )

        # Create responsive button layout
        return self.create_responsive_container(
            content=self.create_responsive_row(
                controls=[
                    self._apply_button,
                    self._reset_button,
                    self._save_preset_button
                ],
                mobile_wrap=True,
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=ft.padding.all(spacing.md)
        )

    # Event Handlers
    def _on_preset_change_handler(self, e) -> None:
        """Handle preset selection change."""
        try:
            preset_value = e.control.value
            preset = RefreshRatePreset(preset_value)

            if preset != RefreshRatePreset.CUSTOM:
                # Apply preset configuration
                preset_config = self._preset_configs[preset]
                self._config = RefreshRateConfiguration(**preset_config.__dict__)
                self._update_ui_from_config()

            # Update preset in config
            self._config.preset = preset

            # Trigger callback
            if self._on_preset_change:
                self._on_preset_change(preset)

            # Update apply button state
            self._update_apply_button_state()

        except (ValueError, KeyError) as e:
            pass

    def _on_refresh_rate_slider_change(self, e) -> None:
        """Handle refresh rate slider change."""
        try:
            new_rate = float(e.control.value)
            self._config.refresh_interval_seconds = new_rate
            self._config.preset = RefreshRatePreset.CUSTOM

            # Update UI components
            if self._refresh_rate_input:
                self._refresh_rate_input.value = f"{new_rate:.1f}"

            if self._preset_dropdown:
                self._preset_dropdown.value = "custom"

            # Update slider label
            e.control.label = f"{new_rate:.1f}s"

            # Update rate display and apply button
            self._update_rate_display()
            self._update_apply_button_state()
            self.update()

        except ValueError:
            pass

    def _on_refresh_rate_input_change(self, e) -> None:
        """Handle refresh rate input field change."""
        try:
            new_rate = float(e.control.value)
            if 0.1 <= new_rate <= 10.0:
                self._config.refresh_interval_seconds = new_rate
                self._config.preset = RefreshRatePreset.CUSTOM

                # Update slider and preset
                if self._refresh_rate_slider:
                    self._refresh_rate_slider.value = new_rate
                    self._refresh_rate_slider.label = f"{new_rate:.1f}s"

                if self._preset_dropdown:
                    self._preset_dropdown.value = "custom"

                # Update displays
                self._update_rate_display()
                self._update_apply_button_state()
                self.update()

        except ValueError:
            pass

    def _validate_refresh_rate_input(self, e) -> None:
        """Validate refresh rate input on blur."""
        try:
            value = float(e.control.value)
            if value < 0.1:
                e.control.value = "0.1"
                self._config.refresh_interval_seconds = 0.1
            elif value > 10.0:
                e.control.value = "10.0"
                self._config.refresh_interval_seconds = 10.0
            else:
                self._config.refresh_interval_seconds = value

            self._config.preset = RefreshRatePreset.CUSTOM
            self._update_ui_from_config()

        except ValueError:
            # Reset to current config value
            e.control.value = str(self._config.refresh_interval_seconds)

        self.update()

    def _on_retention_slider_change(self, e) -> None:
        """Handle data retention slider change."""
        try:
            new_retention = int(e.control.value)
            self._config.data_retention_minutes = new_retention
            self._config.preset = RefreshRatePreset.CUSTOM

            # Update UI components
            if self._retention_input:
                self._retention_input.value = str(new_retention)

            if self._preset_dropdown:
                self._preset_dropdown.value = "custom"

            # Update slider label
            e.control.label = f"{new_retention} min"

            # Update retention display and apply button
            self._update_retention_display()
            self._update_apply_button_state()
            self.update()

        except ValueError:
            pass

    def _on_retention_input_change(self, e) -> None:
        """Handle retention input field change."""
        try:
            new_retention = int(e.control.value)
            if 5 <= new_retention <= 1440:
                self._config.data_retention_minutes = new_retention
                self._config.preset = RefreshRatePreset.CUSTOM

                # Update slider and preset
                if self._retention_slider:
                    self._retention_slider.value = new_retention
                    self._retention_slider.label = f"{new_retention} min"

                if self._preset_dropdown:
                    self._preset_dropdown.value = "custom"

                # Update displays
                self._update_retention_display()
                self._update_apply_button_state()
                self.update()

        except ValueError:
            pass

    def _validate_retention_input(self, e) -> None:
        """Validate retention input on blur."""
        try:
            value = int(e.control.value)
            if value < 5:
                e.control.value = "5"
                self._config.data_retention_minutes = 5
            elif value > 1440:
                e.control.value = "1440"
                self._config.data_retention_minutes = 1440
            else:
                self._config.data_retention_minutes = value

            self._config.preset = RefreshRatePreset.CUSTOM
            self._update_ui_from_config()

        except ValueError:
            # Reset to current config value
            e.control.value = str(self._config.data_retention_minutes)

        self.update()

    def _on_auto_adjust_change(self, e) -> None:
        """Handle auto-adjust switch change."""
        self._config.auto_adjust_enabled = e.control.value
        self._config.preset = RefreshRatePreset.CUSTOM
        if self._preset_dropdown:
            self._preset_dropdown.value = "custom"
        self._update_apply_button_state()

    def _on_performance_mode_change(self, e) -> None:
        """Handle performance mode switch change."""
        self._config.performance_mode = e.control.value
        self._config.preset = RefreshRatePreset.CUSTOM
        if self._preset_dropdown:
            self._preset_dropdown.value = "custom"
        self._update_apply_button_state()

    def _on_batch_updates_change(self, e) -> None:
        """Handle batch updates switch change."""
        self._config.batch_updates = e.control.value
        self._config.preset = RefreshRatePreset.CUSTOM
        if self._preset_dropdown:
            self._preset_dropdown.value = "custom"
        self._update_apply_button_state()

    def _on_adaptive_rate_change(self, e) -> None:
        """Handle adaptive rate switch change."""
        self._config.enable_adaptive_rate = e.control.value
        self._config.preset = RefreshRatePreset.CUSTOM
        if self._preset_dropdown:
            self._preset_dropdown.value = "custom"
        self._update_apply_button_state()

    def _apply_changes(self, e) -> None:
        """Apply configuration changes."""
        try:
            # Save configuration to database if available
            if self._user_preferences_db:
                self._save_config_to_database()

            # Update original config
            self._original_config = RefreshRateConfiguration(**self._config.__dict__)

            # Trigger callback
            if self._on_config_change:
                self._on_config_change(self._config)

            # Update apply button state
            self._update_apply_button_state()

            # Show success message
            self._show_success_message("Configuration applied successfully")

        except Exception as e:
            self._show_error_message(f"Failed to apply configuration: {str(e)}")

    def _reset_changes(self, e) -> None:
        """Reset configuration to original values."""
        self._config = RefreshRateConfiguration(**self._original_config.__dict__)
        self._update_ui_from_config()
        self._update_apply_button_state()

    def _save_as_preset(self, e) -> None:
        """Save current configuration as a custom preset."""
        # This would typically open a dialog to name the preset
        # For now, just show a placeholder message
        self._show_info_message("Custom preset saving not yet implemented")

    # Utility Methods
    def _update_ui_from_config(self) -> None:
        """Update UI components from current configuration."""
        try:
            # Update preset dropdown
            if self._preset_dropdown:
                self._preset_dropdown.value = self._config.preset.value

            # Update refresh rate controls
            if self._refresh_rate_slider:
                self._refresh_rate_slider.value = self._config.refresh_interval_seconds
                self._refresh_rate_slider.label = f"{self._config.refresh_interval_seconds:.1f}s"

            if self._refresh_rate_input:
                self._refresh_rate_input.value = str(self._config.refresh_interval_seconds)

            # Update retention controls
            if self._retention_slider:
                self._retention_slider.value = self._config.data_retention_minutes
                self._retention_slider.label = f"{self._config.data_retention_minutes} min"

            if self._retention_input:
                self._retention_input.value = str(self._config.data_retention_minutes)

            # Update switches
            if self._auto_adjust_switch:
                self._auto_adjust_switch.value = self._config.auto_adjust_enabled

            if self._performance_switch:
                self._performance_switch.value = self._config.performance_mode

            if self._batch_updates_switch:
                self._batch_updates_switch.value = self._config.batch_updates

            if self._adaptive_rate_switch:
                self._adaptive_rate_switch.value = self._config.enable_adaptive_rate

            # Update displays
            self._update_rate_display()
            self._update_retention_display()

            self.update()

        except Exception as e:
            pass

    def _update_rate_display(self) -> None:
        """Update the refresh rate display."""
        # This would update the rate display container
        # Implementation depends on how the display is structured
        pass

    def _update_retention_display(self) -> None:
        """Update the data retention display."""
        # This would update the retention display container
        # Implementation depends on how the display is structured
        pass

    def _update_apply_button_state(self) -> None:
        """Update the apply button enabled state."""
        if self._apply_button:
            self._apply_button.disabled = not self._has_changes()
            self.update()

    def _has_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return (
            self._config.preset != self._original_config.preset or
            self._config.refresh_interval_seconds != self._original_config.refresh_interval_seconds or
            self._config.data_retention_minutes != self._original_config.data_retention_minutes or
            self._config.auto_adjust_enabled != self._original_config.auto_adjust_enabled or
            self._config.performance_mode != self._original_config.performance_mode or
            self._config.batch_updates != self._original_config.batch_updates or
            self._config.enable_adaptive_rate != self._original_config.enable_adaptive_rate
        )

    def _save_config_to_database(self) -> None:
        """Save configuration to database."""
        try:
            if self._user_preferences_db:
                config_data = {
                    'refresh_rate_preset': self._config.preset.value,
                    'refresh_interval_seconds': self._config.refresh_interval_seconds,
                    'data_retention_minutes': self._config.data_retention_minutes,
                    'auto_adjust_enabled': self._config.auto_adjust_enabled,
                    'performance_mode': self._config.performance_mode,
                    'batch_updates': self._config.batch_updates,
                    'enable_adaptive_rate': self._config.enable_adaptive_rate,
                    'max_history_points': self._config.max_history_points,
                    'min_refresh_rate': self._config.min_refresh_rate,
                    'max_refresh_rate': self._config.max_refresh_rate
                }

                # Save to user preferences
                self._user_preferences_db.set_preference('refresh_rate_config', config_data)

        except Exception as e:
            raise Exception(f"Failed to save configuration to database: {str(e)}")

    def _load_config_from_database(self) -> Optional[RefreshRateConfiguration]:
        """Load configuration from database."""
        try:
            if self._user_preferences_db:
                config_data = self._user_preferences_db.get_preference('refresh_rate_config')
                if config_data:
                    return RefreshRateConfiguration(
                        preset=RefreshRatePreset(config_data.get('refresh_rate_preset', 'standard')),
                        refresh_interval_seconds=config_data.get('refresh_interval_seconds', 1.0),
                        data_retention_minutes=config_data.get('data_retention_minutes', 60),
                        auto_adjust_enabled=config_data.get('auto_adjust_enabled', False),
                        performance_mode=config_data.get('performance_mode', False),
                        batch_updates=config_data.get('batch_updates', True),
                        enable_adaptive_rate=config_data.get('enable_adaptive_rate', False),
                        max_history_points=config_data.get('max_history_points', 1000),
                        min_refresh_rate=config_data.get('min_refresh_rate', 0.1),
                        max_refresh_rate=config_data.get('max_refresh_rate', 10.0)
                    )
        except Exception:
            pass

        return None

    def _show_success_message(self, message: str) -> None:
        """Show success message to user."""
        # This would typically show a snackbar or toast notification
        # For now, just print to console
        print(f"Success: {message}")

    def _show_error_message(self, message: str) -> None:
        """Show error message to user."""
        # This would typically show an error dialog or notification
        # For now, just print to console
        print(f"Error: {message}")

    def _show_info_message(self, message: str) -> None:
        """Show info message to user."""
        # This would typically show an info dialog or notification
        # For now, just print to console
        print(f"Info: {message}")

    async def start_performance_monitoring(self) -> None:
        """Start monitoring performance metrics."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._performance_monitoring_loop())

    async def stop_performance_monitoring(self) -> None:
        """Stop monitoring performance metrics."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def _performance_monitoring_loop(self) -> None:
        """Performance monitoring loop."""
        try:
            while self._is_monitoring:
                # Update performance metrics
                await self._update_performance_metrics()

                # Wait for next update
                await asyncio.sleep(2.0)  # Update metrics every 2 seconds

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Performance monitoring error: {e}")

    async def _update_performance_metrics(self) -> None:
        """Update performance metrics display."""
        try:
            # Simulate performance metrics collection
            # In a real implementation, this would collect actual metrics
            import random

            if self._current_metrics:
                self._current_metrics.current_rate = self._config.refresh_interval_seconds
                self._current_metrics.target_rate = self._config.refresh_interval_seconds
                self._current_metrics.actual_update_time = random.uniform(0.001, 0.1)
                self._current_metrics.missed_updates = random.randint(0, 2)
                self._current_metrics.performance_impact = random.uniform(1.0, 10.0)
                self._current_metrics.memory_usage_mb = random.uniform(5.0, 50.0)
                self._current_metrics.cpu_usage_percent = random.uniform(0.5, 5.0)
                self._current_metrics.last_update = datetime.now()

                # Update metrics display if visible
                if self._show_performance_metrics and self._metrics_display:
                    self._build_component()
                    self.update()

        except Exception as e:
            print(f"Error updating performance metrics: {e}")

    # Public API Methods
    def get_configuration(self) -> RefreshRateConfiguration:
        """Get current refresh rate configuration."""
        return RefreshRateConfiguration(**self._config.__dict__)

    def set_configuration(self, config: RefreshRateConfiguration) -> None:
        """Set refresh rate configuration."""
        self._config = RefreshRateConfiguration(**config.__dict__)
        self._update_ui_from_config()

    def get_performance_metrics(self) -> Optional[RefreshRateMetrics]:
        """Get current performance metrics."""
        return self._current_metrics

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._config = RefreshRateConfiguration()
        self._original_config = RefreshRateConfiguration()
        self._update_ui_from_config()
        self._update_apply_button_state()

    def apply_preset(self, preset: RefreshRatePreset) -> None:
        """Apply a specific preset configuration."""
        if preset in self._preset_configs:
            self._config = RefreshRateConfiguration(**self._preset_configs[preset].__dict__)
            self._update_ui_from_config()
            self._update_apply_button_state()

    def enable_performance_monitoring(self, enable: bool = True) -> None:
        """Enable or disable performance monitoring."""
        if enable and not self._is_monitoring:
            asyncio.create_task(self.start_performance_monitoring())
        elif not enable and self._is_monitoring:
            asyncio.create_task(self.stop_performance_monitoring())

    def refresh_ui(self) -> None:
        """Refresh the UI component."""
        self._build_component()
        self.update()

    def cleanup(self) -> None:
        """Cleanup resources."""
        if self._is_monitoring:
            asyncio.create_task(self.stop_performance_monitoring())
