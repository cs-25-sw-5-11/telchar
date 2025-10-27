from typing import Tuple, Set, Optional, Dict, List
from utils.functions_misc import haversine, get_bin_indices
from configs.config import METERS_PER_DEGREE
from math import sqrt
import logging
import copy

logger = logging.getLogger(__name__)

class Network:
    def __init__(self):
        self._vertices: Dict[int, 'Vertex'] = {}
        self._temporary_vertices: Set['Vertex'] = set()
        self._vertex_id_counter: int = 1
        self._vertex_bin_lookup: Dict[Tuple[int, int], List['Vertex']] = {}
        
        self._edges: Dict[int, 'Edge'] = {}
        self._temporary_edges: Set['Edge'] = set()
        self._detached_edges: Set['Edge'] = set()
        self._edge_id_counter: int = 0
        self._edge_bin_lookup: Dict[Tuple[int, int], List['Edge']] = {}
    
    def add_vertex(self, vertex: 'Vertex') -> None:
        """Add vertex to the network"""
        self._vertices[vertex.id] = vertex
        vertex._network = self
        
        if vertex.is_temporary:
            self._temporary_vertices.add(vertex)
        
        # Update bin lookup
        if vertex.bin_coords:
            if vertex.bin_coords not in self._vertex_bin_lookup:
                self._vertex_bin_lookup[vertex.bin_coords] = []
            if vertex not in self._vertex_bin_lookup[vertex.bin_coords]:
                self._vertex_bin_lookup[vertex.bin_coords].append(vertex)
    
    def remove_vertex(self, vertex: 'Vertex') -> None:
        """Remove vertex from the network"""
        if vertex.id in self._vertices:
            del self._vertices[vertex.id]
        
        if vertex in self._temporary_vertices:
            self._temporary_vertices.remove(vertex)
        
        # Remove from bin lookup
        if vertex.bin_coords and vertex.bin_coords in self._vertex_bin_lookup:
            if vertex in self._vertex_bin_lookup[vertex.bin_coords]:
                self._vertex_bin_lookup[vertex.bin_coords].remove(vertex)
                # Clean up empty bin lists
                if not self._vertex_bin_lookup[vertex.bin_coords]:
                    del self._vertex_bin_lookup[vertex.bin_coords]
        
        vertex._network = None
    
    def add_edge(self, edge: 'Edge') -> None:
        """Add edge to the network"""
        self._edges[edge.id] = edge
        edge._network = self
        
        if edge in self._temporary_edges:
            # Already marked as temporary elsewhere
            pass
        
        # Update bin lookup
        for bin_coord in edge.bins_covered:
            if bin_coord not in self._edge_bin_lookup:
                self._edge_bin_lookup[bin_coord] = []
            if edge not in self._edge_bin_lookup[bin_coord]:
                self._edge_bin_lookup[bin_coord].append(edge)
    
    def remove_edge(self, edge: 'Edge') -> None:
        """Remove edge from the network"""
        if edge.id in self._edges:
            del self._edges[edge.id]
        
        if edge in self._temporary_edges:
            self._temporary_edges.remove(edge)
        
        if edge in self._detached_edges:
            self._detached_edges.remove(edge)
        
        # Remove from bin lookup
        for bin_coord in edge.bins_covered:
            if bin_coord in self._edge_bin_lookup and edge in self._edge_bin_lookup[bin_coord]:
                self._edge_bin_lookup[bin_coord].remove(edge)
                if not self._edge_bin_lookup[bin_coord]:
                    del self._edge_bin_lookup[bin_coord]
        
        edge._network = None

    def split_edge_at_vertex(self, edge: 'Edge', vertex: 'Vertex', temporary: bool = False) -> Optional[Tuple['Edge', 'Edge']]:
        """Split an edge at a given vertex, returning the two new edges"""
        # Verify vertex is on edge
        node_ids_on_edge = [node_id for _, _, node_id in edge.non_vertex_nodes]
        if vertex.id not in node_ids_on_edge:
            raise ValueError(f"Vertex {vertex.id} not found on Edge {edge.id}")
        
        # Find index of vertex in non-vertex nodes
        split_index = node_ids_on_edge.index(vertex.id)
        
        # Create new edges
        start_vertex = edge.start
        end_vertex = edge.end
        
        # Nodes for the first new edge
        nodes_edge1 = edge.non_vertex_nodes[:split_index]
        edge1 = Edge(
            network=self,
            start_vertex=start_vertex,
            end_vertex=vertex,
            non_vertex_nodes=nodes_edge1,
            edge_type=edge.type,
            oneway=edge.oneway,
            parent_edge=edge.parent_edge
        )
        
        # Nodes for the second new edge
        nodes_edge2 = edge.non_vertex_nodes[split_index + 1:]
        edge2 = Edge(
            network=self,
            start_vertex=vertex,
            end_vertex=end_vertex,
            non_vertex_nodes=nodes_edge2,
            edge_type=edge.type,
            oneway=edge.oneway,
            parent_edge=edge.parent_edge
        )
        
        # If this is a temporary operation, detach the original edge and set parent_edges to new edges.
        # Otherwise, remove the original edge from the network.
        if temporary:
            edge.detach_edge()
            edge1.parent_edge = edge.parent_edge
            edge2.parent_edge = edge.parent_edge
        else:
            edge.delete_edge()

        return (edge1, edge2)
    
    def get_vertex_by_id(self, vertex_id: int) -> Optional['Vertex']:
        """Get a vertex by its ID"""
        return self._vertices.get(vertex_id)
    
    def get_edge_by_id(self, edge_id: int) -> Optional['Edge']:
        """Get an edge by its ID"""
        return self._edges.get(edge_id)
    
    def get_vertices_in_bin(self, lat_idx: int, lon_idx: int) -> List['Vertex']:
        """Get all vertices in a specific spatial bin"""
        return self._vertex_bin_lookup.get((lat_idx, lon_idx), [])
    
    def get_edges_in_bin(self, lat_idx: int, lon_idx: int) -> List['Edge']:
        """Get all active (non-detached) edges in a specific spatial bin"""
        all_edges = self._edge_bin_lookup.get((lat_idx, lon_idx), [])
        return [edge for edge in all_edges if not edge.detached]
    
    def get_next_vertex_id(self) -> int:
        """Get the next available vertex ID"""
        vertex_id = self._vertex_id_counter
        self._vertex_id_counter += 1
        return vertex_id
    
    def get_next_edge_id(self) -> int:
        """Get the next available edge ID"""
        edge_id = self._edge_id_counter
        self._edge_id_counter += 1
        return edge_id
    
    def clear_all(self) -> None:
        """Clear all vertices and edges from the network"""
        self._vertices.clear()
        self._edges.clear()
        self._temporary_vertices.clear()
        self._temporary_edges.clear()
        self._detached_edges.clear()
        self._vertex_bin_lookup.clear()
        self._edge_bin_lookup.clear()
        self._vertex_id_counter = 1
        self._edge_id_counter = 0
    
    def copy(self) -> 'Network':
        """Create a deep copy of the network"""
        return copy.deepcopy(self)
    
    def get_stats(self) -> Dict[str, int]:
        """Get network statistics"""
        return {
            'vertices': len(self._vertices),
            'edges': len(self._edges),
            'temporary_vertices': len(self._temporary_vertices),
            'temporary_edges': len(self._temporary_edges),
            'detached_edges': len(self._detached_edges)
        }
    
    def delete_all_temporary_vertices(self) -> None:
        """Delete all temporary vertices and their edges"""
        for vertex in list(self._temporary_vertices):
            vertex.delete_vertex()
        self._temporary_vertices.clear()
    
    def delete_all_temporary_edges(self) -> None:
        """Delete all temporary edges"""
        for edge in list(self._temporary_edges):
            edge.delete_edge()
        self._temporary_edges.clear()
    
    def restore_all_detached_edges(self) -> None:
        """Restore all detached edges"""
        for edge in list(self._detached_edges):
            edge._restore_references_to_edge()
    
    def get_all_vertices(self) -> List['Vertex']:
        """Get a list of all vertices in the network"""
        return list(self._vertices.values())
    
    def get_all_edges(self) -> List['Edge']:
        """Get a list of all edges in the network"""
        return list(self._edges.values())
    
    def get_max_vertex_id(self) -> int:
        """Get the maximum vertex ID currently assigned"""
        if self._vertices:
            return max(self._vertices.keys())
        return 0
    
    def get_max_edge_id(self) -> int:
        """Get the maximum edge ID currently assigned"""
        if self._edges:
            return max(self._edges.keys())
        return 0
    
    def check_vertex_exists(self, vertex_id: int) -> bool:
        """Check if a vertex with the given ID exists"""
        return vertex_id in self._vertices
    
    def check_edge_exists(self, edge_id: int) -> bool:
        """Check if an edge with the given ID exists"""
        return edge_id in self._edges
    
    def delete_vertex_by_id(self, vertex_id: int) -> None:
        """Delete a vertex by its ID"""
        vertex = self._vertices.get(vertex_id)
        if vertex:
            vertex.delete_vertex()

    def __repr__(self):
        return f"Network(vertices={len(self._vertices)}, edges={len(self._edges)})"

    def __eq__(self, other):
        return (isinstance(other, Network) and
                self._vertices == other._vertices and
                self._edges == other._edges and
                self._temporary_vertices == other._temporary_vertices and
                self._temporary_edges == other._temporary_edges and
                self._detached_edges == other._detached_edges and
                self._vertex_id_counter == other._vertex_id_counter and
                self._edge_id_counter == other._edge_id_counter)


