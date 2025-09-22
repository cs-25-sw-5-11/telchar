import pandas as pd
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
import os
from glob import glob
import matplotlib.pyplot as plt
import pickle
from tqdm import tqdm

def log_trip_intersections(csv_file, output_file):
    df = pd.read_csv(csv_file)
    if 'trip_id' not in df.columns:
        print('No trip_id column found.')
        return []
    trips = []
    trip_ids = []
    geom_id_to_index = {}
    for trip_id, group in df.groupby('trip_id'):
        coords = list(zip(group['longitude'], group['latitude']))
        if len(coords) < 2:
            continue
        line = LineString(coords)
        trips.append(line)
        trip_ids.append(trip_id)
        geom_id_to_index[id(line)] = len(trips) - 1
    # Build spatial index
    tree = STRtree(trips)
    intersections = []
    for i, line in enumerate(tqdm(trips, desc="Checking intersections")):
        candidates = tree.query(line)
        for candidate in candidates:
            j = geom_id_to_index.get(id(candidate), None)
            if j is None or i >= j:
                continue  # Avoid duplicate/self or missing
            if line.intersects(candidate):
                intersection = line.intersection(candidate)
                if not intersection.is_empty:
                    # Handle MultiPoint or Point
                    if intersection.geom_type == 'Point':
                        intersections.append((trip_ids[i], trip_ids[j], intersection.x, intersection.y))
                    elif intersection.geom_type == 'MultiPoint':
                        for pt in intersection.geoms:
                            intersections.append((trip_ids[i], trip_ids[j], pt.x, pt.y))
    # Save intersections to file
    with open(output_file, 'wb') as f:
        pickle.dump(intersections, f)
    return intersections

def load_intersections(output_file):
    with open(output_file, 'rb') as f:
        return pickle.load(f)

def plot_intersections(intersections):
    if not intersections:
        print('No intersections to plot.')
        return
    xs = [x for _, _, x, y in intersections]
    ys = [y for _, _, x, y in intersections]
    plt.figure(figsize=(8, 6))
    plt.scatter(xs, ys, c='red', s=20, alpha=0.7)
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Trip Intersections')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main():
    data_dir = 'cleaned_data'
    csv_files = glob(os.path.join(data_dir, '*03.csv'))
    for file in csv_files:
        output_file = file + '_intersections.pkl'
        if os.path.exists(output_file):
            print(f'Loading intersections from {output_file}')
            intersections = load_intersections(output_file)
        else:
            print(f'Checking intersections in {file}')
            intersections = log_trip_intersections(file, output_file)
        plot_intersections(intersections)

if __name__ == '__main__':
    main()
