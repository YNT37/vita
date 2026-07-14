"""信用账户还款制度：账单归属、默认还款日、分期计划。

以官方公开规则为默认知识库；用户已有「每月X号」提醒时优先用用户日期。
可选联网拉取帮助页摘要（失败则回退知识库）。
"""

from __future__ import annotations

import calendar
import json
import logging
import re
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

# 默认制度（用户可改账单日/还款日；以 App 实际页面为准）
REPAY_POLICIES: dict[str, dict] = {
    "花呗": {
        "aliases": ("花呗", "蚂蚁花呗"),
        "statement_day": 1,
        "due_day": 10,
        "due_offset_days": None,
        "typical_due_days": (8, 9, 10, 15, 20),
        "summary": (
            "花呗按账单制：每月账单日出账，之后在还款日前还清。"
            "常见账单日为每月1日（也可为5/10日），还款日多为账单日后约7–10天"
            "（如1日出账对应8/9/10日还；5日→15日、10日→20日）。"
            "多数网购需确认收货后才入账；扫码等常为付款成功即入账。"
        ),
        "charge_rule": (
            "入账日 ≤ 本期账单日 → 计入本期账单，在本期还款日还；"
            "入账日 > 本期账单日 → 计入下期账单。"
            "账单日当天入账一般计入本期（以支付宝实际入账为准）。"
        ),
        "sources": ("https://cschannel.alipay.com/mobile/helpDetail.htm?help_id=513629",),
    },
    "京东白条": {
        "aliases": ("京东白条", "白条"),
        "statement_day": 3,
        "due_day": 12,
        "due_offset_days": 9,
        "typical_due_days": (12, 14, 19, 24, 29, 3),
        "summary": (
            "京东白条常见为账单制：每月固定账单日，还款日一般为账单日+9天"
            "（新用户常见账单日3日、还款日12日，可在京东金融调整）。"
            "另有订单制白条：按消费日滚动还款，以 App 显示为准。"
        ),
        "charge_rule": (
            "账单日前消费 → 当期账单；账单日当天及之后消费 → 通常计入下一期"
            "（分期首期同此规则）。还款日=账单日+9天。"
        ),
        "sources": ("https://baitiao.jd.com/",),
    },
    "借呗": {
        "aliases": ("借呗",),
        "statement_day": 1,
        "due_day": 10,
        "due_offset_days": None,
        "typical_due_days": (8, 9, 10),
        "summary": "借呗按借据约定还款日还款，常接近每月固定日；以支付宝借呗页面为准。",
        "charge_rule": "支用后按借据生成还款计划；若约定按月还，则每期在约定还款日还。",
        "sources": (),
    },
    "信用卡": {
        "aliases": ("信用卡",),
        "statement_day": 1,
        "due_day": 20,
        "due_offset_days": None,
        "typical_due_days": (15, 20, 25),
        "summary": "信用卡账单周期一般为「上期账单日次日～本期账单日」，还款日在账单日后若干天。",
        "charge_rule": "账单日当天消费通常计入本期；账单日次日起计入下期（以发卡行规则为准）。",
        "sources": (),
    },
    "抖音月付": {
        "aliases": ("抖音月付",),
        "statement_day": 1,
        "due_day": 6,
        "due_offset_days": 5,
        "typical_due_days": (6, 15, 20),
        "summary": (
            "抖音月付按账单制：账单日常见为每月1/10/15日，还款日一般为账单日+5天"
            "（对应6/15/20日，可在抖音「还款助手」查看，每年可改一次）。"
            "支持一次性还或3/6/12期分期；部分交易需确认收货后入账。"
        ),
        "charge_rule": (
            "账单日当天及之前已入账消费通常计入本期；账单日次日起计入下期"
            "（以抖音月付账单页入账时间为准）。"
        ),
        "sources": (),
    },
    "美团月付": {
        "aliases": ("美团月付",),
        "statement_day": 1,
        "due_day": 10,
        "due_offset_days": None,
        "typical_due_days": (8, 9, 10),
        "summary": "美团月付按账单制还款，具体账单日/还款日以美团 App 月付页为准。",
        "charge_rule": "入账后计入对应账期，在当期还款日前还清；以 App 显示为准。",
        "sources": (),
    },
    "微信分付": {
        "aliases": ("微信分付", "分付"),
        "statement_day": 1,
        "due_day": 10,
        "due_offset_days": None,
        "typical_due_days": (8, 9, 10),
        "summary": "微信分付按账单还款，账单日与还款日以微信「分付」页为准。",
        "charge_rule": "消费入账后计入当期或下期账单，于还款日前还清。",
        "sources": (),
    },
}


