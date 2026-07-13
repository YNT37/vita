"""用户设置读写（persona、AI 接口配置）。"""



from flask import current_app



from extensions import db

from models import Setting

from services.prompts import PERSONA_OPTIONS



PERSONA_KEY = "persona"

AI_PROVIDER = "ai_provider"

AI_API_KEY = "ai_api_key"

AI_BASE_URL = "ai_base_url"

AI_MODEL = "ai_model"



AI_PROVIDERS = ("openai", "anthropic")

AI_PROVIDER_DEFAULTS = {

    "openai": {

        "base_url": "https://api.openai.com/v1",

        "model": "gpt-4o-mini",

    },

    "anthropic": {

        "base_url": "",

        "model": "claude-3-5-haiku-latest",

    },

}



# 兼容旧版 DeepSeek 专用字段名

_LEGACY_API_KEY = "deepseek_api_key"





def _get_setting(user_id: int, key: str) -> str | None:

    row = Setting.query.filter_by(user_id=user_id, key=key).first()

    if row and row.value.strip():

        return row.value.strip()

    return None





def _set_setting(user_id: int, key: str, value: str | None) -> None:

    text = (value or "").strip()

    row = Setting.query.filter_by(user_id=user_id, key=key).first()

    if not text:

        if row:

            db.session.delete(row)

        return

    if row:

        row.value = text

    else:

        db.session.add(Setting(user_id=user_id, key=key, value=text))





def _normalize_provider(provider: str | None) -> str:

    p = (provider or "openai").strip().lower()

    return p if p in AI_PROVIDERS else "openai"





def get_persona(user_id: int) -> str:

    row = Setting.query.filter_by(user_id=user_id, key=PERSONA_KEY).first()

    if row and row.value in PERSONA_OPTIONS:

        return row.value

    return "butler"





def set_persona(user_id: int, persona: str) -> None:

    _set_setting(user_id, PERSONA_KEY, persona)

    db.session.commit()





def get_user_ai_provider(user_id: int) -> str | None:

    raw = _get_setting(user_id, AI_PROVIDER)

    if raw and raw in AI_PROVIDERS:

        return raw

    return None





def get_user_ai_api_key(user_id: int) -> str | None:

    return _get_setting(user_id, AI_API_KEY) or _get_setting(user_id, _LEGACY_API_KEY)





def get_user_ai_base_url(user_id: int) -> str | None:

    return _get_setting(user_id, AI_BASE_URL)





def get_user_ai_model(user_id: int) -> str | None:

    return _get_setting(user_id, AI_MODEL)





def set_user_ai_provider(user_id: int, provider: str | None) -> None:

    if provider and provider in AI_PROVIDERS:

        _set_setting(user_id, AI_PROVIDER, provider)

    else:

        _set_setting(user_id, AI_PROVIDER, None)

    db.session.commit()





def set_user_ai_api_key(user_id: int, api_key: str | None) -> None:

    _set_setting(user_id, AI_API_KEY, api_key)

    legacy = Setting.query.filter_by(user_id=user_id, key=_LEGACY_API_KEY).first()

    if legacy:

        db.session.delete(legacy)

    db.session.commit()





def set_user_ai_base_url(user_id: int, base_url: str | None) -> None:

    _set_setting(user_id, AI_BASE_URL, base_url)

    db.session.commit()





def set_user_ai_model(user_id: int, model: str | None) -> None:

    _set_setting(user_id, AI_MODEL, model)

    db.session.commit()





def mask_api_key(api_key: str | None) -> str | None:

    if not api_key:

        return None

    if len(api_key) <= 8:

        return "****"

    return f"{api_key[:3]}...{api_key[-4:]}"





def _is_configured(provider: str, api_key: str | None, base_url: str | None, model: str | None) -> bool:

    if not api_key or not model:

        return False

    if provider == "anthropic":

        return True

    return bool(base_url)





def resolve_ai_config(user_id: int) -> dict:

    """合并用户设置与环境变量，得到最终 AI 调用参数。"""

    user_provider = get_user_ai_provider(user_id)

    user_key = get_user_ai_api_key(user_id)

    user_base = get_user_ai_base_url(user_id)

    user_model = get_user_ai_model(user_id)



    env_provider = _normalize_provider(current_app.config.get("AI_PROVIDER"))

    env_key = (current_app.config.get("AI_API_KEY") or "").strip()

    env_base = (current_app.config.get("AI_BASE_URL") or "").strip()

    env_model = (current_app.config.get("AI_MODEL") or "").strip()



    provider = _normalize_provider(user_provider or env_provider)

    defaults = AI_PROVIDER_DEFAULTS[provider]



    api_key = user_key or env_key

    base_url = user_base or env_base or defaults["base_url"]

    model = user_model or env_model or defaults["model"]



    def _source(user_val, env_val):

        if user_val:

            return "user"

        if env_val:

            return "env"

        return "none"



    return {

        "provider": provider,

        "api_key": api_key or None,

        "base_url": base_url or None,

        "model": model or None,

        "provider_source": _source(user_provider, env_provider),

        "api_key_source": _source(user_key, env_key),

        "base_url_source": _source(user_base, env_base),

        "model_source": _source(user_model, env_model),

        "configured": _is_configured(provider, api_key, base_url, model),

    }


WXPUSHER_UID = "wxpusher_uid"
SERVERCHAN_SENDKEY = "serverchan_sendkey"


def get_wxpusher_uid(user_id: int) -> str | None:
    return _get_setting(user_id, WXPUSHER_UID)


def set_wxpusher_uid(user_id: int, uid: str | None) -> None:
    text = (uid or "").strip()
    _set_setting(user_id, WXPUSHER_UID, text if text else None)
    db.session.commit()


def mask_wxpusher_uid(uid: str | None) -> str | None:
    if not uid:
        return None
    if len(uid) <= 8:
        return "****"
    return f"{uid[:4]}...{uid[-4:]}"


def get_serverchan_sendkey(user_id: int) -> str | None:
    return _get_setting(user_id, SERVERCHAN_SENDKEY)


def set_serverchan_sendkey(user_id: int, sendkey: str | None) -> None:
    text = (sendkey or "").strip()
    _set_setting(user_id, SERVERCHAN_SENDKEY, text if text else None)
    db.session.commit()


def mask_serverchan_sendkey(sendkey: str | None) -> str | None:
    if not sendkey:
        return None
    if len(sendkey) <= 8:
        return "****"
    return f"{sendkey[:4]}...{sendkey[-4:]}"

