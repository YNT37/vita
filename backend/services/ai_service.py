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
LIABILITY_KEYWORDS = (
    "花呗", "白条", "借呗", "信用卡", "月付", "分付", "负债", "欠款", "贷款",
)
ASSET_KEYWORDS = (
    "基金", "余额宝", "股票", "银行卡", "储蓄卡", "现金", "理财", "债券",
    "外汇", "微信", "支付宝", "建行", "工行", "招行", "农行", "中行", "交行",
    "花呗", "白条", "信用卡", "抖音月付", "美团月付", "分付",
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
- balance: {name, balance(number), kind?: asset|liability, note?}
- transaction: {type income|expense, amount, category, note?, date?, account?}
  account=付款账户（花呗/工行/微信等）；花呗白条支付时必填，表示增加欠款
- reminder: {title, due_at ISO, type bill|life|anniversary, note?, repeat?: none|monthly|weekly, linked_asset_name?}
- query: {topic assets|expense|income|reminders|overview}

硬性规则：
- 「花呗支付500」「用花呗付了300」→ transaction(expense)+account=花呗；禁止写成 balance 把花呗设为500
- 「京东白条支付50」→ transaction + 若尚无周期提醒则同时给出 monthly reminder；并说明计入本月/下月账单
- 「抖音月付支付300」→ transaction(account=抖音月付) + monthly reminder；即使资产列表尚无该账户也要新建
- 「白条支付300分3期」→ transaction + 每一期一张 reminder（含期数与金额）
- 「吃饭花了50，工商银行付款」→ transaction(expense,餐饮)+account=工行
- 提到花呗/白条/借呗/信用卡欠款（欠/待还/应还）时，必须同时给出：① balance（kind=liability）② reminder（type=bill，含还款日）
- 若说「每月/每个月 X 号」，reminder.repeat=monthly，并填 linked_asset_name（如花呗）
- 不能只记余额不建还款提醒；日期可用「七月25日」「7.25」「每月25号」等

示例：
用户：「基金1901.74，微信57.6，建行270.29，工行151.16；花呗707.69七月25日还，京东白条412.58分两期每期206.29二十七日还」
→ batch，4 个 balance(asset) + 2 个 balance(liability) + 2 个 reminder(bill)

用户：「花呗欠款800，七月25日还」
→ batch：balance(花呗,800,liability) + reminder(还花呗 800元, due 本年7月25日)

用户：「花呗支付500」
→ transaction：expense 500，account=花呗；并附带还花呗的 monthly reminder（若尚无）

用户：「京东白条支付50」
→ transaction：expense 50，account=京东白条 + monthly reminder

用户：「白条300分3期」
→ transaction 300 + 3 张分期 reminder

用户：「吃饭花了50，工商银行付款」
→ transaction：expense 50，category=餐饮，account=工行
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


def _looks_like_payment(text: str) -> bool:
    """花钱/付款类表达（区别于「账户余额汇报」）。"""
    return bool(
        re.search(
            r"支付|付款|付了|花了|消费|买了|刷了|"
            r"用.{0,8}(?:付|支付|付款)|"
            r"(?:花呗|白条|借呗|信用卡|月付|分付|微信|支付宝|建行|工行|招行).{0,4}(?:支付|付款|付了|付)",
            text or "",
        )
    )


def _extract_pay_account(text: str) -> str:
    """从「花呗支付 / 工行付款 / 抖音月付支付 / 用微信付」提取付款账户。"""
    text = _normalize_finance_text(text or "")
    names = (
        "京东白条",
        "抖音月付",
        "美团月付",
        "花呗",
        "白条",
        "借呗",
        "信用卡",
        "微信分付",
        "分付",
        "微信",
        "支付宝",
        "建行",
        "工行",
        "招行",
        "农行",
        "中行",
        "交行",
        "现金",
    )
    joined = "|".join(names)
    m = re.search(
        rf"(?:用|通过|经)\s*({joined}|[\u4e00-\u9fa5]{{2,8}}月付)\s*(?:来)?(?:支付|付款|付了|付|刷|花了|消费)?",
        text,
    )
    if m:
        return m.group(1)
    m = re.search(
        rf"({joined}|[\u4e00-\u9fa5]{{2,8}}月付)\s*(?:支付|付款|付了|付的|付)",
        text,
    )
    if m:
        return m.group(1)
    return ""


def _infer_expense_category(text: str) -> str:
    if re.search(r"吃饭|午饭|午餐|早餐|晚餐|外卖|餐饮|食堂|奶茶|咖啡|宵夜", text):
        return "餐饮"
    if re.search(r"交通|地铁|打车|公交|出租|加油|滴滴", text):
        return "交通"
    if re.search(r"房租|水电|物业|话费|网费", text):
        return "居住"
    if re.search(r"超市|日用|购物|淘宝|拼多多", text) or (
        re.search(r"京东", text) and not re.search(r"白条", text)
    ):
        return "购物"
    return "其他"


def _parse_cn_due(text: str, default_hour: int = 10) -> str:
    """把「7月25日」「七月25日」「7.25」「25号还」等解析为今年 ISO 时间。"""
    now = datetime.now()
    year = now.year
    cn_month = {
        "正": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
        "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
    }
    cn_day = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
        "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13,
        "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18,
        "十九": 19, "二十": 20, "廿": 20, "三十": 30,
    }

    def _finish(y: int, month: int, day: int) -> str | None:
        try:
            due = datetime(y, month, day, default_hour, 0)
            if due.date() < now.date() and month < now.month:
                due = datetime(y + 1, month, day, default_hour, 0)
            elif due.date() < now.date():
                # 同月已过的日期 → 下一年
                due = datetime(y + 1, month, day, default_hour, 0)
            return due.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return None

    m = re.search(r"(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})[日号]?", text)
    if m:
        got = _finish(int(m.group(1) or year), int(m.group(2)), int(m.group(3)))
        if got:
            return got

    m = re.search(
        r"(?:(\d{4})年)?\s*(正|十一|十二|一|二|三|四|五|六|七|八|九|十)月\s*"
        r"([一二三四五六七八九十廿\d]{1,3})[日号]?",
        text,
    )
    if m:
        month = cn_month.get(m.group(2), 0)
        day_raw = m.group(3)
        day = int(day_raw) if day_raw.isdigit() else cn_day.get(day_raw, 0)
        if month and day:
            got = _finish(int(m.group(1) or year), month, day)
            if got:
                return got

    m = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            got = _finish(year, month, day)
            if got:
                return got

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

    # 「二十七日还」无月份 → 本月或下月该日
    m = re.search(r"(二十[一二三四五六七八九]?|三十|廿[一二三四五六七八九]?|[一二三四五六七八九十]{1,3})日", text)
    if m:
        day = cn_day.get(m.group(1), 0)
        if day:
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
    # 支付/消费不是余额汇报（「花呗支付500」「工行付款」）
    if _looks_like_payment(text) and not re.search(
        r"余额|结余|还剩|欠款|欠了|待还|应还|账单", text
    ):
        return False
    return bool(
        re.search(
            r"余额|结余|还剩|剩了|剩下|账户|资产|基金|微信|支付宝|建行|工行|招行|"
            r"银行|花呗|白条|更新了|查了下|看了看|刚看|整理|汇报|记一下|同步|录入",
            text,
        )
    )

