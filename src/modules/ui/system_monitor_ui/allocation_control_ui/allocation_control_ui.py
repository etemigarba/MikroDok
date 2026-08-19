"""
Module: allocation_control_ui
Description: Comprehensive memory allocation control interface providing IDRAlloc mode selection, memory limits configuration, priority settings, and real-time allocation control
Phase: 2
Location: /src/modules/ui/system_monitor_ui/allocation_control_ui/
"""

# Standard library imports
import asyncio
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.memory_allocation_lg.allocation_strategy_lg.allocation_strategy_lg import (
    IDRAllocMode, AllocationStrategy, HardwareProfile
)
from src.modules.logic.memory_allocation_lg.memory_tier_manager_lg.memory_tier_manager_lg import (
    MemoryTierManager, MemoryTier, TierStatus
)
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier


class AllocationControlMode(Enum):
    """Allocation control operation modes."""
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"
    HYBRID = "HYBRID"
    MONITORING_ONLY = "MONITORING_ONLY"


class AllocationControlAction(Enum):
    """Allocation control actions."""
    START_CONTROL = "START_CONTROL"
    STOP_CONTROL = "STOP_CONTROL"
    APPLY_SETTINGS = "APPLY_SETTINGS"
    RESET_SETTINGS = "RESET_SETTINGS"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    OPTIMIZE_ALLOCATION = "OPTIMIZE_ALLOCATION"


class AllocationControlState(Enum):
    """Allocation control states."""
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    CONFIGURING = "CONFIGURING"
    ERROR = "ERROR"
    EMERGENCY = "EMERGENCY"


@dataclass
class MemoryLimitConfiguration:
    """Memory limit configuration."""
    gpu_limit_percent: float = 90.0
    cpu_limit_percent: float = 80.0
    virtual_limit_percent: float = 85.0
    enable_dynamic_limits: bool = True
    emergency_threshold_percent: float = 95.0
    warning_threshold_percent: float = 85.0


@dataclass
class ThermalLimitConfiguration:
    """Thermal limit configuration."""
    gpu_temp_limit_celsius: float = 83.0
    cpu_temp_limit_celsius: float = 85.0
    enable_thermal_throttling: bool = True
    thermal_warning_threshold: float = 75.0
    thermal_emergency_threshold: float = 90.0
    cooling_delay_seconds: float = 30.0


@dataclass
class AllocationControlConfiguration:
    """Configuration for allocation control."""
    control_mode: AllocationControlMode = AllocationControlMode.AUTOMATIC
    idralloc_mode: IDRAllocMode = IDRAllocMode.AUTO
    memory_limits: MemoryLimitConfiguration = None
    thermal_limits: ThermalLimitConfiguration = None
    process_priority: int = 0  # -20 to 19 range
    enable_advanced_settings: bool = False
    memory_page_size_kb: int = 4
    buffer_size_mb: int = 256
    auto_optimization_enabled: bool = True
    refresh_interval_ms: int = 1000
    enable_emergency_controls: bool = True

    def __post_init__(self):
        if self.memory_limits is None:
            self.memory_limits = MemoryLimitConfiguration()
        if self.thermal_limits is None:
            self.thermal_limits = ThermalLimitConfiguration()


