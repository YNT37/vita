"""LangChain AI 服务：OpenAI 兼容 + Anthropic，含降级兜底。"""

import json
import logging
import re
from datetime import date, datetime, timedelta

from flask import current_app

from services.prompts import (
    FALLBACK_BRIEF,
    FALLBACK_BRIEF_EMPTY,
    FALLBACK_CHAT,
    PERSONA_OPTIONS,
    SYSTEM_PROMPTS,
)
from services.user_settings import AI_PROVIDER_DEFAULTS

logger = logging.getLogger(__name__)

MAX_HISTORY = 6
MAX_CONTENT_LEN = 500
_LLM_CACHE: dict[str, object] = {}


def _normalize_provider(provider: str | None) -> str:
    p = (provider or "openai").strip().lower()
    return p if p in ("openai", "anthropic") else "openai"


def _resolve_api_key(user_api_key: str | None = None) -> str:
    if user_api_key and str(user_api_key).strip():
        return str(user_api_key).strip()
    return (current_app.config.get("AI_API_KEY") or "").strip()


def _resolve_base_url(provider: str, user_base_url: str | None = None) -> str:
    if user_base_url is not None and str(user_base_url).strip():
        return str(user_base_url).strip().rstrip("/")
    if provider == "anthropic":
        return ""
    env = (current_app.config.get("AI_BASE_URL") or "").strip()
    return env.rstrip("/") if env else AI_PROVIDER_DEFAULTS["openai"]["base_url"]


def _resolve_model(provider: str, user_model: str | None = None) -> str:
    if user_model and str(user_model).strip():
        return str(user_model).strip()
    env = (current_app.config.get("AI_MODEL") or "").strip()
    return env if env else AI_PROVIDER_DEFAULTS[provider]["model"]


def _llm_cache_key(provider: str, api_key: str, base_url: str, model: str) -> str:
    return f"{provider}|{base_url}|{model}|{api_key}"


def _valid_persona(persona):
    return persona if persona in PERSONA_OPTIONS else "butler"


def _truncate(text, limit=MAX_CONTENT_LEN):
    text = (text or "").strip()
    return text[:limit] if len(text) > limit else text


def _get_llm(
    provider: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
):
    """按 Provider + Key + Base URL + Model 惰性初始化 LLM。"""
    resolved_provider = _normalize_provider(provider)
    resolved_key = _resolve_api_key(api_key)
    resolved_base = _resolve_base_url(resolved_provider, base_url)
    resolved_model = _resolve_model(resolved_provider, model)
    if not resolved_key:
        return None
    cache_key = _llm_cache_key(resolved_provider, resolved_key, resolved_base, resolved_model)
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]
    try:
        if resolved_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            kwargs = {
                "model": resolved_model,
                "api_key": resolved_key,
                "temperature": 0.7,
                "timeout": 25,
                "max_retries": 1,
            }
            if resolved_base:
                kwargs["base_url"] = resolved_base
            llm = ChatAnthropic(**kwargs)
        else:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                base_url=resolved_base,
                api_key=resolved_key,
                model=resolved_model,
                temperature=0.7,
                timeout=25,
                max_retries=1,
            )
        _LLM_CACHE[cache_key] = llm
        return llm
    except Exception as e:
        logger.warning("LLM init failed: %s", e)
        return None


