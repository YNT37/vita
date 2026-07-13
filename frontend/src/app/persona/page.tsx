"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api";

type PersonaId = "butler" | "servant" | "sassy" | "lover";

type ChatMsg = { role: "user" | "assistant"; content: string };

type ParseResult = {
  intent: "transaction" | "reminder" | "unknown";
  data: Record<string, unknown>;
};

const PERSONA_LABELS: Record<PersonaId, string> = {
  butler: "管家",
  servant: "奴才",
  sassy: "毒舌闺蜜",
  lover: "暖心恋人",
};

export default function PersonaPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [persona, setPersona] = useState<PersonaId>("butler");
  const [options, setOptions] = useState<PersonaId[]>([]);
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
      const res = await apiFetch<{ current: PersonaId; options: PersonaId[] }>("/api/persona");
      setPersona(res.current);
      setOptions(res.options);
      await loadBrief();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    }
  }, [loadBrief]);

  useEffect(() => {
    if (user) loadPersona();
  }, [user, loadPersona]);

  async function switchPersona(id: PersonaId) {
    if (id === persona) return;
    setError("");
    try {
      const res = await apiFetch<{ current: PersonaId }>("/api/persona", {
        method: "POST",
        body: { persona: id },
      });
      setPersona(res.current);
      setMessages([]);
      await loadBrief();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "切换角色失败");
    }
  }

  async function sendChat(e: React.FormEvent) {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setError("");
    setChatSending(true);
    setChatInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const res = await apiFetch<{ reply: string }>("/api/ai/chat", {
        method: "POST",
        body: { message: text },
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
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
      if (parseResult.intent === "transaction") {
        await apiFetch("/api/transactions", {
          method: "POST",
          body: parseResult.data,
        });
      } else if (parseResult.intent === "reminder") {
        await apiFetch("/api/reminders", {
          method: "POST",
          body: parseResult.data,
        });
      }
      setParseInput("");
      setParseResult(null);
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

  const personaOptions = options.length > 0 ? options : (Object.keys(PERSONA_LABELS) as PersonaId[]);

  return (
    <main className="flex-1 p-6 max-w-2xl mx-auto w-full flex flex-col min-h-0">
      <header className="mb-4 shrink-0">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← 返回仪表盘
        </Link>
        <h1 className="text-2xl font-semibold mt-2">AI 管家</h1>
        <p className="text-sm text-gray-500">切换角色 · 对话陪伴 · 快捷录入</p>
      </header>

      {/* 角色切换 */}
      <section className="flex flex-wrap gap-2 mb-4 shrink-0">
        {personaOptions.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => switchPersona(id)}
            className={`rounded-full px-3 py-1.5 text-sm border transition-colors ${
              persona === id
                ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-950/30"
                : "border-black/15 dark:border-white/20 text-gray-500 hover:border-blue-300"
            }`}
          >
            {PERSONA_LABELS[id]}
          </button>
        ))}
      </section>

      {/* 每日简报 */}
      <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 mb-4 shrink-0">
        <div className="flex items-center justify-between mb-2">
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

      {error && (
        <p className="text-sm text-red-500 mb-3 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2 shrink-0">
          {error}
        </p>
      )}

      {/* 对话区 */}
      <section className="rounded-2xl border border-black/10 dark:border-white/15 flex flex-col flex-1 min-h-[280px] mb-4 overflow-hidden">
        <h2 className="text-sm font-medium text-gray-500 px-4 pt-4 pb-2 shrink-0">
          与{PERSONA_LABELS[persona]}对话
        </h2>
        <div className="flex-1 overflow-y-auto px-4 space-y-3 min-h-0">
          {messages.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">说点什么吧～</p>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
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
        <form onSubmit={sendChat} className="p-3 border-t border-black/10 dark:border-white/15 flex gap-2 shrink-0">
          <input
            className="flex-1 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="输入消息…"
            disabled={chatSending}
          />
          <button
            type="submit"
            disabled={chatSending || !chatInput.trim()}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60 shrink-0"
          >
            发送
          </button>
        </form>
      </section>

      {/* 自然语言快捷录入 */}
      <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 shrink-0">
        <h2 className="text-sm font-medium text-gray-500 mb-2">一句话录入</h2>
        <p className="text-xs text-gray-400 mb-3">例如：「午饭30」「提醒我明天还花呗」</p>
        <form onSubmit={doParse} className="flex gap-2 mb-3">
          <input
            className="flex-1 rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
            value={parseInput}
            onChange={(e) => setParseInput(e.target.value)}
            placeholder="自然语言输入…"
            disabled={parseLoading}
          />
          <button
            type="submit"
            disabled={parseLoading || !parseInput.trim()}
            className="rounded-lg border border-black/15 dark:border-white/20 px-4 py-2 text-sm hover:bg-black/5 disabled:opacity-60 shrink-0"
          >
            {parseLoading ? "解析中…" : "解析"}
          </button>
        </form>

        {parseResult && (
          <div className="rounded-xl bg-black/5 dark:bg-white/10 p-3 text-sm">
            {parseResult.intent === "unknown" ? (
              <p className="text-gray-500">未能识别，请手动到记账/提醒页填写。</p>
            ) : (
              <>
                <p className="mb-2">
                  识别为：<strong>{parseResult.intent === "transaction" ? "记账" : "提醒"}</strong>
                </p>
                <pre className="text-xs text-gray-500 mb-3 overflow-x-auto">
                  {JSON.stringify(parseResult.data, null, 2)}
                </pre>
                <button
                  type="button"
                  onClick={confirmParse}
                  disabled={confirming}
                  className="rounded-lg bg-green-600 text-white px-3 py-1.5 text-sm hover:bg-green-700 disabled:opacity-60"
                >
                  {confirming ? "写入中…" : "确认写入"}
                </button>
              </>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
