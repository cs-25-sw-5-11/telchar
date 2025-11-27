import heapq
import logging

from classes import Edge, Network, Vertex
from configs.config import LAT_BIN_SIZE, LAT_MIN, LON_BIN_SIZE, LON_MIN
from utils.functions_misc import get_bin_indices

logger = logging.getLogger(__name__)


def get_edges_near_coordinates(lat, lon, cell_range=0):
    """
    Get edges near given coordinates using the class-based spatial binning system.
    """
    idx = get_bin_indices(lat, lon)
    if idx is None:
        raise ValueError(
            f"Coordinates (lat={lat}, lon={lon}) are out of bounds for the configured bins."
        )
    lat_idx, lon_idx = idx
    edges = set()

    if cell_range == 0:
        # Use the corner-based logic for cell_range=0
        lat_bin_start = LAT_MIN + lat_idx * LAT_BIN_SIZE
        lon_bin_start = LON_MIN + lon_idx * LON_BIN_SIZE
        corners = [
            (lat_bin_start, lon_bin_start),  # bottom-left (0,0)
            (lat_bin_start + LAT_BIN_SIZE, lon_bin_start),  # top-left (1,0)
            (lat_bin_start, lon_bin_start + LON_BIN_SIZE),  # bottom-right (0,1)
            (
                lat_bin_start + LAT_BIN_SIZE,
                lon_bin_start + LON_BIN_SIZE,
            ),  # top-right (1,1)
        ]
        dists = [
            ((lat - clat) ** 2 + (lon - clon) ** 2, idx)
            for idx, (clat, clon) in enumerate(corners)
        ]
        _, closest_corner_idx = min(dists)

        # Define the 4 bins that share each corner
        # Each corner is shared by 4 bins, we want the current bin plus the 3 adjacent ones
        corner_to_offsets = {
            0: [(0, 0), (-1, 0), (0, -1), (-1, -1)],  # bottom-left corner
            1: [(0, 0), (1, 0), (0, -1), (1, -1)],  # top-left corner
            2: [(0, 0), (-1, 0), (0, 1), (-1, 1)],  # bottom-right corner
            3: [(0, 0), (1, 0), (0, 1), (1, 1)],  # top-right corner
        }

        offsets = corner_to_offsets[closest_corner_idx]
        bins = []
        for di, dj in offsets:
            i = lat_idx + di
            j = lon_idx + dj
            bins.append((i, j))

        # Query the class-based system for each bin
        for i, j in bins:
            if (i, j) in Edge._bin_lookup:
                edges.update(Edge._bin_lookup[(i, j)])
    else:
        # Use cell_range expansion
        for dlat in range(-cell_range, cell_range + 1):
            for dlon in range(-cell_range, cell_range + 1):
                i = lat_idx + dlat
                j = lon_idx + dlon
                if (i, j) in Edge._bin_lookup:
                    edges.update(Edge._bin_lookup[(i, j)])
    return list(edges)