import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import PYTHON_CHECKS_DIR, PYTHON_FIGURES_DIR, PYTHON_TABLES_DIR, RANDOM_STATE, SQL_TABLES_DIR
from project_utils import ensure_dirs, write_csv, write_json


CATEGORICAL_FEATURES = [
    "country",
    "vendor_name",
    "manufacturing_site",
    "shipment_mode",
    "fulfill_via",
    "vendor_inco_term",
    "product_group",
    "sub_classification",
    "managed_by",
    "first_line_designation",
]

NUMERIC_FEATURES = [
    "line_item_quantity",
    "line_item_value",
    "pack_price",
    "unit_price",
    "weight_kg",
    "unit_of_measure_per_pack",
    "planned_lead_days",
    "pq_to_po_days",
]


def make_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(
            sparse_output=False,
            handle_unknown="infrequent_if_exist",
            min_frequency=20,
        )
    except TypeError:
        return OneHotEncoder(sparse=False, handle_unknown="ignore")


def make_pipeline(model_type: str) -> Pipeline:
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("onehot", make_one_hot_encoder()),
        ]
    )
    if model_type == "logistic_regression":
        numeric_pipe = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        model = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            solver="lbfgs",
        )
    else:
        numeric_pipe = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])
        model = RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=5,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, NUMERIC_FEATURES),
            ("cat", categorical_pipe, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])


