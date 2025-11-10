from classes.classes import Vertex
from tqdm import tqdm


def get_vertices_to_split(edge, should_be_vertices) -> list["Vertex"]:
    vertices = []
    for lat, lon, node_id in edge.non_vertex_nodes:
        # Convert to string for consistent lookup (should_be_vertices contains strings)
        node_id_str = str(node_id)
        if node_id_str in should_be_vertices:
            # Convert to int for vertex lookup
            vertex = Vertex.get_vertex_by_id(int(node_id))
            if vertex is not None:  # Only add if vertex actually exists
                vertices.append(vertex)
    return vertices


def split_edge_at_vertices(edge, vertices_to_split: list["Vertex"]) -> None:
    current_edge = edge
    for vertex in vertices_to_split:
        if vertex is None:  # Skip None vertices
            continue
        try:
            result = current_edge.split_edge_along_vertex(vertex, temporary=False)
            if result is not None:
                _, edge2 = result
                current_edge = edge2
        except ValueError:
            # If vertex not found on edge, continue with next vertex
            continue

    return


def process_edges_to_split(edges_to_process, should_be_vertices) -> None:
    """Main function to process all edges"""
    for edge in tqdm(edges_to_process, desc="Processing edges"):
        vertices_to_split = get_vertices_to_split(edge, should_be_vertices)
        if vertices_to_split:
            split_edge_at_vertices(edge, vertices_to_split)
    return
