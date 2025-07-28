# Flink Job Controller — Development Commands
# This Justfile encapsulates all development workflow commands from our development-workflow.md

# Default recipe to show available commands
default:
    @just --list

# =============================================================================
# PHASE 0: ENVIRONMENT SETUP
# =============================================================================

# Setup development environment
setup:
    #!/usr/bin/env bash
    echo "🚀 Setting up Flink Job Controller development environment..."
    echo "This will install dependencies and configure the environment."
    echo ""
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./scripts/setup.sh
    else
        echo "Setup cancelled."
        exit 0
    fi

# Quick setup (non-interactive)
setup-quick:
    echo "🚀 Quick setup - installing dependencies..."
    ./scripts/setup.sh

# =============================================================================
# PHASE 1: PLANNING & DESIGN
# =============================================================================

# Create a new feature branch
feature branch:
    #!/usr/bin/env bash
    if [ -z "$1" ]; then
        echo "Usage: just feature <branch-name>"
        echo "Example: just feature job-deployer-validation"
        exit 1
    fi
    git checkout -b feature/$1
    echo "✅ Created feature branch: feature/$1"

# Create component design document
design component:
    #!/usr/bin/env bash
    if [ -z "$1" ]; then
        echo "Usage: just design <component-name>"
        echo "Example: just design JobDeployer"
        exit 1
    fi
    mkdir -p docs/design
    echo "# $1 Component Design" > docs/design/$1.md
    echo "" >> docs/design/$1.md
    echo "## Responsibilities" >> docs/design/$1.md
    echo "TODO: Define component responsibilities" >> docs/design/$1.md
    echo "" >> docs/design/$1.md
    echo "## Interfaces" >> docs/design/$1.md
    echo "TODO: Define public interfaces" >> docs/design/$1.md
    echo "" >> docs/design/$1.md
    echo "## Dependencies" >> docs/design/$1.md
    echo "TODO: List component dependencies" >> docs/design/$1.md
    echo "" >> docs/design/$1.md
    echo "## Security Considerations" >> docs/design/$1.md
    echo "TODO: Security impact assessment" >> docs/design/$1.md
    echo "TODO: Authentication/authorization requirements" >> docs/design/$1.md
    echo "TODO: Input validation strategy" >> docs/design/$1.md
    echo "" >> docs/design/$1.md
    echo "## Test Strategy" >> docs/design/$1.md
    echo "TODO: Unit test scenarios" >> docs/design/$1.md
    echo "TODO: Integration test scenarios" >> docs/design/$1.md
    echo "TODO: Contract test scenarios" >> docs/design/$1.md
    echo "TODO: Chaos test scenarios" >> docs/design/$1.md
    echo "✅ Created design document: docs/design/$1.md"

# =============================================================================
# PHASE 2: TDD DEVELOPMENT
# =============================================================================

# Run TDD cycle for a specific test
tdd test:
    #!/usr/bin/env bash
    if [ -z "$1" ]; then
        echo "Usage: just tdd <test-file>::<test-function>"
        echo "Example: just tdd tests/unit/test_deployer.py::test_deploy_job_success"
        exit 1
    fi
    echo "🔴 TDD Red Phase: Running failing test..."
    python3 -m pytest $1 -v
    echo "📝 Now implement minimal code to make test pass"
    echo "🟢 Then run: just tdd $1"

# Run all unit tests
test-unit:
    python3 -m pytest tests/unit/ -v

# Run integration tests with real systems
test-integration:
    python3 -m pytest tests/integration/ -v

# Run contract validation tests
test-contract:
    python3 -m pytest tests/contract/ -v

# Run chaos tests
test-chaos:
    python3 -m pytest tests/chaos/ -v

# Run all tests (unit + integration + contract)
test-all:
    python3 -m pytest tests/unit/ tests/integration/ tests/contract/ -v

# Run tests with coverage
test-coverage:
    python3 -m pytest tests/unit/ tests/integration/ tests/contract/ --cov=src --cov-report=term --cov-report=html --cov-fail-under=90

# Run security tests (real authentication only)
test-security:
    python3 -m pytest tests/security/ -v

# =============================================================================
# PHASE 3: CODE QUALITY & REVIEW
# =============================================================================

