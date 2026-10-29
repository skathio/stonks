import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { applyTheme, loadTheme } from "./lib/theme.js";
import "./styles.css";

// Apply the stored theme before the first render to avoid a flash.
applyTheme(loadTheme());

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);
