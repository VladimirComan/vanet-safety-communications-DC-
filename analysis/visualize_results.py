#!/usr/bin/env python3
"""
visualize_results.py
====================

Visualization module for VANET simulation results.
Creates publication-quality plots for analysis and presentation.

This module generates:
- Delay vs distance plots
- PDR vs vehicle density plots
- CDF of event-alert latency
- AODV vs OLSR comparative plots
- Jitter analysis plots
- Throughput comparison plots

Author: VANET Project Team
Course: Data Communications and Computer Networks
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import argparse
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Patch
import seaborn as sns

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from parse_results import (
    ExperimentResults, load_experiment, load_experiment_matrix,
    create_combined_dataframe, aggregate_by_parameter,
    calculate_distance_based_metrics
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# PLOT CONFIGURATION
# ============================================================================

# Set publication-quality defaults
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'legend.fontsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.figsize': (8, 6),
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'lines.linewidth': 2,
    'lines.markersize': 8,
})

# Color palette for routing protocols
PROTOCOL_COLORS = {
    'AODV': '#1f77b4',  # Blue
    'OLSR': '#ff7f0e',  # Orange
}

# Marker styles
PROTOCOL_MARKERS = {
    'AODV': 'o',
    'OLSR': 's',
}

# Line styles
PROTOCOL_LINESTYLES = {
    'AODV': '-',
    'OLSR': '--',
}


# ============================================================================
# DELAY ANALYSIS PLOTS
# ============================================================================

def plot_delay_vs_density(
    df: pd.DataFrame,
    output_path: str,
    title: str = "End-to-End Delay vs Vehicle Density"
):
    """
    Plot mean delay vs vehicle density for different routing protocols.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]

        # Group by vehicle count and calculate statistics
        grouped = proto_data.groupby('vehicles').agg({
            'delay_mean': ['mean', 'std'],
            'delay_p95': ['mean', 'std']
        }).reset_index()

        grouped.columns = ['vehicles', 'delay_mean', 'delay_std',
                           'delay_p95_mean', 'delay_p95_std']

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        marker = PROTOCOL_MARKERS.get(protocol, 'x')
        linestyle = PROTOCOL_LINESTYLES.get(protocol, '-')

        # Plot mean delay with error bars
        ax.errorbar(
            grouped['vehicles'], grouped['delay_mean'],
            yerr=grouped['delay_std'],
            label=f'{protocol} (Mean)',
            color=color, marker=marker, linestyle=linestyle,
            capsize=4, capthick=1.5
        )

        # Plot p95 delay
        ax.errorbar(
            grouped['vehicles'], grouped['delay_p95_mean'],
            yerr=grouped['delay_p95_std'],
            label=f'{protocol} (P95)',
            color=color, marker=marker, linestyle=':',
            capsize=4, capthick=1.5, alpha=0.7
        )

    ax.set_xlabel('Number of Vehicles')
    ax.set_ylabel('Delay (ms)')
    ax.set_title(title)
    ax.legend(loc='upper left')
    ax.set_xticks(sorted(df['vehicles'].unique()))

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


