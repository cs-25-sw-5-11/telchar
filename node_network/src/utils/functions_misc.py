from typing import List, Tuple
from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from math import radians, sin, cos, sqrt, atan2
import logging
import json

logger = logging.getLogger(__name__)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

def get_time_index(timestamp: int, reference: int, interval: int) -> int:
    """
    Convert a UNIX timestamp to a time index representing the number of a set minute intervals since a reference time.
    
    Args:
        timestamp: UNIX timestamp (seconds since epoch)
        reference: Reference UNIX timestamp (e.g., start of day)

    Returns:
        Time index (int) representing the number of 5-minute intervals since the reference time.
    """
    return (timestamp - reference) // interval

def writeout_traversals_to_json(file_path: str, edge_items):
    from math import sqrt
    with open(file_path, 'w') as f:
        f.write('{\n')
        for i, edge in enumerate(edge_items):
            # Convert to integers at output time for space efficiency, sorted by time_idx
            # Convert variance to standard deviation for interpretability
            traversals_data_int = {
                time_idx: (int(mean), int(sqrt(variance)), int(total_length))
                for time_idx, (mean, variance, total_length) in sorted(edge.traversals_data.items())
            }
            
            edge_data = {
                'length (cm)': int(edge.length * 100), 
                'traversals_data': traversals_data_int
            }
            f.write(f'\t"{edge.id}": {json.dumps(edge_data)}')
            if i < len(edge_items) - 1:
                f.write(',')
            f.write('\n')
        f.write('}\n')

def get_bin_indices(lat: float, lon: float):
    """Calculate bin indices for given latitude and longitude coordinates.
    
    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        
    Returns:
        Tuple[int, int] or None: (lat_idx, lon_idx) if within bounds, None otherwise
    """
    from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
    
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None
        
    lat_idx = int((lat - LAT_MIN) / LAT_BIN_SIZE)
    lon_idx = int((lon - LON_MIN) / LON_BIN_SIZE)
    return (lat_idx, lon_idx)

def get_bins_near_point(lat: float, lon: float, range: int=0) -> List[Tuple[int, int]]:
    idx = get_bin_indices(lat, lon)
    if idx is None:
        raise ValueError(f"Coordinates (lat={lat}, lon={lon}) are out of bounds for the configured bins.")
    lat_idx, lon_idx = idx

    if range==0:
        # Check which corner the edge is closest to
        if lat % LAT_BIN_SIZE < LAT_BIN_SIZE / 2:
            if lon % LON_BIN_SIZE < LON_BIN_SIZE / 2:
                # Bottom-left corner
                offsets = [(0, 0), (-1, 0), (0, -1), (-1, -1)]
            else:
                # Bottom-right corner
                offsets = [(0, 0), (-1, 0), (0, 1), (-1, 1)]
        else:
            if lon % LON_BIN_SIZE < LON_BIN_SIZE / 2:
                # Top-left corner
                offsets = [(0, 0), (1, 0), (0, -1), (1, -1)]
            else:
                # Top-right corner
                offsets = [(0, 0), (1, 0), (0, 1), (1, 1)]
    else:
        # Not currently supported, raise error.
        raise NotImplementedError("Range > 0 not currently supported in _get_bins_near_point.")

    bins = []
    for d_lat, d_lon in offsets:
        bins.append((lat_idx + d_lat, lon_idx + d_lon))

    return bins

