import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from config import PYTHON_FIGURES_DIR, PYTHON_TABLES_DIR, SQL_TABLES_DIR
from project_utils import ensure_dirs, write_csv


sns.set_theme(style="whitegrid")


def savefig(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_long_tail_hist(series, title, xlabel, output_path):
    values = pd.to_numeric(series, errors="coerce").dropna()
    positive = values[values > 0]
    zero_or_invalid_count = int(len(values) - len(positive))
    if positive.empty:
        raise ValueError(f"No positive values available for {title}")

    p50, p80, p95 = positive.quantile([0.50, 0.80, 0.95])
    min_value = positive.min()
    max_value = positive.max()
    bins = np.logspace(np.log10(min_value), np.log10(max_value), 55)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(positive, bins=bins, color="#4c78a8", alpha=0.82, edgecolor="white", linewidth=0.4)
    ax.set_xscale("log")
    ax.set_title(title)
    ax.set_xlabel(f"{xlabel} (log scale)")
    ax.set_ylabel("Order Count")

    for value, label, color in [
        (p50, "P50", "#54a24b"),
        (p80, "P80", "#f58518"),
        (p95, "P95", "#e45756"),
    ]:
        ax.axvline(value, color=color, linestyle="--", linewidth=1.8)
        ax.text(
            value,
            ax.get_ylim()[1] * 0.92,
            label,
            rotation=90,
            va="top",
            ha="right",
            color=color,
            fontsize=9,
        )

    note = (
        f"n={len(positive):,}; P80={p80:,.2f}; max={max_value:,.2f}"
        + (f"; zero/invalid={zero_or_invalid_count:,}" if zero_or_invalid_count else "")
    )
    ax.text(0.01, 0.97, note, transform=ax.transAxes, va="top", ha="left", fontsize=9)
    ax.grid(True, which="major", axis="both", alpha=0.35)
    ax.grid(True, which="minor", axis="x", alpha=0.12)
    savefig(output_path)


def main() -> None:
    ensure_dirs()
    wide = pd.read_csv(SQL_TABLES_DIR / "wide_shipment_risk.csv")

    threshold_cols = [
        "cost_risk_global_p75",
        "cost_risk_global_p80",
        "cost_risk_global_p90",
        "cost_risk_mode_p75",
        "cost_risk_mode_p80",
        "cost_risk_mode_p90",
        "is_cost_risk_mode_country_p80",
    ]
    comparison = []
    for col in threshold_cols:
        comparison.append(
            {
                "threshold_scheme": col,
                "flagged_count": int(wide[col].sum()),
                "flagged_rate": round(float(wide[col].mean()), 4),
                "flagged_freight": round(float(wide.loc[wide[col].eq(1), "freight_cost_usd"].sum()), 2),
            }
        )
    write_csv(pd.DataFrame(comparison), PYTHON_TABLES_DIR / "cost_threshold_comparison.csv")

    segment = (
        wide.groupby("risk_segment", dropna=False)
        .agg(order_count=("shipment_id", "count"), freight_sum=("freight_cost_usd", "sum"), avg_delay_days=("delay_days", "mean"))
        .reset_index()
    )
    write_csv(segment, PYTHON_TABLES_DIR / "risk_segment_summary.csv")

    plot_long_tail_hist(
        wide["freight_cost_usd"],
        "Total Transportation Cost Distribution",
        "Total Transportation Cost USD",
        PYTHON_FIGURES_DIR / "fig01_freight_distribution.png",
    )

    plot_long_tail_hist(
        wide["freight_per_kg"],
        "Total Transportation Cost Distribution",
        "Total Transportation Cost USD",
        PYTHON_FIGURES_DIR / "fig02_freight_per_kg_distribution.png",
    )

    plt.figure(figsize=(8, 5))
    segment_labels = {
        "normal": "Normal Orders",
        "cost_risk_only": "Cost Focus Orders",
        "delay_risk_only": "Delivery Focus Orders",
        "compound_high_risk": "Compound Focus Orders",
    }
    segment_display = wide.assign(segment_display=wide["risk_segment"].map(segment_labels).fillna(wide["risk_segment"]))
    order = segment_display["segment_display"].value_counts().index
    sns.countplot(data=segment_display, y="segment_display", order=order)
    plt.title("Priority Review Segment Counts")
    plt.xlabel("Order Count")
    plt.ylabel("Priority Review Segment")
    savefig(PYTHON_FIGURES_DIR / "fig03_risk_segment_counts.png")

    for filename, title in [
        ("risk_summary_by_country.csv", "Top Countries by Priority Review Freight"),
        ("risk_summary_by_vendor.csv", "Top Vendors by Priority Review Freight"),
        ("risk_summary_by_shipment_mode.csv", "Shipment Mode Priority Review Summary"),
        ("risk_summary_by_country_shipment_mode.csv", "Top Country-Mode Priority Review Combos"),
    ]:
        df = pd.read_csv(SQL_TABLES_DIR / filename).head(12)
        plt.figure(figsize=(10, 6))
        sns.barplot(data=df, x="high_risk_freight", y="dimension_value")
        plt.title(title)
        plt.xlabel("Priority Review Freight USD")
        plt.ylabel("")
        savefig(PYTHON_FIGURES_DIR / f"fig_{filename.replace('.csv', '.png')}")

    pareto = pd.read_csv(SQL_TABLES_DIR / "pareto_country_high_risk_freight.csv")
    plt.figure(figsize=(10, 5))
    top = pareto.head(15)
    sns.barplot(data=top, x="dimension_value", y="contribution_rate", color="#4c78a8")
    plt.plot(top["dimension_value"], top["cumulative_contribution_rate"], color="#f58518", marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.title("Pareto: Country Contribution to Priority Review Freight")
    plt.xlabel("Country")
    plt.ylabel("Contribution Rate")
    savefig(PYTHON_FIGURES_DIR / "fig04_pareto_country_high_risk_freight.png")

    print("Generated EDA tables and figures.")


if __name__ == "__main__":
    main()
