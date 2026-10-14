import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dos páginas: la tienda (index.html) y el panel del vendedor (vendedor.html).
// En desarrollo Vite sirve las dos solo; esto es para que `npm run build`
// también genere la del vendedor.
// El backend (uvicorn) corre en esta misma compu, en el puerto 8000.
const API_PROXY = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (ruta) => ruta.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  // host: true → también se puede abrir desde otros dispositivos del mismo
  // wifi (Vite muestra la dirección "Network" al arrancar).
  // proxy: la página le pasa al backend todo lo que empieza con /api. Así el
  // navegador habla con UNA sola dirección (la de la página), que es lo que
  // necesita el túnel de Cloudflare para compartir el proyecto por internet.
  // allowedHosts: deja entrar por los links de trycloudflare.com.
  server: { port: 5173, host: true, proxy: API_PROXY, allowedHosts: [".trycloudflare.com"] },
  preview: { port: 4173, host: true, proxy: API_PROXY, allowedHosts: [".trycloudflare.com"] },
  build: {
    rollupOptions: {
      input: {
        tienda: fileURLToPath(new URL("./index.html", import.meta.url)),
        vendedor: fileURLToPath(new URL("./vendedor.html", import.meta.url)),
      },
    },
  },
});
