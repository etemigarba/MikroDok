"""
High Contrast UI Module

This module provides high contrast accessibility features for the MikroDok application,
including WCAG 2.1 AA/AAA compliant color schemes, color blind support, enhanced focus
indicators, and comprehensive accessibility features.

Features:
- High contrast color palettes with enhanced contrast ratios
- Color blind accessibility modes (Protanopia, Deuteranopia, Tritanopia)
- Enhanced focus indicators and keyboard navigation
- Reduced motion support for vestibular disorders
- Large text and UI element scaling
- Screen reader optimization
- WCAG 2.1 compliance checking

Phase: 1
Location: /src/modules/ui/accessibility_ui/high_contrast_ui/
"""

# Import main classes and functions
from .high_contrast_ui import (
    # Main class
    HighContrastUI,
    
    # Enums
    HighContrastLevel,
    AccessibilityFeature,
    
    # Data classes
    HighContrastPalette,
    ColorBlindPalette,
    AccessibilityConfig,
    
    # Utility functions
    create_high_contrast_ui,
    get_wcag_compliant_colors,
    check_color_accessibility
)

# Import from theme system for convenience
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ColorBlindMode,
    ThemeMode,
    ScreenSize
)

# Module metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "High contrast accessibility UI module for MikroDok"

# Public API
__all__ = [
    # Main class
    "HighContrastUI",
    
    # Enums
    "HighContrastLevel",
    "AccessibilityFeature",
    "ColorBlindMode",
    "ThemeMode",
    "ScreenSize",
    
    # Data classes
    "HighContrastPalette",
    "ColorBlindPalette",
    "AccessibilityConfig",
    
    # Utility functions
    "create_high_contrast_ui",
    "get_wcag_compliant_colors",
    "check_color_accessibility"
]

# Module constants
WCAG_AA_CONTRAST_RATIO = 4.5
WCAG_AAA_CONTRAST_RATIO = 7.0
MIN_TOUCH_TARGET_SIZE = 44  # pixels
ENHANCED_TOUCH_TARGET_SIZE = 48  # pixels

# Default configurations
DEFAULT_HIGH_CONTRAST_CONFIG = {
    'high_contrast_enabled': False,
    'high_contrast_level': HighContrastLevel.ENHANCED,
    'color_blind_mode': ColorBlindMode.NONE,
    'enhanced_focus_enabled': False,
    'reduced_motion_enabled': False,
    'large_text_enabled': False,
    'large_ui_elements': False,
    'screen_reader_optimized': False,
    'enhanced_keyboard_nav': False
}

# Color blind safe color palettes
COLOR_BLIND_SAFE_PALETTES = {
    'protanopia': {
        'primary': '#0000FF',    # Blue
        'secondary': '#FFFF00',  # Yellow
        'accent': '#00FFFF',     # Cyan
        'neutral': '#808080'     # Gray
    },
    'deuteranopia': {
        'primary': '#0000FF',    # Blue
        'secondary': '#8000FF',  # Purple
        'accent': '#FF8000',     # Orange
        'neutral': '#808080'     # Gray
    },
    'tritanopia': {
        'primary': '#FF0000',    # Red
        'secondary': '#00FF00',  # Green
        'accent': '#FF80FF',     # Pink
        'neutral': '#808080'     # Gray
    }
}

# High contrast color schemes
HIGH_CONTRAST_SCHEMES = {
    'standard': {
        'background': '#000000',
        'surface': '#1A1A1A',
        'text': '#FFFFFF',
        'primary': '#00FFFF',
        'secondary': '#FFFF00',
        'error': '#FF0000',
        'success': '#00FF00',
        'warning': '#FFFF00',
        'info': '#00FFFF'
    },
    'enhanced': {
        'background': '#000000',
        'surface': '#0A0A0A',
        'text': '#FFFFFF',
        'primary': '#00FFFF',
        'secondary': '#FFFF00',
        'error': '#FF0000',
        'success': '#00FF00',
        'warning': '#FFFF00',
        'info': '#00FFFF'
    },
    'maximum': {
        'background': '#000000',
        'surface': '#000000',
        'text': '#FFFFFF',
        'primary': '#FFFFFF',
        'secondary': '#FFFFFF',
        'error': '#FF0000',
        'success': '#00FF00',
        'warning': '#FFFF00',
        'info': '#00FFFF'
    }
}

