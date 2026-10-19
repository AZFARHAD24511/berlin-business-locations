"""Run the initial data validation and descriptive pipeline."""
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from berlin_businesses.config import DATA_RAW, DATA_PROCESSED, REPORTS, FIGURES
from berlin_businesses.data import load_sources, validate_schema, coerce_coordinates
from berlin_businesses.analysis import count_by, coordinate_summary
from berlin_businesses.visualize import plot_top_categories

def main():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    df = coerce_coordinates(load_sources(DATA_RAW))
    validation = validate_schema(df)

    # Persist only aggregate metadata by default; raw/processed data remain local.
    meta = {
        "rows": validation["rows"],
        "columns": validation["columns"],
        "duplicate_rows": validation["duplicate_rows"],
        "missing_coordinate_columns": validation["missing_coordinate_columns"],
        "missing_by_column": {str(k): int(v) for k, v in validation["missing_by_column"].items()},
    }
    (REPORTS / "data_validation.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    category_col = next(
        (c for c in ("branch_top_level_desc", "ihk_branch_desc", "nace_desc") if c in df.columns),
        None,
    )
    if category_col:
        counts = count_by(df, category_col, dropna=False)
        counts.to_csv(REPORTS / "business_category_counts.csv", index=False)
        fig, _ = plot_top_categories(
            counts, category_col, output=FIGURES / "top_business_categories.png"
        )
        import matplotlib.pyplot as plt
        plt.close(fig)

    if {"latitude", "longitude"}.issubset(df.columns):
        coord = coordinate_summary(df)
        coord_summary = {k: v for k, v in coord.items() if k != "coordinate_pair_size_distribution"}
        coord_summary["coordinate_pair_size_distribution"] = {
            str(k): int(v) for k, v in coord["coordinate_pair_size_distribution"].items()
        }
        (REPORTS / "coordinate_summary.json").write_text(
            json.dumps(coord_summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(f"Pipeline complete. Outputs written to: {REPORTS}")

if __name__ == "__main__":
    main()