def evaluate_predictions(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
    return {
        "threshold": threshold,
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, proba),
        "pr_auc": average_precision_score(y_true, proba),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def add_risk_definitions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["freight_per_kg_country_p80"] = out.groupby("country")["freight_per_kg"].transform(
        lambda values: values.quantile(0.80)
    )
    out["cost_risk_country_p80"] = (
        out["freight_per_kg"].gt(out["freight_per_kg_country_p80"])
        & out["freight_per_kg_country_p80"].notna()
    ).astype(int)
    out["risk_main_mode_p80_or_delay"] = (
        (out["cost_risk_mode_p80"] == 1) | (out["is_delay_risk"] == 1)
    ).astype(int)
    out["risk_global_p80_or_delay"] = (
        (out["cost_risk_global_p80"] == 1) | (out["is_delay_risk"] == 1)
    ).astype(int)
    out["risk_country_p80_or_delay"] = (
        (out["cost_risk_country_p80"] == 1) | (out["is_delay_risk"] == 1)
    ).astype(int)
    out["risk_mode_p90_or_delay"] = (
        (out["cost_risk_mode_p90"] == 1) | (out["is_delay_risk"] == 1)
    ).astype(int)
    out["risk_mode_country_p80_or_delay"] = (
        (out["is_cost_risk_mode_country_p80"] == 1) | (out["is_delay_risk"] == 1)
    ).astype(int)
    out["risk_delay_only"] = out["is_delay_risk"].astype(int)
    out["risk_compound_only"] = out["is_compound_high_risk"].astype(int)
    return out


def summarize_dimension(df: pd.DataFrame, risk_col: str, dim_cols: list[str]) -> pd.DataFrame:
    dim = "_".join(dim_cols)
    work = df.copy()
    for col in dim_cols:
        work[col] = work[col].fillna("Unknown")
    grouped = (
        work.groupby(dim_cols, dropna=False)
        .agg(
            order_count=("shipment_id", "count"),
            risk_count=(risk_col, "sum"),
            total_freight=("freight_cost_usd", "sum"),
            risk_freight=(
                "freight_cost_usd",
                lambda x: x[work.loc[x.index, risk_col].eq(1)].sum(),
            ),
        )
        .reset_index()
    )
    grouped["risk_rate"] = grouped["risk_count"] / grouped["order_count"]
    grouped["risk_freight_contribution_rate"] = grouped["risk_freight"] / grouped["risk_freight"].sum()
    grouped["dimension_name"] = dim
    grouped["dimension_value"] = grouped[dim_cols].astype(str).agg(" | ".join, axis=1)
    return grouped.sort_values(["risk_freight", "risk_count"], ascending=False)


def run_sensitivity(df: pd.DataFrame) -> None:
    risk_cols = [
        "risk_main_mode_p80_or_delay",
        "risk_global_p80_or_delay",
        "risk_country_p80_or_delay",
        "risk_mode_p90_or_delay",
        "risk_mode_country_p80_or_delay",
        "risk_delay_only",
        "risk_compound_only",
    ]
    dimensions = {
        "country": ["country"],
        "vendor": ["vendor_name"],
        "shipment_mode": ["shipment_mode"],
        "country_shipment_mode": ["country", "shipment_mode"],
    }

    overview_rows = []
    top_rows = []
    stability_rows = []
    main_tops = {}

    for risk_col in risk_cols:
        overview_rows.append(
            {
                "risk_definition": risk_col,
                "risk_count": int(df[risk_col].sum()),
                "risk_rate": float(df[risk_col].mean()),
                "risk_freight": float(df.loc[df[risk_col].eq(1), "freight_cost_usd"].sum()),
            }
        )
        for dim_name, dim_cols in dimensions.items():
            summary = summarize_dimension(df, risk_col, dim_cols)
            current_top = summary["dimension_value"].head(5).tolist()
            if risk_col == "risk_main_mode_p80_or_delay":
                main_tops[dim_name] = set(current_top)
            else:
                overlap = len(set(current_top) & main_tops[dim_name])
                stability_rows.append(
                    {
                        "risk_definition": risk_col,
                        "dimension_name": dim_name,
                        "top5_overlap_with_main": overlap,
                        "top5_overlap_rate_with_main": overlap / 5,
                        "top5_values": "; ".join(current_top),
                    }
                )
            top_part = summary.head(10).copy()
            top_part.insert(0, "risk_definition", risk_col)
            top_rows.append(
                top_part[
                    [
                        "risk_definition",
                        "dimension_name",
                        "dimension_value",
                        "order_count",
                        "risk_count",
                        "risk_rate",
                        "risk_freight",
                        "risk_freight_contribution_rate",
                    ]
                ]
            )

    write_csv(pd.DataFrame(overview_rows), PYTHON_TABLES_DIR / "risk_definition_sensitivity_overview.csv")
    write_csv(pd.concat(top_rows, ignore_index=True), PYTHON_TABLES_DIR / "risk_definition_sensitivity_top_dimensions.csv")
    stability = pd.DataFrame(stability_rows)
    write_csv(stability, PYTHON_TABLES_DIR / "risk_definition_top5_stability.csv")
    plot_top5_stability(stability)


def plot_top5_stability(stability: pd.DataFrame) -> None:
    label_map = {
        "risk_global_p80_or_delay": "Global P80 + delay",
        "risk_country_p80_or_delay": "Country P80 + delay",
        "risk_mode_p90_or_delay": "Mode P90 + delay",
        "risk_mode_country_p80_or_delay": "Mode-country P80 + delay",
        "risk_delay_only": "Delay only",
        "risk_compound_only": "Compound only",
    }
    dim_map = {
        "country": "Country",
        "vendor": "Vendor",
        "shipment_mode": "Shipment mode",
        "country_shipment_mode": "Country-mode",
    }
    plot_df = stability.copy()
    plot_df["risk_definition_label"] = plot_df["risk_definition"].map(label_map)
    plot_df["dimension_label"] = plot_df["dimension_name"].map(dim_map)
    matrix = plot_df.pivot(
        index="risk_definition_label",
        columns="dimension_label",
        values="top5_overlap_with_main",
    ).loc[list(label_map.values()), list(dim_map.values())]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    im = ax.imshow(matrix.values, cmap="YlGnBu", vmin=0, vmax=5, aspect="auto")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Top 5 overlap count")
    ax.set_xticks(np.arange(matrix.shape[1]))
    ax.set_xticklabels(matrix.columns)
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{int(matrix.iloc[i, j])}/5", ha="center", va="center", color="#111111")
    ax.set_xticks(np.arange(-0.5, matrix.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, matrix.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_title("Top 5 Stability Across Risk Definitions")
    ax.set_xlabel("Analysis Dimension")
    ax.set_ylabel("Risk Definition Compared with Main Standard")
    plt.xticks(rotation=0)
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(
        PYTHON_FIGURES_DIR / "fig_risk_definition_top5_stability.png",
        dpi=180,
    )
    plt.close()


def run_time_split_model(df: pd.DataFrame) -> None:
    modeling = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES + ["is_high_risk", "po_sent_date"]].copy()
    modeling["_po_sent_date"] = pd.to_datetime(modeling["po_sent_date"], errors="coerce")
    modeling = modeling.dropna(subset=["_po_sent_date", "is_high_risk"]).sort_values("_po_sent_date")
    split_idx = int(len(modeling) * 0.75)
    train_df = modeling.iloc[:split_idx].copy()
    test_df = modeling.iloc[split_idx:].copy()

    X_train = train_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y_train = train_df["is_high_risk"].astype(int)
    X_test = test_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y_test = test_df["is_high_risk"].astype(int)

    metrics_rows = []
    for model_type in ["logistic_regression", "random_forest"]:
        pipe = make_pipeline(model_type)
        pipe.fit(X_train, y_train)
        proba = pipe.predict_proba(X_test)[:, 1]
        metrics = evaluate_predictions(y_test, proba, 0.5)
        metrics.update(
            {
                "model": model_type,
                "split_method": "out_of_time_by_po_sent_date_nonmissing",
                "train_rows": int(len(train_df)),
                "test_rows": int(len(test_df)),
                "train_start": str(train_df["_po_sent_date"].min().date()),
                "train_end": str(train_df["_po_sent_date"].max().date()),
                "test_start": str(test_df["_po_sent_date"].min().date()),
                "test_end": str(test_df["_po_sent_date"].max().date()),
                "train_high_risk_rate": float(y_train.mean()),
                "test_high_risk_rate": float(y_test.mean()),
            }
        )
        metrics_rows.append(metrics)

    output = pd.DataFrame(metrics_rows)
    front_cols = [
        "model",
        "split_method",
        "train_rows",
        "test_rows",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "train_high_risk_rate",
        "test_high_risk_rate",
    ]
    write_csv(output[front_cols + [c for c in output.columns if c not in front_cols]], PYTHON_TABLES_DIR / "time_split_model_metrics.csv")
    write_json(
        PYTHON_CHECKS_DIR / "09_time_split_sample_checks.json",
        {
            "po_sent_date_nonmissing_rows": int(len(modeling)),
            "po_sent_date_nonmissing_rate": round(float(len(modeling) / len(df)), 4),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_date_range": [str(train_df["_po_sent_date"].min().date()), str(train_df["_po_sent_date"].max().date())],
            "test_date_range": [str(test_df["_po_sent_date"].min().date()), str(test_df["_po_sent_date"].max().date())],
        },
    )


def run_strategy_quantification(df: pd.DataFrame) -> None:
    combo = summarize_dimension(df, "is_high_risk", ["country", "shipment_mode"]).head(20).copy()
    total_orders = len(df)
    total_high_risk_orders = int(df["is_high_risk"].sum())
    total_high_risk_freight = float(df.loc[df["is_high_risk"].eq(1), "freight_cost_usd"].sum())
    combo["review_order_share"] = combo["order_count"] / total_orders
    combo["high_risk_order_capture_rate"] = combo["risk_count"] / total_high_risk_orders
    combo["high_risk_freight_capture_rate"] = combo["risk_freight"] / total_high_risk_freight
    combo["cumulative_review_order_share"] = combo["review_order_share"].cumsum()
    combo["cumulative_high_risk_order_capture_rate"] = combo["high_risk_order_capture_rate"].cumsum()
    combo["cumulative_high_risk_freight_capture_rate"] = combo["high_risk_freight_capture_rate"].cumsum()
    combo["high_risk_orders_per_100_reviewed"] = combo["risk_count"] / combo["order_count"] * 100
    write_csv(
        combo[
            [
                "dimension_value",
                "order_count",
                "risk_count",
                "risk_rate",
                "risk_freight",
                "review_order_share",
                "high_risk_order_capture_rate",
                "high_risk_freight_capture_rate",
                "cumulative_review_order_share",
                "cumulative_high_risk_order_capture_rate",
                "cumulative_high_risk_freight_capture_rate",
                "high_risk_orders_per_100_reviewed",
            ]
        ],
        PYTHON_TABLES_DIR / "strategy_review_coverage_by_country_mode.csv",
    )

    coverage_rows = []
    for top_n in [3, 5, 10, 17]:
        part = combo.head(top_n)
        coverage_rows.append(
            {
                "top_country_mode_count": top_n,
                "review_order_count": int(part["order_count"].sum()),
                "review_order_share": float(part["order_count"].sum() / total_orders),
                "captured_high_risk_order_count": int(part["risk_count"].sum()),
                "captured_high_risk_order_share": float(part["risk_count"].sum() / total_high_risk_orders),
                "captured_high_risk_freight": float(part["risk_freight"].sum()),
                "captured_high_risk_freight_share": float(part["risk_freight"].sum() / total_high_risk_freight),
            }
        )
    write_csv(pd.DataFrame(coverage_rows), PYTHON_TABLES_DIR / "strategy_review_coverage_summary.csv")


def main() -> None:
    ensure_dirs()
    wide = pd.read_csv(SQL_TABLES_DIR / "wide_shipment_risk.csv")
    wide = add_risk_definitions(wide)
    run_sensitivity(wide)
    run_time_split_model(wide)
    run_strategy_quantification(wide)
    print(json.dumps({"status": "ok", "rows": len(wide)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
