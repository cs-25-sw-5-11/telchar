from typing import List, Tuple
from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
from math import radians, sin, cos, sqrt, atan2
import logging
import json
import numpy as np

logger = logging.getLogger(__name__)



def vector_haversine(lat0, lon0, lat1, lon1) -> float:
    lat0 = np.radians(lat0)
    lon0 = np.radians(lon0)

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    dlat = lat1-lat0
    dlon = lon1-lon0

    a = np.sin(dlat/2.0) ** 2 + np.cos(lat0) * np.cos(lat1) * np.sin(dlon/2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    R = 6371

    return R * c



def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

def get_time_index(timestamp: int, reference: int, interval: int) -> int:
    """
    Convert a UNIX timestamp to a time index representing the number of a set minute intervals since a reference time.
    
    Args:
        timestamp: UNIX timestamp (seconds since epoch)
        reference: Reference UNIX timestamp (e.g., start of day)

    Returns:
        Time index (int) representing the number of 5-minute intervals since the reference time.
    """
    return (timestamp - reference) // interval

def writeout_traversals_to_json(file_path: str, edge_items):
    from math import sqrt
    with open(file_path, 'w') as f:
        f.write('{\n')
        for i, edge in enumerate(edge_items):
            # Convert to integers at output time for space efficiency, sorted by time_idx
            # Convert variance to standard deviation for interpretability
            traversals_data_int = {
                time_idx: (int(mean), int(sqrt(variance)), int(total_length))
                for time_idx, (mean, variance, total_length) in sorted(edge.traversals_data.items())
            }
            
            edge_data = {
                'length (cm)': int(edge.length * 100), 
                'traversals_data': traversals_data_int
            }
            f.write(f'\t"{edge.id}": {json.dumps(edge_data)}')
            if i < len(edge_items) - 1:
                f.write(',')
            f.write('\n')
        f.write('}\n')

def get_bin_indices(lat: float, lon: float):
    """Calculate bin indices for given latitude and longitude coordinates.
    
    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        
    Returns:
        Tuple[int, int] or None: (lat_idx, lon_idx) if within bounds, None otherwise
    """
    from configs.config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, LAT_BIN_SIZE, LON_BIN_SIZE
    
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None
        
    lat_idx = int((lat - LAT_MIN) / LAT_BIN_SIZE)
    lon_idx = int((lon - LON_MIN) / LON_BIN_SIZE)
    return (lat_idx, lon_idx)

def get_bins_near_point(lat: float, lon: float, range: int=0) -> List[Tuple[int, int]]:
    idx = get_bin_indices(lat, lon)
    if idx is None:
        raise ValueError(f"Coordinates (lat={lat}, lon={lon}) are out of bounds for the configured bins.")
    lat_idx, lon_idx = idx

    if range==0:
        # Check which corner the edge is closest to
        if lat % LAT_BIN_SIZE < LAT_BIN_SIZE / 2:
            if lon % LON_BIN_SIZE < LON_BIN_SIZE / 2:
                # Bottom-left corner
                offsets = [(0, 0), (-1, 0), (0, -1), (-1, -1)]
            else:
                # Bottom-right corner
                offsets = [(0, 0), (-1, 0), (0, 1), (-1, 1)]
        else:
            if lon % LON_BIN_SIZE < LON_BIN_SIZE / 2:
                # Top-left corner
                offsets = [(0, 0), (1, 0), (0, -1), (1, -1)]
            else:
                # Top-right corner
                offsets = [(0, 0), (1, 0), (0, 1), (1, 1)]
    else:
        # Not currently supported, raise error.
        raise NotImplementedError("Range > 0 not currently supported in _get_bins_near_point.")

    bins = []
    for d_lat, d_lon in offsets:
        bins.append((lat_idx + d_lat, lon_idx + d_lon))

    return bins