def normalize_product(name: str | None) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    if "京东白条" in text or text == "白条":
        return "京东白条"
    if text.endswith("白条") and "京东" in text:
        return "京东白条"
    if "抖音月付" in text or ("抖音" in text and "月付" in text):
        return "抖音月付"
    if "美团月付" in text or ("美团" in text and "月付" in text):
        return "美团月付"
    if "分付" in text:
        return "微信分付"
    for canon, meta in REPAY_POLICIES.items():
        if text == canon or text in meta.get("aliases", ()):
            return canon
        if canon in text:
            return canon
    # 其它「xx月付」保留原名，仍按信用产品处理
    if text.endswith("月付"):
        return text
    return text


def is_credit_product(name: str | None) -> bool:
    n = normalize_product(name)
    if not n:
        return False
    if n in REPAY_POLICIES:
        return True
    return n.endswith("月付") or "分付" in n or "白条" in n or "花呗" in n


def _clamp_day(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(1, day), last))


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return _clamp_day(y, m, d.day)


def resolve_policy(
    product: str,
    *,
    statement_day: int | None = None,
    due_day: int | None = None,
    allow_generic: bool = False,
) -> dict | None:
    canon = normalize_product(product)
    base = REPAY_POLICIES.get(canon)
    if not base and canon.endswith("月付"):
        base = {
            "statement_day": 1,
            "due_day": 6,
            "due_offset_days": 5,
            "summary": (
                f"「{canon}」为先享后付类账单产品，账单日/还款日以对应 App 为准；"
                "暂按常见「账单日每月1日、还款日每月6日」拟定，请在确认卡中按实际修改。"
            ),
            "charge_rule": (
                "账单日当天及之前入账通常计入本期；之后计入下期（以 App 入账时间为准）。"
            ),
            "sources": (),
        }
    if not base and allow_generic and canon:
        base = {
            "statement_day": int(statement_day or 1),
            "due_day": int(due_day or 10),
            "due_offset_days": None,
            "summary": (
                f"「{canon}」已按信用/负债账户处理。公开还款制度未收录该产品，"
                "暂按每月还款日提醒；请按 App 实际账单日/还款日修改确认卡。"
            ),
            "charge_rule": "请以该信用产品 App 的账单周期为准判断本月/下月归属。",
            "sources": (),
        }
    if not base:
        return None
    s_day = int(statement_day or base["statement_day"])
    if due_day:
        d_day = int(due_day)
    elif base.get("due_offset_days") is not None:
        # 账单日 + offset，可能跨月
        probe = _clamp_day(2000, 1, s_day) + timedelta(days=int(base["due_offset_days"]))
        d_day = probe.day
    else:
        d_day = int(base["due_day"])
    return {
        "product": canon,
        "statement_day": s_day,
        "due_day": d_day,
        "due_offset_days": base.get("due_offset_days"),
        "summary": base["summary"],
        "charge_rule": base["charge_rule"],
        "sources": list(base.get("sources") or []),
        "user_overridden": bool(statement_day or due_day),
    }


