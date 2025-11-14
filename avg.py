import pandas as pd
import numpy as np

# List of edge data files from the 5 days
edge_data_files = [
    "./data/output_data/edge_data_day3.csv",
    "./data/output_data/edge_data_day4.csv",
    "./data/output_data/edge_data_day5.csv",
    "./data/output_data/edge_data_day6.csv",
    "./data/output_data/edge_data_day7.csv",
]

print("\n=== Averaging results across days ===")

matrices = []
for file in edge_data_files:
    df = pd.read_csv(file)
    matrices.append(df)
    print(f"Loaded {file}: shape {df.shape}")

combined_df = matrices[0].copy()

valid_counts = sum([(df.iloc[:, 1:] != -1).astype(int) for df in matrices])
total_sum = sum([df.iloc[:, 1:].mask(df.iloc[:, 1:] == -1, 0) for df in matrices])

# Calculate averages only for valid entries
averaged_values = total_sum / valid_counts.replace(0, np.nan)

averaged_df = combined_df.copy()
averaged_df.iloc[:, 1:] = averaged_values.fillna(-1)

averaged_df.to_csv("./data/output_data/edge_data_averaged.csv", index=False)

print("\n=== Final averaged file saved to ./data/output_data/edge_data_averaged.csv ===")
print(f"Shape: {averaged_df.shape}")
print(f"Data density: {((averaged_df.iloc[:, 1:] != -1).sum().sum() / (averaged_df.shape[0] * (averaged_df.shape[1]-1)) * 100):.2f}%")
