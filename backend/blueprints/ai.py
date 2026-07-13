from datetime import date, datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import ChatMessage, Reminder, Setting, Transaction
from errors import ApiError
from services.ai_service import generate_brief, generate_chat_reply, parse_input
from services.prompts import PERSONA_OPTIONS

ai_bp = Blueprint("ai", __name__, url_prefix="/api")

PERSONA_KEY = "persona"


def _uid():
    return int(get_jwt_identity())


def _get_persona(user_id):
    row = Setting.query.filter_by(user_id=user_id, key=PERSONA_KEY).first()
    if row and row.value in PERSONA_OPTIONS:
        return row.value
    return "butler"


def _set_persona(user_id, persona):
    row = Setting.query.filter_by(user_id=user_id, key=PERSONA_KEY).first()
    if row:
        row.value = persona
    else:
        db.session.add(Setting(user_id=user_id, key=PERSONA_KEY, value=persona))
    db.session.commit()


def _load_history(user_id, persona):
    rows = (
        ChatMessage.query.filter_by(user_id=user_id, persona=persona)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(12)
        .all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]


def _today_brief_context(user_id):
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    txns = (
        Transaction.query.filter_by(user_id=user_id, date=today)
        .order_by(Transaction.id.desc())
        .all()
    )
    reminders = (
        Reminder.query.filter(
            Reminder.user_id == user_id,
            Reminder.done.is_(False),
            Reminder.due_at <= end,
        )
        .order_by(Reminder.due_at.asc())
        .all()
    )

    expense_total = sum(float(t.amount) for t in txns if t.type == "expense")
    income_total = sum(float(t.amount) for t in txns if t.type == "income")

    return {
        "transactions_today": [t.to_dict() for t in txns],
        "reminders_today": [r.to_dict() for r in reminders],
        "expense_total": expense_total,
        "income_total": income_total,
    }


@ai_bp.get("/persona")
@jwt_required()
def get_persona():
    return jsonify({
        "current": _get_persona(_uid()),
        "options": list(PERSONA_OPTIONS),
    }), 200


@ai_bp.post("/persona")
@jwt_required()
def set_persona():
    data = request.get_json(silent=True) or {}
    persona = (data.get("persona") or "").strip()
    if persona not in PERSONA_OPTIONS:
        raise ApiError("invalid_persona", "未知角色，可选 butler/servant/sassy/lover", 400, "persona")
    _set_persona(_uid(), persona)
    return jsonify({"current": persona}), 200


@ai_bp.post("/ai/chat")
@jwt_required()
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        raise ApiError("invalid_message", "消息不能为空", 400, "message")
    if len(message) > 500:
        raise ApiError("invalid_message", "消息不超过500字", 400, "message")

    uid = _uid()
    persona = _get_persona(uid)
    history = _load_history(uid, persona)
    reply = generate_chat_reply(persona, message, history)

    db.session.add(ChatMessage(user_id=uid, role="user", content=message, persona=persona))
    db.session.add(ChatMessage(user_id=uid, role="assistant", content=reply, persona=persona))
    db.session.commit()

    return jsonify({"reply": reply}), 200


@ai_bp.post("/ai/brief")
@jwt_required()
def ai_brief():
    uid = _uid()
    persona = _get_persona(uid)
    context = _today_brief_context(uid)
    text = generate_brief(persona, context)
    return jsonify({"text": text}), 200


@ai_bp.post("/ai/parse")
@jwt_required()
def ai_parse():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        raise ApiError("invalid_text", "文本不能为空", 400, "text")
    if len(text) > 200:
        raise ApiError("invalid_text", "文本不超过200字", 400, "text")

    result = parse_input(text)
    return jsonify(result), 200
