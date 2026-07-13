import joblib
import pandas as pd
from sklearn.inspection import permutation_importance

from config import PYTHON_MODELS_DIR, PYTHON_TABLES_DIR, RANDOM_STATE, SQL_TABLES_DIR
from project_utils import ensure_dirs, write_csv

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

TARGET = "is_high_risk"


def split_data(df: pd.DataFrame):
    usable_date = pd.to_datetime(df["po_sent_date"], errors="coerce")
    use_time_split = usable_date.notna().mean() >= 0.8
    if use_time_split:
        ordered = df.assign(_split_date=usable_date).sort_values("_split_date")
        split_idx = int(len(ordered) * 0.75)
        train_df = ordered.iloc[:split_idx].drop(columns="_split_date")
        test_df = ordered.iloc[split_idx:].drop(columns="_split_date")
        if train_df[TARGET].nunique() == 2 and test_df[TARGET].nunique() == 2:
            return train_df, test_df, "time_split_by_po_sent_date"

    from sklearn.model_selection import train_test_split

    train_df, test_df = train_test_split(
        df,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=df[TARGET],
    )
    return train_df, test_df, "stratified_random_split"


def main() -> None:
    ensure_dirs()
    wide = pd.read_csv(SQL_TABLES_DIR / "wide_shipment_risk.csv")
    modeling_df = wide[CATEGORICAL_FEATURES + NUMERIC_FEATURES + [TARGET, "po_sent_date"]].copy()
    train_df, test_df, _ = split_data(modeling_df)
    X_test = test_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y_test = test_df[TARGET].astype(int)

    rf = joblib.load(PYTHON_MODELS_DIR / "random_forest_pipeline.joblib")
    perm = permutation_importance(
        rf,
        X_test,
        y_test,
        n_repeats=5,
        random_state=RANDOM_STATE,
        scoring="average_precision",
        n_jobs=-1,
    )
    perm_df = pd.DataFrame(
        {
            "feature": CATEGORICAL_FEATURES + NUMERIC_FEATURES,
            "permutation_importance_mean_pr_auc": perm.importances_mean,
            "permutation_importance_std": perm.importances_std,
        }
    ).sort_values("permutation_importance_mean_pr_auc", ascending=False)
    write_csv(perm_df, PYTHON_TABLES_DIR / "permutation_importance_random_forest.csv")

    country = pd.read_csv(SQL_TABLES_DIR / "risk_summary_by_country.csv").head(10)
    vendor = pd.read_csv(SQL_TABLES_DIR / "risk_summary_by_vendor.csv").head(10)
    mode = pd.read_csv(SQL_TABLES_DIR / "risk_summary_by_shipment_mode.csv")

    interpretation = pd.concat(
        [
            country.assign(evidence_source="sql_country_summary"),
            vendor.assign(evidence_source="sql_vendor_summary"),
            mode.assign(evidence_source="sql_shipment_mode_summary"),
        ],
        ignore_index=True,
    )
    write_csv(interpretation, PYTHON_TABLES_DIR / "descriptive_model_cross_evidence.csv")
    print("Generated model explanation outputs.")


if __name__ == "__main__":
    main()
