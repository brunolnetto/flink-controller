# Developer Experience Guide

## Overview
This document ensures consistent developer experience across different environments and platforms, providing a unified workflow regardless of the developer's setup.

## 🎯 Core Principles

### 1. **Justfile as Primary Interface**
- All development tasks go through the Justfile
- Consistent commands across all platforms
- Reduced cognitive load for developers
- Automated quality gates and workflows

### 2. **Cross-Platform Compatibility**
- Linux (Ubuntu/Debian)
- macOS (with Homebrew)
- Windows (native and WSL2)
- Docker containers

### 3. **Reality-Based Testing**
- Integration tests with real systems
- Contract validation against real APIs
- Chaos testing under real failure conditions
- Security testing with real authentication

### 4. **Quality-First Approach**
- 90%+ test coverage requirement
- Automated code quality checks
- Pre-commit hooks for consistency
- Security scanning integration

## 🚀 Getting Started

### Environment Setup

#### Automated Setup (Recommended)
```bash
# Linux/macOS
./scripts/setup.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

# Windows (WSL2)
./scripts/setup.sh
```

#### Manual Setup
```bash
# Install Just command runner
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash

# Setup project
just install-dev
just pre-commit-install
```

### First-Time Developer Experience
```bash
# 1. Clone and setup
git clone <repo-url>
cd flink-controller
just setup

# 2. Configure environment
nano .env  # Update with your credentials

# 3. Verify setup
just status
just test-unit

# 4. Start development
just feature my-first-feature
```

## 🛠️ Development Workflow

### Feature Development
```bash
# Create feature branch
just feature job-deployer

# This automatically:
# - Creates feature branch
# - Sets up development environment
# - Creates component design document
# - Initializes test structure
```

### TDD Development
```bash
# Run TDD cycle
just tdd tests/unit/test_deployer.py::test_deploy_job_success

# Complete TDD cycle
just tdd-cycle tests/unit/test_deployer.py test_deploy_job_success
```

### Testing Strategy
```bash
# Unit tests (fast, isolated)
just test-unit

# Integration tests (real systems)
just test-integration

# Contract tests (API validation)
just test-contract

# Chaos tests (resilience)
just test-chaos

# Security tests (real auth)
just security-test

# All tests with coverage
just test-coverage
```

### Quality Assurance
```bash
# Run quality checks
just quality-check

# Fix formatting
just quality-fix

# Run pre-commit hooks
just pre-commit-run
```

## 🔧 Platform-Specific Considerations

### Linux (Ubuntu/Debian)
```bash
# System dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl

# Setup
./scripts/setup.sh
```

### macOS
```bash
# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Just
brew install just

# Setup
./scripts/setup.sh
```

### Windows (Native)
```bash
# Install Python from https://python.org/
# Install Just from https://just.systems/

# Setup via PowerShell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

### Windows (WSL2)
```bash
# Enable WSL2 and install Ubuntu
wsl --install

# Setup (same as Linux)
./scripts/setup.sh
```

### Docker Development
```bash
# Build development container
docker build -f Dockerfile.dev -t flink-controller-dev .

# Run with Justfile
docker run -it --rm -v $(pwd):/app flink-controller-dev just test-all
```

## 📊 Monitoring and Observability

### Local Development
```bash
# Start monitoring stack
just monitor-start

# View dashboards
just monitor-dashboards

# Stop monitoring
just monitor-stop
```

### Available Dashboards
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **Jaeger**: http://localhost:16686

## 🔒 Security Development

### Credential Management
```bash
# Set up credentials in .env file
export FLINK_USERNAME="your-username"
export FLINK_PASSWORD="your-password"
export FLINK_API_KEY="your-api-key"
export FLINK_REST_URL="http://localhost:8081"
```

### Security Testing
```bash
# Security scanning
just security-scan

# Security testing with real auth
just security-test
```

## 🧪 Testing Philosophy

### Reality-Based Testing
We emphasize **real-world confidence** over excessive mocking:

1. **Integration Tests**: Test with real systems when possible
2. **Contract Tests**: Validate that mocks match real API behavior
3. **Chaos Tests**: Test system resilience under real failure conditions
4. **Security Tests**: Use real authentication flows, never mock security

### Test Categories
- **Unit Tests**: Fast, isolated, comprehensive (90%+ coverage)
- **Integration Tests**: Real system interaction
- **Contract Tests**: API behavior validation
- **Chaos Tests**: Resilience under failure
- **Security Tests**: Real authentication flows
- **Performance Tests**: Load and stress testing
- **End-to-End Tests**: Complete workflow validation

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Development Workflow
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install Just
        run: |
          curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash
      - name: Install dependencies
        run: just install-dev
      - name: Run tests
        run: just test-coverage
      - name: Quality check
        run: just quality-check
      - name: Security scan
        run: just security-scan
```

## 🆘 Troubleshooting

### Common Issues

#### Environment Setup
```bash
# Check project status
just status

# Reset development environment
just clean
just install-dev
```

#### Testing Issues
```bash
# Verify test environment
just test-unit

# Check with real systems
just test-flink-real
```

#### Quality Issues
```bash
# Fix formatting
just quality-fix

# Run pre-commit hooks
just pre-commit-run
```

### Platform-Specific Issues

#### Windows/WSL2
- Ensure WSL2 is properly configured
- Use `just install-dev` for dependency installation
- Set environment variables in `.env` file

#### macOS
- Use Homebrew for package management
- Install Just via Homebrew: `brew install just`
- Follow standard setup process

#### Linux
- Use system package manager for prerequisites
- Follow standard setup process
- Ensure Python 3.8+ is available

## 📚 Documentation Standards

### Keeping Documentation Current
- Update component design docs: `just design <component>`
- Update API documentation after changes
- Update README.md with new features
- Update CHANGELOG.md for releases

### Documentation Quality
- Use clear, concise language
- Include code examples
- Provide troubleshooting guides
- Keep setup instructions current

## 🎯 Success Metrics

### Developer Experience
- **Setup Time**: < 5 minutes for new developers
- **Command Consistency**: Same commands work across all platforms
- **Error Resolution**: Clear troubleshooting guides
- **Documentation**: Always up-to-date and accurate

### Quality Metrics
- **Test Coverage**: 90%+ maintained
- **Code Quality**: All checks pass
- **Security**: No vulnerabilities in scans
- **Integration**: Real system tests pass

### Productivity Metrics
- **TDD Cycle**: < 30 seconds for unit tests
- **Quality Gates**: Automated and fast
- **Deployment**: One-command deployment
- **Monitoring**: Real-time visibility

## 🔄 Continuous Improvement

### Feedback Loop
- Regular developer surveys
- Setup time tracking
- Error rate monitoring
- Documentation usage analytics

### Iteration Process
- Monthly workflow reviews
- Quarterly tool evaluation
- Annual architecture assessment
- Continuous documentation updates

This guide ensures that every developer, regardless of their environment, has a consistent, high-quality experience while maintaining our production-ready standards and reality-based testing approach. 