def plot_delay_vs_distance(
    experiments: List[ExperimentResults],
    output_path: str,
    distance_bins: List[Tuple[float, float]] = None,
    title: str = "Delay vs Communication Distance"
):
    """
    Plot delay metrics binned by distance between sender and receiver.

    Args:
        experiments: List of experiment results
        output_path: Path to save figure
        distance_bins: List of (min, max) distance tuples
        title: Plot title
    """
    if distance_bins is None:
        distance_bins = [(0, 100), (100, 200), (200, 300)]

    fig, ax = plt.subplots(figsize=(10, 6))

    # Aggregate distance-based metrics by routing protocol
    protocol_metrics = {}

    for exp in experiments:
        protocol = exp.routing_protocol
        if protocol not in protocol_metrics:
            protocol_metrics[protocol] = []

        if exp.packet_log is not None and exp.mobility_log is not None:
            metrics = calculate_distance_based_metrics(
                exp.packet_log, exp.mobility_log, distance_bins
            )
            if not metrics.empty:
                metrics['protocol'] = protocol
                protocol_metrics[protocol].append(metrics)

    # Plot for each protocol
    bar_width = 0.35
    num_protocols = len(protocol_metrics)
    x_positions = np.arange(len(distance_bins))

    for i, (protocol, metrics_list) in enumerate(protocol_metrics.items()):
        if not metrics_list:
            continue

        # Combine metrics from all experiments
        combined = pd.concat(metrics_list, ignore_index=True)

        # Aggregate by distance bin
        aggregated = combined.groupby('distance_label').agg({
            'delay_mean_ms': ['mean', 'std'],
            'delay_p95_ms': ['mean', 'std'],
            'packet_count': 'sum'
        }).reset_index()

        aggregated.columns = ['distance', 'delay_mean', 'delay_std',
                              'p95_mean', 'p95_std', 'count']

        # Ensure proper ordering
        distance_order = [f"{b[0]}-{b[1]}m" if b[1] < float('inf')
                         else f">{b[0]}m" for b in distance_bins]

        aggregated['order'] = aggregated['distance'].apply(
            lambda x: distance_order.index(x) if x in distance_order else 999
        )
        aggregated = aggregated.sort_values('order')

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        offset = (i - num_protocols/2 + 0.5) * bar_width

        bars = ax.bar(
            x_positions + offset,
            aggregated['delay_mean'],
            bar_width,
            yerr=aggregated['delay_std'],
            label=protocol,
            color=color,
            capsize=4,
            alpha=0.8
        )

    ax.set_xlabel('Distance (m)')
    ax.set_ylabel('Mean Delay (ms)')
    ax.set_title(title)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([f"{b[0]}-{b[1]}" if b[1] < float('inf')
                        else f">{b[0]}" for b in distance_bins])
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


def plot_delay_cdf(
    experiments: List[ExperimentResults],
    output_path: str,
    max_delay_ms: float = 100.0,
    title: str = "CDF of End-to-End Delay"
):
    """
    Plot Cumulative Distribution Function of delay.

    Args:
        experiments: List of experiment results
        output_path: Path to save figure
        max_delay_ms: Maximum delay to show on x-axis
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for protocol in ['AODV', 'OLSR']:
        # Collect all delays for this protocol
        all_delays = []
        for exp in experiments:
            if exp.routing_protocol == protocol and exp.delays:
                all_delays.extend(exp.delays)

        if not all_delays:
            continue

        all_delays = np.array(all_delays)
        all_delays = all_delays[all_delays <= max_delay_ms]  # Filter outliers

        # Sort and calculate CDF
        sorted_delays = np.sort(all_delays)
        cdf = np.arange(1, len(sorted_delays) + 1) / len(sorted_delays)

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        linestyle = PROTOCOL_LINESTYLES.get(protocol, '-')

        ax.plot(sorted_delays, cdf, label=protocol,
                color=color, linestyle=linestyle, linewidth=2)

        # Mark percentiles
        p50 = np.percentile(all_delays, 50)
        p95 = np.percentile(all_delays, 95)
        p99 = np.percentile(all_delays, 99)

        ax.axhline(y=0.50, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=0.95, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=0.99, color='gray', linestyle=':', alpha=0.5)

    ax.set_xlabel('Delay (ms)')
    ax.set_ylabel('CDF')
    ax.set_title(title)
    ax.legend(loc='lower right')
    ax.set_xlim(0, max_delay_ms)
    ax.set_ylim(0, 1.05)

    # Add percentile labels
    ax.text(max_delay_ms * 0.98, 0.50, 'P50', va='center', ha='right', fontsize=9)
    ax.text(max_delay_ms * 0.98, 0.95, 'P95', va='center', ha='right', fontsize=9)
    ax.text(max_delay_ms * 0.98, 0.99, 'P99', va='center', ha='right', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


def plot_alert_delay_cdf(
    experiments: List[ExperimentResults],
    output_path: str,
    title: str = "CDF of Event Alert Delay"
):
    """
    Plot CDF specifically for event alerts (emergency messages).

    Args:
        experiments: List of experiment results
        output_path: Path to save figure
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    max_delay = 0

    for protocol in ['AODV', 'OLSR']:
        # Collect alert delays
        all_alert_delays = []
        for exp in experiments:
            if exp.routing_protocol != protocol:
                continue
            if exp.packet_log is None or exp.packet_log.empty:
                continue

            alerts = exp.packet_log[
                (exp.packet_log['direction'] == 'RX') &
                (exp.packet_log['type'] == 'ALERT')
            ]

            if 'delayMs' in alerts.columns:
                delays = alerts['delayMs'].dropna().values
                all_alert_delays.extend(delays)

        if not all_alert_delays:
            continue

        all_alert_delays = np.array(all_alert_delays)
        max_delay = max(max_delay, np.percentile(all_alert_delays, 99))

        sorted_delays = np.sort(all_alert_delays)
        cdf = np.arange(1, len(sorted_delays) + 1) / len(sorted_delays)

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        linestyle = PROTOCOL_LINESTYLES.get(protocol, '-')

        ax.plot(sorted_delays, cdf, label=protocol,
                color=color, linestyle=linestyle, linewidth=2)

    # Add safety threshold line (e.g., 100ms for safety-critical)
    ax.axvline(x=100, color='red', linestyle='--', alpha=0.7, label='100ms threshold')

    ax.set_xlabel('Alert Delay (ms)')
    ax.set_ylabel('CDF')
    ax.set_title(title)
    ax.legend(loc='lower right')
    ax.set_xlim(0, min(max_delay * 1.1, 200))
    ax.set_ylim(0, 1.05)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


