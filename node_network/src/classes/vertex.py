from __future__ import annotations
from typing import Optional, Dict, List, TYPE_CHECKING
from utils.functions_misc import get_bin_indices
import logging

if TYPE_CHECKING:
    from .network import Network
    from .edge import Edge

logger = logging.getLogger(__name__)

class Vertex:
    """Represents a vertex/node in the graph"""
    
    def __init__(self, network: Network, lat: float, lon: float, node_id: Optional[int] = None):
        self._network = network
        self.lat = lat
        self.lon = lon
        self.onward_edges: Dict['Edge', 'Vertex'] = {}
        self.backward_edges: Dict['Edge', 'Vertex'] = {}
        
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