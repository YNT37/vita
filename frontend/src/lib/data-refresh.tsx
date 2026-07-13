"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { usePathname } from "next/navigation";

type DataRefreshContextType = {
  version: number;
  bump: () => void;
};

const DataRefreshContext = createContext<DataRefreshContextType | undefined>(
  undefined
);

export function DataRefreshProvider({ children }: { children: React.ReactNode }) {
  const [version, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <DataRefreshContext.Provider value={{ version, bump }}>
      {children}
    </DataRefreshContext.Provider>
  );
}

export function useDataRefresh() {
  const ctx = useContext(DataRefreshContext);
  if (!ctx) throw new Error("useDataRefresh 必须在 DataRefreshProvider 内使用");
  return ctx;
}

/** 登录后自动加载；数据版本变化或切回本页时重新加载 */
export function useAutoReload(load: () => void | Promise<void>, enabled: boolean) {
  const pathname = usePathname();
  const { version } = useDataRefresh();

  useEffect(() => {
    if (!enabled) return;
    void load();
  }, [enabled, version, pathname, load]);
}
