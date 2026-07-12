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

    app.register_blueprint(auth_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(finance_bp)

    register_error_handlers(app)
    register_jwt_error_handlers(jwt)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
