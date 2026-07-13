"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useAutoReload, useDataRefresh } from "@/lib/data-refresh";
import { apiFetch, ApiError } from "@/lib/api";
import { PageContainer } from "@/components/PageContainer";

type TxnType = "income" | "expense";
type AssetKind = "asset" | "liability";
type ReminderType = "bill" | "life" | "anniversary";

type AssetRow = {
  id: number;
  name: string;
  balance: number;
  kind: AssetKind;
  note: string;
  updated_at: string | null;
};

type ReminderRow = {
  id: number;
  title: string;
  due_at: string;
  type: ReminderType | string;
  done: boolean;
  note?: string;
};

type OverviewData = {
  month: string;
  stats: {
    income: number;
    expense: number;
    balance: number;
    byCategory: { category: string; type: TxnType; amount: number }[];
    byDay: { date: string; income: number; expense: number }[];
  };
  assets: AssetRow[];
  assets_total: number;
  liabilities_total: number;
  net_worth: number;
  reminders_pending: ReminderRow[];
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

function toDatetimeLocal(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "概览" },
  { id: "assets", label: "账户" },
  { id: "reminders", label: "待办" },
  { id: "categories", label: "分类" },
];

const inputCls =
  "w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-blue-500";

export default function StatsPage() {
  const { user, loading: authLoading } = useAuth();
  const { bump } = useDataRefresh();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [month, setMonth] = useState(currentMonth);
  const [data, setData] = useState<OverviewData | null>(null);
  const [categoryRows, setCategoryRows] = useState<CategoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [okMsg, setOkMsg] = useState("");

  const [editingAssetId, setEditingAssetId] = useState<number | null>(null);
  const [assetDraft, setAssetDraft] = useState({
    name: "",
    balance: "",
    kind: "asset" as AssetKind,
    note: "",
  });
  const [newAsset, setNewAsset] = useState({
    name: "",
    balance: "",
    kind: "asset" as AssetKind,
    note: "",
  });

  const [editingRemId, setEditingRemId] = useState<number | null>(null);
  const [remDraft, setRemDraft] = useState({
    title: "",
    due_at: "",
    type: "life" as ReminderType,
    note: "",
    done: false,
  });
  const [newRem, setNewRem] = useState({
    title: "",
    due_at: "",
    type: "life" as ReminderType,
    note: "",
  });

  const [editingCatId, setEditingCatId] = useState<number | null>(null);
  const [catDraft, setCatDraft] = useState({ name: "", kind: "expense" as TxnType });
  const [newCat, setNewCat] = useState({ name: "", kind: "expense" as TxnType });

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

  useAutoReload(load, !!user);

  function flash(msg: string) {
    setOkMsg(msg);
    setTimeout(() => setOkMsg(""), 2000);
  }

  async function createAsset(e: React.FormEvent) {
    e.preventDefault();
    const balance = Number(newAsset.balance);
    if (!newAsset.name.trim() || Number.isNaN(balance) || balance < 0) {
      setError("请填写账户名和有效余额");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/assets", {
        method: "POST",
        body: {
          name: newAsset.name.trim(),
          balance,
          kind: newAsset.kind,
          note: newAsset.note.trim(),
        },
      });
      setNewAsset({ name: "", balance: "", kind: "asset", note: "" });
      bump();
      await load();
      flash("账户已保存");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  function startEditAsset(a: AssetRow) {
    setEditingAssetId(a.id);
    setAssetDraft({
      name: a.name,
      balance: String(a.balance),
      kind: a.kind === "liability" ? "liability" : "asset",
      note: a.note || "",
    });
  }

  async function saveAssetEdit(id: number) {
    const balance = Number(assetDraft.balance);
    if (!assetDraft.name.trim() || Number.isNaN(balance) || balance < 0) {
      setError("请填写有效名称和余额");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/api/assets/${id}`, {
        method: "PATCH",
        body: {
          name: assetDraft.name.trim(),
          balance,
          kind: assetDraft.kind,
          note: assetDraft.note.trim(),
        },
      });
      setEditingAssetId(null);
      bump();
      await load();
      flash("账户已更新");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "更新失败");
    } finally {
      setSaving(false);
    }
  }

  async function removeAsset(id: number) {
    if (!confirm("确认删除该账户？")) return;
    setError("");
    try {
      await apiFetch(`/api/assets/${id}`, { method: "DELETE" });
      bump();
      await load();
      flash("已删除");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  async function createReminder(e: React.FormEvent) {
    e.preventDefault();
    if (!newRem.title.trim() || !newRem.due_at) {
      setError("请填写待办标题和到期时间");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/reminders", {
        method: "POST",
        body: {
          title: newRem.title.trim(),
          due_at: newRem.due_at,
          type: newRem.type,
          note: newRem.note.trim(),
        },
      });
      setNewRem({ title: "", due_at: "", type: "life", note: "" });
      bump();
      await load();
      flash("待办已添加");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "添加失败");
    } finally {
      setSaving(false);
    }
  }

  function startEditRem(r: ReminderRow) {
    setEditingRemId(r.id);
    setRemDraft({
      title: r.title,
      due_at: toDatetimeLocal(r.due_at),
      type: (r.type as ReminderType) || "life",
      note: r.note || "",
      done: r.done,
    });
  }

  async function saveRemEdit(id: number) {
    if (!remDraft.title.trim() || !remDraft.due_at) {
      setError("请填写标题和到期时间");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/api/reminders/${id}`, {
        method: "PATCH",
        body: {
          title: remDraft.title.trim(),
          due_at: remDraft.due_at,
          type: remDraft.type,
          note: remDraft.note.trim(),
          done: remDraft.done,
        },
      });
      setEditingRemId(null);
      bump();
      await load();
      flash("待办已更新");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "更新失败");
    } finally {
      setSaving(false);
    }
  }

  async function removeReminder(id: number) {
    if (!confirm("确认删除该待办？")) return;
    try {
      await apiFetch(`/api/reminders/${id}`, { method: "DELETE" });
      bump();
      await load();
      flash("已删除");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  async function createCategory(e: React.FormEvent) {
    e.preventDefault();
    if (!newCat.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/categories", {
        method: "POST",
        body: { name: newCat.name.trim(), kind: newCat.kind },
      });
      setNewCat({ name: "", kind: newCat.kind });
      bump();
      await load();
      flash("分类已添加");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "添加失败");
    } finally {
      setSaving(false);
    }
  }

  function startEditCat(c: CategoryRow) {
    setEditingCatId(c.id);
    setCatDraft({ name: c.name, kind: c.kind });
  }

  async function saveCatEdit(id: number) {
    if (!catDraft.name.trim()) {
      setError("分类名不能为空");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/api/categories/${id}`, {
        method: "PATCH",
        body: { name: catDraft.name.trim(), kind: catDraft.kind },
      });
      setEditingCatId(null);
      bump();
      await load();
      flash("分类已更新");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "更新失败");
    } finally {
      setSaving(false);
    }
  }

  async function removeCategory(id: number) {
    if (!confirm("确认删除该分类？")) return;
    try {
      await apiFetch(`/api/categories/${id}`, { method: "DELETE" });
      bump();
      await load();
      flash("已删除");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>;
  }

  const maxCat = Math.max(...(data?.stats.byCategory.map((c) => c.amount) ?? [1]), 1);
  const assetsOnly = data?.assets.filter((a) => a.kind !== "liability") ?? [];
  const liabilities = data?.assets.filter((a) => a.kind === "liability") ?? [];

  return (
    <PageContainer wide>
      <header className="mb-4">
        <h1 className="text-xl sm:text-2xl font-semibold">统计中心</h1>
        <p className="text-sm text-gray-500">自由增删改账户、待办与分类，维护你的财务档案</p>
      </header>

      <div className="flex items-center gap-3 mb-4">
        <input
          type="month"
          className={inputCls + " w-auto"}
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
      {okMsg && (
        <p className="text-sm text-green-600 mb-3 rounded-lg bg-green-50 dark:bg-green-950/30 px-3 py-2">
          {okMsg}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">加载中…</p>
      ) : !data ? null : (
        <>
          {tab === "overview" && (
            <div className="space-y-4">
              <section className="grid gap-3 grid-cols-2 sm:grid-cols-3">
                <StatCard label="本月收入" value={data.stats.income} color="text-green-600" />
                <StatCard label="本月支出" value={data.stats.expense} color="text-red-500" />
                <StatCard
                  label="本月结余"
                  value={data.stats.balance}
                  color={data.stats.balance >= 0 ? "text-blue-600" : "text-red-500"}
                  className="col-span-2 sm:col-span-1"
                />
              </section>
              <section className="grid gap-3 grid-cols-2 sm:grid-cols-3">
                <StatCard label="资产合计" value={data.assets_total} color="text-blue-600" />
                <StatCard label="负债合计" value={data.liabilities_total || 0} color="text-amber-600" />
                <StatCard
                  label="净资产"
                  value={data.net_worth ?? data.assets_total}
                  color="text-emerald-600"
                  className="col-span-2 sm:col-span-1"
                />
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
            </div>
          )}

          {tab === "assets" && (
            <div className="space-y-4">
              <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-2">
                <h2 className="text-sm font-medium">新增账户</h2>
                <form onSubmit={createAsset} className="grid gap-2 sm:grid-cols-2">
                  <input
                    className={inputCls}
                    placeholder="账户名"
                    value={newAsset.name}
                    onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })}
                  />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className={inputCls}
                    placeholder="余额"
                    value={newAsset.balance}
                    onChange={(e) => setNewAsset({ ...newAsset, balance: e.target.value })}
                  />
                  <select
                    className={inputCls}
                    value={newAsset.kind}
                    onChange={(e) =>
                      setNewAsset({ ...newAsset, kind: e.target.value as AssetKind })
                    }
                  >
                    <option value="asset">资产</option>
                    <option value="liability">负债</option>
                  </select>
                  <input
                    className={inputCls}
                    placeholder="备注（可选）"
                    value={newAsset.note}
                    onChange={(e) => setNewAsset({ ...newAsset, note: e.target.value })}
                  />
                  <button
                    type="submit"
                    disabled={saving}
                    className="sm:col-span-2 rounded-lg bg-blue-600 text-white px-4 py-2 text-sm disabled:opacity-60"
                  >
                    添加账户
                  </button>
                </form>
              </section>

              <AssetEditableList
                title={`资产 · ¥${formatMoney(data.assets_total)}`}
                items={assetsOnly}
                editingId={editingAssetId}
                draft={assetDraft}
                setDraft={setAssetDraft}
                onEdit={startEditAsset}
                onSave={saveAssetEdit}
                onCancel={() => setEditingAssetId(null)}
                onDelete={removeAsset}
                saving={saving}
              />
              <AssetEditableList
                title={`负债 · ¥${formatMoney(data.liabilities_total || 0)}`}
                items={liabilities}
                editingId={editingAssetId}
                draft={assetDraft}
                setDraft={setAssetDraft}
                onEdit={startEditAsset}
                onSave={saveAssetEdit}
                onCancel={() => setEditingAssetId(null)}
                onDelete={removeAsset}
                saving={saving}
                liability
              />
            </div>
          )}

          {tab === "reminders" && (
            <div className="space-y-4">
              <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-2">
                <h2 className="text-sm font-medium">新增待办</h2>
                <form onSubmit={createReminder} className="grid gap-2 sm:grid-cols-2">
                  <input
                    className={inputCls + " sm:col-span-2"}
                    placeholder="标题"
                    value={newRem.title}
                    onChange={(e) => setNewRem({ ...newRem, title: e.target.value })}
                  />
                  <input
                    type="datetime-local"
                    className={inputCls}
                    value={newRem.due_at}
                    onChange={(e) => setNewRem({ ...newRem, due_at: e.target.value })}
                  />
                  <select
                    className={inputCls}
                    value={newRem.type}
                    onChange={(e) =>
                      setNewRem({ ...newRem, type: e.target.value as ReminderType })
                    }
                  >
                    <option value="life">生活</option>
                    <option value="bill">账单</option>
                    <option value="anniversary">纪念日</option>
                  </select>
                  <input
                    className={inputCls + " sm:col-span-2"}
                    placeholder="备注（可选）"
                    value={newRem.note}
                    onChange={(e) => setNewRem({ ...newRem, note: e.target.value })}
                  />
                  <button
                    type="submit"
                    disabled={saving}
                    className="sm:col-span-2 rounded-lg bg-blue-600 text-white px-4 py-2 text-sm disabled:opacity-60"
                  >
                    添加待办
                  </button>
                </form>
              </section>

              <section className="space-y-2">
                <h2 className="text-sm font-medium text-gray-500">
                  待办列表 · {data.reminders_pending.length} 条
                  {data.reminders_overdue_count > 0 && (
                    <span className="text-red-500 ml-2">逾期 {data.reminders_overdue_count}</span>
                  )}
                </h2>
                {data.reminders_pending.length === 0 ? (
                  <p className="text-sm text-gray-400 border border-dashed rounded-xl p-6 text-center">
                    暂无待办
                  </p>
                ) : (
                  data.reminders_pending.map((r) => {
                    const overdue = new Date(r.due_at) < new Date();
                    if (editingRemId === r.id) {
                      return (
                        <div
                          key={r.id}
                          className="rounded-xl border border-blue-300 p-3 space-y-2 bg-blue-50/30 dark:bg-blue-950/20"
                        >
                          <input
                            className={inputCls}
                            value={remDraft.title}
                            onChange={(e) => setRemDraft({ ...remDraft, title: e.target.value })}
                          />
                          <div className="grid gap-2 sm:grid-cols-2">
                            <input
                              type="datetime-local"
                              className={inputCls}
                              value={remDraft.due_at}
                              onChange={(e) =>
                                setRemDraft({ ...remDraft, due_at: e.target.value })
                              }
                            />
                            <select
                              className={inputCls}
                              value={remDraft.type}
                              onChange={(e) =>
                                setRemDraft({
                                  ...remDraft,
                                  type: e.target.value as ReminderType,
                                })
                              }
                            >
                              <option value="life">生活</option>
                              <option value="bill">账单</option>
                              <option value="anniversary">纪念日</option>
                            </select>
                          </div>
                          <input
                            className={inputCls}
                            placeholder="备注"
                            value={remDraft.note}
                            onChange={(e) => setRemDraft({ ...remDraft, note: e.target.value })}
                          />
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={remDraft.done}
                              onChange={(e) =>
                                setRemDraft({ ...remDraft, done: e.target.checked })
                              }
                            />
                            已完成
                          </label>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() => saveRemEdit(r.id)}
                              className="rounded-lg bg-blue-600 text-white px-3 py-1.5 text-sm"
                            >
                              保存
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingRemId(null)}
                              className="rounded-lg border px-3 py-1.5 text-sm"
                            >
                              取消
                            </button>
                          </div>
                        </div>
                      );
                    }
                    return (
                      <div
                        key={r.id}
                        className={`rounded-xl border p-3 ${
                          overdue
                            ? "border-red-300 bg-red-50/40 dark:bg-red-950/20"
                            : "border-black/10 dark:border-white/15"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-medium text-sm">{r.title}</p>
                            <p className="text-xs text-gray-400 mt-0.5">
                              {toDatetimeLocal(r.due_at).replace("T", " ")} · {r.type}
                            </p>
                            {r.note && <p className="text-xs text-gray-500 mt-1">{r.note}</p>}
                          </div>
                          <div className="flex gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => startEditRem(r)}
                              className="text-xs text-blue-600 hover:underline"
                            >
                              编辑
                            </button>
                            <button
                              type="button"
                              onClick={() => removeReminder(r.id)}
                              className="text-xs text-red-500 hover:underline"
                            >
                              删除
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </section>
            </div>
          )}

          {tab === "categories" && (
            <div className="space-y-4">
              <form
                onSubmit={createCategory}
                className="rounded-2xl border border-black/10 dark:border-white/15 p-4 flex flex-wrap gap-2"
              >
                <select
                  className={inputCls + " w-auto"}
                  value={newCat.kind}
                  onChange={(e) => setNewCat({ ...newCat, kind: e.target.value as TxnType })}
                >
                  <option value="expense">支出</option>
                  <option value="income">收入</option>
                </select>
                <input
                  className={inputCls + " flex-1 min-w-[120px]"}
                  placeholder="新分类名"
                  value={newCat.name}
                  onChange={(e) => setNewCat({ ...newCat, name: e.target.value })}
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
                <section
                  key={kind}
                  className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-2"
                >
                  <h2 className="text-sm font-medium text-gray-500">
                    {kind === "expense" ? "支出分类" : "收入分类"}
                  </h2>
                  <ul className="space-y-2">
                    {categoryRows
                      .filter((c) => c.kind === kind)
                      .map((c) =>
                        editingCatId === c.id ? (
                          <li key={c.id} className="flex flex-wrap gap-2 items-center">
                            <input
                              className={inputCls + " flex-1 min-w-[100px]"}
                              value={catDraft.name}
                              onChange={(e) =>
                                setCatDraft({ ...catDraft, name: e.target.value })
                              }
                            />
                            <select
                              className={inputCls + " w-auto"}
                              value={catDraft.kind}
                              onChange={(e) =>
                                setCatDraft({
                                  ...catDraft,
                                  kind: e.target.value as TxnType,
                                })
                              }
                            >
                              <option value="expense">支出</option>
                              <option value="income">收入</option>
                            </select>
                            <button
                              type="button"
                              onClick={() => saveCatEdit(c.id)}
                              className="text-xs text-blue-600"
                            >
                              保存
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingCatId(null)}
                              className="text-xs text-gray-500"
                            >
                              取消
                            </button>
                          </li>
                        ) : (
                          <li
                            key={c.id}
                            className="flex items-center justify-between rounded-lg border border-black/10 dark:border-white/15 px-3 py-2"
                          >
                            <span className="text-sm">{c.name}</span>
                            <span className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => startEditCat(c)}
                                className="text-xs text-blue-600 hover:underline"
                              >
                                编辑
                              </button>
                              <button
                                type="button"
                                onClick={() => removeCategory(c.id)}
                                className="text-xs text-red-500 hover:underline"
                              >
                                删除
                              </button>
                            </span>
                          </li>
                        )
                      )}
                  </ul>
                </section>
              ))}
              <p className="text-xs text-gray-400">分类会同步给 AI 与记账页。</p>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}

