from project_utils import ensure_dirs, get_connection
from config import SQL_TABLES_DIR


def main() -> None:
    ensure_dirs()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
    manifest = SQL_TABLES_DIR / "sql_result_manifest.txt"
    csvs = sorted(p.name for p in SQL_TABLES_DIR.glob("*.csv"))
    manifest.write_text(
        "Database tables:\n"
        + "\n".join(tables)
        + "\n\nCSV outputs:\n"
        + "\n".join(csvs),
        encoding="utf-8",
    )
    print("Wrote SQL result manifest.")


if __name__ == "__main__":
    main()
