import pandas as pd

from config import SQL_CHECKS_DIR, SQL_TABLES_DIR
from project_utils import ensure_dirs, export_query, get_connection, write_csv


DIMENSIONS = {
    "country": "country",
    "vendor": "vendor_name",
    "shipment_mode": "shipment_mode",
    "product_group": "product_group",
    "country_shipment_mode": "CONCAT(COALESCE(country, 'Unknown'), ' | ', COALESCE(shipment_mode, 'Unknown'))",
}


def risk_summary_sql(dim_expr: str) -> str:
    return f"""
    WITH base AS (
        SELECT
            COALESCE({dim_expr}, 'Unknown') AS dimension_value,
            shipment_id,
            freight_cost_usd,
            delay_days,
            is_high_risk,
            is_cost_risk,
            is_delay_risk,
            is_compound_high_risk,
            is_severe_delay
        FROM wide_shipment_risk
    ),
    total AS (
        SELECT SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) AS total_high_risk_freight
        FROM base
    )
    SELECT
        b.dimension_value,
        COUNT(*) AS order_count,
        SUM(is_high_risk) AS high_risk_order_count,
        ROUND(1.0 * SUM(is_high_risk) / COUNT(*), 4) AS high_risk_rate,
        ROUND(SUM(freight_cost_usd), 2) AS total_freight,
        ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END), 2) AS high_risk_freight,
        ROUND(
            1.0 * SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END)
            / NULLIF((SELECT total_high_risk_freight FROM total), 0),
            4
        ) AS high_risk_freight_contribution_rate,
        ROUND(AVG(delay_days), 2) AS avg_delay_days,
        SUM(is_severe_delay) AS severe_delay_order_count,
        SUM(is_compound_high_risk) AS compound_high_risk_order_count,
        SUM(is_cost_risk) AS cost_risk_order_count,
        SUM(is_delay_risk) AS delay_risk_order_count
    FROM base b
    GROUP BY b.dimension_value
    ORDER BY high_risk_freight DESC, high_risk_order_count DESC
    """


def pareto_sql(dim_expr: str, metric_expr: str, metric_name: str) -> str:
    return f"""
    WITH grouped AS (
        SELECT
            COALESCE({dim_expr}, 'Unknown') AS dimension_value,
            {metric_expr} AS metric_value
        FROM wide_shipment_risk
        GROUP BY COALESCE({dim_expr}, 'Unknown')
    ),
    ranked AS (
        SELECT
            dimension_value,
            metric_value,
            SUM(metric_value) OVER () AS total_metric,
            SUM(metric_value) OVER (ORDER BY metric_value DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_metric
        FROM grouped
    )
    SELECT
        dimension_value,
        '{metric_name}' AS metric_name,
        ROUND(metric_value, 2) AS metric_value,
        ROUND(1.0 * metric_value / NULLIF(total_metric, 0), 4) AS contribution_rate,
        ROUND(1.0 * cumulative_metric / NULLIF(total_metric, 0), 4) AS cumulative_contribution_rate,
        CASE WHEN 1.0 * cumulative_metric / NULLIF(total_metric, 0) <= 0.8 THEN 1 ELSE 0 END AS within_first_80_percent
    FROM ranked
    ORDER BY metric_value DESC
    """


def main() -> None:
    ensure_dirs()
    with get_connection() as conn:
        for name, expr in DIMENSIONS.items():
            export_query(conn, risk_summary_sql(expr), SQL_TABLES_DIR / f"risk_summary_by_{name}.csv")

        pareto_metrics = {
            "high_risk_order_count": "SUM(is_high_risk)",
            "high_risk_freight": "SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END)",
            "compound_high_risk_order_count": "SUM(is_compound_high_risk)",
            "positive_delay_days": "SUM(CASE WHEN delay_days > 0 THEN delay_days ELSE 0 END)",
        }
        pareto_frames = []
        for dim_name, expr in {
            "country": DIMENSIONS["country"],
            "vendor": DIMENSIONS["vendor"],
            "country_shipment_mode": DIMENSIONS["country_shipment_mode"],
        }.items():
            for metric_name, metric_expr in pareto_metrics.items():
                df = export_query(
                    conn,
                    pareto_sql(expr, metric_expr, metric_name),
                    SQL_TABLES_DIR / f"pareto_{dim_name}_{metric_name}.csv",
                )
                df.insert(0, "dimension_name", dim_name)
                pareto_frames.append(df)

        if pareto_frames:
            write_csv(pd.concat(pareto_frames, ignore_index=True), SQL_TABLES_DIR / "pareto_all.csv")

        export_query(
            conn,
            """
            SELECT
                risk_segment,
                COUNT(*) AS order_count,
                ROUND(1.0 * COUNT(*) / (SELECT COUNT(*) FROM wide_shipment_risk), 4) AS order_rate,
                ROUND(SUM(freight_cost_usd), 2) AS freight_sum,
                ROUND(AVG(delay_days), 2) AS avg_delay_days
            FROM wide_shipment_risk
            GROUP BY risk_segment
            ORDER BY order_count DESC
            """,
            SQL_CHECKS_DIR / "04_risk_segment_counts.csv",
        )

        export_query(
            conn,
            """
            SELECT
                COUNT(*) AS wide_rows,
                COUNT(DISTINCT shipment_id) AS distinct_shipment_id_count,
                COUNT(*) - COUNT(DISTINCT shipment_id) AS duplicate_shipment_id_count,
                SUM(is_high_risk) AS high_risk_count,
                ROUND(1.0 * SUM(is_high_risk) / COUNT(*), 4) AS high_risk_rate,
                SUM(is_cost_risk) AS cost_risk_count,
                SUM(is_delay_risk) AS delay_risk_count,
                SUM(is_compound_high_risk) AS compound_high_risk_count,
                SUM(is_date_missing) AS date_missing_count,
                SUM(is_weight_invalid) AS invalid_weight_count
            FROM wide_shipment_risk
            """,
            SQL_CHECKS_DIR / "04_core_quality_checks.csv",
        )

    print("Generated SQL risk summaries and Pareto tables.")


if __name__ == "__main__":
    main()
