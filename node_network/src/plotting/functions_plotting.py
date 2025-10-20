import matplotlib.pyplot as plt
from tqdm import tqdm
from classes.classes import Vertex, Edge
from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from graph_mapping.functions_mapping import get_edges_near_coordinates
from utils.functions_misc import get_bin_indices


def in_largest_network(vertex, largest_network):
    return vertex in largest_network

def plot_networks(results=None, vertex_layers=None, highlight_lat=None, highlight_lon=None, show_densest_bin=False, cell_range=0):
    plt.figure(figsize=(12, 10))
    for edge in tqdm(Edge.get_all_edges(), desc="Plotting edges"):
        lats = [edge.start.lat] + [lat for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lat]
        lons = [edge.start.lon] + [lon for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lon]
        plt.plot(lons, lats, color='black', zorder=3, linewidth=1, alpha=0.7)

    black_lats, black_lons = [], []
    for vertex in tqdm(Vertex.get_all_vertices(), desc="Collecting vertices for scatter plot"):
        black_lats.append(vertex.lat)
        black_lons.append(vertex.lon)
    plt.scatter(black_lons, black_lats, c='black', s=5, zorder=3, label='Network')

    # Highlight the center and edges of the densest bin (using class-based system)
    if show_densest_bin:
        max_count = 0
        max_i, max_j = 0, 0
        # Search through the class-based bin lookup to find densest bin
        for (i, j), edges_in_bin in Edge._bin_lookup.items():
            if len(edges_in_bin) > max_count:
                max_count = len(edges_in_bin)
                max_i, max_j = i, j
        
        if max_count > 0:
            # Use max_i directly for latitude
            center_lat = LAT_MIN + (max_i + 0.5) * LAT_BIN_SIZE
            center_lon = LON_MIN + (max_j + 0.5) * LON_BIN_SIZE
            # Bin edges
            lat0 = LAT_MIN + max_i * LAT_BIN_SIZE
            lat1 = lat0 + LAT_BIN_SIZE
            lon0 = LON_MIN + max_j * LON_BIN_SIZE
            lon1 = lon0 + LON_BIN_SIZE
            print(f"Densest bin center: lat={center_lat}, lon={center_lon}, count={max_count}")
            print(f"Edges in densest bin: {[e.id for e in Edge._bin_lookup[(max_i, max_j)]]}")
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

    if highlight_lat is not None and highlight_lon is not None:
        highlight_edges = get_edges_near_coordinates(highlight_lat, highlight_lon, cell_range)
        plt.scatter([highlight_lon], [highlight_lat], c='magenta', s=120, marker='X', zorder=20, label='Query coordinate')
        for edge in highlight_edges:
            lats = [edge.start.lat] + [lat for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lat]
            lons = [edge.start.lon] + [lon for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lon]
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

