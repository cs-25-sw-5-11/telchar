# Vertex and Edge classes, plus haversine and projection logic
from math import radians, sin, cos, sqrt, atan2

class Vertex:
    vertex_dict = {}  # Class-level dictionary: node_id -> Vertex object
    _id_counter = 1   # Class-level counter for unique Vertex IDs

    def __init__(self, node_id=None, lat=None, lon=None):
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
        self.neighbors = {}  # Dict[Edge, Vertex]: edge -> neighbor vertex
        Vertex.vertex_dict[self.id] = self
    def __repr__(self):
        return f"Vertex(id={self.id}, lat={self.lat}, lon={self.lon})"
    def to_serializable(self):
        # Store neighbor as (edge_id, neighbor_id) pairs
        return {
            'id': self.id,
            'lat': self.lat,
            'lon': self.lon,
            'neighbors': [(id(e), v.id) for e, v in self.neighbors.items()]
        }
    @staticmethod
    def from_serializable(data):
        v = Vertex(data['id'], data['lat'], data['lon'])
        # neighbors will be set after all vertices and edges are created
        return v

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

class Edge:
    edge_dict = {}  # Class-level dictionary: edge_id -> Edge object
    _id_counter = 0

    def __init__(self, start_vertex, end_vertex, non_vertex_nodes):
        self.start = start_vertex  # Vertex object
        self.end = end_vertex      # Vertex object
        self.non_vertex_nodes = non_vertex_nodes  # List of (lat, lon) tuples for non-vertex nodes
        self.length = self.calculate_length()
        self.id = Edge._id_counter
        Edge.edge_dict[self.id] = self
        Edge._id_counter += 1

    def calculate_length(self):
        points = [(self.start.lat, self.start.lon)] + self.non_vertex_nodes + [(self.end.lat, self.end.lon)]
        total = 0.0
        for i in range(len(points) - 1):
            total += haversine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        return total
    
    def project_coordinates_onto_edge(self, lat, lon):
        points = [(self.start.lat, self.start.lon)] + self.non_vertex_nodes + [(self.end.lat, self.end.lon)]
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
