from flask import Blueprint, request, jsonify

from flask_jwt_extended import jwt_required, get_jwt_identity

from errors import ApiError
from services.prompts import PERSONA_OPTIONS
from services.user_settings import (
    AI_PROVIDERS,
    AI_PROVIDER_DEFAULTS,
    get_persona,
    set_persona,
    set_user_ai_provider,
    set_user_ai_api_key,
    set_user_ai_base_url,
    set_user_ai_model,
    mask_api_key,
    resolve_ai_config,
)

settings_bp = Blueprint("settings", __name__, url_prefix="/api")


def _uid():
    return int(get_jwt_identity())


def _settings_payload(user_id: int):
    cfg = resolve_ai_config(user_id)
    provider = cfg["provider"]
    defaults = AI_PROVIDER_DEFAULTS[provider]
    return {
        "persona": get_persona(user_id),
        "persona_options": list(PERSONA_OPTIONS),
        "ai_provider": provider,
        "ai_provider_options": list(AI_PROVIDERS),
        "ai_configured": cfg["configured"],
        "ai_api_key_set": bool(cfg["api_key"]),
        "ai_api_key_source": cfg["api_key_source"],
        "ai_api_key_hint": mask_api_key(cfg["api_key"]) if cfg["api_key"] else None,
        "ai_base_url": cfg["base_url"] or defaults["base_url"],
        "ai_base_url_source": cfg["base_url_source"],
        "ai_model": cfg["model"] or defaults["model"],
        "ai_model_source": cfg["model_source"],
    }


def _validate_base_url(url: str):
    if not url.startswith(("http://", "https://")):
        raise ApiError("invalid_base_url", "Base URL 需以 http:// 或 https:// 开头", 400, "ai_base_url")
    if len(url) > 200:
        raise ApiError("invalid_base_url", "Base URL 过长", 400, "ai_base_url")


@settings_bp.get("/settings")
@jwt_required()
def get_settings():
    return jsonify(_settings_payload(_uid())), 200


@settings_bp.post("/settings")
@jwt_required()
def update_settings():
    data = request.get_json(silent=True) or {}
    uid = _uid()

    if "persona" in data:
        persona = (data.get("persona") or "").strip()
        if persona not in PERSONA_OPTIONS:
            raise ApiError("invalid_persona", "未知角色，可选 butler/servant/sassy/lover", 400, "persona")
        set_persona(uid, persona)

    if "ai_provider" in data:
        raw = data.get("ai_provider")
        if raw is not None and not isinstance(raw, str):
            raise ApiError("invalid_provider", "接口类型格式无效", 400, "ai_provider")
        provider = (raw or "").strip().lower()
        if provider and provider not in AI_PROVIDERS:
            raise ApiError("invalid_provider", "接口类型仅支持 openai / anthropic", 400, "ai_provider")
        set_user_ai_provider(uid, provider if provider else None)

    if "ai_api_key" in data:
        raw = data.get("ai_api_key")
        if raw is not None and not isinstance(raw, str):
            raise ApiError("invalid_api_key", "API Key 格式无效", 400, "ai_api_key")
        key = (raw or "").strip()
        if key and len(key) < 8:
            raise ApiError("invalid_api_key", "API Key 过短", 400, "ai_api_key")
        set_user_ai_api_key(uid, key if key else None)

    if "ai_base_url" in data:
        raw = data.get("ai_base_url")
        if raw is not None and not isinstance(raw, str):
            raise ApiError("invalid_base_url", "Base URL 格式无效", 400, "ai_base_url")
        url = (raw or "").strip().rstrip("/")
        if url:
            _validate_base_url(url)
            set_user_ai_base_url(uid, url)
        else:
            set_user_ai_base_url(uid, None)

    if "ai_model" in data:
        raw = data.get("ai_model")
        if raw is not None and not isinstance(raw, str):
            raise ApiError("invalid_model", "模型名格式无效", 400, "ai_model")
        model = (raw or "").strip()
        if model and len(model) > 64:
            raise ApiError("invalid_model", "模型名过长", 400, "ai_model")
        set_user_ai_model(uid, model if model else None)

    return jsonify(_settings_payload(uid)), 200
