import pandas as pd
import h5py
import os

def convert_structured_h5_to_csv():
    """
    Converts structured HDF5 trip files to a single flat CSV file.
    """
    os.chdir('data')
    h5_files = [f for f in os.listdir('.') if f.endswith('.h5')]
    if not h5_files:
        print("No .h5 files found in the current directory.")
        return

    for h5_file in h5_files:
        output_csv_file = h5_file.replace('.h5', '.csv')
        print(f"Processing {h5_file}...")
        
        all_trips_dfs = []
        try:
            with h5py.File(h5_file, 'r') as h5f:
                # Get the total number of trips from the metadata
                num_trips = int(h5f['/meta/ntrips'][()])
                
                print(f"--> Found {num_trips} trips in the file.")

                # Loop through each trip
                for i in range(1, num_trips + 1):
                    trip_path = f'/trip/{i}'
                    try:
                        lat = h5f[f'{trip_path}/lat'][:]
                        lon = h5f[f'{trip_path}/lon'][:]
                        tms = h5f[f'{trip_path}/tms'][:]
                        speed = h5f[f'{trip_path}/speed'][:]
                        devid = h5f[f'{trip_path}/devid'][()]

                        # Create a DataFrame for the current trip
                        trip_df = pd.DataFrame({
                            'trip_id': i,
                            'devid': devid,
                            'latitude': lat,
                            'longitude': lon,
                            'timestamp': tms,
                            'speed': speed
                        })
                        all_trips_dfs.append(trip_df)
                    except KeyError:
                        print(f"--> Warning: Could not find trip data for trip/{i}. Skipping.")
                
            if not all_trips_dfs:
                print(f"--> No valid trips were extracted from {h5_file}.")
                continue

            # Concatenate all trip DataFrames into one large DataFrame
            final_df = pd.concat(all_trips_dfs, ignore_index=True)

            # Save the final DataFrame to a CSV file
            final_df.to_csv(output_csv_file, index=False)
            print(f"--> Successfully converted {h5_file} to {output_csv_file}")

        except Exception as e:
            print(f"--> An error occurred while processing {h5_file}: {e}")

def print_first_csv_head():
    """
    Finds the first CSV file in the directory and prints its head.
    """
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    if csv_files:
        first_csv = sorted(csv_files)[0]
        print(f"\nDisplaying head of {first_csv}:")
        try:
            df = pd.read_csv(first_csv)
            print(df.head())
        except Exception as e:
            print(f"--> An error occurred while reading {first_csv}: {e}")
    else:
        print("\nNo CSV files were created to display.")

if __name__ == "__main__":
    convert_structured_h5_to_csv()
    print_first_csv_head()