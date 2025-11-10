import os

import pytest
from data_cleaning.clean_trips import (
    check_has_high_speed,
    check_has_repeated_timestamp,
    clean_trips,
    file_already_cleaned,
    get_csv_files,
    is_valid_trip,
)
from utils.csv_io import read_csv_stream


def test_unit_check_has_repeated_timestamp_with_no_repeated_timestamp():
    # Positive test case, no repeated timestamp.
    trip_rows = [
        ["1", "45.7", "126.5", "0"],
        ["1", "45.71", "126.51", "1"],
        ["1", "45.72", "126.52", "2"],
    ]

    assert not check_has_repeated_timestamp(trip_rows, 3)


def test_unit_check_has_repeated_timestamp_with_repeated_timestamp():
    # Negative test case, with repeated timestamp.
    trip_rows_repeated = [
        ["1", "45.7", "126.5", "0"],
        ["1", "45.71", "126.51", "1"],
        ["1", "45.72", "126.52", "1"],
    ]

    assert check_has_repeated_timestamp(trip_rows_repeated, 3)


def test_unit_check_has_high_speed_with_low_speed():
    # Positive test case with very low speed.
    trip_rows = [
        ["1", "45.700000", "126.500000", "0"],
        ["1", "45.700001", "126.500001", "60"],
        ["1", "45.700002", "126.500002", "120"],
    ]

    assert not check_has_high_speed(trip_rows, timestamp_idx=3, lat_idx=1, lon_idx=2)


def test_unit_check_has_high_speed_with_high_speed():
    # Negative test case with very high speed.
    trip_rows = [
        ["1", "45.700000", "126.500000", "0"],
        ["1", "46.700000", "127.500000", "60"],
        ["1", "47.700000", "128.500000", "120"],
    ]

    assert check_has_high_speed(trip_rows, timestamp_idx=3, lat_idx=1, lon_idx=2)


def test_integration_is_valid_trip_valid():
    # Valid trip case, neither high speed nor repeated timestamp.
    trip_rows = [
        ["1", "45.700000", "126.500000", "0"],
        ["1", "45.700001", "126.500001", "60"],
        ["1", "45.700002", "126.500002", "120"],
    ]

    assert is_valid_trip(trip_rows, ts_idx=3, lat_idx=1, lon_idx=2)


def test_integration_is_valid_trip_invalid_repeated_timestamp():
    # Invalid trip case due to repeated timestamp.
    trip_rows = [
        ["1", "45.70000", "126.50000", "0"],
        ["1", "45.70000", "126.50000", "0"],
        ["1", "45.70001", "126.50001", "60"],
        ["1", "45.70002", "126.50002", "120"],
    ]

    assert not is_valid_trip(trip_rows, ts_idx=3, lat_idx=1, lon_idx=2)


def test_integration_is_valid_trip_invalid_high_speed():
    # Invalid trip case due to high speed.
    trip_rows = [
        ["1", "45.70000", "126.50000", "0"],
        ["1", "46.70000", "127.50000", "60"],
        ["1", "47.70000", "128.50000", "120"],
    ]

    assert not is_valid_trip(trip_rows, ts_idx=3, lat_idx=1, lon_idx=2)


def test_integration_is_valid_trip_invalid_both():
    # Invalid trip case due to both repeated timestamp and high speed.
    trip_rows = [
        ["1", "45.70000", "126.50000", "0"],
        ["1", "45.70000", "126.50000", "0"],
        ["1", "46.70000", "127.50000", "60"],
        ["1", "47.70000", "128.50000", "120"],
    ]

    assert not is_valid_trip(trip_rows, ts_idx=3, lat_idx=1, lon_idx=2)


def test_unit_read_csv_stream_returns_correct_rows_1():
    # Test that read_csv_stream yields the correct header and selected columns.
    # Simulate and save some data.
    data = "trip_id,lat,lon,timestamp,extra\n1,45.7,126.5,0,x\n1,45.71,126.51,60,y\n"
    column_headers = ["trip_id", "lat", "lon", "timestamp"]
    with open("temp_test.csv", "w", encoding="utf-8") as f:
        f.write(data)

    stream = read_csv_stream("temp_test.csv", column_headers)
    header = next(stream)
    assert header == ["trip_id", "lat", "lon", "timestamp"]
    rows = list(stream)
    assert rows[0] == ["1", "45.7", "126.5", "0"]
    assert rows[1] == ["1", "45.71", "126.51", "60"]

    # Clean up temporary file.
    os.remove("temp_test.csv")


