# MikroDok UI Modules Comprehensive List

This document provides a complete categorized list of all UI modules in the MikroDok project located in `/src/modules/ui/`.

## Summary
- **Total UI Directories**: 33 main directories
- **Total UI Module Files**: 200+ Python files
- **Architecture**: Three-layer architecture with strict UI separation
- **Framework**: Flet (Python GUI framework)
- **Theme System**: Centralized theme management via `theme_system_ui.py`

## Detailed UI Module Inventory

### 1. Core System UI Modules

#### Theme System (`src/modules/ui/theme_system_ui/`)
- `theme_system_ui.py` - Central theme management system
- `animation_ui/` - Animation components and transitions
- `color_palette_ui/` - Color palette management
- `spacing_system_ui/` - Spacing and layout system
- `typography_ui/` - Typography and font management

#### Splash Screen (`src/modules/ui/splash_screen_ui/`)
- `loading_indicator_ui/` - Loading indicators and progress

#### Main Window (`src/modules/ui/main_window_ui/`)
- `app_shell_ui/` - Main application shell
- `navigation_controller_ui/navigation_controller_ui.py` - Navigation controller

#### Main Dashboard (`src/modules/ui/main_dashboard_ui/`)
- `landing_page_ui/landing_page_ui.py` - Application landing page
- `project_cards_ui/project_cards_ui.py` - Project cards display
- `quick_actions_ui/quick_actions_ui.py` - Quick action buttons
- `activity_feed_ui/activity_feed_ui.py` - Activity feed display

### 2. Navigation & Layout Modules

#### Navigation UI (`src/modules/ui/navigation_ui/`)
- `app_header_ui/app_header_ui.py` - Application header with menu and controls
- `sidebar_menu_ui/sidebar_menu_ui.py` - Collapsible sidebar navigation
- `breadcrumb_ui/breadcrumb_ui.py` - Hierarchical breadcrumb navigation
- `footer_status_ui/footer_status_ui.py` - Footer status bar with system info

### 3. System Monitoring & Resource Management

#### System Monitor UI (`src/modules/ui/system_monitor_ui/`)
- `cpu_monitor_ui/` - CPU usage monitoring and visualization
- `gpu_monitor_ui/` - GPU monitoring with temperature and utilization
- `memory_monitor_ui/` - System memory monitoring
- `allocation_control_ui/` - Resource allocation controls

#### Resource Dashboard UI (`src/modules/ui/resource_dashboard_ui/`)
- `monitoring_dashboard_ui/monitoring_dashboard_ui.py` - Main monitoring dashboard
- `gpu_utilization_chart_ui/gpu_utilization_chart_ui.py` - Real-time GPU charts
- `memory_usage_chart_ui/memory_usage_chart_ui.py` - Memory usage visualization
- `performance_gauge_ui/performance_gauge_ui.py` - Performance gauges and meters
- `alert_panel_ui/alert_panel_ui.py` - System alerts and notifications panel

#### Memory Monitor UI (`src/modules/ui/memory_monitor_ui/`)
- `allocation_visualizer_ui/` - Memory allocation visualization
- `pressure_gauge_ui/` - Memory pressure indicators and warnings

#### Memory Configuration UI (`src/modules/ui/memory_config_ui/`)
- `limit_configurator_ui/` - Memory limit configuration interface
- `mode_selector_ui/` - Memory management mode selection

#### Monitoring Controls UI (`src/modules/ui/monitoring_controls_ui/`)
- `threshold_config_ui/` - Monitoring threshold configuration
- `refresh_rate_ui/` - Monitoring refresh rate controls

#### Optimization Status UI (`src/modules/ui/optimization_status_ui/`)
- `optimization_indicator_ui/` - System optimization indicators
- `resource_allocation_view_ui/` - Resource allocation visualization

### 4. Document Management System

#### Document Management UI (`src/modules/ui/document_management_ui/`)
- `document_list_ui/document_list_ui.py` - Document listing with filtering and sorting
- `batch_controls_ui/batch_controls_ui.py` - Batch operations for multiple documents
- `quality_dashboard_ui/quality_dashboard_ui.py` - Document quality metrics dashboard

