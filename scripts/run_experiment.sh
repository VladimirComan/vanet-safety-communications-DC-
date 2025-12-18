#!/usr/bin/env bash
#
# run_experiment.sh
# =================
#
# Script to run a single VANET experiment with specified parameters.
# This script handles NS-3 execution, parameter passing, and output organization.
#
# Usage:
#   ./run_experiment.sh [OPTIONS]
#
# Options:
#   --vehicles N          Number of vehicles (default: 60)
#   --speed S             Speed in km/h (default: 50)
#   --routing PROTOCOL    Routing protocol: AODV or OLSR (default: AODV)
#   --seed N              Random seed (default: 1)
#   --simtime T           Simulation time in seconds (default: 300)
#   --output DIR          Output directory (default: ./results)
#   --name NAME           Experiment name prefix
#   --help                Show this help
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
NS3_DIR="${PROJECT_DIR}/ns3"

# Default parameters
NUM_VEHICLES=60
SPEED_KMH=50
ROUTING_PROTOCOL="AODV"
RANDOM_SEED=1
SIM_TIME=300
OUTPUT_DIR="${PROJECT_DIR}/results"
EXPERIMENT_NAME=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

die() {
    error "$*"
    exit 1
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run a VANET simulation experiment with specified parameters.

Options:
    --vehicles N          Number of vehicles (default: ${NUM_VEHICLES})
    --speed S             Vehicle speed in km/h (default: ${SPEED_KMH})
    --routing PROTOCOL    Routing protocol: AODV or OLSR (default: ${ROUTING_PROTOCOL})
    --seed N              Random seed for reproducibility (default: ${RANDOM_SEED})
    --simtime T           Simulation time in seconds (default: ${SIM_TIME})
    --output DIR          Output directory (default: ${OUTPUT_DIR})
    --name NAME           Experiment name prefix (auto-generated if not specified)
    --help                Show this help message

Examples:
    $(basename "$0") --vehicles 30 --routing AODV --seed 1
    $(basename "$0") --vehicles 120 --speed 60 --routing OLSR --seed 5

EOF
    exit 0
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --vehicles)
            NUM_VEHICLES="$2"
            shift 2
            ;;
        --speed)
            SPEED_KMH="$2"
            shift 2
            ;;
        --routing)
            ROUTING_PROTOCOL="$2"
            shift 2
            ;;
        --seed)
            RANDOM_SEED="$2"
            shift 2
            ;;
        --simtime)
            SIM_TIME="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --name)
            EXPERIMENT_NAME="$2"
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
# SETUP
# ============================================================================

# Source NS-3 environment
if [[ -f "${SCRIPT_DIR}/ns3_env.sh" ]]; then
    source "${SCRIPT_DIR}/ns3_env.sh"
fi

# Find NS-3 installation
if [[ -z "${NS3_HOME:-}" ]]; then
    if [[ -L "${PROJECT_DIR}/ns3" ]]; then
        NS3_HOME=$(readlink -f "${PROJECT_DIR}/ns3")
    elif [[ -d "${PROJECT_DIR}/ns-3-allinone" ]]; then
        NS3_HOME=$(find "${PROJECT_DIR}/ns-3-allinone" -maxdepth 1 -type d -name "ns-*" | head -1)
    fi
fi

if [[ -z "${NS3_HOME:-}" ]] || [[ ! -d "${NS3_HOME}" ]]; then
    die "NS-3 installation not found. Run build_ns3.sh first."
fi

# Validate routing protocol
case "${ROUTING_PROTOCOL}" in
    AODV|aodv)
        ROUTING_PROTOCOL="AODV"
        ;;
    OLSR|olsr)
        ROUTING_PROTOCOL="OLSR"
        ;;
    *)
        die "Invalid routing protocol: ${ROUTING_PROTOCOL}. Use AODV or OLSR."
        ;;
esac

# Generate experiment name if not provided
if [[ -z "${EXPERIMENT_NAME}" ]]; then
    EXPERIMENT_NAME="vanet_v${NUM_VEHICLES}_s${SPEED_KMH}_${ROUTING_PROTOCOL}_seed${RANDOM_SEED}"
fi

# Convert speed to m/s
SPEED_MS=$(echo "scale=2; ${SPEED_KMH} / 3.6" | bc)

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# ============================================================================
# COPY SIMULATION TO NS-3 SCRATCH
# ============================================================================

info "Preparing simulation..."

# Copy simulation file to NS-3 scratch directory
NS3_SCRATCH="${NS3_HOME}/scratch"
mkdir -p "${NS3_SCRATCH}"

if [[ -f "${PROJECT_DIR}/ns3/vanet-simulation.cc" ]]; then
    cp "${PROJECT_DIR}/ns3/vanet-simulation.cc" "${NS3_SCRATCH}/"
    info "Copied vanet-simulation.cc to NS-3 scratch"
else
    die "vanet-simulation.cc not found in ${PROJECT_DIR}/ns3/"
