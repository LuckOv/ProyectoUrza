import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dos páginas: la tienda (index.html) y el panel del vendedor (vendedor.html).
// En desarrollo Vite sirve las dos solo; esto es para que `npm run build`
// también genere la del vendedor.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      input: {
        tienda: fileURLToPath(new URL("./index.html", import.meta.url)),
        vendedor: fileURLToPath(new URL("./vendedor.html", import.meta.url)),
      },
    },
  },
});