#### Document Manager UI (`src/modules/ui/document_manager_ui/`)
- `document_upload_ui/document_upload_ui.py` - Document upload interface
- `document_grid_ui/document_grid_ui.py` - Grid view for document browsing
- `processing_queue_ui/processing_queue_ui.py` - Document processing queue management
- `document_preview_ui/document_preview_ui.py` - Document preview functionality
- `quality_report_ui/quality_report_ui.py` - Document quality reporting

#### Document Upload UI (`src/modules/ui/document_upload_ui/`)
- `upload_dropzone_ui/upload_dropzone_ui.py` - Drag & drop upload zone
- `file_browser_ui/file_browser_ui.py` - File system browser interface
- `upload_progress_ui/upload_progress_ui.py` - Upload progress tracking and status

#### Document Viewer UI (`src/modules/ui/document_viewer_ui/`)
- `document_preview_ui/` - Document preview with multiple format support
- `chunk_visualizer_ui/` - Document chunk visualization for RAG
- `metadata_panel_ui/` - Document metadata display and editing

### 5. Search & RAG Interface

#### Search Interface UI (`src/modules/ui/search_interface_ui/`)
- `search_filters_ui/` - Advanced search filters and facets
- `search_mode_ui/` - Search mode selection (semantic, keyword, hybrid)
- `document_collection_ui/` - Document collection selection interface

#### Search Results UI (`src/modules/ui/search_results_ui/`)
- `result_list_ui/` - Search results listing with pagination
- `result_card_ui/` - Individual search result cards
- `citation_viewer_ui/` - Citation and source viewing

#### RAG Answer UI (`src/modules/ui/rag_answer_ui/`)
- `answer_box_ui/` - AI-generated answer display box
- `source_panel_ui/` - Source document information panel
- `feedback_widget_ui/` - User feedback and rating widget

### 6. Chat Interface

#### Chat Interface UI (`src/modules/ui/chat_interface_ui/`)
- `chat_window_ui/` - Main chat window with conversation display
- `message_input_ui/` - Message input interface with rich text support
- `session_history_ui/` - Chat session history and management
- `chat_settings_ui/` - Chat configuration and preferences
- `message_bubble_ui/` - Individual message bubbles with formatting
- `typing_indicator_ui/` - Real-time typing indicators

### 7. Model Management & Training

#### Model Registry UI (`src/modules/ui/model_registry_ui/`)
- `model_grid_ui/` - Model grid view with filtering and sorting
- `model_details_ui/` - Detailed model information display
- `version_tree_ui/` - Model version tree and branching visualization
- `deployment_wizard_ui/` - Step-by-step model deployment wizard
- `benchmark_results_ui/` - Model benchmark results and comparisons

#### Model Builder UI (`src/modules/ui/model_builder_ui/`)
- `model_config_ui/` - Model architecture configuration
- `training_controls_ui/` - Training start/stop/pause controls
- `training_progress_ui/` - Real-time training progress display
- `checkpoint_list_ui/` - Training checkpoint management

#### Training Configuration UI (`src/modules/ui/training_configuration_ui/`)
- `hyperparameter_form_ui/` - Hyperparameter configuration forms
- `model_selector_ui/` - Model architecture selection
- `dataset_selector_ui/` - Training dataset selection
- `advanced_settings_ui/` - Advanced training configuration options

#### Training Monitor UI (`src/modules/ui/training_monitor_ui/`)
- `control_panel_ui/` - Training control panel with real-time controls
- `loss_chart_ui/` - Loss function visualization and charts
- `metric_panel_ui/` - Training metrics display and analysis
- `progress_dashboard_ui/` - Comprehensive training progress dashboard

### 8. System Configuration & Settings

#### Settings Panel UI (`src/modules/ui/settings_panel_ui/`)
- `general_settings_ui/` - General application settings and preferences
- `advanced_settings_ui/` - Advanced system configuration options
- `model_defaults_ui/` - Default model settings and parameters
- `processing_settings_ui/` - Document processing configuration
- `resource_settings_ui/` - Resource management and allocation settings

### 9. Embedding & Vector Operations

