"""
MikroDok Allocation Control UI Package
Provides comprehensive memory allocation control interface components including IDRAlloc mode selection, memory limits configuration, and real-time allocation control.
Phase: 2
Location: /src/modules/ui/system_monitor_ui/allocation_control_ui/
"""

# Import allocation control components
try:
    from .allocation_control_ui import (
        AllocationControlUI,
        AllocationControlMode,
        AllocationControlConfiguration,
        MemoryLimitConfiguration,
        ThermalLimitConfiguration,
        AllocationControlState,
        AllocationControlAction
    )
    
    __all__ = [
        'AllocationControlUI',
        'AllocationControlMode',
        'AllocationControlConfiguration',
        'MemoryLimitConfiguration',
        'ThermalLimitConfiguration',
        'AllocationControlState',
        'AllocationControlAction'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import allocation control components: {e}")
    
    __all__ = []
