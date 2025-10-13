import heapq
import os
import json
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from classes import Vertex, Edge
from functions_misc import get_bin_indices, restore_network_to_original_state
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def get_edges_near_coordinates(lat, lon, cell_range=0):
    """
    Get edges near given coordinates using the class-based spatial binning system.
    """
    idx = get_bin_indices(lat, lon)
    if idx is None:
        raise ValueError(f"Coordinates (lat={lat}, lon={lon}) are out of bounds for the configured bins.")
    lat_idx, lon_idx = idx
    edges = set()
    
    if cell_range == 0:
        # Use the corner-based logic for cell_range=0
        lat_bin_start = LAT_MIN + lat_idx * LAT_BIN_SIZE
        lon_bin_start = LON_MIN + lon_idx * LON_BIN_SIZE
        corners = [
            (lat_bin_start, lon_bin_start),                    # bottom-left (0,0)
            (lat_bin_start + LAT_BIN_SIZE, lon_bin_start),     # top-left (1,0)  
            (lat_bin_start, lon_bin_start + LON_BIN_SIZE),     # bottom-right (0,1)
            (lat_bin_start + LAT_BIN_SIZE, lon_bin_start + LON_BIN_SIZE)  # top-right (1,1)
        ]
        dists = [((lat - clat)**2 + (lon - clon)**2, idx) for idx, (clat, clon) in enumerate(corners)]
        _, closest_corner_idx = min(dists)
        
        # Define the 4 bins that share each corner
        # Each corner is shared by 4 bins, we want the current bin plus the 3 adjacent ones
        corner_to_offsets = {
            0: [(0, 0), (-1, 0), (0, -1), (-1, -1)],    # bottom-left corner
            1: [(0, 0), (1, 0), (0, -1), (1, -1)],      # top-left corner
            2: [(0, 0), (-1, 0), (0, 1), (-1, 1)],      # bottom-right corner  
            3: [(0, 0), (1, 0), (0, 1), (1, 1)]         # top-right corner
        }
        
        offsets = corner_to_offsets[closest_corner_idx]
        bins = []
        for di, dj in offsets:
            i = lat_idx + di
            j = lon_idx + dj
            bins.append((i, j))
        
        # Query the class-based system for each bin
        for i, j in bins:
            if (i, j) in Edge._bin_lookup:
                edges.update(Edge._bin_lookup[(i, j)])
    else:
        # Use cell_range expansion
        for dlat in range(-cell_range, cell_range + 1):
            for dlon in range(-cell_range, cell_range + 1):
                i = lat_idx + dlat
                j = lon_idx + dlon
                if (i, j) in Edge._bin_lookup:
                    edges.update(Edge._bin_lookup[(i, j)])
    return list(edges)

def find_existing_vertex_at_projection(proj_lat, proj_lon, proj_edge, tolerance=1e-7):
    """
    Check if projection coordinates match an existing vertex.
    
    Args:
        proj_lat, proj_lon: Projection coordinates
        proj_edge: Edge being projected onto
        tolerance: Coordinate matching tolerance
    
    Returns:
        Vertex object if match found, None otherwise
    """
    # Check if it's close to the start vertex
    if abs(proj_lat - proj_edge.start.lat) < tolerance and abs(proj_lon - proj_edge.start.lon) < tolerance:
        return proj_edge.start
    
    # Check if it's close to the end vertex
    if abs(proj_lat - proj_edge.end.lat) < tolerance and abs(proj_lon - proj_edge.end.lon) < tolerance:
        return proj_edge.end
    
    # Check if it's close to any existing vertex in the same bin
    idx = get_bin_indices(proj_lat, proj_lon)
    if idx and idx in Vertex._bin_lookup:
        for vertex in Vertex._bin_lookup[idx]:
            if abs(vertex.lat - proj_lat) < tolerance and abs(vertex.lon - proj_lon) < tolerance:
                return vertex
    
    return None

def create_temporary_vertex_and_split_edge(proj_lat, proj_lon, proj_edge, seg_idx):
    """
    Create a temporary vertex at projection point and split the edge.
    
    Args:
        proj_lat, proj_lon: Projection coordinates
        proj_edge: Edge to split
        seg_idx: Segment index for insertion
    
    Returns:
        Vertex object if successful, None if failed
    """
    # Create a temporary vertex at the projection point
    temp_vertex = Vertex(proj_lat, proj_lon, temporary=True)
    
    # Insert the new vertex data into the edge's non_vertex_nodes at the correct position
    new_node = (proj_lat, proj_lon, temp_vertex.id)
    insert_pos = seg_idx
    proj_edge.non_vertex_nodes.insert(insert_pos, new_node)
    
    # Now split the edge along this temporary vertex
    try:
        edge1, edge2 = proj_edge.split_edge_along_vertex(temp_vertex, temporary=True)
        return temp_vertex
    except ValueError as e:
        print(f"      Error splitting edge: {e}")
        # Remove the inserted node if splitting failed
        proj_edge.non_vertex_nodes.pop(insert_pos)
        # Remove the temporary vertex
        if temp_vertex.id in Vertex.vertex_dict:
            del Vertex.vertex_dict[temp_vertex.id]
        return None

def process_single_projection(proj_edge, proj_lat, proj_lon, proj_dist, seg_idx):
    """
    Process a single projection to find or create a vertex.
    
    Args:
        proj_edge: Edge being projected onto
        proj_lat, proj_lon: Projection coordinates
        proj_dist: Distance to projection point
        seg_idx: Segment index
    
    Returns:
        Vertex object if successful, None if failed
    """
    
    # First, check if projection matches an existing vertex
    projected_vertex = find_existing_vertex_at_projection(proj_lat, proj_lon, proj_edge)
    
    if projected_vertex:
        return projected_vertex
    
    # If no existing vertex found, create temporary vertex and split edge
    return create_temporary_vertex_and_split_edge(proj_lat, proj_lon, proj_edge, seg_idx)

