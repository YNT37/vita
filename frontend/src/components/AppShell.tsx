"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/", label: "管家", icon: "🤖" },
  { href: "/stats", label: "统计", icon: "📊" },
  { href: "/records", label: "记账", icon: "💰" },
  { href: "/reminders", label: "提醒", icon: "⏰" },
  { href: "/user", label: "我的", icon: "👤" },
];

function isNavActive(pathname: string, href: string) {
  if (href === "/user") {
    return pathname === "/user" || pathname.startsWith("/settings");
  }
  return pathname === href;
}

function NavLinks({ vertical }: { vertical?: boolean }) {
  const pathname = usePathname();

  return (
    <>
      {NAV.map((item) => {
        const active = isNavActive(pathname, item.href);
        if (vertical) {
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                active
                  ? "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                  : "text-gray-600 hover:bg-black/5 dark:text-gray-400 dark:hover:bg-white/5"
              }`}
            >
              <span className="text-lg leading-none w-6 text-center">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        }
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] sm:text-xs transition-colors min-w-0 ${
              active ? "text-blue-600" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <span className="text-lg leading-none">{item.icon}</span>
            <span className="truncate max-w-full">{item.label}</span>
          </Link>
        );
      })}
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const isAuthPage = pathname === "/login" || pathname === "/register";

  if (isAuthPage || loading || !user) {
    return <div className="min-h-dvh flex flex-col">{children}</div>;
  }

  return (
    <div className="min-h-dvh flex flex-col md:flex-row">
      {/* 桌面侧栏 */}
      <aside className="hidden md:flex md:w-52 lg:w-60 shrink-0 flex-col border-r border-black/10 dark:border-white/15 bg-[var(--background)] sticky top-0 h-dvh">
        <div className="px-4 pt-5 pb-4">
          <p className="text-lg font-semibold tracking-tight">Vita</p>
          <p className="text-xs text-gray-400 mt-0.5 truncate">AI 生活管家</p>
        </div>
        <nav className="flex-1 px-2 space-y-0.5 overflow-y-auto">
          <NavLinks vertical />
        </nav>
        <div className="px-4 py-3 text-[11px] text-gray-400 border-t border-black/5 dark:border-white/10">
          @{user.username}
        </div>
      </aside>

      {/* 主内容：手机预留底栏高度 + safe-area */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0 pb-[calc(3.5rem+env(safe-area-inset-bottom,0px))] md:pb-0 md:h-dvh md:overflow-y-auto">
        {children}
      </div>

      {/* 手机底栏 */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-50 border-t border-black/10 dark:border-white/15 bg-[var(--background)]/95 backdrop-blur supports-[backdrop-filter]:bg-[var(--background)]/80"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        <div className="flex max-w-lg mx-auto h-14">
          <NavLinks />
        </div>
      </nav>
    </div>
  );
}
