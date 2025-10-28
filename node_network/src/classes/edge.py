from __future__ import annotations
from typing import Tuple, Set, Optional, Dict, List, TYPE_CHECKING
from utils.functions_misc import haversine, get_bin_indices
from configs.config import METERS_PER_DEGREE
from math import sqrt
import logging

if TYPE_CHECKING:
    from classes.network import Network
    from classes.vertex import Vertex

logger = logging.getLogger(__name__)

class Edge:
    """Represents an edge/connection in the graph"""
    
    def __init__(self, network: Network, start_vertex: Vertex, end_vertex: Vertex, 
                 non_vertex_nodes: List[Tuple[float, float, int]], edge_type: str, 
                 oneway: bool, parent_edge: Optional['Edge'] = None):
        self._network = network
        self.start = start_vertex
        self.end = end_vertex
        self.non_vertex_nodes = non_vertex_nodes
        self.type = edge_type
        self.oneway = oneway
        self.length = self.calculate_length()
        self.detached = False
        self.highlighted = False
        self.traversals_data: Dict[int, Tuple[float, float, int]] = {}
        
        # Set parent edge
        if parent_edge is None:
            self.parent_edge = self
        else:
            self.parent_edge = parent_edge
        
        # Get ID from network
        self._id = network.get_next_edge_id()
        
        # Calculate bins covered
        self.bins_covered = self._calculate_bins_covered()
        
        # Connect vertices
        self.start.onward_edges[self] = self.end
        self.end.backward_edges[self] = self.start
        if not self.oneway:
            self.end.onward_edges[self] = self.start
            self.start.backward_edges[self] = self.end
        
        # Add to network
        network.add_edge(self)
    
    @property
    def id(self) -> int:
        """Read-only edge ID"""
        return self._id
    
    @property
    def network(self) -> Network:
        """The network this edge belongs to"""
        return self._network
    
    def calculate_length(self) -> float:
        points = [(self.start.lat, self.start.lon)] + [(lat, lon) for lat, lon, _ in self.non_vertex_nodes] + [(self.end.lat, self.end.lon)]
        total = 0.0
        for i in range(len(points) - 1):
            total += haversine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        return total
    
    def _calculate_bins_covered(self) -> Set[Tuple[int, int]]:
        """Calculate which spatial bins this edge covers"""        
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
        
        # Interpolate between points to catch bins the edge passes through
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
    
    def delete_edge(self) -> None:
        """Delete this edge from the network"""
        self._remove_references_to_edge()
        if self._network:
            self._network.remove_edge(self)
    
    def _remove_references_to_edge(self) -> None:
        """Remove this edge from vertex connections"""
        if self in self.start.onward_edges:
            del self.start.onward_edges[self]
        if self in self.end.backward_edges:
            del self.end.backward_edges[self]
        if not self.oneway:
            if self in self.end.onward_edges:
                del self.end.onward_edges[self]
            if self in self.start.backward_edges:
                del self.start.backward_edges[self]
    
    def _restore_references_to_edge(self) -> None:
        """Restore this edge's vertex connections"""
        self.start.onward_edges[self] = self.end
        self.end.backward_edges[self] = self.start
        if not self.oneway:
            self.end.onward_edges[self] = self.start
            self.start.backward_edges[self] = self.end
        
        if self._network:
            self._network._edges[self.id] = self
        
        self.detached = False
        
        # Remove from detached edges
        if self._network and self in self._network._detached_edges:
            self._network._detached_edges.remove(self)
    
    def detach_edge(self) -> None:
        """Detach this edge temporarily (for reversible operations)"""
        if self.detached:
            return
        
        self._remove_references_to_edge()
        self.detached = True
        
        if self._network:
            self._network._detached_edges.add(self)
    
    def traversals_data_update(self, time_index: int, speed: int, edge_length: int) -> None:
        """Update traversal statistics for this edge"""
        if time_index in self.traversals_data:
            existing_mean, existing_variance, existing_total_length = self.traversals_data[time_index]
            
            total_weight = existing_total_length + edge_length
            new_mean = existing_mean + edge_length * (speed - existing_mean) / total_weight
            
            delta1 = speed - existing_mean
            delta2 = speed - new_mean
            new_variance = (existing_variance * existing_total_length + edge_length * delta1 * delta2) / total_weight
            
            self.traversals_data[time_index] = (new_mean, new_variance, total_weight)
        else:
            self.traversals_data[time_index] = (speed, 0.0, edge_length)
    
    def project_coordinates_onto_edge(self, lat: float, lon: float) -> Tuple[float, float, float, int]:
        """Project coordinates onto this edge and return closest point, distance, and segment index"""
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
    
    def split_edge_along_vertex(self, vertex: 'Vertex', temporary: bool = False) -> Optional[Tuple['Edge', 'Edge']]:
        """Split edge along a vertex that lies on the edge (finds vertex by ID in non_vertex_nodes)"""
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

        edge1 = Edge(
            network=self._network,
            start_vertex=self.start, 
            end_vertex=vertex, 
            non_vertex_nodes=self.non_vertex_nodes[:found_idx], 
            edge_type=self.type, 
            oneway=self.oneway,
            parent_edge=self.parent_edge
        )
        edge2 = Edge(
            network=self._network,
            start_vertex=vertex, 
            end_vertex=self.end, 
            non_vertex_nodes=self.non_vertex_nodes[found_idx+1:], 
            edge_type=self.type, 
            oneway=self.oneway,
            parent_edge=self.parent_edge
        )

        if temporary:
            self._network._temporary_edges.add(edge1)
            self._network._temporary_edges.add(edge2)
            if self in self._network._temporary_edges:
                # Splitting a temporary edge: remove original temporary container edge
                self.delete_edge()
            else:
                # Splitting an original edge temporarily: detach original for reversibility
                self.detach_edge()
        else:
            self.delete_edge()

        return edge1, edge2
    
    def __repr__(self):
        return f"Edge(id={self.id}, start=({self.start.id}), end=({self.end.id}), length={self.length:.1f} m, type={self.type}, oneway={self.oneway})"
    
    def __hash__(self):
        return self.id
    
    def __eq__(self, other):
        return isinstance(other, Edge) and self.id == other.id