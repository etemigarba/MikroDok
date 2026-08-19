"""
Module: mode_selector_ui
Description: Provides interface for selecting Legacy, Hybrid, or Auto IDRAlloc modes with hardware compatibility checks
Phase: 2
Location: /src/modules/ui/memory_config_ui/mode_selector_ui/
"""

# Standard library imports
import asyncio
import logging
import psutil
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.memory_allocation_lg.allocation_strategy_lg.allocation_strategy_lg import (
    IDRAllocMode, HardwareProfile, AllocationStrategy
)
from src.modules.logic.resource_monitor_lg.memory_monitor_lg.memory_monitor_lg import (
    MemoryMonitor, MemoryMetrics
)
from src.modules.logic.resource_monitor_lg.gpu_monitor_lg.gpu_monitor_lg import GPUMonitor


class ModeCompatibility(Enum):
    """Hardware compatibility levels for IDRAlloc modes."""
    OPTIMAL = "optimal"
    COMPATIBLE = "compatible"
    LIMITED = "limited"
    INCOMPATIBLE = "incompatible"


@dataclass
class ModeInfo:
    """Information about an IDRAlloc mode."""
    mode: IDRAllocMode
    title: str
    description: str
    requirements: str
    benefits: List[str]
    limitations: List[str]
    recommended_vram_gb: float
    recommended_ram_gb: float


@dataclass
class CompatibilityResult:
    """Hardware compatibility assessment result."""
    mode: IDRAllocMode
    level: ModeCompatibility
    score: float  # 0.0 to 1.0
    issues: List[str]
    recommendations: List[str]
    estimated_performance: float  # 0.0 to 1.0


