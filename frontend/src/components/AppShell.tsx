"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/", label: "管家", icon: "🤖" },
  { href: "/stats", label: "统计", icon: "📊" },
  { href: "/records", label: "记账", icon: "💰" },
  { href: "/reminders", label: "提醒", icon: "⏰" },
  { href: "/settings", label: "设置", icon: "⚙️" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const isAuthPage = pathname === "/login" || pathname === "/register";

  if (isAuthPage || loading || !user) {
    return <>{children}</>;
  }

  return (
    <>
      <div className="flex-1 flex flex-col min-h-0 pb-16">{children}</div>
      <nav className="fixed bottom-0 inset-x-0 border-t border-black/10 dark:border-white/15 bg-[var(--background)]/95 backdrop-blur z-50">
        <div className="max-w-2xl mx-auto flex">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex-1 flex flex-col items-center py-2 text-xs transition-colors ${
                  active ? "text-blue-600" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <span className="text-lg leading-none mb-0.5">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
