"""
Module: dataset_selector_ui
Description: Comprehensive dataset selection interface for training configuration with document browsing,
            validation, format detection, and configuration options. Provides intuitive dataset selection
            with real-time validation, quality metrics, and responsive design with full theme integration.
Phase: 4
Location: /src/modules/ui/training_configuration_ui/dataset_selector_ui/dataset_selector_ui.py
"""

# Standard library imports
import asyncio
import logging
import os
import psutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Training data pipeline imports
try:
    from src.modules.logic.training_data_pipeline_lg.base_interfaces import (
        DataFormat,
        DataStatus,
        DataLoaderConfig,
        ValidationConfig,
        ValidationLevel,
        DataSample,
        LoadingResult,
        ValidationResult
    )
    from src.modules.logic.training_data_pipeline_lg.data_loader_lg.data_loader_lg import (
        DataLoader,
        TrainingDataLoader
    )
    from src.modules.logic.training_data_pipeline_lg.data_validator_lg.data_validator_lg import (
        DataValidator
    )
    TRAINING_PIPELINE_AVAILABLE = True
except ImportError:
    DataFormat = None
    DataStatus = None
    DataLoaderConfig = None
    ValidationConfig = None
    ValidationLevel = None
    DataSample = None
    LoadingResult = None
    ValidationResult = None
    DataLoader = None
    TrainingDataLoader = None
    DataValidator = None
    TRAINING_PIPELINE_AVAILABLE = False

# Document repository imports
try:
    from src.modules.database.document_repository_db.document_dao_db.document_dao_db import (
        DocumentDAODB,
        Document,
        DocumentStatus as DBDocumentStatus
    )
    from src.modules.database.document_collections_db.collection_manager_db.collection_manager_db import (
        CollectionManagerDB,
        DocumentCollection
    )
    DOCUMENT_REPOSITORY_AVAILABLE = True
except ImportError:
    DocumentDAODB = None
    Document = None
    DBDocumentStatus = None
    CollectionManagerDB = None
    DocumentCollection = None
    DOCUMENT_REPOSITORY_AVAILABLE = False

# Get logger
logger = logging.getLogger(__name__)


class DatasetSelectionMode(Enum):
    """Dataset selection modes."""
    DOCUMENT_BROWSER = "document_browser"
    FILE_UPLOAD = "file_upload"
    COLLECTION_SELECT = "collection_select"
    CUSTOM_PATH = "custom_path"


class DatasetSource(Enum):
    """Dataset source types."""
    DOCUMENTS = "documents"
    FILES = "files"
    COLLECTIONS = "collections"
    EXTERNAL = "external"


class DatasetFormat(Enum):
    """Supported dataset formats."""
    AUTO_DETECT = "auto_detect"
    TEXT = "text"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"


class DatasetStatus(Enum):
    """Dataset validation status."""
    NOT_SELECTED = "not_selected"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


@dataclass
class DatasetMetrics:
    """Dataset quality and statistics metrics."""
    total_samples: int = 0
    valid_samples: int = 0
    invalid_samples: int = 0
    total_size_mb: float = 0.0
    avg_text_length: float = 0.0
    quality_score: float = 0.0
    format_detected: Optional[str] = None
    encoding_detected: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class DatasetConfiguration:
    """Dataset configuration settings."""
    source: DatasetSource = DatasetSource.DOCUMENTS
    format: DatasetFormat = DatasetFormat.AUTO_DETECT
    path: Optional[Path] = None
    collection_ids: List[str] = field(default_factory=list)
    document_ids: List[str] = field(default_factory=list)
    train_split: float = 0.8
    validation_split: float = 0.1
    test_split: float = 0.1
    batch_size: int = 32
    shuffle: bool = True
    random_seed: int = 42
    max_samples: Optional[int] = None
    min_text_length: int = 10
    max_text_length: int = 8192
    quality_threshold: float = 0.6
    enable_augmentation: bool = False
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetValidationResult:
    """Dataset validation result."""
    status: DatasetStatus
    metrics: DatasetMetrics
    config: DatasetConfiguration
    validation_time_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DatasetSelectorConfig:
    """Configuration for dataset selector interface."""
    mode: DatasetSelectionMode = DatasetSelectionMode.DOCUMENT_BROWSER
    show_validation_details: bool = True
    show_quality_metrics: bool = True
    show_advanced_options: bool = False
    enable_real_time_validation: bool = True
    auto_detect_format: bool = True
    default_config: DatasetConfiguration = field(default_factory=DatasetConfiguration)