# ============================================================================
# PDR ANALYSIS PLOTS
# ============================================================================

def plot_pdr_vs_density(
    df: pd.DataFrame,
    output_path: str,
    title: str = "Packet Delivery Ratio vs Vehicle Density"
):
    """
    Plot PDR vs vehicle density comparison.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]

        grouped = proto_data.groupby('vehicles').agg({
            'pdr': ['mean', 'std', 'min', 'max']
        }).reset_index()

        grouped.columns = ['vehicles', 'pdr_mean', 'pdr_std', 'pdr_min', 'pdr_max']

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        marker = PROTOCOL_MARKERS.get(protocol, 'x')
        linestyle = PROTOCOL_LINESTYLES.get(protocol, '-')

        ax.errorbar(
            grouped['vehicles'], grouped['pdr_mean'],
            yerr=grouped['pdr_std'],
            label=protocol,
            color=color, marker=marker, linestyle=linestyle,
            capsize=4, capthick=1.5
        )

        # Add shaded region for min/max
        ax.fill_between(
            grouped['vehicles'],
            grouped['pdr_min'],
            grouped['pdr_max'],
            color=color, alpha=0.1
        )

    ax.set_xlabel('Number of Vehicles')
    ax.set_ylabel('Packet Delivery Ratio (%)')
    ax.set_title(title)
    ax.legend()
    ax.set_xticks(sorted(df['vehicles'].unique()))
    ax.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


def plot_pdr_vs_speed(
    df: pd.DataFrame,
    output_path: str,
    title: str = "PDR vs Vehicle Speed"
):
    """
    Plot PDR vs vehicle speed.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]

        grouped = proto_data.groupby('speed_kmh').agg({
            'pdr': ['mean', 'std']
        }).reset_index()

        grouped.columns = ['speed', 'pdr_mean', 'pdr_std']

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        marker = PROTOCOL_MARKERS.get(protocol, 'x')
        linestyle = PROTOCOL_LINESTYLES.get(protocol, '-')

        ax.errorbar(
            grouped['speed'], grouped['pdr_mean'],
            yerr=grouped['pdr_std'],
            label=protocol,
            color=color, marker=marker, linestyle=linestyle,
            capsize=4, capthick=1.5, markersize=10
        )

    ax.set_xlabel('Vehicle Speed (km/h)')
    ax.set_ylabel('Packet Delivery Ratio (%)')
    ax.set_title(title)
    ax.legend()
    ax.set_xticks(sorted(df['speed_kmh'].unique()))
    ax.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


# ============================================================================
# COMPARATIVE ANALYSIS PLOTS
# ============================================================================