def restore_network_to_original_state(debug: bool=False):
    """
    Comprehensive function to restore the network to its original state by:
    1. Deleting all temporary vertices and edges
    2. Reattaching all detached edges
    
    This ensures the network is identical to its state before any temporary modifications.
    """
    from classes.classes import Vertex, Edge
    
    logger.debug("Restoring network to original state...")
    # Count current state for reporting
    initial_temp_vertices = Vertex.get_num_of_temporary_vertices()
    initial_temp_edges = Edge.get_num_of_temporary_edges()
    initial_detached_edges = Edge.get_num_of_detached_edges()
    if debug:
        
        print(f"  Found {initial_temp_vertices} temporary vertices to delete")
        print(f"  Found {initial_temp_edges} temporary edges to delete")
        print(f"  Found {initial_detached_edges} detached edges to reattach")
    
    # Step 1: Delete all temporary edges FIRST to avoid edges referencing soon-to-be-removed vertices
    if initial_temp_edges > 0:
        Edge.delete_all_temporary_edges()
        if debug:
            print(f"  ? Deleted {initial_temp_edges} temporary edges")

    # Step 2: Delete all temporary vertices
    if initial_temp_vertices > 0:
        Vertex.delete_all_temporary_vertices()
        if debug:
            print(f"  ? Deleted {initial_temp_vertices} temporary vertices")
    
    # Step 3: Reattach all detached edges
    # Note: restore_references_to_edge() restores vertex connections and removes from detached list
    if initial_detached_edges > 0:
        Edge.restore_all_detached_edges()
        if debug:
            print(f"  ? Reattached {initial_detached_edges} detached edges")
    
    # Verify cleanup was successful
    remaining_temp_vertices = Vertex.get_num_of_temporary_vertices()
    remaining_temp_edges = Edge.get_num_of_temporary_edges()
    remaining_detached_edges = Edge.get_num_of_detached_edges()

    if remaining_temp_vertices == 0 and remaining_temp_edges == 0 and remaining_detached_edges == 0:
        logger.debug("Network successfully restored to original state")
        return True
    else:
        logger.warning("Warning: Cleanup incomplete - some temporary elements remain")
        return False

def validate_network_integrity():
    """
    Validate the integrity of the network by checking:
    1. All edges have valid start/end vertices
    2. All vertex connections are bidirectional where expected
    3. All vertices/edges are properly registered in dictionaries
    4. Bin lookups are consistent
    """
    from classes.classes import Vertex, Edge
    
    logger.debug("Validating network integrity...")
    issues = []
    
    # Check all edges have valid vertices
    for edge in Edge.get_all_edges():
        if Vertex.check_vertex_exists(edge.start.id) is False:
            issues.append(f"Edge {edge.id} start vertex {edge.start.id} not in vertex_dict")

        if Vertex.check_vertex_exists(edge.end.id) is False:
            issues.append(f"Edge {edge.id} end   vertex {edge.end.id} not in vertex_dict")
        
        # Check vertex-edge connections are consistent
        if edge not in edge.start.onward_edges:
            issues.append(f"Edge {edge.id} missing from start vertex {edge.start.id} onward_edges")

        if edge not in edge.end.backward_edges:
            issues.append(f"Edge {edge.id} missing from end vertex {edge.end.id} backward_edges")

        # Check bidirectional edges
        if not edge.oneway:
            if edge not in edge.end.onward_edges:
                issues.append(f"Bidirectional edge {edge.id} missing from end vertex {edge.end.id} onward_edges")
            
            if edge not in edge.start.backward_edges:
                issues.append(f"Bidirectional edge {edge.id} missing from start vertex {edge.start.id} backward_edges")
    
    # Check vertex connections point to valid edges
    for vertex in Vertex.get_all_vertices():
        for edge in vertex.onward_edges.keys():
            if Edge.check_edge_exists(edge.id) is False:
                issues.append(f"Vertex {vertex.id} references non-existent edge {edge.id} in onward_edges")

        for edge in vertex.backward_edges.keys():
            if Edge.check_edge_exists(edge.id) is False:
                issues.append(f"Vertex {vertex.id} references non-existent edge {edge.id} in backward_edges")

    if issues:
        print(f"  ? Found {len(issues)} integrity issues:")
        for issue in issues:
            print(f"    - {issue}")
        return False
    else:
        print("  ? Network integrity validated successfully")
        return True

