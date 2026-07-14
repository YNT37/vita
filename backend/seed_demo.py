#!/usr/bin/env python3
"""Seed a demo user with sample finance data for video recording.

Usage (inside backend container or venv):
  python seed_demo.py
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import Asset, Reminder, Transaction, User
from services.category_service import seed_user_categories
from services.reminder_service import sync_liability_repay_reminder
from services.user_settings import set_persona

DEMO_USER = "demo"
DEMO_PASS = "demo123456"


def _month_days(today: date) -> list[date]:
    """A few dates within the current month for demo transactions."""
    days = [1, 3, 5, 7, 8, 10, 12, 14, 15, 18, 20, 22]
    out = []
    for d in days:
        try:
            out.append(today.replace(day=d))
        except ValueError:
            continue
    # ensure at least today
    if today not in out:
        out.append(today)
    return [d for d in out if d <= today]


def reset_user_data(user_id: int) -> None:
    Transaction.query.filter_by(user_id=user_id).delete()
    Reminder.query.filter_by(user_id=user_id).delete()
    Asset.query.filter_by(user_id=user_id).delete()
    from models import Setting

    Setting.query.filter_by(user_id=user_id).delete()
    db.session.commit()


def seed() -> None:
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=DEMO_USER).first()
        if user:
            reset_user_data(user.id)
            user.set_password(DEMO_PASS)
        else:
            user = User(username=DEMO_USER)
            user.set_password(DEMO_PASS)
            db.session.add(user)
            db.session.commit()
            seed_user_categories(user.id)

        db.session.commit()
        uid = user.id
        today = date.today()

        assets = [
            Asset(
                user_id=uid,
                name="微信",
                balance=Decimal("186.50"),
                kind="asset",
                note="日常零钱",
            ),
            Asset(
                user_id=uid,
                name="工行",
                balance=Decimal("5280.00"),
                kind="asset",
                note="工资卡",
            ),
            Asset(
                user_id=uid,
                name="花呗",
                balance=Decimal("707.69"),
                kind="liability",
                note="信用/负债账户",
                repay_due_day=10,
                repay_statement_day=1,
            ),
            Asset(
                user_id=uid,
                name="京东白条",
                balance=Decimal("412.58"),
                kind="liability",
                note="信用/负债账户",
                repay_due_day=27,
                repay_statement_day=18,
            ),
            Asset(
                user_id=uid,
                name="抖音月付",
                balance=Decimal("89.00"),
                kind="liability",
                note="信用/负债账户",
                repay_due_day=15,
                repay_statement_day=10,
            ),
        ]
        db.session.add_all(assets)
        db.session.flush()

        for a in assets:
            if a.kind == "liability" and a.repay_due_day:
                sync_liability_repay_reminder(
                    uid,
                    a.name,
                    due_day=a.repay_due_day,
                    statement_day=a.repay_statement_day,
                )

        days = _month_days(today)
        txns = [
            ("income", "8000.00", "工资", "七月工资", "", days[0] if days else today),
            ("expense", "28.00", "餐饮", "午饭·盖浇饭", "微信", days[min(1, len(days) - 1)]),
            ("expense", "15.50", "餐饮", "咖啡", "微信", days[min(2, len(days) - 1)]),
            ("expense", "46.00", "餐饮", "外卖", "花呗", days[min(3, len(days) - 1)]),
            ("expense", "120.00", "交通", "地铁月充", "工行", days[min(4, len(days) - 1)]),
            ("expense", "89.90", "购物", "日用品", "京东白条", days[min(5, len(days) - 1)]),
            ("expense", "35.00", "餐饮", "晚饭", "抖音月付", days[min(6, len(days) - 1)]),
            ("expense", "68.00", "购物", "零食", "花呗", days[min(7, len(days) - 1)]),
            ("expense", "22.00", "交通", "打车", "微信", days[min(8, len(days) - 1)]),
            ("expense", "199.00", "居住", "话费宽带", "工行", days[min(9, len(days) - 1)]),
            ("income", "200.00", "其他", "红包", "微信", days[min(10, len(days) - 1)]),
            ("expense", "56.00", "餐饮", "聚餐AA", "花呗", days[-1]),
        ]
        for t_type, amount, category, note, account, d in txns:
            db.session.add(
                Transaction(
                    user_id=uid,
                    type=t_type,
                    amount=Decimal(amount),
                    category=category,
                    note=note,
                    account=account,
                    date=d,
                )
            )

        # Extra one-off life reminders (monthly repay already synced)
        rent_day = min(25, 28)
        try:
            rent_date = today.replace(day=rent_day)
        except ValueError:
            rent_date = today + timedelta(days=5)
        if rent_date < today:
            # next month rough
            if today.month == 12:
                rent_date = date(today.year + 1, 1, rent_day)
            else:
                rent_date = date(today.year, today.month + 1, rent_day)
        db.session.add(
            Reminder(
                user_id=uid,
                title="交房租",
                due_at=datetime.combine(rent_date, datetime.min.time().replace(hour=10)),
                type="bill",
                note="房东微信转账",
                recurrence="monthly",
                linked_asset_name="",
            )
        )
        db.session.add(
            Reminder(
                user_id=uid,
                title="记得买牛奶",
                due_at=datetime.now() + timedelta(days=1),
                type="life",
                note="演示用生活提醒",
                recurrence="none",
            )
        )

        set_persona(uid, "butler")
        db.session.commit()

        n_txn = Transaction.query.filter_by(user_id=uid).count()
        n_asset = Asset.query.filter_by(user_id=uid).count()
        n_rem = Reminder.query.filter_by(user_id=uid).count()
        print(
            f"OK demo user ready: {DEMO_USER} / {DEMO_PASS} "
            f"(assets={n_asset}, txns={n_txn}, reminders={n_rem})"
        )


if __name__ == "__main__":
    seed()
