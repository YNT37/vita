"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useAutoReload, useDataRefresh } from "@/lib/data-refresh";
import { apiFetch, ApiError } from "@/lib/api";
import { PageContainer } from "@/components/PageContainer";

type TxnType = "income" | "expense";

type Transaction = {
  id: number;
  type: TxnType;
  amount: number;
  category: string;
  note: string;
  account?: string;
  date: string;
};

type StatsSummary = {
  income: number;
  expense: number;
  byCategory: { category: string; type: TxnType; amount: number }[];
  byDay: { date: string; income: number; expense: number }[];
};

const TYPE_LABELS: Record<TxnType, string> = {
  income: "收入",
  expense: "支出",
};

const QUICK_CATEGORIES = ["餐饮", "交通", "购物", "居住", "工资", "其他"];

type CategoryRow = { id: number; name: string; kind: TxnType };

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

function todayDate(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function formatMoney(n: number): string {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function RecordsPage() {
  const { user, loading: authLoading } = useAuth();
  const { bump } = useDataRefresh();
  const router = useRouter();

  const [month, setMonth] = useState(currentMonth);
  const [items, setItems] = useState<Transaction[]>([]);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [type, setType] = useState<TxnType>("expense");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("餐饮");
  const [categories, setCategories] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [date, setDate] = useState(todayDate);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [list, summary] = await Promise.all([
        apiFetch<Transaction[]>(`/api/transactions?month=${month}`),
        apiFetch<StatsSummary>(`/api/stats/summary?month=${month}`),
      ]);
      setItems(list);
      setStats(summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useAutoReload(load, !!user);

  useEffect(() => {
    if (!user) return;
    apiFetch<CategoryRow[]>(`/api/categories?kind=${type}`)
      .then((cats) => {
        const names = cats.map((c) => c.name);
        setCategories(names.length > 0 ? names : QUICK_CATEGORIES);
        setCategory((prev) => (names.includes(prev) ? prev : names[0] || prev));
      })
      .catch(() => setCategories(QUICK_CATEGORIES));
  }, [user, type]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const num = Number(amount);
    if (!amount || Number.isNaN(num) || num <= 0) {
      setError("请填写有效金额（大于 0）");
      return;
    }
    if (!category.trim()) {
      setError("请填写分类");
      return;
    }
    if (!date) {
      setError("请选择日期");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch<Transaction>("/api/transactions", {
        method: "POST",
        body: {
          type,
          amount: num,
          category: category.trim(),
          note: note.trim(),
          date,
        },
      });
      setAmount("");
      setNote("");
      bump();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "记账失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: number) {
    setError("");
    try {
      await apiFetch(`/api/transactions/${id}`, { method: "DELETE" });
      bump();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  const balance = (stats?.income ?? 0) - (stats?.expense ?? 0);

  return (
    <PageContainer wide>
      <header className="mb-4 sm:mb-6">
        <h1 className="text-xl sm:text-2xl font-semibold">记账理财</h1>
        <p className="text-sm text-gray-500">
          记一笔收支流水。账户余额/负债请到{" "}
          <a href="/stats" className="text-blue-600 hover:underline">
            统计 → 资产
          </a>{" "}
          查看。
        </p>
      </header>

      <div className="flex items-center gap-3 mb-6">
        <label className="text-sm text-gray-500">查看月份</label>
        <input
          type="month"
          className="rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-blue-500"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
      </div>

      {stats && (
        <section className="grid gap-3 grid-cols-2 sm:grid-cols-3 mb-6">
          <StatCard label="本月收入" value={formatMoney(stats.income)} color="text-green-600" />
          <StatCard label="本月支出" value={formatMoney(stats.expense)} color="text-red-500" />
          <StatCard
            label="结余"
            value={formatMoney(balance)}
            color={balance >= 0 ? "text-blue-600" : "text-red-500"}
          />
        </section>
      )}

      {stats && stats.byCategory.length > 0 && (
        <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 mb-6">
          <h2 className="text-sm font-medium text-gray-500 mb-3">分类统计</h2>
          <ul className="space-y-2">
            {stats.byCategory.map((c) => (
              <li key={`${c.category}-${c.type}`} className="flex justify-between text-sm">
                <span>
                  {c.category}
                  <span className="text-gray-400 ml-2">{TYPE_LABELS[c.type]}</span>
                </span>
                <span className={c.type === "income" ? "text-green-600" : "text-red-500"}>
                  {c.type === "income" ? "+" : "-"}
                  {formatMoney(c.amount)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-2xl border border-black/10 dark:border-white/15 p-5 mb-6">
        <h2 className="font-medium mb-4">记一笔</h2>
        <form onSubmit={onCreate} className="space-y-3">
          <div className="flex gap-2">
            {(["expense", "income"] as TxnType[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setType(t)}
                className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-colors ${
                  type === t
                    ? t === "expense"
                      ? "border-red-400 bg-red-50 text-red-600 dark:bg-red-950/30"
                      : "border-green-400 bg-green-50 text-green-600 dark:bg-green-950/30"
                    : "border-black/15 dark:border-white/20 text-gray-500"
                }`}
              >
                {TYPE_LABELS[t]}
              </button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-sm mb-1">金额</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-sm mb-1">日期</label>
              <input
                type="date"
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="block text-sm mb-1">分类</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategory(c)}
                  className={`text-xs rounded-full px-3 py-1 border transition-colors ${
                    category === c
                      ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-950/30"
                      : "border-black/15 dark:border-white/20 text-gray-500"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
            <input
              className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="或自定义分类"
            />
          </div>
          <div>
            <label className="block text-sm mb-1">备注（可选）</label>
            <input
              className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="例如：午饭"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            {submitting ? "提交中…" : "确认记账"}
          </button>
        </form>
      </section>

      {error && (
        <p className="text-sm text-red-500 mb-4 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2">
          {error}
        </p>
      )}

      <section>
        <h2 className="font-medium mb-3">交易记录</h2>
        {loading ? (
          <p className="text-sm text-gray-500">加载中…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-gray-500 rounded-xl border border-dashed border-black/15 dark:border-white/20 p-6 text-center">
            本月还没有记录，记一笔吧
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.id}
                className="rounded-xl border border-black/10 dark:border-white/15 p-4 flex items-center gap-3"
              >
                <div
                  className={`w-10 h-10 rounded-full grid place-items-center text-sm font-medium shrink-0 ${
                    item.type === "income"
                      ? "bg-green-50 text-green-600 dark:bg-green-950/30"
                      : "bg-red-50 text-red-500 dark:bg-red-950/30"
                  }`}
                >
                  {item.type === "income" ? "+" : "-"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{item.category}</span>
                    {item.account && (
                      <span className="text-xs text-gray-500 shrink-0">
                        {item.account}
                      </span>
                    )}
                    {item.note && (
                      <span className="text-sm text-gray-400 truncate">{item.note}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">{item.date}</p>
                </div>
                <span
                  className={`font-medium shrink-0 ${
                    item.type === "income" ? "text-green-600" : "text-red-500"
                  }`}
                >
                  {item.type === "income" ? "+" : "-"}
                  {formatMoney(item.amount)}
                </span>
                <button
                  type="button"
                  onClick={() => remove(item.id)}
                  className="text-sm text-red-500 hover:underline shrink-0"
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-semibold ${color}`}>¥{value}</p>
    </div>
  );
}
