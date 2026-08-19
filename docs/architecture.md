# MikroDok Architecture Documentation

## Overview

MikroDok follows a **three-layer architecture** designed for enterprise-grade ML operations on desktop hardware. The architecture prioritizes offline-first functionality, resource efficiency, and maintainability while handling complex operations like 12-24 hour model training sessions and real-time memory bridging across GPU/CPU/NVMe storage tiers.

## Architectural Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                      UI LAYER (Flet)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐  │
│  │ Dashboard   │ │ Doc Manager │ │ Model Bldr  │ │ Settings │  │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └────┬────┘  │
│         │               │               │             │        │
│         └───────────────┼───────────────┼─────────────┘        │
│                         ▼               ▼                      │
│              ┌─────────────────────────────────┐              │
│              │      Event Bus / Commands       │              │
│              └───────────────┬────────────────┘              │
└──────────────────────────────┼────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LOGIC LAYER (Pure Python)                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐  │
│  │ Doc Ingestion│ │  Training    │ │  IDRAlloc    │ │  RAG   │  │
│  │  Pipeline    │ │Orchestration │ │ Memory Mgmt  │ │Pipeline│  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────┬───┘  │
│         │                │                │               │      │
│         └────────────────┼────────────────┼───────────────┘      │
│                          ▼                ▼                      │
│              ┌─────────────────────────────────┐              │
│              │    Repository Pattern (Abstraction)             │
│              └───────────────┬────────────────┘              │
└──────────────────────────────┼────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER (SQLite)                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐  │
│  │  Documents  │ │   Models    │ │  Training   │ │ Vectors  │  │
│  │   & Chunks  │ │  Registry   │ │  Sessions   │ │Embeddings│  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Dependency Rules

1. **UI modules depend on Logic modules** (never reverse)
2. **Database modules accessed only through Logic layer repositories**
3. **Infrastructure modules can be used by all layers**
4. **No circular dependencies between modules at any level**

## Core Architectural Components

### 1. Application Core
- **Lifecycle Management**: Initialization, shutdown, crash recovery
- **Configuration Management**: Multi-source config with validation
- **State Persistence**: Auto-save, snapshots, recovery mechanisms
- **Event Bus**: Publish-subscribe pattern for loose coupling

### 2. Processing Pipeline
- **Document Ingestion**: Format detection, validation, batch processing
- **Content Extraction**: Multi-format with OCR and table support
- **Semantic Chunking**: Context-preserving segmentation
- **Quality Validation**: Scoring, deduplication, error recovery

### 3. Training Orchestration
- **Session Management**: Create, execute, pause, resume, terminate
- **Checkpoint Coordination**: Atomic operations, retention policies
- **Resource Allocation**: IDRAlloc integration for memory management
- **Progress Tracking**: Real-time metrics, ETA prediction

### 4. Memory Management (IDRAlloc)
- **Three-Tier Hierarchy**: GPU VRAM (Tier 1) → System RAM (Tier 2) → NVMe (Tier 3)
- **Dynamic Layer Distribution**: Access-pattern based placement
- **Predictive Preloading**: Computation graph analysis
- **Memory Bridge Controller**: DMA transfers with LRU eviction

### 5. User Experience Layer
- **Responsive UI**: Async operations, non-blocking interactions
- **Real-Time Monitoring**: Live dashboards with WebSocket-like updates
- **Progressive Workflows**: Guided complexity disclosure

### 6. Data Persistence
- **Hybrid Storage**: SQLite metadata + filesystem for binary assets
- **Optimized Indexing**: Covering indexes, partial indexes, temporal partitions
- **Transaction Management**: Savepoint architecture for long operations
- **Backup & Recovery**: Online backup API, point-in-time recovery

## Module Organization

```
src/modules/
├── logic/                    # Business logic (no UI, no DB direct access)
│   ├── application_lifecycle_lg/
│   ├── document_ingestion_lg/
│   ├── document_extraction_lg/
│   ├── document_chunking_lg/
│   ├── document_quality_lg/
│   ├── document_metadata_lg/
│   ├── training_orchestration_lg/
│   ├── checkpoint_management_lg/
│   ├── training_metrics_lg/
│   ├── training_data_pipeline_lg/
│   ├── model_optimization_lg/
│   ├── memory_allocation_lg/
│   ├── memory_bridging_lg/
│   ├── nvme_virtual_memory_lg/
│   ├── memory_optimization_lg/
│   ├── embedding_generation_lg/
│   ├── vector_search_lg/
│   ├── hybrid_search_lg/
│   ├── query_processor_lg/
│   ├── context_builder_lg/
│   ├── rag_orchestrator_lg/
│   ├── resource_monitor_lg/
│   ├── performance_optimizer_lg/
│   ├── resource_predictor_lg/
│   └── monitoring_aggregator_lg/
├── ui/                       # Flet UI components
│   ├── main_dashboard_ui/
│   ├── navigation_ui/
│   ├── system_monitor_ui/
│   ├── document_manager_ui/
│   ├── search_interface_ui/
│   ├── chat_interface_ui/
│   ├── model_builder_ui/
│   ├── model_registry_ui/
│   ├── settings_panel_ui/
│   ├── training_monitor_ui/
│   ├── checkpoint_viewer_ui/
│   ├── memory_monitor_ui/
│   ├── memory_config_ui/
│   ├── resource_dashboard_ui/
│   ├── monitoring_controls_ui/
│   ├── optimization_status_ui/
│   ├── dialog_components_ui/
│   ├── visualization_ui/
│   └── splash_screen_ui/
└── database/                 # Data persistence
    ├── app_state_db/
    ├── system_config_db/
    ├── documents_db/
    ├── document_collections_db/
    ├── document_queue_db/
    ├── document_quality_db/
    ├── training_sessions_db/
    ├── training_metrics_db/
    ├── checkpoints_db/
    ├── training_config_db/
    ├── vector_storage_db/
    ├── search_index_db/
    ├── search_cache_db/
    ├── rag_metadata_db/
    ├── resource_monitoring_db/
    ├── database_core_db/
    ├── blob_storage_db/
    └── chat_repository_db/
```

