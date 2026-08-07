// src/hooks/useSidebarCollapsed.js
// Sidebar collapsed/expanded state, persisted to localStorage. This is a
// pure client-rendered SPA (no SSR), so reading localStorage synchronously
// in useState's initializer means the first paint is already correct —
// no collapse-flash the way a server-rendered app would need to guard against.

import { useEffect, useState } from "react";

const STORAGE_KEY = "billbro-sidebar-collapsed";

function getInitial() {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "true";
}

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(getInitial);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  const toggleCollapsed = () => setCollapsed((c) => !c);

  return { collapsed, toggleCollapsed };
}
