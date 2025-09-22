import pandas as pd
import matplotlib.pyplot as plt
from geopy.distance import geodesic
import numpy as np

csv_file = 'cleaned_data/trips_150103.csv'

df = pd.read_csv(csv_file)

plt.figure(figsize=(8, 6))
# Specify trip_id range to plot (inclusive)
trip_id_min = 0  # Change as needed
trip_id_max = 1000  # Change as needed

def interpolate_points(p1, p2, n):
    """Return n points evenly spaced between p1 and p2 (excluding endpoints)."""
    lons = np.linspace(p1[0], p2[0], n+2)[1:-1]
    lats = np.linspace(p1[1], p2[1], n+2)[1:-1]
    return list(zip(lons, lats))

all_x = []
all_y = []

if 'trip_id' in df.columns:
    trip_ids = df['trip_id'].unique()
    for trip_id in trip_ids:
        if trip_id_min <= trip_id <= trip_id_max:
            group = df[df['trip_id'] == trip_id]
            coords = list(zip(group['longitude'], group['latitude']))
            for i in range(len(coords) - 1):
                p1 = coords[i]
                p2 = coords[i+1]
                # Calculate geodesic distance in meters
                dist = geodesic((p1[1], p1[0]), (p2[1], p2[0])).meters
                n_dots = int(dist // 10)
                if n_dots > 0:
                    dots = interpolate_points(p1, p2, n_dots)
                    for x, y in dots:
                        all_x.append(x)
                        all_y.append(y)
else:
    coords = list(zip(df['longitude'], df['latitude']))
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i+1]
        dist = geodesic((p1[1], p1[0]), (p2[1], p2[0])).meters
        n_dots = int(dist // 10)
        if n_dots > 0:
            dots = interpolate_points(p1, p2, n_dots)
            for x, y in dots:
                all_x.append(x)
                all_y.append(y)

plt.scatter(all_x, all_y, c='blue', s=5, alpha=0.7)
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title(f'Dots Along Trip Segments (Trips {trip_id_min} to {trip_id_max})')
plt.grid(True)
plt.show()
