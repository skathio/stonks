// Vite builds the React dashboard from site/ into dist/. The encrypted payload
// (site/data) is not a Vite asset: tools/build.mjs verifies it and copies it.
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  root: "site",
  base: "./", // GitHub Pages serves under /stonks/
  publicDir: false,
  plugins: [react(), tailwindcss()],
  build: { outDir: "../dist", emptyOutDir: true, sourcemap: false },
});