def plot_protocol_comparison_boxplot(
    df: pd.DataFrame,
    output_path: str,
    metric: str = 'delay_mean',
    ylabel: str = 'Delay (ms)',
    title: str = "Protocol Comparison"
):
    """
    Create boxplot comparison between protocols.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        metric: Column name for the metric to compare
        ylabel: Y-axis label
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    protocols = sorted(df['routing'].unique())
    vehicle_counts = sorted(df['vehicles'].unique())

    # Create grouped boxplot
    positions = []
    data = []
    labels = []
    colors = []

    group_width = 0.8
    num_protocols = len(protocols)
    box_width = group_width / num_protocols

    for i, vehicles in enumerate(vehicle_counts):
        for j, protocol in enumerate(protocols):
            subset = df[(df['vehicles'] == vehicles) & (df['routing'] == protocol)]
            if not subset.empty:
                pos = i + (j - num_protocols/2 + 0.5) * box_width
                positions.append(pos)
                data.append(subset[metric].values)
                labels.append(f"{protocol}")
                colors.append(PROTOCOL_COLORS.get(protocol, 'gray'))

    bp = ax.boxplot(data, positions=positions, widths=box_width*0.8,
                    patch_artist=True)

    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xticks(range(len(vehicle_counts)))
    ax.set_xticklabels([str(v) for v in vehicle_counts])
    ax.set_xlabel('Number of Vehicles')
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    # Legend
    legend_patches = [Patch(facecolor=PROTOCOL_COLORS[p], label=p, alpha=0.7)
                      for p in protocols if p in PROTOCOL_COLORS]
    ax.legend(handles=legend_patches, loc='upper left')

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


def plot_heatmap_metrics(
    df: pd.DataFrame,
    output_path: str,
    metric: str = 'pdr',
    title: str = "PDR Heatmap"
):
    """
    Create heatmap of metrics across vehicles and speed.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        metric: Column name for the metric
        title: Plot title
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    protocols = ['AODV', 'OLSR']

    for ax, protocol in zip(axes, protocols):
        proto_data = df[df['routing'] == protocol]

        # Pivot table
        pivot = proto_data.pivot_table(
            values=metric,
            index='vehicles',
            columns='speed_kmh',
            aggfunc='mean'
        )

        sns.heatmap(
            pivot, ax=ax, annot=True, fmt='.1f',
            cmap='RdYlGn' if metric == 'pdr' else 'RdYlGn_r',
            vmin=pivot.values.min() * 0.9,
            vmax=pivot.values.max() * 1.1 if metric != 'pdr' else 100,
            cbar_kws={'label': metric.replace('_', ' ').title()}
        )

        ax.set_xlabel('Speed (km/h)')
        ax.set_ylabel('Number of Vehicles')
        ax.set_title(f'{protocol}')

    fig.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


# ============================================================================
# THROUGHPUT AND JITTER PLOTS
# ============================================================================

