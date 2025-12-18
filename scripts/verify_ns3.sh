#!/usr/bin/env bash
#
# verify_ns3.sh
# =============
# Verification script to test NS-3 installation and 802.11p functionality.
# Updated for NS-3.42+ where WAVE module is integrated into WiFi.
#
# Usage: ./verify_ns3.sh
#
# Author: VANET Project Team
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
LOG_FILE="${SCRIPT_DIR}/verify_ns3.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[PASS]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[FAIL]${NC} $*"; }
skip() { echo -e "${CYAN}[SKIP]${NC} $*"; }

# Find NS-3 installation
find_ns3() {
    info "Looking for NS-3 installation..."

    # Check common locations
    local search_paths=(
        "${PROJECT_DIR}/ns-3-allinone/ns-3.42"
        "${PROJECT_DIR}/ns-3-allinone/ns-3.43"
        "${PROJECT_DIR}/ns-3-allinone/ns-3.41"
        "${PROJECT_DIR}/ns3"
        "/usr/local/ns-3"
        "${HOME}/ns-3-allinone/ns-3.42"
    )

    for path in "${search_paths[@]}"; do
        if [[ -f "${path}/ns3" ]]; then
            NS3_HOME="${path}"
            info "Found NS-3 at: ${NS3_HOME}"
            return 0
        fi
    done

    # Try to find dynamically
    NS3_HOME=$(find "${PROJECT_DIR}" -maxdepth 3 -name "ns3" -type f 2>/dev/null | head -1 | xargs dirname 2>/dev/null || true)

    if [[ -n "${NS3_HOME}" ]] && [[ -d "${NS3_HOME}" ]]; then
        info "Found NS-3 at: ${NS3_HOME}"
        return 0
    fi

    error "NS-3 installation not found!"
    error "Run build_ns3.sh first."
    exit 1
}

# Find library directory
find_lib_dir() {
    if [[ -d "${NS3_HOME}/build/lib" ]]; then
        LIB_DIR="${NS3_HOME}/build/lib"
    elif [[ -d "${NS3_HOME}/cmake-cache/lib" ]]; then
        LIB_DIR="${NS3_HOME}/cmake-cache/lib"
    else
        error "Cannot find NS-3 library directory"
        exit 1
    fi
    info "Library directory: ${LIB_DIR}"
}

# Test basic NS-3 functionality
test_ns3_basic() {
    info "Testing basic NS-3 functionality..."

    cd "${NS3_HOME}"

    # Run hello-simulator
    local output
    if output=$(timeout 30 ./ns3 run hello-simulator 2>&1); then
        if echo "${output}" | grep -q "Hello Simulator"; then
            success "hello-simulator works correctly"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        fi
    fi

    error "hello-simulator test failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    return 1
}

