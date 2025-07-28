# Development Workflow

## Overview
This document operationalizes the implementation policies defined in `implementation-policies.md` into a practical development workflow.

## 1. Environment Setup

### 1.1 Prerequisites
```bash
# Required system packages
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl

# Install Just command runner
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash
```

### 1.2 Project Setup
```bash
# Clone the repository
git clone <repository-url>
cd flink-controller

# Install development dependencies
just install-dev

# Install pre-commit hooks
just pre-commit-install
```

### 1.3 Environment Variables
Create a `.env` file for local development:
```bash
# Flink credentials (for real integration tests)
export FLINK_USERNAME="your-username"
export FLINK_PASSWORD="your-password"
export FLINK_API_KEY="your-api-key"
export FLINK_REST_URL="http://localhost:8081"

# Development settings
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export LOG_LEVEL="DEBUG"
```

## 2. Development Workflow

### 2.1 Feature Development
```bash
# Create a new feature branch
just feature job-deployer

# This will:
# - Create feature branch
# - Set up development environment
# - Create component design document
# - Initialize test structure
```

### 2.2 TDD Development Cycle
```bash
# Run TDD cycle for a specific test
just tdd tests/unit/test_deployer.py::test_deploy_job_success

# Complete TDD cycle for new feature
just tdd-cycle tests/unit/test_deployer.py test_deploy_job_success
```

### 2.3 Reality-Based Testing Integration

#### Step 2.3.1: Integration Test with Real Systems
```bash
# Test with real Flink cluster
just test-flink-real

# Run all integration tests
just test-integration
```

#### Step 2.3.2: Contract Validation
```bash
# Validate contracts against real APIs
just test-contracts-validate

# Run contract tests
just test-contract
```

#### Step 2.3.3: Chaos Testing
```bash
# Run chaos engineering tests
just test-chaos
```

### 2.4 TDD Development Commands
```bash
# Run unit tests
just test-unit

# Run tests with coverage (90%+ required)
just test-coverage

# Run all tests
just test-all

# Run security tests with real authentication
just security-test
```

## 3. Code Quality & Review

### 3.1 Automated Quality Checks
```bash
# Run all quality checks
just quality-check

# Fix formatting issues
just quality-fix

# Run pre-commit hooks
just pre-commit-run
```

### 3.2 Manual Review Checklist
- [ ] Code follows SOLID principles
- [ ] Error handling is comprehensive
- [ ] Logging includes correlation IDs
- [ ] Security considerations addressed
- [ ] Integration tests cover real scenarios
- [ ] Documentation is updated

## 4. Testing Strategy

### 4.1 Test Categories
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

# Performance tests
just test-performance

# End-to-end tests
just test-e2e
```

### 4.2 Coverage Requirements
- **Minimum Coverage**: 90%
- **Critical Paths**: 100%
- **Security Components**: 100%
- **Integration Points**: 95%

### 4.3 Reality-Based Testing
- **No Mocked Security**: Use real authentication flows
- **Integration First**: Prefer real system integration
- **Contract Validation**: Ensure mocks match real APIs
- **Chaos Engineering**: Test under real failure conditions

## 5. Security Review

### 5.1 Security Scanning
```bash
# Run security scan
just security-scan

# Run security tests
just security-test
```

### 5.2 Security Checklist
- [ ] No hardcoded credentials
- [ ] Input validation implemented
- [ ] Authentication flows tested
- [ ] Authorization checks in place
- [ ] Secure communication (TLS)
- [ ] Audit logging configured

## 6. Deployment & Operations

### 6.1 Build Process
```bash
# Build application
just build

# Create release
just release v1.0.0
```

### 6.2 Monitoring Setup
```bash
# Start monitoring stack
just monitor-start

# View dashboards
just monitor-dashboards

# Stop monitoring
just monitor-stop
```

## 7. Cross-Environment Consistency

### 7.1 Development Environment
```bash
# Ensure consistent setup
just status

# Clean temporary files
just clean
```

### 7.2 CI/CD Integration
The Justfile commands are designed to work in CI/CD pipelines:
```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    just test-coverage
    just quality-check
    just security-scan
```

### 7.3 Docker Development
```bash
# Build development container
docker build -f Dockerfile.dev -t flink-controller-dev .

# Run with Justfile
docker run -it --rm -v $(pwd):/app flink-controller-dev just test-all
```

## 8. Troubleshooting

### 8.1 Common Issues
```bash
# Reset development environment
just clean
just install-dev

# Check project status
just status

# Verify Justfile commands
just --list
```

### 8.2 Environment-Specific Setup
```bash
# Windows (WSL2)
just install-dev

# macOS
brew install just
just install-dev

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash
just install-dev
```

## 9. Workflow Automation

### 9.1 Complete Feature Workflow
```bash
# Start to finish feature development
just feature-complete job-deployer
```

### 9.2 Quick Development Commands
```bash
# Quick TDD cycle
just tdd <test-name>

# Quick quality check
just quality-check

# Quick test run
just test-unit
```

## 10. Documentation Updates

### 10.1 Keeping Documentation Current
- Update component design docs: `just design <component>`
- Update API documentation after changes
- Update README.md with new features
- Update CHANGELOG.md for releases

### 10.2 Documentation Standards
- Use clear, concise language
- Include code examples
- Provide troubleshooting guides
- Keep setup instructions current

This workflow ensures consistent developer experience across all environments while maintaining our quality standards and reality-based testing approach. 