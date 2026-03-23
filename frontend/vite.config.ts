import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import pkg from "./package.json"

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  plugins: [
    react(),
    {
      name: "dev-static-prefix-rewrite",
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url?.startsWith("/static/")) {
            req.url = req.url.replace("/static/", "/")
          }
          next()
        })
      },
    },
  ],
  build: {
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        chunkFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        assetFileNames: `assets/[name]-[hash]-${Date.now()}.[ext]`
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: 8802,
    allowedHosts: true,  // Allow all hosts for flexible deployment
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8802',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8802',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./app"),
    },
  },
})
