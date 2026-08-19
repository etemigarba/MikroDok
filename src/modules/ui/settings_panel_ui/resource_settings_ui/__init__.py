"""
MikroDok Resource Settings UI Package
Provides comprehensive resource allocation and hardware configuration interface.
"""

# Import resource settings components
try:
    from .resource_settings_ui import (
        ResourceSettingsUI,
        AllocationMode,
        PerformanceProfile,
        ResourceLimits,
        ThermalConfiguration,
        ResourceSettingsConfig,
        GPUDevice,
        HardwareProfile
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Resource settings UI components for MikroDok settings panel"

# Export main components
__all__ = [
    "ResourceSettingsUI",
    "AllocationMode",
    "PerformanceProfile", 
    "ResourceLimits",
    "ThermalConfiguration",
    "ResourceSettingsConfig",
    "GPUDevice",
    "HardwareProfile"
]
