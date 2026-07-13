from flask import Flask, jsonify

from config import Config
from extensions import db, jwt, cors
from errors import register_error_handlers, register_jwt_error_handlers


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

    app.register_blueprint(auth_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(overview_bp)

    register_error_handlers(app)
    register_jwt_error_handlers(jwt)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        db.create_all()
        _ensure_schema()

    return app


def _ensure_schema():
    """轻量迁移：为已有 SQLite/PG 表补列。"""
    from sqlalchemy import text

    stmts = [
        "ALTER TABLE assets ADD COLUMN kind VARCHAR(16) DEFAULT 'asset'",
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


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
