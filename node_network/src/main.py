from classes import Network, Edge, Vertex, Trip
from graph_building.build_graph import build_graph
<<<<<<< HEAD
from graph_building.filter_out_subnetworks import remove_small_subnetworks
import numpy as np

# from plotting.functions_plotting import plot_networks, plot_directed_graph

from graph_mapping.functions_mapping import process_trip, find_shortest_edge_path
from utils.functions_misc import get_time_index,writeout_traversals_to_json
=======
from graph_building.find_network import find_network
from extract_osm_map.extract_osm_map import extract_map
from data_cleaning.clean_trips import clean_trips
from plotting.functions_plotting import plot_networks, plot_directed_graph

from graph_mapping.functions_mapping import process_trip, find_shortest_edge_path

from utils.functions_misc import get_time_index, writeout_traversals_to_json, restore_network_to_original_state, validate_network_integrity, capture_network_state, compare_network_states

>>>>>>> main
from viterbi.viterbi import viterbi_algorithm

import matplotlib.pyplot as plt
import logging
from tqdm import tqdm
import pandas as pd
import json
from datetime import datetime
import os

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
    print(network.get_stats())

    remove_small_subnetworks(network)
    print(len(network.get_all_vertices()), "vertices after filtering.")

    nodes = set()

    network.load_or_compute_all_pairs_distances(distances_file='all_pairs_distances.npy',
                                                mapping_file='vertex_id_mapping.json')

    for trip_file in ['trips_150103.csv']:
        # Load and filter trip data
        df = pd.read_csv(f'data/cleaned_data/{trip_file}')
        next_writeout = WRITEOUT_INTERVAL
        max_trip = df['trip_id'].max()

        for trip_id in tqdm(range(6, 7), desc=f"Processing trips in {trip_file}"):
            lats, lons, times = get_trip_data(df=df, trip_id=trip_id, time_reference=UNIX_REFERENCE)

            trip = Trip(network, trip_id, lats, lons, times)
            trip_layer_distances = trip.compute_layer_distances(max_dist=MAX_DIST)
            
            best_path = viterbi_algorithm(trip_layer_distances)
            print(best_path)

            for i in range(len(best_path)-1):
                dist, edges = trip.find_shortest_edge_path(start_item_id = best_path[i], end_item_id = best_path[i+1])
                speed = dist / (times[i+1] - times[i])  # m/s
                time_index = get_time_index(timestamp=times[i], reference=0, interval=TIME_INTERVAL)
                trip.apply_speed_to_edges(edges, time_index, speed)


    total_time_intervals = 24 * 60 * 60 / TIME_INTERVAL
    network.mark_missing_edge_traversals(max_time_index=total_time_intervals)
    return

    # Write vertex connections to json file
    writeout_final_result()
    return None


if __name__ == "__main__":
    main()
