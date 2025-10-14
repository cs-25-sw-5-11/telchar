from classes import Vertex, Edge
from functions_building import build_graph
from functions_analysis import find_networks, filter_non_largest_network
from functions_plotting import plot_networks, plot_directed_graph
from functions_mapping import process_trip, find_shortest_edge_path
from functions_misc import get_time_index, writeout_traversals_to_json, restore_network_to_original_state, validate_network_integrity, capture_network_state, compare_network_states
from viterbi import viterbi_algorithm
import matplotlib.pyplot as plt
import logging
from tqdm import tqdm
import pandas as pd
import json
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
WRITEOUT_INTERVAL = 1000 # How often to write edge data to file (in number of trips)

if __name__ == "__main__":
    build_graph('./cleaned_data/osm_nodes_output.json', './cleaned_data/osm_roads_output.json')

    networks = find_networks()
    filter_non_largest_network(networks)

    if COMPARE_STATES:
        # Capture original state for later comparison
        original_state = capture_network_state()

    # print(all_pairs_network_distances_between_layers(vertex_layers[0], vertex_layers[1]))    

    for trip_file in ['trips_150103.csv']:
        # Load and filter trip data
        df = pd.read_csv(f'cleaned_data/{trip_file}')
        next_writeout = WRITEOUT_INTERVAL
        max_trip = df['trip_id'].max()

        for trip_id in tqdm(range(1, max_trip + 1), desc=f"Processing trips in {trip_file}"):
            # Reset network state before processing each trip.
            # Here instead of at the end due to possible early continues.
            restore_network_to_original_state()

            # Writeout intermediate results periodically.
            # Needs to be right after restoration to avoid getting temporary edges.
            if trip_id >= next_writeout:
                next_writeout += WRITEOUT_INTERVAL
                # Time readout.
                start_time = datetime.now()
                # Write edge traversals data to json file.
                print(f"Writing edge traversal data before processing trip_id {trip_id}")
                writeout_traversals_to_json(file_path='edge_traversals.json', 
                                            edge_items=list(Edge.edge_dict.values()))
                end_time = datetime.now()
                time_diff = (end_time - start_time)
                print(f"Readout time: {time_diff.seconds}.{time_diff.microseconds}")

            try:
                group = df[df['trip_id'] == trip_id]
                lats = group['latitude'].tolist()
                lons = group['longitude'].tolist()
                times = (group['timestamp'] - UNIX_REFERENCE).tolist()
            except Exception as e:
                logger.warning(f"Skipping trip_id {trip_id} due to error: {e}")
                continue

            data_output_dict = process_trip(lats, lons, max_dist=MAX_DIST)
            if data_output_dict is None:
                logger.debug(f"Skipping trip_id {trip_id} due to no projected vertices.")
                continue

            try:
                best_path = viterbi_algorithm(data_output_dict)
            except Exception as e:
                continue
            edges_in_path = []
            for i in range(len(best_path)-1):
                start_vertex = Vertex.vertex_dict[best_path[i]]
                end_vertex = Vertex.vertex_dict[best_path[i+1]]
                dist, path_edges = find_shortest_edge_path(start_vertex, end_vertex)

                # 0 as reference, as times has already been adjusted for the reference value.
                time_index = get_time_index(timestamp=times[i], reference=0, interval=TIME_INTERVAL)
                time_diff = times[i+1] - times[i]
                speed = int(dist / time_diff * 100)  # Convert m/s to cm/s

                for edge in path_edges:
                    edge_length = int(edge.length * 100)  # Convert m to cm
                    # Converting to cm and using int to save space.
                    edge.parent_edge.traversals_data_update(time_index, speed, edge_length)

                edges_in_path.extend(path_edges)

            best_path_vertex_coords = [(Vertex.vertex_dict[vertex_id].lat, Vertex.vertex_dict[vertex_id].lon) for vertex_id in best_path]
            for edge in edges_in_path:
                edge.parent_edge.highlighted = True


    # Final cleanup.
    restore_network_to_original_state()
    print("Final writeout of edge traversal data...")
    writeout_traversals_to_json(file_path='edge_traversals.json', 
                                edge_items=list(Edge.edge_dict.values()))

    if PLOT:
        plot_directed_graph(lat_min=45.62, lat_max=45.77, lon_min=126.65, lon_max=126.75,
                            trip_point_lats=lats, trip_point_lons=lons, max_dist=MAX_DIST,
                            best_path_vertex_coords=best_path_vertex_coords)

    if COMPARE_STATES:
        # Validate integrity after restoration
        restored_state = capture_network_state()
        compare_network_states(original_state, restored_state)

    # Write vertex connections to json file
    with open('vertex_data.json', 'w') as f:
        f.write('{\n')
        vertex_items = list(Vertex.vertex_dict.values())
        for i, vertex in enumerate(vertex_items):
            connections = {
                'outward_edges': [edge.id for edge in vertex.get_outward_edges()],
                'backward_edges': [edge.id for edge in vertex.get_backward_edges()],
                'outward_vertices': [vertex.id for vertex in vertex.get_outward_vertices()],
                'backward_vertices': [vertex.id for vertex in vertex.get_backward_vertices()]
            }
            f.write(f'\t"{vertex.id}": {json.dumps(connections)}')
            if i < len(vertex_items) - 1:
                f.write(',')
            f.write('\n')
        f.write('}\n')
