# Contributing to MikroDok

Thank you for your interest in contributing to MikroDok! This document provides guidelines for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Architecture Overview](#architecture-overview)

---

## 🤝 Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainer.

### Our Standards

- **Be respectful** - Use welcoming and inclusive language
- **Be constructive** - Provide actionable feedback
- **Be collaborative** - Work together towards common goals
- **Be transparent** - Communicate openly about changes and decisions

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Git 2.40+
- NVIDIA GPU with CUDA 11.8+ (for GPU-accelerated development)
- 16GB+ RAM, 1TB+ NVMe SSD recommended

### Development Setup

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/MikroDok.git
cd MikroDok

# 3. Add upstream remote
git remote add upstream https://github.com/etemigarba/MikroDok.git

# 4. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 5. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 6. Install pre-commit hooks
pre-commit install

# 7. Verify setup
pytest tests/ -v --tb=short
ruff check src/
mypy src/
```

---

## 🔄 Development Workflow

### Branch Strategy

```
main                    # Production-ready code (protected)
├── develop             # Integration branch (protected)
│   ├── feature/xxx     # New features
│   ├── fix/xxx         # Bug fixes
│   ├── docs/xxx        # Documentation updates
│   ├── refactor/xxx    # Code refactoring
│   └── test/xxx        # Test improvements
└── release/x.y.z       # Release preparation
```

### Creating a Feature Branch

```bash
# Sync with upstream
git fetch upstream
git checkout develop
git merge upstream/develop

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes, commit often
git add .
git commit -m "feat: add amazing feature"

# Push to your fork
git push origin feature/your-feature-name

# Create Pull Request against upstream/develop
```

---

## 🎨 Coding Standards

### Python Style Guide

We use **Ruff** for linting and formatting (replaces Black, isort, flake8):

```bash
# Check code style
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

### Type Checking

We use **MyPy** for static type analysis:

```bash
# Run type checking
mypy src/

# Strict mode for new code
mypy --strict src/modules/logic/new_module/
```

### Key Standards

| Aspect | Standard |
|--------|----------|
| Line Length | 100 characters |
| Quotes | Double quotes (`"`) |
| Indentation | 4 spaces (no tabs) |
| Type Hints | Required for all public APIs |
| Docstrings | Google style for modules/classes/functions |
| Imports | Absolute imports, grouped (stdlib, third-party, local) |

### Example Module Structure

```python
"""Module docstring describing purpose and usage.

Example:
    >>> from mikrodok.module import ClassName
    >>> instance = ClassName()
    >>> instance.method()
"""

# Stdlib imports
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

# Third-party imports
import torch
import flet as ft
from loguru import logger

# Local imports
from src.modules.logic.base_lg import BaseLogic
from src.modules.database.repository_db import RepositoryDB


@dataclass
class Config:
    """Configuration dataclass with type hints."""
    name: str
    value: int = 42
    enabled: bool = True


class ClassName(BaseLogic):
    """Class docstring explaining responsibility."""
    
    def __init__(self, config: Config) -> None:
        """Initialize with configuration.
        
        Args:
            config: Application configuration
            
        Raises:
            ValueError: If config validation fails
        """
        self.config = config
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not self.config.name:
            raise ValueError("Name cannot be empty")
    
    async def async_method(self, param: str) -> Dict[str, Any]:
        """Async method with type hints.
        
        Args:
            param: Input parameter
            
        Returns:
            Result dictionary
        """
        result = await self._process(param)
        logger.info(f"Processed {param}")
        return result
```

---

## 🧪 Testing Requirements

### Test Categories

| Marker | Description | When to Run |
|--------|-------------|-------------|
| `unit` | Fast unit tests | Every commit |
| `integration` | Cross-module tests | PR creation |
| `ui` | UI responsiveness tests | PR creation |
| `gpu` | GPU-required tests | Manual / CI scheduled |
| `slow` | Long-running tests | Nightly / Manual |

### Running Tests

```bash
# All tests (excluding slow)
pytest tests/ -m "not slow" -v

# Unit tests only
pytest tests/ -m "unit" -v

# Integration tests
pytest tests/ -m "integration" -v

# UI tests
pytest tests/ui/ -m "ui" -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Parallel execution
pytest tests/ -n auto -v
```

### Test Requirements

1. **Coverage**: Minimum 80% for new code
2. **Naming**: `test_<function>_<scenario>_<expected>`
3. **Structure**: Arrange-Act-Assert pattern
4. **Fixtures**: Use conftest.py for shared fixtures
5. **Mocking**: Mock external dependencies (GPU, network, filesystem)

### Example Test

```python
"""Tests for memory allocation module."""

import pytest
from unittest.mock import Mock, patch

from src.modules.logic.memory_allocation_lg.allocation_strategy_lg import AllocationStrategy


class TestAllocationStrategy:
    """Test suite for AllocationStrategy."""
    
    @pytest.fixture
    def strategy(self) -> AllocationStrategy:
        """Create strategy instance for testing."""
        return AllocationStrategy()
    
    @pytest.mark.unit
    def test_select_mode_legacy_when_model_fits_vram(
        self, strategy: AllocationStrategy
    ) -> None:
        """Should select Legacy mode when model fits in VRAM."""
        # Arrange
        model_size_mb = 4096  # 4GB
        vram_mb = 8192  # 8GB
        
        # Act
        mode = strategy.select_mode(model_size_mb, vram_mb, 32768)
        
        # Assert
        assert mode == "Legacy"
    
    @pytest.mark.unit
    def test_select_mode_hybrid_when_model_exceeds_vram(
        self, strategy: AllocationStrategy
    ) -> None:
        """Should select Hybrid mode when model exceeds VRAM but fits in RAM."""
        # Arrange
        model_size_mb = 16384  # 16GB
        vram_mb = 8192  # 8GB
        ram_mb = 32768  # 32GB
        
        # Act
        mode = strategy.select_mode(model_size_mb, vram_mb, ram_mb)
        
        # Assert
        assert mode == "Hybrid"
    
    @pytest.mark.integration
    @patch("src.modules.logic.memory_allocation_lg.allocation_strategy_lg.get_gpu_info")
    def test_auto_mode_with_real_hardware(
        self, mock_get_gpu: Mock, strategy: AllocationStrategy
    ) -> None:
        """Integration test with mocked hardware detection."""
        # Arrange
        mock_get_gpu.return_value = {"vram_mb": 24576, "cuda_version": "12.0"}
        
        # Act
        mode = strategy.auto_select(7000000000)  # 7B model
        
        # Assert
        assert mode in ("Legacy", "Hybrid", "Auto")
```

---

## 🔀 Pull Request Process

### PR Checklist

Before submitting a PR, ensure:

- [ ] **Branch** targets `develop` (not `main`)
- [ ] **Title** follows convention: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- [ ] **Description** explains what, why, and how
- [ ] **Tests** pass locally (`pytest tests/ -m "not slow"`)
- [ ] **Linting** passes (`ruff check src/ tests/`)
- [ ] **Type checking** passes (`mypy src/`)
- [ ] **Documentation** updated for user-facing changes
- [ ] **CHANGELOG.md** updated (see [Keep a Changelog](https://keepachangelog.com/))
- [ ] **No sensitive data** in commits (keys, passwords, tokens)

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix/feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement

## Related Issues
Closes #123
Relates to #456

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] UI tests added/updated
- [ ] Manual testing performed (describe)

## Screenshots (if applicable)
<!-- Add screenshots for UI changes -->

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated Checks** - CI runs tests, linting, type checking
2. **Code Review** - Maintainer reviews within 48 hours
3. **Feedback** - Address review comments
4. **Approval** - At least one maintainer approval required
5. **Merge** - Squash and merge to `develop`

---

## 📝 Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructuring |
| `test` | Adding/modifying tests |
| `chore` | Maintenance, build, deps |
| `perf` | Performance improvement |
| `ci` | CI/CD changes |

### Examples

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

---

## 🏗️ Architecture Overview

### Three-Layer Architecture

```
┌─────────────────────────────────────────────┐
│              UI Layer (Flet)                │
│  Components → State → Events → User Actions │
└──────────────────┬──────────────────────────┘
                   │ Events / Commands
┌──────────────────▼──────────────────────────┐
│            Logic Layer (Pure Python)        │
│  Algorithms → Workflows → State Machines    │
└──────────────────┬──────────────────────────┘
                   │ Repository Pattern
┌──────────────────▼──────────────────────────┐
│           Database Layer (SQLite)           │
│  Tables → Queries → Migrations → Backups    │
└─────────────────────────────────────────────┘
```

### Module Naming Convention

```
{domain}_{layer}
├── {subdomain}_{layer}
/   └── {component}_{layer}/
       └── {component}_{layer}.py
```

Examples:
- `document_ingestion_lg/format_detector_lg/format_detector_lg.py`
- `training_orchestration_lg/session_manager_lg/session_manager_lg.py`
- `memory_allocation_lg/bridge_controller_lg/bridge_controller_lg.py`

### Key Principles

1. **Dependency Direction**: UI → Logic → Database (never reverse)
2. **Single Responsibility**: Each module has one clear purpose
3. **Interface Segregation**: Small, focused interfaces
4. **Async-First**: All long-running operations are async
5. **Event-Driven**: Loose coupling via event bus
6. **Offline-First**: No external network dependencies in core logic

---

## 📞 Getting Help

- **Questions**: Open a [Discussion](https://github.com/etemigarba/MikroDok/discussions)
- **Bugs**: File an [Issue](https://github.com/etemigarba/MikroDok/issues)
- **Security**: See [SECURITY.md](SECURITY.md)
- **Maintainer**: @etemigarba

---

## 📄 License

By contributing, you agree that your contributions will be licensed under the same proprietary license as the project. See [LICENSE](LICENSE) for details.

**Copyright © 2025 Etemi Joshua Garba. All rights reserved.**