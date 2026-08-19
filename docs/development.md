# MikroDok Development Guide

## Overview

This guide covers the development workflow, coding standards, testing patterns, and best practices for contributing to MikroDok.

## Development Environment Setup

### Prerequisites

- Python 3.12+
- Git 2.40+
- NVIDIA GPU with CUDA 11.8+ (for GPU development)
- 16GB+ RAM, 500GB+ NVMe SSD
- VS Code / PyCharm recommended

### Initial Setup

```bash
# Clone and setup
git clone https://github.com/etemigarba/MikroDok.git
cd MikroDok

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Verify setup
pytest tests/ -v --tb=short -x
ruff check src/
mypy src/
```

### IDE Configuration

#### VS Code (`.vscode/settings.json`)

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports.ruff": "explicit",
    "source.fixAll.ruff": "explicit"
  },
  "python.analysis.typeCheckingMode": "basic",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true,
    ".mypy_cache": true,
    ".ruff_cache": true,
    "htmlcov": true,
    "dist": true,
    "build": true
  }
}
```

#### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Ruff: Settings → Tools → Ruff
3. Enable MyPy: Settings → Languages → Python → MyPy
4. Configure pytest as test runner

## Project Structure Deep Dive

### Logic Layer Modules

Each logic module follows this pattern:

```
{domain}_lg/
├── {subdomain}_lg/
│   ├── {component}_lg/
│   │   ├── __init__.py           # Public exports
│   │   ├── {component}_lg.py     # Main implementation
│   │   ├── {component}_lg_test.py # Unit tests (optional)
│   │   └── README.md             # Component documentation
```

### Creating a New Logic Module

1. **Create directory structure:**
```bash
mkdir -p src/modules/logic/new_feature_lg/component_lg
```

2. **Implement the component:**
```python
# src/modules/logic/new_feature_lg/component_lg/component_lg.py
"""Component description and purpose."""

from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

from src.modules.logic.base_lg import BaseLogic
from src.modules.database.repository_db import RepositoryDB


@dataclass
class ComponentConfig:
    """Configuration for component."""
    param1: str
    param2: int = 42
    enabled: bool = True


class ComponentLg(BaseLogic):
    """Main component implementation."""
    
    def __init__(self, config: ComponentConfig, repository: RepositoryDB) -> None:
        self.config = config
        self.repository = repository
    
    def process(self, input_data: str) -> dict:
        """Process input and return result."""
        # Implementation
        return {"status": "success", "data": input_data}
```

3. **Export in `__init__.py`:**
```python
# src/modules/logic/new_feature_lg/component_lg/__init__.py
"""Component module exports."""

from .component_lg import ComponentLg, ComponentConfig

__all__ = ["ComponentLg", "ComponentConfig"]
```

### UI Layer Modules

UI components follow Flet patterns:

```
{feature}_ui/
├── {component}_ui/
│   ├── __init__.py
│   ├── {component}_ui.py      # Flet component
│   ├── {component}_ui.css     # Styles (optional)
│   └── README.md
```

### Database Layer Modules

Database modules use repository pattern:

```
{domain}_db/
├── {repository}_db/
│   ├── __init__.py
│   ├── {repository}_db.py     # Repository implementation
│   ├── queries.py             # SQL queries
│   └── models.py              # Data classes
```

## Coding Standards

### Python Style (Ruff)

```bash
# Check
ruff check src/ tests/

# Fix
ruff check --fix src/ tests/

# Format
ruff format src/ tests/
```

### Key Rules

| Rule | Configuration |
|------|---------------|
| Line length | 100 chars |
| Quotes | Double (`"`) |
| Imports | Absolute, grouped |
| Type hints | Required for public APIs |
| Docstrings | Google style |

### Import Organization

```python
# 1. Stdlib imports
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

# 2. Third-party imports
import torch
import flet as ft
from loguru import logger

# 3. Local imports (absolute)
from src.modules.logic.base_lg import BaseLogic
from src.modules.database.repository_db import RepositoryDB
```