class DatasetSelectorUI(ThemeAwareUserControl):
    """
    Comprehensive dataset selection interface for training configuration.
    
    Provides intuitive dataset selection with document browsing, file upload,
    collection selection, and real-time validation with quality metrics.
    
    Features:
    - Multiple dataset selection modes (documents, files, collections, custom paths)
    - Real-time dataset validation and quality assessment
    - Interactive document and collection browsing
    - Format detection and encoding validation
    - Quality metrics and statistics display
    - Responsive design with theme integration
    - Advanced configuration options
    - Split ratio configuration (train/validation/test)
    - Batch size and sampling options
    """

    def __init__(self,
                 config: Optional[DatasetSelectorConfig] = None,
                 on_dataset_change: Optional[Callable[[DatasetConfiguration], None]] = None,
                 on_validation_complete: Optional[Callable[[DatasetValidationResult], None]] = None):
        """
        Initialize dataset selector UI.
        
        Args:
            config: Dataset selector configuration
            on_dataset_change: Callback for dataset configuration changes
            on_validation_complete: Callback for validation completion
        """
        super().__init__()
        
        self._config = config or DatasetSelectorConfig()
        self._on_dataset_change = on_dataset_change
        self._on_validation_complete = on_validation_complete
        
        # Current state
        self._current_config = self._config.default_config
        self._current_validation: Optional[DatasetValidationResult] = None
        self._is_validating = False
        
        # UI components
        self._mode_selector: Optional[ft.Tabs] = None
        self._content_area: Optional[ft.Container] = None
        self._validation_panel: Optional[ft.Container] = None
        self._metrics_panel: Optional[ft.Container] = None
        self._config_panel: Optional[ft.Container] = None
        
        # Document browser components
        self._document_list: Optional[ft.ListView] = None
        self._collection_dropdown: Optional[ft.Dropdown] = None
        self._search_field: Optional[ft.TextField] = None
        
        # File upload components
        self._file_picker: Optional[ft.FilePicker] = None
        self._selected_files_list: Optional[ft.Column] = None
        
        # Configuration components
        self._format_dropdown: Optional[ft.Dropdown] = None
        self._train_split_slider: Optional[ft.Slider] = None
        self._validation_split_slider: Optional[ft.Slider] = None
        self._batch_size_field: Optional[ft.TextField] = None
        
        # Data managers
        self._data_loader: Optional[DataLoader] = None
        self._data_validator: Optional[DataValidator] = None
        self._document_dao: Optional[DocumentDAODB] = None
        self._collection_manager: Optional[CollectionManagerDB] = None
        
        # Initialize data managers
        self._initialize_data_managers()
        
        # Logger
        self._logger = logging.getLogger(__name__)

    def _initialize_data_managers(self) -> None:
        """Initialize data management components."""
        try:
            if TRAINING_PIPELINE_AVAILABLE:
                self._data_loader = TrainingDataLoader() if TrainingDataLoader else None
                self._data_validator = DataValidator() if DataValidator else None
            
            if DOCUMENT_REPOSITORY_AVAILABLE:
                self._document_dao = DocumentDAODB() if DocumentDAODB else None
                self._collection_manager = CollectionManagerDB() if CollectionManagerDB else None
                
        except Exception as e:
            self._logger.warning(f"Failed to initialize data managers: {e}")

    def build(self) -> ft.Control:
        """Build the dataset selector interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create mode selector tabs
        self._mode_selector = ft.Tabs(
            selected_index=0,
            on_change=self._on_mode_change,
            tabs=[
                ft.Tab(
                    text="Documents",
                    icon=self.get_icon('DESCRIPTION'),
                    content=self._create_document_browser_content()
                ),
                ft.Tab(
                    text="Upload Files",
                    icon=self.get_icon('UPLOAD_FILE'),
                    content=self._create_file_upload_content()
                ),
                ft.Tab(
                    text="Collections",
                    icon=self.get_icon('FOLDER'),
                    content=self._create_collection_select_content()
                ),
                ft.Tab(
                    text="Custom Path",
                    icon=self.get_icon('FOLDER_OPEN'),
                    content=self._create_custom_path_content()
                )
            ],
            indicator_color=palette.primary,
            label_color=palette.on_surface,
            unselected_label_color=palette.on_surface_variant
        )

        # Create main layout
        main_content = ft.Column([
            self._create_header(),
            ft.Divider(color=palette.outline_variant),
            self._mode_selector,
            ft.Divider(color=palette.outline_variant) if self._config.show_validation_details else None,
            self._create_validation_panel() if self._config.show_validation_details else None,
            ft.Divider(color=palette.outline_variant) if self._config.show_quality_metrics else None,
            self._create_metrics_panel() if self._config.show_quality_metrics else None,
            ft.Divider(color=palette.outline_variant) if self._config.show_advanced_options else None,
            self._create_config_panel() if self._config.show_advanced_options else None
        ], spacing=spacing.section_spacing)

        return self.create_responsive_container(
            content=main_content,
            padding=self.get_breakpoint_value(
                mobile=spacing.container_padding,
                tablet=spacing.container_padding + 4,
                desktop=spacing.container_padding + 8,
                large=spacing.container_padding + 12
            )
        )

    def _create_header(self) -> ft.Control:
        """Create header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Row([
            ft.Column([
                ft.Text(
                    "Dataset Selection",
                    style=typography.heading_medium,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_600
                ),
                ft.Text(
                    "Select and configure training datasets for your model",
                    style=typography.body_medium,
                    color=palette.on_surface_variant
                )
            ], expand=True),
            ft.IconButton(
                icon=self.get_icon('REFRESH'),
                tooltip="Refresh datasets",
                on_click=self._on_refresh_datasets,
                icon_color=palette.primary
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def _create_document_browser_content(self) -> ft.Control:
        """Create document browser content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Search and filter controls
        search_controls = ft.Row([
            ft.TextField(
                hint_text="Search documents...",
                prefix_icon=self.get_icon('SEARCH'),
                on_change=self._on_search_documents,
                expand=True,
                bgcolor=palette.surface,
                border_color=palette.outline_variant,
                focused_border_color=palette.primary
            ),
            ft.Dropdown(
                label="Collection",
                hint_text="All Collections",
                options=[],
                on_change=self._on_collection_filter,
                width=200,
                bgcolor=palette.surface,
                border_color=palette.outline_variant
            )
        ], spacing=spacing.element_spacing)

        # Document list
        self._document_list = ft.ListView(
            controls=[],
            spacing=spacing.element_spacing,
            padding=ft.padding.all(spacing.element_spacing),
            expand=True
        )

        # Selection summary
        selection_summary = ft.Container(
            content=ft.Row([
                ft.Text(
                    "0 documents selected",
                    style=self.get_typography().body_small,
                    color=palette.on_surface_variant
                ),
                ft.TextButton(
                    text="Select All",
                    on_click=self._on_select_all_documents
                ),
                ft.TextButton(
                    text="Clear Selection",
                    on_click=self._on_clear_selection
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.element_spacing),
            border_radius=8
        )

        return ft.Column([
            search_controls,
            ft.Container(
                content=self._document_list,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=8,
                height=300
            ),
            selection_summary
        ], spacing=spacing.section_spacing)

    def _create_file_upload_content(self) -> ft.Control:
        """Create file upload content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # File picker
        self._file_picker = ft.FilePicker(
            on_result=self._on_files_selected
        )

        # Upload area
        upload_area = ft.Container(
            content=ft.Column([
                ft.Icon(
                    self.get_icon('CLOUD_UPLOAD'),
                    size=48,
                    color=palette.primary
                ),
                ft.Text(
                    "Drop files here or click to browse",
                    style=self.get_typography().body_large,
                    color=palette.on_surface,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    "Supported formats: TXT, JSON, JSONL, CSV, PARQUET",
                    style=self.get_typography().body_small,
                    color=palette.on_surface_variant,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.ElevatedButton(
                    text="Browse Files",
                    icon=self.get_icon('FOLDER_OPEN'),
                    on_click=lambda _: self._file_picker.pick_files(
                        dialog_title="Select training data files",
                        file_type=ft.FilePickerFileType.CUSTOM,
                        allowed_extensions=["txt", "json", "jsonl", "csv", "parquet"]
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.element_spacing),
            bgcolor=palette.surface_variant,
            border=ft.border.all(2, palette.outline_variant, ft.BorderStyle.DASHED),
            border_radius=12,
            padding=ft.padding.all(spacing.section_spacing),
            height=200,
            alignment=ft.alignment.center
        )

        # Selected files list
        self._selected_files_list = ft.Column(
            controls=[],
            spacing=spacing.element_spacing
        )

        return ft.Column([
            upload_area,
            ft.Text(
                "Selected Files",
                style=self.get_typography().title_small,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500
            ),
            ft.Container(
                content=self._selected_files_list,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=8,
                padding=ft.padding.all(spacing.element_spacing),
                height=200
            )
        ], spacing=spacing.section_spacing)

    def _create_collection_select_content(self) -> ft.Control:
        """Create collection selection content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Collection list
        collection_list = ft.ListView(
            controls=[],
            spacing=spacing.element_spacing,
            padding=ft.padding.all(spacing.element_spacing),
            expand=True
        )

        # Collection info panel
        collection_info = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Collection Information",
                    style=self.get_typography().title_small,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                ft.Text(
                    "Select a collection to view details",
                    style=self.get_typography().body_medium,
                    color=palette.on_surface_variant
                )
            ], spacing=spacing.element_spacing),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.section_spacing),
            border_radius=8,
            height=150
        )

        return ft.Column([
            ft.Text(
                "Available Collections",
                style=self.get_typography().title_small,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500
            ),
            ft.Container(
                content=collection_list,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=8,
                height=250
            ),
            collection_info
        ], spacing=spacing.section_spacing)

    def _create_custom_path_content(self) -> ft.Control:
        """Create custom path content."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Path input
        path_input = ft.Row([
            ft.TextField(
                hint_text="Enter dataset path...",
                prefix_icon=self.get_icon('FOLDER'),
                on_change=self._on_path_change,
                expand=True,
                bgcolor=palette.surface,
                border_color=palette.outline_variant,
                focused_border_color=palette.primary
            ),
            ft.IconButton(
                icon=self.get_icon('FOLDER_OPEN'),
                tooltip="Browse for folder",
                on_click=self._on_browse_folder,
                icon_color=palette.primary
            )
        ], spacing=spacing.element_spacing)

        # Path validation status
        path_status = ft.Container(
            content=ft.Row([
                ft.Icon(
                    self.get_icon('INFO'),
                    size=16,
                    color=palette.on_surface_variant
                ),
                ft.Text(
                    "Enter a valid dataset path",
                    style=self.get_typography().body_small,
                    color=palette.on_surface_variant
                )
            ], spacing=8),
            padding=ft.padding.all(spacing.element_spacing),
            bgcolor=palette.surface_variant,
            border_radius=8
        )

        return ft.Column([
            ft.Text(
                "Custom Dataset Path",
                style=self.get_typography().title_small,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500
            ),
            path_input,
            path_status
        ], spacing=spacing.section_spacing)

    def _create_validation_panel(self) -> ft.Control:
        """Create validation status panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Validation status
        status_row = ft.Row([
            ft.Icon(
                self.get_icon('CHECK_CIRCLE'),
                size=20,
                color=palette.success if self._current_validation and
                      self._current_validation.status == DatasetStatus.VALID else palette.on_surface_variant
            ),
            ft.Text(
                "No dataset selected",
                style=self.get_typography().body_medium,
                color=palette.on_surface
            ),
            ft.ProgressRing(
                width=16,
                height=16,
                visible=self._is_validating
            )
        ], spacing=spacing.element_spacing)

        # Validation details
        validation_details = ft.Column(
            controls=[],
            spacing=spacing.element_spacing
        )

        self._validation_panel = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Dataset Validation",
                    style=self.get_typography().title_small,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                status_row,
                validation_details
            ], spacing=spacing.element_spacing),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.section_spacing),
            border_radius=8
        )

        return self._validation_panel

    def _create_metrics_panel(self) -> ft.Control:
        """Create quality metrics panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Metrics grid
        metrics_grid = self.create_responsive_grid(
            children=[
                self._create_metric_card("Total Samples", "0", self.get_icon('DATASET')),
                self._create_metric_card("Valid Samples", "0", self.get_icon('CHECK')),
                self._create_metric_card("Quality Score", "0%", self.get_icon('STAR')),
                self._create_metric_card("Size", "0 MB", self.get_icon('STORAGE'))
            ],
            mobile_cols=2,
            tablet_cols=2,
            desktop_cols=4,
            large_cols=4,
            spacing=spacing.element_spacing
        )

        self._metrics_panel = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Dataset Metrics",
                    style=self.get_typography().title_small,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                metrics_grid
            ], spacing=spacing.element_spacing),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.section_spacing),
            border_radius=8
        )

        return self._metrics_panel

    def _create_metric_card(self, title: str, value: str, icon: str) -> ft.Control:
        """Create a metric display card."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, size=20, color=palette.primary),
                    ft.Text(
                        title,
                        style=self.get_typography().body_small,
                        color=palette.on_surface_variant
                    )
                ], spacing=8),
                ft.Text(
                    value,
                    style=self.get_typography().title_medium,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_600
                )
            ], spacing=4),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.element_spacing),
            border_radius=8,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_config_panel(self) -> ft.Control:
        """Create configuration options panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Format selection
        format_options = [
            ft.dropdown.Option(key=f.value, text=f.value.replace('_', ' ').title())
            for f in DatasetFormat
        ]

        self._format_dropdown = ft.Dropdown(
            label="Dataset Format",
            value=self._current_config.format.value,
            options=format_options,
            on_change=self._on_format_change,
            bgcolor=palette.surface,
            border_color=palette.outline_variant
        )

        # Split configuration
        split_config = ft.Column([
            ft.Text(
                "Data Split Configuration",
                style=self.get_typography().body_medium,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500
            ),
            ft.Row([
                ft.Column([
                    ft.Text("Train", style=self.get_typography().body_small),
                    ft.Slider(
                        min=0.1,
                        max=0.9,
                        value=self._current_config.train_split,
                        divisions=8,
                        label=f"{int(self._current_config.train_split * 100)}%",
                        on_change=self._on_train_split_change
                    )
                ], expand=True),
                ft.Column([
                    ft.Text("Validation", style=self.get_typography().body_small),
                    ft.Slider(
                        min=0.05,
                        max=0.3,
                        value=self._current_config.validation_split,
                        divisions=5,
                        label=f"{int(self._current_config.validation_split * 100)}%",
                        on_change=self._on_validation_split_change
                    )
                ], expand=True)
            ], spacing=spacing.section_spacing)
        ], spacing=spacing.element_spacing)

        # Batch configuration
        batch_config = ft.Row([
            ft.TextField(
                label="Batch Size",
                value=str(self._current_config.batch_size),
                on_change=self._on_batch_size_change,
                width=120,
                input_filter=ft.NumbersOnlyInputFilter(),
                bgcolor=palette.surface,
                border_color=palette.outline_variant
            ),
            ft.Checkbox(
                label="Shuffle Data",
                value=self._current_config.shuffle,
                on_change=self._on_shuffle_change
            ),
            ft.TextField(
                label="Random Seed",
                value=str(self._current_config.random_seed),
                on_change=self._on_seed_change,
                width=120,
                input_filter=ft.NumbersOnlyInputFilter(),
                bgcolor=palette.surface,
                border_color=palette.outline_variant
            )
        ], spacing=spacing.section_spacing)

        self._config_panel = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Advanced Configuration",
                    style=self.get_typography().title_small,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                self._format_dropdown,
                split_config,
                batch_config
            ], spacing=spacing.section_spacing),
            bgcolor=palette.surface_variant,
            padding=ft.padding.all(spacing.section_spacing),
            border_radius=8
        )

        return self._config_panel

    # Event handlers
    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle mode selection change."""
        if e.control.selected_index is not None:
            modes = list(DatasetSelectionMode)
            if e.control.selected_index < len(modes):
                self._config.mode = modes[e.control.selected_index]
                self._refresh_content()

    def _on_refresh_datasets(self, e: ft.ControlEvent) -> None:
        """Handle refresh datasets request."""
        self._refresh_content()
        if self._config.enable_real_time_validation:
            self._validate_current_selection()

    def _on_search_documents(self, e: ft.ControlEvent) -> None:
        """Handle document search."""
        search_term = e.control.value if e.control.value else ""
        self._filter_documents(search_term)

    def _on_collection_filter(self, e: ft.ControlEvent) -> None:
        """Handle collection filter change."""
        collection_id = e.control.value if e.control.value else None
        self._filter_documents_by_collection(collection_id)

    def _on_select_all_documents(self, e: ft.ControlEvent) -> None:
        """Handle select all documents."""
        # Implementation for selecting all visible documents
        self._select_all_visible_documents()

    def _on_clear_selection(self, e: ft.ControlEvent) -> None:
        """Handle clear selection."""
        self._current_config.document_ids.clear()
        self._update_selection_display()
        if self._on_dataset_change:
            self._on_dataset_change(self._current_config)

    def _on_files_selected(self, e: ft.FilePickerResultEvent) -> None:
        """Handle file selection from file picker."""
        if e.files:
            selected_paths = [Path(f.path) for f in e.files]
            self._current_config.path = selected_paths[0] if len(selected_paths) == 1 else None
            self._update_selected_files_display(selected_paths)
            if self._config.enable_real_time_validation:
                self._validate_current_selection()

    def _on_path_change(self, e: ft.ControlEvent) -> None:
        """Handle custom path change."""
        path_str = e.control.value if e.control.value else ""
        if path_str:
            self._current_config.path = Path(path_str)
            if self._config.enable_real_time_validation:
                self._validate_current_selection()

    def _on_browse_folder(self, e: ft.ControlEvent) -> None:
        """Handle browse folder request."""
        # Implementation for folder browsing
        pass

    def _on_format_change(self, e: ft.ControlEvent) -> None:
        """Handle format selection change."""
        if e.control.value:
            self._current_config.format = DatasetFormat(e.control.value)
            if self._on_dataset_change:
                self._on_dataset_change(self._current_config)

    def _on_train_split_change(self, e: ft.ControlEvent) -> None:
        """Handle train split change."""
        self._current_config.train_split = e.control.value
        self._update_split_labels()
        if self._on_dataset_change:
            self._on_dataset_change(self._current_config)

    def _on_validation_split_change(self, e: ft.ControlEvent) -> None:
        """Handle validation split change."""
        self._current_config.validation_split = e.control.value
        self._update_split_labels()
        if self._on_dataset_change:
            self._on_dataset_change(self._current_config)

    def _on_batch_size_change(self, e: ft.ControlEvent) -> None:
        """Handle batch size change."""
        try:
            batch_size = int(e.control.value) if e.control.value else 32
            self._current_config.batch_size = max(1, batch_size)
            if self._on_dataset_change:
                self._on_dataset_change(self._current_config)
        except ValueError:
            pass

    def _on_shuffle_change(self, e: ft.ControlEvent) -> None:
        """Handle shuffle option change."""
        self._current_config.shuffle = e.control.value
        if self._on_dataset_change:
            self._on_dataset_change(self._current_config)

    def _on_seed_change(self, e: ft.ControlEvent) -> None:
        """Handle random seed change."""
        try:
            seed = int(e.control.value) if e.control.value else 42
            self._current_config.random_seed = seed
            if self._on_dataset_change:
                self._on_dataset_change(self._current_config)
        except ValueError:
            pass

    # Utility methods
    def _refresh_content(self) -> None:
        """Refresh content based on current mode."""
        try:
            if self._config.mode == DatasetSelectionMode.DOCUMENT_BROWSER:
                self._load_documents()
            elif self._config.mode == DatasetSelectionMode.COLLECTION_SELECT:
                self._load_collections()

            self.update()
        except Exception as e:
            self._logger.error(f"Failed to refresh content: {e}")

    def _load_documents(self) -> None:
        """Load available documents."""
        if not self._document_dao or not self._document_list:
            return

        try:
            # Load documents from database
            documents = self._document_dao.get_all_documents()

            # Clear existing items
            self._document_list.controls.clear()

            # Add document items
            for doc in documents:
                doc_item = self._create_document_item(doc)
                self._document_list.controls.append(doc_item)

        except Exception as e:
            self._logger.error(f"Failed to load documents: {e}")

    def _load_collections(self) -> None:
        """Load available collections."""
        if not self._collection_manager:
            return

        try:
            # Load collections from database
            collections = self._collection_manager.get_all_collections()

            # Update collection dropdown and list
            # Implementation depends on collection manager interface

        except Exception as e:
            self._logger.error(f"Failed to load collections: {e}")

    def _create_document_item(self, document: Any) -> ft.Control:
        """Create a document list item."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Document checkbox and info
        return ft.Container(
            content=ft.Row([
                ft.Checkbox(
                    value=hasattr(document, 'id') and str(document.id) in self._current_config.document_ids,
                    on_change=lambda e, doc_id=str(document.id): self._on_document_select(e, doc_id)
                ),
                ft.Column([
                    ft.Text(
                        getattr(document, 'title', 'Untitled Document'),
                        style=self.get_typography().body_medium,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        f"Size: {getattr(document, 'size', 0)} bytes | "
                        f"Status: {getattr(document, 'status', 'Unknown')}",
                        style=self.get_typography().body_small,
                        color=palette.on_surface_variant
                    )
                ], expand=True, spacing=4)
            ], spacing=spacing.element_spacing),
            padding=ft.padding.all(spacing.element_spacing),
            border_radius=8,
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _on_document_select(self, e: ft.ControlEvent, document_id: str) -> None:
        """Handle document selection."""
        if e.control.value:
            if document_id not in self._current_config.document_ids:
                self._current_config.document_ids.append(document_id)
        else:
            if document_id in self._current_config.document_ids:
                self._current_config.document_ids.remove(document_id)

        self._update_selection_display()
        if self._on_dataset_change:
            self._on_dataset_change(self._current_config)

        if self._config.enable_real_time_validation:
            self._validate_current_selection()

    def _filter_documents(self, search_term: str) -> None:
        """Filter documents by search term."""
        # Implementation for document filtering
        pass

    def _filter_documents_by_collection(self, collection_id: Optional[str]) -> None:
        """Filter documents by collection."""
        # Implementation for collection-based filtering
        pass

    def _select_all_visible_documents(self) -> None:
        """Select all currently visible documents."""
        # Implementation for selecting all visible documents
        pass

    def _update_selection_display(self) -> None:
        """Update selection summary display."""
        # Implementation for updating selection count and summary
        pass

    def _update_selected_files_display(self, file_paths: List[Path]) -> None:
        """Update selected files display."""
        if not self._selected_files_list:
            return

        # Clear existing files
        self._selected_files_list.controls.clear()

        # Add file items
        for file_path in file_paths:
            file_item = self._create_file_item(file_path)
            self._selected_files_list.controls.append(file_item)

        self.update()

    def _create_file_item(self, file_path: Path) -> ft.Control:
        """Create a file list item."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Get file info
        try:
            file_size = file_path.stat().st_size if file_path.exists() else 0
            size_str = self._format_file_size(file_size)
        except Exception:
            size_str = "Unknown size"

        return ft.Container(
            content=ft.Row([
                ft.Icon(
                    self.get_icon('DESCRIPTION'),
                    size=20,
                    color=palette.primary
                ),
                ft.Column([
                    ft.Text(
                        file_path.name,
                        style=self.get_typography().body_medium,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        f"{size_str} | {file_path.suffix.upper()[1:] if file_path.suffix else 'Unknown'}",
                        style=self.get_typography().body_small,
                        color=palette.on_surface_variant
                    )
                ], expand=True, spacing=4),
                ft.IconButton(
                    icon=self.get_icon('CLOSE'),
                    tooltip="Remove file",
                    on_click=lambda e, path=file_path: self._remove_file(path),
                    icon_color=palette.error
                )
            ], spacing=spacing.element_spacing),
            padding=ft.padding.all(spacing.element_spacing),
            border_radius=8,
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _remove_file(self, file_path: Path) -> None:
        """Remove file from selection."""
        # Implementation for removing file from selection
        pass

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    def _update_split_labels(self) -> None:
        """Update split ratio labels."""
        # Implementation for updating split labels
        pass

    async def _validate_current_selection(self) -> None:
        """Validate current dataset selection."""
        if self._is_validating:
            return

        self._is_validating = True

        try:
            # Create validation config
            validation_config = ValidationConfig(
                validation_level=ValidationLevel.STANDARD,
                min_text_length=self._current_config.min_text_length,
                max_text_length=self._current_config.max_text_length,
                min_quality_score=self._current_config.quality_threshold
            )

            # Perform validation based on current selection
            if self._current_config.source == DatasetSource.DOCUMENTS and self._current_config.document_ids:
                result = await self._validate_documents(validation_config)
            elif self._current_config.source == DatasetSource.FILES and self._current_config.path:
                result = await self._validate_files(validation_config)
            else:
                result = DatasetValidationResult(
                    status=DatasetStatus.NOT_SELECTED,
                    metrics=DatasetMetrics(),
                    config=self._current_config
                )

            self._current_validation = result
            self._update_validation_display()

            if self._on_validation_complete:
                self._on_validation_complete(result)

        except Exception as e:
            self._logger.error(f"Validation failed: {e}")
            self._current_validation = DatasetValidationResult(
                status=DatasetStatus.ERROR,
                metrics=DatasetMetrics(validation_errors=[str(e)]),
                config=self._current_config
            )
            self._update_validation_display()

        finally:
            self._is_validating = False

    async def _validate_documents(self, config: ValidationConfig) -> DatasetValidationResult:
        """Validate selected documents."""
        # Implementation for document validation
        return DatasetValidationResult(
            status=DatasetStatus.VALID,
            metrics=DatasetMetrics(
                total_samples=len(self._current_config.document_ids),
                valid_samples=len(self._current_config.document_ids)
            ),
            config=self._current_config
        )

    async def _validate_files(self, config: ValidationConfig) -> DatasetValidationResult:
        """Validate selected files."""
        # Implementation for file validation
        return DatasetValidationResult(
            status=DatasetStatus.VALID,
            metrics=DatasetMetrics(total_samples=1, valid_samples=1),
            config=self._current_config
        )

    def _update_validation_display(self) -> None:
        """Update validation status display."""
        if not self._validation_panel or not self._current_validation:
            return

        palette = self.get_palette()

        # Update status based on validation result
        status_icon = self.get_icon('CHECK_CIRCLE') if self._current_validation.status == DatasetStatus.VALID else self.get_icon('ERROR')
        status_color = palette.success if self._current_validation.status == DatasetStatus.VALID else palette.error

        # Update validation panel content
        # Implementation for updating validation display
        self.update()

    def _update_metrics_display(self) -> None:
        """Update metrics panel display."""
        if not self._metrics_panel or not self._current_validation:
            return

        metrics = self._current_validation.metrics

        # Update metric cards with current values
        # Implementation for updating metrics display
        self.update()

    # Public methods
    def get_current_config(self) -> DatasetConfiguration:
        """Get current dataset configuration."""
        return self._current_config

    def set_config(self, config: DatasetConfiguration) -> None:
        """Set dataset configuration."""
        self._current_config = config
        self._refresh_content()
        if self._config.enable_real_time_validation:
            asyncio.create_task(self._validate_current_selection())

    def get_validation_result(self) -> Optional[DatasetValidationResult]:
        """Get current validation result."""
        return self._current_validation

    def refresh(self) -> None:
        """Refresh the dataset selector interface."""
        self._refresh_content()

    def validate_dataset(self) -> None:
        """Manually trigger dataset validation."""
        if not self._is_validating:
            asyncio.create_task(self._validate_current_selection())
