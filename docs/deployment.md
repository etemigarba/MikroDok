# MikroDok Deployment Guide

## Overview

This guide covers production deployment of MikroDok across Windows, macOS, and Linux platforms. MikroDok is distributed as a self-contained desktop application with embedded Python runtime and all ML dependencies.

## Build Requirements

### Build Machine Specifications

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 8 cores | 16+ cores |
| RAM | 32 GB | 64+ GB |
| GPU | RTX 3070 (8GB) | RTX 4090 (24GB) |
| Storage | 500 GB NVMe | 2 TB NVMe |
| OS | Windows 11 / Ubuntu 22.04 / macOS 13 | Latest LTS |

### Required Software

```bash
# Windows
- Visual Studio 2022 Build Tools
- Windows 10/11 SDK
- WiX Toolset 3.11+ (for MSI)
- NSIS 3.09+ (alternative installer)

# macOS
- Xcode 15+ Command Line Tools
- create-dmg (for DMG creation)
- Apple Developer ID (for notarization)

# Linux
- GCC 11+ / Clang 14+
- AppImageTool
- patchelf
- fakeroot, dpkg, rpm (for package building)
```

## Build Process

### 1. Prepare Build Environment

```bash
# Clone repository
git clone https://github.com/etemigarba/MikroDok.git
cd MikroDok

# Create clean build environment
python -m venv build-env
source build-env/bin/activate  # Windows: build-env\Scripts\activate

# Install build dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install flet-build pyinstaller cx-freeze
```

### 2. Configure Build

Create `build-config.yaml`:

```yaml
app:
  name: "MikroDok"
  version: "0.1.0"
  bundle_id: "com.etemigarba.mikrodok"
  copyright: "Copyright © 2025 Etemi Joshua Garba"

platforms:
  windows:
    installer: "msi"
    code_sign: true
    certificate: "path/to/cert.pfx"
    timestamp_server: "http://timestamp.digicert.com"
  
  macos:
    format: "dmg"
    code_sign: true
    notarize: true
    team_id: "YOUR_TEAM_ID"
    entitlements: "entitlements.plist"
  
  linux:
    format: "appimage"
    desktop_entry: true

assets:
  icon: "assets/icon.ico"
  splash: "assets/splash.png"
  license: "LICENSE"

includes:
  packages:
    - torch
    - transformers
    - deepspeed
    - onnxruntime
    - chromadb
    - sentence_transformers
    - bitsandbytes
    - pdfplumber
    - docx
    - bs4
    - pytesseract
    - numpy
    - PIL
    - psutil
    - GPUtil
    - cpuinfo
    - pynvml
  
  files:
    - assets/
    - data/
    
excludes:
  - tests
  - scripts
  - docs
  - sphinx
  - pytest
  - ruff
  - mypy
  - pre_commit
  - black
  - isort
```

### 3. Build for Each Platform

#### Windows (MSI Installer)

```bash
# Using flet build
flet build windows \
  --project-name MikroDok \
  --bundle-id com.etemigarba.mikrodok \
  --code-sign \
  --installer-type msi \
  --certificate-path cert.pfx \
  --certificate-password $CERT_PASSWORD

# Or using PyInstaller directly
pyinstaller --clean --noconfirm \
  --name MikroDok \
  --icon assets/icon.ico \
  --add-data "assets;assets" \
  --add-data "data;data" \
  --hidden-import torch \
  --hidden-import transformers \
  --hidden-import deepspeed \
  --hidden-import onnxruntime \
  --hidden-import chromadb \
  --collect-all torch \
  --collect-all transformers \
  src/main.py

# Create MSI with WiX
candle -dVersion=0.1.0 installer.wxs
light -ext WixUIExtension installer.wixobj -o MikroDok-Setup-x64.msi
```

#### macOS (DMG)

```bash
# Using flet build
flet build macos \
  --project-name MikroDok \
  --bundle-id com.etemigarba.mikrodok \
  --code-sign \
  --notarize \
  --team-id $APPLE_TEAM_ID

# Manual notarization
xcrun notarytool submit MikroDok.dmg \
  --apple-id $APPLE_ID \
  --password $APP_PASSWORD \
  --team-id $TEAM_ID \
  --wait

xcrun stapler staple MikroDok.dmg
```

#### Linux (AppImage)

```bash
# Using flet build
flet build linux \
  --project-name MikroDok \
  --bundle-id com.etemigarba.mikrodok \
  --format AppImage

# Or manual AppImage creation
cd dist
appimagetool MikroDok.AppDir MikroDok-x86_64.AppImage
```

## Distribution

### Release Artifacts

| Platform | Artifact | Size (est.) | Signature |
|----------|----------|-------------|-----------|
| Windows | `MikroDok-Setup-x64.msi` | ~2.5 GB | Authenticode |
| Windows | `MikroDok-Portable-x64.zip` | ~2.5 GB | SHA256 |
| macOS | `MikroDok-x64.dmg` | ~2.8 GB | Notarized |
| Linux | `MikroDok-x86_64.AppImage` | ~2.6 GB | GPG |

### Checksums

```bash
# Generate checksums
sha256sum *.msi *.dmg *.AppImage *.zip > SHA256SUMS
gpg --clearsign SHA256SUMS
```

### GitHub Release

