Executive Summary - MikroDok Database Architecture
Overview
The MikroDok database architecture employs SQLite as the primary data store, optimized for desktop deployment with emphasis on offline operation, high-performance ML workloads, and efficient handling of large model artifacts. The design prioritizes local-first operation while maintaining enterprise-grade reliability.
Core Design Principles
1. Hybrid Storage Strategy
•	Metadata in SQLite: Model configurations, training metrics, document metadata, and system state
•	Binary Assets on Filesystem: Model weights, checkpoints, and large embeddings stored as files
•	Reference Architecture: SQLite maintains file paths and integrity checksums for external assets
2. Performance-First Design
•	Strategic Denormalization: Training metrics and frequently accessed data denormalized for read performance
•	Write-Ahead Logging (WAL): Enables concurrent reads during long training operations
•	Memory-Mapped I/O: 1GB mmap_size for optimal model metadata access
•	Minimal Locking: Separate databases for high-frequency writes (metrics) and stable data (models)
3. ML-Specific Optimizations
•	Temporal Data Handling: Efficient storage of time-series training metrics
•	Checkpoint Management: Incremental checkpoint tracking with delta storage references
•	Resource Monitoring: Lightweight tables for real-time GPU/CPU/memory statistics
•	Version Control: Git-style model versioning with branch and merge capabilities
4. Data Integrity & Recovery
•	ACID Compliance: Full transactional support for critical operations
•	Automatic Checkpointing: Configurable WAL checkpointing for durability
•	Referential Integrity: Foreign key constraints ensuring data consistency
•	Backup Strategies: Online backup API integration with incremental snapshots
5. Scalability Considerations
•	Modular Schema: Separate schemas for core, documents, training, and vectors
•	Sharding Ready: Document collections designed for future partitioning
•	Migration Path: Clear upgrade path to client-server architecture if needed
•	Size Management: Automatic archival of old training runs and checkpoints
Key Technical Decisions
Database Configuration
•	Journal Mode: WAL for concurrent access
•	Synchronous: NORMAL for balanced performance/durability
•	Cache Size: 50,000 pages (200MB) for in-memory operations
•	Page Size: 4096 bytes optimized for SSD storage
Schema Organization
•	Core Tables: 15 tables for model lifecycle management
•	Document Tables: 8 tables for RAG and document processing
•	Training Tables: 10 tables for metrics and progress tracking
•	Vector Tables: 5 tables for embedding storage and search
•	System Tables: 6 tables for configuration and monitoring
Security Architecture
•	Encryption: Optional SQLite encryption extension support
•	Access Control: Application-level security with audit trails
•	Data Sanitization: Parameterized queries throughout
•	Sensitive Data: Separate encrypted storage for API keys and credentials
Expected Performance Characteristics
•	Model Metadata Queries: <10ms response time
•	Training Metric Inserts: 1000+ inserts/second capability
•	Document Search: <100ms for 1M document corpus
•	Concurrent Access: 10+ simultaneous read connections
•	Database Size: Optimized for 50GB+ deployments
X
Entity-Relationship Model - MikroDok Database
Core Entities
Projects
Primary entity representing user workspace for model development. Contains project metadata, configuration settings, and serves as parent for all project-related entities.
Models
Central entity storing trained language model metadata. Links to physical model files, tracks versions, performance metrics, and deployment status.
Documents
Represents source documents for training. Stores document metadata, processing status, and links to extracted content chunks.
Training_Sessions
Tracks individual training runs including configuration, progress, resource usage, and checkpoints.
Users
Manages application users (single-user desktop focus) with preferences and settings.
Supporting Entities
Model_Versions
Version control for models with branching support, allowing rollback and comparison.
Document_Chunks
Processed text segments from documents with embeddings for RAG functionality.
Vector_Embeddings
Stores high-dimensional vectors for semantic search operations.
Training_Metrics
Time-series data for loss curves, validation scores, and performance metrics.
Resource_Allocations
IDRAlloc configuration and memory distribution strategies per training session.
Checkpoints
Training state snapshots enabling resume capabilities and model recovery.
Chat_Sessions
Interactive inference sessions with conversation history and context.
System_Logs
Application events, errors, and performance monitoring data.
Key Relationships
One-to-Many Relationships
•	Projects → Models (1:N) - Project contains multiple models
•	Projects → Documents (1:N) - Project includes document collections
•	Models → Model_Versions (1:N) - Model has version history
•	Models → Training_Sessions (1:N) - Model trained multiple times
•	Documents → Document_Chunks (1:N) - Document split into chunks
•	Training_Sessions → Checkpoints (1:N) - Session creates checkpoints
•	Training_Sessions → Training_Metrics (1:N) - Session generates metrics
•	Models → Chat_Sessions (1:N) - Model serves multiple chats
Many-to-Many Relationships
•	Documents ↔ Models (M:N) - Documents train multiple models, models use multiple documents
•	Document_Chunks ↔ Vector_Embeddings (M:N) - Chunks have multiple embedding versions
One-to-One Relationships
•	Training_Sessions → Resource_Allocations (1:1) - Each session has specific resource config
•	Model_Versions → Deployment_Configs (1:1) - Version has deployment settings
Entity Constraints
Referential Integrity
•	Cascade delete from Projects to dependent entities
•	Restrict delete for Models with active Chat_Sessions
•	Cascade update for Document processing status changes
Business Rules
•	Model size constraints based on hardware capabilities
•	Document format validation before processing
•	Training session uniqueness per model/timestamp
•	Checkpoint retention policies (max 50 per model)
•	Vector embedding dimension consistency (384/768 dimensions)
Performance Considerations
Denormalization Points
•	Model performance metrics cached in Models table
•	Document statistics aggregated in Projects table
•	Recent chat messages materialized for quick access
•	Training progress percentage stored redundantly
Partitioning Strategy
•	Time-based partitioning for Training_Metrics (monthly)
•	Size-based partitioning for Vector_Embeddings (per collection)
•	Separate storage for large BLOB data (model files, embeddings)
X
Core Database Schema
Table Name: projects
Purpose: Master table for managing ML projects and their lifecycle
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing project identifier
name	TEXT NOT NULL	User-defined project name with UNIQUE constraint
description	TEXT	Project description and objectives
created_at	TIMESTAMP DEFAULT CURRENT_TIMESTAMP	Project creation timestamp
updated_at	TIMESTAMP	Last modification timestamp with trigger update
status	TEXT CHECK(status IN ('active','archived','deleted'))	Project lifecycle status
settings	JSON	Project-specific configuration stored as JSON
metadata	JSON	Custom user-defined metadata fields
Table Name: ml_models
Purpose: Registry for trained models with versioning and metadata
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing model identifier
project_id	INTEGER NOT NULL	Foreign key to projects table with CASCADE
name	TEXT NOT NULL	Model name with version suffix
version	TEXT NOT NULL	Semantic version (major.minor.patch)
architecture	TEXT CHECK(architecture IN ('1B','3B','7B'))	Model parameter size
base_model	TEXT	Parent model identifier for fine-tuned models
model_path	TEXT NOT NULL	Filesystem path to model artifacts
onnx_path	TEXT	Path to ONNX-converted model
quantization_type	TEXT CHECK(quantization_type IN ('INT4','INT8','FP16','FP32'))	Model quantization level
parameters_count	BIGINT	Exact parameter count
model_size_mb	REAL	Model size in megabytes
created_at	TIMESTAMP DEFAULT CURRENT_TIMESTAMP	Model creation timestamp
training_duration_seconds	INTEGER	Total training time
training_metrics	JSON	Final training metrics (loss, accuracy, etc.)
performance_metrics	JSON	Inference benchmarks by hardware
is_active	BOOLEAN DEFAULT 1	Active model flag for quick filtering
UNIQUE(project_id, name, version)		Composite unique constraint
Table Name: training_sessions
Purpose: Track individual training runs with configuration and results
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing session identifier
model_id	INTEGER NOT NULL	Foreign key to ml_models table
started_at	TIMESTAMP DEFAULT CURRENT_TIMESTAMP	Training start timestamp
completed_at	TIMESTAMP	Training completion timestamp
status	TEXT CHECK(status IN ('running','completed','failed','cancelled'))	Session status
training_config	JSON NOT NULL	Complete training hyperparameters
resource_allocation	JSON	IDRAlloc configuration used
final_loss	REAL	Final training loss value
best_validation_score	REAL	Best achieved validation metric
checkpoint_count	INTEGER DEFAULT 0	Number of saved checkpoints
error_log	TEXT	Error messages if failed
Table Name: model_checkpoints
Purpose: Store training checkpoints for recovery and model selection
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing checkpoint identifier
training_session_id	INTEGER NOT NULL	Foreign key to training_sessions
epoch	INTEGER NOT NULL	Epoch number when saved
global_step	BIGINT	Global training step counter
checkpoint_path	TEXT NOT NULL	Filesystem path to checkpoint
loss	REAL	Loss value at checkpoint
validation_score	REAL	Validation metric at checkpoint
is_best	BOOLEAN DEFAULT 0	Flag for best performing checkpoint
created_at	TIMESTAMP DEFAULT CURRENT_TIMESTAMP	Checkpoint creation time
file_size_mb	REAL	Checkpoint file size
Table Name: resource_allocation_profiles
Purpose: Store reusable resource allocation configurations
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing profile identifier
name	TEXT NOT NULL UNIQUE	Profile name for quick selection
allocation_mode	TEXT CHECK(allocation_mode IN ('Legacy','Hybrid','Auto'))	IDRAlloc mode
gpu_memory_limit_mb	INTEGER	GPU VRAM limit in MB
cpu_memory_limit_mb	INTEGER	System RAM limit in MB
nvme_swap_path	TEXT	Path for NVMe virtual memory
nvme_swap_size_gb	INTEGER	Virtual memory allocation size
priority	TEXT CHECK(priority IN ('low','normal','high'))	Process priority
thermal_limit_celsius	INTEGER	Temperature throttling threshold
config_json	JSON	Advanced configuration parameters
is_default	BOOLEAN DEFAULT 0	Default profile flag
Table Name: system_settings
Purpose: Application-wide configuration and preferences
FIELD	DATA TYPE	DESCRIPTION
key	TEXT PRIMARY KEY	Setting identifier
value	TEXT	Setting value (cast as needed)
category	TEXT NOT NULL	Setting category for grouping
data_type	TEXT CHECK(data_type IN ('string','integer','boolean','json'))	Value data type
description	TEXT	Setting description for UI
is_user_configurable	BOOLEAN DEFAULT 1	User-editable flag
updated_at	TIMESTAMP DEFAULT CURRENT_TIMESTAMP	Last update timestamp
X
Document Management Schema
Overview
Tables supporting multi-format document ingestion, processing, chunking, and RAG implementation for MikroDok's document-to-model pipeline.
Document Collections
Table Name: document_collections Purpose: Organize documents into logical groups for training and RAG operations
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing collection identifier
name	TEXT NOT NULL	User-defined collection name, unique per project
project_id	INTEGER NOT NULL	Foreign key to projects table
description	TEXT	Optional collection description
created_at	TIMESTAMP	Collection creation timestamp
updated_at	TIMESTAMP	Last modification timestamp
metadata	JSON	Additional collection properties (tags, settings)
Documents
Table Name: documents Purpose: Store document metadata and processing status for all ingested files
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing document identifier
collection_id	INTEGER NOT NULL	Foreign key to document_collections
filename	TEXT NOT NULL	Original filename with extension
file_path	TEXT NOT NULL	Relative path to stored document file
file_hash	TEXT NOT NULL	SHA-256 hash for deduplication and integrity
file_size	INTEGER	File size in bytes
format	TEXT NOT NULL	Document format (PDF, DOCX, TXT, HTML, MD)
status	TEXT NOT NULL	Processing status (pending, processing, completed, failed)
processing_started_at	TIMESTAMP	Processing start time
processing_completed_at	TIMESTAMP	Processing completion time
error_message	TEXT	Error details if processing failed
metadata	JSON	Extracted metadata (author, creation_date, properties)
created_at	TIMESTAMP	Document addition timestamp
Document Chunks
Table Name: document_chunks Purpose: Store processed text chunks for training and retrieval
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing chunk identifier
document_id	INTEGER NOT NULL	Foreign key to documents table
chunk_index	INTEGER NOT NULL	Sequential chunk number within document
content	TEXT NOT NULL	Actual text content of chunk
start_char	INTEGER	Starting character position in original document
end_char	INTEGER	Ending character position in original document
token_count	INTEGER	Number of tokens in chunk
chunk_hash	TEXT	Hash of chunk content for deduplication
metadata	JSON	Additional chunk properties (page_number, section_title)
created_at	TIMESTAMP	Chunk creation timestamp
Document Embeddings
Table Name: document_embeddings Purpose: Store vector embeddings for semantic search and retrieval
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing embedding identifier
chunk_id	INTEGER NOT NULL	Foreign key to document_chunks
model_name	TEXT NOT NULL	Embedding model used (e.g., all-MiniLM-L6-v2)
embedding_blob_id	INTEGER	Foreign key to blob_storage for vector data
dimension	INTEGER NOT NULL	Vector dimension size
created_at	TIMESTAMP	Embedding generation timestamp
Extraction Results
Table Name: extraction_results Purpose: Store structured data extracted from documents (tables, images, metadata)
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing extraction identifier
document_id	INTEGER NOT NULL	Foreign key to documents table
extraction_type	TEXT NOT NULL	Type of extraction (table, image, metadata)
content	JSON	Extracted structured content
confidence_score	REAL	Extraction confidence (0.0-1.0)
page_number	INTEGER	Source page number if applicable
bounding_box	JSON	Location coordinates in document
created_at	TIMESTAMP	Extraction timestamp
Document Processing Queue
Table Name: document_processing_queue Purpose: Manage document processing workflow and batch operations
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing queue identifier
document_id	INTEGER NOT NULL	Foreign key to documents table
priority	INTEGER DEFAULT 5	Processing priority (1-10, higher = more urgent)
operation	TEXT NOT NULL	Operation type (ingest, chunk, embed, extract)
status	TEXT NOT NULL	Queue status (pending, processing, completed, failed)
retry_count	INTEGER DEFAULT 0	Number of retry attempts
scheduled_at	TIMESTAMP	Scheduled processing time
started_at	TIMESTAMP	Actual processing start time
completed_at	TIMESTAMP	Processing completion time
error_details	JSON	Detailed error information if failed
Document Quality Metrics
Table Name: document_quality_metrics Purpose: Track document quality scores and validation results
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing metric identifier
document_id	INTEGER NOT NULL	Foreign key to documents table
overall_score	REAL	Overall quality score (0.0-100.0)
text_quality	REAL	Text extraction quality score
ocr_confidence	REAL	OCR confidence if applicable
completeness_score	REAL	Document completeness metric
duplicate_content_ratio	REAL	Percentage of duplicate content
validation_warnings	JSON	Array of validation warnings
validation_errors	JSON	Array of validation errors
evaluated_at	TIMESTAMP	Quality evaluation timestamp
Unique Constraints and Indexes
•	UNIQUE(collection_id, filename) on documents
•	UNIQUE(document_id, chunk_index) on document_chunks
•	INDEX on file_hash for deduplication checks
•	INDEX on status for queue management
•	INDEX on chunk_id for embedding lookups
X
Training and Monitoring Schema
Purpose
Captures model training lifecycle, performance metrics, resource utilization, and real-time monitoring data for MikroDok's ML operations.
Training Sessions Table
Table Name: training_sessions Purpose: Master record for each training run with configuration and status tracking
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing session identifier
model_id	INTEGER NOT NULL	Foreign key to ml_models table
start_time	TIMESTAMP	Training start timestamp with timezone
end_time	TIMESTAMP	Training completion timestamp (NULL if active)
status	TEXT CHECK	Current status: 'initializing', 'training', 'paused', 'completed', 'failed', 'cancelled'
total_epochs	INTEGER	Configured number of training epochs
batch_size	INTEGER	Training batch size configuration
learning_rate	REAL	Initial learning rate value
optimizer_type	TEXT	Optimizer algorithm (Adam, SGD, etc.)
allocation_mode	TEXT	Resource allocation: 'legacy', 'hybrid', 'auto_idralloc'
training_config	JSON	Complete hyperparameter configuration
error_message	TEXT	Error details if status='failed'
created_by	TEXT	User identifier for audit trail
Training Metrics Table
Table Name: training_metrics Purpose: Time-series storage of training performance metrics
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing metric identifier
session_id	INTEGER NOT NULL	Foreign key to training_sessions
epoch	INTEGER NOT NULL	Current epoch number
batch	INTEGER	Current batch within epoch
timestamp	TIMESTAMP	Metric recording timestamp
loss	REAL	Training loss value
validation_loss	REAL	Validation loss if applicable
accuracy	REAL	Model accuracy percentage
perplexity	REAL	Language model perplexity score
learning_rate	REAL	Current learning rate (may change during training)
gradient_norm	REAL	Gradient magnitude for stability monitoring
tokens_per_second	REAL	Training throughput metric
Resource Monitoring Table
Table Name: resource_monitoring Purpose: Real-time hardware resource utilization tracking
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing monitor record identifier
session_id	INTEGER NOT NULL	Foreign key to training_sessions
timestamp	TIMESTAMP	Measurement timestamp (1-second intervals)
gpu_utilization	REAL	GPU usage percentage (0-100)
gpu_memory_used	INTEGER	GPU VRAM usage in MB
gpu_memory_total	INTEGER	Total GPU VRAM available in MB
gpu_temperature	REAL	GPU temperature in Celsius
cpu_utilization	REAL	CPU usage percentage across all cores
ram_used	INTEGER	System RAM usage in MB
ram_total	INTEGER	Total system RAM in MB
swap_used	INTEGER	Virtual memory usage in MB
nvme_read_speed	REAL	NVMe read throughput in MB/s
nvme_write_speed	REAL	NVMe write throughput in MB/s
memory_bridge_active	BOOLEAN	IDRAlloc memory bridging status
Training Checkpoints Table
Table Name: training_checkpoints Purpose: Checkpoint management for training state preservation
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing checkpoint identifier
session_id	INTEGER NOT NULL	Foreign key to training_sessions
epoch	INTEGER NOT NULL	Epoch number at checkpoint
step	INTEGER	Training step within epoch
checkpoint_path	TEXT NOT NULL	File system path to checkpoint files
model_state_hash	TEXT	SHA-256 hash of model parameters
optimizer_state_hash	TEXT	SHA-256 hash of optimizer state
loss	REAL	Loss value at checkpoint
validation_metrics	JSON	Validation scores at checkpoint time
file_size	INTEGER	Checkpoint file size in bytes
is_best	BOOLEAN	Flag for best performing checkpoint
created_at	TIMESTAMP	Checkpoint creation timestamp
retention_policy	TEXT	Retention rule: 'permanent', 'auto_delete', 'milestone'
Training Events Table
Table Name: training_events Purpose: Audit log of significant training events and milestones
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing event identifier
session_id	INTEGER NOT NULL	Foreign key to training_sessions
event_type	TEXT CHECK	Event category: 'start', 'pause', 'resume', 'checkpoint', 'error', 'warning', 'milestone'
event_timestamp	TIMESTAMP	When event occurred
event_data	JSON	Event-specific data payload
severity	TEXT	Log level: 'info', 'warning', 'error', 'critical'
message	TEXT	Human-readable event description
Memory Allocation Table
Table Name: memory_allocations Purpose: Track IDRAlloc memory distribution across tiers
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing allocation identifier
session_id	INTEGER NOT NULL	Foreign key to training_sessions
timestamp	TIMESTAMP	Allocation snapshot timestamp
layer_group	TEXT	Model layer group identifier
memory_tier	TEXT CHECK	Allocation tier: 'gpu_vram', 'system_ram', 'nvme_swap'
size_mb	INTEGER	Memory allocation size in MB
access_frequency	INTEGER	Access count since last reallocation
last_accessed	TIMESTAMP	Last access timestamp for LRU tracking
allocation_strategy	TEXT	Strategy used: 'frequency', 'size', 'manual'
Performance Benchmarks Table
Table Name: performance_benchmarks Purpose: Store model performance test results
FIELD	DATA TYPE	DESCRIPTION
id	INTEGER PRIMARY KEY	Auto-incrementing benchmark identifier
model_id	INTEGER NOT NULL	Foreign key to ml_models
session_id	INTEGER	Associated training session if applicable
benchmark_type	TEXT	Test type: 'inference_speed', 'memory_usage', 'quality'
hardware_config	JSON	Hardware specification during benchmark
test_timestamp	TIMESTAMP	When benchmark was executed
tokens_per_second	REAL	Inference throughput
first_token_latency	REAL	Time to first token in milliseconds
memory_peak_mb	INTEGER	Maximum memory usage during test
quantization_type	TEXT	Model quantization: 'int4', 'int8', 'fp16', 'fp32'
test_parameters	JSON	Complete benchmark configuration
results	JSON	Detailed benchmark results
Key Design Decisions:
•	Separate metrics table for high-frequency time-series data with efficient storage
•	JSON columns for flexible configuration storage while maintaining queryable fields
•	Resource monitoring at 1-second intervals for real-time dashboard updates
•	Checkpoint deduplication through hash comparison
•	Event logging for comprehensive training audit trail
•	Memory allocation tracking specifically for IDRAlloc optimization
•	Performance benchmarks linked to both models and training sessions
X
MikroDok Database Indexing Strategy
Overview
Strategic indexing design optimized for ML workload patterns, balancing query performance with write overhead during intensive training operations.
Primary Index Categories
1. Clustered Indexes
•	ml_models table: Clustered on id for sequential access during training
•	training_checkpoints table: Clustered on (model_id, epoch) for checkpoint retrieval
•	documents table: Clustered on id for document processing workflows
2. Covering Indexes
•	Model Query Index: idx_models_active_query 
o	Columns: (is_archived, created_at, name, version, parameters_count)
o	Covers common dashboard queries without table access
•	Training Status Index: idx_training_active_status 
o	Columns: (status, started_at, model_id, current_epoch, total_epochs)
o	Optimizes real-time training monitoring
3. Composite Indexes
•	Document Search: idx_documents_collection_type 
o	Columns: (collection_id, file_type, processing_status)
•	Metrics Retrieval: idx_metrics_model_epoch 
o	Columns: (model_id, epoch, metric_type)
•	Resource Tracking: idx_resources_session_time 
o	Columns: (training_session_id, timestamp, resource_type)
Specialized ML Indexes
4. Vector Search Optimization
•	Embedding Lookup: idx_embeddings_doc_chunk 
o	Columns: (document_id, chunk_index)
o	Supports RAG retrieval patterns
•	Similarity Search: idx_vector_metadata 
o	Columns: (collection_id, embedding_norm, created_at)
o	Accelerates k-NN operations
5. Temporal Indexes
•	Time-Series Metrics: idx_metrics_timestamp 
o	Columns: (timestamp, model_id, metric_type)
o	Optimizes performance graph queries
•	Audit Trail: idx_audit_timestamp_user 
o	Columns: (timestamp DESC, user_action, model_id)
Write-Optimized Indexes
6. Deferred Index Updates
•	Training metrics tables use WITHOUT ROWID optimization
•	Batch index updates during checkpoint saves
•	Temporary index dropping during bulk document imports
7. Partial Indexes
•	Active Models Only: idx_models_active 
o	Condition: WHERE is_archived = 0
•	Failed Training: idx_training_failed 
o	Condition: WHERE status = 'failed'
•	Unprocessed Documents: idx_docs_pending 
o	Condition: WHERE processing_status = 'pending'
Index Maintenance Strategy
8. Automatic Optimization
•	ANALYZE execution after every 1000 document imports
•	Index statistics update during training idle periods
•	Automatic index rebuilding threshold at 30% fragmentation
9. Memory-Mapped Indexes
•	Configure 1GB mmap_size for index pages
•	Prioritize frequently accessed indexes in cache
•	Separate index file for vector embeddings
Performance Considerations
10. Index Selection Rules
•	Maximum 5 indexes per table to minimize write overhead
•	Avoid indexing columns with >50% NULL values
•	Exclude BLOB columns from composite indexes
•	Index cardinality analysis before creation
11. Query Plan Optimization
•	Force index hints for complex training queries
•	Maintain index statistics accuracy with regular ANALYZE
•	Monitor slow query log for missing indexes
Index Naming Convention
•	Primary Keys: pk_[table_name]
•	Foreign Keys: fk_[table]_[referenced_table]
•	Unique Constraints: uk_[table]_[columns]
•	Regular Indexes: idx_[table]_[purpose]
•	Partial Indexes: idx_[table]_[condition]_partial
X
Transaction Management - MikroDok Database Design
Overview
Transaction management strategy for MikroDok focuses on maintaining data integrity during long-running ML operations while ensuring responsive UI performance through asynchronous patterns and intelligent isolation levels.
Core Transaction Strategies
Write-Ahead Logging (WAL) Mode
•	Configuration: Enable WAL mode for concurrent read operations during training
•	Benefits: Allows multiple readers while maintaining single writer constraint
•	Checkpoint Strategy: Auto-checkpoint at 1000 pages with TRUNCATE mode
•	Synchronization: NORMAL synchronous mode balancing durability and performance
Transaction Isolation Levels
•	Training Operations: IMMEDIATE transactions to prevent deadlocks
•	Read Operations: DEFERRED transactions for maximum concurrency
•	Model Updates: EXCLUSIVE transactions for critical model state changes
•	Resource Monitoring: Read-only transactions with snapshot isolation
Long-Running Operation Management
Training Session Transactions
•	Savepoint Architecture: Nested savepoints for epoch boundaries
•	Checkpoint Frequency: Transaction commit every epoch completion
•	Progress Tracking: Separate micro-transactions for metrics updates
•	Rollback Points: Maintain last three stable checkpoints
Batch Processing Patterns
•	Document Processing: 100-document transaction batches
•	Embedding Generation: 1000-vector insert batches
•	Index Updates: Deferred index maintenance during bulk operations
•	Memory Management: Transaction size limits based on available RAM
Concurrency Control
Connection Pool Management
•	Write Connection: Single dedicated connection for all write operations
•	Read Pool: 5 read-only connections for parallel queries
•	Thread Affinity: Thread-local storage for connection assignment
•	Queue Management: Write operation queue with priority scheduling
Lock Timeout Strategies
•	Default Timeout: 5 seconds for normal operations
•	Training Timeout: 30 seconds for model update transactions
•	Retry Logic: Exponential backoff (100ms, 500ms, 2s) for busy scenarios
•	Deadlock Detection: Automatic rollback and retry mechanism
Atomic Operation Patterns
Model State Updates
•	Pre-Update Validation: Verify model integrity before modifications
•	State Transition: Atomic status changes with timestamp logging
•	Dependency Updates: CASCADE operations for related entities
•	Audit Trail: Trigger-based history tracking within transaction
Training Checkpoint Management
•	Double-Write Pattern: Write checkpoint metadata before binary data
•	Verification Step: Post-write integrity check within transaction
•	Cleanup Operations: Old checkpoint removal in separate transaction
•	Recovery Markers: Transaction log entries for crash recovery
Error Handling and Recovery
Transaction Rollback Strategies
•	Automatic Rollback: On constraint violations and integrity errors
•	Partial Rollback: Savepoint-based recovery for batch operations
•	State Restoration: Application-level state synchronization
•	User Notification: Clear error messaging with recovery options
Crash Recovery Procedures
•	Journal Recovery: Automatic rollback of incomplete transactions
•	Checkpoint Restoration: Load last valid model state
•	Progress Recovery: Resume training from last committed epoch
•	Data Validation: Post-recovery integrity checks
Performance Optimization
Transaction Batching
•	Write Coalescing: Combine multiple small writes into batches
•	Lazy Commits: Defer non-critical updates for batch processing
•	Priority Queuing: Real-time metrics bypass batch queue
•	Memory Buffering: In-memory accumulation before disk writes
Resource-Aware Transactions
•	Memory Monitoring: Transaction size limits based on free RAM
•	Disk Space Checks: Pre-transaction storage availability verification
•	CPU Throttling: Transaction pacing during intensive operations
•	Temperature Management: Pause transactions on thermal warnings
Monitoring and Diagnostics
Transaction Metrics
•	Duration Tracking: Log transactions exceeding 1 second
•	Lock Wait Analysis: Monitor contention patterns
•	Rollback Frequency: Track failure rates by operation type
•	Throughput Metrics: Transactions per second by category
Debug Capabilities
•	Transaction Logging: Optional verbose logging for debugging
•	Lock Visualization: Real-time lock holder identification
•	Query Plans: EXPLAIN output for transaction queries
•	Performance Profiling: Transaction-level timing analysis
X
MikroDok Database Security Implementation
Overview
Security implementation for MikroDok's SQLite database focusing on offline desktop environment protection, data sovereignty, and compliance with privacy regulations while maintaining high performance for ML operations.
Encryption Strategy
Database-Level Encryption
•	SQLCipher Integration: AES-256 encryption for entire database file
•	Key Derivation: PBKDF2-SHA512 with 256,000 iterations for master key
•	Page-Level Encryption: 4096-byte pages encrypted independently
•	Memory Protection: Secure key storage in protected memory regions
Model Artifact Encryption
•	Separate Encryption: Model files encrypted outside database using AES-256-GCM
•	Chunked Encryption: 1MB chunks for streaming decryption during loading
•	Key Rotation: Periodic re-encryption with versioned keys
•	Integrity Verification: HMAC-SHA256 for tamper detection
Access Control
Application-Level Security
•	OS Authentication: Integration with Windows/macOS/Linux user credentials
•	Session Management: Time-based session tokens with 24-hour expiry
•	Role-Based Access: Read-only, Standard User, Admin roles
•	Audit Logging: All model access and modifications tracked
Database Connection Security
•	Connection Encryption: Memory-encrypted connection strings
•	Exclusive Locking: Single-process access during sensitive operations
•	Timeout Configuration: 30-second command timeout for long operations
•	Connection Pooling: Secure pool with 5-connection limit
Data Protection Measures
Sensitive Data Handling
•	PII Anonymization: Hash-based pseudonymization for user data
•	Document Sanitization: Automatic PII detection and masking
•	Secure Deletion: 7-pass DoD 5220.22-M standard for data wiping
•	Memory Clearing: Explicit zeroing of sensitive data in RAM
Model Protection
•	Checksum Verification: SHA-256 hashes for model integrity
•	Version Control: Cryptographic signatures for model versions
•	Export Controls: Watermarking and usage tracking for exported models
•	License Enforcement: Encrypted license keys tied to hardware
SQL Injection Prevention
Query Security
•	Parameterized Queries: All dynamic queries use parameter binding
•	Input Validation: Whitelist-based validation for all user inputs
•	Stored Procedures: Limited use for complex operations only
•	Query Logging: Suspicious query pattern detection
Schema Protection
•	Minimal Permissions: Application uses least-privilege database user
•	Schema Locking: Production schema modification restrictions
•	Trigger Limitations: No user-defined triggers allowed
•	View-Based Access: Restricted data access through views
Compliance Features
GDPR/HIPAA Compliance
•	Right to Erasure: Complete data removal capabilities
•	Data Portability: Secure export in encrypted formats
•	Access Logs: Comprehensive audit trail for compliance
•	Consent Management: Explicit consent tracking for data processing
Data Residency
•	Local Storage Only: No cloud synchronization of sensitive data
•	Geographic Restrictions: Configurable data location policies
•	Cross-Border Controls: Export restrictions for certain regions
•	Offline Validation: License and compliance checks without internet
Backup Security
Encrypted Backups
•	Backup Encryption: Separate encryption keys for backup files
•	Incremental Security: Only changed pages in encrypted backups
•	Secure Storage: Designated secure backup locations only
•	Version History: Encrypted backup chain with 30-day retention
Recovery Security
•	Authentication Required: Multi-factor for backup restoration
•	Integrity Checks: Automatic verification before restoration
•	Selective Restore: Granular recovery without full exposure
•	Audit Trail: All recovery operations logged
Runtime Security
Memory Protection
•	Secure Allocator: Custom memory allocation for sensitive data
•	Anti-Debugging: Protection against memory inspection
•	Stack Protection: Buffer overflow prevention mechanisms
•	Heap Randomization: ASLR for memory layout
Process Isolation
•	Sandboxing: Database operations in isolated process
•	IPC Security: Encrypted inter-process communication
•	Resource Limits: Prevent resource exhaustion attacks
•	Crash Protection: Secure cleanup on abnormal termination
Monitoring and Alerting
Security Monitoring
•	Access Anomalies: Unusual access pattern detection
•	Performance Anomalies: Potential attack indicator monitoring
•	File Integrity: Real-time database file monitoring
•	Resource Usage: Abnormal resource consumption alerts
Incident Response
•	Automatic Lockdown: Suspicious activity triggers protection
•	Evidence Collection: Forensic data preservation
•	Recovery Mode: Secure mode for incident investigation
•	Notification System: Admin alerts for security events
X
Performance Optimization Techniques
SQLite Configuration
Pragma Settings
•	PRAGMA journal_mode = WAL - Enable Write-Ahead Logging for concurrent read access during training
•	PRAGMA synchronous = NORMAL - Balance between safety and performance for desktop environment
•	PRAGMA cache_size = 50000 - 50MB cache for model metadata and frequent queries
•	PRAGMA temp_store = MEMORY - Use RAM for temporary tables during batch operations
•	PRAGMA mmap_size = 1073741824 - 1GB memory-mapped I/O for large table scans
Model Storage Strategy
External Storage for Large Objects
•	Store model files on NVMe SSD with only metadata in SQLite
•	Use 256KB chunks for model artifacts to optimize disk I/O
•	Implement lazy loading for model parameters during inference
•	Maintain separate model cache directory with LRU eviction policy
Compression Techniques
•	Apply zstd compression for model checkpoints (30-40% reduction)
•	Store training logs with incremental compression
•	Use binary format for embedding vectors instead of JSON
Query Optimization
Denormalization for Hot Paths
•	Denormalize latest model metrics into models table
•	Cache aggregate statistics in summary tables
•	Maintain materialized views for dashboard queries
•	Store computed inference speeds in model registry
Batch Processing
•	Use prepared statements for bulk document insertions
•	Implement write batching with 1000-record transactions
•	Queue training metrics updates every 5 seconds
•	Aggregate resource monitoring data before storage
Memory Management
Connection Pooling
•	Single writer connection with multiple reader connections
•	Thread-local storage for connection management
•	Connection limit of 8 concurrent readers
•	Automatic connection recycling after 1000 operations
Buffer Management
•	Pre-allocate buffers for embedding operations
•	Use memory-mapped files for large document processing
•	Implement circular buffers for real-time metrics
•	Cap in-memory cache at 10% of system RAM
Indexing Optimization
Covering Indexes
•	Create covering indexes for frequently accessed model queries
•	Include commonly selected columns to avoid table lookups
•	Optimize for read-heavy dashboard operations
•	Balance index size with query performance gains
Partial Indexes
•	Index only active models and non-archived documents
•	Create conditional indexes for specific status values
•	Exclude NULL values from optional field indexes
•	Target indexes for time-range queries
Vacuum and Maintenance
Auto-Vacuum Strategy
•	Enable incremental auto-vacuum for gradual space reclamation
•	Schedule full vacuum during idle periods
•	Monitor fragmentation levels with 20% threshold
•	Coordinate vacuum with checkpoint operations
Statistics Updates
•	Run ANALYZE after bulk operations
•	Update statistics after 10% data change
•	Maintain query plan stability during training
•	Monitor slow query patterns for optimization
Resource Monitoring Integration
Lightweight Metrics Collection
•	Sample GPU/CPU metrics at 1-second intervals
•	Batch insert monitoring data every 10 seconds
•	Use ring buffer tables for time-series data
•	Automatic old data pruning after 7 days
Asynchronous Operations
•	Defer non-critical updates to background threads
•	Use SQLite's async VFS for logging operations
•	Implement write queues for training metrics
•	Separate UI queries from heavy analytical queries
X
Migration and Versioning Strategy
Schema Version Control
Version Tracking Table
•	schema_versions table maintains migration history
•	Each migration has unique ID, timestamp, checksum, and rollback capability
•	Semantic versioning (MAJOR.MINOR.PATCH) for schema changes
Migration Framework
Migration Files Structure
•	Sequential numbering: 001_initial_schema.sql, 002_add_rag_tables.sql
•	Each file contains UP and DOWN migrations
•	Transactional execution with automatic rollback on failure
Migration Categories
•	Breaking Changes: New major version (2.0.0)
•	Feature Additions: New minor version (1.1.0)
•	Bug Fixes/Optimizations: Patch version (1.0.1)
Backward Compatibility
Compatibility Rules
•	Support 2 major versions backward compatibility
•	Deprecation warnings for 1 full version cycle
•	Data transformation utilities for major upgrades
Column Evolution Strategy
•	ADD COLUMN with DEFAULT values for non-breaking changes
•	Create new tables instead of modifying critical structures
•	Use views for backward-compatible interfaces
Data Migration Patterns
Large Object Migration
•	Chunk-based migration for model files and embeddings
•	Progress tracking with resumable migrations
•	Parallel processing for independent data sets
Zero-Downtime Migrations
•	Shadow table creation for structural changes
•	Online data copying with triggers for sync
•	Atomic table swap at completion
Version Detection
Application-Database Compatibility
•	Startup version check against schema_versions
•	Automatic migration prompt for outdated schemas
•	Force upgrade option for major versions
Migration State Management
•	PENDING, IN_PROGRESS, COMPLETED, FAILED states
•	Partial migration recovery mechanisms
•	Migration lock to prevent concurrent executions
Testing Strategy
Migration Testing
•	Automated forward/backward migration tests
•	Data integrity validation post-migration
•	Performance impact assessment
Rollback Procedures
•	Point-in-time recovery before migration
•	Automatic backup creation pre-migration
•	One-click rollback for last 3 migrations
Special Considerations
Model Artifact Handling
•	External file references preserved across migrations
•	Path updates for relocated model storage
•	Checksum verification for file integrity
Training State Preservation
•	Checkpoint compatibility across versions
•	Training resume capability after migration
•	Metric history continuity
User Data Protection
•	No data loss guarantees for all migrations
•	Export/import utilities for major transitions
•	Clear user communication for breaking changes
X
Backup and Recovery Procedures - MikroDok Database
Overview
Desktop-optimized backup strategy ensuring data integrity for offline ML operations with minimal performance impact during active training sessions.
Backup Strategy
Three-Tier Backup Approach
•	Continuous Checkpointing: SQLite WAL mode with automatic checkpoint intervals
•	Scheduled Full Backups: Daily automated backups during idle periods
•	On-Demand Snapshots: User-triggered backups before critical operations
Backup Components
•	Database Files: Main .db file, WAL journal, shared memory files
•	Model Artifacts: Separate versioned storage with reference tracking
•	Configuration State: Application settings and user preferences
•	Recovery Metadata: Backup manifests with integrity checksums
Backup Implementation
Online Backup API
•	Utilizes SQLite's backup API for live database copying
•	Non-blocking operation during model training
•	Progress callback integration with UI
•	Automatic retry on busy database conditions
Incremental Backup System
•	Page-level change tracking since last backup
•	Differential backups every 4 hours during active use
•	Compression using ZSTD for 60-70% size reduction
•	Retention policy: 7 daily, 4 weekly, 3 monthly backups
Model Checkpoint Integration
•	Synchronized with training epoch completions
•	Atomic backup of database + model state
•	Rollback capability to any checkpoint
•	Automatic cleanup of orphaned checkpoints
Recovery Procedures
Automated Recovery Detection
•	Integrity check on application startup
•	WAL journal analysis for incomplete transactions
•	Automatic rollback to last consistent state
•	User notification of recovery actions
Point-in-Time Recovery
•	Restore to specific training epoch
•	Selective model version recovery
•	Document collection preservation
•	Configuration rollback options
Disaster Recovery
•	Shadow copy creation before major operations
•	Emergency recovery mode with minimal UI
•	Data salvage tools for corrupted databases
•	Export functionality for partial data extraction
Performance Considerations
Backup Scheduling
•	Background thread execution
•	I/O throttling during active training
•	NVMe-optimized sequential writes
•	Memory-mapped file exclusion during backup
Storage Management
•	Automatic pruning of old backups
•	Compression of inactive backups
•	External drive support for archives
•	Cloud sync integration (optional, manual)
Data Integrity Measures
Verification Procedures
•	SHA-256 checksums for all backup files
•	Page-level corruption detection
•	Model artifact validation
•	Test restoration in isolated environment
Monitoring and Alerts
•	Backup failure notifications
•	Storage space warnings at 80% capacity
•	Corruption detection alerts
•	Recovery success confirmation
User-Controlled Options
Backup Preferences
•	Custom backup locations
•	Frequency configuration
•	Compression level selection
•	Automatic vs manual backup modes
Recovery Options
•	Quick recovery (latest backup)
•	Advanced recovery wizard
•	Selective data restoration
•	Merge capabilities for partial backups
X

