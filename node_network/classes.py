from typing import Tuple
from functions_misc import haversine
from math import sqrt

class Vertex:
    vertex_dict = {}  # Class-level dictionary: node_id -> Vertex object
    _id_counter = 1   # Class-level counter for unique Vertex IDs

    def __new__(cls, lat: float, lon: float, node_id: int = None):
        # If node_id is provided and already exists, return existing vertex
        if node_id is not None and node_id in cls.vertex_dict:
            return cls.vertex_dict[node_id]
        
        # Otherwise, create a new instance
        return super().__new__(cls)

    def __init__(self, lat: float, lon: float, node_id: int = None):
        # Skip initialization if this is an existing vertex
        if hasattr(self, 'id'):
            return
            
        if node_id is None:
            self.id = Vertex._id_counter
            Vertex._id_counter += 1
        else:
            self.id = int(node_id)
            # Keep _id_counter ahead of any manually assigned IDs
            try:
                if self.id >= Vertex._id_counter:
                    Vertex._id_counter = self.id + 1
            except Exception:
                pass
        self.lat = lat
        self.lon = lon
        self.onward_edges = {}
        self.backward_edges = {}
        Vertex.vertex_dict[self.id] = self

    def get_outward_nodes(self):
        return [edge.end for edge in self.onward_edges.values()]
    
    def get_backward_nodes(self):
        return [edge.start for edge in self.backward_edges.values()]
    
    def __repr__(self):
        return f"Vertex(id={self.id}, lat={self.lat}, lon={self.lon})"

class Edge:
    edge_dict = {}  # Class-level dictionary: edge_id -> Edge object
    temporary_edges = []
    detached_edges = []
    _id_counter = 0

    @classmethod
    def restore_all_detached_edges(cls):
        for edge in cls.detached_edges:
            edge.restore_references_to_edge()

    @classmethod
    def delete_all_temporary_edges(cls):
        for edge in cls.temporary_edges:
            edge.delete_edge()
        cls.temporary_edges.clear()

    def __init__(self, start_vertex: Vertex, end_vertex: Vertex, non_vertex_nodes: list[Tuple[float, float, int]], type: str, oneway: bool):
        self.start = start_vertex  # Vertex object
        self.end = end_vertex      # Vertex object
        self.non_vertex_nodes = non_vertex_nodes  # List of (lat, lon, id) tuples for non-vertex nodes
        self.type = type
        self.oneway = oneway
        self.length = self.calculate_length()

        self.id = Edge._id_counter
        Edge.edge_dict[self.id] = self
        Edge._id_counter += 1

        self.start.onward_edges[self] = self.end
        self.end.backward_edges[self] = self.start
        if not self.oneway:
            self.end.onward_edges[self] = self.start
            self.start.backward_edges[self] = self.end

    def calculate_length(self):
        points = [(self.start.lat, self.start.lon)] + [(lat, lon) for lat, lon, _ in self.non_vertex_nodes] + [(self.end.lat, self.end.lon)]
        total = 0.0
        for i in range(len(points) - 1):
            total += haversine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        return total
    
    def split_edge_along_vertex(self, vertex: Vertex, temporary: bool = False):
        if vertex in (self.start, self.end):
            return None  # No split needed
        
        found_idx = None
        for idx, (lat, lon, node_id) in enumerate(self.non_vertex_nodes):
            if vertex.id == node_id:
                found_idx = idx
                break

        if found_idx is None:
            raise ValueError("Vertex not found on edge")

        edge1 = Edge(self.start, vertex, self.non_vertex_nodes[:found_idx], self.type, self.oneway)
        edge2 = Edge(vertex, self.end, self.non_vertex_nodes[found_idx+1:], self.type, self.oneway)

        if temporary:
            Edge.temporary_edges.extend([edge1, edge2])
            self.detach_edge()
        else:
            self.delete_edge()

        return edge1, edge2


    def remove_references_to_edge(self):
        if self in self.start.onward_edges:
            del self.start.onward_edges[self]
        if self in self.end.backward_edges:
            del self.end.backward_edges[self]
        if not self.oneway:
            if self in self.end.onward_edges:
                del self.end.onward_edges[self]
            if self in self.start.backward_edges:
                del self.start.backward_edges[self]

    def restore_references_to_edge(self):
        self.start.onward_edges[self] = self.end
        self.end.backward_edges[self] = self.start
        if not self.oneway:
            self.end.onward_edges[self] = self.start
            self.start.backward_edges[self] = self.end
        Edge.edge_dict[self.id] = self
        Edge.detached_edges.remove(self)

    def delete_edge(self):
        self.remove_references_to_edge()
        if self.id in Edge.edge_dict:
            del Edge.edge_dict[self.id]
        
    def detach_edge(self):
        self.remove_references_to_edge()
        Edge.detached_edges.append(self)

    def project_coordinates_onto_edge(self, lat: float, lon: float):
        points = [(self.start.lat, self.start.lon)] + [(lat, lon) for lat, lon, _ in self.non_vertex_nodes] + [(self.end.lat, self.end.lon)]
        min_dist = float('inf')
        proj_point = None
        seg_idx = -1
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i+1]
            px, py = lat, lon
            dx, dy = x1 - x0, y1 - y0
            if dx == 0 and dy == 0:
                proj = (x0, y0)
            else:
                t = ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)
                t = max(0, min(1, t))
                proj = (x0 + t * dx, y0 + t * dy)
            dist = sqrt((proj[0] - px) ** 2 + (proj[1] - py) ** 2)
            if dist < min_dist:
                min_dist = dist
                proj_point = proj
                seg_idx = i
        # Convert min_dist (in degrees) to meters using haversine
        if proj_point is not None:
            min_dist_m = haversine(lat, lon, proj_point[0], proj_point[1])
        else:
            min_dist_m = None
        return (*proj_point, min_dist_m, seg_idx)
    def __repr__(self):
        return f"Edge(id={self.id}, start=({self.start.id}), end=({self.end.id}), length={self.length:.1f} m)"
    def __hash__(self):
        return self.id
    def __eq__(self, other):
        return isinstance(other, Edge) and self.id == other.id
