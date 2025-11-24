import os
from classes.trip import Trip, Network
from graph_building.build_graph import build_graph
from extract_osm_map.extract_osm_map import extract_map

def setup_mock_osm_file():
    # Create a mock OSM file for testing
    with open("mock_osm.osm", "w", encoding="utf-8") as f:
        f.write(
            """<?xml version='1.0' encoding='UTF-8'?>
                <osm version="0.6" generator="Overpass API 0.7.62.8 e802775f">
                  <node id="1001" lat="45.001" lon="126.001"/>
                  <node id="1002" lat="45.002" lon="126.002"/>
                  <node id="1003" lat="45.003" lon="126.003"/>
                  <node id="1004" lat="45.004" lon="126.004"/>
                  <node id="1005" lat="45.005" lon="126.005"/>
                  <way id="1">
                    <nd ref="1001"/>
                    <nd ref="1002"/>
                    <nd ref="1003"/>
                    <tag k="highway" v="primary"/>
                    <tag k="oneway" v="yes"/>
                  </way>
                  <way id="2">
                    <nd ref="1003"/>
                    <nd ref="1004"/>
                    <tag k="highway" v="primary"/>
                  </way>
                  <way id="3">
                    <nd ref="1004"/>
                    <nd ref="1005"/>
                    <tag k="highway" v="lane"/>
                  </way>                          
                </osm>"""
        )

def setup_more_complex_mock_osm_file():
    # Create a mock OSM file for testing
    with open("mock_osm.osm", "w", encoding="utf-8") as f:
        f.write(
            """<?xml version='1.0' encoding='UTF-8'?>
                <osm version="0.6" generator="Overpass API 0.7.62.8 e802775f">
                  <node id="1001" lat="45.7015" lon="126.5505"/>
                  <node id="1002" lat="45.7025" lon="126.5505"/>
                  <node id="1003" lat="45.7035" lon="126.5505"/>
                  <node id="1004" lat="45.7045" lon="126.5505"/>
                  <node id="1005" lat="45.7055" lon="126.5505"/>
                  <node id="2001" lat="45.7515" lon="126.6505"/>
                  <node id="2002" lat="45.7525" lon="126.6505"/>
                  <node id="2003" lat="45.7535" lon="126.6505"/>
                  <node id="2004" lat="45.7545" lon="126.6505"/>
                  <node id="2005" lat="45.7555" lon="126.6505"/>
                  <way id="1">
                    <nd ref="1001"/>
                    <nd ref="1002"/>
                    <nd ref="1003"/>
                    <tag k="highway" v="primary"/>
                    <tag k="oneway" v="yes"/>
                  </way>
                  <way id="2">
                    <nd ref="1003"/>
                    <nd ref="1004"/>
                    <tag k="highway" v="primary"/>
                  </way>
                  <way id="3">
                    <nd ref="1004"/>
                    <nd ref="1005"/>
                    <tag k="highway" v="primary"/>
                  </way>
                  <way id="4">
                    <nd ref="2005"/>
                    <nd ref="2004"/>
                    <nd ref="2003"/>
                    <nd ref="2002"/>
                    <nd ref="2001"/>
                    <tag k="highway" v="primary"/>
                    <tag k="oneway" v="yes"/>
                  </way>
                  <way id="5">
                    <nd ref="2002"/>
                    <nd ref="1002"/>
                    <tag k="highway" v="secondary"/>
                    <tag k="oneway" v="yes"/>
                  </way>
                  <way id="6">
                    <nd ref="1005"/>
                    <nd ref="2005"/>
                    <tag k="highway" v="secondary"/>
                    <tag k="oneway" v="yes"/>
                  </way>
                </osm>"""
        )


def delete_mock_osm_file():
    os.remove("mock_osm.osm")

def integration_clean_trips_setup():
    temp_data = [
        ["1", "45.70000", "126.50000", "0"],
        ["1", "45.70001", "126.50001", "60"],
        ["1", "45.70002", "126.50002", "120"],
        ["2", "45.70000", "126.50000", "0"],
        ["2", "45.70001", "126.50001", "0"],
        ["2", "45.70002", "126.50002", "0"],
        ["3", "47.70000", "128.50000", "0"],
        ["3", "48.70000", "129.50000", "60"],
        ["3", "49.70000", "130.50000", "120"],
        ["4", "50.70000", "131.50000", "0"],
        ["4", "50.70001", "131.50001", "60"],
        ["4", "50.70002", "131.50002", "120"],
    ]

    # Make temporary input dir and create a CSV file.
    os.makedirs("temp_input_dir", exist_ok=False)
    with open("temp_input_dir/temp_file.csv", "w", encoding="utf-8") as f:
        f.write("trip_id,lat,lon,timestamp\n")
        for row in temp_data:
            f.write(",".join(row) + "\n")

    os.makedirs("temp_output_dir", exist_ok=False)


def integration_clean_trips_cleanup():
    # Clean up temporary files and directories created in setup.
    os.remove("temp_input_dir/temp_file.csv")
    os.rmdir("temp_input_dir")

    os.remove("temp_output_dir/temp_file.csv")
    os.rmdir("temp_output_dir")

def build_graph_with_mock_data():
    setup_more_complex_mock_osm_file()

    nodes_file, roads_file = extract_map(osm_file_path="mock_osm.osm", output_dir=".")

    network = build_graph(nodes_file, roads_file)
    delete_mock_osm_file()
    os.remove(nodes_file)
    os.remove(roads_file)
    return network

def setup_network_and_trip():
    network = build_graph_with_mock_data()
    print(network)
    network.load_or_compute_all_pairs_distances(distances_file='temp_distances.npy', mapping_file='temp_mapping.json')
    os.remove("temp_distances.npy")
    os.remove("temp_mapping.json")
    trip = Trip(network=network, trip_id=1,
                lats=[], lons=[], times=[])
    
    return network, trip