def test_unit_read_csv_stream_returns_correct_rows_2():
    # Test that read_csv_stream yields the correct header and selected columns.
    # Simulate and save some data.
    # Swap headers around. Rows should still be the same.
    data = "lat,lon,timestamp,trip_id,extra\n45.7,126.5,0,1,x\n45.71,126.51,60,1,y\n"
    column_headers = ["trip_id", "lat", "lon", "timestamp"]
    with open("temp_test.csv", "w", encoding="utf-8") as f:
        f.write(data)

    stream = read_csv_stream("temp_test.csv", column_headers)
    header = next(stream)
    assert header == ["trip_id", "lat", "lon", "timestamp"]
    rows = list(stream)
    assert rows[0] == ["1", "45.7", "126.5", "0"]
    assert rows[1] == ["1", "45.71", "126.51", "60"]

    # Clean up temporary file.
    os.remove("temp_test.csv")


def test_unit_read_csv_stream_throws_error_if_header_missing():
    # Test that read_csv_stream raises ValueError if a requested header is missing.
    # Simulate and save some data, but changing timestamp to ts.
    data = "trip_id,lat,lon,ts\n1,45.7,126.5,0\n1,45.71,126.51,60\n"
    column_headers = ["trip_id", "lat", "lon", "timestamp"]
    with open("temp_test.csv", "w", encoding="utf-8") as f:
        f.write(data)

    # Expect ValueError due to missing 'timestamp' header.
    stream = read_csv_stream("temp_test.csv", column_headers)
    with pytest.raises(ValueError) as e:
        next(stream)
    assert "'timestamp' is not in list" in str(e.value)

    # Clean up temporary file.
    os.remove("temp_test.csv")


def test_unit_read_csv_stream_throws_error_if_value_is_missing():
    # Test that read_csv_stream raises ValueError if a row has a missing value.
    # Simulate and save some data, but changing timestamp to ts.
    data = "trip_id,lat,lon,timestamp\n1,45.7,126.5,0\n1,45.71,126.51\n"
    column_headers = ["trip_id", "lat", "lon", "timestamp"]
    with open("temp_test.csv", "w", encoding="utf-8") as f:
        f.write(data)

    stream = read_csv_stream("temp_test.csv", column_headers)
    next(stream)
    next(stream)
    # Expect value error due to missing value in second row.
    with pytest.raises(ValueError) as e:
        next(stream)
    assert "Row has 3 columns but header has 4 columns." in str(e.value)

    # Clean up temporary file.
    os.remove("temp_test.csv")


def test_unit_read_csv_stream_throws_error_if_value_is_empty():
    # Test that read_csv_stream raises ValueError if a row has an empty value.
    # Simulate and save some data, but changing timestamp to ts.
    data = "trip_id,lat,lon,timestamp\n1,45.7,126.5,0\n1,45.71,126.51,\n"
    column_headers = ["trip_id", "lat", "lon", "timestamp"]
    with open("temp_test.csv", "w", encoding="utf-8") as f:
        f.write(data)

    stream = read_csv_stream("temp_test.csv", column_headers)
    next(stream)
    next(stream)
    # Expect value error due to missing value in second row.
    with pytest.raises(ValueError) as e:
        next(stream)
    assert "Row has empty value(s) in required columns." in str(e.value)

    # Clean up temporary file.
    os.remove("temp_test.csv")


def test_unit_read_csv_stream_throws_error_if_value_cannot_be_float():
    # Test that read_csv_stream raises ValueError if a row has a value that
    # cannot be converted to float.
    data = "trip_id,lat,lon,timestamp\n1,45.7,126.5,0\n1,45.71,126.51,abc\n"
    column_headers = ["trip_id", "lat", "lon", "timestamp"]
    with open("temp_test.csv", "w", encoding="utf-8") as f:
        f.write(data)

    stream = read_csv_stream("temp_test.csv", column_headers)
    next(stream)
    next(stream)
    # Expect value error due to missing value in second row.
    with pytest.raises(ValueError) as e:
        next(stream)
    assert "Value 'abc' cannot be converted to float." in str(e.value)

    # Clean up temporary file.
    os.remove("temp_test.csv")


