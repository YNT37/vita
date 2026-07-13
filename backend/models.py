from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {"id": self.id, "username": self.username}


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    kind = db.Column(db.String(16), nullable=False)  # expense / income

    def to_dict(self):
        return {"id": self.id, "name": self.name, "kind": self.kind}


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(16), nullable=False)  # income / expense
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    note = db.Column(db.String(200), default="")
    date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "amount": float(self.amount),
            "category": self.category,
            "note": self.note or "",
            "date": self.date.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Reminder(db.Model):
    __tablename__ = "reminders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    due_at = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.String(16), default="life")  # bill / life / anniversary
    done = db.Column(db.Boolean, default=False)
    note = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "type": self.type,
            "done": self.done,
            "note": self.note or "",
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)  # user / assistant
    content = db.Column(db.Text, nullable=False)
    persona = db.Column(db.String(16), default="butler")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "persona": self.persona,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Setting(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    key = db.Column(db.String(32), nullable=False)
    value = db.Column(db.String(255), default="")

    def to_dict(self):
        return {"key": self.key, "value": self.value}


class Asset(db.Model):
    """用户资产余额快照（基金、余额宝等）。"""
    __tablename__ = "assets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(32), nullable=False)
    balance = db.Column(db.Numeric(14, 2), nullable=False)
    note = db.Column(db.String(200), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "balance": float(self.balance),
            "note": self.note or "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
