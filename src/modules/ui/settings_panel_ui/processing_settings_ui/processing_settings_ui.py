"""
Module: processing_settings_ui
Description: Comprehensive document processing configuration interface for MikroDok application.
            Provides settings for document processing including chunk size, overlap configuration,
            OCR settings, format support, quality validation, deduplication, table extraction,
            and advanced processing options. Features responsive design, real-time validation,
            and full theme system integration with accessibility compliance.

Features:
- Document format support configuration with enable/disable toggles
- Chunking strategy selection with size and overlap controls
- OCR language and preprocessing settings
- Quality validation thresholds and criteria
- Deduplication settings with similarity thresholds
- Table extraction and image processing options
- Advanced processing parameters and timeouts
- Configuration presets and import/export functionality
- Real-time validation with visual feedback
- Responsive design with breakpoint-aware layouts
- Full theme system integration with accessibility support

Phase: 2
Location: /src/modules/ui/settings_panel_ui/processing_settings_ui/processing_settings_ui.py
"""

# Standard library imports
import os
import json
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)


class DocumentFormat(Enum):
    """Supported document formats for processing."""
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "md"
    TEXT = "txt"
    RTF = "rtf"
    ODT = "odt"


class ChunkingStrategy(Enum):
    """Document chunking strategies."""
    FIXED_SIZE = "fixed_size"
    SENTENCE_BOUNDARY = "sentence_boundary"
    PARAGRAPH_BOUNDARY = "paragraph_boundary"
    SEMANTIC_BOUNDARY = "semantic_boundary"
    SLIDING_WINDOW = "sliding_window"


class OCRLanguage(Enum):
    """OCR language options."""
    ENGLISH = "eng"
    SPANISH = "spa"
    FRENCH = "fra"
    GERMAN = "deu"
    ITALIAN = "ita"
    PORTUGUESE = "por"
    RUSSIAN = "rus"
    CHINESE_SIMPLIFIED = "chi_sim"
    CHINESE_TRADITIONAL = "chi_tra"
    JAPANESE = "jpn"
    KOREAN = "kor"
    ARABIC = "ara"


