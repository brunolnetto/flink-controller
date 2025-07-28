# Flink Job Controller

A production-ready, declarative Flink job controller with enterprise-grade security and observability.

## 🚀 Quick Start (5 minutes)

### 1. Setup
```bash
git clone <repository-url>
cd flink-controller
just setup
```

### 2. Start Development
```bash
just dev          # Auto-test, auto-format
# Edit code → Tests run automatically
```

### 3. Typical Workflow
```bash
just test         # Run all tests
git commit        # Commit changes
```

## 🔧 Essential Commands

### Development (5 commands)
```bash
just dev          # Development mode (auto-test, auto-format)
just test         # All tests (unit + integration)
just test-fast    # Fast tests only (TDD)
just build        # Build application
just deploy       # Deploy to target
```

### Quality (3 commands)
```bash
just check        # Quality checks
just fix          # Auto-fix issues
just security     # Security scan
```

### Utilities (4 commands)
```bash
just status       # Project status
just setup        # One-time setup
just clean        # Clean temporary files
just help         # Show help
```

## 🧪 TDD Workflow

```bash
# 1. Start development mode
just dev

# 2. Write failing test
# Edit test file → Tests run automatically

# 3. Write minimal code to pass
# Edit source file → Tests run automatically

# 4. Refactor
# Edit code → Tests run automatically

# 5. Commit when ready
just test
git commit
```

## 📊 Progressive Quality

### Development Phase
- **Test Coverage**: 70%+ (not 90%+)
- **Quality Checks**: Optional
- **Security Scan**: Weekly

### Production Phase
- **Test Coverage**: 90%+
- **Quality Checks**: Required
- **Security Scan**: Every commit

## 🏗️ Architecture

### Core Components
- **Job Controller**: Declarative job lifecycle management
- **Security Manager**: Authentication and credential management
- **Resilience Manager**: Circuit breakers and retry logic
- **Observability**: Structured logging and metrics

### Key Features
- **Declarative Control Loop**: Reconciling desired vs. current state
- **Production Security**: Kerberos, SSL/TLS, API key authentication
- **Enterprise Observability**: Prometheus, Grafana integration
- **Reality-Based Testing**: Integration with real systems

## 📚 Documentation

- [`roadmap.md`](roadmap.md) - Implementation specification
- [`implementation-policies.md`](implementation-policies.md) - Development standards
- [`development-workflow.md`](development-workflow.md) - Workflow guide
- [`milestone-tracker.md`](milestone-tracker.md) - Progress tracking

## 🔒 Security

### Authentication
- **Kerberos**: Enterprise authentication
- **API Key**: Simple authentication
- **SSL/TLS**: Secure communication

### Security Features
- **Input Validation**: Comprehensive validation
- **Audit Logging**: Security event tracking
- **Credential Management**: Secure storage and rotation

## 📈 Observability

### Monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards
- **Structured Logging**: Correlation IDs and context

### Key Metrics
- Job deployment success/failure rates
- API response times and error rates
- System resource utilization

## 🚀 Deployment

```bash
just build        # Build application
just deploy       # Deploy to target
```

## 🤝 Contributing

### Development Standards
- Follow TDD workflow
- Progressive test coverage (70% → 80% → 90%)
- Reality-based testing approach
- Comprehensive error handling

### Pull Request Process
1. Create feature branch
2. Implement with TDD: `just dev`
3. Run tests: `just test`
4. Submit pull request

## 📋 Project Status

Current progress tracked in [`milestone-tracker.md`](milestone-tracker.md).

### Completed
- ✅ Secure credential management
- ✅ Flink REST API authentication
- ✅ Artifact signature verification
- ✅ Streamlined development workflow

### In Progress
- 🔄 Circuit breaker pattern
- 🔄 State management system
- 🔄 Job lifecycle management

## 🔧 Troubleshooting

### Common Issues

#### Setup Issues
```bash
just status       # Check project status
just setup        # Re-run setup
```

#### Test Issues
```bash
just test-fast    # Run fast tests
just clean        # Clean temporary files
```

#### Quality Issues
```bash
just fix          # Auto-fix issues
just check        # Check what's left
```

### Getting Help
```bash
just help         # Show all commands
just status       # Check project status
```

## 📄 License

[License information]

---

**Built with ❤️ following production-ready standards and progressive enhancement.** 