### Type Hints

```python
# Function signatures
async def process_documents(
    files: List[Path],
    config: ProcessingConfig,
    callback: Optional[Callable[[ProgressEvent], None]] = None
) -> ProcessingResult:
    ...

# Class attributes
class Trainer:
    model: torch.nn.Module
    optimizer: torch.optim.Optimizer
    config: TrainingConfig
    
    def __init__(self, config: TrainingConfig) -> None:
        ...
```

### Docstrings (Google Style)

```python
def train_model(
    self,
    config: TrainingConfig,
    documents: List[Document],
    progress_callback: Optional[Callable[[TrainingProgress], None]] = None
) -> TrainingResult:
    """Train a language model on the provided documents.
    
    Args:
        config: Training configuration including model size and hyperparameters.
        documents: List of processed documents to train on.
        progress_callback: Optional callback for progress updates.
        
    Returns:
        TrainingResult containing model ID, metrics, and checkpoint paths.
        
    Raises:
        ValidationError: If configuration is invalid.
        ResourceError: If insufficient hardware resources.
        TrainingError: If training fails unexpectedly.
        
    Example:
        >>> config = TrainingConfig(model_size=ModelSize.B7)
        >>> result = await engine.train_model(config, documents)
        >>> print(result.model_id)
        model_abc123
    """
```

## Testing Patterns

### Test Organization

```
tests/
├── unit/                    # Fast unit tests
│   ├── logic/
│   │   ├── test_chunking.py
│   │   ├── test_embedding.py
│   │   └── test_idralloc.py
├── integration/             # Cross-module tests
│   ├── test_training_pipeline.py
│   └── test_rag_pipeline.py
├── ui/                      # UI tests
│   ├── test_responsiveness.py
│   └── test_navigation.py
├── gpu/                     # GPU-required tests
│   └── test_training_gpu.py
├── fixtures/                # Test fixtures
│   ├── sample_documents/
│   └── mock_models/
├── conftest.py              # Shared fixtures
└── test_utils.py            # Test utilities
```

### Writing Unit Tests

```python
# tests/unit/logic/test_idralloc.py
"""Tests for IDRAlloc memory management."""

import pytest
from unittest.mock import Mock, patch

from src.modules.logic.memory_allocation_lg.allocation_strategy_lg import AllocationStrategy
from src.modules.logic.memory_allocation_lg.memory_tier_manager_lg import MemoryTierManager


class TestAllocationStrategy:
    """Test suite for AllocationStrategy."""
    
    @pytest.fixture
    def strategy(self) -> AllocationStrategy:
        """Create strategy instance."""
        return AllocationStrategy()
    
    @pytest.fixture
    def mock_tier_manager(self) -> Mock:
        """Mock memory tier manager."""
        manager = Mock(spec=MemoryTierManager)
        manager.get_tier_capacity.return_value = {
            1: 8192,   # GPU VRAM: 8GB
            2: 32768,  # System RAM: 32GB
            3: 102400  # NVMe: 100GB
        }
        return manager
    
    @pytest.mark.unit
    def test_select_legacy_when_model_fits_vram(
        self, 
        strategy: AllocationStrategy,
        mock_tier_manager: Mock
    ) -> None:
        """Should select Legacy mode for models fitting in VRAM."""
        # Arrange
        strategy.tier_manager = mock_tier_manager
        model_size_mb = 4096  # 4GB model
        
        # Act
        mode = strategy.select_mode(model_size_mb)
        
        # Assert
        assert mode == "Legacy"
    
    @pytest.mark.unit
    def test_select_hybrid_when_model_exceeds_vram(
        self,
        strategy: AllocationStrategy,
        mock_tier_manager: Mock
    ) -> None:
        """Should select Hybrid when model exceeds VRAM but fits in RAM."""
        strategy.tier_manager = mock_tier_manager
        model_size_mb = 16384  # 16GB model
        
        mode = strategy.select_mode(model_size_mb)
        
        assert mode == "Hybrid"
    
    @pytest.mark.unit
    @pytest.mark.parametrize("model_size,expected_mode", [
        (2048, "Legacy"),    # 2GB
        (8192, "Legacy"),    # 8GB
        (12288, "Hybrid"),   # 12GB
        (24576, "Hybrid"),   # 24GB
        (40960, "Auto"),     # 40GB
    ])
    def test_mode_selection_boundaries(
        self,
        strategy: AllocationStrategy,
        mock_tier_manager: Mock,
        model_size: int,
        expected_mode: str
    ) -> None:
        """Test mode selection at boundary conditions."""
        strategy.tier_manager = mock_tier_manager
        
        mode = strategy.select_mode(model_size)
        
        assert mode == expected_mode
```