# Run all code quality checks
quality-check:
    echo "🔍 Running code quality checks..."
    python3 -m black src/ tests/ --check
    python3 -m isort src/ tests/ --check-only
    python3 -m flake8 src/ tests/
    python3 -m mypy src/
    echo "✅ Code quality checks completed"

# Fix code formatting
quality-fix:
    echo "🔧 Fixing code formatting..."
    python3 -m black src/ tests/
    python3 -m isort src/ tests/
    echo "✅ Code formatting fixed"

# Run pre-commit hooks
pre-commit-run:
    pre-commit run --all-files

# Install pre-commit hooks
pre-commit-install:
    pre-commit install

# =============================================================================
# PHASE 4: TESTING & VALIDATION
# =============================================================================

# Run performance tests
test-performance:
    python3 -m pytest tests/performance/ -v

# Run end-to-end tests
test-e2e:
    python3 -m pytest tests/e2e/ -v

# Run tests with real Flink cluster
test-flink-real:
    #!/usr/bin/env bash
    if [ -z "$FLINK_REST_URL" ]; then
        echo "❌ FLINK_REST_URL environment variable not set"
        echo "Set it to your Flink cluster REST API URL"
        echo "Example: export FLINK_REST_URL=http://localhost:8081"
        exit 1
    fi
    echo "🔗 Testing with real Flink cluster: $FLINK_REST_URL"
    python3 -m pytest tests/integration/test_flink_real.py -v

# Validate contracts against real APIs
test-contracts-validate:
    #!/usr/bin/env bash
    if [ -z "$FLINK_REST_URL" ]; then
        echo "❌ FLINK_REST_URL environment variable not set"
        exit 1
    fi
    echo "📋 Validating contracts against real Flink API..."
    python3 -m pytest tests/contract/test_flink_contract.py -v

# =============================================================================
# PHASE 5: SECURITY REVIEW
# =============================================================================

# Run security scan
security-scan:
    echo "🔒 Running security scan..."
    bandit -r src/
    safety check
    echo "✅ Security scan completed"

# Run security tests with real authentication
security-test:
    #!/usr/bin/env bash
    if [ -z "$FLINK_USERNAME" ] || [ -z "$FLINK_PASSWORD" ] || [ -z "$FLINK_API_KEY" ]; then
        echo "❌ Flink credentials not set"
        echo "Set FLINK_USERNAME, FLINK_PASSWORD, and FLINK_API_KEY"
        exit 1
    fi
    echo "🔐 Running security tests with real authentication..."
    python3 -m pytest tests/security/ -v

# =============================================================================
# PHASE 6: DEPLOYMENT & RELEASE
# =============================================================================

# Build the application
build:
    echo "🏗️ Building Flink Job Controller..."
    python3 -m build
    echo "✅ Build completed"

# Run deployment tests
test deployment:
    python3 -m pytest tests/deployment/ -v

# Create release
release version:
    #!/usr/bin/env bash
    if [ -z "$1" ]; then
        echo "Usage: just release <version>"
        echo "Example: just release 1.0.0"
        exit 1
    fi
    echo "🚀 Creating release v$1..."
    git tag -a v$1 -m "Release v$1"
    git push origin v$1
    echo "✅ Release v$1 created and pushed"

# =============================================================================
# PHASE 7: MONITORING & OBSERVABILITY
# =============================================================================

# Start monitoring stack
monitor-start:
    echo "📊 Starting monitoring stack..."
    docker-compose -f docker/monitoring.yml up -d
    echo "✅ Monitoring stack started"

# Stop monitoring stack
monitor-stop:
    echo "🛑 Stopping monitoring stack..."
    docker-compose -f docker/monitoring.yml down
    echo "✅ Monitoring stack stopped"

# View monitoring dashboards
monitor-dashboards:
    echo "📈 Monitoring dashboards:"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000"
    echo "  - Jaeger: http://localhost:16686"

# =============================================================================
# DEVELOPMENT WORKFLOW RECIPES
# =============================================================================

# Complete TDD cycle for a new feature
tdd-cycle test-file test-function:
    #!/usr/bin/env bash
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo "Usage: just tdd-cycle <test-file> <test-function>"
        echo "Example: just tdd-cycle tests/unit/test_deployer.py test_deploy_job_success"
        exit 1
    fi
    echo "🔄 Starting TDD cycle for $1::$2"
    echo "🔴 Step 1: Red - Write failing test"
    echo "📝 Edit $1 to add failing test: $2"
    echo "🟢 Step 2: Green - Implement minimal code"
    echo "🔧 Step 3: Refactor - Improve implementation"
    echo ""
    echo "Commands to run:"
    echo "  just tdd $1::$2"
    echo "  just test unit"
    echo "  just quality check"
    echo "  just test integration"

