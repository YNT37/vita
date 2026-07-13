"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useAutoReload, useDataRefresh } from "@/lib/data-refresh";
import { apiFetch, ApiError } from "@/lib/api";
import { PageContainer } from "@/components/PageContainer";

type ReminderType = "bill" | "life" | "anniversary";

type Reminder = {
  id: number;
  title: string;
  due_at: string;
  type: ReminderType;
  done: boolean;
  note: string;
};

const TYPE_LABELS: Record<ReminderType, string> = {
  bill: "账单",
  life: "生活",
  anniversary: "纪念日",
};

function toDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatDue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isDueSoon(iso: string): boolean {
  const due = new Date(iso).getTime();
  if (Number.isNaN(due)) return false;
  const now = Date.now();
  const threeDays = 3 * 24 * 60 * 60 * 1000;
  return due >= now && due - now <= threeDays;
}

export default function RemindersPage() {
  const { user, loading: authLoading } = useAuth();
  const { bump } = useDataRefresh();
  const router = useRouter();

  const [items, setItems] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [type, setType] = useState<ReminderType>("life");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const list = await apiFetch<Reminder[]>("/api/reminders");
      setItems(list);
      apiFetch("/api/serverchan/dispatch", { method: "POST", body: {} }).catch(() => {});
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoReload(load, !!user);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!title.trim()) {
      setError("请填写标题");
      return;
    }
    if (!dueAt) {
      setError("请选择到期时间");
      return;
    }
    setSubmitting(true);
    try {
      const created = await apiFetch<Reminder>("/api/reminders", {
        method: "POST",
        body: {
          title: title.trim(),
          due_at: dueAt,
          type,
          note: note.trim(),
        },
      });
      setItems((prev) =>
        [...prev, created].sort(
          (a, b) => new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
        )
      );
      setTitle("");
      setDueAt("");
      setType("life");
      setNote("");
      bump();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "新增失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleDone(item: Reminder) {
    setError("");
    try {
      const updated = await apiFetch<Reminder>(`/api/reminders/${item.id}`, {
        method: "PATCH",
        body: { done: !item.done },
      });
      setItems((prev) => prev.map((r) => (r.id === item.id ? updated : r)));
      bump();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "更新失败");
    }
  }

  async function remove(id: number) {
    setError("");
    try {
      await apiFetch(`/api/reminders/${id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((r) => r.id !== id));
      bump();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  return (
    <PageContainer>
      <header className="mb-4 sm:mb-6">
        <h1 className="text-xl sm:text-2xl font-semibold">日程提醒</h1>
        <p className="text-sm text-gray-500">待办、账单与纪念日到期提醒</p>
      </header>

      <section className="rounded-2xl border border-black/10 dark:border-white/15 p-5 mb-6">
        <h2 className="font-medium mb-4">新增提醒</h2>
        <form onSubmit={onCreate} className="space-y-3">
          <div>
            <label className="block text-sm mb-1">标题</label>
            <input
              className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：还花呗"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-sm mb-1">到期时间</label>
              <input
                type="datetime-local"
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
                value={dueAt}
                onChange={(e) => setDueAt(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">类型</label>
              <select
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
                value={type}
                onChange={(e) => setType(e.target.value as ReminderType)}
              >
                <option value="life">生活</option>
                <option value="bill">账单</option>
                <option value="anniversary">纪念日</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm mb-1">备注（可选）</label>
            <input
              className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="补充说明"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            {submitting ? "提交中…" : "添加提醒"}
          </button>
        </form>
      </section>

      {error && (
        <p className="text-sm text-red-500 mb-4 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2">
          {error}
        </p>
      )}

      <section>
        <h2 className="font-medium mb-3">我的提醒</h2>
        {loading ? (
          <p className="text-sm text-gray-500">加载中…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-gray-500 rounded-xl border border-dashed border-black/15 dark:border-white/20 p-6 text-center">
            还没有提醒，添加一条吧
          </p>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => {
              const soon = !item.done && isDueSoon(item.due_at);
              return (
                <li
                  key={item.id}
                  className={`rounded-xl border p-4 flex gap-3 items-start ${
                    soon
                      ? "border-amber-400/60 bg-amber-50/50 dark:bg-amber-950/20"
                      : "border-black/10 dark:border-white/15"
                  } ${item.done ? "opacity-60" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() => toggleDone(item)}
                    className="mt-1 h-4 w-4 accent-blue-600"
                    aria-label={`标记 ${item.title} 完成`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`font-medium ${item.done ? "line-through text-gray-500" : ""}`}
                      >
                        {item.title}
                      </span>
                      <span className="text-xs rounded-full bg-black/5 dark:bg-white/10 px-2 py-0.5">
                        {TYPE_LABELS[item.type]}
                      </span>
                      {soon && (
                        <span className="text-xs text-amber-600 dark:text-amber-400">
                          即将到期
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {formatDue(item.due_at)}
                    </p>
                    {item.note && (
                      <p className="text-sm text-gray-400 mt-1">{item.note}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => remove(item.id)}
                    className="text-sm text-red-500 hover:underline shrink-0"
                  >
                    删除
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}
