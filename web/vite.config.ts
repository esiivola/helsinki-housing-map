import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: process.env.VITE_BASE_PATH ?? "/",
  publicDir: process.env.VITE_SKIP_PUBLIC === "1" ? false : (process.env.VITE_PUBLIC_DIR ?? "public"),
  plugins: [react()],
  server: {
    // The static release ships hundreds of thousands of tile files under
    // public/data (and data/work). Letting the dev-server file watcher index
    // them pegs the Vite process at ~420% CPU and starves every request
    // (~100 s for the 4.5 MB manifest.json, tiles effectively never arrive).
    // The data is static during dev, so exclude it from the watcher; native
    // static serving then responds in single-digit milliseconds.
    watch: { ignored: ["**/public/data/**", "**/data/work/**"] },
  },
});
