from __future__ import annotations
import re
import zipfile
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
RAW = ROOT / "data" / "raw"
FIGURES.mkdir(parents=True, exist_ok=True)
TREND_FILE = REPORTS / "monthly_business_trend.csv"
ARCHIVE_NAME = "documents-export-2026-10-17.zip"
SOURCE_URL = "https://www.ihk.de/berlin/service-und-beratung/digitalisierung/open-data-5691102"
REPOSITORY_URL = "https://github.com/IHKBerlin/IHKBerlin_Gewerbedaten"

def find_column(df, candidates, numeric=None):
    norm = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in norm:
            col = norm[name.lower()]
            if numeric is None or pd.api.types.is_numeric_dtype(df[col]) == numeric:
                return col
    if numeric is True:
        cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        return cols[-1] if cols else None
    if numeric is False:
        cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
        return cols[0] if cols else None
    return None

def save_monthly_charts():
    if not TREND_FILE.exists():
        raise FileNotFoundError(f"Missing {TREND_FILE}; run temporal analysis first.")
    df = pd.read_csv(TREND_FILE)
    needed = {"month", "original_unique_business_ids", "adjusted_unique_business_ids"}
    if not needed.issubset(df.columns):
        raise ValueError(f"Trend CSV needs columns: {sorted(needed)}")
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
    df = df.sort_values("month")
    df["change"] = df["original_unique_business_ids"].diff()

    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.plot(df["month"], df["original_unique_business_ids"], marker="o", markersize=3,
            linewidth=2, label="Original monthly unique IDs")
    ax.plot(df["month"], df["adjusted_unique_business_ids"], linestyle="--", linewidth=1.8,
            label="Exploratory adjusted series")
    ax.set_title("Berlin business records by monthly snapshot")
    ax.set_xlabel("Source snapshot month")
    ax.set_ylabel("Unique business IDs")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "monthly_business_trend_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.bar(df["month"].dt.strftime("%Y-%m"), df["change"],
           color=["tab:red" if x < 0 else "tab:blue" for x in df["change"].fillna(0)])
    ax.axhline(0, linewidth=0.8)
    ax.set_title("Month-over-month change in unique business IDs")
    ax.set_xlabel("Source snapshot month")
    ax.set_ylabel("Change vs. previous snapshot")
    ax.tick_params(axis="x", rotation=65)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "business_month_over_month_change.png", dpi=180)
    plt.close(fig)

    def value(month):
        s = df.loc[df["month"] == pd.Timestamp(month + "-01"), "original_unique_business_ids"]
        return int(s.iloc[0]) if len(s) else None
    jan, feb, dec, sep, octo = value("2026-01"), value("2026-02"), value("2025-12"), value("2026-09"), value("2026-10")
    jan_removed = None
    if "adjustment_removed_ids" in df.columns and (df["month"] == pd.Timestamp("2026-01-01")).any():
        jan_removed = int(df.loc[df["month"] == pd.Timestamp("2026-01-01"), "adjustment_removed_ids"].iloc[0])
    return {
        "first_month": df["month"].min().strftime("%Y-%m"),
        "last_month": df["month"].max().strftime("%Y-%m"),
        "first_count": int(df.iloc[0]["original_unique_business_ids"]),
        "last_count": int(df.iloc[-1]["original_unique_business_ids"]),
        "jan": jan, "feb": feb, "dec": dec, "sep": sep, "oct": octo,
        "jan_feb_change": jan - feb if jan is not None and feb is not None else None,
        "jan_feb_pct": (feb / jan - 1) * 100 if jan and feb else None,
        "jan_removed": jan_removed,
    }

