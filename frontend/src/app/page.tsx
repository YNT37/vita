"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useAutoReload, useDataRefresh } from "@/lib/data-refresh";
import { apiFetch, ApiError } from "@/lib/api";
import { PageContainer } from "@/components/PageContainer";
import {
  ConfirmCard,
  draftToBody,
  pendingToCard,
  type ConfirmCardState,
  type ConfirmDraft,
  type PendingAction,
} from "@/components/ConfirmCard";
import {
  type PersonaId,
  type ChatMsg,
  PERSONA_LABELS,
} from "@/lib/persona";

type TimelineItem =
  | { kind: "msg"; id: string; role: "user" | "assistant"; content: string }
  | { kind: "confirm"; id: string };

let seq = 0;
function nextId(prefix: string) {
  seq += 1;
  return `${prefix}-${Date.now()}-${seq}`;
}

export default function HomePage() {
  const { user, loading: authLoading } = useAuth();
  const { bump } = useDataRefresh();
  const router = useRouter();

  const [persona, setPersona] = useState<PersonaId>("butler");
  const [brief, setBrief] = useState("");
  const [briefLoading, setBriefLoading] = useState(false);

  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [cards, setCards] = useState<Record<string, ConfirmCardState>>({});
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [busyCardIds, setBusyCardIds] = useState<Record<string, boolean>>({});

  const [error, setError] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await apiFetch<{ messages: ChatMsg[] }>("/api/ai/chat/history");
      setTimeline(
        res.messages.map((m, i) => ({
          kind: "msg" as const,
          id: `hist-${i}-${m.role}`,
          role: m.role,
          content: m.content,
        }))
      );
      setCards({});
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "对话记录加载失败");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const loadBrief = useCallback(async () => {
    setBriefLoading(true);
    try {
      const res = await apiFetch<{ text: string }>("/api/ai/brief", { method: "POST" });
      setBrief(res.text);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "简报加载失败");
    } finally {
      setBriefLoading(false);
    }
  }, []);

  const loadPersona = useCallback(async () => {
    try {
      const res = await apiFetch<{ current: PersonaId }>("/api/persona");
      setPersona(res.current);
      await Promise.all([loadBrief(), loadHistory()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    }
  }, [loadBrief, loadHistory]);

  useEffect(() => {
    if (user) loadPersona();
  }, [user, loadPersona]);

  const reloadHome = useCallback(async () => {
    if (!user) return;
    await loadBrief();
  }, [user, loadBrief]);

  useAutoReload(reloadHome, !!user);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [timeline, cards]);

  async function sendChat(e: React.FormEvent) {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setError("");
    setChatSending(true);
    setChatInput("");
    const userItem: TimelineItem = {
      kind: "msg",
      id: nextId("u"),
      role: "user",
      content: text,
    };
    setTimeline((prev) => [...prev, userItem]);
    try {
      const res = await apiFetch<{
        reply: string;
        pending?: PendingAction[];
      }>("/api/ai/chat", {
        method: "POST",
        body: { message: text },
      });
      const assistantItem: TimelineItem = {
        kind: "msg",
        id: nextId("a"),
        role: "assistant",
        content: res.reply,
      };
      const pending = Array.isArray(res.pending) ? res.pending : [];
      const newCards: ConfirmCardState[] = pending.map((p) =>
        pendingToCard(p, nextId("c"))
      );
      setCards((prev) => {
        const next = { ...prev };
        for (const c of newCards) next[c.id] = c;
        return next;
      });
      setTimeline((prev) => [
        ...prev,
        assistantItem,
        ...newCards.map((c) => ({ kind: "confirm" as const, id: c.id })),
      ]);
    } catch (err) {
      setTimeline((prev) => prev.filter((item) => item.id !== userItem.id));
      setChatInput(text);
      setError(err instanceof ApiError ? err.message : "发送失败");
    } finally {
      setChatSending(false);
    }
  }

  function updateCardDraft(id: string, draft: ConfirmDraft) {
    setCards((prev) => {
      const cur = prev[id];
      if (!cur || cur.status !== "pending") return prev;
      return { ...prev, [id]: { ...cur, draft } };
    });
  }

  function dismissCard(id: string) {
    setCards((prev) => {
      const cur = prev[id];
      if (!cur) return prev;
      return { ...prev, [id]: { ...cur, status: "dismissed" } };
    });
  }

  async function confirmCard(id: string) {
    const card = cards[id];
    if (!card || card.status !== "pending") return;
    setError("");
    setBusyCardIds((prev) => ({ ...prev, [id]: true }));
    try {
      const body = draftToBody(card);
      if (card.intent === "transaction") {
        if (!body.amount || Number(body.amount) <= 0) {
          throw new Error("请填写有效金额");
        }
        await apiFetch("/api/transactions", { method: "POST", body });
      } else if (card.intent === "reminder") {
        if (!String(body.title || "").trim()) {
          throw new Error("请填写提醒标题");
        }
        await apiFetch("/api/reminders", { method: "POST", body });
      } else {
        if (!String(body.name || "").trim()) {
          throw new Error("请填写账户名");
        }
        await apiFetch("/api/assets", { method: "POST", body });
      }
      setCards((prev) => ({
        ...prev,
        [id]: { ...prev[id], status: "done" },
      }));
      bump();
      await loadBrief();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "写入失败");
    } finally {
      setBusyCardIds((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  return (
    <PageContainer wide className="flex flex-col min-h-0 md:min-h-full lg:h-full">
      <header className="mb-3 sm:mb-4 shrink-0">
        <h1 className="text-xl sm:text-2xl font-semibold">Vita</h1>
        <p className="text-sm text-gray-500">
          你的{PERSONA_LABELS[persona]} ·{" "}
          <button
            type="button"
            onClick={() => router.push("/user")}
            className="hover:text-blue-600 hover:underline"
          >
            {user.username}
          </button>
        </p>
      </header>

      {error && (
        <p className="text-sm text-red-500 mb-2 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2 shrink-0">
          {error}
        </p>
      )}

      <div className="flex flex-col gap-3 flex-1 min-h-0 lg:grid lg:grid-cols-[minmax(240px,0.75fr)_minmax(0,1.35fr)] lg:gap-4 lg:items-stretch">
        <section className="rounded-2xl border border-black/10 dark:border-white/15 p-3 sm:p-4 shrink-0 lg:overflow-y-auto lg:min-h-0">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-medium text-gray-500">今日播报</h2>
            <button
              type="button"
              onClick={loadBrief}
              disabled={briefLoading}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            >
              {briefLoading ? "刷新中…" : "刷新"}
            </button>
          </div>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {briefLoading && !brief ? "加载中…" : brief || "暂无播报"}
          </p>
          <p className="text-xs text-gray-400 mt-3">
            记账、提醒请直接和管家说；对话里会弹出可编辑确认卡，点「确定」后才写入。
          </p>
        </section>

        <section className="rounded-2xl border border-black/10 dark:border-white/15 flex flex-col flex-1 min-h-[320px] lg:min-h-0 overflow-hidden">
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto overscroll-contain px-3 py-3 space-y-3 min-h-0"
          >
            {historyLoading && timeline.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">加载对话…</p>
            ) : timeline.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">
                试试：「中午吃饭花了20」或「记得提醒我明天还花呗」
              </p>
            ) : (
              timeline.map((item) => {
                if (item.kind === "confirm") {
                  const card = cards[item.id];
                  if (!card || card.status === "dismissed") return null;
                  return (
                    <div key={item.id} className="flex justify-start">
                      <ConfirmCard
                        card={card}
                        busy={!!busyCardIds[item.id]}
                        onChange={updateCardDraft}
                        onConfirm={confirmCard}
                        onDismiss={dismissCard}
                      />
                    </div>
                  );
                }
                return (
                  <div
                    key={item.id}
                    className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[90%] sm:max-w-[80%] rounded-2xl px-3 py-2 text-sm break-words ${
                        item.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-black/5 dark:bg-white/10"
                      }`}
                    >
                      {item.content}
                    </div>
                  </div>
                );
              })
            )}
          </div>
          <form
            onSubmit={sendChat}
            className="p-2 sm:p-3 border-t border-black/10 dark:border-white/15 flex gap-2 shrink-0"
          >
            <input
              className="flex-1 min-w-0 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="和管家说说记账或提醒…"
              disabled={chatSending}
            />
            <button
              type="submit"
              disabled={chatSending || !chatInput.trim()}
              className="rounded-lg bg-blue-600 text-white px-3 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60 shrink-0"
            >
              发送
            </button>
          </form>
        </section>
      </div>
    </PageContainer>
  );
}
