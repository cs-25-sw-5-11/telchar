import os
import pandas as pd
from glob import glob

folder = './cleaned_data'  # Current folder; change as needed
lat_min = float('inf')
lat_max = float('-inf')
lon_min = float('inf')
lon_max = float('-inf')

csv_files = glob(os.path.join(folder, '*.csv'))

for file in csv_files:
    try:
        df = pd.read_csv(file)
        if 'latitude' in df.columns and 'longitude' in df.columns:
            lat_min = min(lat_min, df['latitude'].min())
            lat_max = max(lat_max, df['latitude'].max())
            lon_min = min(lon_min, df['longitude'].min())
            lon_max = max(lon_max, df['longitude'].max())
            print(f"{file}: lat [{df['latitude'].min()}, {df['latitude'].max()}], lon [{df['longitude'].min()}, {df['longitude'].max()}]")
        else:
            print(f"{file}: latitude/longitude columns not found.")
    except Exception as e:
        print(f"{file}: Error reading file: {e}")

print("\nOverall:")
print(f"Latitude: min={lat_min}, max={lat_max}")
print(f"Longitude: min={lon_min}, max={lon_max}")

# Found values:
# Latitude: min=45.65792, max=45.830902
# Longitude: min=126.50613, max=126.77186