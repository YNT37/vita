"""LangChain AI 服务：OpenAI 兼容 + Anthropic，含降级兜底。"""
import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from flask import current_app
from extensions import db
from models import Asset, Reminder, Transaction
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
MAX_CONTENT_LEN = 1000
_LLM_CACHE: dict[str, object] = {}
ACTIONABLE_INTENTS = ("transaction", "balance", "reminder", "batch")
UNDERSTAND_INTENTS = ("chat", "query", "transaction", "balance", "reminder", "batch", "unknown")
LIABILITY_KEYWORDS = ("花呗", "白条", "借呗", "信用卡", "负债", "欠款", "贷款")
ASSET_KEYWORDS = (
    "基金", "余额宝", "股票", "银行卡", "储蓄卡", "现金", "理财", "债券",
    "外汇", "微信", "支付宝", "建行", "工行", "招行", "农行", "中行", "交行",
    "花呗", "白条", "信用卡",
)
UNDERSTAND_SYSTEM = """你是 Vita 生活管家的意图理解模块。根据用户消息和已有数据，只输出 JSON，不要 markdown。

格式（单条）：
{"intent":"chat|query|transaction|balance|reminder|batch|unknown","should_act":bool,"data":{},"actions":[],"summary":"一句话"}

当用户一次汇报多个账户/多笔账单时，必须用 intent=batch，并在 actions 里列出每一项：
{"intent":"batch","should_act":true,"actions":[{"intent":"balance","data":{...}},{"intent":"reminder","data":{...}}],"summary":"..."}

意图：
- chat：闲聊，不涉及记账写入
- query：询问已有数据（只读）。若【用户当前数据】为空，不要臆造数字
- transaction：单笔收入/支出
- balance：单个资产账户余额（基金/微信/建行/工行等）
- reminder：单个提醒（含花呗/白条还款日）
- batch：一次多账户或多笔提醒/记账
- unknown：无法理解

should_act：用户明确汇报账户余额、欠款、记账、要求记下 → true；只是询问 → false。

data：
- balance: {name, balance(number), note?}
- transaction: {type income|expense, amount, category, note?, date?}
- reminder: {title, due_at ISO, type bill|life|anniversary, note?}
- query: {topic assets|expense|income|reminders|overview}

示例：
用户：「基金1901.74，微信57.6，建行270.29，工行151.16；花呗707.69七月25日还，京东白条412.58分两期每期206.29二十七日还」
→ batch，4 个 balance + 2 个 reminder(bill)
"""

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

def _strip_json(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()
def _normalize_finance_text(text: str) -> str:
    """统一口语账户名，便于规则提取。"""
    text = text or ""
    text = text.replace("欠款", "欠")
    replacements = (
        (r"建设银行(?:卡|储蓄卡|借记卡)?", "建行"),
        (r"建行(?:卡|储蓄卡|借记卡)", "建行"),
        (r"工商银行(?:卡|储蓄卡|借记卡)?", "工行"),
        (r"工行(?:卡|储蓄卡|借记卡)", "工行"),
        (r"招商银行(?:卡)?", "招行"),
        (r"农业银行(?:卡)?", "农行"),
        (r"中国银行(?:卡)?", "中行"),
        (r"交通银行(?:卡)?", "交行"),
        (r"京东白条", "京东白条"),
    )
    for pat, name in replacements:
        text = re.sub(pat, name, text)
    return text

def _extract_asset_name(text: str) -> str:
    text = _normalize_finance_text(text)
    for kw in ASSET_KEYWORDS:
        if kw in text:
            return kw
    m = re.search(r"([\u4e00-\u9fa5]{2,8})(?:的)?(?:余额|结余|账户)", text)
    if m:
        return m.group(1)
    m = re.search(r"([\u4e00-\u9fa5]{2,8})(?:余额|结余)", text)
    if m:
        return m.group(1)
    return "资产"

def _is_liability_name(name: str) -> bool:
    return any(k in (name or "") for k in LIABILITY_KEYWORDS)

def _parse_cn_due(text: str, default_hour: int = 10) -> str:
    """把「7月25日」「7.25」「25号还」等解析为今年 ISO 时间。"""
    now = datetime.now()
    year = now.year
    m = re.search(r"(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})[日号]?", text)
    if m:
        y = int(m.group(1) or year)
        month, day = int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, month, day, default_hour, 0).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            pass
    m = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                due = datetime(year, month, day, default_hour, 0)
                if due.date() < now.date() and month < now.month:
                    due = datetime(year + 1, month, day, default_hour, 0)
                return due.strftime("%Y-%m-%dT%H:%M")
            except ValueError:
                pass
    m = re.search(r"(?:每个月|每月|每月的)?\s*(\d{1,2})[日号]", text)
    if m:
        day = int(m.group(1))
        month = now.month
        try:
            due = datetime(year, month, day, default_hour, 0)
            if due.date() < now.date():
                if month == 12:
                    due = datetime(year + 1, 1, day, default_hour, 0)
                else:
                    due = datetime(year, month + 1, day, default_hour, 0)
            return due.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            pass
    return (now + timedelta(days=1)).strftime("%Y-%m-%dT10:00")