def _invoke_llm(
    system: str,
    user: str,
    provider: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str | None:
    llm = _get_llm(provider, api_key, base_url, model)
    if not llm:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        content = getattr(resp, "content", None) or str(resp)
        return _truncate(content, 800)
    except Exception as e:
        logger.warning("LLM invoke failed: %s", e)
        return None


def _ai_params(ai_config: dict | None = None):
    cfg = ai_config or {}
    provider = _normalize_provider(cfg.get("provider"))
    return provider, cfg.get("api_key"), cfg.get("base_url"), cfg.get("model")


def generate_chat_reply(
    persona: str,
    message: str,
    history: list | None = None,
    ai_config: dict | None = None,
) -> str:
    persona = _valid_persona(persona)
    message = _truncate(message)
    if not message:
        return FALLBACK_CHAT[persona]

    system = SYSTEM_PROMPTS[persona]
    hist = (history or [])[-MAX_HISTORY:]
    parts = []
    for h in hist:
        role = h.get("role", "")
        content = _truncate(h.get("content", ""))
        if content:
            parts.append(f"{role}: {content}")
    parts.append(f"user: {message}")
    user_prompt = "以下是对话历史（最近几轮）与当前用户消息，请以角色语气回复：\n" + "\n".join(parts)

    provider, key, base, model = _ai_params(ai_config)
    reply = _invoke_llm(system, user_prompt, provider, key, base, model)
    return reply or FALLBACK_CHAT[persona]


def generate_brief(
    persona: str, context: dict | None = None, ai_config: dict | None = None
) -> str:
    persona = _valid_persona(persona)
    ctx = context or {}
    txns = ctx.get("transactions_today") or []
    reminders = ctx.get("reminders_today") or []
    expense_total = ctx.get("expense_total", 0)
    income_total = ctx.get("income_total", 0)

    if not txns and not reminders:
        return FALLBACK_BRIEF_EMPTY[persona]

    summary_lines = [
        f"今日支出合计：{expense_total} 元",
        f"今日收入合计：{income_total} 元",
        f"今日交易笔数：{len(txns)}",
        f"今日待办/提醒：{len(reminders)} 条",
    ]
    for r in reminders[:5]:
        summary_lines.append(f"- 提醒：{r.get('title', '')}（{r.get('due_at', '')}）")
    for t in txns[:5]:
        summary_lines.append(
            f"- {t.get('type', '')} {t.get('amount', '')} {t.get('category', '')} {t.get('note', '')}"
        )

    system = SYSTEM_PROMPTS[persona] + " 请根据以下今日数据，用角色语气写一段 100 字以内的每日播报。"
    user_prompt = "\n".join(summary_lines)
    provider, key, base, model = _ai_params(ai_config)
    reply = _invoke_llm(system, user_prompt, provider, key, base, model)
    return reply or FALLBACK_BRIEF[persona]


def _regex_parse(text: str) -> dict:
    """正则兜底：简单句式解析为 transaction 或 reminder。"""
    text = text.strip()
    today = date.today().isoformat()

    if re.search(r"提醒|记得|别忘了|还|到期", text):
        due = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")
        if "今天" in text or "今日" in text:
            due = datetime.now().strftime("%Y-%m-%dT18:00")
        title = re.sub(r"提醒我|记得|别忘了", "", text).strip() or text
        return {
            "intent": "reminder",
            "data": {
                "title": title[:120],
                "due_at": due,
                "type": "bill" if re.search(r"花呗|账单|还款|房租", text) else "life",
                "note": "",
            },
        }

    m = re.search(r"(\d+(?:\.\d{1,2})?)", text)
    if m:
        amount = float(m.group(1))
        if amount > 0:
            category = "餐饮"
            if re.search(r"交通|地铁|打车|公交", text):
                category = "交通"
            elif re.search(r"工资|收入|奖金", text):
                return {
                    "intent": "transaction",
                    "data": {
                        "type": "income",
                        "amount": amount,
                        "category": "工资",
                        "note": text[:200],
                        "date": today,
                    },
                }
            return {
                "intent": "transaction",
                "data": {
                    "type": "expense",
                    "amount": amount,
                    "category": category,
                    "note": text[:200],
                    "date": today,
                },
            }

    return {"intent": "unknown", "data": {}}


def _llm_parse(text: str, ai_config: dict | None = None) -> dict | None:
    system = (
        "你是记账助手。把用户输入解析为 JSON，仅输出 JSON，不要 markdown。"
        '格式：{"intent":"transaction|reminder|unknown","data":{...}}。'
        "transaction 的 data 含 type(income/expense), amount(number), category, note, date(YYYY-MM-DD)。"
        "reminder 的 data 含 title, due_at(ISO), type(bill/life/anniversary), note。"
        "无法解析则 intent=unknown, data={}。"
    )
    provider, key, base, model = _ai_params(ai_config)
    raw = _invoke_llm(system, text, provider, key, base, model)
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
        intent = obj.get("intent", "unknown")
        if intent not in ("transaction", "reminder", "unknown"):
            intent = "unknown"
        return {"intent": intent, "data": obj.get("data") or {}}
    except json.JSONDecodeError:
        return None


def parse_input(text: str, ai_config: dict | None = None) -> dict:
    text = _truncate(text, 200)
    if not text:
        return {"intent": "unknown", "data": {}}

    result = _llm_parse(text, ai_config)
    if result and result.get("intent") != "unknown":
        return result
    regex_result = _regex_parse(text)
    if regex_result.get("intent") != "unknown":
        return regex_result
    return {"intent": "unknown", "data": {}}
