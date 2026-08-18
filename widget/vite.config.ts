import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  resolve: {
    alias: {
      "@eylo": path.resolve(__dirname, "./src/"),
      "@eylo/*": path.resolve(__dirname, "./src/*"),
    },
  },
});
