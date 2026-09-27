import { useEffect, useMemo, useState } from "react";

import { pesos } from "../formato.js";
import * as api from "./api.js";
import {
  CLAVES_DIA, Confirmar, DIAS_CORTOS, ESTADOS, EtiquetaEstado, Icono, MESES, Modal,
  desdeIso, fechaHora, iso, useAviso,
} from "./comunes.jsx";

/* Las 6 semanas (lunes a domingo) que muestra el calendario de un mes. */
function semanasDelMes(anio, mes) {
  const primero = new Date(anio, mes, 1);
  const corrimiento = (primero.getDay() + 6) % 7;      // 0 = lunes
  const inicio = new Date(anio, mes, 1 - corrimiento);
  const dias = [];
  for (let i = 0; i < 42; i++) dias.push(new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + i));
  // Si la última semana es toda del mes siguiente, se saca.
  return dias.slice(35).every((d) => d.getMonth() !== mes) ? dias.slice(0, 35) : dias;
}

function EditarPedido({ pedido, onCerrar, onGuardado }) {
  const [estado, setEstado] = useState(pedido.estado);
  const [fecha, setFecha] = useState(pedido.fecha_retiro);
  const [hora, setHora] = useState(pedido.hora_retiro);
  const [comentario, setComentario] = useState(pedido.comentario);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function guardar() {
    setError("");
    setOcupado(true);
    try {
      onGuardado(await api.cambiarPedido(pedido.id, { estado, fecha_retiro: fecha, hora_retiro: hora, comentario }));
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Modal
      titulo={`Editar pedido #${pedido.id}`}
      subtitulo={`${pedido.nombre} ${pedido.apellido} · ${pesos(pedido.total)}`}
      onCerrar={onCerrar}
      ancho={480}
      pie={
        <>
          <button className="boton" onClick={onCerrar}>Cancelar</button>
          <button className="boton primario" onClick={guardar} disabled={ocupado}>
            {ocupado ? "Guardando…" : "Guardar"}
          </button>
        </>
      }
    >
      <div className="formulario">
        <label className="campo">
          <span>Estado</span>
          <select value={estado} onChange={(e) => setEstado(e.target.value)}>
            {Object.entries(ESTADOS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </select>
          {estado === "rechazada" && pedido.estado !== "rechazada" && (
            <small>Las cartas del pedido vuelven al stock.</small>
          )}
          {pedido.estado === "rechazada" && estado !== "rechazada" && (
            <small>Se vuelven a reservar las cartas (si todavía hay stock).</small>
          )}
        </label>
        <div className="fila-campos">
          <label className="campo">
            <span>Día de retiro</span>
            <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </label>
          <label className="campo">
            <span>Hora</span>
            <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
          </label>
        </div>
        <label className="campo">
          <span>Comentario del vendedor</span>
          <textarea rows="3" value={comentario} onChange={(e) => setComentario(e.target.value)} />
        </label>
        {error && <p className="error-texto">{error}</p>}
      </div>
    </Modal>
  );
}

function NuevoPedido({ fechaInicial, onCerrar, onCreado }) {
  const [inventario, setInventario] = useState([]);
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [fecha, setFecha] = useState(fechaInicial);
  const [hora, setHora] = useState("17:00");
  const [comentario, setComentario] = useState("");
  const [lineas, setLineas] = useState([]);     // [{carta, cantidad}]
  const [buscar, setBuscar] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => { api.inventario().then((r) => setInventario(r.items)).catch((e) => setError(e.message)); }, []);

  const opciones = useMemo(() => {
    const t = buscar.trim().toLowerCase();
    if (!t) return [];
    return inventario
      .filter((i) => i.cantidad > 0 && !lineas.some((l) => l.carta.id === i.id))
      .filter((i) => `${i.nombre} ${i.set_nombre} ${i.sku}`.toLowerCase().includes(t))
      .slice(0, 8);
  }, [buscar, inventario, lineas]);

  const total = lineas.reduce((s, l) => s + (l.carta.precio_ars || 0) * l.cantidad, 0);

  async function crear() {
    setError("");
    setOcupado(true);
    try {
      const p = await api.nuevoPedido({
        nombre, apellido, fecha_retiro: fecha, hora_retiro: hora, comentario,
        items: lineas.map((l) => ({ inventario_id: l.carta.id, cantidad: Number(l.cantidad) })),
      });
      onCreado(p);
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Modal
      titulo="Nuevo pedido"
      subtitulo="Para alguien que reservó por teléfono o en el local. Las cartas se reservan al crearlo."
      onCerrar={onCerrar}
      ancho={640}
      pie={
        <>
          <span className="pie-total">Total: <strong>{pesos(total)}</strong></span>
          <button className="boton" onClick={onCerrar}>Cancelar</button>
          <button className="boton primario" onClick={crear}
                  disabled={ocupado || !nombre.trim() || !apellido.trim() || !lineas.length}>
            {ocupado ? "Creando…" : "Crear pedido"}
          </button>
        </>
      }
    >
      <div className="formulario">
        <div className="fila-campos">
          <label className="campo"><span>Nombre</span><input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus /></label>
          <label className="campo"><span>Apellido</span><input value={apellido} onChange={(e) => setApellido(e.target.value)} /></label>
        </div>
        <div className="fila-campos">
          <label className="campo"><span>Día de retiro</span><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
          <label className="campo"><span>Hora</span><input type="time" value={hora} onChange={(e) => setHora(e.target.value)} /></label>
        </div>

        <div className="campo">
          <span>Cartas</span>
          <div className="autocompletar">
            <label className="buscador ancho">
              <Icono nombre="buscar" />
              <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar en el inventario (con stock)" />
            </label>
            {opciones.length > 0 && (
              <ul className="sugerencias-scryfall">
                {opciones.map((o) => (
                  <li key={o.id}>
                    <button onClick={() => { setLineas((l) => [...l, { carta: o, cantidad: 1 }]); setBuscar(""); }}>
                      {o.nombre} <span className="apagado">· {o.set_nombre} · {o.grado} · {pesos(o.precio_ars)} · {o.cantidad} u.</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {lineas.length > 0 && (
            <ul className="lineas">
              {lineas.map((l, i) => (
                <li key={l.carta.id}>
                  <span className="lineas-nombre">{l.carta.nombre} <span className="apagado">· {l.carta.grado}</span></span>
                  <input
                    type="number" min="1" max={l.carta.cantidad} value={l.cantidad}
                    onChange={(e) => setLineas((ls) => ls.map((x, j) => (j === i ? { ...x, cantidad: e.target.value } : x)))}
                    aria-label={`Cantidad de ${l.carta.nombre}`}
                  />
                  <span className="lineas-precio">{pesos((l.carta.precio_ars || 0) * l.cantidad)}</span>
                  <button className="quitar" onClick={() => setLineas((ls) => ls.filter((_, j) => j !== i))} aria-label="Quitar">×</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <label className="campo">
          <span>Comentario</span>
          <textarea rows="2" value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Opcional" />
        </label>
        {error && <p className="error-texto">{error}</p>}
      </div>
    </Modal>
  );
}

export default function Pedidos() {
  const hoy = new Date();
  const [mes, setMes] = useState({ anio: hoy.getFullYear(), mes: hoy.getMonth() });
  const [estado, setEstado] = useState("");
  const [pedidos, setPedidos] = useState([]);
  const [horarios, setHorarios] = useState(null);
  const [dia, setDia] = useState(iso(hoy));
  const [elegido, setElegido] = useState(null);         // id del pedido abierto en el panel
  const [marcados, setMarcados] = useState(new Set());  // para "Sacar pedidos"
  const [modal, setModal] = useState(null);
  const [error, setError] = useState("");
  const [avisar, aviso] = useAviso();

  const dias = semanasDelMes(mes.anio, mes.mes);

  async function cargar() {
    try {
      const r = await api.pedidos({ desde: iso(dias[0]), hasta: iso(dias[dias.length - 1]), estado });
      setPedidos(r.pedidos);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => { cargar(); }, [mes.anio, mes.mes, estado]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.config().then((c) => setHorarios(c.horarios)).catch(() => {}); }, []);

  const porDia = useMemo(() => {
    const m = {};
    for (const p of pedidos) (m[p.fecha_retiro] ||= []).push(p);
    return m;
  }, [pedidos]);

  const delDia = porDia[dia] || [];
  const abierto = pedidos.find((p) => p.id === elegido) || null;

  const mover = (delta) => setMes(({ anio, mes: m }) => {
    const d = new Date(anio, m + delta, 1);
    return { anio: d.getFullYear(), mes: d.getMonth() };
  });

  const irAHoy = () => { setMes({ anio: hoy.getFullYear(), mes: hoy.getMonth() }); setDia(iso(hoy)); };

  async function cambiarEstado(p, nuevo) {
    try {
      await api.cambiarPedido(p.id, { estado: nuevo });
      avisar(`Pedido #${p.id}: ${ESTADOS[nuevo].toLowerCase()}.`);
      cargar();
    } catch (e) {
      avisar(e.message, true);
    }
  }

  const alternarMarca = (id) => setMarcados((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <section>
      <div className="cabecera">
        <div>
          <h1>Pedidos</h1>
          <p>Retiros por día. Tocá un día para ver sus pedidos.</p>
        </div>
      </div>

      <div className="barra-herramientas">
        <label className="selector">
          <Icono nombre="filtro" />
          <select value={estado} onChange={(e) => setEstado(e.target.value)} aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            {Object.entries(ESTADOS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </select>
        </label>
        <button className="boton" onClick={irAHoy}><Icono nombre="calendario" /> Hoy</button>
        <span className="separador" />
        <button className="boton" disabled={!abierto} onClick={() => setModal("editar")}
                title={!abierto ? "Elegí un pedido del panel de la derecha" : undefined}>
          <Icono nombre="editar" /> Editar
        </button>
        <button className="boton peligro-suave" disabled={!marcados.size} onClick={() => setModal("sacar")}
                title={!marcados.size ? "Marcá pedidos en el panel del día" : undefined}>
          <Icono nombre="borrar" /> Sacar pedidos{marcados.size > 0 && ` (${marcados.size})`}
        </button>
        <button className="boton primario empujar" onClick={() => setModal("nuevo")}>
          <Icono nombre="mas" /> Nuevo pedido
        </button>
      </div>

      {error && <p className="hoja error-texto">{error}</p>}

      <div className="hoja calendario-hoja">
        <div className="calendario">
          <div className="calendario-cabeza">
            <div>
              <h2>{MESES[mes.mes][0].toUpperCase() + MESES[mes.mes].slice(1)} {mes.anio}</h2>
              <p>{pedidos.filter((p) => desdeIso(p.fecha_retiro).getMonth() === mes.mes).length} pedidos este mes</p>
            </div>
            <div className="calendario-flechas">
              <button className="icono-boton claro" onClick={() => mover(-1)} aria-label="Mes anterior"><Icono nombre="izquierda" /></button>
              <button className="icono-boton claro" onClick={() => mover(1)} aria-label="Mes siguiente"><Icono nombre="derecha" /></button>
            </div>
          </div>

          <div className="calendario-grilla" role="grid">
            {DIAS_CORTOS.map((d) => <div key={d} className="calendario-dia-semana" role="columnheader">{d}</div>)}
            {dias.map((d) => {
              const clave = iso(d);
              const lista = porDia[clave] || [];
              const cerrado = horarios && !horarios[CLAVES_DIA[(d.getDay() + 6) % 7]];
              const clases = [
                "celda",
                d.getMonth() !== mes.mes && "afuera",
                clave === iso(hoy) && "hoy",
                clave === dia && "elegida",
                cerrado && "cerrada",
              ].filter(Boolean).join(" ");
              return (
                <button key={clave} className={clases} role="gridcell"
                        onClick={() => { setDia(clave); setElegido(lista[0]?.id ?? null); }}
                        aria-label={`${d.getDate()} de ${MESES[d.getMonth()]}, ${lista.length} pedidos`}>
                  <span className="celda-num">{d.getDate()}</span>
                  {cerrado && lista.length === 0 && <span className="celda-cerrado">cerrado</span>}
                  {lista.slice(0, 3).map((p) => (
                    <span key={p.id} className={`celda-pedido estado-${p.estado}`}>
                      {p.hora_retiro} {p.nombre} {p.apellido[0]}.
                    </span>
                  ))}
                  {lista.length > 3 && <span className="celda-mas">+{lista.length - 3} más</span>}
                </button>
              );
            })}
          </div>
        </div>

        <aside className="dia-panel">
          <h3>{desdeIso(dia).getDate()} de {MESES[desdeIso(dia).getMonth()]}</h3>
          <p className="apagado">
            {delDia.length ? `${delDia.length} ${delDia.length === 1 ? "pedido" : "pedidos"}` : "Sin retiros este día"}
          </p>
          <ul className="dia-lista">
            {delDia.map((p) => (
              <li key={p.id}>
                <div className={`dia-pedido${p.id === elegido ? " abierto" : ""}`}>
                  <div className="dia-pedido-cabeza">
                    <input type="checkbox" checked={marcados.has(p.id)} onChange={() => alternarMarca(p.id)}
                           aria-label={`Marcar pedido ${p.id}`} />
                    <button className="dia-pedido-titulo" onClick={() => setElegido(p.id === elegido ? null : p.id)}>
                      <strong>{p.hora_retiro}</strong> · #{p.id} {p.nombre} {p.apellido}
                    </button>
                  </div>
                  <div className="dia-pedido-fila">
                    <EtiquetaEstado estado={p.estado} corta />
                    <span>{p.unidades} u. · {pesos(p.total)}</span>
                  </div>
                  {p.id === elegido && (
                    <div className="dia-pedido-detalle">
                      <ul>
                        {p.items.map((i, k) => (
                          <li key={k}>{i.cantidad} × {i.nombre} <span className="apagado">({i.grado})</span></li>
                        ))}
                      </ul>
                      <p className="apagado">Pedido {fechaHora(p.creado)} · {p.origen === "chat" ? "por el chat" : "cargado a mano"}</p>
                      {p.comentario && <p className="comentario">“{p.comentario}”</p>}
                      <div className="dia-pedido-acciones">
                        {p.estado !== "realizada" && (
                          <button className="boton chico" onClick={() => cambiarEstado(p, "realizada")}>
                            <Icono nombre="check" tam={14} /> Entregado
                          </button>
                        )}
                        {p.estado !== "rechazada" && (
                          <button className="boton chico peligro-suave" onClick={() => cambiarEstado(p, "rechazada")}>Rechazar</button>
                        )}
                        {p.estado !== "pendiente" && (
                          <button className="boton chico" onClick={() => cambiarEstado(p, "pendiente")}>Volver a pendiente</button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <footer className="calendario-pie">
          <span>{desdeIso(dia).toLocaleDateString("es-AR", { day: "numeric", month: "short", year: "numeric" })}</span>
          <span className="leyenda">
            {Object.keys(ESTADOS).map((k) => <EtiquetaEstado key={k} estado={k} />)}
          </span>
        </footer>
      </div>

      {modal === "editar" && abierto && (
        <EditarPedido
          pedido={abierto}
          onCerrar={() => setModal(null)}
          onGuardado={(p) => { avisar(`Guardé el pedido #${p.id}.`); setModal(null); setDia(p.fecha_retiro); cargar(); }}
        />
      )}
      {modal === "nuevo" && (
        <NuevoPedido
          fechaInicial={dia}
          onCerrar={() => setModal(null)}
          onCreado={(p) => { avisar(`Pedido #${p.id} creado para ${p.nombre} ${p.apellido}.`); setModal(null); setDia(p.fecha_retiro); setElegido(p.id); cargar(); }}
        />
      )}
      {modal === "sacar" && (
        <Confirmar
          titulo={`Sacar ${marcados.size} ${marcados.size === 1 ? "pedido" : "pedidos"}`}
          mensaje="Se borran del sistema. Si estaban pendientes, sus cartas vuelven al stock. Si sólo querés cancelarlo, mejor marcalo como rechazado y queda en el historial."
          accion="Sacar"
          peligro
          onNo={() => setModal(null)}
          onSi={async () => {
            try {
              const r = await api.borrarPedidos([...marcados]);
              avisar(`Saqué ${r.borrados} ${r.borrados === 1 ? "pedido" : "pedidos"}.`);
              setMarcados(new Set());
              setElegido(null);
              setModal(null);
              cargar();
            } catch (e) {
              avisar(e.message, true);
            }
          }}
        />
      )}
      {aviso}
    </section>
  );
}