def save_report_bar_chart(filename, title, label_candidates, output_name, top_n=15):
    path = REPORTS / filename
    if not path.exists():
        print(f"Skipping {output_name}: {path.name} not found.")
        return
    df = pd.read_csv(path)
    label = find_column(df, label_candidates, numeric=False)
    value = find_column(df, ["count", "business_count", "total", "records", "n", "unique_business_ids"], numeric=True)
    if label is None or value is None or label == value:
        print(f"Skipping {output_name}: cannot identify columns in {path.name}: {list(df.columns)}")
        return
    plot = df[[label, value]].copy()
    plot[value] = pd.to_numeric(plot[value], errors="coerce")
    plot = plot.dropna().nlargest(top_n, value).sort_values(value)
    if plot.empty:
        print(f"Skipping {output_name}: no plot data.")
        return
    fig, ax = plt.subplots(figsize=(10, max(5, len(plot) * .32)))
    ax.barh(plot[label].astype(str), plot[value])
    ax.set_title(title)
    ax.set_xlabel(str(value).replace("_", " ").title())
    ax.grid(axis="x", alpha=.25)
    fig.tight_layout()
    fig.savefig(FIGURES / output_name, dpi=180)
    plt.close(fig)
    print(f"Created {FIGURES / output_name}")

def save_location_plot():
    archives = sorted(RAW.glob("*.zip"))
    archive = next((p for p in archives if p.name == ARCHIVE_NAME), archives[-1] if archives else None)
    if archive is None:
        print("Skipping location chart: no ZIP archive found in data/raw.")
        return
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if re.search(r"\d{4}_\d{2}_IHK_Berlin_Gewerbedaten\.csv$", n)]
        if not names:
            print("Skipping location chart: no monthly IHK CSV found in ZIP.")
            return
        member = sorted(names)[-1]
        cols = pd.read_csv(zf.open(member), nrows=0).columns.tolist()
        norm = {str(c).strip().lower(): c for c in cols}
        lat = next((norm[k] for k in ("latitude", "lat", "breitengrad") if k in norm), None)
        lon = next((norm[k] for k in ("longitude", "lon", "long", "laengengrad", "längengrad") if k in norm), None)
        district = next((norm[k] for k in ("bezirk", "district") if k in norm), None)
        if lat is None or lon is None:
            print(f"Skipping location chart: no latitude/longitude columns in {member}.")
            return
        usecols = [lat, lon] + ([district] if district else [])
        chunks = []
        for part in pd.read_csv(zf.open(member), usecols=usecols, chunksize=100_000, low_memory=False):
            part[lat] = pd.to_numeric(part[lat], errors="coerce")
            part[lon] = pd.to_numeric(part[lon], errors="coerce")
            part = part.dropna(subset=[lat, lon])
            part = part[part[lat].between(52.3, 52.7) & part[lon].between(13.0, 13.8)]
            chunks.append(part)
        points = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    if points.empty:
        print("Skipping location chart: no valid coordinates.")
        return
    if len(points) > 120_000:
        points = points.sample(120_000, random_state=42)
    fig, ax = plt.subplots(figsize=(8, 8))
    if district:
        group_col = points[district].fillna("Unknown").astype(str)
        for name in sorted(group_col.unique()):
            subset = points[group_col == name]
            ax.scatter(subset[lon], subset[lat], s=2, alpha=.35, label=name, rasterized=True)
        ax.legend(title="District", fontsize=7, title_fontsize=8)
    else:
        ax.scatter(points[lon], points[lat], s=2, alpha=.3, rasterized=True)
    ax.set_title(f"Geographic distribution of business records ({member[:7]})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "business_locations_berlin.png", dpi=180)
    plt.close(fig)
    print(f"Created {FIGURES / 'business_locations_berlin.png'} from {member}")

def update_readme(s):
    readme = ROOT / "README.md"
    current = readme.read_text(encoding="utf-8") if readme.exists() else "# Berlin Business Locations\n"
    jan, feb, dec, sep, octo = s["jan"], s["feb"], s["dec"], s["sep"], s["oct"]
    pct = f'{s["jan_feb_pct"]:.2f}%' if s["jan_feb_pct"] is not None else "not available"
    removed = s["jan_removed"] if s["jan_removed"] is not None else "not reported"
    section = f"""## Monthly Trend and Key Findings

This project compares monthly snapshots of unique business IDs in the IHK Berlin Gewerbedaten dataset. These figures are **records/unique IDs present in each snapshot**, not independently verified counts of businesses that opened or closed.

![Monthly business trend comparison](reports/figures/monthly_business_trend_comparison.png)

![Month-over-month change](reports/figures/business_month_over_month_change.png)

### Key findings

- **Longer-term direction:** the series runs from {s["first_month"]} ({s["first_count"]:,} unique IDs) to {s["last_month"]} ({s["last_count"]:,}). The latest month may be incomplete, so endpoint comparisons need caution.
- **Sharp drop in early 2026:** December 2025 had {dec:,} IDs, January 2026 had {jan:,}, and February had {feb:,}. January-to-February change was {jan - feb:,} IDs ({pct}).
- **Partial recovery:** September 2026 had {sep:,} IDs, above February's {feb:,}, but below January's {jan:,}.
- **October 2026:** the snapshot contains {octo:,} IDs. Verify that October is a complete monthly snapshot before interpreting the decline from September as a real-world change.
- **Interpretation:** the February discontinuity is a material data-coverage / data-quality signal. Counts alone do **not** prove that this number of real businesses closed. Check source release notes, schema and identifier changes, and snapshot completeness before drawing a causal conclusion.

### Exploratory adjustment caveat

The current trend CSV reports {removed} IDs removed from the January 2026 count by the current adjustment rule. This is **not** the previously discussed approximately 27,000-record cohort. Do not describe the adjusted series as removing 27,000 records until the original cohort and rule have been reproduced and verified. Candidate IDs are not confirmed errors.

### Geographic and category views

![Business locations in Berlin](reports/figures/business_locations_berlin.png)

![Top business categories](reports/figures/top_business_categories.png)

![Businesses by district](reports/figures/businesses_by_district.png)

### Data source and reproducibility

- **Publisher:** IHK Berlin
- **Official data page:** {SOURCE_URL}
- **Publisher's dataset repository:** {REPOSITORY_URL}
- **Local source archive analyzed:** `{ARCHIVE_NAME}`
- **Coverage in the current trend table:** {s["first_month"]} through {s["last_month"]}
- **License:** the publisher's repository states CC0. Re-check current source terms and attribution notes before redistributing source files or derived data.
- The large raw archive is intentionally not committed to this repository. Obtain it from the publisher and place it in `data/raw/` to reproduce the analysis.

The location chart plots valid coordinates from the latest monthly CSV within a broad Berlin bounding box. It is a point distribution, not a street map. Overlapping records may represent multiple records at the same coordinate; shared coordinates are not automatically errors.
"""
    pattern = re.compile(r"(?ms)^## Monthly Trend and Key Findings\s*\n.*?(?=^## |\Z)")
    current = pattern.sub(section.strip() + "\n\n", current) if pattern.search(current) else current.rstrip() + "\n\n" + section.strip() + "\n"
    readme.write_text(current, encoding="utf-8")
    print(f"Updated {readme}")

def main():
    stats = save_monthly_charts()
    save_report_bar_chart("business_category_counts.csv", "Top business categories",
                          ["category", "business_category", "activity", "hauptbranche", "bezeichnung", "name"],
                          "top_business_categories.png")
    save_report_bar_chart("portfolio_districts.csv", "Business records by district",
                          ["bezirk", "district", "district_name", "name"],
                          "businesses_by_district.png")
    save_location_plot()
    update_readme(stats)
    print(f'January 2026 adjustment removed: {stats["jan_removed"]} IDs (not approximately 27,000).')
    print("Review README.md and reports/figures before committing.")

if __name__ == "__main__":
    main()
