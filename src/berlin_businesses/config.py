"""Project paths and shared configuration."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
REPORTS = PROJECT_ROOT / "reports"
FIGURES = REPORTS / "figures"

# Approximate bounding box used only as a plausibility check, not as an authoritative boundary.
BERLIN_BOUNDS = {
    "latitude_min": 52.3,
    "latitude_max": 52.7,
    "longitude_min": 13.0,
    "longitude_max": 13.8,
}
