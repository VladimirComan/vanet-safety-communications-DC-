#!/usr/bin/env python3
"""
feature_extraction.py
=====================

Feature extraction module for AI-based anomaly detection in VANET.

This module extracts features from simulation logs that can be used
to detect broadcast storms, misconfigured nodes, and other anomalies.

Features extracted per node per time window:
- Channel busy ratio (estimated)
- Transmission rate (packets/s, bytes/s)
- Retransmission count (if available)
- Neighbor count
- Duplicate packet count
- Average inter-packet interval
- Packet size statistics

Author: VANET Project Team
Course: Data Communications and Computer Networks
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

import numpy as np
import pandas as pd
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# FEATURE DEFINITIONS
# ============================================================================

FEATURE_NAMES = [
    'node_id',
    'time_window',
    # Transmission features
    'tx_count',
    'tx_rate_per_sec',
    'tx_bytes',
    'tx_bytes_per_sec',
    'avg_tx_size',
    'std_tx_size',
    # Reception features
    'rx_count',
    'rx_rate_per_sec',
    'rx_bytes',
    'unique_senders',
    # Timing features
    'avg_inter_tx_interval',
    'std_inter_tx_interval',
    'min_inter_tx_interval',
    # Alert features
    'alert_count',
    'alert_ratio',
    # Delay features (if receiving)
    'avg_delay_ms',
    'max_delay_ms',
    # Duplicate detection
    'duplicate_rx_count',
    'duplicate_ratio',
    # Channel estimation
    'channel_busy_ratio',
]


# ============================================================================
# FEATURE EXTRACTION
# ============================================================================

def extract_node_features(
    packet_log: pd.DataFrame,
    node_id: int,
    time_start: float,
    time_end: float,
    beacon_interval: float = 0.1  # 10 Hz expected
) -> Dict:
    """
    Extract features for a single node within a time window.

    Args:
        packet_log: DataFrame with packet data
        node_id: Node ID to analyze
        time_start: Start of time window
        time_end: End of time window
        beacon_interval: Expected beacon interval for anomaly detection

    Returns:
        Dictionary of feature values
    """
    window_duration = time_end - time_start

    # Filter packets for this node and time window
    node_packets = packet_log[
        (packet_log['nodeId'] == node_id) &
        (packet_log['time'] >= time_start) &
        (packet_log['time'] < time_end)
    ]

    if node_packets.empty:
        return None

    # Separate TX and RX
    tx_packets = node_packets[node_packets['direction'] == 'TX']
    rx_packets = node_packets[node_packets['direction'] == 'RX']

    features = {
        'node_id': node_id,
        'time_window': time_start,
    }

    # ---- Transmission Features ----
    tx_count = len(tx_packets)
    features['tx_count'] = tx_count
    features['tx_rate_per_sec'] = tx_count / window_duration if window_duration > 0 else 0

    if tx_count > 0:
        features['tx_bytes'] = tx_packets['size'].sum()
        features['tx_bytes_per_sec'] = features['tx_bytes'] / window_duration
        features['avg_tx_size'] = tx_packets['size'].mean()
        features['std_tx_size'] = tx_packets['size'].std() if tx_count > 1 else 0

        # Inter-packet intervals
        tx_times = tx_packets['time'].sort_values().values
        if len(tx_times) > 1:
            intervals = np.diff(tx_times)
            features['avg_inter_tx_interval'] = intervals.mean()
            features['std_inter_tx_interval'] = intervals.std()
            features['min_inter_tx_interval'] = intervals.min()
        else:
            features['avg_inter_tx_interval'] = window_duration
            features['std_inter_tx_interval'] = 0
            features['min_inter_tx_interval'] = window_duration

        # Alert features
        if 'type' in tx_packets.columns:
            alert_count = len(tx_packets[tx_packets['type'] == 'ALERT'])
        else:
            alert_count = 0
        features['alert_count'] = alert_count
        features['alert_ratio'] = alert_count / tx_count if tx_count > 0 else 0
    else:
        features['tx_bytes'] = 0
        features['tx_bytes_per_sec'] = 0
        features['avg_tx_size'] = 0
        features['std_tx_size'] = 0
        features['avg_inter_tx_interval'] = window_duration
        features['std_inter_tx_interval'] = 0
        features['min_inter_tx_interval'] = window_duration
        features['alert_count'] = 0
        features['alert_ratio'] = 0

    # ---- Reception Features ----
    rx_count = len(rx_packets)
    features['rx_count'] = rx_count
    features['rx_rate_per_sec'] = rx_count / window_duration if window_duration > 0 else 0

    if rx_count > 0:
        features['rx_bytes'] = rx_packets['size'].sum()

        # Unique senders (neighbors)
        if 'peerId' in rx_packets.columns:
            unique_senders = rx_packets['peerId'].nunique()
        else:
            unique_senders = 0
        features['unique_senders'] = unique_senders

        # Delay features
        if 'delayMs' in rx_packets.columns:
            delays = rx_packets['delayMs'].dropna()
            if len(delays) > 0:
                features['avg_delay_ms'] = delays.mean()
                features['max_delay_ms'] = delays.max()
            else:
                features['avg_delay_ms'] = 0
                features['max_delay_ms'] = 0
        else:
            features['avg_delay_ms'] = 0
            features['max_delay_ms'] = 0

        # Duplicate detection (same seqNum from same sender)
        if 'seqNum' in rx_packets.columns and 'peerId' in rx_packets.columns:
            duplicates = rx_packets.duplicated(subset=['seqNum', 'peerId'], keep='first').sum()
        else:
            duplicates = 0
        features['duplicate_rx_count'] = duplicates
        features['duplicate_ratio'] = duplicates / rx_count if rx_count > 0 else 0
    else:
        features['rx_bytes'] = 0
        features['unique_senders'] = 0
        features['avg_delay_ms'] = 0
        features['max_delay_ms'] = 0
        features['duplicate_rx_count'] = 0
        features['duplicate_ratio'] = 0

    # ---- Channel Busy Ratio Estimation ----
    # Estimate based on TX + RX activity
    # Assume each packet occupies channel for approximately size/rate_bps seconds
    data_rate_bps = 6e6  # 6 Mbps OFDM
    total_bytes = features['tx_bytes'] + features['rx_bytes']
    transmission_time = (total_bytes * 8) / data_rate_bps
    features['channel_busy_ratio'] = min(1.0, transmission_time / window_duration)

    return features


def extract_all_features(
    packet_log: pd.DataFrame,
    window_size: float = 5.0,  # 5 second windows
    overlap: float = 0.0,     # No overlap by default
    beacon_interval: float = 0.1
) -> pd.DataFrame:
    """
    Extract features for all nodes across all time windows.

    Args:
        packet_log: DataFrame with packet data
        window_size: Duration of each time window (seconds)
        overlap: Overlap between consecutive windows (0-1)
        beacon_interval: Expected beacon interval

    Returns:
        DataFrame with features for each node-window combination
    """
    if packet_log is None or packet_log.empty:
        logger.warning("Empty packet log")
        return pd.DataFrame()

    # Determine time range
    time_min = packet_log['time'].min()
    time_max = packet_log['time'].max()

    # Get all unique nodes
    all_nodes = packet_log['nodeId'].unique()

    logger.info(f"Extracting features for {len(all_nodes)} nodes")
    logger.info(f"Time range: {time_min:.1f}s - {time_max:.1f}s")
    logger.info(f"Window size: {window_size}s")

    # Generate time windows
    step = window_size * (1 - overlap)
    windows = []
    t = time_min
    while t + window_size <= time_max:
        windows.append((t, t + window_size))
        t += step

    logger.info(f"Generated {len(windows)} time windows")

    # Extract features for each node-window combination
    all_features = []

    for node_id in all_nodes:
        for t_start, t_end in windows:
            features = extract_node_features(
                packet_log, node_id, t_start, t_end, beacon_interval
            )
            if features is not None:
                all_features.append(features)

    df = pd.DataFrame(all_features)
    logger.info(f"Extracted {len(df)} feature vectors")

    return df


# ============================================================================
# ANOMALY INJECTION
# ============================================================================

def inject_broadcast_storm_anomaly(
    features_df: pd.DataFrame,
    anomaly_ratio: float = 0.05,
    storm_factor: float = 5.0,  # 5x normal rate
    random_seed: int = 42
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Inject simulated broadcast storm anomalies into feature data.

    This simulates nodes transmitting at much higher rates than normal,
    which would indicate a misconfigured beacon rate.

    Args:
        features_df: DataFrame with extracted features
        anomaly_ratio: Fraction of samples to make anomalous
        storm_factor: Multiplier for TX rate in anomalies
        random_seed: Random seed for reproducibility

    Returns:
        Tuple of (modified_df, labels) where labels are 0=normal, 1=anomaly
    """
    np.random.seed(random_seed)

    df = features_df.copy()
    n_samples = len(df)
    n_anomalies = int(n_samples * anomaly_ratio)

    # Initialize labels
    labels = np.zeros(n_samples, dtype=int)

    # Select random samples to make anomalous
    anomaly_indices = np.random.choice(n_samples, n_anomalies, replace=False)

    for idx in anomaly_indices:
        labels[idx] = 1

        # Modify features to simulate broadcast storm
        df.loc[df.index[idx], 'tx_count'] *= storm_factor
        df.loc[df.index[idx], 'tx_rate_per_sec'] *= storm_factor
        df.loc[df.index[idx], 'tx_bytes'] *= storm_factor
        df.loc[df.index[idx], 'tx_bytes_per_sec'] *= storm_factor

        # Decrease inter-packet interval
        df.loc[df.index[idx], 'avg_inter_tx_interval'] /= storm_factor
        df.loc[df.index[idx], 'min_inter_tx_interval'] /= storm_factor

        # Increase channel busy ratio
        current_cbr = df.loc[df.index[idx], 'channel_busy_ratio']
        df.loc[df.index[idx], 'channel_busy_ratio'] = min(1.0, current_cbr * storm_factor)

    logger.info(f"Injected {n_anomalies} broadcast storm anomalies ({anomaly_ratio*100:.1f}%)")

    return df, labels


