
"""Build portfolio-ready descriptive and data-quality reports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from berlin_businesses.config import DATA_RAW, REPORTS, FIGURES
from berlin_businesses.data import load_latest_month, coerce_coordinates


def save_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(REPORTS / name, index=False, encoding="utf-8-sig")


def save_bar(
    data: pd.Series,
    title: str,
    xlabel: str,
    filename: str,
    top_n: int = 15,
) -> None:
    data = data.head(top_n).sort_values()
    fig, ax = plt.subplots(figsize=(10, max(5, len(data) * 0.38)))
    ax.barh(data.index.astype(str), data.values)
    ax.set_title(title, loc="left", fontsize=14, pad=12)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    df, source = load_latest_month(DATA_RAW)
    df = coerce_coordinates(df)

    total = len(df)
    valid_coords = df.dropna(subset=["latitude", "longitude"])
    valid_ids = df["opendata_id"].dropna()
    duplicate_ids = int(valid_ids.duplicated().sum())

    # 1. Overall data quality
    quality = {
        "source_file": source["source_file"],
        "snapshot": f"{source['year']}-{source['month']:02d}",
        "total_records": int(total),
        "unique_nonmissing_ids": int(valid_ids.nunique()),
        "missing_ids": int(df["opendata_id"].isna().sum()),
        "duplicate_nonmissing_ids": duplicate_ids,
        "duplicate_full_rows": int(df.duplicated().sum()),
        "records_missing_latitude": int(df["latitude"].isna().sum()),
        "records_missing_longitude": int(df["longitude"].isna().sum()),
        "records_with_valid_coordinates": int(len(valid_coords)),
        "missing_values_by_column": {
            str(k): int(v)
            for k, v in df.isna().sum().items()
            if v > 0
        },
    }

    if {"latitude", "longitude"}.issubset(df.columns):
        in_bounds = (
            df["latitude"].between(52.3, 52.7)
            & df["longitude"].between(13.0, 13.8)
        )
        has_both = df["latitude"].notna() & df["longitude"].notna()
        quality["outside_approximate_berlin_bounds"] = int(
            (has_both & ~in_bounds).sum()
        )
        quality["note"] = (
            "Bounding box is approximate; out-of-bounds records require "
            "investigation and are not automatically errors."
        )

    (REPORTS / "portfolio_data_quality.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 2. Overall business categories
    category_col = "branch_top_level_desc"
    if category_col in df.columns:
        categories = (
            df[category_col]
            .fillna("Unknown / missing")
            .value_counts()
            .rename_axis("business_category")
            .reset_index(name="record_count")
        )
        categories["share_pct"] = (
            categories["record_count"] / total * 100
        ).round(3)
        save_csv(categories, "portfolio_categories.csv")

        save_bar(
            categories.set_index("business_category")["record_count"],
            "Largest business categories in Berlin",
            "Records",
            "portfolio_top_categories.png",
        )

    # 3. District distribution
    district_col = "Bezirk"
    if district_col in df.columns:
        districts = (
            df[district_col]
            .fillna("Unknown / missing")
            .value_counts()
            .rename_axis("district")
            .reset_index(name="record_count")
        )
        districts["share_pct"] = (
            districts["record_count"] / total * 100
        ).round(3)
        save_csv(districts, "portfolio_districts.csv")

        save_bar(
            districts.set_index("district")["record_count"],
            "Business records by Berlin district",
            "Records",
            "portfolio_districts.png",
            top_n=20,
        )

    # 4. Category mix within each district
    if district_col in df.columns and category_col in df.columns:
        mix = (
            df.groupby([district_col, category_col], dropna=False)
            .size()
            .rename("record_count")
            .reset_index()
        )
        totals = mix.groupby(district_col)["record_count"].transform("sum")
        mix["district_share_pct"] = (
            mix["record_count"] / totals * 100
        ).round(3)
        save_csv(mix, "portfolio_district_category_mix.csv")

        top_mix = (
            mix.sort_values(
                [district_col, "record_count"],
                ascending=[True, False],
            )
            .groupby(district_col, dropna=False)
            .head(5)
        )
        save_csv(top_mix, "portfolio_top_categories_by_district.csv")

    # 5. Shared coordinate diagnostics
    if {"latitude", "longitude"}.issubset(df.columns):
        points = valid_coords.groupby(
            ["latitude", "longitude"], as_index=False
        ).agg(
            record_count=("opendata_id", "size"),
            unique_ids=("opendata_id", "nunique"),
            distinct_postcodes=("postcode", "nunique"),
            distinct_districts=("Bezirk", "nunique"),
            distinct_categories=(category_col, "nunique"),
        )

        points = points.sort_values("record_count", ascending=False)
        save_csv(points.head(1000), "portfolio_top_shared_coordinates.csv")

        coordinate_summary = {
            "valid_coordinate_records": int(len(valid_coords)),
            "unique_coordinate_pairs": int(len(points)),
            "pairs_shared_by_multiple_records": int(
                (points["record_count"] > 1).sum()
            ),
            "pairs_with_10_or_more_records": int(
                (points["record_count"] >= 10).sum()
            ),
            "pairs_with_100_or_more_records": int(
                (points["record_count"] >= 100).sum()
            ),
            "records_on_shared_coordinates": int(
                points.loc[
                    points["record_count"] > 1, "record_count"
                ].sum()
            ),
            "interpretation": (
                "Shared coordinates do not prove incorrect geocoding. "
                "Multiple businesses may share an address or approximate point."
            ),
        }
        (REPORTS / "portfolio_coordinate_quality.json").write_text(
            json.dumps(coordinate_summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Scatter plot: a visual overview, not a density map.
        sample = valid_coords.sample(
            n=min(30000, len(valid_coords)), random_state=42
        )
        fig, ax = plt.subplots(figsize=(9, 9))
        ax.scatter(
            sample["longitude"],
            sample["latitude"],
            s=2,
            alpha=0.25,
            rasterized=True,
        )
        ax.set_title("Business coordinate distribution in the dataset")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(
            FIGURES / "portfolio_coordinate_distribution.png",
            dpi=180,
            bbox_inches="tight",
        )
        plt.close(fig)

    print(f"Snapshot analyzed: {source['year']}-{source['month']:02d}")
    print(f"Records analyzed: {total:,}")
    print(f"Unique non-missing IDs: {valid_ids.nunique():,}")
    print(f"Duplicate non-missing IDs: {duplicate_ids:,}")
    print(f"Reports: {REPORTS}")
    print(f"Figures: {FIGURES}")


if __name__ == "__main__":
    main()