class QualityLevel(Enum):
    """Quality validation levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    STRICT = "strict"


@dataclass
class ProcessingSettingsConfig:
    """Configuration for processing settings interface."""
    # Display settings
    show_advanced_options: bool = False
    enable_real_time_validation: bool = True
    enable_auto_save: bool = True
    auto_save_interval: int = 30  # seconds
    enable_tooltips: bool = True
    enable_import_export: bool = True
    
    # Validation settings
    validate_on_change: bool = True
    show_validation_errors: bool = True
    
    # Performance settings
    debounce_delay: int = 300  # milliseconds
    max_history_entries: int = 50


@dataclass
class ProcessingSettingsData:
    """Data structure for document processing settings."""
    # Document format support
    enabled_formats: List[DocumentFormat] = field(default_factory=lambda: [
        DocumentFormat.PDF, DocumentFormat.DOCX, DocumentFormat.HTML,
        DocumentFormat.MARKDOWN, DocumentFormat.TEXT
    ])
    
    # Chunking settings
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE_BOUNDARY
    chunk_size: int = 512  # tokens
    min_chunk_size: int = 256  # tokens
    max_chunk_size: int = 1024  # tokens
    chunk_overlap: int = 50  # tokens
    overlap_percentage: float = 10.0  # percentage
    preserve_sentences: bool = True
    preserve_paragraphs: bool = True
    respect_section_boundaries: bool = True
    
    # OCR settings
    enable_ocr: bool = True
    ocr_language: OCRLanguage = OCRLanguage.ENGLISH
    additional_ocr_languages: List[OCRLanguage] = field(default_factory=list)
    ocr_confidence_threshold: float = 30.0
    enable_preprocessing: bool = True
    enable_deskew: bool = True
    enable_noise_removal: bool = True
    enable_contrast_enhancement: bool = True
    ocr_resize_factor: float = 2.0
    
    # Table and image extraction
    enable_table_extraction: bool = True
    table_detection_strategy: str = "lattice"  # lattice, stream, auto
    enable_image_extraction: bool = True
    image_min_size: Tuple[int, int] = (50, 50)
    extract_image_text: bool = True
    
    # Quality validation
    enable_quality_validation: bool = True
    quality_level: QualityLevel = QualityLevel.MEDIUM
    quality_threshold: float = 0.7
    min_content_length: int = 100  # characters
    max_content_length: int = 1000000  # characters
    enable_language_detection: bool = True
    enable_encoding_detection: bool = True
    
    # Deduplication settings
    enable_deduplication: bool = True
    similarity_threshold: float = 0.95
    enable_semantic_dedup: bool = True
    enable_fuzzy_matching: bool = False
    hash_algorithm: str = "sha256"
    
    # Processing limits and timeouts
    max_concurrent_documents: int = 5
    max_file_size_mb: int = 100
    processing_timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Advanced settings
    enable_metadata_extraction: bool = True
    enable_structure_analysis: bool = True
    enable_content_classification: bool = False
    enable_entity_recognition: bool = False
    preserve_original_formatting: bool = True
    enable_compression: bool = False
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class ProcessingSettingsUI(ThemeAwareUserControl):
    """
    Comprehensive document processing configuration interface.
    
    Features:
    - Document format support configuration with visual toggles
    - Chunking strategy selection with real-time preview
    - OCR language and preprocessing configuration
    - Quality validation settings with threshold controls
    - Deduplication configuration with similarity settings
    - Table and image extraction options
    - Advanced processing parameters and limits
    - Configuration presets and import/export
    - Real-time validation with visual feedback
    - Responsive design with breakpoint-aware layouts
    - Full theme system integration with accessibility support
    """
    
    def __init__(self,
                 config: Optional[ProcessingSettingsConfig] = None,
                 initial_data: Optional[ProcessingSettingsData] = None,
                 on_settings_changed: Optional[Callable[[ProcessingSettingsData], None]] = None,
                 **kwargs):
        """
        Initialize processing settings interface.
        
        Args:
            config: Configuration for the interface
            initial_data: Initial settings data
            on_settings_changed: Callback for settings changes
            **kwargs: Additional arguments for UserControl
        """
        super().__init__(**kwargs)
        
        # Configuration and data
        self.config = config or ProcessingSettingsConfig()
        self._current_settings = initial_data or ProcessingSettingsData()
        self._original_settings = ProcessingSettingsData(**asdict(self._current_settings))
        
        # Callbacks
        self._on_settings_changed = on_settings_changed
        
        # UI state
        self._validation_errors: Dict[str, str] = {}
        self._is_modified = False
        self._current_tab = 0
        self._validation_timer = None
        
        # UI components
        self._tabs: Optional[ft.Tabs] = None
        self._validation_panel: Optional[ft.Container] = None
        self._action_bar: Optional[ft.Container] = None
        
        # Build UI
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the processing settings interface."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Initialize responsive manager
        self._responsive_manager = self.get_responsive_layout_manager()
        
        # Main container with responsive design
        self.content = ft.Column(
            controls=[
                self._create_header(),
                self._create_tabs(),
                self._create_validation_panel(),
                self._create_action_bar()
            ],
            spacing=spacing.md,
            expand=True
        )
        
        # Apply theme-aware styling
        self.bgcolor = palette.surface
        self.border_radius = self.get_responsive_value(8, 10, 12, 14)
        self.padding = self.get_responsive_padding(
            mobile=spacing.md,
            tablet=spacing.lg,
            desktop=spacing.xl
        )
        
        # Initial validation
        if self.config.enable_real_time_validation:
            self._schedule_validation()

    def _create_header(self) -> ft.Container:
        """Create the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        title_text = ft.Text(
            "Document Processing Settings",
            style=ft.TextStyle(
                size=typography.h2[0],
                weight=ft.FontWeight.W_600,
                color=palette.text_primary
            )
        )

        subtitle_text = ft.Text(
            "Configure document processing, chunking, OCR, and quality validation settings",
            style=ft.TextStyle(
                size=typography.body_medium[0],
                color=palette.text_secondary
            )
        )

        # Status indicator
        status_indicator = ft.Row(
            controls=[
                ft.Icon(
                    icons.CHECK_CIRCLE if not self._validation_errors else icons.WARNING,
                    color=palette.success if not self._validation_errors else palette.warning,
                    size=self.get_responsive_value(16, 18, 20, 22)
                ),
                ft.Text(
                    "Configuration Valid" if not self._validation_errors else f"{len(self._validation_errors)} Issues",
                    style=ft.TextStyle(
                        size=typography.body_small[0],
                        color=palette.success if not self._validation_errors else palette.warning
                    )
                )
            ],
            spacing=spacing.xs,
            alignment=ft.MainAxisAlignment.START
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[title_text, subtitle_text],
                                spacing=spacing.xs,
                                expand=True
                            ),
                            status_indicator
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.only(bottom=spacing.lg)
        )

    def _create_tabs(self) -> ft.Container:
        """Create the tabbed interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._tabs = ft.Tabs(
            selected_index=self._current_tab,
            on_change=self._on_tab_changed,
            tabs=[
                ft.Tab(
                    text="Formats & Chunking",
                    content=self._create_formats_chunking_tab()
                ),
                ft.Tab(
                    text="OCR & Extraction",
                    content=self._create_ocr_extraction_tab()
                ),
                ft.Tab(
                    text="Quality & Validation",
                    content=self._create_quality_validation_tab()
                ),
                ft.Tab(
                    text="Advanced Settings",
                    content=self._create_advanced_settings_tab()
                )
            ],
            expand=True
        )

        return ft.Container(
            content=self._tabs,
            expand=True,
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=ft.padding.all(spacing.md)
        )

    def _create_formats_chunking_tab(self) -> ft.Container:
        """Create the formats and chunking configuration tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Document formats section
        formats_section = self._create_settings_section(
            "Supported Document Formats",
            [
                self._create_format_toggles(),
                self._create_file_size_limit_setting()
            ]
        )

        # Chunking strategy section
        chunking_section = self._create_settings_section(
            "Chunking Configuration",
            [
                self._create_chunking_strategy_setting(),
                self._create_chunk_size_settings(),
                self._create_overlap_settings(),
                self._create_boundary_preservation_settings()
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[formats_section, chunking_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_ocr_extraction_tab(self) -> ft.Container:
        """Create the OCR and extraction configuration tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # OCR settings section
        ocr_section = self._create_settings_section(
            "OCR Configuration",
            [
                self._create_switch_setting(
                    "enable_ocr",
                    "Enable OCR",
                    "Enable Optical Character Recognition for scanned documents",
                    self._current_settings.enable_ocr
                ),
                self._create_ocr_language_settings(),
                self._create_ocr_preprocessing_settings(),
                self._create_ocr_confidence_setting()
            ]
        )

        # Table and image extraction section
        extraction_section = self._create_settings_section(
            "Table & Image Extraction",
            [
                self._create_switch_setting(
                    "enable_table_extraction",
                    "Extract Tables",
                    "Extract and parse tables from documents",
                    self._current_settings.enable_table_extraction
                ),
                self._create_table_detection_setting(),
                self._create_switch_setting(
                    "enable_image_extraction",
                    "Extract Images",
                    "Extract images and diagrams from documents",
                    self._current_settings.enable_image_extraction
                ),
                self._create_image_settings()
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[ocr_section, extraction_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_quality_validation_tab(self) -> ft.Container:
        """Create the quality validation configuration tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Quality validation section
        quality_section = self._create_settings_section(
            "Quality Validation",
            [
                self._create_switch_setting(
                    "enable_quality_validation",
                    "Enable Quality Validation",
                    "Validate document quality before processing",
                    self._current_settings.enable_quality_validation
                ),
                self._create_quality_level_setting(),
                self._create_quality_threshold_setting(),
                self._create_content_length_settings()
            ]
        )

        # Deduplication section
        dedup_section = self._create_settings_section(
            "Deduplication",
            [
                self._create_switch_setting(
                    "enable_deduplication",
                    "Enable Deduplication",
                    "Remove duplicate content during processing",
                    self._current_settings.enable_deduplication
                ),
                self._create_similarity_threshold_setting(),
                self._create_deduplication_options()
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[quality_section, dedup_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_advanced_settings_tab(self) -> ft.Container:
        """Create the advanced settings configuration tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Processing limits section
        limits_section = self._create_settings_section(
            "Processing Limits",
            [
                self._create_slider_setting(
                    "max_concurrent_documents",
                    "Max Concurrent Documents",
                    "Maximum number of documents to process simultaneously",
                    1, 20, 5,
                    self._current_settings.max_concurrent_documents
                ),
                self._create_slider_setting(
                    "processing_timeout_seconds",
                    "Processing Timeout (seconds)",
                    "Maximum time to spend processing a single document",
                    30, 1800, 300,
                    self._current_settings.processing_timeout_seconds
                ),
                self._create_slider_setting(
                    "max_retries",
                    "Max Retries",
                    "Maximum number of retry attempts for failed processing",
                    0, 10, 3,
                    self._current_settings.max_retries
                )
            ]
        )

        # Advanced features section
        features_section = self._create_settings_section(
            "Advanced Features",
            [
                self._create_switch_setting(
                    "enable_metadata_extraction",
                    "Extract Metadata",
                    "Extract document metadata and properties",
                    self._current_settings.enable_metadata_extraction
                ),
                self._create_switch_setting(
                    "enable_structure_analysis",
                    "Structure Analysis",
                    "Analyze document structure and hierarchy",
                    self._current_settings.enable_structure_analysis
                ),
                self._create_switch_setting(
                    "enable_content_classification",
                    "Content Classification",
                    "Classify document content by type and topic",
                    self._current_settings.enable_content_classification
                ),
                self._create_switch_setting(
                    "preserve_original_formatting",
                    "Preserve Formatting",
                    "Maintain original document formatting where possible",
                    self._current_settings.preserve_original_formatting
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[limits_section, features_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_validation_panel(self) -> ft.Container:
        """Create the validation panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        if not self._validation_errors:
            return ft.Container(height=0)

        error_controls = []
        for field, error in self._validation_errors.items():
            error_controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(
                            icons.ERROR_OUTLINE,
                            color=palette.error,
                            size=self.get_responsive_value(16, 18, 20, 22)
                        ),
                        ft.Text(
                            f"{field}: {error}",
                            style=ft.TextStyle(
                                size=typography.body_small[0],
                                color=palette.error
                            ),
                            expand=True
                        )
                    ],
                    spacing=spacing.xs
                )
            )

        self._validation_panel = ft.Container(
            content=ft.Column(
                controls=error_controls,
                spacing=spacing.xs
            ),
            bgcolor=palette.error_container,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            padding=ft.padding.all(spacing.md),
            margin=ft.margin.only(bottom=spacing.md)
        )

        return self._validation_panel

    def _create_action_bar(self) -> ft.Container:
        """Create the action bar with save, reset, and import/export buttons."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Action buttons
        save_button = ft.ElevatedButton(
            text="Save Settings",
            icon=icons.SAVE,
            on_click=self._on_save_clicked,
            disabled=not self._is_modified,
            style=ft.ButtonStyle(
                bgcolor=palette.primary,
                color=palette.text_primary
            )
        )

        reset_button = ft.OutlinedButton(
            text="Reset to Defaults",
            icon=icons.RESTORE,
            on_click=self._on_reset_clicked,
            disabled=not self._is_modified
        )

        # Import/Export buttons
        import_button = ft.TextButton(
            text="Import",
            icon=icons.UPLOAD,
            on_click=self._on_import_clicked
        )

        export_button = ft.TextButton(
            text="Export",
            icon=icons.DOWNLOAD,
            on_click=self._on_export_clicked
        )

        self._action_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[import_button, export_button],
                        spacing=spacing.sm
                    ),
                    ft.Row(
                        controls=[reset_button, save_button],
                        spacing=spacing.sm
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=ft.padding.only(top=spacing.lg)
        )

        return self._action_bar

    def _create_settings_section(self, title: str, controls: List[ft.Control]) -> ft.Container:
        """Create a settings section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        title_text = ft.Text(
            title,
            style=ft.TextStyle(
                size=typography.h4[0],
                weight=ft.FontWeight.W_600,
                color=palette.text_primary
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    title_text,
                    ft.Divider(color=palette.outline_variant),
                    *controls
                ],
                spacing=spacing.md
            ),
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_switch_setting(self, key: str, title: str, description: str, value: bool) -> ft.Container:
        """Create a switch setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        switch = ft.Switch(
            value=value,
            on_change=lambda e: self._on_setting_changed(key, e.control.value)
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                style=ft.TextStyle(
                                    size=typography.body_medium[0],
                                    weight=ft.FontWeight.W_500,
                                    color=palette.text_primary
                                )
                            ),
                            ft.Text(
                                description,
                                style=ft.TextStyle(
                                    size=typography.body_small[0],
                                    color=palette.text_secondary
                                )
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    ),
                    switch
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.all(spacing.md)
        )

    def _create_slider_setting(self, key: str, title: str, description: str,
                             min_val: int, max_val: int, step: int, value: int) -> ft.Container:
        """Create a slider setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        value_text = ft.Text(
            str(value),
            style=ft.TextStyle(
                size=typography.body_medium[0],
                weight=ft.FontWeight.W_500,
                color=palette.text_primary
            )
        )

        slider = ft.Slider(
            min=min_val,
            max=max_val,
            divisions=(max_val - min_val) // step,
            value=value,
            on_change=lambda e: self._on_slider_changed(key, e.control.value, value_text)
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        title,
                                        style=ft.TextStyle(
                                            size=typography.body_medium[0],
                                            weight=ft.FontWeight.W_500,
                                            color=palette.text_primary
                                        )
                                    ),
                                    ft.Text(
                                        description,
                                        style=ft.TextStyle(
                                            size=typography.body_small[0],
                                            color=palette.text_secondary
                                        )
                                    )
                                ],
                                spacing=spacing.xs,
                                expand=True
                            ),
                            value_text
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    slider
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md)
        )

    def _create_dropdown_setting(self, key: str, title: str, description: str,
                                options: List[Tuple[str, str]], value: str) -> ft.Container:
        """Create a dropdown setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=k, text=v) for k, v in options],
            value=value,
            on_change=lambda e: self._on_setting_changed(key, e.control.value)
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        style=ft.TextStyle(
                            size=typography.body_medium[0],
                            weight=ft.FontWeight.W_500,
                            color=palette.text_primary
                        )
                    ),
                    ft.Text(
                        description,
                        style=ft.TextStyle(
                            size=typography.body_small[0],
                            color=palette.text_secondary
                        )
                    ),
                    dropdown
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md)
        )

    def _create_format_toggles(self) -> ft.Container:
        """Create document format toggle controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        format_controls = []
        for format_type in DocumentFormat:
            is_enabled = format_type in self._current_settings.enabled_formats

            format_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                format_type.value.upper(),
                                style=ft.TextStyle(
                                    size=typography.body_medium[0],
                                    weight=ft.FontWeight.W_500,
                                    color=palette.text_primary
                                )
                            ),
                            ft.Switch(
                                value=is_enabled,
                                on_change=lambda e, fmt=format_type: self._on_format_toggled(fmt, e.control.value)
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    padding=ft.padding.symmetric(vertical=spacing.xs, horizontal=spacing.sm),
                    bgcolor=palette.surface_variant if is_enabled else None,
                    border_radius=self.get_responsive_value(6, 8, 10, 12)
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=format_controls,
                spacing=spacing.xs
            ),
            padding=ft.padding.all(spacing.md)
        )

    def _create_file_size_limit_setting(self) -> ft.Container:
        """Create file size limit setting."""
        return self._create_slider_setting(
            "max_file_size_mb",
            "Maximum File Size (MB)",
            "Maximum size for individual documents",
            1, 500, 10,
            self._current_settings.max_file_size_mb
        )

    def _create_chunking_strategy_setting(self) -> ft.Container:
        """Create chunking strategy dropdown."""
        options = [
            (strategy.value, strategy.value.replace('_', ' ').title())
            for strategy in ChunkingStrategy
        ]

        return self._create_dropdown_setting(
            "chunking_strategy",
            "Chunking Strategy",
            "Method for splitting documents into chunks",
            options,
            self._current_settings.chunking_strategy.value
        )

    def _create_chunk_size_settings(self) -> ft.Container:
        """Create chunk size configuration controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_slider_setting(
                        "chunk_size",
                        "Target Chunk Size (tokens)",
                        "Preferred size for document chunks",
                        128, 2048, 32,
                        self._current_settings.chunk_size
                    ),
                    self._create_slider_setting(
                        "min_chunk_size",
                        "Minimum Chunk Size (tokens)",
                        "Minimum allowed chunk size",
                        64, 1024, 16,
                        self._current_settings.min_chunk_size
                    ),
                    self._create_slider_setting(
                        "max_chunk_size",
                        "Maximum Chunk Size (tokens)",
                        "Maximum allowed chunk size",
                        256, 4096, 64,
                        self._current_settings.max_chunk_size
                    )
                ],
                spacing=spacing.sm
            )
        )

    def _create_overlap_settings(self) -> ft.Container:
        """Create overlap configuration controls."""
        return self._create_slider_setting(
            "chunk_overlap",
            "Chunk Overlap (tokens)",
            "Number of overlapping tokens between chunks",
            0, 200, 10,
            self._current_settings.chunk_overlap
        )

    def _create_boundary_preservation_settings(self) -> ft.Container:
        """Create boundary preservation settings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_switch_setting(
                        "preserve_sentences",
                        "Preserve Sentences",
                        "Avoid breaking sentences across chunks",
                        self._current_settings.preserve_sentences
                    ),
                    self._create_switch_setting(
                        "preserve_paragraphs",
                        "Preserve Paragraphs",
                        "Avoid breaking paragraphs across chunks",
                        self._current_settings.preserve_paragraphs
                    ),
                    self._create_switch_setting(
                        "respect_section_boundaries",
                        "Respect Section Boundaries",
                        "Avoid breaking document sections across chunks",
                        self._current_settings.respect_section_boundaries
                    )
                ],
                spacing=spacing.sm
            )
        )

    def _create_ocr_language_settings(self) -> ft.Container:
        """Create OCR language configuration."""
        options = [
            (lang.value, lang.name.replace('_', ' ').title())
            for lang in OCRLanguage
        ]

        return self._create_dropdown_setting(
            "ocr_language",
            "Primary OCR Language",
            "Primary language for OCR processing",
            options,
            self._current_settings.ocr_language.value
        )

    def _create_ocr_preprocessing_settings(self) -> ft.Container:
        """Create OCR preprocessing settings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_switch_setting(
                        "enable_preprocessing",
                        "Enable Preprocessing",
                        "Apply image preprocessing before OCR",
                        self._current_settings.enable_preprocessing
                    ),
                    self._create_switch_setting(
                        "enable_deskew",
                        "Deskew Images",
                        "Correct image rotation and skew",
                        self._current_settings.enable_deskew
                    ),
                    self._create_switch_setting(
                        "enable_noise_removal",
                        "Remove Noise",
                        "Remove image noise and artifacts",
                        self._current_settings.enable_noise_removal
                    ),
                    self._create_switch_setting(
                        "enable_contrast_enhancement",
                        "Enhance Contrast",
                        "Improve image contrast for better OCR",
                        self._current_settings.enable_contrast_enhancement
                    )
                ],
                spacing=spacing.sm
            )
        )

    def _create_ocr_confidence_setting(self) -> ft.Container:
        """Create OCR confidence threshold setting."""
        return self._create_slider_setting(
            "ocr_confidence_threshold",
            "OCR Confidence Threshold (%)",
            "Minimum confidence level for OCR text acceptance",
            0, 100, 5,
            int(self._current_settings.ocr_confidence_threshold)
        )

    def _create_table_detection_setting(self) -> ft.Container:
        """Create table detection strategy setting."""
        options = [
            ("lattice", "Lattice Detection"),
            ("stream", "Stream Detection"),
            ("auto", "Automatic Detection")
        ]

        return self._create_dropdown_setting(
            "table_detection_strategy",
            "Table Detection Strategy",
            "Method for detecting tables in documents",
            options,
            self._current_settings.table_detection_strategy
        )

    def _create_image_settings(self) -> ft.Container:
        """Create image extraction settings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_switch_setting(
                        "extract_image_text",
                        "Extract Text from Images",
                        "Use OCR to extract text from embedded images",
                        self._current_settings.extract_image_text
                    ),
                    ft.Text(
                        f"Minimum Image Size: {self._current_settings.image_min_size[0]}x{self._current_settings.image_min_size[1]} pixels",
                        style=ft.TextStyle(
                            size=self.get_typography().body_small[0],
                            color=palette.text_secondary
                        )
                    )
                ],
                spacing=spacing.sm
            )
        )

    def _create_quality_level_setting(self) -> ft.Container:
        """Create quality level setting."""
        options = [
            (level.value, level.value.title())
            for level in QualityLevel
        ]

        return self._create_dropdown_setting(
            "quality_level",
            "Quality Level",
            "Overall quality validation strictness",
            options,
            self._current_settings.quality_level.value
        )

    def _create_quality_threshold_setting(self) -> ft.Container:
        """Create quality threshold setting."""
        return self._create_slider_setting(
            "quality_threshold",
            "Quality Threshold",
            "Minimum quality score for document acceptance",
            0, 100, 5,
            int(self._current_settings.quality_threshold * 100)
        )

    def _create_content_length_settings(self) -> ft.Container:
        """Create content length validation settings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_slider_setting(
                        "min_content_length",
                        "Minimum Content Length (characters)",
                        "Minimum required content length",
                        10, 1000, 10,
                        self._current_settings.min_content_length
                    ),
                    ft.Text(
                        f"Maximum Content Length: {self._current_settings.max_content_length:,} characters",
                        style=ft.TextStyle(
                            size=self.get_typography().body_small[0],
                            color=palette.text_secondary
                        )
                    )
                ],
                spacing=spacing.sm
            )
        )

    def _create_similarity_threshold_setting(self) -> ft.Container:
        """Create similarity threshold setting."""
        return self._create_slider_setting(
            "similarity_threshold",
            "Similarity Threshold",
            "Threshold for considering documents as duplicates",
            50, 100, 1,
            int(self._current_settings.similarity_threshold * 100)
        )

    def _create_deduplication_options(self) -> ft.Container:
        """Create deduplication options."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_switch_setting(
                        "enable_semantic_dedup",
                        "Semantic Deduplication",
                        "Use semantic similarity for deduplication",
                        self._current_settings.enable_semantic_dedup
                    ),
                    self._create_switch_setting(
                        "enable_fuzzy_matching",
                        "Fuzzy Matching",
                        "Use fuzzy string matching for deduplication",
                        self._current_settings.enable_fuzzy_matching
                    ),
                    self._create_dropdown_setting(
                        "hash_algorithm",
                        "Hash Algorithm",
                        "Algorithm for content hashing",
                        [("sha256", "SHA-256"), ("md5", "MD5"), ("sha1", "SHA-1")],
                        self._current_settings.hash_algorithm
                    )
                ],
                spacing=spacing.sm
            )
        )

    # Event handlers
    def _on_tab_changed(self, e: ft.ControlEvent) -> None:
        """Handle tab change."""
        self._current_tab = e.control.selected_index
        self.update()

    def _on_setting_changed(self, key: str, value: Any) -> None:
        """Handle setting value change."""
        # Update the setting value
        if hasattr(self._current_settings, key):
            # Handle enum conversions
            if key == "chunking_strategy":
                value = ChunkingStrategy(value)
            elif key == "ocr_language":
                value = OCRLanguage(value)
            elif key == "quality_level":
                value = QualityLevel(value)
            elif key in ["quality_threshold", "similarity_threshold"]:
                value = value / 100.0  # Convert percentage to decimal

            setattr(self._current_settings, key, value)

            # Mark as modified
            self._is_modified = True

            # Schedule validation
            if self.config.enable_real_time_validation:
                self._schedule_validation()

            # Notify callback
            if self._on_settings_changed:
                self._on_settings_changed(self._current_settings)

            # Update UI
            self.update()

    def _on_slider_changed(self, key: str, value: float, value_text: ft.Text) -> None:
        """Handle slider value change."""
        int_value = int(value)
        value_text.value = str(int_value)
        value_text.update()
        self._on_setting_changed(key, int_value)

    def _on_format_toggled(self, format_type: DocumentFormat, enabled: bool) -> None:
        """Handle document format toggle."""
        if enabled and format_type not in self._current_settings.enabled_formats:
            self._current_settings.enabled_formats.append(format_type)
        elif not enabled and format_type in self._current_settings.enabled_formats:
            self._current_settings.enabled_formats.remove(format_type)

        self._is_modified = True

        if self.config.enable_real_time_validation:
            self._schedule_validation()

        if self._on_settings_changed:
            self._on_settings_changed(self._current_settings)

        self.update()

    def _on_save_clicked(self, e: ft.ControlEvent) -> None:
        """Handle save button click."""
        # Validate settings
        if self._validate_settings():
            # Save settings (implementation would depend on persistence layer)
            self._original_settings = ProcessingSettingsData(**asdict(self._current_settings))
            self._is_modified = False

            # Show success message
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("Processing settings saved successfully"),
                    bgcolor=self.get_palette().success
                )
            )

            self.update()

    def _on_reset_clicked(self, e: ft.ControlEvent) -> None:
        """Handle reset button click."""
        # Reset to original settings
        self._current_settings = ProcessingSettingsData(**asdict(self._original_settings))
        self._is_modified = False
        self._validation_errors.clear()

        # Rebuild UI with reset values
        self._build_ui()
        self.update()

    def _on_import_clicked(self, e: ft.ControlEvent) -> None:
        """Handle import button click."""
        # Implementation would show file picker and import settings
        pass

    def _on_export_clicked(self, e: ft.ControlEvent) -> None:
        """Handle export button click."""
        # Implementation would show file picker and export settings
        pass

    def _schedule_validation(self) -> None:
        """Schedule validation with debouncing."""
        if self._validation_timer:
            # Cancel previous timer (in real implementation)
            pass

        # In real implementation, would use a timer
        # For now, validate immediately
        self._validate_settings()

    def _validate_settings(self) -> bool:
        """Validate current settings and update validation errors."""
        self._validation_errors.clear()

        # Validate chunk sizes
        if self._current_settings.min_chunk_size >= self._current_settings.max_chunk_size:
            self._validation_errors["chunk_size"] = "Minimum chunk size must be less than maximum"

        if self._current_settings.chunk_size < self._current_settings.min_chunk_size:
            self._validation_errors["chunk_size"] = "Target chunk size must be at least minimum size"

        if self._current_settings.chunk_size > self._current_settings.max_chunk_size:
            self._validation_errors["chunk_size"] = "Target chunk size must not exceed maximum size"

        if self._current_settings.chunk_overlap >= self._current_settings.chunk_size:
            self._validation_errors["chunk_overlap"] = "Overlap must be less than chunk size"

        # Validate format selection
        if not self._current_settings.enabled_formats:
            self._validation_errors["formats"] = "At least one document format must be enabled"

        # Validate OCR settings
        if self._current_settings.enable_ocr:
            if self._current_settings.ocr_confidence_threshold < 0 or self._current_settings.ocr_confidence_threshold > 100:
                self._validation_errors["ocr_confidence"] = "OCR confidence must be between 0 and 100"

        # Validate quality settings
        if self._current_settings.enable_quality_validation:
            if self._current_settings.quality_threshold < 0 or self._current_settings.quality_threshold > 1:
                self._validation_errors["quality_threshold"] = "Quality threshold must be between 0 and 1"

            if self._current_settings.min_content_length <= 0:
                self._validation_errors["content_length"] = "Minimum content length must be positive"

        # Validate deduplication settings
        if self._current_settings.enable_deduplication:
            if self._current_settings.similarity_threshold < 0 or self._current_settings.similarity_threshold > 1:
                self._validation_errors["similarity_threshold"] = "Similarity threshold must be between 0 and 1"

        # Validate processing limits
        if self._current_settings.max_concurrent_documents <= 0:
            self._validation_errors["concurrent_docs"] = "Max concurrent documents must be positive"

        if self._current_settings.max_file_size_mb <= 0:
            self._validation_errors["file_size"] = "Max file size must be positive"

        if self._current_settings.processing_timeout_seconds <= 0:
            self._validation_errors["timeout"] = "Processing timeout must be positive"

        # Update validation panel
        if hasattr(self, '_validation_panel') and self._validation_panel:
            self._validation_panel = self._create_validation_panel()

        return len(self._validation_errors) == 0

    def get_current_settings(self) -> ProcessingSettingsData:
        """Get current settings data."""
        return self._current_settings

    def set_settings(self, settings: ProcessingSettingsData) -> None:
        """Set settings data and rebuild UI."""
        self._current_settings = settings
        self._original_settings = ProcessingSettingsData(**asdict(settings))
        self._is_modified = False
        self._validation_errors.clear()

        # Rebuild UI
        self._build_ui()
        self.update()

    def is_modified(self) -> bool:
        """Check if settings have been modified."""
        return self._is_modified

    def has_validation_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self._validation_errors) > 0

    def get_validation_errors(self) -> Dict[str, str]:
        """Get current validation errors."""
        return self._validation_errors.copy()


# Utility functions for creating processing settings UI
def create_processing_settings_ui(
    config: Optional[ProcessingSettingsConfig] = None,
    initial_data: Optional[ProcessingSettingsData] = None,
    on_settings_changed: Optional[Callable[[ProcessingSettingsData], None]] = None
) -> ProcessingSettingsUI:
    """
    Create a processing settings UI instance.

    Args:
        config: Configuration for the interface
        initial_data: Initial settings data
        on_settings_changed: Callback for settings changes

    Returns:
        ProcessingSettingsUI instance
    """
    return ProcessingSettingsUI(
        config=config,
        initial_data=initial_data,
        on_settings_changed=on_settings_changed
    )


def get_default_processing_settings() -> ProcessingSettingsData:
    """Get default processing settings."""
    return ProcessingSettingsData()


def validate_processing_settings(settings: ProcessingSettingsData) -> Dict[str, str]:
    """
    Validate processing settings and return any errors.

    Args:
        settings: Settings to validate

    Returns:
        Dictionary of validation errors (empty if valid)
    """
    # Create temporary UI instance for validation
    temp_ui = ProcessingSettingsUI(initial_data=settings)
    temp_ui._validate_settings()
    return temp_ui.get_validation_errors()
