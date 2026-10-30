// Theme preference: "auto" follows the OS; "light"/"dark" pin it. Stored per device.
const THEME_STORE = "stonks.theme";
export const THEMES = ["auto", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

const isTheme = (t: unknown): t is Theme => THEMES.includes(t as Theme);

export function loadTheme(): Theme {
  try {
    const t = window.localStorage.getItem(THEME_STORE);
    return isTheme(t) ? t : "auto";
  } catch {
    return "auto";
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  try {
    window.localStorage.setItem(THEME_STORE, theme);
  } catch { /* storage blocked: preference lasts this page view */ }
}

export function nextTheme(theme: Theme): Theme {
  return THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length] ?? "auto";
}
