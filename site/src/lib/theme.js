// Theme preference: "auto" follows the OS; "light"/"dark" pin it. Stored per device.
const THEME_STORE = "stonks.theme";
export const THEMES = ["auto", "light", "dark"];

export function loadTheme() {
  try {
    const t = window.localStorage.getItem(THEME_STORE);
    return THEMES.includes(t) ? t : "auto";
  } catch {
    return "auto";
  }
}

export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  try {
    window.localStorage.setItem(THEME_STORE, theme);
  } catch { /* storage blocked: preference lasts this page view */ }
}

export function nextTheme(theme) {
  return THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
}
