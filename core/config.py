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
    direct = os.getenv("DATABASE_URL", "").strip() or os.getenv("POSTGRES_URL", "").strip()
    if direct:
        # Vercel/others use postgresql:// - SQLAlchemy async needs postgresql+asyncpg://
        if direct.startswith("postgresql://"):
            url = direct.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif direct.startswith("postgres://"):
            url = direct.replace("postgres://", "postgresql+asyncpg://", 1)
        else:
            return direct

        # asyncpg doesn't support sslmode in URL - strip it and use connect_args instead
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            params.pop("sslmode", None)
            params.pop("ssl", None)
            new_query = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=new_query))
        return url
    return _build_mysql_url()


def use_postgres() -> bool:
    """True if DATABASE_URL/POSTGRES_URL points to PostgreSQL."""
    direct = os.getenv("DATABASE_URL", "").strip() or os.getenv("POSTGRES_URL", "").strip()
    return direct.startswith("postgresql://") or direct.startswith("postgres://")


def get_app_name() -> str:
    return os.getenv("APP_NAME", "company-research-chatbot")
