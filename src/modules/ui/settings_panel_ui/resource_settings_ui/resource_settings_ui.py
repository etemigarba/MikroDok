"""
Module: resource_settings_ui
Description: Comprehensive resource allocation and hardware configuration interface for MikroDok application.
            Provides settings for IDRAlloc mode selection, GPU device configuration, memory limits,
            NVMe storage paths, performance profiles, thermal management, and hardware optimization.
            Features responsive design, real-time validation, and full theme system integration.

Features:
- IDRAlloc mode selection (Legacy, Hybrid, Auto) with compatibility checking
- GPU device selection with memory display and capability detection
- Memory limits configuration with real-time sliders and validation
- NVMe storage path selection with capacity monitoring
- Performance profile management (Balanced, Performance, Power Saver)
- Thermal limits and monitoring configuration
- Hardware detection and compatibility assessment
- Real-time resource monitoring and optimization suggestions
- Configuration import/export and preset management
- Full integration with theme system and responsive design

Phase: 1
Location: /src/modules/ui/settings_panel_ui/resource_settings_ui/resource_settings_ui.py
"""

# Standard library imports
import os
import json
import asyncio
import platform
import psutil
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path
import threading
import time
from datetime import datetime

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl, 
    ResponsiveLayoutManager,
    ColorPalette,
    TypographyScale,
    SpacingSystem,
    IconSystem,
    ScreenSize
)


class AllocationMode(Enum):
    """IDRAlloc memory allocation modes."""
    LEGACY = ("legacy", "Legacy (GPU Only)", "Traditional GPU-only memory allocation")
    HYBRID = ("hybrid", "Hybrid (GPU + RAM)", "Intelligent GPU and system RAM bridging")
    AUTO = ("auto", "Auto IDRAlloc", "Automatic allocation across all tiers")

    def __init__(self, mode_id: str, display_name: str, description: str):
        self.mode_id = mode_id
        self.display_name = display_name
        self.description = description


class PerformanceProfile(Enum):
    """Performance optimization profiles."""
    POWER_SAVER = ("power_saver", "Power Saver", "Optimized for energy efficiency")
    BALANCED = ("balanced", "Balanced", "Optimal balance of performance and efficiency")
    PERFORMANCE = ("performance", "Performance", "Maximum performance prioritization")
    CUSTOM = ("custom", "Custom", "User-defined configuration")

    def __init__(self, profile_id: str, display_name: str, description: str):
        self.profile_id = profile_id
        self.display_name = display_name
        self.description = description


@dataclass
class ResourceLimits:
    """Resource allocation limits configuration."""
    gpu_memory_limit_percent: float = 90.0
    system_memory_limit_percent: float = 80.0
    nvme_memory_limit_percent: float = 70.0
    gpu_memory_limit_mb: Optional[int] = None
    system_memory_limit_mb: Optional[int] = None
    nvme_memory_limit_mb: Optional[int] = None
    enable_dynamic_limits: bool = True
    memory_pressure_threshold: float = 85.0
    swap_threshold_percent: float = 60.0


@dataclass
class ThermalConfiguration:
    """Thermal management configuration."""
    enable_thermal_monitoring: bool = True
    gpu_temp_limit_celsius: int = 83
    cpu_temp_limit_celsius: int = 85
    thermal_throttle_threshold: int = 80
    enable_aggressive_cooling: bool = False
    fan_curve_profile: str = "balanced"
    thermal_shutdown_temp: int = 95


@dataclass
class GPUDevice:
    """GPU device information."""
    device_id: int
    name: str
    memory_total_mb: int
    memory_available_mb: int
    compute_capability: str
    driver_version: str
    is_available: bool = True
    supports_cuda: bool = False
    supports_opencl: bool = False
    power_limit_watts: Optional[int] = None


@dataclass
class HardwareProfile:
    """System hardware profile."""
    cpu_cores: int
    cpu_threads: int
    system_memory_gb: int
    gpu_devices: List[GPUDevice]
    nvme_devices: List[Dict[str, Any]]
    platform_info: Dict[str, str]
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ResourceSettingsConfig:
    """Complete resource settings configuration."""
    allocation_mode: AllocationMode = AllocationMode.AUTO
    performance_profile: PerformanceProfile = PerformanceProfile.BALANCED
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    thermal_config: ThermalConfiguration = field(default_factory=ThermalConfiguration)
    selected_gpu_id: Optional[int] = None
    nvme_storage_path: str = ""
    enable_hardware_monitoring: bool = True
    auto_optimize_allocation: bool = True
    enable_memory_compression: bool = False
    checkpoint_memory_optimization: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'allocation_mode': self.allocation_mode.mode_id,
            'performance_profile': self.performance_profile.profile_id,
            'resource_limits': asdict(self.resource_limits),
            'thermal_config': asdict(self.thermal_config),
            'selected_gpu_id': self.selected_gpu_id,
            'nvme_storage_path': self.nvme_storage_path,
            'enable_hardware_monitoring': self.enable_hardware_monitoring,
            'auto_optimize_allocation': self.auto_optimize_allocation,
            'enable_memory_compression': self.enable_memory_compression,
            'checkpoint_memory_optimization': self.checkpoint_memory_optimization
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceSettingsConfig':
        """Create configuration from dictionary."""
        config = cls()
        
        # Parse allocation mode
        if 'allocation_mode' in data:
            for mode in AllocationMode:
                if mode.mode_id == data['allocation_mode']:
                    config.allocation_mode = mode
                    break
        
        # Parse performance profile
        if 'performance_profile' in data:
            for profile in PerformanceProfile:
                if profile.profile_id == data['performance_profile']:
                    config.performance_profile = profile
                    break
        
        # Parse resource limits
        if 'resource_limits' in data:
            config.resource_limits = ResourceLimits(**data['resource_limits'])
        
        # Parse thermal config
        if 'thermal_config' in data:
            config.thermal_config = ThermalConfiguration(**data['thermal_config'])
        
        # Parse other fields
        for field_name in ['selected_gpu_id', 'nvme_storage_path', 'enable_hardware_monitoring',
                          'auto_optimize_allocation', 'enable_memory_compression', 
                          'checkpoint_memory_optimization']:
            if field_name in data:
                setattr(config, field_name, data[field_name])
        
        return config


