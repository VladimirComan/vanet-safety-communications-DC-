#!/usr/bin/env bash
#
# run_experiment_matrix.sh
# ========================
#
# Automation script to run the complete VANET experimental matrix.
# Executes all combinations of parameters as specified in the project requirements.
#
# Experimental Matrix:
# - Vehicle density: 30, 60, 120
# - Speed: 30 km/h, 60 km/h
# - Routing protocols: AODV, OLSR
# - Random seeds: 1-5 (for statistical reliability)
#
# Usage:
#   ./run_experiment_matrix.sh [OPTIONS]
#
# Options:
#   --quick         Run quick test (subset of matrix)
#   --parallel N    Run N experiments in parallel (default: 1)
#   --output DIR    Output directory
#   --resume        Resume from last incomplete experiment
#   --help          Show this help
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

# Default output directory
OUTPUT_DIR="${PROJECT_DIR}/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MATRIX_OUTPUT_DIR="${OUTPUT_DIR}/matrix_${TIMESTAMP}"

# Experimental matrix parameters
VEHICLE_COUNTS=(30 60 120)
SPEEDS_KMH=(30 60)
ROUTING_PROTOCOLS=("AODV" "OLSR")
RANDOM_SEEDS=(1 2 3 4 5)
SIM_TIME=300

# Execution options
PARALLEL_JOBS=1
QUICK_MODE=false
RESUME_MODE=false
PROGRESS_FILE=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

progress() {
    echo -e "${CYAN}[PROGRESS]${NC} $*"
}

die() {
    error "$*"
    exit 1
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run the complete VANET experimental matrix.

Matrix Parameters:
    Vehicle counts:     ${VEHICLE_COUNTS[*]}
    Speeds (km/h):      ${SPEEDS_KMH[*]}
    Routing protocols:  ${ROUTING_PROTOCOLS[*]}
    Random seeds:       ${RANDOM_SEEDS[*]}
    Simulation time:    ${SIM_TIME} seconds

Options:
    --quick             Run quick test (reduced matrix)
    --parallel N        Run N experiments in parallel (default: ${PARALLEL_JOBS})
    --output DIR        Output directory (default: auto-timestamped)
    --simtime T         Simulation time in seconds (default: ${SIM_TIME})
    --resume            Resume from last incomplete run
    --dry-run           Show experiments without running
    --help              Show this help message

Examples:
    $(basename "$0")                    # Run full matrix
    $(basename "$0") --quick            # Quick test mode
    $(basename "$0") --parallel 4       # Run 4 experiments in parallel

Total experiments in full matrix: $((${#VEHICLE_COUNTS[@]} * ${#SPEEDS_KMH[@]} * ${#ROUTING_PROTOCOLS[@]} * ${#RANDOM_SEEDS[@]}))

EOF
    exit 0
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --parallel)
            PARALLEL_JOBS="$2"
            shift 2
            ;;
        --output)
            MATRIX_OUTPUT_DIR="$2"
            shift 2
            ;;
        --simtime)
            SIM_TIME="$2"
            shift 2
            ;;
        --resume)
            RESUME_MODE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# Quick mode: reduced matrix
if [[ "${QUICK_MODE}" == "true" ]]; then
    VEHICLE_COUNTS=(30 60)
    SPEEDS_KMH=(50)
    RANDOM_SEEDS=(1 2)
    SIM_TIME=60
    info "Quick mode enabled: reduced matrix and simulation time"
fi

# ============================================================================
# SETUP
# ============================================================================

# Create output directory
mkdir -p "${MATRIX_OUTPUT_DIR}"
PROGRESS_FILE="${MATRIX_OUTPUT_DIR}/progress.log"

