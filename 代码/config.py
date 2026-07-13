from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_SQL_CANDIDATES = [
    BASE_DIR / "delivery_data.sql",
    BASE_DIR / "data" / "delivery_data.sql",
    PROJECT_ROOT / "数据" / "delivery_data.sql",
    PROJECT_ROOT.parent / "数据" / "delivery_data.sql",
]
DATA_SQL_PATH = next((path for path in DATA_SQL_CANDIDATES if path.exists()), DATA_SQL_CANDIDATES[-1])

OUTPUT_DIR = BASE_DIR / "output"
SQL_TABLES_DIR = OUTPUT_DIR / "sql_tables"
SQL_CHECKS_DIR = OUTPUT_DIR / "sql_checks"
PYTHON_TABLES_DIR = OUTPUT_DIR / "python_tables"
PYTHON_FIGURES_DIR = OUTPUT_DIR / "python_figures"
PYTHON_MODELS_DIR = OUTPUT_DIR / "python_models"
PYTHON_CHECKS_DIR = OUTPUT_DIR / "python_checks"
LOG_DIR = BASE_DIR / "logs"

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "scms delivery dataset",
    "charset": "utf8mb4",
}

RANDOM_STATE = 42
TEST_SIZE = 0.25
COST_RISK_MAIN_QUANTILE = 0.80
ROBUST_QUANTILES = [0.75, 0.80, 0.90]
MIN_MODE_COUNTRY_GROUP_SIZE = 30
LOW_FREQUENCY_MIN_COUNT = 20

LEAKAGE_COLUMNS = [
    "freight_cost_usd",
    "freight_per_kg",
    "delay_days",
    "delivered_to_client_date",
    "delivery_recorded_date",
    "is_high_freight_global_p80",
    "is_high_cost_risk",
    "is_delay_risk",
    "is_high_risk",
    "is_compound_high_risk",
    "risk_segment",
    "is_severe_delay",
]