def _looks_like_balance(text: str) -> bool:
    if re.search(r"多少|多少钱|什么情况|怎么样|查看|查询", text) and not re.search(
        r"余额为|余额是|还有\d|剩\d|记一下|同步|录入", text
    ):
        return False
    return bool(
        re.search(
            r"余额|结余|还剩|剩了|剩下|账户|资产|基金|微信|支付宝|建行|工行|招行|"
            r"银行|花呗|白条|更新了|查了下|看了看|刚看|整理|汇报|记一下|同步|录入",
            text,
        )
    )

def _looks_like_finance_report(text: str) -> bool:
    """是否像一次汇报多账户/多负债。"""
    text = _normalize_finance_text(text)
    money_hits = re.findall(r"\d+(?:\.\d{1,2})?", text)
    name_hits = sum(1 for kw in ASSET_KEYWORDS if kw in text)
    if "银行" in text:
        name_hits += 1
    return len(money_hits) >= 2 and name_hits >= 2

def _looks_like_sync_request(text: str) -> bool:
    return bool(
        re.search(
            r"同步|重新录入|重新记|需要|记下来|写入|帮我记|录入|补上|记入|再记|保存资产|记录账户",
            text or "",
        )
    )

def _regex_extract_batch(text: str) -> list[dict]:
    """规则提取多账户余额 + 负债还款提醒。"""
    text = _normalize_finance_text(text)
    actions: list[dict] = []
    seen_assets: set[str] = set()

    # 花呗/白条 + 金额 → reminder + 负债账户
    debt_pat = re.compile(
        r"(花呗|京东白条|白条|借呗|信用卡)\s*(?:欠款|欠|待还|还)?\s*"
        r"(\d+(?:\.\d{1,2})?)\s*元?"
    )
    for m in debt_pat.finditer(text):
        name, amount_s = m.group(1), m.group(2)
        amount = float(amount_s)
        window = text[m.end() : m.end() + 56]
        cut = re.search(r"花呗|京东白条|白条|借呗|信用卡", window)
        if cut:
            window = window[: cut.start()]
        due = _parse_cn_due(window)
        installment = re.search(
            r"(?:每期|每个月还|每月还)\s*(\d+(?:\.\d{1,2})?)",
            window,
        )
        pay = float(installment.group(1)) if installment else amount
        title = f"还{name} {pay:g}元" if installment else f"还{name} {amount:g}元"
        actions.append(
            {
                "intent": "reminder",
                "data": {
                    "title": title[:120],
                    "due_at": due,
                    "type": "bill",
                    "note": f"总额{amount:g}" + (f"；{window.strip()}" if window.strip() else ""),
                },
            }
        )
        if name not in seen_assets:
            seen_assets.add(name)
            actions.append(
                {
                    "intent": "balance",
                    "data": {"name": name, "balance": amount, "note": "负债欠款"},
                }
            )

    # 账户名 + 金额
    asset_pat = re.compile(
        r"(基金|余额宝|股票|微信|支付宝|建行|工行|招行|农行|中行|交行|现金|理财|"
        r"银行卡|储蓄卡)"
        r"(?:的)?(?:余额|账户|卡)?"
        r"(?:为|是|剩|还有|：|:|)?\s*"
        r"(\d+(?:\.\d{1,2})?)\s*元?"
    )
    for m in asset_pat.finditer(text):
        name, amount_s = m.group(1), m.group(2)
        if _is_liability_name(name):
            continue
        if name in seen_assets:
            continue
        seen_assets.add(name)
        actions.append(
            {
                "intent": "balance",
                "data": {"name": name[:32], "balance": float(amount_s), "note": text[:200]},
            }
        )

    return actions

