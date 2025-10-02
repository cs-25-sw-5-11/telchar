from classes import Vertex, Edge
from functions_building import build_graph
from functions_analysis import find_networks, filter_non_largest_network
from functions_plotting import plot_networks, plot_directed_graph
from functions_mapping import process_trip, project_trip_coordinates_onto_edges, all_pairs_network_distances_between_layers
from functions_misc import restore_network_to_original_state, validate_network_integrity, capture_network_state, compare_network_states
import matplotlib.pyplot as plt
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see debug statements
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

COMPARE_STATES = True

if __name__ == "__main__":
    build_graph('./cleaned_data/osm_nodes_output.json', './cleaned_data/osm_roads_output.json')
    
    networks = find_networks()
    filter_non_largest_network(networks)

    if COMPARE_STATES:
        # Capture original state for later comparison
        original_state = capture_network_state()

    # Use new object-oriented approach - no need to build matrices
    vertex_layers = project_trip_coordinates_onto_edges(trip_id=6, trip_file='trips_150103.csv',
                                                        cell_range=0, max_dist=50)

    # print(all_pairs_network_distances_between_layers(vertex_layers[0], vertex_layers[1]))    

    for trip_file in ['trips_150103.csv']:
        for trip_id in [6]:
            process_trip(trip_file, trip_id)

    # Plot as usual
    # plot_networks(vertex_layers=vertex_layers, highlight_lat=45.7485, highlight_lon=126.6905, show_densest_bin=False)
    # plot_networks()
    # plot_directed_graph(lat_min=45.72, lat_max=45.77, lon_min=126.72, lon_max=126.75)


    if COMPARE_STATES:
        restore_network_to_original_state()
        # Validate integrity after restoration
        restored_state = capture_network_state()
        compare_network_states(original_state, restored_state)
    # validate_network_integrity()
