import heapq
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from classes import Vertex, Edge
from functions_analysis import get_bin_indices
import pandas as pd

def get_edges_near_coordinates(edges_binned_matrix, lat, lon, cell_range=0):
    idx = get_bin_indices(lat, lon)
    n_lat = len(edges_binned_matrix)
    n_lon = len(edges_binned_matrix[0])
    if idx is None:
        raise ValueError(f"Coordinates (lat={lat}, lon={lon}) are out of bounds for the configured bins.")
    lat_idx, lon_idx = idx
    edges = set()
    if cell_range == 0:
        lat_bin_start = LAT_MIN + lat_idx * LAT_BIN_SIZE
        lon_bin_start = LON_MIN + lon_idx * LON_BIN_SIZE
        corners = [
            (lat_bin_start, lon_bin_start),
            (lat_bin_start + LAT_BIN_SIZE, lon_bin_start),
            (lat_bin_start, lon_bin_start + LON_BIN_SIZE),
            (lat_bin_start + LAT_BIN_SIZE, lon_bin_start + LON_BIN_SIZE)
        ]
        dists = [((lat - clat)**2 + (lon - clon)**2, idx) for idx, (clat, clon) in enumerate(corners)]
        _, closest = min(dists)
        offsets = [(0,0), (1,0), (0,1), (1,1)]
        base_i, base_j = lat_idx, lon_idx
        bins = []
        for di, dj in offsets:
            i = base_i + di if base_i + di < n_lat else n_lat - 1
            j = base_j + dj if base_j + dj < n_lon else n_lon - 1
            bins.append((i, j))
        bins = set((min(max(i, 0), n_lat - 1), min(max(j, 0), n_lon - 1)) for i, j in bins)
        for i, j in bins:
            edges.update(edges_binned_matrix[i][j])
    else:
        for dlat in range(-cell_range, cell_range + 1):
            for dlon in range(-cell_range, cell_range + 1):
                i = lat_idx + dlat
                j = lon_idx + dlon
                if 0 <= i < n_lat and 0 <= j < n_lon:
                    edges.update(edges_binned_matrix[i][j])
    return list(edges)

def project_coordinates_onto_edges(edges_binned_matrix, lat, lon, cell_range, max_dist=float('inf')):
    edges = get_edges_near_coordinates(edges_binned_matrix, lat, lon, cell_range)
    projections = []
    for edge in edges:
        proj_lat, proj_lon, dist, seg_idx = edge.project_coordinates_onto_edge(lat, lon)
        if dist is not None and dist <= max_dist:
            projections.append((edge, proj_lat, proj_lon, dist, seg_idx))
    return projections

def project_trip_coordinates_onto_edges(edges_binned_matrix, trip_id, trip_file, cell_range, max_dist=float('inf')):
    df = pd.read_csv(f'cleaned_data/{trip_file}')

    if 'trip_id' in df.columns:
        group = df[df['trip_id'] == trip_id]
        lats = group['latitude']
        lons = group['longitude']

    results = []
    for lat, lon in zip(lats, lons):
        projections = project_coordinates_onto_edges(edges_binned_matrix, lat, lon, cell_range, max_dist)
        if len(projections) == 0:
            print(f"No edges found near point (lat={lat}, lon={lon})")
        results.append((lat, lon, projections))
    
    return results

def find_or_create_vertex_at_projection(proj_lat, proj_lon, vertices_binned_matrix, tolerance=1e-9):
    idx = get_bin_indices(proj_lat, proj_lon)
    if idx is None:
        return None, False
    lat_idx, lon_idx = idx
    for v in vertices_binned_matrix[lat_idx][lon_idx]:
        if abs(v.lat - proj_lat) <= tolerance and abs(v.lon - proj_lon) <= tolerance:
            return v, False
    # No existing vertex found, create new using Vertex._id_counter
    v = Vertex(None, proj_lat, proj_lon)
    vertices_binned_matrix[lat_idx][lon_idx].append(v)
    return v, True

