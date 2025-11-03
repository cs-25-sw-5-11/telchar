from . import Edge, Network, Vertex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .trip import Trip

class PointProjection:
    """Represents a projected point on an edge."""
    def __init__(self, trip: 'Trip', parent_edge: 'Edge', lat: float, lon: float, seg_idx: int, seg_t: float):
        self.lat = lat
        self.lon = lon
        self.parent_edge = parent_edge
        self.seg_idx = seg_idx
        self.seg_t = seg_t

        # Get ID from trip
        self.id = trip.get_next_point_projection_id()

        self.onward_vertex = parent_edge.end
        self.backward_vertex = parent_edge.start
        self.backward_vertex_dist: float = self.parent_edge.get_projection_distance_from_start(self.seg_idx, self.seg_t)
        self.onward_vertex_dist: float = self.parent_edge.length - self.backward_vertex_dist

    def get_distance_between_projections(self, network: Network, second_projection: 'PointProjection') -> float:
        """Get the distance in meters between this projection and another projection,
        possibly via the network if they do not share the same parent edge."""
        
        if self.id == second_projection.id:
            return 0.0

        if self.parent_edge == second_projection.parent_edge:
            return self.get_distance_between_projections_sharing_edge(second_projection)
        
        min_dist = float('inf')
        for first_vertex in [self.onward_vertex, self.backward_vertex]:
            distance_to_first_vertex = (self.onward_vertex_dist 
                                        if first_vertex == self.onward_vertex
                                        else self.backward_vertex_dist)
            for second_vertex in [second_projection.onward_vertex, second_projection.backward_vertex]:
                distance_to_second_vertex = (second_projection.onward_vertex_dist 
                                             if second_vertex == second_projection.onward_vertex
                                             else second_projection.backward_vertex_dist)
                dist = network.get_distance(first_vertex, second_vertex)
                min_dist = min(min_dist, dist + distance_to_first_vertex + distance_to_second_vertex)

        return min_dist if min_dist != float('inf') else None

    def get_distance_between_projections_sharing_edge(self, second_projection: 'PointProjection') -> float | None:
        """Get the distance in meters between this projection and another projection
        that shares the same parent edge.
        Will go from the first point to the second point. This means that if the
        edge is oneway and the second projection is before the first projection,
        it is not possible to reach the second projection without leaving the edge.
        In this case, the distance will be returned as None."""
        if self.parent_edge != second_projection.parent_edge:
            raise ValueError("Projections do not share the same parent edge.")

        if self.parent_edge.oneway:
            if self.backward_vertex_dist < second_projection.backward_vertex_dist:
                return second_projection.backward_vertex_dist - self.backward_vertex_dist
            else:
                return None
        else:
            return abs(self.backward_vertex_dist - second_projection.backward_vertex_dist)
        
    def get_distance_to_vertex(self, network: Network, target_vertex: Vertex) -> float:
        """Get the distance in meters from this projection to the given vertex."""
        if self.parent_edge.oneway:
            return network.get_distance(self.onward_vertex, target_vertex) + self.onward_vertex_dist

        else:
            return min(
                network.get_distance(self.onward_vertex, target_vertex) + self.onward_vertex_dist,
                network.get_distance(self.backward_vertex, target_vertex) + self.backward_vertex_dist
            )
        
    def get_distance_from_vertex(self, network: Network, source_vertex: Vertex) -> float:
        """Get the distance in meters from the given vertex to this projection."""
        if self.parent_edge.oneway:
            return network.get_distance(source_vertex, self.backward_vertex) + self.backward_vertex_dist

        else:
            return min(
                network.get_distance(source_vertex, self.backward_vertex) + self.backward_vertex_dist,
                network.get_distance(source_vertex, self.onward_vertex) + self.onward_vertex_dist
            )

    def __repr__(self) -> str:
        return f"PointProjection(lat={self.lat}, lon={self.lon}, edge_id={self.parent_edge.id}, seg_idx={self.seg_idx}, seg_t={self.seg_t})"
    
    def __str__(self) -> str:
        return self.__repr__()