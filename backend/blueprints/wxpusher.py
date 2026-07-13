"""WxPusher 绑定与推送 API。"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from errors import ApiError
from services.notify_service import dispatch_due_reminders
from services.user_settings import (
    get_wxpusher_uid,
    set_wxpusher_uid,
    mask_wxpusher_uid,
)
from services.wxpusher_service import (
    create_bind_qrcode,
    is_configured,
    query_scan_uid,
    send_message,
)

wxpusher_bp = Blueprint("wxpusher", __name__, url_prefix="/api/wxpusher")


def _uid():
    return int(get_jwt_identity())


def _status_payload(user_id: int):
    uid = get_wxpusher_uid(user_id)
    return {
        "configured": is_configured(),
        "bound": bool(uid),
        "uid_hint": mask_wxpusher_uid(uid),
        "bind_help_url": "https://wxpusher.zjiecode.com/docs/#/?id=获取uid",
    }


@wxpusher_bp.get("/status")
@jwt_required()
def status():
    return jsonify(_status_payload(_uid())), 200


@wxpusher_bp.post("/uid")
@jwt_required()
def bind_uid():
    """手动填写 UID（微信内关注后菜单「获取UID」）。"""
    if not is_configured():
        raise ApiError("wxpusher_not_configured", "服务器未配置 WXPUSHER_APP_TOKEN", 503)
    data = request.get_json(silent=True) or {}
    raw = data.get("uid")
    if raw is not None and not isinstance(raw, str):
        raise ApiError("invalid_uid", "UID 格式无效", 400, "uid")
    uid = (raw or "").strip()
    if uid and len(uid) > 64:
        raise ApiError("invalid_uid", "UID 过长", 400, "uid")
    set_wxpusher_uid(_uid(), uid if uid else None)
    return jsonify(_status_payload(_uid())), 200


@wxpusher_bp.post("/bind-qrcode")
@jwt_required()
def bind_qrcode():
    if not is_configured():
        raise ApiError("wxpusher_not_configured", "服务器未配置 WXPUSHER_APP_TOKEN", 503)
    user_id = _uid()
    result = create_bind_qrcode(extra=f"vita:{user_id}", valid_time=1800)
    if not result.get("ok"):
        raise ApiError("wxpusher_qr_failed", result.get("error") or "创建二维码失败", 502)
    return jsonify({
        "code": result.get("code"),
        "url": result.get("url"),
        "shortUrl": result.get("shortUrl"),
        "expires": result.get("expires"),
        "poll_interval_sec": 10,
        "hint": "请用微信扫码关注；扫码后等待约 10 秒自动绑定。也可手动填写 UID。",
    }), 200


@wxpusher_bp.get("/bind-poll")
@jwt_required()
def bind_poll():
    """轮询扫码结果；间隔须 ≥10 秒。"""
    if not is_configured():
        raise ApiError("wxpusher_not_configured", "服务器未配置 WXPUSHER_APP_TOKEN", 503)
    code = (request.args.get("code") or "").strip()
    if not code:
        raise ApiError("invalid_code", "缺少 code", 400, "code")
    result = query_scan_uid(code)
    if not result.get("ok"):
        raise ApiError("wxpusher_poll_failed", result.get("error") or "查询失败", 502)
    wx_uid = result.get("uid")
    bound = False
    if wx_uid:
        set_wxpusher_uid(_uid(), wx_uid)
        bound = True
    payload = _status_payload(_uid())
    payload["scanned"] = bool(wx_uid)
    payload["bound_now"] = bound
    return jsonify(payload), 200


@wxpusher_bp.post("/test")
@jwt_required()
def test_push():
    if not is_configured():
        raise ApiError("wxpusher_not_configured", "服务器未配置 WXPUSHER_APP_TOKEN", 503)
    user_id = _uid()
    wx_uid = get_wxpusher_uid(user_id)
    if not wx_uid:
        raise ApiError("wxpusher_not_bound", "请先绑定微信（UID）", 400)
    result = send_message(
        wx_uid,
        "【Vita】测试消息：微信提醒通道已打通，到期待办会推送到这里。",
        summary="Vita 测试推送",
    )
    if not result.get("ok"):
        raise ApiError("wxpusher_send_failed", result.get("error") or "发送失败", 502)
    return jsonify({"ok": True, "message": "已发送测试消息，请查看微信"}), 200


@wxpusher_bp.post("/dispatch")
def dispatch():
    """
    扫描并推送到期提醒。
    - 登录用户：只推送自己的
    - 带 X-Cron-Secret（与 WXPUSHER_CRON_SECRET 一致）：推送全部用户
    """
    secret = (current_app.config.get("WXPUSHER_CRON_SECRET") or "").strip()
    header = (request.headers.get("X-Cron-Secret") or "").strip()
    auth = request.headers.get("Authorization") or ""

    if secret and header and header == secret:
        result = dispatch_due_reminders(user_id=None)
        return jsonify(result), 200 if result.get("ok") else 503

    if auth.lower().startswith("bearer "):
        # 走 JWT：需手动校验
        from flask_jwt_extended import verify_jwt_in_request

        verify_jwt_in_request()
        result = dispatch_due_reminders(user_id=_uid())
        return jsonify(result), 200 if result.get("ok") else 503

    if secret:
        raise ApiError("unauthorized", "需要登录或有效的 X-Cron-Secret", 401)
    raise ApiError("unauthorized", "请先登录", 401)


@wxpusher_bp.post("/callback")
def callback():
    """WxPusher 关注回调（可选）：extra 为 vita:{user_id} 时自动绑定。"""
    data = request.get_json(silent=True) or {}
    action = data.get("action") or ""
    payload = data.get("data") or {}
    if action not in ("app_subscribe", "subscribe"):
        return jsonify({"ok": True, "ignored": True}), 200
    wx_uid = (payload.get("uid") or "").strip()
    extra = (payload.get("extra") or "").strip()
    if not wx_uid or not extra.startswith("vita:"):
        return jsonify({"ok": True, "bound": False}), 200
    try:
        user_id = int(extra.split(":", 1)[1])
    except (ValueError, IndexError):
        return jsonify({"ok": True, "bound": False}), 200
    set_wxpusher_uid(user_id, wx_uid)
    return jsonify({"ok": True, "bound": True, "user_id": user_id}), 200