```bash
# Create release via CLI
gh release create v0.1.0 \
  --title "MikroDok v0.1.0 - Alpha Release" \
  --notes-file RELEASE_NOTES.md \
  MikroDok-Setup-x64.msi \
  MikroDok-Portable-x64.zip \
  MikroDok-x64.dmg \
  MikroDok-x86_64.AppImage \
  SHA256SUMS \
  SHA256SUMS.asc
```

## Enterprise Deployment

### Silent Installation (Windows)

```cmd
# MSI silent install
msiexec /i MikroDok-Setup-x64.msi /quiet /norestart \
  INSTALLDIR="C:\Program Files\MikroDok" \
  ALLUSERS=1

# With custom configuration
msiexec /i MikroDok-Setup-x64.msi /quiet \
  CONFIG_FILE="\\server\share\mikrodok-config.json"
```

### Group Policy Deployment

1. Copy MSI to network share
2. Create GPO: Computer Configuration → Policies → Software Settings → Software Installation
3. Assign package with "Assigned" deployment
4. Configure via registry or config file:

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SOFTWARE\MikroDok]
"ConfigPath"="\\server\share\mikrodok-enterprise.json"
"AutoUpdate"=dword:00000000
"TelemetryEnabled"=dword:00000000
```

### Configuration Management

Enterprise config template:

```json
{
  "allocation_mode": "Auto",
  "gpu_memory_limit_mb": 20480,
  "cpu_memory_limit_mb": 32768,
  "nvme_swap_path": "D:\\MikroDok\\swap",
  "nvme_swap_size_gb": 200,
  "priority": "high",
  "thermal_limit_celsius": 83,
  "theme": "Dark",
  "language": "en",
  "auto_update": false,
  "telemetry_enabled": false,
  "log_level": "INFO",
  "license_key": "ENTERPRISE-LICENSE-KEY"
}
```

### Volume Licensing

```bash
# Activate volume license
mikrodok --activate-volume-license \
  --license-file enterprise-license.lic \
  --organization "Acme Corp" \
  --seats 100

# Verify license status
mikrodok --license-status
```

## Air-Gapped Deployment

### Offline Installer Preparation

```bash
# Create offline bundle with all dependencies
mkdir mikrodok-offline
cd mikrodok-offline

# Download all wheels
pip download -r requirements.txt -d wheels/
pip download -r requirements-dev.txt -d wheels-dev/

# Copy application
cp -r ../dist/MikroDok .

# Create install script
cat > install-offline.sh << 'EOF'
#!/bin/bash
pip install --no-index --find-links wheels -r requirements.txt
cp -r MikroDok /opt/mikrodok
ln -s /opt/mikrodok/mikrodok /usr/local/bin/mikrodok
EOF

chmod +x install-offline.sh
tar -czf ../mikrodok-offline.tar.gz .
```

### Air-Gapped Installation

```bash
# On target machine (no internet)
tar -xzf mikrodok-offline.tar.gz
cd mikrodok-offline
sudo ./install-offline.sh

# Verify installation
mikrodok --version
mikrodok --system-check
```

## Post-Installation Verification

### System Check

```bash
# Run system validation
mikrodok --system-check

# Expected output:
# ✓ Python 3.12.3
# ✓ PyTorch 2.1.0 (CUDA 12.0)
# ✓ CUDA Driver 535.104
# ✓ GPU: NVIDIA RTX 4090 (24GB)
# ✓ NVMe: Samsung 990 Pro 2TB (7000 MB/s)
# ✓ RAM: 64GB DDR5
# ✓ Disk: 1.8TB free
# ✓ All dependencies satisfied
```

### Smoke Tests

```bash
# Quick functional test
mikrodok --smoke-test

# Full validation suite
mikrodok --validate-installation
```

## Updates & Maintenance

### Delta Updates

```bash
# Check for updates
mikrodok --check-updates

# Apply update (delta if available)
mikrodok --update

# Rollback if needed
mikrodok --rollback
```

### Scheduled Maintenance

```bash
# Database vacuum (weekly)
mikrodok --maintenance vacuum

# Clean old checkpoints
mikrodok --maintenance clean-checkpoints --keep 50

# Optimize vector indices
mikrodok --maintenance optimize-indices

# Full maintenance
mikrodok --maintenance full
```

## Troubleshooting

### Common Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| "CUDA out of memory" | Model too large for VRAM | Enable Hybrid/Auto IDRAlloc mode |
| "NVMe not detected" | Wrong path or permissions | Check `nvme_swap_path` config |
| "Installer blocked" | SmartScreen/App Gatekeeper | Sign with valid certificate |
| "Slow inference" | CPU fallback | Verify GPU detection, update drivers |
| "Permission denied" | Folder permissions | Run installer as admin/root |

### Log Locations

| Platform | Log Directory |
|----------|---------------|
| Windows | `%LOCALAPPDATA%\MikroDok\logs\` |
| macOS | `~/Library/Logs/MikroDok/` |
| Linux | `~/.local/share/MikroDok/logs/` |

### Support Bundle

```bash
# Generate support bundle
mikrodok --support-bundle

# Creates: mikrodok-support-YYYYMMDD-HHMMSS.zip
# Contains: logs, config, system info, crash reports
```

---

*Last Updated: 2025-01-15*
*Version: 0.1.0-alpha*