def project_and_split_edges_with_reversibility(vertices_binned_matrix, projections, tolerance=1e-9):
    import math
    from collections import defaultdict
    changes = {'new_vertices': [], 'new_edges': [], 'removed_edges': []}
    vertex_map = {}  # (layer_idx, proj_idx) -> vertex
    # Group projections by edge
    edge_to_projs = defaultdict(list)
    for proj in projections:
        # proj = (edge, proj_lat, proj_lon, dist, seg_idx, layer_idx, proj_idx)
        edge = proj[0]
        edge_to_projs[edge].append(proj)
    # For each edge, process all splits in order
    for edge, projs in edge_to_projs.items():
        points = [(edge.start.lat, edge.start.lon)] + edge.non_vertex_nodes + [(edge.end.lat, edge.end.lon)]
        def proj_sort_key(proj):
            proj_lat, proj_lon, dist, seg_idx, layer_idx, proj_idx = proj[1:]
            seg_start = points[seg_idx]
            seg_end = points[seg_idx+1]
            seg_len = math.hypot(seg_end[0] - seg_start[0], seg_end[1] - seg_start[1])
            if seg_len == 0:
                frac = 0
            else:
                frac = math.hypot(proj_lat - seg_start[0], proj_lon - seg_start[1]) / seg_len
            return (seg_idx, frac)
        projs_sorted = sorted(projs, key=proj_sort_key)
        # Remove the original edge
        if edge.id in Edge.edge_dict:
            del Edge.edge_dict[edge.id]
            changes['removed_edges'].append(edge)
        for other_vertex in Vertex.vertex_dict.values():
            to_update = [e for e in other_vertex.neighbors if e == edge]
            for e in to_update:
                del other_vertex.neighbors[e]
        # Sequentially split the edge, chaining new vertices
        split_vertices = []
        split_indices = []
        split_ids = []
        for proj in projs_sorted:
            proj_lat, proj_lon, dist, seg_idx, layer_idx, proj_idx = proj[1:]
            v, created = find_or_create_vertex_at_projection(proj_lat, proj_lon, vertices_binned_matrix, tolerance)
            if created:
                changes['new_vertices'].append(v)
            vertex_map[(layer_idx, proj_idx)] = v
            split_vertices.append(v)
            split_indices.append(seg_idx)
            split_ids.append((layer_idx, proj_idx))
        chain_vertices = [edge.start] + split_vertices + [edge.end]
        chain_indices = [0] + split_indices + [len(points)-2]
        for i in range(len(chain_vertices)-1):
            v_start = chain_vertices[i]
            v_end = chain_vertices[i+1]
            idx_start = chain_indices[i]
            idx_end = chain_indices[i+1]
            non_vertex_nodes = []
            if idx_end > idx_start:
                non_vertex_nodes = points[idx_start+1:idx_end+1]
            # For all but the last edge, add the projection point as the last non-vertex node
            if i < len(chain_vertices)-2:
                non_vertex_nodes = [(lat, lon) for lat, lon in non_vertex_nodes]
                # Add the projection point for this split
                proj_lat, proj_lon, _, _, _, _ = projs_sorted[i][1:]
                non_vertex_nodes.append((proj_lat, proj_lon))
            else:
                # For the last edge, just add any remaining non-vertex nodes and the end vertex
                non_vertex_nodes = [(lat, lon) for lat, lon in non_vertex_nodes]
                non_vertex_nodes.append((edge.end.lat, edge.end.lon))
            new_edge = Edge(v_start, v_end, non_vertex_nodes)
            changes['new_edges'].append(new_edge)
            v_start.neighbors[new_edge] = v_end
            v_end.neighbors[new_edge] = v_start
    # Convert vertex_map to vertex_layers: list of lists, each sublist for one input point (layer_idx)
    if vertex_map:
        max_layer = max(layer_idx for (layer_idx, proj_idx) in vertex_map.keys())
        vertex_layers = [[] for _ in range(max_layer + 1)]
        for (layer_idx, proj_idx), v in vertex_map.items():
            vertex_layers[layer_idx].append((proj_idx, v))
        # Sort each layer by proj_idx to preserve input order
        for layer in vertex_layers:
            layer.sort()
        # Remove proj_idx, keep only vertices
        vertex_layers = [[v for _, v in layer] for layer in vertex_layers]
    else:
        vertex_layers = []
    return changes, vertex_layers

