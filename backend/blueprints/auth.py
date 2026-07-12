from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from extensions import db
from models import User
from errors import ApiError

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
me_bp = Blueprint("me", __name__, url_prefix="/api")


def _get_credentials():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    return username, password


@auth_bp.post("/register")
def register():
    username, password = _get_credentials()
    if not username or len(username) > 64:
        raise ApiError("invalid_username", "用户名不能为空且不超过64位", 400, "username")
    if len(password) < 6 or len(password) > 128:
        raise ApiError("invalid_password", "密码长度需为 6-128 位", 400, "password")
    if User.query.filter_by(username=username).first():
        raise ApiError("username_taken", "用户名已存在", 409, "username")
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@auth_bp.post("/login")
def login():
    username, password = _get_credentials()
    if not username or not password:
        raise ApiError("invalid_input", "用户名和密码不能为空", 400)
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        raise ApiError("invalid_credentials", "用户名或密码错误", 401)
    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200


@me_bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        raise ApiError("not_found", "用户不存在", 404)
    return jsonify(user.to_dict()), 200
