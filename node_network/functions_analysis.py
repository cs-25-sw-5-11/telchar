from classes import Vertex, Edge
from tqdm import tqdm
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
import math

def find_networks(vertices):
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
                    stack.extend([v for v in curr.neighbors.values() if v not in visited])
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
    # Remove neighbors not in largest network
    for v in tqdm(Vertex.vertex_dict.values(), desc="Filtering neighbors"):
        v.neighbors = {e: n for e, n in v.neighbors.items() if n in largest_network and e.start in largest_network and e.end in largest_network}


def get_bin_indices(lat, lon):
    if not (LAT_MIN <= lat < LAT_MAX and LON_MIN <= lon < LON_MAX):
        return None
    lat_idx = int((lat - LAT_MIN) / LAT_BIN_SIZE)
    lon_idx = int((lon - LON_MIN) / LON_BIN_SIZE)
    return lat_idx, lon_idx

def bin_edges_by_lat_lon():
    """
    Returns a 2D matrix (list of lists) where each cell contains a list of edges that have at least one point (start, end, or non-vertex node)
    within the corresponding lat/lon bin. Points outside the configured bounds are ignored.
    """
    # Compute number of bins
    n_lat_bins = math.ceil((LAT_MAX - LAT_MIN) / LAT_BIN_SIZE)
    n_lon_bins = math.ceil((LON_MAX - LON_MIN) / LON_BIN_SIZE)
    # Initialize edges_binned_matrix
    edges_binned_matrix = [[[] for _ in range(n_lon_bins)] for _ in range(n_lat_bins)]

    for edge in tqdm(Edge.edge_dict.values(), desc="Binning edges by lat/lon"):
        points = [(edge.start.lat, edge.start.lon)] + [(lat, lon) for lat, lon, _ in edge.non_vertex_nodes] + [(edge.end.lat, edge.end.lon)]
        bins_covered = set()
        # Bin for explicit points
        for lat, lon in points:
            idx = get_bin_indices(lat, lon)
            if idx is not None:
                bins_covered.add(idx)
        # Bin for all bins the edge passes through (rasterize each segment)
        for i in range(len(points) - 1):
            lat0, lon0 = points[i]
            lat1, lon1 = points[i+1]
            idx0 = get_bin_indices(lat0, lon0)
            idx1 = get_bin_indices(lat1, lon1)
            if idx0 is None or idx1 is None:
                continue
            # DDA (Digital Differential Analyzer) grid traversal
            n_steps = max(abs(idx1[0] - idx0[0]), abs(idx1[1] - idx0[1]), 1)
            for step in range(n_steps + 1):
                frac = step / n_steps
                lat = lat0 + frac * (lat1 - lat0)
                lon = lon0 + frac * (lon1 - lon0)
                idx = get_bin_indices(lat, lon)
                if idx is not None:
                    bins_covered.add(idx)
        for lat_idx, lon_idx in bins_covered:
            edges_binned_matrix[lat_idx][lon_idx].append(edge)

    return edges_binned_matrix

def bin_vertices_by_lat_lon():
    """
    Returns a 2D matrix (list of lists) where each cell contains a list of vertices that fall within the corresponding lat/lon bin.
    Points outside the configured bounds are ignored.
    """
    # Compute number of bins
    n_lat_bins = math.ceil((LAT_MAX - LAT_MIN) / LAT_BIN_SIZE)
    n_lon_bins = math.ceil((LON_MAX - LON_MIN) / LON_BIN_SIZE)
    # Initialize vertices_binned_matrix
    vertices_binned_matrix = [[[] for _ in range(n_lon_bins)] for _ in range(n_lat_bins)]

    for v in tqdm(Vertex.vertex_dict.values(), desc="Binning vertices by lat/lon"):
        idx = get_bin_indices(v.lat, v.lon)
        if idx is not None:
            lat_idx, lon_idx = idx
            vertices_binned_matrix[lat_idx][lon_idx].append(v)

    return vertices_binned_matrix