def classify_charge(
    policy: dict,
    charge_on: date | None = None,
) -> dict:
    """判断消费计入哪一期账单，并给出对应还款日。"""
    charge_on = charge_on or date.today()
    s_day = int(policy["statement_day"])
    d_day = int(policy["due_day"])
    product = policy["product"]

    # 本期账单日（本月）
    this_statement = _clamp_day(charge_on.year, charge_on.month, s_day)
    # 京东白条等：账单日当天及之后 → 下期；花呗/普通信用卡：账单日当天计入本期
    same_day_counts_current = product != "京东白条"

    if same_day_counts_current:
        in_current = charge_on <= this_statement
    else:
        in_current = charge_on < this_statement

    if in_current:
        statement_date = this_statement
        period = "本月账单"
    else:
        statement_date = _add_months(this_statement, 1)
        period = "下月账单"

    due_date = _clamp_day(statement_date.year, statement_date.month, d_day)
    # 还款日若制度上晚于账单日且 due_day < statement_day，则在账单月的下一月
    if due_date <= statement_date and policy.get("due_offset_days"):
        due_date = statement_date + timedelta(days=int(policy["due_offset_days"]))
    elif due_date < statement_date:
        due_date = _add_months(due_date, 1)

    explain = (
        f"「{product}」默认账单日每月{s_day}日、还款日每月{d_day}日"
        f"{'（可按你 App 实际日期修改确认卡）' if not policy.get('user_overridden') else ''}。"
        f"本笔按入账日 {charge_on.isoformat()} 判断：计入【{period}】"
        f"（出账 {statement_date.isoformat()}，建议还款日 {due_date.isoformat()}）。"
        f"规则：{policy['charge_rule']}"
    )
    return {
        "period": period,
        "in_current_bill": in_current,
        "statement_date": statement_date.isoformat(),
        "due_date": due_date.isoformat(),
        "due_at": f"{due_date.isoformat()}T10:00",
        "explain": explain,
        "summary": policy["summary"],
    }


