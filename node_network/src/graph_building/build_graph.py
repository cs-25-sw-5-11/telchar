import json
from collections import Counter
from classes import Network, Vertex, Edge
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

def create_edges_and_vertices_from_roads(network: Network, road: dict[str,any], nodes_dict: dict[str, dict[str,float]]) -> None:
    nodes = road['nodes']
    if len(nodes) < 2:
        return
        
    road_type = road.get('type', 'unknown')
    oneway = road.get('oneway', True) is True
    
    # Create vertices for start and end of road
    start_node_id = nodes[0]
    end_node_id = nodes[-1]
    
    # Get node data from nodes_dict using the node ID
    start_node_data = nodes_dict[start_node_id]
    end_node_data = nodes_dict[end_node_id]

    # Get existing vertex or create new one
    start_vertex = network.get_vertex_by_id(int(start_node_id))
    if start_vertex is None:
        start_vertex = Vertex(network, start_node_data['lat'], start_node_data['lon'], int(start_node_id))
    
    end_vertex = network.get_vertex_by_id(int(end_node_id))
    if end_vertex is None:
        end_vertex = Vertex(network, end_node_data['lat'], end_node_data['lon'], int(end_node_id))

    # All intermediate nodes are non-vertex nodes for now
    non_vertex_nodes = []
    for node_id in nodes[1:-1]:
        node_data = nodes_dict[node_id]
        non_vertex_nodes.append((node_data['lat'], node_data['lon'], int(node_id)))
    
    
    # Create the edge
    Edge(network, start_vertex, end_vertex, non_vertex_nodes, road_type, oneway)
    return

def convert_point_to_vertex(network: Network, node_id: str, nodes_dict: dict[str, dict[str,float]]) -> None:
    # Don't recreate if already exists
    if network.check_vertex_exists(int(node_id)):
        return

    node_data = nodes_dict[node_id]
    Vertex(network, node_data['lat'], node_data['lon'], int(node_id))
    return

def build_graph(nodes_file: str, roads_file: str) -> Network:
    """Main function for creating a network"""
    network = Network()

    with open(nodes_file, 'r', encoding='utf-8') as f:
        nodes_dict = json.load(f)
    with open(roads_file, 'r', encoding='utf-8') as f:
        roads_dict = json.load(f)

    all_nodes = set()
    repeated_nodes = set()

    # Determining repeated nodes and turning start and end nodes into vertices.
    for road in roads_dict.values():
        if 'nodes' not in road or not road['nodes']:
            raise ValueError("Road entry missing 'nodes' or has empty 'nodes' list.")
        for node_id in road['nodes']:
            node_id = int(node_id)
            if node_id in all_nodes:
                repeated_nodes.add(node_id)
            else:
                all_nodes.add(node_id)

        Vertex(network=network, 
               lat=nodes_dict[road['nodes'][0]]['lat'], 
               lon=nodes_dict[road['nodes'][0]]['lon'], 
               node_id=int(road['nodes'][0]))
        Vertex(network=network,
               lat=nodes_dict[road['nodes'][-1]]['lat'], 
               lon=nodes_dict[road['nodes'][-1]]['lon'], 
               node_id=int(road['nodes'][-1]))

    # Create vertices for all repeated nodes
    for node_id in repeated_nodes:
        Vertex(network=network,
               lat=nodes_dict[str(node_id)]['lat'],
               lon=nodes_dict[str(node_id)]['lon'],
               node_id=node_id)
        
    # Creating edges from roads, but broken up by vertices.
    for road in roads_dict.values():
        road_type = road.get('type', 'unknown')
        oneway = road.get('oneway', True) is True
        nodes = road['nodes']
        if len(nodes) < 2: # An edge must span at least two points.
            continue

        start_vertex = network.get_vertex_by_id(int(nodes[0]))
        current_edge_nodes = []
        for node_id in nodes[1:]:
            node_id_int = int(node_id)
            if network.check_vertex_exists(node_id_int):
                # Create edge up to this vertex
                end_vertex = network.get_vertex_by_id(node_id_int)
                Edge(network, start_vertex, end_vertex, current_edge_nodes, road_type, oneway)
                # Reset for next edge segment
                start_vertex = end_vertex
                current_edge_nodes = []
            else:
                node_data = nodes_dict[str(node_id_int)]
                current_edge_nodes.append((node_data['lat'], node_data['lon'], node_id_int))

    return network

    # Convert dict to list of roads for processing
    roads = convert_json_roads_to_list(roads_dict)

    print("Step 1: Creating initial edges and vertices from roads...")
    # Step 1: Create edges and vertices from roads (one edge per road, plus start/end vertices)
    for road in tqdm(roads, desc="Creating initial edges"):
        road_type = road.get('type', 'unknown')
        oneway = road.get('oneway', True) is True


        create_edges_and_vertices_from_roads(network, road, nodes_dict)
    
    print("Step 2: Identifying shared nodes...")
    # Step 2: Count node usage to identify which nodes should be vertices
    node_usage = Counter()
    for road in tqdm(roads, desc="Counting node usage"):
        for node_id in road['nodes']:
            node_usage[node_id] += 1
    
    # Nodes that appear in multiple roads should be vertices
    should_be_vertices = { node_id for node_id, count in node_usage.items() if count > 1 }
    
    print(f"Found {len(should_be_vertices)} shared nodes")
    
    print("Step 3: Creating vertex objects for intersection nodes...")
    # Step 3: Create vertex objects for nodes that should be vertices
    for node_id in tqdm(should_be_vertices, desc="Creating vertices"):
        convert_point_to_vertex(network, node_id, nodes_dict)
        
    
    print("Step 4: Splitting edges at intersection points...")
    # Step 4: Split edges where non-vertex nodes should actually be vertices
    edges_to_process = network.get_all_edges()  # Get current edges
    process_edges_to_split(network, edges_to_process, should_be_vertices)
    
    print("Graph building complete.")

    return network
