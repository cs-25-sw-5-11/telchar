import csv
from typing import List, Tuple, Generator


def read_csv_stream(file_path: str, columns: List[int]) -> Generator[List[str], None, None]:
    """yields CSV header then, selected columns from CSV file one row at a time, to minimize RAM usage"""
    with open(file_path, 'r', newline='',encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        selected_header = [header[i] for i in columns]
        yield selected_header
        for row in reader:
            yield [row[i] for i in columns]
        