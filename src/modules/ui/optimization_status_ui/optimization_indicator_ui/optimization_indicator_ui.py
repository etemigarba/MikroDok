"""
Module: optimization_indicator_ui
Description: Visual indicators showing active optimizations and their impact on system performance.
            Provides real-time optimization status display with responsive design and theme integration.
            Features optimization type indicators, performance impact metrics, and system health status.

Phase: 2
Location: /src/modules/ui/optimization_status_ui/optimization_indicator_ui/optimization_indicator_ui.py
"""

# Standard library imports
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import threading

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ScreenSize
)


class OptimizationType(Enum):
    """Types of system optimizations."""
    MEMORY_OPTIMIZATION = "memory_optimization"
    CPU_OPTIMIZATION = "cpu_optimization"
    GPU_OPTIMIZATION = "gpu_optimization"
    STORAGE_OPTIMIZATION = "storage_optimization"
    NETWORK_OPTIMIZATION = "network_optimization"
    BATCH_PROCESSING = "batch_processing"
    CACHE_OPTIMIZATION = "cache_optimization"
    RESOURCE_ALLOCATION = "resource_allocation"


class OptimizationStatus(Enum):
    """Status of optimization processes."""
    IDLE = "idle"
    ACTIVE = "active"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


class PerformanceImpact(Enum):
    """Performance impact levels."""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OptimizationMetric:
    """Optimization metric data structure."""
    optimization_type: OptimizationType
    status: OptimizationStatus
    impact: PerformanceImpact
    progress: float  # 0.0 to 1.0
    start_time: float
    estimated_completion: Optional[float]
    performance_gain: float  # Percentage improvement
    resource_usage: Dict[str, float]  # Resource utilization
    description: str
    error_message: Optional[str] = None


@dataclass
class OptimizationConfiguration:
    """Configuration for optimization indicator."""
    update_interval_ms: int = 500
    show_detailed_metrics: bool = True
    show_performance_impact: bool = True
    show_progress_bars: bool = True
    enable_animations: bool = True
    max_visible_optimizations: int = 8
    auto_hide_completed: bool = True
    completion_display_duration: int = 3000  # ms


