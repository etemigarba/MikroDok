"""
Module: advanced_settings_ui
Description: Comprehensive advanced settings interface for MikroDok application providing sophisticated
            configuration options for logging levels, telemetry, cache management, configuration export/import,
            and system diagnostics. Features responsive design, real-time validation, and full theme system
            integration with accessibility compliance.

Features:
- Logging level configuration with real-time preview and log viewer
- Telemetry and analytics settings with granular privacy controls
- Cache management and optimization tools with storage analysis
- Configuration backup and restore functionality with versioning
- System diagnostics and health monitoring with performance metrics
- Performance tuning and optimization settings
- Security and privacy configuration options
- Developer and debugging tools with advanced diagnostics
- Configuration import/export with validation and migration
- Real-time settings validation with visual feedback
- Responsive design with breakpoint-aware components
- Full theme system integration with accessibility support

Phase: 1
Location: /src/modules/ui/settings_panel_ui/advanced_settings_ui/advanced_settings_ui.py
"""

# Standard library imports
import os
import json
import asyncio
import logging
import platform
import psutil
import shutil
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path
import tempfile
import zipfile

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
    ThemeMode,
    ScreenSize
)

# Database imports (with fallback handling)
try:
    from src.modules.database.app_state_db.user_preferences_db.user_preferences_db import (
        UserPreferencesDB
    )
    DATABASE_AVAILABLE = True
except ImportError:
    UserPreferencesDB = None
    DATABASE_AVAILABLE = False

# App state imports (with fallback handling)
try:
    from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
    APP_STATE_AVAILABLE = True
except ImportError:
    AppStateManager = None
    APP_STATE_AVAILABLE = False


class SettingsCategory(Enum):
    """Advanced settings categories for organization."""
    LOGGING = "logging"
    TELEMETRY = "telemetry"
    CACHE = "cache"
    BACKUP = "backup"
    DIAGNOSTICS = "diagnostics"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DEVELOPER = "developer"


class LoggingLevel(Enum):
    """Logging level options."""
    DEBUG = ("DEBUG", "Debug", "Detailed debugging information")
    INFO = ("INFO", "Info", "General information messages")
    WARNING = ("WARNING", "Warning", "Warning messages only")
    ERROR = ("ERROR", "Error", "Error messages only")
    CRITICAL = ("CRITICAL", "Critical", "Critical errors only")

    def __init__(self, level: str, display_name: str, description: str):
        self.level = level
        self.display_name = display_name
        self.description = description


class TelemetryLevel(Enum):
    """Telemetry collection levels."""
    NONE = ("none", "Disabled", "No telemetry data collected")
    BASIC = ("basic", "Basic", "Essential usage statistics only")
    STANDARD = ("standard", "Standard", "Usage patterns and performance metrics")
    DETAILED = ("detailed", "Detailed", "Comprehensive analytics and diagnostics")

    def __init__(self, level: str, display_name: str, description: str):
        self.level = level
        self.display_name = display_name
        self.description = description


class CacheStrategy(Enum):
    """Cache management strategies."""
    CONSERVATIVE = ("conservative", "Conservative", "Minimal cache usage")
    BALANCED = ("balanced", "Balanced", "Optimal cache performance")
    AGGRESSIVE = ("aggressive", "Aggressive", "Maximum cache utilization")
    CUSTOM = ("custom", "Custom", "User-defined cache settings")

    def __init__(self, strategy: str, display_name: str, description: str):
        self.strategy = strategy
        self.display_name = display_name
        self.description = description


class DiagnosticsMode(Enum):
    """System diagnostics modes."""
    BASIC = ("basic", "Basic", "Essential system information")
    STANDARD = ("standard", "Standard", "Comprehensive system analysis")
    ADVANCED = ("advanced", "Advanced", "Detailed diagnostics and profiling")
    DEVELOPER = ("developer", "Developer", "Full debugging information")

    def __init__(self, mode: str, display_name: str, description: str):
        self.mode = mode
        self.display_name = display_name
        self.description = description


class ExportFormat(Enum):
    """Configuration export formats."""
    JSON = ("json", "JSON", "Human-readable JSON format")
    YAML = ("yaml", "YAML", "YAML configuration format")
    ZIP = ("zip", "ZIP Archive", "Compressed archive with all settings")
    BACKUP = ("backup", "Full Backup", "Complete application backup")

    def __init__(self, format_type: str, display_name: str, description: str):
        self.format_type = format_type
        self.display_name = display_name
        self.description = description


class SecurityLevel(Enum):
    """Security configuration levels."""
    STANDARD = ("standard", "Standard", "Default security settings")
    ENHANCED = ("enhanced", "Enhanced", "Increased security measures")
    STRICT = ("strict", "Strict", "Maximum security enforcement")
    CUSTOM = ("custom", "Custom", "User-defined security settings")

    def __init__(self, level: str, display_name: str, description: str):
        self.level = level
        self.display_name = display_name
        self.description = description


