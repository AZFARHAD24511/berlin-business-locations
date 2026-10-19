"""Small reusable plotting helpers."""
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

def plot_top_categories(counts: pd.DataFrame, category_col: str, *, top_n: int = 15, output=None):
    """Plot top categories from a count_by() output table."""
    plot_data = counts.head(top_n).sort_values("business_count")
    fig, ax = plt.subplots(figsize=(10, max(5, top_n * 0.35)))
    ax.barh(plot_data[category_col].astype(str), plot_data["business_count"])
    ax.set_xlabel("Number of businesses")
    ax.set_ylabel("")
    ax.set_title(f"Top {min(top_n, len(plot_data))} business categories")
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160, bbox_inches="tight")
    return fig, ax
