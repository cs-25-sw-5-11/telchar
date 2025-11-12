#!/usr/bin/env python3
"""
Network visualization tool for Telchar GPS map-matching results.

Displays the road network with edges colored by traversal time.
Uses a time slider to navigate through different times of day.
"""

import os
import sys

# Set matplotlib backend for Wayland (Hyprland) before importing pyplot
import matplotlib
matplotlib.use('Qt5Agg')  # Qt backend for Wayland compatibility

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.collections import LineCollection
import numpy as np

def load_network_data(output_dir):
    """Load vertex, edge, and traversal time data from CSV files."""
    print(f"Loading network data from {output_dir}...")

    # Load vertices
    vertex_path = os.path.join(output_dir, "vertex.csv")
    vertices = pd.read_csv(vertex_path)
    print(f"  ✓ Loaded {len(vertices)} vertices")

    # Load edge connections
    edge_path = os.path.join(output_dir, "edge_connections.csv")
    edges = pd.read_csv(edge_path)
    print(f"  ✓ Loaded {len(edges)} edges")

    # Load edge data (traversal times by time bin)
    data_path = os.path.join(output_dir, "edge_data.csv")
    edge_data = pd.read_csv(data_path)
    print(f"  ✓ Loaded traversal data for {len(edge_data)} time bins")

    return vertices, edges, edge_data

def get_edge_colors(edges, edge_data, time_index, cmap, norm):
    """
    Get colors for each edge based on traversal time at given time index.

    Returns array of RGBA colors, one per edge.
    Grey (0.7, 0.7, 0.7, 1.0) for missing data (-1).
    Color mapped from green (fast) to red (slow) for valid data.
    """
    colors = []

    for edge_id in range(len(edges)):
        col_name = f"edge{edge_id}_traversal_time_seconds"

        if col_name in edge_data.columns:
            value = edge_data.iloc[time_index][col_name]

            if value < 0:  # Missing data
                colors.append((0.7, 0.7, 0.7, 1.0))
            else:
                # Map to colormap (green = fast, red = slow)
                colors.append(cmap(norm(value)))
        else:
            # Edge not in data
            colors.append((0.7, 0.7, 0.7, 1.0))

    return colors

def create_edge_segments(vertices, edges):
    """Create line segments for all edges."""
    segments = []
    skipped = 0

    for _, edge in edges.iterrows():
        # Skip rows with NaN values
        if pd.isna(edge['vertex_start_id']) or pd.isna(edge['vertex_end_id']):
            skipped += 1
            continue

        start_idx = int(edge['vertex_start_id'])
        end_idx = int(edge['vertex_end_id'])

        # Skip edges with out-of-bounds indices
        if start_idx >= len(vertices) or end_idx >= len(vertices):
            skipped += 1
            continue

        start_vertex = vertices.iloc[start_idx]
        end_vertex = vertices.iloc[end_idx]

        segment = [
            (start_vertex['longitude'], start_vertex['latitude']),
            (end_vertex['longitude'], end_vertex['latitude'])
        ]
        segments.append(segment)

    if skipped > 0:
        print(f"  ! Skipped {skipped} edges with invalid vertex references")

    return segments

def visualize_network(output_dir):
    """Create interactive visualization with time slider."""

    # Load data
    vertices, edges, edge_data = load_network_data(output_dir)

    # Create edge segments
    segments = create_edge_segments(vertices, edges)

    # Calculate reasonable color scale (excluding -1 values)
    all_values = []
    for col in edge_data.columns:
        if col.startswith('edge') and col.endswith('_traversal_time_seconds'):
            values = edge_data[col].values
            valid_values = values[values >= 0]
            all_values.extend(valid_values)

    if len(all_values) == 0:
        print("Warning: No valid traversal time data found!")
        vmin, vmax = 0, 60
    else:
        # Use percentiles to avoid outliers
        vmin = np.percentile(all_values, 5)
        vmax = np.percentile(all_values, 95)
        print(f"\n  Color scale: {vmin:.1f}s (green) to {vmax:.1f}s (red)")

    # Create colormap (green = fast, red = slow)
    cmap = plt.cm.RdYlGn_r  # Reversed so green is low, red is high
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 10))
    plt.subplots_adjust(bottom=0.15)

    # Initial time index
    initial_time = 0

    # Create line collection
    lc = LineCollection(segments, linewidths=1.5, alpha=0.8)
    initial_colors = get_edge_colors(edges, edge_data, initial_time, cmap, norm)
    lc.set_colors(initial_colors)

    ax.add_collection(lc)

    # Set plot limits
    lon_min, lon_max = vertices['longitude'].min(), vertices['longitude'].max()
    lat_min, lat_max = vertices['latitude'].min(), vertices['latitude'].max()

    lon_margin = (lon_max - lon_min) * 0.05
    lat_margin = (lat_max - lat_min) * 0.05

    ax.set_xlim(lon_min - lon_margin, lon_max + lon_margin)
    ax.set_ylim(lat_min - lat_margin, lat_max + lat_margin)
    ax.set_aspect('equal')

    # Labels
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')

    # Initial title
    timestamp = edge_data.iloc[initial_time]['timestamp']
    ax.set_title(f'Road Network Traversal Times - Time: {timestamp}', fontsize=14, fontweight='bold')

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation='vertical', pad=0.02)
    cbar.set_label('Traversal Time (seconds)', rotation=270, labelpad=20)

    # Create slider
    ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
    slider = Slider(
        ax_slider,
        'Time',
        0,
        len(edge_data) - 1,
        valinit=initial_time,
        valstep=1
    )

    # Update function
    def update(val):
        time_index = int(slider.val)

        # Update colors
        colors = get_edge_colors(edges, edge_data, time_index, cmap, norm)
        lc.set_colors(colors)

        # Update title
        timestamp = edge_data.iloc[time_index]['timestamp']
        ax.set_title(f'Road Network Traversal Times - Time: {timestamp}', fontsize=14, fontweight='bold')

        fig.canvas.draw_idle()

    slider.on_changed(update)

    # Add statistics text
    num_edges_with_data = sum(1 for col in edge_data.columns
                               if col.startswith('edge') and
                               edge_data[col].max() >= 0)

    stats_text = f"Network: {len(vertices)} vertices, {len(edges)} edges\n"
    stats_text += f"Time bins: {len(edge_data)} (5-minute intervals)\n"
    stats_text += f"Edges with data: {num_edges_with_data}/{len(edges)}\n"
    stats_text += f"Grey = no data, Green = fast, Red = slow"

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    print(f"\n✓ Visualization ready!")
    print(f"  Use the slider to navigate through {len(edge_data)} time bins")
    print(f"  Green = fast travel, Red = slow travel, Grey = no data")
    print(f"\nOpening visualization window...")
    print(f"Backend: {matplotlib.get_backend()}")

    # Force the window to appear and block
    plt.show(block=True)

def main():
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "../output"

    if not os.path.exists(output_dir):
        print(f"Error: Output directory '{output_dir}' not found!")
        print(f"Usage: {sys.argv[0]} [output_dir]")
        print(f"Default: {sys.argv[0]} ../output")
        sys.exit(1)

    print("=== Telchar Network Visualization ===\n")
    visualize_network(output_dir)

if __name__ == "__main__":
    main()
