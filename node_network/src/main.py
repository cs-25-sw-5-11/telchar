from classes import Network, Edge, Vertex, Trip
from graph_building.build_graph import build_graph
from graph_building.filter_out_subnetworks import remove_small_subnetworks
from extract_osm_map.extract_osm_map import extract_map
from data_cleaning.clean_trips import clean_trips
from utils.functions_misc import writeout_traversals_to_json
from viterbi.viterbi import viterbi_algorithm

import logging
import pandas as pd
import json
import os
from tqdm import tqdm
from datetime import datetime

logging.basicConfig(
    level=logging.WARNING,  # Set to DEBUG to see debug statements
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)

# Suppress matplotlib font manager debug messages
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

COMPARE_STATES = True
PLOT = False
MAX_DIST = 100
UNIX_REFERENCE = 1420243200
TIME_INTERVAL = 300  # 5 minutes in seconds
# How often to write edge data to file (in number of trips)
WRITEOUT_INTERVAL = 1000

# input and clean data directories
DATA_INPUT_DIRECTORY = "data/input_data"
CLEANED_DATA_DIRECTORY = "data/cleaned_data"


def write_intermediate_edge_data(writeout_timer, trip_id) -> None:
    # Time readout.
    start_time = datetime.now()
    # Write edge traversals data to json file.
    print(f"Writing edge traversal data before processing trip_id {trip_id}")
    writeout_traversals_to_json(file_path='edge_traversals.json',
                                edge_items=Edge.get_all_edges())
    end_time = datetime.now()
    time_diff = (end_time - start_time)
    print(
        f"Writeout at {start_time}, took {time_diff.seconds}.{time_diff.microseconds} seconds.")
    return None

def get_trip_data(df: pd.DataFrame, trip_id: int, time_reference: int) -> tuple[list[float], list[float], list[float]] | None:
    try:
        group = df[df['trip_id'] == trip_id]
        lats = group['latitude'].tolist()
        lons = group['longitude'].tolist()
        times = (group['timestamp'] - time_reference).tolist()
    except Exception as e:
        logger.warning(f"Skipping trip_id {trip_id} due to error: {e}")
        return None
    
    return lats, lons, times

def writeout_final_result() -> None:
    with open('vertex_data.json', 'w') as f:
        f.write('{\n')
        vertex_items = Vertex.get_all_vertices()
        for i, vertex in enumerate(vertex_items):
            connections = {
                'outward_edges': [edge.id for edge in vertex.get_outward_edges()],
                'backward_edges': [edge.id for edge in vertex.get_backward_edges()],
                'outward_vertices': [v.id for v in vertex.get_outward_vertices()],
                'backward_vertices': [v.id for v in vertex.get_backward_vertices()]
            }
            f.write(f'\t"{vertex.id}": {json.dumps(connections)}')
            if i < len(vertex_items) - 1:
                f.write(',')
            f.write('\n')
        f.write('}\n')

    return None

def main() -> None:
    network = build_graph('./cleaned_data/osm_nodes_output.json', './cleaned_data/osm_roads_output.json')
    remove_small_subnetworks(network)
    network.load_or_compute_all_pairs_distances(distances_file='all_pairs_distances.npy',
                                                mapping_file='vertex_id_mapping.json')

    for trip_file in ['trips_150103.csv']:
        # Load and filter trip data
        df = pd.read_csv(f'./cleaned_data/{trip_file}')
        next_writeout = WRITEOUT_INTERVAL
        max_trip = df['trip_id'].max()

        for trip_id in tqdm(range(100), desc=f"Processing trips in {trip_file}"):
            lats, lons, times = get_trip_data(df=df, trip_id=trip_id, time_reference=UNIX_REFERENCE)

            trip = Trip(network, trip_id, lats, lons, times)
            trip_layer_distances = trip.compute_layer_distances(max_dist=MAX_DIST)
            best_path = viterbi_algorithm(trip_layer_distances)
            trip.process_and_apply_best_path(best_path, times, TIME_INTERVAL)

    total_time_intervals = int(24 * 60 * 60 / TIME_INTERVAL)
    network.mark_missing_edge_traversals(max_time_index=total_time_intervals)

    import csv

    with open('temp_result.csv', 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        fieldnames = ['edge_id']
        for i in range(total_time_intervals):
            fieldnames.append(f'time_idx_{i}')
        csv_writer.writerow(fieldnames)
        for edge in network.get_all_edges():
            row = [edge.id]
            for time_idx in range(total_time_intervals):
                mean, variance, total_length = edge.traversals_data[time_idx]
                row.append(mean)
            csv_writer.writerow(row)

    return
    # Write vertex connections to json file
    writeout_final_result()
    return None


if __name__ == "__main__":
    main()
