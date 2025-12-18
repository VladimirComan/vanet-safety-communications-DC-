#!/usr/bin/env python3
"""
parse_results.py
================

Parser module for VANET simulation results.
Handles FlowMonitor XML, custom CSV logs, and summary files.

This module provides functions to:
- Parse FlowMonitor XML output for detailed flow statistics
- Parse custom packet and mobility CSV logs
- Calculate KPIs (latency, PDR, jitter, throughput)
- Aggregate results across multiple experiments

Author: VANET Project Team
Course: Data Communications and Computer Networks
"""

import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class FlowStats:
    """Statistics for a single flow from FlowMonitor."""
    flow_id: int
    src_addr: str
    dst_addr: str
    src_port: int
    dst_port: int
    protocol: int
    tx_bytes: int
    tx_packets: int
    rx_bytes: int
    rx_packets: int
    lost_packets: int
    delay_sum_ns: float
    delay_sum_ms: float = 0.0
    jitter_sum_ns: float = 0.0
    jitter_sum_ms: float = 0.0
    first_tx_time: float = 0.0
    last_tx_time: float = 0.0
    first_rx_time: float = 0.0
    last_rx_time: float = 0.0

    # Derived metrics
    pdr: float = 0.0
    mean_delay_ms: float = 0.0
    mean_jitter_ms: float = 0.0
    throughput_kbps: float = 0.0

    def calculate_derived_metrics(self):
        """Calculate derived metrics from raw statistics."""
        # Packet Delivery Ratio
        if self.tx_packets > 0:
            self.pdr = (self.rx_packets / self.tx_packets) * 100.0

        # Mean delay
        if self.rx_packets > 0:
            self.mean_delay_ms = (self.delay_sum_ns / self.rx_packets) / 1e6

        # Mean jitter
        if self.rx_packets > 1:
            self.mean_jitter_ms = (self.jitter_sum_ns / (self.rx_packets - 1)) / 1e6

        # Throughput
        duration = self.last_rx_time - self.first_tx_time
        if duration > 0:
            self.throughput_kbps = (self.rx_bytes * 8.0) / (duration * 1000.0)


@dataclass
class ExperimentResults:
    """Complete results from a single experiment."""
    experiment_name: str
    num_vehicles: int
    speed_kmh: float
    routing_protocol: str
    random_seed: int
    sim_time: float

    # Aggregate statistics
    total_tx_packets: int = 0
    total_rx_packets: int = 0
    total_tx_bytes: int = 0
    total_rx_bytes: int = 0

    # KPIs
    pdr: float = 0.0
    mean_delay_ms: float = 0.0
    p50_delay_ms: float = 0.0
    p95_delay_ms: float = 0.0
    p99_delay_ms: float = 0.0
    mean_jitter_ms: float = 0.0
    throughput_kbps: float = 0.0

    # Raw data
    delays: List[float] = field(default_factory=list)
    flow_stats: List[FlowStats] = field(default_factory=list)
    packet_log: Optional[pd.DataFrame] = None
    mobility_log: Optional[pd.DataFrame] = None


# ============================================================================
# FLOWMONITOR XML PARSER
# ============================================================================

