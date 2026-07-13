"""Server酱 绑定与推送 API。"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from errors import ApiError
from services.notify_service import dispatch_due_reminders
from services.serverchan_service import is_valid_sendkey, send_message
from services.user_settings import (
    get_serverchan_sendkey,
    set_serverchan_sendkey,
    mask_serverchan_sendkey,
)

serverchan_bp = Blueprint("serverchan", __name__, url_prefix="/api/serverchan")


def _uid():
    return int(get_jwt_identity())


def _status_payload(user_id: int):
    key = get_serverchan_sendkey(user_id)
    return {
        "bound": bool(key),
        "key_hint": mask_serverchan_sendkey(key),
        "bind_help_url": "https://sct.ftqq.com/",
    }


@serverchan_bp.get("/status")
@jwt_required()
def status():
    return jsonify(_status_payload(_uid())), 200


@serverchan_bp.post("/key")
@jwt_required()
def bind_key():
    """保存或清空 Server酱 SendKey。"""
    data = request.get_json(silent=True) or {}
    raw = data.get("sendkey")
    if raw is not None and not isinstance(raw, str):
        raise ApiError("invalid_sendkey", "SendKey 格式无效", 400, "sendkey")
    key = (raw or "").strip()
    if key and not is_valid_sendkey(key):
        raise ApiError(
            "invalid_sendkey",
            "SendKey 无效，请到 sct.ftqq.com 用微信登录后复制",
            400,
            "sendkey",
        )
    set_serverchan_sendkey(_uid(), key if key else None)
    return jsonify(_status_payload(_uid())), 200


@serverchan_bp.post("/test")
@jwt_required()
def test_push():
    user_id = _uid()
    key = get_serverchan_sendkey(user_id)
    if not key:
        raise ApiError("serverchan_not_bound", "请先绑定 Server酱 SendKey", 400)
    result = send_message(
        key,
        "Vita 测试推送",
        "微信提醒通道已打通。到期待办会推送到这里，无需安装额外 App。",
    )
    if not result.get("ok"):
        raise ApiError("serverchan_send_failed", result.get("error") or "发送失败", 502)
    return jsonify({"ok": True, "message": "已发送测试消息，请查看微信"}), 200


@serverchan_bp.post("/dispatch")
def dispatch():
    """
    扫描并推送到期提醒。
    - 登录用户：只推送自己的
    - Header X-Cron-Secret 与 NOTIFY_CRON_SECRET 一致：推送全部
    """
    secret = (
        current_app.config.get("NOTIFY_CRON_SECRET")
        or current_app.config.get("WXPUSHER_CRON_SECRET")
        or ""
    ).strip()
    header = (request.headers.get("X-Cron-Secret") or "").strip()
    auth = request.headers.get("Authorization") or ""

    if secret and header and header == secret:
        result = dispatch_due_reminders(user_id=None)
        return jsonify(result), 200

    if auth.lower().startswith("bearer "):
        from flask_jwt_extended import verify_jwt_in_request

        verify_jwt_in_request()
        result = dispatch_due_reminders(user_id=_uid())
        return jsonify(result), 200

    if secret:
        raise ApiError("unauthorized", "需要登录或有效的 X-Cron-Secret", 401)
    raise ApiError("unauthorized", "请先登录", 401)
