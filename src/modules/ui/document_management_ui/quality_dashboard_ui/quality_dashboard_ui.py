"""
Module: quality_dashboard_ui
Description: Visualizes document quality metrics, processing statistics, and error reports with interactive charts and indicators.
            Provides comprehensive quality assessment dashboard with real-time updates, theme-aware visualization,
            and responsive design for document quality monitoring and analysis.
Phase: 3
Location: /src/modules/ui/document_management_ui/quality_dashboard_ui/quality_dashboard_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.document_quality_lg.base_interfaces import (
    QualityMetric, QualityCategory, QualityScoreResult
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class QualityChartType(Enum):
    """Types of quality visualization charts."""
    OVERVIEW = "overview"
    METRICS_BREAKDOWN = "metrics_breakdown"
    TREND_ANALYSIS = "trend_analysis"
    CATEGORY_COMPARISON = "category_comparison"
    ERROR_DISTRIBUTION = "error_distribution"


class QualityIndicator(Enum):
    """Quality level indicators."""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"           # 75-89%
    FAIR = "fair"           # 60-74%
    POOR = "poor"           # 40-59%
    CRITICAL = "critical"   # 0-39%


@dataclass
class QualityReport:
    """Quality report data structure."""
    document_id: str
    document_name: str
    overall_score: float
    category_scores: Dict[QualityCategory, float]
    metric_scores: Dict[QualityMetric, float]
    processing_time_ms: float
    validation_warnings: List[str]
    validation_errors: List[str]
    timestamp: datetime
    status: str


@dataclass
class DashboardConfig:
    """Configuration for quality dashboard."""
    refresh_interval_seconds: float = 2.0
    show_trend_charts: bool = True
    show_category_breakdown: bool = True
    show_error_details: bool = True
    auto_refresh: bool = True
    max_history_items: int = 100
    enable_alerts: bool = True


class QualityDashboardUI(ThemeAwareUserControl):
    """
    Quality dashboard UI component for document quality visualization.
    
    Provides comprehensive quality monitoring with:
    - Real-time quality metrics display
    - Interactive quality charts and graphs
    - Category-based quality breakdown
    - Processing statistics and trends
    - Error and warning reporting
    - Quality indicators and alerts
    - Theme-aware responsive design
    - Performance optimization
    """

    def __init__(
        self,
        config: Optional[DashboardConfig] = None,
        on_document_selected: Optional[Callable[[str], None]] = None,
        on_quality_alert: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        """
        Initialize quality dashboard UI.
        
        Args:
            config: Dashboard configuration
            on_document_selected: Callback for document selection
            on_quality_alert: Callback for quality alerts
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or DashboardConfig()
        self._on_document_selected = on_document_selected
        self._on_quality_alert = on_quality_alert
        
        # Logger
        self._logger = get_logger(__name__)
        
        # State management
        self._quality_reports: List[QualityReport] = []
        self._selected_document_id: Optional[str] = None
        self._is_refreshing = False
        self._refresh_timer: Optional[asyncio.Task] = None
        
        # UI references
        self._refs = {}
        
        # Initialize component
        self._initialize_dashboard()

    def _initialize_dashboard(self) -> None:
        """Initialize dashboard components."""
        try:
            self._logger.info("Initializing quality dashboard UI")
            
            # Setup refresh timer if auto-refresh is enabled
            if self._config.auto_refresh:
                self._start_auto_refresh()
                
        except Exception as e:
            self._logger.error(f"Failed to initialize quality dashboard: {e}")

    def build(self) -> ft.Control:
        """Build the quality dashboard interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            rlm = self.get_responsive_layout()
            
            # Main dashboard layout
            return ft.Container(
                content=ft.Column([
                    self._create_dashboard_header(),
                    ft.Container(height=spacing.md),
                    self._create_metrics_overview(),
                    ft.Container(height=spacing.lg),
                    self._create_quality_charts(),
                    ft.Container(height=spacing.lg),
                    self._create_details_section()
                ], scroll=ft.ScrollMode.AUTO),
                bgcolor=palette.background,
                padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
                expand=True
            )
            
        except Exception as e:
            self._logger.error(f"Failed to build quality dashboard: {e}")
            return self._create_error_display(str(e))

    def _create_dashboard_header(self) -> ft.Control:
        """Create dashboard header with title and controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()
        
        # Title
        title = ft.Text(
            "Document Quality Dashboard",
            style=self.get_text_style('h1'),
            color=palette.text_primary
        )
        
        # Refresh button
        refresh_btn = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh Dashboard",
            on_click=self._handle_refresh,
            icon_color=palette.primary,
            icon_size=rlm.get_breakpoint_value(20, 22, 24, 26)
        )
        
        # Auto-refresh toggle
        auto_refresh_toggle = ft.Switch(
            value=self._config.auto_refresh,
            on_change=self._handle_auto_refresh_toggle,
            active_color=palette.primary
        )
        
        auto_refresh_label = ft.Text(
            "Auto Refresh",
            style=self.get_text_style('body2'),
            color=palette.text_secondary
        )
        
        # Controls row
        controls = ft.Row([
            ft.Row([auto_refresh_label, auto_refresh_toggle], spacing=spacing.sm),
            refresh_btn
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        return ft.Container(
            content=ft.Column([
                title,
                ft.Container(height=spacing.sm),
                controls
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

    def _create_metrics_overview(self) -> ft.Control:
        """Create metrics overview cards."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()
        
        # Calculate overview metrics
        total_docs = len(self._quality_reports)
        avg_score = self._calculate_average_score()
        excellent_count = self._count_by_quality_level(QualityIndicator.EXCELLENT)
        poor_count = self._count_by_quality_level(QualityIndicator.POOR)
        
        # Overview cards
        cards = [
            self._create_metric_card(
                "Total Documents",
                str(total_docs),
                self.get_icon('DESCRIPTION'),
                palette.primary
            ),
            self._create_metric_card(
                "Average Quality",
                f"{avg_score:.1f}%",
                self.get_icon('STAR'),
                self._get_quality_color(avg_score)
            ),
            self._create_metric_card(
                "Excellent Quality",
                str(excellent_count),
                self.get_icon('CHECK_CIRCLE'),
                palette.success
            ),
            self._create_metric_card(
                "Needs Attention",
                str(poor_count),
                self.get_icon('WARNING'),
                palette.warning if poor_count > 0 else palette.text_disabled
            )
        ]
        
        # Responsive grid layout
        return self.create_responsive_grid(
            children=cards,
            mobile_cols=1,
            tablet_cols=2,
            desktop_cols=4,
            large_cols=4,
            spacing=spacing.md
        )

    def _create_metric_card(self, title: str, value: str, icon: str, color: str) -> ft.Control:
        """Create a metric card with icon, title, and value."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Card content
        icon_widget = ft.Icon(
            icon,
            color=color,
            size=rlm.get_breakpoint_value(24, 28, 32, 36)
        )

        title_text = ft.Text(
            title,
            style=self.get_text_style('caption'),
            color=palette.text_secondary
        )

        value_text = ft.Text(
            value,
            style=self.get_text_style('h3'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD
        )

        return ft.Container(
            content=ft.Column([
                ft.Row([icon_widget, value_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=spacing.xs),
                title_text
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            width=rlm.get_breakpoint_value(None, None, 200, 220)
        )

    def _create_quality_charts(self) -> ft.Control:
        """Create quality visualization charts."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Chart containers
        charts = []

        if self._config.show_category_breakdown:
            charts.append(self._create_category_breakdown_chart())

        if self._config.show_trend_charts:
            charts.append(self._create_trend_chart())

        if self._config.show_error_details:
            charts.append(self._create_error_distribution_chart())

        # Section header
        header = ft.Text(
            "Quality Analysis",
            style=self.get_text_style('h2'),
            color=palette.text_primary
        )

        # Charts layout
        charts_layout = self.create_responsive_grid(
            children=charts,
            mobile_cols=1,
            tablet_cols=1,
            desktop_cols=2,
            large_cols=3,
            spacing=spacing.lg
        ) if charts else ft.Container(
            content=ft.Text(
                "No quality data available",
                style=self.get_text_style('body1'),
                color=palette.text_disabled
            ),
            alignment=ft.alignment.center,
            height=200
        )

        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.md),
                charts_layout
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

    def _create_category_breakdown_chart(self) -> ft.Control:
        """Create category breakdown chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Calculate category averages
        category_scores = self._calculate_category_averages()

        # Create progress bars for each category
        category_bars = []
        for category, score in category_scores.items():
            color = self._get_quality_color(score)

            bar = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(
                            category.value.replace('_', ' ').title(),
                            style=self.get_text_style('body2'),
                            color=palette.text_primary
                        ),
                        ft.Text(
                            f"{score:.1f}%",
                            style=self.get_text_style('body2'),
                            color=palette.text_secondary,
                            weight=ft.FontWeight.BOLD
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=spacing.xs),
                    ft.ProgressBar(
                        value=score / 100.0,
                        color=color,
                        bgcolor=palette.surface_variant,
                        height=rlm.get_breakpoint_value(6, 8, 10, 12)
                    )
                ]),
                padding=ft.padding.symmetric(vertical=spacing.sm)
            )
            category_bars.append(bar)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Quality Categories",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(category_bars)
            ]),
            bgcolor=palette.background,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            height=rlm.get_breakpoint_value(300, 350, 400, 450)
        )

    def _create_trend_chart(self) -> ft.Control:
        """Create quality trend chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create trend visualization (simplified as line chart representation)
        trend_data = self._calculate_quality_trends()

        # Create trend indicators
        trend_items = []
        for i, (timestamp, score) in enumerate(trend_data[-10:]):  # Last 10 items
            color = self._get_quality_color(score)

            item = ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=rlm.get_breakpoint_value(8, 10, 12, 14),
                        height=rlm.get_breakpoint_value(8, 10, 12, 14),
                        bgcolor=color,
                        border_radius=ft.border_radius.all(50)
                    ),
                    ft.Text(
                        f"{score:.1f}%",
                        style=self.get_text_style('caption'),
                        color=palette.text_secondary
                    )
                ], spacing=spacing.sm),
                padding=ft.padding.symmetric(vertical=spacing.xs)
            )
            trend_items.append(item)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Quality Trends",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(trend_items) if trend_items else ft.Text(
                    "No trend data available",
                    style=self.get_text_style('body2'),
                    color=palette.text_disabled
                )
            ]),
            bgcolor=palette.background,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            height=rlm.get_breakpoint_value(300, 350, 400, 450)
        )

    def _create_error_distribution_chart(self) -> ft.Control:
        """Create error distribution chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Calculate error statistics
        error_stats = self._calculate_error_statistics()

        # Create error type indicators
        error_items = []
        for error_type, count in error_stats.items():
            if count > 0:
                item = ft.Container(
                    content=ft.Row([
                        ft.Icon(
                            self.get_icon('ERROR'),
                            color=palette.error,
                            size=rlm.get_breakpoint_value(16, 18, 20, 22)
                        ),
                        ft.Text(
                            error_type,
                            style=self.get_text_style('body2'),
                            color=palette.text_primary
                        ),
                        ft.Text(
                            str(count),
                            style=self.get_text_style('body2'),
                            color=palette.text_secondary,
                            weight=ft.FontWeight.BOLD
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(vertical=spacing.sm)
                )
                error_items.append(item)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Error Distribution",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(error_items) if error_items else ft.Text(
                    "No errors detected",
                    style=self.get_text_style('body2'),
                    color=palette.success
                )
            ]),
            bgcolor=palette.background,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            height=rlm.get_breakpoint_value(300, 350, 400, 450)
        )

    def _create_details_section(self) -> ft.Control:
        """Create detailed quality reports section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Recent reports list
        recent_reports = self._quality_reports[-10:] if self._quality_reports else []

        # Create report items
        report_items = []
        for report in recent_reports:
            quality_indicator = self._get_quality_indicator(report.overall_score)
            color = self._get_quality_color(report.overall_score)

            item = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        self.get_icon('DESCRIPTION'),
                        color=palette.text_secondary,
                        size=rlm.get_breakpoint_value(20, 22, 24, 26)
                    ),
                    ft.Column([
                        ft.Text(
                            report.document_name,
                            style=self.get_text_style('body1'),
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Text(
                            f"Processed: {report.timestamp.strftime('%Y-%m-%d %H:%M')}",
                            style=self.get_text_style('caption'),
                            color=palette.text_secondary
                        )
                    ], spacing=spacing.xs),
                    ft.Container(
                        content=ft.Text(
                            f"{report.overall_score:.1f}%",
                            style=self.get_text_style('body2'),
                            color=color,
                            weight=ft.FontWeight.BOLD
                        ),
                        bgcolor=f"{color}20",  # 20% opacity
                        padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
                        border_radius=ft.border_radius.all(4)
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.padding.all(spacing.md),
                border=ft.border.all(1, palette.borders),
                border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10)),
                on_click=lambda e, doc_id=report.document_id: self._handle_document_selected(doc_id)
            )
            report_items.append(item)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Recent Quality Reports",
                    style=self.get_text_style('h2'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(report_items, spacing=spacing.sm) if report_items else ft.Container(
                    content=ft.Text(
                        "No quality reports available",
                        style=self.get_text_style('body1'),
                        color=palette.text_disabled
                    ),
                    alignment=ft.alignment.center,
                    height=100
                )
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

    # Helper methods for calculations and data processing
    def _calculate_average_score(self) -> float:
        """Calculate average quality score across all reports."""
        if not self._quality_reports:
            return 0.0
        return sum(report.overall_score for report in self._quality_reports) / len(self._quality_reports)

    def _count_by_quality_level(self, level: QualityIndicator) -> int:
        """Count documents by quality level."""
        count = 0
        for report in self._quality_reports:
            if self._get_quality_indicator(report.overall_score) == level:
                count += 1
        return count

    def _get_quality_indicator(self, score: float) -> QualityIndicator:
        """Get quality indicator based on score."""
        if score >= 90:
            return QualityIndicator.EXCELLENT
        elif score >= 75:
            return QualityIndicator.GOOD
        elif score >= 60:
            return QualityIndicator.FAIR
        elif score >= 40:
            return QualityIndicator.POOR
        else:
            return QualityIndicator.CRITICAL

    def _get_quality_color(self, score: float) -> str:
        """Get color based on quality score."""
        palette = self.get_palette()
        indicator = self._get_quality_indicator(score)

        color_map = {
            QualityIndicator.EXCELLENT: palette.success,
            QualityIndicator.GOOD: palette.info,
            QualityIndicator.FAIR: palette.warning,
            QualityIndicator.POOR: palette.error,
            QualityIndicator.CRITICAL: palette.error
        }
        return color_map.get(indicator, palette.text_disabled)

    def _calculate_category_averages(self) -> Dict[QualityCategory, float]:
        """Calculate average scores for each quality category."""
        if not self._quality_reports:
            return {category: 0.0 for category in QualityCategory}

        category_totals = {category: 0.0 for category in QualityCategory}
        category_counts = {category: 0 for category in QualityCategory}

        for report in self._quality_reports:
            for category, score in report.category_scores.items():
                category_totals[category] += score
                category_counts[category] += 1

        return {
            category: category_totals[category] / max(category_counts[category], 1)
            for category in QualityCategory
        }

    def _calculate_quality_trends(self) -> List[Tuple[datetime, float]]:
        """Calculate quality trends over time."""
        if not self._quality_reports:
            return []

        # Sort reports by timestamp
        sorted_reports = sorted(self._quality_reports, key=lambda r: r.timestamp)
        return [(report.timestamp, report.overall_score) for report in sorted_reports]

    def _calculate_error_statistics(self) -> Dict[str, int]:
        """Calculate error distribution statistics."""
        error_stats = {}

        for report in self._quality_reports:
            # Count validation errors
            for error in report.validation_errors:
                error_type = error.split(':')[0] if ':' in error else 'General Error'
                error_stats[error_type] = error_stats.get(error_type, 0) + 1

            # Count validation warnings
            for warning in report.validation_warnings:
                warning_type = warning.split(':')[0] if ':' in warning else 'General Warning'
                error_stats[warning_type] = error_stats.get(warning_type, 0) + 1

        return error_stats

    def _create_error_display(self, error_message: str) -> ft.Control:
        """Create error display widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    self.get_icon('ERROR'),
                    color=palette.error,
                    size=48
                ),
                ft.Container(height=spacing.md),
                ft.Text(
                    "Dashboard Error",
                    style=self.get_text_style('h3'),
                    color=palette.error
                ),
                ft.Container(height=spacing.sm),
                ft.Text(
                    error_message,
                    style=self.get_text_style('body2'),
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            bgcolor=palette.surface,
            padding=ft.padding.all(32),
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.error),
            expand=True
        )

    # Event handlers
    def _handle_refresh(self, e: ft.ControlEvent) -> None:
        """Handle dashboard refresh."""
        try:
            if not self._is_refreshing:
                self._is_refreshing = True
                self.refresh_dashboard()
                self._is_refreshing = False
        except Exception as ex:
            self._logger.error(f"Failed to refresh dashboard: {ex}")
            self._is_refreshing = False

    def _handle_auto_refresh_toggle(self, e: ft.ControlEvent) -> None:
        """Handle auto-refresh toggle."""
        try:
            self._config.auto_refresh = e.control.value

            if self._config.auto_refresh:
                self._start_auto_refresh()
            else:
                self._stop_auto_refresh()

        except Exception as ex:
            self._logger.error(f"Failed to toggle auto-refresh: {ex}")

    def _handle_document_selected(self, document_id: str) -> None:
        """Handle document selection."""
        try:
            self._selected_document_id = document_id

            if self._on_document_selected:
                self._on_document_selected(document_id)

        except Exception as e:
            self._logger.error(f"Failed to handle document selection: {e}")

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()

            async def refresh_loop():
                while self._config.auto_refresh:
                    await asyncio.sleep(self._config.refresh_interval_seconds)
                    if self._config.auto_refresh and not self._is_refreshing:
                        self.refresh_dashboard()

            self._refresh_timer = asyncio.create_task(refresh_loop())

        except Exception as e:
            self._logger.error(f"Failed to start auto-refresh: {e}")

    def _stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()
                self._refresh_timer = None
        except Exception as e:
            self._logger.error(f"Failed to stop auto-refresh: {e}")

    # Public methods for external integration
    def refresh_dashboard(self) -> None:
        """Refresh dashboard data and UI."""
        try:
            self._logger.info("Refreshing quality dashboard")

            # Trigger UI update
            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to refresh dashboard: {e}")

    def add_quality_report(self, report: QualityReport) -> None:
        """Add a new quality report to the dashboard."""
        try:
            self._quality_reports.append(report)

            # Maintain max history limit
            if len(self._quality_reports) > self._config.max_history_items:
                self._quality_reports = self._quality_reports[-self._config.max_history_items:]

            # Check for quality alerts
            if self._config.enable_alerts:
                self._check_quality_alerts(report)

            # Refresh UI
            self.refresh_dashboard()

        except Exception as e:
            self._logger.error(f"Failed to add quality report: {e}")

    def update_quality_reports(self, reports: List[QualityReport]) -> None:
        """Update dashboard with new quality reports."""
        try:
            self._quality_reports = reports[-self._config.max_history_items:]
            self.refresh_dashboard()

        except Exception as e:
            self._logger.error(f"Failed to update quality reports: {e}")

    def clear_reports(self) -> None:
        """Clear all quality reports."""
        try:
            self._quality_reports.clear()
            self._selected_document_id = None
            self.refresh_dashboard()

        except Exception as e:
            self._logger.error(f"Failed to clear reports: {e}")

    def get_selected_document_id(self) -> Optional[str]:
        """Get currently selected document ID."""
        return self._selected_document_id

    def set_config(self, config: DashboardConfig) -> None:
        """Update dashboard configuration."""
        try:
            self._config = config

            # Restart auto-refresh if needed
            if self._config.auto_refresh:
                self._start_auto_refresh()
            else:
                self._stop_auto_refresh()

            self.refresh_dashboard()

        except Exception as e:
            self._logger.error(f"Failed to set config: {e}")

    def _check_quality_alerts(self, report: QualityReport) -> None:
        """Check for quality alerts and trigger callbacks."""
        try:
            if not self._on_quality_alert:
                return

            # Check for poor quality
            if report.overall_score < 40:
                self._on_quality_alert(
                    report.document_id,
                    f"Critical quality score: {report.overall_score:.1f}%"
                )

            # Check for validation errors
            if report.validation_errors:
                self._on_quality_alert(
                    report.document_id,
                    f"Validation errors detected: {len(report.validation_errors)} errors"
                )

        except Exception as e:
            self._logger.error(f"Failed to check quality alerts: {e}")

    def cleanup(self) -> None:
        """Cleanup dashboard resources."""
        try:
            self._stop_auto_refresh()
            self._quality_reports.clear()
            self._logger.info("Quality dashboard cleaned up")

        except Exception as e:
            self._logger.error(f"Failed to cleanup dashboard: {e}")
