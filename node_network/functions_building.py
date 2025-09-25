import json
from collections import Counter
from classes import Vertex, Edge
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from tqdm import tqdm

def build_graph():
    # Clear existing data
    Vertex.vertex_dict.clear()
    Vertex._id_counter = 1
    Edge.edge_dict.clear()
    Edge._id_counter = 0

    with open('./cleaned_data/osm_nodes_output.json', 'r', encoding='utf-8') as f:
        nodes_dict = json.load(f)
    with open('./cleaned_data/osm_roads_output.json', 'r', encoding='utf-8') as f:
        roads_dict = json.load(f)
    
    # Convert dict to list of roads for processing
    roads = []
    for road_id, road_data in roads_dict.items():
        if 'nodes' in road_data and road_data['nodes']:
            road_data['id'] = road_id
            roads.append(road_data)
    
    print("Step 1: Creating initial edges and vertices from roads...")
    # Step 1: Create edges and vertices from roads (one edge per road, plus start/end vertices)
    for road in tqdm(roads, desc="Creating initial edges"):
        nodes = road['nodes']
        if len(nodes) < 2:
            continue
            
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
        non_vertex_nodes = [
            (nodes_dict[node_id]['lat'], nodes_dict[node_id]['lon'], int(node_id))
            for node_id in nodes[1:-1]
        ]
        
        # Create the edge
        Edge(start_vertex, end_vertex, non_vertex_nodes, road_type, oneway)
    
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
        # Convert to int for consistent vertex lookup
        int_node_id = int(node_id) if isinstance(node_id, str) else node_id
        if int_node_id not in Vertex.vertex_dict:  # Don't recreate if already exists
            node_data = nodes_dict[node_id]
            Vertex(node_data['lat'], node_data['lon'], int_node_id)
    
    print("Step 4: Splitting edges at intersection points...")
    # Step 4: Split edges where non-vertex nodes should actually be vertices
    edges_to_process = list(Edge.edge_dict.values())  # Get current edges
    
    for original_edge in tqdm(edges_to_process, desc="Processing edges"):
        # Find all vertices that need to be split on this edge
        vertices_to_split = []
        for lat, lon, node_id in original_edge.non_vertex_nodes:
            if str(node_id) in should_be_vertices:
                # Convert to int for consistent vertex lookup
                int_node_id = int(node_id) if isinstance(node_id, str) else node_id
                vertex = Vertex.vertex_dict[int_node_id]
                vertices_to_split.append(vertex)
        
        # Split the edge at all vertices (this handles multiple splits correctly)
        if vertices_to_split:
            current_edge = original_edge
            for vertex in vertices_to_split:
                try:
                    result = current_edge.split_edge_along_vertex(vertex, temporary=False)
                    if result is not None:
                        edge1, edge2 = result
                        # Continue with the second edge for further splits
                        current_edge = edge2
                    # If result is None, the vertex was already at start/end, so no split needed
                except ValueError:
                    # Vertex not found on current edge (might have been split already)
                    break

    print(f"Graph construction complete!")
    print(f"Created {len(Vertex.vertex_dict)} vertices and {len(Edge.edge_dict)} edges")
    
    return Vertex.vertex_dict, Edge.edge_dict