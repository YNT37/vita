"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!username.trim() || !password) {
      setError("请填写用户名和密码");
      return;
    }
    setLoading(true);
    try {
      await login(username.trim(), password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败，请稍后再试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex-1 grid place-items-center p-6">
      <div className="w-full max-w-sm rounded-2xl border border-black/10 dark:border-white/15 p-8 shadow-sm">
        <h1 className="text-2xl font-semibold mb-1">登录 Vita</h1>
        <p className="text-sm text-gray-500 mb-6">你的 AI 生活管家</p>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm mb-1">用户名</label>
            <input
              className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm mb-1">密码</label>
            <input
              type="password"
              className="w-full rounded-lg border border-black/15 dark:border-white/20 bg-transparent px-3 py-2 outline-none focus:border-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 text-white py-2 font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "登录中…" : "登录"}
          </button>
        </form>
        <p className="text-sm text-gray-500 mt-4">
          还没有账号？{" "}
          <Link href="/register" className="text-blue-600 hover:underline">
            去注册
          </Link>
        </p>
      </div>
    </main>
  );
}
