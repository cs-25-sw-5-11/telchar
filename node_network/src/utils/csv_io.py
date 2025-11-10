import csv
from typing import Generator, List


def read_csv_stream(file_path: str, headers: List[str]) -> Generator[List[str], None, None]:
    """yields CSV header then, selected columns from CSV file one row at a time, to minimize RAM usage.
    Will throw error if a requested header is missing, if a row has a different number of columns than header,
    or if a row has missing values in requested columns."""
    with open(file_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

        # Determine indices for requested headers (raises ValueError if any missing)
        columns = [
            header.index(headers[0]),
            header.index(headers[1]),
            header.index(headers[2]),
            header.index(headers[3]),
        ]

        selected_header = [header[i] for i in columns]
        yield selected_header

        header_len = len(header)
        for row in reader:
            # Must have same number of columns as header
            if len(row) != header_len:
                raise ValueError(f"Row has {len(row)} columns but header has {header_len} columns.")

            # Must have non-empty values for all selected columns
            if any((row[i].strip() == "") for i in columns):
                raise ValueError("Row has empty value(s) in required columns.")

            yield [row[i] for i in columns]

