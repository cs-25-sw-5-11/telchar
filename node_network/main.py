from classes import Vertex, Edge
from functions_building import build_graph
from functions_analysis import find_networks, filter_non_largest_network, extract_lats_lons_for_trip
from functions_plotting import plot_networks, plot_directed_graph
from functions_mapping import process_trip, find_shortest_edge_path
from functions_misc import restore_network_to_original_state, validate_network_integrity, capture_network_state, compare_network_states
from viterbi import viterbi_algorithm
import matplotlib.pyplot as plt
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see debug statements
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

# Suppress matplotlib font manager debug messages
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

COMPARE_STATES = True
MAX_DIST = 50

if __name__ == "__main__":
    build_graph('./cleaned_data/osm_nodes_output.json', './cleaned_data/osm_roads_output.json')
    
    networks = find_networks()
    filter_non_largest_network(networks)

    if COMPARE_STATES:
        # Capture original state for later comparison
        original_state = capture_network_state()

    # print(all_pairs_network_distances_between_layers(vertex_layers[0], vertex_layers[1]))    

    for trip_file in ['trips_150103.csv']:
        for trip_id in [6]:
            lats, lons = extract_lats_lons_for_trip(trip_file, trip_id)
            data_output_dict = process_trip(lats, lons, max_dist=MAX_DIST)
            best_path = viterbi_algorithm(data_output_dict)
            print(best_path)
            edges_in_path = []
            for i in range(len(best_path)-1):
                start_vertex = Vertex.vertex_dict[best_path[i]]
                end_vertex = Vertex.vertex_dict[best_path[i+1]]
                dist, path_edges = find_shortest_edge_path(start_vertex, end_vertex)
                edges_in_path.extend(path_edges)

            best_path_vertex_coords = [(Vertex.vertex_dict[vertex_id].lat, Vertex.vertex_dict[vertex_id].lon) for vertex_id in best_path]
            print(f"Edges in best path: {[edge.id for edge in edges_in_path]}")
            for edge in edges_in_path:
                edge.parent_edge.highlighted = True
            restore_network_to_original_state()

    # Plot as usual
    # plot_networks(vertex_layers=vertex_layers, highlight_lat=45.7485, highlight_lon=126.6905, show_densest_bin=False)
    # plot_networks()
    plot_directed_graph(lat_min=45.62, lat_max=45.77, lon_min=126.65, lon_max=126.75,
                        trip_point_lats=lats, trip_point_lons=lons, max_dist=MAX_DIST,
                        best_path_vertex_coords=best_path_vertex_coords)
    

    if COMPARE_STATES:
        # Validate integrity after restoration
        restored_state = capture_network_state()
        compare_network_states(original_state, restored_state)
    # validate_network_integrity()