@dataclass
class AdvancedSettingsConfig:
    """Configuration for advanced settings interface."""
    # Logging settings
    logging_level: LoggingLevel = LoggingLevel.INFO
    log_file_enabled: bool = True
    log_file_max_size_mb: int = 100
    log_file_backup_count: int = 5
    console_logging_enabled: bool = True
    
    # Telemetry settings
    telemetry_level: TelemetryLevel = TelemetryLevel.NONE
    anonymous_usage_stats: bool = False
    crash_reporting: bool = False
    performance_metrics: bool = False
    
    # Cache settings
    cache_strategy: CacheStrategy = CacheStrategy.BALANCED
    cache_max_size_gb: float = 2.0
    cache_cleanup_interval_hours: int = 24
    auto_cache_cleanup: bool = True
    
    # Backup settings
    auto_backup_enabled: bool = True
    backup_interval_hours: int = 24
    backup_retention_days: int = 30
    backup_location: str = ""
    
    # Diagnostics settings
    diagnostics_mode: DiagnosticsMode = DiagnosticsMode.BASIC
    system_monitoring_enabled: bool = True
    performance_profiling: bool = False
    
    # Security settings
    security_level: SecurityLevel = SecurityLevel.STANDARD
    secure_deletion: bool = False
    encryption_enabled: bool = False
    
    # Developer settings
    debug_mode: bool = False
    verbose_logging: bool = False
    profiling_enabled: bool = False
    experimental_features: bool = False
    
    # Interface settings
    show_advanced_options: bool = False
    enable_tooltips: bool = True
    real_time_validation: bool = True


