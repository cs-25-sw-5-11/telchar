import matplotlib.pyplot as plt
import pandas as pd

csv_file = "cleaned_data/trips_150103.csv"

df = pd.read_csv(csv_file)

plt.figure(figsize=(8, 6))
# Specify trip_id range to plot (inclusive)
trip_id_min = 0  # Change as needed
trip_id_max = 1000  # Change as needed

if "trip_id" in df.columns:
    trip_ids = df["trip_id"].unique()
    for trip_id in trip_ids:
        if trip_id_min <= trip_id <= trip_id_max:
            group = df[df["trip_id"] == trip_id]
            plt.plot(
                group["longitude"],
                group["latitude"],
                "-",
                alpha=0.7,
                label=f"Trip {trip_id}",
            )
        elif trip_id > trip_id_max:
            break
    if trip_id_max - trip_id_min < 20:
        plt.legend(title="trip_id", loc="best", fontsize="small")
else:
    plt.plot(df["longitude"], df["latitude"], "k-")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title(f"Longitude vs Latitude Plot (Trips {trip_id_min} to {trip_id_max})")
plt.grid(True)
plt.show()
