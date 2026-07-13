from datetime import date, datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from errors import ApiError
from models import Asset, Reminder
from services.category_service import seed_user_categories
from services.user_context import build_user_context, month_stats

overview_bp = Blueprint("overview", __name__, url_prefix="/api")


def _uid():
    return int(get_jwt_identity())


@overview_bp.get("/overview")
@jwt_required()
def get_overview():
    uid = _uid()
    seed_user_categories(uid)
    month = (request.args.get("month") or date.today().strftime("%Y-%m")).strip()

    ctx = build_user_context(uid)
    now = datetime.utcnow()
    overdue = [
        r for r in ctx.get("reminders_pending", [])
        if r.get("due_at") and datetime.fromisoformat(r["due_at"]) < now
    ]

    from models import Transaction

    start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    items = (
        Transaction.query.filter(
            Transaction.user_id == uid,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .all()
    )
    by_cat = {}
    by_day = {}
    for t in items:
        by_cat.setdefault((t.category, t.type), 0)
        by_cat[(t.category, t.type)] += t.amount
        key = t.date.isoformat()
        by_day.setdefault(key, {"income": 0, "expense": 0})
        by_day[key][t.type] += t.amount

    stats = {
        **month_stats(uid, month),
        "byCategory": [
            {"category": c, "type": tp, "amount": float(v)}
            for (c, tp), v in sorted(by_cat.items())
        ],
        "byDay": [
            {"date": d, "income": float(v["income"]), "expense": float(v["expense"])}
            for d, v in sorted(by_day.items())
        ],
    }

    return jsonify({
        "month": month,
        "stats": stats,
        "assets": ctx["assets"],
        "assets_total": ctx["assets_total"],
        "reminders_pending": ctx["reminders_pending"],
        "reminders_overdue_count": len(overdue),
        "categories": ctx["categories"],
    }), 200
