import json
import logging
import os
from datetime import datetime

import pandas as pd
from classes.classes import Edge, Vertex
from data_cleaning.clean_trips import clean_trips
from extract_osm_map.extract_osm_map import extract_map
from graph_building.build_graph import build_graph
from graph_building.find_network import find_network
from graph_mapping.functions_mapping import find_shortest_edge_path, process_trip
from plotting.functions_plotting import plot_directed_graph
from tqdm import tqdm
from utils.functions_misc import (
    capture_network_state,
    compare_network_states,
    get_time_index,
    restore_network_to_original_state,
    writeout_traversals_to_json,
)
from viterbi.viterbi import viterbi_algorithm

logging.basicConfig(
    level=logging.WARNING,  # Set to DEBUG to see debug statements
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

# Suppress matplotlib font manager debug messages
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

COMPARE_STATES = True
PLOT = False
MAX_DIST = 100
UNIX_REFERENCE = 1420243200
TIME_INTERVAL = 300  # 5 minutes in seconds
# How often to write edge data to file (in number of trips)
WRITEOUT_INTERVAL = 1000

# input and clean data directories
DATA_INPUT_DIRECTORY = "data/input_data"
CLEANED_DATA_DIRECTORY = "data/cleaned_data"


def write_intermediate_edge_data(writeout_timer, trip_id) -> None:
    # Time readout.
    start_time = datetime.now()
    # Write edge traversals data to json file.
    print(f"Writing edge traversal data before processing trip_id {trip_id}")
    writeout_traversals_to_json(
        file_path="edge_traversals.json", edge_items=Edge.get_all_edges()
    )
    end_time = datetime.now()
    time_diff = end_time - start_time
    print(
        f"Writeout at {start_time}, took {time_diff.seconds}.{time_diff.microseconds} seconds."
    )
    return None


def extract_trip(
    df: pd.DataFrame, trip_id: int
) -> tuple[list[float], list[float], list[float]] | None:
    try:
        group = df[df["trip_id"] == trip_id]
        lats = group["latitude"].tolist()
        lons = group["longitude"].tolist()
        times = (group["timestamp"] - UNIX_REFERENCE).tolist()

    except Exception as e:
        logger.warning(f"Skipping trip_id {trip_id} due to error: {e}")
        return None

    return lats, lons, times


def get_edges_in_path(
    best_path: list[int], time_interval: int, times: list[float]
) -> list[Edge]:
    edges_in_path = []
    for i in range(len(best_path) - 1):
        start_vertex = Vertex.get_vertex_by_id(best_path[i])
        end_vertex = Vertex.get_vertex_by_id(best_path[i + 1])
        dist, path_edges = find_shortest_edge_path(start_vertex, end_vertex)

        # 0 as reference, as times has already been adjusted for the reference value.
        time_index = get_time_index(
            timestamp=times[i], reference=0, interval=time_interval
        )
        time_diff = times[i + 1] - times[i]
        speed = int(dist / time_diff * 100)  # Convert m/s to cm/s

        for edge in path_edges:
            edge_length = int(edge.length * 100)  # Convert m to cm
            # Converting to cm and using int to save space.
            edge.parent_edge.traversals_data_update(time_index, speed, edge_length)

        edges_in_path.extend(path_edges)

    return edges_in_path


def writeout_final_result() -> None:
    with open("vertex_data.json", "w") as f:
        f.write("{\n")
        vertex_items = Vertex.get_all_vertices()
        for i, vertex in enumerate(vertex_items):
            connections = {
                "outward_edges": [edge.id for edge in vertex.get_outward_edges()],
                "backward_edges": [edge.id for edge in vertex.get_backward_edges()],
                "outward_vertices": [v.id for v in vertex.get_outward_vertices()],
                "backward_vertices": [v.id for v in vertex.get_backward_vertices()],
            }
            f.write(f'\t"{vertex.id}": {json.dumps(connections)}')
            if i < len(vertex_items) - 1:
                f.write(",")
            f.write("\n")
        f.write("}\n")

    return None


def process_trip_by_id(
    trip_id: int, df: pd.DataFrame
) -> tuple[list[Edge], list[tuple[float, float]], list[float], list[float]] | None:
    result = extract_trip(df, trip_id)
    if result is None:
        return None
    lats, lons, times = result

    data_output_dict = process_trip(lats, lons, max_dist=MAX_DIST)

    if data_output_dict is None:
        logger.debug(f"Skipping trip_id {trip_id} due to no projected vertices.")
        return None

    try:
        best_path = viterbi_algorithm(data_output_dict)
    except Exception:
        return None

    edges_in_path = get_edges_in_path(best_path, TIME_INTERVAL, times)

    best_path_vertex_coords = [
        (Vertex.get_vertex_by_id(vertex_id).lat, Vertex.get_vertex_by_id(vertex_id).lon)
        for vertex_id in best_path
    ]
    for edge in edges_in_path:
        edge.parent_edge.highlighted = True
    return edges_in_path, best_path_vertex_coords, lats, lons


def main() -> None:
    cleaned_nodes_file, cleaned_roads_file = extract_map(
        DATA_INPUT_DIRECTORY, CLEANED_DATA_DIRECTORY
    )

    cleaned_files = clean_trips(
        DATA_INPUT_DIRECTORY,
        CLEANED_DATA_DIRECTORY,
        trip_id_column=0,
        lat_column=2,
        lon_column=3,
        timestamp_column=4,
    )

    build_graph(cleaned_nodes_file, cleaned_roads_file)

    _network = find_network()

    if COMPARE_STATES:
        # Capture original state for later comparison
        original_state = capture_network_state()

    for trip_file in cleaned_files:
        trip_file = os.path.basename(trip_file)
        # Load and filter trip data
        df = pd.read_csv(f"data/cleaned_data/{trip_file}")
        next_writeout = WRITEOUT_INTERVAL
        df["trip_id"].max()

        lats = None
        lons = None
        best_path_vertex_coords = None

        # TODO change to full length of cleaned file instead of trip 3-8
        for trip_id in tqdm(range(3, 8), desc=f"Processing trips in {trip_file}"):
            # Reset network state before processing each trip.
            # Here instead of at the end due to possible early continues.
            restore_network_to_original_state()

            # Writeout intermediate results periodically.
            # Needs to be right after restoration to avoid getting temporary edges.
            if trip_id >= next_writeout:
                write_intermediate_edge_data(next_writeout, trip_id)
                next_writeout += WRITEOUT_INTERVAL

            result = process_trip_by_id(trip_id, df)
            if result is None:
                continue
            edges_in_path, best_path_vertex_coords, lats, lons = result

    # Final cleanup.
    restore_network_to_original_state()
    print("Final writeout of edge traversal data...")
    writeout_traversals_to_json(
        file_path="edge_traversals.json", edge_items=Edge.get_all_edges()
    )

    if PLOT:
        plot_directed_graph(
            lat_min=45.62,
            lat_max=45.77,
            lon_min=126.65,
            lon_max=126.75,
            trip_point_lats=lats,
            trip_point_lons=lons,
            max_dist=MAX_DIST,
            best_path_vertex_coords=best_path_vertex_coords,
        )

    if COMPARE_STATES:
        # Validate integrity after restoration
        restored_state = capture_network_state()
        compare_network_states(original_state, restored_state)

    # Write vertex connections to json file
    writeout_final_result()
    return None


if __name__ == "__main__":
    main()
