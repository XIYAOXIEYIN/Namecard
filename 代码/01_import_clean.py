import pandas as pd

from config import DATA_SQL_PATH, SQL_CHECKS_DIR, SQL_TABLES_DIR
from project_utils import ensure_dirs, get_connection, parse_all_raw_tables, replace_table_from_df, write_csv, write_json


def main() -> None:
    ensure_dirs()
    if DATA_SQL_PATH.exists():
        raw_tables = parse_all_raw_tables(DATA_SQL_PATH)
        source_note = "MySQL dump"
    else:
        table_names = ["order", "order_detail", "product", "shipment", "vendor"]
        raw_tables = {
            table_name: pd.read_csv(SQL_TABLES_DIR / f"raw_{table_name}.csv")
            for table_name in table_names
        }
        source_note = "existing raw CSV snapshots"

    row_checks = []
    with get_connection() as conn:
        for table_name, df in raw_tables.items():
            write_csv(df, SQL_TABLES_DIR / f"raw_{table_name}.csv")
            replace_table_from_df(conn, f"raw_{table_name}", df)
            row_checks.append(
                {
                    "table_name": table_name,
                    "row_count": int(len(df)),
                    "distinct_id_count": int(df["id"].nunique()),
                    "duplicate_id_count": int(df["id"].duplicated().sum()),
                    "min_id": int(df["id"].min()),
                    "max_id": int(df["id"].max()),
                }
            )
        conn.commit()

    checks = pd.DataFrame(row_checks)
    write_csv(checks, SQL_CHECKS_DIR / "01_raw_table_row_checks.csv")
    write_json(SQL_CHECKS_DIR / "01_import_summary.json", row_checks)
    print(f"Imported raw tables from {source_note} into CSV files and local SQL tables.")


if __name__ == "__main__":
    main()
