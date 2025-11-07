from typing import Tuple, Set, Optional, Dict, List
from . import Edge, Vertex, Network, PointProjection
from utils.functions_misc import haversine, get_bin_indices, get_bins_near_point, get_time_index
import numpy as np
import logging

logger = logging.getLogger(__name__)

class Trip:
    """Represents a trip consisting of a sequence of GPS points,
    and the projections of these points onto the network."""
    
    def __init__(self, network: Network, 
                 trip_id: int, 
                 lats: list[float], lons: list[float], 
                 times: list[float]):
        self.trip_id = trip_id
        self.lats = lats
        self.lons = lons
        self.times = times
        self.network = network
        self._point_projection_id_counter = 1
        self._point_projections: Dict[int, 'PointProjection'] = {}
        self._point_projection_bin_lookup: Dict[Tuple[int, int], List['PointProjection']] = {}
        self._projection_layers: list[list[Vertex | PointProjection]] = []

    def process_and_apply_best_path(self, best_path: list[int], times: list[float], time_interval: int) -> None:
        if len(best_path) < 2:
            return

        for i in range(len(best_path)-1):
            dist, edges = self.find_shortest_edge_path(start_item_id = best_path[i], end_item_id = best_path[i+1])
            speed = dist / (times[i+1] - times[i])  # m/s
            print("printing speed of best path:", speed)
            time_index = get_time_index(timestamp=times[i], reference=0, interval=time_interval)
            self.apply_speed_to_edges(edges, time_index, speed)
            if i == 1:
            for projection_id in [3, 13]:
                projection = self.get_point_projection_by_id(projection_id)
                edge = projection.parent_edge
                start = edge.start
                end = edge.end
                print(f'Edge oneway? {edge.oneway}')
                print(f'Distance from {start.id} to {end.id}: {self.network.get_distance(start, end)} meters')
                print(f'Distance from {end.id} to {start.id}: {self.network.get_distance(end, start)} meters')

    def get_id_max(self) -> int:
        """Get the maximum ID used in this trip (for vertices and point projections)."""
        return self._point_projection_id_counter - 1
    
    def add_point_projection(self, point_projection: PointProjection) -> None:
        """Add a point projection to this trip's collection."""
        self._point_projections[point_projection.id] = point_projection

    def get_point_projection_by_id(self, point_projection_id: int) -> Optional[PointProjection]:
        """Get the point projection with the given ID, if it exists."""
        return self._point_projections.get(point_projection_id, None)

    def get_next_point_projection_id(self) -> int:
        """Get the next available point projection ID for this trip."""
        point_projection_id = self._point_projection_id_counter
        self._point_projection_id_counter += 1
        return point_projection_id

    def plot_trip(self, edge_ids: list[int], vertex_ids: list[int], point_projection_ids: list[int]) -> None:
        """Plot the trip's GPS points, along with specified edges, vertices, and point projections."""
        import matplotlib.pyplot as plt

        # Plot GPS points
        plt.plot(self.lons, self.lats, 'o-', color='blue', label='GPS Points')

        # Plot edges, but each edge in a different color
        color_map = ['r', 'g', 'm', 'c', 'y', 'k']
        for i, edge_id in enumerate(edge_ids):
            edge = self.network.get_edge_by_id(edge_id)
            if edge is not None:
                edge_lats = [node[0] for node in edge.get_all_nodes()]
                edge_lons = [node[1] for node in edge.get_all_nodes()]
                plt.plot(edge_lons, edge_lats, '-', color=color_map[i % len(color_map)], label=f'Edge {edge_id}')

        # Plot vertices
        for vertex_id in vertex_ids:
            vertex = self.network.get_vertex_by_id(vertex_id)
            if vertex is not None:
                plt.plot(vertex.lon, vertex.lat, 's', color='red', label=f'Vertex {vertex_id}')

        # Plot point projections
        for pp_id in point_projection_ids:
            pp = self.get_point_projection_by_id(pp_id)
            if pp is not None:
                plt.plot(pp.lon, pp.lat, 'x', color='orange', label=f'PointProjection {pp_id}')

        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.title(f'Trip {self.trip_id} Visualization')
        plt.legend()
        plt.show()

    def _project_trip_point(self, lat: float, lon: float, 
                            max_dist: float) -> set[Edge]:
        """Projects a single GPS point onto nearby edges in the network,
        returning a set of vertices.
        If an edge projection does not already have a vertex at the projected point,
        a temporary vertex is created.
        Furthermore, all existing temporary vertices are evaluated and added to the
        set, if it is within range."""
        projection_layer: set[Vertex | PointProjection] = set()

        # Get nearby edges and determine valid projections onto them.
        valid_projections = []
        nearby_edges = self.network.get_edges_near_coordinate(lat, lon)
        for edge in nearby_edges:
            proj_lat, proj_lon, dist_m, seg_idx, seg_t = edge.project_coordinates_onto_edge(lat, lon)        

            if dist_m is not None and dist_m <= max_dist:
                valid_projections.append((edge, proj_lat, proj_lon, dist_m, seg_idx, seg_t))

        for valid_projection in valid_projections:
            edge, proj_lat, proj_lon, dist_m, seg_idx, seg_t = valid_projection
            # If seg_t is 0 or 1, the projection may be on an existing vertex.
            if seg_t == 0.0 and seg_idx == 0:
                projection_layer.add(edge.start)
                continue
            if seg_t == 1.0 and seg_idx == len(edge.non_vertex_nodes):
                projection_layer.add(edge.end)
                continue

            # Check if a projection already exists here.
            idx = get_bin_indices(proj_lat, proj_lon)
            existing_projections = self._point_projection_bin_lookup[idx] if idx in self._point_projection_bin_lookup else []
            existing_projection_found=False
            for existing_projection in existing_projections:
                if (abs(existing_projection.lat - proj_lat) < 1e-9 and
                    abs(existing_projection.lon - proj_lon) < 1e-9 and 
                    existing_projection.parent_edge.id == edge.id):
                    logger.debug("Found existing projection:", existing_projection)
                    logger.debug("Current values: ", proj_lat, proj_lon, edge.id, seg_idx, seg_t)
                    # Found an existing projection matching this one.
                    if existing_projection not in projection_layer:
                        projection_layer.add(existing_projection)
                    existing_projection_found = True
                    break

            if existing_projection_found:
                continue

            # Otherwise, make a point projection.
            point_projection = PointProjection(self, edge, proj_lat, proj_lon, seg_idx, seg_t)
            # Add it to layer
            projection_layer.add(point_projection)
            # And to point projection bin lookup
            if idx not in self._point_projection_bin_lookup:
                self._point_projection_bin_lookup[idx] = []
            if point_projection not in self._point_projection_bin_lookup[idx]:
                self._point_projection_bin_lookup[idx].append(point_projection)

        # Add prior projections if they are within range of the trip point.
        # Only examine projections in nearby bins for efficiency.
        nearby_bins = get_bins_near_point(lat, lon, range=0)
        for bin in nearby_bins:
            if bin not in self._point_projection_bin_lookup:
                continue
            for prior_projection in self._point_projection_bin_lookup[bin]:
                dist_to_prior_projection = haversine(lat, lon, prior_projection.lat, prior_projection.lon)
                if dist_to_prior_projection <= max_dist:
                    projection_layer.add(prior_projection)

        return projection_layer
    
    def _project_trip_onto_network(self, max_dist: float) -> None:
        """Project the trip's GPS points onto the given network, storing the resulting projections and vertices
        (where a vertex is used if one exists where a projection would have been) as layers, with each layer
        corresponding to projections at one point in the trip."""
        for lat, lon in zip(self.lats, self.lons):
            new_projection_layers = self._project_trip_point(lat, lon, max_dist)
            self._projection_layers.append(new_projection_layers)

    def compute_layer_distances(self, max_dist: float=100) -> None:
        """Compute the distance matrix between each layer of projections/vertices
        for the trip, returning a dictionary where each key is a layer index,
        and each value is another dictionary mapping projection IDs to their distances."""
        self._project_trip_onto_network(max_dist)

        result_dict = {}
        for i in range(len(self._projection_layers) - 1):
            current_layer = self._projection_layers[i]
            next_layer = self._projection_layers[i + 1]
            layer_distances = {}

            for current_projection in current_layer:
                distances = {}
                for next_projection in next_layer:
                    if type(current_projection) is Vertex:
                        if type(next_projection) is Vertex:
                            distance = self.network.get_distance(current_projection, next_projection)
                        elif type(next_projection) is PointProjection:
                            distance = next_projection.get_distance_from_vertex(self.network, current_projection)
                        else:
                            raise ValueError("Unknown projection types.")
                    elif type(current_projection) is PointProjection:
                        if type(next_projection) is Vertex:
                            distance = current_projection.get_distance_to_vertex(self.network, next_projection)
                        elif type(current_projection) is PointProjection and type(next_projection) is PointProjection:
                            distance = current_projection.get_distance_between_projections(self.network, next_projection)
                        else:
                            raise ValueError("Unknown projection types.")
                    else:
                        raise ValueError("Unknown projection types.")
                    
                    if distance is None:
                        distance = np.iinfo(np.int32).max # Used to represent unreachable.
                    
                    distances[next_projection.id] = distance
                layer_distances[current_projection.id] = distances
            result_dict[i] = layer_distances

        return result_dict
    
    def apply_speed_to_edges(self, edges: list[Edge], time_index: int, speed: float) -> None:
        """Apply a speed to the given edges, updating their travel time statistics."""
        for edge in edges:
            edge.traversals_data_update(time_index, speed)
    
    def find_shortest_edge_path(self, start_item_id: int, end_item_id: int) -> Tuple[float, list[Edge]]:
        """Find the shortest path between a projections/vertices and a specific vertex in the network or a projection,
        returning the total distance and the list of edges in the path."""
        # Trivial case: start and end are the same.
        if start_item_id == end_item_id:
            return (0.0, [])
        
        # Determine if the item is a PointProjection or Vertex.
        # Vertices will have IDs with 10 or more digits, while PointProjections have smaller IDs.
        if start_item_id <= self.get_id_max():
            start = self.get_point_projection_by_id(start_item_id)
        else:
            start = self.network.get_vertex_by_id(start_item_id)

        if end_item_id <= self.get_id_max():
            end = self.get_point_projection_by_id(end_item_id)
        else:
            end = self.network.get_vertex_by_id(end_item_id)


        # Simple case: end is a vertex, simply run find_shortest_edge_path_to_vertex.
        if isinstance(end, Vertex):
            return self._find_shortest_edge_path_to_vertex(start, end)
        
        # Otherwise, end is a PointProjection. Start by checking whether the parent edge is oneway.
        # If it is oneway, we can only reach it from the start vertex.
        if end.parent_edge.oneway:
            dist, edges = self._find_shortest_edge_path_to_vertex(start, end.backward_vertex)
            dist += end.backward_vertex_dist
            edges.append(end.parent_edge)
            return (dist, edges)

        # Otherwise, it can be reached from both onward and backward vertices. Compute both paths and take the shorter one.
        dist_to_backward, edges_to_backward = self._find_shortest_edge_path_to_vertex(start, end.backward_vertex)
        dist_to_onward, edges_to_onward = self._find_shortest_edge_path_to_vertex(start, end.onward_vertex)
        if (dist_to_backward + end.backward_vertex_dist) <= (dist_to_onward + end.onward_vertex_dist):
            edges_to_backward.append(end.parent_edge)
            return (dist_to_backward, edges_to_backward)
        else:
            edges_to_onward.append(end.parent_edge)
            return (dist_to_onward, edges_to_onward)

    def _find_shortest_edge_path_to_vertex(self, start: Vertex | PointProjection, end: Vertex) -> Tuple[float, list[Edge]]:
        """Find the shortest path between a projections/vertices and a specific vertex in the network,
        returning the total distance and the list of edges in the path."""
        # A* search for shortest path finding, using Haversine distance as heuristic.
        import heapq
        
        # Handle same start and end
        if start.id == end.id:
            return (0.0, [])
        
        # Priority queue: (f_score, g_score, current_node, path_edges)
        # f_score = g_score + heuristic
        open_set = []

        # If start is PointProjection, add the connected vertices as initial nodes
        if isinstance(start, PointProjection):
            # Move forward to end vertex
            neighbor = start.onward_vertex
            edge_cost = start.onward_vertex_dist
            heuristic = haversine(neighbor.lat, neighbor.lon, end.lat, end.lon)
            f_score = edge_cost + heuristic
            heapq.heappush(open_set, (f_score, edge_cost, neighbor, [start.parent_edge]))
            
            # Move backward to start vertex (if edge allows)
            if not start.parent_edge.oneway:
                neighbor = start.backward_vertex
                edge_cost = start.backward_vertex_dist
                heuristic = haversine(neighbor.lat, neighbor.lon, end.lat, end.lon)
                f_score = edge_cost + heuristic
                heapq.heappush(open_set, (f_score, edge_cost, neighbor, [start.parent_edge]))
        else: 
            heapq.heappush(open_set, (0.0, 0.0, start, []))

        # Track visited nodes and their best g_scores
        visited = set()
        g_scores = {start.id: 0.0}
        
        while open_set:
            f_score, g_score, current, path_edges = heapq.heappop(open_set)
            
            # Skip if we've already processed this node with a better score
            if current.id in visited:
                continue
            visited.add(current.id)
            
            # Check if we reached the destination
            if current.id == end.id:
                return (g_score, path_edges)

            # Explore neighbors
            neighbors = []
            
            if isinstance(current, Vertex):
                # For vertices, explore all outward edges
                for edge in current.get_outward_edges():
                    neighbor = edge.end
                    edge_cost = edge.length
                    neighbors.append((neighbor, edge_cost, edge))

                # For bidirectional edges, also explore backward edges
                for edge in current.get_backward_edges():
                    if not edge.oneway:
                        neighbor = edge.start
                        edge_cost = edge.length
                        neighbors.append((neighbor, edge_cost, edge))
            else:
                raise ValueError("Current node should be a vertex.")
               
            # Process each neighbor
            for neighbor, edge_cost, edge in neighbors:
                if neighbor.id in visited:
                    continue
                    
                tentative_g_score = g_score + edge_cost
                
                # Skip if we've found a better path to this neighbor
                if neighbor.id in g_scores and tentative_g_score >= g_scores[neighbor.id]:
                    continue
                
                g_scores[neighbor.id] = tentative_g_score
                
                # Calculate heuristic (straight-line distance to goal)
                heuristic = haversine(neighbor.lat, neighbor.lon, end.lat, end.lon)
                f_score = tentative_g_score + heuristic
                
                # Add to open set
                new_path = path_edges + [edge]
                heapq.heappush(open_set, (f_score, tentative_g_score, neighbor, new_path))
        
        # No path found
        return (float('inf'), [])
