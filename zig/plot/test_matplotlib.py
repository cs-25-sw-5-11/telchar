#!/usr/bin/env python3
"""Test matplotlib backends to see which one works on your system."""

import matplotlib
import sys

print("Testing matplotlib backends...\n")

backends_to_test = ['Qt5Agg', 'TkAgg', 'GTK3Agg', 'WXAgg']

for backend in backends_to_test:
    try:
        matplotlib.use(backend, force=True)
        import matplotlib.pyplot as plt

        print(f"✓ {backend}: Available")

        # Try to create a simple plot
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.set_title(f"Test - {backend}")

        print(f"  Creating test window...")
        plt.show(block=False)
        plt.pause(0.1)
        plt.close()
        print(f"  Test successful!\n")

    except Exception as e:
        print(f"✗ {backend}: Failed - {e}\n")

print("\nRecommendation:")
print("Use the first backend that showed '✓ Available' in visualize_network.py")
print("Edit line 14 to: matplotlib.use('BACKEND_NAME')")
