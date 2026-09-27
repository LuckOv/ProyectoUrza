import { useEffect, useState } from "react";

import { pesos } from "../formato.js";
import * as api from "./api.js";
import { ESTADOS, EtiquetaEstado, Icono, fechaCorta, fechaHora, iso, useAviso } from "./comunes.jsx";

/* Comentario editable en la misma fila: se guarda al salir del campo. */
function Comentario({ pedido, onGuardado, onError }) {
  const [texto, setTexto] = useState(pedido.comentario);
  const [estado, setEstado] = useState("");   // "" | "guardando" | "listo"

  useEffect(() => { setTexto(pedido.comentario); }, [pedido.comentario]);

  async function guardar() {
    if (texto.trim() === pedido.comentario) return;
    setEstado("guardando");
    try {
      onGuardado(await api.cambiarPedido(pedido.id, { comentario: texto }));
      setEstado("listo");
      setTimeout(() => setEstado(""), 1500);
    } catch (e) {
      setEstado("");
      onError(e.message);
    }
  }

  return (
    <div className="comentario-celda">
      <textarea
        rows="2"
        value={texto}
        placeholder="Agregar comentario…"
        onChange={(e) => setTexto(e.target.value)}
        onBlur={guardar}
        aria-label={`Comentario del pedido ${pedido.id}`}
      />
      {estado === "guardando" && <span className="apagado chico">Guardando…</span>}
      {estado === "listo" && <span className="guardado"><Icono nombre="check" tam={13} /> Guardado</span>}
    </div>
  );
}

export default function Historial() {
  const hoy = new Date();
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState("");
  const [desde, setDesde] = useState(iso(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 30)));
  const [hasta, setHasta] = useState(iso(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() + 60)));
  const [por, setPor] = useState("pedido");
  const [pedidos, setPedidos] = useState(null);
  const [error, setError] = useState("");
  const [avisar, aviso] = useAviso();

  const filtros = { q: q.trim(), estado, desde, hasta, por };

  useEffect(() => {
    // Pausa corta para que la búsqueda no dispare un pedido por tecla.
    const t = setTimeout(() => {
      api.pedidos(filtros)
        .then((r) => {
          // Lo más nuevo arriba.
          const orden = por === "pedido"
            ? (a, b) => b.creado.localeCompare(a.creado)
            : (a, b) => `${b.fecha_retiro} ${b.hora_retiro}`.localeCompare(`${a.fecha_retiro} ${a.hora_retiro}`);
          setPedidos([...r.pedidos].sort(orden));
          setError("");
        })
        .catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [q, estado, desde, hasta, por]);   // eslint-disable-line react-hooks/exhaustive-deps

  const reemplazar = (p) => setPedidos((ps) => ps.map((x) => (x.id === p.id ? p : x)));

  return (
    <section>
      <div className="cabecera">
        <div>
          <h1>Historial</h1>
          <p>Protocolo de todos los pedidos: quién, qué, cuándo retira y tus comentarios.</p>
        </div>
      </div>

      <div className="barra-herramientas">
        <label className="buscador ancho-medio">
          <Icono nombre="buscar" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar carta, pedido o nombre…"
                 aria-label="Buscar carta, pedido o nombre" />
        </label>
        <label className="selector">
          <Icono nombre="filtro" />
          <select value={estado} onChange={(e) => setEstado(e.target.value)} aria-label="Estado">
            <option value="">Todos los estados</option>
            {Object.entries(ESTADOS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </select>
        </label>
        <div className="rango">
          <Icono nombre="calendario" />
          <select value={por} onChange={(e) => setPor(e.target.value)} aria-label="Filtrar fechas por">
            <option value="pedido">Fecha de pedido</option>
            <option value="retiro">Fecha de retiro</option>
          </select>
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} aria-label="Desde" />
          <span>—</span>
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} aria-label="Hasta" />
        </div>
        <button
          className="boton primario empujar"
          onClick={() => api.exportarHistorial(filtros).catch((e) => avisar(e.message, true))}
        >
          <Icono nombre="descargar" /> Exportar CSV
        </button>
      </div>

      {error && <p className="hoja error-texto">{error}</p>}

      <div className="hoja tabla-hoja">
        <table className="protocolo">
          <thead>
            <tr>
              <th>Fecha y hora de retiro</th>
              <th>Fecha y hora de pedido</th>
              <th>Nombre del pedido</th>
              <th className="num">Unidades</th>
              <th>Detalle</th>
              <th>Comentario <span className="apagado">(lo pone el vendedor)</span></th>
            </tr>
          </thead>
          <tbody>
            {pedidos === null && (
              <tr><td colSpan="6" className="cargando">Cargando…</td></tr>
            )}
            {pedidos?.length === 0 && (
              <tr><td colSpan="6" className="vacio">No hay pedidos con esos filtros.</td></tr>
            )}
            {pedidos?.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{fechaCorta(p.fecha_retiro)} · {p.hora_retiro}</strong>
                  <div><EtiquetaEstado estado={p.estado} /></div>
                </td>
                <td>{fechaHora(p.creado)}<div className="apagado chico">{p.origen === "chat" ? "Por el chat" : "Cargado a mano"}</div></td>
                <td>
                  <span className="apagado">#{p.id}</span> {p.nombre} {p.apellido}
                </td>
                <td className="num"><strong>{p.unidades}</strong></td>
                <td>
                  <ul className="detalle">
                    {p.items.map((i, k) => (
                      <li key={k}>{i.cantidad} × {i.nombre} <span className="apagado">({i.set_nombre} · {i.grado})</span></li>
                    ))}
                  </ul>
                  <span className="total">{pesos(p.total)}</span>
                </td>
                <td>
                  <Comentario pedido={p} onGuardado={reemplazar} onError={(m) => avisar(m, true)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {aviso}
    </section>
  );
}