def parse_flowmonitor_xml(xml_path: str) -> List[FlowStats]:
    """
    Parse FlowMonitor XML output file.

    Args:
        xml_path: Path to FlowMonitor XML file

    Returns:
        List of FlowStats objects
    """
    if not os.path.exists(xml_path):
        logger.warning(f"FlowMonitor XML not found: {xml_path}")
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML {xml_path}: {e}")
        return []

    flows = []

    # Parse Ipv4FlowClassifier for flow identification
    flow_classifier = {}
    classifier = root.find('.//Ipv4FlowClassifier')
    if classifier is not None:
        for flow in classifier.findall('Flow'):
            flow_id = int(flow.get('flowId', 0))
            flow_classifier[flow_id] = {
                'src_addr': flow.get('sourceAddress', ''),
                'dst_addr': flow.get('destinationAddress', ''),
                'src_port': int(flow.get('sourcePort', 0)),
                'dst_port': int(flow.get('destinationPort', 0)),
                'protocol': int(flow.get('protocol', 0))
            }

    # Parse FlowStats
    flow_stats = root.find('.//FlowStats')
    if flow_stats is not None:
        for flow in flow_stats.findall('Flow'):
            flow_id = int(flow.get('flowId', 0))

            # Get classifier info
            clf_info = flow_classifier.get(flow_id, {
                'src_addr': '', 'dst_addr': '',
                'src_port': 0, 'dst_port': 0, 'protocol': 0
            })

            # Parse statistics
            stats = FlowStats(
                flow_id=flow_id,
                src_addr=clf_info['src_addr'],
                dst_addr=clf_info['dst_addr'],
                src_port=clf_info['src_port'],
                dst_port=clf_info['dst_port'],
                protocol=clf_info['protocol'],
                tx_bytes=int(flow.get('txBytes', 0)),
                tx_packets=int(flow.get('txPackets', 0)),
                rx_bytes=int(flow.get('rxBytes', 0)),
                rx_packets=int(flow.get('rxPackets', 0)),
                lost_packets=int(flow.get('lostPackets', 0)),
                delay_sum_ns=float(flow.get('delaySum', '0ns').replace('ns', '').replace('+', '')),
                jitter_sum_ns=float(flow.get('jitterSum', '0ns').replace('ns', '').replace('+', '')),
            )

            # Parse time histograms if available
            time_first_tx = flow.get('timeFirstTxPacket', '0ns')
            time_last_tx = flow.get('timeLastTxPacket', '0ns')
            time_first_rx = flow.get('timeFirstRxPacket', '0ns')
            time_last_rx = flow.get('timeLastRxPacket', '0ns')

            def parse_time(time_str):
                """Parse NS-3 time string to seconds."""
                time_str = time_str.replace('+', '')
                if time_str.endswith('ns'):
                    return float(time_str.replace('ns', '')) / 1e9
                elif time_str.endswith('us'):
                    return float(time_str.replace('us', '')) / 1e6
                elif time_str.endswith('ms'):
                    return float(time_str.replace('ms', '')) / 1e3
                elif time_str.endswith('s'):
                    return float(time_str.replace('s', ''))
                return float(time_str)

            stats.first_tx_time = parse_time(time_first_tx)
            stats.last_tx_time = parse_time(time_last_tx)
            stats.first_rx_time = parse_time(time_first_rx)
            stats.last_rx_time = parse_time(time_last_rx)

            stats.calculate_derived_metrics()
            flows.append(stats)

    logger.info(f"Parsed {len(flows)} flows from {xml_path}")
    return flows


# ============================================================================
# CSV PARSERS
# ============================================================================

