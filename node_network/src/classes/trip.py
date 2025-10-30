from . import Edge, Vertex, Network, PointProjection
from utils.functions_misc import haversine

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
        self._point_projections: set[PointProjection] = set()
        self._projection_layers: list[list[Vertex | PointProjection]] = []

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

            # Otherwise, make a point projection.
            point_projection = PointProjection(edge, proj_lat, proj_lon, seg_idx, seg_t)
            self._point_projections.add(point_projection)
            projection_layer.add(point_projection)

        # Add prior projections if they are within range of the trip point.
        for prior_projection in self._point_projections:
            dist_to_prior_projection = haversine(lat, lon, prior_projection.lat, prior_projection.lon)
            if dist_to_prior_projection <= max_dist:
                projection_layer.add(prior_projection)

        return projection_layer
    
    def _project_trip_onto_network(self, network: Network, max_dist: float) -> None:
        """Project the trip's GPS points onto the given network,
        storing the resulting vertices."""
        for lat, lon in zip(self.lats, self.lons):
            print(lat, lon)
            new_projection_layers = self._project_trip_point(network, lat, lon, max_dist)
            self._projection_layers.append(new_projection_layers)

    def compute_layer_distances(self, network: Network, max_dist: float=100) -> None:
        print("Projecting trip onto network...")
        self._project_trip_onto_network(network, max_dist)

        result_dict = {}
        for i in range(len(self._projection_layers) - 1):
            current_layer = self._projection_layers[i]
            next_layer = self._projection_layers[i + 1]
            layer_distances = {}

            for current_projection in current_layer:
                distances = {}
                for next_projection in next_layer:
                    if type(current_projection) is Vertex and type(next_projection) is Vertex:
                        distance = network.get_distance(current_projection, next_projection)
                    elif type(current_projection) is Vertex and type(next_projection) is PointProjection:
                        distance = next_projection.get_distance_from_vertex(network, current_projection)
                    elif type(current_projection) is PointProjection and type(next_projection) is Vertex:
                        distance = current_projection.get_distance_to_vertex(network, next_projection)
                    elif type(current_projection) is PointProjection and type(next_projection) is PointProjection:
                        distance = current_projection.get_distance_between_projections(network, next_projection)
                    else:
                        raise ValueError("Unknown projection types.")
                    
                    distances[next_projection.id] = distance
                layer_distances[current_projection.id] = distances
            result_dict[i] = layer_distances

        return result_dict

