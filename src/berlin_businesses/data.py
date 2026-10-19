"""Loading and basic validation for IHK Berlin business exports."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import pandas as pd

PREFERRED_COLUMNS = [
    "opendata_id", "city", "postcode", "latitude", "longitude",
    "ihk_branch_id", "nace_id", "branch_top_level_id", "employees_range",
    "ihk_branch_desc", "nace_desc", "branch_top_level_desc", "business_age",
    "business_type", "Bezirk", "planungsraum_id", "Planungsraum",
    "Bezirksregion", "Prognoseraum", "Ortsteil",
]

def _read_csv_bytes_or_path(source, *, name: str | None = None) -> pd.DataFrame:
    if name and name.lower().endswith(".csv"):
        return pd.read_csv(source, low_memory=False)
    return pd.read_csv(source, low_memory=False)

def load_csv(path: str | Path) -> pd.DataFrame:
    """Load one CSV file."""
    return pd.read_csv(path, low_memory=False)

def load_sources(raw_dir: str | Path) -> pd.DataFrame:
    """Load CSV files and CSV members of ZIP archives under raw_dir.

    Returns a concatenated DataFrame with a source_file column. This intentionally
    does not deduplicate records; that decision belongs to a documented analysis step.
    """
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory does not exist: {raw_dir}")

    frames: list[pd.DataFrame] = []
    for path in sorted(raw_dir.iterdir()):
        if path.name.startswith("."):
            continue
        if path.suffix.lower() == ".csv":
            frame = pd.read_csv(path, low_memory=False)
            frame["source_file"] = path.name
            frames.append(frame)
        elif path.suffix.lower() == ".zip":
            with ZipFile(path) as archive:
                for member in sorted(archive.namelist()):
                    if member.lower().endswith(".csv") and not member.startswith("__MACOSX/"):
                        with archive.open(member) as stream:
                            frame = pd.read_csv(stream, low_memory=False)
                        frame["source_file"] = f"{path.name}:{member}"
                        frames.append(frame)
    if not frames:
        raise FileNotFoundError(
            f"No CSV files or ZIP archives containing CSV files found in {raw_dir}"
        )
    return pd.concat(frames, ignore_index=True, sort=False)

def validate_schema(df: pd.DataFrame) -> dict:
    """Return basic validation findings without silently altering the DataFrame."""
    required_any = {"latitude", "longitude"}
    missing_coords = sorted(required_any - set(df.columns))
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_by_column": df.isna().sum().sort_values(ascending=False),
        "missing_coordinate_columns": missing_coords,
        "columns": list(df.columns),
    }

def coerce_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with latitude and longitude converted to numeric when present."""
    result = df.copy()
    for col in ("latitude", "longitude"):
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result
