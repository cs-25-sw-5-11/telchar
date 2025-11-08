from classes.classes import Vertex

from .filter_largest_network import filter_largest_network


def explore_neighbors(start_vertex: "Vertex", visited: set["Vertex"]) -> set["Vertex"]:
    """DFS search for all neighbors"""

    stack = [start_vertex]
    subnetwork = set()

    while stack:
        current_vertex = stack.pop()
        if current_vertex not in visited:
            visited.add(current_vertex)
            subnetwork.add(current_vertex)

            neighbors = (
                current_vertex.get_outward_vertices()
                + current_vertex.get_backward_vertices()
            )
            stack.extend([n for n in neighbors if n not in visited])

    return subnetwork


def find_road_subnetworks(vertices: list["Vertex"]) -> list[set["Vertex"]]:
    """Find all connected subnetworks"""
    visited = set()
    connected_road_subnetworks = []

    for vertex in vertices:
        if vertex not in visited:
            subnetwork = explore_neighbors(vertex, visited)
            connected_road_subnetworks.append(subnetwork)

    return connected_road_subnetworks


def find_network() -> list[set["Vertex"]]:
    """Main function, finds all connected road networks"""
    vertices = Vertex.get_all_vertices()
    networks = find_road_subnetworks(vertices)

    print(f"Number of networks (connected components): {len(networks)}")
    filter_largest_network(networks)

    return networks