## Module Naming Convention

```
{domain}_{layer}
├── {subdomain}_{layer}
    └── {component}_{layer}/
        └── {component}_{layer}.py
```

**Layer Suffixes:**
- `_lg` = Logic layer
- `_ui` = UI layer
- `_db` = Database layer

## Communication Patterns

### UI → Logic: Event Bus / Commands
```python
# UI dispatches command
event_bus.publish("training.start", {
    "model_config": config,
    "documents": doc_ids,
    "allocation_mode": "Auto"
})

# Logic publishes progress events
event_bus.publish("training.progress", {
    "epoch": 5,
    "loss": 2.34,
    "gpu_util": 87.5
})
```

### Logic → Database: Repository Pattern
```python
# Logic uses repository interface
session_repo = SessionRepositoryDB()
session = session_repo.create(session_data)

# Repository handles all DB concerns
class SessionRepositoryDB:
    def create(self, data: dict) -> TrainingSession:
        with self.db.transaction() as conn:
            return self._insert(data, conn)
```

## Data Flow Architecture

### Training Flow
```
Document Upload
      │
      ▼
Format Detection ──▶ Content Extraction ──▶ Semantic Chunking
      │                    │                      │
      ▼                    ▼                      ▼
Quality Scoring      Metadata Extraction      Embedding Generation
      │                    │                      │
      └────────────────────┼──────────────────────┘
                           ▼
                    Vector Database (ChromaDB)
                           │
                           ▼
Model Configuration ──▶ Resource Allocation (IDRAlloc)
      │                    │
      ▼                    ▼
Training Loop ◀────── Checkpoint Management
      │
      ▼
Model Optimization ──▶ ONNX Conversion ──▶ Model Registry
```

### Inference Flow
```
User Query
     │
     ▼
Query Parser ──▶ Hybrid Search (Semantic + BM25)
     │                    │
     ▼                    ▼
Vector Search ◀───── Keyword Search
     │
     ▼
Result Fusion ──▶ Cross-Encoder Reranking
     │
     ▼
Context Window Construction
     │
     ▼
Model Loading (with IDRAlloc) ──▶ Token Generation ──▶ Response Streaming
```

## Key Design Principles

### SOLID Compliance
| Principle | Implementation |
|-----------|----------------|
| Single Responsibility | Each module handles one specific aspect |
| Open/Closed | Extension points for cloud sync, multi-user |
| Liskov Substitution | Interface-based design for swappable implementations |
| Interface Segregation | Focused interfaces for different consumer needs |
| Dependency Inversion | Core logic depends on abstractions |

### Additional Principles
- **Offline-First**: All core functionality operates without internet
- **Progressive Disclosure**: Complex features hidden behind simple interfaces
- **Fail-Safe Defaults**: Graceful degradation when resources constrained
- **Immutable State**: Training configurations and model metadata immutable once created

## Performance Optimization Points

| Layer | Optimization |
|-------|--------------|
| Logic | Caching at module boundaries, lazy loading, batch processing |
| UI | Virtualized lists, skeleton screens, async updates |
| Database | WAL mode, memory-mapped I/O, covering indexes, connection pooling |
| ML | Mixed precision, quantization, ONNX optimization, memory pooling |

## Quality Attributes

### Reliability
- Comprehensive error handling at module boundaries
- Automatic recovery mechanisms for training failures
- Data integrity through transactional boundaries
- Crash recovery with state reconstruction

### Performance
- Asynchronous operations for UI responsiveness
- Resource pooling for efficient memory usage
- Optimized data structures for ML workloads
- Profiling hooks for continuous monitoring

### Maintainability
- Clear module boundaries reducing coupling
- Consistent patterns across similar modules
- Comprehensive logging and monitoring interfaces
- Automated testing at unit, integration, and UI levels

### Security
- Offline-first design eliminating network attack vectors
- Encryption interfaces for sensitive model data
- Audit trail capabilities for compliance
- Secure defaults for all configurations

## Extensibility Considerations

### Future-Ready Design
- **Plugin Architecture**: Preparation for custom processors
- **API Gateway Pattern**: Potential cloud integration
- **Multi-Tenant Isolation**: Boundaries for future multi-user support
- **Modular Auth/Authorization**: Hooks for enterprise SSO

---

*Last Updated: 2025-01-15*
*Version: 0.1.0-alpha*