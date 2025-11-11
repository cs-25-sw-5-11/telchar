from classes import Network, Trip, Vertex
from utils.functions_misc import get_bin_indices
import matplotlib.pyplot as plt
from typing import List

def plot_helper(trip: Trip, network: Network, trip_id: int, lats: List[float], lons: List[float], best_path: List[int]) -> None:
    best_path_lats, best_path_lons = [], []

    point_projection_id_threshold = trip.get_id_max() + 1
    for item in best_path:
        if item < point_projection_id_threshold:
            point_projection = trip.get_point_projection_by_id(item)
            best_path_lats.append(point_projection.lat)
            best_path_lons.append(point_projection.lon)
        else:
            vertex = network.get_vertex_by_id(item)
            best_path_lats.append(vertex.lat)
            best_path_lons.append(vertex.lon)

    min_lat, max_lat = min(best_path_lats), max(best_path_lats)
    min_lon, max_lon = min(best_path_lons), max(best_path_lons)

    lat_idx_min, lon_idx_min = get_bin_indices(min_lat, min_lon)
    lat_idx_max, lon_idx_max = get_bin_indices(max_lat, max_lon)

    all_vertices_in_area = []
    all_edges_in_area = []
    
    for lat_idx in range(lat_idx_min - 1, lat_idx_max + 2):
        for lon_idx in range(lon_idx_min - 1, lon_idx_max + 2):
            all_vertices_in_area.extend(network.get_vertices_in_bin(lat_idx, lon_idx))
            for edge in network.get_edges_in_bin(lat_idx, lon_idx):
                if edge not in all_edges_in_area:
                    all_edges_in_area.append(edge)
    
    best_path_edges = []
    for i in range(len(best_path)-1):
        dist, edge_path = trip.find_shortest_edge_path(best_path[i], best_path[i+1])
        for edge in edge_path:
            best_path_edges.append(edge)            

    plt.figure()
    plt.scatter([v.lon for v in all_vertices_in_area], [v.lat for v in all_vertices_in_area], c='black', s=5, label='Vertices')
    for edge in all_edges_in_area:
        plt.plot([edge.start.lon, edge.end.lon], [edge.start.lat, edge.end.lat], c='gray', linewidth=0.5)
    for edge in best_path_edges:
        plt.plot([edge.start.lon, edge.end.lon], [edge.start.lat, edge.end.lat], c='red', linewidth=2)
    plt.scatter(lons, lats, c='blue', s=15, label='Original Trip')
    plt.scatter(best_path_lons, best_path_lats, c='orange', marker='x', s=30, label='Best Path')
    plt.legend()
    plt.title(f"Trip {trip_id} - Best Path")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.show()
    