from typing import Tuple, Set, Optional, Dict, List
from . import Edge, Vertex, Network, PointProjection
from utils.functions_misc import haversine, get_bin_indices, get_bins_near_point
import numpy as np

class Trip:
    """Represents a trip consisting of a sequence of GPS points,
    and the projections of these points onto the network."""
    
    def __init__(self, trip_id: int, 
                 lats: list[float], lons: list[float], 
                 times: list[float]):
        self.trip_id = trip_id
        self.lats = lats
        self.lons = lons
        self.times = times
        self.dummy_network = Network()
        self._point_projection_id_counter = 1
        self._point_projections: Dict[int, 'PointProjection'] = {}
        self._point_projection_bin_lookup: Dict[Tuple[int, int], List['PointProjection']] = {}
        self._projection_layers: list[list[Vertex | PointProjection]] = []

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

    def plot_trip(self, network: Network, edge_ids: list[int], vertex_ids: list[int], point_projection_ids: list[int]) -> None:
        """Plot the trip's GPS points, along with specified edges, vertices, and point projections."""
        import matplotlib.pyplot as plt

        # Plot GPS points
        plt.plot(self.lons, self.lats, 'o-', color='blue', label='GPS Points')

        # Plot edges, but each edge in a different color
        color_map = ['r', 'g', 'm', 'c', 'y', 'k']
        for i, edge_id in enumerate(edge_ids):
            edge = network.get_edge_by_id(edge_id)
            if edge is not None:
                edge_lats = [node[0] for node in edge.get_all_nodes()]
                edge_lons = [node[1] for node in edge.get_all_nodes()]
                plt.plot(edge_lons, edge_lats, '-', color=color_map[i % len(color_map)], label=f'Edge {edge_id}')

        # Plot vertices
        for vertex_id in vertex_ids:
            vertex = network.get_vertex_by_id(vertex_id)
            if vertex is not None:
                plt.plot(vertex.lon, vertex.lat, 's', color='red', label=f'Vertex {vertex_id}')

        # Plot point projections
        for pp_id in point_projection_ids:
            pp = next((pp for pp in self._point_projections if pp.id == pp_id), None)
            if pp is not None:
                plt.plot(pp.lon, pp.lat, 'x', color='orange', label=f'PointProjection {pp_id}')

        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.title(f'Trip {self.trip_id} Visualization')
        plt.legend()
        plt.show()

    def _project_trip_point(self, network: Network, 
                            lat: float, lon: float, 
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
        nearby_edges = network.get_edges_near_coordinate(lat, lon)
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
                    print("Found existing projection:", existing_projection)
                    print("Current values: ", proj_lat, proj_lon, edge.id, seg_idx, seg_t)
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
    
    def _project_trip_onto_network(self, network: Network, max_dist: float) -> None:
        """Project the trip's GPS points onto the given network, storing the resulting projections and vertices
        (where a vertex is used if one exists where a projection would have been) as layers, with each layer
        corresponding to projections at one point in the trip."""
        for lat, lon in zip(self.lats, self.lons):
            new_projection_layers = self._project_trip_point(network, lat, lon, max_dist)
            self._projection_layers.append(new_projection_layers)

    def compute_layer_distances(self, network: Network, max_dist: float=100) -> None:
        """Compute the distance matrix between each layer of projections/vertices
        for the trip, returning a dictionary where each key is a layer index,
        and each value is another dictionary mapping projection IDs to their distances."""
        self._project_trip_onto_network(network, max_dist)

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
                            distance = network.get_distance(current_projection, next_projection)
                        elif type(next_projection) is PointProjection:
                            distance = next_projection.get_distance_from_vertex(network, current_projection)
                        else:
                            raise ValueError("Unknown projection types.")
                    elif type(current_projection) is PointProjection:
                        if type(next_projection) is Vertex:
                            distance = current_projection.get_distance_to_vertex(network, next_projection)
                        elif type(current_projection) is PointProjection and type(next_projection) is PointProjection:
                            distance = current_projection.get_distance_between_projections(network, next_projection)
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

