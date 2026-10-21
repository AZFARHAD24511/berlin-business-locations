
"""Loading and validation for monthly IHK Berlin business exports."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import re

import pandas as pd


MONTHLY_FILE_PATTERN = re.compile(
    r"(?P<year>\d{4})_(?P<month>\d{2})_IHK_Berlin_Gewerbedaten\.csv$",
    re.IGNORECASE,
)


def list_monthly_sources(raw_dir: str | Path) -> list[dict]:
    """List recognized monthly CSV sources inside raw CSVs and ZIP archives."""
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory does not exist: {raw_dir}")

    sources = []
    for path in sorted(raw_dir.iterdir()):
        if path.name.startswith("."):
            continue

        if path.suffix.lower() == ".csv":
            match = MONTHLY_FILE_PATTERN.search(path.name)
            if match:
                sources.append({
                    "year": int(match.group("year")),
                    "month": int(match.group("month")),
                    "source_file": path.name,
                    "archive_path": None,
                    "member": None,
                })

        elif path.suffix.lower() == ".zip":
            with ZipFile(path) as archive:
                for member in archive.namelist():
                    match = MONTHLY_FILE_PATTERN.search(Path(member).name)
                    if match:
                        sources.append({
                            "year": int(match.group("year")),
                            "month": int(match.group("month")),
                            "source_file": f"{path.name}:{member}",
                            "archive_path": path,
                            "member": member,
                        })

    sources.sort(key=lambda item: (item["year"], item["month"]))
    if not sources:
        raise FileNotFoundError(
            f"No recognized monthly IHK CSV sources found in {raw_dir}"
        )

    return sources


def load_monthly_source(source: dict) -> pd.DataFrame:
    """Load exactly one monthly CSV source."""
    if source["archive_path"] is None:
        df = pd.read_csv(source["source_file"], low_memory=False)
    else:
        with ZipFile(source["archive_path"]) as archive:
            with archive.open(source["member"]) as stream:
                df = pd.read_csv(stream, low_memory=False)

    df["source_file"] = source["source_file"]
    df["source_year"] = source["year"]
    df["source_month"] = source["month"]
    return df


def load_latest_month(raw_dir: str | Path) -> tuple[pd.DataFrame, dict]:
    """Load only the latest recognized monthly export."""
    source = list_monthly_sources(raw_dir)[-1]
    return load_monthly_source(source), source


def load_sources(raw_dir: str | Path) -> pd.DataFrame:
    """Backward-compatible loader that concatenates all supported sources."""
    raw_dir = Path(raw_dir)
    frames = []

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
    missing_coordinate_columns = sorted(
        {"latitude", "longitude"} - set(df.columns)
    )
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_by_column": df.isna().sum().sort_values(ascending=False),
        "missing_coordinate_columns": missing_coordinate_columns,
    }


def coerce_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with coordinates converted to numeric when present."""
    result = df.copy()
    for col in ("latitude", "longitude"):
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result
