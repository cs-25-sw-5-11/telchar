import json
from collections import Counter
from classes import Network, Vertex, Edge
from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from tqdm import tqdm

def build_graph(nodes_file: str, roads_file: str) -> Network:
    """Main function for creating a network"""
    network = Network()

    with open(nodes_file, "r", encoding="utf-8") as f:
        nodes_dict = json.load(f)
    with open(roads_file, "r", encoding="utf-8") as f:
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