def _parse_cn_amount(token: str) -> float | None:
    """把「300」「三百」「一千二」等转成数字。"""
    s = (token or "").strip().replace(",", "").replace("两", "二")
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d{1,2})?", s):
        return float(s)
    digits = {
        "零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    if s in digits:
        return float(digits[s])
    # 仅支持常见口语：百/千/万组合，如 三百、一千五、两千零三十
    total = 0
    num = 0
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in digits:
            num = digits[ch]
            i += 1
            continue
        if ch in units:
            unit = units[ch]
            if num == 0 and unit == 10:
                num = 1  # 「十二」
            total += num * unit
            num = 0
            i += 1
            continue
        return None
    total += num
    return float(total) if total > 0 else None


def _amount_token_re() -> str:
    return r"(?:\d+(?:\.\d{1,2})?|[一二三四五六七八九十百千万两零〇]+)"


def _looks_like_sync_request(text: str) -> bool:
    return bool(
        re.search(
            r"同步|重新录入|重新记|需要|记下来|写入|帮我记|录入|补上|记入|再记|"
            r"保存资产|记录账户|设置(?:当前)?(?:账户)?资产|资产信息",
            text or "",
        )
    )


def _looks_like_finance_report(text: str) -> bool:
    """是否像一次汇报多账户/多负债。"""
    text = _normalize_finance_text(text)
    money_hits = re.findall(r"\d+(?:\.\d{1,2})?", text)
    money_hits += re.findall(r"[一二三四五六七八九十百千万两零〇]+元?", text)
    # 过滤误伤的纯「一」「二」等过短字
    money_hits = [m for m in money_hits if not re.fullmatch(r"[一二三四五六七八九]", m)]
    name_hits = sum(1 for kw in ASSET_KEYWORDS if kw in text)
    if "银行" in text or "建设银行" in text or "工商银行" in text:
        name_hits += 1
    return len(money_hits) >= 2 and name_hits >= 2


def _regex_extract_debts(text: str) -> list[dict]:
    """花呗/白条等：同时产出负债账户(balance) + 还款提醒(reminder)。"""
    text = _normalize_finance_text(text)
    actions: list[dict] = []
    seen: set[str] = set()
    amt = _amount_token_re()

    debt_pat = re.compile(
        r"(抖音月付|美团月付|花呗|京东白条|白条|借呗|信用卡|微信分付|[\u4e00-\u9fa5]{2,8}月付)"
        r"(?:\s*(?:的)?(?:欠款|欠费|欠|待还|应还|账单))?"
        r"\s*(?:为|是|：|:)?\s*"
        rf"({amt})\s*元?"
    )
    for m in debt_pat.finditer(text):
        name, amount_s = m.group(1), m.group(2)
        if name == "白条" and text[max(0, m.start() - 2) : m.start()] == "京东":
            continue
        # 「花呗支付500」中间是支付动词 → 消费记账，不是欠款余额
        between = text[m.start(1) + len(name) : m.start(2)]
        if re.search(r"支付|付款|付了|花了|消费|买了|刷了", between):
            continue
        amount = _parse_cn_amount(amount_s)
        if amount is None or amount < 0:
            continue
        window = text[m.end() : m.end() + 100]
        cut = re.search(
            r"抖音月付|美团月付|花呗|京东白条|白条|借呗|信用卡|微信分付|[\u4e00-\u9fa5]{2,8}月付",
            window,
        )
        if cut:
            window = window[: cut.start()]
        # 还款日可在整句任意处（「花呗欠三百，……每个月28号还款」）
        due_src = window + " " + text
        due = _parse_cn_due(due_src)
        installment = re.search(
            rf"(?:每期|每个月还|每月还|分\s*\d+\s*期)\s*(?:还)?\s*({amt})",
            window + " " + text,
        )
        pay = _parse_cn_amount(installment.group(1)) if installment else amount
        if pay is None:
            pay = amount
        title = f"还{name} {pay:g}元"
        from services.reminder_service import detect_repeat_from_text, infer_linked_asset_name

        repeat = detect_repeat_from_text(due_src)
        actions.append(
            {
                "intent": "reminder",
                "data": {
                    "title": title[:120],
                    "due_at": due,
                    "type": "bill",
                    "note": f"总额{amount:g}"
                    + (f"；{window.strip()[:80]}" if window.strip() else ""),
                    "repeat": repeat,
                    "linked_asset_name": infer_linked_asset_name(name, ""),
                },
            }
        )
        if name not in seen:
            seen.add(name)
            actions.append(
                {
                    "intent": "balance",
                    "data": {
                        "name": name,
                        "balance": amount,
                        "kind": "liability",
                        "note": "负债欠款",
                    },
                }
            )

    # 「花呗每个月28号还款提醒」——金额已在上文或暂无金额也要出提醒卡
    monthly = re.search(
        r"(?:每个月|每月)(?:的)?\s*(\d{1,2})[日号].{0,20}(?:还|还款|提醒)|"
        r"(?:还|还款|提醒).{0,20}(?:每个月|每月)(?:的)?\s*(\d{1,2})[日号]",
        text,
    )
    if monthly and re.search(r"花呗|白条|借呗|信用卡|月付|分付", text):
        day = int(monthly.group(1) or monthly.group(2))
        due = _parse_cn_due(f"每月{day}号")
        for name in ("抖音月付", "美团月付", "花呗", "京东白条", "白条", "借呗", "信用卡", "微信分付"):
            if name == "白条" and "京东白条" in text:
                continue
            if name not in text:
                continue
            # 已有同名提醒则只修正 due
            existing = next(
                (
                    a
                    for a in actions
                    if a.get("intent") == "reminder"
                    and name in str((a.get("data") or {}).get("title") or "")
                ),
                None,
            )
            if existing:
                existing["data"]["due_at"] = due
                existing["data"]["repeat"] = "monthly"
                existing["data"]["linked_asset_name"] = name
                note = str(existing["data"].get("note") or "")
                if "每月" not in note:
                    existing["data"]["note"] = (note + f"；每月{day}号").strip("；")[:200]
            else:
                bal = next(
                    (
                        (a.get("data") or {}).get("balance")
                        for a in actions
                        if a.get("intent") == "balance"
                        and (a.get("data") or {}).get("name") == name
                    ),
                    None,
                )
                title = f"还{name}" + (f" {float(bal):g}元" if bal is not None else "")
                actions.append(
                    {
                        "intent": "reminder",
                        "data": {
                            "title": title[:120],
                            "due_at": due,
                            "type": "bill",
                            "note": f"每月{day}号还款",
                            "repeat": "monthly",
                            "linked_asset_name": name,
                        },
                    }
                )
            break

    return actions


def _regex_extract_batch(text: str) -> list[dict]:
    """规则提取多账户余额 + 负债还款提醒。"""
    text = _normalize_finance_text(text)
    actions: list[dict] = _regex_extract_debts(text)
    seen_assets: set[str] = {
        (a.get("data") or {}).get("name", "")
        for a in actions
        if a.get("intent") == "balance"
    }

    # 账户名 + 金额（支持「三百」）
    amt = _amount_token_re()
    asset_pat = re.compile(
        r"(基金|余额宝|股票|微信|支付宝|建行|工行|招行|农行|中行|交行|现金|理财|"
        r"银行卡|储蓄卡)"
        r"(?:的)?(?:余额|账户|卡)?"
        r"(?:为|是|剩|还有|：|:|)?\s*"
        rf"({amt})\s*元?"
    )
    for m in asset_pat.finditer(text):
        name, amount_s = m.group(1), m.group(2)
        if _is_liability_name(name):
            continue
        if name in seen_assets:
            continue
        amount = _parse_cn_amount(amount_s)
        if amount is None:
            continue
        seen_assets.add(name)
        actions.append(
            {
                "intent": "balance",
                "data": {
                    "name": name[:32],
                    "balance": amount,
                    "kind": "asset",
                    "note": text[:200],
                },
            }
        )

    return actions


def _enrich_actions_with_debts(text: str, actions: list[dict]) -> list[dict]:
    """补上 LLM 漏掉的花呗/白条：负债余额 + 还款提醒。"""
    debts = _regex_extract_debts(text)
    if not debts:
        # 仍给已有负债账户标 kind
        out = []
        for item in actions:
            if item.get("intent") == "balance":
                data = dict(item.get("data") or {})
                if _is_liability_name(str(data.get("name") or "")):
                    data["kind"] = "liability"
                    if "负债" not in str(data.get("note") or ""):
                        data["note"] = ("负债欠款；" + str(data.get("note") or "")).strip("；")[:200]
                out.append({"intent": "balance", "data": data})
            else:
                out.append(item)
        return out

    out = list(actions)
    bal_names = {
        str((a.get("data") or {}).get("name") or "")
        for a in out
        if a.get("intent") == "balance"
    }
    rem_titles = " ".join(
        str((a.get("data") or {}).get("title") or "")
        for a in out
        if a.get("intent") == "reminder"
    )

    for item in debts:
        data = item.get("data") or {}
        if item.get("intent") == "balance":
            name = str(data.get("name") or "")
            if name in bal_names:
                for a in out:
                    if a.get("intent") == "balance" and str((a.get("data") or {}).get("name")) == name:
                        a["data"] = {**(a.get("data") or {}), "kind": "liability"}
                        if data.get("balance") is not None and not (a.get("data") or {}).get("balance"):
                            a["data"]["balance"] = data["balance"]
                continue
            out.append(item)
            bal_names.add(name)
        elif item.get("intent") == "reminder":
            name = ""
            for kw in ("抖音月付", "美团月付", "花呗", "京东白条", "白条", "借呗", "信用卡", "微信分付"):
                if kw in str(data.get("title") or ""):
                    name = kw
                    break
            if name and name in rem_titles:
                continue
            out.append(item)
            rem_titles += " " + str(data.get("title") or "")

    return out

def _looks_like_record(text: str) -> bool:
    return bool(
        re.search(
            r"记|花了|付了|支付|付款|买了|消费|支出|收入|到账|工资|奖金|打车|"
            r"午饭|早餐|晚餐|奶茶|咖啡",
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
        kind = (data.get("kind") or "").strip()
        if kind not in ("asset", "liability"):
            kind = "liability" if _is_liability_name(name) else "asset"
        return {
            "intent": "balance",
            "data": {"name": name, "balance": balance, "kind": kind, "note": note},
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
        account = (data.get("account") or data.get("asset_name") or "").strip()[:32]
        if not account:
            account = _extract_pay_account(source_text)
        return {
            "intent": "transaction",
            "data": {
                "type": t_type,
                "amount": amount,
                "category": (data.get("category") or "其他")[:32],
                "note": (data.get("note") or source_text)[:200],
                "date": (data.get("date") or date.today().isoformat())[:10],
                "account": account,
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
        from services.reminder_service import (
            detect_repeat_from_text,
            infer_linked_asset_name,
            normalize_repeat,
        )

        repeat = normalize_repeat(data.get("repeat"))
        if repeat == "none":
            repeat = detect_repeat_from_text(source_text + " " + title + " " + str(data.get("note") or ""))
        linked = (data.get("linked_asset_name") or "").strip()[:32]
        if not linked and r_type == "bill":
            linked = infer_linked_asset_name(title, str(data.get("note") or "") + source_text)
        return {
            "intent": "reminder",
            "data": {
                "title": title,
                "due_at": due_at,
                "type": r_type,
                "note": (data.get("note") or "")[:200],
                "repeat": repeat,
                "linked_asset_name": linked,
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
    if parsed.get("intent") == "batch" and parsed.get("actions"):
        return {
            "intent": "batch",
            "should_act": True,
            "data": {},
            "actions": parsed["actions"],
            "summary": f"规则识别批量写入 {len(parsed['actions'])} 项",
        }
    return {"intent": "chat", "should_act": False, "data": {}, "actions": [], "summary": ""}

def _finalize_understanding(
    source: str,
    result: dict,
    context: dict | None = None,
    user_id: int | None = None,
) -> dict:
    """统一补全花呗/白条等负债动作，保证确认卡同时出现账户+提醒。"""
    actions = list(result.get("actions") or [])
    if result.get("should_act") and not actions:
        intent = result.get("intent")
        data = result.get("data") or {}
        if intent in ("balance", "transaction", "reminder"):
            actions = [{"intent": intent, "data": data}]
    actions = _enrich_actions_with_debts(source, actions)
    actions, repay_explain = _enrich_credit_payment_actions(
        source, actions, context=context, user_id=user_id
    )
    # 仅有负债规则命中时也要强制 should_act
    if not actions:
        return result
    intent = result.get("intent") or "batch"
    if len(actions) >= 2:
        intent = "batch"
    elif len(actions) == 1:
        intent = actions[0]["intent"]
    summary = result.get("summary") or (
        f"识别 {len(actions)} 项待确认" if len(actions) > 1 else result.get("summary") or ""
    )
    if repay_explain:
        summary = f"{summary}｜{repay_explain[:180]}"
    out = {
        **result,
        "intent": intent,
        "should_act": True,
        "data": {} if intent == "batch" else (actions[0].get("data") or {}),
        "actions": actions,
        "summary": summary,
    }
    if repay_explain:
        out["repay_explain"] = repay_explain
    return out


def _collect_context_reminders(context: dict | None, user_id: int | None) -> list[dict]:
    ctx = context or {}
    rem = list(ctx.get("reminders_pending") or []) + list(ctx.get("reminders_today") or [])
    if user_id is None:
        return rem
    try:
        from models import Reminder

        rows = (
            Reminder.query.filter_by(user_id=user_id, done=False)
            .order_by(Reminder.due_at.asc())
            .limit(50)
            .all()
        )
        for r in rows:
            rem.append(r.to_dict())
    except Exception:
        pass
    return rem


def _enrich_credit_payment_actions(
    source: str,
    actions: list[dict],
    *,
    context: dict | None = None,
    user_id: int | None = None,
) -> tuple[list[dict], str]:
    """信用账户支付：补充账单归属说明、周期提醒或分期逐期提醒。"""
    from services.repay_policy import (
        build_installment_reminders,
        build_monthly_reminder,
        classify_charge,
        enrich_explain_with_web,
        extract_due_day_from_reminders,
        has_monthly_reminder,
        infer_statement_day,
        is_credit_product,
        normalize_product,
        parse_installment,
        resolve_policy,
    )

    out = list(actions)
    explains: list[str] = []
    reminders = _collect_context_reminders(context, user_id)

    # 找信用账户相关的支出
    credit_txns = []
    for a in out:
        if a.get("intent") != "transaction":
            continue
        data = a.get("data") or {}
        if (data.get("type") or "expense") != "expense":
            continue
        account = normalize_product(data.get("account") or "")
        if not is_credit_product(account):
            continue
        credit_txns.append((a, account, data))

    if not credit_txns and _looks_like_payment(source):
        # 文本里点名信用产品但 actions 尚未带 account
        for name in ("抖音月付", "美团月付", "京东白条", "花呗", "白条", "借呗", "信用卡", "微信分付"):
            if name in source and is_credit_product(name):
                # 由调用方已生成 txn；这里仅兜底
                break

    for item, product, data in credit_txns:
        amount = float(data.get("amount") or 0)
        user_due = extract_due_day_from_reminders(product, reminders)
        user_statement = infer_statement_day(product, user_due) if user_due else None
        policy = resolve_policy(
            product,
            statement_day=user_statement,
            due_day=user_due,
        )
        if not policy:
            continue
        classification = classify_charge(policy)
        explain = enrich_explain_with_web(policy, classification)
        explains.append(explain)

        # 备注写入账单归属
        note = str(data.get("note") or source)[:200]
        tag = f"计入{classification['period']}；应还日{classification['due_date']}"
        if tag not in note:
            data = {
                **data,
                "note": f"{note}；{tag}"[:200],
                "account": product,
                "bill_period": classification["period"],
                "bill_due_date": classification["due_date"],
            }
            item["data"] = data

        inst = parse_installment(source, amount)
        if inst:
            first_due = datetime.strptime(classification["due_date"], "%Y-%m-%d").date()
            # 若计入下月账单，首期还款日已是 classification.due_date
            installments = build_installment_reminders(
                product,
                total=amount,
                periods=int(inst["periods"]),
                first_due=first_due,
                per_amount=inst.get("per_amount"),
            )
            # 去掉已有同名分期草稿，再追加
            out = [
                a
                for a in out
                if not (
                    a.get("intent") == "reminder"
                    and product in str((a.get("data") or {}).get("title") or "")
                    and "期" in str((a.get("data") or {}).get("title") or "")
                )
            ]
            out.extend(installments)
            explains.append(
                f"已按{inst['periods']}期拆分，每期约 {inst.get('per_amount') or '?'} 元，"
                "下方为每一期还款提醒，请核对金额与日期。"
            )
        elif not has_monthly_reminder(product, reminders):
            # 尚无周期提醒 → 同步创建
            already = any(
                a.get("intent") == "reminder"
                and (a.get("data") or {}).get("repeat") == "monthly"
                and normalize_product((a.get("data") or {}).get("linked_asset_name") or "")
                == product
                for a in out
            )
            if not already:
                rem = build_monthly_reminder(
                    product,
                    int(policy["due_day"]),
                    note=(
                        f"每月{policy['due_day']}号还款；"
                        f"默认账单日{policy['statement_day']}号；"
                        f"{classification['period']}"
                    ),
                )
                # 用本笔归属的还款日作为首期 due
                rem["data"]["due_at"] = classification["due_at"]
                out.append(rem)
                explains.append(
                    f"检测到「{product}」尚无周期还款提醒，已按制度拟定每月"
                    f"{policy['due_day']}号提醒，请确认是否与 App 一致。"
                )

    return out, "\n".join(explains).strip()


def understand_message(
    message: str,
    context: dict | None = None,
    ai_config: dict | None = None,
    history_text: str | None = None,
    user_id: int | None = None,
) -> dict:
    """统一意图理解：LLM 优先，规则兜底；多账户汇报强制批量写入。"""
    message = _truncate(message, MAX_CONTENT_LEN)
    if not message:
        return {"intent": "unknown", "should_act": False, "data": {}, "actions": [], "summary": ""}

    def _fin(src: str, result: dict) -> dict:
        return _finalize_understanding(src, result, context=context, user_id=user_id)

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

    # 支付/消费优先：避免「花呗支付500」「工行付款」被当成余额
    pay_txn = _regex_parse_transaction(source)
    if pay_txn:
        return _fin(
            source,
            {
                "intent": "transaction",
                "should_act": True,
                "data": pay_txn.get("data") or {},
                "actions": [pay_txn],
                "summary": "识别为记账（含付款账户）",
            },
        )

    # 含花呗/白条欠款：规则直接出账户+提醒，避免 LLM 只聊不落库
    debt_actions = _regex_extract_debts(source)
    if debt_actions and (
        _looks_like_finance_report(source)
        or _looks_like_sync_request(message)
        or _looks_like_balance(source)
        or len(debt_actions) >= 2
    ):
        # 多账户时合并资产规则
        if _looks_like_finance_report(source):
            actions = _regex_extract_batch(source)
        else:
            actions = debt_actions
        if actions:
            return _fin(
                source,
                {
                    "intent": "batch",
                    "should_act": True,
                    "data": {},
                    "actions": actions,
                    "summary": f"批量记录 {len(actions)} 项财务信息",
                },
            )

    # 多账户汇报：规则优先，避免 LLM 只闲聊不落库
    if _looks_like_finance_report(source):
        actions = _regex_extract_batch(source)
        if len(actions) >= 2:
            return _fin(
                source,
                {
                    "intent": "batch",
                    "should_act": True,
                    "data": {},
                    "actions": actions,
                    "summary": f"批量记录 {len(actions)} 项财务信息",
                },
            )

    result = _llm_understand(message, context, ai_config)
    if result and result.get("intent") != "unknown":
        if result["intent"] in ("chat", "query") and (
            _looks_like_balance(source) or _looks_like_finance_report(source) or debt_actions
        ):
            actions = _regex_extract_batch(source) or debt_actions
            if actions:
                return _fin(
                    source,
                    {
                        "intent": "batch" if len(actions) > 1 else actions[0]["intent"],
                        "should_act": True,
                        "data": {} if len(actions) > 1 else actions[0]["data"],
                        "actions": actions,
                        "summary": "纠正为财务写入",
                    },
                )
        return _fin(source, result)
    return _fin(source, _fallback_understand(source, context))

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


def extract_pending_actions(understanding: dict) -> list[dict]:
    """提取待用户确认的写入项（聊天场景不自动落库）。"""
    if understanding.get("intent") == "query":
        return []
    actions = understanding.get("actions") or []
    if understanding.get("should_act") and not actions:
        intent = understanding.get("intent")
        data = understanding.get("data") or {}
        if intent in ("balance", "transaction", "reminder"):
            actions = [{"intent": intent, "data": data}]
    pending: list[dict] = []
    for item in actions:
        intent = item.get("intent")
        if intent in ("balance", "transaction", "reminder"):
            pending.append({"intent": intent, "data": item.get("data") or {}})
    return pending


def generate_chat_reply(
    persona: str,
    message: str,
    history: list | None = None,
    ai_config: dict | None = None,
    context: dict | None = None,
    understanding: dict | None = None,
    action_note: str | None = None,
    query_answer: str | None = None,
    pending_count: int = 0,
    repay_explain: str | None = None,
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
    if repay_explain:
        parts.append(
            "【还款制度与账单归属】\n"
            + repay_explain
            + "\n请用角色语气向用户说明：本笔计入本月还是下月、建议还款日；"
            "若新建了周期/分期提醒请提示核对确认卡；以 App 实际账单日为准可改卡。"
        )
    if query_answer:
        parts.append(f"【查询结果】{query_answer}")
    if action_note:
        parts.append(f"【系统已执行】{action_note}")
    elif pending_count > 0:
        parts.append(
            f"【待用户确认】本次消息已识别 {pending_count} 项待写入，"
            "界面已为【本轮】弹出可编辑确认卡片；尚未写入数据库。"
            "请用角色语气请用户核对【下方本轮卡片】后点确定。"
            "禁止拿上一轮未确认卡片来拖延本轮记账；本轮有记账卡就应请用户确认本轮卡。"
            "禁止说「系统没有提醒功能」「等以后再添」——若有提醒卡则已经生成。"
            "禁止编造「等旧卡入库后再补记本笔」——本笔若已有确认卡，确认即可写入。"
            "信用付（花呗/白条/月付/分付）即使资产列表里还没有该账户，也应按下方确认卡新建负债账户，"
            "禁止说「没有该账户所以记不了」或要求用户改用已有账户。"
        )
    else:
        parts.append("【系统已执行】无（本次未写入数据库）")
    for h in hist:
        role = h.get("role", "")
        content = _truncate(h.get("content", ""))
        if content:
            parts.append(f"{role}: {content}")
    parts.append(f"user: {message}")
    if pending_count > 0:
        repay_hint = ""
        if repay_explain:
            repay_hint = " " + repay_explain.split("\n")[0][:120]
        ask = {
            "butler": (
                f"好的，本轮整理了 {pending_count} 项确认卡。"
                f"{repay_hint}"
                "请核对方才这几张（含还款日/分期若有），点确定后写入。"
            ),
            "servant": (
                f"嗻！本轮奴才拟了 {pending_count} 条草稿在下方。"
                f"{repay_hint}"
                "主子点确定即入库；分期则每一期都在卡里，劳烦过目。"
            ),
            "sassy": (
                f"本轮 {pending_count} 张卡在下面，核对点确定。"
                f"{repay_hint}"
            ),
            "lover": (
                f"本轮有 {pending_count} 张确认卡～"
                f"{repay_hint}"
                "你改好还款日再点确定就好。"
            ),
        }
        user_prompt = (
            "以下是对话历史、用户数据与当前消息。请用角色语气自然回复。\n"
            "硬性规则：必须请用户确认【本轮】下方卡片；禁止声称没有提醒/记账功能；"
            "禁止把未点确定的内容说成已入库；禁止用旧卡拖延本轮记账写入。"
            "若有【还款制度与账单归属】，必须简明说明本月/下月归属与还款日。\n"
            + "\n".join(parts)
        )
        provider, key, base, model = _ai_params(ai_config)
        reply = _invoke_llm(system, user_prompt, provider, key, base, model)
        bad = bool(
            reply
            and re.search(
                r"没有.{0,8}(提醒|功能)|等系统|以后再|尚未支持|还没.{0,6}功能|添此等|"
                r"还没入库呢|等.{0,12}入库.{0,8}再|立马把.{0,30}补上|"
                r"没有.{0,8}账户|无「[^」]+」|并🈚️|改用已有|指定已有账户",
                reply,
            )
        )
        if reply and not bad:
            return reply
        return ask.get(persona, f"请确认下方 {pending_count} 项后再写入。")

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


def _regex_parse_transaction(text: str) -> dict | None:
    """解析支出/收入，并尽量带上付款账户。"""
    text = (text or "").strip()
    if not text:
        return None
    # 纯欠款/余额汇报不走这里
    if re.search(r"(?:欠款|欠了|待还|应还|余额|结余)", text) and not _looks_like_payment(text):
        return None
    if not (_looks_like_payment(text) or _looks_like_record(text)):
        return None
    today = date.today().isoformat()
    amt = _amount_token_re()
    m = re.search(rf"({amt})", text)
    if not m:
        return None
    amount = _parse_cn_amount(m.group(1))
    if amount is None or amount <= 0:
        return None
    if re.search(r"工资|收入|奖金|到账", text) and not re.search(r"花了|付了|支付|付款|消费", text):
        return {
            "intent": "transaction",
            "data": {
                "type": "income",
                "amount": amount,
                "category": "工资",
                "note": text[:200],
                "date": today,
                "account": _extract_pay_account(text),
            },
        }
    account = _extract_pay_account(text)
    category = _infer_expense_category(text)
    note = text[:200]
    if account and account not in note:
        note = f"{note}；{account}支付"[:200]
    return {
        "intent": "transaction",
        "data": {
            "type": "expense",
            "amount": amount,
            "category": category,
            "note": note,
            "date": today,
            "account": account,
        },
    }


def _regex_parse(text: str) -> dict:
    text = text.strip()
    # 支付/消费优先于余额，避免「花呗支付500」被设成花呗余额=500
    txn = _regex_parse_transaction(text)
    if txn:
        return txn
    # 花呗/白条欠款：账户 + 还款提醒
    debts = _regex_extract_debts(text)
    if debts:
        if len(debts) == 1:
            return {"intent": debts[0]["intent"], "data": debts[0].get("data") or {}}
        return {
            "intent": "batch",
            "data": {},
            "actions": debts,
        }
    balance = _regex_parse_balance(text)
    if balance:
        return balance
    if re.search(r"提醒|记得|别忘了|到期|还款", text) and not re.search(r"多少|多少钱", text):
        due = _parse_cn_due(text)
        title = re.sub(r"提醒我|记得|别忘了", "", text).strip() or text
        return {
            "intent": "reminder",
            "data": {
                "title": title[:120],
                "due_at": due,
                "type": "bill" if re.search(r"花呗|账单|还款|房租|白条", text) else "life",
                "note": "",
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
    account = (data.get("account") or data.get("asset_name") or "").strip()[:32]
    d = datetime.strptime((data.get("date") or date.today().isoformat())[:10], "%Y-%m-%d").date()
    txn = Transaction(
        user_id=user_id,
        type=t_type,
        amount=amount,
        category=category,
        note=note,
        account=account,
        date=d,
    )
    db.session.add(txn)
    account_note = _adjust_account_for_transaction(user_id, account, t_type, amount)
    db.session.commit()
    label = "收入" if t_type == "income" else "支出"
    base = f"已记录{label} {float(amount)} 元（{category}）"
    return base + account_note


def resolve_transaction_account(txn) -> str:
    """优先用流水上的 account，旧数据再从备注推断。"""
    account = (getattr(txn, "account", None) or "").strip()[:32]
    if account:
        return account
    note = getattr(txn, "note", None) or ""
    return _extract_pay_account(note)


def _adjust_account_for_transaction(
    user_id: int,
    account: str,
    t_type: str,
    amount: Decimal,
    *,
    reverse: bool = False,
) -> str:
    """付款账户联动：负债账户增加欠款，资产账户扣减余额。reverse=True 时冲正。"""
    name = (account or "").strip()[:32]
    if not name:
        return ""
    asset = Asset.query.filter_by(user_id=user_id, name=name).first()
    is_liab = _is_liability_name(name) or (asset is not None and (asset.kind or "") == "liability")
    if t_type == "expense":
        delta = amount if is_liab else -amount
    else:
        delta = -amount if is_liab else amount
    if reverse:
        delta = -delta

    if asset:
        asset.balance = Decimal(str(asset.balance or 0)) + delta
        if is_liab:
            asset.kind = "liability"
            if "负债" not in (asset.note or ""):
                asset.note = (("负债欠款；" + (asset.note or "")).strip("；"))[:200]
        asset.updated_at = datetime.utcnow()
        if reverse:
            if is_liab:
                return f"；已冲正，{name}欠款现为 {float(asset.balance):g} 元"
            return f"；已冲正，{name}余额现为 {float(asset.balance):g} 元"
        if is_liab:
            return f"；{name}欠款现为 {float(asset.balance):g} 元"
        return f"；已从{name}扣除，余额现为 {float(asset.balance):g} 元"

    if reverse:
        return ""

    if is_liab:
        start = amount if t_type == "expense" else Decimal("0")
        db.session.add(
            Asset(
                user_id=user_id,
                name=name,
                balance=start,
                kind="liability",
                note="负债欠款",
            )
        )
        return f"；已新建负债账户「{name}」{float(start):g} 元"

    return f"；未找到账户「{name}」，仅记流水未改余额"

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
    from services.reminder_service import (
        detect_repeat_from_text,
        infer_linked_asset_name,
        normalize_repeat,
    )

    repeat = normalize_repeat(data.get("repeat"))
    if repeat == "none":
        repeat = detect_repeat_from_text(f"{title} {note}")
    linked = (data.get("linked_asset_name") or "").strip()[:32]
    if not linked and r_type == "bill":
        linked = infer_linked_asset_name(title, note)
    reminder = Reminder(
        user_id=user_id,
        title=title,
        due_at=due_at,
        type=r_type,
        note=note,
        recurrence=repeat,
        linked_asset_name=linked,
    )
    db.session.add(reminder)
    db.session.commit()
    extra = ""
    if repeat == "monthly":
        extra = "（每月循环）"
    elif repeat == "weekly":
        extra = "（每周循环）"
    if linked:
        extra += f"，关联账户「{linked}」"
    return f"已添加提醒：{title}{extra}"