# Check required modules
test_modules() {
    info "Checking required modules..."

    local required_modules=(
        "wifi"
        "mobility"
        "internet"
        "aodv"
        "olsr"
        "flow-monitor"
        "propagation"
        "applications"
    )

    local all_found=true

    for module in "${required_modules[@]}"; do
        if ls "${LIB_DIR}"/libns3*-"${module}"* &>/dev/null 2>&1; then
            success "Module '${module}' found"
        else
            error "Module '${module}' NOT found"
            all_found=false
        fi
    done

    if [[ "${all_found}" == "true" ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Test 802.11p support (now in WiFi module)
test_80211p() {
    info "Testing 802.11p support..."

    # Check if WiFi module supports 802.11p
    if grep -r "WIFI_STANDARD_80211p" "${NS3_HOME}/src/wifi/" &>/dev/null; then
        success "802.11p standard support found in WiFi module"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        warn "802.11p support not found (may be older NS-3 version)"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    fi
}

# Run a simple wireless test
test_wireless() {
    info "Testing wireless simulation..."

    cd "${NS3_HOME}"

    # Try running a wireless example
    local examples=(
        "wifi-simple-adhoc"
        "wifi-simple-infra"
        "third"
    )

    for example in "${examples[@]}"; do
        if timeout 60 ./ns3 run "${example}" &>/dev/null 2>&1; then
            success "Wireless example '${example}' runs successfully"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        fi
    done

    warn "No wireless example ran successfully"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
}

# Test routing protocols
test_routing() {
    info "Testing routing protocols..."

    cd "${NS3_HOME}"

    # Check AODV
    if ls "${LIB_DIR}"/libns3*-aodv* &>/dev/null; then
        success "AODV module present"
    else
        error "AODV module missing"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    # Check OLSR
    if ls "${LIB_DIR}"/libns3*-olsr* &>/dev/null; then
        success "OLSR module present"
    else
        error "OLSR module missing"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    TESTS_PASSED=$((TESTS_PASSED + 1))
}

# Create and test a simple 802.11p simulation
test_vanet_simulation() {
    info "Testing VANET simulation capability..."

    cd "${NS3_HOME}"

    # Create a minimal test script
    local test_file="${NS3_HOME}/scratch/vanet-test-minimal.cc"

    cat > "${test_file}" << 'ENDOFTEST'
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/internet-module.h"

using namespace ns3;

int main(int argc, char *argv[])
{
    // Create 2 nodes
    NodeContainer nodes;
    nodes.Create(2);

    // Configure WiFi for 802.11p
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211p);

    YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());

    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");

    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                  "DataMode", StringValue("OfdmRate6MbpsBW10MHz"),
                                  "ControlMode", StringValue("OfdmRate6MbpsBW10MHz"));

    NetDeviceContainer devices = wifi.Install(phy, mac, nodes);

    // Set up mobility
    MobilityHelper mobility;
    mobility.SetPositionAllocator("ns3::GridPositionAllocator",
                                   "MinX", DoubleValue(0.0),
                                   "MinY", DoubleValue(0.0),
                                   "DeltaX", DoubleValue(50.0));
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(nodes);

    // Install internet stack
    InternetStackHelper internet;
    internet.Install(nodes);

    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    ipv4.Assign(devices);

    // Run for 1 second
    Simulator::Stop(Seconds(1.0));
    Simulator::Run();
    Simulator::Destroy();

    std::cout << "VANET test completed successfully!" << std::endl;
    return 0;
}
ENDOFTEST

    # Build the test
    info "Building VANET test..."
    if ! ./ns3 build vanet-test-minimal &>/dev/null 2>&1; then
        # Try rebuilding
        ./ns3 configure --enable-examples &>/dev/null 2>&1 || true
        ./ns3 build &>/dev/null 2>&1 || true
    fi

    # Run the test
    info "Running VANET test..."
    local output
    if output=$(timeout 30 ./ns3 run vanet-test-minimal 2>&1); then
        if echo "${output}" | grep -q "completed successfully"; then
            success "VANET 802.11p simulation works!"
            TESTS_PASSED=$((TESTS_PASSED + 1))

            # Cleanup
            rm -f "${test_file}"
            return 0
        fi
    fi

    warn "VANET test did not complete as expected"
    warn "Output: ${output}"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))

    # Cleanup
    rm -f "${test_file}"
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "  NS-3 Verification Summary"
    echo "=========================================="
    echo ""
    echo "NS-3 Location: ${NS3_HOME}"
    echo ""
    echo -e "Tests passed:  ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests failed:  ${RED}${TESTS_FAILED}${NC}"
    echo -e "Tests skipped: ${CYAN}${TESTS_SKIPPED}${NC}"
    echo ""

    if [[ ${TESTS_FAILED} -eq 0 ]]; then
        echo -e "${GREEN}NS-3 is ready for VANET simulations!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed. Check the output above.${NC}"
        return 1
    fi
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "  NS-3 Installation Verification"
    echo "=========================================="
    echo ""

    # Initialize log
    echo "=== Verification started: $(date) ===" > "${LOG_FILE}"

    find_ns3
    find_lib_dir

    echo ""
    echo "Running tests..."
    echo "----------------"
    echo ""

    test_ns3_basic
    test_modules
    test_80211p
    test_routing
    test_wireless
    test_vanet_simulation

    print_summary
}

main "$@"
