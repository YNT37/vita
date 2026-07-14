"use client";

import { useState } from "react";

export type ConfirmIntent = "transaction" | "reminder" | "balance";

export type ConfirmDraft = {
  // transaction
  type?: "income" | "expense";
  amount?: string;
  category?: string;
  note?: string;
  date?: string;
  // reminder
  title?: string;
  due_at?: string;
  remType?: "bill" | "life" | "anniversary";
  repeat?: "none" | "monthly" | "weekly";
  linked_asset_name?: string;
  // balance
  name?: string;
  balance?: string;
  kind?: "asset" | "liability";
};

export type PendingAction = {
  intent: ConfirmIntent;
  data: Record<string, unknown>;
};

export type ConfirmCardState = {
  id: string;
  intent: ConfirmIntent;
  draft: ConfirmDraft;
  status: "pending" | "done" | "dismissed";
};

const inputCls =
  "w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-blue-500";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function toDatetimeLocal(raw: unknown): string {
  const s = String(raw || "").trim();
  if (!s) {
    const d = new Date(Date.now() + 86400000);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T10:00`;
  }
  const normalized = s.replace("Z", "").replace(" ", "T").slice(0, 16);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(normalized)) return normalized;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s.slice(0, 10))) return `${s.slice(0, 10)}T10:00`;
  return normalized;
}

export function pendingToCard(action: PendingAction, id: string): ConfirmCardState {
  const data = action.data || {};
  if (action.intent === "transaction") {
    return {
      id,
      intent: "transaction",
      status: "pending",
      draft: {
        type: data.type === "income" ? "income" : "expense",
        amount: String(data.amount ?? ""),
        category: String(data.category ?? "其他"),
        note: String(data.note ?? ""),
        date: String(data.date || todayISO()).slice(0, 10),
      },
    };
  }
  if (action.intent === "reminder") {
    const remType = String(data.type || "life");
    const repeatRaw = String(data.repeat || "none");
    const repeat =
      repeatRaw === "monthly" || repeatRaw === "weekly" ? repeatRaw : "none";
    return {
      id,
      intent: "reminder",
      status: "pending",
      draft: {
        title: String(data.title ?? ""),
        due_at: toDatetimeLocal(data.due_at),
        remType:
          remType === "bill" || remType === "anniversary" ? remType : "life",
        repeat,
        linked_asset_name: String(data.linked_asset_name ?? ""),
        note: String(data.note ?? ""),
      },
    };
  }
  return {
    id,
    intent: "balance",
    status: "pending",
    draft: {
      name: String(data.name ?? "资产"),
      balance: String(data.balance ?? ""),
      kind:
        data.kind === "liability" ||
        /花呗|白条|借呗|信用卡|负债|欠款|贷款/.test(String(data.name ?? "")) ||
        String(data.note ?? "").includes("负债")
          ? "liability"
          : "asset",
      note: String(data.note ?? ""),
    },
  };
}

export function draftToBody(card: ConfirmCardState): Record<string, unknown> {
  const d = card.draft;
  if (card.intent === "transaction") {
    return {
      type: d.type || "expense",
      amount: Number(d.amount),
      category: (d.category || "其他").trim(),
      note: (d.note || "").trim(),
      date: (d.date || todayISO()).slice(0, 10),
    };
  }
  if (card.intent === "reminder") {
    return {
      title: (d.title || "").trim(),
      due_at: (d.due_at || "").trim(),
      type: d.remType || "life",
      note: (d.note || "").trim(),
      repeat: d.repeat || "none",
      linked_asset_name: (d.linked_asset_name || "").trim(),
    };
  }
  return {
    name: (d.name || "资产").trim(),
    balance: Number(d.balance),
    kind: d.kind || "asset",
    note: (d.note || "").trim(),
  };
}

const TITLES: Record<ConfirmIntent, string> = {
  transaction: "确认记账",
  reminder: "确认提醒",
  balance: "确认账户余额",
};

type Props = {
  card: ConfirmCardState;
  busy?: boolean;
  onChange: (id: string, draft: ConfirmDraft) => void;
  onConfirm: (id: string) => void;
  onDismiss: (id: string) => void;
};

export function ConfirmCard({ card, busy, onChange, onConfirm, onDismiss }: Props) {
  const [localBusy, setLocalBusy] = useState(false);
  const disabled = busy || localBusy || card.status !== "pending";

  if (card.status === "dismissed") return null;

  if (card.status === "done") {
    return (
      <div className="w-full max-w-md rounded-2xl border border-green-200 dark:border-green-900 bg-green-50/80 dark:bg-green-950/30 px-3 py-2 text-sm text-green-700 dark:text-green-300">
        已写入 · {TITLES[card.intent].replace("确认", "")}
      </div>
    );
  }

  function setDraft(patch: Partial<ConfirmDraft>) {
    onChange(card.id, { ...card.draft, ...patch });
  }

  async function handleConfirm() {
    setLocalBusy(true);
    try {
      await onConfirm(card.id);
    } finally {
      setLocalBusy(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-blue-200 dark:border-blue-900 bg-[var(--background)] shadow-sm p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300">
          {TITLES[card.intent]}
        </h3>
        <span className="text-[11px] text-gray-400">可编辑 · 确定后写入</span>
      </div>

      {card.intent === "transaction" && (
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-gray-500 space-y-1">
            <span>类型</span>
            <select
              className={inputCls}
              value={card.draft.type || "expense"}
              disabled={disabled}
              onChange={(e) =>
                setDraft({ type: e.target.value as "income" | "expense" })
              }
            >
              <option value="expense">支出</option>
              <option value="income">收入</option>
            </select>
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>金额</span>
            <input
              className={inputCls}
              type="number"
              step="0.01"
              min="0"
              value={card.draft.amount || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ amount: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>分类</span>
            <input
              className={inputCls}
              value={card.draft.category || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ category: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>日期</span>
            <input
              className={inputCls}
              type="date"
              value={card.draft.date || todayISO()}
              disabled={disabled}
              onChange={(e) => setDraft({ date: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1 sm:col-span-2">
            <span>备注</span>
            <input
              className={inputCls}
              value={card.draft.note || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ note: e.target.value })}
            />
          </label>
        </div>
      )}

      {card.intent === "reminder" && (
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-gray-500 space-y-1 sm:col-span-2">
            <span>标题</span>
            <input
              className={inputCls}
              value={card.draft.title || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ title: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>到期时间</span>
            <input
              className={inputCls}
              type="datetime-local"
              value={card.draft.due_at || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ due_at: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>类型</span>
            <select
              className={inputCls}
              value={card.draft.remType || "life"}
              disabled={disabled}
              onChange={(e) =>
                setDraft({
                  remType: e.target.value as "bill" | "life" | "anniversary",
                })
              }
            >
              <option value="life">生活</option>
              <option value="bill">账单/还款</option>
              <option value="anniversary">纪念日</option>
            </select>
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>周期</span>
            <select
              className={inputCls}
              value={card.draft.repeat || "none"}
              disabled={disabled}
              onChange={(e) =>
                setDraft({
                  repeat: e.target.value as "none" | "monthly" | "weekly",
                })
              }
            >
              <option value="none">仅一次</option>
              <option value="monthly">每月重复</option>
              <option value="weekly">每周重复</option>
            </select>
          </label>
          <label className="text-xs text-gray-500 space-y-1 sm:col-span-2">
            <span>关联欠款账户（到期自动带上当前欠款）</span>
            <input
              className={inputCls}
              value={card.draft.linked_asset_name || ""}
              disabled={disabled}
              placeholder="例如：花呗"
              onChange={(e) => setDraft({ linked_asset_name: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1 sm:col-span-2">
            <span>备注</span>
            <input
              className={inputCls}
              value={card.draft.note || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ note: e.target.value })}
            />
          </label>
        </div>
      )}

      {card.intent === "balance" && (
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-gray-500 space-y-1">
            <span>账户名</span>
            <input
              className={inputCls}
              value={card.draft.name || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ name: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>余额</span>
            <input
              className={inputCls}
              type="number"
              step="0.01"
              value={card.draft.balance || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ balance: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>类型</span>
            <select
              className={inputCls}
              value={card.draft.kind || "asset"}
              disabled={disabled}
              onChange={(e) =>
                setDraft({ kind: e.target.value as "asset" | "liability" })
              }
            >
              <option value="asset">资产</option>
              <option value="liability">负债</option>
            </select>
          </label>
          <label className="text-xs text-gray-500 space-y-1">
            <span>备注</span>
            <input
              className={inputCls}
              value={card.draft.note || ""}
              disabled={disabled}
              onChange={(e) => setDraft({ note: e.target.value })}
            />
          </label>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          disabled={disabled}
          onClick={handleConfirm}
          className="rounded-lg bg-blue-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
        >
          {localBusy ? "写入中…" : "确定"}
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onDismiss(card.id)}
          className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-sm text-gray-500 hover:bg-black/5 disabled:opacity-60"
        >
          取消
        </button>
      </div>
    </div>
  );
}