def _looks_like_record(text: str) -> bool:
    return bool(
        re.search(
            r"记|花了|付了|买了|消费|支出|收入|到账|工资|奖金|打车|午饭|早餐|晚餐|奶茶|咖啡",
            text,
        )
    )

def _looks_like_query(text: str) -> bool:
    if _looks_like_record(text) or _looks_like_balance(text):
        return False
    return bool(re.search(r"多少|多少钱|几块钱|有什么|有哪些|什么情况|怎么样|查看|查询|总共|概况", text))

def _query_topic(text: str) -> str:
    if re.search(r"基金|余额|资产|余额宝|股票|账户|钱", text):
        return "assets"
    if re.search(r"收入|工资|到账", text):
        return "income"
    if re.search(r"提醒|待办|要做什么|有什么事", text):
        return "reminders"
    if re.search(r"花了|支出|消费", text):
        return "expense"
    return "overview"

def format_user_context(context: dict | None) -> str:
    ctx = context or {}
    lines = ["【用户当前数据】"]
    cats = ctx.get("categories") or {}
    if cats:
        exp = "、".join(cats.get("expense") or []) or "无"
        inc = "、".join(cats.get("income") or []) or "无"
        lines.append(f"支出分类：{exp}")
        lines.append(f"收入分类：{inc}")
    assets = ctx.get("assets") or []
    assets_total = ctx.get("assets_total", 0)
    if assets:
        lines.append(f"资产账户（合计 {assets_total} 元）：")
        for a in assets[:12]:
            lines.append(f"- {a.get('name', '')}：{a.get('balance', 0)} 元")
    else:
        lines.append("资产账户：暂无记录")
    mstats = ctx.get("month_stats") or {}
    if mstats:
        lines.append(
            f"本月（{mstats.get('month', '')}）收入 {mstats.get('income', 0)} 元，"
            f"支出 {mstats.get('expense', 0)} 元，结余 {mstats.get('balance', 0)} 元"
        )
    expense = ctx.get("expense_total", 0)
    income = ctx.get("income_total", 0)
    lines.append(f"今日支出：{expense} 元；今日收入：{income} 元")
    txns = ctx.get("transactions_today") or []
    if txns:
        lines.append("今日交易：")
        for t in txns[:5]:
            lines.append(
                f"- {t.get('type', '')} {t.get('amount', '')} {t.get('category', '')} {t.get('note', '')}"
            )
    reminders = ctx.get("reminders_pending") or ctx.get("reminders_today") or []
    if reminders:
        lines.append("待办提醒：")
        for r in reminders[:8]:
            status = "已完成" if r.get("done") else "待办"
            lines.append(f"- [{status}] {r.get('title', '')}（{r.get('due_at', '')}）")
    return "\n".join(lines)

def answer_query(topic: str, context: dict | None) -> str:
    ctx = context or {}
    assets = ctx.get("assets") or []
    expense = ctx.get("expense_total", 0)
    income = ctx.get("income_total", 0)
    reminders = ctx.get("reminders_pending") or ctx.get("reminders_today") or []
    if topic == "assets":
        if not assets:
            return "您还没有记录任何资产余额，可以直接告诉我，比如「基金余额1901」。"
        parts = [f"{a.get('name', '')} {a.get('balance', 0)} 元" for a in assets[:8]]
        return "当前资产：" + "；".join(parts) + "。"
    if topic == "expense":
        m = ctx.get("month_stats") or {}
        return f"本月支出 {m.get('expense', expense)} 元，今日支出 {expense} 元。"
    if topic == "income":
        m = ctx.get("month_stats") or {}
        return f"本月收入 {m.get('income', income)} 元，今日收入 {income} 元。"
    if topic == "reminders":
        if not reminders:
            return "暂无待办提醒。"
        parts = [r.get("title", "") for r in reminders[:8]]
        return "待办提醒：" + "；".join(parts) + "。"
    total_assets = sum(float(a.get("balance", 0)) for a in assets)
    m = ctx.get("month_stats") or {}
    return (
        f"本月收入 {m.get('income', income)} 元，支出 {m.get('expense', expense)} 元；"
        f"资产合计约 {total_assets:.2f} 元；"
        f"待办 {len(reminders)} 条。"
    )