def parse_packet_log(csv_path: str) -> pd.DataFrame:
    """
    Parse custom packet log CSV.

    Expected columns:
    time, nodeId, direction, type, seqNum, size, peerId, delayMs

    Args:
        csv_path: Path to packet CSV file

    Returns:
        DataFrame with packet data
    """
    if not os.path.exists(csv_path):
        logger.warning(f"Packet log not found: {csv_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path)

        # Convert time to float
        df['time'] = pd.to_numeric(df['time'], errors='coerce')

        # Convert delay to float, handling missing values
        if 'delayMs' in df.columns:
            df['delayMs'] = pd.to_numeric(df['delayMs'], errors='coerce')

        logger.info(f"Parsed {len(df)} packets from {csv_path}")
        return df

    except Exception as e:
        logger.error(f"Failed to parse packet log {csv_path}: {e}")
        return pd.DataFrame()


def parse_mobility_log(csv_path: str) -> pd.DataFrame:
    """
    Parse custom mobility log CSV.

    Expected columns:
    time, nodeId, posX, posY, posZ, velX, velY, speed

    Args:
        csv_path: Path to mobility CSV file

    Returns:
        DataFrame with mobility data
    """
    if not os.path.exists(csv_path):
        logger.warning(f"Mobility log not found: {csv_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Parsed {len(df)} mobility records from {csv_path}")
        return df

    except Exception as e:
        logger.error(f"Failed to parse mobility log {csv_path}: {e}")
        return pd.DataFrame()


def parse_summary_csv(csv_path: str) -> Dict:
    """
    Parse experiment summary CSV.

    Expected format:
    metric,value

    Args:
        csv_path: Path to summary CSV file

    Returns:
        Dictionary of metric: value pairs
    """
    if not os.path.exists(csv_path):
        logger.warning(f"Summary CSV not found: {csv_path}")
        return {}

    try:
        df = pd.read_csv(csv_path)
        summary = dict(zip(df['metric'], df['value']))
        logger.info(f"Parsed summary with {len(summary)} metrics from {csv_path}")
        return summary

    except Exception as e:
        logger.error(f"Failed to parse summary {csv_path}: {e}")
        return {}


def parse_metadata_json(json_path: str) -> Dict:
    """
    Parse experiment metadata JSON.

    Args:
        json_path: Path to metadata JSON file

    Returns:
        Dictionary with metadata
    """
    if not os.path.exists(json_path):
        logger.warning(f"Metadata JSON not found: {json_path}")
        return {}

    try:
        with open(json_path, 'r') as f:
            metadata = json.load(f)
        logger.info(f"Parsed metadata from {json_path}")
        return metadata

    except Exception as e:
        logger.error(f"Failed to parse metadata {json_path}: {e}")
        return {}


# ============================================================================
# EXPERIMENT LOADER
# ============================================================================

def load_experiment(exp_dir: str) -> Optional[ExperimentResults]:
    """
    Load all results from an experiment directory.

    Args:
        exp_dir: Path to experiment directory

    Returns:
        ExperimentResults object or None if loading fails
    """
    exp_dir = Path(exp_dir)

    if not exp_dir.exists():
        logger.error(f"Experiment directory not found: {exp_dir}")
        return None

    # Find experiment name from directory or files
    exp_name = exp_dir.name

    # Load metadata
    metadata_file = exp_dir / f"{exp_name}_metadata.json"
    if not metadata_file.exists():
        # Try to find any metadata file
        metadata_files = list(exp_dir.glob("*_metadata.json"))
        if metadata_files:
            metadata_file = metadata_files[0]
            exp_name = metadata_file.stem.replace("_metadata", "")

    metadata = parse_metadata_json(str(metadata_file))

    # Extract parameters from metadata or filename
    params = metadata.get('parameters', {})

    if not params:
        # Parse from experiment name: v60_s50_AODV_seed1
        parts = exp_name.split('_')
        try:
            for part in parts:
                if part.startswith('v'):
                    params['num_vehicles'] = int(part[1:])
                elif part.startswith('s'):
                    params['speed_kmh'] = float(part[1:])
                elif part.startswith('seed'):
                    params['random_seed'] = int(part[4:])
                elif part in ['AODV', 'OLSR']:
                    params['routing_protocol'] = part
        except ValueError:
            pass

    # Create results object
    results = ExperimentResults(
        experiment_name=exp_name,
        num_vehicles=params.get('num_vehicles', 0),
        speed_kmh=params.get('speed_kmh', 0),
        routing_protocol=params.get('routing_protocol', 'UNKNOWN'),
        random_seed=params.get('random_seed', 0),
        sim_time=params.get('sim_time', 0)
    )

    # Load summary CSV
    summary_file = exp_dir / f"{exp_name}_summary.csv"
    if not summary_file.exists():
        summary_files = list(exp_dir.glob("*_summary.csv"))
        if summary_files:
            summary_file = summary_files[0]

    summary = parse_summary_csv(str(summary_file))

    if summary:
        results.total_tx_packets = int(float(summary.get('beaconsSent', 0)))
        results.total_rx_packets = int(float(summary.get('beaconsReceived', 0)))
        results.pdr = float(summary.get('pdr', 0))
        results.mean_delay_ms = float(summary.get('delayMean', 0))
        results.p50_delay_ms = float(summary.get('delayP50', 0))
        results.p95_delay_ms = float(summary.get('delayP95', 0))
        results.p99_delay_ms = float(summary.get('delayP99', 0))
        results.throughput_kbps = float(summary.get('throughputKbps', 0))

    # Load FlowMonitor data
    fm_file = exp_dir / f"{exp_name}_flowmonitor.xml"
    if not fm_file.exists():
        fm_files = list(exp_dir.glob("*_flowmonitor.xml"))
        if fm_files:
            fm_file = fm_files[0]

    results.flow_stats = parse_flowmonitor_xml(str(fm_file))

    # Load packet log
    packet_file = exp_dir / f"{exp_name}_packets.csv"
    if not packet_file.exists():
        packet_files = list(exp_dir.glob("*_packets.csv"))
        if packet_files:
            packet_file = packet_files[0]

    results.packet_log = parse_packet_log(str(packet_file))

    # Extract delays from packet log
    if results.packet_log is not None and not results.packet_log.empty:
        rx_packets = results.packet_log[results.packet_log['direction'] == 'RX']
        if 'delayMs' in rx_packets.columns:
            delays = rx_packets['delayMs'].dropna().values
            results.delays = list(delays[delays > 0])

    # Load mobility log
    mobility_file = exp_dir / f"{exp_name}_mobility.csv"
    if not mobility_file.exists():
        mobility_files = list(exp_dir.glob("*_mobility.csv"))
        if mobility_files:
            mobility_file = mobility_files[0]

    results.mobility_log = parse_mobility_log(str(mobility_file))

    logger.info(f"Loaded experiment: {exp_name}")
    return results


def load_experiment_matrix(matrix_dir: str) -> List[ExperimentResults]:
    """
    Load all experiments from a matrix run directory.

    Args:
        matrix_dir: Path to matrix results directory

    Returns:
        List of ExperimentResults objects
    """
    matrix_dir = Path(matrix_dir)

    if not matrix_dir.exists():
        logger.error(f"Matrix directory not found: {matrix_dir}")
        return []

    results = []

    # Find all experiment subdirectories
    exp_dirs = [d for d in matrix_dir.iterdir() if d.is_dir()]

    logger.info(f"Found {len(exp_dirs)} experiment directories in {matrix_dir}")

    for exp_dir in sorted(exp_dirs):
        exp_results = load_experiment(str(exp_dir))
        if exp_results is not None:
            results.append(exp_results)

    logger.info(f"Successfully loaded {len(results)} experiments")
    return results


# ============================================================================
# DISTANCE-BASED ANALYSIS
# ============================================================================

def calculate_distance_based_metrics(
    packet_log: pd.DataFrame,
    mobility_log: pd.DataFrame,
    distance_bins: List[Tuple[float, float]] = None
) -> pd.DataFrame:
    """
    Calculate metrics binned by distance between sender and receiver.

    Args:
        packet_log: DataFrame with packet data
        mobility_log: DataFrame with mobility data
        distance_bins: List of (min, max) distance tuples in meters

    Returns:
        DataFrame with metrics per distance bin
    """
    if packet_log is None or packet_log.empty:
        return pd.DataFrame()

    if mobility_log is None or mobility_log.empty:
        return pd.DataFrame()

    if distance_bins is None:
        distance_bins = [(0, 100), (100, 200), (200, 300), (300, float('inf'))]

    # Get RX packets only
    rx_packets = packet_log[packet_log['direction'] == 'RX'].copy()

    if rx_packets.empty:
        return pd.DataFrame()

    # Calculate distances for each packet
    distances = []

    for _, pkt in rx_packets.iterrows():
        time = pkt['time']
        sender_id = pkt.get('peerId', -1)
        receiver_id = pkt['nodeId']

        if sender_id < 0:
            distances.append(np.nan)
            continue

        # Get positions at packet time (approximate)
        time_tolerance = 1.0  # seconds

        sender_pos = mobility_log[
            (mobility_log['nodeId'] == sender_id) &
            (mobility_log['time'] >= time - time_tolerance) &
            (mobility_log['time'] <= time + time_tolerance)
        ]

        receiver_pos = mobility_log[
            (mobility_log['nodeId'] == receiver_id) &
            (mobility_log['time'] >= time - time_tolerance) &
            (mobility_log['time'] <= time + time_tolerance)
        ]

        if sender_pos.empty or receiver_pos.empty:
            distances.append(np.nan)
            continue

        # Use closest time
        s_pos = sender_pos.iloc[(sender_pos['time'] - time).abs().argsort().iloc[0]]
        r_pos = receiver_pos.iloc[(receiver_pos['time'] - time).abs().argsort().iloc[0]]

        dist = np.sqrt(
            (s_pos['posX'] - r_pos['posX'])**2 +
            (s_pos['posY'] - r_pos['posY'])**2
        )
        distances.append(dist)

    rx_packets['distance'] = distances

    # Calculate metrics per bin
    results = []

    for bin_min, bin_max in distance_bins:
        bin_packets = rx_packets[
            (rx_packets['distance'] >= bin_min) &
            (rx_packets['distance'] < bin_max)
        ]

        if bin_packets.empty:
            continue

        delays = bin_packets['delayMs'].dropna()

        results.append({
            'distance_min': bin_min,
            'distance_max': bin_max,
            'distance_label': f"{bin_min}-{bin_max}m" if bin_max < float('inf') else f">{bin_min}m",
            'packet_count': len(bin_packets),
            'delay_mean_ms': delays.mean() if len(delays) > 0 else np.nan,
            'delay_p50_ms': delays.quantile(0.5) if len(delays) > 0 else np.nan,
            'delay_p95_ms': delays.quantile(0.95) if len(delays) > 0 else np.nan,
            'delay_p99_ms': delays.quantile(0.99) if len(delays) > 0 else np.nan,
        })

    return pd.DataFrame(results)


# ============================================================================
# AGGREGATION FUNCTIONS
# ============================================================================

def aggregate_by_parameter(
    experiments: List[ExperimentResults],
    group_by: str = 'routing_protocol'
) -> pd.DataFrame:
    """
    Aggregate experiment results by a parameter.

    Args:
        experiments: List of ExperimentResults
        group_by: Parameter to group by ('routing_protocol', 'num_vehicles', 'speed_kmh')

    Returns:
        DataFrame with aggregated statistics
    """
    if not experiments:
        return pd.DataFrame()

    # Create DataFrame from experiments
    data = []
    for exp in experiments:
        data.append({
            'experiment_name': exp.experiment_name,
            'num_vehicles': exp.num_vehicles,
            'speed_kmh': exp.speed_kmh,
            'routing_protocol': exp.routing_protocol,
            'random_seed': exp.random_seed,
            'pdr': exp.pdr,
            'delay_mean_ms': exp.mean_delay_ms,
            'delay_p50_ms': exp.p50_delay_ms,
            'delay_p95_ms': exp.p95_delay_ms,
            'delay_p99_ms': exp.p99_delay_ms,
            'throughput_kbps': exp.throughput_kbps,
            'total_tx': exp.total_tx_packets,
            'total_rx': exp.total_rx_packets
        })

    df = pd.DataFrame(data)

    # Aggregate by the specified parameter
    agg_funcs = {
        'pdr': ['mean', 'std', 'min', 'max'],
        'delay_mean_ms': ['mean', 'std', 'min', 'max'],
        'delay_p95_ms': ['mean', 'std'],
        'delay_p99_ms': ['mean', 'std'],
        'throughput_kbps': ['mean', 'std'],
        'experiment_name': 'count'
    }

    aggregated = df.groupby(group_by).agg(agg_funcs)
    aggregated.columns = ['_'.join(col).strip() for col in aggregated.columns.values]
    aggregated = aggregated.rename(columns={'experiment_name_count': 'num_experiments'})

    return aggregated.reset_index()


def create_combined_dataframe(experiments: List[ExperimentResults]) -> pd.DataFrame:
    """
    Create a combined DataFrame from all experiments for analysis.

    Args:
        experiments: List of ExperimentResults

    Returns:
        DataFrame with all experiment data
    """
    data = []
    for exp in experiments:
        data.append({
            'experiment': exp.experiment_name,
            'vehicles': exp.num_vehicles,
            'speed_kmh': exp.speed_kmh,
            'routing': exp.routing_protocol,
            'seed': exp.random_seed,
            'pdr': exp.pdr,
            'delay_mean': exp.mean_delay_ms,
            'delay_p50': exp.p50_delay_ms,
            'delay_p95': exp.p95_delay_ms,
            'delay_p99': exp.p99_delay_ms,
            'jitter': exp.mean_jitter_ms,
            'throughput': exp.throughput_kbps,
            'tx_packets': exp.total_tx_packets,
            'rx_packets': exp.total_rx_packets
        })

    return pd.DataFrame(data)


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse VANET simulation results")
    parser.add_argument("path", help="Path to experiment directory or matrix directory")
    parser.add_argument("--matrix", action="store_true", help="Load as matrix of experiments")
    parser.add_argument("--output", "-o", help="Output CSV file")

    args = parser.parse_args()

    if args.matrix:
        experiments = load_experiment_matrix(args.path)
        if experiments:
            df = create_combined_dataframe(experiments)
            print("\nCombined Results:")
            print(df.to_string())

            if args.output:
                df.to_csv(args.output, index=False)
                print(f"\nSaved to {args.output}")

            # Print aggregations
            print("\n\nAggregated by Routing Protocol:")
            print(aggregate_by_parameter(experiments, 'routing_protocol').to_string())

            print("\n\nAggregated by Vehicle Count:")
            print(aggregate_by_parameter(experiments, 'num_vehicles').to_string())
    else:
        exp = load_experiment(args.path)
        if exp:
            print(f"\nExperiment: {exp.experiment_name}")
            print(f"Vehicles: {exp.num_vehicles}")
            print(f"Speed: {exp.speed_kmh} km/h")
            print(f"Routing: {exp.routing_protocol}")
            print(f"PDR: {exp.pdr:.2f}%")
            print(f"Delay (mean): {exp.mean_delay_ms:.3f} ms")
            print(f"Delay (p95): {exp.p95_delay_ms:.3f} ms")
            print(f"Throughput: {exp.throughput_kbps:.2f} kbps")
