import { useEffect, useState } from "react";

import * as api from "./api.js";
import { Etiqueta, Icono, TIPOS_MOVIMIENTO, fechaHora, haceCuanto } from "./comunes.jsx";

// Filtros por grupo: cada opción junta varios tipos de movimiento.
const GRUPOS = [
  { id: "", texto: "Todo" },
  { id: "reserva,estado,venta,devolucion,pedido", texto: "Pedidos y estados" },
  { id: "comentario", texto: "Comentarios" },
  { id: "entrada,ajuste,edicion,baja", texto: "Stock e inventario" },
  { id: "config", texto: "Configuración y descuentos" },
];

/* Todo lo que pasó en la tienda, del más nuevo al más viejo: pedidos y sus
   cambios de estado (incluso volver a "pendiente"), comentarios agregados o
   editados, retiros reprogramados, altas y ajustes de stock, y cambios de
   horarios, dólar y descuentos. */
export default function RegistroActividad() {
  const [movimientos, setMovimientos] = useState(null);
  const [hayMas, setHayMas] = useState(false);
  const [tipo, setTipo] = useState("");
  const [q, setQ] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  async function cargar(mas = false) {
    setCargando(true);
    try {
      const antes = mas && movimientos?.length ? movimientos[movimientos.length - 1].id : undefined;
      const r = await api.actividad({ tipo, q: q.trim(), limite: 30, antes_de: antes });
      setMovimientos((m) => (mas ? [...(m || []), ...r.movimientos] : r.movimientos));
      setHayMas(r.hay_mas);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }

  // Pausa corta para que la búsqueda no dispare un pedido por tecla.
  useEffect(() => {
    const t = setTimeout(() => cargar(false), 250);
    return () => clearTimeout(t);
  }, [tipo, q]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="bloque registro">
      <div className="bloque-cabeza">
        <div>
          <h3>Registro de actividad</h3>
          <p className="ayuda">Cada cambio que se hace en la tienda queda anotado acá, con fecha y hora.</p>
        </div>
        <button className="boton chico" onClick={() => cargar(false)} disabled={cargando}>Actualizar</button>
      </div>

      <div className="registro-filtros">
        <label className="buscador ancho-medio">
          <Icono nombre="buscar" />
          <input value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Buscar pedido, carta o nombre…" aria-label="Buscar en el registro" />
        </label>
        <div className="segmentado envolvente" role="radiogroup" aria-label="Tipo de actividad">
          {GRUPOS.map((g) => (
            <button key={g.id || "todo"} role="radio" aria-checked={tipo === g.id}
                    className={tipo === g.id ? "activo" : ""} onClick={() => setTipo(g.id)}>
              {g.texto}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="error-texto">{error}</p>}
      {movimientos === null && !error && <p className="cargando">Cargando…</p>}
      {movimientos?.length === 0 && <p className="vacio">No hay movimientos con esos filtros.</p>}

      <ul className="actividad">
        {(movimientos || []).map((m) => {
          const t = TIPOS_MOVIMIENTO[m.tipo] || { texto: m.tipo, tono: "neutro" };
          return (
            <li key={m.id}>
              <div>
                <p className="actividad-titulo">{m.titulo}</p>
                {m.detalle && <p className="apagado">{m.detalle}</p>}
              </div>
              <div className="actividad-lado">
                <Etiqueta tono={t.tono}>{t.texto}</Etiqueta>
                <span className="apagado" title={fechaHora(m.fecha)}>{haceCuanto(m.fecha)}</span>
              </div>
            </li>
          );
        })}
      </ul>

      {hayMas && (
        <button className="boton ancho" onClick={() => cargar(true)} disabled={cargando}>
          {cargando ? "Cargando…" : "Cargar más"}
        </button>
      )}
    </section>
  );
}
