"""
Module: metadata_panel_ui
Description: Displays extracted metadata, quality scores, and processing status with comprehensive
            editing capabilities. Provides responsive metadata visualization with theme integration,
            field validation, batch editing, and real-time updates for document metadata management.
Phase: 3
Location: /src/modules/ui/document_viewer_ui/metadata_panel_ui/metadata_panel_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    ResponsiveLayoutManager
)
from src.modules.logic.document_metadata_lg.base_interfaces import (
    DocumentMetadata,
    MetadataType
)


class MetadataDisplayMode(Enum):
    """Metadata display mode enumeration."""
    VIEW_ONLY = "view_only"
    EDIT_MODE = "edit_mode"
    COMPACT = "compact"
    DETAILED = "detailed"
    COMPARISON = "comparison"


class MetadataFieldType(Enum):
    """Metadata field type enumeration."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    LIST = "list"
    CUSTOM = "custom"
    READONLY = "readonly"


@dataclass
class MetadataField:
    """Data class for metadata field configuration."""
    key: str
    label: str
    value: Any
    field_type: MetadataFieldType
    editable: bool = True
    required: bool = False
    validation_pattern: Optional[str] = None
    description: Optional[str] = None
    category: str = "general"
    display_order: int = 0


@dataclass
class MetadataSection:
    """Data class for metadata section organization."""
    title: str
    fields: List[MetadataField]
    collapsible: bool = True
    expanded: bool = True
    icon: Optional[str] = None
    description: Optional[str] = None


