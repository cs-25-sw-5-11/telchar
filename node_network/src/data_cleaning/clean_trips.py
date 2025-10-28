import os
from glob import glob

def check_has_repeated_timestamp(trip_buffer, timestamp_idx=4):
    for i in range(1, len(trip_buffer)):
        if trip_buffer[i][timestamp_idx] == trip_buffer[i-1][timestamp_idx]:
            return True
    return False

def check_has_high_speed(trip_buffer, timestamp_idx=4, lon_idx=3, lat_idx=2, speed_limit=150):
    from math import radians, sin, cos, sqrt, asin
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2.0)**2 + cos(lat1) * cos(lat2) * sin(dlon/2.0)**2
        c = 2 * asin(sqrt(a))
        km = 6371 * c
        return km
    for i in range(1, len(trip_buffer)):
        try:
            t1 = float(trip_buffer[i][timestamp_idx])
            t0 = float(trip_buffer[i-1][timestamp_idx])
            diff = t1 - t0
            if diff <= 0:
                continue
            lon1 = float(trip_buffer[i][lon_idx])
            lat1 = float(trip_buffer[i][lat_idx])
            lon0 = float(trip_buffer[i-1][lon_idx])
            lat0 = float(trip_buffer[i-1][lat_idx])
            dist = haversine(lon0, lat0, lon1, lat1)
            speed = dist / (diff / 3600.0)
            if speed > speed_limit:
                return True
        except Exception:
            continue
    return False

def clean_trips(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    csv_files = glob(os.path.join(input_dir, '*.csv'))
    for file in csv_files:
        with open(file, 'r', encoding='utf-8') as f:
            header = f.readline()
            trip_id_idx = 0
            lat_idx = 2
            lon_idx = 3
            timestamp_idx = 4
            cleaned_lines = [header]
            trip_buffer = []
            prev_trip_id = None
            for line in f:
                parts = line.strip().split(',')
                if len(parts) <= max(trip_id_idx, timestamp_idx, lon_idx, lat_idx):
                    continue
                trip_id = parts[trip_id_idx]
                # If new trip, flush buffer
                if prev_trip_id is not None and trip_id != prev_trip_id:
                    if not check_has_repeated_timestamp(trip_buffer, timestamp_idx) and not check_has_high_speed(trip_buffer, timestamp_idx, lon_idx, lat_idx):
                        for l in trip_buffer:
                            cleaned_lines.append(','.join(l))
                    trip_buffer = []
                trip_buffer.append(parts)
                prev_trip_id = trip_id
            # Handle last trip
            if trip_buffer:
                if not check_has_repeated_timestamp(trip_buffer, timestamp_idx) and not check_has_high_speed(trip_buffer, timestamp_idx, lon_idx, lat_idx):
                    for l in trip_buffer:
                        cleaned_lines.append(','.join(l))
        # Write cleaned file
        out_file = os.path.join(output_dir, os.path.basename(file))
        with open(out_file, 'w', encoding='utf-8') as fout:
            for l in cleaned_lines:
                fout.write(l if l.endswith('\n') else l + '\n')

