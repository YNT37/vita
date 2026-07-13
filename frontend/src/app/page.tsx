"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="flex-1 grid place-items-center text-gray-500">加载中…</main>
    );
  }

  return (
    <main className="flex-1 p-6 max-w-3xl mx-auto w-full">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold">Vita · 仪表盘</h1>
          <p className="text-sm text-gray-500">你好，{user.username}</p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg border border-black/15 dark:border-white/20 px-3 py-1.5 text-sm hover:bg-black/5 dark:hover:bg-white/10"
        >
          退出登录
        </button>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <NavCard href="/records" title="记账" desc="记一笔 · 收支统计" />
        <NavCard href="/reminders" title="提醒" desc="待办 · 账单到期" />
        <NavCard href="/persona" title="AI 管家" desc="角色对话 · 每日播报" />
      </div>
    </main>
  );
}

function NavCard({
  href,
  title,
  desc,
}: {
  href: string;
  title: string;
  desc: string;
}) {
  return (
    <Link
      href={href}
      className="rounded-2xl border border-black/10 dark:border-white/15 p-5 hover:shadow-md transition-shadow"
    >
      <h2 className="font-medium mb-1">{title}</h2>
      <p className="text-sm text-gray-500">{desc}</p>
    </Link>
  );
}
