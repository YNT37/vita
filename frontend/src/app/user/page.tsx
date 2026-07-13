"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, type User } from "@/lib/auth";
import { useAutoReload } from "@/lib/data-refresh";
import { apiFetch, ApiError } from "@/lib/api";
import { PageContainer } from "@/components/PageContainer";
import { ServerChanBind } from "@/components/ServerChanBind";
import { type PersonaId, PERSONA_LABELS } from "@/lib/persona";

type OverviewBrief = {
  net_worth: number;
  assets_total: number;
  liabilities_total: number;
  reminders_pending: { id: number }[];
  stats: { income: number; expense: number };
};

function formatMoney(n: number) {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function UserPage() {
  const { user, loading: authLoading, logout, setUser } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<User | null>(null);
  const [persona, setPersona] = useState<PersonaId>("butler");
  const [overview, setOverview] = useState<OverviewBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [editingName, setEditingName] = useState(false);
  const [usernameInput, setUsernameInput] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState("");

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [savingPwd, setSavingPwd] = useState(false);
  const [pwdMsg, setPwdMsg] = useState("");
  const [pwdError, setPwdError] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [me, settings, ov] = await Promise.all([
        apiFetch<User>("/api/me"),
        apiFetch<{ persona: PersonaId }>("/api/settings"),
        apiFetch<OverviewBrief>(`/api/overview?month=${currentMonth()}`),
      ]);
      setProfile(me);
      setUser(me);
      setUsernameInput(me.username);
      setPersona(settings.persona);
      setOverview(ov);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [setUser]);

  useEffect(() => {
    if (user) load();
    // 仅在登录用户变化时加载，避免 setUser 刷新资料导致循环
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  useAutoReload(load, !!user);

  async function saveUsername(e: React.FormEvent) {
    e.preventDefault();
    setNameMsg("");
    setError("");
    setSavingName(true);
    try {
      const me = await apiFetch<User>("/api/me", {
        method: "PATCH",
        body: { username: usernameInput.trim() },
      });
      setProfile(me);
      setUser(me);
      setEditingName(false);
      setNameMsg("用户名已更新");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "修改失败");
    } finally {
      setSavingName(false);
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwdMsg("");
    setPwdError("");
    setSavingPwd(true);
    try {
      await apiFetch<{ ok: boolean }>("/api/me/password", {
        method: "POST",
        body: { old_password: oldPassword, new_password: newPassword },
      });
      setOldPassword("");
      setNewPassword("");
      setPwdMsg("密码已更新");
    } catch (err) {
      setPwdError(err instanceof ApiError ? err.message : "修改失败");
    } finally {
      setSavingPwd(false);
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  const display = profile || user;
  const initial = (display.username || "?").slice(0, 1).toUpperCase();
  const pendingCount = overview?.reminders_pending?.length ?? 0;

  return (
    <PageContainer className="space-y-4">
      <header className="mb-0">
        <h1 className="text-xl sm:text-2xl font-semibold">我的</h1>
        <p className="text-sm text-gray-500">账号与快捷入口</p>
      </header>

      {error && (
        <p className="text-sm text-red-500 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2">
          {error}
        </p>
      )}

      {loading && !profile ? (
        <p className="text-sm text-gray-500">加载中…</p>
      ) : (
        <div className="space-y-4 lg:grid lg:grid-cols-2 lg:gap-4 lg:space-y-0 lg:items-start">
          <div className="space-y-4">
          <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-blue-600 text-white grid place-items-center text-lg font-semibold">
                {initial}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium truncate">{display.username}</p>
                <p className="text-xs text-gray-400">
                  ID {display.id} · 加入于 {formatDate(display.created_at)}
                </p>
              </div>
            </div>

            {!editingName ? (
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-gray-500">
                  当前管家：{PERSONA_LABELS[persona]}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setEditingName(true);
                    setNameMsg("");
                    setUsernameInput(display.username);
                  }}
                  className="text-xs text-blue-600 hover:underline"
                >
                  修改用户名
                </button>
              </div>
            ) : (
              <form onSubmit={saveUsername} className="space-y-2">
                <label className="block text-xs text-gray-500">新用户名</label>
                <input
                  className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                  value={usernameInput}
                  onChange={(e) => setUsernameInput(e.target.value)}
                  maxLength={64}
                  required
                />
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={savingName}
                    className="rounded-lg bg-blue-600 text-white px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                  >
                    {savingName ? "保存中…" : "保存"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingName(false)}
                    className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-xs"
                  >
                    取消
                  </button>
                </div>
              </form>
            )}
            {nameMsg && <p className="text-xs text-green-600 mt-2">{nameMsg}</p>}
          </section>

          <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
            <h2 className="text-sm font-medium mb-3">本月摘要</h2>
            {overview ? (
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-400">净资产</p>
                  <p className="font-medium">¥{formatMoney(overview.net_worth)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">待办</p>
                  <p className="font-medium">{pendingCount} 项</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">本月收入</p>
                  <p className="font-medium text-green-600">
                    ¥{formatMoney(overview.stats?.income ?? 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">本月支出</p>
                  <p className="font-medium text-red-500">
                    ¥{formatMoney(overview.stats?.expense ?? 0)}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">暂无数据</p>
            )}
            <div className="flex flex-wrap gap-3 mt-3 text-xs">
              <Link href="/stats" className="text-blue-600 hover:underline">
                去统计
              </Link>
              <Link href="/records" className="text-blue-600 hover:underline">
                去记账
              </Link>
              <Link href="/reminders" className="text-blue-600 hover:underline">
                去提醒
              </Link>
            </div>
          </section>

          <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-3">
            <div>
              <h2 className="text-sm font-medium">应用设置</h2>
              <p className="text-xs text-gray-400 mt-1">
                管家性格与 AI 接口配置
              </p>
            </div>
            <Link
              href="/settings"
              className="flex items-center justify-between rounded-xl border border-black/10 dark:border-white/15 px-3 py-3 text-sm hover:border-blue-300 transition-colors"
            >
              <span>
                AI 设置 · {PERSONA_LABELS[persona]}
              </span>
              <span className="text-gray-400">→</span>
            </Link>
          </section>

          <ServerChanBind />
          </div>

          <div className="space-y-4">
          <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
            <h2 className="text-sm font-medium mb-3">修改密码</h2>
            <form onSubmit={savePassword} className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">原密码</label>
                <input
                  type="password"
                  className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">新密码（6–128 位）</label>
                <input
                  type="password"
                  className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                  maxLength={128}
                  required
                />
              </div>
              {pwdError && <p className="text-sm text-red-500">{pwdError}</p>}
              {pwdMsg && <p className="text-sm text-green-600">{pwdMsg}</p>}
              <button
                type="submit"
                disabled={savingPwd}
                className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
              >
                {savingPwd ? "保存中…" : "更新密码"}
              </button>
            </form>
          </section>

          <button
            type="button"
            onClick={logout}
            className="w-full rounded-lg border border-red-200 text-red-600 py-2.5 text-sm font-medium hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-950/30"
          >
            退出登录
          </button>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
