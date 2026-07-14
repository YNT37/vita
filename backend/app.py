from flask import Flask, jsonify
import atexit
import logging
import threading
import time

from config import Config
from extensions import db, jwt, cors
from errors import register_error_handlers, register_jwt_error_handlers

logger = logging.getLogger(__name__)
_dispatch_stop = threading.Event()
_dispatch_thread: threading.Thread | None = None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # 导入模型确保建表；导入蓝图并注册
    from blueprints.auth import auth_bp, me_bp
    from blueprints.finance import finance_bp
    from blueprints.reminders import reminders_bp
    from blueprints.ai import ai_bp
    from blueprints.settings import settings_bp
    from blueprints.categories import categories_bp
    from blueprints.overview import overview_bp
    from blueprints.serverchan import serverchan_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(serverchan_bp)

    register_error_handlers(app)
    register_jwt_error_handlers(jwt)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        db.create_all()
        _ensure_schema()

    # Flask debug 热重载时只在子进程启动后台线程，避免双开
    import os

    if (not app.debug) or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _start_dispatch_loop(app)

    return app


def _ensure_schema():
    """轻量迁移：为已有 SQLite/PG 表补列。"""
    from sqlalchemy import text

    stmts = [
        "ALTER TABLE assets ADD COLUMN kind VARCHAR(16) DEFAULT 'asset'",
        "ALTER TABLE reminders ADD COLUMN notified_at DATETIME",
        "ALTER TABLE reminders ADD COLUMN recurrence VARCHAR(16) DEFAULT 'none'",
        "ALTER TABLE reminders ADD COLUMN linked_asset_name VARCHAR(32) DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN account VARCHAR(32) DEFAULT ''",
        "ALTER TABLE assets ADD COLUMN repay_due_day INTEGER",
        "ALTER TABLE assets ADD COLUMN repay_statement_day INTEGER",
    ]
    with db.engine.begin() as conn:
        for sql in stmts:
            try:
                conn.execute(text(sql))
            except Exception:
                pass
        # 旧负债备注回填 kind
        try:
            conn.execute(
                text("UPDATE assets SET kind='liability' WHERE note LIKE '%负债%'")
            )
            conn.execute(
                text("UPDATE assets SET kind='asset' WHERE kind IS NULL OR kind=''")
            )
        except Exception:
            pass


def _start_dispatch_loop(app: Flask):
    """后台定时推送到期提醒（用户已绑定 Server酱 SendKey 时生效）。"""
    global _dispatch_thread
    interval = int(app.config.get("NOTIFY_DISPATCH_INTERVAL") or 0)
    if interval <= 0:
        return
    if _dispatch_thread and _dispatch_thread.is_alive():
        return

    def _loop():
        time.sleep(min(15, interval))
        while not _dispatch_stop.is_set():
            try:
                with app.app_context():
                    from services.notify_service import dispatch_due_reminders

                    result = dispatch_due_reminders()
                    if result.get("sent"):
                        logger.info("notify dispatch sent=%s", result.get("sent"))
            except Exception as e:
                logger.warning("notify dispatch error: %s", e)
            _dispatch_stop.wait(interval)

    _dispatch_thread = threading.Thread(target=_loop, name="notify-dispatch", daemon=True)
    _dispatch_thread.start()

    def _stop():
        _dispatch_stop.set()

    atexit.register(_stop)


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
