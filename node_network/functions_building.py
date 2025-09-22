import json
from collections import Counter
from classes import Vertex, Edge
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from tqdm import tqdm

def load_osm_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_graph(roads):
    from classes import Edge  # Ensure Edge class is up to date
    Edge.edge_dict.clear()
    Edge._id_counter = 0
    node_usage = Counter()
    for road in roads:
        for node in road['nodes']:
            if node['lat'] is not None and node['lon'] is not None:
                node_usage[(node['id'], node['lat'], node['lon'])] += 1
    vertex_set = set()
    for road in roads:
        nodes = [n for n in road['nodes'] if n['lat'] is not None and n['lon'] is not None]
        if not nodes:
            continue
        vertex_set.add((nodes[0]['id'], nodes[0]['lat'], nodes[0]['lon']))
        vertex_set.add((nodes[-1]['id'], nodes[-1]['lat'], nodes[-1]['lon']))
        for n in nodes:
            if node_usage[(n['id'], n['lat'], n['lon'])] > 1:
                vertex_set.add((n['id'], n['lat'], n['lon']))
    vertices = {v: Vertex(*v) for v in vertex_set}
    edges = []
    for road in roads:
        nodes = [n for n in road['nodes'] if n['lat'] is not None and n['lon'] is not None]
        if len(nodes) < 2:
            continue
        seg_start = 0
        while seg_start < len(nodes) - 1:
            for seg_end in range(seg_start + 1, len(nodes)):
                n = nodes[seg_end]
                key = (n['id'], n['lat'], n['lon'])
                if key in vertices or seg_end == len(nodes) - 1:
                    start_key = (nodes[seg_start]['id'], nodes[seg_start]['lat'], nodes[seg_start]['lon'])
                    end_key = (nodes[seg_end]['id'], nodes[seg_end]['lat'], nodes[seg_end]['lon'])
                    if start_key in vertices and end_key in vertices and seg_end > seg_start:
                        non_vertex_nodes = [
                            (nodes[i]['lat'], nodes[i]['lon'])
                            for i in range(seg_start + 1, seg_end)
                            if (nodes[i]['id'], nodes[i]['lat'], nodes[i]['lon']) not in vertices
                        ]
                        edge = Edge(vertices[start_key], vertices[end_key], non_vertex_nodes)
                        edges.append(edge)
                        # Add to both vertices' neighbor dicts
                        vertices[start_key].neighbors[edge] = vertices[end_key]
                        vertices[end_key].neighbors[edge] = vertices[start_key]
                    seg_start = seg_end
                    break
            else:
                break
    return vertices, edges