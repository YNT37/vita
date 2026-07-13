"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

type ScStatus = {
  bound: boolean;
  key_hint: string | null;
  bind_help_url?: string;
};

export function ServerChanBind() {
  const [status, setStatus] = useState<ScStatus | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const res = await apiFetch<ScStatus>("/api/serverchan/status");
      setStatus(res);
      setErr("");
    } catch (e) {
      setStatus({ bound: false, key_hint: null });
      setErr(e instanceof ApiError ? e.message : "加载推送状态失败");
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  async function saveKey(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      const res = await apiFetch<ScStatus>("/api/serverchan/key", {
        method: "POST",
        body: { sendkey: keyInput.trim() },
      });
      setStatus(res);
      setKeyInput("");
      setMsg(res.bound ? "SendKey 已保存" : "已清除绑定");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function unbind() {
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch<ScStatus>("/api/serverchan/key", {
        method: "POST",
        body: { sendkey: "" },
      });
      setStatus(res);
      setMsg("已解除绑定");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "解绑失败");
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const res = await apiFetch<{ message: string }>("/api/serverchan/test", {
        method: "POST",
        body: {},
      });
      setMsg(res.message || "已发送");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function dispatchNow() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const res = await apiFetch<{ sent: number; skipped: number }>(
        "/api/serverchan/dispatch",
        { method: "POST", body: {} }
      );
      setMsg(`已检查到期提醒：推送 ${res.sent} 条，跳过 ${res.skipped} 条`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "检查失败");
    } finally {
      setBusy(false);
    }
  }

  if (!status) {
    return (
      <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-2">
        <p className="text-sm text-gray-500">加载微信提醒…</p>
        {err && <p className="text-sm text-red-500">{err}</p>}
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-3">
      <div>
        <h2 className="text-sm font-medium">微信提醒（Server酱）</h2>
        <p className="text-xs text-gray-400 mt-1">
          微信扫码拿 SendKey 即可，无需下载额外 App
        </p>
      </div>

      <ol className="text-xs text-gray-500 list-decimal pl-4 space-y-1">
        <li>
          打开{" "}
          <a
            href="https://sct.ftqq.com/"
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 hover:underline"
          >
            sct.ftqq.com
          </a>
          ，用微信登录
        </li>
        <li>在「Key&API」复制 SendKey，粘贴到下方保存</li>
        <li>点「发送测试」，微信应收到消息</li>
      </ol>

      <p className="text-sm">
        状态：{" "}
        {status.bound ? (
          <span className="text-green-600">已绑定 {status.key_hint}</span>
        ) : (
          <span className="text-gray-500">未绑定</span>
        )}
      </p>

      <form onSubmit={saveKey} className="space-y-2">
        <label className="block text-xs text-gray-500">SendKey</label>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            className="flex-1 min-w-0 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="SCTxxxxxxxx"
            autoComplete="off"
          />
          <button
            type="submit"
            disabled={busy || !keyInput.trim()}
            className="rounded-lg bg-blue-600 text-white px-3 py-2 text-sm disabled:opacity-60 shrink-0"
          >
            保存
          </button>
        </div>
      </form>

      {status.bound && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={sendTest}
            className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-sm disabled:opacity-60"
          >
            发送测试
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={dispatchNow}
            className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-sm disabled:opacity-60"
          >
            立即检查到期
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={unbind}
            className="rounded-lg text-red-500 text-sm px-2 py-1.5 disabled:opacity-60"
          >
            解除绑定
          </button>
        </div>
      )}

      {msg && <p className="text-sm text-green-600">{msg}</p>}
      {err && <p className="text-sm text-red-500">{err}</p>}
    </section>
  );
}
