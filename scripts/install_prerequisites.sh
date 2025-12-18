#!/usr/bin/env bash
#
# install_prerequisites.sh
# ========================
# Idempotent script to install all prerequisites for NS-3 VANET simulation
# on Debian 13 (Trixie).
#
# This script installs:
# - NS-3 build dependencies (C++ toolchain, CMake, libraries)
# - 802.11p/WAVE support dependencies
# - SUMO traffic simulator (optional)
# - Python scientific stack
#
# Usage: sudo ./install_prerequisites.sh
#
# Author: VANET Project Team
# Course: Data Communications and Computer Networks
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/install_prerequisites.log"
MARKER_FILE="${SCRIPT_DIR}/.prerequisites_installed"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $*"
    log "INFO" "$*"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
    log "SUCCESS" "$*"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
    log "WARNING" "$*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    log "ERROR" "$*"
}

die() {
    error "$*"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root. Use: sudo $0"
    fi
}

check_debian() {
    if [[ ! -f /etc/os-release ]]; then
        die "Cannot detect OS. /etc/os-release not found."
    fi

    source /etc/os-release

    if [[ "${ID}" != "debian" ]]; then
        warn "This script is designed for Debian. Detected: ${ID}"
        warn "Proceeding anyway, but some packages may differ."
    fi

    info "Detected OS: ${PRETTY_NAME:-${ID} ${VERSION_ID}}"
}

is_package_installed() {
    dpkg -l "$1" 2>/dev/null | grep -q "^ii"
}

install_package() {
    local package="$1"
    if is_package_installed "${package}"; then
        info "Package '${package}' is already installed. Skipping."
    else
        info "Installing package: ${package}"
        apt-get install -y "${package}" >> "${LOG_FILE}" 2>&1 || {
            warn "Failed to install ${package}. Continuing..."
            return 1
        }
        success "Installed: ${package}"
    fi
    return 0
}