def _normalize_one_action(intent: str, data: dict, source_text: str) -> dict | None:
    intent = (intent or "").strip().lower()
    data = data or {}
    if intent == "balance":
        name = (data.get("name") or _extract_asset_name(source_text)).strip()[:32] or "资产"
        try:
            balance = float(data.get("balance", data.get("amount", 0)))
        except (TypeError, ValueError):
            return None
        if balance < 0:
            return None
        note = (data.get("note") or source_text)[:200]
        if _is_liability_name(name) and "负债" not in note:
            note = ("负债欠款；" + note).strip("；")[:200]
        return {
            "intent": "balance",
            "data": {"name": name, "balance": balance, "note": note},
        }
    if intent == "transaction":
        t_type = (data.get("type") or "expense").strip()
        if t_type not in ("income", "expense"):
            t_type = "expense"
        try:
            amount = float(data.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            return None
        return {
            "intent": "transaction",
            "data": {
                "type": t_type,
                "amount": amount,
                "category": (data.get("category") or "其他")[:32],
                "note": (data.get("note") or source_text)[:200],
                "date": (data.get("date") or date.today().isoformat())[:10],
            },
        }
    if intent == "reminder":
        title = (data.get("title") or source_text).strip()[:120]
        due_at = (data.get("due_at") or "").strip()
        if not due_at or not re.match(r"\d{4}-\d{2}-\d{2}", due_at):
            due_at = _parse_cn_due(source_text + " " + title)
        r_type = (data.get("type") or "life").strip()
        if r_type not in ("bill", "life", "anniversary"):
            r_type = "bill" if any(k in title for k in LIABILITY_KEYWORDS) else "life"
        return {
            "intent": "reminder",
            "data": {
                "title": title,
                "due_at": due_at,
                "type": r_type,
                "note": (data.get("note") or "")[:200],
            },
        }
    return None

def _normalize_understanding(obj: dict, source_text: str) -> dict:
    intent = (obj.get("intent") or "unknown").strip().lower()
    if intent not in UNDERSTAND_INTENTS:
        intent = "unknown"
    summary = (obj.get("summary") or "").strip()
    raw_actions = obj.get("actions") if isinstance(obj.get("actions"), list) else []

    actions: list[dict] = []
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        one = _normalize_one_action(item.get("intent", ""), item.get("data") or {}, source_text)
        if one:
            actions.append(one)

    if intent == "batch" or (len(actions) >= 2):
        if not actions:
            actions = _regex_extract_batch(source_text)
        return {
            "intent": "batch",
            "should_act": bool(actions),
            "data": {},
            "actions": actions,
            "summary": summary or f"批量写入 {len(actions)} 项",
        }

    if intent in ("balance", "transaction", "reminder"):
        one = _normalize_one_action(intent, obj.get("data") or {}, source_text)
        if not one:
            return {"intent": "unknown", "should_act": False, "data": {}, "actions": [], "summary": summary}
        should_act = bool(obj.get("should_act", True))
        return {
            "intent": one["intent"],
            "should_act": should_act,
            "data": one["data"],
            "actions": [one] if should_act else [],
            "summary": summary,
        }

    if intent == "query":
        topic = ((obj.get("data") or {}).get("topic") or _query_topic(source_text)).strip()
        if topic not in ("assets", "expense", "income", "reminders", "overview"):
            topic = "overview"
        return {
            "intent": "query",
            "should_act": False,
            "data": {"topic": topic},
            "actions": [],
            "summary": summary,
        }

    return {
        "intent": intent if intent in ("chat", "unknown") else "unknown",
        "should_act": False,
        "data": {},
        "actions": [],
        "summary": summary,
    }

def _llm_understand(message: str, context: dict | None, ai_config: dict | None) -> dict | None:
    provider, key, base, model = _ai_params(ai_config)
    user_prompt = format_user_context(context) + f"\n\n用户消息：{message}"
    raw = _invoke_llm(UNDERSTAND_SYSTEM, user_prompt, provider, key, base, model)
    if not raw:
        return None
    try:
        obj = json.loads(_strip_json(raw))
        return _normalize_understanding(obj, message)
    except json.JSONDecodeError:
        return None

def _fallback_understand(message: str, context: dict | None) -> dict:
    if _looks_like_finance_report(message) or (
        _looks_like_balance(message) and len(re.findall(r"\d+(?:\.\d{1,2})?", message)) >= 2
    ):
        actions = _regex_extract_batch(message)
        if actions:
            return {
                "intent": "batch",
                "should_act": True,
                "data": {},
                "actions": actions,
                "summary": f"规则识别批量写入 {len(actions)} 项",
            }
    if _looks_like_query(message) and not _looks_like_finance_report(message):
        topic = _query_topic(message)
        return {
            "intent": "query",
            "should_act": False,
            "data": {"topic": topic},
            "actions": [],
            "summary": f"查询{topic}",
        }
    parsed = _regex_parse(message)
    if parsed.get("intent") in ("transaction", "balance", "reminder"):
        one = {
            "intent": parsed["intent"],
            "data": parsed.get("data") or {},
        }
        return {
            "intent": parsed["intent"],
            "should_act": True,
            "data": parsed.get("data") or {},
            "actions": [one],
            "summary": f"识别为{parsed['intent']}",
        }
    return {"intent": "chat", "should_act": False, "data": {}, "actions": [], "summary": ""}

def understand_message(
    message: str,
    context: dict | None = None,
    ai_config: dict | None = None,
    history_text: str | None = None,
) -> dict:
    """统一意图理解：LLM 优先，规则兜底；多账户汇报强制批量写入。"""
    message = _truncate(message, MAX_CONTENT_LEN)
    if not message:
        return {"intent": "unknown", "should_act": False, "data": {}, "actions": [], "summary": ""}

    # 「同步/需要/记下来」但没带数字 → 从近期对话找回财务明细再写入
    source = message
    if _looks_like_sync_request(message) and not _looks_like_finance_report(message):
        hist = (history_text or "").strip()
        if hist and _looks_like_finance_report(hist):
            source = hist
        elif hist:
            # 拼最近用户话，尽量捞出含金额的句子
            money_lines = [
                ln for ln in hist.splitlines()
                if re.search(r"\d+(?:\.\d{1,2})?", ln) and re.search(r"基金|微信|银行|花呗|白条|资产", ln)
            ]
            if money_lines:
                source = "\n".join(money_lines[-3:])

    # 多账户汇报：规则优先，避免 LLM 只闲聊不落库
    if _looks_like_finance_report(source):
        actions = _regex_extract_batch(source)
        if len(actions) >= 2:
            return {
                "intent": "batch",
                "should_act": True,
                "data": {},
                "actions": actions,
                "summary": f"批量记录 {len(actions)} 项财务信息",
            }

    result = _llm_understand(message, context, ai_config)
    if result and result.get("intent") != "unknown":
        if result["intent"] in ("chat", "query") and (
            _looks_like_balance(source) or _looks_like_finance_report(source)
        ):
            actions = _regex_extract_batch(source)
            if actions:
                return {
                    "intent": "batch" if len(actions) > 1 else actions[0]["intent"],
                    "should_act": True,
                    "data": {} if len(actions) > 1 else actions[0]["data"],
                    "actions": actions,
                    "summary": "纠正为财务写入",
                }
        return result
    return _fallback_understand(source, context)

def execute_intent(user_id: int, understanding: dict) -> str | None:
    actions = understanding.get("actions") or []
    if understanding.get("should_act") and not actions:
        intent = understanding.get("intent")
        data = understanding.get("data") or {}
        if intent in ("balance", "transaction", "reminder"):
            actions = [{"intent": intent, "data": data}]
    if not actions:
        return None

    notes: list[str] = []
    for item in actions:
        intent = item.get("intent")
        data = item.get("data") or {}
        try:
            if intent == "balance":
                notes.append(apply_balance_update(user_id, data))
            elif intent == "transaction":
                notes.append(apply_transaction(user_id, data))
            elif intent == "reminder":
                notes.append(apply_reminder(user_id, data))
        except Exception as e:
            logger.warning("execute_intent item failed: %s", e)
    if not notes:
        return None
    # 合并说明，避免过长
    if len(notes) <= 3:
        return "；".join(notes)
    return f"已写入 {len(notes)} 项：" + "；".join(notes[:4]) + ("…" if len(notes) > 4 else "")

def generate_chat_reply(
    persona: str,
    message: str,
    history: list | None = None,
    ai_config: dict | None = None,
    context: dict | None = None,
    understanding: dict | None = None,
    action_note: str | None = None,
    query_answer: str | None = None,
) -> str:
    persona = _valid_persona(persona)
    message = _truncate(message)
    if not message:
        return FALLBACK_CHAT[persona]
    system = SYSTEM_PROMPTS[persona]
    hist = (history or [])[-MAX_HISTORY:]
    parts = [format_user_context(context)]
    if understanding and understanding.get("summary"):
        parts.append(f"【意图理解】{understanding['summary']}")
    if query_answer:
        parts.append(f"【查询结果】{query_answer}")
    if action_note:
        parts.append(f"【系统已执行】{action_note}")
    else:
        parts.append("【系统已执行】无（本次未写入数据库）")
    for h in hist:
        role = h.get("role", "")
        content = _truncate(h.get("content", ""))
        if content:
            parts.append(f"{role}: {content}")
    parts.append(f"user: {message}")
    user_prompt = (
        "以下是对话历史、用户数据与当前消息。请用角色语气自然回复。\n"
        "硬性规则：涉及金额/账户/待办时，只能依据【用户当前数据】与【系统已执行】；"
        "禁止把聊天记录里未入库的数字当成已保存数据复述；"
        "若数据为空且未执行写入，请明确说「尚未记入系统」，并引导用户再说一遍账户明细。\n"
        + "\n".join(parts)
    )
    provider, key, base, model = _ai_params(ai_config)
    reply = _invoke_llm(system, user_prompt, provider, key, base, model)
    if reply:
        return reply
    if query_answer:
        return query_answer
    if action_note:
        ack = {
            "butler": f"好的，{action_note}。可在统计页查看。",
            "servant": f"主子放心，{action_note}，奴才已记入账册，统计页可查。",
            "sassy": f"行，{action_note}，统计页自己去看，别再问我记没记。",
            "lover": f"嗯嗯，{action_note}，统计页也能看到哦。",
        }
        return ack.get(persona, action_note)
    return FALLBACK_CHAT[persona]

def generate_brief(
    persona: str, context: dict | None = None, ai_config: dict | None = None
) -> str:
    persona = _valid_persona(persona)
    ctx = context or {}
    txns = ctx.get("transactions_today") or []
    reminders = ctx.get("reminders_today") or []
    expense_total = ctx.get("expense_total", 0)
    income_total = ctx.get("income_total", 0)
    if not txns and not reminders and not ctx.get("assets"):
        return FALLBACK_BRIEF_EMPTY[persona]
    summary_lines = [
        f"今日支出合计：{expense_total} 元",
        f"今日收入合计：{income_total} 元",
        f"今日交易笔数：{len(txns)}",
        f"今日待办/提醒：{len(reminders)} 条",
    ]
    assets = ctx.get("assets") or []
    if assets:
        summary_lines.append(f"资产账户：{len(assets)} 个")
        for a in assets[:5]:
            summary_lines.append(f"- {a.get('name', '')} 余额 {a.get('balance', 0)} 元")
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

def _regex_parse_balance(text: str) -> dict | None:
    if not _looks_like_balance(text):
        return None
    m = (
        re.search(r"(?:余额|结余|还有|剩(?:了|下)?)(?:为|是|约|大概)?\s*(\d+(?:\.\d{1,2})?)", text)
        or re.search(r"(\d+(?:\.\d{1,2})?)\s*元?\s*(?:的)?(?:余额|结余)", text)
        or re.search(r"(\d+(?:\.\d{1,2})?)", text)
    )
    if not m:
        return None
    amount = float(m.group(1))
    if amount < 0:
        return None
    return {
        "intent": "balance",
        "data": {"name": _extract_asset_name(text), "balance": amount, "note": text[:200]},
    }

def _regex_parse(text: str) -> dict:
    text = text.strip()
    today = date.today().isoformat()
    balance = _regex_parse_balance(text)
    if balance:
        return balance
    if re.search(r"提醒|记得|别忘了|到期", text) and not re.search(r"多少|多少钱", text):
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
    if m and _looks_like_record(text):
        amount = float(m.group(1))
        if amount > 0:
            category = "餐饮"
            if re.search(r"交通|地铁|打车|公交", text):
                category = "交通"
            elif re.search(r"工资|收入|奖金|到账", text):
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
    understanding = _llm_understand(text, {}, ai_config)
    if not understanding:
        return None
    intent = understanding.get("intent")
    if intent == "batch":
        actions = understanding.get("actions") or []
        if not actions:
            return None
        # 一句话录入：返回第一项可写意图供确认；批量由聊天处理
        first = actions[0]
        return {"intent": first["intent"], "data": first.get("data") or {}, "actions": actions}
    if intent not in ("transaction", "balance", "reminder"):
        return None
    return {
        "intent": intent,
        "data": understanding.get("data") or {},
        "actions": understanding.get("actions") or [],
    }

def parse_input(text: str, ai_config: dict | None = None) -> dict:
    text = _truncate(text, 500)
    if not text:
        return {"intent": "unknown", "data": {}, "actions": []}
    if _looks_like_finance_report(text):
        actions = _regex_extract_batch(text)
        if actions:
            return {
                "intent": "batch",
                "data": {},
                "actions": actions,
            }
    understanding = understand_message(text, {}, ai_config)
    if understanding.get("intent") == "batch" and understanding.get("actions"):
        return {
            "intent": "batch",
            "data": {},
            "actions": understanding["actions"],
        }
    if understanding.get("intent") in ("transaction", "balance", "reminder"):
        return {
            "intent": understanding["intent"],
            "data": understanding.get("data") or {},
            "actions": understanding.get("actions") or [],
        }
    regex_result = _regex_parse(text)
    if regex_result.get("intent") != "unknown":
        return regex_result
    return {"intent": "unknown", "data": {}, "actions": []}

def apply_balance_update(user_id: int, data: dict) -> str:
    name = (data.get("name") or "资产").strip()[:32]
    try:
        balance = Decimal(str(data.get("balance", 0)))
    except Exception:
        raise ValueError("invalid balance")
    note = (data.get("note") or "").strip()[:200]
    kind = (data.get("kind") or "").strip()
    if kind not in ("asset", "liability"):
        kind = "liability" if _is_liability_name(name) or "负债" in note else "asset"
    asset = Asset.query.filter_by(user_id=user_id, name=name).first()
    if asset:
        asset.balance = balance
        asset.note = note
        asset.kind = kind
        asset.updated_at = datetime.utcnow()
        action = f"已更新{name}余额为 {float(balance)} 元"
    else:
        asset = Asset(user_id=user_id, name=name, balance=balance, note=note, kind=kind)
        db.session.add(asset)
        action = f"已记录{name}余额 {float(balance)} 元"
    db.session.commit()
    return action

def apply_transaction(user_id: int, data: dict) -> str:
    t_type = (data.get("type") or "expense").strip()
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid amount")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("invalid amount")
    category = (data.get("category") or "其他").strip()[:32]
    note = (data.get("note") or "").strip()[:200]
    d = datetime.strptime((data.get("date") or date.today().isoformat())[:10], "%Y-%m-%d").date()
    txn = Transaction(
        user_id=user_id,
        type=t_type,
        amount=amount,
        category=category,
        note=note,
        date=d,
    )
    db.session.add(txn)
    db.session.commit()
    label = "收入" if t_type == "income" else "支出"
    return f"已记录{label} {float(amount)} 元（{category}）"

def apply_reminder(user_id: int, data: dict) -> str:
    title = (data.get("title") or "").strip()[:120]
    if not title:
        raise ValueError("invalid title")
    due_text = (data.get("due_at") or "").strip().replace("Z", "")
    due_at = None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            due_at = datetime.strptime(due_text, fmt)
            break
        except ValueError:
            continue
    if not due_at:
        due_at = datetime.now() + timedelta(days=1)
    r_type = (data.get("type") or "life").strip()
    if r_type not in ("bill", "life", "anniversary"):
        r_type = "life"
    note = (data.get("note") or "").strip()[:200]
    reminder = Reminder(
        user_id=user_id,
        title=title,
        due_at=due_at,
        type=r_type,
        note=note,
    )
    db.session.add(reminder)
    db.session.commit()
    return f"已添加提醒：{title}"
