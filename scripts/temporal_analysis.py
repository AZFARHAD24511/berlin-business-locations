from pathlib import Path
from zipfile import ZipFile
import re
import json
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from berlin_businesses.config import DATA_RAW, REPORTS, FIGURES

PATTERN = re.compile(
    r"(?P<year>\d{4})_(?P<month>\d{2})_IHK_Berlin_Gewerbedaten\.csv$",
    re.IGNORECASE,
)

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    monthly_ids = {}
    source_names = {}

    # Read only IDs, not the full business dataset.
    for archive_path in DATA_RAW.glob("*.zip"):
        with ZipFile(archive_path) as archive:
            for member in archive.namelist():
                match = PATTERN.search(Path(member).name)
                if not match:
                    continue

                period = f"{match.group('year')}-{match.group('month')}"
                with archive.open(member) as stream:
                    ids = pd.read_csv(
                        stream,
                        usecols=["opendata_id"],
                        dtype={"opendata_id": "string"},
                    )["opendata_id"].dropna().str.strip()

                monthly_ids[period] = set(ids[ids.ne("")].unique())
                source_names[period] = f"{archive_path.name}:{member}"

    if not monthly_ids:
        raise FileNotFoundError("No monthly IHK CSV files found in ZIP archives.")

    periods = sorted(monthly_ids)
    if "2026-01" not in monthly_ids or "2026-02" not in monthly_ids:
        raise ValueError("Monthly files for January and February 2026 are required.")

    # Original monthly unique-ID counts.
    rows = []
    for period in periods:
        rows.append({
            "month": period,
            "original_unique_business_ids": len(monthly_ids[period]),
            "source_file": source_names[period],
        })
    trend = pd.DataFrame(rows)

    # Candidate anomaly cohort: IDs present in Jan 2026 but absent
    # from both Dec 2025 and Feb 2026. This is a candidate, not proof of error.
    jan_ids = monthly_ids["2026-01"]
    feb_ids = monthly_ids["2026-02"]
    dec_ids = monthly_ids.get("2025-12", set())

    jan_not_feb = jan_ids - feb_ids
    jan_only = jan_ids - feb_ids - dec_ids

    # Save candidate lists for auditability.
    pd.DataFrame({"opendata_id": sorted(jan_not_feb)}).to_csv(
        REPORTS / "january_2026_missing_in_february_candidates.csv",
        index=False,
    )
    pd.DataFrame({"opendata_id": sorted(jan_only)}).to_csv(
        REPORTS / "january_2026_january_only_candidates.csv",
        index=False,
    )

    # Adjusted trend excludes the Jan-only cohort from every month.
    # If an ID appears in another month, it is excluded there too.
    trend["adjusted_unique_business_ids"] = [
        len(monthly_ids[p] - jan_only) for p in periods
    ]
    trend["adjustment_removed_ids"] = (
        trend["original_unique_business_ids"]
        - trend["adjusted_unique_business_ids"]
    )

    trend.to_csv(
        REPORTS / "monthly_business_trend.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Two comparable trends on one chart.
    x = pd.to_datetime(trend["month"])
    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.plot(
        x, trend["original_unique_business_ids"],
        marker="o", markersize=3, linewidth=1.8,
        label="Original monthly unique IDs",
    )
    ax.plot(
        x, trend["adjusted_unique_business_ids"],
        marker="o", markersize=3, linewidth=1.8,
        label="Adjusted: January-only cohort excluded",
    )
    ax.set_title("Berlin business records over time", loc="left", fontsize=15)
    ax.set_xlabel("Month")
    ax.set_ylabel("Unique business IDs")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(
        FIGURES / "monthly_business_trend_comparison.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close(fig)

    summary = {
        "months": len(periods),
        "first_month": periods[0],
        "last_month": periods[-1],
        "january_2026_unique_ids": len(jan_ids),
        "february_2026_unique_ids": len(feb_ids),
        "january_ids_absent_in_february": len(jan_not_feb),
        "january_ids_absent_in_december_and_february": len(jan_only),
        "warning": (
            "January-only IDs are candidates, not confirmed errors. "
            "Verify the historical anomaly evidence before treating the "
            "adjusted trend as the definitive result."
        ),
    }
    (REPORTS / "monthly_business_trend_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\nCreated:")
    print(REPORTS / "monthly_business_trend.csv")
    print(REPORTS / "monthly_business_trend_summary.json")
    print(FIGURES / "monthly_business_trend_comparison.png")


if __name__ == "__main__":
    main()