fi

# ============================================================================
# BUILD SIMULATION
# ============================================================================

info "Building simulation..."

cd "${NS3_HOME}"

# Build with NS-3
if [[ -f "${NS3_HOME}/ns3" ]]; then
    ./ns3 build scratch/vanet-simulation 2>&1 | tail -20
elif [[ -f "${NS3_HOME}/waf" ]]; then
    ./waf build 2>&1 | tail -20
else
    die "No NS-3 build system found"
fi

# Check if build succeeded
if [[ -f "${NS3_HOME}/ns3" ]]; then
    if ! ./ns3 show targets 2>/dev/null | grep -q "scratch_vanet-simulation"; then
        warn "Build may have failed. Attempting to run anyway..."
    fi
fi

# ============================================================================
# RUN SIMULATION
# ============================================================================

info "Running experiment: ${EXPERIMENT_NAME}"
info "  Vehicles: ${NUM_VEHICLES}"
info "  Speed: ${SPEED_KMH} km/h (${SPEED_MS} m/s)"
info "  Routing: ${ROUTING_PROTOCOL}"
info "  Seed: ${RANDOM_SEED}"
info "  Simulation time: ${SIM_TIME} s"
info "  Output: ${OUTPUT_DIR}/${EXPERIMENT_NAME}"

# Prepare arguments
NS3_ARGS=(
    "--numVehicles=${NUM_VEHICLES}"
    "--vehicleSpeed=${SPEED_MS}"
    "--routingProtocol=${ROUTING_PROTOCOL}"
    "--randomSeed=${RANDOM_SEED}"
    "--simTime=${SIM_TIME}"
    "--outputDir=${OUTPUT_DIR}"
    "--experimentName=${EXPERIMENT_NAME}"
    "--enablePcap=true"
    "--enableFlowMonitor=true"
)

# Run the simulation
START_TIME=$(date +%s)

if [[ -f "${NS3_HOME}/ns3" ]]; then
    ./ns3 run "scratch/vanet-simulation ${NS3_ARGS[*]}" 2>&1 | tee "${OUTPUT_DIR}/${EXPERIMENT_NAME}_console.log"
    RUN_STATUS=${PIPESTATUS[0]}
elif [[ -f "${NS3_HOME}/waf" ]]; then
    ./waf --run "scratch/vanet-simulation ${NS3_ARGS[*]}" 2>&1 | tee "${OUTPUT_DIR}/${EXPERIMENT_NAME}_console.log"
    RUN_STATUS=${PIPESTATUS[0]}
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ============================================================================
# POST-PROCESSING
# ============================================================================

if [[ ${RUN_STATUS:-1} -eq 0 ]]; then
    success "Experiment completed in ${DURATION} seconds"

    # Move any PCAP files generated in NS-3 directory to results
    cd "${NS3_HOME}"
    if ls "${EXPERIMENT_NAME}"*.pcap &>/dev/null 2>&1; then
        mv "${EXPERIMENT_NAME}"*.pcap "${OUTPUT_DIR}/"
        info "Moved PCAP files to ${OUTPUT_DIR}/"
    fi

    # Create experiment metadata file
    cat > "${OUTPUT_DIR}/${EXPERIMENT_NAME}_metadata.json" << EOF
{
    "experiment_name": "${EXPERIMENT_NAME}",
    "timestamp": "$(date -Iseconds)",
    "duration_seconds": ${DURATION},
    "parameters": {
        "num_vehicles": ${NUM_VEHICLES},
        "speed_kmh": ${SPEED_KMH},
        "speed_ms": ${SPEED_MS},
        "routing_protocol": "${ROUTING_PROTOCOL}",
        "random_seed": ${RANDOM_SEED},
        "sim_time": ${SIM_TIME}
    },
    "output_files": {
        "statistics": "${EXPERIMENT_NAME}_statistics.txt",
        "summary_csv": "${EXPERIMENT_NAME}_summary.csv",
        "packets_csv": "${EXPERIMENT_NAME}_packets.csv",
        "mobility_csv": "${EXPERIMENT_NAME}_mobility.csv",
        "flowmonitor_xml": "${EXPERIMENT_NAME}_flowmonitor.xml"
    }
}
EOF

    info "Results saved to: ${OUTPUT_DIR}/"
    info "  - Statistics: ${EXPERIMENT_NAME}_statistics.txt"
    info "  - Summary CSV: ${EXPERIMENT_NAME}_summary.csv"
    info "  - Packet log: ${EXPERIMENT_NAME}_packets.csv"
    info "  - Mobility log: ${EXPERIMENT_NAME}_mobility.csv"

else
    error "Experiment failed with status ${RUN_STATUS}"
    error "Check ${OUTPUT_DIR}/${EXPERIMENT_NAME}_console.log for details"
    exit 1
fi

success "Experiment ${EXPERIMENT_NAME} completed successfully!"
