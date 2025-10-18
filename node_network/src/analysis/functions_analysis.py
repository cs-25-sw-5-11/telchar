from classes.classes import Vertex, Edge
from tqdm import tqdm
from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from utils.functions_misc import get_bin_indices
import math
import pandas as pd






def filter_non_largest_network(networks):
    print("Filtering out vertices and edges not belonging to the largest network...")
    largest_network = max(networks, key=len)
    # Remove vertices not in largest network from Vertex.vertex_dict
    to_remove_vertices = []
    for _, vertex in tqdm(list(Vertex.vertex_dict.items()), desc="Identifying vertices to remove"):
        if vertex not in largest_network:
            to_remove_vertices.append(vertex)
    for vertex in tqdm(to_remove_vertices, desc="Deleting vertices"):
        vertex.delete_vertex()

def get_edges_near_coordinate(lat: float, lon: float, radius_bins: int = 1) -> list:
    """
    Get all edges within a radius of bins around a coordinate using the new bin system.
    
    Args:
        lat, lon: Target coordinate
        radius_bins: Number of bins to search in each direction (default 1 = 3x3 area)
    
    Returns:
        List of Edge objects near the coordinate
    """
    center_bin = get_bin_indices(lat, lon)
    if center_bin is None:
        return []
    
    center_lat_idx, center_lon_idx = center_bin
    nearby_edges = set()
    
    for lat_offset in range(-radius_bins, radius_bins + 1):
        for lon_offset in range(-radius_bins, radius_bins + 1):
            search_lat_idx = center_lat_idx + lat_offset
            search_lon_idx = center_lon_idx + lon_offset
            
            edges_in_bin = Edge.get_edges_in_bin(search_lat_idx, search_lon_idx)
            nearby_edges.update(edges_in_bin)
    
    return list(nearby_edges)

def get_vertices_near_coordinate(lat: float, lon: float, radius_bins: int = 1) -> list:
    """
    Get all vertices within a radius of bins around a coordinate using the new bin system.
    
    Args:
        lat, lon: Target coordinate
        radius_bins: Number of bins to search in each direction (default 1 = 3x3 area)
    
    Returns:
        List of Vertex objects near the coordinate
    """
    center_bin = get_bin_indices(lat, lon)
    if center_bin is None:
        return []
    
    center_lat_idx, center_lon_idx = center_bin
    nearby_vertices = set()
    
    for lat_offset in range(-radius_bins, radius_bins + 1):
        for lon_offset in range(-radius_bins, radius_bins + 1):
            search_lat_idx = center_lat_idx + lat_offset
            search_lon_idx = center_lon_idx + lon_offset
            
            vertices_in_bin = Vertex.get_vertices_in_bin(search_lat_idx, search_lon_idx)
            nearby_vertices.update(vertices_in_bin)
    
    return list(nearby_vertices)
    """
    Get all vertices within a radius of bins around a coordinate using the new bin system.
    
    Args:
        lat, lon: Target coordinate
        radius_bins: Number of bins to search in each direction (default 1 = 3x3 area)
    
    Returns:
        List of Vertex objects near the coordinate
    """
    center_bin = get_bin_indices(lat, lon)
    if center_bin is None:
        return []
    
    center_lat_idx, center_lon_idx = center_bin
    nearby_vertices = set()
    
    for lat_offset in range(-radius_bins, radius_bins + 1):
        for lon_offset in range(-radius_bins, radius_bins + 1):
            search_lat_idx = center_lat_idx + lat_offset
            search_lon_idx = center_lon_idx + lon_offset
            
            vertices_in_bin = Vertex.get_vertices_in_bin(search_lat_idx, search_lon_idx)
            nearby_vertices.update(vertices_in_bin)
    
    return list(nearby_vertices)