import os
from glob import glob
from utils.functions_misc import haversine
from utils.csv_io import read_csv_stream
from configs.config import PRE_TRIP_ID_COLUMN,PRE_LAT_ID_COLUMN, PRE_LON_ID_COLUMN, PRE_TIMESTAMP_COLUMN, SPEED_LIMIT
from typing import List, TextIO
import csv
def check_has_repeated_timestamp(current_trip_rows, timestamp_idx):
    for i in range(1, len(current_trip_rows)):
        if current_trip_rows[i][timestamp_idx] == current_trip_rows[i-1][timestamp_idx]:
            return True
    return False

def check_has_high_speed(current_trip_rows, timestamp_idx, lon_idx, lat_idx):
    speed_limit = SPEED_LIMIT
    
    for i in range(1, len(current_trip_rows)):
        try:
            t1 = float(current_trip_rows[i][timestamp_idx])
            t0 = float(current_trip_rows[i-1][timestamp_idx])
            diff = t1 - t0
            if diff <= 0:
                continue
            lon1 = float(current_trip_rows[i][lon_idx])
            lat1 = float(current_trip_rows[i][lat_idx])
            lon0 = float(current_trip_rows[i-1][lon_idx])
            lat0 = float(current_trip_rows[i-1][lat_idx])
            dist = haversine(lon0, lat0, lon1, lat1)
            speed = dist / (diff / 3600.0)
            if speed > speed_limit:
                return True
        except (ValueError,IndexError):
            continue
    return False

def get_csv_files(input_dir: str) -> List[str]:
    files = glob(os.path.join(input_dir, '*.csv'))
    return files

def is_valid_trip(trip_rows: List[List[str]], ts_idx: int, lon_idx: int, lat_idx: int) -> bool:
    repeated_timestamp = check_has_repeated_timestamp(trip_rows,ts_idx)
    high_speed = check_has_high_speed(trip_rows,ts_idx, lon_idx, lat_idx)

    return not(repeated_timestamp or high_speed)

def select_relevant_columns(rows: List[List[str]], cols: List[int]) -> List[List[str]]:
    selected_rows = [[row[i] for i in cols] for row in rows]
    return selected_rows



def process_and_write_trip_stream(stream, writer, relevant_cols) -> None:

    trip_id_idx, lon_idx, lat_idx, timestamp_idx = 0,1,2,3

    current_trip = []
    prev_trip_id = None

    for row in stream:

        if len(row) < max(relevant_cols):
            continue


        trip_id = row[trip_id_idx]

        if prev_trip_id is not None and trip_id != prev_trip_id:
            if current_trip and is_valid_trip(current_trip, timestamp_idx, lon_idx, lat_idx):
                print(f"Writing trip with {len(current_trip)} rows")
                writer.writerows(current_trip)
            current_trip = []
        current_trip.append(row)
        prev_trip_id = trip_id
            
        
    # handle last trip
    if current_trip and is_valid_trip(current_trip, timestamp_idx, lon_idx, lat_idx):
        writer.writerows(current_trip)
                

    return 





def clean_trips(input_dir: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    relevant_cols = [
        PRE_TRIP_ID_COLUMN,
        PRE_LON_ID_COLUMN,
        PRE_LAT_ID_COLUMN,
        PRE_TIMESTAMP_COLUMN
    ]
    

    for file_path in get_csv_files(input_dir):
        stream = read_csv_stream(file_path, relevant_cols)
        header = next(stream)
        print("First 3 rows:")
        for _ in range(3):
            print(next(stream))

    
        # Write cleaned file
        out_file = os.path.join(output_dir, os.path.basename(file_path))
        with open(out_file, 'w', newline='',encoding='utf-8') as fout:
            writer = csv.writer(fout)
            writer.writerow(header)

            process_and_write_trip_stream(stream,writer,relevant_cols)

    return None
