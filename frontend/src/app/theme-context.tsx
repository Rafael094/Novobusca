"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

/**
 * Light/dark theme store — mirrors CerberoFront's theme toggle.
 *
 * The dark mode is applied by toggling the `dark` class on <body> (same
 * mechanism as CerberoFront's `body.dark`), which flips the CSS custom
 * properties declared in globals.css. The choice is persisted in localStorage
 * and falls back to the OS preference on first visit.
 */
const STORAGE_KEY = "intelliinpi.theme";

type Theme = "light" | "dark";

type ThemeContextValue = {
  isDark: boolean;
  toggle: () => void;
  setTheme: (t: Theme) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function applyBodyClass(isDark: boolean) {
  if (typeof document === "undefined") return;
  document.body.classList.toggle("dark", isDark);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [isDark, setIsDark] = useState(false);

  // Resolve the initial theme once on mount (localStorage > OS preference).
  useEffect(() => {
    let initial: Theme = "light";
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (saved === "light" || saved === "dark") {
        initial = saved;
      } else if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
        initial = "dark";
      }
    } catch {
      /* ignore storage access errors */
    }
    const dark = initial === "dark";
    setIsDark(dark);
    applyBodyClass(dark);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    const dark = t === "dark";
    setIsDark(dark);
    applyBodyClass(dark);
    try {
      window.localStorage.setItem(STORAGE_KEY, t);
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = useCallback(() => {
    setTheme(isDark ? "light" : "dark");
  }, [isDark, setTheme]);

  return (
    <ThemeContext.Provider value={{ isDark, toggle, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    // Safe fallback so a component used outside the provider still renders.
    return { isDark: false, toggle: () => {}, setTheme: () => {} };
  }
  return ctx;
}
