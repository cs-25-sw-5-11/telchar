import glob
import json
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd

# Path to the JSON file generated from OSM
data_file = "cleaned_data/osm_roads_output.json"

with open(data_file, "r", encoding="utf-8") as f:
    roads = json.load(f)

plt.figure(figsize=(10, 8))

# Plot OSM roads
for road in roads:
    lons = []
    lats = []
    for node in road["nodes"]:
        if node["lat"] is not None and node["lon"] is not None:
            lons.append(node["lon"])
            lats.append(node["lat"])
    if lons and lats:
        plt.plot(lons, lats, "-", linewidth=1, alpha=0.7, color="grey", zorder=1)

# Identify nodes used in more than one road
node_usage = Counter()
for road in roads:
    for node in road["nodes"]:
        if node["lat"] is not None and node["lon"] is not None:
            node_usage[(node["lat"], node["lon"])] += 1

multi_road_nodes = [(lat, lon) for (lat, lon), count in node_usage.items() if count > 1]

# Plot black dots for nodes used in more than one road
if multi_road_nodes:
    lats, lons = zip(*multi_road_nodes)
    plt.scatter(lons, lats, c="black", s=5, zorder=3)

# CSV files pattern
csv_files = glob.glob("cleaned_data/trips_*03.csv")

# Plot only a single trip from each CSV file, and zoom to its extent
trip_to_plot = 6
trip_bounds = []
for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file)
        if (
            "latitude" in df.columns
            and "longitude" in df.columns
            and "trip_id" in df.columns
        ):
            if trip_to_plot in df["trip_id"].values:
                trip_points = df[df["trip_id"] == trip_to_plot]
                plt.plot(
                    trip_points["longitude"],
                    trip_points["latitude"],
                    "-",
                    linewidth=2,
                    alpha=0.9,
                    zorder=3,
                    color="blue",
                    label=f"Trip {trip_to_plot}",
                )
                # Collect bounds
                min_lon, max_lon = (
                    trip_points["longitude"].min(),
                    trip_points["longitude"].max(),
                )
                min_lat, max_lat = (
                    trip_points["latitude"].min(),
                    trip_points["latitude"].max(),
                )
                trip_bounds.append((min_lon, max_lon, min_lat, max_lat))
    except Exception as e:
        print(f"Error loading {csv_file}: {e}")

# Set axis limits to just fit the plotted trip(s)
if trip_bounds:
    min_lon = min(b[0] for b in trip_bounds)
    max_lon = max(b[1] for b in trip_bounds)
    min_lat = min(b[2] for b in trip_bounds)
    max_lat = max(b[3] for b in trip_bounds)
    lon_pad = (max_lon - min_lon) * 0.15 if max_lon > min_lon else 0.001
    lat_pad = (max_lat - min_lat) * 0.15 if max_lat > min_lat else 0.001
    plt.xlim(min_lon - lon_pad, max_lon + lon_pad)
    plt.ylim(min_lat - lat_pad, max_lat + lat_pad)

plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title(f"OSM Roads Plot with Trip {trip_to_plot}")
plt.grid(False)
plt.tight_layout()
plt.legend()
plt.show()
