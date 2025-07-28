#!/bin/bash

# Flink Job Controller - Development Environment Setup
# This script ensures consistent setup across different environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     
            if command_exists lsb_release; then
                echo "$(lsb_release -si | tr '[:upper:]' '[:lower:]')"
            else
                echo "linux"
            fi
            ;;
        Darwin*)    echo "macos";;
        CYGWIN*)    echo "windows";;
        MINGW*)     echo "windows";;
        MSYS*)      echo "windows";;
        *)          echo "unknown";;
    esac
}

# Function to install Just command runner
install_just() {
    if command_exists just; then
        print_success "Just command runner already installed"
        return 0
    fi

    print_status "Installing Just command runner..."
    
    case "$(detect_os)" in
        "macos")
            if command_exists brew; then
                brew install just
            else
                print_error "Homebrew not found. Please install Homebrew first: https://brew.sh/"
                return 1
            fi
            ;;
        "linux"|"ubuntu"|"debian")
            curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash
            ;;
        "windows")
            print_warning "Windows detected. Please install Just manually: https://just.systems/"
            print_warning "Or use WSL2 for better compatibility"
            return 1
            ;;
        *)
            print_error "Unsupported OS: $(uname -s)"
            return 1
            ;;
    esac

    if command_exists just; then
        print_success "Just command runner installed successfully"
    else
        print_error "Failed to install Just command runner"
        return 1
    fi
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Check Python version
    if ! command_exists python3; then
        print_error "Python 3 not found. Please install Python 3.8+"
        return 1
    fi

    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_status "Python version: $PYTHON_VERSION"

    # Install system dependencies (Linux only)
    if [[ "$(detect_os)" == "linux" ]]; then
        print_status "Installing system dependencies..."
        sudo apt update
        sudo apt install -y python3-venv python3-pip
    fi

    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate

    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip

    # Install development dependencies
    print_status "Installing development dependencies..."
    pip install -r requirements-dev.txt

    print_success "Python dependencies installed successfully"
}

# Function to setup pre-commit hooks
setup_pre_commit() {
    print_status "Setting up pre-commit hooks..."
    
    if command_exists pre-commit; then
        pre-commit install
        print_success "Pre-commit hooks installed successfully"
    else
        print_warning "Pre-commit not found. Please install it manually: pip install pre-commit"
    fi
}

# Function to create environment file
create_env_file() {
    if [[ ! -f ".env" ]]; then
        print_status "Creating .env file..."
        cat > .env << 'EOF'
# Flink credentials (for real integration tests)
export FLINK_USERNAME="your-username"
export FLINK_PASSWORD="your-password"
export FLINK_API_KEY="your-api-key"
export FLINK_REST_URL="http://localhost:8081"

# Development settings
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export LOG_LEVEL="DEBUG"
EOF
        print_success ".env file created. Please update with your actual credentials."
    else
        print_status ".env file already exists"
    fi
}

# Function to verify setup
verify_setup() {
    print_status "Verifying setup..."
    
    local errors=0
    
    # Check Just
    if ! command_exists just; then
        print_error "Just command runner not found"
        ((errors++))
    fi
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 not found"
        ((errors++))
    fi
    
    # Check virtual environment
    if [[ ! -d "venv" ]]; then
        print_error "Virtual environment not found"
        ((errors++))
    fi
    
    # Check dependencies
    if [[ -d "venv" ]]; then
        source venv/bin/activate
        if ! python3 -c "import pytest" 2>/dev/null; then
            print_error "pytest not found in virtual environment"
            ((errors++))
        fi
    fi
    
    if [[ $errors -eq 0 ]]; then
        print_success "Setup verification completed successfully"
        return 0
    else
        print_error "Setup verification failed with $errors error(s)"
        return 1
    fi
}

# Function to show next steps
show_next_steps() {
    echo
    print_success "Setup completed! Next steps:"
    echo
    echo "1. Update your credentials in .env file:"
    echo "   nano .env"
    echo
    echo "2. Activate virtual environment:"
    echo "   source venv/bin/activate"
    echo
    echo "3. Run initial tests:"
    echo "   just test-unit"
    echo
    echo "4. Start development:"
    echo "   just feature my-feature"
    echo
    echo "5. View available commands:"
    echo "   just --list"
    echo
    echo "6. Get help:"
    echo "   just help"
    echo
}

# Main setup function
main() {
    echo "🚀 Flink Job Controller - Development Environment Setup"
    echo "======================================================"
    echo
    
    # Detect OS
    OS=$(detect_os)
    print_status "Detected OS: $OS"
    
    # Install Just
    install_just
    
    # Install Python dependencies
    install_python_deps
    
    # Setup pre-commit hooks
    setup_pre_commit
    
    # Create environment file
    create_env_file
    
    # Verify setup
    if verify_setup; then
        show_next_steps
    else
        print_error "Setup verification failed. Please check the errors above."
        exit 1
    fi
}

# Run main function
main "$@" 