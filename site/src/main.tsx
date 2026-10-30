import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { applyTheme, loadTheme } from "./lib/theme.ts";
import "./styles.css";

// Apply the stored theme before the first render to avoid a flash.
applyTheme(loadTheme());

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");
createRoot(root).render(<StrictMode><App /></StrictMode>);
