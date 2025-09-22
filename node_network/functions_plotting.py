import matplotlib.pyplot as plt
from tqdm import tqdm
from classes import Vertex, Edge
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from functions_mapping import get_edges_near_coordinates


def in_largest_network(vertex, largest_network):
    return vertex in largest_network

def plot_networks(edges_binned_matrix, results=None, vertex_layers=None, highlight_lat=None, highlight_lon=None, show_densest_bin=False, cell_range=0):
    plt.figure(figsize=(12, 10))
    for edge in tqdm(Edge.edge_dict.values(), desc="Plotting edges"):
        lats = [edge.start.lat] + [lat for lat, lon in edge.non_vertex_nodes] + [edge.end.lat]
        lons = [edge.start.lon] + [lon for lat, lon in edge.non_vertex_nodes] + [edge.end.lon]
        plt.plot(lons, lats, color='black', zorder=3, linewidth=1, alpha=0.7)

    black_lats, black_lons = [], []
    for v in tqdm(Vertex.vertex_dict.values(), desc="Collecting vertices for scatter plot"):
        black_lats.append(v.lat)
        black_lons.append(v.lon)
    plt.scatter(black_lons, black_lats, c='black', s=5, zorder=3, label='Network')

    # Highlight the center and edges of the densest bin (using provided edges_binned_matrix)
    if show_densest_bin:
        max_count = 0
        max_i, max_j = 0, 0
        for i, row in enumerate(edges_binned_matrix):
            for j, cell in enumerate(row):
                if len(cell) > max_count:
                    max_count = len(cell)
                    max_i, max_j = i, j
        # Use max_i directly for latitude
        center_lat = LAT_MIN + (max_i + 0.5) * LAT_BIN_SIZE
        center_lon = LON_MIN + (max_j + 0.5) * LON_BIN_SIZE
        # Bin edges
        lat0 = LAT_MIN + max_i * LAT_BIN_SIZE
        lat1 = lat0 + LAT_BIN_SIZE
        lon0 = LON_MIN + max_j * LON_BIN_SIZE
        lon1 = lon0 + LON_BIN_SIZE
        print(f"Densest bin center: lat={center_lat}, lon={center_lon}, count={max_count}")
        print(f"Edges in densest bin: {[e.id for e in edges_binned_matrix[max_i][max_j]]}")
        plt.scatter([center_lon], [center_lat], c='blue', s=100, marker='*', zorder=10, label='Densest bin center')
        plt.plot([lon0, lon1, lon1, lon0, lon0], [lat0, lat0, lat1, lat1, lat0], c='blue', linestyle='--', linewidth=2, zorder=9, label='Densest bin edges')
        plt.legend()

    # Draw all bin borders
    n_lat_bins = int((LAT_MAX - LAT_MIN) / LAT_BIN_SIZE)
    n_lon_bins = int((LON_MAX - LON_MIN) / LON_BIN_SIZE)
    for i in range(n_lat_bins + 1):
        lat = LAT_MIN + i * LAT_BIN_SIZE
        plt.plot([LON_MIN, LON_MAX], [lat, lat], c='green', linestyle='-', linewidth=1, zorder=0)
    for j in range(n_lon_bins + 1):
        lon = LON_MIN + j * LON_BIN_SIZE
        plt.plot([lon, lon], [LAT_MIN, LAT_MAX], c='green', linestyle='-', linewidth=1, zorder=0)

    # Overlay: plot the coordinate and highlight the edges
    if highlight_lat is not None and highlight_lon is not None:
        highlight_edges = get_edges_near_coordinates(edges_binned_matrix, highlight_lat, highlight_lon, cell_range)
        plt.scatter([highlight_lon], [highlight_lat], c='magenta', s=120, marker='X', zorder=20, label='Query coordinate')
        for edge in highlight_edges:
            lats = [edge.start.lat] + [lat for lat, lon in edge.non_vertex_nodes] + [edge.end.lat]
            lons = [edge.start.lon] + [lon for lat, lon in edge.non_vertex_nodes] + [edge.end.lon]
            plt.plot(lons, lats, color='magenta', linewidth=3, alpha=0.8, zorder=19, label='Nearby edge')

    if results is not None:
        for result in results:
            lat, lon, projections = result
            plt.scatter(lon, lat, c='orange', s=8, marker='o', zorder=15)
            for proj in projections:
                edge, proj_lat, proj_lon, dist_m, seg_idx = proj
                plt.plot([lon, proj_lon], [lat, proj_lat], c='cyan', linestyle='--', linewidth=1, alpha=0.6, zorder=1)
                plt.scatter(proj_lon, proj_lat, c='cyan', s=7, marker='x', zorder=2)
        # Mark first and last points distinctly
        plt.scatter(results[0][1], results[0][0], c='green', s=10, marker='o', zorder=16, label='First point')
        plt.scatter(results[-1][1], results[-1][0], c='red', s=10, marker='o', zorder=16, label='Last point')

    if vertex_layers is not None:
        colors = ['purple', 'orange', 'brown', 'pink', 'gray']
        for layer_idx, layer in enumerate(vertex_layers):
            layer_lats = [v.lat for v in layer]
            layer_lons = [v.lon for v in layer]
            plt.scatter(layer_lons, layer_lats, c=colors[layer_idx % len(colors)], s=25, marker='^', zorder=2, label=f'Layer {layer_idx+1}')

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('OSM Graph')
    plt.legend()
    plt.grid(False)
    plt.tight_layout()
    plt.show()
