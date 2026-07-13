"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api";

type TxnType = "income" | "expense";

type OverviewData = {
  month: string;
  stats: {
    income: number;
    expense: number;
    balance: number;
    byCategory: { category: string; type: TxnType; amount: number }[];
    byDay: { date: string; income: number; expense: number }[];
  };
  assets: { id: number; name: string; balance: number; note: string; updated_at: string | null }[];
  assets_total: number;
  reminders_pending: {
    id: number;
    title: string;
    due_at: string;
    type: string;
    done: boolean;
  }[];
  reminders_overdue_count: number;
  categories: { expense: string[]; income: string[] };
};

type CategoryRow = { id: number; name: string; kind: TxnType };

type Tab = "overview" | "assets" | "reminders" | "categories";

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

function formatMoney(n: number) {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDue(iso: string) {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "概览" },
  { id: "assets", label: "资产" },
  { id: "reminders", label: "待办" },
  { id: "categories", label: "分类" },
];

export default function StatsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [month, setMonth] = useState(currentMonth);
  const [data, setData] = useState<OverviewData | null>(null);
  const [categoryRows, setCategoryRows] = useState<CategoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const [assetName, setAssetName] = useState("");
  const [assetBalance, setAssetBalance] = useState("");
  const [newCatName, setNewCatName] = useState("");
  const [newCatKind, setNewCatKind] = useState<TxnType>("expense");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [overview, cats] = await Promise.all([
        apiFetch<OverviewData>(`/api/overview?month=${month}`),
        apiFetch<CategoryRow[]>("/api/categories"),
      ]);
      setData(overview);
      setCategoryRows(cats);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  async function saveAsset(e: React.FormEvent) {
    e.preventDefault();
    const balance = Number(assetBalance);
    if (!assetName.trim() || Number.isNaN(balance) || balance < 0) {
      setError("请填写资产名称和有效余额");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/assets", {
        method: "POST",
        body: { name: assetName.trim(), balance, note: "" },
      });
      setAssetName("");
      setAssetBalance("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function removeAsset(id: number) {
    setError("");
    try {
      await apiFetch(`/api/assets/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  async function addCategory(e: React.FormEvent) {
    e.preventDefault();
    if (!newCatName.trim()) return;
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/categories", {
        method: "POST",
        body: { name: newCatName.trim(), kind: newCatKind },
      });
      setNewCatName("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "添加失败");
    } finally {
      setSaving(false);
    }
  }

  async function removeCategory(id: number) {
    setError("");
    try {
      await apiFetch(`/api/categories/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>;
  }

  const maxCat = Math.max(...(data?.stats.byCategory.map((c) => c.amount) ?? [1]), 1);

  return (
    <main className="flex-1 p-4 max-w-2xl mx-auto w-full pb-4">
      <header className="mb-4">
        <h1 className="text-xl font-semibold">统计中心</h1>
        <p className="text-sm text-gray-500">资产 · 待办 · 分类 · 收支概览</p>
      </header>

      <div className="flex items-center gap-3 mb-4">
        <input
          type="month"
          className="rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-blue-500"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
      </div>

      <div className="flex gap-1 mb-4 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-sm border transition-colors ${
              tab === t.id
                ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/30"
                : "border-black/15 dark:border-white/20 text-gray-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-sm text-red-500 mb-3 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">加载中…</p>
      ) : !data ? null : (
        <>
          {tab === "overview" && (
            <div className="space-y-4">
              <section className="grid gap-3 sm:grid-cols-3">
                <StatCard label="本月收入" value={data.stats.income} color="text-green-600" />
                <StatCard label="本月支出" value={data.stats.expense} color="text-red-500" />
                <StatCard
                  label="本月结余"
                  value={data.stats.balance}
                  color={data.stats.balance >= 0 ? "text-blue-600" : "text-red-500"}
                />
              </section>

              <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
                <h2 className="text-sm font-medium text-gray-500 mb-2">资产总览</h2>
                <p className="text-2xl font-semibold text-blue-600">¥{formatMoney(data.assets_total)}</p>
                <p className="text-xs text-gray-400 mt-1">{data.assets.length} 个账户</p>
              </section>

              {data.stats.byCategory.length > 0 && (
                <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
                  <h2 className="text-sm font-medium text-gray-500 mb-3">分类支出/收入</h2>
                  <ul className="space-y-2">
                    {data.stats.byCategory.map((c) => (
                      <li key={`${c.category}-${c.type}`}>
                        <div className="flex justify-between text-sm mb-1">
                          <span>
                            {c.category}
                            <span className="text-gray-400 ml-1">
                              {c.type === "income" ? "收入" : "支出"}
                            </span>
                          </span>
                          <span className={c.type === "income" ? "text-green-600" : "text-red-500"}>
                            ¥{formatMoney(c.amount)}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              c.type === "income" ? "bg-green-500" : "bg-red-400"
                            }`}
                            style={{ width: `${Math.min(100, (c.amount / maxCat) * 100)}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {data.stats.byDay.length > 0 && (
                <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
                  <h2 className="text-sm font-medium text-gray-500 mb-3">每日趋势</h2>
                  <ul className="space-y-1 text-sm">
                    {data.stats.byDay.slice(-7).map((d) => (
                      <li key={d.date} className="flex justify-between">
                        <span className="text-gray-500">{d.date.slice(5)}</span>
                        <span>
                          <span className="text-green-600">+{formatMoney(d.income)}</span>
                          <span className="text-gray-300 mx-1">/</span>
                          <span className="text-red-500">-{formatMoney(d.expense)}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}

          {tab === "assets" && (
            <div className="space-y-4">
              <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
                <h2 className="text-sm font-medium mb-3">添加/更新账户</h2>
                <form onSubmit={saveAsset} className="flex flex-col gap-2 sm:flex-row">
                  <input
                    className="flex-1 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                    placeholder="账户名（基金、余额宝…）"
                    value={assetName}
                    onChange={(e) => setAssetName(e.target.value)}
                  />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="w-full sm:w-32 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                    placeholder="余额"
                    value={assetBalance}
                    onChange={(e) => setAssetBalance(e.target.value)}
                  />
                  <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm disabled:opacity-60"
                  >
                    保存
                  </button>
                </form>
                <p className="text-xs text-gray-400 mt-2">同名账户会更新余额；AI 对话也可自动记入。</p>
              </section>

              <section>
                <h2 className="text-sm font-medium text-gray-500 mb-2">
                  账户列表 · 合计 ¥{formatMoney(data.assets_total)}
                </h2>
                {data.assets.length === 0 ? (
                  <p className="text-sm text-gray-400 border border-dashed rounded-xl p-6 text-center">
                    暂无资产记录
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.assets.map((a) => (
                      <li
                        key={a.id}
                        className="rounded-xl border border-black/10 dark:border-white/15 p-3 flex items-center justify-between"
                      >
                        <div>
                          <p className="font-medium">{a.name}</p>
                          <p className="text-xs text-gray-400">
                            {a.updated_at ? formatDue(a.updated_at) : ""}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-blue-600">¥{formatMoney(a.balance)}</span>
                          <button
                            type="button"
                            onClick={() => removeAsset(a.id)}
                            className="text-xs text-red-500 hover:underline"
                          >
                            删除
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}

          {tab === "reminders" && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-gray-500">
                  待办 {data.reminders_pending.length} 条
                  {data.reminders_overdue_count > 0 && (
                    <span className="text-red-500 ml-2">逾期 {data.reminders_overdue_count}</span>
                  )}
                </h2>
                <Link href="/reminders" className="text-xs text-blue-600 hover:underline">
                  去提醒页管理 →
                </Link>
              </div>
              {data.reminders_pending.length === 0 ? (
                <p className="text-sm text-gray-400 border border-dashed rounded-xl p-6 text-center">
                  暂无待办
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.reminders_pending.map((r) => {
                    const overdue = new Date(r.due_at) < new Date();
                    return (
                      <li
                        key={r.id}
                        className={`rounded-xl border p-3 ${
                          overdue
                            ? "border-red-300 bg-red-50/50 dark:bg-red-950/20"
                            : "border-black/10 dark:border-white/15"
                        }`}
                      >
                        <p className="font-medium text-sm">{r.title}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{formatDue(r.due_at)}</p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          )}

          {tab === "categories" && (
            <div className="space-y-4">
              <form onSubmit={addCategory} className="rounded-2xl border border-black/10 dark:border-white/15 p-4 flex flex-wrap gap-2">
                <select
                  className="rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm"
                  value={newCatKind}
                  onChange={(e) => setNewCatKind(e.target.value as TxnType)}
                >
                  <option value="expense">支出</option>
                  <option value="income">收入</option>
                </select>
                <input
                  className="flex-1 min-w-[120px] rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                  placeholder="新分类名"
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm disabled:opacity-60"
                >
                  添加
                </button>
              </form>

              {(["expense", "income"] as TxnType[]).map((kind) => (
                <section key={kind} className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
                  <h2 className="text-sm font-medium text-gray-500 mb-2">
                    {kind === "expense" ? "支出分类" : "收入分类"}
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {categoryRows
                      .filter((c) => c.kind === kind)
                      .map((c) => (
                        <span
                          key={c.id}
                          className="inline-flex items-center gap-1 rounded-full border border-black/15 dark:border-white/20 px-3 py-1 text-sm"
                        >
                          {c.name}
                          <button
                            type="button"
                            onClick={() => removeCategory(c.id)}
                            className="text-gray-400 hover:text-red-500 text-xs"
                            aria-label={`删除${c.name}`}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                  </div>
                </section>
              ))}
              <p className="text-xs text-gray-400">分类会同步给 AI，记账时优先匹配这些名称。</p>
            </div>
          )}
        </>
      )}
    </main>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-semibold ${color}`}>¥{formatMoney(value)}</p>
    </div>
  );
}
