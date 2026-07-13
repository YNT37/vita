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

MAX_CONTENT_LEN = 500

_LLM_CACHE: dict[str, object] = {}



ACTIONABLE_INTENTS = ("transaction", "balance", "reminder")

UNDERSTAND_INTENTS = ("chat", "query", "transaction", "balance", "reminder", "unknown")



UNDERSTAND_SYSTEM = """你是 Vita 生活管家的意图理解模块。根据用户消息和已有数据，只输出 JSON，不要 markdown。



格式：

{"intent":"chat|query|transaction|balance|reminder|unknown","should_act":bool,"data":{},"summary":"一句话说明你的理解"}



意图：

- chat：闲聊、情绪、知识问答，不涉及用户账目

- query：询问已有数据（今天花了多少、基金余额、有什么提醒），只读不写入

- transaction：记录收入/支出（午饭30、工资到账8000、打车15元）

- balance：记录/更新资产账户余额快照（基金余额1901、余额宝还有5000、刚查了下股票账户剩三万二）

- reminder：新建提醒（提醒我明天还花呗、下周三交房租）

- unknown：实在无法理解



should_act 规则：

- transaction/balance/reminder 且用户明确在汇报或要求记录 → true

- 用户在询问、试探、聊天 → false（intent 用 query 或 chat）

- 含糊不清（如只说了一个数字）→ false



data 字段：

- transaction: type(income/expense), amount(number), category, note, date(YYYY-MM-DD，默认今天)

- balance: name(资产名), balance(number), note

- reminder: title, due_at(ISO如2026-07-14T10:00), type(bill/life/anniversary), note

- query: topic(assets|expense|income|reminders|overview)

- 其他 intent: {}



关键区分：

- 「基金余额1901」「检查了下基金剩1901」→ balance + should_act true

- 「我基金现在多少」「基金什么情况」→ query topic=assets

- 「今天花了多少」→ query topic=expense

- 「今天午饭花了30」→ transaction expense

- 「心情不好」→ chat

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





ASSET_KEYWORDS = ("基金", "余额宝", "股票", "银行卡", "储蓄卡", "现金", "理财", "债券", "外汇", "花呗", "信用卡")





def _extract_asset_name(text: str) -> str:

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





def _looks_like_balance(text: str) -> bool:

    if re.search(r"多少|多少钱|什么情况|怎么样|查看|查询", text):

        return False

    return bool(

        re.search(

            r"余额|结余|还剩|剩了|剩下|账户(?:里|内)?(?:有|剩)|更新了|查了下|看了看|刚看",

            text,

        )

    )





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





def _normalize_understanding(obj: dict, source_text: str) -> dict:

    intent = (obj.get("intent") or "unknown").strip().lower()

    if intent not in UNDERSTAND_INTENTS:

        intent = "unknown"

    should_act = bool(obj.get("should_act")) and intent in ACTIONABLE_INTENTS

    data = obj.get("data") or {}

    summary = (obj.get("summary") or "").strip()



    if intent == "balance":

        name = (data.get("name") or _extract_asset_name(source_text)).strip()[:32] or "资产"

        try:

            balance = float(data.get("balance", data.get("amount", 0)))

        except (TypeError, ValueError):

            balance = -1

        if balance < 0:

            intent, should_act = "unknown", False

            data = {}

        else:

            data = {"name": name, "balance": balance, "note": (data.get("note") or source_text)[:200]}

    elif intent == "transaction":

        t_type = (data.get("type") or "expense").strip()

        if t_type not in ("income", "expense"):

            t_type = "expense"

        try:

            amount = float(data.get("amount", 0))

        except (TypeError, ValueError):

            amount = 0

        if amount <= 0:

            intent, should_act = "unknown", False

            data = {}

        else:

            data = {

                "type": t_type,

                "amount": amount,

                "category": (data.get("category") or "其他")[:32],

                "note": (data.get("note") or source_text)[:200],

                "date": (data.get("date") or date.today().isoformat())[:10],

            }

    elif intent == "reminder":

        title = (data.get("title") or source_text).strip()[:120]

        due_at = (data.get("due_at") or "").strip()

        if not due_at:

            due_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")

        r_type = (data.get("type") or "life").strip()

        if r_type not in ("bill", "life", "anniversary"):

            r_type = "life"

        data = {

            "title": title,

            "due_at": due_at,

            "type": r_type,

            "note": (data.get("note") or "")[:200],

        }

    elif intent == "query":

        topic = (data.get("topic") or _query_topic(source_text)).strip()

        if topic not in ("assets", "expense", "income", "reminders", "overview"):

            topic = "overview"

        data = {"topic": topic}

        should_act = False



    return {

        "intent": intent,

        "should_act": should_act,

        "data": data,

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

    if _looks_like_query(message):

        topic = _query_topic(message)

        return {

            "intent": "query",

            "should_act": False,

            "data": {"topic": topic},

            "summary": f"查询{topic}",

        }



    parsed = _regex_parse(message)

    if parsed.get("intent") in ACTIONABLE_INTENTS:

        return {

            "intent": parsed["intent"],

            "should_act": True,

            "data": parsed.get("data") or {},

            "summary": f"识别为{parsed['intent']}",

        }



    return {"intent": "chat", "should_act": False, "data": {}, "summary": ""}





def understand_message(

    message: str,

    context: dict | None = None,

    ai_config: dict | None = None,

) -> dict:

    """统一意图理解：LLM 优先，规则兜底。"""

    message = _truncate(message, 500)

    if not message:

        return {"intent": "unknown", "should_act": False, "data": {}, "summary": ""}



    result = _llm_understand(message, context, ai_config)

    if result and result.get("intent") != "unknown":

        return result

    return _fallback_understand(message, context)





def execute_intent(user_id: int, understanding: dict) -> str | None:

    if not understanding.get("should_act"):

        return None

    intent = understanding.get("intent")

    data = understanding.get("data") or {}

    try:

        if intent == "balance":

            return apply_balance_update(user_id, data)

        if intent == "transaction":

            return apply_transaction(user_id, data)

        if intent == "reminder":

            return apply_reminder(user_id, data)

    except Exception as e:

        logger.warning("execute_intent failed: %s", e)

        return None

    return None





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

    for h in hist:

        role = h.get("role", "")

        content = _truncate(h.get("content", ""))

        if content:

            parts.append(f"{role}: {content}")

    parts.append(f"user: {message}")

    user_prompt = (

        "以下是对话历史、用户数据与当前消息。请用角色语气自然回复；"

        "若是查询，请基于【查询结果】或【用户当前数据】回答，不要编造。\n"

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

            "butler": f"好的，{action_note}。",

            "servant": f"主子放心，{action_note}，奴才记下了。",

            "sassy": f"行，{action_note}，别到时候又亏光了。",

            "lover": f"嗯嗯，{action_note}，我帮你记着呢。",

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

    if not understanding or understanding.get("intent") not in ACTIONABLE_INTENTS:

        return None

    return {

        "intent": understanding["intent"],

        "data": understanding.get("data") or {},

    }





def parse_input(text: str, ai_config: dict | None = None) -> dict:

    text = _truncate(text, 200)

    if not text:

        return {"intent": "unknown", "data": {}}



    understanding = understand_message(text, {}, ai_config)

    if understanding.get("intent") in ACTIONABLE_INTENTS:

        return {

            "intent": understanding["intent"],

            "data": understanding.get("data") or {},

        }

    regex_result = _regex_parse(text)

    if regex_result.get("intent") != "unknown":

        return regex_result

    return {"intent": "unknown", "data": {}}





def apply_balance_update(user_id: int, data: dict) -> str:

    name = (data.get("name") or "资产").strip()[:32]

    try:

        balance = Decimal(str(data.get("balance", 0)))

    except Exception:

        raise ValueError("invalid balance")

    note = (data.get("note") or "").strip()[:200]



    asset = Asset.query.filter_by(user_id=user_id, name=name).first()

    if asset:

        asset.balance = balance

        asset.note = note

        asset.updated_at = datetime.utcnow()

        action = f"已更新{name}余额为 {float(balance)} 元"

    else:

        asset = Asset(user_id=user_id, name=name, balance=balance, note=note)

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


