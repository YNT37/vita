import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url):
    """兼容旧格式 postgres:// -> postgresql://（SQLAlchemy 2.x 要求）。"""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    _db_url = os.getenv("DATABASE_URL", "").strip()
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _normalize_db_url(_db_url)
    else:
        # 本地开发默认 SQLite，文件固定在 backend/vita.db
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "vita.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JWT_SECRET_KEY = os.getenv("JWT_SECRET", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_EXPIRES_HOURS", "24")))

    # AI 接口：openai（OpenAI 兼容）/ anthropic（Anthropic 原生）
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
    AI_API_KEY = os.getenv("AI_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
    AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    # 到期提醒推送（Server酱，用户各自绑定 SendKey，无需服务器 Token）
    # 兼容旧变量名 WXPUSHER_DISPATCH_INTERVAL / WXPUSHER_CRON_SECRET
    NOTIFY_DISPATCH_INTERVAL = int(
        os.getenv("NOTIFY_DISPATCH_INTERVAL", os.getenv("WXPUSHER_DISPATCH_INTERVAL", "60"))
    )
    NOTIFY_CRON_SECRET = (
        os.getenv("NOTIFY_CRON_SECRET") or os.getenv("WXPUSHER_CRON_SECRET") or ""
    ).strip()
