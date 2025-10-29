# Spatial binning and coordinate constants for the node_network project
LAT_MIN         = 45.6570
LAT_MAX         = 45.8310
LON_MIN         = 126.500
LON_MAX         = 126.780
LAT_BIN_SIZE    =   0.001
LON_BIN_SIZE    =   0.001

# Distance conversion for coordinate system
# Calculated for middle latitude of region: (45.6570 + 45.8310) / 2 = 45.744�
# At this latitude: cos(45.744�) ? 0.6985
# Geometric mean of lat/lon conversions: sqrt(111000 * 111000 * 0.6985) ? 92,800 m/degree
METERS_PER_DEGREE = 92800  # Approximate meters per degree for this region

# Original coordinate ranges from data:
# Latitude: min=45.65792, max=45.830902
# Longitude: min=126.50613, max=126.77186


# column number from data in csv files
TRIP_ID_COLUMN = 0
LAT_ID_COLUMN = 2
LON_ID_COLUMN = 3
TIMESTAMP_COLUMN = 4
