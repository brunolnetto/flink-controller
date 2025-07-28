# Flink Job Controller - Development Environment Setup (Windows)
# This script ensures consistent setup on Windows systems

param(
    [switch]$Quick,
    [switch]$Force
)

# Function to write colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Function to check if command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Function to install Just command runner
function Install-Just {
    if (Test-Command "just") {
        Write-Success "Just command runner already installed"
        return $true
    }

    Write-Status "Installing Just command runner..."
    
    # Check if we're in WSL2
    if ($env:WSL_DISTRO_NAME) {
        Write-Status "WSL2 detected, installing via curl..."
        try {
            Invoke-Expression "curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash"
            Write-Success "Just command runner installed successfully"
            return $true
        }
        catch {
            Write-Error "Failed to install Just command runner"
            return $false
        }
    }
    else {
        Write-Warning "Windows native detected. Please install Just manually:"
        Write-Warning "1. Visit: https://just.systems/"
        Write-Warning "2. Download and install the Windows version"
        Write-Warning "3. Or use WSL2 for better compatibility"
        return $false
    }
}

# Function to install Python dependencies
function Install-PythonDeps {
    Write-Status "Installing Python dependencies..."
    
    # Check Python version
    if (-not (Test-Command "python")) {
        Write-Error "Python not found. Please install Python 3.8+ from https://python.org/"
        return $false
    }

    $pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Status "Python version: $pythonVersion"

    # Create virtual environment if it doesn't exist
    if (-not (Test-Path "venv")) {
        Write-Status "Creating virtual environment..."
        python -m venv venv
    }

    # Activate virtual environment
    Write-Status "Activating virtual environment..."
    & "venv\Scripts\Activate.ps1"

    # Upgrade pip
    Write-Status "Upgrading pip..."
    python -m pip install --upgrade pip

    # Install development dependencies
    Write-Status "Installing development dependencies..."
    pip install -r requirements-dev.txt

    Write-Success "Python dependencies installed successfully"
    return $true
}

# Function to setup pre-commit hooks
function Setup-PreCommit {
    Write-Status "Setting up pre-commit hooks..."
    
    if (Test-Command "pre-commit") {
        pre-commit install
        Write-Success "Pre-commit hooks installed successfully"
        return $true
    }
    else {
        Write-Warning "Pre-commit not found. Please install it manually: pip install pre-commit"
        return $false
    }
}

# Function to create environment file
function Create-EnvFile {
    if (-not (Test-Path ".env")) {
        Write-Status "Creating .env file..."
        @"
# Flink credentials (for real integration tests)
export FLINK_USERNAME="your-username"
export FLINK_PASSWORD="your-password"
export FLINK_API_KEY="your-api-key"
export FLINK_REST_URL="http://localhost:8081"

# Development settings
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export LOG_LEVEL="DEBUG"
"@ | Out-File -FilePath ".env" -Encoding UTF8
        Write-Success ".env file created. Please update with your actual credentials."
    }
    else {
        Write-Status ".env file already exists"
    }
}

# Function to verify setup
function Test-Setup {
    Write-Status "Verifying setup..."
    
    $errors = 0
    
    # Check Just
    if (-not (Test-Command "just")) {
        Write-Error "Just command runner not found"
        $errors++
    }
    
    # Check Python
    if (-not (Test-Command "python")) {
        Write-Error "Python not found"
        $errors++
    }
    
    # Check virtual environment
    if (-not (Test-Path "venv")) {
        Write-Error "Virtual environment not found"
        $errors++
    }
    
    # Check dependencies
    if (Test-Path "venv") {
        & "venv\Scripts\Activate.ps1"
        try {
            python -c "import pytest" 2>$null
        }
        catch {
            Write-Error "pytest not found in virtual environment"
            $errors++
        }
    }
    
    if ($errors -eq 0) {
        Write-Success "Setup verification completed successfully"
        return $true
    }
    else {
        Write-Error "Setup verification failed with $errors error(s)"
        return $false
    }
}

# Function to show next steps
function Show-NextSteps {
    Write-Host ""
    Write-Success "Setup completed! Next steps:"
    Write-Host ""
    Write-Host "1. Update your credentials in .env file:"
    Write-Host "   notepad .env"
    Write-Host ""
    Write-Host "2. Activate virtual environment:"
    Write-Host "   venv\Scripts\Activate.ps1"
    Write-Host ""
    Write-Host "3. Run initial tests:"
    Write-Host "   just test-unit"
    Write-Host ""
    Write-Host "4. Start development:"
    Write-Host "   just feature my-feature"
    Write-Host ""
    Write-Host "5. View available commands:"
    Write-Host "   just --list"
    Write-Host ""
    Write-Host "6. Get help:"
    Write-Host "   just help"
    Write-Host ""
}

# Main setup function
function Main {
    Write-Host "🚀 Flink Job Controller - Development Environment Setup (Windows)" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Check if we should proceed
    if (-not $Quick) {
        $response = Read-Host "This will install dependencies and configure the environment. Continue? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            Write-Host "Setup cancelled."
            exit 0
        }
    }
    
    # Install Just
    $justInstalled = Install-Just
    
    # Install Python dependencies
    $pythonInstalled = Install-PythonDeps
    
    # Setup pre-commit hooks
    $preCommitInstalled = Setup-PreCommit
    
    # Create environment file
    Create-EnvFile
    
    # Verify setup
    if (Test-Setup) {
        Show-NextSteps
    }
    else {
        Write-Error "Setup verification failed. Please check the errors above."
        exit 1
    }
}

# Run main function
Main 