class HardwareDetector:
    """Hardware detection and monitoring utility."""

    def __init__(self):
        self._gpu_devices: List[GPUDevice] = []
        self._hardware_profile: Optional[HardwareProfile] = None
        self._detection_cache_ttl = 300  # 5 minutes
        self._last_detection_time = 0

    def detect_hardware(self, force_refresh: bool = False) -> HardwareProfile:
        """
        Detect system hardware configuration.

        Args:
            force_refresh: Force hardware re-detection

        Returns:
            Hardware profile with detected components
        """
        current_time = time.time()

        # Use cached result if available and not expired
        if (not force_refresh and
            self._hardware_profile and
            (current_time - self._last_detection_time) < self._detection_cache_ttl):
            return self._hardware_profile

        try:
            # Detect CPU information
            cpu_cores = psutil.cpu_count(logical=False) or 1
            cpu_threads = psutil.cpu_count(logical=True) or 1

            # Detect system memory
            memory_info = psutil.virtual_memory()
            system_memory_gb = int(memory_info.total / (1024**3))

            # Detect GPU devices
            gpu_devices = self._detect_gpu_devices()

            # Detect NVMe devices
            nvme_devices = self._detect_nvme_devices()

            # Platform information
            platform_info = {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            }

            self._hardware_profile = HardwareProfile(
                cpu_cores=cpu_cores,
                cpu_threads=cpu_threads,
                system_memory_gb=system_memory_gb,
                gpu_devices=gpu_devices,
                nvme_devices=nvme_devices,
                platform_info=platform_info
            )

            self._last_detection_time = current_time
            return self._hardware_profile

        except Exception as e:
            print(f"Hardware detection error: {e}")
            # Return minimal profile on error
            return HardwareProfile(
                cpu_cores=1,
                cpu_threads=1,
                system_memory_gb=8,
                gpu_devices=[],
                nvme_devices=[],
                platform_info={'system': 'Unknown'}
            )

    def _detect_gpu_devices(self) -> List[GPUDevice]:
        """Detect available GPU devices."""
        gpu_devices = []

        try:
            # Try to detect NVIDIA GPUs using nvidia-ml-py if available
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()

                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                    gpu_device = GPUDevice(
                        device_id=i,
                        name=name,
                        memory_total_mb=int(memory_info.total / (1024**2)),
                        memory_available_mb=int(memory_info.free / (1024**2)),
                        compute_capability="Unknown",
                        driver_version="Unknown",
                        supports_cuda=True
                    )
                    gpu_devices.append(gpu_device)

            except ImportError:
                # Fallback: Create mock GPU for development
                gpu_devices.append(GPUDevice(
                    device_id=0,
                    name="Mock GPU Device",
                    memory_total_mb=8192,
                    memory_available_mb=7168,
                    compute_capability="8.6",
                    driver_version="Mock",
                    supports_cuda=True
                ))

        except Exception as e:
            print(f"GPU detection error: {e}")

        return gpu_devices

    def _detect_nvme_devices(self) -> List[Dict[str, Any]]:
        """Detect NVMe storage devices."""
        nvme_devices = []

        try:
            # Get disk partitions
            partitions = psutil.disk_partitions()

            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)

                    # Check if it's likely an NVMe device (simplified detection)
                    is_nvme = ('nvme' in partition.device.lower() or
                              'ssd' in partition.opts.lower() or
                              partition.fstype in ['NTFS', 'ext4', 'APFS'])

                    if is_nvme:
                        nvme_device = {
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total_gb': int(usage.total / (1024**3)),
                            'free_gb': int(usage.free / (1024**3)),
                            'used_percent': (usage.used / usage.total) * 100
                        }
                        nvme_devices.append(nvme_device)

                except (PermissionError, OSError):
                    continue

        except Exception as e:
            print(f"NVMe detection error: {e}")

        return nvme_devices

    def get_memory_info(self) -> Dict[str, Any]:
        """Get current memory information."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'used_percent': memory.percent,
                'swap_total_gb': swap.total / (1024**3),
                'swap_used_percent': swap.percent
            }
        except Exception:
            return {
                'total_gb': 16.0,
                'available_gb': 8.0,
                'used_percent': 50.0,
                'swap_total_gb': 4.0,
                'swap_used_percent': 10.0
            }

    def check_allocation_mode_compatibility(self, mode: AllocationMode) -> Tuple[bool, List[str]]:
        """
        Check if allocation mode is compatible with current hardware.

        Args:
            mode: Allocation mode to check

        Returns:
            Tuple of (is_compatible, issues_list)
        """
        issues = []

        if not self._hardware_profile:
            self.detect_hardware()

        if mode == AllocationMode.LEGACY:
            if not self._hardware_profile.gpu_devices:
                issues.append("No GPU devices detected for Legacy mode")
            elif self._hardware_profile.gpu_devices[0].memory_total_mb < 4096:
                issues.append("GPU memory too low for Legacy mode (minimum 4GB)")

        elif mode == AllocationMode.HYBRID:
            if not self._hardware_profile.gpu_devices:
                issues.append("No GPU devices detected for Hybrid mode")
            if self._hardware_profile.system_memory_gb < 16:
                issues.append("System memory too low for Hybrid mode (minimum 16GB)")

        elif mode == AllocationMode.AUTO:
            if self._hardware_profile.system_memory_gb < 8:
                issues.append("System memory too low for Auto IDRAlloc (minimum 8GB)")
            if not self._hardware_profile.nvme_devices:
                issues.append("No NVMe storage detected for Auto IDRAlloc")

        return len(issues) == 0, issues


class ResourceSettingsUI(ThemeAwareUserControl):
    """
    Comprehensive resource allocation and hardware configuration interface.

    Features:
    - IDRAlloc mode selection with compatibility checking
    - GPU device selection with memory display
    - Memory limits configuration with real-time validation
    - NVMe storage path selection with capacity monitoring
    - Performance profile management with optimization presets
    - Thermal limits and monitoring configuration
    - Hardware detection and compatibility assessment
    - Real-time resource monitoring and status updates
    - Configuration import/export and preset management
    - Full theme system integration with responsive design
    - Accessibility compliance and cross-platform compatibility
    """

    def __init__(self,
                 on_settings_change: Optional[Callable[[ResourceSettingsConfig], None]] = None,
                 initial_config: Optional[ResourceSettingsConfig] = None,
                 **kwargs):
        super().__init__(**kwargs)

        # Callbacks
        self._on_settings_change = on_settings_change

        # Configuration
        self._config = initial_config or ResourceSettingsConfig()
        self._original_config = ResourceSettingsConfig()
        self._has_unsaved_changes = False

        # Hardware detection
        self._hardware_detector = HardwareDetector()
        self._hardware_profile: Optional[HardwareProfile] = None

        # UI components
        self._allocation_mode_group: Optional[ft.RadioGroup] = None
        self._gpu_selector: Optional[ft.Dropdown] = None
        self._performance_profile_dropdown: Optional[ft.Dropdown] = None
        self._nvme_path_field: Optional[ft.TextField] = None
        self._memory_limit_sliders: Dict[str, ft.Slider] = {}
        self._thermal_limit_controls: Dict[str, ft.Control] = {}
        self._status_indicators: Dict[str, ft.Control] = {}
        self._validation_messages: Dict[str, ft.Text] = {}

        # State management
        self._is_loading = False
        self._auto_save_enabled = True
        self._validation_timer: Optional[threading.Timer] = None

        # Initialize hardware detection
        self._detect_hardware_async()

    def build(self) -> ft.Control:
        """Build the resource settings interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout_manager()

        # Create main container with responsive layout
        main_container = ft.Container(
            content=ft.Column([
                self._create_header(),
                ft.Divider(color=palette.outline_variant),
                self._create_allocation_mode_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_gpu_selection_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_memory_limits_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_nvme_storage_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_performance_profile_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_thermal_management_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_advanced_options_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_action_buttons()
            ], spacing=spacing.md, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(rlm.get_responsive_padding()),
            bgcolor=palette.surface,
            border_radius=rlm.get_border_radius('medium'),
            border=ft.border.all(1, palette.outline_variant)
        )

        return main_container

    def _create_header(self) -> ft.Control:
        """Create header section with title and status."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Status indicator
        status_icon = ft.Icon(
            name=self.get_icon('SETTINGS'),
            color=palette.primary,
            size=24
        )

        # Unsaved changes indicator
        changes_indicator = ft.Container(
            content=ft.Row([
                ft.Icon(
                    name=self.get_icon('WARNING'),
                    color=palette.warning,
                    size=16
                ),
                ft.Text(
                    "Unsaved changes",
                    style=self.get_text_style('caption'),
                    color=palette.warning
                )
            ], spacing=spacing.xs),
            visible=self._has_unsaved_changes
        )
        self._status_indicators['changes'] = changes_indicator

        return ft.Container(
            content=ft.Row([
                ft.Row([
                    status_icon,
                    ft.Text(
                        "Resource Settings",
                        style=self.get_text_style('h2'),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_600
                    )
                ], spacing=spacing.sm),
                changes_indicator
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md)
        )

    def _create_allocation_mode_section(self) -> ft.Control:
        """Create IDRAlloc mode selection section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create mode cards
        mode_cards = []
        for mode in AllocationMode:
            is_selected = mode == self._config.allocation_mode

            # Check compatibility
            is_compatible, issues = self._hardware_detector.check_allocation_mode_compatibility(mode)

            card_color = palette.primary_container if is_selected else palette.surface_variant
            text_color = palette.text_primary if is_compatible else palette.text_secondary

            mode_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Radio(
                            value=mode.mode_id,
                            active_color=palette.primary,
                            fill_color=palette.primary if is_compatible else palette.text_secondary
                        ),
                        ft.Column([
                            ft.Text(
                                mode.display_name,
                                style=self.get_text_style('body_large'),
                                color=text_color,
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Text(
                                mode.description,
                                style=self.get_text_style('body_small'),
                                color=palette.text_secondary
                            )
                        ], expand=True, spacing=spacing.xs)
                    ], spacing=spacing.sm),
                    # Compatibility issues
                    ft.Column([
                        ft.Text(
                            f"⚠️ {issue}",
                            style=self.get_text_style('caption'),
                            color=palette.warning
                        ) for issue in issues
                    ], spacing=spacing.xs, visible=len(issues) > 0)
                ], spacing=spacing.sm),
                padding=ft.padding.all(spacing.md),
                bgcolor=card_color,
                border_radius=8,
                border=ft.border.all(2, palette.primary if is_selected else palette.outline_variant),
                on_click=lambda e, m=mode: self._on_allocation_mode_change(m)
            )
            mode_cards.append(mode_card)

        # Create radio group for accessibility
        self._allocation_mode_group = ft.RadioGroup(
            content=ft.Column(mode_cards, spacing=spacing.sm),
            value=self._config.allocation_mode.mode_id,
            on_change=self._on_allocation_mode_radio_change
        )

        return self._create_section(
            title="Memory Allocation Mode",
            icon=self.get_icon('MEMORY'),
            content=self._allocation_mode_group,
            description="Select how MikroDok manages memory across GPU, RAM, and storage tiers"
        )

    def _create_gpu_selection_section(self) -> ft.Control:
        """Create GPU device selection section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # GPU dropdown options
        gpu_options = []
        if self._hardware_profile and self._hardware_profile.gpu_devices:
            for gpu in self._hardware_profile.gpu_devices:
                memory_gb = gpu.memory_total_mb / 1024
                available_gb = gpu.memory_available_mb / 1024

                gpu_options.append(ft.dropdown.Option(
                    key=str(gpu.device_id),
                    text=f"{gpu.name} ({memory_gb:.1f}GB, {available_gb:.1f}GB available)"
                ))
        else:
            gpu_options.append(ft.dropdown.Option(
                key="none",
                text="No GPU devices detected"
            ))

        self._gpu_selector = ft.Dropdown(
            options=gpu_options,
            value=str(self._config.selected_gpu_id) if self._config.selected_gpu_id is not None else None,
            on_change=self._on_gpu_selection_change,
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=self.get_text_style('body_medium'),
            hint_text="Select GPU device"
        )

        # GPU status indicator
        gpu_status = ft.Container(
            content=ft.Row([
                ft.Icon(
                    name=self.get_icon('GPU'),
                    color=palette.success if gpu_options[0].key != "none" else palette.warning,
                    size=16
                ),
                ft.Text(
                    f"{len(self._hardware_profile.gpu_devices) if self._hardware_profile else 0} GPU(s) detected",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            padding=ft.padding.only(top=spacing.xs)
        )

        return self._create_section(
            title="GPU Device Selection",
            icon=self.get_icon('GPU'),
            content=ft.Column([
                self._gpu_selector,
                gpu_status
            ], spacing=spacing.sm),
            description="Choose the primary GPU device for training and inference"
        )

    def _create_memory_limits_section(self) -> ft.Control:
        """Create memory limits configuration section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Memory limit configurations
        limit_configs = [
            ("gpu_memory", "GPU Memory Limit", self._config.resource_limits.gpu_memory_limit_percent, "%"),
            ("system_memory", "System Memory Limit", self._config.resource_limits.system_memory_limit_percent, "%"),
            ("nvme_memory", "NVMe Memory Limit", self._config.resource_limits.nvme_memory_limit_percent, "%")
        ]

        limit_controls = []
        for limit_id, title, current_value, unit in limit_configs:
            # Value display
            value_text = ft.Text(
                f"{current_value:.0f}{unit}",
                style=self.get_text_style('body_medium'),
                color=palette.primary,
                weight=ft.FontWeight.W_600
            )

            # Slider control
            slider = ft.Slider(
                min=10,
                max=95,
                value=current_value,
                divisions=17,
                label=f"{current_value:.0f}{unit}",
                on_change=lambda e, lid=limit_id: self._on_memory_limit_change(lid, e.control.value),
                active_color=palette.primary,
                inactive_color=palette.outline_variant,
                thumb_color=palette.primary
            )
            self._memory_limit_sliders[limit_id] = slider

            # Memory info (if available)
            memory_info = self._get_memory_info_for_limit(limit_id)
            info_text = ft.Text(
                memory_info,
                style=self.get_text_style('caption'),
                color=palette.text_secondary
            )

            limit_control = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(
                            title,
                            style=self.get_text_style('body_medium'),
                            color=palette.text_primary,
                            expand=True
                        ),
                        value_text
                    ]),
                    slider,
                    info_text
                ], spacing=spacing.xs),
                padding=ft.padding.all(spacing.sm),
                bgcolor=palette.surface_variant,
                border_radius=8
            )
            limit_controls.append(limit_control)

        # Dynamic limits toggle
        dynamic_toggle = ft.Switch(
            value=self._config.resource_limits.enable_dynamic_limits,
            on_change=self._on_dynamic_limits_toggle,
            active_color=palette.primary
        )

        dynamic_control = ft.Row([
            ft.Text(
                "Enable Dynamic Limits",
                style=self.get_text_style('body_medium'),
                color=palette.text_primary,
                expand=True
            ),
            dynamic_toggle
        ])

        return self._create_section(
            title="Memory Allocation Limits",
            icon=self.get_icon('MEMORY'),
            content=ft.Column([
                *limit_controls,
                ft.Divider(color=palette.outline_variant),
                dynamic_control
            ], spacing=spacing.md),
            description="Configure maximum memory usage for each tier"
        )

    def _create_nvme_storage_section(self) -> ft.Control:
        """Create NVMe storage path selection section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Path input field
        self._nvme_path_field = ft.TextField(
            value=self._config.nvme_storage_path,
            hint_text="Select NVMe storage path for virtual memory",
            on_change=self._on_nvme_path_change,
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=self.get_text_style('body_medium'),
            expand=True
        )

        # Browse button
        browse_button = ft.IconButton(
            icon=self.get_icon('FOLDER_OPEN'),
            on_click=self._on_browse_nvme_path,
            tooltip="Browse for storage path",
            icon_color=palette.primary
        )

        # Storage info
        storage_info = self._get_nvme_storage_info()
        info_container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Available NVMe Devices:",
                    style=self.get_text_style('body_small'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                *[ft.Text(
                    f"• {device['device']} - {device['free_gb']:.1f}GB free of {device['total_gb']:.1f}GB",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                ) for device in storage_info]
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=8
        )

        return self._create_section(
            title="NVMe Storage Configuration",
            icon=self.get_icon('DISK'),
            content=ft.Column([
                ft.Row([
                    self._nvme_path_field,
                    browse_button
                ], spacing=spacing.sm),
                info_container
            ], spacing=spacing.md),
            description="Configure storage location for virtual memory extension"
        )

    def _create_performance_profile_section(self) -> ft.Control:
        """Create performance profile selection section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Performance profile dropdown
        profile_options = [
            ft.dropdown.Option(
                key=profile.profile_id,
                text=f"{profile.display_name} - {profile.description}"
            ) for profile in PerformanceProfile
        ]

        self._performance_profile_dropdown = ft.Dropdown(
            options=profile_options,
            value=self._config.performance_profile.profile_id,
            on_change=self._on_performance_profile_change,
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=self.get_text_style('body_medium')
        )

        # Profile description
        profile_description = ft.Text(
            self._config.performance_profile.description,
            style=self.get_text_style('body_small'),
            color=palette.text_secondary
        )

        return self._create_section(
            title="Performance Profile",
            icon=self.get_icon('SPEED'),
            content=ft.Column([
                self._performance_profile_dropdown,
                profile_description
            ], spacing=spacing.sm),
            description="Choose optimization strategy for performance vs efficiency"
        )

    def _create_thermal_management_section(self) -> ft.Control:
        """Create thermal management configuration section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Thermal monitoring toggle
        thermal_toggle = ft.Switch(
            value=self._config.thermal_config.enable_thermal_monitoring,
            on_change=self._on_thermal_monitoring_toggle,
            active_color=palette.primary
        )

        # Temperature limit controls
        temp_controls = []
        temp_configs = [
            ("gpu_temp", "GPU Temperature Limit", self._config.thermal_config.gpu_temp_limit_celsius, "°C"),
            ("cpu_temp", "CPU Temperature Limit", self._config.thermal_config.cpu_temp_limit_celsius, "°C"),
            ("throttle_temp", "Throttle Threshold", self._config.thermal_config.thermal_throttle_threshold, "°C")
        ]

        for temp_id, title, current_value, unit in temp_configs:
            temp_field = ft.TextField(
                value=str(current_value),
                hint_text=f"Enter {title.lower()}",
                on_change=lambda e, tid=temp_id: self._on_thermal_limit_change(tid, e.control.value),
                bgcolor=palette.surface_variant,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                text_style=self.get_text_style('body_medium'),
                width=100,
                suffix_text=unit
            )
            self._thermal_limit_controls[temp_id] = temp_field

            temp_control = ft.Row([
                ft.Text(
                    title,
                    style=self.get_text_style('body_medium'),
                    color=palette.text_primary,
                    expand=True
                ),
                temp_field
            ])
            temp_controls.append(temp_control)

        return self._create_section(
            title="Thermal Management",
            icon=self.get_icon('THERMAL'),
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "Enable Thermal Monitoring",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary,
                        expand=True
                    ),
                    thermal_toggle
                ]),
                ft.Divider(color=palette.outline_variant),
                *temp_controls
            ], spacing=spacing.md),
            description="Configure thermal limits and monitoring"
        )

    def _create_advanced_options_section(self) -> ft.Control:
        """Create advanced options section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Advanced option toggles
        options = [
            ("hardware_monitoring", "Enable Hardware Monitoring", self._config.enable_hardware_monitoring),
            ("auto_optimize", "Auto-Optimize Allocation", self._config.auto_optimize_allocation),
            ("memory_compression", "Enable Memory Compression", self._config.enable_memory_compression),
            ("checkpoint_optimization", "Checkpoint Memory Optimization", self._config.checkpoint_memory_optimization)
        ]

        option_controls = []
        for option_id, title, current_value in options:
            toggle = ft.Switch(
                value=current_value,
                on_change=lambda e, oid=option_id: self._on_advanced_option_toggle(oid, e.control.value),
                active_color=palette.primary
            )

            option_control = ft.Row([
                ft.Text(
                    title,
                    style=self.get_text_style('body_medium'),
                    color=palette.text_primary,
                    expand=True
                ),
                toggle
            ])
            option_controls.append(option_control)

        return self._create_section(
            title="Advanced Options",
            icon=self.get_icon('TUNE'),
            content=ft.Column(option_controls, spacing=spacing.md),
            description="Advanced resource management and optimization settings"
        )

    def _create_action_buttons(self) -> ft.Control:
        """Create action buttons section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Action buttons
        save_button = ft.ElevatedButton(
            text="Save Settings",
            icon=self.get_icon('SAVE'),
            on_click=self._on_save_settings,
            bgcolor=palette.primary,
            color=palette.on_primary,
            disabled=not self._has_unsaved_changes
        )

        reset_button = ft.OutlinedButton(
            text="Reset to Defaults",
            icon=self.get_icon('RESTORE'),
            on_click=self._on_reset_settings,
            color=palette.primary
        )

        export_button = ft.TextButton(
            text="Export Config",
            icon=self.get_icon('DOWNLOAD'),
            on_click=self._on_export_config,
            color=palette.primary
        )

        import_button = ft.TextButton(
            text="Import Config",
            icon=self.get_icon('UPLOAD'),
            on_click=self._on_import_config,
            color=palette.primary
        )

        return ft.Container(
            content=ft.Row([
                ft.Row([
                    save_button,
                    reset_button
                ], spacing=spacing.md),
                ft.Row([
                    export_button,
                    import_button
                ], spacing=spacing.sm)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md)
        )

    def _create_section(self, title: str, icon: str, content: ft.Control, description: str = "") -> ft.Control:
        """Create a settings section with consistent styling."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        header = ft.Row([
            ft.Icon(
                name=icon,
                color=palette.primary,
                size=20
            ),
            ft.Text(
                title,
                style=self.get_text_style('h3'),
                color=palette.text_primary,
                weight=ft.FontWeight.W_600
            )
        ], spacing=spacing.sm)

        section_content = [header]

        if description:
            section_content.append(
                ft.Text(
                    description,
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                )
            )

        section_content.append(content)

        return ft.Container(
            content=ft.Column(section_content, spacing=spacing.md),
            padding=ft.padding.all(spacing.lg)
        )

    # Event Handlers
    def _on_allocation_mode_change(self, mode: AllocationMode) -> None:
        """Handle allocation mode change."""
        if mode != self._config.allocation_mode:
            self._config.allocation_mode = mode
            self._mark_changes()

            # Update radio group
            if self._allocation_mode_group:
                self._allocation_mode_group.value = mode.mode_id
                self._allocation_mode_group.update()

            # Trigger validation
            self._validate_configuration()

    def _on_allocation_mode_radio_change(self, e: ft.ControlEvent) -> None:
        """Handle radio group change for allocation mode."""
        for mode in AllocationMode:
            if mode.mode_id == e.control.value:
                self._on_allocation_mode_change(mode)
                break

    def _on_gpu_selection_change(self, e: ft.ControlEvent) -> None:
        """Handle GPU selection change."""
        try:
            gpu_id = int(e.control.value) if e.control.value != "none" else None
            if gpu_id != self._config.selected_gpu_id:
                self._config.selected_gpu_id = gpu_id
                self._mark_changes()
        except (ValueError, TypeError):
            pass

    def _on_memory_limit_change(self, limit_id: str, value: float) -> None:
        """Handle memory limit slider change."""
        if limit_id == "gpu_memory":
            self._config.resource_limits.gpu_memory_limit_percent = value
        elif limit_id == "system_memory":
            self._config.resource_limits.system_memory_limit_percent = value
        elif limit_id == "nvme_memory":
            self._config.resource_limits.nvme_memory_limit_percent = value

        self._mark_changes()

        # Update slider label
        if limit_id in self._memory_limit_sliders:
            slider = self._memory_limit_sliders[limit_id]
            slider.label = f"{value:.0f}%"
            slider.update()

    def _on_dynamic_limits_toggle(self, e: ft.ControlEvent) -> None:
        """Handle dynamic limits toggle."""
        self._config.resource_limits.enable_dynamic_limits = e.control.value
        self._mark_changes()

    def _on_nvme_path_change(self, e: ft.ControlEvent) -> None:
        """Handle NVMe path change."""
        self._config.nvme_storage_path = e.control.value
        self._mark_changes()
        self._validate_nvme_path()

    def _on_browse_nvme_path(self, e: ft.ControlEvent) -> None:
        """Handle browse button click for NVMe path."""
        # In a real implementation, this would open a directory picker
        # For now, we'll use a placeholder
        if self._nvme_path_field and self._hardware_profile:
            # Auto-select first available NVMe device
            nvme_devices = self._hardware_profile.nvme_devices
            if nvme_devices:
                self._nvme_path_field.value = nvme_devices[0]['mountpoint']
                self._nvme_path_field.update()
                self._on_nvme_path_change(e)

    def _on_performance_profile_change(self, e: ft.ControlEvent) -> None:
        """Handle performance profile change."""
        for profile in PerformanceProfile:
            if profile.profile_id == e.control.value:
                self._config.performance_profile = profile
                self._mark_changes()
                break

    def _on_thermal_monitoring_toggle(self, e: ft.ControlEvent) -> None:
        """Handle thermal monitoring toggle."""
        self._config.thermal_config.enable_thermal_monitoring = e.control.value
        self._mark_changes()

    def _on_thermal_limit_change(self, temp_id: str, value: str) -> None:
        """Handle thermal limit change."""
        try:
            temp_value = int(value)
            if temp_id == "gpu_temp":
                self._config.thermal_config.gpu_temp_limit_celsius = temp_value
            elif temp_id == "cpu_temp":
                self._config.thermal_config.cpu_temp_limit_celsius = temp_value
            elif temp_id == "throttle_temp":
                self._config.thermal_config.thermal_throttle_threshold = temp_value

            self._mark_changes()
        except ValueError:
            pass

    def _on_advanced_option_toggle(self, option_id: str, value: bool) -> None:
        """Handle advanced option toggle."""
        if option_id == "hardware_monitoring":
            self._config.enable_hardware_monitoring = value
        elif option_id == "auto_optimize":
            self._config.auto_optimize_allocation = value
        elif option_id == "memory_compression":
            self._config.enable_memory_compression = value
        elif option_id == "checkpoint_optimization":
            self._config.checkpoint_memory_optimization = value

        self._mark_changes()

    def _on_save_settings(self, e: ft.ControlEvent) -> None:
        """Handle save settings button click."""
        if self._validate_configuration():
            self._save_configuration()
            self._has_unsaved_changes = False
            self._update_status_indicators()

            if self._on_settings_change:
                self._on_settings_change(self._config)

    def _on_reset_settings(self, e: ft.ControlEvent) -> None:
        """Handle reset settings button click."""
        self._config = ResourceSettingsConfig()
        self._has_unsaved_changes = True
        self._update_ui_from_config()
        self._update_status_indicators()

    def _on_export_config(self, e: ft.ControlEvent) -> None:
        """Handle export configuration button click."""
        # In a real implementation, this would open a file save dialog
        config_data = self._config.to_dict()
        print("Export configuration:", json.dumps(config_data, indent=2))

    def _on_import_config(self, e: ft.ControlEvent) -> None:
        """Handle import configuration button click."""
        # In a real implementation, this would open a file picker
        print("Import configuration requested")

    # Helper Methods
    def _detect_hardware_async(self) -> None:
        """Detect hardware asynchronously."""
        def detect():
            self._hardware_profile = self._hardware_detector.detect_hardware()
            if self.page:
                self.page.update()

        threading.Thread(target=detect, daemon=True).start()

    def _get_memory_info_for_limit(self, limit_id: str) -> str:
        """Get memory information text for a limit type."""
        if not self._hardware_profile:
            return "Hardware detection in progress..."

        memory_info = self._hardware_detector.get_memory_info()

        if limit_id == "gpu_memory":
            if self._hardware_profile.gpu_devices:
                gpu = self._hardware_profile.gpu_devices[0]
                return f"GPU: {gpu.memory_total_mb / 1024:.1f}GB total"
            return "No GPU detected"
        elif limit_id == "system_memory":
            return f"System: {memory_info['total_gb']:.1f}GB total, {memory_info['available_gb']:.1f}GB available"
        elif limit_id == "nvme_memory":
            if self._hardware_profile.nvme_devices:
                total_nvme = sum(device['total_gb'] for device in self._hardware_profile.nvme_devices)
                return f"NVMe: {total_nvme:.1f}GB total across {len(self._hardware_profile.nvme_devices)} device(s)"
            return "No NVMe devices detected"

        return ""

    def _get_nvme_storage_info(self) -> List[Dict[str, Any]]:
        """Get NVMe storage device information."""
        if self._hardware_profile and self._hardware_profile.nvme_devices:
            return self._hardware_profile.nvme_devices
        return []

    def _mark_changes(self) -> None:
        """Mark that configuration has unsaved changes."""
        self._has_unsaved_changes = True
        self._update_status_indicators()

        # Auto-save if enabled
        if self._auto_save_enabled:
            self._schedule_auto_save()

    def _schedule_auto_save(self) -> None:
        """Schedule auto-save with debouncing."""
        if self._validation_timer:
            self._validation_timer.cancel()

        self._validation_timer = threading.Timer(2.0, self._auto_save)
        self._validation_timer.start()

    def _auto_save(self) -> None:
        """Perform auto-save."""
        if self._has_unsaved_changes and self._validate_configuration():
            self._save_configuration()
            self._has_unsaved_changes = False
            self._update_status_indicators()

    def _validate_configuration(self) -> bool:
        """Validate current configuration."""
        is_valid = True

        # Validate allocation mode compatibility
        if self._hardware_profile:
            is_compatible, issues = self._hardware_detector.check_allocation_mode_compatibility(
                self._config.allocation_mode
            )
            if not is_compatible:
                is_valid = False

        # Validate memory limits
        limits = self._config.resource_limits
        if limits.gpu_memory_limit_percent > 95 or limits.gpu_memory_limit_percent < 10:
            is_valid = False
        if limits.system_memory_limit_percent > 95 or limits.system_memory_limit_percent < 10:
            is_valid = False
        if limits.nvme_memory_limit_percent > 95 or limits.nvme_memory_limit_percent < 10:
            is_valid = False

        # Validate thermal limits
        thermal = self._config.thermal_config
        if thermal.gpu_temp_limit_celsius > 100 or thermal.gpu_temp_limit_celsius < 60:
            is_valid = False
        if thermal.cpu_temp_limit_celsius > 100 or thermal.cpu_temp_limit_celsius < 60:
            is_valid = False

        return is_valid

    def _validate_nvme_path(self) -> bool:
        """Validate NVMe storage path."""
        if not self._config.nvme_storage_path:
            return True  # Empty path is allowed

        path = Path(self._config.nvme_storage_path)
        return path.exists() and path.is_dir()

    def _save_configuration(self) -> None:
        """Save configuration to persistent storage."""
        try:
            # In a real implementation, this would save to database or file
            config_data = self._config.to_dict()
            print("Saving configuration:", json.dumps(config_data, indent=2))
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def _update_status_indicators(self) -> None:
        """Update status indicators in the UI."""
        if 'changes' in self._status_indicators:
            changes_indicator = self._status_indicators['changes']
            changes_indicator.visible = self._has_unsaved_changes
            changes_indicator.update()

    def _update_ui_from_config(self) -> None:
        """Update UI components from current configuration."""
        # Update allocation mode
        if self._allocation_mode_group:
            self._allocation_mode_group.value = self._config.allocation_mode.mode_id
            self._allocation_mode_group.update()

        # Update GPU selection
        if self._gpu_selector:
            self._gpu_selector.value = str(self._config.selected_gpu_id) if self._config.selected_gpu_id is not None else None
            self._gpu_selector.update()

        # Update memory limit sliders
        for limit_id, slider in self._memory_limit_sliders.items():
            if limit_id == "gpu_memory":
                slider.value = self._config.resource_limits.gpu_memory_limit_percent
            elif limit_id == "system_memory":
                slider.value = self._config.resource_limits.system_memory_limit_percent
            elif limit_id == "nvme_memory":
                slider.value = self._config.resource_limits.nvme_memory_limit_percent
            slider.update()

        # Update NVMe path
        if self._nvme_path_field:
            self._nvme_path_field.value = self._config.nvme_storage_path
            self._nvme_path_field.update()

        # Update performance profile
        if self._performance_profile_dropdown:
            self._performance_profile_dropdown.value = self._config.performance_profile.profile_id
            self._performance_profile_dropdown.update()

        # Update thermal controls
        for temp_id, control in self._thermal_limit_controls.items():
            if temp_id == "gpu_temp":
                control.value = str(self._config.thermal_config.gpu_temp_limit_celsius)
            elif temp_id == "cpu_temp":
                control.value = str(self._config.thermal_config.cpu_temp_limit_celsius)
            elif temp_id == "throttle_temp":
                control.value = str(self._config.thermal_config.thermal_throttle_threshold)
            control.update()

    # Public Methods
    def get_configuration(self) -> ResourceSettingsConfig:
        """Get current configuration."""
        return self._config

    def set_configuration(self, config: ResourceSettingsConfig) -> None:
        """Set configuration and update UI."""
        self._config = config
        self._update_ui_from_config()
        self._mark_changes()

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_unsaved_changes

    def refresh_hardware_detection(self) -> None:
        """Refresh hardware detection."""
        self._detect_hardware_async()
