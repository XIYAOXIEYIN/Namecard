import ast
import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    LOG_DIR,
    MYSQL_CONFIG,
    OUTPUT_DIR,
    PYTHON_CHECKS_DIR,
    PYTHON_FIGURES_DIR,
    PYTHON_MODELS_DIR,
    PYTHON_TABLES_DIR,
    SQL_CHECKS_DIR,
    SQL_TABLES_DIR,
)


OUTPUT_SUBDIRS = [
    OUTPUT_DIR,
    SQL_TABLES_DIR,
    SQL_CHECKS_DIR,
    PYTHON_TABLES_DIR,
    PYTHON_FIGURES_DIR,
    PYTHON_MODELS_DIR,
    PYTHON_CHECKS_DIR,
    LOG_DIR,
]


RAW_COLUMN_MAP = {
    "order": [
        "id",
        "project_code",
        "pq_number",
        "po_so_number",
        "asn_dn_number",
        "managed_by",
    ],
    "order_detail": [
        "id",
        "line_item_quantity",
        "pack_price",
        "unit_price",
        "line_item_value",
        "first_line_designation",
    ],
    "product": [
        "id",
        "product_group",
        "sub_classification",
        "item_description",
        "molecule_test_type",
        "brand",
        "dosage",
        "dosage_form",
        "unit_of_measure_per_pack",
    ],
    "shipment": [
        "id",
        "country",
        "fulfill_via",
        "vendor_inco_term",
        "shipment_mode",
        "pq_first_sent_date",
        "po_sent_date",
        "scheduled_delivery_date",
        "delivered_to_client_date",
        "delivery_recorded_date",
        "weight_kg",
        "freight_cost_usd",
        "insurance_cost_usd",
    ],
    "vendor": ["id", "vendor_name", "manufacturing_site"],
}


def ensure_dirs() -> None:
    for path in OUTPUT_SUBDIRS:
        path.mkdir(parents=True, exist_ok=True)


def get_connection():
    ensure_dirs()
    import pymysql

    return pymysql.connect(**MYSQL_CONFIG)


def is_mysql_connection(conn) -> bool:
    return True


def quote_identifier(name: str, conn=None) -> str:
    return "`" + name.replace("`", "``") + "`"


def _mysql_type_for_series(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE"
    if pd.api.types.is_bool_dtype(series):
        return "TINYINT"
    max_len = int(series.dropna().astype(str).str.len().max() or 0)
    if max_len <= 255:
        return "VARCHAR(255)"
    return "TEXT"


def replace_table_from_df(conn, table_name: str, df: pd.DataFrame) -> None:
    cur = conn.cursor()
    table = quote_identifier(table_name, conn)
    cur.execute(f"DROP TABLE IF EXISTS {table}")
    columns = []
    for col in df.columns:
        columns.append(f"{quote_identifier(col, conn)} {_mysql_type_for_series(df[col])}")
    cur.execute(f"CREATE TABLE {table} ({', '.join(columns)})")
    if not df.empty:
        cols = ", ".join(quote_identifier(col, conn) for col in df.columns)
        placeholders = ", ".join(["%s"] * len(df.columns))
        values = [
            tuple(None if pd.isna(value) else value for value in row)
            for row in df.itertuples(index=False, name=None)
        ]
        cur.executemany(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values)
    conn.commit()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def normalize_text_series(series: pd.Series) -> pd.Series:
    out = series.astype("string").str.strip()
    out = out.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "N/A": pd.NA})
    return out


def parse_mysql_insert_values(sql_text: str, table: str) -> pd.DataFrame:
    pattern = re.compile(rf"INSERT INTO `{re.escape(table)}` VALUES (.*?);", re.S)
    rows = []
    for match in pattern.finditer(sql_text):
        values = match.group(1)
        values = re.sub(r"\bNULL\b", "None", values)
        parsed = ast.literal_eval("[" + values + "]")
        rows.extend(parsed)
    return pd.DataFrame(rows, columns=RAW_COLUMN_MAP[table])


def parse_all_raw_tables(sql_path: Path) -> dict[str, pd.DataFrame]:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    return {table: parse_mysql_insert_values(sql_text, table) for table in RAW_COLUMN_MAP}


def load_table(table_name: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(f"SELECT * FROM {quote_identifier(table_name, conn)}", conn)


def export_query(conn, sql: str, path: Path) -> pd.DataFrame:
    df = pd.read_sql_query(sql, conn)
    write_csv(df, path)
    return df


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({"": np.nan, "N/A": np.nan}), errors="coerce")


def clean_date(series: pd.Series) -> pd.Series:
    cleaned = normalize_text_series(series)
    return pd.to_datetime(cleaned, errors="coerce")
