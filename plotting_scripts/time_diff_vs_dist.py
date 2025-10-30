import os
import matplotlib.pyplot as plt
from glob import glob
from config import TIMESTAMP_COLUMN, LAT_COLUMN, LON_COLUMN, TRIP_ID_COLUMN

def haversine(lon1, lat1, lon2, lat2):
    # Calculate the great circle distance between two points on the earth (specified in decimal degrees)
    from math import radians, sin, cos, sqrt, asin
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2.0)**2 + cos(lat1) * cos(lat2) * sin(dlon/2.0)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

def main():
    data_dir = 'cleaned_data'
    csv_files = glob(os.path.join(data_dir, '*03.csv'))
    all_time_diffs = []
    all_distances = []
    all_speeds = []
    target_trip_id = None  # Set to a string trip_id to filter, or None to disable filtering
    for file in csv_files:
        tdiffs, dists, speeds = process_file(file, target_trip_id)
        all_time_diffs.extend(tdiffs)
        all_distances.extend(dists)
        all_speeds.extend(speeds)
    plot_time_diff_vs_distance(all_time_diffs, all_distances, target_trip_id)

def process_file(file, target_trip_id=None):
    all_time_diffs = []
    all_distances = []
    all_speeds = []
    with open(file, 'r', encoding='utf-8') as f:
        header = f.readline()
        columns = [col.strip() for col in header.strip().split(',')]
        trip_id_idx = TRIP_ID_COLUMN
        lat_idx = LAT_COLUMN
        lon_idx = LON_COLUMN
        timestamp_idx = TIMESTAMP_COLUMN
        prev_trip_id = None
        prev_time = None
        prev_lon = None
        prev_lat = None
        line_num = 1  # Start after header
        for line in f:
            line_num += 1
            parts = line.strip().split(',')
            if len(parts) <= max(trip_id_idx, lon_idx, lat_idx, timestamp_idx):
                continue
            trip_id = parts[trip_id_idx]
            lon = parts[lon_idx]
            lat = parts[lat_idx]
            timestamp = parts[timestamp_idx]
            # Only process the specified trip_id if filtering is enabled
            if target_trip_id is not None and trip_id != target_trip_id:
                prev_trip_id = trip_id
                prev_time = None
                prev_lon = None
                prev_lat = None
                continue
            # Skip if missing data
            if not (timestamp and lon and lat):
                prev_trip_id = trip_id
                prev_time = None
                prev_lon = None
                prev_lat = None
                continue
            if prev_trip_id == trip_id and prev_time is not None and prev_lon is not None and prev_lat is not None:
                try:
                    t1 = float(timestamp)
                    t0 = float(prev_time)
                    diff = t1 - t0
                    if diff == 0:
                        print(f"Zero time difference detected in file {file}, trip_id {trip_id}, at line {line_num} (timestamp={timestamp})")
                    lon1 = float(lon)
                    lat1 = float(lat)
                    lon0 = float(prev_lon)
                    lat0 = float(prev_lat)
                    dist = haversine(lon0, lat0, lon1, lat1)
                    all_time_diffs.append(diff)
                    all_distances.append(dist)
                    # Calculate speed in km/h if time diff > 0
                    if diff > 0:
                        speed = dist / (diff / 3600.0)
                        all_speeds.append(speed)
                        if speed > 100:
                            print(f"High speed detected: {speed:.2f} km/h in file {file}, trip_id {trip_id}, at line {line_num}")
                except Exception:
                    pass
            prev_trip_id = trip_id
            prev_time = timestamp
            prev_lon = lon
            prev_lat = lat
    return all_time_diffs, all_distances, all_speeds

def plot_time_diff_vs_distance(all_time_diffs, all_distances, target_trip_id=None):
    plt.figure(figsize=(10, 6))
    plt.scatter(all_time_diffs, all_distances, c='blue', alpha=0.5)
    plt.xlabel('Time difference between points (seconds)')
    plt.ylabel('Distance between points (km)')
    if target_trip_id is not None:
        plt.title(f'Time Difference vs Distance (Trip {target_trip_id})')
    else:
        plt.title('Time Difference vs Distance (All Trips)')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()