class OptimizationIndicatorUI(ThemeAwareUserControl):
    """
    Visual indicators showing active optimizations and their impact on system performance.
    
    Features:
    - Real-time optimization status display with responsive design
    - Multiple optimization type indicators (memory, CPU, GPU, storage, etc.)
    - Performance impact visualization with color-coded severity levels
    - Progress tracking with animated progress bars and completion estimates
    - Resource utilization metrics with detailed breakdowns
    - Theme-aware styling with full responsive layout support
    - Accessibility compliance with screen reader support
    - Performance-optimized updates with configurable refresh rates
    """

    def __init__(self, 
                 config: Optional[OptimizationConfiguration] = None,
                 on_optimization_click: Optional[Callable[[OptimizationMetric], None]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or OptimizationConfiguration()
        self._on_optimization_click = on_optimization_click
        
        # State management
        self._active_optimizations: Dict[str, OptimizationMetric] = {}
        self._optimization_controls: Dict[str, ft.Control] = {}
        self._is_updating = False
        self._update_timer: Optional[threading.Timer] = None
        
        # UI components
        self._main_container: Optional[ft.Control] = None
        self._header_section: Optional[ft.Control] = None
        self._indicators_section: Optional[ft.Control] = None
        self._summary_section: Optional[ft.Control] = None
        
        # Performance tracking
        self._last_update_time = 0.0
        self._update_count = 0
        
        # Start update cycle
        self._start_update_cycle()

    def build(self) -> ft.Control:
        """Build the optimization indicator UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header section
        self._header_section = self._create_header_section()
        
        # Create indicators section
        self._indicators_section = self._create_indicators_section()
        
        # Create summary section
        self._summary_section = self._create_summary_section()
        
        # Main container with responsive layout
        self._main_container = ft.Container(
            content=ft.Column([
                self._header_section,
                ft.Container(height=spacing.sm),
                self._indicators_section,
                ft.Container(height=spacing.sm),
                self._summary_section
            ], spacing=0),
            padding=ft.padding.all(self.get_responsive_padding()),
            bgcolor=palette.surface,
            border_radius=self.get_breakpoint_value(8, 10, 12, 14),
            border=ft.border.all(1, palette.outline),
            animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT) if self._config.enable_animations else None
        )
        
        return self._main_container

    def _create_header_section(self) -> ft.Control:
        """Create header section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Title
        title = ft.Text(
            "System Optimizations",
            style=self.get_text_style("heading_small"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )
        
        # Status indicator
        active_count = len([opt for opt in self._active_optimizations.values() 
                           if opt.status == OptimizationStatus.ACTIVE])
        
        status_color = palette.success if active_count > 0 else palette.text_secondary
        status_text = f"{active_count} Active" if active_count > 0 else "Idle"
        
        status_indicator = ft.Container(
            content=ft.Row([
                ft.Icon(
                    self.get_icon('SPEED'),
                    size=self.get_responsive_size(16),
                    color=status_color
                ),
                ft.Text(
                    status_text,
                    style=self.get_text_style("body_small"),
                    color=status_color,
                    weight=ft.FontWeight.W_500
                )
            ], spacing=spacing.xs, tight=True),
            padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
            bgcolor=self.get_color_with_opacity(status_color, 0.1),
            border_radius=self.get_responsive_size(16),
            border=ft.border.all(1, self.get_color_with_opacity(status_color, 0.2))
        )
        
        # Header row
        return ft.Row([
            title,
            status_indicator
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def _create_indicators_section(self) -> ft.Control:
        """Create optimization indicators section."""
        if not self._active_optimizations:
            return self._create_empty_state()
        
        # Create indicator cards
        indicator_cards = []
        for opt_id, metric in self._active_optimizations.items():
            if len(indicator_cards) >= self._config.max_visible_optimizations:
                break
            
            card = self._create_optimization_card(opt_id, metric)
            indicator_cards.append(card)
        
        # Responsive grid layout
        return self.create_responsive_grid(
            children=indicator_cards,
            mobile_cols=1,
            tablet_cols=2,
            desktop_cols=3,
            large_cols=4,
            spacing=self.get_spacing().md,
            run_spacing=self.get_spacing().md
        )

    def _create_optimization_card(self, opt_id: str, metric: OptimizationMetric) -> ft.Control:
        """Create individual optimization card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Status color mapping
        status_colors = {
            OptimizationStatus.ACTIVE: palette.primary,
            OptimizationStatus.OPTIMIZING: palette.warning,
            OptimizationStatus.COMPLETED: palette.success,
            OptimizationStatus.ERROR: palette.error,
            OptimizationStatus.PAUSED: palette.text_secondary,
            OptimizationStatus.IDLE: palette.text_tertiary
        }
        
        status_color = status_colors.get(metric.status, palette.text_secondary)
        
        # Optimization type icon mapping
        type_icons = {
            OptimizationType.MEMORY_OPTIMIZATION: 'MEMORY',
            OptimizationType.CPU_OPTIMIZATION: 'CPU',
            OptimizationType.GPU_OPTIMIZATION: 'GRAPHIC_EQ',
            OptimizationType.STORAGE_OPTIMIZATION: 'STORAGE',
            OptimizationType.NETWORK_OPTIMIZATION: 'NETWORK_CHECK',
            OptimizationType.BATCH_PROCESSING: 'BATCH_PREDICTION',
            OptimizationType.CACHE_OPTIMIZATION: 'CACHED',
            OptimizationType.RESOURCE_ALLOCATION: 'TUNE'
        }
        
        icon = self.get_icon(type_icons.get(metric.optimization_type, 'SETTINGS'))
        
        # Card header
        header = ft.Row([
            ft.Icon(
                icon,
                size=self.get_responsive_size(20),
                color=status_color
            ),
            ft.Column([
                ft.Text(
                    metric.optimization_type.value.replace('_', ' ').title(),
                    style=self.get_text_style("body_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Text(
                    metric.status.value.title(),
                    style=self.get_text_style("body_small"),
                    color=status_color
                )
            ], spacing=spacing.xs // 2, tight=True)
        ], spacing=spacing.sm)
        
        # Progress section
        progress_section = None
        if self._config.show_progress_bars and metric.status in [OptimizationStatus.ACTIVE, OptimizationStatus.OPTIMIZING]:
            progress_section = self._create_progress_section(metric)
        
        # Performance impact
        impact_section = None
        if self._config.show_performance_impact:
            impact_section = self._create_impact_section(metric)
        
        # Card content
        card_content = [header]
        if progress_section:
            card_content.extend([ft.Container(height=spacing.sm), progress_section])
        if impact_section:
            card_content.extend([ft.Container(height=spacing.sm), impact_section])
        
        # Create card
        card = ft.Container(
            content=ft.Column(card_content, spacing=0),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_size(8),
            border=ft.border.all(1, self.get_color_with_opacity(status_color, 0.3)),
            on_click=lambda e, metric=metric: self._handle_optimization_click(metric) if self._on_optimization_click else None,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if self._config.enable_animations else None
        )
        
        # Store reference for updates
        self._optimization_controls[opt_id] = card
        
        return card

    def _create_progress_section(self, metric: OptimizationMetric) -> ft.Control:
        """Create progress section for optimization card."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Progress bar
        progress_bar = ft.ProgressBar(
            value=metric.progress,
            color=palette.primary,
            bgcolor=self.get_color_with_opacity(palette.primary, 0.2),
            height=self.get_responsive_size(4)
        )

        # Progress text
        progress_text = ft.Text(
            f"{metric.progress * 100:.1f}%",
            style=self.get_text_style("body_small"),
            color=palette.text_secondary,
            weight=ft.FontWeight.W_500
        )

        # Estimated completion
        completion_text = ""
        if metric.estimated_completion:
            remaining_time = metric.estimated_completion - time.time()
            if remaining_time > 0:
                if remaining_time < 60:
                    completion_text = f"~{int(remaining_time)}s remaining"
                elif remaining_time < 3600:
                    completion_text = f"~{int(remaining_time / 60)}m remaining"
                else:
                    completion_text = f"~{int(remaining_time / 3600)}h remaining"

        completion_label = ft.Text(
            completion_text,
            style=self.get_text_style("caption"),
            color=palette.text_tertiary
        ) if completion_text else None

        # Progress section
        progress_content = [
            ft.Row([
                progress_bar,
                progress_text
            ], spacing=spacing.sm, expand=True)
        ]

        if completion_label:
            progress_content.append(completion_label)

        return ft.Column(progress_content, spacing=spacing.xs)

    def _create_impact_section(self, metric: OptimizationMetric) -> ft.Control:
        """Create performance impact section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Impact color mapping
        impact_colors = {
            PerformanceImpact.MINIMAL: palette.success,
            PerformanceImpact.LOW: palette.info,
            PerformanceImpact.MODERATE: palette.warning,
            PerformanceImpact.HIGH: palette.error,
            PerformanceImpact.CRITICAL: palette.error
        }

        impact_color = impact_colors.get(metric.impact, palette.text_secondary)

        # Performance gain
        gain_text = f"+{metric.performance_gain:.1f}%" if metric.performance_gain > 0 else "Calculating..."

        # Impact indicator
        impact_chip = ft.Container(
            content=ft.Text(
                metric.impact.value.title(),
                style=self.get_text_style("caption"),
                color=impact_color,
                weight=ft.FontWeight.W_500
            ),
            padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs // 2),
            bgcolor=self.get_color_with_opacity(impact_color, 0.1),
            border_radius=self.get_responsive_size(12),
            border=ft.border.all(1, self.get_color_with_opacity(impact_color, 0.3))
        )

        # Performance gain indicator
        gain_indicator = ft.Text(
            gain_text,
            style=self.get_text_style("body_small"),
            color=palette.success if metric.performance_gain > 0 else palette.text_secondary,
            weight=ft.FontWeight.W_500
        )

        return ft.Row([
            impact_chip,
            gain_indicator
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def _create_summary_section(self) -> ft.Control:
        """Create optimization summary section."""
        if not self._active_optimizations:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate summary metrics
        total_optimizations = len(self._active_optimizations)
        active_count = len([opt for opt in self._active_optimizations.values()
                           if opt.status == OptimizationStatus.ACTIVE])
        avg_progress = sum(opt.progress for opt in self._active_optimizations.values()) / total_optimizations
        total_gain = sum(opt.performance_gain for opt in self._active_optimizations.values())

        # Summary cards
        summary_cards = [
            self._create_summary_card("Total", str(total_optimizations), self.get_icon('TUNE'), palette.primary),
            self._create_summary_card("Active", str(active_count), self.get_icon('SPEED'), palette.success),
            self._create_summary_card("Progress", f"{avg_progress * 100:.0f}%", self.get_icon('TRENDING_UP'), palette.info),
            self._create_summary_card("Gain", f"+{total_gain:.1f}%", self.get_icon('ARROW_UPWARD'), palette.success)
        ]

        # Responsive summary layout
        return self.create_responsive_grid(
            children=summary_cards,
            mobile_cols=2,
            tablet_cols=4,
            desktop_cols=4,
            large_cols=4,
            spacing=spacing.sm,
            run_spacing=spacing.sm
        )

    def _create_summary_card(self, label: str, value: str, icon: str, color: str) -> ft.Control:
        """Create summary metric card."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    icon,
                    size=self.get_responsive_size(16),
                    color=color
                ),
                ft.Text(
                    value,
                    style=self.get_text_style("heading_small"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600
                ),
                ft.Text(
                    label,
                    style=self.get_text_style("caption"),
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs // 2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.sm),
            bgcolor=self.get_color_with_opacity(color, 0.05),
            border_radius=self.get_responsive_size(6),
            border=ft.border.all(1, self.get_color_with_opacity(color, 0.2))
        )

    def _create_empty_state(self) -> ft.Control:
        """Create empty state when no optimizations are active."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    self.get_icon('SPEED'),
                    size=self.get_responsive_size(48),
                    color=palette.text_tertiary
                ),
                ft.Text(
                    "No Active Optimizations",
                    style=self.get_text_style("heading_small"),
                    color=palette.text_secondary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Text(
                    "System optimizations will appear here when active",
                    style=self.get_text_style("body_small"),
                    color=palette.text_tertiary,
                    text_align=ft.TextAlign.CENTER
                )
            ], spacing=spacing.md, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.xl),
            alignment=ft.alignment.center
        )

    def _handle_optimization_click(self, metric: OptimizationMetric) -> None:
        """Handle optimization card click."""
        if self._on_optimization_click:
            try:
                self._on_optimization_click(metric)
            except Exception as e:
                print(f"Error handling optimization click: {e}")

    def _start_update_cycle(self) -> None:
        """Start the update cycle for real-time data."""
        if not self._is_updating:
            self._is_updating = True
            self._schedule_update()

    def _schedule_update(self) -> None:
        """Schedule next update."""
        if self._is_updating:
            self._update_timer = threading.Timer(
                self._config.update_interval_ms / 1000.0,
                self._update_optimizations
            )
            self._update_timer.start()

    def _update_optimizations(self) -> None:
        """Update optimization data and UI."""
        try:
            current_time = time.time()

            # Update performance tracking
            if self._last_update_time > 0:
                update_interval = current_time - self._last_update_time
                self._update_count += 1

            self._last_update_time = current_time

            # Auto-hide completed optimizations
            if self._config.auto_hide_completed:
                self._cleanup_completed_optimizations()

            # Update UI if mounted
            if hasattr(self, 'page') and self.page:
                try:
                    self.update()
                except Exception as e:
                    print(f"Error updating optimization indicator UI: {e}")

            # Schedule next update
            self._schedule_update()

        except Exception as e:
            print(f"Error in optimization update cycle: {e}")
            self._schedule_update()

    def _cleanup_completed_optimizations(self) -> None:
        """Remove completed optimizations after display duration."""
        current_time = time.time()
        to_remove = []

        for opt_id, metric in self._active_optimizations.items():
            if metric.status == OptimizationStatus.COMPLETED:
                # Check if completion display duration has passed
                completion_time = metric.estimated_completion or current_time
                if current_time - completion_time > (self._config.completion_display_duration / 1000.0):
                    to_remove.append(opt_id)

        for opt_id in to_remove:
            self.remove_optimization(opt_id)

    # Public API methods
    def add_optimization(self, opt_id: str, metric: OptimizationMetric) -> None:
        """
        Add or update an optimization metric.

        Args:
            opt_id: Unique optimization identifier
            metric: Optimization metric data
        """
        self._active_optimizations[opt_id] = metric

        # Update UI if built
        if self._is_built and hasattr(self, 'page') and self.page:
            try:
                self.content = self.build()
                self.update()
            except Exception as e:
                print(f"Error adding optimization: {e}")

    def remove_optimization(self, opt_id: str) -> None:
        """
        Remove an optimization from display.

        Args:
            opt_id: Optimization identifier to remove
        """
        if opt_id in self._active_optimizations:
            del self._active_optimizations[opt_id]

        if opt_id in self._optimization_controls:
            del self._optimization_controls[opt_id]

        # Update UI if built
        if self._is_built and hasattr(self, 'page') and self.page:
            try:
                self.content = self.build()
                self.update()
            except Exception as e:
                print(f"Error removing optimization: {e}")

    def update_optimization_progress(self, opt_id: str, progress: float,
                                   estimated_completion: Optional[float] = None) -> None:
        """
        Update optimization progress.

        Args:
            opt_id: Optimization identifier
            progress: Progress value (0.0 to 1.0)
            estimated_completion: Estimated completion timestamp
        """
        if opt_id in self._active_optimizations:
            self._active_optimizations[opt_id].progress = max(0.0, min(1.0, progress))
            if estimated_completion is not None:
                self._active_optimizations[opt_id].estimated_completion = estimated_completion

    def update_optimization_status(self, opt_id: str, status: OptimizationStatus,
                                 error_message: Optional[str] = None) -> None:
        """
        Update optimization status.

        Args:
            opt_id: Optimization identifier
            status: New optimization status
            error_message: Error message if status is ERROR
        """
        if opt_id in self._active_optimizations:
            self._active_optimizations[opt_id].status = status
            if error_message:
                self._active_optimizations[opt_id].error_message = error_message

    def update_performance_gain(self, opt_id: str, performance_gain: float) -> None:
        """
        Update optimization performance gain.

        Args:
            opt_id: Optimization identifier
            performance_gain: Performance improvement percentage
        """
        if opt_id in self._active_optimizations:
            self._active_optimizations[opt_id].performance_gain = performance_gain

    def update_resource_usage(self, opt_id: str, resource_usage: Dict[str, float]) -> None:
        """
        Update optimization resource usage.

        Args:
            opt_id: Optimization identifier
            resource_usage: Resource utilization metrics
        """
        if opt_id in self._active_optimizations:
            self._active_optimizations[opt_id].resource_usage.update(resource_usage)

    def clear_all_optimizations(self) -> None:
        """Clear all optimization indicators."""
        self._active_optimizations.clear()
        self._optimization_controls.clear()

        # Update UI if built
        if self._is_built and hasattr(self, 'page') and self.page:
            try:
                self.content = self.build()
                self.update()
            except Exception as e:
                print(f"Error clearing optimizations: {e}")

    def get_optimization_count(self) -> int:
        """Get total number of active optimizations."""
        return len(self._active_optimizations)

    def get_active_optimization_count(self) -> int:
        """Get number of actively running optimizations."""
        return len([opt for opt in self._active_optimizations.values()
                   if opt.status == OptimizationStatus.ACTIVE])

    def get_optimization_metrics(self) -> Dict[str, OptimizationMetric]:
        """Get all optimization metrics."""
        return self._active_optimizations.copy()

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary of all optimizations.

        Returns:
            Dictionary containing performance metrics
        """
        if not self._active_optimizations:
            return {
                'total_optimizations': 0,
                'active_optimizations': 0,
                'average_progress': 0.0,
                'total_performance_gain': 0.0,
                'optimization_types': []
            }

        active_count = len([opt for opt in self._active_optimizations.values()
                           if opt.status == OptimizationStatus.ACTIVE])
        avg_progress = sum(opt.progress for opt in self._active_optimizations.values()) / len(self._active_optimizations)
        total_gain = sum(opt.performance_gain for opt in self._active_optimizations.values())
        optimization_types = list(set(opt.optimization_type for opt in self._active_optimizations.values()))

        return {
            'total_optimizations': len(self._active_optimizations),
            'active_optimizations': active_count,
            'average_progress': avg_progress,
            'total_performance_gain': total_gain,
            'optimization_types': [opt_type.value for opt_type in optimization_types]
        }

    def set_configuration(self, config: OptimizationConfiguration) -> None:
        """
        Update optimization indicator configuration.

        Args:
            config: New configuration settings
        """
        self._config = config

        # Restart update cycle with new interval
        if self._is_updating:
            self.stop_updates()
            self._start_update_cycle()

    def stop_updates(self) -> None:
        """Stop the update cycle."""
        self._is_updating = False
        if self._update_timer:
            self._update_timer.cancel()
            self._update_timer = None

    def get_update_performance_metrics(self) -> Dict[str, Any]:
        """
        Get update performance metrics.

        Returns:
            Dictionary containing performance statistics
        """
        if self._update_count == 0:
            return {
                'update_count': 0,
                'average_update_interval': 0.0,
                'last_update_time': 0.0
            }

        return {
            'update_count': self._update_count,
            'last_update_time': self._last_update_time,
            'configured_interval_ms': self._config.update_interval_ms
        }

    def will_unmount(self) -> None:
        """Clean up resources when control is unmounted."""
        self.stop_updates()
        super().will_unmount()

    # Utility methods for creating sample data (for testing/demo purposes)
    @staticmethod
    def create_sample_optimization(opt_type: OptimizationType,
                                 status: OptimizationStatus = OptimizationStatus.ACTIVE,
                                 progress: float = 0.5) -> OptimizationMetric:
        """
        Create sample optimization metric for testing.

        Args:
            opt_type: Type of optimization
            status: Optimization status
            progress: Progress value (0.0 to 1.0)

        Returns:
            Sample OptimizationMetric instance
        """
        current_time = time.time()

        return OptimizationMetric(
            optimization_type=opt_type,
            status=status,
            impact=PerformanceImpact.MODERATE,
            progress=progress,
            start_time=current_time - 30,  # Started 30 seconds ago
            estimated_completion=current_time + 60 if status == OptimizationStatus.ACTIVE else None,
            performance_gain=15.5 if status == OptimizationStatus.COMPLETED else 0.0,
            resource_usage={'cpu': 25.0, 'memory': 40.0, 'gpu': 60.0},
            description=f"{opt_type.value.replace('_', ' ').title()} optimization in progress"
        )
