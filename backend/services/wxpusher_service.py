"""WxPusher 微信消息推送。"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import current_app

logger = logging.getLogger(__name__)

SEND_URL = "https://wxpusher.zjiecode.com/api/send/message"
CREATE_QR_URL = "https://wxpusher.zjiecode.com/api/fun/create/qrcode"
SCAN_UID_URL = "https://wxpusher.zjiecode.com/api/fun/scan-qrcode-uid"


def get_app_token() -> str:
    return (current_app.config.get("WXPUSHER_APP_TOKEN") or "").strip()


def is_configured() -> bool:
    return bool(get_app_token())


def _http_json(method: str, url: str, payload: dict | None = None, timeout: int = 15) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        logger.warning("WxPusher HTTP %s: %s", e.code, raw[:300])
        try:
            return json.loads(raw)
        except Exception:
            return {"code": e.code, "msg": raw or str(e)}
    except Exception as e:
        logger.warning("WxPusher request failed: %s", e)
        return {"code": -1, "msg": str(e)}


def create_bind_qrcode(extra: str, valid_time: int = 1800) -> dict[str, Any]:
    """创建带参数二维码，用于把 Vita 用户与 WxPusher UID 绑定。"""
    token = get_app_token()
    if not token:
        return {"ok": False, "error": "服务器未配置 WXPUSHER_APP_TOKEN"}
    extra = (extra or "")[:64]
    res = _http_json(
        "POST",
        CREATE_QR_URL,
        {"appToken": token, "extra": extra, "validTime": valid_time},
    )
    if res.get("code") != 1000:
        return {"ok": False, "error": res.get("msg") or "创建二维码失败", "raw": res}
    data = res.get("data") or {}
    return {
        "ok": True,
        "code": data.get("code"),
        "url": data.get("url") or data.get("shortUrl"),
        "shortUrl": data.get("shortUrl"),
        "expires": data.get("expires") or valid_time,
        "extra": data.get("extra") or extra,
    }


def query_scan_uid(code: str) -> dict[str, Any]:
    """查询参数二维码最近一次扫码用户的 UID（轮询间隔须 ≥10 秒）。"""
    if not code:
        return {"ok": False, "uid": None, "error": "缺少 code"}
    qs = urllib.parse.urlencode({"code": code})
    res = _http_json("GET", f"{SCAN_UID_URL}?{qs}")
    # 成功时 data 可能是 uid 字符串，或尚未扫码时为空
    if res.get("code") == 1000:
        data = res.get("data")
        uid = None
        if isinstance(data, str) and data.strip():
            uid = data.strip()
        elif isinstance(data, dict):
            uid = (data.get("uid") or data.get("UID") or "").strip() or None
        return {"ok": True, "uid": uid, "raw": res}
    # 未扫码时部分版本返回非 1000
    msg = res.get("msg") or ""
    if "没有" in msg or "未" in msg or res.get("code") in (1001, 1005):
        return {"ok": True, "uid": None, "raw": res}
    return {"ok": False, "uid": None, "error": msg or "查询失败", "raw": res}


def send_message(
    uid: str,
    content: str,
    summary: str | None = None,
    content_type: int = 1,
    url: str | None = None,
) -> dict[str, Any]:
    token = get_app_token()
    if not token:
        return {"ok": False, "error": "服务器未配置 WXPUSHER_APP_TOKEN"}
    uid = (uid or "").strip()
    if not uid:
        return {"ok": False, "error": "未绑定 WxPusher UID"}
    content = (content or "").strip()
    if not content:
        return {"ok": False, "error": "消息内容为空"}
    payload: dict[str, Any] = {
        "appToken": token,
        "content": content[:4000],
        "contentType": content_type,
        "uids": [uid],
        "verifyPayType": 0,
    }
    if summary:
        payload["summary"] = summary[:100]
    if url:
        payload["url"] = url
    res = _http_json("POST", SEND_URL, payload)
    if res.get("code") == 1000:
        return {"ok": True, "raw": res}
    return {"ok": False, "error": res.get("msg") or "发送失败", "raw": res}
