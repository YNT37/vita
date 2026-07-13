"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

type WxStatus = {
  configured: boolean;
  bound: boolean;
  uid_hint: string | null;
};

type QrPayload = {
  code: string;
  url: string;
  shortUrl?: string;
  expires: number;
  poll_interval_sec: number;
  hint: string;
};

export function WxPusherBind() {
  const [status, setStatus] = useState<WxStatus | null>(null);
  const [uidInput, setUidInput] = useState("");
  const [qr, setQr] = useState<QrPayload | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const res = await apiFetch<WxStatus>("/api/wxpusher/status");
      setStatus(res);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "加载推送状态失败");
    }
  }, []);

  useEffect(() => {
    loadStatus();
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current);
    };
  }, [loadStatus]);

  function stopPoll() {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }

  async function startQrBind() {
    setErr("");
    setMsg("");
    setBusy(true);
    stopPoll();
    try {
      const res = await apiFetch<QrPayload>("/api/wxpusher/bind-qrcode", {
        method: "POST",
        body: {},
      });
      setQr(res);
      setMsg(res.hint || "请用微信扫码");
      const interval = Math.max(10, res.poll_interval_sec || 10) * 1000;
      pollTimer.current = setInterval(async () => {
        try {
          const polled = await apiFetch<WxStatus & { scanned?: boolean; bound_now?: boolean }>(
            `/api/wxpusher/bind-poll?code=${encodeURIComponent(res.code)}`
          );
          if (polled.scanned || polled.bound_now || polled.bound) {
            setStatus(polled);
            setMsg("绑定成功！可点「发送测试」验证。");
            setQr(null);
            stopPoll();
          }
        } catch {
          // 轮询失败不打断，下次再试
        }
      }, interval);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "创建二维码失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveUid(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      const res = await apiFetch<WxStatus>("/api/wxpusher/uid", {
        method: "POST",
        body: { uid: uidInput.trim() },
      });
      setStatus(res);
      setUidInput("");
      setMsg(res.bound ? "UID 已保存" : "已清除绑定");
      setQr(null);
      stopPoll();
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
      const res = await apiFetch<WxStatus>("/api/wxpusher/uid", {
        method: "POST",
        body: { uid: "" },
      });
      setStatus(res);
      setMsg("已解除绑定");
      setQr(null);
      stopPoll();
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
      const res = await apiFetch<{ message: string }>("/api/wxpusher/test", {
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
        "/api/wxpusher/dispatch",
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
      <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
        <p className="text-sm text-gray-500">加载微信提醒…</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-3">
      <div>
        <h2 className="text-sm font-medium">微信提醒（WxPusher）</h2>
        <p className="text-xs text-gray-400 mt-1">
          绑定后，到期待办会推送到你的微信
        </p>
      </div>

      {!status.configured ? (
        <p className="text-sm text-amber-600">
          服务器尚未配置 <code className="text-xs">WXPUSHER_APP_TOKEN</code>
          ，请管理员在 backend/.env 填写后重启。
        </p>
      ) : (
        <>
          <p className="text-sm">
            状态：{" "}
            {status.bound ? (
              <span className="text-green-600">已绑定 {status.uid_hint}</span>
            ) : (
              <span className="text-gray-500">未绑定</span>
            )}
          </p>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={startQrBind}
              className="rounded-lg bg-blue-600 text-white px-3 py-1.5 text-sm disabled:opacity-60"
            >
              {busy && !qr ? "准备中…" : "扫码绑定"}
            </button>
            {status.bound && (
              <>
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
              </>
            )}
          </div>

          {qr?.url && (
            <div className="rounded-xl border border-dashed border-black/15 p-3 text-center space-y-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qr.url}
                alt="WxPusher 绑定二维码"
                className="mx-auto w-48 h-48 object-contain bg-white rounded-lg"
              />
              <p className="text-xs text-gray-500">
                用微信扫码关注；约每 10 秒自动检测一次（WxPusher 限制）
              </p>
              {qr.shortUrl && (
                <a
                  href={qr.shortUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                >
                  打不开图？点这里打开
                </a>
              )}
            </div>
          )}

          <form onSubmit={saveUid} className="space-y-2">
            <label className="block text-xs text-gray-500">
              或手动填写 UID（关注公众号后菜单「获取UID」）
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                className="flex-1 min-w-0 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                value={uidInput}
                onChange={(e) => setUidInput(e.target.value)}
                placeholder="UID_xxxxxxxx"
              />
              <button
                type="submit"
                disabled={busy || !uidInput.trim()}
                className="rounded-lg border border-black/15 px-3 py-2 text-sm disabled:opacity-60 shrink-0"
              >
                保存 UID
              </button>
            </div>
          </form>
        </>
      )}

      {msg && <p className="text-sm text-green-600">{msg}</p>}
      {err && <p className="text-sm text-red-500">{err}</p>}
    </section>
  );
}
