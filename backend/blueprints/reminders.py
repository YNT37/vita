from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Reminder
from errors import ApiError
from services.reminder_service import (
    VALID_REPEAT,
    advance_recurring_reminder,
    infer_linked_asset_name,
    normalize_repeat,
    reminder_to_dict,
)

reminders_bp = Blueprint("reminders", __name__, url_prefix="/api")

VALID_TYPES = ("bill", "life", "anniversary")
_DUE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def _uid():
    return int(get_jwt_identity())


def _parse_due(s, field="due_at"):
    if not s or not isinstance(s, str):
        raise ApiError("invalid_due", "due_at 不能为空", 400, field)
    text = s.strip().replace("Z", "")
    for fmt in _DUE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ApiError("invalid_due", "due_at 格式应为 ISO 时间，如 2026-07-13T10:00", 400, field)


def _validate_title(value):
    title = (value or "").strip()
    if not title or len(title) > 120:
        raise ApiError("invalid_title", "标题不能为空且不超过120位", 400, "title")
    return title


def _validate_type(value):
    r_type = (value or "").strip()
    if r_type not in VALID_TYPES:
        raise ApiError("invalid_type", "type 必须是 bill/life/anniversary", 400, "type")
    return r_type


def _validate_note(value):
    note = (value or "").strip()
    if len(note) > 200:
        raise ApiError("invalid_note", "备注不超过200位", 400, "note")
    return note


def _validate_repeat(value):
    rep = normalize_repeat(value)
    if (value or "none").strip() and rep == "none" and (value or "").strip().lower() not in ("", "none"):
        raise ApiError("invalid_repeat", "repeat 必须是 none/monthly/weekly", 400, "repeat")
    return rep


def _validate_linked_asset(value):
    name = (value or "").strip()
    if len(name) > 32:
        raise ApiError("invalid_linked_asset", "关联账户名不超过32位", 400, "linked_asset_name")
    return name


@reminders_bp.get("/reminders")
@jwt_required()
def list_reminders():
    with_debt = (request.args.get("with_debt") or "").lower() in ("1", "true", "yes")
    items = (
        Reminder.query.filter_by(user_id=_uid())
        .order_by(Reminder.due_at.asc())
        .all()
    )
    return jsonify([reminder_to_dict(r, with_debt=with_debt) for r in items]), 200


@reminders_bp.get("/reminders/due-check")
@jwt_required()
def due_check():
    """到期提醒 + 关联欠款快照（浏览器弹窗 / 主动检查用）。"""
    now = datetime.now()
    items = (
        Reminder.query.filter(
            Reminder.user_id == _uid(),
            Reminder.done.is_(False),
            Reminder.due_at <= now,
        )
        .order_by(Reminder.due_at.asc())
        .limit(50)
        .all()
    )
    return jsonify(
        {
            "checked_at": now.isoformat(),
            "items": [reminder_to_dict(r, with_debt=True) for r in items],
        }
    ), 200


@reminders_bp.post("/reminders")
@jwt_required()
def create_reminder():
    data = request.get_json(silent=True) or {}
    title = _validate_title(data.get("title"))
    due_at = _parse_due(data.get("due_at"))
    r_type = _validate_type(data.get("type") or "life")
    note = _validate_note(data.get("note"))
    repeat = _validate_repeat(data.get("repeat"))
    linked = _validate_linked_asset(data.get("linked_asset_name"))
    if not linked and r_type == "bill":
        linked = infer_linked_asset_name(title, note)
    reminder = Reminder(
        user_id=_uid(),
        title=title,
        due_at=due_at,
        type=r_type,
        note=note,
        done=False,
        repeat=repeat,
        linked_asset_name=linked,
    )
    db.session.add(reminder)
    db.session.commit()
    return jsonify(reminder_to_dict(reminder, with_debt=True)), 201


@reminders_bp.patch("/reminders/<int:reminder_id>")
@jwt_required()
def update_reminder(reminder_id):
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=_uid()).first()
    if not reminder:
        raise ApiError("not_found", "提醒不存在", 404)
    data = request.get_json(silent=True) or {}
    advancing = False
    if "done" in data:
        want_done = bool(data["done"])
        if want_done and normalize_repeat(reminder.repeat) != "none":
            # 周期提醒：完成本期 → 推到下一期，保持未完成
            advancing = advance_recurring_reminder(reminder)
        else:
            reminder.done = want_done
    if "title" in data:
        reminder.title = _validate_title(data.get("title"))
    if "due_at" in data:
        reminder.due_at = _parse_due(data.get("due_at"))
        reminder.notified_at = None
    if "type" in data:
        reminder.type = _validate_type(data.get("type"))
    if "note" in data:
        reminder.note = _validate_note(data.get("note"))
    if "repeat" in data:
        reminder.repeat = _validate_repeat(data.get("repeat"))
    if "linked_asset_name" in data:
        reminder.linked_asset_name = _validate_linked_asset(data.get("linked_asset_name"))
    db.session.commit()
    body = reminder_to_dict(reminder, with_debt=True)
    if advancing:
        body["advanced"] = True
    return jsonify(body), 200


@reminders_bp.delete("/reminders/<int:reminder_id>")
@jwt_required()
def delete_reminder(reminder_id):
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=_uid()).first()
    if not reminder:
        raise ApiError("not_found", "提醒不存在", 404)
    db.session.delete(reminder)
    db.session.commit()
    return jsonify({"ok": True}), 200
