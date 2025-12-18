#!/usr/bin/env bash
#
# NS-3 Environment Setup Script
# Source this file to set up NS-3 environment variables.
#
# Usage: source ns3_env.sh
#

export NS3_HOME="/home/vladimir/proiectDC/ns-3-allinone/ns-3.42"
export NS3_VERSION="3.42"

# Add NS-3 to PATH
if [[ -d "${NS3_HOME}/build/bin" ]]; then
    export PATH="${NS3_HOME}/build/bin:${PATH}"
elif [[ -d "${NS3_HOME}/cmake-cache" ]]; then
    export PATH="${NS3_HOME}/cmake-cache:${PATH}"
fi

# Python bindings
if [[ -d "${NS3_HOME}/build/bindings/python" ]]; then
    export PYTHONPATH="${NS3_HOME}/build/bindings/python:${PYTHONPATH:-}"
fi

# Library path
if [[ -d "${NS3_HOME}/build/lib" ]]; then
    export LD_LIBRARY_PATH="${NS3_HOME}/build/lib:${LD_LIBRARY_PATH:-}"
elif [[ -d "${NS3_HOME}/cmake-cache/lib" ]]; then
    export LD_LIBRARY_PATH="${NS3_HOME}/cmake-cache/lib:${LD_LIBRARY_PATH:-}"
fi

echo "NS-3 environment configured."
echo "  NS3_HOME: ${NS3_HOME}"
echo "  NS3_VERSION: ${NS3_VERSION}"

# Helper function to run NS-3 programs
ns3_run() {
    if [[ -f "${NS3_HOME}/ns3" ]]; then
        cd "${NS3_HOME}" && ./ns3 run "$@"
    elif [[ -f "${NS3_HOME}/waf" ]]; then
        cd "${NS3_HOME}" && ./waf --run "$@"
    else
        echo "Error: No NS-3 runner found."
        return 1
    fi
}

export -f ns3_run
