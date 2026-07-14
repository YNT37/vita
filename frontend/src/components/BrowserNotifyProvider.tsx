"use client";

import { useCallback, useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import {
  isBrowserNotifyEnabled,
  notifyDueReminders,
  type DueReminder,
} from "@/lib/browser-notify";

const POLL_MS = 45_000;

/**
 * 登录后定期检查到期提醒，并弹出浏览器通知。
 * 需要用户在「我的」里开启权限；仅在页面打开时有效。
 */
export function BrowserNotifyProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const check = useCallback(async () => {
    if (!user || !isBrowserNotifyEnabled()) return;
    try {
      const res = await apiFetch<{ items: DueReminder[] }>("/api/reminders/due-check");
      notifyDueReminders(Array.isArray(res.items) ? res.items : []);
    } catch {
      // 忽略网络错误，下次再试
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
      return;
    }
    void check();
    timer.current = setInterval(() => void check(), POLL_MS);
    const onVis = () => {
      if (document.visibilityState === "visible") void check();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      if (timer.current) clearInterval(timer.current);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [user, check]);

  return <>{children}</>;
}