class AllocationControlUI(ThemeAwareUserControl):
    """
    Comprehensive allocation control UI component.
    
    Features:
    - IDRAlloc mode selection with visual indicators
    - Memory limits configuration with real-time sliders
    - Process priority settings and thermal limits
    - Advanced settings for memory page size and buffer configuration
    - Real-time allocation monitoring and control
    - Emergency stop functionality for critical situations
    - Theme-aware styling with responsive design
    - Integration with memory tier manager and allocation strategy
    - Performance optimization controls
    - Accessibility compliance and cross-platform compatibility
    """

    def __init__(self, 
                 allocation_strategy: Optional[AllocationStrategy] = None,
                 memory_tier_manager: Optional[MemoryTierManager] = None,
                 configuration: Optional[AllocationControlConfiguration] = None,
                 on_control_action: Optional[Callable[[AllocationControlAction, Dict[str, Any]], None]] = None):
        """
        Initialize allocation control UI.
        
        Args:
            allocation_strategy: Allocation strategy instance
            memory_tier_manager: Memory tier manager instance
            configuration: Control configuration
            on_control_action: Callback for control actions
        """
        super().__init__()
        
        # Initialize logger
        self._logger = logging.getLogger(__name__)
        
        # Store dependencies
        self._allocation_strategy = allocation_strategy
        self._memory_tier_manager = memory_tier_manager
        self._config = configuration or AllocationControlConfiguration()
        self._on_control_action = on_control_action
        
        # Control state
        self._control_state = AllocationControlState.INACTIVE
        self._is_monitoring = False
        self._last_update = datetime.now(timezone.utc)
        
        # UI components
        self._mode_selector = None
        self._memory_limit_sliders = {}
        self._thermal_limit_inputs = {}
        self._priority_dropdown = None
        self._advanced_settings_panel = None
        self._control_buttons = {}
        self._status_indicator = None
        
        # Monitoring task
        self._monitoring_task = None
        
        self._logger.info("Allocation control UI initialized")

    def build(self) -> ft.Control:
        """Build the allocation control UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()
        
        # Create main container with responsive layout
        main_container = ft.Container(
            content=ft.Column([
                self._create_header(),
                ft.Divider(color=palette.outline_variant),
                self._create_mode_selection(),
                ft.Divider(color=palette.outline_variant),
                self._create_memory_limits(),
                ft.Divider(color=palette.outline_variant),
                self._create_thermal_limits(),
                ft.Divider(color=palette.outline_variant),
                self._create_priority_settings(),
                ft.Divider(color=palette.outline_variant),
                self._create_advanced_settings(),
                ft.Divider(color=palette.outline_variant),
                self._create_control_panel()
            ], spacing=spacing.md, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border_radius=rlm.get_border_radius('medium'),
            border=ft.border.all(1, palette.outline_variant)
        )
        
        return main_container

    def _create_header(self) -> ft.Control:
        """Create header with title and status."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Status indicator
        status_color = self._get_status_color()
        status_text = self._control_state.value.replace('_', ' ').title()
        
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "Allocation Control",
                        style=self.get_text_style('h2'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "IDRAlloc memory allocation control and configuration",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], expand=True),
                ft.Column([
                    ft.Row([
                        ft.Icon(self.get_icon('CIRCLE'), color=status_color, size=12),
                        ft.Text(
                            status_text,
                            style=self.get_text_style('body_small'),
                            color=status_color
                        )
                    ], spacing=spacing.xs),
                    ft.Text(
                        f"Last Update: {self._last_update.strftime('%H:%M:%S')}",
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    )
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md)
        )

    def _create_mode_selection(self) -> ft.Control:
        """Create IDRAlloc mode selection."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Mode options
        mode_options = [
            (IDRAllocMode.LEGACY, "Legacy", "Traditional GPU-only allocation"),
            (IDRAllocMode.HYBRID, "Hybrid", "Balanced GPU/RAM allocation"),
            (IDRAllocMode.AUTO, "Auto", "Intelligent adaptive allocation")
        ]
        
        mode_controls = []
        for mode, title, description in mode_options:
            is_selected = self._config.idralloc_mode == mode
            
            mode_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Radio(
                            value=mode.value,
                            group_name="idralloc_mode",
                            on_change=self._on_mode_change,
                            active_color=palette.primary
                        ),
                        ft.Column([
                            ft.Text(
                                title,
                                style=self.get_text_style('body_large'),
                                color=palette.text_primary,
                                weight=ft.FontWeight.W_600
                            ),
                            ft.Text(
                                description,
                                style=self.get_text_style('body_small'),
                                color=palette.text_secondary
                            )
                        ], expand=True)
                    ])
                ]),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.primary_container if is_selected else palette.surface_variant,
                border_radius=8,
                border=ft.border.all(
                    2 if is_selected else 1,
                    palette.primary if is_selected else palette.outline_variant
                ),
                on_click=lambda e, m=mode: self._select_mode(m)
            )
            mode_controls.append(mode_card)
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "IDRAlloc Mode",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Column(mode_controls, spacing=spacing.sm)
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md)
        )

    def _create_memory_limits(self) -> ft.Control:
        """Create memory limits configuration."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Memory limit sliders
        limit_configs = [
            ("gpu_limit", "GPU Memory Limit", self._config.memory_limits.gpu_limit_percent, "%"),
            ("cpu_limit", "CPU Memory Limit", self._config.memory_limits.cpu_limit_percent, "%"),
            ("virtual_limit", "Virtual Memory Limit", self._config.memory_limits.virtual_limit_percent, "%")
        ]

        limit_controls = []
        for limit_id, title, current_value, unit in limit_configs:
            slider = ft.Slider(
                min=10,
                max=100,
                value=current_value,
                divisions=18,
                label=f"{current_value:.0f}{unit}",
                on_change=lambda e, lid=limit_id: self._on_memory_limit_change(lid, e.control.value),
                active_color=palette.primary,
                inactive_color=palette.outline_variant
            )
            self._memory_limit_sliders[limit_id] = slider

            limit_control = ft.Column([
                ft.Row([
                    ft.Text(
                        title,
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary,
                        expand=True
                    ),
                    ft.Text(
                        f"{current_value:.0f}{unit}",
                        style=self.get_text_style('body_medium'),
                        color=palette.primary,
                        weight=ft.FontWeight.W_600
                    )
                ]),
                slider
            ], spacing=spacing.xs)
            limit_controls.append(limit_control)

        # Dynamic limits toggle
        dynamic_toggle = ft.Switch(
            value=self._config.memory_limits.enable_dynamic_limits,
            on_change=self._on_dynamic_limits_toggle,
            active_color=palette.primary
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory Limits",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Column(limit_controls, spacing=spacing.md),
                ft.Row([
                    ft.Text(
                        "Enable Dynamic Limits",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary,
                        expand=True
                    ),
                    dynamic_toggle
                ])
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md)
        )

    def _create_thermal_limits(self) -> ft.Control:
        """Create thermal limits configuration."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Thermal limit inputs
        thermal_configs = [
            ("gpu_temp", "GPU Temperature Limit", self._config.thermal_limits.gpu_temp_limit_celsius, "°C"),
            ("cpu_temp", "CPU Temperature Limit", self._config.thermal_limits.cpu_temp_limit_celsius, "°C")
        ]

        thermal_controls = []
        for thermal_id, title, current_value, unit in thermal_configs:
            input_field = ft.TextField(
                value=str(current_value),
                label=title,
                suffix_text=unit,
                width=150,
                on_change=lambda e, tid=thermal_id: self._on_thermal_limit_change(tid, e.control.value),
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary)
            )
            self._thermal_limit_inputs[thermal_id] = input_field
            thermal_controls.append(input_field)

        # Thermal throttling toggle
        throttling_toggle = ft.Switch(
            value=self._config.thermal_limits.enable_thermal_throttling,
            on_change=self._on_thermal_throttling_toggle,
            active_color=palette.primary
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Thermal Limits",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Row(thermal_controls, spacing=spacing.lg),
                ft.Row([
                    ft.Text(
                        "Enable Thermal Throttling",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary,
                        expand=True
                    ),
                    throttling_toggle
                ])
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md)
        )

    def _create_priority_settings(self) -> ft.Control:
        """Create process priority settings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Priority options
        priority_options = [
            (-20, "Highest", "Maximum priority (requires admin)"),
            (-10, "High", "High priority"),
            (0, "Normal", "Default priority"),
            (10, "Low", "Low priority"),
            (19, "Lowest", "Minimum priority")
        ]

        priority_dropdown = ft.Dropdown(
            value=str(self._config.process_priority),
            options=[
                ft.dropdown.Option(
                    key=str(priority),
                    text=f"{name} ({priority})"
                ) for priority, name, _ in priority_options
            ],
            on_change=self._on_priority_change,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary)
        )
        self._priority_dropdown = priority_dropdown

        # Priority description
        current_desc = next(
            desc for priority, _, desc in priority_options
            if priority == self._config.process_priority
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Process Priority",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Row([
                    priority_dropdown,
                    ft.Text(
                        current_desc,
                        style=self.get_text_style('body_small'),
                        color=palette.text_secondary,
                        expand=True
                    )
                ], spacing=spacing.lg)
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md)
        )

    def _create_advanced_settings(self) -> ft.Control:
        """Create advanced settings panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Advanced settings inputs
        page_size_input = ft.TextField(
            value=str(self._config.memory_page_size_kb),
            label="Memory Page Size",
            suffix_text="KB",
            width=150,
            on_change=self._on_page_size_change,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary)
        )

        buffer_size_input = ft.TextField(
            value=str(self._config.buffer_size_mb),
            label="Buffer Size",
            suffix_text="MB",
            width=150,
            on_change=self._on_buffer_size_change,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary)
        )

        # Auto optimization toggle
        auto_opt_toggle = ft.Switch(
            value=self._config.auto_optimization_enabled,
            on_change=self._on_auto_optimization_toggle,
            active_color=palette.primary
        )

        # Advanced settings content
        advanced_content = ft.Column([
            ft.Row([page_size_input, buffer_size_input], spacing=spacing.lg),
            ft.Row([
                ft.Text(
                    "Enable Auto Optimization",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_primary,
                    expand=True
                ),
                auto_opt_toggle
            ])
        ], spacing=spacing.md)

        # Expandable panel
        advanced_panel = ft.ExpansionTile(
            title=ft.Text(
                "Advanced Settings",
                style=self.get_text_style('h3'),
                color=palette.text_primary
            ),
            subtitle=ft.Text(
                "Memory page size and buffer configuration",
                style=self.get_text_style('body_small'),
                color=palette.text_secondary
            ),
            controls=[advanced_content],
            initially_expanded=self._config.enable_advanced_settings,
            on_change=self._on_advanced_settings_toggle
        )

        return ft.Container(
            content=advanced_panel,
            padding=ft.padding.all(spacing.md)
        )

    def _create_control_panel(self) -> ft.Control:
        """Create control panel with action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Control buttons
        start_button = ft.ElevatedButton(
            text="Start Control" if self._control_state == AllocationControlState.INACTIVE else "Stop Control",
            icon=self.get_icon('PLAY_ARROW') if self._control_state == AllocationControlState.INACTIVE else self.get_icon('STOP'),
            on_click=self._on_start_stop_control,
            bgcolor=palette.success if self._control_state == AllocationControlState.INACTIVE else palette.error,
            color=palette.on_primary
        )
        self._control_buttons['start_stop'] = start_button

        apply_button = ft.ElevatedButton(
            text="Apply Settings",
            icon=self.get_icon('CHECK'),
            on_click=self._on_apply_settings,
            bgcolor=palette.primary,
            color=palette.on_primary
        )
        self._control_buttons['apply'] = apply_button

        reset_button = ft.OutlinedButton(
            text="Reset",
            icon=self.get_icon('REFRESH'),
            on_click=self._on_reset_settings,
            color=palette.text_primary
        )
        self._control_buttons['reset'] = reset_button

        emergency_button = ft.ElevatedButton(
            text="Emergency Stop",
            icon=self.get_icon('WARNING'),
            on_click=self._on_emergency_stop,
            bgcolor=palette.error,
            color=palette.on_error
        )
        self._control_buttons['emergency'] = emergency_button

        optimize_button = ft.ElevatedButton(
            text="Optimize",
            icon=self.get_icon('TUNE'),
            on_click=self._on_optimize_allocation,
            bgcolor=palette.tertiary,
            color=palette.on_tertiary
        )
        self._control_buttons['optimize'] = optimize_button

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Control Panel",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Row([
                    start_button,
                    apply_button,
                    reset_button
                ], spacing=spacing.md),
                ft.Row([
                    optimize_button,
                    emergency_button
                ], spacing=spacing.md)
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md)
        )

    # Event Handlers
    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle IDRAlloc mode change."""
        try:
            mode = IDRAllocMode(e.control.value)
            self._config.idralloc_mode = mode
            self._logger.info(f"IDRAlloc mode changed to: {mode.value}")
            self._trigger_control_action(AllocationControlAction.APPLY_SETTINGS, {"mode": mode})
        except Exception as ex:
            self._logger.error(f"Error changing mode: {ex}")

    def _select_mode(self, mode: IDRAllocMode) -> None:
        """Select IDRAlloc mode."""
        self._config.idralloc_mode = mode
        self._logger.info(f"IDRAlloc mode selected: {mode.value}")
        self.update()

    def _on_memory_limit_change(self, limit_id: str, value: float) -> None:
        """Handle memory limit change."""
        try:
            if limit_id == "gpu_limit":
                self._config.memory_limits.gpu_limit_percent = value
            elif limit_id == "cpu_limit":
                self._config.memory_limits.cpu_limit_percent = value
            elif limit_id == "virtual_limit":
                self._config.memory_limits.virtual_limit_percent = value

            self._logger.info(f"Memory limit {limit_id} changed to: {value}%")
        except Exception as ex:
            self._logger.error(f"Error changing memory limit: {ex}")

    def _on_dynamic_limits_toggle(self, e: ft.ControlEvent) -> None:
        """Handle dynamic limits toggle."""
        self._config.memory_limits.enable_dynamic_limits = e.control.value
        self._logger.info(f"Dynamic limits: {e.control.value}")

    def _on_thermal_limit_change(self, thermal_id: str, value: str) -> None:
        """Handle thermal limit change."""
        try:
            temp_value = float(value)
            if thermal_id == "gpu_temp":
                self._config.thermal_limits.gpu_temp_limit_celsius = temp_value
            elif thermal_id == "cpu_temp":
                self._config.thermal_limits.cpu_temp_limit_celsius = temp_value

            self._logger.info(f"Thermal limit {thermal_id} changed to: {temp_value}°C")
        except ValueError:
            self._logger.warning(f"Invalid thermal limit value: {value}")

    def _on_thermal_throttling_toggle(self, e: ft.ControlEvent) -> None:
        """Handle thermal throttling toggle."""
        self._config.thermal_limits.enable_thermal_throttling = e.control.value
        self._logger.info(f"Thermal throttling: {e.control.value}")

    def _on_priority_change(self, e: ft.ControlEvent) -> None:
        """Handle process priority change."""
        try:
            priority = int(e.control.value)
            self._config.process_priority = priority
            self._logger.info(f"Process priority changed to: {priority}")
        except ValueError:
            self._logger.warning(f"Invalid priority value: {e.control.value}")

    def _on_page_size_change(self, e: ft.ControlEvent) -> None:
        """Handle memory page size change."""
        try:
            page_size = int(e.control.value)
            self._config.memory_page_size_kb = page_size
            self._logger.info(f"Memory page size changed to: {page_size}KB")
        except ValueError:
            self._logger.warning(f"Invalid page size value: {e.control.value}")

    def _on_buffer_size_change(self, e: ft.ControlEvent) -> None:
        """Handle buffer size change."""
        try:
            buffer_size = int(e.control.value)
            self._config.buffer_size_mb = buffer_size
            self._logger.info(f"Buffer size changed to: {buffer_size}MB")
        except ValueError:
            self._logger.warning(f"Invalid buffer size value: {e.control.value}")

    def _on_auto_optimization_toggle(self, e: ft.ControlEvent) -> None:
        """Handle auto optimization toggle."""
        self._config.auto_optimization_enabled = e.control.value
        self._logger.info(f"Auto optimization: {e.control.value}")

    def _on_advanced_settings_toggle(self, e: ft.ControlEvent) -> None:
        """Handle advanced settings toggle."""
        self._config.enable_advanced_settings = e.control.expanded
        self._logger.info(f"Advanced settings expanded: {e.control.expanded}")

    def _on_start_stop_control(self, e: ft.ControlEvent) -> None:
        """Handle start/stop control."""
        if self._control_state == AllocationControlState.INACTIVE:
            self._start_control()
        else:
            self._stop_control()

    def _on_apply_settings(self, e: ft.ControlEvent) -> None:
        """Handle apply settings."""
        self._trigger_control_action(AllocationControlAction.APPLY_SETTINGS, self._get_current_config())

    def _on_reset_settings(self, e: ft.ControlEvent) -> None:
        """Handle reset settings."""
        self._config = AllocationControlConfiguration()
        self._trigger_control_action(AllocationControlAction.RESET_SETTINGS, {})
        self.update()

    def _on_emergency_stop(self, e: ft.ControlEvent) -> None:
        """Handle emergency stop."""
        self._control_state = AllocationControlState.EMERGENCY
        self._trigger_control_action(AllocationControlAction.EMERGENCY_STOP, {})
        self.update()

    def _on_optimize_allocation(self, e: ft.ControlEvent) -> None:
        """Handle optimize allocation."""
        self._trigger_control_action(AllocationControlAction.OPTIMIZE_ALLOCATION, {})

    # Control Methods
    def _start_control(self) -> None:
        """Start allocation control."""
        try:
            self._control_state = AllocationControlState.ACTIVE
            self._is_monitoring = True
            self._last_update = datetime.now(timezone.utc)

            # Start monitoring task
            if self._monitoring_task is None or self._monitoring_task.done():
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            self._trigger_control_action(AllocationControlAction.START_CONTROL, self._get_current_config())
            self._logger.info("Allocation control started")
            self.update()

        except Exception as ex:
            self._logger.error(f"Error starting control: {ex}")
            self._control_state = AllocationControlState.ERROR

    def _stop_control(self) -> None:
        """Stop allocation control."""
        try:
            self._control_state = AllocationControlState.INACTIVE
            self._is_monitoring = False

            # Cancel monitoring task
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()

            self._trigger_control_action(AllocationControlAction.STOP_CONTROL, {})
            self._logger.info("Allocation control stopped")
            self.update()

        except Exception as ex:
            self._logger.error(f"Error stopping control: {ex}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring and self._control_state == AllocationControlState.ACTIVE:
                # Update monitoring data
                await self._update_monitoring_data()

                # Check for automatic optimizations
                if self._config.auto_optimization_enabled:
                    await self._check_auto_optimization()

                # Update UI
                self._last_update = datetime.now(timezone.utc)
                self.update()

                # Wait for next update
                await asyncio.sleep(self._config.refresh_interval_ms / 1000.0)

        except asyncio.CancelledError:
            self._logger.info("Monitoring loop cancelled")
        except Exception as ex:
            self._logger.error(f"Error in monitoring loop: {ex}")
            self._control_state = AllocationControlState.ERROR

    async def _update_monitoring_data(self) -> None:
        """Update monitoring data."""
        try:
            if self._memory_tier_manager:
                # Get tier usage information
                tier_usage = self._memory_tier_manager.get_tier_usage()

                # Check memory limits
                for tier, usage_percent in tier_usage.items():
                    if tier == MemoryTier.GPU_VRAM and usage_percent > self._config.memory_limits.gpu_limit_percent:
                        self._logger.warning(f"GPU memory usage ({usage_percent:.1f}%) exceeds limit")
                    elif tier == MemoryTier.SYSTEM_RAM and usage_percent > self._config.memory_limits.cpu_limit_percent:
                        self._logger.warning(f"CPU memory usage ({usage_percent:.1f}%) exceeds limit")

        except Exception as ex:
            self._logger.error(f"Error updating monitoring data: {ex}")

    async def _check_auto_optimization(self) -> None:
        """Check for automatic optimization opportunities."""
        try:
            if self._allocation_strategy:
                # Get current performance metrics
                # This would integrate with actual performance monitoring
                pass

        except Exception as ex:
            self._logger.error(f"Error checking auto optimization: {ex}")

    # Utility Methods
    def _get_status_color(self) -> str:
        """Get status indicator color."""
        palette = self.get_palette()

        status_colors = {
            AllocationControlState.INACTIVE: palette.text_tertiary,
            AllocationControlState.ACTIVE: palette.success,
            AllocationControlState.CONFIGURING: palette.warning,
            AllocationControlState.ERROR: palette.error,
            AllocationControlState.EMERGENCY: palette.error
        }

        return status_colors.get(self._control_state, palette.text_tertiary)

    def _get_current_config(self) -> Dict[str, Any]:
        """Get current configuration as dictionary."""
        return {
            "control_mode": self._config.control_mode.value,
            "idralloc_mode": self._config.idralloc_mode.value,
            "memory_limits": {
                "gpu_limit_percent": self._config.memory_limits.gpu_limit_percent,
                "cpu_limit_percent": self._config.memory_limits.cpu_limit_percent,
                "virtual_limit_percent": self._config.memory_limits.virtual_limit_percent,
                "enable_dynamic_limits": self._config.memory_limits.enable_dynamic_limits
            },
            "thermal_limits": {
                "gpu_temp_limit_celsius": self._config.thermal_limits.gpu_temp_limit_celsius,
                "cpu_temp_limit_celsius": self._config.thermal_limits.cpu_temp_limit_celsius,
                "enable_thermal_throttling": self._config.thermal_limits.enable_thermal_throttling
            },
            "process_priority": self._config.process_priority,
            "memory_page_size_kb": self._config.memory_page_size_kb,
            "buffer_size_mb": self._config.buffer_size_mb,
            "auto_optimization_enabled": self._config.auto_optimization_enabled
        }

    def _trigger_control_action(self, action: AllocationControlAction, data: Dict[str, Any]) -> None:
        """Trigger control action callback."""
        try:
            if self._on_control_action:
                self._on_control_action(action, data)
        except Exception as ex:
            self._logger.error(f"Error triggering control action: {ex}")

    # Public Methods
    def update_configuration(self, config: AllocationControlConfiguration) -> None:
        """Update control configuration."""
        self._config = config
        self.update()

    def get_configuration(self) -> AllocationControlConfiguration:
        """Get current configuration."""
        return self._config

    def get_control_state(self) -> AllocationControlState:
        """Get current control state."""
        return self._control_state

    def set_allocation_strategy(self, strategy: AllocationStrategy) -> None:
        """Set allocation strategy."""
        self._allocation_strategy = strategy

    def set_memory_tier_manager(self, manager: MemoryTierManager) -> None:
        """Set memory tier manager."""
        self._memory_tier_manager = manager

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self._is_monitoring = False
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
            self._logger.info("Allocation control UI cleaned up")
        except Exception as ex:
            self._logger.error(f"Error during cleanup: {ex}")