def inject_misconfigured_node_anomaly(
    features_df: pd.DataFrame,
    anomaly_ratio: float = 0.05,
    random_seed: int = 42
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Inject simulated misconfigured node anomalies.

    This simulates nodes with incorrect beacon sizes or abnormal alert ratios.

    Args:
        features_df: DataFrame with extracted features
        anomaly_ratio: Fraction of samples to make anomalous
        random_seed: Random seed

    Returns:
        Tuple of (modified_df, labels)
    """
    np.random.seed(random_seed)

    df = features_df.copy()
    n_samples = len(df)
    n_anomalies = int(n_samples * anomaly_ratio)

    labels = np.zeros(n_samples, dtype=int)
    anomaly_indices = np.random.choice(n_samples, n_anomalies, replace=False)

    for idx in anomaly_indices:
        labels[idx] = 1

        # Vary the type of misconfiguration
        anomaly_type = np.random.choice(['large_packets', 'high_alerts', 'no_rx'])

        if anomaly_type == 'large_packets':
            # Abnormally large packet sizes
            df.loc[df.index[idx], 'avg_tx_size'] *= 3.0
            df.loc[df.index[idx], 'tx_bytes'] *= 3.0
            df.loc[df.index[idx], 'tx_bytes_per_sec'] *= 3.0

        elif anomaly_type == 'high_alerts':
            # Excessive alert ratio
            df.loc[df.index[idx], 'alert_ratio'] = 0.8
            df.loc[df.index[idx], 'alert_count'] = df.loc[df.index[idx], 'tx_count'] * 0.8

        elif anomaly_type == 'no_rx':
            # Node not receiving (isolated or deaf)
            df.loc[df.index[idx], 'rx_count'] = 0
            df.loc[df.index[idx], 'rx_rate_per_sec'] = 0
            df.loc[df.index[idx], 'unique_senders'] = 0

    logger.info(f"Injected {n_anomalies} misconfigured node anomalies ({anomaly_ratio*100:.1f}%)")

    return df, labels


# ============================================================================
# PREPROCESSING
# ============================================================================

def preprocess_features(
    features_df: pd.DataFrame,
    exclude_columns: List[str] = None
) -> Tuple[np.ndarray, List[str]]:
    """
    Preprocess features for ML models.

    Args:
        features_df: DataFrame with features
        exclude_columns: Columns to exclude from features

    Returns:
        Tuple of (feature_matrix, feature_names)
    """
    if exclude_columns is None:
        exclude_columns = ['node_id', 'time_window']

    # Get feature columns
    feature_cols = [col for col in features_df.columns if col not in exclude_columns]

    # Extract feature matrix
    X = features_df[feature_cols].values

    # Handle NaN and inf values
    X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

    return X, feature_cols


def normalize_features(
    X: np.ndarray,
    method: str = 'standardize'
) -> Tuple[np.ndarray, Dict]:
    """
    Normalize feature matrix.

    Args:
        X: Feature matrix
        method: 'standardize' (zero mean, unit variance) or 'minmax' (0-1 range)

    Returns:
        Tuple of (normalized_X, normalization_params)
    """
    params = {}

    if method == 'standardize':
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0)
        std[std == 0] = 1  # Avoid division by zero
        X_norm = (X - mean) / std
        params = {'mean': mean, 'std': std}

    elif method == 'minmax':
        min_val = np.min(X, axis=0)
        max_val = np.max(X, axis=0)
        range_val = max_val - min_val
        range_val[range_val == 0] = 1
        X_norm = (X - min_val) / range_val
        params = {'min': min_val, 'max': max_val}

    else:
        raise ValueError(f"Unknown normalization method: {method}")

    return X_norm, params


# ============================================================================
# DATA SPLITTING
# ============================================================================

def split_train_test(
    X: np.ndarray,
    y: np.ndarray = None,
    test_ratio: float = 0.2,
    random_seed: int = 42
) -> Tuple:
    """
    Split data into train and test sets.

    Args:
        X: Feature matrix
        y: Labels (optional)
        test_ratio: Fraction of data for testing
        random_seed: Random seed

    Returns:
        Tuple of (X_train, X_test, y_train, y_test) if y provided,
        otherwise (X_train, X_test)
    """
    np.random.seed(random_seed)

    n_samples = len(X)
    indices = np.random.permutation(n_samples)
    n_test = int(n_samples * test_ratio)

    test_indices = indices[:n_test]
    train_indices = indices[n_test:]

    X_train = X[train_indices]
    X_test = X[test_indices]

    if y is not None:
        y_train = y[train_indices]
        y_test = y[test_indices]
        return X_train, X_test, y_train, y_test

    return X_train, X_test


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract features from packet logs")
    parser.add_argument("packet_log", help="Path to packet log CSV")
    parser.add_argument("--output", "-o", help="Output CSV file")
    parser.add_argument("--window", type=float, default=5.0,
                        help="Time window size (seconds)")
    parser.add_argument("--inject-anomalies", action="store_true",
                        help="Inject synthetic anomalies")

    args = parser.parse_args()

    # Load packet log
    logger.info(f"Loading packet log from {args.packet_log}")
    packet_log = pd.read_csv(args.packet_log)

    # Extract features
    features_df = extract_all_features(packet_log, window_size=args.window)

    if features_df.empty:
        logger.error("No features extracted")
        sys.exit(1)

    print(f"\nExtracted {len(features_df)} feature vectors")
    print(f"\nFeature summary:")
    print(features_df.describe())

    # Optionally inject anomalies
    if args.inject_anomalies:
        features_df, labels = inject_broadcast_storm_anomaly(features_df)
        features_df['anomaly_label'] = labels

    # Save output
    if args.output:
        features_df.to_csv(args.output, index=False)
        logger.info(f"Saved features to {args.output}")
