import React, { createContext, useContext, useState, useCallback } from "react";

const STORAGE_KEY = "theme";

export function readStoredTheme() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark") return v;
    const legacy = localStorage.getItem("onetouch-theme");
    if (legacy === "light" || legacy === "dark") return legacy;
  } catch {
    /* ignore */
  }
  return "dark";
}

const ThemeContext = createContext({ theme: "dark", toggle: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readStoredTheme);

  const toggle = useCallback(() => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
