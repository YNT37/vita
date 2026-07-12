from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Transaction
from errors import ApiError

finance_bp = Blueprint("finance", __name__, url_prefix="/api")


def _uid():
    return int(get_jwt_identity())


def _parse_date(s, field="date"):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ApiError("invalid_date", "日期格式应为 YYYY-MM-DD", 400, field)


def _month_range(month):
    """month: 'YYYY-MM'，返回左闭右开区间 [start, end)。"""
    try:
        start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except (ValueError, TypeError):
        raise ApiError("invalid_month", "月份格式应为 YYYY-MM", 400, "month")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@finance_bp.post("/transactions")
@jwt_required()
def create_transaction():
    data = request.get_json(silent=True) or {}
    t_type = (data.get("type") or "").strip()
    if t_type not in ("income", "expense"):
        raise ApiError("invalid_type", "type 必须是 income 或 expense", 400, "type")
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError, ValueError):
        raise ApiError("invalid_amount", "金额必须是数字", 400, "amount")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("100000000"):
        raise ApiError("invalid_amount", "金额需大于 0 且不超过 1 亿", 400, "amount")
    category = (data.get("category") or "").strip()
    if not category or len(category) > 32:
        raise ApiError("invalid_category", "分类不能为空且不超过32位", 400, "category")
    note = (data.get("note") or "").strip()
    if len(note) > 200:
        raise ApiError("invalid_note", "备注不超过200位", 400, "note")
    d = _parse_date(data.get("date"))
    txn = Transaction(
        user_id=_uid(),
        type=t_type,
        amount=amount,
        category=category,
        note=note,
        date=d,
    )
    db.session.add(txn)
    db.session.commit()
    return jsonify(txn.to_dict()), 201


@finance_bp.get("/transactions")
@jwt_required()
def list_transactions():
    q = Transaction.query.filter_by(user_id=_uid())
    month = request.args.get("month")
    if month:
        start, end = _month_range(month)
        q = q.filter(Transaction.date >= start, Transaction.date < end)
    category = request.args.get("category")
    if category:
        q = q.filter_by(category=category)
    items = q.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    return jsonify([t.to_dict() for t in items]), 200


@finance_bp.delete("/transactions/<int:txn_id>")
@jwt_required()
def delete_transaction(txn_id):
    txn = Transaction.query.filter_by(id=txn_id, user_id=_uid()).first()
    if not txn:
        raise ApiError("not_found", "交易不存在", 404)
    db.session.delete(txn)
    db.session.commit()
    return jsonify({"ok": True}), 200


@finance_bp.get("/stats/summary")
@jwt_required()
def stats_summary():
    q = Transaction.query.filter_by(user_id=_uid())
    month = request.args.get("month")
    if month:
        start, end = _month_range(month)
        q = q.filter(Transaction.date >= start, Transaction.date < end)
    items = q.all()

    income = sum((t.amount for t in items if t.type == "income"), Decimal("0"))
    expense = sum((t.amount for t in items if t.type == "expense"), Decimal("0"))

    by_cat = {}
    by_day = {}
    for t in items:
        by_cat.setdefault((t.category, t.type), Decimal("0"))
        by_cat[(t.category, t.type)] += t.amount
        key = t.date.isoformat()
        by_day.setdefault(key, {"income": Decimal("0"), "expense": Decimal("0")})
        by_day[key][t.type] += t.amount

    return jsonify({
        "income": float(income),
        "expense": float(expense),
        "byCategory": [
            {"category": c, "type": tp, "amount": float(v)}
            for (c, tp), v in sorted(by_cat.items())
        ],
        "byDay": [
            {"date": d, "income": float(v["income"]), "expense": float(v["expense"])}
            for d, v in sorted(by_day.items())
        ],
    }), 200