# Calculate total experiments
TOTAL_EXPERIMENTS=$((${#VEHICLE_COUNTS[@]} * ${#SPEEDS_KMH[@]} * ${#ROUTING_PROTOCOLS[@]} * ${#RANDOM_SEEDS[@]}))

info "Experimental Matrix Configuration:"
info "  Vehicle counts: ${VEHICLE_COUNTS[*]}"
info "  Speeds (km/h): ${SPEEDS_KMH[*]}"
info "  Routing protocols: ${ROUTING_PROTOCOLS[*]}"
info "  Random seeds: ${RANDOM_SEEDS[*]}"
info "  Simulation time: ${SIM_TIME} s"
info "  Total experiments: ${TOTAL_EXPERIMENTS}"
info "  Parallel jobs: ${PARALLEL_JOBS}"
info "  Output directory: ${MATRIX_OUTPUT_DIR}"

if [[ "${DRY_RUN}" == "true" ]]; then
    info "DRY RUN MODE - experiments will not be executed"
fi

# ============================================================================
# EXPERIMENT EXECUTION
# ============================================================================

# Generate experiment list
declare -a EXPERIMENTS

exp_index=0
for vehicles in "${VEHICLE_COUNTS[@]}"; do
    for speed in "${SPEEDS_KMH[@]}"; do
        for routing in "${ROUTING_PROTOCOLS[@]}"; do
            for seed in "${RANDOM_SEEDS[@]}"; do
                exp_name="v${vehicles}_s${speed}_${routing}_seed${seed}"
                EXPERIMENTS+=("${vehicles}:${speed}:${routing}:${seed}:${exp_name}")
                ((exp_index++)) || true
            done
        done
    done
done

# Check for completed experiments (resume mode)
declare -A COMPLETED_EXPERIMENTS

if [[ "${RESUME_MODE}" == "true" ]] && [[ -f "${PROGRESS_FILE}" ]]; then
    while IFS= read -r line; do
        if [[ "${line}" =~ ^COMPLETED: ]]; then
            exp_name="${line#COMPLETED: }"
            COMPLETED_EXPERIMENTS["${exp_name}"]=1
        fi
    done < "${PROGRESS_FILE}"
    info "Resuming: ${#COMPLETED_EXPERIMENTS[@]} experiments already completed"
fi

# Function to run a single experiment
run_single_experiment() {
    local exp_spec="$1"
    local exp_num="$2"
    local total="$3"

    IFS=':' read -r vehicles speed routing seed exp_name <<< "${exp_spec}"

    # Check if already completed
    if [[ -n "${COMPLETED_EXPERIMENTS[${exp_name}]:-}" ]]; then
        progress "[${exp_num}/${total}] Skipping ${exp_name} (already completed)"
        return 0
    fi

    progress "[${exp_num}/${total}] Running ${exp_name}..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "  Would run: --vehicles ${vehicles} --speed ${speed} --routing ${routing} --seed ${seed}"
        return 0
    fi

    # Create experiment-specific output directory
    local exp_output="${MATRIX_OUTPUT_DIR}/${exp_name}"
    mkdir -p "${exp_output}"

    # Run the experiment
    local start_time=$(date +%s)

    "${SCRIPT_DIR}/run_experiment.sh" \
        --vehicles "${vehicles}" \
        --speed "${speed}" \
        --routing "${routing}" \
        --seed "${seed}" \
        --simtime "${SIM_TIME}" \
        --output "${exp_output}" \
        --name "${exp_name}" \
        > "${exp_output}/run.log" 2>&1

    local status=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [[ ${status} -eq 0 ]]; then
        echo "COMPLETED: ${exp_name}" >> "${PROGRESS_FILE}"
        success "[${exp_num}/${total}] ${exp_name} completed in ${duration}s"
        return 0
    else
        echo "FAILED: ${exp_name}" >> "${PROGRESS_FILE}"
        error "[${exp_num}/${total}] ${exp_name} failed after ${duration}s"
        return 1
    fi
}

# Export function for parallel execution
export -f run_single_experiment
export SCRIPT_DIR MATRIX_OUTPUT_DIR PROGRESS_FILE DRY_RUN

# ============================================================================
# MAIN EXECUTION LOOP
# ============================================================================

echo ""
echo "=========================================="
echo "  VANET Experimental Matrix"
echo "  Total experiments: ${TOTAL_EXPERIMENTS}"
echo "=========================================="
echo ""

# Initialize progress file
if [[ "${DRY_RUN}" != "true" ]]; then
    echo "# Experiment progress log" >> "${PROGRESS_FILE}"
    echo "# Started: $(date)" >> "${PROGRESS_FILE}"
fi

FAILED_EXPERIMENTS=()
COMPLETED_COUNT=0
START_TIME=$(date +%s)

if [[ ${PARALLEL_JOBS} -gt 1 ]] && command -v parallel &>/dev/null; then
    # Use GNU parallel for concurrent execution
    info "Running ${PARALLEL_JOBS} experiments in parallel..."

    exp_num=0
    for exp in "${EXPERIMENTS[@]}"; do
        ((exp_num++)) || true
        echo "${exp}:${exp_num}:${TOTAL_EXPERIMENTS}"
    done | parallel -j "${PARALLEL_JOBS}" --colsep ':' \
        run_single_experiment '{1}:{2}:{3}:{4}:{5}' '{6}' '{7}'

else
    # Sequential execution
    exp_num=0
    for exp in "${EXPERIMENTS[@]}"; do
        ((exp_num++)) || true

        IFS=':' read -r vehicles speed routing seed exp_name <<< "${exp}"

        # Check if already completed
        if [[ -n "${COMPLETED_EXPERIMENTS[${exp_name}]:-}" ]]; then
            progress "[${exp_num}/${TOTAL_EXPERIMENTS}] Skipping ${exp_name} (already completed)"
            ((COMPLETED_COUNT++)) || true
            continue
        fi

        progress "[${exp_num}/${TOTAL_EXPERIMENTS}] Running ${exp_name}..."

        if [[ "${DRY_RUN}" == "true" ]]; then
            echo "  Would run: --vehicles ${vehicles} --speed ${speed} --routing ${routing} --seed ${seed}"
            continue
        fi

        # Create experiment-specific output directory
        exp_output="${MATRIX_OUTPUT_DIR}/${exp_name}"
        mkdir -p "${exp_output}"

        # Run the experiment
        exp_start=$(date +%s)

        if "${SCRIPT_DIR}/run_experiment.sh" \
            --vehicles "${vehicles}" \
            --speed "${speed}" \
            --routing "${routing}" \
            --seed "${seed}" \
            --simtime "${SIM_TIME}" \
            --output "${exp_output}" \
            --name "${exp_name}" \
            > "${exp_output}/run.log" 2>&1; then

            exp_end=$(date +%s)
            exp_duration=$((exp_end - exp_start))
            echo "COMPLETED: ${exp_name}" >> "${PROGRESS_FILE}"
            success "[${exp_num}/${TOTAL_EXPERIMENTS}] ${exp_name} completed in ${exp_duration}s"
            ((COMPLETED_COUNT++)) || true
        else
            exp_end=$(date +%s)
            exp_duration=$((exp_end - exp_start))
            echo "FAILED: ${exp_name}" >> "${PROGRESS_FILE}"
            error "[${exp_num}/${TOTAL_EXPERIMENTS}] ${exp_name} failed after ${exp_duration}s"
            FAILED_EXPERIMENTS+=("${exp_name}")
        fi

        # Show ETA
        if [[ ${exp_num} -gt 0 ]] && [[ ${exp_num} -lt ${TOTAL_EXPERIMENTS} ]]; then
            elapsed=$(($(date +%s) - START_TIME))
            avg_time=$((elapsed / exp_num))
            remaining=$((TOTAL_EXPERIMENTS - exp_num))
            eta=$((remaining * avg_time))
            info "Estimated time remaining: $((eta / 60)) minutes"
        fi
    done
fi

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "=========================================="
echo "  Experimental Matrix Summary"
echo "=========================================="
echo ""

if [[ "${DRY_RUN}" == "true" ]]; then
    info "Dry run completed. No experiments were executed."
    exit 0
fi

echo "Total duration: $((TOTAL_DURATION / 60)) minutes $((TOTAL_DURATION % 60)) seconds"
echo "Experiments completed: ${COMPLETED_COUNT}/${TOTAL_EXPERIMENTS}"

if [[ ${#FAILED_EXPERIMENTS[@]} -gt 0 ]]; then
    echo ""
    error "Failed experiments (${#FAILED_EXPERIMENTS[@]}):"
    for exp in "${FAILED_EXPERIMENTS[@]}"; do
        echo "  - ${exp}"
    done
fi

# Create summary CSV with all results
info "Generating combined results summary..."

SUMMARY_FILE="${MATRIX_OUTPUT_DIR}/combined_results.csv"

# Header
echo "experiment,vehicles,speed_kmh,routing,seed,beacons_sent,beacons_received,pdr,delay_mean_ms,delay_p95_ms,delay_p99_ms,throughput_kbps" > "${SUMMARY_FILE}"

# Collect results from each experiment
for exp in "${EXPERIMENTS[@]}"; do
    IFS=':' read -r vehicles speed routing seed exp_name <<< "${exp}"

    summary_csv="${MATRIX_OUTPUT_DIR}/${exp_name}/${exp_name}_summary.csv"

    if [[ -f "${summary_csv}" ]]; then
        # Extract values from summary CSV
        beacons_sent=$(grep "beaconsSent" "${summary_csv}" | cut -d',' -f2 || echo "0")
        beacons_received=$(grep "beaconsReceived" "${summary_csv}" | cut -d',' -f2 || echo "0")
        pdr=$(grep "^pdr," "${summary_csv}" | cut -d',' -f2 || echo "0")
        delay_mean=$(grep "delayMean" "${summary_csv}" | cut -d',' -f2 || echo "0")
        delay_p95=$(grep "delayP95" "${summary_csv}" | cut -d',' -f2 || echo "0")
        delay_p99=$(grep "delayP99" "${summary_csv}" | cut -d',' -f2 || echo "0")
        throughput=$(grep "throughputKbps" "${summary_csv}" | cut -d',' -f2 || echo "0")

        echo "${exp_name},${vehicles},${speed},${routing},${seed},${beacons_sent},${beacons_received},${pdr},${delay_mean},${delay_p95},${delay_p99},${throughput}" >> "${SUMMARY_FILE}"
    fi
done

info "Combined results saved to: ${SUMMARY_FILE}"

# Generate quick stats
if [[ -f "${SUMMARY_FILE}" ]]; then
    echo ""
    info "Quick Statistics:"

    # Count by routing protocol
    for routing in "${ROUTING_PROTOCOLS[@]}"; do
        count=$(grep ",${routing}," "${SUMMARY_FILE}" | wc -l)
        avg_pdr=$(grep ",${routing}," "${SUMMARY_FILE}" | cut -d',' -f8 | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
        avg_delay=$(grep ",${routing}," "${SUMMARY_FILE}" | cut -d',' -f9 | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
        echo "  ${routing}: ${count} experiments, avg PDR=${avg_pdr}%, avg delay=${avg_delay}ms"
    done
fi

echo ""
echo "Output directory: ${MATRIX_OUTPUT_DIR}"
echo ""

if [[ ${#FAILED_EXPERIMENTS[@]} -eq 0 ]]; then
    success "All experiments completed successfully!"
    exit 0
else
    warn "Some experiments failed. Use --resume to retry."
    exit 1
fi
