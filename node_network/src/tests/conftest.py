# Ensure the project 'src' directory is on sys.path when running pytest from the repo root.
# This makes imports like `from data_cleaning.clean_trips import ...` work without
# setting PYTHONPATH manually.
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