def test_unit_file_already_cleaned_returns_true_for_existing_file():
    # Create a temporary cleaned file.
    os.makedirs("temp_cleaned_dir", exist_ok=False)
    with open("temp_cleaned_dir/temp_file.csv", "w", encoding="utf-8") as f:
        f.write("trip_id,lat,lon,timestamp\n")

    assert (
        file_already_cleaned("some_input_dir/temp_file.csv", "temp_cleaned_dir") == True
    )

    # Clean up temporary file and directory.
    os.remove("temp_cleaned_dir/temp_file.csv")
    os.rmdir("temp_cleaned_dir")


def test_unit_file_already_cleaned_returns_false_for_nonexisting_file():
    # Ensure the cleaned directory is empty.
    os.makedirs("temp_cleaned_dir_empty", exist_ok=False)

    assert (
        file_already_cleaned(
            "some_input_dir/nonexistent_file.csv", "temp_cleaned_dir_empty"
        )
        == False
    )

    # Clean up temporary directory.
    os.rmdir("temp_cleaned_dir_empty")


def test_unit_get_csv_files_returns_csv_files_in_directory():
    # Create a temporary input directory with some CSV files.
    os.makedirs("temp_input_dir", exist_ok=False)
    with open("temp_input_dir/file1.csv", "w", encoding="utf-8") as f:
        f.write("trip_id,lat,lon,timestamp\n")
    with open("temp_input_dir/file2.csv", "w", encoding="utf-8") as f:
        f.write("trip_id,lat,lon,timestamp\n")
    with open("temp_input_dir/file3.txt", "w", encoding="utf-8") as f:
        f.write("This is not a CSV file.\n")

    csv_files = get_csv_files("temp_input_dir")
    expected_files = [
        os.path.join("temp_input_dir", "file1.csv"),
        os.path.join("temp_input_dir", "file2.csv"),
    ]

    # Clean up temporary files and directory.
    os.remove("temp_input_dir/file1.csv")
    os.remove("temp_input_dir/file2.csv")
    os.remove("temp_input_dir/file3.txt")
    os.rmdir("temp_input_dir")

    assert set(csv_files) == set(expected_files)


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


def test_integration_clean_trips_returns_already_cleaned_files_if_present():
    integration_clean_trips_setup()

    # Create cleaned file to simulate already cleaned scenario.
    with open("temp_output_dir/temp_file.csv", "w", encoding="utf-8") as f:
        f.write("trip_id,lat,lon,timestamp\n")

    cleaned_files = clean_trips(
        input_dir="temp_input_dir",
        output_dir="temp_output_dir",
        trip_id_header="trip_id",
        lat_header="lat",
        lon_header="lon",
        timestamp_header="timestamp",
    )

    # Read cleaned files to verify no new cleaning was done.
    with open("temp_output_dir/temp_file.csv", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Cleanup.
    integration_clean_trips_cleanup()

    assert len(lines) == 1  # Only header should be present in the existing file.
    assert cleaned_files == [
        os.path.join("temp_output_dir", "temp_file.csv")
    ]  # Only the existing file should be reported as cleaned.


def test_integration_clean_trips_cleans_files_properly():
    integration_clean_trips_setup()

    cleaned_files = clean_trips(
        input_dir="temp_input_dir",
        output_dir="temp_output_dir",
        trip_id_header="trip_id",
        lat_header="lat",
        lon_header="lon",
        timestamp_header="timestamp",
    )

    # Read cleaned file to verify cleaning was done correctly.
    with open("temp_output_dir/temp_file.csv", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Cleanup.
    integration_clean_trips_cleanup()

    assert len(lines) == 7  # Header + 2 valid trips (trip_id 1 and 4)
    assert lines == [
        "trip_id,lat,lon,timestamp\n",
        "1,45.7,126.5,0\n",
        "1,45.70001,126.50001,60\n",
        "1,45.70002,126.50002,120\n",
        "4,50.7,131.5,0\n",
        "4,50.70001,131.50001,60\n",
        "4,50.70002,131.50002,120\n",
    ]
    assert cleaned_files == [os.path.join("temp_output_dir", "temp_file.csv")]

