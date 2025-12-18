#!/bin/bash
# run_pyviz.sh - Run VANET simulation with PyViz visualization
# Uses system Python to ensure PyGObject is available

set -e

# Default parameters
VEHICLES=${VEHICLES:-30}
SPEED=${SPEED:-30}
ROUTING=${ROUTING:-AODV}
SIM_TIME=${SIM_TIME:-60}
GRID_SIZE=${GRID_SIZE:-3}

# Convert speed from km/h to m/s
SPEED_MS=$(echo "scale=2; $SPEED / 3.6" | bc)

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --vehicles|-v)
            VEHICLES="$2"
            shift 2
            ;;
        --speed|-s)
            SPEED="$2"
            SPEED_MS=$(echo "scale=2; $SPEED / 3.6" | bc)
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
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Run VANET simulation with PyViz visualization"
            echo ""
            echo "Options:"
            echo "  -v, --vehicles NUM    Number of vehicles (default: 30)"
            echo "  -s, --speed KMH       Vehicle speed in km/h (default: 30)"
            echo "  -r, --routing PROTO   Routing protocol: AODV or OLSR (default: AODV)"
            echo "  -t, --time SEC        Simulation time in seconds (default: 60)"
            echo "  -g, --grid SIZE       Grid size (default: 3)"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "PyViz Controls:"
            echo "  - Mouse wheel: Zoom in/out"
            echo "  - Left drag: Pan view"
            echo "  - Right click: Context menu"
            echo "  - Play/Pause: Control simulation speed"
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

cd "$NS3_DIR"

echo "=============================================="
echo "VANET Simulation with PyViz Visualization"
echo "=============================================="
echo "Parameters:"
echo "  Vehicles: $VEHICLES"
echo "  Speed: $SPEED km/h ($SPEED_MS m/s)"
echo "  Routing: $ROUTING"
echo "  Simulation time: $SIM_TIME s"
echo "  Grid: ${GRID_SIZE}x${GRID_SIZE}"
echo "=============================================="
echo ""
echo "PyViz Controls:"
echo "  - Use the slider to control simulation speed"
echo "  - Mouse wheel to zoom, drag to pan"
echo "  - Nodes are colored by their activity"
echo "=============================================="
echo ""

# Run with PyViz
export DISPLAY=${DISPLAY:-:0}
python3 ./ns3 run "scratch/vanet-simulation \
    --numVehicles=$VEHICLES \
    --vehicleSpeed=$SPEED_MS \
    --routingProtocol=$ROUTING \
    --simTime=$SIM_TIME \
    --gridSizeX=$GRID_SIZE \
    --gridSizeY=$GRID_SIZE \
    --enablePcap=false \
    --warmupTime=5" --vis
