import csv
import os
from glob import glob
from typing import Iterable, List

import numpy as np
from configs.config import SPEED_LIMIT
from utils.csv_io import read_csv_stream
from utils.functions_misc import vector_haversine


def check_has_repeated_timestamp(current_trip_rows, timestamp_idx) -> bool:
    for i in range(1, len(current_trip_rows)):
        current_timestamp = current_trip_rows[i][timestamp_idx]
        prev_timestamp = current_trip_rows[i - 1][timestamp_idx]
        if current_timestamp == prev_timestamp:
            return True
    return False


def check_has_high_speed(trip_rows, timestamp_idx, lat_idx, lon_idx) -> bool:
    rows = np.array(trip_rows, dtype=float)
    timestamps = rows[:, timestamp_idx]
    lats = rows[:, lat_idx]
    lons = rows[:, lon_idx]

    dt = np.diff(timestamps)
    dists = vector_haversine(lats[:-1], lons[:-1], lats[1:], lons[1:])

    valid = dt > 0
    if not np.any(valid):
        return False

    dt = dt[valid]
    dists = dists[valid]

    speeds = dists / (dt / 3600.0)

    has_high_speed = np.any(speeds > SPEED_LIMIT)
    return has_high_speed


def get_csv_files(input_dir: str) -> List[str]:
    files = glob(os.path.join(input_dir, "*.csv"))
    return files


def is_valid_trip(
    trip_rows: List[List[str]], ts_idx: int, lat_idx: int, lon_idx: int
) -> bool:
    repeated_timestamp = check_has_repeated_timestamp(trip_rows, ts_idx)
    high_speed = check_has_high_speed(trip_rows, ts_idx, lat_idx, lon_idx)

    return not (repeated_timestamp or high_speed)


def select_relevant_columns(rows: List[List[str]], cols: List[int]) -> List[List[str]]:
    selected_rows = [[row[i] for i in cols] for row in rows]
    return selected_rows


def process_and_write_trip_stream(
    stream: Iterable[List[str]], writer: csv.writer, relevant_trip_headers: List[str]
) -> None:
    trip_id_idx, lat_idx, lon_idx, timestamp_idx = 0, 1, 2, 3

    current_trip = []
    prev_trip_id = None

    for row in stream:
        new_row = row.copy()
        try:
            new_row[lat_idx] = f"{round(float(new_row[lat_idx]), 5)}"
            new_row[lon_idx] = f"{round(float(new_row[lon_idx]), 5)}"
        except ValueError:
            pass

        trip_id = new_row[trip_id_idx]

        is_new_trip = prev_trip_id is not None and trip_id != prev_trip_id

        if is_new_trip:
            if current_trip and is_valid_trip(
                current_trip, timestamp_idx, lat_idx, lon_idx
            ):
                writer.writerows(current_trip)
            current_trip = []
        current_trip.append(new_row)
        prev_trip_id = trip_id

    # handle last trip
    if current_trip and is_valid_trip(current_trip, timestamp_idx, lat_idx, lon_idx):
        writer.writerows(current_trip)

    return None


def file_already_cleaned(file_path: str, output_dir: str) -> bool:
    file_name = os.path.basename(file_path)
    cleaned_file_path = os.path.join(output_dir, file_name)
    cleaned_file_already = os.path.exists(cleaned_file_path)
    if cleaned_file_already:
        print(f"skipping cleaning: {file_name}, file already cleaned. ")
        return True

    return False


def clean_trips(input_dir: str, output_dir: str,
                trip_id_header: str, lat_header: str, lon_header: str, timestamp_header: str
                ) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    relevant_trip_headers = [ trip_id_header, lat_header, lon_header, timestamp_header]
    output_files = []
    for file_path in get_csv_files(input_dir):
        output_files.append(file_path)
        if file_already_cleaned(file_path, output_dir):
            continue

        print(f"cleaning csv {file_path}")
        stream = read_csv_stream(file_path, relevant_trip_headers)
        header = next(stream)

        # Write cleaned file
        out_file = os.path.join(output_dir, os.path.basename(file_path))
        with open(out_file, "w", newline="", encoding="utf-8") as fout:
            writer = csv.writer(fout)
            writer.writerow(header)

            process_and_write_trip_stream(stream, writer, relevant_trip_headers)

    # return cleaned data files

    return output_files
