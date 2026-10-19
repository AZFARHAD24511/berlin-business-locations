"""Descriptive analysis helpers."""
from __future__ import annotations
import pandas as pd

def count_by(df: pd.DataFrame, column: str, *, dropna: bool = False) -> pd.DataFrame:
    """Count records by one column, including missing values by default."""
    if column not in df.columns:
        raise KeyError(f"Column not found: {column}")
    return (
        df[column]
        .value_counts(dropna=dropna)
        .rename_axis(column)
        .reset_index(name="business_count")
    )

def category_shares_by_group(
    df: pd.DataFrame, group_col: str, category_col: str
) -> pd.DataFrame:
    """Return category counts and within-group shares."""
    missing = [c for c in (group_col, category_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Column(s) not found: {missing}")
    counts = (
        df.groupby([group_col, category_col], dropna=False)
        .size()
        .rename("business_count")
        .reset_index()
    )
    totals = counts.groupby(group_col, dropna=False)["business_count"].transform("sum")
    counts["share_within_group"] = counts["business_count"] / totals
    return counts

def coordinate_summary(df: pd.DataFrame) -> dict:
    """Summarize duplicate coordinate pairs; requires latitude and longitude."""
    required = {"latitude", "longitude"}
    if not required.issubset(df.columns):
        raise KeyError(f"Required coordinate columns: {sorted(required)}")
    valid = df.dropna(subset=["latitude", "longitude"])
    pairs = valid.groupby(["latitude", "longitude"], dropna=False).size()
    return {
        "rows_with_valid_coordinates": int(len(valid)),
        "unique_coordinate_pairs": int(len(pairs)),
        "records_at_shared_coordinates": int(pairs[pairs > 1].sum()),
        "coordinate_pairs_with_multiple_records": int((pairs > 1).sum()),
        "coordinate_pair_size_distribution": pairs.value_counts().sort_index(),
    }
