// src/components/TopBar.jsx — replaces components/Sidebar.jsx.
//
// Moved off a fixed-width left sidebar onto a single horizontal bar: it's
// what makes the app actually usable on a phone (a 272px sidebar just
// doesn't fit), and it puts every page one tap away instead of nested
// under a collapse toggle. Below ~860px the nav collapses into a menu
// button that opens a full-width dropdown — same links, same grouping,
// just stacked instead of inline.

import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useTheme } from "../hooks/useTheme.js";
import { useTour } from "../context/TourContext.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import {
  IconCart,
  IconBox,
  IconAlert,
  IconPlus,
  IconSettings,
  IconCube,
  IconMenu,
  IconClose,
  IconHelp,
} from "./Icons.jsx";

export const NAV_ITEMS = [
  { to: "/checkout", label: "Checkout", Icon: IconCart },
  { to: "/inventory", label: "Inventory", Icon: IconBox },
  { to: "/alerts", label: "Alerts", Icon: IconAlert },
  { to: "/add-item", label: "Add Item", Icon: IconPlus },
  { to: "/admin", label: "Admin", Icon: IconSettings },
  { to: "/models", label: "Models", Icon: IconCube },
];

export default function TopBar() {
  const { theme, toggleTheme } = useTheme();
  const { start: startTour } = useTour();
  const [menuOpen, setMenuOpen] = useState(false);

  // Close the mobile menu on any resize back up to desktop width, so it
  // doesn't linger open (and mispositioned) if someone rotates a tablet
  // or resizes a browser window mid-session.
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 860) setMenuOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <header className="bb-topbar">
      <div className="bb-topbar-inner">
        <NavLink to="/checkout" className="bb-brand-link">
          <span className="bb-brand-mark" aria-hidden="true">
            B
          </span>
          <span className="bb-brand-name">BillBro</span>
        </NavLink>

        <nav className="bb-topbar-nav" aria-label="Main" data-tour="topnav">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="bb-topbar-actions">
          <button
            type="button"
            className="bb-icon-btn"
            onClick={startTour}
            aria-label="Take a guided tour"
            title="Take a guided tour"
          >
            <IconHelp />
          </button>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <button
            type="button"
            className="bb-icon-btn bb-menu-toggle"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <IconClose /> : <IconMenu />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav className="bb-mobile-menu" aria-label="Main (mobile)">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => (isActive ? "active" : "")}
              onClick={() => setMenuOpen(false)}
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
