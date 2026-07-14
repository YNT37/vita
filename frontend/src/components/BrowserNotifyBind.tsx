"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import {
  clearBrowserNotifyHistory,
  getNotifyPermission,
  isBrowserNotifyEnabled,
  isNotifySupported,
  notifyDueReminders,
  requestBrowserNotifyPermission,
  setBrowserNotifyEnabled,
  type DueReminder,
} from "@/lib/browser-notify";

type Perm = NotificationPermission | "unsupported";

export function BrowserNotifyBind() {
  const [perm, setPerm] = useState<Perm>("default");
  const [enabled, setEnabled] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    setPerm(getNotifyPermission());
    setEnabled(isBrowserNotifyEnabled());
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function enable() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      if (!isNotifySupported()) {
        setErr("当前浏览器不支持桌面通知");
        return;
      }
      const p = await requestBrowserNotifyPermission();
      setPerm(p);
      if (p !== "granted") {
        setErr("未获得通知权限。请在浏览器地址栏允许通知后重试。");
        setBrowserNotifyEnabled(false);
        setEnabled(false);
        return;
      }
      setBrowserNotifyEnabled(true);
      setEnabled(true);
      setMsg("已开启。到期提醒会在本机弹出（需保持网页打开或在后台标签页）。");
      // 立刻检查一次
      const list = await apiFetch<DueReminder[]>("/api/reminders?with_debt=1");
      const n = notifyDueReminders(list);
      if (n > 0) setMsg(`已开启，并弹出 ${n} 条到期提醒`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "开启失败");
    } finally {
      setBusy(false);
      refresh();
    }
  }

  function disable() {
    setBrowserNotifyEnabled(false);
    setEnabled(false);
    setMsg("已关闭浏览器弹窗提醒");
    setErr("");
  }

  async function testNow() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      if (getNotifyPermission() !== "granted") {
        setErr("请先开启通知权限");
        return;
      }
      const { showBrowserNotification } = await import("@/lib/browser-notify");
      showBrowserNotification("Vita 测试弹窗", {
        body: "浏览器通知正常。到期待办会以同样方式弹出。",
        tag: "vita-test",
      });
      setMsg("已发送测试弹窗，请看屏幕角落/通知中心");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "测试失败");
    } finally {
      setBusy(false);
    }
  }

  function resetHistory() {
    clearBrowserNotifyHistory();
    setMsg("已清除「已弹过」记录，到期项可再次弹出");
  }

  const statusText =
    perm === "unsupported"
      ? "当前环境不支持"
      : perm === "granted" && enabled
        ? "已开启"
        : perm === "granted" && !enabled
          ? "已授权但未开启"
          : perm === "denied"
            ? "已被浏览器拒绝"
            : "未开启";

  return (
    <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-3">
      <div>
        <h2 className="text-sm font-medium">浏览器弹窗提醒</h2>
        <p className="text-xs text-gray-400 mt-1">
          推荐：点一次允许即可，无需微信 / Server酱。需保持 Vita 页面打开。
        </p>
      </div>

      <p className="text-sm">
        状态：{" "}
        <span
          className={
            perm === "granted" && enabled ? "text-green-600" : "text-gray-500"
          }
        >
          {statusText}
        </span>
      </p>

      <div className="flex flex-wrap gap-2">
        {!(perm === "granted" && enabled) ? (
          <button
            type="button"
            disabled={busy || perm === "unsupported" || perm === "denied"}
            onClick={enable}
            className="rounded-lg bg-blue-600 text-white px-3 py-1.5 text-sm disabled:opacity-60"
          >
            {busy ? "开启中…" : "开启浏览器通知"}
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={testNow}
              className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-sm disabled:opacity-60"
            >
              发送测试弹窗
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={resetHistory}
              className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-sm disabled:opacity-60"
            >
              重置已弹记录
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={disable}
              className="rounded-lg text-red-500 text-sm px-2 py-1.5 disabled:opacity-60"
            >
              关闭
            </button>
          </>
        )}
      </div>

      {perm === "denied" && (
        <p className="text-xs text-amber-600">
          请在浏览器地址栏左侧图标中，把本站「通知」改为允许，然后刷新页面再点开启。
        </p>
      )}

      {msg && <p className="text-sm text-green-600">{msg}</p>}
      {err && <p className="text-sm text-red-500">{err}</p>}
    </section>
  );
}
