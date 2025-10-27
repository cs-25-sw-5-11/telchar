from classes.classes import Vertex
from tqdm import tqdm

def filter_largest_network(networks: list["Vertex"]) -> None:
    print("Filtering out vertices and edges not belonging to the largest network...")
    largest_network = max(networks, key=len)
    # Remove vertices not in largest network
    to_remove_vertices = []
    for vertex in tqdm(Vertex.get_all_vertices(), desc="Identifying vertices to remove"):
        if vertex not in largest_network:
            to_remove_vertices.append(vertex)
    for vertex in tqdm(to_remove_vertices, desc="Deleting vertices"):
        vertex.delete_vertex()
    return