install_packages() {
    local packages=("$@")
    local failed=()

    for pkg in "${packages[@]}"; do
        install_package "${pkg}" || failed+=("${pkg}")
    done

    if [[ ${#failed[@]} -gt 0 ]]; then
        warn "Failed to install: ${failed[*]}"
    fi
}

# ============================================================================
# MAIN INSTALLATION FUNCTIONS
# ============================================================================

update_system() {
    info "Updating package lists..."
    apt-get update >> "${LOG_FILE}" 2>&1

    info "Upgrading installed packages..."
    apt-get upgrade -y >> "${LOG_FILE}" 2>&1

    success "System updated successfully."
}

install_build_essentials() {
    info "Installing build essentials and C++ toolchain..."

    local packages=(
        # Core build tools
        build-essential
        gcc
        g++
        clang
        cmake
        ninja-build
        ccache

        # Version control
        git
        git-lfs
        mercurial

        # Build systems
        autoconf
        automake
        libtool
        pkg-config

        # Compression and archives
        tar
        gzip
        bzip2
        xz-utils
        unzip

        # Text processing
        gawk
        sed

        # Utilities
        wget
        curl
        ca-certificates
        gnupg
    )

    install_packages "${packages[@]}"
    success "Build essentials installed."
}

install_ns3_dependencies() {
    info "Installing NS-3 core dependencies..."

    local packages=(
        # Python (NS-3 bindings and waf)
        python3
        python3-dev
        python3-pip
        python3-venv
        python3-setuptools

        # Boost libraries (required by many NS-3 modules)
        libboost-all-dev

        # SQLite (for statistics)
        sqlite3
        libsqlite3-dev

        # XML processing
        libxml2
        libxml2-dev

        # GTK for visualization (optional but recommended)
        libgtk-3-dev

        # GLib
        libglib2.0-dev

        # GSL (GNU Scientific Library)
        libgsl-dev

        # Cryptographic libraries
        libssl-dev
        libgcrypt20-dev

        # Qt5 (for NetAnim)
        qt5-qmake
        qtbase5-dev
        qtchooser

        # Doxygen for documentation
        doxygen
        graphviz
        imagemagick

        # Debugging tools
        gdb
        valgrind

        # Flex and Bison (for parsers)
        flex
        bison

        # Click modular router (optional)
        # libclick-dev

        # OpenFlow support (optional)
        # libpcap-dev

        # MPI for distributed simulation (optional)
        openmpi-bin
        libopenmpi-dev
    )

    install_packages "${packages[@]}"
    success "NS-3 core dependencies installed."
}

install_wave_dependencies() {
    info "Installing 802.11p/WAVE specific dependencies..."

    local packages=(
        # Network simulation libraries
        libpcap-dev

        # Wireless tools
        wireless-tools
        iw

        # Additional networking
        net-tools
        iputils-ping
        tcpdump
        wireshark-common
        tshark
    )

    install_packages "${packages[@]}"
    success "802.11p/WAVE dependencies installed."
}

install_sumo() {
    info "Installing SUMO traffic simulator..."

    # Check if SUMO is already installed
    if command -v sumo &> /dev/null; then
        local version
        version=$(sumo --version 2>/dev/null | head -1 || echo "unknown")
        info "SUMO is already installed: ${version}"
        return 0
    fi

    # Try to install from official repositories
    local packages=(
        sumo
        sumo-tools
        sumo-doc
    )

    # First, try official Debian repos
    if apt-cache show sumo &> /dev/null; then
        install_packages "${packages[@]}"
    else
        warn "SUMO not found in repositories. Installing from SUMO PPA..."

        # Add SUMO repository
        apt-get install -y software-properties-common >> "${LOG_FILE}" 2>&1

        # For Debian, we may need to build from source or use a compatible repo
        # Try the Eclipse SUMO repository
        if [[ ! -f /etc/apt/sources.list.d/sumo.list ]]; then
            echo "deb https://eclipse.dev/sumo/releases/latest/debian/ stable main" > /etc/apt/sources.list.d/sumo.list
            wget -qO - https://eclipse.dev/sumo/releases/latest/sumo.gpg | apt-key add - 2>/dev/null || true
            apt-get update >> "${LOG_FILE}" 2>&1 || true
        fi

        install_packages "${packages[@]}" || {
            warn "Could not install SUMO from repository."
            warn "SUMO can be built from source if needed."
            warn "See: https://sumo.dlr.de/docs/Installing/index.html"
        }
    fi

    # Verify installation
    if command -v sumo &> /dev/null; then
        success "SUMO installed successfully."
        sumo --version 2>/dev/null | head -1 || true
    else
        warn "SUMO installation incomplete. Manual installation may be required."
    fi
}

install_python_scientific() {
    info "Installing Python scientific stack..."

    # System packages for Python scientific computing
    local packages=(
        python3-numpy
        python3-scipy
        python3-pandas
        python3-matplotlib
        python3-seaborn
        python3-sklearn
        python3-networkx
        python3-lxml
        python3-yaml
        python3-h5py
        python3-tables
        python3-xlrd
        python3-openpyxl
    )

    install_packages "${packages[@]}"

    # Create a virtual environment for additional packages
    local venv_dir="/opt/vanet-venv"

    if [[ ! -d "${venv_dir}" ]]; then
        info "Creating Python virtual environment at ${venv_dir}..."
        python3 -m venv "${venv_dir}"
    fi

    info "Installing additional Python packages via pip..."

    # Activate venv and install packages
    source "${venv_dir}/bin/activate"

    pip install --upgrade pip >> "${LOG_FILE}" 2>&1

    # Core scientific packages
    pip install \
        numpy \
        pandas \
        matplotlib \
        seaborn \
        scipy \
        scikit-learn \
        >> "${LOG_FILE}" 2>&1

    # Additional useful packages
    pip install \
        tqdm \
        joblib \
        pyyaml \
        xmltodict \
        >> "${LOG_FILE}" 2>&1

    # Deep learning (optional, for autoencoder)
    pip install \
        tensorflow \
        keras \
        >> "${LOG_FILE}" 2>&1 || {
        warn "TensorFlow installation failed. Trying PyTorch instead..."
        pip install torch >> "${LOG_FILE}" 2>&1 || warn "PyTorch also failed. AI features may be limited."
    }

    deactivate

    # Create activation script
    cat > "${SCRIPT_DIR}/activate_venv.sh" << 'EOF'
#!/usr/bin/env bash
# Source this file to activate the VANET Python environment
# Usage: source activate_venv.sh

VENV_DIR="/opt/vanet-venv"

if [[ -d "${VENV_DIR}" ]]; then
    source "${VENV_DIR}/bin/activate"
    echo "VANET Python environment activated."
    echo "Python: $(which python)"
    echo "Pip: $(which pip)"
else
    echo "Error: Virtual environment not found at ${VENV_DIR}"
    echo "Run install_prerequisites.sh first."
fi
EOF
    chmod +x "${SCRIPT_DIR}/activate_venv.sh"

    success "Python scientific stack installed."
    info "Activate with: source ${SCRIPT_DIR}/activate_venv.sh"
}

install_visualization_tools() {
    info "Installing visualization and analysis tools..."

    local packages=(
        # Plotting
        gnuplot
        gnuplot-qt

        # Image processing
        imagemagick

        # PDF tools
        texlive-latex-base
        texlive-latex-extra
        texlive-fonts-recommended

        # Video (for animations)
        ffmpeg
    )

    install_packages "${packages[@]}"
    success "Visualization tools installed."
}

verify_installation() {
    info "Verifying installation..."

    local errors=0

    # Check C++ compiler
    if command -v g++ &> /dev/null; then
        success "g++ found: $(g++ --version | head -1)"
    else
        error "g++ not found!"
        ((errors++))
    fi

    # Check CMake
    if command -v cmake &> /dev/null; then
        success "CMake found: $(cmake --version | head -1)"
    else
        error "CMake not found!"
        ((errors++))
    fi

    # Check Python
    if command -v python3 &> /dev/null; then
        success "Python3 found: $(python3 --version)"
    else
        error "Python3 not found!"
        ((errors++))
    fi

    # Check Git
    if command -v git &> /dev/null; then
        success "Git found: $(git --version)"
    else
        error "Git not found!"
        ((errors++))
    fi

    # Check SUMO (optional)
    if command -v sumo &> /dev/null; then
        success "SUMO found: $(sumo --version 2>/dev/null | head -1 || echo 'version unknown')"
    else
        warn "SUMO not found (optional)"
    fi

    # Check virtual environment
    if [[ -d "/opt/vanet-venv" ]]; then
        success "Python virtual environment found at /opt/vanet-venv"
    else
        warn "Python virtual environment not found"
    fi

    if [[ ${errors} -gt 0 ]]; then
        die "Verification failed with ${errors} error(s)."
    fi

    success "All core prerequisites verified successfully!"
}

create_marker_file() {
    cat > "${MARKER_FILE}" << EOF
# Prerequisites installation marker
# Created: $(date)
# System: $(uname -a)
# Script: ${BASH_SOURCE[0]}
EOF
    info "Marker file created: ${MARKER_FILE}"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo ""
    echo "=========================================="
    echo "  VANET Project - Prerequisites Installer"
    echo "  Target: Debian 13 (Trixie)"
    echo "=========================================="
    echo ""

    # Initialize log
    echo "=== Installation started: $(date) ===" > "${LOG_FILE}"

    # Pre-flight checks
    check_root
    check_debian

    # Check if already installed
    if [[ -f "${MARKER_FILE}" ]]; then
        warn "Prerequisites were previously installed."
        warn "Marker file found: ${MARKER_FILE}"
        read -p "Do you want to reinstall? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping installation. Remove ${MARKER_FILE} to force reinstall."
            verify_installation
            exit 0
        fi
    fi

    # Run installation steps
    update_system
    install_build_essentials
    install_ns3_dependencies
    install_wave_dependencies
    install_sumo
    install_python_scientific
    install_visualization_tools

    # Verify and finalize
    verify_installation
    create_marker_file

    echo ""
    echo "=========================================="
    echo "  Installation Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Run: ./build_ns3.sh"
    echo "  2. Run: ./verify_ns3.sh"
    echo ""
    echo "Log file: ${LOG_FILE}"
    echo ""

    success "Prerequisites installation completed successfully!"
}

# Run main function
main "$@"
