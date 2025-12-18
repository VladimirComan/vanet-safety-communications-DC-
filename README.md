# VANET Safety Communications Simulation Project

## Vehicular Ad-Hoc Network (VANET) Safety Communications + AI Congestion Control

**Course:** Data Communications and Computer Networks
**Project Topic:** Tema 4 – VANET Safety Communications

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Project Structure](#project-structure)
5. [Running Simulations](#running-simulations)
6. [Data Analysis](#data-analysis)
7. [AI Anomaly Detection](#ai-anomaly-detection)
8. [Reproducing Results](#reproducing-results)
9. [Academic Discussion](#academic-discussion)

---

## Project Overview

This project implements a comprehensive VANET (Vehicular Ad-Hoc Network) simulation framework for studying safety communications using IEEE 802.11p/WAVE technology. The simulation models realistic urban scenarios with:

- **Urban Grid Topology**: 1-2 km² area with 4-16 intersections
- **Vehicle Counts**: 30, 60, and 120 vehicles
- **Vehicle Speeds**: 30-60 km/h with stop-and-go behavior
- **Wireless Protocol**: IEEE 802.11p at 5.9 GHz
- **Safety Messages**: 10 Hz beacons (200-400 bytes) + event alerts
- **Routing Protocols**: AODV vs OLSR comparison

### Key Performance Indicators (KPIs)

The simulation measures and reports:

| Metric | Description |
|--------|-------------|
| **Latency** | End-to-end delay (mean, P50, P95, P99) |
| **PDR** | Packet Delivery Ratio (%) |
| **Jitter** | Delay variation |
| **Throughput** | Data delivery rate (kbps) |

### Optional AI Component

An AI-based anomaly detection system identifies:
- Broadcast storms (excessive transmission rates)
- Misconfigured nodes (wrong beacon rates/sizes)
- Network anomalies

---

## System Requirements

### Target Operating System
- **Debian 13 (Trixie)** or compatible Linux distribution

### Hardware Requirements
- CPU: Multi-core recommended (parallelization support)
- RAM: 8 GB minimum, 16 GB recommended
- Storage: 10 GB free space

### Software Dependencies

| Software | Purpose |
|----------|---------|
| NS-3 (3.42+) | Network simulation |
| GCC/G++ | C++ compilation |
| CMake/Ninja | Build system |
| Python 3.10+ | Analysis and AI |
| NumPy, Pandas | Data processing |
| Matplotlib, Seaborn | Visualization |
| scikit-learn | Machine learning |
| TensorFlow (optional) | Deep learning autoencoder |

---

## Installation

### Step 1: Install Prerequisites

```bash
cd scripts/
sudo ./install_prerequisites.sh
```

This script installs:
- Build tools (GCC, CMake, Ninja)
- NS-3 dependencies (Boost, SQLite, Qt5)
- Python scientific stack
- SUMO traffic simulator (optional)

### Step 2: Build NS-3

```bash
./build_ns3.sh
```

Options:
- `--clean`: Clean rebuild
- `--version 3.42`: Specify NS-3 version
- `--debug`: Debug build

### Step 3: Verify Installation

```bash
./verify_ns3.sh
```

This verifies:
- NS-3 core functionality
- 802.11p/WAVE module
- AODV and OLSR routing modules
- FlowMonitor

### Step 4: Set Up Environment

```bash
source scripts/ns3_env.sh
source scripts/activate_venv.sh  # For Python environment
```

---

## Project Structure

```
proiectDC/
├── scripts/                    # Automation scripts
│   ├── install_prerequisites.sh
│   ├── build_ns3.sh
│   ├── verify_ns3.sh
│   ├── run_experiment.sh
│   ├── run_experiment_matrix.sh
│   └── ns3_env.sh
│
├── ns3/                        # NS-3 simulation code
│   └── vanet-simulation.cc     # Main VANET simulation
│
├── analysis/                   # Python analysis scripts
│   ├── parse_results.py        # Result parsing module
│   └── visualize_results.py    # Visualization module
│
├── ai/                         # AI anomaly detection
│   ├── feature_extraction.py   # Feature extraction
│   └── anomaly_detection.py    # ML models
│
├── results/                    # Simulation outputs
│   └── (generated during runs)
│
└── README.md                   # This file
```

---

## Running Simulations

### Single Experiment

Run a single simulation with specific parameters:

```bash
./scripts/run_experiment.sh \
    --vehicles 60 \
    --speed 50 \
    --routing AODV \
    --seed 1 \
    --simtime 300
```

**Parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--vehicles N` | Number of vehicles | 60 |
| `--speed S` | Speed in km/h | 50 |
| `--routing PROTOCOL` | AODV or OLSR | AODV |
| `--seed N` | Random seed | 1 |
| `--simtime T` | Simulation time (s) | 300 |
| `--output DIR` | Output directory | ./results |

### Full Experimental Matrix

Run all parameter combinations:

```bash
./scripts/run_experiment_matrix.sh
```

This runs:
- Vehicle counts: 30, 60, 120
- Speeds: 30, 60 km/h
- Protocols: AODV, OLSR
- Seeds: 1-5 (for statistical reliability)

**Total experiments:** 60

**Options:**

| Option | Description |
|--------|-------------|
| `--quick` | Reduced matrix for testing |
| `--parallel N` | Run N experiments in parallel |
| `--resume` | Resume incomplete run |
| `--dry-run` | Show experiments without running |

### Quick Test

```bash
./scripts/run_experiment_matrix.sh --quick
```

Runs a reduced matrix with fewer seeds and shorter simulation time.

---

## Visualization

Two visualization methods are available to watch simulations:

### PyViz (Real-time Visualization)

PyViz shows the simulation running live with interactive controls. Nodes and packets are displayed in real-time.

```bash
# Run with default parameters (30 vehicles, 30 km/h, AODV)
./scripts/run_pyviz.sh

# Run with custom parameters
./scripts/run_pyviz.sh --vehicles 60 --speed 50 --routing OLSR --time 120

# Show help
./scripts/run_pyviz.sh --help
```

**PyViz Controls:**
- Mouse wheel: Zoom in/out
- Left drag: Pan view
- Speed slider: Control simulation speed
- Right-click: Context menu with options

**Requirements:** PyGObject and GooCanvas (install with `sudo apt install python3-gi gir1.2-goocanvas-2.0`)

### NetAnim (Replay Visualization)

NetAnim creates a trace file during simulation that can be replayed and analyzed afterwards. This is useful for detailed analysis and presentations.

```bash
# Run simulation and open NetAnim viewer
./scripts/run_netanim.sh

# Run with custom parameters
./scripts/run_netanim.sh --vehicles 60 --speed 50 --routing AODV --time 60

# Open existing trace file (skip simulation)
./scripts/run_netanim.sh --open-only

# Show help
./scripts/run_netanim.sh --help
```

**NetAnim Features:**
- Play/Pause animation playback
- Speed slider for faster/slower playback
- Show/hide packet transmissions
- Click nodes for detailed information
- Export frames as images

**Animation files are saved to:** `results/*_animation.xml`

### Direct NS-3 Visualization Commands

You can also run visualizations directly:

```bash
cd ns-3-allinone/ns-3.42

# PyViz (real-time)
./ns3 run "scratch/vanet-simulation --numVehicles=30 --simTime=60" --vis

# NetAnim (trace generation)
./ns3 run "scratch/vanet-simulation --numVehicles=30 --simTime=60 --enableNetAnim=true"

# Then open trace in NetAnim
../netanim-3.109/NetAnim ../results/vanet_animation.xml
```

---

## Data Analysis

### Generate All Visualizations

```bash
cd analysis/
python visualize_results.py ../results/matrix_YYYYMMDD_HHMMSS/
```

### Output Plots

The visualization module generates:

1. **Delay vs Density** (`vanet_delay_vs_density.png`)
   - Mean and P95 delay vs vehicle count
   - AODV vs OLSR comparison

2. **PDR vs Density** (`vanet_pdr_vs_density.png`)
   - Packet delivery ratio vs vehicle count
   - Error bars from multiple seeds

3. **Delay CDF** (`vanet_delay_cdf.png`)
   - Cumulative distribution of end-to-end delay
   - P50, P95, P99 marked

4. **Alert Delay CDF** (`vanet_alert_delay_cdf.png`)
   - CDF for event-driven safety alerts
   - 100ms threshold marked

5. **Throughput Comparison** (`vanet_throughput.png`)
   - Aggregate throughput by protocol

6. **Heatmaps** (`vanet_pdr_heatmap.png`, `vanet_delay_heatmap.png`)
   - Metrics across vehicles × speed matrix

7. **Summary Dashboard** (`vanet_dashboard.png`)
   - Combined visualization of all key metrics

### Parse Individual Results

```bash
python parse_results.py ../results/experiment_name/
```

---

## AI Anomaly Detection

### Run Detection Pipeline

```bash
cd ai/
python anomaly_detection.py ../results/experiment_name/experiment_name_packets.csv \
    --output ../results/ai_results/ \
    --window 5.0 \
    --anomaly-ratio 0.05
```

### Features Extracted

Per node per time window:

| Feature | Description |
|---------|-------------|
| `tx_rate_per_sec` | Transmission rate |
| `tx_bytes_per_sec` | Byte transmission rate |
| `avg_inter_tx_interval` | Average time between transmissions |
| `unique_senders` | Neighbor count |
| `duplicate_ratio` | Duplicate packet ratio |
| `channel_busy_ratio` | Estimated channel utilization |
| `alert_ratio` | Fraction of alert messages |
| `avg_delay_ms` | Average receive delay |

### Models Compared

1. **Isolation Forest**
   - Fast, scalable unsupervised detection
   - Works well with high-dimensional data

2. **One-Class SVM**
   - Boundary-based outlier detection
   - Good for well-defined normal behavior

3. **Autoencoder**
   - Reconstruction error-based detection
   - Captures complex patterns

### Expected Results

Target: **F1 Score ≥ 0.85** for anomaly detection

---

## Reproducing Results

### Complete Reproduction

```bash
# 1. Install everything
cd scripts/
sudo ./install_prerequisites.sh
./build_ns3.sh
./verify_ns3.sh

# 2. Run full experimental matrix (takes several hours)
./run_experiment_matrix.sh

# 3. Generate visualizations
cd ../analysis/
python visualize_results.py ../results/matrix_*/

# 4. Run AI analysis
cd ../ai/
for exp in ../results/matrix_*/*; do
    if [ -f "$exp"/*_packets.csv ]; then
        python anomaly_detection.py "$exp"/*_packets.csv --output "$exp/ai/"
    fi
done
```

### Quick Validation

```bash
# Quick test (5-10 minutes)
./scripts/run_experiment_matrix.sh --quick

# Verify outputs exist
ls results/matrix_*/combined_results.csv
ls results/matrix_*/plots/
```

---

## Academic Discussion

### AODV vs OLSR Under Mobility and Density

**AODV (Ad-hoc On-demand Distance Vector)**
- Reactive protocol: routes discovered on demand
- Lower overhead in sparse networks
- Route discovery latency during initial communication
- Sensitive to high mobility (frequent route breaks)

**OLSR (Optimized Link State Routing)**
- Proactive protocol: maintains routing tables constantly
- Higher control overhead (TC, HELLO messages)
- Lower latency for established routes
- Better route stability due to precomputed alternatives

**Key Findings:**

| Condition | Better Protocol | Reason |
|-----------|-----------------|--------|
| Low density (30 vehicles) | AODV | Less overhead |
| High density (120 vehicles) | OLSR | Stable routes |
| High mobility (60 km/h) | OLSR | Precomputed alternatives |
| Sparse topology | AODV | On-demand efficiency |

### Safety Message Reliability and Latency

**Critical Requirements:**
- Safety beacons: < 100 ms latency (DSRC standard)
- Emergency alerts: < 50 ms preferred

**Factors Affecting Performance:**

1. **Hidden Terminal Problem**
   - Multiple vehicles broadcasting simultaneously
   - Mitigated by RTS/CTS (not used in broadcast)
   - Solution: Controlled beacon intervals with jitter

2. **Channel Congestion**
   - 10 Hz × N vehicles = high channel utilization
   - 120 vehicles × 10 Hz × 300 bytes ≈ 2.88 Mbps
   - Approaches 6 Mbps channel capacity

3. **Mobility Effects**
   - Route changes cause temporary packet loss
   - Higher speeds increase handoff frequency

### Impact of Congestion

**Observed Effects:**

- PDR decreases as vehicle count increases
- Delay variance (jitter) increases with congestion
- Alert messages may be delayed during peak load
- Routing overhead compounds congestion

**Mitigation Strategies:**

1. **Adaptive Beacon Rate**: Reduce beacon frequency when channel busy ratio is high
2. **Priority Queuing**: Prioritize alerts over regular beacons
3. **Congestion Control**: Transmit power control, rate adaptation

### Value of AI-Based Detection

**Benefits:**

1. **Real-time Anomaly Detection**
   - Identify broadcast storms within seconds
   - Detect misconfigured nodes automatically

2. **Proactive Network Management**
   - Alert operators before severe congestion
   - Enable automated response actions

3. **Security Enhancement**
   - Detect potential denial-of-service attacks
   - Identify malicious nodes flooding the network

**Implementation Considerations:**

- Feature extraction can run in real-time on RSUs
- Models require periodic retraining as traffic patterns change
- Lightweight models (Isolation Forest) suitable for embedded systems

---

## References

1. NS-3 Documentation: https://www.nsnam.org/docs/
2. IEEE 802.11p Standard
3. WAVE/DSRC Protocol Stack
4. AODV RFC 3561
5. OLSR RFC 3626

---

## Authors

VANET Project Team
Data Communications and Computer Networks Course

---

## License

Academic use only. For educational purposes.
