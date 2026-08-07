// src/components/ThemeToggle.jsx
// Small sun/moon switch. Lives in the sidebar footer, next to the version badge.

export default function ThemeToggle({ theme, onToggle, collapsed = false }) {
  const isDark = theme === "dark";
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      className={`bb-theme-toggle${collapsed ? " collapsed" : ""}`}
      onClick={onToggle}
      aria-label={label}
      title={label}
    >
      <span className="bb-theme-toggle-icon" aria-hidden="true">
        {isDark ? (
          // Moon
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path
              d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"
              fill="currentColor"
            />
          </svg>
        ) : (
          // Sun
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="4.2" fill="currentColor" />
            <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M12 2.5v2.4M12 19.1v2.4M4.2 4.2l1.7 1.7M18.1 18.1l1.7 1.7M2.5 12h2.4M19.1 12h2.4M4.2 19.8l1.7-1.7M18.1 5.9l1.7-1.7" />
            </g>
          </svg>
        )}
      </span>
      {!collapsed && (isDark ? "Dark mode" : "Light mode")}
    </button>
  );
}
