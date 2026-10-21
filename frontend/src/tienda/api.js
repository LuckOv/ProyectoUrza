/* Único lugar donde el frontend sabe hablar con el backend.
   No hay cuentas: el carrito se identifica con el thread_id de la charla. */

// Los pedidos van a /api en la MISMA dirección de la página y Vite se los
// pasa al backend (ver vite.config.js). Así anda igual en esta compu y desde
// el celular u otra compu del mismo wifi.
// Para apuntar a otro backend: VITE_API=http://... en frontend/.env
const API = import.meta.env.VITE_API || "/api";

async function pedir(ruta, { metodo = "GET", cuerpo } = {}) {
  let r;
  try {
    r = await fetch(`${API}${ruta}`, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new Error("No pude contactar el servidor de URZA. Fijate que el backend (uvicorn) esté corriendo.");
  }

  if (r.status === 204) return null;
  const datos = await r.json().catch(() => ({}));

  // FastAPI manda detail como texto (errores nuestros) o como lista (validación).
  const detalle = Array.isArray(datos.detail) ? datos.detail.map((d) => d.msg).join(" · ") : datos.detail;
  // Si el backend está apagado, el proxy de Vite responde 500/502 sin detalle.
  if (!r.ok && !detalle && r.status >= 500) {
    throw new Error("No pude contactar el servidor de URZA. Fijate que el backend (uvicorn) esté corriendo.");
  }
  if (!r.ok) throw new Error(detalle || `Error ${r.status}`);
  return datos;
}

const id = encodeURIComponent;

export const verCarrito = (threadId) => pedir(`/carrito/${id(threadId)}`);
export const agregarAlCarrito = (threadId, item) =>
  pedir(`/carrito/${id(threadId)}`, { metodo: "POST", cuerpo: item });
export const quitarDelCarrito = (threadId, itemId) =>
  pedir(`/carrito/${id(threadId)}/${itemId}`, { metodo: "DELETE" });
export const vaciarCarrito = (threadId) =>
  pedir(`/carrito/${id(threadId)}`, { metodo: "DELETE" });

export const preguntar = (thread_id, texto) =>
  pedir("/chat", { metodo: "POST", cuerpo: { thread_id, texto } });

export const catalogo = () => pedir("/catalogo");

export const autocompletarCartas = (q) => pedir(`/cartas/autocompletar?q=${encodeURIComponent(q)}`);
export const impresionesCartas = (nombre) => pedir(`/cartas/impresiones?nombre=${encodeURIComponent(nombre)}`);
export const enviarPropuesta = (datos) => pedir("/propuestas", { metodo: "POST", cuerpo: datos });
