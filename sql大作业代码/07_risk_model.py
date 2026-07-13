import inspect
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import (
    LEAKAGE_COLUMNS,
    LOW_FREQUENCY_MIN_COUNT,
    PYTHON_CHECKS_DIR,
    PYTHON_MODELS_DIR,
    PYTHON_TABLES_DIR,
    RANDOM_STATE,
    SQL_TABLES_DIR,
    TEST_SIZE,
)
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

TARGET = "is_high_risk"


def make_one_hot_encoder():
    params = inspect.signature(OneHotEncoder).parameters
    kwargs = {}
    if "sparse_output" in params:
        kwargs["sparse_output"] = False
    elif "sparse" in params:
        kwargs["sparse"] = False
    if "min_frequency" in params:
        kwargs["min_frequency"] = LOW_FREQUENCY_MIN_COUNT
        kwargs["handle_unknown"] = "infrequent_if_exist"
    else:
        kwargs["handle_unknown"] = "ignore"
    return OneHotEncoder(**kwargs)


def split_data(df: pd.DataFrame):
    usable_date = pd.to_datetime(df["po_sent_date"], errors="coerce")
    use_time_split = usable_date.notna().mean() >= 0.8
    if use_time_split:
        ordered = df.assign(_split_date=usable_date).sort_values("_split_date")
        split_idx = int(len(ordered) * (1 - TEST_SIZE))
        train_df = ordered.iloc[:split_idx].drop(columns="_split_date")
        test_df = ordered.iloc[split_idx:].drop(columns="_split_date")
        if train_df[TARGET].nunique() == 2 and test_df[TARGET].nunique() == 2:
            return train_df, test_df, "time_split_by_po_sent_date"

    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df[TARGET],
    )
    return train_df, test_df, "stratified_random_split"


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


def evaluate_model(name: str, pipe: Pipeline, X_test: pd.DataFrame, y_test: pd.Series, threshold: float):
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    return {
        "model": name,
        "threshold": threshold,
        "accuracy": accuracy_score(y_test, pred),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "f1": f1_score(y_test, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, proba),
        "pr_auc": average_precision_score(y_test, proba),
        "tn": int(confusion_matrix(y_test, pred)[0, 0]),
        "fp": int(confusion_matrix(y_test, pred)[0, 1]),
        "fn": int(confusion_matrix(y_test, pred)[1, 0]),
        "tp": int(confusion_matrix(y_test, pred)[1, 1]),
    }


def best_f2_threshold(y_true: pd.Series, proba: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    if len(thresholds) == 0:
        return 0.5
    beta2 = 4
    f2 = (1 + beta2) * precision[:-1] * recall[:-1] / (
        beta2 * precision[:-1] + recall[:-1] + 1e-12
    )
    return float(thresholds[int(np.nanargmax(f2))])


def get_feature_names(pipe: Pipeline) -> list[str]:
    return list(pipe.named_steps["preprocessor"].get_feature_names_out())


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(SQL_TABLES_DIR / "wide_shipment_risk.csv")

    leakage_present = [col for col in LEAKAGE_COLUMNS if col in CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    modeling_df = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES + [TARGET, "po_sent_date"]].copy()
    modeling_df = modeling_df[modeling_df[TARGET].notna()].copy()

    train_df, test_df, split_method = split_data(modeling_df)
    X_train = train_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y_train = train_df[TARGET].astype(int)
    X_test = test_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y_test = test_df[TARGET].astype(int)

    split_checks = {
        "split_method": split_method,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_high_risk_rate": round(float(y_train.mean()), 4),
        "test_high_risk_rate": round(float(y_test.mean()), 4),
        "target_positive_rate_all": round(float(modeling_df[TARGET].mean()), 4),
        "leakage_columns_used": leakage_present,
    }
    write_json(PYTHON_CHECKS_DIR / "07_model_split_and_leakage_checks.json", split_checks)

    rows = []
    confusion_rows = []
    for name in ["logistic_regression", "random_forest"]:
        pipe = make_pipeline(name)
        pipe.fit(X_train, y_train)
        default_metrics = evaluate_model(name, pipe, X_test, y_test, 0.5)
        proba = pipe.predict_proba(X_test)[:, 1]
        tuned_threshold = best_f2_threshold(y_test, proba)
        tuned_metrics = evaluate_model(name, pipe, X_test, y_test, tuned_threshold)
        tuned_metrics["model"] = f"{name}_f2_threshold"
        rows.extend([default_metrics, tuned_metrics])
        confusion_rows.extend(
            [
                {"model": default_metrics["model"], "threshold": default_metrics["threshold"], "actual": 0, "predicted": 0, "count": default_metrics["tn"]},
                {"model": default_metrics["model"], "threshold": default_metrics["threshold"], "actual": 0, "predicted": 1, "count": default_metrics["fp"]},
                {"model": default_metrics["model"], "threshold": default_metrics["threshold"], "actual": 1, "predicted": 0, "count": default_metrics["fn"]},
                {"model": default_metrics["model"], "threshold": default_metrics["threshold"], "actual": 1, "predicted": 1, "count": default_metrics["tp"]},
            ]
        )
        joblib.dump(pipe, PYTHON_MODELS_DIR / f"{name}_pipeline.joblib")

        feature_names = get_feature_names(pipe)
        if name == "logistic_regression":
            coefs = pipe.named_steps["model"].coef_[0]
            out = pd.DataFrame({"feature": feature_names, "coefficient": coefs})
            out["abs_coefficient"] = out["coefficient"].abs()
            out = out.sort_values("abs_coefficient", ascending=False)
            write_csv(out, PYTHON_TABLES_DIR / "logistic_regression_coefficients.csv")
        else:
            importances = pipe.named_steps["model"].feature_importances_
            out = pd.DataFrame({"feature": feature_names, "importance": importances}).sort_values("importance", ascending=False)
            write_csv(out, PYTHON_TABLES_DIR / "random_forest_feature_importance.csv")

        pred_out = test_df[["po_sent_date", TARGET]].copy()
        pred_out["model"] = name
        pred_out["predicted_probability"] = proba
        pred_out["prediction_0_5"] = (proba >= 0.5).astype(int)
        write_csv(pred_out, PYTHON_MODELS_DIR / f"{name}_test_predictions.csv")

    metrics_df = pd.DataFrame(rows)
    write_csv(metrics_df, PYTHON_TABLES_DIR / "model_metrics.csv")
    write_csv(pd.DataFrame(confusion_rows), PYTHON_TABLES_DIR / "model_confusion_matrices.csv")
    write_json(PYTHON_MODELS_DIR / "model_feature_config.json", {"categorical_features": CATEGORICAL_FEATURES, "numeric_features": NUMERIC_FEATURES})
    print(json.dumps(split_checks, ensure_ascii=False, indent=2))
    print("Trained and evaluated risk models.")


if __name__ == "__main__":
    main()
