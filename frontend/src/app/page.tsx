"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useAutoReload, useDataRefresh } from "@/lib/data-refresh";
import { apiFetch, ApiError } from "@/lib/api";
import { PageContainer } from "@/components/PageContainer";
import {
  type PersonaId,
  type ChatMsg,
  type ParseResult,
  PERSONA_LABELS,
} from "@/lib/persona";

export default function HomePage() {
  const { user, loading: authLoading } = useAuth();
  const { bump } = useDataRefresh();
  const router = useRouter();

  const [persona, setPersona] = useState<PersonaId>("butler");
  const [brief, setBrief] = useState("");
  const [briefLoading, setBriefLoading] = useState(false);

  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);

  const [parseInput, setParseInput] = useState("");
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [parseLoading, setParseLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const [error, setError] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const loadHistory = useCallback(async () => {
    try {
      const res = await apiFetch<{ messages: ChatMsg[] }>("/api/ai/chat/history");
      setMessages(res.messages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "对话记录加载失败");
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
    await Promise.all([loadBrief(), loadHistory()]);
  }, [user, loadBrief, loadHistory]);

  useAutoReload(reloadHome, !!user);

  async function sendChat(e: React.FormEvent) {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setError("");
    setChatSending(true);
    setChatInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const res = await apiFetch<{
        reply: string;
        action?: string | null;
        wrote?: boolean;
      }>("/api/ai/chat", {
        method: "POST",
        body: { message: text },
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      if (res.action || res.wrote) {
        bump();
        await loadBrief();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "发送失败");
    } finally {
      setChatSending(false);
    }
  }

  async function doParse(e: React.FormEvent) {
    e.preventDefault();
    const text = parseInput.trim();
    if (!text) return;
    setError("");
    setParseLoading(true);
    setParseResult(null);
    try {
      const res = await apiFetch<ParseResult>("/api/ai/parse", {
        method: "POST",
        body: { text },
      });
      setParseResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "解析失败");
    } finally {
      setParseLoading(false);
    }
  }

  async function confirmParse() {
    if (!parseResult || parseResult.intent === "unknown") return;
    setError("");
    setConfirming(true);
    try {
      const items =
        parseResult.intent === "batch"
          ? parseResult.actions || []
          : [{ intent: parseResult.intent, data: parseResult.data }];
      for (const item of items) {
        if (item.intent === "transaction") {
          await apiFetch("/api/transactions", { method: "POST", body: item.data });
        } else if (item.intent === "reminder") {
          await apiFetch("/api/reminders", { method: "POST", body: item.data });
        } else if (item.intent === "balance") {
          await apiFetch("/api/assets", { method: "POST", body: item.data });
        }
      }
      setParseInput("");
      setParseResult(null);
      bump();
      await loadBrief();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "写入失败");
    } finally {
      setConfirming(false);
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  const briefBlock = (
    <section className="rounded-2xl border border-black/10 dark:border-white/15 p-3 sm:p-4 shrink-0">
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
    </section>
  );

  const parseBlock = (
    <section className="rounded-2xl border border-black/10 dark:border-white/15 p-3 sm:p-4 shrink-0">
      <h2 className="text-sm font-medium text-gray-500 mb-2">一句话录入</h2>
      <form onSubmit={doParse} className="flex flex-col sm:flex-row gap-2 mb-2">
        <input
          className="flex-1 min-w-0 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
          value={parseInput}
          onChange={(e) => setParseInput(e.target.value)}
          placeholder="午饭30 / 基金余额1901 / 提醒我明天还花呗"
          disabled={parseLoading}
        />
        <button
          type="submit"
          disabled={parseLoading || !parseInput.trim()}
          className="rounded-lg border border-black/15 px-3 py-2 text-sm hover:bg-black/5 disabled:opacity-60 shrink-0"
        >
          {parseLoading ? "…" : "解析"}
        </button>
      </form>
      {parseResult && (
        <div className="rounded-xl bg-black/5 dark:bg-white/10 p-2 text-sm">
          {parseResult.intent === "unknown" ? (
            <p className="text-gray-500">未能识别，请手动到记账/提醒页填写。</p>
          ) : (
            <>
              <p className="mb-1">
                识别为：
                <strong>
                  {parseResult.intent === "transaction"
                    ? "记账"
                    : parseResult.intent === "reminder"
                      ? "提醒"
                      : parseResult.intent === "batch"
                        ? `批量 ${parseResult.actions?.length || 0} 项`
                        : "资产余额"}
                </strong>
                {parseResult.intent === "balance" && (
                  <span className="text-gray-500 ml-1">
                    {String(parseResult.data.name ?? "资产")} →{" "}
                    {String(parseResult.data.balance ?? "")} 元
                  </span>
                )}
              </p>
              {parseResult.intent === "batch" && parseResult.actions && (
                <ul className="text-xs text-gray-500 mb-2 space-y-0.5">
                  {parseResult.actions.map((a, i) => (
                    <li key={i}>
                      {a.intent === "balance"
                        ? `账户 ${String(a.data.name)} ${String(a.data.balance)} 元`
                        : a.intent === "reminder"
                          ? `提醒 ${String(a.data.title)}`
                          : `记账 ${String(a.data.amount)}`}
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                onClick={confirmParse}
                disabled={confirming}
                className="rounded-lg bg-green-600 text-white px-3 py-1 text-sm hover:bg-green-700 disabled:opacity-60"
              >
                {confirming ? "写入中…" : "确认写入"}
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );

  const chatBlock = (
    <section className="rounded-2xl border border-black/10 dark:border-white/15 flex flex-col flex-1 min-h-[280px] sm:min-h-[320px] lg:min-h-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto overscroll-contain px-3 py-3 space-y-2 min-h-0">
        {messages.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">和管家说点什么吧～</p>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[90%] sm:max-w-[80%] rounded-2xl px-3 py-2 text-sm break-words ${
                  m.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-black/5 dark:bg-white/10"
                }`}
              >
                {m.content}
              </div>
            </div>
          ))
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
          placeholder="输入消息…"
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
  );

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

      <div className="flex flex-col gap-3 flex-1 min-h-0 lg:grid lg:grid-cols-[minmax(260px,0.9fr)_minmax(0,1.2fr)] lg:gap-4 lg:items-stretch">
        <div className="flex flex-col gap-3 order-1 lg:order-none lg:overflow-y-auto lg:min-h-0">
          {briefBlock}
          <div className="hidden lg:block">{parseBlock}</div>
        </div>
        <div className="flex flex-col flex-1 min-h-0 order-2 lg:order-none">{chatBlock}</div>
        <div className="order-3 lg:hidden">{parseBlock}</div>
      </div>
    </PageContainer>
  );
}