### Integration Tests

```python
# tests/integration/test_training_pipeline.py
"""Integration tests for training pipeline."""

import pytest
import tempfile
from pathlib import Path

from src.modules.logic.training_orchestration_lg.session_manager_lg import SessionManager
from src.modules.logic.document_ingestion_lg.batch_processor_lg import BatchProcessor


class TestTrainingPipeline:
    """End-to-end training pipeline tests."""
    
    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_document_to_model_workflow(
        self,
        temp_dir: Path
    ) -> None:
        """Test complete document → model workflow."""
        # Arrange
        processor = BatchProcessor()
        session_mgr = SessionManager()
        
        # Create test documents
        docs = self._create_test_documents(temp_dir)
        
        # Act - Process documents
        processed = await processor.process_batch(docs)
        
        # Assert - Documents processed
        assert len(processed) == len(docs)
        assert all(d.status == "completed" for d in processed)
        
        # Act - Train model
        config = TrainingConfig(
            model_size=ModelSize.B1,  # Small for testing
            epochs=1,
            batch_size=2
        )
        
        session = await session_mgr.create_session(config, processed)
        result = await session_mgr.execute_session(session)
        
        # Assert - Model trained
        assert result.status == "completed"
        assert result.model_id is not None
        assert result.final_loss < 10.0  # Reasonable loss
```

### UI Tests

```python
# tests/ui/test_responsiveness.py
"""UI responsiveness tests."""

import pytest
from unittest.mock import AsyncMock, patch

import flet as ft
from src.modules.ui.main_dashboard_ui.landing_page_ui import LandingPageUI


class TestMainDashboard:
    """Tests for main dashboard UI."""
    
    @pytest.fixture
    def page(self) -> ft.Page:
        """Create mock Flet page."""
        page = AsyncMock(spec=ft.Page)
        page.width = 1920
        page.height = 1080
        return page
    
    @pytest.mark.ui
    def test_dashboard_renders_at_1080p(self, page: ft.Page) -> None:
        """Dashboard should render correctly at 1080p."""
        dashboard = LandingPageUI(page)
        
        # Render
        controls = dashboard.build()
        
        # Assert structure
        assert controls is not None
        assert len(controls) > 0
    
    @pytest.mark.ui
    @pytest.mark.parametrize("width,height", [
        (1920, 1080),   # Full HD
        (2560, 1440),   # QHD
        (3840, 2160),   # 4K
    ])
    def test_responsive_layout(self, page: ft.Page, width: int, height: int) -> None:
        """Layout should adapt to different resolutions."""
        page.width = width
        page.height = height
        
        dashboard = LandingPageUI(page)
        controls = dashboard.build()
        
        # Should not crash at any resolution
        assert controls is not None
```

### Running Tests

```bash
# All tests (fast)
pytest tests/ -m "not slow and not gpu" -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# UI tests
pytest tests/ui/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Parallel execution
pytest tests/ -n auto -v

# Specific test
pytest tests/unit/logic/test_idralloc.py::TestAllocationStrategy::test_select_legacy_when_model_fits_vram -v
```

