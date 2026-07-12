from flask import jsonify


class ApiError(Exception):
    """统一业务异常，序列化为 {"error":{"code","message","field?"}}。"""

    def __init__(self, code, message, status=400, field=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.field = field

    def to_response(self):
        body = {"error": {"code": self.code, "message": self.message}}
        if self.field:
            body["error"]["field"] = self.field
        return jsonify(body), self.status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _handle_api_error(err):
        return err.to_response()

    @app.errorhandler(400)
    def _bad_request(e):
        return jsonify({"error": {"code": "bad_request", "message": "请求无效"}}), 400

    @app.errorhandler(404)
    def _not_found(e):
        return jsonify({"error": {"code": "not_found", "message": "资源不存在"}}), 404

    @app.errorhandler(405)
    def _method_not_allowed(e):
        return jsonify({"error": {"code": "method_not_allowed", "message": "方法不允许"}}), 405

    @app.errorhandler(500)
    def _server_error(e):
        return jsonify({"error": {"code": "server_error", "message": "服务器内部错误"}}), 500


def register_jwt_error_handlers(jwt):
    """把所有 token 相关错误统一成 401，且格式与业务错误一致。"""

    def _unauth(msg):
        return jsonify({"error": {"code": "unauthorized", "message": msg}}), 401

    @jwt.unauthorized_loader
    def _missing_token(reason):
        return _unauth("缺少认证令牌")

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return _unauth("无效的令牌")

    @jwt.expired_token_loader
    def _expired_token(header, payload):
        return _unauth("令牌已过期")

    @jwt.revoked_token_loader
    def _revoked_token(header, payload):
        return _unauth("令牌已失效")

    @jwt.needs_fresh_token_loader
    def _needs_fresh(header, payload):
        return _unauth("需要重新登录")
