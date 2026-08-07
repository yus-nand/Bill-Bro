// src/components/Sidebar.jsx
// Mirrors the st.sidebar nav block in app.py — grouped so related tabs sit
// together, and collapsible down to an icon-only rail for more screen room.

import { NavLink } from "react-router-dom";
import { API_BASE_URL, STORE_ID, APP_VERSION } from "../config.js";
import { useTheme } from "../hooks/useTheme.js";
import { useSidebarCollapsed } from "../hooks/useSidebarCollapsed.js";
import ThemeToggle from "./ThemeToggle.jsx";

export const NAV_GROUPS = [
  {
    label: "Store Operations",
    items: [
      { to: "/checkout", label: "Checkout", icon: "🛒" },
      { to: "/inventory", label: "Inventory", icon: "📦" },
      { to: "/alerts", label: "Alerts", icon: "🚨" },
    ],
  },
  {
    label: "Catalog & Management",
    items: [
      { to: "/add-item", label: "Add Item", icon: "➕" },
      { to: "/admin", label: "Admin", icon: "⚙️" },
      { to: "/models", label: "Models", icon: "🤖" },
    ],
  },
];

function CollapseIcon({ collapsed }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      style={{ transform: collapsed ? "rotate(180deg)" : "none" }}
    >
      <path
        d="M15 4L7 12l8 8"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Sidebar() {
  const { theme, toggleTheme } = useTheme();
  const { collapsed, toggleCollapsed } = useSidebarCollapsed();

  return (
    <aside className={`bb-sidebar${collapsed ? " collapsed" : ""}`}>
      <div className="bb-brand-row">
        <div className="bb-brand">
          <h1>{collapsed ? "🛍️" : "🛍️ BillBro"}</h1>
          {!collapsed && (
            <p className="bb-subtitle">Smart Grocery Checkout &amp; Inventory</p>
          )}
        </div>
        <button
          type="button"
          className="bb-collapse-toggle"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <CollapseIcon collapsed={collapsed} />
        </button>
      </div>

      <nav>
        {NAV_GROUPS.map((group) => (
          <div className="bb-nav-group" key={group.label}>
            {!collapsed && <p className="bb-nav-group-label">{group.label}</p>}
            <ul className="bb-nav">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) => (isActive ? "active" : "")}
                    title={collapsed ? item.label : undefined}
                  >
                    <span className="bb-nav-icon" aria-hidden="true">
                      {item.icon}
                    </span>
                    {!collapsed && item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="bb-sidebar-footer">
        <ThemeToggle theme={theme} onToggle={toggleTheme} collapsed={collapsed} />
        {!collapsed && (
          <>
            <hr className="bb-divider" />
            <p>
              Store: <code>{STORE_ID}</code>
            </p>
            <p>
              API: <code>{API_BASE_URL}</code>
            </p>
            <div className="bb-version-badge">Version: {APP_VERSION}</div>
          </>
        )}
      </div>
    </aside>
  );
}
