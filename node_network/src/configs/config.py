# Spatial binning and coordinate constants for the node_network project
LAT_MIN = 45.6570
LAT_MAX = 45.8310
LON_MIN = 126.500
LON_MAX = 126.780
LAT_BIN_SIZE = 0.001
LON_BIN_SIZE = 0.001

# Distance conversion for coordinate system
# Calculated for middle latitude of region: (45.6570 + 45.8310) / 2 = 45.744 deg
# At this latitude: cos(45.744 deg) ~= 0.6985
# Geometric mean of lat/lon conversions: sqrt(111000 * 111000 * 0.6985) ~= 92,800 m/degree
METERS_PER_DEGREE = 92800  # Approximate meters per degree for this region

# Original coordinate ranges from data:
# Latitude: min=45.65792, max=45.830902
# Longitude: min=126.50613, max=126.77186

# speed limit for cleaning trips
SPEED_LIMIT = 150

# Settings for processing trips.
# Threshold for when speeds are thrown away when being applied.
SPEED_KMS_CUTOFF = 120

# Compares the distance given to Viterbi to the distance computed when
# doing A* pathfinding between the two points determined by the Viterbi
# algorithm to be the two "true" points for the taxi trip.  
DIST_VERIFICATION = True 
DIST_VERIFICATION_TOLERANCE = 0.1  # 10% tolerance