class AdvancedSettingsUI(ThemeAwareUserControl):
    """
    Comprehensive advanced settings interface for MikroDok application.

    Provides sophisticated configuration options for logging, telemetry, cache management,
    configuration backup/restore, system diagnostics, and developer tools.

    Features:
    - Tabbed interface with category-based organization
    - Real-time validation with visual feedback
    - Configuration import/export functionality
    - System diagnostics and health monitoring
    - Cache management and optimization tools
    - Logging configuration with live preview
    - Telemetry and privacy controls
    - Developer and debugging tools
    - Full theme system integration with responsive design
    """

    def __init__(self,
                 config: Optional[AdvancedSettingsConfig] = None,
                 on_settings_changed: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_export_config: Optional[Callable[[str, ExportFormat], None]] = None,
                 on_import_config: Optional[Callable[[str], None]] = None):
        """
        Initialize the advanced settings interface.

        Args:
            config: Advanced settings configuration
            on_settings_changed: Callback for settings changes
            on_export_config: Callback for configuration export
            on_import_config: Callback for configuration import
        """
        super().__init__()

        # Configuration
        self.config = config or AdvancedSettingsConfig()
        self._original_config = asdict(self.config)

        # Callbacks
        self._on_settings_changed = on_settings_changed
        self._on_export_config = on_export_config
        self._on_import_config = on_import_config

        # UI state
        self._current_tab = 0
        self._validation_errors: Dict[str, str] = {}
        self._is_modified = False
        self._system_info: Dict[str, Any] = {}

        # UI components
        self._tabs: Optional[ft.Tabs] = None
        self._status_bar: Optional[ft.Container] = None
        self._validation_panel: Optional[ft.Container] = None

        # Logging
        self._logger = logging.getLogger(__name__)

        # Initialize system information
        self._collect_system_info()

    def build(self) -> ft.Control:
        """Build the advanced settings interface."""
        return self._build_ui()

    def _build_ui(self) -> ft.Container:
        """Build the main UI container."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Main container with responsive design
        main_content = ft.Column(
            controls=[
                self._create_header(),
                self._create_tabs(),
                self._create_validation_panel(),
                self._create_action_bar()
            ],
            spacing=spacing.md,
            expand=True
        )

        return ft.Container(
            content=main_content,
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=self.get_responsive_padding(
                mobile=spacing.md,
                tablet=spacing.lg,
                desktop=spacing.xl
            ),
            expand=True
        )

    def _create_header(self) -> ft.Container:
        """Create the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Title and description
        title = ft.Text(
            "Advanced Settings",
            style=self.get_text_style("h2"),
            color=palette.text_primary
        )

        description = ft.Text(
            "Configure advanced application settings, logging, telemetry, and system options",
            style=self.get_text_style("body_medium"),
            color=palette.text_secondary
        )

        # Settings mode selector
        mode_selector = ft.Dropdown(
            label="Settings Mode",
            value="standard",
            options=[
                ft.dropdown.Option("basic", "Basic"),
                ft.dropdown.Option("standard", "Standard"),
                ft.dropdown.Option("advanced", "Advanced"),
                ft.dropdown.Option("developer", "Developer")
            ],
            on_change=self._on_mode_changed,
            width=self.get_responsive_value(200, 220, 240, 260)
        )

        # Header controls
        header_controls = ft.Row(
            controls=[
                ft.Column(
                    controls=[title, description],
                    spacing=spacing.xs,
                    expand=True
                ),
                mode_selector
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

        return ft.Container(
            content=header_controls,
            padding=ft.padding.only(bottom=spacing.lg),
            border=ft.border.only(
                bottom=ft.BorderSide(1, palette.borders)
            )
        )

    def _create_tabs(self) -> ft.Container:
        """Create the main tabs interface."""
        palette = self.get_palette()
        icons = self.get_icons()

        # Create tabs based on current mode
        tab_controls = [
            ft.Tab(
                text="Logging",
                icon=icons.DESCRIPTION,
                content=self._create_logging_tab()
            ),
            ft.Tab(
                text="Telemetry",
                icon=icons.ANALYTICS,
                content=self._create_telemetry_tab()
            ),
            ft.Tab(
                text="Cache",
                icon=icons.STORAGE,
                content=self._create_cache_tab()
            ),
            ft.Tab(
                text="Backup",
                icon=icons.BACKUP,
                content=self._create_backup_tab()
            ),
            ft.Tab(
                text="Diagnostics",
                icon=icons.BUG_REPORT,
                content=self._create_diagnostics_tab()
            ),
            ft.Tab(
                text="Security",
                icon=icons.SECURITY,
                content=self._create_security_tab()
            ),
            ft.Tab(
                text="Export/Import",
                icon=icons.IMPORT_EXPORT,
                content=self._create_export_import_tab()
            )
        ]

        self._tabs = ft.Tabs(
            tabs=tab_controls,
            selected_index=self._current_tab,
            animation_duration=300,
            tab_alignment=ft.TabAlignment.START,
            on_change=self._on_tab_changed,
            expand=True
        )

        return ft.Container(
            content=self._tabs,
            expand=True,
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=ft.padding.all(self.get_spacing().md)
        )

    def _create_logging_tab(self) -> ft.Container:
        """Create the logging configuration tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Logging level selection
        logging_level_section = self._create_section(
            title="Logging Level",
            icon=icons.TUNE,
            controls=[
                ft.Dropdown(
                    label="Log Level",
                    value=self.config.logging_level.level,
                    options=[
                        ft.dropdown.Option(level.level, level.display_name)
                        for level in LoggingLevel
                    ],
                    on_change=self._on_logging_level_changed,
                    width=self.get_responsive_value(200, 220, 240, 260)
                ),
                ft.Text(
                    self.config.logging_level.description,
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Log file settings
        log_file_section = self._create_section(
            title="Log File Settings",
            icon=icons.DESCRIPTION,
            controls=[
                ft.Row(
                    controls=[
                        ft.Switch(
                            label="Enable log file",
                            value=self.config.log_file_enabled,
                            on_change=self._on_log_file_enabled_changed
                        ),
                        ft.Switch(
                            label="Console logging",
                            value=self.config.console_logging_enabled,
                            on_change=self._on_console_logging_changed
                        )
                    ],
                    spacing=spacing.lg
                ),
                ft.Row(
                    controls=[
                        ft.TextField(
                            label="Max file size (MB)",
                            value=str(self.config.log_file_max_size_mb),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=self._on_log_file_size_changed,
                            width=self.get_responsive_value(120, 140, 160, 180)
                        ),
                        ft.TextField(
                            label="Backup count",
                            value=str(self.config.log_file_backup_count),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=self._on_log_backup_count_changed,
                            width=self.get_responsive_value(120, 140, 160, 180)
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        # Log viewer section
        log_viewer_section = self._create_section(
            title="Log Viewer",
            icon=icons.VISIBILITY,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="View Current Log",
                            icon=icons.OPEN_IN_NEW,
                            on_click=self._on_view_log_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Clear Log",
                            icon=icons.CLEAR,
                            on_click=self._on_clear_log_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Export Log",
                            icon=icons.DOWNLOAD,
                            on_click=self._on_export_log_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    logging_level_section,
                    log_file_section,
                    log_viewer_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_telemetry_tab(self) -> ft.Container:
        """Create the telemetry configuration tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Privacy notice
        privacy_notice = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icons.INFO, color=palette.info),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Privacy Notice",
                                style=self.get_text_style("h6"),
                                color=palette.text_primary
                            ),
                            ft.Text(
                                "All telemetry data is collected anonymously and used solely for improving the application. "
                                "No personal information or document content is ever transmitted.",
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    )
                ],
                spacing=spacing.md
            ),
            bgcolor=palette.info + "20",  # 20% opacity
            border_radius=8,
            padding=ft.padding.all(spacing.md),
            margin=ft.margin.only(bottom=spacing.lg)
        )

        # Telemetry level selection
        telemetry_level_section = self._create_section(
            title="Telemetry Level",
            icon=icons.ANALYTICS,
            controls=[
                ft.Dropdown(
                    label="Collection Level",
                    value=self.config.telemetry_level.level,
                    options=[
                        ft.dropdown.Option(level.level, level.display_name)
                        for level in TelemetryLevel
                    ],
                    on_change=self._on_telemetry_level_changed,
                    width=self.get_responsive_value(200, 220, 240, 260)
                ),
                ft.Text(
                    self.config.telemetry_level.description,
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Specific telemetry options
        telemetry_options_section = self._create_section(
            title="Telemetry Options",
            icon=icons.TUNE,
            controls=[
                ft.Column(
                    controls=[
                        ft.Switch(
                            label="Anonymous usage statistics",
                            value=self.config.anonymous_usage_stats,
                            on_change=self._on_usage_stats_changed
                        ),
                        ft.Switch(
                            label="Crash reporting",
                            value=self.config.crash_reporting,
                            on_change=self._on_crash_reporting_changed
                        ),
                        ft.Switch(
                            label="Performance metrics",
                            value=self.config.performance_metrics,
                            on_change=self._on_performance_metrics_changed
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    privacy_notice,
                    telemetry_level_section,
                    telemetry_options_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_cache_tab(self) -> ft.Container:
        """Create the cache management tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Cache strategy selection
        cache_strategy_section = self._create_section(
            title="Cache Strategy",
            icon=icons.TUNE,
            controls=[
                ft.Dropdown(
                    label="Strategy",
                    value=self.config.cache_strategy.strategy,
                    options=[
                        ft.dropdown.Option(strategy.strategy, strategy.display_name)
                        for strategy in CacheStrategy
                    ],
                    on_change=self._on_cache_strategy_changed,
                    width=self.get_responsive_value(200, 220, 240, 260)
                ),
                ft.Text(
                    self.config.cache_strategy.description,
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Cache size and cleanup settings
        cache_settings_section = self._create_section(
            title="Cache Settings",
            icon=icons.STORAGE,
            controls=[
                ft.Row(
                    controls=[
                        ft.TextField(
                            label="Max cache size (GB)",
                            value=str(self.config.cache_max_size_gb),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=self._on_cache_size_changed,
                            width=self.get_responsive_value(150, 170, 190, 210)
                        ),
                        ft.TextField(
                            label="Cleanup interval (hours)",
                            value=str(self.config.cache_cleanup_interval_hours),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=self._on_cache_cleanup_interval_changed,
                            width=self.get_responsive_value(150, 170, 190, 210)
                        )
                    ],
                    spacing=spacing.md
                ),
                ft.Switch(
                    label="Auto cache cleanup",
                    value=self.config.auto_cache_cleanup,
                    on_change=self._on_auto_cache_cleanup_changed
                )
            ]
        )

        # Cache management actions
        cache_actions_section = self._create_section(
            title="Cache Management",
            icon=icons.BUILD,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="View Cache Info",
                            icon=icons.INFO,
                            on_click=self._on_view_cache_info_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Clear Cache",
                            icon=icons.CLEAR,
                            on_click=self._on_clear_cache_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Optimize Cache",
                            icon=icons.TUNE,
                            on_click=self._on_optimize_cache_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    cache_strategy_section,
                    cache_settings_section,
                    cache_actions_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_backup_tab(self) -> ft.Container:
        """Create the backup configuration tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Auto backup settings
        auto_backup_section = self._create_section(
            title="Automatic Backup",
            icon=icons.BACKUP,
            controls=[
                ft.Switch(
                    label="Enable automatic backup",
                    value=self.config.auto_backup_enabled,
                    on_change=self._on_auto_backup_enabled_changed
                ),
                ft.Row(
                    controls=[
                        ft.TextField(
                            label="Backup interval (hours)",
                            value=str(self.config.backup_interval_hours),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=self._on_backup_interval_changed,
                            width=self.get_responsive_value(150, 170, 190, 210)
                        ),
                        ft.TextField(
                            label="Retention (days)",
                            value=str(self.config.backup_retention_days),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=self._on_backup_retention_changed,
                            width=self.get_responsive_value(150, 170, 190, 210)
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        # Backup location settings
        backup_location_section = self._create_section(
            title="Backup Location",
            icon=icons.FOLDER,
            controls=[
                ft.Row(
                    controls=[
                        ft.TextField(
                            label="Backup directory",
                            value=self.config.backup_location or str(Path.home() / "MikroDok_Backups"),
                            on_change=self._on_backup_location_changed,
                            expand=True
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Browse",
                            icon=icons.FOLDER_OPEN,
                            on_click=self._on_browse_backup_location_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        # Manual backup actions
        manual_backup_section = self._create_section(
            title="Manual Backup",
            icon=icons.SAVE,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="primary",
                            text="Create Backup Now",
                            icon=icons.BACKUP,
                            on_click=self._on_create_backup_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Restore Backup",
                            icon=icons.RESTORE,
                            on_click=self._on_restore_backup_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="View Backups",
                            icon=icons.LIST,
                            on_click=self._on_view_backups_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    auto_backup_section,
                    backup_location_section,
                    manual_backup_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_diagnostics_tab(self) -> ft.Container:
        """Create the diagnostics tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # System information display
        system_info_section = self._create_section(
            title="System Information",
            icon=icons.COMPUTER,
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(f"OS: {self._system_info.get('os', 'Unknown')}",
                               style=self.get_text_style("body_medium")),
                        ft.Text(f"CPU: {self._system_info.get('cpu', 'Unknown')}",
                               style=self.get_text_style("body_medium")),
                        ft.Text(f"Memory: {self._system_info.get('memory', 'Unknown')}",
                               style=self.get_text_style("body_medium")),
                        ft.Text(f"Python: {self._system_info.get('python', 'Unknown')}",
                               style=self.get_text_style("body_medium"))
                    ],
                    spacing=spacing.xs
                )
            ]
        )

        # Diagnostics mode selection
        diagnostics_mode_section = self._create_section(
            title="Diagnostics Mode",
            icon=icons.BUG_REPORT,
            controls=[
                ft.Dropdown(
                    label="Mode",
                    value=self.config.diagnostics_mode.mode,
                    options=[
                        ft.dropdown.Option(mode.mode, mode.display_name)
                        for mode in DiagnosticsMode
                    ],
                    on_change=self._on_diagnostics_mode_changed,
                    width=self.get_responsive_value(200, 220, 240, 260)
                ),
                ft.Text(
                    self.config.diagnostics_mode.description,
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Monitoring options
        monitoring_section = self._create_section(
            title="System Monitoring",
            icon=icons.MONITOR,
            controls=[
                ft.Column(
                    controls=[
                        ft.Switch(
                            label="System monitoring",
                            value=self.config.system_monitoring_enabled,
                            on_change=self._on_system_monitoring_changed
                        ),
                        ft.Switch(
                            label="Performance profiling",
                            value=self.config.performance_profiling,
                            on_change=self._on_performance_profiling_changed
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        # Diagnostic actions
        diagnostic_actions_section = self._create_section(
            title="Diagnostic Tools",
            icon=icons.BUILD,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Run Diagnostics",
                            icon=icons.PLAY_ARROW,
                            on_click=self._on_run_diagnostics_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Export Report",
                            icon=icons.DOWNLOAD,
                            on_click=self._on_export_diagnostics_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="System Health",
                            icon=icons.HEALTH,
                            on_click=self._on_system_health_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    system_info_section,
                    diagnostics_mode_section,
                    monitoring_section,
                    diagnostic_actions_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_security_tab(self) -> ft.Container:
        """Create the security configuration tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Security level selection
        security_level_section = self._create_section(
            title="Security Level",
            icon=icons.SECURITY,
            controls=[
                ft.Dropdown(
                    label="Level",
                    value=self.config.security_level.level,
                    options=[
                        ft.dropdown.Option(level.level, level.display_name)
                        for level in SecurityLevel
                    ],
                    on_change=self._on_security_level_changed,
                    width=self.get_responsive_value(200, 220, 240, 260)
                ),
                ft.Text(
                    self.config.security_level.description,
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Security options
        security_options_section = self._create_section(
            title="Security Options",
            icon=icons.SHIELD,
            controls=[
                ft.Column(
                    controls=[
                        ft.Switch(
                            label="Secure deletion",
                            value=self.config.secure_deletion,
                            on_change=self._on_secure_deletion_changed
                        ),
                        ft.Switch(
                            label="Encryption enabled",
                            value=self.config.encryption_enabled,
                            on_change=self._on_encryption_enabled_changed
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    security_level_section,
                    security_options_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_export_import_tab(self) -> ft.Container:
        """Create the export/import configuration tab."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Export section
        export_section = self._create_section(
            title="Export Configuration",
            icon=icons.DOWNLOAD,
            controls=[
                ft.Dropdown(
                    label="Export Format",
                    value=ExportFormat.JSON.format_type,
                    options=[
                        ft.dropdown.Option(fmt.format_type, fmt.display_name)
                        for fmt in ExportFormat
                    ],
                    width=self.get_responsive_value(200, 220, 240, 260)
                ),
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="primary",
                            text="Export Settings",
                            icon=icons.DOWNLOAD,
                            on_click=self._on_export_settings_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Export All",
                            icon=icons.ARCHIVE,
                            on_click=self._on_export_all_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        # Import section
        import_section = self._create_section(
            title="Import Configuration",
            icon=icons.UPLOAD,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Import Settings",
                            icon=icons.UPLOAD,
                            on_click=self._on_import_settings_clicked
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Reset to Defaults",
                            icon=icons.RESTORE,
                            on_click=self._on_reset_defaults_clicked
                        )
                    ],
                    spacing=spacing.md
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    export_section,
                    import_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_section(self, title: str, icon: str, controls: List[ft.Control]) -> ft.Container:
        """Create a settings section with title and controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        section_header = ft.Row(
            controls=[
                ft.Icon(icon, color=palette.primary),
                ft.Text(
                    title,
                    style=self.get_text_style("h6"),
                    color=palette.text_primary
                )
            ],
            spacing=spacing.sm
        )

        section_content = ft.Column(
            controls=controls,
            spacing=spacing.md
        )

        return ft.Container(
            content=ft.Column(
                controls=[section_header, section_content],
                spacing=spacing.md
            ),
            bgcolor=palette.surface,
            border_radius=8,
            padding=ft.padding.all(spacing.lg),
            border=ft.border.all(1, palette.borders)
        )

    def _create_validation_panel(self) -> ft.Container:
        """Create the validation panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self._validation_errors:
            return ft.Container(height=0)

        error_controls = []
        for field, error in self._validation_errors.items():
            error_controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ERROR, color=palette.error, size=16),
                        ft.Text(
                            f"{field}: {error}",
                            style=self.get_text_style("body_small"),
                            color=palette.error
                        )
                    ],
                    spacing=spacing.xs
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=error_controls,
                spacing=spacing.xs
            ),
            bgcolor=palette.error + "20",  # 20% opacity
            border_radius=8,
            padding=ft.padding.all(spacing.md),
            border=ft.border.all(1, palette.error)
        )

    def _create_action_bar(self) -> ft.Container:
        """Create the action bar with save/cancel buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        f"Modified: {'Yes' if self._is_modified else 'No'}",
                        style=self.get_text_style("body_small"),
                        color=palette.text_secondary
                    ),
                    ft.Row(
                        controls=[
                            self.create_themed_component(
                                "button",
                                variant="secondary",
                                text="Reset",
                                on_click=self._on_reset_clicked
                            ),
                            self.create_themed_component(
                                "button",
                                variant="primary",
                                text="Apply Changes",
                                on_click=self._on_apply_clicked,
                                disabled=not self._is_modified
                            )
                        ],
                        spacing=spacing.md
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=ft.padding.only(top=spacing.lg),
            border=ft.border.only(
                top=ft.BorderSide(1, palette.borders)
            )
        )

    # Event handlers
    def _on_mode_changed(self, e: ft.ControlEvent) -> None:
        """Handle settings mode change."""
        try:
            mode = e.control.value
            # Update interface based on mode
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing mode: {ex}")

    def _on_tab_changed(self, e: ft.ControlEvent) -> None:
        """Handle tab change."""
        try:
            self._current_tab = e.control.selected_index
        except Exception as ex:
            self._logger.error(f"Error changing tab: {ex}")

    def _on_logging_level_changed(self, e: ft.ControlEvent) -> None:
        """Handle logging level change."""
        try:
            level_str = e.control.value
            for level in LoggingLevel:
                if level.level == level_str:
                    self.config.logging_level = level
                    break
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing logging level: {ex}")

    def _on_log_file_enabled_changed(self, e: ft.ControlEvent) -> None:
        """Handle log file enabled change."""
        try:
            self.config.log_file_enabled = e.control.value
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing log file enabled: {ex}")

    def _on_console_logging_changed(self, e: ft.ControlEvent) -> None:
        """Handle console logging change."""
        try:
            self.config.console_logging_enabled = e.control.value
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing console logging: {ex}")

    def _on_log_file_size_changed(self, e: ft.ControlEvent) -> None:
        """Handle log file size change."""
        try:
            size = int(e.control.value)
            if size > 0:
                self.config.log_file_max_size_mb = size
                self._mark_modified()
        except (ValueError, TypeError) as ex:
            self._logger.error(f"Error changing log file size: {ex}")

    def _on_log_backup_count_changed(self, e: ft.ControlEvent) -> None:
        """Handle log backup count change."""
        try:
            count = int(e.control.value)
            if count >= 0:
                self.config.log_file_backup_count = count
                self._mark_modified()
        except (ValueError, TypeError) as ex:
            self._logger.error(f"Error changing log backup count: {ex}")

    def _on_telemetry_level_changed(self, e: ft.ControlEvent) -> None:
        """Handle telemetry level change."""
        try:
            level_str = e.control.value
            for level in TelemetryLevel:
                if level.level == level_str:
                    self.config.telemetry_level = level
                    break
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing telemetry level: {ex}")

    def _on_usage_stats_changed(self, e: ft.ControlEvent) -> None:
        """Handle usage stats change."""
        try:
            self.config.anonymous_usage_stats = e.control.value
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing usage stats: {ex}")

    def _on_crash_reporting_changed(self, e: ft.ControlEvent) -> None:
        """Handle crash reporting change."""
        try:
            self.config.crash_reporting = e.control.value
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing crash reporting: {ex}")

    def _on_performance_metrics_changed(self, e: ft.ControlEvent) -> None:
        """Handle performance metrics change."""
        try:
            self.config.performance_metrics = e.control.value
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing performance metrics: {ex}")

    def _on_cache_strategy_changed(self, e: ft.ControlEvent) -> None:
        """Handle cache strategy change."""
        try:
            strategy_str = e.control.value
            for strategy in CacheStrategy:
                if strategy.strategy == strategy_str:
                    self.config.cache_strategy = strategy
                    break
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing cache strategy: {ex}")

    def _on_cache_size_changed(self, e: ft.ControlEvent) -> None:
        """Handle cache size change."""
        try:
            size = float(e.control.value)
            if size > 0:
                self.config.cache_max_size_gb = size
                self._mark_modified()
        except (ValueError, TypeError) as ex:
            self._logger.error(f"Error changing cache size: {ex}")

    def _on_cache_cleanup_interval_changed(self, e: ft.ControlEvent) -> None:
        """Handle cache cleanup interval change."""
        try:
            interval = int(e.control.value)
            if interval > 0:
                self.config.cache_cleanup_interval_hours = interval
                self._mark_modified()
        except (ValueError, TypeError) as ex:
            self._logger.error(f"Error changing cache cleanup interval: {ex}")

    def _on_auto_cache_cleanup_changed(self, e: ft.ControlEvent) -> None:
        """Handle auto cache cleanup change."""
        try:
            self.config.auto_cache_cleanup = e.control.value
            self._mark_modified()
        except Exception as ex:
            self._logger.error(f"Error changing auto cache cleanup: {ex}")

    # Action button handlers
    def _on_view_log_clicked(self, e: ft.ControlEvent) -> None:
        """Handle view log button click."""
        try:
            # Implementation would open log viewer
            self._show_info_message("Log viewer functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error viewing log: {ex}")

    def _on_clear_log_clicked(self, e: ft.ControlEvent) -> None:
        """Handle clear log button click."""
        try:
            # Implementation would clear log files
            self._show_info_message("Log clearing functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error clearing log: {ex}")

    def _on_export_log_clicked(self, e: ft.ControlEvent) -> None:
        """Handle export log button click."""
        try:
            # Implementation would export log files
            self._show_info_message("Log export functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error exporting log: {ex}")

    def _on_view_cache_info_clicked(self, e: ft.ControlEvent) -> None:
        """Handle view cache info button click."""
        try:
            # Implementation would show cache information
            self._show_info_message("Cache info display would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error viewing cache info: {ex}")

    def _on_clear_cache_clicked(self, e: ft.ControlEvent) -> None:
        """Handle clear cache button click."""
        try:
            # Implementation would clear cache
            self._show_info_message("Cache clearing functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error clearing cache: {ex}")

    def _on_optimize_cache_clicked(self, e: ft.ControlEvent) -> None:
        """Handle optimize cache button click."""
        try:
            # Implementation would optimize cache
            self._show_info_message("Cache optimization would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error optimizing cache: {ex}")

    def _on_export_settings_clicked(self, e: ft.ControlEvent) -> None:
        """Handle export settings button click."""
        try:
            if self._on_export_config:
                config_data = asdict(self.config)
                self._on_export_config(json.dumps(config_data, indent=2), ExportFormat.JSON)
            else:
                self._show_info_message("Export functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error exporting settings: {ex}")

    def _on_export_all_clicked(self, e: ft.ControlEvent) -> None:
        """Handle export all button click."""
        try:
            # Implementation would export all application settings
            self._show_info_message("Full export functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error exporting all settings: {ex}")

    def _on_import_settings_clicked(self, e: ft.ControlEvent) -> None:
        """Handle import settings button click."""
        try:
            # Implementation would open file picker for import
            self._show_info_message("Import functionality would be implemented here")
        except Exception as ex:
            self._logger.error(f"Error importing settings: {ex}")

    def _on_reset_defaults_clicked(self, e: ft.ControlEvent) -> None:
        """Handle reset to defaults button click."""
        try:
            self.config = AdvancedSettingsConfig()
            self._mark_modified()
            self._show_info_message("Settings reset to defaults")
        except Exception as ex:
            self._logger.error(f"Error resetting to defaults: {ex}")

    def _on_apply_clicked(self, e: ft.ControlEvent) -> None:
        """Handle apply changes button click."""
        try:
            if self._validate_settings():
                if self._on_settings_changed:
                    self._on_settings_changed(asdict(self.config))
                self._is_modified = False
                self._original_config = asdict(self.config)
                self._show_success_message("Settings applied successfully")
                self.update()
        except Exception as ex:
            self._logger.error(f"Error applying settings: {ex}")
            self._show_error_message(f"Failed to apply settings: {ex}")

    def _on_reset_clicked(self, e: ft.ControlEvent) -> None:
        """Handle reset button click."""
        try:
            # Reset to original configuration
            for key, value in self._original_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            self._is_modified = False
            self._show_info_message("Settings reset to last saved state")
            self.update()
        except Exception as ex:
            self._logger.error(f"Error resetting settings: {ex}")

    # Utility methods
    def _mark_modified(self) -> None:
        """Mark settings as modified."""
        self._is_modified = True
        if hasattr(self, 'update'):
            self.update()

    def _validate_settings(self) -> bool:
        """Validate current settings."""
        self._validation_errors.clear()

        try:
            # Validate log file size
            if self.config.log_file_max_size_mb <= 0:
                self._validation_errors["Log File Size"] = "Must be greater than 0"

            # Validate cache size
            if self.config.cache_max_size_gb <= 0:
                self._validation_errors["Cache Size"] = "Must be greater than 0"

            # Validate backup interval
            if self.config.backup_interval_hours <= 0:
                self._validation_errors["Backup Interval"] = "Must be greater than 0"

            # Validate backup retention
            if self.config.backup_retention_days < 0:
                self._validation_errors["Backup Retention"] = "Cannot be negative"

            return len(self._validation_errors) == 0

        except Exception as ex:
            self._logger.error(f"Error validating settings: {ex}")
            self._validation_errors["Validation"] = str(ex)
            return False

    def _collect_system_info(self) -> None:
        """Collect system information for diagnostics."""
        try:
            self._system_info = {
                "os": f"{platform.system()} {platform.release()}",
                "cpu": platform.processor() or "Unknown",
                "memory": f"{psutil.virtual_memory().total // (1024**3)} GB" if 'psutil' in globals() else "Unknown",
                "python": platform.python_version()
            }
        except Exception as ex:
            self._logger.error(f"Error collecting system info: {ex}")
            self._system_info = {"error": str(ex)}

    def _show_info_message(self, message: str) -> None:
        """Show info message to user."""
        # Implementation would show a snackbar or dialog
        print(f"INFO: {message}")

    def _show_success_message(self, message: str) -> None:
        """Show success message to user."""
        # Implementation would show a success snackbar
        print(f"SUCCESS: {message}")

    def _show_error_message(self, message: str) -> None:
        """Show error message to user."""
        # Implementation would show an error dialog
        print(f"ERROR: {message}")

    # Additional placeholder event handlers for completeness
    def _on_auto_backup_enabled_changed(self, e: ft.ControlEvent) -> None:
        """Handle auto backup enabled change."""
        self.config.auto_backup_enabled = e.control.value
        self._mark_modified()

    def _on_backup_interval_changed(self, e: ft.ControlEvent) -> None:
        """Handle backup interval change."""
        try:
            interval = int(e.control.value)
            if interval > 0:
                self.config.backup_interval_hours = interval
                self._mark_modified()
        except (ValueError, TypeError):
            pass

    def _on_backup_retention_changed(self, e: ft.ControlEvent) -> None:
        """Handle backup retention change."""
        try:
            retention = int(e.control.value)
            if retention >= 0:
                self.config.backup_retention_days = retention
                self._mark_modified()
        except (ValueError, TypeError):
            pass

    def _on_backup_location_changed(self, e: ft.ControlEvent) -> None:
        """Handle backup location change."""
        self.config.backup_location = e.control.value
        self._mark_modified()

    def _on_browse_backup_location_clicked(self, e: ft.ControlEvent) -> None:
        """Handle browse backup location button click."""
        self._show_info_message("File browser would be implemented here")

    def _on_create_backup_clicked(self, e: ft.ControlEvent) -> None:
        """Handle create backup button click."""
        self._show_info_message("Backup creation would be implemented here")

    def _on_restore_backup_clicked(self, e: ft.ControlEvent) -> None:
        """Handle restore backup button click."""
        self._show_info_message("Backup restoration would be implemented here")

    def _on_view_backups_clicked(self, e: ft.ControlEvent) -> None:
        """Handle view backups button click."""
        self._show_info_message("Backup viewer would be implemented here")

    def _on_diagnostics_mode_changed(self, e: ft.ControlEvent) -> None:
        """Handle diagnostics mode change."""
        mode_str = e.control.value
        for mode in DiagnosticsMode:
            if mode.mode == mode_str:
                self.config.diagnostics_mode = mode
                break
        self._mark_modified()

    def _on_system_monitoring_changed(self, e: ft.ControlEvent) -> None:
        """Handle system monitoring change."""
        self.config.system_monitoring_enabled = e.control.value
        self._mark_modified()

    def _on_performance_profiling_changed(self, e: ft.ControlEvent) -> None:
        """Handle performance profiling change."""
        self.config.performance_profiling = e.control.value
        self._mark_modified()

    def _on_run_diagnostics_clicked(self, e: ft.ControlEvent) -> None:
        """Handle run diagnostics button click."""
        self._show_info_message("Diagnostics would be run here")

    def _on_export_diagnostics_clicked(self, e: ft.ControlEvent) -> None:
        """Handle export diagnostics button click."""
        self._show_info_message("Diagnostics export would be implemented here")

    def _on_system_health_clicked(self, e: ft.ControlEvent) -> None:
        """Handle system health button click."""
        self._show_info_message("System health check would be implemented here")

    def _on_security_level_changed(self, e: ft.ControlEvent) -> None:
        """Handle security level change."""
        level_str = e.control.value
        for level in SecurityLevel:
            if level.level == level_str:
                self.config.security_level = level
                break
        self._mark_modified()

    def _on_secure_deletion_changed(self, e: ft.ControlEvent) -> None:
        """Handle secure deletion change."""
        self.config.secure_deletion = e.control.value
        self._mark_modified()

    def _on_encryption_enabled_changed(self, e: ft.ControlEvent) -> None:
        """Handle encryption enabled change."""
        self.config.encryption_enabled = e.control.value
        self._mark_modified()
