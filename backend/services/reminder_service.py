"""提醒周期推进与关联欠款快照。"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta

from models import Asset, Reminder

VALID_REPEAT = ("none", "monthly", "weekly")


def normalize_repeat(value: str | None) -> str:
    v = (value or "none").strip().lower()
    return v if v in VALID_REPEAT else "none"


def next_due_at(due: datetime, repeat: str) -> datetime:
    """按周期把到期时间推到下一期（尽量保持日/时分）。"""
    repeat = normalize_repeat(repeat)
    if repeat == "weekly":
        return due + timedelta(days=7)
    if repeat == "monthly":
        year, month, day = due.year, due.month, due.day
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        last = calendar.monthrange(year, month)[1]
        day = min(day, last)
        return due.replace(year=year, month=month, day=day)
    return due


def infer_linked_asset_name(title: str, note: str = "") -> str:
    text = f"{title} {note}"
    for kw in ("京东白条", "花呗", "白条", "借呗", "信用卡"):
        if kw == "白条" and "京东白条" in text:
            continue
        if kw in text:
            return kw
    return ""


def advance_recurring_reminder(reminder: Reminder, now: datetime | None = None) -> bool:
    """周期提醒完成一期后：推进 due_at，保持未完成以便下期再提醒。"""
    if normalize_repeat(getattr(reminder, "repeat", None)) == "none":
        return False
    base = reminder.due_at or (now or datetime.now())
    nxt = next_due_at(base, reminder.repeat)
    # 若仍不晚于现在（例如积压），继续往后推，最多 24 次
    cursor = now or datetime.now()
    for _ in range(24):
        if nxt > cursor:
            break
        nxt = next_due_at(nxt, reminder.repeat)
    reminder.due_at = nxt
    reminder.done = False
    reminder.notified_at = None
    return True


def debt_snapshot_for_reminder(reminder: Reminder) -> dict:
    """查关联负债账户当前欠款。"""
    name = (getattr(reminder, "linked_asset_name", None) or "").strip()
    if not name:
        name = infer_linked_asset_name(reminder.title or "", reminder.note or "")
    if not name:
        return {}
    asset = Asset.query.filter_by(user_id=reminder.user_id, name=name).first()
    if not asset:
        # 模糊：名称包含关键词
        assets = Asset.query.filter_by(user_id=reminder.user_id).all()
        asset = next((a for a in assets if name in (a.name or "")), None)
    if not asset:
        return {"linked_asset_name": name, "linked_balance": None, "debt_summary": f"未找到账户「{name}」"}
    bal = float(asset.balance)
    return {
        "linked_asset_name": asset.name,
        "linked_balance": bal,
        "linked_kind": asset.kind or "liability",
        "debt_summary": f"{asset.name}当前欠款 ¥{bal:.2f}",
    }


def reminder_to_dict(reminder: Reminder, *, with_debt: bool = False) -> dict:
    data = reminder.to_dict()
    if with_debt:
        data.update(debt_snapshot_for_reminder(reminder))
    return data


def detect_repeat_from_text(text: str) -> str:
    if re.search(r"每个月|每月|每月的|月月", text or ""):
        return "monthly"
    if re.search(r"每周|每星期", text or ""):
        return "weekly"
    return "none"