# Complete feature development workflow
feature-complete branch-name:
    #!/usr/bin/env bash
    if [ -z "$1" ]; then
        echo "Usage: just feature-complete <branch-name>"
        exit 1
    fi
    echo "🎯 Complete feature development workflow for: $1"
    echo ""
    echo "1. Create feature branch:"
    echo "   just feature $1"
    echo ""
    echo "2. Develop with TDD:"
    echo "   just tdd-cycle <test-file> <test-function>"
    echo ""
    echo "3. Run all tests:"
    echo "   just test all"
    echo "   just test coverage"
    echo ""
    echo "4. Code quality:"
    echo "   just quality check"
    echo "   just pre-commit"
    echo ""
    echo "5. Security review:"
    echo "   just security scan"
    echo "   just security test"
    echo ""
    echo "6. Commit and push:"
    echo "   git add ."
    echo "   git commit -m 'feat($1): implement feature with TDD'"
    echo "   git push origin feature/$1"

# =============================================================================
# UTILITY COMMANDS
# =============================================================================

# Show project status
status:
    echo "📊 Flink Job Controller - Project Status"
    echo ""
    echo "🔍 Code Quality:"
    just quality-check
    echo ""
    echo "🧪 Test Coverage:"
    python3 -m pytest tests/unit/ --cov=src --cov-report=term-missing
    echo ""
    echo "📈 Git Status:"
    git status --short

# Clean up temporary files
clean:
    echo "🧹 Cleaning up temporary files..."
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
    echo "✅ Cleanup completed"

# Install development dependencies
install-dev:
    echo "📦 Installing development dependencies..."
    pip3 install -r requirements.txt
    pip3 install -r requirements-dev.txt
    just pre-commit install
    echo "✅ Development environment setup completed"

# Show help for development workflow
help:
    echo "🚀 Flink Job Controller - Development Workflow"
    echo ""
    echo "🔧 PHASE 0: ENVIRONMENT SETUP"
    echo "  just setup                    - Interactive environment setup"
    echo "  just setup-quick              - Quick non-interactive setup"
    echo ""
    echo "📋 PHASE 1: PLANNING & DESIGN"
    echo "  just feature <name>           - Create feature branch"
    echo "  just design <component>       - Create component design doc"
    echo ""
    echo "🧪 PHASE 2: TDD DEVELOPMENT"
    echo "  just tdd <test>               - Run TDD cycle for specific test"
    echo "  just test-unit                - Run unit tests"
    echo "  just test-integration         - Run integration tests"
    echo "  just test-contract            - Run contract tests"
    echo "  just test-chaos               - Run chaos tests"
    echo "  just test-all                 - Run all tests"
    echo "  just test-coverage            - Run tests with coverage"
    echo "  just test-flink-real          - Test with real Flink cluster"
    echo ""
    echo "🔍 PHASE 3: CODE QUALITY"
    echo "  just quality-check            - Run code quality checks"
    echo "  just quality-fix              - Fix code formatting"
    echo "  just pre-commit-run           - Run pre-commit hooks"
    echo ""
    echo "🔒 PHASE 5: SECURITY"
    echo "  just security-scan            - Run security scan"
    echo "  just security-test            - Run security tests"
    echo ""
    echo "🚀 PHASE 6: DEPLOYMENT"
    echo "  just build                    - Build application"
    echo "  just release <version>        - Create release"
    echo ""
    echo "📊 PHASE 7: MONITORING"
    echo "  just monitor-start            - Start monitoring stack"
    echo "  just monitor-stop             - Stop monitoring stack"
    echo ""
    echo "🔄 WORKFLOW RECIPES"
    echo "  just tdd-cycle <file> <func>  - Complete TDD cycle"
    echo "  just feature-complete <name>  - Complete feature workflow"
    echo ""
    echo "🛠️ UTILITIES"
    echo "  just status                   - Show project status"
    echo "  just clean                    - Clean temporary files"
    echo "  just install-dev              - Install dev dependencies"
    echo "  just help                     - Show this help" 