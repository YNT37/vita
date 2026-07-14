"""到期提醒扫描并推送到 Server酱；周期提醒推送后自动进入下一期。"""

from __future__ import annotations

import logging
from datetime import datetime

from extensions import db
from models import Reminder, User
from services.reminder_service import (
    advance_recurring_reminder,
    debt_snapshot_for_reminder,
    normalize_repeat,
)
from services.serverchan_service import send_message
from services.user_settings import get_serverchan_sendkey

logger = logging.getLogger(__name__)

TYPE_LABEL = {
    "bill": "账单",
    "life": "生活",
    "anniversary": "纪念日",
}
REPEAT_LABEL = {
    "monthly": "每月",
    "weekly": "每周",
    "none": "一次",
}


def dispatch_due_reminders(user_id: int | None = None) -> dict:
    """推送已到期且未发送过的提醒。可指定用户，或扫描全部已绑定用户。

    due_at 按「本地墙钟时间」比较（与前端 datetime-local 一致），不用 utcnow。
    周期提醒在成功推送后自动推进到下一期，并附带关联欠款快照。
    """
    now = datetime.now()
    q = Reminder.query.filter(
        Reminder.done.is_(False),
        Reminder.due_at <= now,
    )
    if user_id is not None:
        q = q.filter_by(user_id=user_id)
    items = q.order_by(Reminder.due_at.asc()).limit(200).all()
    due = [
        r
        for r in items
        if r.notified_at is None or (r.due_at and r.notified_at < r.due_at)
    ]

    sent = 0
    skipped = 0
    advanced = 0
    errors: list[str] = []

    by_user: dict[int, list[Reminder]] = {}
    for r in due:
        by_user.setdefault(r.user_id, []).append(r)

    for uid, reminders in by_user.items():
        sendkey = get_serverchan_sendkey(uid)
        if not sendkey:
            skipped += len(reminders)
            continue
        user = db.session.get(User, uid)
        uname = user.username if user else str(uid)
        for r in reminders:
            label = TYPE_LABEL.get(r.type or "life", "提醒")
            due_text = r.due_at.strftime("%Y-%m-%d %H:%M") if r.due_at else ""
            snap = debt_snapshot_for_reminder(r)
            title = f"Vita提醒：{r.title}"
            desp = (
                f"### Vita 到期提醒\n\n"
                f"- 用户：{uname}\n"
                f"- 类型：{label}\n"
                f"- 周期：{REPEAT_LABEL.get(normalize_repeat(r.recurrence), '一次')}\n"
                f"- 标题：{r.title}\n"
                f"- 时间：{due_text}\n"
            )
            if snap.get("debt_summary"):
                desp += f"- 欠款：{snap['debt_summary']}\n"
            if r.note:
                desp += f"- 备注：{r.note}\n"
            desp += "\n请打开 Vita「提醒」页查看；周期提醒完成本期后会自动排到下一期。"
            result = send_message(sendkey, title, desp)
            if result.get("ok"):
                r.notified_at = now
                sent += 1
                if normalize_repeat(r.recurrence) != "none":
                    if advance_recurring_reminder(r, now=now):
                        advanced += 1
            else:
                errors.append(f"#{r.id}:{result.get('error')}")
                logger.warning("notify reminder %s failed: %s", r.id, result.get("error"))

    if sent or advanced:
        db.session.commit()

    return {
        "ok": True,
        "sent": sent,
        "skipped": skipped,
        "advanced": advanced,
        "errors": errors[:10],
        "checked_at": now.isoformat() + "Z",
    }
