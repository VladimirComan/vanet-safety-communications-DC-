#!/bin/bash
# run_netanim.sh - Run simulation and open NetAnim viewer
# Generates animation trace and opens the NetAnim GUI to replay

set -e

# Default parameters
VEHICLES=${VEHICLES:-30}
SPEED=${SPEED:-30}
ROUTING=${ROUTING:-AODV}
SIM_TIME=${SIM_TIME:-60}
GRID_SIZE=${GRID_SIZE:-3}
SKIP_SIM=${SKIP_SIM:-false}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --vehicles|-v)
            VEHICLES="$2"
            shift 2
            ;;
        --speed|-s)
            SPEED="$2"
            shift 2
            ;;
        --routing|-r)
            ROUTING="$2"
            shift 2
            ;;
        --time|-t)
            SIM_TIME="$2"
            shift 2
            ;;
        --grid|-g)
            GRID_SIZE="$2"
            shift 2
            ;;
        --open-only|-o)
            SKIP_SIM=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Run VANET simulation and view with NetAnim"
            echo ""
            echo "Options:"
            echo "  -v, --vehicles NUM    Number of vehicles (default: 30)"
            echo "  -s, --speed KMH       Vehicle speed in km/h (default: 30)"
            echo "  -r, --routing PROTO   Routing protocol: AODV or OLSR (default: AODV)"
            echo "  -t, --time SEC        Simulation time in seconds (default: 60)"
            echo "  -g, --grid SIZE       Grid size (default: 3)"
            echo "  -o, --open-only       Skip simulation, just open existing trace"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "NetAnim Controls:"
            echo "  - Play/Pause button to control animation"
            echo "  - Speed slider to control playback speed"
            echo "  - Click nodes to see details"
            echo "  - Enable 'Show packets' to visualize network traffic"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
NS3_DIR="$PROJECT_DIR/ns-3-allinone/ns-3.42"
NETANIM_DIR="$PROJECT_DIR/ns-3-allinone/netanim-3.109"
RESULTS_DIR="$PROJECT_DIR/results"

# Convert speed from km/h to m/s
SPEED_MS=$(echo "scale=2; $SPEED / 3.6" | bc)

# Experiment name
EXPERIMENT="vanet_v${VEHICLES}_s${SPEED}_${ROUTING}"

cd "$NS3_DIR"

if [ "$SKIP_SIM" = false ]; then
    echo "=============================================="
    echo "VANET Simulation with NetAnim Visualization"
    echo "=============================================="
    echo "Parameters:"
    echo "  Vehicles: $VEHICLES"
    echo "  Speed: $SPEED km/h ($SPEED_MS m/s)"
    echo "  Routing: $ROUTING"
    echo "  Simulation time: $SIM_TIME s"
    echo "  Grid: ${GRID_SIZE}x${GRID_SIZE}"
    echo "=============================================="
    echo ""
    echo "Running simulation..."

    # Run simulation with NetAnim trace enabled
    /usr/bin/python3 ./ns3 run "scratch/vanet-simulation \
        --numVehicles=$VEHICLES \
        --vehicleSpeed=$SPEED_MS \
        --routingProtocol=$ROUTING \
        --simTime=$SIM_TIME \
        --gridSizeX=$GRID_SIZE \
        --gridSizeY=$GRID_SIZE \
        --enablePcap=false \
        --enableNetAnim=true \
        --experimentName=$EXPERIMENT \
        --warmupTime=5"

    echo ""
    echo "Simulation complete!"
fi

TRACE_FILE="$NS3_DIR/results/${EXPERIMENT}_animation.xml"

if [ ! -f "$TRACE_FILE" ]; then
    # Try default name in NS3 results
    TRACE_FILE="$NS3_DIR/results/vanet_animation.xml"
fi

if [ ! -f "$TRACE_FILE" ]; then
    # Try project results directory
    TRACE_FILE="$RESULTS_DIR/${EXPERIMENT}_animation.xml"
fi

if [ ! -f "$TRACE_FILE" ]; then
    TRACE_FILE="$RESULTS_DIR/vanet_animation.xml"
fi

if [ ! -f "$TRACE_FILE" ]; then
    echo "Error: Animation trace file not found!"
    echo "Searched in:"
    echo "  - $NS3_DIR/results/"
    echo "  - $RESULTS_DIR/"
    echo ""
    echo "Run a simulation first with: ./run_netanim.sh --vehicles 20 --time 30"
    exit 1
fi

echo ""
echo "=============================================="
echo "Opening NetAnim..."
echo "Trace file: $TRACE_FILE"
echo "=============================================="
echo ""
echo "NetAnim Tips:"
echo "  1. Click 'Play' to start animation"
echo "  2. Use speed slider for faster playback"
echo "  3. Enable 'Show Packets' to see traffic"
echo "  4. Click nodes for details"
echo "=============================================="

# Open NetAnim with trace file
"$NETANIM_DIR/NetAnim" "$TRACE_FILE"
