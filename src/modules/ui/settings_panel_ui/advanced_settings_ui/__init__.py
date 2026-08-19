"""
MikroDok Advanced Settings UI Package
Provides comprehensive advanced settings interface for logging levels, telemetry, cache management,
configuration export/import, and system diagnostics with full theme system integration.

This module implements the advanced settings panel for the MikroDok application settings interface,
offering sophisticated configuration options for power users and system administrators.

Features:
- Logging level configuration with real-time preview
- Telemetry and analytics settings with privacy controls
- Cache management and optimization tools
- Configuration backup and restore functionality
- System diagnostics and health monitoring
- Performance tuning and optimization settings
- Security and privacy configuration options
- Developer and debugging tools
- Full theme system integration with responsive design
- Accessibility compliance with WCAG 2.1 AA standards

Phase: 1
Location: /src/modules/ui/settings_panel_ui/advanced_settings_ui/
"""

from .advanced_settings_ui import (
    AdvancedSettingsUI,
    AdvancedSettingsConfig,
    SettingsCategory,
    LoggingLevel,
    CacheStrategy,
    TelemetryLevel,
    DiagnosticsMode,
    ExportFormat,
    SecurityLevel
)

__all__ = [
    "AdvancedSettingsUI",
    "AdvancedSettingsConfig", 
    "SettingsCategory",
    "LoggingLevel",
    "CacheStrategy",
    "TelemetryLevel",
    "DiagnosticsMode",
    "ExportFormat",
    "SecurityLevel"
]

__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Advanced settings interface for MikroDok application configuration"