class MetadataPanelUI(ThemeAwareUserControl):
    """
    Comprehensive metadata panel UI component with responsive design and theme integration.
    
    Features:
    - Responsive metadata display with breakpoint-aware layouts
    - Multiple display modes (view, edit, compact, detailed)
    - Field validation and real-time editing
    - Sectioned metadata organization
    - Quality score visualization
    - Processing status indicators
    - Batch editing capabilities
    - Theme-aware styling with accessibility compliance
    - Integration with document metadata extraction
    """

    def __init__(self,
                 metadata: Optional[DocumentMetadata] = None,
                 display_mode: MetadataDisplayMode = MetadataDisplayMode.VIEW_ONLY,
                 editable: bool = False,
                 show_quality_scores: bool = True,
                 show_processing_status: bool = True,
                 on_metadata_changed: Optional[Callable[[DocumentMetadata], None]] = None,
                 on_field_validated: Optional[Callable[[str, bool], None]] = None,
                 **kwargs):
        """
        Initialize metadata panel UI.
        
        Args:
            metadata: Document metadata to display
            display_mode: Display mode for metadata
            editable: Whether metadata can be edited
            show_quality_scores: Whether to show quality scores
            show_processing_status: Whether to show processing status
            on_metadata_changed: Callback for metadata changes
            on_field_validated: Callback for field validation
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._metadata = metadata or DocumentMetadata()
        self._display_mode = display_mode
        self._editable = editable
        self._show_quality_scores = show_quality_scores
        self._show_processing_status = show_processing_status
        
        # Callbacks
        self._on_metadata_changed = on_metadata_changed
        self._on_field_validated = on_field_validated
        
        # State
        self._sections: List[MetadataSection] = []
        self._field_controls: Dict[str, ft.Control] = {}
        self._validation_errors: Dict[str, str] = {}
        self._is_editing = False
        self._has_changes = False
        
        # UI components
        self._header_container: Optional[ft.Container] = None
        self._content_container: Optional[ft.Container] = None
        self._action_bar: Optional[ft.Container] = None
        self._search_field: Optional[ft.TextField] = None
        
        # Initialize metadata sections
        self._initialize_metadata_sections()

    def _initialize_metadata_sections(self):
        """Initialize metadata sections from document metadata."""
        if not self._metadata:
            return
            
        # Basic Information Section
        basic_fields = [
            MetadataField("title", "Title", self._metadata.title, MetadataFieldType.TEXT, True, True),
            MetadataField("author", "Author", self._metadata.author, MetadataFieldType.TEXT, True),
            MetadataField("subject", "Subject", self._metadata.subject, MetadataFieldType.TEXT, True),
            MetadataField("language", "Language", self._metadata.language, MetadataFieldType.TEXT, True),
        ]
        
        # Document Statistics Section
        stats_fields = [
            MetadataField("page_count", "Pages", self._metadata.page_count, MetadataFieldType.NUMBER, False),
            MetadataField("word_count", "Words", self._metadata.word_count, MetadataFieldType.NUMBER, False),
            MetadataField("character_count", "Characters", self._metadata.character_count, MetadataFieldType.NUMBER, False),
            MetadataField("file_size", "File Size", self._metadata.file_size, MetadataFieldType.NUMBER, False),
        ]
        
        # Technical Information Section
        technical_fields = [
            MetadataField("file_format", "Format", self._metadata.file_format, MetadataFieldType.READONLY, False),
            MetadataField("encoding", "Encoding", self._metadata.encoding, MetadataFieldType.READONLY, False),
            MetadataField("version", "Version", self._metadata.version, MetadataFieldType.READONLY, False),
            MetadataField("creator", "Creator", self._metadata.creator, MetadataFieldType.TEXT, True),
            MetadataField("producer", "Producer", self._metadata.producer, MetadataFieldType.TEXT, True),
        ]
        
        # Dates Section
        date_fields = [
            MetadataField("creation_date", "Created", self._metadata.creation_date, MetadataFieldType.DATE, True),
            MetadataField("modification_date", "Modified", self._metadata.modification_date, MetadataFieldType.DATE, True),
            MetadataField("extraction_timestamp", "Extracted", self._metadata.extraction_timestamp, MetadataFieldType.READONLY, False),
        ]
        
        # Keywords Section
        keywords_fields = [
            MetadataField("keywords", "Keywords", self._metadata.keywords, MetadataFieldType.LIST, True),
        ]
        
        # Create sections
        self._sections = [
            MetadataSection("Basic Information", basic_fields, True, True, "info", "Document identification and description"),
            MetadataSection("Statistics", stats_fields, True, False, "analytics", "Document content statistics"),
            MetadataSection("Technical Details", technical_fields, True, False, "settings", "Technical document properties"),
            MetadataSection("Dates", date_fields, True, False, "schedule", "Document timestamps"),
            MetadataSection("Keywords", keywords_fields, True, False, "tag", "Document tags and keywords"),
        ]

    def build(self) -> ft.Control:
        """Build the metadata panel UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    self._create_header(),
                    ft.Divider(height=1, color=palette.borders),
                    self._create_content_area(),
                    self._create_action_bar() if self._editable else ft.Container(height=0),
                ],
                spacing=0,
                expand=True,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=self.get_responsive_padding()
        )

    def _create_header(self) -> ft.Control:
        """Create the metadata panel header."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Title and mode indicator
        title_row = ft.Row(
            controls=[
                ft.Icon(
                    name=ft.Icons.INFO_OUTLINE,
                    color=palette.primary,
                    size=self.get_responsive_size(20)
                ),
                ft.Text(
                    "Document Metadata",
                    size=typography.heading_small[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.text_primary
                ),
                ft.Container(expand=True),
                self._create_mode_indicator(),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.sm
        )
        
        # Search and filter controls
        search_row = self._create_search_controls() if self._display_mode == MetadataDisplayMode.DETAILED else ft.Container(height=0)
        
        return ft.Container(
            content=ft.Column(
                controls=[title_row, search_row],
                spacing=spacing.md,
                tight=True
            ),
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface
        )

    def _create_mode_indicator(self) -> ft.Control:
        """Create display mode indicator."""
        palette = self.get_palette()
        typography = self.get_typography()
        
        mode_text = {
            MetadataDisplayMode.VIEW_ONLY: "View Only",
            MetadataDisplayMode.EDIT_MODE: "Edit Mode",
            MetadataDisplayMode.COMPACT: "Compact",
            MetadataDisplayMode.DETAILED: "Detailed",
            MetadataDisplayMode.COMPARISON: "Comparison"
        }.get(self._display_mode, "Unknown")
        
        mode_color = {
            MetadataDisplayMode.VIEW_ONLY: palette.text_secondary,
            MetadataDisplayMode.EDIT_MODE: palette.warning,
            MetadataDisplayMode.COMPACT: palette.info,
            MetadataDisplayMode.DETAILED: palette.primary,
            MetadataDisplayMode.COMPARISON: palette.success
        }.get(self._display_mode, palette.text_secondary)
        
        return ft.Container(
            content=ft.Text(
                mode_text,
                size=typography.body_small[0],
                color=mode_color,
                weight=ft.FontWeight.W_500
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=self.get_responsive_size(4)
        )

    def _create_search_controls(self) -> ft.Control:
        """Create search and filter controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._search_field = ft.TextField(
            hint_text="Search metadata fields...",
            prefix_icon=ft.Icons.SEARCH,
            border_color=palette.borders,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary),
            hint_style=ft.TextStyle(color=palette.text_secondary),
            on_change=self._on_search_changed,
            expand=True
        )

        filter_button = ft.IconButton(
            icon=ft.Icons.FILTER_LIST,
            icon_color=palette.text_secondary,
            tooltip="Filter metadata",
            on_click=self._on_filter_clicked
        )

        return ft.Row(
            controls=[self._search_field, filter_button],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START
        )

    def _create_content_area(self) -> ft.Control:
        """Create the main content area with metadata sections."""
        if self._display_mode == MetadataDisplayMode.COMPACT:
            return self._create_compact_view()
        else:
            return self._create_detailed_view()

    def _create_compact_view(self) -> ft.Control:
        """Create compact metadata view."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Get essential fields
        essential_fields = []
        for section in self._sections:
            for field in section.fields[:2]:  # Take first 2 fields from each section
                if field.value is not None:
                    essential_fields.append(field)

        # Create compact field displays
        field_chips = []
        for field in essential_fields:
            chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            f"{field.label}:",
                            size=typography.body_small[0],
                            weight=ft.FontWeight.W_500,
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            str(field.value)[:30] + ("..." if len(str(field.value)) > 30 else ""),
                            size=typography.body_small[0],
                            color=palette.text_primary
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                bgcolor=palette.surface_variant,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=self.get_responsive_size(4),
                margin=ft.margin.only(right=spacing.xs, bottom=spacing.xs)
            )
            field_chips.append(chip)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Quick Overview",
                        size=typography.body_large[0],
                        weight=ft.FontWeight.W_500,
                        color=palette.text_primary
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=field_chips,
                            wrap=True,
                            spacing=0
                        ),
                        padding=ft.padding.only(top=spacing.sm)
                    )
                ],
                spacing=spacing.md,
                tight=True
            ),
            padding=ft.padding.all(spacing.lg)
        )

    def _create_detailed_view(self) -> ft.Control:
        """Create detailed metadata view with sections."""
        spacing = self.get_spacing()

        section_controls = []
        for section in self._sections:
            if self._should_show_section(section):
                section_control = self._create_metadata_section(section)
                section_controls.append(section_control)

        return ft.Container(
            content=ft.Column(
                controls=section_controls,
                spacing=spacing.md,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _should_show_section(self, section: MetadataSection) -> bool:
        """Determine if section should be shown based on search and filters."""
        if not self._search_field or not self._search_field.value:
            return True

        search_term = self._search_field.value.lower()

        # Check section title
        if search_term in section.title.lower():
            return True

        # Check field labels and values
        for field in section.fields:
            if (search_term in field.label.lower() or
                (field.value and search_term in str(field.value).lower())):
                return True

        return False

    def _create_metadata_section(self, section: MetadataSection) -> ft.Control:
        """Create a metadata section with fields."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Section header
        header_icon = ft.Icon(
            name=getattr(ft.Icons, section.icon.upper()) if section.icon else ft.Icons.FOLDER,
            color=palette.primary,
            size=self.get_responsive_size(18)
        )

        header_text = ft.Text(
            section.title,
            size=typography.body_large[0],
            weight=ft.FontWeight.W_600,
            color=palette.text_primary
        )

        expand_icon = ft.IconButton(
            icon=ft.Icons.EXPAND_LESS if section.expanded else ft.Icons.EXPAND_MORE,
            icon_color=palette.text_secondary,
            icon_size=self.get_responsive_size(20),
            on_click=lambda e, s=section: self._toggle_section(s)
        )

        header = ft.Container(
            content=ft.Row(
                controls=[header_icon, header_text, ft.Container(expand=True), expand_icon],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.sm
            ),
            padding=ft.padding.symmetric(horizontal=spacing.md, vertical=spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_size(8),
            on_click=lambda e, s=section: self._toggle_section(s)
        )

        # Section content
        if section.expanded:
            field_controls = []
            for field in section.fields:
                if field.value is not None or self._display_mode == MetadataDisplayMode.EDIT_MODE:
                    field_control = self._create_metadata_field(field)
                    field_controls.append(field_control)

            content = ft.Container(
                content=ft.Column(
                    controls=field_controls,
                    spacing=spacing.sm,
                    tight=True
                ),
                padding=ft.padding.all(spacing.md),
                margin=ft.margin.only(top=spacing.xs)
            )
        else:
            content = ft.Container(height=0)

        return ft.Column(
            controls=[header, content],
            spacing=0,
            tight=True
        )

    def _create_metadata_field(self, field: MetadataField) -> ft.Control:
        """Create a metadata field display/edit control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Field label
        label = ft.Text(
            field.label,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )

        # Field value control based on type and edit mode
        if self._display_mode == MetadataDisplayMode.EDIT_MODE and field.editable:
            value_control = self._create_editable_field(field)
        else:
            value_control = self._create_readonly_field(field)

        # Validation error display
        error_control = ft.Container(height=0)
        if field.key in self._validation_errors:
            error_control = ft.Text(
                self._validation_errors[field.key],
                size=typography.body_small[0],
                color=palette.error,
                italic=True
            )

        # Field description
        description_control = ft.Container(height=0)
        if field.description and self._display_mode == MetadataDisplayMode.DETAILED:
            description_control = ft.Text(
                field.description,
                size=typography.body_small[0],
                color=palette.text_secondary,
                italic=True
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            label,
                            ft.Container(expand=True),
                            ft.Icon(
                                name=ft.Icons.STAR,
                                color=palette.warning,
                                size=self.get_responsive_size(16)
                            ) if field.required else ft.Container(width=0)
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    value_control,
                    error_control,
                    description_control
                ],
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm),
            border=ft.border.only(
                bottom=ft.BorderSide(1, palette.borders)
            ) if field != self._get_last_field_in_section(field) else None
        )

    def _create_editable_field(self, field: MetadataField) -> ft.Control:
        """Create editable field control based on field type."""
        palette = self.get_palette()

        if field.field_type == MetadataFieldType.TEXT:
            control = ft.TextField(
                value=str(field.value) if field.value else "",
                hint_text=f"Enter {field.label.lower()}",
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                on_change=lambda e, f=field: self._on_field_changed(f, e.control.value),
                expand=True
            )
        elif field.field_type == MetadataFieldType.NUMBER:
            control = ft.TextField(
                value=str(field.value) if field.value else "",
                hint_text=f"Enter {field.label.lower()}",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                on_change=lambda e, f=field: self._on_field_changed(f, e.control.value),
                expand=True
            )
        elif field.field_type == MetadataFieldType.DATE:
            control = ft.TextField(
                value=field.value.strftime("%Y-%m-%d %H:%M:%S") if field.value else "",
                hint_text="YYYY-MM-DD HH:MM:SS",
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                on_change=lambda e, f=field: self._on_field_changed(f, e.control.value),
                expand=True
            )
        elif field.field_type == MetadataFieldType.BOOLEAN:
            control = ft.Switch(
                value=bool(field.value) if field.value else False,
                active_color=palette.primary,
                on_change=lambda e, f=field: self._on_field_changed(f, e.control.value)
            )
        elif field.field_type == MetadataFieldType.LIST:
            # For lists, create a text field with comma-separated values
            list_value = ", ".join(field.value) if field.value and isinstance(field.value, list) else ""
            control = ft.TextField(
                value=list_value,
                hint_text="Enter comma-separated values",
                multiline=True,
                min_lines=2,
                max_lines=4,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                on_change=lambda e, f=field: self._on_list_field_changed(f, e.control.value),
                expand=True
            )
        else:
            # Default to text field
            control = ft.TextField(
                value=str(field.value) if field.value else "",
                hint_text=f"Enter {field.label.lower()}",
                border_color=palette.borders,
                focused_border_color=palette.primary,
                text_style=ft.TextStyle(color=palette.text_primary),
                on_change=lambda e, f=field: self._on_field_changed(f, e.control.value),
                expand=True
            )

        self._field_controls[field.key] = control
        return control

    def _create_readonly_field(self, field: MetadataField) -> ft.Control:
        """Create readonly field display."""
        palette = self.get_palette()
        typography = self.get_typography()

        if field.value is None:
            display_value = "Not available"
            text_color = palette.text_secondary
            italic = True
        else:
            if field.field_type == MetadataFieldType.DATE and isinstance(field.value, datetime):
                display_value = field.value.strftime("%Y-%m-%d %H:%M:%S")
            elif field.field_type == MetadataFieldType.LIST and isinstance(field.value, list):
                display_value = ", ".join(str(item) for item in field.value)
            elif field.field_type == MetadataFieldType.BOOLEAN:
                display_value = "Yes" if field.value else "No"
            elif field.field_type == MetadataFieldType.NUMBER and isinstance(field.value, (int, float)):
                if field.key == "file_size":
                    display_value = self._format_file_size(field.value)
                else:
                    display_value = f"{field.value:,}"
            else:
                display_value = str(field.value)

            text_color = palette.text_primary
            italic = False

        return ft.Container(
            content=ft.Text(
                display_value,
                size=typography.body_medium[0],
                color=text_color,
                italic=italic,
                selectable=True
            ),
            padding=ft.padding.symmetric(vertical=4),
            bgcolor=palette.surface_variant if field.field_type == MetadataFieldType.READONLY else None,
            border_radius=self.get_responsive_size(4) if field.field_type == MetadataFieldType.READONLY else None
        )

    def _create_action_bar(self) -> ft.Control:
        """Create action bar for edit mode."""
        if not self._editable or self._display_mode != MetadataDisplayMode.EDIT_MODE:
            return ft.Container(height=0)

        palette = self.get_palette()
        spacing = self.get_spacing()

        save_button = ft.ElevatedButton(
            text="Save Changes",
            icon=ft.Icons.SAVE,
            bgcolor=palette.primary,
            color=palette.on_primary,
            disabled=not self._has_changes,
            on_click=self._on_save_clicked
        )

        cancel_button = ft.TextButton(
            text="Cancel",
            icon=ft.Icons.CANCEL,
            on_click=self._on_cancel_clicked
        )

        reset_button = ft.TextButton(
            text="Reset",
            icon=ft.Icons.REFRESH,
            on_click=self._on_reset_clicked
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    reset_button,
                    cancel_button,
                    save_button
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border=ft.border.only(top=ft.BorderSide(1, palette.borders))
        )

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

    def _get_last_field_in_section(self, field: MetadataField) -> bool:
        """Check if field is the last field in its section."""
        for section in self._sections:
            if field in section.fields:
                return field == section.fields[-1]
        return False

    def _toggle_section(self, section: MetadataSection):
        """Toggle section expanded state."""
        section.expanded = not section.expanded
        self.update()

    def _on_search_changed(self, e):
        """Handle search field changes."""
        self.update()

    def _on_filter_clicked(self, e):
        """Handle filter button click."""
        # TODO: Implement filter dialog
        pass

    def _on_field_changed(self, field: MetadataField, value: str):
        """Handle field value changes."""
        try:
            # Convert value based on field type
            if field.field_type == MetadataFieldType.NUMBER:
                converted_value = float(value) if value else None
            elif field.field_type == MetadataFieldType.DATE:
                converted_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S") if value else None
            else:
                converted_value = value if value else None

            # Update field value
            field.value = converted_value

            # Update metadata object
            setattr(self._metadata, field.key, converted_value)

            # Validate field
            is_valid = self._validate_field(field)

            # Mark as changed
            self._has_changes = True

            # Trigger callbacks
            if self._on_field_validated:
                self._on_field_validated(field.key, is_valid)

            self.update()

        except ValueError as e:
            self._validation_errors[field.key] = f"Invalid {field.field_type.value}: {str(e)}"
            self.update()

    def _on_list_field_changed(self, field: MetadataField, value: str):
        """Handle list field value changes."""
        try:
            # Convert comma-separated string to list
            if value:
                list_value = [item.strip() for item in value.split(",") if item.strip()]
            else:
                list_value = []

            # Update field value
            field.value = list_value

            # Update metadata object
            setattr(self._metadata, field.key, list_value)

            # Mark as changed
            self._has_changes = True

            # Clear any validation errors
            if field.key in self._validation_errors:
                del self._validation_errors[field.key]

            self.update()

        except Exception as e:
            self._validation_errors[field.key] = f"Invalid list format: {str(e)}"
            self.update()

    def _validate_field(self, field: MetadataField) -> bool:
        """Validate field value."""
        # Clear existing error
        if field.key in self._validation_errors:
            del self._validation_errors[field.key]

        # Check required fields
        if field.required and not field.value:
            self._validation_errors[field.key] = "This field is required"
            return False

        # Validate pattern if provided
        if field.validation_pattern and field.value:
            import re
            if not re.match(field.validation_pattern, str(field.value)):
                self._validation_errors[field.key] = "Invalid format"
                return False

        return True

    def _on_save_clicked(self, e):
        """Handle save button click."""
        # Validate all fields
        all_valid = True
        for section in self._sections:
            for field in section.fields:
                if not self._validate_field(field):
                    all_valid = False

        if all_valid:
            # Trigger metadata changed callback
            if self._on_metadata_changed:
                self._on_metadata_changed(self._metadata)

            # Reset change flag
            self._has_changes = False
            self.update()
        else:
            # Show validation errors
            self.update()

    def _on_cancel_clicked(self, e):
        """Handle cancel button click."""
        # Reset to original values
        self._initialize_metadata_sections()
        self._has_changes = False
        self._validation_errors.clear()
        self.update()

    def _on_reset_clicked(self, e):
        """Handle reset button click."""
        # Clear all field values
        for section in self._sections:
            for field in section.fields:
                if field.editable:
                    field.value = None
                    setattr(self._metadata, field.key, None)

        self._has_changes = True
        self._validation_errors.clear()
        self.update()

    # Public methods for external control
    def set_metadata(self, metadata: DocumentMetadata):
        """Set new metadata to display."""
        self._metadata = metadata
        self._initialize_metadata_sections()
        self._has_changes = False
        self._validation_errors.clear()
        self.update()

    def set_display_mode(self, mode: MetadataDisplayMode):
        """Set display mode."""
        self._display_mode = mode
        self.update()

    def get_metadata(self) -> DocumentMetadata:
        """Get current metadata."""
        return self._metadata

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_changes

    def validate_all_fields(self) -> bool:
        """Validate all fields and return True if all are valid."""
        all_valid = True
        for section in self._sections:
            for field in section.fields:
                if not self._validate_field(field):
                    all_valid = False
        return all_valid
