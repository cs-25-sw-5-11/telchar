#!/usr/bin/env python3
"""
Calculate edge speeds from traversal times and edge lengths.
Speed = (edge_length_meters / traversal_time_seconds) * 3.6 km/h
"""

import csv
import sys

def load_edge_lengths(edge_connections_path, vertex_path):
    """Load edge lengths by calculating distance between vertices."""
    from math import radians, sin, cos, sqrt, atan2

    def haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two lat/lon points."""
        R = 6371000  # Earth radius in meters

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    # Load vertices
    vertices = {}
    with open(vertex_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            node_id = int(row['node_id'])
            vertices[node_id] = (float(row['latitude']), float(row['longitude']))

    # Calculate edge lengths
    edge_lengths = []
    skipped = 0
    with open(edge_connections_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip incomplete rows
            if not row['vertex_start_id'] or not row['vertex_end_id']:
                continue

            start_id = int(row['vertex_start_id'])
            end_id = int(row['vertex_end_id'])

            # Check if vertices exist
            if start_id not in vertices or end_id not in vertices:
                edge_lengths.append(0)  # Mark as invalid
                skipped += 1
                continue

            lat1, lon1 = vertices[start_id]
            lat2, lon2 = vertices[end_id]

            length = haversine(lat1, lon1, lat2, lon2)
            edge_lengths.append(length)

    if skipped > 0:
        print(f"  ⚠ Skipped {skipped} edges with missing vertices")

    return edge_lengths

def calculate_speeds(time_csv_path, edge_connections_path, vertex_path, output_path):
    """Calculate speeds from traversal times and edge lengths."""

    print("Loading edge lengths from vertex.csv and edge_connections.csv...")
    edge_lengths = load_edge_lengths(edge_connections_path, vertex_path)
    num_edges = len(edge_lengths)
    print(f"  ✓ Loaded {num_edges} edge lengths")

    print(f"Reading traversal times from {time_csv_path}...")
    with open(time_csv_path, 'r') as f_in, open(output_path, 'w') as f_out:
        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        # Read and transform header
        header = next(reader)
        speed_header = ['timestamp'] + [col.replace('_traversal_time_seconds', '_speed_kmh') for col in header[1:]]
        writer.writerow(speed_header)

        # Process each time bin
        row_count = 0
        for row in reader:
            timestamp = row[0]
            speed_row = [timestamp]

            for edge_id in range(num_edges):
                col_idx = edge_id + 1
                if col_idx >= len(row):
                    speed_row.append('-1')
                    continue

                time_str = row[col_idx]

                # Check if we have valid time data
                if time_str == '-1' or not time_str:
                    speed_row.append('-1')
                    continue

                try:
                    time_seconds = float(time_str)
                    edge_length_m = edge_lengths[edge_id]

                    # Calculate speed: (meters / seconds) * 3.6 = km/h
                    # Note: time_str already has speed validation applied (0-150 km/h filter)
                    # in the Zig code, so all times should produce realistic speeds
                    if time_seconds > 0 and edge_length_m > 0:
                        speed_kmh = (edge_length_m / time_seconds) * 3.6
                        speed_row.append(f'{speed_kmh:.1f}')
                    else:
                        speed_row.append('-1')
                except (ValueError, IndexError):
                    speed_row.append('-1')

            writer.writerow(speed_row)
            row_count += 1

        print(f"  ✓ Processed {row_count} time bins")

    print(f"✓ Wrote speeds to {output_path}")

if __name__ == '__main__':
    # Paths
    output_dir = 'output'
    time_csv = f'{output_dir}/edge_data.csv'
    edge_connections = f'{output_dir}/edge_connections.csv'
    vertex_csv = f'{output_dir}/vertex.csv'
    speed_output = f'{output_dir}/edge_data_speed.csv'

    print("=== Calculate Edge Speeds ===")
    print("Speed = (edge_length / traversal_time) * 3.6 km/h\n")

    calculate_speeds(time_csv, edge_connections, vertex_csv, speed_output)
    print("\nDone!")
