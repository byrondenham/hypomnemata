# Installation Guide

This guide provides detailed installation instructions for Hypomnemata on different platforms.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
  - [pipx (Recommended)](#pipx-recommended)
  - [pip](#pip)
  - [Single-File Executable](#single-file-executable)
  - [From Source](#from-source)
- [Platform-Specific Instructions](#platform-specific-instructions)
  - [Linux](#linux)
  - [macOS](#macos)
  - [Windows](#windows)
- [Verifying Installation](#verifying-installation)
- [Verifying Downloads](#verifying-downloads)
- [Upgrading](#upgrading)
- [Uninstalling](#uninstalling)

## Prerequisites

- Python 3.10 or higher
- For pipx: `pipx` installed (see [pipx installation](https://pipx.pypa.io/stable/installation/))

## Installation Methods

### pipx (Recommended)

`pipx` installs Python CLI tools in isolated environments, preventing dependency conflicts:

```bash
pipx install hypomnemata
```

This creates a `hypo` command available in your PATH.

**Benefits:**
- Isolated environment (no dependency conflicts)
- Easy to upgrade and uninstall
- Automatic PATH management

### pip

Install globally or in a virtual environment:

```bash
# Global install (may require sudo on Linux/macOS)
pip install hypomnemata

# Or in a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install hypomnemata
```

### Single-File Executable

Download a `.pyz` file for your platform from the [releases page](https://github.com/byrondenham/hypomnemata/releases).

**Linux/macOS:**
```bash
# Download
curl -L -o hypo.pyz https://github.com/byrondenham/hypomnemata/releases/latest/download/hypo-linux-x86_64.pyz

# Make executable
chmod +x hypo.pyz

# Move to PATH (optional)
sudo mv hypo.pyz /usr/local/bin/hypo

# Or run directly
./hypo.pyz --version
```

**Windows:**
```powershell
# Download using PowerShell
Invoke-WebRequest -Uri "https://github.com/byrondenham/hypomnemata/releases/latest/download/hypo-windows.pyz" -OutFile "hypo.pyz"

# Run with Python
python hypo.pyz --version

# Create a batch file wrapper (optional)
# Create hypo.bat with: @python "%~dp0hypo.pyz" %*
```

### From Source

For development or the latest unreleased changes:

```bash
# Clone the repository
git clone https://github.com/byrondenham/hypomnemata.git
cd hypomnemata

# Install in editable mode
pip install -e .

# Or with all optional dependencies
pip install -e ".[dev,api,watch]"
```

## Platform-Specific Instructions

### Linux

#### Ubuntu/Debian

```bash
# Install Python 3.10+ if needed
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Install pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install hypomnemata
pipx install hypomnemata
```

#### Fedora/RHEL

```bash
# Install Python 3.10+ if needed
sudo dnf install python3 python3-pip

# Install pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install hypomnemata
pipx install hypomnemata
```

#### Arch Linux

```bash
# Install Python (usually already installed)
sudo pacman -S python python-pip

# Install pipx
python -m pip install --user pipx
python -m pipx ensurepath

# Install hypomnemata
pipx install hypomnemata
```

### macOS

#### Using Homebrew

```bash
# Install Python 3.10+ if needed
brew install python@3.12

# Install pipx
brew install pipx
pipx ensurepath

# Install hypomnemata
pipx install hypomnemata
```

#### Without Homebrew

```bash
# Python 3 should be pre-installed on recent macOS
# Install pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install hypomnemata
pipx install hypomnemata
```

### Windows

#### Using Python from python.org

1. Download and install Python 3.10+ from [python.org](https://www.python.org/downloads/)
   - ✓ Check "Add Python to PATH" during installation

2. Install pipx:
```powershell
python -m pip install --user pipx
python -m pipx ensurepath
```

3. Restart your terminal, then:
```powershell
pipx install hypomnemata
```

#### Using Windows Store Python

1. Install Python from the Microsoft Store

2. Install pipx and hypomnemata:
```powershell
python -m pip install --user pipx
python -m pipx ensurepath
# Restart terminal
pipx install hypomnemata
```

## Verifying Installation

After installation, verify it works:

```bash
# Check version
hypo --version

# Should output something like:
# hypomnemata 0.9.0 (python 3.12.3 / platform linux / commit abc1234)

# Check help
hypo --help

# Create a test vault
mkdir test-vault
cd test-vault
hypo new --title "Test Note"
```

## Verifying Downloads

For security, verify the checksum of downloaded files:

1. Download the `.pyz` file and `SHA256SUMS.txt` from the release page

2. Verify the checksum:

**Linux/macOS:**
```bash
sha256sum -c SHA256SUMS.txt 2>&1 | grep hypo-linux-x86_64.pyz
# Should show: hypo-linux-x86_64.pyz: OK
```

**Windows (PowerShell):**
```powershell
# Get the hash
$hash = (Get-FileHash hypo-windows.pyz -Algorithm SHA256).Hash.ToLower()

# Compare with SHA256SUMS.txt
Select-String -Path SHA256SUMS.txt -Pattern "hypo-windows.pyz"
# Manually compare the hashes
```

## Upgrading

### pipx

```bash
pipx upgrade hypomnemata
```

### pip

```bash
pip install --upgrade hypomnemata
```

### Single-File Executable

Download the latest `.pyz` file and replace the old one.

### From Source

```bash
cd hypomnemata
git pull
pip install -e .
```

## Uninstalling

### pipx

```bash
pipx uninstall hypomnemata
```

### pip

```bash
pip uninstall hypomnemata
```

### Single-File Executable

Simply delete the `.pyz` file and any wrapper scripts.

## Troubleshooting

### Command not found after installation

**pipx:**
- Run `pipx ensurepath` and restart your terminal
- Check if `~/.local/bin` (Linux/macOS) or `%USERPROFILE%\.local\bin` (Windows) is in your PATH

**pip:**
- Check if Python's scripts directory is in your PATH
- On Linux/macOS: Usually `~/.local/bin`
- On Windows: Usually `%APPDATA%\Python\Python3XX\Scripts`

### Permission errors

**Linux/macOS:**
- Don't use `sudo` with pip or pipx for user installations
- If you must use system Python, use a virtual environment instead

**Windows:**
- Run PowerShell as Administrator only if absolutely necessary
- Prefer user installations over system-wide

### Python version too old

Check your Python version:
```bash
python --version
# or
python3 --version
```

Hypomnemata requires Python 3.10 or higher. Install a newer Python version for your platform.

## Next Steps

After installation:

1. Read the [README.md](README.md) for a quick start guide
2. See [CLI_DEMO.md](CLI_DEMO.md) for comprehensive examples
3. Check [CONTRIBUTING.md](CONTRIBUTING.md) if you want to contribute
4. Review [SECURITY.md](SECURITY.md) for security best practices