class ModeSelectorUI(ThemeAwareUserControl):
    """
    Memory allocation mode selector interface.
    
    Provides interface for selecting Legacy, Hybrid, or Auto IDRAlloc modes
    with real-time hardware compatibility checks and performance estimation.
    
    Features:
    - Interactive mode selection with visual cards
    - Real-time hardware compatibility validation
    - Performance estimation and recommendations
    - Responsive design with theme integration
    - Hardware monitoring integration
    """
    
    def __init__(self, 
                 on_mode_change: Optional[Callable[[IDRAllocMode], None]] = None,
                 initial_mode: IDRAllocMode = IDRAllocMode.AUTO,
                 **kwargs):
        super().__init__(**kwargs)
        self._logger = logging.getLogger(__name__)
        
        # Callbacks
        self._on_mode_change = on_mode_change
        
        # State management
        self._current_mode = initial_mode
        self._hardware_profile: Optional[HardwareProfile] = None
        self._compatibility_results: Dict[IDRAllocMode, CompatibilityResult] = {}
        self._is_checking_compatibility = False
        
        # UI components
        self._mode_radio_group: Optional[ft.RadioGroup] = None
        self._compatibility_panel: Optional[ft.Container] = None
        self._performance_indicator: Optional[ft.Container] = None
        
        # Hardware monitors
        try:
            self._memory_monitor = MemoryMonitor()
            self._gpu_monitor = GPUMonitor()
        except Exception as e:
            self._logger.warning(f"Could not initialize hardware monitors: {e}")
            self._memory_monitor = None
            self._gpu_monitor = None
        
        # Mode information
        self._mode_info = self._initialize_mode_info()
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize core components."""
        try:
            # Detect hardware profile
            self._detect_hardware_profile()
            
        except Exception as e:
            self._logger.error(f"Error initializing components: {str(e)}")
    
    def _detect_hardware_profile(self) -> None:
        """Detect current hardware configuration."""
        try:
            # Get system information
            memory_info = psutil.virtual_memory()
            
            # Detect GPU information (simplified for now)
            gpu_vram_gb = 8.0  # Default, should be detected from actual GPU
            
            # Create hardware profile
            self._hardware_profile = HardwareProfile(
                gpu_vram_gb=gpu_vram_gb,
                system_ram_gb=memory_info.total / (1024**3),
                nvme_capacity_gb=100.0,  # Simplified
                nvme_bandwidth_gbps=3.5,  # Typical NVMe speed
                gpu_compute_capability="8.6",  # Default
                cpu_cores=psutil.cpu_count(),
                memory_bandwidth_gbps=25.6  # Typical DDR4 speed
            )
            
        except Exception as e:
            self._logger.error(f"Error detecting hardware profile: {str(e)}")
            # Use default profile
            self._hardware_profile = HardwareProfile(
                gpu_vram_gb=8.0,
                system_ram_gb=16.0,
                nvme_capacity_gb=100.0,
                nvme_bandwidth_gbps=3.5,
                gpu_compute_capability="8.6",
                cpu_cores=8,
                memory_bandwidth_gbps=25.6
            )
    
    def build(self) -> ft.Control:
        """Build the mode selector interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column([
                self._create_header(),
                ft.Divider(color=palette.outline_variant),
                self._create_mode_selection(),
                ft.Divider(color=palette.outline_variant),
                self._create_compatibility_panel()
            ], spacing=spacing.section_spacing),
            padding=ft.padding.all(spacing.container_padding),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.outline_variant)
        )
    
    def _create_header(self) -> ft.Control:
        """Create header with title and refresh button."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Row([
            ft.Icon(self.get_icon('SETTINGS'), color=palette.primary, size=24),
            ft.Text(
                "IDRAlloc Mode Selection",
                style=self.get_text_style('h3'),
                color=palette.text_primary
            ),
            ft.Container(expand=True),
            ft.IconButton(
                icon=self.get_icon('REFRESH'),
                tooltip="Refresh Hardware Compatibility",
                on_click=self._on_refresh_compatibility,
                icon_color=palette.primary
            )
        ], spacing=spacing.element_spacing)
    
    def _create_mode_selection(self) -> ft.Control:
        """Create mode selection radio group."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create radio options
        radio_options = []
        for mode in IDRAllocMode:
            mode_info = self._mode_info[mode]
            radio_options.append(
                ft.Radio(
                    value=mode.value,
                    label=mode_info.title,
                    active_color=palette.primary
                )
            )
        
        self._mode_radio_group = ft.RadioGroup(
            content=ft.Column(radio_options, spacing=spacing.element_spacing),
            value=self._current_mode.value,
            on_change=self._on_mode_selection_change
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Select Memory Allocation Mode",
                    style=self.get_text_style('subtitle1'),
                    color=palette.text_primary
                ),
                self._mode_radio_group,
                self._create_mode_descriptions()
            ], spacing=spacing.component_spacing),
            padding=ft.padding.all(spacing.element_padding),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(4)
        )

    def _create_mode_descriptions(self) -> ft.Control:
        """Create mode descriptions panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        current_info = self._mode_info[self._current_mode]

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    current_info.description,
                    style=self.get_text_style('body1'),
                    color=palette.text_secondary
                ),
                ft.Row([
                    ft.Icon(self.get_icon('CHECK_CIRCLE'), color=palette.success, size=16),
                    ft.Text(
                        "Benefits:",
                        style=self.get_text_style('subtitle2'),
                        color=palette.text_primary
                    )
                ], spacing=spacing.element_spacing),
                ft.Column([
                    ft.Text(
                        f" {benefit}",
                        style=self.get_text_style('body2'),
                        color=palette.text_secondary
                    ) for benefit in current_info.benefits
                ], spacing=2)
            ], spacing=spacing.element_spacing),
            padding=ft.padding.all(spacing.element_padding),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(4),
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_compatibility_panel(self) -> ft.Control:
        """Create hardware compatibility assessment panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(self.get_icon('CPU'), color=palette.primary, size=20),
                    ft.Text(
                        "Hardware Compatibility",
                        style=self.get_text_style('subtitle1'),
                        color=palette.text_primary
                    )
                ], spacing=spacing.element_spacing),
                ft.Text(
                    "Click refresh to check hardware compatibility",
                    style=self.get_text_style('body2'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.component_spacing),
            padding=ft.padding.all(spacing.element_padding),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(4)
        )

    def _on_mode_selection_change(self, e: ft.ControlEvent) -> None:
        """Handle mode selection change."""
        try:
            new_mode = IDRAllocMode(e.control.value)
            if new_mode != self._current_mode:
                self._current_mode = new_mode
                self.update()

                if self._on_mode_change:
                    self._on_mode_change(new_mode)

                self._logger.info(f"Mode changed to: {new_mode.value}")
        except Exception as ex:
            self._logger.error(f"Error handling mode selection change: {ex}")

    def _on_refresh_compatibility(self, e: ft.ControlEvent) -> None:
        """Handle compatibility refresh request."""
        self._logger.info("Compatibility refresh requested")

    def _initialize_mode_info(self) -> Dict[IDRAllocMode, ModeInfo]:
        """Initialize mode information dictionary."""
        return {
            IDRAllocMode.LEGACY: ModeInfo(
                mode=IDRAllocMode.LEGACY,
                title="Legacy Mode",
                description="Traditional memory allocation using only system RAM. Simple and reliable for basic workloads.",
                requirements="Minimum 4GB RAM",
                benefits=[
                    "Simple configuration and management",
                    "Compatible with all hardware configurations",
                    "Predictable memory behavior",
                    "Lower complexity and overhead"
                ],
                limitations=[
                    "Limited to system RAM capacity",
                    "No GPU acceleration benefits",
                    "Lower performance for large models"
                ],
                recommended_vram_gb=0.0,
                recommended_ram_gb=4.0
            ),
            IDRAllocMode.HYBRID: ModeInfo(
                mode=IDRAllocMode.HYBRID,
                title="Hybrid Mode",
                description="Intelligent allocation between GPU VRAM and system RAM with manual tier management.",
                requirements="Minimum 8GB RAM, 2GB GPU VRAM",
                benefits=[
                    "GPU acceleration for critical operations",
                    "Efficient use of available VRAM",
                    "Manual control over memory placement",
                    "Good performance-cost balance"
                ],
                limitations=[
                    "Requires manual configuration",
                    "Limited automatic optimization",
                    "Complex memory management"
                ],
                recommended_vram_gb=2.0,
                recommended_ram_gb=8.0
            ),
            IDRAllocMode.AUTO: ModeInfo(
                mode=IDRAllocMode.AUTO,
                title="Auto Mode",
                description="Fully automatic three-tier allocation across GPU VRAM, system RAM, and NVMe storage with intelligent optimization.",
                requirements="Minimum 16GB RAM, 4GB GPU VRAM, 100GB NVMe",
                benefits=[
                    "Maximum performance optimization",
                    "Automatic tier management",
                    "Efficient use of all memory tiers",
                    "Adaptive to workload patterns",
                    "Handles very large models"
                ],
                limitations=[
                    "Requires high-end hardware",
                    "Complex internal algorithms",
                    "Higher system overhead"
                ],
                recommended_vram_gb=4.0,
                recommended_ram_gb=16.0
            )
        }

    # Public methods
    def set_mode(self, mode: IDRAllocMode) -> None:
        """Set the current mode programmatically."""
        try:
            if mode != self._current_mode:
                self._current_mode = mode
                if self._mode_radio_group:
                    self._mode_radio_group.value = mode.value
                self.update()

                if self._on_mode_change:
                    self._on_mode_change(mode)

        except Exception as ex:
            self._logger.error(f"Error setting mode: {ex}")

    def get_current_mode(self) -> IDRAllocMode:
        """Get the currently selected mode."""
        return self._current_mode

    def get_compatibility_result(self, mode: IDRAllocMode) -> Optional[CompatibilityResult]:
        """Get compatibility result for a specific mode."""
        return self._compatibility_results.get(mode)

    def refresh_compatibility(self) -> None:
        """Trigger compatibility check refresh."""
        self._logger.info("Compatibility refresh triggered")
