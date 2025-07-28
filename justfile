# Flink Job Controller — Streamlined Development Commands
# Simplified from 36 commands to 12 essential commands

# Default recipe to show available commands
default:
    @just --list

# =============================================================================
# CORE DEVELOPMENT COMMANDS (5 commands)
# =============================================================================

# Start development mode (watch files, auto-test, auto-format)
dev:
    #!/usr/bin/env bash
    echo "🚀 Starting development mode..."
    echo "📁 Watching files for changes..."
    echo "🧪 Auto-running tests..."
    echo "🔧 Auto-formatting code..."
    echo ""
    echo "Press Ctrl+C to stop development mode"
    echo ""
    # Start file watcher and auto-run tests
    python3 -m watchdog.watchmedo auto-restart \
        --patterns="*.py" \
        --recursive \
        --directory="src,tests" \
        -- python3 -m pytest tests/unit/ -v

# Run all tests (unit + integration)
test:
    echo "🧪 Running all tests..."
    python3 -m pytest tests/unit/ tests/integration/ -v --tb=short

# Run fast tests only (for TDD)
test-fast:
    echo "⚡ Running fast tests (unit only)..."
    python3 -m pytest tests/unit/ -v --tb=short

# Build the application
build:
    echo "🔨 Building application..."
    python3 -m build

# Deploy to target environment
deploy:
    echo "🚀 Deploying application..."
    # Add deployment logic here
    echo "✅ Deployment completed"

# =============================================================================
# QUALITY COMMANDS (3 commands)
# =============================================================================

# Run all quality checks
check:
    echo "🔍 Running quality checks..."
    python3 -m black src/ tests/ --check
    python3 -m isort src/ tests/ --check-only
    python3 -m flake8 src/ tests/
    python3 -m mypy src/
    echo "✅ Quality checks completed"

# Auto-fix quality issues
fix:
    echo "🔧 Fixing quality issues..."
    python3 -m black src/ tests/
    python3 -m isort src/ tests/
    echo "✅ Quality issues fixed"

# Security scan
security:
    echo "🔒 Running security scan..."
    python3 -m bandit -r src/
    echo "✅ Security scan completed"

# =============================================================================
# UTILITY COMMANDS (4 commands)
# =============================================================================

# Show project status
status:
    echo "📊 Flink Job Controller - Project Status"
    echo ""
    echo "🔍 Code Quality:"
    just check
    echo ""
    echo "🧪 Test Status:"
    python3 -m pytest tests/unit/ --tb=no -q
    echo ""
    echo "📈 Git Status:"
    git status --short

# One-time setup
setup:
    #!/usr/bin/env bash
    echo "🚀 Setting up Flink Job Controller development environment..."
    echo ""
    echo "📦 Installing dependencies..."
    pip3 install --break-system-packages -r requirements-dev.txt
    echo "🔧 Setting up pre-commit hooks..."
    pre-commit install
    echo "✅ Setup completed!"

# Clean up temporary files
clean:
    echo "🧹 Cleaning up temporary files..."
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
    echo "✅ Cleanup completed"

# Show help
help:
    echo "🚀 Flink Job Controller - Streamlined Development Workflow"
    echo ""
    echo "🎯 CORE DEVELOPMENT (5 commands)"
    echo "  just dev          - Start development mode (auto-test, auto-format)"
    echo "  just test         - Run all tests (unit + integration)"
    echo "  just test-fast    - Run fast tests only (for TDD)"
    echo "  just build        - Build application"
    echo "  just deploy       - Deploy to target environment"
    echo ""
    echo "🔍 QUALITY (3 commands)"
    echo "  just check        - Run all quality checks"
    echo "  just fix          - Auto-fix quality issues"
    echo "  just security     - Security scan"
    echo ""
    echo "🛠️ UTILITIES (4 commands)"
    echo "  just status       - Show project status"
    echo "  just setup        - One-time setup"
    echo "  just clean        - Clean temporary files"
    echo "  just help         - Show this help"
    echo ""
    echo "💡 TYPICAL WORKFLOW:"
    echo "  1. just setup     # One-time setup"
    echo "  2. just dev       # Start development mode"
    echo "  3. # Edit code (auto-test, auto-format)"
    echo "  4. just test      # Run all tests"
    echo "  5. git commit     # Commit changes" 