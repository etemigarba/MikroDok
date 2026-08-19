"""
Module: threshold_config_ui
Description: Interface for configuring warning and critical thresholds for various resource metrics.
            Provides comprehensive threshold management with real-time validation, preset configurations,
            and theme-aware responsive design for optimal user experience.
Phase: 2
Location: /src/modules/ui/monitoring_controls_ui/threshold_config_ui/threshold_config_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.database.resource_monitoring_db.threshold_config_db.threshold_config_db import ThresholdConfigDB


class ResourceCategory(Enum):
    """Resource categories for threshold configuration."""
    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    DISK = "disk"
    THERMAL = "thermal"
    NETWORK = "network"


class ThresholdType(Enum):
    """Types of thresholds."""
    USAGE = "usage"
    TEMPERATURE = "temperature"
    FREQUENCY = "frequency"
    BANDWIDTH = "bandwidth"
    LATENCY = "latency"


@dataclass
class ThresholdConfiguration:
    """Threshold configuration data structure."""
    config_id: str
    config_name: str
    resource_category: ResourceCategory
    metric_name: str
    threshold_type: ThresholdType
    warning_threshold: float
    critical_threshold: float
    emergency_threshold: float
    threshold_unit: str
    comparison_operator: str = "greater_than"
    enabled: bool = True
    description: str = ""


@dataclass
class ThresholdPreset:
    """Predefined threshold preset."""
    name: str
    description: str
    configurations: List[ThresholdConfiguration]


class ThresholdConfigUI(ThemeAwareUserControl):
    """
    Threshold configuration UI component.
    
    Provides comprehensive threshold management with:
    - Interactive threshold configuration forms
    - Real-time validation and preview
    - Preset configuration templates
    - Resource category organization
    - Theme-aware responsive design
    - Integration with ThresholdConfigDB
    """
    
    def __init__(
        self,
        on_threshold_changed: Optional[Callable[[str, ThresholdConfiguration], None]] = None,
        on_preset_applied: Optional[Callable[[ThresholdPreset], None]] = None
    ):
        """
        Initialize threshold configuration UI.
        
        Args:
            on_threshold_changed: Callback for threshold changes
            on_preset_applied: Callback for preset application
        """
        super().__init__()
        self._on_threshold_changed = on_threshold_changed
        self._on_preset_applied = on_preset_applied
        
        # Database integration
        self._threshold_db = ThresholdConfigDB()
        
        # UI state
        self._current_configurations: Dict[str, ThresholdConfiguration] = {}
        self._selected_category = ResourceCategory.CPU
        self._is_loading = False
        self._validation_errors: Dict[str, str] = {}
        
        # UI components
        self._category_tabs = None
        self._threshold_forms: Dict[ResourceCategory, ft.Control] = {}
        self._preset_dropdown = None
        self._save_button = None
        self._reset_button = None
        self._status_text = None
        
        # Load initial data
        self._load_configurations()
    
    def _load_configurations(self) -> None:
        """Load threshold configurations from database."""
        try:
            self._is_loading = True
            
            # Load configurations for each category
            for category in ResourceCategory:
                configs = self._threshold_db.get_threshold_configurations(category.value)
                for config_data in configs:
                    config = ThresholdConfiguration(
                        config_id=config_data['config_id'],
                        config_name=config_data['config_name'],
                        resource_category=ResourceCategory(config_data['resource_category']),
                        metric_name=config_data['metric_name'],
                        threshold_type=ThresholdType(config_data['threshold_type']),
                        warning_threshold=config_data['warning_threshold'],
                        critical_threshold=config_data['critical_threshold'],
                        emergency_threshold=config_data['emergency_threshold'],
                        threshold_unit=config_data['threshold_unit'],
                        comparison_operator=config_data.get('comparison_operator', 'greater_than'),
                        enabled=config_data.get('enabled', True),
                        description=config_data.get('description', '')
                    )
                    self._current_configurations[config.config_id] = config
                    
        except Exception as e:
            print(f"Error loading threshold configurations: {e}")
        finally:
            self._is_loading = False
    
    def build(self) -> ft.Control:
        """Build the threshold configuration UI."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()
        
        # Get responsive layout manager
        responsive = self._responsive_manager
        current_size = responsive.get_current_screen_size() if responsive else None
        
        # Determine layout based on screen size
        is_mobile = current_size and current_size.name in ['MOBILE', 'TABLET']
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._build_header(),
                    self._build_category_tabs(),
                    self._build_threshold_content(),
                    self._build_action_buttons()
                ],
                spacing=spacing.md,
                expand=True
            ),
            padding=spacing.lg,
            bgcolor=palette.background_primary,
            expand=True
        )
    
    def _build_header(self) -> ft.Control:
        """Build the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=icons.settings,
                        color=palette.primary,
                        size=typography.heading_large.size
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Threshold Configuration",
                                style=self.get_text_style("heading_large"),
                                color=palette.text_primary
                            ),
                            ft.Text(
                                "Configure warning and critical thresholds for system monitoring",
                                style=self.get_text_style("body_medium"),
                                color=palette.text_secondary
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    )
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.md
            ),
            padding=ft.padding.only(bottom=spacing.lg),
            border=ft.border.only(
                bottom=ft.BorderSide(
                    width=1,
                    color=palette.borders
                )
            )
        )
    
    def _build_category_tabs(self) -> ft.Control:
        """Build category selection tabs."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        tabs = []
        for category in ResourceCategory:
            tab = ft.Tab(
                text=category.value.upper(),
                content=ft.Container(),  # Content will be built separately
                icon=self._get_category_icon(category)
            )
            tabs.append(tab)
        
        self._category_tabs = ft.Tabs(
            tabs=tabs,
            selected_index=list(ResourceCategory).index(self._selected_category),
            on_change=self._on_category_changed,
            indicator_color=palette.primary,
            label_color=palette.text_primary,
            unselected_label_color=palette.text_secondary
        )
        
        return self._category_tabs
    
    def _get_category_icon(self, category: ResourceCategory) -> str:
        """Get icon for resource category."""
        icons = self.get_icons()
        
        icon_map = {
            ResourceCategory.CPU: icons.cpu,
            ResourceCategory.GPU: icons.gpu,
            ResourceCategory.MEMORY: icons.memory,
            ResourceCategory.DISK: icons.storage,
            ResourceCategory.THERMAL: icons.thermostat,
            ResourceCategory.NETWORK: icons.network
        }
        
        return icon_map.get(category, icons.settings)
    
    def _build_threshold_content(self) -> ft.Control:
        """Build threshold configuration content for current category."""
        return ft.Container(
            content=self._build_threshold_form(self._selected_category),
            expand=True
        )
    
    def _build_threshold_form(self, category: ResourceCategory) -> ft.Control:
        """Build threshold configuration form for specific category."""
        if category in self._threshold_forms:
            return self._threshold_forms[category]
        
        # Get configurations for this category
        category_configs = [
            config for config in self._current_configurations.values()
            if config.resource_category == category
        ]
        
        if not category_configs:
            return self._build_empty_state(category)
        
        form = self._build_configuration_list(category_configs)
        self._threshold_forms[category] = form
        return form
    
    def _build_empty_state(self, category: ResourceCategory) -> ft.Control:
        """Build empty state for category with no configurations."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=icons.info,
                        color=palette.text_tertiary,
                        size=48
                    ),
                    ft.Text(
                        f"No {category.value} thresholds configured",
                        style=self.get_text_style("heading_medium"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Add threshold configurations to monitor system resources",
                        style=self.get_text_style("body_medium"),
                        color=palette.text_tertiary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.ElevatedButton(
                        text="Add Threshold",
                        icon=icons.add,
                        on_click=lambda _: self._add_new_threshold(category),
                        bgcolor=palette.primary,
                        color=palette.text_primary
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.lg
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _build_configuration_list(self, configs: List[ThresholdConfiguration]) -> ft.Control:
        """Build list of threshold configurations."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        config_controls = []
        for config in configs:
            config_control = self._build_configuration_item(config)
            config_controls.append(config_control)

        return ft.Container(
            content=ft.Column(
                controls=config_controls,
                spacing=spacing.md,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _build_configuration_item(self, config: ThresholdConfiguration) -> ft.Control:
        """Build individual threshold configuration item."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Get responsive layout manager
        responsive = self._responsive_manager
        current_size = responsive.get_current_screen_size() if responsive else None
        is_mobile = current_size and current_size.name in ['MOBILE', 'TABLET']

        # Create threshold input fields
        warning_field = ft.TextField(
            label="Warning",
            value=str(config.warning_threshold),
            suffix_text=config.threshold_unit,
            width=120 if not is_mobile else None,
            expand=is_mobile,
            on_change=lambda e, cfg=config: self._on_threshold_value_changed(cfg, 'warning', e.control.value),
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            focused_border_color=palette.primary
        )

        critical_field = ft.TextField(
            label="Critical",
            value=str(config.critical_threshold),
            suffix_text=config.threshold_unit,
            width=120 if not is_mobile else None,
            expand=is_mobile,
            on_change=lambda e, cfg=config: self._on_threshold_value_changed(cfg, 'critical', e.control.value),
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            focused_border_color=palette.warning
        )

        emergency_field = ft.TextField(
            label="Emergency",
            value=str(config.emergency_threshold),
            suffix_text=config.threshold_unit,
            width=120 if not is_mobile else None,
            expand=is_mobile,
            on_change=lambda e, cfg=config: self._on_threshold_value_changed(cfg, 'emergency', e.control.value),
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            focused_border_color=palette.error
        )

        # Enable/disable switch
        enable_switch = ft.Switch(
            value=config.enabled,
            on_change=lambda e, cfg=config: self._on_threshold_enabled_changed(cfg, e.control.value),
            active_color=palette.primary
        )

        # Layout based on screen size
        if is_mobile:
            # Mobile layout - vertical stacking
            content = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                config.config_name,
                                style=self.get_text_style("body_large"),
                                color=palette.text_primary,
                                expand=True
                            ),
                            enable_switch
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    ft.Text(
                        f"{config.metric_name} ({config.threshold_type.value})",
                        style=self.get_text_style("body_small"),
                        color=palette.text_secondary
                    ),
                    warning_field,
                    critical_field,
                    emergency_field
                ],
                spacing=spacing.sm
            )
        else:
            # Desktop layout - horizontal
            content = ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                config.config_name,
                                style=self.get_text_style("body_large"),
                                color=palette.text_primary
                            ),
                            ft.Text(
                                f"{config.metric_name} ({config.threshold_type.value})",
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    ),
                    warning_field,
                    critical_field,
                    emergency_field,
                    enable_switch
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.md
            )

        return ft.Container(
            content=content,
            padding=spacing.md,
            bgcolor=palette.surface,
            border_radius=8,
            border=ft.border.all(1, palette.borders)
        )

    def _build_action_buttons(self) -> ft.Control:
        """Build action buttons section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Get responsive layout manager
        responsive = self._responsive_manager
        current_size = responsive.get_current_screen_size() if responsive else None
        is_mobile = current_size and current_size.name in ['MOBILE', 'TABLET']

        self._save_button = ft.ElevatedButton(
            text="Save Changes",
            icon=icons.save,
            on_click=self._on_save_clicked,
            bgcolor=palette.primary,
            color=palette.text_primary,
            expand=is_mobile
        )

        self._reset_button = ft.OutlinedButton(
            text="Reset",
            icon=icons.refresh,
            on_click=self._on_reset_clicked,
            expand=is_mobile
        )

        preset_button = ft.OutlinedButton(
            text="Load Preset",
            icon=icons.download,
            on_click=self._on_preset_clicked,
            expand=is_mobile
        )

        self._status_text = ft.Text(
            "",
            style=self.get_text_style("body_small"),
            color=palette.text_secondary
        )

        if is_mobile:
            # Mobile layout - vertical stacking
            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._status_text,
                        self._save_button,
                        ft.Row(
                            controls=[self._reset_button, preset_button],
                            spacing=spacing.sm
                        )
                    ],
                    spacing=spacing.sm
                ),
                padding=ft.padding.only(top=spacing.lg),
                border=ft.border.only(
                    top=ft.BorderSide(width=1, color=palette.borders)
                )
            )
        else:
            # Desktop layout - horizontal
            return ft.Container(
                content=ft.Row(
                    controls=[
                        self._status_text,
                        ft.Row(
                            controls=[
                                preset_button,
                                self._reset_button,
                                self._save_button
                            ],
                            spacing=spacing.sm
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.only(top=spacing.lg),
                border=ft.border.only(
                    top=ft.BorderSide(width=1, color=palette.borders)
                )
            )

    def _on_category_changed(self, e: ft.ControlEvent) -> None:
        """Handle category tab change."""
        if e.control.selected_index is not None:
            categories = list(ResourceCategory)
            if 0 <= e.control.selected_index < len(categories):
                self._selected_category = categories[e.control.selected_index]
                self._refresh_threshold_content()

    def _refresh_threshold_content(self) -> None:
        """Refresh threshold content for current category."""
        if hasattr(self, 'content') and self.content:
            # Clear cached form for this category
            if self._selected_category in self._threshold_forms:
                del self._threshold_forms[self._selected_category]

            # Rebuild the UI
            self.content = self.build()
            self.update()

    def _on_threshold_value_changed(self, config: ThresholdConfiguration,
                                  threshold_type: str, value: str) -> None:
        """Handle threshold value change."""
        try:
            numeric_value = float(value) if value else 0.0

            # Update configuration
            if threshold_type == 'warning':
                config.warning_threshold = numeric_value
            elif threshold_type == 'critical':
                config.critical_threshold = numeric_value
            elif threshold_type == 'emergency':
                config.emergency_threshold = numeric_value

            # Validate thresholds
            self._validate_threshold_configuration(config)

            # Notify change
            if self._on_threshold_changed:
                self._on_threshold_changed(config.config_id, config)

        except ValueError:
            # Invalid numeric value
            self._validation_errors[f"{config.config_id}_{threshold_type}"] = "Invalid numeric value"
            self._update_status("Invalid threshold value entered", is_error=True)

    def _on_threshold_enabled_changed(self, config: ThresholdConfiguration, enabled: bool) -> None:
        """Handle threshold enabled state change."""
        config.enabled = enabled

        # Notify change
        if self._on_threshold_changed:
            self._on_threshold_changed(config.config_id, config)

    def _validate_threshold_configuration(self, config: ThresholdConfiguration) -> bool:
        """Validate threshold configuration values."""
        errors = []

        # Check threshold ordering
        if config.warning_threshold >= config.critical_threshold:
            errors.append("Warning threshold must be less than critical threshold")

        if config.critical_threshold >= config.emergency_threshold:
            errors.append("Critical threshold must be less than emergency threshold")

        # Check minimum values
        if config.warning_threshold < 0:
            errors.append("Warning threshold cannot be negative")

        # Check maximum values based on threshold type
        if config.threshold_type == ThresholdType.USAGE:
            if config.emergency_threshold > 100:
                errors.append("Usage thresholds cannot exceed 100%")

        # Store validation errors
        config_key = config.config_id
        if errors:
            self._validation_errors[config_key] = "; ".join(errors)
            return False
        else:
            self._validation_errors.pop(config_key, None)
            return True

    def _on_save_clicked(self, e: ft.ControlEvent) -> None:
        """Handle save button click."""
        asyncio.create_task(self._save_configurations())

    async def _save_configurations(self) -> None:
        """Save threshold configurations to database."""
        try:
            self._update_status("Saving configurations...", is_loading=True)

            # Validate all configurations
            all_valid = True
            for config in self._current_configurations.values():
                if not self._validate_threshold_configuration(config):
                    all_valid = False

            if not all_valid:
                self._update_status("Please fix validation errors before saving", is_error=True)
                return

            # Save to database
            for config in self._current_configurations.values():
                config_data = {
                    'config_name': config.config_name,
                    'resource_category': config.resource_category.value,
                    'metric_name': config.metric_name,
                    'threshold_type': config.threshold_type.value,
                    'warning_threshold': config.warning_threshold,
                    'critical_threshold': config.critical_threshold,
                    'emergency_threshold': config.emergency_threshold,
                    'threshold_unit': config.threshold_unit,
                    'comparison_operator': config.comparison_operator,
                    'enabled': config.enabled,
                    'description': config.description
                }

                # Update existing or create new
                existing = self._threshold_db.get_threshold_configuration(config.config_id)
                if existing:
                    self._threshold_db.update_threshold_configuration(config.config_id, config_data)
                else:
                    self._threshold_db.create_threshold_configuration(config_data)

            self._update_status("Configurations saved successfully", is_success=True)

        except Exception as e:
            self._update_status(f"Error saving configurations: {str(e)}", is_error=True)

    def _on_reset_clicked(self, e: ft.ControlEvent) -> None:
        """Handle reset button click."""
        # Reload configurations from database
        self._load_configurations()

        # Clear cached forms
        self._threshold_forms.clear()

        # Refresh UI
        self._refresh_threshold_content()
        self._update_status("Configurations reset to saved values")

    def _on_preset_clicked(self, e: ft.ControlEvent) -> None:
        """Handle preset button click."""
        # Show preset selection dialog
        self._show_preset_dialog()

    def _show_preset_dialog(self) -> None:
        """Show preset selection dialog."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        presets = self._get_threshold_presets()

        preset_options = []
        for preset in presets:
            preset_options.append(
                ft.ListTile(
                    title=ft.Text(preset.name, color=palette.text_primary),
                    subtitle=ft.Text(preset.description, color=palette.text_secondary),
                    on_click=lambda e, p=preset: self._apply_preset(p)
                )
            )

        dialog = ft.AlertDialog(
            title=ft.Text("Select Threshold Preset", color=palette.text_primary),
            content=ft.Container(
                content=ft.Column(
                    controls=preset_options,
                    spacing=spacing.sm,
                    scroll=ft.ScrollMode.AUTO
                ),
                width=400,
                height=300
            ),
            actions=[
                ft.TextButton(
                    text="Cancel",
                    on_click=lambda e: self._close_dialog()
                )
            ],
            bgcolor=palette.surface
        )

        if self.page:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()

    def _close_dialog(self) -> None:
        """Close the current dialog."""
        if self.page and self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def _apply_preset(self, preset: ThresholdPreset) -> None:
        """Apply a threshold preset."""
        try:
            # Update current configurations with preset values
            for config in preset.configurations:
                if config.config_id in self._current_configurations:
                    current_config = self._current_configurations[config.config_id]
                    current_config.warning_threshold = config.warning_threshold
                    current_config.critical_threshold = config.critical_threshold
                    current_config.emergency_threshold = config.emergency_threshold
                    current_config.enabled = config.enabled

            # Clear cached forms and refresh UI
            self._threshold_forms.clear()
            self._refresh_threshold_content()

            # Close dialog
            self._close_dialog()

            # Update status
            self._update_status(f"Applied preset: {preset.name}")

            # Notify preset applied
            if self._on_preset_applied:
                self._on_preset_applied(preset)

        except Exception as e:
            self._update_status(f"Error applying preset: {str(e)}", is_error=True)

    def _get_threshold_presets(self) -> List[ThresholdPreset]:
        """Get predefined threshold presets."""
        return [
            ThresholdPreset(
                name="Conservative",
                description="Conservative thresholds for stable systems",
                configurations=[
                    ThresholdConfiguration(
                        config_id="cpu_usage_conservative",
                        config_name="CPU Usage",
                        resource_category=ResourceCategory.CPU,
                        metric_name="usage_percent",
                        threshold_type=ThresholdType.USAGE,
                        warning_threshold=60.0,
                        critical_threshold=80.0,
                        emergency_threshold=95.0,
                        threshold_unit="percent"
                    ),
                    ThresholdConfiguration(
                        config_id="memory_usage_conservative",
                        config_name="Memory Usage",
                        resource_category=ResourceCategory.MEMORY,
                        metric_name="usage_percent",
                        threshold_type=ThresholdType.USAGE,
                        warning_threshold=70.0,
                        critical_threshold=85.0,
                        emergency_threshold=95.0,
                        threshold_unit="percent"
                    )
                ]
            ),
            ThresholdPreset(
                name="Balanced",
                description="Balanced thresholds for general use",
                configurations=[
                    ThresholdConfiguration(
                        config_id="cpu_usage_balanced",
                        config_name="CPU Usage",
                        resource_category=ResourceCategory.CPU,
                        metric_name="usage_percent",
                        threshold_type=ThresholdType.USAGE,
                        warning_threshold=75.0,
                        critical_threshold=90.0,
                        emergency_threshold=98.0,
                        threshold_unit="percent"
                    ),
                    ThresholdConfiguration(
                        config_id="memory_usage_balanced",
                        config_name="Memory Usage",
                        resource_category=ResourceCategory.MEMORY,
                        metric_name="usage_percent",
                        threshold_type=ThresholdType.USAGE,
                        warning_threshold=80.0,
                        critical_threshold=90.0,
                        emergency_threshold=98.0,
                        threshold_unit="percent"
                    )
                ]
            ),
            ThresholdPreset(
                name="Performance",
                description="High-performance thresholds for demanding workloads",
                configurations=[
                    ThresholdConfiguration(
                        config_id="cpu_usage_performance",
                        config_name="CPU Usage",
                        resource_category=ResourceCategory.CPU,
                        metric_name="usage_percent",
                        threshold_type=ThresholdType.USAGE,
                        warning_threshold=85.0,
                        critical_threshold=95.0,
                        emergency_threshold=99.0,
                        threshold_unit="percent"
                    ),
                    ThresholdConfiguration(
                        config_id="memory_usage_performance",
                        config_name="Memory Usage",
                        resource_category=ResourceCategory.MEMORY,
                        metric_name="usage_percent",
                        threshold_type=ThresholdType.USAGE,
                        warning_threshold=85.0,
                        critical_threshold=95.0,
                        emergency_threshold=99.0,
                        threshold_unit="percent"
                    )
                ]
            )
        ]

    def _add_new_threshold(self, category: ResourceCategory) -> None:
        """Add a new threshold configuration for the category."""
        # Generate new configuration ID
        config_id = f"{category.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create new configuration with default values
        new_config = ThresholdConfiguration(
            config_id=config_id,
            config_name=f"New {category.value.title()} Threshold",
            resource_category=category,
            metric_name="usage_percent",
            threshold_type=ThresholdType.USAGE,
            warning_threshold=70.0,
            critical_threshold=85.0,
            emergency_threshold=95.0,
            threshold_unit="percent",
            enabled=True,
            description=""
        )

        # Add to current configurations
        self._current_configurations[config_id] = new_config

        # Clear cached form and refresh
        if category in self._threshold_forms:
            del self._threshold_forms[category]

        self._refresh_threshold_content()
        self._update_status(f"Added new {category.value} threshold configuration")

    def _update_status(self, message: str, is_error: bool = False,
                      is_success: bool = False, is_loading: bool = False) -> None:
        """Update status message."""
        if self._status_text:
            palette = self.get_palette()

            if is_error:
                color = palette.error
            elif is_success:
                color = palette.success
            elif is_loading:
                color = palette.info
            else:
                color = palette.text_secondary

            self._status_text.value = message
            self._status_text.color = color

            if hasattr(self._status_text, 'update'):
                self._status_text.update()

    def get_current_configurations(self) -> Dict[str, ThresholdConfiguration]:
        """Get current threshold configurations."""
        return self._current_configurations.copy()

    def set_configuration(self, config_id: str, config: ThresholdConfiguration) -> None:
        """Set a specific threshold configuration."""
        self._current_configurations[config_id] = config

        # Clear cached forms for the category
        if config.resource_category in self._threshold_forms:
            del self._threshold_forms[config.resource_category]

        # Refresh UI if this is the current category
        if config.resource_category == self._selected_category:
            self._refresh_threshold_content()

    def remove_configuration(self, config_id: str) -> bool:
        """Remove a threshold configuration."""
        if config_id in self._current_configurations:
            config = self._current_configurations[config_id]
            del self._current_configurations[config_id]

            # Remove from database
            try:
                # Note: ThresholdConfigDB doesn't have a delete method in the provided code
                # This would need to be implemented in the database layer
                pass
            except Exception as e:
                print(f"Error removing configuration from database: {e}")

            # Clear cached forms for the category
            if config.resource_category in self._threshold_forms:
                del self._threshold_forms[config.resource_category]

            # Refresh UI if this is the current category
            if config.resource_category == self._selected_category:
                self._refresh_threshold_content()

            return True
        return False

    def export_configurations(self) -> Dict[str, Any]:
        """Export current configurations to dictionary."""
        export_data = {
            'version': '1.0',
            'export_timestamp': datetime.now().isoformat(),
            'configurations': {}
        }

        for config_id, config in self._current_configurations.items():
            export_data['configurations'][config_id] = {
                'config_name': config.config_name,
                'resource_category': config.resource_category.value,
                'metric_name': config.metric_name,
                'threshold_type': config.threshold_type.value,
                'warning_threshold': config.warning_threshold,
                'critical_threshold': config.critical_threshold,
                'emergency_threshold': config.emergency_threshold,
                'threshold_unit': config.threshold_unit,
                'comparison_operator': config.comparison_operator,
                'enabled': config.enabled,
                'description': config.description
            }

        return export_data

    def import_configurations(self, import_data: Dict[str, Any]) -> bool:
        """Import configurations from dictionary."""
        try:
            if 'configurations' not in import_data:
                return False

            imported_count = 0
            for config_id, config_data in import_data['configurations'].items():
                config = ThresholdConfiguration(
                    config_id=config_id,
                    config_name=config_data['config_name'],
                    resource_category=ResourceCategory(config_data['resource_category']),
                    metric_name=config_data['metric_name'],
                    threshold_type=ThresholdType(config_data['threshold_type']),
                    warning_threshold=config_data['warning_threshold'],
                    critical_threshold=config_data['critical_threshold'],
                    emergency_threshold=config_data['emergency_threshold'],
                    threshold_unit=config_data['threshold_unit'],
                    comparison_operator=config_data.get('comparison_operator', 'greater_than'),
                    enabled=config_data.get('enabled', True),
                    description=config_data.get('description', '')
                )

                self._current_configurations[config_id] = config
                imported_count += 1

            # Clear cached forms and refresh
            self._threshold_forms.clear()
            self._refresh_threshold_content()

            self._update_status(f"Imported {imported_count} configurations", is_success=True)
            return True

        except Exception as e:
            self._update_status(f"Error importing configurations: {str(e)}", is_error=True)
            return False
