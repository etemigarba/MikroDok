# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - Development

### Added
- Initial project structure with three-layer architecture (UI/Logic/Database)
- Comprehensive design documentation in `project_documents/`
- Flet-based cross-platform UI framework
- SQLite database with WAL mode and optimized indexing
- Document processing pipeline (PDF, DOCX, TXT, HTML, Markdown)
- Training orchestration with checkpoint management
- IDRAlloc memory management system (Legacy, Hybrid, Auto modes)
- RAG pipeline with ChromaDB and BM25 hybrid search
- ONNX conversion and quantization engine
- Real-time resource monitoring dashboard
- Comprehensive test suite with UI responsiveness tests

### Changed
- N/A (initial development)

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

---

## [0.1.0] - 2025-06-20 (Planned Alpha Release)

### Added
- **Core Architecture**
  - Three-layer modular architecture (Logic/UI/Database)
  - Event-driven communication between layers
  - Lazy loading system for optimized startup
  - Configuration management with validation

- **Document Processing**
  - Multi-format support: PDF, DOCX, TXT, HTML, Markdown
  - Magic number verification for format detection
  - Semantic text chunking (512-1024 tokens with overlap)
  - OCR processing via Tesseract
  - Table extraction from PDFs
  - Metadata preservation (author, dates, properties)
  - Quality scoring (0-100) with validation reports
  - Deduplication via SHA-256 and semantic similarity

- **Model Training**
  - Support for 1B, 3B, 7B parameter models
  - Training methods: From Scratch, Fine-Tune, QLoRA
  - DeepSpeed ZeRO-Infinity integration
  - Mixed precision training (bfloat16)
  - Gradient accumulation and checkpointing
  - Early stopping based on validation metrics
  - Pause/resume capability with state preservation

- **IDRAlloc Memory Management**
  - Three-tier hierarchy: GPU VRAM → System RAM → NVMe
  - Dynamic layer distribution based on access patterns
  - Memory bridge controller with DMA transfers
  - Predictive preloading via computation graph analysis
  - LRU eviction policy for tier management
  - Auto mode selection via ML-based prediction
  - Thermal throttling protection

- **RAG & Search**
  - ChromaDB vector storage with HNSW indexing
  - Sentence Transformers embeddings (all-MiniLM-L6-v2)
  - BM25 keyword search fallback
  - Weighted fusion with configurable alpha parameter
  - Cross-encoder reranking for improved relevance
  - Context window construction with token optimization
  - Source citation tracking with page numbers

- **Inference & Deployment**
  - ONNX Runtime with CUDA/CPU/Metal providers
  - INT4/INT8/FP16 quantization support
  - TensorRT optimization for NVIDIA GPUs
  - Sub-2-second inference for 7B INT4 models
  - Batch processing (8-16 concurrent requests)
  - Cross-platform model export

- **User Interface**
  - Main Dashboard with project cards and quick actions
  - System Information with real-time hardware monitoring
  - Document Manager with drag-and-drop upload
  - Interactive Search (RAG) with hybrid search modes
  - Intelligent Chat with model builder and chat modes
  - Model Registry with versioning and benchmark comparison
  - Settings panel with resource allocation configuration
  - Training Monitor with live loss curves and metrics
  - WCAG 2.1 AA accessibility compliance
  - Light/Dark/Auto theme support

- **Database**
  - SQLite with WAL mode for concurrent access
  - Optimized schema for ML workloads
  - Time-series metrics with circular buffer storage
  - Automated backup and recovery procedures
  - Migration framework with version tracking
  - Encryption support via SQLCipher

- **Monitoring & Observability**
  - Real-time GPU/CPU/RAM/NVMe metrics (1-second sampling)
  - GPU memory pressure detection with prediction
  - Adaptive resource allocation triggers
  - Thermal monitoring with automatic throttling
  - Performance profiling and bottleneck detection
  - Alert system with configurable thresholds

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- Offline-first architecture with zero external dependencies
- AES-256 encryption for model artifacts (optional)
- PBKDF2-SHA512 key derivation (256,000 iterations)
- Parameterized queries preventing SQL injection
- Secure deletion for sensitive data (DoD 5220.22-M)
- Audit logging for compliance requirements

---

## Version History Template

### [x.y.z] - YYYY-MM-DD

#### Added
- New features

#### Changed
- Changes in existing functionality

#### Deprecated
- Soon-to-be removed features

#### Removed
- Removed features

#### Fixed
- Bug fixes

#### Security
- Security improvements

---

## Release Process

1. Update version in `pyproject.toml` and `src/__init__.py`
2. Update `CHANGELOG.md` with release notes
3. Create release branch: `git checkout -b release/x.y.z`
4. Run full test suite: `pytest tests/ -v`
5. Build distribution packages: `python -m build`
6. Create signed installers for each platform
7. Tag release: `git tag -a v0.1.0 -m "Release v0.1.0"`
8. Push tags: `git push origin v0.1.0`
9. Create GitHub Release with artifacts
10. Merge release branch to `main` and `develop`

## Links

- [Unreleased]: https://github.com/etemigarba/MikroDok/compare/v0.1.0...HEAD
- [0.1.0]: https://github.com/etemigarba/MikroDok/releases/tag/v0.1.0