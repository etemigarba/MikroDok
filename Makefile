# MikroDok Development Makefile

.PHONY: help install dev-install test lint format typecheck clean build docs release

# Default target
help:
	@echo "MikroDok Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install       Install production dependencies"
	@echo "  dev-install   Install development dependencies"
	@echo "  pre-commit    Install pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  test          Run all tests (excl. slow/gpu)"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-integration Run integration tests"
	@echo "  test-ui       Run UI tests"
	@echo "  test-gpu      Run GPU tests (requires GPU)"
	@echo "  test-coverage Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint          Run Ruff linting"
	@echo "  format        Format code with Ruff"
	@echo "  typecheck     Run MyPy type checking"
	@echo "  pyright       Run Pyright type checking"
	@echo "  check-all     Run all quality checks"
	@echo ""
	@echo "Documentation:"
	@echo "  docs          Build documentation"
	@echo "  docs-serve    Serve documentation locally"
	@echo ""
	@echo "Building:"
	@echo "  build         Build distribution packages"
	@echo "  build-windows Build Windows installer (on Windows)"
	@echo "  build-macos   Build macOS DMG (on macOS)"
	@echo "  build-linux   Build Linux AppImage (on Linux)"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean         Clean build artifacts"
	@echo "  update-deps   Update dependencies"
	@echo "  audit         Run security audit"
	@echo ""

# Setup
install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

pre-commit:
	pre-commit install
	pre-commit run --all-files

# Testing
test:
	pytest tests/ -v --tb=short -m "not slow and not gpu"

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short -m "not slow and not gpu"

test-ui:
	pytest tests/ui/ -v --tb=short -m "not slow"

test-gpu:
	pytest tests/ -v --tb=short -m "gpu"

test-coverage:
	pytest tests/ -v --tb=short \
		--cov=src \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		-m "not slow and not gpu"

# Code Quality
lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

pyright:
	pyright src/

check-all: lint format typecheck pyright

# Documentation
docs:
	cd docs && sphinx-build -b html -W --keep-going . _build/html

docs-serve:
	cd docs && sphinx-autobuild -b html --port 8000 . _build/html

# Building
build:
	python -m build --wheel --sdist
	twine check dist/*

build-windows:
ifeq ($(OS),Windows_NT)
	flet build windows --project-name MikroDok --bundle-id com.etemigarba.mikrodok --code-sign --installer-type msi
else
	@echo "Windows build must run on Windows"
	exit 1
endif

build-macos:
ifeq ($(shell uname),Darwin)
	flet build macos --project-name MikroDok --bundle-id com.etemigarba.mikrodok --code-sign --notarize
else
	@echo "macOS build must run on macOS"
	exit 1
endif

build-linux:
ifeq ($(shell uname),Linux)
	flet build linux --project-name MikroDok --bundle-id com.etemigarba.mikrodok --format AppImage
else
	@echo "Linux build must run on Linux"
	exit 1
endif

# Maintenance
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf docs/_build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

update-deps:
	pip install --upgrade pip
	pip install -r requirements.txt --upgrade
	pip install -r requirements-dev.txt --upgrade
	pip freeze > requirements.lock.txt

audit:
	pip-audit -r requirements.txt --desc

# Development shortcuts
run:
	python -m src.main

run-dev:
	python -m src.main --dev --debug

shell:
	python -c "import src; print('MikroDok modules loaded')"

# CI simulation
ci-local: check-all test-coverage build
	@echo "Local CI simulation complete"

# Release helpers
version-patch:
	bump2version patch

version-minor:
	bump2version minor

version-major:
	bump2version major

# Docker
docker-build:
	docker build -t mikrodok:latest .

docker-run:
	docker run --rm -it --gpus all mikrodok:latest

docker-shell:
	docker run --rm -it --gpus all mikrodok:latest /bin/bash