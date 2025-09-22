import xml.etree.ElementTree as ET
from collections import defaultdict
import json

osm_file = './data/map.osm'  # Change to your OSM file name
accepted_values = {
    'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential',
    'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link',
    'living_street', 'service', 'road' 
}

# Parse OSM XML
tree = ET.parse(osm_file)
root = tree.getroot()

# Extract all nodes (id -> (lat, lon))
nodes = {}
for node in root.findall('node'):
    node_id = node.attrib['id']
    lat = float(node.attrib['lat'])
    lon = float(node.attrib['lon'])
    nodes[node_id] = (lat, lon)

# Extract roads (ways with highway tag)
roads = []
for way in root.findall('way'):
    is_road = False
    oneway = None
    for tag in way.findall('tag'):
        if tag.attrib.get('k') == 'highway' and tag.attrib.get('v') in accepted_values:
            is_road = True
        if tag.attrib.get('k') == 'oneway':
            oneway = tag.attrib.get('v')
    if is_road:
        nds = [nd.attrib['ref'] for nd in way.findall('nd')]
        roads.append({'id': way.attrib['id'], 'nodes': nds, 'oneway': oneway})

# Output: print summary
print(f"Found {len(roads)} roads.")
for road in roads[:10]:  # Print first 10 roads as example
    print(f"Road id: {road['id']}, node count: {len(road['nodes'])}, oneway: {road['oneway']}")
    for node_id in road['nodes']:
        if node_id in nodes:
            lat, lon = nodes[node_id]
            print(f"  Node {node_id}: lat={lat}, lon={lon}")
        else:
            print(f"  Node {node_id}: not found in node list")
    print()

# Save all roads and their nodes (with coordinates) to a JSON file
output = []
for road in roads:
    road_nodes = []
    for node_id in road['nodes']:
        if node_id in nodes:
            lat, lon = nodes[node_id]
            road_nodes.append({'id': node_id, 'lat': lat, 'lon': lon})
        else:
            road_nodes.append({'id': node_id, 'lat': None, 'lon': None})
    output.append({'road_id': road['id'], 'nodes': road_nodes, 'oneway': road['oneway']})

with open('./cleaned_data/osm_roads_output.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print('Saved road and node data to ./cleaned_data/osm_roads_output.json')