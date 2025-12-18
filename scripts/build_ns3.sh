#!/usr/bin/env bash
#
# build_ns3.sh
# ============
# Idempotent script to download and build NS-3 from source.
# Configures NS-3 with 802.11p/WAVE support for VANET simulations.
#
# Usage: ./build_ns3.sh [--clean] [--version VERSION]
#
# Options:
#   --clean     Remove existing NS-3 installation and rebuild
#   --version   Specify NS-3 version (default: 3.42)
#
# Author: VANET Project Team
# Course: Data Communications and Computer Networks
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
LOG_FILE="${SCRIPT_DIR}/build_ns3.log"

# NS-3 Configuration
NS3_VERSION="${NS3_VERSION:-3.42}"
NS3_DIR="${PROJECT_DIR}/ns-3-allinone"
NS3_SRC_DIR="${NS3_DIR}/ns-3.${NS3_VERSION}"
NS3_URL="https://www.nsnam.org/releases/ns-allinone-${NS3_VERSION}.tar.bz2"

# Build configuration
BUILD_TYPE="optimized"  # debug, optimized, or release
ENABLE_EXAMPLES="ON"
ENABLE_TESTS="ON"
NUM_JOBS=$(nproc)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Download and build NS-3 for VANET simulations.

Options:
    --clean         Remove existing NS-3 and rebuild from scratch
    --version VER   Specify NS-3 version (default: ${NS3_VERSION})
    --debug         Build in debug mode
    --release       Build in release mode
    --jobs N        Number of parallel build jobs (default: ${NUM_JOBS})
    --help          Show this help message

Examples:
    $(basename "$0")                    # Build with defaults
    $(basename "$0") --clean            # Clean rebuild
    $(basename "$0") --version 3.41     # Build specific version
    $(basename "$0") --debug --jobs 4   # Debug build with 4 jobs

EOF
    exit 0
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

CLEAN_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --version)
            NS3_VERSION="$2"
            NS3_SRC_DIR="${NS3_DIR}/ns-3.${NS3_VERSION}"
            NS3_URL="https://www.nsnam.org/releases/ns-allinone-${NS3_VERSION}.tar.bz2"
            shift 2
            ;;
        --debug)
            BUILD_TYPE="debug"
            shift
            ;;
        --release)
            BUILD_TYPE="release"
            shift
            ;;
        --jobs)
            NUM_JOBS="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# ============================================================================
# INSTALLATION FUNCTIONS
# ============================================================================

check_prerequisites() {
    info "Checking prerequisites..."

    local required_commands=(
        "g++"
        "cmake"
        "python3"
        "git"
        "wget"
        "tar"
    )

    local missing=()
    for cmd in "${required_commands[@]}"; do
        if ! command -v "${cmd}" &> /dev/null; then
            missing+=("${cmd}")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Missing required commands: ${missing[*]}. Run install_prerequisites.sh first."
    fi

    success "All prerequisites found."
}

clean_existing() {
    if [[ "${CLEAN_BUILD}" == "true" ]] && [[ -d "${NS3_DIR}" ]]; then
        warn "Removing existing NS-3 installation at ${NS3_DIR}..."
        rm -rf "${NS3_DIR}"
        success "Cleaned existing installation."
    fi
}

