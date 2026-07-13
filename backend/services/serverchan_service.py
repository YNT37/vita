"""Server酱·Turbo 微信推送（https://sct.ftqq.com）。"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# POST https://sctapi.ftqq.com/<SendKey>.send
SEND_URL_TMPL = "https://sctapi.ftqq.com/{sendkey}.send"


def _http_json(url: str, payload: dict, timeout: int = 15) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        logger.warning("Server酱 HTTP %s: %s", e.code, raw[:300])
        try:
            return json.loads(raw)
        except Exception:
            return {"code": e.code, "message": raw or str(e)}
    except Exception as e:
        logger.warning("Server酱 request failed: %s", e)
        return {"code": -1, "message": str(e)}


def normalize_sendkey(sendkey: str | None) -> str:
    return (sendkey or "").strip()


def is_valid_sendkey(sendkey: str) -> bool:
    """SendKey 一般为 SCT/SCU 开头，长度不宜过短。"""
    key = normalize_sendkey(sendkey)
    if len(key) < 8 or len(key) > 128:
        return False
    # 允许 SCT_xxx / SCUxxx / 纯字母数字下划线
    return bool(re.match(r"^[A-Za-z0-9_\-]+$", key))


def send_message(sendkey: str, title: str, desp: str = "") -> dict[str, Any]:
    key = normalize_sendkey(sendkey)
    if not key:
        return {"ok": False, "error": "未绑定 Server酱 SendKey"}
    title = (title or "").strip() or "Vita 提醒"
    if len(title) > 100:
        title = title[:100]
    desp = (desp or "").strip()
    url = SEND_URL_TMPL.format(sendkey=urllib.parse.quote(key, safe=""))
    res = _http_json(url, {"title": title, "desp": desp})
    # Turbo：成功 code == 0
    code = res.get("code")
    if code == 0 or code == "0":
        return {"ok": True, "raw": res}
    msg = res.get("message") or res.get("msg") or "发送失败"
    return {"ok": False, "error": str(msg), "raw": res}
