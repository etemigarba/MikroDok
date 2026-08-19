"""
Module: quality_report_ui
Description: Comprehensive quality report display component for individual document quality analysis.
            Provides detailed quality metrics visualization, validation results, recommendations,
            and export functionality with theme-aware responsive design and accessibility compliance.
Phase: 3
Location: /src/modules/ui/document_manager_ui/quality_report_ui/quality_report_ui.py
"""

# Standard library imports
import asyncio
import json
import csv
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.document_quality_lg.base_interfaces import (
    QualityMetric, QualityCategory, QualityScoreResult
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ReportExportFormat(Enum):
    """Export format options for quality reports."""
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"
    HTML = "html"


class QualityIndicator(Enum):
    """Quality level indicators with score ranges."""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"           # 75-89%
    FAIR = "fair"           # 60-74%
    POOR = "poor"           # 40-59%
    CRITICAL = "critical"   # 0-39%


@dataclass
class ReportConfig:
    """Configuration for quality report display."""
    show_detailed_metrics: bool = True
    show_recommendations: bool = True
    show_validation_details: bool = True
    show_processing_stats: bool = True
    enable_export: bool = True
    auto_refresh: bool = False
    refresh_interval_seconds: float = 5.0
    max_recommendations: int = 10
    highlight_issues: bool = True


@dataclass
class QualityReportData:
    """Quality report data structure for UI display."""
    document_id: str
    document_name: str
    document_path: str
    overall_score: float
    quality_level: str
    category_scores: Dict[QualityCategory, float]
    metric_scores: Dict[QualityMetric, float]
    validation_errors: List[str]
    validation_warnings: List[str]
    recommendations: List[str]
    processing_time_ms: float
    content_length: int
    timestamp: datetime
    metadata: Dict[str, Any]


class QualityReportUI(ThemeAwareUserControl):
    """
    Quality report UI component for detailed document quality analysis display.
    
    Provides comprehensive quality reporting with:
    - Overall quality score and level indicator
    - Detailed metrics breakdown by category
    - Validation errors and warnings display
    - Quality improvement recommendations
    - Processing statistics and metadata
    - Export functionality (PDF, JSON, CSV, HTML)
    - Theme-aware responsive design
    - Accessibility compliance
    - Performance optimization
    """

    def __init__(
        self,
        config: Optional[ReportConfig] = None,
        on_export_report: Optional[Callable[[str, ReportExportFormat], None]] = None,
        on_refresh_report: Optional[Callable[[str], None]] = None,
        on_view_document: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        """
        Initialize quality report UI.
        
        Args:
            config: Report display configuration
            on_export_report: Callback for report export (document_id, format)
            on_refresh_report: Callback for report refresh (document_id)
            on_view_document: Callback for viewing source document (document_id)
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)
        
        # Configuration and callbacks
        self._config = config or ReportConfig()
        self._on_export_report = on_export_report
        self._on_refresh_report = on_refresh_report
        self._on_view_document = on_view_document
        
        # State management
        self._report_data: Optional[QualityReportData] = None
        self._is_loading = False
        self._export_dialog: Optional[ft.AlertDialog] = None
        
        # UI components
        self._header_section: Optional[ft.Control] = None
        self._metrics_section: Optional[ft.Control] = None
        self._details_section: Optional[ft.Control] = None
        self._actions_section: Optional[ft.Control] = None
        
        # Initialize logger
        self._logger = get_logger(__name__)
        
        # Auto-refresh timer
        self._refresh_timer: Optional[asyncio.Task] = None

    def build(self) -> ft.Control:
        """Build the quality report interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            rlm = self.get_responsive_layout()
            
            # Main report layout
            return ft.Container(
                content=ft.Column([
                    self._create_report_header(),
                    ft.Container(height=spacing.md),
                    self._create_metrics_overview(),
                    ft.Container(height=spacing.lg),
                    self._create_detailed_sections(),
                    ft.Container(height=spacing.lg),
                    self._create_actions_section()
                ], scroll=ft.ScrollMode.AUTO),
                bgcolor=palette.surface,
                border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
                border=ft.border.all(1, palette.outline),
                padding=ft.padding.all(rlm.get_breakpoint_value(16, 20, 24, 28)),
                expand=True
            )
            
        except Exception as e:
            self._logger.error(f"Failed to build quality report: {e}")
            return self._create_error_display(str(e))

    def _create_report_header(self) -> ft.Control:
        """Create report header with document info and overall score."""
        if not self._report_data:
            return self._create_empty_state()
        
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()
        
        # Quality indicator color
        quality_color = self._get_quality_color(self._report_data.overall_score)
        quality_icon = self._get_quality_icon(self._report_data.overall_score)
        
        # Document info section
        doc_info = ft.Column([
            ft.Text(
                self._report_data.document_name,
                style=typography.heading_medium,
                color=palette.text_primary,
                weight=ft.FontWeight.W_600
            ),
            ft.Text(
                f"Document ID: {self._report_data.document_id}",
                style=typography.body_small,
                color=palette.text_secondary
            ),
            ft.Text(
                f"Analyzed: {self._report_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                style=typography.body_small,
                color=palette.text_secondary
            )
        ], spacing=spacing.xs)
        
        # Overall score display
        score_display = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(
                        quality_icon,
                        color=quality_color,
                        size=rlm.get_breakpoint_value(24, 28, 32, 36)
                    ),
                    ft.Text(
                        f"{self._report_data.overall_score:.1f}%",
                        style=typography.heading_large,
                        color=quality_color,
                        weight=ft.FontWeight.W_700
                    )
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=spacing.sm),
                ft.Text(
                    self._report_data.quality_level.title(),
                    style=typography.body_medium,
                    color=quality_color,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=spacing.xs),
            bgcolor=f"{quality_color}15",  # 15% opacity
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
            border=ft.border.all(1, quality_color),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            width=rlm.get_breakpoint_value(120, 140, 160, 180)
        )
        
        # Action buttons
        action_buttons = ft.Row([
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip="Refresh Report",
                on_click=self._handle_refresh_report,
                icon_color=palette.primary,
                bgcolor=f"{palette.primary}15"
            ),
            ft.IconButton(
                icon=ft.Icons.VISIBILITY,
                tooltip="View Document",
                on_click=self._handle_view_document,
                icon_color=palette.primary,
                bgcolor=f"{palette.primary}15"
            ),
            ft.IconButton(
                icon=ft.Icons.DOWNLOAD,
                tooltip="Export Report",
                on_click=self._handle_export_dialog,
                icon_color=palette.primary,
                bgcolor=f"{palette.primary}15"
            )
        ], spacing=spacing.sm)
        
        # Responsive header layout
        if rlm.current_screen_size in [rlm.ScreenSize.MOBILE, rlm.ScreenSize.TABLET]:
            # Vertical layout for smaller screens
            return ft.Column([
                doc_info,
                ft.Container(height=spacing.md),
                ft.Row([
                    score_display,
                    ft.Container(expand=True),
                    action_buttons
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=spacing.sm)
        else:
            # Horizontal layout for larger screens
            return ft.Row([
                ft.Container(content=doc_info, expand=True),
                score_display,
                action_buttons
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=spacing.lg)

    def _create_empty_state(self) -> ft.Control:
        """Create empty state display when no report data is available."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    ft.Icons.DESCRIPTION_OUTLINED,
                    size=rlm.get_breakpoint_value(48, 56, 64, 72),
                    color=palette.text_tertiary
                ),
                ft.Text(
                    "No Quality Report Available",
                    style=typography.heading_medium,
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    "Select a document to view its quality analysis report",
                    style=typography.body_medium,
                    color=palette.text_tertiary,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=spacing.md),
            padding=ft.padding.all(rlm.get_breakpoint_value(32, 40, 48, 56)),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_metrics_overview(self) -> ft.Control:
        """Create metrics overview section with score cards."""
        if not self._report_data:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        # Create metric cards
        metric_cards = []
        for metric, score in self._report_data.metric_scores.items():
            metric_card = self._create_metric_card(metric, score)
            metric_cards.append(metric_card)

        # Responsive grid layout
        columns = rlm.get_breakpoint_value(1, 2, 3, 4)

        # Create grid rows
        grid_rows = []
        for i in range(0, len(metric_cards), columns):
            row_cards = metric_cards[i:i + columns]
            # Fill remaining slots with empty containers if needed
            while len(row_cards) < columns:
                row_cards.append(ft.Container())

            grid_rows.append(
                ft.Row(
                    row_cards,
                    spacing=spacing.md,
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY
                )
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Quality Metrics",
                    style=typography.heading_small,
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600
                ),
                ft.Container(height=spacing.sm),
                ft.Column(grid_rows, spacing=spacing.md)
            ], spacing=spacing.xs),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
            padding=ft.padding.all(rlm.get_breakpoint_value(16, 20, 24, 28))
        )

    def _create_metric_card(self, metric: QualityMetric, score: float) -> ft.Control:
        """Create individual metric score card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        # Get metric display info
        metric_info = self._get_metric_display_info(metric)
        score_color = self._get_score_color(score)

        # Progress indicator
        progress_bar = ft.ProgressBar(
            value=score / 100.0,
            color=score_color,
            bgcolor=f"{score_color}20",
            height=rlm.get_breakpoint_value(4, 5, 6, 7)
        )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(
                        metric_info["icon"],
                        color=score_color,
                        size=rlm.get_breakpoint_value(16, 18, 20, 22)
                    ),
                    ft.Text(
                        metric_info["name"],
                        style=typography.body_small,
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.xs),
                ft.Container(height=spacing.xs),
                ft.Text(
                    f"{score:.1f}%",
                    style=typography.heading_small,
                    color=score_color,
                    weight=ft.FontWeight.W_700
                ),
                ft.Container(height=spacing.xs),
                progress_bar,
                ft.Container(height=spacing.xs),
                ft.Text(
                    metric_info["description"],
                    style=typography.body_small,
                    color=palette.text_tertiary,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS
                )
            ], spacing=spacing.xs),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 14, 16, 18)),
            width=rlm.get_breakpoint_value(280, 220, 200, 180),
            height=rlm.get_breakpoint_value(140, 130, 120, 110)
        )

    def _create_detailed_sections(self) -> ft.Control:
        """Create detailed sections with tabs for different aspects."""
        if not self._report_data:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create tabs for different sections
        tabs = []

        if self._config.show_validation_details:
            tabs.append(ft.Tab(
                text="Validation",
                icon=ft.Icons.VERIFIED_USER,
                content=self._create_validation_section()
            ))

        if self._config.show_recommendations:
            tabs.append(ft.Tab(
                text="Recommendations",
                icon=ft.Icons.LIGHTBULB,
                content=self._create_recommendations_section()
            ))

        if self._config.show_processing_stats:
            tabs.append(ft.Tab(
                text="Statistics",
                icon=ft.Icons.ANALYTICS,
                content=self._create_statistics_section()
            ))

        # Category breakdown tab
        tabs.append(ft.Tab(
            text="Categories",
            icon=ft.Icons.CATEGORY,
            content=self._create_category_breakdown()
        ))

        return ft.Container(
            content=ft.Tabs(
                tabs=tabs,
                selected_index=0,
                animation_duration=300,
                tab_alignment=ft.TabAlignment.START,
                expand=True
            ),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
            padding=ft.padding.all(rlm.get_breakpoint_value(8, 10, 12, 14)),
            height=rlm.get_breakpoint_value(400, 450, 500, 550)
        )

    def _create_validation_section(self) -> ft.Control:
        """Create validation errors and warnings section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        content_items = []

        # Validation errors
        if self._report_data.validation_errors:
            content_items.append(
                ft.Text(
                    "Validation Errors",
                    style=typography.body_large,
                    color=palette.error,
                    weight=ft.FontWeight.W_600
                )
            )

            for error in self._report_data.validation_errors:
                content_items.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.ERROR,
                                color=palette.error,
                                size=rlm.get_breakpoint_value(16, 18, 20, 22)
                            ),
                            ft.Text(
                                error,
                                style=typography.body_medium,
                                color=palette.text_primary,
                                expand=True
                            )
                        ], spacing=spacing.sm),
                        bgcolor=f"{palette.error}10",
                        border_radius=rlm.get_breakpoint_value(4, 5, 6, 7),
                        border=ft.border.all(1, palette.error),
                        padding=ft.padding.all(rlm.get_breakpoint_value(8, 10, 12, 14))
                    )
                )

        # Validation warnings
        if self._report_data.validation_warnings:
            if content_items:  # Add spacing if errors exist
                content_items.append(ft.Container(height=spacing.lg))

            content_items.append(
                ft.Text(
                    "Validation Warnings",
                    style=typography.body_large,
                    color=palette.warning,
                    weight=ft.FontWeight.W_600
                )
            )

            for warning in self._report_data.validation_warnings:
                content_items.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.WARNING,
                                color=palette.warning,
                                size=rlm.get_breakpoint_value(16, 18, 20, 22)
                            ),
                            ft.Text(
                                warning,
                                style=typography.body_medium,
                                color=palette.text_primary,
                                expand=True
                            )
                        ], spacing=spacing.sm),
                        bgcolor=f"{palette.warning}10",
                        border_radius=rlm.get_breakpoint_value(4, 5, 6, 7),
                        border=ft.border.all(1, palette.warning),
                        padding=ft.padding.all(rlm.get_breakpoint_value(8, 10, 12, 14))
                    )
                )

        # No issues message
        if not self._report_data.validation_errors and not self._report_data.validation_warnings:
            content_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE,
                            color=palette.success,
                            size=rlm.get_breakpoint_value(24, 28, 32, 36)
                        ),
                        ft.Text(
                            "No validation issues found",
                            style=typography.body_large,
                            color=palette.success,
                            weight=ft.FontWeight.W_500
                        )
                    ], spacing=spacing.md, alignment=ft.MainAxisAlignment.CENTER),
                    padding=ft.padding.all(rlm.get_breakpoint_value(16, 20, 24, 28)),
                    alignment=ft.alignment.center
                )
            )

        return ft.Container(
            content=ft.Column(content_items, spacing=spacing.sm, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            expand=True
        )

    def _create_recommendations_section(self) -> ft.Control:
        """Create quality improvement recommendations section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        content_items = []

        if self._report_data.recommendations:
            # Limit recommendations based on config
            recommendations = self._report_data.recommendations[:self._config.max_recommendations]

            for i, recommendation in enumerate(recommendations, 1):
                content_items.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Text(
                                    str(i),
                                    style=typography.body_small,
                                    color=palette.surface,
                                    weight=ft.FontWeight.W_600,
                                    text_align=ft.TextAlign.CENTER
                                ),
                                bgcolor=palette.primary,
                                border_radius=rlm.get_breakpoint_value(10, 12, 14, 16),
                                width=rlm.get_breakpoint_value(20, 24, 28, 32),
                                height=rlm.get_breakpoint_value(20, 24, 28, 32),
                                alignment=ft.alignment.center
                            ),
                            ft.Text(
                                recommendation,
                                style=typography.body_medium,
                                color=palette.text_primary,
                                expand=True
                            )
                        ], spacing=spacing.md),
                        bgcolor=f"{palette.primary}08",
                        border_radius=rlm.get_breakpoint_value(6, 8, 10, 12),
                        border=ft.border.all(1, f"{palette.primary}30"),
                        padding=ft.padding.all(rlm.get_breakpoint_value(12, 14, 16, 18))
                    )
                )
        else:
            content_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.THUMB_UP,
                            color=palette.success,
                            size=rlm.get_breakpoint_value(24, 28, 32, 36)
                        ),
                        ft.Text(
                            "No specific recommendations - document quality is good",
                            style=typography.body_large,
                            color=palette.success,
                            weight=ft.FontWeight.W_500
                        )
                    ], spacing=spacing.md, alignment=ft.MainAxisAlignment.CENTER),
                    padding=ft.padding.all(rlm.get_breakpoint_value(16, 20, 24, 28)),
                    alignment=ft.alignment.center
                )
            )

        return ft.Container(
            content=ft.Column(content_items, spacing=spacing.md, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            expand=True
        )

    def _create_statistics_section(self) -> ft.Control:
        """Create processing statistics and metadata section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        # Statistics cards
        stats_cards = [
            self._create_stat_card(
                "Processing Time",
                f"{self._report_data.processing_time_ms:.1f} ms",
                ft.Icons.TIMER,
                palette.info
            ),
            self._create_stat_card(
                "Content Length",
                f"{self._report_data.content_length:,} chars",
                ft.Icons.TEXT_FIELDS,
                palette.primary
            ),
            self._create_stat_card(
                "Analysis Date",
                self._report_data.timestamp.strftime('%Y-%m-%d'),
                ft.Icons.CALENDAR_TODAY,
                palette.secondary
            ),
            self._create_stat_card(
                "Analysis Time",
                self._report_data.timestamp.strftime('%H:%M:%S'),
                ft.Icons.ACCESS_TIME,
                palette.secondary
            )
        ]

        # Responsive grid for stats
        columns = rlm.get_breakpoint_value(1, 2, 2, 4)
        stats_rows = []
        for i in range(0, len(stats_cards), columns):
            row_cards = stats_cards[i:i + columns]
            while len(row_cards) < columns:
                row_cards.append(ft.Container())

            stats_rows.append(
                ft.Row(
                    row_cards,
                    spacing=spacing.md,
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY
                )
            )

        content_items = [
            ft.Text(
                "Processing Statistics",
                style=typography.body_large,
                color=palette.text_primary,
                weight=ft.FontWeight.W_600
            ),
            ft.Container(height=spacing.sm),
            ft.Column(stats_rows, spacing=spacing.md)
        ]

        # Metadata section
        if self._report_data.metadata:
            content_items.extend([
                ft.Container(height=spacing.lg),
                ft.Text(
                    "Metadata",
                    style=typography.body_large,
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600
                ),
                ft.Container(height=spacing.sm),
                self._create_metadata_display()
            ])

        return ft.Container(
            content=ft.Column(content_items, spacing=spacing.xs, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            expand=True
        )

    def _create_stat_card(self, title: str, value: str, icon: str, color: str) -> ft.Control:
        """Create individual statistics card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(
                        icon,
                        color=color,
                        size=rlm.get_breakpoint_value(16, 18, 20, 22)
                    ),
                    ft.Text(
                        title,
                        style=typography.body_small,
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.xs),
                ft.Container(height=spacing.xs),
                ft.Text(
                    value,
                    style=typography.body_large,
                    color=color,
                    weight=ft.FontWeight.W_700
                )
            ], spacing=spacing.xs),
            bgcolor=f"{color}08",
            border_radius=rlm.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, f"{color}30"),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 14, 16, 18)),
            width=rlm.get_breakpoint_value(140, 130, 120, 110),
            height=rlm.get_breakpoint_value(80, 75, 70, 65)
        )

    def _create_metadata_display(self) -> ft.Control:
        """Create metadata display section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        metadata_items = []
        for key, value in self._report_data.metadata.items():
            metadata_items.append(
                ft.Row([
                    ft.Text(
                        f"{key.replace('_', ' ').title()}:",
                        style=typography.body_medium,
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500,
                        width=rlm.get_breakpoint_value(120, 140, 160, 180)
                    ),
                    ft.Text(
                        str(value),
                        style=typography.body_medium,
                        color=palette.text_primary,
                        expand=True
                    )
                ], spacing=spacing.sm)
            )

        return ft.Container(
            content=ft.Column(metadata_items, spacing=spacing.sm),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 14, 16, 18))
        )

    def _create_category_breakdown(self) -> ft.Control:
        """Create quality category breakdown section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        if not self._report_data.category_scores:
            return ft.Container(
                content=ft.Text(
                    "No category breakdown available",
                    style=typography.body_medium,
                    color=palette.text_tertiary,
                    text_align=ft.TextAlign.CENTER
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        # Create category cards
        category_cards = []
        for category, score in self._report_data.category_scores.items():
            category_info = self._get_category_display_info(category)
            score_color = self._get_score_color(score)

            category_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(
                            category_info["icon"],
                            color=score_color,
                            size=rlm.get_breakpoint_value(20, 22, 24, 26)
                        ),
                        ft.Text(
                            category_info["name"],
                            style=typography.body_medium,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600,
                            expand=True
                        )
                    ], spacing=spacing.sm),
                    ft.Container(height=spacing.sm),
                    ft.Text(
                        f"{score:.1f}%",
                        style=typography.heading_medium,
                        color=score_color,
                        weight=ft.FontWeight.W_700
                    ),
                    ft.Container(height=spacing.sm),
                    ft.ProgressBar(
                        value=score / 100.0,
                        color=score_color,
                        bgcolor=f"{score_color}20",
                        height=rlm.get_breakpoint_value(6, 7, 8, 9)
                    ),
                    ft.Container(height=spacing.sm),
                    ft.Text(
                        category_info["description"],
                        style=typography.body_small,
                        color=palette.text_tertiary,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS
                    )
                ], spacing=spacing.xs),
                bgcolor=palette.surface,
                border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
                border=ft.border.all(1, palette.outline),
                padding=ft.padding.all(rlm.get_breakpoint_value(16, 18, 20, 22)),
                width=rlm.get_breakpoint_value(300, 280, 260, 240),
                height=rlm.get_breakpoint_value(180, 170, 160, 150)
            )
            category_cards.append(category_card)

        # Responsive grid layout
        columns = rlm.get_breakpoint_value(1, 1, 2, 2)
        grid_rows = []
        for i in range(0, len(category_cards), columns):
            row_cards = category_cards[i:i + columns]
            while len(row_cards) < columns:
                row_cards.append(ft.Container())

            grid_rows.append(
                ft.Row(
                    row_cards,
                    spacing=spacing.lg,
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY
                )
            )

        return ft.Container(
            content=ft.Column(grid_rows, spacing=spacing.lg, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
            expand=True
        )

    def _create_actions_section(self) -> ft.Control:
        """Create actions section with export and other controls."""
        if not self._report_data or not self._config.enable_export:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        # Export buttons
        export_buttons = [
            ft.ElevatedButton(
                text="Export PDF",
                icon=ft.Icons.PICTURE_AS_PDF,
                on_click=lambda e: self._handle_export(ReportExportFormat.PDF),
                bgcolor=palette.primary,
                color=palette.surface,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=rlm.get_breakpoint_value(6, 8, 10, 12))
                )
            ),
            ft.ElevatedButton(
                text="Export JSON",
                icon=ft.Icons.CODE,
                on_click=lambda e: self._handle_export(ReportExportFormat.JSON),
                bgcolor=palette.secondary,
                color=palette.surface,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=rlm.get_breakpoint_value(6, 8, 10, 12))
                )
            ),
            ft.ElevatedButton(
                text="Export CSV",
                icon=ft.Icons.TABLE_CHART,
                on_click=lambda e: self._handle_export(ReportExportFormat.CSV),
                bgcolor=palette.info,
                color=palette.surface,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=rlm.get_breakpoint_value(6, 8, 10, 12))
                )
            )
        ]

        # Responsive layout for buttons
        if rlm.current_screen_size == rlm.ScreenSize.MOBILE:
            # Vertical layout for mobile
            button_layout = ft.Column(export_buttons, spacing=spacing.sm)
        else:
            # Horizontal layout for larger screens
            button_layout = ft.Row(export_buttons, spacing=spacing.md)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Export Options",
                    style=typography.body_large,
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600
                ),
                ft.Container(height=spacing.sm),
                button_layout
            ], spacing=spacing.xs),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
            padding=ft.padding.all(rlm.get_breakpoint_value(16, 20, 24, 28))
        )

    # Helper methods for UI components and data processing
    def _get_quality_color(self, score: float) -> str:
        """Get color based on quality score."""
        palette = self.get_palette()

        if score >= 90:
            return palette.success
        elif score >= 75:
            return palette.info
        elif score >= 60:
            return palette.warning
        elif score >= 40:
            return "#FF9800"  # Orange
        else:
            return palette.error

    def _get_quality_icon(self, score: float) -> str:
        """Get icon based on quality score."""
        if score >= 90:
            return ft.Icons.VERIFIED
        elif score >= 75:
            return ft.Icons.THUMB_UP
        elif score >= 60:
            return ft.Icons.WARNING
        elif score >= 40:
            return ft.Icons.ERROR_OUTLINE
        else:
            return ft.Icons.DANGEROUS

    def _get_score_color(self, score: float) -> str:
        """Get color for individual metric scores."""
        return self._get_quality_color(score)

    def _get_metric_display_info(self, metric: QualityMetric) -> Dict[str, str]:
        """Get display information for quality metrics."""
        metric_info = {
            QualityMetric.TEXT_COHERENCE: {
                "name": "Text Coherence",
                "icon": ft.Icons.TEXT_SNIPPET,
                "description": "Logical flow and readability of text content"
            },
            QualityMetric.SEMANTIC_COMPLETENESS: {
                "name": "Completeness",
                "icon": ft.Icons.CHECKLIST,
                "description": "Semantic richness and information completeness"
            },
            QualityMetric.EXTRACTION_ACCURACY: {
                "name": "Extraction",
                "icon": ft.Icons.PRECISION_MANUFACTURING,
                "description": "Accuracy of content extraction process"
            },
            QualityMetric.READABILITY_SCORE: {
                "name": "Readability",
                "icon": ft.Icons.VISIBILITY,
                "description": "Text readability and comprehension level"
            },
            QualityMetric.STRUCTURE_INTEGRITY: {
                "name": "Structure",
                "icon": ft.Icons.ACCOUNT_TREE,
                "description": "Document structure and organization quality"
            },
            QualityMetric.CONTENT_DENSITY: {
                "name": "Density",
                "icon": ft.Icons.DENSITY_MEDIUM,
                "description": "Information density and content richness"
            },
            QualityMetric.LANGUAGE_CONSISTENCY: {
                "name": "Language",
                "icon": ft.Icons.LANGUAGE,
                "description": "Language consistency and grammar quality"
            }
        }

        return metric_info.get(metric, {
            "name": metric.value.replace('_', ' ').title(),
            "icon": ft.Icons.HELP,
            "description": "Quality metric analysis"
        })

    def _get_category_display_info(self, category: QualityCategory) -> Dict[str, str]:
        """Get display information for quality categories."""
        category_info = {
            QualityCategory.CONTENT_QUALITY: {
                "name": "Content Quality",
                "icon": ft.Icons.ARTICLE,
                "description": "Overall content quality including coherence, completeness, and readability"
            },
            QualityCategory.EXTRACTION_QUALITY: {
                "name": "Extraction Quality",
                "icon": ft.Icons.TRANSFORM,
                "description": "Quality of content extraction and processing accuracy"
            },
            QualityCategory.STRUCTURAL_QUALITY: {
                "name": "Structural Quality",
                "icon": ft.Icons.ARCHITECTURE,
                "description": "Document structure, organization, and formatting quality"
            },
            QualityCategory.LINGUISTIC_QUALITY: {
                "name": "Linguistic Quality",
                "icon": ft.Icons.SPELLCHECK,
                "description": "Language consistency, grammar, and linguistic correctness"
            }
        }

        return category_info.get(category, {
            "name": category.value.replace('_', ' ').title(),
            "icon": ft.Icons.CATEGORY,
            "description": "Quality category analysis"
        })

    def _create_error_display(self, error_message: str) -> ft.Control:
        """Create error display widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    ft.Icons.ERROR_OUTLINE,
                    size=rlm.get_breakpoint_value(48, 56, 64, 72),
                    color=palette.error
                ),
                ft.Text(
                    "Error Loading Report",
                    style=typography.heading_medium,
                    color=palette.error,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    error_message,
                    style=typography.body_medium,
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=spacing.md),
            padding=ft.padding.all(rlm.get_breakpoint_value(32, 40, 48, 56)),
            alignment=ft.alignment.center,
            expand=True
        )

    # Event handlers
    def _handle_refresh_report(self, e: ft.ControlEvent) -> None:
        """Handle report refresh request."""
        try:
            if self._on_refresh_report and self._report_data:
                self._on_refresh_report(self._report_data.document_id)
        except Exception as ex:
            self._logger.error(f"Failed to refresh report: {ex}")

    def _handle_view_document(self, e: ft.ControlEvent) -> None:
        """Handle view document request."""
        try:
            if self._on_view_document and self._report_data:
                self._on_view_document(self._report_data.document_id)
        except Exception as ex:
            self._logger.error(f"Failed to view document: {ex}")

    def _handle_export_dialog(self, e: ft.ControlEvent) -> None:
        """Handle export dialog display."""
        try:
            if not self._report_data:
                return

            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            rlm = self.get_responsive_layout()

            # Create export format options
            format_options = [
                ft.RadioGroup(
                    content=ft.Column([
                        ft.Radio(value="pdf", label="PDF Report"),
                        ft.Radio(value="json", label="JSON Data"),
                        ft.Radio(value="csv", label="CSV Metrics"),
                        ft.Radio(value="html", label="HTML Report")
                    ], spacing=spacing.sm),
                    value="pdf"
                )
            ]

            self._export_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(
                    "Export Quality Report",
                    style=typography.heading_small,
                    color=palette.text_primary
                ),
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(
                            f"Export report for: {self._report_data.document_name}",
                            style=typography.body_medium,
                            color=palette.text_secondary
                        ),
                        ft.Container(height=spacing.md),
                        ft.Text(
                            "Select export format:",
                            style=typography.body_medium,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_500
                        ),
                        format_options[0]
                    ], spacing=spacing.sm),
                    width=rlm.get_breakpoint_value(300, 350, 400, 450),
                    height=rlm.get_breakpoint_value(200, 220, 240, 260)
                ),
                actions=[
                    ft.TextButton(
                        text="Cancel",
                        on_click=self._handle_export_cancel
                    ),
                    ft.ElevatedButton(
                        text="Export",
                        on_click=lambda e: self._handle_export_confirm(format_options[0]),
                        bgcolor=palette.primary,
                        color=palette.surface
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )

            if self.page:
                self.page.dialog = self._export_dialog
                self._export_dialog.open = True
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Failed to show export dialog: {ex}")

    def _handle_export_cancel(self, e: ft.ControlEvent) -> None:
        """Handle export dialog cancellation."""
        try:
            if self._export_dialog and self.page:
                self._export_dialog.open = False
                self.page.update()
        except Exception as ex:
            self._logger.error(f"Failed to cancel export dialog: {ex}")

    def _handle_export_confirm(self, format_group: ft.RadioGroup) -> None:
        """Handle export confirmation."""
        try:
            if not self._export_dialog or not self.page or not self._report_data:
                return

            # Get selected format
            selected_format = ReportExportFormat(format_group.value)

            # Close dialog
            self._export_dialog.open = False
            self.page.update()

            # Trigger export callback
            if self._on_export_report:
                self._on_export_report(self._report_data.document_id, selected_format)

        except Exception as ex:
            self._logger.error(f"Failed to confirm export: {ex}")

    def _handle_export(self, format_type: ReportExportFormat) -> None:
        """Handle direct export without dialog."""
        try:
            if self._on_export_report and self._report_data:
                self._on_export_report(self._report_data.document_id, format_type)
        except Exception as ex:
            self._logger.error(f"Failed to export report: {ex}")

    # Public methods for external control
    def set_report_data(self, report_data: QualityReportData) -> None:
        """
        Set quality report data for display.

        Args:
            report_data: Quality report data to display
        """
        try:
            self._report_data = report_data
            self._is_loading = False

            # Rebuild UI with new data
            if self._is_built:
                self.content = self.build()
                self.update()

            # Start auto-refresh if enabled
            if self._config.auto_refresh:
                self._start_auto_refresh()

        except Exception as e:
            self._logger.error(f"Failed to set report data: {e}")

    def clear_report(self) -> None:
        """Clear current report data."""
        try:
            self._report_data = None
            self._is_loading = False

            # Stop auto-refresh
            self._stop_auto_refresh()

            # Rebuild UI
            if self._is_built:
                self.content = self.build()
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to clear report: {e}")

    def set_loading(self, loading: bool) -> None:
        """
        Set loading state.

        Args:
            loading: Whether report is loading
        """
        try:
            self._is_loading = loading

            if self._is_built:
                self.content = self.build()
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to set loading state: {e}")

    def get_report_data(self) -> Optional[QualityReportData]:
        """Get current report data."""
        return self._report_data

    def update_config(self, config: ReportConfig) -> None:
        """
        Update report configuration.

        Args:
            config: New report configuration
        """
        try:
            self._config = config

            # Restart auto-refresh if needed
            if self._config.auto_refresh:
                self._start_auto_refresh()
            else:
                self._stop_auto_refresh()

            # Rebuild UI with new config
            if self._is_built:
                self.content = self.build()
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to update config: {e}")

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        try:
            self._stop_auto_refresh()  # Stop existing timer

            if self._config.auto_refresh and self._report_data:
                async def refresh_loop():
                    while self._config.auto_refresh and self._report_data:
                        await asyncio.sleep(self._config.refresh_interval_seconds)
                        if self._on_refresh_report and self._report_data:
                            self._on_refresh_report(self._report_data.document_id)

                self._refresh_timer = asyncio.create_task(refresh_loop())

        except Exception as e:
            self._logger.error(f"Failed to start auto-refresh: {e}")

    def _stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        try:
            if self._refresh_timer and not self._refresh_timer.done():
                self._refresh_timer.cancel()
                self._refresh_timer = None
        except Exception as e:
            self._logger.error(f"Failed to stop auto-refresh: {e}")

    def cleanup(self) -> None:
        """Cleanup resources and stop timers."""
        try:
            self._stop_auto_refresh()
        except Exception as e:
            self._logger.error(f"Failed to cleanup: {e}")
