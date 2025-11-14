import pandas as pd
import geopandas as gpd
from datetime import timedelta
from fmm import STMATCH, STMATCHConfig, Network, NetworkGraph, GPSConfig, ResultConfig


def get_edge_lengths_from_shapefile(shapefile_path):
    print("Loading edge lengths from shapefile...")
    edges_gdf = gpd.read_file(shapefile_path)

    # Project to metric CRS if needed
    if edges_gdf.crs.is_geographic:
        edges_gdf = edges_gdf.to_crs("EPSG:32651")  # UTM for Harbin

    edge_lengths = {}
    for idx, row in edges_gdf.iterrows():
        edge_id = row["fid"]
        edge_lengths[edge_id] = row.geometry.length

    print(f"Loaded {len(edge_lengths)} edge lengths")
    return edge_lengths


def parse_stmatch_results(result_file, gps_file, edge_lengths):
    print("Parsing STMatch results...")
    result_df = pd.read_csv(result_file, sep=";")

    gps_df = pd.read_csv(gps_file, sep=";")

    result_df["edges"] = result_df["cpath"].apply(
        lambda x: [int(e) for e in str(x).split(",")]
        if pd.notna(x) and str(x) != ""
        else []
    )

    traversals = []

    for idx, row in result_df.iterrows():
        trip_id = row["id"]
        edges = row["edges"]

        if not edges or len(edges) == 0:
            continue

        # Get GPS points for this trip
        trip_gps = (
            gps_df[gps_df["trip_id"] == trip_id]
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        if len(trip_gps) < 2:
            continue

        # Calculate traversal info for each edge
        total_time = trip_gps["timestamp"].iloc[-1] - trip_gps["timestamp"].iloc[0]
        total_length = sum([edge_lengths.get(edge_id, 100) for edge_id in edges])

        if total_time <= 0 or total_length <= 0:
            continue

        # Distribute time across edges proportionally
        cumulative_time = trip_gps["timestamp"].iloc[0]

        for edge_id in edges:
            edge_length = edge_lengths.get(edge_id, 100)
            edge_time = (edge_length / total_length) * total_time

            # Calculate speed
            if edge_time > 0:
                speed_ms = edge_length / edge_time
                speed_kmh = speed_ms * 3.6
            else:
                speed_kmh = 0

            traversals.append(
                {
                    "timestamp": cumulative_time,
                    "edge_id": edge_id,
                    "speed_kmh": round(speed_kmh, 2),
                    "traversal_time_seconds": round(edge_time, 2),
                }
            )

            cumulative_time += edge_time

    return pd.DataFrame(traversals)


def create_time_edge_matrix(
    traversals_df, time_interval_minutes=5, output_file="edge_data.csv"
):
    print("Creating time edge matrix")
    # Convert Unix timestamps to datetime
    traversals_df["datetime"] = pd.to_datetime(traversals_df["timestamp"], unit="s")

    # Find start and end of day
    start_of_day = (
        traversals_df["datetime"]
        .min()
        .replace(hour=0, minute=0, second=0, microsecond=0)
    )
    end_of_day = start_of_day + timedelta(days=1)

    time_slots = pd.date_range(
        start=start_of_day, end=end_of_day, freq=f"{time_interval_minutes}min"
    )[:-1]

    # Assign each traversal to a time slot
    traversals_df["time_slot"] = pd.cut(
        traversals_df["datetime"],
        bins=pd.date_range(
            start=start_of_day, end=end_of_day, freq=f"{time_interval_minutes}min"
        ),
        labels=time_slots,
        include_lowest=True,
    )

    all_edges = sorted(traversals_df["edge_id"].unique())

    # Aggregate: for each (time_slot, edge), calculate mean traversal time
    aggregated = (
        traversals_df.groupby(["time_slot", "edge_id"])["traversal_time_seconds"]
        .mean()
        .reset_index()
    )

    # Pivot to create matrix: rows=time_slots, columns=edges
    matrix = aggregated.pivot(
        index="time_slot", columns="edge_id", values="traversal_time_seconds"
    )

    # Reindex to include all time slots and all edges
    matrix = matrix.reindex(index=time_slots, columns=all_edges)

    # Fill missing values with -1 (no data for that time slot)
    matrix = matrix.fillna(-1)

    matrix.index = matrix.index.strftime("%H:%M")
    matrix.columns = [f"edge{edge_id}_traversal_time_sec" for edge_id in matrix.columns]
    matrix = matrix.reset_index()
    matrix = matrix.rename(columns={"index": "time_slot"})

    matrix.to_csv(output_file, index=False)

    print(f"Matrix saved to {output_file}")
    print(f"Shape: {matrix.shape}")
    print(f"Non-empty cells: {(matrix.iloc[:, 1:] != -1).sum().sum()}")

    return matrix


def generate_vertex_csv(shapefile_path, output_file="vertex.csv"):
    print("Generating vertex.csv...")
    edges_gdf = gpd.read_file(shapefile_path)

    # Ensure we're in lat/lon
    if not edges_gdf.crs.is_geographic:
        edges_gdf = edges_gdf.to_crs("EPSG:4326")

    vertices = {}

    for idx, row in edges_gdf.iterrows():
        u = row["u"]
        v = row["v"]
        geom = row.geometry

        start_point = geom.coords[0]
        end_point = geom.coords[-1]

        if u not in vertices:
            vertices[u] = {"longitude": start_point[0], "latitude": start_point[1]}
        if v not in vertices:
            vertices[v] = {"longitude": end_point[0], "latitude": end_point[1]}

    # Create DataFrame
    vertex_df = pd.DataFrame(
        [
            {
                "node_id": node_id,
                "longitude": coords["longitude"],
                "latitude": coords["latitude"],
            }
            for node_id, coords in vertices.items()
        ]
    )

    vertex_df = vertex_df.sort_values("node_id").reset_index(drop=True)
    vertex_df.to_csv(output_file, index=False)

    print(f"Saved {len(vertex_df)} vertices to {output_file}")
    return vertex_df


def generate_edge_connections_csv(shapefile_path, output_file="edge_connections.csv"):
    print("Generating edge_connections.csv...")
    edges_gdf = gpd.read_file(shapefile_path)

    edge_connections = []

    for idx, row in edges_gdf.iterrows():
        edge_connections.append(
            {
                "edge_id": row["fid"],
                "vertex_start_id": row["u"],
                "vertex_end_id": row["v"],
            }
        )

    edge_conn_df = pd.DataFrame(edge_connections)
    edge_conn_df = edge_conn_df.sort_values("edge_id").reset_index(drop=True)
    edge_conn_df.to_csv(output_file, index=False)

    print(f"Saved {len(edge_conn_df)} edge connections to {output_file}")
    return edge_conn_df


def process_single_day(gps_file, network_file, result_file, edge_data_file):
    print(f"\n=== Processing file: {gps_file} ===")

    network = Network(network_file, "fid", "u", "v")
    graph = NetworkGraph(network)
    model = STMATCH(network, graph)
    stmatch_config = STMATCHConfig()

    input_config = GPSConfig()
    input_config.file = gps_file
    input_config.id = "trip_id"
    input_config.x = "longitude"
    input_config.y = "latitude"
    input_config.timestamp = "timestamp"
    input_config.gps_point = True

    result_config = ResultConfig()
    result_config.file = result_file

    model.match_gps_file(input_config, result_config, stmatch_config)

    edge_lengths = get_edge_lengths_from_shapefile(network_file)
    traversals_df = parse_stmatch_results(result_file, gps_file, edge_lengths)
    matrix = create_time_edge_matrix(
        traversals_df, time_interval_minutes=5, output_file=edge_data_file
    )

    return matrix


if __name__ == "__main__":
    gps_files = [
        "./data/output_data/edge_data_day3.csv",
        "./data/output_data/edge_data_day4.csv",
        "./data/output_data/edge_data_day5.csv",
        "./data/output_data/edge_data_day6.csv",
        "./data/output_data/edge_data_day7.csv",
    ]
    network_file = "./data/osm_data/harbin/edges.shp"

    vertex_df = generate_vertex_csv(network_file, "./data/output_data/vertex.csv")
    edge_conn_df = generate_edge_connections_csv(
        network_file, "./data/output_data/edge_connections.csv"
    )

    matrices = []
    for i, gps_file in enumerate(gps_files, start=3):
        result_file = f"./data/output_data/matched_data_day{i}.txt"
        edge_data_file = f"./data/output_data/edge_data_day{i}.csv"
        matrix = process_single_day(gps_file, network_file, result_file, edge_data_file)
        matrices.append(matrix)