def plot_throughput_comparison(
    df: pd.DataFrame,
    output_path: str,
    title: str = "Throughput Comparison"
):
    """
    Plot throughput comparison.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        title: Plot title
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    bar_width = 0.35
    vehicle_counts = sorted(df['vehicles'].unique())
    x_pos = np.arange(len(vehicle_counts))

    for i, protocol in enumerate(['AODV', 'OLSR']):
        proto_data = df[df['routing'] == protocol]
        grouped = proto_data.groupby('vehicles')['throughput'].agg(['mean', 'std']).reset_index()

        color = PROTOCOL_COLORS.get(protocol, 'gray')

        ax.bar(
            x_pos + i * bar_width - bar_width/2,
            grouped['mean'],
            bar_width,
            yerr=grouped['std'],
            label=protocol,
            color=color,
            capsize=4,
            alpha=0.8
        )

    ax.set_xlabel('Number of Vehicles')
    ax.set_ylabel('Throughput (kbps)')
    ax.set_title(title)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(vehicle_counts)
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


def plot_jitter_analysis(
    df: pd.DataFrame,
    output_path: str,
    title: str = "Jitter Analysis"
):
    """
    Plot jitter comparison.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        title: Plot title
    """
    # Check if jitter data exists
    if 'jitter' not in df.columns or df['jitter'].isna().all():
        logger.warning("No jitter data available")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]

        grouped = proto_data.groupby('vehicles')['jitter'].agg(['mean', 'std']).reset_index()

        color = PROTOCOL_COLORS.get(protocol, 'gray')
        marker = PROTOCOL_MARKERS.get(protocol, 'x')
        linestyle = PROTOCOL_LINESTYLES.get(protocol, '-')

        ax.errorbar(
            grouped['vehicles'], grouped['mean'],
            yerr=grouped['std'],
            label=protocol,
            color=color, marker=marker, linestyle=linestyle,
            capsize=4, capthick=1.5
        )

    ax.set_xlabel('Number of Vehicles')
    ax.set_ylabel('Jitter (ms)')
    ax.set_title(title)
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


# ============================================================================
# SUMMARY DASHBOARD
# ============================================================================

def create_summary_dashboard(
    df: pd.DataFrame,
    output_path: str,
    title: str = "VANET Simulation Results Summary"
):
    """
    Create a comprehensive summary dashboard with multiple subplots.

    Args:
        df: DataFrame with experiment results
        output_path: Path to save figure
        title: Dashboard title
    """
    fig = plt.figure(figsize=(16, 12))

    # Grid spec for layout
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 1. PDR vs Density (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]
        grouped = proto_data.groupby('vehicles')['pdr'].mean().reset_index()
        ax1.plot(grouped['vehicles'], grouped['pdr'],
                 label=protocol, color=PROTOCOL_COLORS.get(protocol, 'gray'),
                 marker=PROTOCOL_MARKERS.get(protocol, 'o'))
    ax1.set_xlabel('Vehicles')
    ax1.set_ylabel('PDR (%)')
    ax1.set_title('PDR vs Density')
    ax1.legend()

    # 2. Delay vs Density (top center)
    ax2 = fig.add_subplot(gs[0, 1])
    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]
        grouped = proto_data.groupby('vehicles')['delay_mean'].mean().reset_index()
        ax2.plot(grouped['vehicles'], grouped['delay_mean'],
                 label=protocol, color=PROTOCOL_COLORS.get(protocol, 'gray'),
                 marker=PROTOCOL_MARKERS.get(protocol, 'o'))
    ax2.set_xlabel('Vehicles')
    ax2.set_ylabel('Delay (ms)')
    ax2.set_title('Mean Delay vs Density')
    ax2.legend()

    # 3. P95 Delay (top right)
    ax3 = fig.add_subplot(gs[0, 2])
    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]
        grouped = proto_data.groupby('vehicles')['delay_p95'].mean().reset_index()
        ax3.plot(grouped['vehicles'], grouped['delay_p95'],
                 label=protocol, color=PROTOCOL_COLORS.get(protocol, 'gray'),
                 marker=PROTOCOL_MARKERS.get(protocol, 'o'))
    ax3.set_xlabel('Vehicles')
    ax3.set_ylabel('P95 Delay (ms)')
    ax3.set_title('P95 Delay vs Density')
    ax3.legend()

    # 4. Protocol comparison boxplot (middle left)
    ax4 = fig.add_subplot(gs[1, 0])
    df.boxplot(column='pdr', by='routing', ax=ax4)
    ax4.set_xlabel('Protocol')
    ax4.set_ylabel('PDR (%)')
    ax4.set_title('PDR Distribution')
    plt.suptitle('')  # Remove auto-generated title

    # 5. Throughput (middle center)
    ax5 = fig.add_subplot(gs[1, 1])
    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]
        grouped = proto_data.groupby('vehicles')['throughput'].mean().reset_index()
        ax5.bar(grouped['vehicles'] + (list(df['routing'].unique()).index(protocol) - 0.5) * 5,
                grouped['throughput'], width=4,
                label=protocol, color=PROTOCOL_COLORS.get(protocol, 'gray'), alpha=0.7)
    ax5.set_xlabel('Vehicles')
    ax5.set_ylabel('Throughput (kbps)')
    ax5.set_title('Throughput')
    ax5.legend()

    # 6. Speed effect (middle right)
    ax6 = fig.add_subplot(gs[1, 2])
    for protocol in df['routing'].unique():
        proto_data = df[df['routing'] == protocol]
        grouped = proto_data.groupby('speed_kmh')['pdr'].mean().reset_index()
        ax6.plot(grouped['speed_kmh'], grouped['pdr'],
                 label=protocol, color=PROTOCOL_COLORS.get(protocol, 'gray'),
                 marker=PROTOCOL_MARKERS.get(protocol, 'o'), markersize=10)
    ax6.set_xlabel('Speed (km/h)')
    ax6.set_ylabel('PDR (%)')
    ax6.set_title('PDR vs Speed')
    ax6.legend()

    # 7. Summary statistics table (bottom, spanning)
    ax7 = fig.add_subplot(gs[2, :])
    ax7.axis('off')

    # Create summary table
    summary_data = []
    for protocol in ['AODV', 'OLSR']:
        proto_data = df[df['routing'] == protocol]
        if proto_data.empty:
            continue
        summary_data.append({
            'Protocol': protocol,
            'Mean PDR (%)': f"{proto_data['pdr'].mean():.1f} ± {proto_data['pdr'].std():.1f}",
            'Mean Delay (ms)': f"{proto_data['delay_mean'].mean():.2f} ± {proto_data['delay_mean'].std():.2f}",
            'P95 Delay (ms)': f"{proto_data['delay_p95'].mean():.2f}",
            'Throughput (kbps)': f"{proto_data['throughput'].mean():.1f}",
            'Experiments': len(proto_data)
        })

    summary_df = pd.DataFrame(summary_data)

    if not summary_df.empty:
        table = ax7.table(
            cellText=summary_df.values,
            colLabels=summary_df.columns,
            loc='center',
            cellLoc='center',
            colColours=['lightblue'] * len(summary_df.columns)
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)

    fig.suptitle(title, fontsize=16, y=0.98)

    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved: {output_path}")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def generate_all_plots(
    experiments: List[ExperimentResults],
    output_dir: str,
    prefix: str = "vanet"
):
    """
    Generate all visualization plots from experiment results.

    Args:
        experiments: List of ExperimentResults
        output_dir: Output directory for plots
        prefix: Filename prefix
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create combined DataFrame
    df = create_combined_dataframe(experiments)

    if df.empty:
        logger.error("No data to visualize")
        return

    logger.info(f"Generating plots for {len(experiments)} experiments")
    logger.info(f"Output directory: {output_dir}")

    # Generate individual plots
    plot_delay_vs_density(
        df, str(output_dir / f"{prefix}_delay_vs_density.png"),
        "End-to-End Delay vs Vehicle Density"
    )

    plot_pdr_vs_density(
        df, str(output_dir / f"{prefix}_pdr_vs_density.png"),
        "Packet Delivery Ratio vs Vehicle Density"
    )

    plot_pdr_vs_speed(
        df, str(output_dir / f"{prefix}_pdr_vs_speed.png"),
        "PDR vs Vehicle Speed"
    )

    plot_delay_cdf(
        experiments, str(output_dir / f"{prefix}_delay_cdf.png"),
        max_delay_ms=100, title="CDF of End-to-End Delay"
    )

    plot_alert_delay_cdf(
        experiments, str(output_dir / f"{prefix}_alert_delay_cdf.png"),
        "CDF of Event Alert Delay"
    )

    plot_protocol_comparison_boxplot(
        df, str(output_dir / f"{prefix}_delay_boxplot.png"),
        metric='delay_mean', ylabel='Mean Delay (ms)',
        title="Delay Distribution by Protocol"
    )

    plot_throughput_comparison(
        df, str(output_dir / f"{prefix}_throughput.png"),
        "Throughput Comparison"
    )

    plot_heatmap_metrics(
        df, str(output_dir / f"{prefix}_pdr_heatmap.png"),
        metric='pdr', title="PDR Heatmap by Vehicles and Speed"
    )

    plot_heatmap_metrics(
        df, str(output_dir / f"{prefix}_delay_heatmap.png"),
        metric='delay_mean', title="Delay Heatmap by Vehicles and Speed"
    )

    # Generate summary dashboard
    create_summary_dashboard(
        df, str(output_dir / f"{prefix}_dashboard.png"),
        "VANET Simulation Results Summary"
    )

    # Try distance-based plot if mobility data available
    plot_delay_vs_distance(
        experiments, str(output_dir / f"{prefix}_delay_vs_distance.png"),
        title="Delay vs Communication Distance"
    )

    logger.info("All plots generated successfully")

    # Save aggregated data to CSV
    df.to_csv(output_dir / f"{prefix}_combined_data.csv", index=False)

    agg_protocol = aggregate_by_parameter(experiments, 'routing_protocol')
    agg_protocol.to_csv(output_dir / f"{prefix}_agg_by_protocol.csv", index=False)

    agg_vehicles = aggregate_by_parameter(experiments, 'num_vehicles')
    agg_vehicles.to_csv(output_dir / f"{prefix}_agg_by_vehicles.csv", index=False)

    logger.info("Aggregated data saved to CSV files")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate visualization plots from VANET simulation results"
    )
    parser.add_argument(
        "input_dir",
        help="Path to experiment matrix directory"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for plots (default: input_dir/plots)"
    )
    parser.add_argument(
        "--prefix", "-p",
        default="vanet",
        help="Filename prefix for output files"
    )

    args = parser.parse_args()

    # Load experiments
    experiments = load_experiment_matrix(args.input_dir)

    if not experiments:
        logger.error("No experiments found")
        sys.exit(1)

    # Determine output directory
    output_dir = args.output or str(Path(args.input_dir) / "plots")

    # Generate all plots
    generate_all_plots(experiments, output_dir, args.prefix)

    print(f"\nPlots saved to: {output_dir}")
