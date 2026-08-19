MikroDok Modular Architecture - Executive Summary and Overview
Executive Summary
MikroDok's modular architecture implements a three-layer separation pattern designed to support enterprise-grade machine learning operations on desktop hardware. The architecture prioritizes offline-first functionality, resource efficiency, and maintainability while handling complex operations like 12-24 hour model training sessions and real-time memory bridging across GPU/CPU/NVMe storage tiers.
Key Architectural Decisions
1. Three-Layer Architecture Pattern
•	Logic Layer (_lg): Pure business logic, algorithms, and workflows isolated from UI and persistence concerns
•	UI Layer (_ui): Flet-based frontend components with reactive state management and async communication
•	Database Layer (_db): SQLite-optimized data access with separate concerns for metadata and binary storage
2. Domain-Driven Design Approach
•	Bounded contexts for major domains: Training, Document Processing, Resource Management, and Model Deployment
•	Aggregate roots managing consistency boundaries within each domain
•	Clear separation between core domain logic and infrastructure concerns
3. Event-Driven Communication
•	Asynchronous message bus for UI-Backend communication to maintain responsiveness during long operations
•	Event sourcing for training session state management and recovery
•	Observer pattern for real-time resource monitoring updates
4. Resource-Aware Architecture
•	Dedicated modules for IDRAlloc memory management system
•	Separate monitoring and optimization trigger modules
•	Thread pool management with operation-specific allocations
Design Principles
SOLID Compliance
•	Single Responsibility: Each module handles one specific aspect of functionality
•	Open/Closed: Extension points for future features (cloud sync, multi-user support)
•	Liskov Substitution: Interface-based design for swappable implementations
•	Interface Segregation: Focused interfaces for different consumer needs
•	Dependency Inversion: Core logic depends on abstractions, not concrete implementations
Additional Principles
•	Offline-First: All core functionality operates without internet connectivity
•	Progressive Disclosure: Complex features hidden behind simple interfaces
•	Fail-Safe Defaults: Graceful degradation when resources are constrained
•	Immutable State: Training configurations and model metadata are immutable once created
Module Organization Strategy
Hierarchical Structure
/src/modules/
├── logic/          # Business logic and algorithms
├── ui/             # User interface components
├── database/       # Data persistence and access
└── infrastructure/ # Cross-cutting concerns
Module Naming Conventions
•	Descriptive names indicating primary responsibility
•	Consistent suffixing: _lg (logic), _ui (UI), _db (database)
•	Submodule names reflect specific functionality within parent module
Dependency Rules
1.	UI modules depend on Logic modules (never reverse)
2.	Database modules are accessed only through Logic layer repositories
3.	Infrastructure modules can be used by all layers
4.	No circular dependencies between modules at any level
Core Architectural Components
1. Application Core
•	Lifecycle management for initialization and shutdown
•	Central configuration management
•	State persistence and recovery mechanisms
2. Processing Pipeline
•	Document ingestion with format detection
•	Parallel processing with thread pool management
•	Quality validation and error recovery
3. Training Orchestration
•	Session management with pause/resume capability
•	Checkpoint coordination with atomic operations
•	Resource allocation through IDRAlloc
4. Memory Management (IDRAlloc)
•	Three-tier memory hierarchy (GPU VRAM, System RAM, NVMe)
•	Dynamic layer distribution based on access patterns
•	Predictive preloading and eviction strategies
5. User Experience Layer
•	Responsive UI during long-running operations
•	Real-time monitoring dashboards
•	Progressive workflow guidance
6. Data Persistence
•	Hybrid storage strategy (SQLite for metadata, filesystem for models)
•	Optimized indexing for ML workloads
•	Transaction management for training operations
Extensibility Considerations
Future-Ready Design
•	Plugin architecture preparation for custom processors
•	API gateway pattern for potential cloud integration
•	Multi-tenant isolation boundaries for future multi-user support
•	Modular authentication/authorization hooks
Performance Optimization Points
•	Caching layers at module boundaries
•	Lazy loading for resource-intensive operations
•	Batch processing interfaces for bulk operations
•	Profiling hooks for performance monitoring
Quality Attributes Addressed
Reliability
•	Comprehensive error handling at module boundaries
•	Automatic recovery mechanisms for training failures
•	Data integrity through transactional boundaries
Performance
•	Asynchronous operations for UI responsiveness
•	Resource pooling for efficient memory usage
•	Optimized data structures for ML workloads
Maintainability
•	Clear module boundaries reducing coupling
•	Consistent patterns across similar modules
•	Comprehensive logging and monitoring interfaces
Security
•	Offline-first design eliminating attack vectors
•	Encryption interfaces for sensitive model data
•	Audit trail capabilities for compliance
X
Core System Modules
Foundation modules for application lifecycle, configuration management, and system initialization.
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
application_lifecycle_lg	startup_manager_lg	Orchestrates application initialization sequence including hardware detection, service startup, and dependency resolution	/src/modules/logic/application_lifecycle_lg/startup_manager_lg/
application_lifecycle_lg	shutdown_handler_lg	Manages graceful shutdown procedures, saves application state, and ensures proper resource cleanup	/src/modules/logic/application_lifecycle_lg/shutdown_handler_lg/
application_lifecycle_lg	crash_recovery_lg	Handles unexpected terminations, creates recovery checkpoints, and restores application state after crashes	/src/modules/logic/application_lifecycle_lg/crash_recovery_lg/
state_management_lg	app_state_manager_lg	Maintains global application state, manages state transitions, and ensures state consistency across modules	/src/modules/logic/state_management_lg/app_state_manager_lg/
state_management_lg	state_persistence_lg	Handles state serialization, auto-save functionality, and state recovery from persistent storage	/src/modules/logic/state_management_lg/state_persistence_lg/
configuration_manager_lg	config_loader_lg	Loads and validates application configuration from multiple sources with environment-specific overrides	/src/modules/logic/configuration_manager_lg/config_loader_lg/
configuration_manager_lg	settings_validator_lg	Validates user settings against schema, ensures configuration integrity, and provides default values	/src/modules/logic/configuration_manager_lg/settings_validator_lg/
event_bus_lg	message_dispatcher_lg	Routes messages between application components using publish-subscribe pattern for loose coupling	/src/modules/logic/event_bus_lg/message_dispatcher_lg/
event_bus_lg	event_aggregator_lg	Collects and batches events for efficient processing, manages event priorities and delivery guarantees	/src/modules/logic/event_bus_lg/event_aggregator_lg/
thread_coordination_lg	thread_pool_manager_lg	Manages application-wide thread pools for different operation types with priority-based scheduling	/src/modules/logic/thread_coordination_lg/thread_pool_manager_lg/
thread_coordination_lg	lock_manager_lg	Coordinates thread-safe access to shared resources, prevents deadlocks, and manages resource locks	/src/modules/logic/thread_coordination_lg/lock_manager_lg/
async_operations_lg	task_scheduler_lg	Schedules and manages asynchronous operations with dependency tracking and priority execution	/src/modules/logic/async_operations_lg/task_scheduler_lg/
async_operations_lg	callback_manager_lg	Handles completion callbacks, error handlers, and progress notifications for long-running operations	/src/modules/logic/async_operations_lg/callback_manager_lg/
system_requirements_lg	hardware_validator_lg	Validates system hardware meets minimum requirements, detects GPU capabilities and available resources	/src/modules/logic/system_requirements_lg/hardware_validator_lg/
system_requirements_lg	dependency_checker_lg	Verifies required software dependencies, CUDA drivers, and system libraries are properly installed	/src/modules/logic/system_requirements_lg/dependency_checker_lg/
main_window_ui	app_shell_ui	Primary application window container with title bar, menu system, and layout management	/src/modules/ui/main_window_ui/app_shell_ui/
main_window_ui	navigation_controller_ui	Manages navigation between different application views and maintains navigation history	/src/modules/ui/main_window_ui/navigation_controller_ui/
splash_screen_ui	loading_indicator_ui	Displays startup progress, system checks status, and initialization messages during launch	/src/modules/ui/splash_screen_ui/loading_indicator_ui/
system_tray_ui	tray_icon_ui	System tray integration for minimized operation, quick access menu, and status notifications	/src/modules/ui/system_tray_ui/tray_icon_ui/
app_state_db	state_snapshots_db	Stores application state snapshots for recovery, maintains state history with timestamps	/src/modules/database/app_state_db/state_snapshots_db/
app_state_db	user_preferences_db	Persists user preferences, window layouts, and application settings across sessions	/src/modules/database/app_state_db/user_preferences_db/
system_config_db	config_storage_db	Stores system configuration, feature flags, and environment-specific settings	/src/modules/database/system_config_db/config_storage_db/
system_config_db	config_versions_db	Tracks configuration changes, maintains version history, and enables rollback capabilities	/src/modules/database/system_config_db/config_versions_db/
X
Document Processing Modules
Overview
Document processing modules handle the complete pipeline from document upload to training-ready data. These modules support multiple formats (PDF, DOCX, TXT, HTML, Markdown) and include advanced features like OCR, semantic chunking, and quality validation.
Module Structure
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
document_ingestion_lg	format_detector_lg	Identifies document format through file extension and magic number verification, routes to appropriate processor	/src/modules/logic/document_ingestion_lg/format_detector_lg/
document_ingestion_lg	file_validator_lg	Validates file integrity, size limits (10GB max), and format compatibility before processing	/src/modules/logic/document_ingestion_lg/file_validator_lg/
document_ingestion_lg	batch_processor_lg	Manages parallel processing of multiple documents with priority queuing and resource allocation	/src/modules/logic/document_ingestion_lg/batch_processor_lg/
document_extraction_lg	pdf_extractor_lg	Extracts text, tables, and metadata from PDF documents using PDFPlumber integration	/src/modules/logic/document_extraction_lg/pdf_extractor_lg/
document_extraction_lg	docx_extractor_lg	Processes Word documents preserving formatting and structure using python-docx	/src/modules/logic/document_extraction_lg/docx_extractor_lg/
document_extraction_lg	html_extractor_lg	Parses HTML content while maintaining semantic structure using BeautifulSoup	/src/modules/logic/document_extraction_lg/html_extractor_lg/
document_extraction_lg	markdown_extractor_lg	Processes Markdown files preserving formatting and code blocks	/src/modules/logic/document_extraction_lg/markdown_extractor_lg/
document_extraction_lg	ocr_processor_lg	Performs optical character recognition on images and scanned documents using Tesseract	/src/modules/logic/document_extraction_lg/ocr_processor_lg/
document_chunking_lg	semantic_chunker_lg	Splits documents into semantically coherent chunks (512-1024 tokens) preserving context	/src/modules/logic/document_chunking_lg/semantic_chunker_lg/
document_chunking_lg	overlap_manager_lg	Manages chunk overlap strategies to maintain context continuity between segments	/src/modules/logic/document_chunking_lg/overlap_manager_lg/
document_chunking_lg	chunk_validator_lg	Validates chunk boundaries, token counts, and semantic completeness	/src/modules/logic/document_chunking_lg/chunk_validator_lg/
document_quality_lg	content_analyzer_lg	Evaluates text coherence, completeness, and extraction accuracy	/src/modules/logic/document_quality_lg/content_analyzer_lg/
document_quality_lg	deduplication_engine_lg	Identifies and handles duplicate content using SHA-256 hashing and semantic similarity	/src/modules/logic/document_quality_lg/deduplication_engine_lg/
document_quality_lg	quality_scorer_lg	Calculates overall document quality scores (0-100) based on multiple metrics	/src/modules/logic/document_quality_lg/quality_scorer_lg/
document_metadata_lg	metadata_extractor_lg	Extracts document properties including author, creation date, and custom metadata	/src/modules/logic/document_metadata_lg/metadata_extractor_lg/
document_metadata_lg	structure_analyzer_lg	Analyzes document structure including headers, sections, and hierarchical organization	/src/modules/logic/document_metadata_lg/structure_analyzer_lg/
document_upload_ui	upload_dropzone_ui	Drag-and-drop interface for document upload with visual feedback and progress indicators	/src/modules/ui/document_upload_ui/upload_dropzone_ui/
document_upload_ui	file_browser_ui	File selection dialog with format filtering and multi-select capabilities	/src/modules/ui/document_upload_ui/file_browser_ui/
document_upload_ui	upload_progress_ui	Real-time upload progress visualization with pause/resume functionality	/src/modules/ui/document_upload_ui/upload_progress_ui/
document_viewer_ui	document_preview_ui	Displays document content with syntax highlighting and formatting preservation	/src/modules/ui/document_viewer_ui/document_preview_ui/
document_viewer_ui	chunk_visualizer_ui	Shows document chunks with boundaries, overlap regions, and token counts	/src/modules/ui/document_viewer_ui/chunk_visualizer_ui/
document_viewer_ui	metadata_panel_ui	Displays extracted metadata, quality scores, and processing status	/src/modules/ui/document_viewer_ui/metadata_panel_ui/
document_management_ui	document_list_ui	Grid/list view of processed documents with sorting, filtering, and search capabilities	/src/modules/ui/document_management_ui/document_list_ui/
document_management_ui	batch_controls_ui	Interface for batch operations including select all, bulk delete, and reprocess	/src/modules/ui/document_management_ui/batch_controls_ui/
document_management_ui	quality_dashboard_ui	Visualizes document quality metrics, processing statistics, and error reports	/src/modules/ui/document_management_ui/quality_dashboard_ui/
documents_db	document_repository_db	Data access layer for document CRUD operations with transaction support	/src/modules/database/documents_db/document_repository_db/
documents_db	document_chunks_db	Manages storage and retrieval of processed text chunks with indexing	/src/modules/database/documents_db/document_chunks_db/
documents_db	extraction_results_db	Stores structured extraction results including tables, images, and metadata	/src/modules/database/documents_db/extraction_results_db/
document_collections_db	collection_manager_db	Handles document collection organization and hierarchical grouping	/src/modules/database/document_collections_db/collection_manager_db/
document_collections_db	collection_metadata_db	Stores collection-level settings, tags, and aggregated statistics	/src/modules/database/document_collections_db/collection_metadata_db/
document_queue_db	processing_queue_db	Manages document processing queue with priority and retry mechanisms	/src/modules/database/document_queue_db/processing_queue_db/
document_queue_db	queue_status_db	Tracks processing status, error logs, and retry attempts	/src/modules/database/document_queue_db/queue_status_db/
document_quality_db	quality_metrics_db	Persists document quality scores, validation results, and assessment history	/src/modules/database/document_quality_db/quality_metrics_db/
document_quality_db	deduplication_cache_db	Maintains hash index for duplicate detection across document collections	/src/modules/database/document_quality_db/deduplication_cache_db/
Key Design Considerations
1.	Separation of Concerns: Each module handles a specific aspect of document processing with clear interfaces
2.	Extensibility: New document formats can be added by implementing format-specific extractor submodules
3.	Performance: Batch processing and parallel execution support for handling large document collections
4.	Quality Assurance: Comprehensive validation and quality scoring at each processing stage
5.	Error Recovery: Robust error handling with retry mechanisms and partial result preservation
X
Model Training Modules - MikroDok Architecture
Overview
This section defines the modular structure for all model training-related functionality in MikroDok, including training orchestration, checkpoint management, and session handling. The modules support long-running training operations (12-24 hours) with pause/resume capabilities and comprehensive progress tracking.
Module Structure
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
training_orchestration_lg		Master module coordinating all training operations and workflows	/src/modules/logic/training_orchestration_lg/
training_orchestration_lg	session_manager_lg	Manages training session lifecycle including creation, execution, pause, resume, and termination	/src/modules/logic/training_orchestration_lg/session_manager_lg/
training_orchestration_lg	training_executor_lg	Executes the core training loop with epoch management and batch processing	/src/modules/logic/training_orchestration_lg/training_executor_lg/
training_orchestration_lg	hyperparameter_manager_lg	Manages training hyperparameters including learning rate, batch size, and optimizer settings	/src/modules/logic/training_orchestration_lg/hyperparameter_manager_lg/
training_orchestration_lg	training_scheduler_lg	Schedules and queues training jobs with priority management	/src/modules/logic/training_orchestration_lg/training_scheduler_lg/
checkpoint_management_lg		Handles all checkpoint-related operations for model state preservation	/src/modules/logic/checkpoint_management_lg/
checkpoint_management_lg	checkpoint_creator_lg	Creates and saves model checkpoints with state serialization	/src/modules/logic/checkpoint_management_lg/checkpoint_creator_lg/
checkpoint_management_lg	checkpoint_validator_lg	Validates checkpoint integrity using checksums and state verification	/src/modules/logic/checkpoint_management_lg/checkpoint_validator_lg/
checkpoint_management_lg	checkpoint_recovery_lg	Recovers training from checkpoints after interruptions or failures	/src/modules/logic/checkpoint_management_lg/checkpoint_recovery_lg/
checkpoint_management_lg	checkpoint_cleaner_lg	Manages checkpoint retention policies and cleanup of old checkpoints	/src/modules/logic/checkpoint_management_lg/checkpoint_cleaner_lg/
training_metrics_lg		Processes and analyzes training performance metrics	/src/modules/logic/training_metrics_lg/
training_metrics_lg	loss_calculator_lg	Calculates and tracks training and validation loss values	/src/modules/logic/training_metrics_lg/loss_calculator_lg/
training_metrics_lg	metric_aggregator_lg	Aggregates various training metrics for reporting and analysis	/src/modules/logic/training_metrics_lg/metric_aggregator_lg/
training_metrics_lg	early_stopping_lg	Implements early stopping logic based on validation metrics	/src/modules/logic/training_metrics_lg/early_stopping_lg/
training_metrics_lg	metric_exporter_lg	Exports training metrics in various formats for analysis	/src/modules/logic/training_metrics_lg/metric_exporter_lg/
training_data_pipeline_lg		Manages data flow and preprocessing for training	/src/modules/logic/training_data_pipeline_lg/
training_data_pipeline_lg	data_loader_lg	Loads and batches training data from processed documents	/src/modules/logic/training_data_pipeline_lg/data_loader_lg/
training_data_pipeline_lg	data_augmentation_lg	Applies data augmentation techniques for training improvement	/src/modules/logic/training_data_pipeline_lg/data_augmentation_lg/
training_data_pipeline_lg	data_validator_lg	Validates training data quality and completeness	/src/modules/logic/training_data_pipeline_lg/data_validator_lg/
training_data_pipeline_lg	batch_generator_lg	Generates training batches with proper tokenization and padding	/src/modules/logic/training_data_pipeline_lg/batch_generator_lg/
model_optimization_lg		Post-training model optimization and conversion	/src/modules/logic/model_optimization_lg/
model_optimization_lg	quantization_engine_lg	Applies quantization techniques (INT4, INT8, FP16) to trained models	/src/modules/logic/model_optimization_lg/quantization_engine_lg/
model_optimization_lg	onnx_converter_lg	Converts PyTorch models to ONNX format for deployment	/src/modules/logic/model_optimization_lg/onnx_converter_lg/
model_optimization_lg	optimization_validator_lg	Validates optimized models maintain acceptable performance	/src/modules/logic/model_optimization_lg/optimization_validator_lg/
model_optimization_lg	compression_engine_lg	Compresses model artifacts for efficient storage	/src/modules/logic/model_optimization_lg/compression_engine_lg/
training_monitor_ui		User interface for training progress visualization	/src/modules/ui/training_monitor_ui/
training_monitor_ui	progress_dashboard_ui	Main dashboard showing training progress, metrics, and resource usage	/src/modules/ui/training_monitor_ui/progress_dashboard_ui/
training_monitor_ui	loss_chart_ui	Real-time loss curve visualization with interactive charts	/src/modules/ui/training_monitor_ui/loss_chart_ui/
training_monitor_ui	metric_panel_ui	Displays various training metrics in organized panels	/src/modules/ui/training_monitor_ui/metric_panel_ui/
training_monitor_ui	control_panel_ui	Training control interface with pause, resume, and stop buttons	/src/modules/ui/training_monitor_ui/control_panel_ui/
training_configuration_ui		Interface for configuring training parameters	/src/modules/ui/training_configuration_ui/
training_configuration_ui	hyperparameter_form_ui	Form interface for setting training hyperparameters	/src/modules/ui/training_configuration_ui/hyperparameter_form_ui/
training_configuration_ui	model_selector_ui	UI for selecting model architecture and size (1B, 3B, 7B)	/src/modules/ui/training_configuration_ui/model_selector_ui/
training_configuration_ui	dataset_selector_ui	Interface for selecting documents and datasets for training	/src/modules/ui/training_configuration_ui/dataset_selector_ui/
training_configuration_ui	advanced_settings_ui	Advanced training configuration options interface	/src/modules/ui/training_configuration_ui/advanced_settings_ui/
checkpoint_viewer_ui		UI for checkpoint management and viewing	/src/modules/ui/checkpoint_viewer_ui/
checkpoint_viewer_ui	checkpoint_list_ui	Lists all available checkpoints with metadata	/src/modules/ui/checkpoint_viewer_ui/checkpoint_list_ui/
checkpoint_viewer_ui	checkpoint_details_ui	Displays detailed information about selected checkpoints	/src/modules/ui/checkpoint_viewer_ui/checkpoint_details_ui/
checkpoint_viewer_ui	recovery_dialog_ui	Dialog for checkpoint recovery operations	/src/modules/ui/checkpoint_viewer_ui/recovery_dialog_ui/
training_sessions_db		Database operations for training session persistence	/src/modules/database/training_sessions_db/
training_sessions_db	session_repository_db	CRUD operations for training session records	/src/modules/database/training_sessions_db/session_repository_db/
training_sessions_db	session_state_db	Manages training session state persistence	/src/modules/database/training_sessions_db/session_state_db/
training_sessions_db	session_history_db	Maintains historical training session data	/src/modules/database/training_sessions_db/session_history_db/
training_metrics_db		Database operations for training metrics storage	/src/modules/database/training_metrics_db/
training_metrics_db	metric_repository_db	Stores and retrieves training metrics time-series data	/src/modules/database/training_metrics_db/metric_repository_db/
training_metrics_db	metric_aggregation_db	Stores aggregated metric summaries and statistics	/src/modules/database/training_metrics_db/metric_aggregation_db/
training_metrics_db	metric_indexing_db	Indexes metrics for efficient querying and analysis	/src/modules/database/training_metrics_db/metric_indexing_db/
checkpoints_db		Database operations for checkpoint management	/src/modules/database/checkpoints_db/
checkpoints_db	checkpoint_registry_db	Maintains registry of all checkpoints with metadata	/src/modules/database/checkpoints_db/checkpoint_registry_db/
checkpoints_db	checkpoint_versioning_db	Manages checkpoint versioning and relationships	/src/modules/database/checkpoints_db/checkpoint_versioning_db/
checkpoints_db	checkpoint_cleanup_db	Tracks checkpoint retention and cleanup operations	/src/modules/database/checkpoints_db/checkpoint_cleanup_db/
training_config_db		Stores training configuration templates and presets	/src/modules/database/training_config_db/
training_config_db	config_repository_db	CRUD operations for training configuration storage	/src/modules/database/training_config_db/config_repository_db/
training_config_db	config_versioning_db	Manages configuration version history	/src/modules/database/training_config_db/config_versioning_db/
training_config_db	preset_manager_db	Stores and manages training configuration presets	/src/modules/database/training_config_db/preset_manager_db/
Key Design Principles
1.	Separation of Concerns: Each module handles a specific aspect of the training pipeline
2.	Fault Tolerance: Checkpoint system ensures training can recover from failures
3.	Scalability: Modular design allows for distributed training in future versions
4.	Performance: Optimized data pipeline for handling large datasets efficiently
5.	Extensibility: Easy to add new training algorithms or optimization techniques
X
IDRAlloc Memory Management Modules
Overview
The Intelligent Dynamic Resource Allocation (IDRAlloc) system is a critical component of MikroDok that enables training and inference of models larger than available GPU memory through sophisticated memory bridging across GPU VRAM, system RAM, and NVMe storage.
Module Structure
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
memory_allocation_lg	allocation_strategy_lg	Implements core allocation algorithms for Legacy, Hybrid, and Auto IDRAlloc modes with intelligent mode selection based on hardware capabilities	/src/modules/logic/memory_allocation_lg/allocation_strategy_lg/
memory_allocation_lg	memory_tier_manager_lg	Manages three-tier memory hierarchy (GPU VRAM, System RAM, NVMe) with bandwidth ratings and capacity tracking	/src/modules/logic/memory_allocation_lg/memory_tier_manager_lg/
memory_allocation_lg	layer_distribution_lg	Distributes model layers across memory tiers based on access patterns and criticality (embeddings, output layers prioritized)	/src/modules/logic/memory_allocation_lg/layer_distribution_lg/
memory_bridging_lg	bridge_controller_lg	Orchestrates data movement between memory tiers using DMA transfers with LRU eviction policies	/src/modules/logic/memory_bridging_lg/bridge_controller_lg/
memory_bridging_lg	predictive_preloader_lg	Analyzes computation graphs to anticipate layer access patterns and schedules background transfers	/src/modules/logic/memory_bridging_lg/predictive_preloader_lg/
memory_bridging_lg	transfer_queue_lg	Manages pending memory transfers with priority scheduling and bandwidth allocation	/src/modules/logic/memory_bridging_lg/transfer_queue_lg/
memory_optimization_lg	memory_pressure_detector_lg	Monitors memory usage patterns and predicts exhaustion using regression analysis on allocation history	/src/modules/logic/memory_optimization_lg/memory_pressure_detector_lg/
memory_optimization_lg	adaptive_reallocation_lg	Dynamically adjusts memory distribution based on performance metrics and resource availability	/src/modules/logic/memory_optimization_lg/adaptive_reallocation_lg/
memory_optimization_lg	fragmentation_manager_lg	Handles memory fragmentation issues with pool pre-allocation and defragmentation strategies	/src/modules/logic/memory_optimization_lg/fragmentation_manager_lg/
nvme_virtual_memory_lg	swap_controller_lg	Manages NVMe-based virtual VRAM implementation with high-speed page swapping (>3.5GB/s)	/src/modules/logic/nvme_virtual_memory_lg/swap_controller_lg/
nvme_virtual_memory_lg	page_manager_lg	Handles 4KB page-level operations for efficient disk-based memory extension	/src/modules/logic/nvme_virtual_memory_lg/page_manager_lg/
memory_monitor_ui	allocation_visualizer_ui	Displays real-time memory distribution across tiers with animated flow indicators	/src/modules/ui/memory_monitor_ui/allocation_visualizer_ui/
memory_monitor_ui	pressure_gauge_ui	Shows memory pressure levels with color-coded indicators (green/yellow/red)	/src/modules/ui/memory_monitor_ui/pressure_gauge_ui/
memory_config_ui	mode_selector_ui	Provides interface for selecting Legacy, Hybrid, or Auto IDRAlloc modes with hardware compatibility checks	/src/modules/ui/memory_config_ui/mode_selector_ui/
memory_config_ui	limit_configurator_ui	Allows setting memory limits for each tier with slider controls and validation	/src/modules/ui/memory_config_ui/limit_configurator_ui/
resource_allocation_db	allocation_profiles_db	Stores reusable resource allocation configurations with mode settings and limits	/src/modules/database/resource_allocation_db/allocation_profiles_db/
resource_allocation_db	memory_metrics_db	Persists memory allocation history and performance metrics for optimization analysis	/src/modules/database/resource_allocation_db/memory_metrics_db/
resource_allocation_db	allocation_state_db	Maintains current memory distribution state and layer placement mappings	/src/modules/database/resource_allocation_db/allocation_state_db/
Key Design Principles
1.	Separation of Concerns: Memory management logic is isolated from UI and persistence layers
2.	Modularity: Each submodule handles a specific aspect of memory management
3.	Extensibility: New memory tiers or allocation strategies can be added without affecting existing modules
4.	Performance: Critical path operations are optimized for minimal latency
5.	Fault Tolerance: Graceful degradation when memory tiers become unavailable
X
RAG and Search Modules - MikroDok Architecture
Overview
This section defines the modular structure for MikroDok's Retrieval-Augmented Generation (RAG) and search functionality, enabling semantic search across document collections and context-aware response generation.
Module Structure Table
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
LOGIC MODULES			
embedding_generation_lg	document_embedder_lg	Converts document chunks into high-dimensional vectors using transformer models (all-MiniLM-L6-v2)	/src/modules/logic/embedding_generation_lg/document_embedder_lg/
embedding_generation_lg	batch_processor_lg	Manages batch processing of embeddings with configurable batch sizes for efficiency	/src/modules/logic/embedding_generation_lg/batch_processor_lg/
embedding_generation_lg	embedding_cache_lg	LRU cache implementation for frequently accessed embeddings to reduce computation	/src/modules/logic/embedding_generation_lg/embedding_cache_lg/
vector_search_lg	similarity_calculator_lg	Implements cosine similarity calculations for semantic search operations	/src/modules/logic/vector_search_lg/similarity_calculator_lg/
vector_search_lg	knn_search_lg	K-nearest neighbor search implementation for finding similar document chunks	/src/modules/logic/vector_search_lg/knn_search_lg/
vector_search_lg	index_optimizer_lg	Optimizes vector indices (FLAT, IVF, HNSW) for performance based on collection size	/src/modules/logic/vector_search_lg/index_optimizer_lg/
hybrid_search_lg	semantic_searcher_lg	Performs vector-based semantic search using embeddings and similarity metrics	/src/modules/logic/hybrid_search_lg/semantic_searcher_lg/
hybrid_search_lg	keyword_searcher_lg	Implements BM25 algorithm for traditional keyword-based search	/src/modules/logic/hybrid_search_lg/keyword_searcher_lg/
hybrid_search_lg	result_fusion_lg	Combines and ranks results from semantic and keyword searches using weighted fusion	/src/modules/logic/hybrid_search_lg/result_fusion_lg/
query_processor_lg	query_parser_lg	Parses user queries, extracts special operators and filters	/src/modules/logic/query_processor_lg/query_parser_lg/
query_processor_lg	query_expansion_lg	Expands queries with synonyms and related terms for better recall	/src/modules/logic/query_processor_lg/query_expansion_lg/
query_processor_lg	query_optimizer_lg	Optimizes query execution plans based on index statistics	/src/modules/logic/query_processor_lg/query_optimizer_lg/
context_builder_lg	chunk_selector_lg	Selects optimal chunks for LLM context based on relevance and token limits	/src/modules/logic/context_builder_lg/chunk_selector_lg/
context_builder_lg	context_window_lg	Manages context window construction with token counting and optimization	/src/modules/logic/context_builder_lg/context_window_lg/
context_builder_lg	reranker_lg	Implements cross-encoder reranking for improved result relevance	/src/modules/logic/context_builder_lg/reranker_lg/
rag_orchestrator_lg	pipeline_manager_lg	Orchestrates complete RAG pipeline from query to augmented response	/src/modules/logic/rag_orchestrator_lg/pipeline_manager_lg/
rag_orchestrator_lg	retrieval_strategy_lg	Implements different retrieval strategies (dense, sparse, hybrid)	/src/modules/logic/rag_orchestrator_lg/retrieval_strategy_lg/
rag_orchestrator_lg	augmentation_engine_lg	Augments prompts with retrieved context for LLM input	/src/modules/logic/rag_orchestrator_lg/augmentation_engine_lg/
UI MODULES			
search_interface_ui	search_bar_ui	Main search input component with auto-complete suggestions	/src/modules/ui/search_interface_ui/search_bar_ui/
search_interface_ui	search_filters_ui	UI for search filters including document type, date range, relevance threshold	/src/modules/ui/search_interface_ui/search_filters_ui/
search_interface_ui	search_mode_ui	Toggle interface for semantic-only, keyword-only, or hybrid search modes	/src/modules/ui/search_interface_ui/search_mode_ui/
search_results_ui	result_list_ui	Displays search results with highlighted snippets and relevance scores	/src/modules/ui/search_results_ui/result_list_ui/
search_results_ui	result_card_ui	Individual result card component showing document excerpt and metadata	/src/modules/ui/search_results_ui/result_card_ui/
search_results_ui	citation_viewer_ui	Shows source citations with clickable references to original documents	/src/modules/ui/search_results_ui/citation_viewer_ui/
rag_answer_ui	answer_box_ui	Displays AI-generated answers with confidence scores	/src/modules/ui/rag_answer_ui/answer_box_ui/
rag_answer_ui	source_panel_ui	Side panel showing source documents used for answer generation	/src/modules/ui/rag_answer_ui/source_panel_ui/
rag_answer_ui	feedback_widget_ui	User feedback collection for answer quality improvement	/src/modules/ui/rag_answer_ui/feedback_widget_ui/
embedding_status_ui	embedding_progress_ui	Shows real-time progress of embedding generation for documents	/src/modules/ui/embedding_status_ui/embedding_progress_ui/
embedding_status_ui	index_stats_ui	Displays vector index statistics and optimization suggestions	/src/modules/ui/embedding_status_ui/index_stats_ui/
DATABASE MODULES			
vector_storage_db	chromadb_adapter_db	ChromaDB integration layer for vector storage and retrieval	/src/modules/database/vector_storage_db/chromadb_adapter_db/
vector_storage_db	embedding_repository_db	Repository pattern for managing document embeddings persistence	/src/modules/database/vector_storage_db/embedding_repository_db/
vector_storage_db	collection_manager_db	Manages vector collections with metadata and configuration	/src/modules/database/vector_storage_db/collection_manager_db/
search_index_db	inverted_index_db	Manages inverted index for keyword search functionality	/src/modules/database/search_index_db/inverted_index_db/
search_index_db	document_frequency_db	Stores document frequency statistics for BM25 ranking	/src/modules/database/search_index_db/document_frequency_db/
search_cache_db	query_cache_db	Caches frequent search queries and results for performance	/src/modules/database/search_cache_db/query_cache_db/
search_cache_db	result_cache_db	Stores cached search results with TTL management	/src/modules/database/search_cache_db/result_cache_db/
rag_metadata_db	chunk_mapping_db	Maps document chunks to their source documents and positions	/src/modules/database/rag_metadata_db/chunk_mapping_db/
rag_metadata_db	retrieval_history_db	Tracks retrieval operations for analytics and optimization	/src/modules/database/rag_metadata_db/retrieval_history_db/
Key Design Principles
•	Separation of Concerns: Clear boundaries between embedding generation, search operations, and result presentation
•	Performance Optimization: Caching layers and index optimization for sub-100ms search latency
•	Flexibility: Support for multiple search modes (semantic, keyword, hybrid) with pluggable strategies
•	Scalability: Designed to handle document collections up to 10GB with efficient memory usage
•	Offline-First: All RAG operations work completely offline without external API dependencies
X
Resource Monitoring Modules
Real-time system resource tracking, performance monitoring, and optimization triggers for MikroDok application.
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
resource_monitor_lg	hardware_monitor_lg	Core monitoring service that continuously tracks GPU, CPU, RAM, and storage utilization with configurable sampling intervals	/src/modules/logic/resource_monitor_lg/hardware_monitor_lg/
resource_monitor_lg	gpu_monitor_lg	Specialized GPU monitoring including VRAM usage, temperature, compute utilization, and CUDA/ROCm compatibility detection	/src/modules/logic/resource_monitor_lg/gpu_monitor_lg/
resource_monitor_lg	memory_monitor_lg	Tracks system RAM, swap usage, and memory allocation patterns for both training and inference operations	/src/modules/logic/resource_monitor_lg/memory_monitor_lg/
resource_monitor_lg	disk_monitor_lg	Monitors NVMe and storage I/O performance, available space, and read/write throughput for virtual memory operations	/src/modules/logic/resource_monitor_lg/disk_monitor_lg/
resource_monitor_lg	thermal_monitor_lg	Temperature monitoring system with throttling detection and automatic performance adjustment capabilities	/src/modules/logic/resource_monitor_lg/thermal_monitor_lg/
performance_optimizer_lg	optimization_trigger_lg	Evaluates system metrics against thresholds and triggers appropriate optimization actions based on resource pressure	/src/modules/logic/performance_optimizer_lg/optimization_trigger_lg/
performance_optimizer_lg	memory_pressure_handler_lg	Responds to memory exhaustion by adjusting allocations, offloading to lower tiers, and implementing emergency cleanup	/src/modules/logic/performance_optimizer_lg/memory_pressure_handler_lg/
performance_optimizer_lg	batch_size_optimizer_lg	Dynamically adjusts training batch sizes based on available resources and performance metrics	/src/modules/logic/performance_optimizer_lg/batch_size_optimizer_lg/
performance_optimizer_lg	cache_optimizer_lg	Manages cache eviction policies and prefetching strategies based on access patterns and available memory	/src/modules/logic/performance_optimizer_lg/cache_optimizer_lg/
resource_predictor_lg	usage_predictor_lg	ML-based prediction of future resource requirements using LSTM networks and historical usage patterns	/src/modules/logic/resource_predictor_lg/usage_predictor_lg/
resource_predictor_lg	bottleneck_detector_lg	Identifies performance bottlenecks and suggests optimization strategies based on resource utilization patterns	/src/modules/logic/resource_predictor_lg/bottleneck_detector_lg/
monitoring_aggregator_lg	metrics_aggregator_lg	Collects and aggregates performance metrics from all monitoring subsystems for unified reporting	/src/modules/logic/monitoring_aggregator_lg/metrics_aggregator_lg/
monitoring_aggregator_lg	time_series_processor_lg	Processes time-series monitoring data with downsampling and rolling window calculations	/src/modules/logic/monitoring_aggregator_lg/time_series_processor_lg/
resource_dashboard_ui	monitoring_dashboard_ui	Main monitoring interface displaying real-time resource utilization graphs and system health status	/src/modules/ui/resource_dashboard_ui/monitoring_dashboard_ui/
resource_dashboard_ui	gpu_utilization_chart_ui	Real-time GPU usage visualization with VRAM allocation, compute percentage, and temperature displays	/src/modules/ui/resource_dashboard_ui/gpu_utilization_chart_ui/
resource_dashboard_ui	memory_usage_chart_ui	Stacked area charts showing RAM, VRAM, and swap usage with tier distribution visualization	/src/modules/ui/resource_dashboard_ui/memory_usage_chart_ui/
resource_dashboard_ui	performance_gauge_ui	Circular gauge components for displaying CPU usage, disk I/O rates, and thermal status	/src/modules/ui/resource_dashboard_ui/performance_gauge_ui/
resource_dashboard_ui	alert_panel_ui	Displays resource warnings, threshold violations, and optimization recommendations	/src/modules/ui/resource_dashboard_ui/alert_panel_ui/
monitoring_controls_ui	threshold_config_ui	Interface for configuring warning and critical thresholds for various resource metrics	/src/modules/ui/monitoring_controls_ui/threshold_config_ui/
monitoring_controls_ui	refresh_rate_ui	Controls for adjusting monitoring update frequencies and data retention periods	/src/modules/ui/monitoring_controls_ui/refresh_rate_ui/
optimization_status_ui	optimization_indicator_ui	Visual indicators showing active optimizations and their impact on system performance	/src/modules/ui/optimization_status_ui/optimization_indicator_ui/
optimization_status_ui	resource_allocation_view_ui	Displays current IDRAlloc resource distribution across GPU, RAM, and NVMe tiers	/src/modules/ui/optimization_status_ui/resource_allocation_view_ui/
resource_monitoring_db	monitoring_metrics_db	Stores time-series resource utilization data with efficient circular buffer implementation	/src/modules/database/resource_monitoring_db/monitoring_metrics_db/
resource_monitoring_db	performance_history_db	Long-term storage of aggregated performance metrics for trend analysis and reporting	/src/modules/database/resource_monitoring_db/performance_history_db/
resource_monitoring_db	optimization_log_db	Records optimization trigger events, actions taken, and their effectiveness	/src/modules/database/resource_monitoring_db/optimization_log_db/
resource_monitoring_db	threshold_config_db	Persists user-defined resource monitoring thresholds and alert configurations	/src/modules/database/resource_monitoring_db/threshold_config_db/
resource_monitoring_db	thermal_history_db	Tracks temperature readings and thermal throttling events for hardware protection	/src/modules/database/resource_monitoring_db/thermal_history_db/
Key Design Principles:
•	Real-time Performance: 1-second sampling rate for critical metrics with minimal overhead
•	Predictive Capabilities: ML-based resource prediction to prevent exhaustion
•	Automatic Optimization: Self-adjusting system based on resource pressure
•	Hardware Protection: Thermal monitoring with automatic throttling
•	Scalable Storage: Efficient time-series data storage with automatic pruning
X
User Interface Modules - Frontend Components
Overview
This section defines all user interface modules for the MikroDok application, organized according to visual components, interaction patterns, and user workflows. Each module is designed with responsive layouts, accessibility compliance (WCAG 2.1 AA), and cross-platform compatibility.
UI Module Structure
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
main_dashboard_ui	landing_page_ui	Main application dashboard with project cards, quick actions, and system overview widgets	/src/modules/ui/main_dashboard_ui/landing_page_ui/
main_dashboard_ui	project_cards_ui	Interactive project card components displaying project metadata, status, and quick actions	/src/modules/ui/main_dashboard_ui/project_cards_ui/
main_dashboard_ui	quick_actions_ui	Quick start action buttons for creating models, importing documents, and starting training	/src/modules/ui/main_dashboard_ui/quick_actions_ui/
main_dashboard_ui	activity_feed_ui	Real-time activity feed showing recent system events and notifications	/src/modules/ui/main_dashboard_ui/activity_feed_ui/
navigation_ui	app_header_ui	Top navigation bar with logo, primary menu, user profile, and theme toggle	/src/modules/ui/navigation_ui/app_header_ui/
navigation_ui	sidebar_menu_ui	Collapsible sidebar with navigation links, resource monitor mini-view, and quick links	/src/modules/ui/navigation_ui/sidebar_menu_ui/
navigation_ui	breadcrumb_ui	Contextual breadcrumb navigation for deep application states	/src/modules/ui/navigation_ui/breadcrumb_ui/
navigation_ui	footer_status_ui	Bottom status bar showing memory usage, GPU temperature, and version info	/src/modules/ui/navigation_ui/footer_status_ui/
system_monitor_ui	resource_dashboard_ui	Comprehensive system resource monitoring dashboard with real-time graphs	/src/modules/ui/system_monitor_ui/resource_dashboard_ui/
system_monitor_ui	gpu_monitor_ui	GPU utilization, VRAM usage, and temperature visualization components	/src/modules/ui/system_monitor_ui/gpu_monitor_ui/
system_monitor_ui	cpu_monitor_ui	CPU usage graphs with per-core visualization and thermal monitoring	/src/modules/ui/system_monitor_ui/cpu_monitor_ui/
system_monitor_ui	memory_monitor_ui	RAM, VRAM, and swap usage visualization with allocation breakdowns	/src/modules/ui/system_monitor_ui/memory_monitor_ui/
system_monitor_ui	allocation_control_ui	IDRAlloc mode selector and resource allocation configuration interface	/src/modules/ui/system_monitor_ui/allocation_control_ui/
document_manager_ui	document_upload_ui	Drag-and-drop file upload interface with format validation and batch support	/src/modules/ui/document_manager_ui/document_upload_ui/
document_manager_ui	document_grid_ui	Grid view of uploaded documents with thumbnails, metadata, and processing status	/src/modules/ui/document_manager_ui/document_grid_ui/
document_manager_ui	processing_queue_ui	Document processing queue visualization with progress bars and status indicators	/src/modules/ui/document_manager_ui/processing_queue_ui/
document_manager_ui	document_preview_ui	Document preview panel with search highlighting and metadata display	/src/modules/ui/document_manager_ui/document_preview_ui/
document_manager_ui	quality_report_ui	Document quality assessment results with validation warnings and errors	/src/modules/ui/document_manager_ui/quality_report_ui/
search_interface_ui	search_bar_ui	Advanced search input with auto-complete, filters, and query builder	/src/modules/ui/search_interface_ui/search_bar_ui/
search_interface_ui	search_results_ui	Search results display with relevance scores, snippets, and source citations	/src/modules/ui/search_interface_ui/search_results_ui/
search_interface_ui	rag_answer_ui	AI-generated answer box with confidence scores and source references	/src/modules/ui/search_interface_ui/rag_answer_ui/
search_interface_ui	document_collection_ui	Document collection tree view for organizing imported documents	/src/modules/ui/search_interface_ui/document_collection_ui/
chat_interface_ui	chat_window_ui	Main chat interface with message history and typing indicators	/src/modules/ui/chat_interface_ui/chat_window_ui/
chat_interface_ui	message_input_ui	Multi-line input with markdown preview and attachment support	/src/modules/ui/chat_interface_ui/message_input_ui/
chat_interface_ui	chat_settings_ui	Chat configuration panel for temperature, max tokens, and response settings	/src/modules/ui/chat_interface_ui/chat_settings_ui/
chat_interface_ui	session_history_ui	Previous chat sessions list with timestamps and quick access	/src/modules/ui/chat_interface_ui/session_history_ui/
model_builder_ui	model_config_ui	Model architecture selection and training parameter configuration forms	/src/modules/ui/model_builder_ui/model_config_ui/
model_builder_ui	training_controls_ui	Start, pause, resume, and cancel training action buttons with state management	/src/modules/ui/model_builder_ui/training_controls_ui/
model_builder_ui	training_progress_ui	Real-time training progress visualization with loss curves and metrics	/src/modules/ui/model_builder_ui/training_progress_ui/
model_builder_ui	checkpoint_list_ui	Training checkpoint management interface with restore options	/src/modules/ui/model_builder_ui/checkpoint_list_ui/
model_registry_ui	model_grid_ui	Model card grid view with performance metrics and quick actions	/src/modules/ui/model_registry_ui/model_grid_ui/
model_registry_ui	model_details_ui	Detailed model information panel with architecture and training history	/src/modules/ui/model_registry_ui/model_details_ui/
model_registry_ui	version_tree_ui	Git-style version tree visualization for model versions	/src/modules/ui/model_registry_ui/version_tree_ui/
model_registry_ui	deployment_wizard_ui	Model export and deployment configuration wizard interface	/src/modules/ui/model_registry_ui/deployment_wizard_ui/
model_registry_ui	benchmark_results_ui	Model performance benchmark visualization across hardware configs	/src/modules/ui/model_registry_ui/benchmark_results_ui/
settings_panel_ui	general_settings_ui	Language, theme, auto-save, and update preference controls	/src/modules/ui/settings_panel_ui/general_settings_ui/
settings_panel_ui	resource_settings_ui	Resource allocation limits, performance profiles, and hardware configuration	/src/modules/ui/settings_panel_ui/resource_settings_ui/
settings_panel_ui	model_defaults_ui	Default model architecture, training parameters, and quantization settings	/src/modules/ui/settings_panel_ui/model_defaults_ui/
settings_panel_ui	processing_settings_ui	Document processing format support, chunk size, and OCR configuration	/src/modules/ui/settings_panel_ui/processing_settings_ui/
settings_panel_ui	advanced_settings_ui	Logging levels, telemetry, cache management, and configuration export/import	/src/modules/ui/settings_panel_ui/advanced_settings_ui/
dialog_components_ui	error_dialog_ui	Error notification dialogs with severity levels and recovery actions	/src/modules/ui/dialog_components_ui/error_dialog_ui/
dialog_components_ui	confirmation_dialog_ui	Confirmation dialogs for destructive actions with safety warnings	/src/modules/ui/dialog_components_ui/confirmation_dialog_ui/
dialog_components_ui	progress_dialog_ui	Long-running operation progress dialogs with cancellation support	/src/modules/ui/dialog_components_ui/progress_dialog_ui/
dialog_components_ui	file_picker_ui	Custom file/directory picker dialogs for document and model selection	/src/modules/ui/dialog_components_ui/file_picker_ui/
visualization_ui	chart_components_ui	Reusable chart components for metrics, performance graphs, and resource usage	/src/modules/ui/visualization_ui/chart_components_ui/
visualization_ui	metric_cards_ui	Metric display cards with real-time updates and trend indicators	/src/modules/ui/visualization_ui/metric_cards_ui/
visualization_ui	progress_indicators_ui	Various progress bars, spinners, and loading animations	/src/modules/ui/visualization_ui/progress_indicators_ui/
visualization_ui	status_badges_ui	Status indicator badges for training states, model health, and system status	/src/modules/ui/visualization_ui/status_badges_ui/
common_components_ui	form_controls_ui	Reusable form inputs, sliders, toggles, and validation components	/src/modules/ui/common_components_ui/form_controls_ui/
common_components_ui	table_components_ui	Data tables with sorting, filtering, and pagination capabilities	/src/modules/ui/common_components_ui/table_components_ui/
common_components_ui	notification_ui	Toast notifications, alerts, and inline message components	/src/modules/ui/common_components_ui/notification_ui/
common_components_ui	tooltip_ui	Context-sensitive tooltips and help popovers	/src/modules/ui/common_components_ui/tooltip_ui/
theme_system_ui	color_palette_ui	Monochromatic color system with light/dark mode definitions	/src/modules/ui/theme_system_ui/color_palette_ui/
theme_system_ui	typography_ui	Font system with Inter and JetBrains Mono configurations	/src/modules/ui/theme_system_ui/typography_ui/
theme_system_ui	spacing_system_ui	Consistent spacing scale and layout grid definitions	/src/modules/ui/theme_system_ui/spacing_system_ui/
theme_system_ui	animation_ui	Animation timing, transitions, and motion design system	/src/modules/ui/theme_system_ui/animation_ui/
accessibility_ui	screen_reader_ui	ARIA labels, live regions, and screen reader optimizations	/src/modules/ui/accessibility_ui/screen_reader_ui/
accessibility_ui	keyboard_nav_ui	Keyboard navigation handlers, shortcuts, and focus management	/src/modules/ui/accessibility_ui/keyboard_nav_ui/
accessibility_ui	high_contrast_ui	High contrast mode support and color blind friendly palettes	/src/modules/ui/accessibility_ui/high_contrast_ui/
accessibility_ui	responsive_ui	Responsive breakpoint handlers and adaptive layouts	/src/modules/ui/accessibility_ui/responsive_ui/
Key Design Principles
•	Component Reusability: Common UI elements are centralized in shared modules
•	State Management: Each UI module maintains its own local state with global state synchronization
•	Event-Driven Updates: Real-time UI updates through event bus integration
•	Progressive Disclosure: Complex features revealed gradually based on user expertise
•	Offline-First Design: All UI components function without internet connectivity
•	Performance Optimization: Virtual scrolling, lazy loading, and efficient re-rendering strategies
X
Database and Persistence Modules - MikroDok Architecture
Overview
Database and persistence modules handle all data access operations, SQLite integration, repository patterns, and data integrity management. These modules implement clean separation between business logic and data persistence, supporting offline operation with high-performance requirements for ML workloads.
Module Structure
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
database_core_db	connection_manager_db	Manages SQLite database connections with WAL mode, connection pooling, and thread-safe access patterns	/src/modules/database/database_core_db/connection_manager_db/
database_core_db	migration_engine_db	Handles schema versioning, database migrations, and backward compatibility with rollback support	/src/modules/database/database_core_db/migration_engine_db/
database_core_db	transaction_coordinator_db	Coordinates complex transactions across multiple tables with ACID compliance and deadlock prevention	/src/modules/database/database_core_db/transaction_coordinator_db/
database_core_db	backup_service_db	Implements online backup API for live database copying with checkpoint synchronization	/src/modules/database/database_core_db/backup_service_db/
project_repository_db	project_dao_db	Data access operations for project entities including CRUD operations and query optimization	/src/modules/database/project_repository_db/project_dao_db/
project_repository_db	project_settings_db	Manages project-specific configurations and user preferences with JSON storage	/src/modules/database/project_repository_db/project_settings_db/
model_repository_db	model_dao_db	Handles model metadata persistence, version tracking, and performance metrics storage	/src/modules/database/model_repository_db/model_dao_db/
model_repository_db	model_versions_db	Manages model version history with Git-style branching and semantic versioning support	/src/modules/database/model_repository_db/model_versions_db/
model_repository_db	checkpoint_storage_db	Stores training checkpoint metadata with retention policies and best model tracking	/src/modules/database/model_repository_db/checkpoint_storage_db/
training_repository_db	training_session_db	Persists training session data including configuration, progress, and resource allocation	/src/modules/database/training_repository_db/training_session_db/
training_repository_db	training_metrics_db	Time-series storage for training metrics with efficient batch insertion and aggregation	/src/modules/database/training_repository_db/training_metrics_db/
training_repository_db	resource_allocation_db	Stores IDRAlloc configurations and memory distribution strategies	/src/modules/database/training_repository_db/resource_allocation_db/
document_repository_db	document_dao_db	Manages document metadata, processing status, and file references with deduplication	/src/modules/database/document_repository_db/document_dao_db/
document_repository_db	document_chunks_db	Stores processed text chunks with position mappings and quality metrics	/src/modules/database/document_repository_db/document_chunks_db/
document_repository_db	document_collection_db	Organizes documents into logical collections for training and RAG operations	/src/modules/database/document_repository_db/document_collection_db/
vector_storage_db	embedding_repository_db	Manages high-dimensional vector storage with efficient similarity search support	/src/modules/database/vector_storage_db/embedding_repository_db/
vector_storage_db	vector_index_db	Implements vector indexing strategies (FLAT, IVF, HNSW) for fast retrieval	/src/modules/database/vector_storage_db/vector_index_db/
vector_storage_db	chunk_mapping_db	Maintains relationships between document chunks and their embeddings	/src/modules/database/vector_storage_db/chunk_mapping_db/
monitoring_repository_db	resource_metrics_db	Stores system resource utilization data with circular buffer implementation	/src/modules/database/monitoring_repository_db/resource_metrics_db/
monitoring_repository_db	performance_benchmarks_db	Persists model performance test results and hardware configuration data	/src/modules/database/monitoring_repository_db/performance_benchmarks_db/
monitoring_repository_db	system_logs_db	Manages application event logs, errors, and audit trails with retention policies	/src/modules/database/monitoring_repository_db/system_logs_db/
chat_repository_db	chat_session_db	Stores interactive inference sessions with conversation history	/src/modules/database/chat_repository_db/chat_session_db/
chat_repository_db	chat_messages_db	Persists individual chat messages with context window management	/src/modules/database/chat_repository_db/chat_messages_db/
chat_repository_db	inference_metrics_db	Tracks inference performance metrics and resource usage per session	/src/modules/database/chat_repository_db/inference_metrics_db/
cache_persistence_db	model_cache_db	Implements persistent caching layer for frequently accessed model metadata	/src/modules/database/cache_persistence_db/model_cache_db/
cache_persistence_db	query_cache_db	Caches database query results with intelligent invalidation rules	/src/modules/database/cache_persistence_db/query_cache_db/
cache_persistence_db	embedding_cache_db	Persists computed embeddings to avoid recomputation during RAG operations	/src/modules/database/cache_persistence_db/embedding_cache_db/
blob_storage_db	model_artifacts_db	Manages references to large model files stored on filesystem with integrity checks	/src/modules/database/blob_storage_db/model_artifacts_db/
blob_storage_db	document_files_db	Tracks original document files with hash-based deduplication	/src/modules/database/blob_storage_db/document_files_db/
blob_storage_db	checkpoint_files_db	Manages checkpoint binary data with compression and incremental storage	/src/modules/database/blob_storage_db/checkpoint_files_db/
optimization_db	index_manager_db	Manages database indexes with automatic optimization and statistics updates	/src/modules/database/optimization_db/index_manager_db/
optimization_db	vacuum_scheduler_db	Implements incremental auto-vacuum with fragmentation monitoring	/src/modules/database/optimization_db/vacuum_scheduler_db/
optimization_db	query_optimizer_db	Analyzes and optimizes slow queries with execution plan caching	/src/modules/database/optimization_db/query_optimizer_db/
Key Design Principles
1.	Repository Pattern: Each entity type has dedicated repository modules with clear interfaces
2.	Connection Management: Thread-safe connection pooling with separate read/write connections
3.	Performance Optimization: Strategic denormalization and covering indexes for hot paths
4.	Data Integrity: Comprehensive foreign key constraints and transaction management
5.	Offline Operation: All persistence operations designed for local SQLite with no external dependencies
6.	Memory Efficiency: External blob storage for large objects with metadata in database
7.	Scalability: Modular design supports future migration to client-server architecture
X
Infrastructure and Support Modules - MikroDok
Overview
This section defines the infrastructure and support modules that provide cross-cutting functionality across the MikroDok application. These modules handle logging, error management, background services, security, caching, and other foundational concerns essential for enterprise-grade reliability and performance.
Module Structure Table
MODULE	SUBMODULE	DESCRIPTION	DIRECTORY PATH
logging_infrastructure_lg	log_manager_lg	Centralized logging management with configurable levels and outputs	/src/modules/logic/logging_infrastructure_lg/log_manager_lg/
logging_infrastructure_lg	performance_logger_lg	Specialized logging for performance metrics and bottleneck detection	/src/modules/logic/logging_infrastructure_lg/performance_logger_lg/
logging_infrastructure_lg	audit_logger_lg	Security and compliance audit trail logging with tamper protection	/src/modules/logic/logging_infrastructure_lg/audit_logger_lg/
logging_infrastructure_lg	training_logger_lg	Dedicated logger for ML training metrics and progress tracking	/src/modules/logic/logging_infrastructure_lg/training_logger_lg/
error_handling_lg	error_classifier_lg	Categorizes errors by severity and determines recovery strategies	/src/modules/logic/error_handling_lg/error_classifier_lg/
error_handling_lg	recovery_orchestrator_lg	Manages error recovery workflows and fallback mechanisms	/src/modules/logic/error_handling_lg/recovery_orchestrator_lg/
error_handling_lg	crash_handler_lg	Handles application crashes with state preservation and recovery	/src/modules/logic/error_handling_lg/crash_handler_lg/
error_handling_lg	validation_engine_lg	Input validation and data integrity checking across modules	/src/modules/logic/error_handling_lg/validation_engine_lg/
background_services_lg	service_registry_lg	Manages lifecycle of all background services and workers	/src/modules/logic/background_services_lg/service_registry_lg/
background_services_lg	task_scheduler_lg	Schedules and coordinates background tasks with priority management	/src/modules/logic/background_services_lg/task_scheduler_lg/
background_services_lg	maintenance_service_lg	Handles database optimization, cleanup, and routine maintenance	/src/modules/logic/background_services_lg/maintenance_service_lg/
background_services_lg	health_monitor_lg	Monitors application health and service status continuously	/src/modules/logic/background_services_lg/health_monitor_lg/
event_system_lg	event_bus_lg	Central message bus for decoupled component communication	/src/modules/logic/event_system_lg/event_bus_lg/
event_system_lg	event_dispatcher_lg	Routes events to appropriate handlers with filtering and priority	/src/modules/logic/event_system_lg/event_dispatcher_lg/
event_system_lg	event_aggregator_lg	Batches and aggregates events for efficient processing	/src/modules/logic/event_system_lg/event_aggregator_lg/
event_system_lg	state_synchronizer_lg	Maintains consistency between frontend and backend state	/src/modules/logic/event_system_lg/state_synchronizer_lg/
thread_coordination_lg	thread_pool_manager_lg	Manages application-wide thread pools for different operations	/src/modules/logic/thread_coordination_lg/thread_pool_manager_lg/
thread_coordination_lg	lock_manager_lg	Coordinates resource locks and prevents deadlocks	/src/modules/logic/thread_coordination_lg/lock_manager_lg/
thread_coordination_lg	async_task_manager_lg	Handles asynchronous operation lifecycle and callbacks	/src/modules/logic/thread_coordination_lg/async_task_manager_lg/
thread_coordination_lg	work_distributor_lg	Distributes work across available threads with load balancing	/src/modules/logic/thread_coordination_lg/work_distributor_lg/
security_infrastructure_lg	encryption_manager_lg	Handles data encryption for models and sensitive information	/src/modules/logic/security_infrastructure_lg/encryption_manager_lg/
security_infrastructure_lg	access_controller_lg	Manages access control and permission validation	/src/modules/logic/security_infrastructure_lg/access_controller_lg/
security_infrastructure_lg	secure_storage_lg	Provides secure storage for credentials and API keys	/src/modules/logic/security_infrastructure_lg/secure_storage_lg/
security_infrastructure_lg	integrity_validator_lg	Validates data integrity with checksums and signatures	/src/modules/logic/security_infrastructure_lg/integrity_validator_lg/
cache_management_lg	memory_cache_lg	In-memory caching for frequently accessed data	/src/modules/logic/cache_management_lg/memory_cache_lg/
cache_management_lg	model_cache_lg	Specialized cache for model metadata and parameters	/src/modules/logic/cache_management_lg/model_cache_lg/
cache_management_lg	embedding_cache_lg	LRU cache for document embeddings and vectors	/src/modules/logic/cache_management_lg/embedding_cache_lg/
cache_management_lg	cache_coordinator_lg	Ensures cache consistency across different layers	/src/modules/logic/cache_management_lg/cache_coordinator_lg/
performance_optimization_lg	resource_optimizer_lg	Dynamically optimizes resource allocation based on load	/src/modules/logic/performance_optimization_lg/resource_optimizer_lg/
performance_optimization_lg	throttle_controller_lg	Manages rate limiting and prevents system overload	/src/modules/logic/performance_optimization_lg/throttle_controller_lg/
performance_optimization_lg	memory_pool_allocator_lg	Pre-allocated memory pools to reduce allocation overhead	/src/modules/logic/performance_optimization_lg/memory_pool_allocator_lg/
performance_optimization_lg	batch_processor_lg	Optimizes batch operations for efficiency	/src/modules/logic/performance_optimization_lg/batch_processor_lg/
backup_recovery_lg	backup_manager_lg	Handles automated backups of models and data	/src/modules/logic/backup_recovery_lg/backup_manager_lg/
backup_recovery_lg	recovery_engine_lg	Manages recovery from backups and corrupted states	/src/modules/logic/backup_recovery_lg/recovery_engine_lg/
backup_recovery_lg	checkpoint_archiver_lg	Archives and manages training checkpoints	/src/modules/logic/backup_recovery_lg/checkpoint_archiver_lg/
backup_recovery_lg	state_snapshotter_lg	Creates and manages application state snapshots	/src/modules/logic/backup_recovery_lg/state_snapshotter_lg/
system_initialization_lg	startup_orchestrator_lg	Manages application startup sequence and dependencies	/src/modules/logic/system_initialization_lg/startup_orchestrator_lg/
system_initialization_lg	preflight_checker_lg	Validates system requirements before initialization	/src/modules/logic/system_initialization_lg/preflight_checker_lg/
system_initialization_lg	shutdown_coordinator_lg	Handles graceful shutdown with resource cleanup	/src/modules/logic/system_initialization_lg/shutdown_coordinator_lg/
system_initialization_lg	dependency_resolver_lg	Resolves and validates module dependencies	/src/modules/logic/system_initialization_lg/dependency_resolver_lg/
notification_system_ui	toast_manager_ui	Displays non-blocking toast notifications	/src/modules/ui/notification_system_ui/toast_manager_ui/
notification_system_ui	alert_dialog_ui	Shows modal alerts for critical messages	/src/modules/ui/notification_system_ui/alert_dialog_ui/
notification_system_ui	progress_overlay_ui	Displays progress overlays for long operations	/src/modules/ui/notification_system_ui/progress_overlay_ui/
notification_system_ui	status_bar_ui	Shows persistent status messages in status bar	/src/modules/ui/notification_system_ui/status_bar_ui/
system_logs_db	log_entries_db	Stores application logs with severity and timestamps	/src/modules/database/system_logs_db/log_entries_db/
system_logs_db	audit_trail_db	Maintains tamper-proof audit trail records	/src/modules/database/system_logs_db/audit_trail_db/
system_logs_db	error_history_db	Persists error occurrences and recovery attempts	/src/modules/database/system_logs_db/error_history_db/
system_logs_db	performance_metrics_db	Stores historical performance data for analysis	/src/modules/database/system_logs_db/performance_metrics_db/
Key Design Principles
1.	Separation of Concerns: Each module handles a specific infrastructure aspect without overlapping responsibilities
2.	Extensibility: Modules designed to accommodate future enhancements like cloud integration or multi-user support
3.	Reliability: Comprehensive error handling and recovery mechanisms throughout
4.	Performance: Optimized caching, threading, and resource management for ML workloads
5.	Security: Built-in encryption, access control, and audit capabilities
6.	Maintainability: Clear module boundaries and standardized interfaces
X