def capture_network_state():
    """
    Capture the current state of the network for comparison.
    Returns a dictionary with network statistics and structure.
    """
    from classes.classes import Vertex, Edge
    
    state = {
        'vertex_count': Vertex.get_num_of_vertices(),
        'edge_count': Edge.get_num_of_edges(),
        'vertex_ids': set(Vertex.get_all_vertices()),
        'edge_ids': set(Edge.get_all_edges()),
        'temporary_vertices': Vertex.get_num_of_temporary_vertices(),
        'temporary_edges': Edge.get_num_of_temporary_edges(),
        'detached_edges': Edge.get_num_of_detached_edges(),
        'vertex_connections': {},
        'edge_properties': {}
    }
    
    # Capture vertex connections
    for vertex in Vertex.get_all_vertices():
        state['vertex_connections'][vertex.id] = {
            'onward_edges': set(edge.id for edge in vertex.get_outward_edges()),
            'backward_edges': set(edge.id for edge in vertex.get_backward_edges())
        }
    
    # Capture edge properties
    for edge in Edge.get_all_edges():
        state['edge_properties'][edge.id] = {
            'start_vertex': edge.start.id,
            'end_vertex': edge.end.id,
            'oneway': edge.oneway,
            'length': edge.length,
            'detached': edge.detached
        }
    
    return state

def compare_network_states(state1, state2):
    """
    Compare two network states and report differences.
    Returns True if states are identical, False otherwise.
    """
    differences = []
    
    # Compare basic counts
    if state1['vertex_count'] != state2['vertex_count']:
        differences.append(f"Vertex count: {state1['vertex_count']} -> {state2['vertex_count']}")
    
    if state1['edge_count'] != state2['edge_count']:
        differences.append(f"Edge count: {state1['edge_count']} -> {state2['edge_count']}")
    
    # Compare vertex IDs
    if state1['vertex_ids'] != state2['vertex_ids']:
        added_vertices = state2['vertex_ids'] - state1['vertex_ids']
        removed_vertices = state1['vertex_ids'] - state2['vertex_ids']
        if added_vertices:
            differences.append(f"Added vertices: {added_vertices}")
        if removed_vertices:
            differences.append(f"Removed vertices: {removed_vertices}")
    
    # Compare edge IDs
    if state1['edge_ids'] != state2['edge_ids']:
        added_edges = state2['edge_ids'] - state1['edge_ids']
        removed_edges = state1['edge_ids'] - state2['edge_ids']
        if added_edges:
            differences.append(f"Added edges: {added_edges}")
        if removed_edges:
            differences.append(f"Removed edges: {removed_edges}")
    
    # Compare temporary counts
    if state1['temporary_vertices'] != state2['temporary_vertices']:
        differences.append(f"Temporary vertices: {state1['temporary_vertices']} -> {state2['temporary_vertices']}")
    
    if state1['temporary_edges'] != state2['temporary_edges']:
        differences.append(f"Temporary edges: {state1['temporary_edges']} -> {state2['temporary_edges']}")
    
    if state1['detached_edges'] != state2['detached_edges']:
        differences.append(f"Detached edges: {state1['detached_edges']} -> {state2['detached_edges']}")
    
    # Compare vertex connections (only for vertices that exist in both states)
    common_vertices = state1['vertex_ids'] & state2['vertex_ids']
    for vertex in common_vertices:
        if state1['vertex_connections'][vertex.id] != state2['vertex_connections'][vertex.id]:
            differences.append(f"Vertex {vertex.id} connections changed")
    
    # Compare edge properties (only for edges that exist in both states)
    common_edges = state1['edge_ids'] & state2['edge_ids']
    for edge in common_edges:
        if state1['edge_properties'][edge.id] != state2['edge_properties'][edge.id]:
            differences.append(f"Edge {edge.id} properties changed")

    if differences:
        print("Network state differences found:")
        for diff in differences:
            print(f"  - {diff}")
        return False
    else:
        print("Network states are identical")
        return True