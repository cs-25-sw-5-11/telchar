from extract_osm_map.extract_osm_map import extract_roads, extract_nodes, write_to_json, extract_map
import xml.etree.ElementTree as ET
import pytest
from .utils_functions import setup_mock_osm_file, delete_mock_osm_file
from extract_osm_map.extract_osm_map import (
    extract_map,
    extract_nodes,
    extract_roads,
    write_to_json,
)
import os
import json

def test_unit_extract_roads_returns_correct_output():
    # Arrange
    setup_mock_osm_file()
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

    # Act
    tree = ET.parse("mock_osm.osm")
    root = tree.getroot()

    roads = extract_roads(root, accepted_values)

    delete_mock_osm_file()

    # Assert
    assert len(roads) == 2  # Only 2 roads should be extracted
    assert "1" in roads
    assert roads["1"]["oneway"] is True
    assert roads["1"]["road_type"] == "primary"
    assert roads["1"]["nodes"] == ["1001", "1002", "1003"]
    assert "2" in roads
    assert roads["2"]["oneway"] is False
    assert roads["2"]["road_type"] == "primary"
    assert roads["2"]["nodes"] == ["1003", "1004"]
    assert "3" not in roads  # The way with highway=lane should be ignored


def test_unit_extract_nodes_returns_correct_output():
    setup_mock_osm_file()

    tree = ET.parse("mock_osm.osm")
    root = tree.getroot()

    nodes = extract_nodes(root)

    delete_mock_osm_file()

    assert len(nodes) == 5
    assert nodes["1001"] == {"lat": 45.001, "lon": 126.001}
    assert nodes["1002"] == {"lat": 45.002, "lon": 126.002}
    assert nodes["1003"] == {"lat": 45.003, "lon": 126.003}
    assert nodes["1004"] == {"lat": 45.004, "lon": 126.004}
    assert nodes["1005"] == {"lat": 45.005, "lon": 126.005}


def test_unit_write_to_json_creates_correct_file():
    data = {
        "roads": {
            "1": {
                "oneway": True,
                "road_type": "primary",
                "nodes": ["1001", "1002", "1003"],
            }
        },
        "nodes": {
            "1001": {"lat": 45.001, "lon": 126.001},
            "1002": {"lat": 45.002, "lon": 126.002},
            "1003": {"lat": 45.003, "lon": 126.003},
        },
    }
    output_file = "test_output.json"
    write_to_json(data, output_file)

    # Verify file contents
    with open(output_file, "r", encoding="utf-8") as f:
        loaded_data = json.load(f)

    # Clean up
    os.remove(output_file)

    assert loaded_data == data


def test_unit_extract_map_fails_with_invalid_path():
    with pytest.raises(FileNotFoundError) as e:
        extract_map("mock_osm.osm", "test")
    assert "No such file or directory" in str(e.value)


def test_unit_extract_map_skips_if_already_extracted(capsys):
    setup_mock_osm_file()
    output_dir = "test_output_dir"
    os.makedirs(output_dir, exist_ok=True)

    nodes_file = os.path.join(output_dir, "osm_nodes_output.json")
    roads_file = os.path.join(output_dir, "osm_roads_output.json")

    # Create dummy output files to simulate already extracted data
    with open(nodes_file, "w", encoding="utf-8") as f:
        f.write("{}")
    with open(roads_file, "w", encoding="utf-8") as f:
        f.write("{}")

    returned_nodes_file, returned_roads_file = extract_map("mock_osm.osm", output_dir)

    delete_mock_osm_file()
    os.remove(nodes_file)
    os.remove(roads_file)
    os.rmdir(output_dir)

    captured = capsys.readouterr()
    stdout = captured.out

    assert returned_nodes_file == nodes_file
    assert returned_roads_file == roads_file
    assert "skipping map extraction. Map already extracted." in stdout


def test_integration_extract_map_creates_correct_output_files():
    setup_mock_osm_file()
    output_dir = "test_output_dir"
    os.makedirs(output_dir, exist_ok=True)

    nodes_file, roads_file = extract_map("mock_osm.osm", output_dir)

    with open(nodes_file, "r", encoding="utf-8") as f:
        nodes_data = json.load(f)
    with open(roads_file, "r", encoding="utf-8") as f:
        roads_data = json.load(f)

    delete_mock_osm_file()
    os.remove(nodes_file)
    os.remove(roads_file)
    os.rmdir(output_dir)

    assert len(nodes_data) == 5
    assert len(roads_data) == 2
    assert nodes_data == {
        "1001": {"lat": 45.001, "lon": 126.001},
        "1002": {"lat": 45.002, "lon": 126.002},
        "1003": {"lat": 45.003, "lon": 126.003},
        "1004": {"lat": 45.004, "lon": 126.004},
        "1005": {"lat": 45.005, "lon": 126.005},
    }
    assert roads_data == {
        "1": {
            "oneway": True,
            "road_type": "primary",
            "nodes": ["1001", "1002", "1003"],
        },
        "2": {"oneway": False, "road_type": "primary", "nodes": ["1003", "1004"]},
    }
