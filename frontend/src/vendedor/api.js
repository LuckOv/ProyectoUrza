/* Cliente de los endpoints /vendedor. La clave viaja en el header
   X-Vendedor-Clave; se guarda en sessionStorage, así al cerrar el
   navegador hay que volver a entrar. */

// Los pedidos van a /api en la MISMA dirección de la página y Vite se los
// pasa al backend (ver vite.config.js). Así anda igual en esta compu, desde
// el celular por wifi y por el link del túnel de Cloudflare.
// Para apuntar a otro backend: VITE_API=http://... en frontend/.env
const API = import.meta.env.VITE_API || "/api";
const LLAVE = "urza_vendedor";

function leer() { try { return sessionStorage.getItem(LLAVE) || ""; } catch { return ""; } }
export const hayClave = () => Boolean(leer());
export const guardarClave = (c) => { try { sessionStorage.setItem(LLAVE, c); } catch { /* sin storage */ } };
export const olvidarClave = () => { try { sessionStorage.removeItem(LLAVE); } catch { /* sin storage */ } };

let alVencer = () => {};
export const cuandoVenza = (fn) => { alVencer = fn; };

async function pedir(ruta, { metodo = "GET", cuerpo, crudo = false, clave } = {}) {
  let r;
  try {
    r = await fetch(`${API}${ruta}`, {
      method: metodo,
      headers: { "Content-Type": "application/json", "X-Vendedor-Clave": clave ?? leer() },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new Error("No pude contactar el servidor de URZA. Fijate que el backend (uvicorn) esté corriendo.");
  }
  if (r.status === 401 && ruta !== "/vendedor/entrar") {
    olvidarClave();
    alVencer();
  }
  if (crudo && r.ok) return r;
  const datos = await r.json().catch(() => ({}));
  const detalle = Array.isArray(datos.detail) ? datos.detail.map((d) => d.msg).join(" · ") : datos.detail;
  // Si el backend está apagado, el proxy de Vite responde 500/502 sin detalle.
  if (!r.ok && !detalle && r.status >= 500) {
    throw new Error("No pude contactar el servidor de URZA. Fijate que el backend (uvicorn) esté corriendo.");
  }
  if (!r.ok) throw new Error(detalle || `Error ${r.status}`);
  return datos;
}

const qs = (params) => {
  const limpio = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));
  const s = new URLSearchParams(limpio).toString();
  return s ? `?${s}` : "";
};

export const entrar = (clave) => pedir("/vendedor/entrar", { metodo: "POST", cuerpo: { clave }, clave });

export const inventario = (filtros = {}) => pedir(`/vendedor/inventario${qs(filtros)}`);
export const altaCarta = (datos) => pedir("/vendedor/inventario", { metodo: "POST", cuerpo: datos });
export const editarCarta = (id, datos) => pedir(`/vendedor/inventario/${id}`, { metodo: "PATCH", cuerpo: datos });
export const precioSugerido = (params) => pedir(`/vendedor/precio-sugerido${qs(params)}`);
export const nuevaVariante = (id, datos) =>
  pedir(`/vendedor/inventario/${id}/variante`, { metodo: "POST", cuerpo: datos });
export const borrarCartas = (ids) => pedir("/vendedor/inventario/borrar", { metodo: "POST", cuerpo: { ids } });

export const autocompletar = (q) => pedir(`/vendedor/scryfall/autocompletar${qs({ q })}`);
export const impresiones = (nombre) => pedir(`/vendedor/scryfall/impresiones${qs({ nombre })}`);

export const pedidos = (filtros = {}) => pedir(`/vendedor/pedidos${qs(filtros)}`);
export const nuevoPedido = (datos) => pedir("/vendedor/pedidos", { metodo: "POST", cuerpo: datos });
export const cambiarPedido = (id, datos) => pedir(`/vendedor/pedidos/${id}`, { metodo: "PATCH", cuerpo: datos });
export const borrarPedidos = (ids) => pedir("/vendedor/pedidos/borrar", { metodo: "POST", cuerpo: { ids } });

export async function exportarHistorial(filtros = {}) {
  const r = await pedir(`/vendedor/historial.csv${qs(filtros)}`, { crudo: true });
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `historial_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const dashboard = (dias = 30) => pedir(`/vendedor/dashboard${qs({ dias })}`);
export const actualizarMercado = () => pedir("/vendedor/mercado/actualizar", { metodo: "POST" });
export const mantenerPrecio = (id) => pedir(`/vendedor/inventario/${id}/mantener-precio`, { metodo: "POST" });

export const propuestas = (filtros = {}) => pedir(`/vendedor/propuestas${qs(filtros)}`);
export const cambiarPropuesta = (id, datos) => pedir(`/vendedor/propuestas/${id}`, { metodo: "PATCH", cuerpo: datos });
export const propuestaAlInventario = (id, datos) =>
  pedir(`/vendedor/propuestas/${id}/al-inventario`, { metodo: "POST", cuerpo: datos });
export const borrarPropuesta = (id) => pedir(`/vendedor/propuestas/${id}`, { metodo: "DELETE" });
export const actividad = (filtros = {}) => pedir(`/vendedor/actividad${qs(filtros)}`);

export const config = () => pedir("/vendedor/config");
export const bot = () => pedir("/vendedor/bot");
export const instalarBot = (partes) => pedir("/vendedor/bot/instalar", { metodo: "POST", cuerpo: { partes } });
export const cancelarBot = () => pedir("/vendedor/bot/cancelar", { metodo: "POST" });
export const guardarConfig = (datos) => pedir("/vendedor/config", { metodo: "PUT", cuerpo: datos });
export const actualizarDolar = () => pedir("/vendedor/config/dolar/actualizar", { metodo: "POST" });

export const descuentos = () => pedir("/vendedor/descuentos");
export const descuentoGeneral = (porcentaje) =>
  pedir("/vendedor/descuentos/general", { metodo: "PUT", cuerpo: { porcentaje } });
export const descuentoCartas = (ids, porcentaje) =>
  pedir("/vendedor/descuentos", { metodo: "POST", cuerpo: { ids, porcentaje } });
export const quitarDescuento = (id) => pedir(`/vendedor/descuentos/${id}`, { metodo: "DELETE" });