def apply_projection_and_splitting(vertices_binned_matrix, results, tolerance=1e-9, max_points=None):

    # Attach (layer_idx, proj_idx) to each projection
    all_projections = []
    points_considered = 0
    for layer_idx, (lat, lon, projections) in enumerate(results):
        for proj_idx, proj in enumerate(projections):
            # proj = (edge, proj_lat, proj_lon, dist, seg_idx)
            all_projections.append(proj + (layer_idx, proj_idx))
        points_considered += 1
        if max_points is not None and points_considered >= max_points:
            break
    if all_projections:
        changes, vertex_layers = project_and_split_edges_with_reversibility(vertices_binned_matrix, all_projections, tolerance)
        all_changes = [changes]
    else:
        all_changes = []
        vertex_layers = []
    return all_changes, vertex_layers

def undo_project_and_split_changes(changes):
    """
    Reverses the changes made by project_and_split_edges_with_reversibility.
    Removes new vertices and new edges, and restores removed edges.
    """
    # Remove new edges
    for edge in changes.get('new_edges', []):
        if edge.id in Edge.edge_dict:
            del Edge.edge_dict[edge.id]
        # Remove from neighbors
        if edge.start and edge in edge.start.neighbors:
            del edge.start.neighbors[edge]
        if edge.end and edge in edge.end.neighbors:
            del edge.end.neighbors[edge]
    # Remove new vertices
    for v in changes.get('new_vertices', []):
        if v.id in Vertex.vertex_dict:
            del Vertex.vertex_dict[v.id]
        # Remove from neighbors of all other vertices
        for other in Vertex.vertex_dict.values():
            to_remove = [e for e, n in other.neighbors.items() if n == v]
            for e in to_remove:
                del other.neighbors[e]
    # Restore removed edges
    for edge in changes.get('removed_edges', []):
        Edge.edge_dict[edge.id] = edge
        # Restore neighbors
        if edge.start:
            edge.start.neighbors[edge] = edge.end
        if edge.end:
            edge.end.neighbors[edge] = edge.start

def all_pairs_network_distances_between_layers(layer1, layer2):
    """
    For each vertex in layer1, compute the shortest network distance to every vertex in layer2.
    Returns a dict: {v1: {v2: dist, ...}, ...} where dist is the sum of edge.length along the shortest path.
    """
    import heapq
    results = {}
    layer2_ids = set(v.id for v in layer2)
    for v1 in layer1:
        # Dijkstra's algorithm from v1, with early stopping
        visited = set()
        found_layer2 = set()
        heap = [(0, v1)]  # (distance, vertex)
        dists = {v1.id: 0}
        while heap and len(found_layer2) < len(layer2_ids):
            dist_u, u = heapq.heappop(heap)
            if u.id in visited:
                continue
            visited.add(u.id)
            if u.id in layer2_ids:
                found_layer2.add(u.id)
            for edge, neighbor in u.neighbors.items():
                if neighbor.id not in visited:
                    alt = dist_u + edge.length
                    if alt < dists.get(neighbor.id, float('inf')):
                        dists[neighbor.id] = alt
                        heapq.heappush(heap, (alt, neighbor))
        # Collect distances to all layer2 vertices
        result_row = {}
        for v2 in layer2:
            result_row[v2] = dists.get(v2.id, float('inf'))
        results[v1] = result_row
    return results