## Git Workflow

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<short-description>` | `feature/add-qlora-support` |
| Bug Fix | `fix/<short-description>` | `fix/memory-leak-training` |
| Docs | `docs/<short-description>` | `docs/update-api-reference` |
| Refactor | `refactor/<short-description>` | `refactor/chunking-module` |
| Test | `test/<short-description>` | `test/add-ui-tests` |
| Chore | `chore/<short-description>` | `chore/update-dependencies` |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Feature
git commit -m "feat(training): add QLoRA support for 7B models"

# Fix
git commit -m "fix(memory): resolve NVMe swap allocation race condition"

# Docs
git commit -m "docs(api): update IDRAlloc configuration reference"

# Refactor
git commit -m "refactor(chunking): extract semantic chunker to separate module"

# Test
git commit -m "test(resource_monitor): add GPU pressure detection tests"

# Chore
git commit -m "chore(deps): update PyTorch to 2.2.0"
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
        args: [--check]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]
  
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: debugger-statements
      - id: check-added-large-files
```

## Debugging

### Logging

```python
from loguru import logger

# Configure in application startup
logger.add(
    "logs/mikrodok_{time}.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
)

# Usage
logger.debug("Processing document: {doc_id}", doc_id=doc_id)
logger.info("Training started: {model_size}B", model_size=7)
logger.warning("GPU memory at 90%: {used_mb}MB", used_mb=7200)
logger.error("Training failed: {error}", error=str(e))
```

### Debugging Training

```python
# Enable PyTorch anomaly detection
import torch
torch.autograd.set_detect_anomaly(True)

# Memory profiling
from torch.profiler import profile, record_function, ProfilerActivity

with profile(
    activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
    record_shapes=True,
    profile_memory=True
) as prof:
    # Training code
    loss = model(batch)
    loss.backward()

print(prof.key_averages().table(sort_by="cuda_memory_usage", row_limit=10))
```

### Debugging UI

```python
# Flet debug mode
import flet as ft

ft.app(target=main, view=ft.WEB_BROWSER, port=8550)  # Web mode for debugging

# Or enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Optimization

### Profiling

```bash
# CPU profiling
python -m cProfile -o profile.stats src/main.py
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Memory profiling
pip install memray
memray run src/main.py
memray flamegraph profile.bin

# GPU profiling
nsys profile --trace=cuda,nvtx python src/main.py
```

### Common Optimizations

1. **Batch Operations**: Use batch processing for embeddings, database inserts
2. **Lazy Loading**: Defer heavy imports until needed
3. **Caching**: Cache embeddings, model configurations, query results
4. **Connection Pooling**: Reuse database connections
4. **Async I/O**: Use async for file operations, network calls

## Code Review Checklist

### For Authors

- [ ] Tests pass locally (`pytest tests/ -m "not slow"`)
- [ ] Linting passes (`ruff check src/ tests/`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No sensitive data committed
- [ ] Commit messages follow convention

### For Reviewers

- [ ] Code follows architecture patterns
- [ ] Logic/UI/Database layer separation maintained
- [ ] Error handling is comprehensive
- [ ] Tests cover new functionality
- [ ] Performance implications considered
- [ ] Security implications reviewed
- [ ] Breaking changes documented

## Release Process

### Version Bumping

```bash
# Patch (bug fixes)
bump2version patch

# Minor (features)
bump2version minor

# Major (breaking changes)
bump2version major
```

### Release Checklist

- [ ] All CI checks pass
- [ ] Version bumped in `pyproject.toml` and `src/__init__.py`
- [ ] CHANGELOG.md updated
- [ ] Release notes written
- [ ] Binaries built for all platforms
- [ ] Signatures and checksums generated
- [ ] GitHub release created
- [ ] Documentation deployed

---

*Last Updated: 2025-01-15*
*Version: 0.1.0-alpha*