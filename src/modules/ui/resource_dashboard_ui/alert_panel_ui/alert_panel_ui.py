"""
Module: alert_panel_ui
Description: Displays resource warnings, threshold violations, and optimization recommendations.
            Provides comprehensive alert management with real-time notifications, alert history,
            severity classification, and theme-aware visualization components.
Phase: 2
Location: /src/modules/ui/resource_dashboard_ui/alert_panel_ui/alert_panel_ui.py
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
from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import AlertSeverity, ResourceAlert


class AlertCategory(Enum):
    """Alert categories for classification."""
    RESOURCE = "resource"
    PERFORMANCE = "performance"
    THERMAL = "thermal"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    SYSTEM = "system"


class AlertAction(Enum):
    """Available actions for alerts."""
    DISMISS = "dismiss"
    ACKNOWLEDGE = "acknowledge"
    SNOOZE = "snooze"
    VIEW_DETAILS = "view_details"
    APPLY_RECOMMENDATION = "apply_recommendation"


@dataclass
class AlertItem:
    """Alert item with metadata."""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    category: AlertCategory
    timestamp: datetime
    source: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    recommendation: Optional[str] = None
    is_acknowledged: bool = False
    is_dismissed: bool = False
    snooze_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertPanelConfiguration:
    """Configuration for alert panel."""
    max_visible_alerts: int = 10
    auto_dismiss_after_minutes: int = 60
    show_acknowledged_alerts: bool = False
    show_dismissed_alerts: bool = False
    enable_sound_notifications: bool = False
    enable_desktop_notifications: bool = True
    group_similar_alerts: bool = True
    alert_refresh_interval: float = 5.0
    show_recommendations: bool = True


class AlertPanelUI(ThemeAwareUserControl):
    """
    Alert panel UI component.
    
    Provides comprehensive alert management with:
    - Real-time alert display with severity indicators
    - Alert categorization and filtering
    - Interactive alert actions (dismiss, acknowledge, snooze)
    - Performance optimization recommendations
    - Alert history and statistics
    - Theme-aware styling and animations
    - Customizable alert thresholds
    """
    
    def __init__(
        self,
        config: Optional[AlertPanelConfiguration] = None,
        on_alert_action: Optional[Callable[[str, AlertAction, AlertItem], None]] = None,
        on_recommendation_apply: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize alert panel.
        
        Args:
            config: Alert panel configuration
            on_alert_action: Callback for alert actions
            on_recommendation_apply: Callback for applying recommendations
        """
        super().__init__()
        self._config = config or AlertPanelConfiguration()
        self._on_alert_action = on_alert_action
        self._on_recommendation_apply = on_recommendation_apply
        
        # Alert data
        self._alerts: List[AlertItem] = []
        self._alert_history: List[AlertItem] = []
        self._alert_stats: Dict[str, int] = {
            "total": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
            "acknowledged": 0,
            "dismissed": 0
        }
        
        # UI state
        self._selected_category: Optional[AlertCategory] = None
        self._show_filters = False
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # UI components
        self._alert_list: Optional[ft.Column] = None
        self._stats_container: Optional[ft.Container] = None
        self._filter_controls: Optional[ft.Container] = None
        self._no_alerts_message: Optional[ft.Container] = None
        
        # Controls
        self._category_filter: Optional[ft.Dropdown] = None
        self._severity_filter: Optional[ft.Dropdown] = None
        self._clear_all_button: Optional[ft.ElevatedButton] = None
    
    def build(self) -> ft.Control:
        """Build the alert panel UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header with stats
        header = self._create_header()
        
        # Create filter controls
        filter_controls = self._create_filter_controls()
        
        # Create alert list
        alert_list = self._create_alert_list()
        
        # Create action buttons
        action_buttons = self._create_action_buttons()
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.sm),
                filter_controls,
                ft.Container(height=spacing.md),
                alert_list,
                ft.Container(height=spacing.md),
                action_buttons
            ], scroll=ft.ScrollMode.AUTO),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.lg),
            expand=True
        )
    
    def _create_header(self) -> ft.Control:
        """Create header with alert statistics."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Alert count badges
        total_badge = self._create_stat_badge("Total", self._alert_stats["total"], palette.text_primary)
        critical_badge = self._create_stat_badge("Critical", self._alert_stats["critical"], palette.error)
        warning_badge = self._create_stat_badge("Warning", self._alert_stats["warning"], palette.warning)
        info_badge = self._create_stat_badge("Info", self._alert_stats["info"], palette.info)
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "System Alerts",
                        style=self.get_text_style('h2'),
                        color=palette.text_primary
                    ),
                    ft.IconButton(
                        icon=self.get_icon("SETTINGS"),
                        tooltip="Toggle Filters",
                        on_click=self._toggle_filters,
                        icon_color=palette.text_secondary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=spacing.sm),
                ft.Row([
                    total_badge,
                    critical_badge,
                    warning_badge,
                    info_badge
                ], spacing=spacing.md)
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.lg),
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )
    
    def _create_stat_badge(self, label: str, count: int, color: str) -> ft.Control:
        """Create statistics badge."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    str(count),
                    style=self.get_text_style('metric_medium'),
                    color=color,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    label,
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=f"{color}10",
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(4),
            border=ft.border.all(1, f"{color}40"),
            width=80
        )
    
    def _create_filter_controls(self) -> ft.Control:
        """Create filter controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Category filter
        self._category_filter = ft.Dropdown(
            label="Category",
            value="all",
            options=[
                ft.dropdown.Option("all", "All Categories"),
                ft.dropdown.Option("resource", "Resource"),
                ft.dropdown.Option("performance", "Performance"),
                ft.dropdown.Option("thermal", "Thermal"),
                ft.dropdown.Option("memory", "Memory"),
                ft.dropdown.Option("disk", "Disk"),
                ft.dropdown.Option("network", "Network"),
                ft.dropdown.Option("system", "System")
            ],
            on_change=self._on_category_filter_change,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            width=150
        )
        
        # Severity filter
        self._severity_filter = ft.Dropdown(
            label="Severity",
            value="all",
            options=[
                ft.dropdown.Option("all", "All Severities"),
                ft.dropdown.Option("critical", "Critical"),
                ft.dropdown.Option("warning", "Warning"),
                ft.dropdown.Option("info", "Info")
            ],
            on_change=self._on_severity_filter_change,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders,
            width=150
        )
        
        # Show/hide toggle
        show_toggle = ft.Row([
            ft.Checkbox(
                label="Show Acknowledged",
                value=self._config.show_acknowledged_alerts,
                on_change=self._on_show_acknowledged_change
            ),
            ft.Checkbox(
                label="Show Dismissed",
                value=self._config.show_dismissed_alerts,
                on_change=self._on_show_dismissed_change
            )
        ], spacing=spacing.lg)
        
        self._filter_controls = ft.Container(
            content=ft.Column([
                ft.Row([
                    self._category_filter,
                    self._severity_filter
                ], spacing=spacing.lg),
                ft.Container(height=spacing.sm),
                show_toggle
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders),
            visible=self._show_filters
        )
        
        return self._filter_controls
    
    def _create_alert_list(self) -> ft.Control:
        """Create scrollable alert list."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create alert items
        alert_items = self._create_alert_items()
        
        if not alert_items:
            # No alerts message
            self._no_alerts_message = ft.Container(
                content=ft.Column([
                    ft.Icon(
                        self.get_icon("SUCCESS"),
                        color=palette.success,
                        size=48
                    ),
                    ft.Text(
                        "No Active Alerts",
                        style=self.get_text_style('h3'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "All systems are operating normally",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=spacing.md),
                bgcolor=palette.surface,
                padding=ft.padding.all(spacing.xl),
                border_radius=ft.border_radius.all(8),
                border=ft.border.all(1, palette.borders),
                alignment=ft.alignment.center
            )
            return self._no_alerts_message
        
        self._alert_list = ft.Column(
            alert_items,
            spacing=spacing.sm,
            scroll=ft.ScrollMode.AUTO
        )
        
        return ft.Container(
            content=self._alert_list,
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders),
            padding=ft.padding.all(spacing.md),
            height=400,
            expand=True
        )

    def _create_alert_items(self) -> List[ft.Control]:
        """Create alert item widgets."""
        filtered_alerts = self._get_filtered_alerts()
        return [self._create_alert_item(alert) for alert in filtered_alerts[:self._config.max_visible_alerts]]

    def _create_alert_item(self, alert: AlertItem) -> ft.Control:
        """Create individual alert item widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Get severity color and icon
        severity_color, severity_icon = self._get_severity_style(alert.severity)

        # Format timestamp
        time_str = alert.timestamp.strftime("%H:%M:%S")

        # Create alert content
        alert_content = ft.Row([
            # Severity indicator
            ft.Container(
                content=ft.Icon(severity_icon, color=severity_color, size=20),
                width=30
            ),
            # Alert details
            ft.Column([
                ft.Row([
                    ft.Text(
                        alert.title,
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Text(
                        time_str,
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(
                    alert.message,
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                ),
                # Value and threshold (if available)
                ft.Row([
                    ft.Text(
                        f"Value: {alert.value:.1f}" if alert.value is not None else "",
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    ),
                    ft.Text(
                        f"Threshold: {alert.threshold:.1f}" if alert.threshold is not None else "",
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    )
                ], spacing=spacing.lg) if alert.value is not None or alert.threshold is not None else ft.Container(),
                # Recommendation (if available)
                ft.Container(
                    content=ft.Row([
                        ft.Icon(self.get_icon("INFO"), color=palette.warning, size=16),
                        ft.Text(
                            alert.recommendation,
                            style=self.get_text_style('body_small'),
                            color=palette.warning,
                            italic=True
                        )
                    ], spacing=spacing.xs),
                    visible=bool(alert.recommendation and self._config.show_recommendations)
                )
            ], expand=True, spacing=spacing.xs),
            # Action buttons
            ft.Column([
                ft.IconButton(
                    icon=self.get_icon("SUCCESS"),
                    tooltip="Acknowledge",
                    on_click=lambda e, a=alert: self._acknowledge_alert(a),
                    icon_color=palette.success,
                    icon_size=16
                ),
                ft.IconButton(
                    icon=self.get_icon('CLOSE'),
                    tooltip="Dismiss",
                    on_click=lambda e, a=alert: self._dismiss_alert(a),
                    icon_color=palette.error,
                    icon_size=16
                ),
                ft.IconButton(
                    icon=self.get_icon("PAUSE"),
                    tooltip="Snooze",
                    on_click=lambda e, a=alert: self._snooze_alert(a),
                    icon_color=palette.text_secondary,
                    icon_size=16
                )
            ], spacing=2)
        ], spacing=spacing.sm)

        # Apply styling based on alert state
        border_color = severity_color
        bgcolor = palette.surface

        if alert.is_acknowledged:
            bgcolor = f"{palette.success}10"
            border_color = palette.success
        elif alert.is_dismissed:
            bgcolor = f"{palette.text_tertiary}10"
            border_color = palette.text_tertiary

        return ft.Container(
            content=alert_content,
            bgcolor=bgcolor,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(4),
            border=ft.border.all(1, border_color),
            on_click=lambda e, a=alert: self._view_alert_details(a)
        )

    def _create_action_buttons(self) -> ft.Control:
        """Create action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Clear all button
        self._clear_all_button = ft.ElevatedButton(
            text="Clear All",
            icon=self.get_icon("DELETE"),
            on_click=self._clear_all_alerts,
            bgcolor=palette.error,
            color=palette.text_primary
        )

        # Acknowledge all button
        acknowledge_all_button = ft.ElevatedButton(
            text="Acknowledge All",
            icon=self.get_icon('SUCCESS'),
            on_click=self._acknowledge_all_alerts,
            bgcolor=palette.success,
            color=palette.text_primary
        )

        # Refresh button
        refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh Alerts",
            on_click=self._refresh_alerts,
            icon_color=palette.text_secondary
        )

        return ft.Container(
            content=ft.Row([
                acknowledge_all_button,
                self._clear_all_button,
                refresh_button
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=spacing.lg),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    def _get_severity_style(self, severity: AlertSeverity) -> Tuple[str, str]:
        """Get color and icon for alert severity."""
        palette = self.get_palette()

        if getattr(AlertSeverity, 'CRITICAL', None) and severity == getattr(AlertSeverity, 'CRITICAL'):
            return palette.error, self.get_icon('ERROR')
        elif (getattr(AlertSeverity, 'WARNING', None) and severity == getattr(AlertSeverity, 'WARNING')) or (getattr(AlertSeverity, 'HIGH', None) and severity == getattr(AlertSeverity, 'HIGH')):
            return palette.warning, self.get_icon('WARNING')
        elif (getattr(AlertSeverity, 'INFO', None) and severity == getattr(AlertSeverity, 'INFO')) or (getattr(AlertSeverity, 'MEDIUM', None) and severity == getattr(AlertSeverity, 'MEDIUM')):
            return palette.info, self.get_icon('INFO')
        else:
            return palette.text_secondary, self.get_icon('CIRCLE')

    def _get_filtered_alerts(self) -> List[AlertItem]:
        """Get filtered alerts based on current filters."""
        filtered = self._alerts.copy()

        # Filter by category
        if self._selected_category:
            filtered = [a for a in filtered if a.category == self._selected_category]

        # Filter by acknowledgment status
        if not self._config.show_acknowledged_alerts:
            filtered = [a for a in filtered if not a.is_acknowledged]

        if not self._config.show_dismissed_alerts:
            filtered = [a for a in filtered if not a.is_dismissed]

        # Filter by snooze status
        current_time = datetime.now()
        filtered = [a for a in filtered if not a.snooze_until or a.snooze_until <= current_time]

        # Sort by severity and timestamp (support different enums)
        severity_order = {
            getattr(AlertSeverity, 'CRITICAL', None): 0,
            getattr(AlertSeverity, 'HIGH', None): 1,
            getattr(AlertSeverity, 'WARNING', None): 1,
            getattr(AlertSeverity, 'MEDIUM', None): 2,
            getattr(AlertSeverity, 'INFO', None): 3,
            getattr(AlertSeverity, 'LOW', None): 3,
        }
        filtered.sort(key=lambda a: (severity_order.get(a.severity, 4), a.timestamp), reverse=True)

        return filtered

    def add_alert(self, alert: AlertItem) -> None:
        """Add new alert to the panel."""
        # Check for duplicate alerts
        if self._config.group_similar_alerts:
            existing = next((a for a in self._alerts if a.title == alert.title and a.source == alert.source), None)
            if existing:
                # Update existing alert
                existing.timestamp = alert.timestamp
                existing.value = alert.value
                existing.message = alert.message
                self._update_alert_display()
                return

        # Add new alert
        self._alerts.append(alert)
        self._alert_history.append(alert)

        # Update statistics
        self._update_alert_stats()

        # Update display
        self._update_alert_display()

        # Trigger notification if enabled
        if self._config.enable_desktop_notifications:
            self._show_desktop_notification(alert)

    def remove_alert(self, alert_id: str) -> None:
        """Remove alert by ID."""
        self._alerts = [a for a in self._alerts if a.id != alert_id]
        self._update_alert_stats()
        self._update_alert_display()

    def _acknowledge_alert(self, alert: AlertItem) -> None:
        """Acknowledge an alert."""
        alert.is_acknowledged = True
        if self._on_alert_action:
            self._on_alert_action(alert.id, AlertAction.ACKNOWLEDGE, alert)
        self._update_alert_stats()
        self._update_alert_display()

    def _dismiss_alert(self, alert: AlertItem) -> None:
        """Dismiss an alert."""
        alert.is_dismissed = True
        if self._on_alert_action:
            self._on_alert_action(alert.id, AlertAction.DISMISS, alert)
        self._update_alert_stats()
        self._update_alert_display()

    def _snooze_alert(self, alert: AlertItem) -> None:
        """Snooze an alert for 15 minutes."""
        alert.snooze_until = datetime.now() + timedelta(minutes=15)
        if self._on_alert_action:
            self._on_alert_action(alert.id, AlertAction.SNOOZE, alert)
        self._update_alert_display()

    def _view_alert_details(self, alert: AlertItem) -> None:
        """View alert details."""
        if self._on_alert_action:
            self._on_alert_action(alert.id, AlertAction.VIEW_DETAILS, alert)

    def _clear_all_alerts(self, e) -> None:
        """Clear all alerts."""
        for alert in self._alerts:
            alert.is_dismissed = True
        self._update_alert_stats()
        self._update_alert_display()

    def _acknowledge_all_alerts(self, e) -> None:
        """Acknowledge all alerts."""
        for alert in self._alerts:
            if not alert.is_acknowledged:
                alert.is_acknowledged = True
        self._update_alert_stats()
        self._update_alert_display()

    def _refresh_alerts(self, e) -> None:
        """Refresh alert display."""
        self._update_alert_display()

    def _toggle_filters(self, e) -> None:
        """Toggle filter controls visibility."""
        self._show_filters = not self._show_filters
        if self._filter_controls:
            self._filter_controls.visible = self._show_filters
        self.update()

    def _on_category_filter_change(self, e) -> None:
        """Handle category filter change."""
        value = e.control.value
        self._selected_category = AlertCategory(value) if value != "all" else None
        self._update_alert_display()

    def _on_severity_filter_change(self, e) -> None:
        """Handle severity filter change."""
        # Implementation for severity filtering
        self._update_alert_display()

    def _on_show_acknowledged_change(self, e) -> None:
        """Handle show acknowledged checkbox change."""
        self._config.show_acknowledged_alerts = e.control.value
        self._update_alert_display()

    def _on_show_dismissed_change(self, e) -> None:
        """Handle show dismissed checkbox change."""
        self._config.show_dismissed_alerts = e.control.value
        self._update_alert_display()

    def _update_alert_stats(self) -> None:
        """Update alert statistics."""
        self._alert_stats = {
            "total": len([a for a in self._alerts if not a.is_dismissed]),
            "critical": len([a for a in self._alerts if getattr(AlertSeverity, 'CRITICAL', None) and a.severity == getattr(AlertSeverity, 'CRITICAL') and not a.is_dismissed]),
            "warning": len([a for a in self._alerts if ((getattr(AlertSeverity, 'WARNING', None) and a.severity == getattr(AlertSeverity, 'WARNING')) or (getattr(AlertSeverity, 'HIGH', None) and a.severity == getattr(AlertSeverity, 'HIGH'))) and not a.is_dismissed]),
            "info": len([a for a in self._alerts if ((getattr(AlertSeverity, 'INFO', None) and a.severity == getattr(AlertSeverity, 'INFO')) or (getattr(AlertSeverity, 'MEDIUM', None) and a.severity == getattr(AlertSeverity, 'MEDIUM')) or (getattr(AlertSeverity, 'LOW', None) and a.severity == getattr(AlertSeverity, 'LOW'))) and not a.is_dismissed]),
            "acknowledged": len([a for a in self._alerts if a.is_acknowledged]),
            "dismissed": len([a for a in self._alerts if a.is_dismissed])
        }

    def _update_alert_display(self) -> None:
        """Update alert display."""
        self.update()

    def _show_desktop_notification(self, alert: AlertItem) -> None:
        """Show desktop notification for alert."""
        # Placeholder for desktop notification implementation
        pass

    def configure_panel(self, config: AlertPanelConfiguration) -> None:
        """Update panel configuration."""
        self._config = config
        self._update_alert_display()

    def get_active_alerts(self) -> List[AlertItem]:
        """Get list of active alerts."""
        return [a for a in self._alerts if not a.is_dismissed]

    def get_alert_stats(self) -> Dict[str, int]:
        """Get alert statistics."""
        return self._alert_stats.copy()

    def clear_alert_history(self) -> None:
        """Clear alert history."""
        self._alert_history.clear()

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
        super().will_unmount()
