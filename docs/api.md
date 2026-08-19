# MikroDok API Reference

## Overview

This document describes the internal APIs, service interfaces, and event system for MikroDok. All APIs are designed for internal use within the three-layer architecture.

## Core Service APIs

### MLProcessingEngine

Main service for model training and inference operations.

```python
class MLProcessingEngine:
    """Core ML processing service."""
    
    async def train_model(
        self,
        config: TrainingConfig,
        documents: List[Document],
        allocation_mode: AllocationMode = AllocationMode.AUTO,
        progress_callback: Optional[Callable] = None
    ) -> TrainingResult:
        """Train a new language model."""
    
    async def load_model(
        self,
        model_id: str,
        allocation_mode: AllocationMode = AllocationMode.AUTO
    ) -> ModelHandle:
        """Load model for inference."""
    
    async def infer(
        self,
        model: ModelHandle,
        prompt: str,
        generation_config: GenerationConfig
    ) -> AsyncGenerator[str, None]:
        """Stream inference tokens."""
    
    async def optimize_model(
        self,
        model_id: str,
        quantization: QuantizationType = QuantizationType.INT4,
        target_platform: Platform = Platform.CURRENT
    ) -> OptimizedModel:
        """Convert and quantize model for deployment."""
```

### ResourceManager

Manages IDRAlloc resource allocation across GPU/CPU/NVMe.

```python
class ResourceManager:
    """Intelligent Dynamic Resource Allocation service."""
    
    def allocate(
        self,
        requirements: ResourceRequirements,
        mode: AllocationMode = AllocationMode.AUTO
    ) -> ResourceAllocation:
        """Allocate resources for operation."""
    
    def monitor(self) -> ResourceMetrics:
        """Get current resource utilization."""
    
    def predict(
        self,
        workload: WorkloadProfile
    ) -> PredictedRequirements:
        """Predict resource needs for workload."""
    
    def release(self, allocation_id: str) -> None:
        """Release allocated resources."""
    
    def switch_mode(
        self,
        new_mode: AllocationMode,
        graceful: bool = True
    ) -> bool:
        """Switch allocation mode at runtime."""
```

### DocumentProcessor

Handles document ingestion, processing, and indexing.

```python
class DocumentProcessor:
    """Document processing pipeline service."""
    
    async def ingest(
        self,
        files: List[Path],
        config: ProcessingConfig
    ) -> IngestionResult:
        """Process and index documents."""
    
    def chunk(
        self,
        content: str,
        config: ChunkingConfig
    ) -> List[Chunk]:
        """Split document into semantic chunks."""
    
    def embed(
        self,
        chunks: List[Chunk],
        model: EmbeddingModel = EmbeddingModel.MINILM_L6_V2
    ) -> List[Embedding]:
        """Generate embeddings for chunks."""
    
    def index(
        self,
        embeddings: List[Embedding],
        collection: str
    ) -> IndexResult:
        """Add embeddings to vector store."""
```

### ModelRegistry

Manages model lifecycle, versioning, and metadata.

```python
class ModelRegistry:
    """Model registry with versioning."""
    
    def register(
        self,
        model: TrainedModel,
        metadata: ModelMetadata
    ) -> ModelRecord:
        """Register trained model."""
    
    def version(
        self,
        model_id: str,
        version: str,
        changes: List[str]
    ) -> ModelVersion:
        """Create new model version."""
    
    def rollback(
        self,
        model_id: str,
        target_version: str
    ) -> ModelRecord:
        """Rollback to previous version."""
    
    def export(
        self,
        model_id: str,
        format: ExportFormat,
        config: ExportConfig
    ) -> ExportResult:
        """Export model for deployment."""
```

### VectorStore

Vector similarity search interface.

```python
class VectorStore:
    """Vector database interface."""
    
    def add(
        self,
        embeddings: List[Embedding],
        metadata: List[Dict]
    ) -> List[str]:
        """Add vectors to index."""
    
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Semantic similarity search."""
    
    def hybrid_search(
        self,
        query: str,
        query_vector: np.ndarray,
        top_k: int = 10,
        alpha: float = 0.5
    ) -> List[SearchResult]:
        """Combined semantic + keyword search."""
```

## Data Transfer Objects

### TrainingConfig

```python
@dataclass
class TrainingConfig:
    model_size: ModelSize          # 1B, 3B, 7B
    method: TrainingMethod         # FROM_SCRATCH, FINE_TUNE, QLORA
    batch_size: int
    learning_rate: float
    epochs: int
    optimizer: OptimizerType       # ADAM, ADAMW, SGD
    scheduler: SchedulerType       # COSINE, LINEAR, CONSTANT
    mixed_precision: bool = True
    gradient_accumulation: int = 1
    max_seq_length: int = 2048
    validation_split: float = 0.1
    early_stopping_patience: int = 3
```

### AllocationMode

```python
class AllocationMode(Enum):
    LEGACY = "Legacy"           # GPU only
    HYBRID = "Hybrid"           # CPU + GPU with bridging
    AUTO = "Auto"               # ML-based dynamic selection
```

### ResourceRequirements

```python
@dataclass
class ResourceRequirements:
    model_size_mb: int
    min_gpu_vram_mb: int
    min_system_ram_mb: int
    nvme_swap_mb: int
    priority: ProcessPriority = ProcessPriority.NORMAL
    thermal_limit_c: int = 83
```

### GenerationConfig

```python
@dataclass
class GenerationConfig:
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stop_sequences: List[str] = field(default_factory=list)
    stream: bool = True
```

## Event System

### Training Events

