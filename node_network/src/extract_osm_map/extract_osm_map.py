import xml.etree.ElementTree as ET
import json
import os
from typing import TypedDict, Optional, List, Dict, Set


class RoadInfo(TypedDict):
    oneway: Optional[bool]
    road_type: Optional[str]
    nodes: List[str]


class NodeInfo(TypedDict):
    lat: float
    lon: float


def extract_roads(root: ET.Element, accepted_values: Set[str]) -> Dict[str, RoadInfo]:
    # Extract roads (ways with highway tag)
    roads: Dict[str, RoadInfo] = {}

    for way in root.findall('way'):
        is_road = False
        oneway: Optional[bool] = None
        road_type: Optional[str] = None
        for tag in way.findall('tag'):
            k = tag.attrib.get('k')
            v = tag.attrib.get('v')

            if k == "highway" and v in accepted_values:
                is_road = True
                road_type = v
            elif k == "oneway":
                if v == "yes":
                    oneway = True

        if is_road:
            node_refs = []
            for nd in way.findall('nd'):
                node_refs.append(nd.attrib['ref'])
            roads[way.attrib['id']] = {
                "oneway": oneway,
                "road_type": road_type,
                "nodes": node_refs
            }
    return roads


def extract_nodes(root: ET.Element) -> Dict[str, NodeInfo]:
    nodes: Dict[str, NodeInfo] = {}
    for node in root.findall('node'):
        node_id = node.attrib['id']
        nodes[node_id] = {
            'lat': float(node.attrib['lat']),
            'lon': float(node.attrib['lon'])
        }

    return nodes


def write_to_json(input, output_file) -> None:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(input, f, ensure_ascii=False, indent=2)
    return None


def extract_map(input_dir: str, output_dir: str) -> None:
    # Parse OSM XML
    accepted_values = {
        'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential',
        'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link',
        'living_street', 'service', 'road'
    }
    osm_file = os.path.join(input_dir, "map.osm")

    tree = ET.parse(osm_file)
    root = tree.getroot()

    os.makedirs(output_dir, exist_ok=True)

    nodes = extract_nodes(root)
    nodes_file = os.path.join(output_dir, "osm_nodes_output.json")
    write_to_json(nodes, nodes_file)

    roads = extract_roads(root, accepted_values)
    roads_file = os.path.join(output_dir, "osm_roads_output.json")
    write_to_json(roads, roads_file)

    return None
