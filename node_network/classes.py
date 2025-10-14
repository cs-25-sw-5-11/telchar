from typing import Tuple, Set
from functions_misc import haversine, get_bin_indices
from config import METERS_PER_DEGREE
from math import sqrt
import logging

logger = logging.getLogger(__name__)

class Vertex:
    vertex_dict = {}  # Class-level dictionary: node_id -> Vertex object
    temporary_vertices = set()  # Set of temporary vertices
    _id_counter = 1   # Class-level counter for unique Vertex IDs
    _bin_lookup = {}  # Class-level reverse lookup: (lat_idx, lon_idx) -> [vertices]

    @classmethod
    def clear_all(cls):
        """Reset all vertex-related registries and counters."""
        cls.vertex_dict.clear()
        cls.temporary_vertices.clear()
        cls._id_counter = 1
        cls._bin_lookup.clear()
        logger.debug("Vertex.clear_all() completed")

    @classmethod
    def delete_all_temporary_vertices(cls):
        """Delete all temporary vertices and clear the temporary set"""
        for vertex in list(cls.temporary_vertices):  # list() snapshot to avoid mutation issues
            vertex.delete_vertex()
        cls.temporary_vertices.clear()

    def __new__(cls, lat: float, lon: float, node_id: int = None, temporary: bool = False):
        # If node_id is provided and already exists, return existing vertex
        if node_id is not None and node_id in cls.vertex_dict:
            existing_vertex = cls.vertex_dict[node_id]
            if temporary:
                if existing_vertex in cls.temporary_vertices:
                    logger.debug("Requested temporary creation of existing temporary vertex %s", node_id)
                else:
                    logger.warning("Attempt to treat existing non-temporary vertex %s as temporary; ignoring temporary flag", node_id)
            return existing_vertex
        
        # Otherwise, create a new instance
        return super().__new__(cls)

    def __init__(self, lat: float, lon: float, node_id: int = None, temporary: bool = False):
        # Skip initialization if this is an existing vertex
        if hasattr(self, 'id'):
            # If this is an existing vertex being requested as temporary, DO NOT add to temporary list
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
        self.parent_edge = None
        
        # Determine & record temporary status
        self.is_temporary = bool(temporary)
        if self.is_temporary:
            Vertex.temporary_vertices.add(self)
        
        # Calculate and store bin coordinates
        self.bin_coords = get_bin_indices(self.lat, self.lon)
        self._update_bin_lookup()

    def print_neighbors(self):
        logger.info("Vertex %s neighbors:", self.id)
        for edge, vertex in self.onward_edges.items():
            logger.info("  Outward via Edge %s to Vertex %s", edge.id, vertex.id)
        for edge, vertex in self.backward_edges.items():
            logger.info("  Backward via Edge %s to Vertex %s", edge.id, vertex.id)

    def get_outward_edges(self):
        return list(self.onward_edges.keys())
    
    def get_backward_edges(self):
        return list(self.backward_edges.keys())
    
    def get_outward_vertices(self):
        return list(self.onward_edges.values())

    def get_backward_vertices(self):
        return list(self.backward_edges.values())

    def delete_vertex(self):
        """Delete this vertex from all data structures."""
        # Remove from vertex_dict
        if self.id in Vertex.vertex_dict:
            del Vertex.vertex_dict[self.id]
        
        # Remove from bin lookup
        if self.bin_coords and self.bin_coords in Vertex._bin_lookup:
            if self in Vertex._bin_lookup[self.bin_coords]:
                Vertex._bin_lookup[self.bin_coords].remove(self)
                # Clean up empty bin lists
                if not Vertex._bin_lookup[self.bin_coords]:
                    del Vertex._bin_lookup[self.bin_coords]
        
        # Remove from temporary list
        if self in Vertex.temporary_vertices:
            Vertex.temporary_vertices.remove(self)

        connected_edges = list(self.onward_edges.keys()) + list(self.backward_edges.keys())
        for edge in connected_edges:
            edge.delete_edge()
    
    def _update_bin_lookup(self):
        """Update the reverse bin lookup dictionary"""
        if self.bin_coords:
            if self.bin_coords not in Vertex._bin_lookup:
                Vertex._bin_lookup[self.bin_coords] = []
            if self not in Vertex._bin_lookup[self.bin_coords]:
                Vertex._bin_lookup[self.bin_coords].append(self)
    
    @classmethod
    def get_vertices_in_bin(cls, lat_idx: int, lon_idx: int) -> list:
        """Get all vertices in a specific bin"""
        return cls._bin_lookup.get((lat_idx, lon_idx), [])
    
    @classmethod
    def clear_bin_lookup(cls):
        """Clear the bin lookup dictionary"""
        cls._bin_lookup.clear()
    
    def __repr__(self):
        return f"Vertex(id={self.id}, lat={self.lat}, lon={self.lon}, bin={self.bin_coords})"

