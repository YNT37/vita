"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api";
import { type PersonaId, PERSONA_LABELS, PERSONA_OPTIONS } from "@/lib/persona";

type AiProvider = "openai" | "anthropic";

type SettingsData = {
  persona: PersonaId;
  persona_options: PersonaId[];
  ai_provider: AiProvider;
  ai_provider_options: AiProvider[];
  ai_configured: boolean;
  ai_api_key_set: boolean;
  ai_api_key_source: "user" | "env" | "none";
  ai_api_key_hint: string | null;
  ai_base_url: string;
  ai_base_url_source: "user" | "env" | "none";
  ai_model: string;
  ai_model_source: "user" | "env" | "none";
};

const PROVIDER_LABELS: Record<AiProvider, string> = {
  openai: "OpenAI 兼容",
  anthropic: "Anthropic",
};

const PROVIDER_DEFAULTS: Record<AiProvider, { baseUrl: string; model: string }> = {
  openai: {
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
  },
  anthropic: {
    baseUrl: "",
    model: "claude-3-5-haiku-latest",
  },
};

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [persona, setPersona] = useState<PersonaId>("butler");
  const [provider, setProvider] = useState<AiProvider>("openai");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrl, setBaseUrl] = useState(PROVIDER_DEFAULTS.openai.baseUrl);
  const [model, setModel] = useState(PROVIDER_DEFAULTS.openai.model);
  const [keyHint, setKeyHint] = useState<string | null>(null);
  const [keySource, setKeySource] = useState<"user" | "env" | "none">("none");
  const [configured, setConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const applyResponse = (res: SettingsData) => {
    setPersona(res.persona);
    setProvider(res.ai_provider);
    setBaseUrl(res.ai_base_url);
    setModel(res.ai_model);
    setKeyHint(res.ai_api_key_hint);
    setKeySource(res.ai_api_key_source);
    setConfigured(res.ai_configured);
    setApiKeyInput("");
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch<SettingsData>("/api/settings");
      applyResponse(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  function switchProvider(next: AiProvider) {
    setProvider(next);
    const defaults = PROVIDER_DEFAULTS[next];
    setBaseUrl(defaults.baseUrl);
    setModel(defaults.model);
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaved(false);
    setSaving(true);
    try {
      const body: Record<string, string> = {
        persona,
        ai_provider: provider,
        ai_base_url: baseUrl.trim(),
        ai_model: model.trim(),
      };
      if (apiKeyInput.trim()) {
        body.ai_api_key = apiKeyInput.trim();
      }
      const res = await apiFetch<SettingsData>("/api/settings", {
        method: "POST",
        body,
      });
      applyResponse(res);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function clearUserAiConfig() {
    setError("");
    setSaving(true);
    try {
      const res = await apiFetch<SettingsData>("/api/settings", {
        method: "POST",
        body: {
          ai_provider: "",
          ai_api_key: "",
          ai_base_url: "",
          ai_model: "",
        },
      });
      applyResponse(res);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "清除失败");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  const statusText = configured
    ? "AI 已配置，可使用真实对话"
    : "AI 未完整配置，将使用降级文案";

  const isAnthropic = provider === "anthropic";

  return (
    <main className="flex-1 p-4 max-w-2xl mx-auto w-full">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">设置</h1>
        <p className="text-sm text-gray-500">管家性格与 AI 接口</p>
      </header>

      {loading ? (
        <p className="text-sm text-gray-500">加载中…</p>
      ) : (
        <form onSubmit={saveSettings} className="space-y-6">
          <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4">
            <h2 className="text-sm font-medium mb-3">管家性格</h2>
            <div className="grid grid-cols-2 gap-2">
              {PERSONA_OPTIONS.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPersona(id)}
                  className={`rounded-xl border px-3 py-3 text-sm text-left transition-colors ${
                    persona === id
                      ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/30"
                      : "border-black/15 dark:border-white/20 hover:border-blue-300"
                  }`}
                >
                  <span className="font-medium">{PERSONA_LABELS[id]}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-black/10 dark:border-white/15 p-4 space-y-3">
            <div>
              <h2 className="text-sm font-medium">AI 接口</h2>
              <p className="text-xs text-gray-400 mt-1">
                支持 OpenAI 兼容（OpenAI / DeepSeek / 中转）与 Anthropic 原生接口。
              </p>
              <p className={`text-xs mt-2 ${configured ? "text-green-600" : "text-amber-600"}`}>
                {statusText}
                {keyHint ? ` · Key: ${keyHint}` : ""}
                {keySource === "env" ? "（服务器默认）" : keySource === "user" ? "（你的配置）" : ""}
              </p>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-2">接口类型</label>
              <div className="grid grid-cols-2 gap-2">
                {(["openai", "anthropic"] as AiProvider[]).map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => switchProvider(id)}
                    className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
                      provider === id
                        ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/30"
                        : "border-black/15 dark:border-white/20 hover:border-blue-300"
                    }`}
                  >
                    {PROVIDER_LABELS[id]}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">API Key</label>
              <input
                type="password"
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={isAnthropic ? "sk-ant-..." : "不修改请留空"}
                autoComplete="off"
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Base URL{isAnthropic ? "（可选）" : ""}
              </label>
              <input
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={
                  isAnthropic
                    ? "留空使用官方 api.anthropic.com"
                    : "https://api.openai.com/v1"
                }
              />
              <p className="text-xs text-gray-400 mt-1">
                {isAnthropic
                  ? "仅在使用代理/中转时填写"
                  : "DeepSeek 填 https://api.deepseek.com"}
              </p>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Model</label>
              <input
                className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={isAnthropic ? "claude-3-5-haiku-latest" : "gpt-4o-mini"}
              />
            </div>

            {keySource === "user" && (
              <button
                type="button"
                onClick={clearUserAiConfig}
                disabled={saving}
                className="text-xs text-red-500 hover:underline disabled:opacity-50"
              >
                清除我的 AI 配置（回退到服务器默认）
              </button>
            )}
          </section>

          {error && (
            <p className="text-sm text-red-500 rounded-lg bg-red-50 dark:bg-red-950/30 px-3 py-2">
              {error}
            </p>
          )}
          {saved && <p className="text-sm text-green-600">已保存</p>}

          <button
            type="submit"
            disabled={saving}
            className="w-full rounded-lg bg-blue-600 text-white py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? "保存中…" : "保存设置"}
          </button>
        </form>
      )}
    </main>
  );
}
