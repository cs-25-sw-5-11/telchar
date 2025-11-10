import json
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set, TypedDict


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

    for way in root.findall("way"):
        is_road = False
        oneway = False
        road_type = ""
        for tag in way.findall("tag"):
            k = tag.attrib.get("k")
            v = tag.attrib.get("v")

            if k == "highway" and v in accepted_values:
                is_road = True
                road_type = v
            elif k == "oneway":
                if v == "yes":
                    oneway = True

        if is_road:
            node_refs = []
            for nd in way.findall("nd"):
                node_refs.append(nd.attrib["ref"])
            roads[way.attrib["id"]] = {
                "oneway": oneway,
                "road_type": road_type,
                "nodes": node_refs,
            }
    return roads


def extract_nodes(root: ET.Element) -> Dict[str, NodeInfo]:
    nodes: Dict[str, NodeInfo] = {}
    for node in root.findall("node"):
        node_id = node.attrib["id"]
        nodes[node_id] = {
            "lat": float(node.attrib["lat"]),
            "lon": float(node.attrib["lon"]),
        }

    return nodes


def write_to_json(input, output_file) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(input, f, ensure_ascii=False, indent=2)
    return None


def extract_map(osm_file_path: str, output_dir: str) -> List[str]:
    # Parse OSM XML
    accepted_values = {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "unclassified",
        "residential",
        "motorway_link",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
        "living_street",
        "service",
        "road",
    }
    tree = ET.parse(osm_file_path)
    root = tree.getroot()

    os.makedirs(output_dir, exist_ok=True)

    nodes_output_name = "osm_nodes_output.json"
    roads_output_name = "osm_roads_output.json"
    nodes_file = os.path.join(output_dir, nodes_output_name)
    roads_file = os.path.join(output_dir, roads_output_name)

    already_extracted = os.path.exists(nodes_file) and os.path.exists(roads_file)

    if not already_extracted:
        nodes = extract_nodes(root)
        write_to_json(nodes, nodes_file)

        roads = extract_roads(root, accepted_values)
        write_to_json(roads, roads_file)
    else:
        print("skipping map extraction. Map already extracted.")

    return nodes_file, roads_file
