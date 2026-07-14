"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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

function parseType(raw: string | null): TxnType | "" {
  if (raw === "income" || raw === "expense") return raw;
  return "";
}

export default function RecordsPage() {
  return (
    <Suspense
      fallback={
        <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
      }
    >
      <RecordsPageInner />
    </Suspense>
  );
}

function RecordsPageInner() {
  const { user, loading: authLoading } = useAuth();
  const { bump } = useDataRefresh();
  const router = useRouter();
  const searchParams = useSearchParams();

  const initialMonth = searchParams.get("month") || currentMonth();
  const initialType = parseType(searchParams.get("type"));
  const initialAccount = (searchParams.get("account") || "").trim();
  const initialCategory = (searchParams.get("category") || "").trim();

  const [month, setMonth] = useState(initialMonth);
  const [filterType, setFilterType] = useState<TxnType | "">(initialType);
  const [filterAccount, setFilterAccount] = useState(initialAccount);
  const [filterCategory, setFilterCategory] = useState(initialCategory);
  const [items, setItems] = useState<Transaction[]>([]);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [type, setType] = useState<TxnType>(initialType || "expense");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("餐饮");
  const [categories, setCategories] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [date, setDate] = useState(todayDate);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  // URL → 筛选状态（从统计中心跳转时）
  useEffect(() => {
    const m = searchParams.get("month");
    if (m) setMonth(m);
    setFilterType(parseType(searchParams.get("type")));
    setFilterAccount((searchParams.get("account") || "").trim());
    setFilterCategory((searchParams.get("category") || "").trim());
  }, [searchParams]);

  const listQuery = useMemo(() => {
    const q = new URLSearchParams();
    if (month) q.set("month", month);
    if (filterType) q.set("type", filterType);
    if (filterAccount) q.set("account", filterAccount);
    if (filterCategory) q.set("category", filterCategory);
    return q.toString();
  }, [month, filterType, filterAccount, filterCategory]);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [list, summary] = await Promise.all([
        apiFetch<Transaction[]>(`/api/transactions?${listQuery}`),
        apiFetch<StatsSummary>(`/api/stats/summary?month=${month}`),
      ]);
      setItems(list);
      setStats(summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [listQuery, month]);

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

  function syncUrl(next: {
    month?: string;
    type?: TxnType | "";
    account?: string;
    category?: string;
  }) {
    const q = new URLSearchParams();
    const m = next.month ?? month;
    const t = next.type !== undefined ? next.type : filterType;
    const a = next.account !== undefined ? next.account : filterAccount;
    const c = next.category !== undefined ? next.category : filterCategory;
    if (m) q.set("month", m);
    if (t) q.set("type", t);
    if (a) q.set("account", a);
    if (c) q.set("category", c);
    const qs = q.toString();
    router.replace(qs ? `/records?${qs}` : "/records");
  }

  function clearFilters() {
    setFilterType("");
    setFilterAccount("");
    setFilterCategory("");
    syncUrl({ type: "", account: "", category: "" });
  }

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
          ...(filterAccount ? { account: filterAccount } : {}),
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
  const hasFilters = Boolean(filterType || filterAccount || filterCategory);

  const listTitle = [
    filterAccount ? `账户「${filterAccount}」` : null,
    filterType ? TYPE_LABELS[filterType] : null,
    filterCategory ? `分类「${filterCategory}」` : null,
    "交易记录",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <PageContainer wide>
      <header className="mb-4 sm:mb-6">
        <h1 className="text-xl sm:text-2xl font-semibold">记账理财</h1>
        <p className="text-sm text-gray-500">
          记一笔收支流水。账户余额/负债请到{" "}
          <a href="/stats?tab=assets" className="text-blue-600 hover:underline">
            统计 → 账户
          </a>{" "}
          查看。
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <label className="text-sm text-gray-500">查看月份</label>
        <input
          type="month"
          className="rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-blue-500"
          value={month}
          onChange={(e) => {
            setMonth(e.target.value);
            syncUrl({ month: e.target.value });
          }}
        />
        <select
          className="rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-blue-500"
          value={filterType}
          onChange={(e) => {
            const v = parseType(e.target.value);
            setFilterType(v);
            syncUrl({ type: v });
          }}
        >
          <option value="">全部类型</option>
          <option value="income">收入</option>
          <option value="expense">支出</option>
        </select>
      </div>

      {hasFilters && (
        <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
          <span className="text-gray-500">当前筛选：</span>
          {filterAccount && (
            <span className="rounded-full bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 px-2.5 py-0.5">
              账户 {filterAccount}
            </span>
          )}
          {filterType && (
            <span className="rounded-full bg-gray-100 dark:bg-white/10 px-2.5 py-0.5">
              {TYPE_LABELS[filterType]}
            </span>
          )}
          {filterCategory && (
            <span className="rounded-full bg-gray-100 dark:bg-white/10 px-2.5 py-0.5">
              {filterCategory}
            </span>
          )}
          <button
            type="button"
            onClick={clearFilters}
            className="text-blue-600 hover:underline"
          >
            清除筛选
          </button>
        </div>
      )}

      {stats && !hasFilters && (
        <section className="grid gap-3 grid-cols-2 sm:grid-cols-3 mb-6">
          <StatCard
            label="本月收入"
            value={formatMoney(stats.income)}
            color="text-green-600"
            onClick={() => {
              setFilterType("income");
              syncUrl({ type: "income" });
            }}
          />
          <StatCard
            label="本月支出"
            value={formatMoney(stats.expense)}
            color="text-red-500"
            onClick={() => {
              setFilterType("expense");
              syncUrl({ type: "expense" });
            }}
          />
          <StatCard
            label="结余"
            value={formatMoney(balance)}
            color={balance >= 0 ? "text-blue-600" : "text-red-500"}
          />
        </section>
      )}

      {stats && !hasFilters && stats.byCategory.length > 0 && (
        <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 mb-6">
          <h2 className="text-sm font-medium text-gray-500 mb-3">分类统计</h2>
          <ul className="space-y-2">
            {stats.byCategory.map((c) => (
              <li key={`${c.category}-${c.type}`}>
                <button
                  type="button"
                  onClick={() => {
                    setFilterType(c.type);
                    setFilterCategory(c.category);
                    syncUrl({ type: c.type, category: c.category });
                  }}
                  className="w-full flex justify-between text-sm rounded-lg px-1 py-0.5 hover:bg-black/5 dark:hover:bg-white/5 text-left"
                >
                  <span>
                    {c.category}
                    <span className="text-gray-400 ml-2">{TYPE_LABELS[c.type]}</span>
                  </span>
                  <span className={c.type === "income" ? "text-green-600" : "text-red-500"}>
                    {c.type === "income" ? "+" : "-"}
                    {formatMoney(c.amount)}
                  </span>
                </button>
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
          {filterAccount && (
            <p className="text-xs text-gray-500">将记入账户：{filterAccount}</p>
          )}
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
        <h2 className="font-medium mb-3">{listTitle}</h2>
        {loading ? (
          <p className="text-sm text-gray-500">加载中…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-gray-500 rounded-xl border border-dashed border-black/15 dark:border-white/20 p-6 text-center">
            {hasFilters ? "没有符合筛选条件的记录" : "本月还没有记录，记一笔吧"}
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
                      <button
                        type="button"
                        onClick={() => {
                          setFilterAccount(item.account || "");
                          syncUrl({ account: item.account || "" });
                        }}
                        className="text-xs text-blue-600 hover:underline shrink-0"
                      >
                        {item.account}
                      </button>
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
  onClick,
}: {
  label: string;
  value: string;
  color: string;
  onClick?: () => void;
}) {
  const cls = `rounded-2xl border border-black/10 dark:border-white/15 p-4 text-left ${
    onClick ? "hover:border-blue-400/60 hover:bg-blue-50/40 dark:hover:bg-blue-950/20 cursor-pointer transition-colors" : ""
  }`;
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls}>
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <p className={`text-xl font-semibold ${color}`}>¥{value}</p>
        <p className="text-[11px] text-gray-400 mt-1">点击查看流水</p>
      </button>
    );
  }
  return (
    <div className={cls}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-semibold ${color}`}>¥{value}</p>
    </div>
  );
}
