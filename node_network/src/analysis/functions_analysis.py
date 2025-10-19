from classes.classes import Vertex, Edge
from tqdm import tqdm
from utils.functions_misc import get_bin_indices








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
  