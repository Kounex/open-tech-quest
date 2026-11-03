import { defineConfig } from "vite";
export default defineConfig({
  base: "/plugins/open_tech_quest/assets/app/",
  build: {
    rollupOptions: {
      output: {
        entryFileNames: "quest.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (asset) =>
          asset.names?.some((name) => name.endsWith(".css"))
            ? "quest.css"
            : "[name]-[hash][extname]",
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/files": "http://127.0.0.1:8000",
    },
  },
});
