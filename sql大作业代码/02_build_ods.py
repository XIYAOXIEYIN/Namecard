import pandas as pd

from config import SQL_CHECKS_DIR, SQL_TABLES_DIR
from project_utils import (
    clean_date,
    clean_numeric,
    ensure_dirs,
    get_connection,
    normalize_text_series,
    quote_identifier,
    replace_table_from_df,
    write_csv,
)


TEXT_COLUMNS = {
    "order": ["project_code", "pq_number", "po_so_number", "asn_dn_number", "managed_by"],
    "order_detail": ["first_line_designation"],
    "product": [
        "product_group",
        "sub_classification",
        "item_description",
        "molecule_test_type",
        "brand",
        "dosage",
        "dosage_form",
    ],
    "shipment": ["country", "fulfill_via", "vendor_inco_term", "shipment_mode"],
    "vendor": ["vendor_name", "manufacturing_site"],
}

NUMERIC_COLUMNS = {
    "order_detail": ["line_item_quantity", "pack_price", "unit_price", "line_item_value"],
    "product": ["unit_of_measure_per_pack"],
    "shipment": ["weight_kg", "freight_cost_usd", "insurance_cost_usd"],
}

DATE_COLUMNS = {
    "shipment": [
        "pq_first_sent_date",
        "po_sent_date",
        "scheduled_delivery_date",
        "delivered_to_client_date",
        "delivery_recorded_date",
    ]
}


def clean_table(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    for col in TEXT_COLUMNS.get(table_name, []):
        df[col] = normalize_text_series(df[col])
    for col in NUMERIC_COLUMNS.get(table_name, []):
        df[col] = clean_numeric(df[col])
    for col in DATE_COLUMNS.get(table_name, []):
        df[col] = clean_date(df[col]).dt.strftime("%Y-%m-%d")
    return df


def main() -> None:
    ensure_dirs()
    table_names = ["order", "order_detail", "product", "shipment", "vendor"]
    checks = []

    with get_connection() as conn:
        cur = conn.cursor()
        for table_name in table_names:
            raw = pd.read_csv(SQL_TABLES_DIR / f"raw_{table_name}.csv")
            clean = clean_table(table_name, raw)
            replace_table_from_df(conn, f"ods_{table_name}", clean)
            ods_table = quote_identifier(f"ods_{table_name}", conn)
            cur.execute(f"SELECT COUNT(*) FROM {ods_table}")
            row_count = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(DISTINCT id) FROM {ods_table}")
            distinct_count = cur.fetchone()[0]
            checks.append(
                {
                    "table_name": f"ods_{table_name}",
                    "row_count": int(row_count),
                    "distinct_id_count": int(distinct_count),
                    "duplicate_id_count": int(row_count - distinct_count),
                    "missing_id_count": int(clean["id"].isna().sum()),
                }
            )
        conn.commit()

    write_csv(pd.DataFrame(checks), SQL_CHECKS_DIR / "02_ods_table_checks.csv")
    print("Built ODS tables in local SQL database.")


if __name__ == "__main__":
    main()