```python
# Published during training
TrainingEvents = {
    "epoch_start": {"epoch": int, "total_epochs": int},
    "epoch_complete": {"epoch": int, "loss": float, "metrics": dict},
    "batch_complete": {"batch": int, "loss": float, "tokens_per_sec": float},
    "checkpoint_saved": {"path": str, "epoch": int, "is_best": bool},
    "validation_start": {"epoch": int},
    "validation_complete": {"epoch": int, "metrics": dict},
    "training_complete": {"model_id": str, "final_metrics": dict},
    "training_failed": {"error": str, "recovery_point": str},
    "training_paused": {"epoch": int, "checkpoint": str},
    "training_resumed": {"epoch": int}
}
```

### Resource Events

```python
ResourceEvents = {
    "allocation_changed": {"allocation": ResourceAllocation},
    "threshold_exceeded": {"resource": str, "current": float, "threshold": float},
    "oom_warning": {"tier": str, "available_mb": int},
    "thermal_warning": {"component": str, "temp_c": float},
    "thermal_critical": {"component": str, "temp_c": float, "throttle_pct": float},
    "mode_switched": {"old_mode": str, "new_mode": str, "reason": str}
}
```

### Processing Events

```python
ProcessingEvents = {
    "document_queued": {"document_id": str, "filename": str},
    "document_processing": {"document_id": str, "stage": str, "progress": float},
    "document_processed": {"document_id": str, "chunks": int, "quality": float},
    "document_failed": {"document_id": str, "error": str, "retry": bool},
    "indexing_complete": {"collection": str, "vectors": int, "duration_sec": float},
    "embedding_batch_done": {"batch": int, "total": int, "vectors": int}
}
```

### Event Bus Usage

```python
from src.modules.logic.event_bus_lg.message_dispatcher_lg import EventBus

# Subscribe to events
event_bus = EventBus()

def on_training_progress(event: Event):
    update_ui_progress(event.data)

event_bus.subscribe("training.epoch_complete", on_training_progress)

# Publish events
event_bus.publish("training.epoch_complete", {
    "epoch": 5,
    "loss": 2.34,
    "val_loss": 2.41
})
```

## Error Handling

### Exception Hierarchy

```python
class MikroDokError(Exception):
    """Base exception."""
    pass

class ValidationError(MikroDokError):
    """Input validation failed."""
    pass

class ResourceError(MikroDokError):
    """Resource allocation failed."""
    pass

class TrainingError(MikroDokError):
    """Training operation failed."""
    pass

class InferenceError(MikroDokError):
    """Inference operation failed."""
    pass

class ModelError(MikroDokError):
    """Model loading/export failed."""
    pass

class DatabaseError(MikroDokError):
    """Database operation failed."""
    pass
```

### Error Response Format

```python
@dataclass
class ErrorResponse:
    error_code: str
    message: str
    severity: ErrorSeverity      # CRITICAL, WARNING, INFO, RECOVERABLE
    recovery_action: str
    user_message: str
    technical_details: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

## Configuration APIs

### System Settings

```python
class SystemSettings:
    """Application-wide configuration."""
    
    # Resource settings
    gpu_device_id: int = 0
    gpu_memory_limit_mb: int = 20480
    cpu_memory_limit_mb: int = 32768
    nvme_swap_path: str = "/fast_nvme/swap"
    nvme_swap_size_gb: int = 100
    allocation_mode: AllocationMode = AllocationMode.AUTO
    
    # Model defaults
    default_model_size: ModelSize = ModelSize.B3
    default_quantization: QuantizationType = QuantizationType.INT4
    checkpoint_interval_epochs: int = 1
    
    # Processing
    supported_formats: List[str] = ["pdf", "docx", "txt", "html", "md"]
    chunk_size_tokens: int = 512
    chunk_overlap_pct: int = 10
    ocr_enabled: bool = True
    deduplication_enabled: bool = True
    
    # UI
    theme: ThemeMode = ThemeMode.AUTO
    language: str = "en"
    auto_save: bool = True
    update_channel: UpdateChannel = UpdateChannel.STABLE
```

## Database Repository Interfaces

### DocumentRepository

```python
class DocumentRepository:
    """Document data access."""
    
    def store(self, document: Document, conn: Connection) -> str:
        """Store document metadata."""
    
    def get(self, doc_id: str, conn: Connection) -> Optional[Document]:
        """Retrieve document by ID."""
    
    def list_by_collection(
        self,
        collection_id: str,
        conn: Connection,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """List documents in collection."""
    
    def delete(self, doc_id: str, conn: Connection) -> bool:
        """Delete document and related data."""
```

### ModelRepository

```python
class ModelRepository:
    """Model registry data access."""
    
    def register(self, model: ModelRecord, conn: Connection) -> ModelRecord:
        """Register new model."""
    
    def get(self, model_id: str, conn: Connection) -> Optional[ModelRecord]:
        """Get model by ID."""
    
    def get_versions(
        self,
        model_id: str,
        conn: Connection
    ) -> List[ModelVersion]:
        """Get all versions of a model."""
    
    def set_active(self, model_id: str, version: str, conn: Connection) -> bool:
        """Set active version."""
```

## Async Patterns

All long-running operations use async/await:

```python
# Correct async usage
async def train_model_example():
    engine = MLProcessingEngine()
    
    # Start training with progress callback
    async def progress(event):
        print(f"Epoch {event['epoch']}: loss={event['loss']:.4f}")
    
    result = await engine.train_model(
        config=config,
        documents=docs,
        progress_callback=progress
    )
    
    return result

# Run in event loop
asyncio.run(train_model_example())
```

## Thread Safety

- **Logic Layer**: Thread-safe via internal locking
- **Database Layer**: Connection pooling with thread-local storage
- **UI Layer**: Main thread only, communicates via event bus
- **ML Engine**: Single training session per process

---

*Last Updated: 2025-01-15*
*Version: 0.1.0-alpha*