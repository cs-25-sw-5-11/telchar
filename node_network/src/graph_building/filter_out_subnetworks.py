from classes import Network, Vertex
from tqdm import tqdm

def explore_neighbors(start_vertex: 'Vertex', visited: set['Vertex']) -> set['Vertex']:
    """DFS search for all neighbors"""

    stack = [start_vertex]
    subnetwork = set()

    while stack:
        current_vertex = stack.pop()
        if current_vertex not in visited:
            visited.add(current_vertex)
            subnetwork.add(current_vertex)

            neighbors = current_vertex.get_outward_vertices() + current_vertex.get_backward_vertices()
            stack.extend([n for n in neighbors if n not in visited])

    return subnetwork

def find_road_subnetworks(vertices: list['Vertex'])-> list[set['Vertex']]:
    """Find all connected subnetworks"""
    visited = set()
    connected_road_subnetworks = []

    for vertex in vertices:
        if vertex not in visited:
            subnetwork = explore_neighbors(vertex, visited)
            connected_road_subnetworks.append(subnetwork)

    return connected_road_subnetworks

def filter_out_smaller_subnetworks(network: Network, subnetworks: list["Vertex"]) -> None:
    print("Filtering out vertices and edges not belonging to the largest subnetwork...")
    largest_subnetwork = max(subnetworks, key=len)
    # Remove vertices not in largest subnetwork
    to_remove_vertices = []
    for vertex in tqdm(network.get_all_vertices(), desc="Identifying vertices to remove"):
        if vertex not in largest_subnetwork:
            to_remove_vertices.append(vertex)
    for vertex in tqdm(to_remove_vertices, desc="Deleting vertices"):
        network.delete_vertex_by_id(vertex.id)
    return

def remove_small_subnetworks(network: Network) -> list[set['Vertex']]:
    """Main function, finds all connected road networks"""
    vertices = network.get_all_vertices()
    subnetworks = find_road_subnetworks(vertices)

    print(f"Number of subnetworks (connected components): {len(subnetworks)}")
    filter_out_smaller_subnetworks(network, subnetworks)
