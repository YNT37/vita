"""聚合用户财务上下文，供 AI 与概览接口共用。"""

from datetime import date, datetime

from models import Asset, Reminder, Transaction
from services.category_service import grouped_categories, seed_user_categories


def _month_range(month: str):
    start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def month_stats(user_id: int, month: str | None = None) -> dict:
    month = month or date.today().strftime("%Y-%m")
    start, end = _month_range(month)
    items = (
        Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .all()
    )
    income = sum((t.amount for t in items if t.type == "income"), 0)
    expense = sum((t.amount for t in items if t.type == "expense"), 0)
    return {
        "month": month,
        "income": float(income),
        "expense": float(expense),
        "balance": float(income) - float(expense),
    }


def build_user_context(user_id: int) -> dict:
    seed_user_categories(user_id)
    today = date.today()
    end = datetime.combine(today, datetime.max.time())
    month = today.strftime("%Y-%m")

    txns = (
        Transaction.query.filter_by(user_id=user_id, date=today)
        .order_by(Transaction.id.desc())
        .all()
    )
    reminders_today = (
        Reminder.query.filter(
            Reminder.user_id == user_id,
            Reminder.done.is_(False),
            Reminder.due_at <= end,
        )
        .order_by(Reminder.due_at.asc())
        .all()
    )
    reminders_pending = (
        Reminder.query.filter_by(user_id=user_id, done=False)
        .order_by(Reminder.due_at.asc())
        .limit(20)
        .all()
    )
    assets = (
        Asset.query.filter_by(user_id=user_id)
        .order_by(Asset.updated_at.desc(), Asset.id.desc())
        .all()
    )
    asset_dicts = [a.to_dict() for a in assets]
    asset_total = sum(a["balance"] for a in asset_dicts if a.get("kind") != "liability")
    liability_total = sum(a["balance"] for a in asset_dicts if a.get("kind") == "liability")

    expense_total = sum(float(t.amount) for t in txns if t.type == "expense")
    income_total = sum(float(t.amount) for t in txns if t.type == "income")
    mstats = month_stats(user_id, month)

    return {
        "transactions_today": [t.to_dict() for t in txns],
        "reminders_today": [r.to_dict() for r in reminders_today],
        "reminders_pending": [r.to_dict() for r in reminders_pending],
        "assets": asset_dicts,
        "assets_total": asset_total,
        "liabilities_total": liability_total,
        "net_worth": asset_total - liability_total,
        "expense_total": expense_total,
        "income_total": income_total,
        "month_stats": mstats,
        "categories": grouped_categories(user_id),
    }