def project_single_trip_point(lat, lon, cell_range, max_dist):
    """
    Project a single trip point onto the network.
    
    Args:
        lat, lon: Trip point coordinates
        cell_range: Search radius in bins
        max_dist: Maximum projection distance
    
    Returns:
        List of vertices where the point was projected
    """
    # Get all edges in nearby bins
    nearby_edges = get_edges_near_coordinates(lat, lon, cell_range)
    
    if not nearby_edges:
        print(f"  No edges found near point ({lat}, {lon})")
        return []
    
    # Find all valid projections within max_dist
    valid_projections = []
    
    for edge in nearby_edges:
        # Skip detached edges
        if edge.detached:
            continue
            
        proj_lat, proj_lon, dist_m, seg_idx = edge.project_coordinates_onto_edge(lat, lon)
        
        if dist_m is not None and dist_m <= max_dist:
            valid_projections.append((edge, proj_lat, proj_lon, dist_m, seg_idx))
    
    if not valid_projections:
        print(f"  No suitable projections found within {max_dist}m")
        return []
    
    # Sort projections by distance (closest first)
    valid_projections.sort(key=lambda x: x[3])
    
    # Process each valid projection to create/find vertices
    projected_vertices = []
    
    for proj_edge, proj_lat, proj_lon, proj_dist, seg_idx in valid_projections:
        projected_vertex = process_single_projection(proj_edge, proj_lat, proj_lon, proj_dist, seg_idx)
        
        # Add the projected vertex to the list if not already present
        if projected_vertex and projected_vertex not in projected_vertices:
            projected_vertices.append(projected_vertex)
    
    return projected_vertices

def project_trip_coordinates_onto_edges(lats, lons, cell_range=0, max_dist=float('inf'), debug: bool=True):
    # Process each trip point sequentially
    results = []  # List of lists of vertices
    
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        if debug:
            print(f"Processing trip point {i+1}/{len(lats)}: ({lat:.6f}, {lon:.6f})")
        
        # Project this single point onto the current network state
        projected_vertices = project_single_trip_point(lat, lon, cell_range, max_dist)
        
        # Add results and log progress
        results.append(projected_vertices)
        if debug:
            print(f"  Created/found {len(projected_vertices)} vertices for this trip point")

    if debug:
        print(f"Trip projection complete. Created {len(Vertex.temporary_vertices)} temporary vertices")
    return results

def find_or_create_vertex_at_projection(proj_lat, proj_lon, tolerance=1e-9):
    """
    Find or create a vertex at the projection location using the class-based spatial system.
    """
    idx = get_bin_indices(proj_lat, proj_lon)
    if idx is None:
        return None, False
    
    lat_idx, lon_idx = idx
    # Check if there are vertices in this bin
    if (lat_idx, lon_idx) in Vertex._bin_lookup:
        for v in Vertex._bin_lookup[(lat_idx, lon_idx)]:
            if abs(v.lat - proj_lat) <= tolerance and abs(v.lon - proj_lon) <= tolerance:
                return v, False
    
    # No existing vertex found, create new one
    v = Vertex(proj_lat, proj_lon, temporary=True)
    return v, True

def all_pairs_network_distances_between_layers(layer1, layer2):
    """
    For each vertex in layer1, compute the shortest network distance to every vertex in layer2.
    Only traverses onward edges (respects directed graph structure).
    Returns a dict: {v1: {v2: dist, ...}, ...} where dist is the sum of edge.length along the shortest path.
    """
    import heapq
    results = {}
    layer2_ids = set(v.id for v in layer2)
    for v1 in layer1:
        dists = dijkstras_algorithm_with_early_stopping(v1, layer2_ids)
        # Collect distances to all layer2 vertices
        result_row = {}
        for v2 in layer2:
            result_row[v2] = dists.get(v2.id, float('inf'))
        results[v1] = result_row
    return results

def dijkstras_algorithm_with_early_stopping(start_vertex, target_vertices):
    visited = set()
    found_layer2 = set()
    heap = [(0, start_vertex)]  # (distance, vertex)
    dists = {start_vertex.id: 0}
    while heap and len(found_layer2) < len(target_vertices):
        dist_u, u = heapq.heappop(heap)
        if u.id in visited:
            continue
        visited.add(u.id)
        if u.id in target_vertices:
            found_layer2.add(u.id)
        for edge, neighbor in u.onward_edges.items():
            if neighbor.id not in visited:
                alt = dist_u + edge.length
                if alt < dists.get(neighbor.id, float('inf')):
                    dists[neighbor.id] = alt
                    heapq.heappush(heap, (alt, neighbor))
    return dists

def generate_network_distances_dict(vertex_layers):    
    data_output_dict = {     }

    logger.debug("Computing all-pairs network distances between layers...")
    for i in range(len(vertex_layers)-1):
        result = all_pairs_network_distances_between_layers(vertex_layers[i], vertex_layers[i+1])        
        transition = {}
        for k, v in result.items():
            transition[k.id] = {vv.id: round(dist, 3) for vv, dist in v.items() if dist is not float('inf')}
        data_output_dict[i] = transition

    return data_output_dict

def process_trip(lats, lons, cell_range=0, max_dist=50):
    vertex_layers = project_trip_coordinates_onto_edges(lats, lons,
                                                        cell_range=cell_range, max_dist=max_dist)
    data_output_dict = generate_network_distances_dict(vertex_layers)

    output_path = f'peter_fucking_around/output_data/network_distances.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data_output_dict, f, indent=4)

    return data_output_dict