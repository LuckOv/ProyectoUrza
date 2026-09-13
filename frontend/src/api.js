/* Único lugar donde el frontend sabe hablar con el backend.
   Guarda el token en localStorage para que la sesión sobreviva a un F5. */

const API = "http://localhost:8000";
const LLAVE = "urza_token";

export const leerToken = () => localStorage.getItem(LLAVE) || "";
export const guardarToken = (t) => localStorage.setItem(LLAVE, t);
export const borrarToken = () => localStorage.removeItem(LLAVE);

async function pedir(ruta, { metodo = "GET", cuerpo, conToken = true } = {}) {
  const cabeceras = { "Content-Type": "application/json" };
  const token = leerToken();
  if (conToken && token) cabeceras.Authorization = `Bearer ${token}`;

  let r;
  try {
    r = await fetch(`${API}${ruta}`, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new Error(`No pude contactar la API en ${API}. Fijate que uvicorn esté corriendo.`);
  }

  if (r.status === 204) return null;
  const datos = await r.json().catch(() => ({}));

  if (!r.ok) {
    // La sesión venció o el token no vale: lo tiramos para no arrastrar basura.
    if (r.status === 401) borrarToken();
    throw new Error(datos.detail || `Error ${r.status}`);
  }
  return datos;
}

export const registrar = (usuario, clave) =>
  pedir("/registro", { metodo: "POST", cuerpo: { usuario, clave }, conToken: false });

export const ingresar = (usuario, clave) =>
  pedir("/login", { metodo: "POST", cuerpo: { usuario, clave }, conToken: false });

export const salir = () => pedir("/logout", { metodo: "POST" });
export const quienSoy = () => pedir("/yo");

export const verCarrito = () => pedir("/carrito");
export const agregarAlCarrito = (item) => pedir("/carrito", { metodo: "POST", cuerpo: item });
export const quitarDelCarrito = (id) => pedir(`/carrito/${id}`, { metodo: "DELETE" });
export const vaciarCarrito = () => pedir("/carrito", { metodo: "DELETE" });

export const preguntar = (thread_id, texto) =>
  pedir("/chat", { metodo: "POST", cuerpo: { thread_id, texto } });
