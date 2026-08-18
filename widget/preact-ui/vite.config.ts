import preact from "@preact/preset-vite";
import { resolve } from "path";
import { defineConfig } from "vite";
import cssInjectedByJsPlugin from "vite-plugin-css-injected-by-js";
// https://vite.dev/config/
export default defineConfig({
  plugins: [preact(), cssInjectedByJsPlugin()],
  resolve: {
    alias: {
      "@eylo": resolve(__dirname, "../src"),
      "@eylo/*": resolve(__dirname, "../src/*"),
      react: "preact/compat",
      "react-dom/test-utils": "preact/test-utils",
      "react-dom": "preact/compat", // Must be below test-utils
      "react/jsx-runtime": "preact/jsx-runtime",
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    fs: {
      // Allow serving files from one level up to the project root
      allow: [".."],
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        assetFileNames: "eylo-widget.[ext]",
        entryFileNames: "eylo-widget.js",
      },
    },
  },
});
