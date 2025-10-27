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

nodes_output = {}
for node_id, (lat, lon) in nodes.items():
    nodes_output[node_id] = {'lat': lat, 'lon': lon}

with open('./cleaned_data/osm_nodes_output.json', 'w', encoding='utf-8') as f:
    json.dump(nodes_output, f, ensure_ascii=False, indent=2)


# Extract roads (ways with highway tag)
output = {}
for way in root.findall('way'):
    is_road = False
    oneway = None
    type = None
    for tag in way.findall('tag'):
        if tag.attrib.get('k') == 'highway' and tag.attrib.get('v') in accepted_values:
            is_road = True
            type = tag.attrib.get('v')
        if tag.attrib.get('k') == 'oneway':
            oneway = tag.attrib.get('v')
            if oneway == 'yes':
                oneway = True
            elif oneway == 'no':
                oneway = False
            else:
                oneway = None  # Unknown values.

    if is_road:
        nodes = [nd.attrib['ref'] for nd in way.findall('nd')]
        output[way.attrib['id']] = {'oneway': oneway, 'type': type, 'nodes': nodes}

with open('./cleaned_data/osm_roads_output.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)