def plot_directed_graph(lat_min=None, lat_max=None, lon_min=None, lon_max=None, 
                        trip_point_lats=None, trip_point_lons=None, max_dist=None,
                        best_path_vertex_coords=None, show_ID_labels=False):
    """
    Plot the directed graph with optional geographic filtering using spatial bins for efficiency.
    
    Parameters:
    lat_min, lat_max: float, optional - Latitude range to plot
    lon_min, lon_max: float, optional - Longitude range to plot
    """
    plt.figure(figsize=(12, 10))
    
    def is_in_bounds(lat, lon):
        """Check if a point is within the specified bounds"""
        if lat_min is not None and lat < lat_min:
            return False
        if lat_max is not None and lat > lat_max:
            return False
        if lon_min is not None and lon < lon_min:
            return False
        if lon_max is not None and lon > lon_max:
            return False
        return True
    
    def add_direction_arrows(edge, lats, lons, meters_per_arrow=100, max_arrows=10):
        """Add directional arrows to a one-way edge"""
        if not edge.oneway or len(lats) <= 1:
            return
            
        # Calculate number of arrows based on edge length (1 arrow per 100m)
        edge_length_m = edge.length  # Edge already has length calculated in meters
        num_arrows = max(1, int(edge_length_m / meters_per_arrow))  # At least 1 arrow, 1 per 100m
        num_arrows = min(num_arrows, max_arrows)  # Cap at 10 arrows to avoid clutter

        # Create evenly spaced arrows along the edge
        for i in range(num_arrows):
            # Calculate position along the edge (0.0 to 1.0)
            if num_arrows == 1:
                position = 0.5  # Single arrow at middle
            else:
                # Multiple arrows: spread evenly, avoiding very start and end
                position = 0.1 + (i / (num_arrows - 1)) * 0.8  # Spread between 10% and 90%
            
            # Find the coordinates at this position along the edge
            total_segments = len(lats) - 1
            target_segment_float = position * total_segments
            segment_idx = int(target_segment_float)
            segment_progress = target_segment_float - segment_idx
            
            # Ensure we don't go out of bounds
            if segment_idx >= total_segments:
                segment_idx = total_segments - 1
                segment_progress = 1.0
            
            # Interpolate position within the segment
            start_lat, start_lon = lats[segment_idx], lons[segment_idx]
            end_lat, end_lon = lats[segment_idx + 1], lons[segment_idx + 1]
            
            # Arrow position
            arrow_lat = start_lat + segment_progress * (end_lat - start_lat)
            arrow_lon = start_lon + segment_progress * (end_lon - start_lon)
            
            # Arrow direction (shortened for better appearance)
            dx = (end_lon - start_lon) * 0.05  # Shorter arrows
            dy = (end_lat - start_lat) * 0.05
            
            # Place arrow
            plt.annotate('', xy=(arrow_lon + dx, arrow_lat + dy), 
                       xytext=(arrow_lon - dx, arrow_lat - dy),
                       arrowprops=dict(arrowstyle='->', color='red', lw=1.2, alpha=0.7),
                       zorder=4)
    
    def get_relevant_vertex_bins():
        """Get vertex bins that intersect with the specified bounds"""
        if all(bound is None for bound in [lat_min, lat_max, lon_min, lon_max]):
            # No filtering - return all vertex bins
            return set(Vertex._bin_lookup.keys())
        
        relevant_bins = set()
        
        # Calculate bin ranges that intersect the bounds
        if lat_min is not None:
            min_lat_bin = max(0, int((lat_min - LAT_MIN) / LAT_BIN_SIZE))
        else:
            min_lat_bin = 0
            
        if lat_max is not None:
            max_lat_bin = min(int((LAT_MAX - LAT_MIN) / LAT_BIN_SIZE), int((lat_max - LAT_MIN) / LAT_BIN_SIZE) + 1)
        else:
            max_lat_bin = int((LAT_MAX - LAT_MIN) / LAT_BIN_SIZE) + 1
            
        if lon_min is not None:
            min_lon_bin = max(0, int((lon_min - LON_MIN) / LON_BIN_SIZE))
        else:
            min_lon_bin = 0
            
        if lon_max is not None:
            max_lon_bin = min(int((LON_MAX - LON_MIN) / LON_BIN_SIZE), int((lon_max - LON_MIN) / LON_BIN_SIZE) + 1)
        else:
            max_lon_bin = int((LON_MAX - LON_MIN) / LON_BIN_SIZE) + 1
        
        # Collect all vertex bins in the range
        for lat_bin in range(min_lat_bin, max_lat_bin):
            for lon_bin in range(min_lon_bin, max_lon_bin):
                if (lat_bin, lon_bin) in Vertex._bin_lookup:
                    relevant_bins.add((lat_bin, lon_bin))
        
        return relevant_bins
    
    # Get vertices from relevant bins, then collect their connected edges
    relevant_bins = get_relevant_vertex_bins()
    vertices_to_plot = set()
    
    for bin_coord in relevant_bins:
        vertices_to_plot.update(Vertex._bin_lookup[bin_coord])
    
    # Collect all edges connected to vertices in relevant bins
    edges_to_plot = set()
    for vertex in vertices_to_plot:
        # Add all edges connected to this vertex (both onward and backward)
        edges_to_plot.update(vertex.onward_edges.keys())
        edges_to_plot.update(vertex.backward_edges.keys())
    
    print(f"Found {len(vertices_to_plot)} vertices in {len(relevant_bins)} relevant bins")
    print(f"Plotting {len(edges_to_plot)} edges connected to those vertices (instead of {Edge.get_num_of_edges()} total edges)")
        
    for edge in tqdm(edges_to_plot, desc="Plotting edges"):
        lats = [edge.start.lat] + [lat for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lat]
        lons = [edge.start.lon] + [lon for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lon]
        
        if edge.oneway:
            color = 'red'
        else:
            color = 'black'
        plt.plot(lons, lats, color=color, zorder=3, linewidth=1, alpha=0.7)
        
        # Add directional arrows for one-way edges
        add_direction_arrows(edge, lats, lons, meters_per_arrow=100, max_arrows=10)
        
        if edge.oneway:
            # Add edge ID label at the middle of the edge
            if len(lats) == 2:
                # Simple edge - use geometric midpoint
                label_x = (lons[0] + lons[1]) / 2
                label_y = (lats[0] + lats[1]) / 2
            else:
                # Complex edge - use middle segment
                mid_idx = len(lats) // 2
                label_x = lons[mid_idx]
                label_y = lats[mid_idx]

            if show_ID_labels:
                plt.text(label_x, label_y, str(edge.id), fontsize=6, ha='center', va='center',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7),
                        zorder=5)
                

    # Plot vertices (vertices_to_plot was already collected above)
    black_lats, black_lons = [], []
    for v in tqdm(vertices_to_plot, desc="Collecting vertices for scatter plot"):
        # Skip vertices outside the specified bounds
        if not is_in_bounds(v.lat, v.lon):
            continue
            
        black_lats.append(v.lat)
        black_lons.append(v.lon)
        
        if show_ID_labels:
            plt.text(v.lon, v.lat, str(v.id), fontsize=6, ha='left', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='lightblue', alpha=0.7),
                    zorder=5)
    
    plt.scatter(black_lons, black_lats, c='black', s=5, zorder=3, label='Network')

    for edge in tqdm(edges_to_plot, desc="Highlighting best path edges"):
        if not edge.highlighted:
            continue

        lats = [edge.start.lat] + [lat for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lat]
        lons = [edge.start.lon] + [lon for lat, lon, id in edge.non_vertex_nodes] + [edge.end.lon]
        
        plt.plot(lons, lats, color='blue', zorder=3, linewidth=1, alpha=0.7)

    if best_path_vertex_coords is not None and len(best_path_vertex_coords) >= 2:
        for i, best_path_vertex in enumerate(best_path_vertex_coords):
            plt.scatter(best_path_vertex[1], best_path_vertex[0], marker='x', color='green', s=25, zorder=10)
            plt.text(best_path_vertex[1], best_path_vertex[0], str(i+1), fontsize=8, ha='right', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='green', alpha=0.7),
                    zorder=11)

    if trip_point_lats is not None and trip_point_lons is not None:
        plt.scatter(trip_point_lons, trip_point_lats, color='orange', s=10, zorder=13)
        for i in range(len(trip_point_lats)):
            plt.text(trip_point_lons[i], trip_point_lats[i], f'Point {i+1}', fontsize=8, ha='right', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='orange', alpha=0.7),
                    zorder=12)
        # Plot circle corresponding to max_dist around each trip point
        if max_dist is not None and max_dist > 0:
            for lat, lon in zip(trip_point_lats, trip_point_lons):
                circle = plt.Circle((lon, lat), max_dist / 111320, color='orange', fill=False, linestyle='--', alpha=0.5, zorder=11)
                plt.gca().add_artist(circle)

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('OSM Graph, directed')
    plt.grid(False)
    plt.tight_layout()
    plt.show()
