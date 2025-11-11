# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telchar is a GPS trajectory map-matching system that analyzes vehicle trip data to compute road segment travel speeds by time of day. It processes OpenStreetMap data and GPS trajectories to generate temporal traffic statistics for network edges.

## Key Commands

### Running the Main Pipeline
```bash
cd node_network/src
python3 main.py
```
This executes the complete pipeline: OSM extraction → trip cleaning → graph building → map matching → speed statistics generation.

### Running Tests
```bash
# Run unit tests (requires pytest)
cd node_network/src
pytest tests/test_clean_trips.py
pytest tests/test_extract_osm_maps.py

# Run specific test
pytest tests/test_clean_trips.py::test_unit_check_has_high_speed_with_low_speed

# Run variance calculation test
python3 test_variance_simple.py  # From project root
```

### Setting Up Environment
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install numpy pandas tqdm matplotlib pytz
```

## Core Architecture

### Graph Data Structure
The system centers around a `Network` class (`node_network/src/classes/network.py`) that manages:
- **Vertices**: Road intersections with lat/lon coordinates
- **Edges**: Directional road segments between vertices
- **Spatial binning**: 0.001-degree grid for O(1) edge lookup
- **Distance matrix**: Pre-computed shortest paths stored as int32 centimeters

### Key Algorithms

1. **Map Matching Pipeline** (`main.py`):
   - Projects GPS points onto nearby edges
   - Uses Viterbi algorithm to find optimal path through projections
   - Applies A* search between consecutive projections

2. **Variance Calculation** (`classes/edge.py:traversals_data_update`):
   - Uses Welford's online algorithm for numerical stability
   - Stores speed in cm/s as integers
   - Caps variance at 100000 to prevent explosion
   - Critical fix: Use float arithmetic during calculation, convert to int for storage

3. **Spatial Indexing** (`graph_mapping/functions_mapping.py`):
   - Maps lat/lon to grid bins: `bin_x = floor((lon - LON_MIN) / LON_BIN_SIZE)`
   - Each point checks 4 corner bins for nearby edges

### Data Flow
```
Input Files:
├── data/input_data/
│   ├── map.osm           # OpenStreetMap data
│   └── *.csv             # GPS trip data

Processing:
1. extract_osm_map → nodes.json, roads.json
2. clean_trips → filtered CSVs (removes invalid trips)
3. build_graph → Network with vertices/edges
4. remove_small_subnetworks → largest component only
5. compute_all_pairs_distances → distance_matrix.npy
6. For each trip: map matching → edge speed updates
7. writeout_traversals_to_json → edge_traversals.json

Output:
└── edge_traversals.json  # Speed statistics per edge/time
```

## Important Configuration

### Regional Settings (`configs/config.py`)
```python
LAT_MIN, LAT_MAX = 45.6570, 45.8310  # Harbin, China bounds
LON_MIN, LON_MAX = 126.500, 126.780
METERS_PER_DEGREE = 92800            # Region-specific
```

### Processing Parameters (`main.py`)
```python
MAX_DIST = 100           # Max meters for GPS projection
TIME_INTERVAL = 300      # 5-minute time bins
SPEED_LIMIT = 150        # km/h validation threshold
WRITEOUT_INTERVAL = 1000 # Checkpoint frequency
```

## Common Development Tasks

### Adding New Road Types
Edit `extract_osm_map/extract_osm_map.py` and modify the highway type filter in the extraction logic.

### Adjusting Speed Limits
Modify `SPEED_LIMIT` in `configs/config.py` for trip validation threshold.

### Changing Time Granularity
Update `TIME_INTERVAL` in `main.py` (default: 300 seconds = 5 minutes).

### Debugging Variance Explosion
Check `classes/edge.py:traversals_data_update()`:
- Ensure Welford's algorithm is used correctly
- Verify variance capping at line 204
- Check float/int conversions

## File Organization

### Core Classes (`node_network/src/classes/`)
- `network.py`: Central graph structure
- `edge.py`: Road segments with traversal statistics
- `vertex.py`: Intersections/nodes
- `trip.py`: GPS trajectory and map matching
- `point_projection.py`: GPS point mapped to edge

### Processing Modules
- `extract_osm_map/`: OSM XML parsing
- `data_cleaning/`: Trip validation and filtering
- `graph_building/`: Network construction
- `viterbi/`: Hidden Markov Model path inference
- `graph_mapping/`: Spatial binning utilities

## Critical Implementation Details

1. **Memory Optimization**: Distance matrix uses int32 centimeters instead of float meters
2. **Numeric Stability**: Variance calculation uses Welford's algorithm to prevent overflow
3. **Edge Splitting**: Temporary edges support reversible graph modifications
4. **Spatial Efficiency**: Corner-based bin lookup reduces search space by ~99%
5. **Type Consistency**: Edge traversal data stores (int mean, int variance, int count)

## Known Issues and Fixes

### Variance Explosion
- **Problem**: Variance values exploding to >10,000
- **Root Cause**: Integer arithmetic precision loss and type inconsistency
- **Solution**: Use float calculations internally, cap at reasonable max, convert to int for storage
- **Test**: Run `python3 test_variance_simple.py` to verify fix

### Missing Dependencies
- **Problem**: numpy not installed
- **Solution**: `pip install --user numpy` or use virtual environment

### Path References
All file paths in `main.py` are relative to `node_network/src/` directory.