# Accessibility feature descriptions
ACCESSIBILITY_FEATURES = {
    AccessibilityFeature.HIGH_CONTRAST: {
        'name': 'High Contrast Mode',
        'description': 'Enhanced color contrast for better visibility',
        'wcag_level': 'AA/AAA'
    },
    AccessibilityFeature.COLOR_BLIND_SUPPORT: {
        'name': 'Color Blind Support',
        'description': 'Color blind friendly palettes and patterns',
        'wcag_level': 'AA'
    },
    AccessibilityFeature.ENHANCED_FOCUS: {
        'name': 'Enhanced Focus Indicators',
        'description': 'High visibility focus rings and indicators',
        'wcag_level': 'AA'
    },
    AccessibilityFeature.REDUCED_MOTION: {
        'name': 'Reduced Motion',
        'description': 'Reduced or disabled animations for vestibular disorders',
        'wcag_level': 'AAA'
    },
    AccessibilityFeature.LARGE_TEXT: {
        'name': 'Large Text',
        'description': 'Scaled text for better readability',
        'wcag_level': 'AA'
    },
    AccessibilityFeature.LARGE_UI_ELEMENTS: {
        'name': 'Large UI Elements',
        'description': 'Enlarged touch targets and UI components',
        'wcag_level': 'AA'
    },
    AccessibilityFeature.SCREEN_READER_OPTIMIZED: {
        'name': 'Screen Reader Optimization',
        'description': 'Enhanced screen reader compatibility',
        'wcag_level': 'AA'
    },
    AccessibilityFeature.KEYBOARD_NAVIGATION: {
        'name': 'Enhanced Keyboard Navigation',
        'description': 'Improved keyboard navigation and shortcuts',
        'wcag_level': 'AA'
    }
}


def get_accessibility_feature_info(feature: AccessibilityFeature) -> dict:
    """
    Get information about an accessibility feature.
    
    Args:
        feature: Accessibility feature to get info for
        
    Returns:
        Feature information dictionary
    """
    return ACCESSIBILITY_FEATURES.get(feature, {
        'name': feature.value,
        'description': 'Unknown accessibility feature',
        'wcag_level': 'Unknown'
    })


def get_color_blind_palette(mode: ColorBlindMode) -> dict:
    """
    Get color blind safe palette for specified mode.
    
    Args:
        mode: Color blind mode
        
    Returns:
        Color palette dictionary
    """
    mode_map = {
        ColorBlindMode.PROTANOPIA: 'protanopia',
        ColorBlindMode.DEUTERANOPIA: 'deuteranopia',
        ColorBlindMode.TRITANOPIA: 'tritanopia'
    }
    
    return COLOR_BLIND_SAFE_PALETTES.get(
        mode_map.get(mode, 'protanopia'),
        COLOR_BLIND_SAFE_PALETTES['protanopia']
    )


def get_high_contrast_scheme(level: HighContrastLevel) -> dict:
    """
    Get high contrast color scheme for specified level.
    
    Args:
        level: High contrast level
        
    Returns:
        Color scheme dictionary
    """
    level_map = {
        HighContrastLevel.STANDARD: 'standard',
        HighContrastLevel.ENHANCED: 'enhanced',
        HighContrastLevel.MAXIMUM: 'maximum'
    }
    
    return HIGH_CONTRAST_SCHEMES.get(
        level_map.get(level, 'enhanced'),
        HIGH_CONTRAST_SCHEMES['enhanced']
    )


# Quick access functions
def quick_enable_high_contrast() -> HighContrastUI:
    """
    Quickly enable high contrast mode with default settings.
    
    Returns:
        Configured HighContrastUI instance
    """
    ui = create_high_contrast_ui()
    ui.enable_high_contrast_mode(HighContrastLevel.ENHANCED)
    return ui


def quick_enable_color_blind_support(mode: ColorBlindMode) -> HighContrastUI:
    """
    Quickly enable color blind support with specified mode.
    
    Args:
        mode: Color blind mode to enable
        
    Returns:
        Configured HighContrastUI instance
    """
    ui = create_high_contrast_ui()
    ui.set_color_blind_mode(mode)
    return ui


def quick_enable_accessibility_suite() -> HighContrastUI:
    """
    Quickly enable comprehensive accessibility features.
    
    Returns:
        Fully configured HighContrastUI instance
    """
    ui = create_high_contrast_ui()
    ui.enable_high_contrast_mode(HighContrastLevel.ENHANCED)
    ui.enable_enhanced_focus_indicators()
    ui.enable_reduced_motion()
    ui.enable_large_text()
    ui.enable_large_ui_elements()
    return ui