function AssetEditableList({
  title,
  items,
  editingId,
  draft,
  setDraft,
  onEdit,
  onSave,
  onCancel,
  onDelete,
  saving,
  liability,
}: {
  title: string;
  items: AssetRow[];
  editingId: number | null;
  draft: { name: string; balance: string; kind: AssetKind; note: string };
  setDraft: (d: { name: string; balance: string; kind: AssetKind; note: string }) => void;
  onEdit: (a: AssetRow) => void;
  onSave: (id: number) => void;
  onCancel: () => void;
  onDelete: (id: number) => void;
  saving: boolean;
  liability?: boolean;
}) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium text-gray-500">{title}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-gray-400 border border-dashed rounded-xl p-4 text-center">
          暂无{liability ? "负债" : "资产"}
        </p>
      ) : (
        items.map((a) =>
          editingId === a.id ? (
            <div
              key={a.id}
              className="rounded-xl border border-blue-300 p-3 space-y-2 bg-blue-50/30 dark:bg-blue-950/20"
            >
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  className={inputCls}
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className={inputCls}
                  value={draft.balance}
                  onChange={(e) => setDraft({ ...draft, balance: e.target.value })}
                />
                <select
                  className={inputCls}
                  value={draft.kind}
                  onChange={(e) =>
                    setDraft({ ...draft, kind: e.target.value as AssetKind })
                  }
                >
                  <option value="asset">资产</option>
                  <option value="liability">负债</option>
                </select>
                <input
                  className={inputCls}
                  placeholder="备注"
                  value={draft.note}
                  onChange={(e) => setDraft({ ...draft, note: e.target.value })}
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => onSave(a.id)}
                  className="rounded-lg bg-blue-600 text-white px-3 py-1.5 text-sm"
                >
                  保存
                </button>
                <button
                  type="button"
                  onClick={onCancel}
                  className="rounded-lg border px-3 py-1.5 text-sm"
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <div
              key={a.id}
              className="rounded-xl border border-black/10 dark:border-white/15 p-3 flex items-center justify-between gap-2"
            >
              <div className="min-w-0">
                <p className="font-medium truncate">
                  {a.name}
                  <span className="ml-2 text-xs text-gray-400">
                    {a.kind === "liability" ? "负债" : "资产"}
                  </span>
                </p>
                {a.note && <p className="text-xs text-gray-400 truncate">{a.note}</p>}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`font-semibold ${
                    liability ? "text-amber-600" : "text-blue-600"
                  }`}
                >
                  ¥{formatMoney(a.balance)}
                </span>
                <button
                  type="button"
                  onClick={() => onEdit(a)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  编辑
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(a.id)}
                  className="text-xs text-red-500 hover:underline"
                >
                  删除
                </button>
              </div>
            </div>
          )
        )
      )}
    </section>
  );
}

function StatCard({
  label,
  value,
  color,
  className = "",
}: {
  label: string;
  value: number;
  color: string;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl border border-black/10 dark:border-white/15 p-3 sm:p-4 ${className}`}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-lg sm:text-xl font-semibold ${color}`}>¥{formatMoney(value)}</p>
    </div>
  );
}
