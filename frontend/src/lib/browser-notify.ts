/** 浏览器 Notification：打开网页时可弹窗提醒（无需微信）。 */

const STORAGE_KEY = "vita_browser_notify_v1";
const ENABLED_KEY = "vita_browser_notify_enabled";

export type DueReminder = {
  id: number;
  title: string;
  due_at: string;
  type?: string;
  note?: string;
  done?: boolean;
};

type NotifiedMap = Record<string, string>; // id -> due_at

function readMap(): NotifiedMap {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") as NotifiedMap;
  } catch {
    return {};
  }
}

function writeMap(map: NotifiedMap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function isNotifySupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function getNotifyPermission(): NotificationPermission | "unsupported" {
  if (!isNotifySupported()) return "unsupported";
  return Notification.permission;
}

export function isBrowserNotifyEnabled(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(ENABLED_KEY) === "1";
}

export function setBrowserNotifyEnabled(on: boolean) {
  if (typeof window === "undefined") return;
  localStorage.setItem(ENABLED_KEY, on ? "1" : "0");
}

export async function requestBrowserNotifyPermission(): Promise<NotificationPermission | "unsupported"> {
  if (!isNotifySupported()) return "unsupported";
  const perm = await Notification.requestPermission();
  if (perm === "granted") setBrowserNotifyEnabled(true);
  return perm;
}

export function showBrowserNotification(title: string, options?: NotificationOptions) {
  if (!isNotifySupported() || Notification.permission !== "granted") return null;
  try {
    return new Notification(title, {
      icon: "/favicon.ico",
      ...options,
    });
  } catch {
    return null;
  }
}

const TYPE_LABEL: Record<string, string> = {
  bill: "账单",
  life: "生活",
  anniversary: "纪念日",
};

/** 对已到期且未完成的提醒弹窗；同一 due_at 只弹一次。 */
export function notifyDueReminders(items: DueReminder[]): number {
  if (!isBrowserNotifyEnabled()) return 0;
  if (!isNotifySupported() || Notification.permission !== "granted") return 0;

  const now = Date.now();
  const map = readMap();
  let count = 0;

  for (const r of items) {
    if (r.done) continue;
    const due = new Date(r.due_at).getTime();
    if (Number.isNaN(due) || due > now) continue;

    const key = String(r.id);
    const dueKey = r.due_at;
    if (map[key] === dueKey) continue;

    const typeLabel = TYPE_LABEL[r.type || "life"] || "提醒";
    const body = [
      `${typeLabel} · ${new Date(r.due_at).toLocaleString("zh-CN")}`,
      r.note || "",
    ]
      .filter(Boolean)
      .join("\n");

    showBrowserNotification(`Vita：${r.title}`, {
      body,
      tag: `vita-reminder-${r.id}`,
      requireInteraction: false,
    });

    map[key] = dueKey;
    count += 1;
  }

  if (count) writeMap(map);
  return count;
}

export function clearBrowserNotifyHistory() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}
