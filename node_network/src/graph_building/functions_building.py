import json
from collections import Counter
from classes.classes import Vertex, Edge
from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from tqdm import tqdm
from .split_edges_intersection import process_edges_to_split


def convert_json_roads_to_list(roads_dict: dict[str,any]) -> list:
    roads = []
    for road_id, road_data in roads_dict.items():
        if 'nodes' in road_data and road_data['nodes']:
            road_data['id'] = road_id
            roads.append(road_data)
    return roads

def create_edge(road: dict[str,any], nodes_dict: dict[str, dict[str,float]]) -> None:
    nodes = road['nodes']
    if len(nodes) < 2:
        return
        
    road_type = road.get('type', 'unknown')
    oneway = road.get('oneway', False) is True
    
    # Create vertices for start and end of road
    start_node_id = nodes[0]
    end_node_id = nodes[-1]
    
    # Get node data from nodes_dict using the node ID
    start_node_data = nodes_dict[start_node_id]
    end_node_data = nodes_dict[end_node_id]
    
    # Constructor automatically returns existing vertex if ID already exists
    start_vertex = Vertex(start_node_data['lat'], start_node_data['lon'], int(start_node_id))
    end_vertex = Vertex(end_node_data['lat'], end_node_data['lon'], int(end_node_id))

    # All intermediate nodes are non-vertex nodes for now
    non_vertex_nodes = []
    for node_id in nodes[1:-1]:
        node_data = nodes_dict[node_id]
        non_vertex_nodes.append((node_data['lat'], node_data['lon'], int(node_id)))
    
    
    # Create the edge
    Edge(start_vertex, end_vertex, non_vertex_nodes, road_type, oneway)
    return

def convert_point_to_vertex(node_id: str, nodes_dict: dict[str, dict[str,float]]) -> None:
    # Don't recreate if already exists
    if int(node_id) in Vertex.vertex_dict:
        return

    node_data = nodes_dict[node_id]
    Vertex(node_data['lat'], node_data['lon'], int(node_id))
    return

def print_stats():
    max_vertex_id = Vertex.get_max_vertex_id()
    max_edge_id = Edge.get_max_edge_id()
    print(f"Max vertex ID: {max_vertex_id}, Max edge ID: {max_edge_id}")    
    
    print(f"Graph construction complete!")
    print(f"Created {Vertex.get_num_of_vertices()} vertices and {Edge.get_num_of_edges()} edges")
    return

def build_graph(nodes_file: str, roads_file:str):
    """Main function for function_building"""
    # Clear Vertex and edge dictionaries
    Vertex.clear_all()
    Edge.clear_all()

    with open(nodes_file, 'r', encoding='utf-8') as f:
        nodes_dict = json.load(f)
    with open(roads_file, 'r', encoding='utf-8') as f:
        roads_dict = json.load(f)
    
    # Convert dict to list of roads for processing
    roads = convert_json_roads_to_list(roads_dict)
    
    print("Step 1: Creating initial edges and vertices from roads...")
    # Step 1: Create edges and vertices from roads (one edge per road, plus start/end vertices)
    for road in tqdm(roads, desc="Creating initial edges"):
        create_edge(road, nodes_dict)
    
    print("Step 2: Identifying shared nodes...")
    # Step 2: Count node usage to identify which nodes should be vertices
    node_usage = Counter()
    for road in tqdm(roads, desc="Counting node usage"):
        for node_id in road['nodes']:
            node_usage[node_id] += 1
    
    # Nodes that appear in multiple roads should be vertices
    should_be_vertices = {node_id for node_id, count in node_usage.items() if count > 1}
    
    print(f"Found {len(should_be_vertices)} shared nodes")
    
    print("Step 3: Creating vertex objects for intersection nodes...")
    # Step 3: Create vertex objects for nodes that should be vertices
    for node_id in tqdm(should_be_vertices, desc="Creating vertices"):
        convert_point_to_vertex(node_id, nodes_dict)
        
    
    print("Step 4: Splitting edges at intersection points...")
    # Step 4: Split edges where non-vertex nodes should actually be vertices
    edges_to_process = list(Edge.edge_dict.values())  # Get current edges
    process_edges_to_split(edges_to_process,should_be_vertices)
    # Print max id for edges and vertices
    
