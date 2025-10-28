from __future__ import annotations
from typing import Tuple, Set, Optional, Dict, List
import logging
import copy
from . import Edge, Vertex

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