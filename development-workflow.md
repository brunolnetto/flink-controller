# Streamlined Development Workflow

## 🎯 **Overview**
This document provides a **simple, practical** development workflow that gets you coding quickly without overwhelming complexity.

## 🚀 **Quick Start (5 minutes)**

### **1. Setup (One-time)**
```bash
# Clone and setup
git clone <repository-url>
cd flink-controller
just setup
```

### **2. Start Development**
```bash
# Start development mode (auto-test, auto-format)
just dev
```

### **3. Typical Workflow**
```bash
# Edit code → Tests run automatically
# When ready to commit:
just test        # Run all tests
git commit       # Commit changes
```

## 🔧 **12 Essential Commands**

### **Core Development (5 commands)**
```bash
just dev          # Start development mode (auto-test, auto-format)
just test         # Run all tests (unit + integration)
just test-fast    # Run fast tests only (for TDD)
just build        # Build application
just deploy       # Deploy to target environment
```

### **Quality (3 commands)**
```bash
just check        # Run all quality checks
just fix          # Auto-fix quality issues
just security     # Security scan
```

### **Utilities (4 commands)**
```bash
just status       # Show project status
just setup        # One-time setup
just clean        # Clean temporary files
just help         # Show help
```

## 🧪 **Simple TDD Workflow**

### **TDD Cycle (Simplified)**
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

### **Test Categories (Simplified)**
```bash
# Fast tests (for TDD)
just test-fast    # Unit tests only, < 30 seconds

# All tests (before commit)
just test         # Unit + integration tests

# Security tests (weekly)
just security     # Security scan
```

## 📊 **Progressive Quality Gates**

### **Development Phase**
```yaml
# During development (relaxed)
quality_requirements:
  test_coverage: 70%+ (not 90%+)
  quality_checks: Optional
  security_scan: Weekly
  pre_commit_hooks: Disabled
```

### **Production Phase**
```yaml
# Before production (strict)
quality_requirements:
  test_coverage: 90%+
  quality_checks: Required
  security_scan: Every commit
  pre_commit_hooks: Enabled
```

## 🔍 **Environment Setup**

### **Prerequisites**
```bash
# Required system packages
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl

# Install Just command runner
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash
```

### **Project Setup**
```bash
# One command setup
just setup

# This will:
# - Install dependencies
# - Setup pre-commit hooks
# - Configure environment
```

### **Environment Variables**
```bash
# Create .env file for local development
export FLINK_USERNAME="your-username"
export FLINK_PASSWORD="your-password"
export FLINK_API_KEY="your-api-key"
export FLINK_REST_URL="http://localhost:8081"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export LOG_LEVEL="DEBUG"
```

## 🚀 **Development Workflow Examples**

### **Example 1: New Feature Development**
```bash
# 1. Start development
just dev

# 2. Create new feature branch
git checkout -b feature/new-job-deployer

# 3. Write tests first (TDD)
# Edit tests/unit/test_job_deployer.py
# Tests run automatically

# 4. Implement feature
# Edit src/core/job_deployer.py
# Tests run automatically

# 5. Run all tests
just test

# 6. Commit changes
git commit -m "feat: implement job deployer"
```

### **Example 2: Bug Fix**
```bash
# 1. Start development
just dev

# 2. Create bug fix branch
git checkout -b fix/circuit-breaker-issue

# 3. Write test that reproduces bug
# Edit test file → Tests run automatically

# 4. Fix the bug
# Edit source file → Tests run automatically

# 5. Run all tests
just test

# 6. Commit fix
git commit -m "fix: resolve circuit breaker state transition issue"
```

### **Example 3: Quality Improvement**
```bash
# 1. Check current quality
just status

# 2. Fix quality issues
just fix

# 3. Run security scan
just security

# 4. Run all tests
just test

# 5. Commit improvements
git commit -m "style: fix code quality issues"
```

## 📈 **Progressive Enhancement**

### **Phase 1: Foundation (Weeks 1-4)**
```yaml
focus:
  - "Get basic functionality working"
  - "70%+ test coverage"
  - "Basic security"
  - "Simple deployment"

workflow:
  - "just dev for development"
  - "just test before commit"
  - "Weekly security scan"
```

### **Phase 2: Core Features (Weeks 5-8)**
```yaml
focus:
  - "Complete core functionality"
  - "80%+ test coverage"
  - "Integration with real Flink"
  - "Performance baselines"

workflow:
  - "just dev for development"
  - "just test before commit"
  - "Weekly security scan"
  - "Performance testing"
```

### **Phase 3: Production Ready (Weeks 9-12)**
```yaml
focus:
  - "Production deployment"
  - "90%+ test coverage"
  - "Zero security vulnerabilities"
  - "Complete monitoring"

workflow:
  - "just dev for development"
  - "just test before commit"
  - "just security before commit"
  - "Performance testing"
  - "Monitoring validation"
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Issue: Tests not running automatically**
```bash
# Check if development mode is running
# Make sure you're in the right directory
# Check file permissions
ls -la tests/unit/
```

#### **Issue: Quality checks failing**
```bash
# Auto-fix what can be fixed
just fix

# Check what's left
just check
```

#### **Issue: Security scan failing**
```bash
# Check for hardcoded secrets
# Review security scan output
just security
```

#### **Issue: Dependencies not found**
```bash
# Reinstall dependencies
just setup
```

### **Getting Help**
```bash
# Show all available commands
just help

# Show project status
just status

# Show specific command help
just --help dev
```

## 📚 **Best Practices**

### **Development Best Practices**
1. **Start with `just dev`** - Always use development mode
2. **Write tests first** - Follow TDD principles
3. **Run tests before commit** - Use `just test`
4. **Fix quality issues** - Use `just fix`
5. **Check status regularly** - Use `just status`

### **Code Quality Best Practices**
1. **Use type hints** - For all function signatures
2. **Write docstrings** - For all public methods
3. **Follow PEP 8** - Use Black formatter
4. **Keep functions small** - Single responsibility
5. **Handle errors gracefully** - Proper exception handling

### **Testing Best Practices**
1. **Test the behavior, not implementation** - Focus on what, not how
2. **Use descriptive test names** - Clear what is being tested
3. **Keep tests fast** - Unit tests should be < 1 second
4. **Use real data when possible** - Avoid over-mocking
5. **Test error scenarios** - Don't just test happy path

---

This streamlined workflow focuses on **getting you coding quickly** while maintaining quality through **progressive enhancement**. Start simple, improve over time. 