from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Reminder
from errors import ApiError

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


@reminders_bp.get("/reminders")
@jwt_required()
def list_reminders():
    items = (
        Reminder.query.filter_by(user_id=_uid())
        .order_by(Reminder.due_at.asc())
        .all()
    )
    return jsonify([r.to_dict() for r in items]), 200


@reminders_bp.post("/reminders")
@jwt_required()
def create_reminder():
    data = request.get_json(silent=True) or {}
    title = _validate_title(data.get("title"))
    due_at = _parse_due(data.get("due_at"))
    r_type = _validate_type(data.get("type") or "life")
    note = _validate_note(data.get("note"))
    reminder = Reminder(
        user_id=_uid(),
        title=title,
        due_at=due_at,
        type=r_type,
        note=note,
        done=False,
    )
    db.session.add(reminder)
    db.session.commit()
    return jsonify(reminder.to_dict()), 201


@reminders_bp.patch("/reminders/<int:reminder_id>")
@jwt_required()
def update_reminder(reminder_id):
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=_uid()).first()
    if not reminder:
        raise ApiError("not_found", "提醒不存在", 404)
    data = request.get_json(silent=True) or {}
    if "done" in data:
        reminder.done = bool(data["done"])
    if "title" in data:
        reminder.title = _validate_title(data.get("title"))
    if "due_at" in data:
        reminder.due_at = _parse_due(data.get("due_at"))
    if "type" in data:
        reminder.type = _validate_type(data.get("type"))
    if "note" in data:
        reminder.note = _validate_note(data.get("note"))
    db.session.commit()
    return jsonify(reminder.to_dict()), 200


@reminders_bp.delete("/reminders/<int:reminder_id>")
@jwt_required()
def delete_reminder(reminder_id):
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=_uid()).first()
    if not reminder:
        raise ApiError("not_found", "提醒不存在", 404)
    db.session.delete(reminder)
    db.session.commit()
    return jsonify({"ok": True}), 200
