from classes import Vertex, Edge
from functions_building import load_osm_json, build_graph
from functions_analysis import find_networks, filter_non_largest_network, bin_edges_by_lat_lon, bin_vertices_by_lat_lon
from functions_mapping import project_trip_coordinates_onto_edges, apply_projection_and_splitting, all_pairs_network_distances_between_layers
from functions_plotting import plot_networks
import matplotlib.pyplot as plt

if __name__ == "__main__":
    roads = load_osm_json('cleaned_data/osm_roads_output.json')
    build_graph(roads)

    networks = find_networks(list(Vertex.vertex_dict.values()))
    filter_non_largest_network(networks)
    edges_binned_matrix = bin_edges_by_lat_lon()  # Build edges_binned_matrix after filtering
    vertices_binned_matrix = bin_vertices_by_lat_lon()
    results = project_trip_coordinates_onto_edges(edges_binned_matrix, trip_id=6, trip_file='trips_150103.csv',
                                                  cell_range=1, max_dist=50)

    print(f"Number of vertices before splitting: {len(Vertex.vertex_dict)}")
    changes, vertex_layers = apply_projection_and_splitting(vertices_binned_matrix, results)
    print(f"Number of vertices after splitting: {len(Vertex.vertex_dict)}")

    print(vertex_layers)

    # print(all_pairs_network_distances_between_layers(vertex_layers[0], vertex_layers[1]))

    # Plot as usual
    # plot_networks(networks, edges_binned_matrix, results, highlight_lat=45.7485, highlight_lon=126.6905, show_densest_bin=True)
    plot_networks(edges_binned_matrix, results, vertex_layers)