/* Único lugar donde el frontend sabe hablar con el backend.
   No hay cuentas: el carrito se identifica con el thread_id de la charla. */

const API = "http://localhost:8000";

async function pedir(ruta, { metodo = "GET", cuerpo } = {}) {
  let r;
  try {
    r = await fetch(`${API}${ruta}`, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new Error(`No pude contactar la API en ${API}. Fijate que uvicorn esté corriendo.`);
  }

  if (r.status === 204) return null;
  const datos = await r.json().catch(() => ({}));

  if (!r.ok) throw new Error(datos.detail || `Error ${r.status}`);
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
