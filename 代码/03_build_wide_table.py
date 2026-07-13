import numpy as np
import pandas as pd

from config import (
    COST_RISK_MAIN_QUANTILE,
    MIN_MODE_COUNTRY_GROUP_SIZE,
    ROBUST_QUANTILES,
    SQL_CHECKS_DIR,
    SQL_TABLES_DIR,
)
from project_utils import ensure_dirs, get_connection, quote_identifier, replace_table_from_df, write_csv, write_json


def p80_by_group(df: pd.DataFrame, group_cols: list[str], value_col: str, min_size: int = 1) -> pd.Series:
    grouped = df.groupby(group_cols)[value_col]
    thresholds = grouped.transform(lambda x: x.quantile(COST_RISK_MAIN_QUANTILE) if x.notna().sum() >= min_size else np.nan)
    return thresholds


def build_risk_labels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    date_cols = [
        "pq_first_sent_date",
        "po_sent_date",
        "scheduled_delivery_date",
        "delivered_to_client_date",
        "delivery_recorded_date",
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["is_date_missing"] = (
        df["scheduled_delivery_date"].isna() | df["delivered_to_client_date"].isna()
    ).astype(int)
    df["delay_days"] = (
        df["delivered_to_client_date"] - df["scheduled_delivery_date"]
    ).dt.days
    df["is_delayed"] = ((df["is_date_missing"] == 0) & (df["delay_days"] > 0)).astype(int)

    df["is_weight_invalid"] = (
        df["weight_kg"].isna() | (df["weight_kg"] <= 0)
    ).astype(int)
    df["freight_per_kg"] = np.where(
        df["is_weight_invalid"].eq(0),
        df["freight_cost_usd"] / df["weight_kg"],
        np.nan,
    )

    valid_cost = df["freight_per_kg"].notna()
    df["freight_per_kg_global_p80"] = df.loc[valid_cost, "freight_per_kg"].quantile(COST_RISK_MAIN_QUANTILE)
    df["freight_cost_global_p80"] = df["freight_cost_usd"].quantile(COST_RISK_MAIN_QUANTILE)
    df["freight_per_kg_mode_p80"] = p80_by_group(df, ["shipment_mode"], "freight_per_kg")
    df["freight_per_kg_mode_country_p80"] = p80_by_group(
        df, ["shipment_mode", "country"], "freight_per_kg", MIN_MODE_COUNTRY_GROUP_SIZE
    )

    for q in ROBUST_QUANTILES:
        label = int(q * 100)
        df[f"cost_risk_global_p{label}"] = (
            valid_cost & (df["freight_per_kg"] > df.loc[valid_cost, "freight_per_kg"].quantile(q))
        ).astype(int)
        df[f"cost_risk_mode_p{label}"] = (
            valid_cost
            & (
                df["freight_per_kg"]
                > df.groupby("shipment_mode")["freight_per_kg"].transform(lambda x: x.quantile(q))
            )
        ).astype(int)

    df["is_high_freight_global_p80"] = (
        df["freight_cost_usd"] > df["freight_cost_global_p80"]
    ).astype(int)
    df["cost_risk_mode_country_available"] = df["freight_per_kg_mode_country_p80"].notna().astype(int)
    df["is_cost_risk_mode_country_p80"] = (
        valid_cost
        & df["freight_per_kg_mode_country_p80"].notna()
        & (df["freight_per_kg"] > df["freight_per_kg_mode_country_p80"])
    ).astype(int)
    df["is_cost_risk"] = df["cost_risk_mode_p80"].astype(int)
    df["is_delay_risk"] = df["is_delayed"].astype(int)

    delayed_delay_days = df.loc[df["is_delayed"].eq(1), "delay_days"]
    severe_threshold = delayed_delay_days.quantile(COST_RISK_MAIN_QUANTILE)
    df["severe_delay_p80_threshold"] = severe_threshold
    df["is_severe_delay"] = (
        df["is_delayed"].eq(1) & (df["delay_days"] > severe_threshold)
    ).astype(int)

    df["is_high_risk"] = ((df["is_cost_risk"] == 1) | (df["is_delay_risk"] == 1)).astype(int)
    df["is_compound_high_risk"] = (
        (df["is_cost_risk"] == 1) & (df["is_delay_risk"] == 1)
    ).astype(int)

    conditions = [
        (df["is_cost_risk"].eq(0) & df["is_delay_risk"].eq(0)),
        (df["is_cost_risk"].eq(1) & df["is_delay_risk"].eq(0)),
        (df["is_cost_risk"].eq(0) & df["is_delay_risk"].eq(1)),
        (df["is_cost_risk"].eq(1) & df["is_delay_risk"].eq(1)),
    ]
    choices = ["normal", "cost_risk_only", "delay_risk_only", "compound_high_risk"]
    df["risk_segment"] = np.select(conditions, choices, default="unclassified")

    df["planned_lead_days"] = (df["scheduled_delivery_date"] - df["po_sent_date"]).dt.days
    df["pq_to_po_days"] = (df["po_sent_date"] - df["pq_first_sent_date"]).dt.days

    for col in date_cols:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    return df


def main() -> None:
    ensure_dirs()
    with get_connection() as conn:
        cur = conn.cursor()
        table_checks = []
        for table in ["ods_order", "ods_order_detail", "ods_product", "ods_vendor", "ods_shipment"]:
            table_id = quote_identifier(table, conn)
            cur.execute(f"SELECT COUNT(*) FROM {table_id}")
            rows = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(DISTINCT id) FROM {table_id}")
            ids = cur.fetchone()[0]
            table_checks.append(
                {"table_name": table, "row_count": rows, "distinct_id_count": ids, "relationship_to_id": "one_to_one" if rows == ids else "one_to_many"}
            )

        cur.execute("DROP TABLE IF EXISTS wide_shipment_base")
        cur.execute(
            """
            CREATE TABLE wide_shipment_base AS
            SELECT
                s.id AS shipment_id,
                o.project_code,
                o.pq_number,
                o.po_so_number,
                o.asn_dn_number,
                o.managed_by,
                p.product_group,
                p.sub_classification,
                p.item_description,
                p.molecule_test_type,
                p.brand,
                p.dosage,
                p.dosage_form,
                p.unit_of_measure_per_pack,
                v.vendor_name,
                v.manufacturing_site,
                od.line_item_quantity,
                od.pack_price,
                od.unit_price,
                od.line_item_value,
                od.first_line_designation,
                s.country,
                s.fulfill_via,
                s.vendor_inco_term,
                s.shipment_mode,
                s.pq_first_sent_date,
                s.po_sent_date,
                s.scheduled_delivery_date,
                s.delivered_to_client_date,
                s.delivery_recorded_date,
                s.weight_kg,
                s.freight_cost_usd,
                s.insurance_cost_usd
            FROM ods_shipment s
            LEFT JOIN ods_order o ON s.id = o.id
            LEFT JOIN ods_product p ON s.id = p.id
            LEFT JOIN ods_vendor v ON s.id = v.id
            LEFT JOIN ods_order_detail od ON s.id = od.id
            """
        )
        conn.commit()

        wide = pd.read_sql_query("SELECT * FROM wide_shipment_base", conn)
        wide = build_risk_labels(wide)
        replace_table_from_df(conn, "wide_shipment_risk", wide)
        conn.commit()

    post_checks = {
        "raw_shipment_rows": int(wide["shipment_id"].shape[0]),
        "wide_rows": int(len(wide)),
        "duplicate_shipment_id_count": int(wide["shipment_id"].duplicated().sum()),
        "distinct_shipment_id_count": int(wide["shipment_id"].nunique()),
        "risk_segment_count_sum": int(wide["risk_segment"].value_counts().sum()),
        "valid_freight_per_kg_count": int(wide["freight_per_kg"].notna().sum()),
        "date_missing_count": int(wide["is_date_missing"].sum()),
        "invalid_weight_count": int(wide["is_weight_invalid"].sum()),
    }

    write_csv(pd.DataFrame(table_checks), SQL_CHECKS_DIR / "03_join_grain_checks.csv")
    write_csv(wide, SQL_TABLES_DIR / "wide_shipment_risk.csv")
    write_csv(wide[wide["is_weight_invalid"].eq(1)], SQL_CHECKS_DIR / "03_invalid_weight_records.csv")
    write_csv(wide[wide["is_date_missing"].eq(1)], SQL_CHECKS_DIR / "03_date_missing_records.csv")
    write_json(SQL_CHECKS_DIR / "03_wide_table_checks.json", post_checks)
    print("Built wide_shipment_risk with risk labels.")


if __name__ == "__main__":
    main()
