from __future__ import annotations

import heapq
import json
import logging
import os
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from tqdm import tqdm
from utils.functions_misc import get_bins_near_point

from . import Edge, Vertex

logger = logging.getLogger(__name__)


class Network:
    def __init__(self):
        self._vertices: Dict[int, "Vertex"] = {}
        self._temporary_vertices: Set["Vertex"] = set()
        self._vertex_id_counter: int = 1
        self._vertex_bin_lookup: Dict[Tuple[int, int], List["Vertex"]] = {}

        self._edges: Dict[int, "Edge"] = {}
        self._temporary_edges: Set["Edge"] = set()
        self._detached_edges: Set["Edge"] = set()
        self._edge_id_counter: int = 0
        self._edge_bin_lookup: Dict[Tuple[int, int], List["Edge"]] = {}

        self._all_pairs_distances: Dict[int, Dict[int, float]] = {}
        self._distances_computed: bool = False
        self._distance_matrix: Optional[np.ndarray] = None
        self._vertex_id_to_index: Dict[int, int] = {}
        self._index_to_vertex_id: Dict[int, int] = {}

        self._memo: Dict[str, float] = {}

    def mark_missing_edge_traversals(self, max_time_index: int):
        """Mark edges that were not traversed in for any time index with -1 speed."""
        for edge in tqdm(self._edges.values(), desc="Marking missing edge traversals"):
            for time_index in range(max_time_index):
                if time_index not in edge.traversals_data:
                    edge.traversals_data[time_index] = (-1, 0, 0)

    def plot_network_within_bins(self, bin_list: List[Tuple[int, int]]) -> None:
        """Plot all edges and vertices within the specified bins."""
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 10))

        # Plot edges
        for lat_idx, lon_idx in bin_list:
            edges_in_bin = self.get_edges_in_bin(lat_idx, lon_idx)
            for edge in edges_in_bin:
                lats = (
                    [edge.start.lat]
                    + [node_lat for node_lat, _, _ in edge.non_vertex_nodes]
                    + [edge.end.lat]
                )
                lons = (
                    [edge.start.lon]
                    + [node_lon for _, node_lon, _ in edge.non_vertex_nodes]
                    + [edge.end.lon]
                )
                plt.plot(lons, lats, "-", color="blue", alpha=0.5)

        # Plot vertices
        for lat_idx, lon_idx in bin_list:
            vertices_in_bin = self.get_vertices_in_bin(lat_idx, lon_idx)
            for vertex in vertices_in_bin:
                plt.plot(vertex.lon, vertex.lat, "o", color="red")

        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.title("Network Visualization within Specified Bins")
        plt.grid(True)
        plt.show()

    def get_edges_near_coordinate(self, lat: float, lon: float) -> Set["Edge"]:
        """Return all edges near a given coordinate.
        Includes edges in the bin containing the coordinate and the 3
        bins sharing the edge the coordinate is closest to."""
        nearby_edges: Set["Edge"] = set()
        nearby_bins = get_bins_near_point(lat, lon)
        for lat_idx, lon_idx in nearby_bins:
            edges_in_bin = self.get_edges_in_bin(lat_idx, lon_idx)
            nearby_edges.update(edges_in_bin)

        return nearby_edges

    def compute_all_pairs_shortest_paths(self):
        """Precompute shortest distances between all vertex pairs using Dijkstra from each vertex."""
        print("Computing all-pairs shortest distances...")
        vertices = self.get_all_vertices()

        # Create vertex ID to matrix index mapping
        self._create_vertex_index_mapping(vertices)

        # Initialize distance matrix with a large value representing infinity for int32
        # int32 max value is far larger than any realistic distance in a network, so
        # it's used to cut down on memory usage.
        n = len(vertices)
        INF_VALUE = np.iinfo(np.int32).max
        self._distance_matrix = np.full((n, n), INF_VALUE, dtype=np.int32)

        for source_vertex in tqdm(vertices, desc="Computing distances"):
            distances = self._dijkstra_algorithm(source_vertex)
            source_idx = self._vertex_id_to_index[source_vertex.id]

            # Fill matrix row for this source vertex
            for target_id, distance in distances.items():
                target_idx = self._vertex_id_to_index[target_id]
                # Convert to centimeters and store as integer
                distance_cm = int(distance * 100)
                self._distance_matrix[source_idx, target_idx] = distance_cm

        self._distances_computed = True
        print(f"Computed distances for {len(vertices)} vertices")

    def _create_vertex_index_mapping(self, vertices: List["Vertex"]) -> None:
        """Create bidirectional mapping between vertex IDs and matrix indices."""
        self._vertex_id_to_index.clear()
        self._index_to_vertex_id.clear()

        for idx, vertex in enumerate(vertices):
            self._vertex_id_to_index[vertex.id] = idx
            self._index_to_vertex_id[idx] = vertex.id

    def _dijkstra_algorithm(self, source_vertex) -> dict[int, float]:
        """Run Dijkstra from a single source vertex to all other vertices."""
        distances = {source_vertex.id: 0.0}
        heap = [(0.0, source_vertex.id)]
        visited = set()

        while heap:
            current_dist, current_id = heapq.heappop(heap)

            if current_id in visited:
                continue
            visited.add(current_id)

            current_vertex: Vertex = self.get_vertex_by_id(current_id)
            for edge, vertex in zip(current_vertex.get_outward_edges(), current_vertex.get_outward_vertices()):
                neighbor_id = vertex.id
                new_dist = current_dist + edge.length

                if neighbor_id not in distances or new_dist < distances[neighbor_id]:
                    distances[neighbor_id] = new_dist
                    heapq.heappush(heap, (new_dist, neighbor_id))

        return distances

    def get_distance(self, source: Vertex, target: Vertex) -> float | None:
        """Get precomputed distance between two vertices. Result will be in meters,
        but be rounded to two decimal places, as distances are stored in centimeters
        in integers internally."""
        source_id = source.id
        target_id = target.id
        hash = f"{source_id}-{target_id}"
        if hash in self._memo:
            return self._memo.get(hash)
        if not self._distances_computed:
            raise RuntimeError(
                "Distances not available. Call load_or_compute_all_pairs_distances() first."
            )

        if (
            source_id not in self._vertex_id_to_index
            or target_id not in self._vertex_id_to_index
        ):
            return None

        source_idx = self._vertex_id_to_index[source_id]
        target_idx = self._vertex_id_to_index[target_id]

        distance_cm = self._distance_matrix[source_idx, target_idx]
        # Check if distance is the "infinity" value (unreachable)
        if distance_cm == np.iinfo(np.int32).max:
            return float(np.iinfo(np.int32).max)

        # Convert back from centimeters to meters
        result = float(distance_cm) / 100.0
        self._memo[hash] = result
        return result

    def get_all_distances_from(self, source: Vertex) -> dict[int, float]:
        """Get all distances from a source vertex."""
        if not self._distances_computed:
            raise RuntimeError(
                "Distances not available. Call load_or_compute_all_pairs_distances() first."
            )

        if source.id not in self._vertex_id_to_index:
            raise RuntimeError(
                f"Source vertex ID {source.id} not found in the network."
            )

        source_idx = self._vertex_id_to_index[source.id]
        distances = {}

        INF_VALUE = np.iinfo(np.int32).max
        for target_idx, distance_cm in enumerate(self._distance_matrix[source_idx]):
            if distance_cm != INF_VALUE:
                target_id = self._index_to_vertex_id[target_idx]
                distances[target_id] = float(distance_cm) / 100.0
            else:
                target_id = self._index_to_vertex_id[target_idx]
                distances[target_id] = float(INF_VALUE)

        return distances

    def load_or_compute_all_pairs_distances(
        self,
        distances_file: str = "all_pairs_distances.npy",
        mapping_file: str = "vertex_id_mapping.json",
    ) -> None:
        """
        Load all-pairs shortest distances from files if they exist, otherwise compute and save to files.

        Args:
            distances_file: Path to the NPY file storing the distance matrix
            mapping_file: Path to the JSON file storing the vertex ID to index mappings
        """
        # Try to load both files
        distances_exist = os.path.exists(distances_file)
        mapping_exists = os.path.exists(mapping_file)

        if distances_exist and mapping_exists:
            print(
                f"Loading precomputed distances from {distances_file} and mappings from {mapping_file}..."
            )
            try:
                # Load distance matrix
                self._distance_matrix = np.load(distances_file)

                # Load vertex ID mappings
                with open(mapping_file, "r") as f:
                    mapping_data = json.load(f)
                    self._vertex_id_to_index = {
                        int(k): v for k, v in mapping_data["vertex_id_to_index"].items()
                    }
                    # Reconstruct the reverse mapping from vertex_id_to_index
                    self._index_to_vertex_id = {
                        v: k for k, v in self._vertex_id_to_index.items()
                    }

                self._distances_computed = True
                print(
                    f"Successfully loaded distances for {len(self._vertex_id_to_index)} vertices"
                )
            except (IOError, KeyError, ValueError, json.JSONDecodeError) as e:
                print(f"Error loading distance data: {e}")
                print("Computing distances from scratch...")
                self._compute_and_save_distances(distances_file, mapping_file)
        else:
            missing_files = []
            if not distances_exist:
                missing_files.append(distances_file)
            if not mapping_exists:
                missing_files.append(mapping_file)

            print(
                f"Distance files not found: {', '.join(missing_files)}. Computing distances..."
            )
            self._compute_and_save_distances(distances_file, mapping_file)

    def _compute_and_save_distances(
        self, distances_file: str, mapping_file: str
    ) -> None:
        """
        Compute all-pairs shortest distances and save to files.

        Args:
            distances_file: Path to save the distance matrix
            mapping_file: Path to save the vertex ID to index mappings
        """
        self.compute_all_pairs_shortest_paths()

        print(
            f"Saving computed distances to {distances_file} and mappings to {mapping_file}..."
        )
        try:
            # Save distance matrix as NPY file
            np.save(distances_file, self._distance_matrix)

            # Save vertex ID mappings as JSON file (only vertex_id_to_index, reconstruct the reverse when loading)
            mapping_data = {
                "vertex_id_to_index": {
                    str(k): v for k, v in self._vertex_id_to_index.items()
                }
            }

            with open(mapping_file, "w") as f:
                json.dump(mapping_data, f, indent=2)

            # Calculate and display file sizes
            distances_size = os.path.getsize(distances_file)
            mapping_size = os.path.getsize(mapping_file)
            distances_mb = distances_size / (1024 * 1024)
            mapping_kb = mapping_size / 1024

            print(f"Successfully saved:")
            print(f"  - Distances to {distances_file} (Size: {distances_mb:.1f} MB)")
            print(f"  - Mappings to {mapping_file} (Size: {mapping_kb:.1f} KB)")

        except IOError as e:
            print(f"Error saving distance data: {e}")

    def add_vertex(self, vertex: "Vertex") -> None:
        """Add vertex to the network"""
        self._vertices[vertex.id] = vertex
        vertex._network = self

        # if vertex.is_temporary:
        #     self._temporary_vertices.add(vertex)

        # Update bin lookup
        if vertex.bin_coords:
            if vertex.bin_coords not in self._vertex_bin_lookup:
                self._vertex_bin_lookup[vertex.bin_coords] = []
            if vertex not in self._vertex_bin_lookup[vertex.bin_coords]:
                self._vertex_bin_lookup[vertex.bin_coords].append(vertex)

    def remove_vertex(self, vertex: "Vertex") -> None:
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

    def add_edge(self, edge: "Edge") -> None:
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

    def remove_edge(self, edge: "Edge") -> None:
        """Remove edge from the network"""
        if edge.id in self._edges:
            del self._edges[edge.id]

        if edge in self._temporary_edges:
            self._temporary_edges.remove(edge)

        if edge in self._detached_edges:
            self._detached_edges.remove(edge)

        # Remove from bin lookup
        for bin_coord in edge.bins_covered:
            if (
                bin_coord in self._edge_bin_lookup
                and edge in self._edge_bin_lookup[bin_coord]
            ):
                self._edge_bin_lookup[bin_coord].remove(edge)
                if not self._edge_bin_lookup[bin_coord]:
                    del self._edge_bin_lookup[bin_coord]

        edge._network = None

    def get_vertex_by_id(self, vertex_id: int) -> Optional["Vertex"]:
        """Get a vertex by its ID"""
        return self._vertices.get(vertex_id)

    def get_edge_by_id(self, edge_id: int) -> Optional["Edge"]:
        """Get an edge by its ID"""
        return self._edges.get(edge_id)

    def get_vertices_in_bin(self, lat_idx: int, lon_idx: int) -> List["Vertex"]:
        """Get all vertices in a specific spatial bin"""
        return self._vertex_bin_lookup.get((lat_idx, lon_idx), [])

    def get_edges_in_bin(self, lat_idx: int, lon_idx: int) -> List["Edge"]:
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

    def get_stats(self) -> Dict[str, int]:
        """Get network statistics"""
        return {
            "vertices": len(self._vertices),
            "edges": len(self._edges),
            "temporary_vertices": len(self._temporary_vertices),
            "temporary_edges": len(self._temporary_edges),
            "detached_edges": len(self._detached_edges),
        }

    def get_all_vertices(self) -> List["Vertex"]:
        """Get a list of all vertices in the network"""
        return list(self._vertices.values())

    def get_all_edges(self) -> List["Edge"]:
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

    def reset_id_counters(self) -> None:
        """Reset vertex and edge ID counters based on current max IDs"""
        self._vertex_id_counter = self.get_max_vertex_id() + 1
        self._edge_id_counter = self.get_max_edge_id() + 1

    def __repr__(self):
        return f"Network(vertices={len(self._vertices)}, edges={len(self._edges)})"

    def __eq__(self, other):
        return (
            isinstance(other, Network)
            and self._vertices == other._vertices
            and self._edges == other._edges
            and self._temporary_vertices == other._temporary_vertices
            and self._temporary_edges == other._temporary_edges
            and self._detached_edges == other._detached_edges
            and self._vertex_id_counter == other._vertex_id_counter
            and self._edge_id_counter == other._edge_id_counter
        )