def parse_installment(text: str, total: float | None = None) -> dict | None:
    """解析「分3期 / 分期3期 / 每期100」。"""
    text = text or ""
    m = re.search(r"分\s*(\d{1,2})\s*期|分期\s*(\d{1,2})\s*期?|(\d{1,2})\s*期分期", text)
    if not m:
        return None
    periods = int(m.group(1) or m.group(2) or m.group(3))
    if periods < 2 or periods > 36:
        return None
    per = None
    m_pay = re.search(r"每期\s*(\d+(?:\.\d{1,2})?)", text)
    if m_pay:
        per = float(m_pay.group(1))
    elif total and total > 0:
        per = float(
            (Decimal(str(total)) / Decimal(periods)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    return {"periods": periods, "per_amount": per, "total": total}


def build_installment_reminders(
    product: str,
    *,
    total: float,
    periods: int,
    first_due: date,
    per_amount: float | None = None,
) -> list[dict]:
    """生成每一期的提醒草稿（不自动循环，逐期一张）。"""
    if periods < 2:
        return []
    if per_amount is None:
        per_amount = float(
            (Decimal(str(total)) / Decimal(periods)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    # 尾差落在最后一期
    amounts = [per_amount] * (periods - 1)
    last = float(
        (Decimal(str(total)) - Decimal(str(per_amount)) * (periods - 1)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    amounts.append(last)
    out = []
    for i, amt in enumerate(amounts, start=1):
        due = _add_months(first_due, i - 1)
        out.append(
            {
                "intent": "reminder",
                "data": {
                    "title": f"还{product}第{i}/{periods}期 {amt:g}元",
                    "due_at": f"{due.isoformat()}T10:00",
                    "type": "bill",
                    "note": f"分期{periods}期；本金合计{total:g}；第{i}期{amt:g}元",
                    "repeat": "none",
                    "linked_asset_name": product,
                    "installment": {
                        "index": i,
                        "periods": periods,
                        "amount": amt,
                        "total": total,
                    },
                },
            }
        )
    return out


def build_monthly_reminder(product: str, due_day: int, *, note: str = "") -> dict:
    today = date.today()
    due = _clamp_day(today.year, today.month, due_day)
    if due < today:
        due = _add_months(due, 1)
    return {
        "intent": "reminder",
        "data": {
            "title": f"还{product}",
            "due_at": f"{due.isoformat()}T10:00",
            "type": "bill",
            "note": (note or f"每月{due_day}号还款（周期提醒）")[:200],
            "repeat": "monthly",
            "linked_asset_name": product,
        },
    }


def extract_due_day_from_reminders(product: str, reminders: list[dict] | None) -> int | None:
    """从已有提醒推断用户还款日。"""
    canon = normalize_product(product)
    for r in reminders or []:
        if not isinstance(r, dict):
            continue
        linked = r.get("linked_asset_name") or ""
        title = r.get("title") or ""
        note = r.get("note") or ""
        if normalize_product(linked) != canon and canon not in title:
            continue
        m = re.search(r"每月\s*(\d{1,2})\s*[日号]", f"{title} {note}")
        if m:
            return int(m.group(1))
        due_raw = (r.get("due_at") or "")[:10]
        try:
            return datetime.strptime(due_raw, "%Y-%m-%d").day
        except ValueError:
            continue
    return None


def has_monthly_reminder(product: str, reminders: list[dict] | None) -> bool:
    canon = normalize_product(product)
    for r in reminders or []:
        if not isinstance(r, dict):
            continue
        linked = normalize_product(r.get("linked_asset_name") or "")
        title = r.get("title") or ""
        repeat = (r.get("repeat") or r.get("recurrence") or "none").lower()
        if linked == canon or canon in title:
            if repeat == "monthly":
                return True
    return False


def fetch_policy_snippet(product: str, timeout: float = 4.0) -> str:
    """尝试联网抓取帮助页文本片段；失败返回空。"""
    policy = REPAY_POLICIES.get(normalize_product(product))
    if not policy:
        return ""
    snippets = []
    for url in policy.get("sources") or []:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "VitaBot/1.0 (+repay-policy)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(80000)
            text = raw.decode("utf-8", errors="ignore")
            text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            if "账单" in text or "还款" in text:
                snippets.append(text[:400])
        except Exception as e:
            logger.info("repay policy fetch failed %s: %s", url, e)
    return " ".join(snippets)[:600]


def enrich_explain_with_web(policy: dict, classification: dict) -> str:
    web = fetch_policy_snippet(policy["product"])
    base = classification["explain"]
    if not web:
        return (
            f"{base}\n【制度说明】{policy['summary']}"
            "（已用内置公开规则；若与你 App 不一致，请改确认卡上的还款日。）"
        )
    return (
        f"{base}\n【制度说明】{policy['summary']}\n"
        f"【联网摘录】{web[:280]}…"
        "（摘录仅供参考，最终以你 App 账单页为准，可改确认卡日期。）"
    )


def infer_statement_day(product: str, due_day: int) -> int:
    """由还款日反推常见账单日。"""
    canon = normalize_product(product)
    d = int(due_day)
    if canon == "花呗":
        return {8: 1, 9: 1, 10: 1, 15: 5, 20: 10}.get(d, 1)
    if canon == "京东白条":
        # 还款日 ≈ 账单日 + 9
        s = d - 9
        if s <= 0:
            s += 28  # 粗略跨月
        return min(max(s, 1), 28)
    if canon == "抖音月付" or canon.endswith("月付"):
        # 还款日 ≈ 账单日 + 5
        return {6: 1, 15: 10, 20: 15}.get(d, max(1, d - 5))
    if canon == "信用卡":
        return max(1, d - 18) if d > 18 else 1
    return 1


def policy_to_setting_key(product: str) -> str:
    canon = normalize_product(product) or (product or "").strip()
    return f"repay_cycle:{canon}"


def load_user_cycle(get_setting, user_id: int, product: str) -> tuple[int | None, int | None]:
    """从 settings 读取用户自定义账单日/还款日。"""
    try:
        raw = get_setting(user_id, policy_to_setting_key(product))
        if not raw:
            return None, None
        obj = json.loads(raw)
        s = obj.get("statement_day")
        d = obj.get("due_day")
        return (int(s) if s else None, int(d) if d else None)
    except Exception:
        return None, None
