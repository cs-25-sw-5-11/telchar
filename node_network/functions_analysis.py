from classes import Vertex, Edge
from tqdm import tqdm
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from functions_misc import get_bin_indices
import math

def find_networks():
    vertices = list(Vertex.vertex_dict.values())
    visited = set()
    networks = []
    for v in vertices:
        if v not in visited:
            stack = [v]
            network = set()
            while stack:
                curr = stack.pop()
                if curr not in visited:
                    visited.add(curr)
                    network.add(curr)
                    stack.extend([neighbor for neighbor in curr.get_outward_nodes() if neighbor not in visited])
                    stack.extend([neighbor for neighbor in curr.get_backward_nodes() if neighbor not in visited])
            networks.append(network)

    print(f"Number of networks (connected components): {len(networks)}")

    return networks

def filter_non_largest_network(networks):
    print("Filtering out nodes not belonging to the largest network...")
    largest_network = max(networks, key=len)
    # Remove vertices not in largest network from Vertex.vertex_dict
    to_remove_v = []
    for vid, v in tqdm(list(Vertex.vertex_dict.items()), desc="Identifying vertices to remove"):
        if v not in largest_network:
            to_remove_v.append(vid)
    for vid in tqdm(to_remove_v, desc="Deleting vertices"):
        del Vertex.vertex_dict[vid]
    # Remove edges not in largest network from Edge.edge_dict
    edges_in_largest = set()
    for e in tqdm(Edge.edge_dict.values(), desc="Identifying edges in largest network"):
        if e.start in largest_network and e.end in largest_network:
            edges_in_largest.add(e)
    to_remove_e = []
    for eid, e in tqdm(list(Edge.edge_dict.items()), desc="Identifying edges to remove"):
        if e not in edges_in_largest:
            to_remove_e.append(eid)
    for eid in tqdm(to_remove_e, desc="Deleting edges"):
        del Edge.edge_dict[eid]



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