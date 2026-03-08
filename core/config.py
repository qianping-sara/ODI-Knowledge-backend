from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env", override=False)

_DEFAULT_DATABASE_NAME = "company_research"


def _build_mysql_url() -> str:
    host = os.getenv("MYSQL_HOST", "localhost").strip() or "localhost"
    port = os.getenv("MYSQL_PORT", "3306").strip() or "3306"
    user = os.getenv("MYSQL_USER", "root").strip() or "root"
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DB", "").strip() or _DEFAULT_DATABASE_NAME
    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    auth = f"{safe_user}:{safe_password}" if safe_password else safe_user
    return f"mysql+aiomysql://{auth}@{host}:{port}/{database}?charset=utf8mb4"


def get_database_url() -> str:
    direct = os.getenv("DATABASE_URL", "").strip()
    if direct:
        return direct
    return _build_mysql_url()


def get_app_name() -> str:
    return os.getenv("APP_NAME", "company-research-chatbot")
