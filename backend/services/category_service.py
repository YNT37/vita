"""用户分类种子与读写。"""

from extensions import db
from models import UserCategory

DEFAULT_EXPENSE = ("餐饮", "交通", "购物", "居住", "娱乐", "医疗", "基金", "其他")
DEFAULT_INCOME = ("工资", "奖金", "理财", "其他")


def seed_user_categories(user_id: int) -> None:
    """为新用户写入默认分类（幂等）。"""
    existing = UserCategory.query.filter_by(user_id=user_id).count()
    if existing > 0:
        return
    for name in DEFAULT_EXPENSE:
        db.session.add(UserCategory(user_id=user_id, name=name, kind="expense"))
    for name in DEFAULT_INCOME:
        db.session.add(UserCategory(user_id=user_id, name=name, kind="income"))
    db.session.commit()


def list_categories(user_id: int, kind: str | None = None) -> list[dict]:
    q = UserCategory.query.filter_by(user_id=user_id)
    if kind in ("expense", "income"):
        q = q.filter_by(kind=kind)
    rows = q.order_by(UserCategory.kind.asc(), UserCategory.id.asc()).all()
    return [r.to_dict() for r in rows]


def grouped_categories(user_id: int) -> dict:
    rows = list_categories(user_id)
    return {
        "expense": [r["name"] for r in rows if r["kind"] == "expense"],
        "income": [r["name"] for r in rows if r["kind"] == "income"],
    }


def add_category(user_id: int, name: str, kind: str) -> dict:
    name = name.strip()[:32]
    if not name:
        raise ValueError("empty name")
    if kind not in ("expense", "income"):
        raise ValueError("invalid kind")
    dup = UserCategory.query.filter_by(user_id=user_id, name=name, kind=kind).first()
    if dup:
        return dup.to_dict()
    row = UserCategory(user_id=user_id, name=name, kind=kind)
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def delete_category(user_id: int, category_id: int) -> bool:
    row = UserCategory.query.filter_by(id=category_id, user_id=user_id).first()
    if not row:
        return False
    db.session.delete(row)
    db.session.commit()
    return True