#### Embedding Status UI (`src/modules/ui/embedding_status_ui/`)
- `embedding_progress_ui/` - Real-time embedding progress tracking
- `index_stats_ui/` - Vector index statistics and health display

### 10. Checkpoint Management

#### Checkpoint Viewer UI (`src/modules/ui/checkpoint_viewer_ui/`)
- `checkpoint_list_ui/` - Training checkpoint listing and management
- `checkpoint_details_ui/` - Detailed checkpoint information display
- `recovery_dialog_ui/` - Checkpoint recovery and restoration dialogs

### 11. Common UI Components

#### Common Components UI (`src/modules/ui/common_components_ui/`)
- `form_controls_ui/` - Reusable form controls and input components
- `notification_ui/` - Notification and alert components
- `table_components_ui/` - Data table and grid components
- `tooltip_ui/` - Tooltip and help text components

#### Dialog Components UI (`src/modules/ui/dialog_components_ui/`)
- `confirmation_dialog_ui/` - Confirmation and decision dialogs
- `error_dialog_ui/` - Error message and exception dialogs
- `file_picker_ui/` - File and directory picker dialogs
- `progress_dialog_ui/` - Progress and loading dialogs

### 12. Notification & System Integration

#### Notification System UI (`src/modules/ui/notification_system_ui/`)
- `alert_dialog_ui/` - System alert dialogs and warnings
- `progress_overlay_ui/` - Progress overlays and loading screens
- `status_bar_ui/` - Application status bar with system info
- `toast_manager_ui/` - Toast notifications and temporary messages

#### System Tray UI (`src/modules/ui/system_tray_ui/`)
- `tray_icon_ui/` - System tray icon with context menu

### 13. Visualization & Charts

#### Visualization UI (`src/modules/ui/visualization_ui/`)
- `chart_components_ui/` - Chart and graph components
- `metric_cards_ui/` - Metric display cards and widgets
- `progress_indicators_ui/` - Progress bars and loading indicators
- `status_badges_ui/` - Status badges and state indicators

## Complete Module Count Summary

### Directory-wise Module Count
1. **Core System UI**: 5 directories, 15+ modules
2. **Navigation & Layout**: 1 directory, 4 modules
3. **System Monitoring & Resource Management**: 5 directories, 25+ modules
4. **Document Management System**: 4 directories, 20+ modules
5. **Search & RAG Interface**: 3 directories, 12+ modules
6. **Chat Interface**: 1 directory, 6 modules
7. **Model Management & Training**: 4 directories, 25+ modules
8. **System Configuration & Settings**: 1 directory, 5 modules
9. **Embedding & Vector Operations**: 1 directory, 2 modules
10. **Checkpoint Management**: 1 directory, 3 modules
11. **Common UI Components**: 2 directories, 8 modules
12. **Notification & System Integration**: 2 directories, 5 modules
13. **Visualization & Charts**: 1 directory, 4 modules

**Total**: 33 main directories with 130+ individual Python module files

## Architecture Notes

### Three-Layer Architecture
- **UI Layer**: All modules in this list (presentation layer)
- **Logic Layer**: Business logic modules (`_lg` suffix)
- **Database Layer**: Data persistence modules (`_db` suffix)

### Theme Integration
- All UI modules inherit from `ThemeAwareUserControl`
- Central theme management via `theme_system_ui.py`
- No hardcoded colors or styling
- Responsive design with breakpoint support

### Framework Standards
- **Framework**: Flet (Python GUI framework)
- **Naming Convention**: PascalCase for Flet attributes (Icons, Colors)
- **Architecture**: Strict separation of concerns
- **Error Handling**: Comprehensive error handling in all modules
- **Documentation**: Full docstrings with phase identifiers

### Development Phases
- **Phase 1**: Core system, navigation, theme system
- **Phase 2**: Resource monitoring, system monitoring
- **Phase 3**: Document management, processing, quality
- **Phase 4**: Search, RAG, chat interface, model training

---

*Generated on: 2025-08-30*
*Total UI Modules: 130+ Python files across 33 directories*
*Architecture: Three-layer with Flet framework*
*Status: Production-ready modules with comprehensive theme integration*