class Edge:
    edge_dict = {}  # Class-level dictionary: edge_id -> Edge object
    temporary_edges = set()
    detached_edges = set()
    _id_counter = 0
    _bin_lookup = {}  # Class-level reverse lookup: (lat_idx, lon_idx) -> [edges]

    @classmethod
    def clear_all(cls):
        """Reset all edge-related registries and counters."""
        cls.edge_dict.clear()
        cls.temporary_edges.clear()
        cls.detached_edges.clear()
        cls._id_counter = 0
        cls._bin_lookup.clear()
        logger.debug("Edge.clear_all() completed")

    @classmethod
    def restore_all_detached_edges(cls):
        # Process edges until the list is empty (safer than blindly clearing)
        for edge in list(cls.detached_edges):
            edge.restore_references_to_edge()

    @classmethod
    def delete_all_temporary_edges(cls):
        # Iterate over a copy so that delete_edge() removing from temporary_edges
        # does not cause elements to be skipped (integrity bug fix)
        for edge in list(cls.temporary_edges):
            edge.delete_edge()
        cls.temporary_edges.clear()

    def __init__(self, start_vertex: Vertex, end_vertex: Vertex, non_vertex_nodes: list[Tuple[float, float, int]], type: str, oneway: bool, parent_edge=None):
        self.start = start_vertex  # Vertex object
        self.end = end_vertex      # Vertex object
        self.non_vertex_nodes = non_vertex_nodes  # List of (lat, lon, id) tuples for non-vertex nodes
        self.type = type
        self.oneway = oneway
        self.length = self.calculate_length()
        self.detached = False  # Boolean flag for detachment status
        self.highlighted = False
        if parent_edge is None:
            self.parent_edge = self
        else:
            self.parent_edge = parent_edge

        self.id = Edge._id_counter
        Edge.edge_dict[self.id] = self
        Edge._id_counter += 1

        self.start.onward_edges[self] = self.end
        self.end.backward_edges[self] = self.start
        if not self.oneway:
            self.end.onward_edges[self] = self.start
            self.start.backward_edges[self] = self.end

        # Dictionary for storing speeds.
        self.traversals_data = {}

        # Calculate and store bins covered by this edge
        self.bins_covered = self._calculate_bins_covered()
        self._update_bin_lookup()

    def traversals_data_update(self, time_index: int, speed: int, edge_length: int):
        # Existing entry: update weighted statistics
        if time_index in self.traversals_data:
            existing_mean, existing_variance, existing_total_length = self.traversals_data[time_index]

            # Calculate new weighted mean using incremental form (slightly faster)
            total_weight = existing_total_length + edge_length
            new_mean = existing_mean + edge_length * (speed - existing_mean) / total_weight
            
            # Calculate new weighted variance using Welford's online algorithm for weighted variance
            # delta1 = x - old_mean, new_mean = old_mean + w2*delta1/(w1+w2)
            # delta2 = x - new_mean, new_variance = (w1*old_var + w2*delta1*delta2) / (w1+w2)
            delta1 = speed - existing_mean
            delta2 = speed - new_mean
            new_variance = (existing_variance * existing_total_length + edge_length * delta1 * delta2) / total_weight

            self.traversals_data[time_index] = (new_mean, new_variance, total_weight)
        # New entry: initialize with single data point (variance = 0)
        else:
            self.traversals_data[time_index] = (speed, 0.0, edge_length)

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
            # Ensure consistent type comparison - convert both to int
            vertex_id = int(vertex.id) if isinstance(vertex.id, str) else vertex.id
            compare_node_id = int(node_id) if isinstance(node_id, str) else node_id
            if vertex_id == compare_node_id:
                found_idx = idx
                break

        if found_idx is None:
            raise ValueError("Vertex not found on edge")

        edge1 = Edge(self.start, vertex, self.non_vertex_nodes[:found_idx], self.type, self.oneway)
        edge2 = Edge(vertex, self.end, self.non_vertex_nodes[found_idx+1:], self.type, self.oneway)

        if temporary:
            edge1.parent_edge = self.parent_edge
            edge2.parent_edge = self.parent_edge
            vertex.parent_edge = self.parent_edge

            Edge.temporary_edges.add(edge1)
            Edge.temporary_edges.add(edge2)
            if self in Edge.temporary_edges:
                # Splitting a temporary edge: remove original temporary container edge
                self.delete_edge()
            else:
                # Splitting an original edge temporarily: detach original for reversibility
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
        self.detached = False
        # Re-add this edge to the spatial bin lookup now that it is active again
        self._update_bin_lookup()
        
        # Remove from detached_edges list if present
        if self in Edge.detached_edges:
            Edge.detached_edges.remove(self)

    def delete_edge(self):
        self.remove_references_to_edge()
        if self.id in Edge.edge_dict:
            del Edge.edge_dict[self.id]
        
        # Remove from bin lookup
        for bin_coord in self.bins_covered:
            if bin_coord in Edge._bin_lookup and self in Edge._bin_lookup[bin_coord]:
                Edge._bin_lookup[bin_coord].remove(self)
                # Clean up empty bin lists
                if not Edge._bin_lookup[bin_coord]:
                    del Edge._bin_lookup[bin_coord]
        
        # Remove from temporary and detached edges list if present
        if self in Edge.temporary_edges:
            Edge.temporary_edges.remove(self)
        if self in Edge.detached_edges:
            Edge.detached_edges.remove(self)
        
    def detach_edge(self):
        if self.detached:
            return
        self.remove_references_to_edge()
        # Remove from bin lookup so spatial queries no longer see this edge
        self._remove_from_bin_lookup()
        self.detached = True
        if self not in Edge.detached_edges:
            Edge.detached_edges.add(self)

    def project_coordinates_onto_edge(self, lat: float, lon: float):
        points = [(self.start.lat, self.start.lon)] + [(lat, lon) for lat, lon, _ in self.non_vertex_nodes] + [(self.end.lat, self.end.lon)]
        min_dist_sq = float('inf')  # Use squared distance to avoid sqrt in the loop
        proj_point = None
        seg_idx = -1
        
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i+1]
            px, py = lat, lon
            dx, dy = x1 - x0, y1 - y0
            
            if dx == 0 and dy == 0:
                # Degenerate segment (zero length)
                proj = (x0, y0)
            else:
                # Project point onto line segment
                t = ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)
                t = max(0, min(1, t))  # Clamp to segment
                proj = (x0 + t * dx, y0 + t * dy)
            
            # Calculate squared distance (avoid sqrt for comparison)
            dist_sq = (proj[0] - px) ** 2 + (proj[1] - py) ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                proj_point = proj
                seg_idx = i
        
        if proj_point is not None:
            # Convert distance from degrees to meters using region-specific constant
            min_dist_degrees = sqrt(min_dist_sq)
            min_dist_m = min_dist_degrees * METERS_PER_DEGREE
        else:
            min_dist_m = None
            
        return (*proj_point, min_dist_m, seg_idx)
    
    def _calculate_bins_covered(self) -> Set[Tuple[int, int]]:
        """Calculate which bins this edge covers"""        
        bins_covered = set()
        
        # Get all points along the edge
        points = [(self.start.lat, self.start.lon)] + \
                [(lat, lon) for lat, lon, _ in self.non_vertex_nodes] + \
                [(self.end.lat, self.end.lon)]
        
        # Add bins for each point
        for lat, lon in points:
            bin_coords = get_bin_indices(lat, lon)
            if bin_coords is not None:
                bins_covered.add(bin_coords)
        
        # Also interpolate between points to catch bins the edge passes through
        for i in range(len(points) - 1):
            lat1, lon1 = points[i]
            lat2, lon2 = points[i + 1]
            
            # Sample points along the segment
            num_samples = max(10, int(haversine(lat1, lon1, lat2, lon2) / 50))  # Sample every ~50m
            for j in range(num_samples + 1):
                t = j / num_samples if num_samples > 0 else 0
                sample_lat = lat1 + t * (lat2 - lat1)
                sample_lon = lon1 + t * (lon2 - lon1)
                
                bin_coords = get_bin_indices(sample_lat, sample_lon)
                if bin_coords is not None:
                    bins_covered.add(bin_coords)
        
        return bins_covered
    
    def _update_bin_lookup(self):
        """Update the reverse bin lookup dictionary"""
        for bin_coord in self.bins_covered:
            if bin_coord not in Edge._bin_lookup:
                Edge._bin_lookup[bin_coord] = []
            if self not in Edge._bin_lookup[bin_coord]:
                Edge._bin_lookup[bin_coord].append(self)
    
    def _remove_from_bin_lookup(self):
        """Remove this edge from all bins it was registered in (used for detach/delete)."""
        for bin_coord in list(self.bins_covered):
            if bin_coord in Edge._bin_lookup and self in Edge._bin_lookup[bin_coord]:
                Edge._bin_lookup[bin_coord].remove(self)
                if not Edge._bin_lookup[bin_coord]:
                    del Edge._bin_lookup[bin_coord]
    

    @classmethod
    def get_edges_in_bin(cls, lat_idx: int, lon_idx: int) -> list:
        """Get all active (non-detached) edges in a specific bin"""
        all_edges = cls._bin_lookup.get((lat_idx, lon_idx), [])
        return [edge for edge in all_edges if not edge.detached]
    
    @classmethod
    def clear_bin_lookup(cls):
        """Clear the bin lookup dictionary"""
        cls._bin_lookup.clear()
    
    def __repr__(self):
        return f"Edge(id={self.id}, start=({self.start.id}), end=({self.end.id}), length={self.length:.1f} m, type={self.type}, oneway={self.oneway}, parent_edge={self.parent_edge.id}, bins_covered={len(self.bins_covered)})"
    def __hash__(self):
        return self.id
    def __eq__(self, other):
        return isinstance(other, Edge) and self.id == other.id