download_ns3() {
    local tarball="${NS3_DIR}/ns-allinone-${NS3_VERSION}.tar.bz2"

    # Create directory
    mkdir -p "${NS3_DIR}"

    # Check if already downloaded
    if [[ -d "${NS3_SRC_DIR}" ]] && [[ -f "${NS3_SRC_DIR}/CMakeLists.txt" ]]; then
        info "NS-3 ${NS3_VERSION} source already exists. Skipping download."
        return 0
    fi

    # Download tarball
    if [[ ! -f "${tarball}" ]]; then
        info "Downloading NS-3 ${NS3_VERSION} from ${NS3_URL}..."
        wget -O "${tarball}" "${NS3_URL}" 2>&1 | tee -a "${LOG_FILE}"

        if [[ ! -f "${tarball}" ]]; then
            die "Download failed. Check your internet connection."
        fi
        success "Download complete."
    else
        info "Tarball already exists. Skipping download."
    fi

    # Extract
    info "Extracting NS-3 ${NS3_VERSION}..."
    cd "${NS3_DIR}"
    tar -xjf "${tarball}" 2>&1 | tee -a "${LOG_FILE}"

    # The tarball extracts to ns-allinone-X.XX/ns-3.X.XX
    # We need to adjust paths
    if [[ -d "${NS3_DIR}/ns-allinone-${NS3_VERSION}" ]]; then
        # Move contents up
        mv "${NS3_DIR}/ns-allinone-${NS3_VERSION}"/* "${NS3_DIR}/" 2>/dev/null || true
        rmdir "${NS3_DIR}/ns-allinone-${NS3_VERSION}" 2>/dev/null || true
    fi

    # Update NS3_SRC_DIR to actual path
    if [[ -d "${NS3_DIR}/ns-${NS3_VERSION}" ]]; then
        NS3_SRC_DIR="${NS3_DIR}/ns-${NS3_VERSION}"
    elif [[ -d "${NS3_DIR}/ns-3.${NS3_VERSION}" ]]; then
        NS3_SRC_DIR="${NS3_DIR}/ns-3.${NS3_VERSION}"
    fi

    if [[ ! -d "${NS3_SRC_DIR}" ]]; then
        # Try to find the actual directory
        NS3_SRC_DIR=$(find "${NS3_DIR}" -maxdepth 1 -type d -name "ns-*" | head -1)
        if [[ -z "${NS3_SRC_DIR}" ]]; then
            die "Could not find NS-3 source directory after extraction."
        fi
    fi

    success "Extraction complete. Source at: ${NS3_SRC_DIR}"
}

configure_ns3() {
    info "Configuring NS-3 ${NS3_VERSION}..."

    cd "${NS3_SRC_DIR}"

    # Check for CMake-based build (NS-3.36+)
    if [[ -f "CMakeLists.txt" ]]; then
        info "Using CMake build system..."

        # Create build directory
        local build_dir="${NS3_SRC_DIR}/cmake-cache"
        mkdir -p "${build_dir}"
        cd "${build_dir}"

        # Configure with CMake
        local cmake_args=(
            -DCMAKE_BUILD_TYPE="${BUILD_TYPE^}"  # Capitalize first letter
            -DNS3_EXAMPLES="${ENABLE_EXAMPLES}"
            -DNS3_TESTS="${ENABLE_TESTS}"
            -DNS3_LOG=ON
            -DNS3_ASSERT=ON
            -DNS3_PYTHON_BINDINGS=ON
            -G "Ninja"
        )

        # Enable specific modules needed for VANET
        # Wave module is essential for 802.11p
        cmake_args+=(
            -DNS3_ENABLED_MODULES="core;network;internet;mobility;wifi;wave;propagation;applications;flow-monitor;stats;aodv;olsr;dsdv;point-to-point;csma;bridge;internet-apps;config-store;buildings"
        )

        info "Running CMake with options: ${cmake_args[*]}"

        cmake "${cmake_args[@]}" "${NS3_SRC_DIR}" 2>&1 | tee -a "${LOG_FILE}"

        success "CMake configuration complete."

    elif [[ -f "waf" ]]; then
        # Legacy waf-based build (NS-3.35 and earlier)
        info "Using waf build system (legacy)..."

        local waf_args=(
            --enable-examples
            --enable-tests
            --build-profile="${BUILD_TYPE}"
        )

        ./waf configure "${waf_args[@]}" 2>&1 | tee -a "${LOG_FILE}"

        success "Waf configuration complete."
    else
        die "No build system found (neither CMakeLists.txt nor waf)."
    fi
}

build_ns3() {
    info "Building NS-3 ${NS3_VERSION} with ${NUM_JOBS} parallel jobs..."

    cd "${NS3_SRC_DIR}"

    local start_time
    start_time=$(date +%s)

    if [[ -f "CMakeLists.txt" ]]; then
        # CMake build
        cd "${NS3_SRC_DIR}/cmake-cache"
        ninja -j "${NUM_JOBS}" 2>&1 | tee -a "${LOG_FILE}"
    else
        # Waf build
        ./waf build -j "${NUM_JOBS}" 2>&1 | tee -a "${LOG_FILE}"
    fi

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    success "Build completed in ${duration} seconds."
}

create_ns3_env_script() {
    info "Creating NS-3 environment script..."

    local env_script="${SCRIPT_DIR}/ns3_env.sh"

    cat > "${env_script}" << EOF
#!/usr/bin/env bash
#
# NS-3 Environment Setup Script
# Source this file to set up NS-3 environment variables.
#
# Usage: source ns3_env.sh
#

export NS3_HOME="${NS3_SRC_DIR}"
export NS3_VERSION="${NS3_VERSION}"

# Add NS-3 to PATH
if [[ -d "\${NS3_HOME}/build/bin" ]]; then
    export PATH="\${NS3_HOME}/build/bin:\${PATH}"
elif [[ -d "\${NS3_HOME}/cmake-cache" ]]; then
    export PATH="\${NS3_HOME}/cmake-cache:\${PATH}"
fi

# Python bindings
if [[ -d "\${NS3_HOME}/build/bindings/python" ]]; then
    export PYTHONPATH="\${NS3_HOME}/build/bindings/python:\${PYTHONPATH:-}"
fi

# Library path
if [[ -d "\${NS3_HOME}/build/lib" ]]; then
    export LD_LIBRARY_PATH="\${NS3_HOME}/build/lib:\${LD_LIBRARY_PATH:-}"
elif [[ -d "\${NS3_HOME}/cmake-cache/lib" ]]; then
    export LD_LIBRARY_PATH="\${NS3_HOME}/cmake-cache/lib:\${LD_LIBRARY_PATH:-}"
fi

echo "NS-3 environment configured."
echo "  NS3_HOME: \${NS3_HOME}"
echo "  NS3_VERSION: \${NS3_VERSION}"

# Helper function to run NS-3 programs
ns3_run() {
    if [[ -f "\${NS3_HOME}/ns3" ]]; then
        cd "\${NS3_HOME}" && ./ns3 run "\$@"
    elif [[ -f "\${NS3_HOME}/waf" ]]; then
        cd "\${NS3_HOME}" && ./waf --run "\$@"
    else
        echo "Error: No NS-3 runner found."
        return 1
    fi
}

export -f ns3_run
EOF

    chmod +x "${env_script}"
    success "Environment script created: ${env_script}"
}

verify_build() {
    info "Verifying NS-3 build..."

    cd "${NS3_SRC_DIR}"

    # Check for key modules
    local required_modules=(
        "core"
        "network"
        "internet"
        "mobility"
        "wifi"
        "wave"
        "propagation"
        "aodv"
        "olsr"
        "flow-monitor"
    )

    info "Checking for required modules..."

    # Find built libraries
    local lib_dir=""
    if [[ -d "${NS3_SRC_DIR}/cmake-cache/lib" ]]; then
        lib_dir="${NS3_SRC_DIR}/cmake-cache/lib"
    elif [[ -d "${NS3_SRC_DIR}/build/lib" ]]; then
        lib_dir="${NS3_SRC_DIR}/build/lib"
    fi

    if [[ -z "${lib_dir}" ]] || [[ ! -d "${lib_dir}" ]]; then
        die "Cannot find NS-3 library directory."
    fi

    local missing=()
    for module in "${required_modules[@]}"; do
        # Look for the module library
        if ls "${lib_dir}"/libns3*-"${module}"* &>/dev/null; then
            success "Module '${module}' found."
        else
            missing+=("${module}")
            warn "Module '${module}' not found!"
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Missing modules: ${missing[*]}"
        warn "Some VANET functionality may not be available."
    fi

    # Run a simple test
    info "Running a simple hello-world test..."

    # Try to run the hello-simulator example
    local hello_result=0
    if [[ -f "${NS3_SRC_DIR}/ns3" ]]; then
        cd "${NS3_SRC_DIR}"
        ./ns3 run hello-simulator 2>&1 | tee -a "${LOG_FILE}" || hello_result=$?
    elif [[ -f "${NS3_SRC_DIR}/waf" ]]; then
        cd "${NS3_SRC_DIR}"
        ./waf --run hello-simulator 2>&1 | tee -a "${LOG_FILE}" || hello_result=$?
    fi

    if [[ ${hello_result} -eq 0 ]]; then
        success "Hello-simulator test passed!"
    else
        warn "Hello-simulator test returned non-zero. Check output above."
    fi

    success "NS-3 build verification complete."
}

create_project_symlink() {
    info "Creating convenient symlink..."

    local link_path="${PROJECT_DIR}/ns3"

    if [[ -L "${link_path}" ]]; then
        rm "${link_path}"
    fi

    ln -sf "${NS3_SRC_DIR}" "${link_path}"

    success "Symlink created: ${link_path} -> ${NS3_SRC_DIR}"
}

print_summary() {
    echo ""
    echo "=========================================="
    echo "  NS-3 Build Summary"
    echo "=========================================="
    echo ""
    echo "Version:     ${NS3_VERSION}"
    echo "Location:    ${NS3_SRC_DIR}"
    echo "Build type:  ${BUILD_TYPE}"
    echo ""
    echo "To use NS-3:"
    echo "  1. Source the environment: source ${SCRIPT_DIR}/ns3_env.sh"
    echo "  2. Run simulations: ns3_run <program-name>"
    echo ""
    echo "Next steps:"
    echo "  - Run ./verify_ns3.sh to test 802.11p/WAVE functionality"
    echo ""
    echo "Log file: ${LOG_FILE}"
    echo ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo ""
    echo "=========================================="
    echo "  NS-3 Build Script"
    echo "  Version: ${NS3_VERSION}"
    echo "=========================================="
    echo ""

    # Initialize log
    echo "=== Build started: $(date) ===" > "${LOG_FILE}"
    echo "NS-3 Version: ${NS3_VERSION}" >> "${LOG_FILE}"
    echo "Build type: ${BUILD_TYPE}" >> "${LOG_FILE}"
    echo "Jobs: ${NUM_JOBS}" >> "${LOG_FILE}"

    # Run build steps
    check_prerequisites
    clean_existing
    download_ns3
    configure_ns3
    build_ns3
    create_ns3_env_script
    verify_build
    create_project_symlink
    print_summary

    success "NS-3 ${NS3_VERSION} build completed successfully!"
}

# Run main
main "$@"
