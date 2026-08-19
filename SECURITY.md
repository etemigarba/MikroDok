# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability in MikroDok, please report it responsibly.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please email the details to:
**etemigarba@users.noreply.github.com**

Include the following information:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Affected versions (if known)
- Any suggested mitigation or fix

### Response Timeline

| Phase | Timeline |
|-------|----------|
| Acknowledgment | Within 48 hours |
| Initial Assessment | Within 1 week |
| Fix Development | Within 4 weeks (depending on severity) |
| Patch Release | Within 2 weeks of fix completion |
| Public Disclosure | After patch release |

## Security Features

MikroDok is designed with security as a core principle:

### Offline-First Architecture
- **Zero network dependency** for core functionality
- No telemetry, analytics, or external API calls by default
- All model training, inference, and data processing occurs locally
- Air-gapped deployment fully supported

### Data Protection
- **AES-256 encryption** for model artifacts at rest (optional, via SQLCipher)
- **PBKDF2-SHA512** with 256,000 iterations for key derivation
- **Secure memory handling** with explicit zeroing of sensitive data
- **SHA-256 integrity verification** for all model checkpoints
- **HMAC-SHA256** for tamper detection on exported models

### Access Control
- **OS-level authentication** integration (Windows/macOS/Linux)
- **Role-based access**: Read-only, Standard User, Admin
- **Session management** with 24-hour expiry
- **Audit logging** for all model operations

### Compliance
- **GDPR Ready**: Right to erasure, data portability, consent management
- **HIPAA Compatible**: Healthcare data handling capabilities
- **Data Residency**: Local storage only, no cross-border data transfer
- **Export Controls**: Configurable geographic restrictions

## Threat Model

### Assets Protected
1. **User Documents** - Source documents for training
2. **Model Artifacts** - Trained models, checkpoints, ONNX exports
3. **Training Data** - Processed chunks, embeddings, metrics
4. **Configuration** - Resource allocation profiles, system settings
5. **Intellectual Property** - Proprietary algorithms (IDRAlloc)

### Threat Scenarios

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Local privilege escalation | Medium | High | Least-privilege execution, sandboxing |
| Model theft via filesystem | Low | High | Encryption, access controls |
| Data exfiltration | Very Low | High | Offline-first, no network stack |
| Supply chain attack | Low | Critical | Dependency pinning, hash verification |
| Side-channel attacks | Low | Medium | Constant-time operations, memory protection |

## Secure Development Practices

### Dependency Management
- All dependencies pinned to specific versions in `requirements.txt`
- `pip-audit` run weekly in CI
- Dependabot alerts monitored and addressed within 72 hours
- Only officially signed packages from PyPI

### Code Security
- **Parameterized queries** for all database operations (SQLite)
- **Input validation** on all user-provided data
- **Path traversal prevention** for file operations
- **Resource limits** to prevent DoS via resource exhaustion
- **Secure defaults** for all configuration options

### Build Security
- **Reproducible builds** with locked dependencies
- **Code signing** for all distributed binaries (Windows/macOS)
- **SBOM generation** (Software Bill of Materials) for each release
- **Scan for secrets** in CI pipeline (truffleHog, detect-secrets)

## Vulnerability Disclosure Process

1. **Report Received** - Acknowledgment within 48 hours
2. **Triage** - Severity assessment (CVSS 4.0)
3. **Investigation** - Root cause analysis
4. **Fix Development** - Patch with test coverage
5. **Testing** - Regression and security testing
6. **Release** - Patched version with security advisory
7. **Disclosure** - Public advisory after patch availability

### Severity Classification

| CVSS Score | Severity | Response Target |
|------------|----------|-----------------|
| 9.0-10.0 | Critical | 72 hours |
| 7.0-8.9 | High | 1 week |
| 4.0-6.9 | Medium | 2 weeks |
| 0.1-3.9 | Low | Next release |

## Security Best Practices for Users

### Installation
- Verify installer signatures (Windows: Authenticode, macOS: Notarization)
- Download only from official GitHub Releases
- Validate SHA-256 checksums

### Configuration
- Enable database encryption for sensitive environments
- Configure resource limits appropriate for your hardware
- Disable telemetry (enabled by default as opt-in only)
- Set strong thermal limits to prevent hardware damage

### Operation
- Keep NVIDIA drivers updated for security patches
- Monitor GPU temperature during extended training
- Regular backup of model registry and configurations
- Use dedicated non-admin user account for daily operation

### Model Deployment
- Verify ONNX model integrity before deployment
- Use quantization appropriate for your security requirements
- Implement rate limiting for inference endpoints
- Monitor for adversarial inputs in production

## Known Security Considerations

### GPU Memory Residue
- **Issue**: GPU memory may retain model weights after process termination
- **Mitigation**: Explicit `torch.cuda.empty_cache()` on shutdown, OS-level memory clearing

### Temporary Files
- **Issue**: Document processing creates temporary files
- **Mitigation**: Secure deletion (DoD 5220.22-M 7-pass) for sensitive documents

### Python Pickle Deserialization
- **Issue**: PyTorch model loading uses pickle
- **Mitigation**: Only load models from trusted sources, validate checksums first

### NVMe Wear
- **Issue**: Heavy swap usage may reduce SSD lifespan
- **Mitigation**: Monitor SMART attributes, configure swap size limits, use enterprise-grade NVMe

## Contact

For security-related questions or concerns:
- **Email**: etemigarba@users.noreply.github.com
- **PGP Key**: Available on request
- **Response Time**: 48 hours maximum

---

**Last Updated**: 2025-01-15
**Version**: 1.0
**Project**: MikroDok Document Language Model Builder
**Copyright**: © 2025 Etemi Joshua Garba