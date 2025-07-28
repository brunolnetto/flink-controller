# Flink Job Controller

A production-ready, declarative Flink job controller for managing streaming and batch job lifecycles with enterprise-grade security, observability, and resilience.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Git
- Docker (optional, for monitoring stack)

### Installation

#### Option 1: Automated Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd flink-controller

# Run automated setup
./scripts/setup.sh          # Linux/macOS
# OR
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1  # Windows
```

#### Option 2: Manual Setup
```bash
# 1. Install Just Command Runner
# Linux/macOS
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash

# Windows (WSL2)
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash

# macOS (Homebrew)
brew install just

# 2. Clone and Setup
git clone <repository-url>
cd flink-controller

# Install development dependencies
just install-dev

# Install pre-commit hooks
just pre-commit-install
```

#### 3. Environment Configuration
Create a `.env` file:
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

## 🛠️ Development Workflow

### Feature Development
```bash
# Create a new feature
just feature job-deployer

# Complete feature workflow
just feature-complete job-deployer
```

### TDD Development
```bash
# Run TDD cycle
just tdd tests/unit/test_deployer.py::test_deploy_job_success

# Complete TDD cycle
just tdd-cycle tests/unit/test_deployer.py test_deploy_job_success
```

### Testing
```bash
# Run all tests with coverage (90%+ required)
just test-coverage

# Run specific test categories
just test-unit          # Unit tests
just test-integration   # Integration tests
just test-contract      # Contract tests
just test-chaos         # Chaos tests
just test-security      # Security tests

# Test with real Flink cluster
just test-flink-real
```

### Code Quality
```bash
# Run quality checks
just quality-check

# Fix formatting
just quality-fix

# Run pre-commit hooks
just pre-commit-run
```

### Security
```bash
# Security scanning
just security-scan

# Security testing
just security-test
```

## 📊 Monitoring

### Start Monitoring Stack
```bash
# Start monitoring (Prometheus, Grafana, Jaeger)
just monitor-start

# View dashboards
just monitor-dashboards

# Stop monitoring
just monitor-stop
```

## 🏗️ Architecture

### Core Components
- **Job Controller**: Declarative job lifecycle management
- **Security Manager**: Authentication, authorization, credential management
- **Resilience Manager**: Circuit breakers, retry logic, graceful degradation
- **Observability Stack**: Structured logging, metrics, distributed tracing
- **Artifact Verifier**: Digital signatures, checksums, integrity validation

### Key Features
- **Declarative Control Loop**: Reconciling desired vs. current state
- **Idempotency**: Hash-based change detection
- **Production Security**: Kerberos, SSL/TLS, API key authentication
- **Enterprise Observability**: Prometheus, Grafana, Jaeger integration
- **Reality-Based Testing**: Integration, contract, and chaos testing

## 📚 Documentation

### Core Documents
- [`roadmap.md`](roadmap.md) - Production implementation specification
- [`implementation-policies.md`](implementation-policies.md) - Development standards
- [`development-workflow.md`](development-workflow.md) - Practical workflow guide
- [`assets-description.md`](assets-description.md) - Asset overview and usage
- [`milestone-tracker.md`](milestone-tracker.md) - Project progress tracking

### Component Design
```bash
# Create component design document
just design JobDeployer
```

## 🔧 Available Commands

### Development
```bash
just feature <name>              # Create feature branch
just design <component>          # Create component design doc
just tdd <test>                 # Run TDD cycle
just tdd-cycle <file> <func>    # Complete TDD cycle
```

### Testing
```bash
just test-unit                  # Unit tests
just test-integration           # Integration tests
just test-contract              # Contract tests
just test-chaos                 # Chaos tests
just test-all                   # All tests
just test-coverage              # Tests with coverage
just test-flink-real            # Real Flink cluster tests
just test-security              # Security tests
```

### Quality
```bash
just quality-check              # Code quality checks
just quality-fix                # Fix formatting
just pre-commit-run             # Run pre-commit hooks
just pre-commit-install         # Install pre-commit hooks
```

### Security
```bash
just security-scan              # Security scanning
just security-test              # Security testing
```

### Monitoring
```bash
just monitor-start              # Start monitoring stack
just monitor-stop               # Stop monitoring stack
just monitor-dashboards         # View dashboards
```

### Utilities
```bash
just status                     # Project status
just clean                      # Clean temporary files
just build                      # Build application
just release <version>          # Create release
just help                       # Show help
```

## 🧪 Testing Philosophy

### Reality-Based Testing
We emphasize **real-world confidence** over excessive mocking:

- **Integration Tests**: Test with real systems when possible
- **Contract Tests**: Validate that mocks match real API behavior
- **Chaos Tests**: Test system resilience under real failure conditions
- **Security Tests**: Use real authentication flows, never mock security

### Test Categories
- **Unit Tests**: Fast, isolated, comprehensive
- **Integration Tests**: Real system interaction
- **Contract Tests**: API behavior validation
- **Chaos Tests**: Resilience under failure
- **Security Tests**: Real authentication flows
- **Performance Tests**: Load and stress testing
- **End-to-End Tests**: Complete workflow validation

## 🔒 Security

### Authentication Methods
- **Kerberos**: Enterprise authentication
- **API Key**: Simple authentication
- **SSL/TLS**: Secure communication
- **Credential Rotation**: Automatic credential management

### Security Features
- **Input Validation**: Comprehensive validation
- **Audit Logging**: Security event tracking
- **Secure Communication**: TLS encryption
- **Credential Management**: Secure storage and rotation

## 📈 Observability

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards
- **Jaeger**: Distributed tracing
- **Structured Logging**: Correlation IDs and context

### Key Metrics
- Job deployment success/failure rates
- Authentication success/failure rates
- API response times and error rates
- System resource utilization
- Security event monitoring

## 🚀 Deployment

### Build
```bash
just build
```

### Release
```bash
just release v1.0.0
```

### Docker
```bash
# Development
docker build -f Dockerfile.dev -t flink-controller-dev .

# Production
docker build -t flink-controller .
```

## 🤝 Contributing

### Development Standards
- Follow TDD workflow
- Maintain 90%+ test coverage
- Use reality-based testing approach
- Follow SOLID principles
- Implement comprehensive error handling

### Quality Gates
- All tests must pass
- Code coverage must be 90%+
- Security scan must pass
- Code quality checks must pass
- Integration tests must pass

### Pull Request Process
1. Create feature branch: `just feature <name>`
2. Implement with TDD: `just tdd <test>`
3. Run quality checks: `just quality-check`
4. Run all tests: `just test-all`
5. Submit pull request

## 📋 Project Status

Current progress and milestones are tracked in [`milestone-tracker.md`](milestone-tracker.md).

### Completed Milestones
- ✅ Secure credential management
- ✅ Flink REST API authentication
- ✅ Artifact signature verification
- ✅ Development workflow automation
- ✅ Reality-based testing framework

### In Progress
- 🔄 Job deployment engine
- 🔄 State management system
- 🔄 Monitoring integration

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

### Platform-Specific

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

## 📄 License

[License information]

## 🆘 Support

For issues and questions:
- Check troubleshooting section
- Review documentation
- Create issue in repository
- Contact development team

---

**Built with ❤️ following production-ready standards and reality-based testing principles.** 