"use client";

import { useState } from "react";

// Dev-only toggle for the whole page. The real theme toggle comes with the navbar (ROADMAP 1.5).
export default function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    setTheme(next);
  }

  return (
    <button type="button" onClick={toggle} aria-pressed={theme === "dark"} style={{
      minHeight: 44,
      padding: "0 18px",
      border: "1px solid var(--rule2)",
      borderRadius: 12,
      background: "var(--card)",
      color: "var(--ink)",
      font: "500 15px var(--sans)",
      cursor: "pointer",
    }}>
      Page theme: {theme}
    </button>
  );
}