class Vertex:
    """Represents a vertex/node in the graph"""
    
    def __init__(self, network: Network, lat: float, lon: float, node_id: Optional[int] = None, temporary: bool = False):
        self._network = network
        self.lat = lat
        self.lon = lon
        self.onward_edges: Dict['Edge', 'Vertex'] = {}
        self.backward_edges: Dict['Edge', 'Vertex'] = {}
        self.parent_edge: Optional['Edge'] = None
        self.is_temporary = bool(temporary)
        
        # Set ID
        if node_id is None:
            self._id = network.get_next_vertex_id()
        else:
            self._id = int(node_id)
            # Keep counter ahead of manually assigned IDs
            if self._id >= network._vertex_id_counter:
                network._vertex_id_counter = self._id + 1
        
        # Calculate and store bin coordinates
        self.bin_coords = get_bin_indices(self.lat, self.lon)
        
        # Add to network
        network.add_vertex(self)
    
    @property
    def id(self) -> int:
        """Read-only vertex ID"""
        return self._id
    
    @property
    def network(self) -> Network:
        """The network this vertex belongs to"""
        return self._network
    
    def get_outward_edges(self) -> List['Edge']:
        return list(self.onward_edges.keys())
    
    def get_backward_edges(self) -> List['Edge']:
        return list(self.backward_edges.keys())
    
    def get_outward_vertices(self) -> List['Vertex']:
        return list(self.onward_edges.values())

    def get_backward_vertices(self) -> List['Vertex']:
        return list(self.backward_edges.values())
    
    def delete_vertex(self) -> None:
        """Delete this vertex from the network"""
        # Delete all connected edges first
        connected_edges = list(self.onward_edges.keys()) + list(self.backward_edges.keys())
        for edge in connected_edges:
            edge.delete_edge()
        
        # Remove from network
        if self._network:
            self._network.remove_vertex(self)
    
    def print_neighbors(self) -> None:
        logger.info("Vertex %s neighbors:", self.id)
        for edge, vertex in self.onward_edges.items():
            logger.info("  Outward via Edge %s to Vertex %s", edge.id, vertex.id)
        for edge, vertex in self.backward_edges.items():
            logger.info("  Backward via Edge %s to Vertex %s", edge.id, vertex.id)
    
    def __repr__(self):
        return f"Vertex(id={self.id}, lat={self.lat}, lon={self.lon}, bin={self.bin_coords})"

    def __hash__(self):
        return self.id
    
    def __eq__(self, other):
        return isinstance(other, Vertex) and self.id == other.id

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