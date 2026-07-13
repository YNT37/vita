from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from errors import ApiError
from services.category_service import (
    add_category,
    delete_category,
    list_categories,
    seed_user_categories,
    update_category,
)

categories_bp = Blueprint("categories", __name__, url_prefix="/api")


def _uid():
    return int(get_jwt_identity())


@categories_bp.get("/categories")
@jwt_required()
def get_categories():
    uid = _uid()
    seed_user_categories(uid)
    kind = (request.args.get("kind") or "").strip()
    if kind and kind not in ("expense", "income"):
        raise ApiError("invalid_kind", "kind 必须是 expense 或 income", 400, "kind")
    return jsonify(list_categories(uid, kind or None)), 200


@categories_bp.post("/categories")
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    kind = (data.get("kind") or "").strip()
    if not name or len(name) > 32:
        raise ApiError("invalid_name", "分类名不能为空且不超过32位", 400, "name")
    if kind not in ("expense", "income"):
        raise ApiError("invalid_kind", "kind 必须是 expense 或 income", 400, "kind")
    try:
        row = add_category(_uid(), name, kind)
    except ValueError as e:
        raise ApiError("invalid_input", str(e), 400)
    return jsonify(row), 201


@categories_bp.patch("/categories/<int:category_id>")
@jwt_required()
def patch_category(category_id):
    data = request.get_json(silent=True) or {}
    name = data.get("name") if "name" in data else None
    kind = data.get("kind") if "kind" in data else None
    if name is None and kind is None:
        raise ApiError("invalid_input", "请提供 name 或 kind", 400)
    try:
        row = update_category(
            _uid(),
            category_id,
            name=str(name) if name is not None else None,
            kind=str(kind) if kind is not None else None,
        )
    except ValueError as e:
        raise ApiError("invalid_input", str(e), 400)
    if not row:
        raise ApiError("not_found", "分类不存在", 404)
    return jsonify(row), 200


@categories_bp.delete("/categories/<int:category_id>")
@jwt_required()
def remove_category(category_id):
    if not delete_category(_uid(), category_id):
        raise ApiError("not_found", "分类不存在", 404)
    return jsonify({"ok": True}), 200
