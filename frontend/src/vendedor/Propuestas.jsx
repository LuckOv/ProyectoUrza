import { useEffect, useState } from "react";

import { dolares, pesos } from "../compartido/formato.js";
import * as api from "./api.js";
import {
  Confirmar, ESTADOS_PROPUESTA, Etiqueta, Icono, Modal, NotaSugerencia, fechaHora, useAviso, usePrecioSugerido,
} from "./comunes.jsx";

const FILTROS = [
  { id: "nueva", texto: "Nuevas" },
  { id: "en_revision", texto: "En revisión" },
  { id: "aceptada", texto: "Aceptadas" },
  { id: "rechazada", texto: "Rechazadas" },
  { id: "", texto: "Todas" },
];

function precioOfrecido(p, dolar) {
  const unidad = p.moneda === "USD" ? dolares(p.precio) : pesos(p.precio);
  const otro = p.moneda === "USD" ? pesos(p.precio * dolar) : dolar ? dolares(p.precio / dolar) : null;
  return { unidad, otro };
}

/* Aceptar una propuesta y cargar la carta al inventario con el precio de venta de la tienda. */
function AlInventario({ propuesta, onCerrar, onHecho }) {
  const [precio, setPrecio] = useState("");
  const [cantidad, setCantidad] = useState(propuesta.cantidad);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const sugerencia = usePrecioSugerido(propuesta.grado, { scryfall_id: propuesta.scryfall_id }, setPrecio);

  async function cargar() {
    setError("");
    setOcupado(true);
    try {
      onHecho(await api.propuestaAlInventario(propuesta.id, {
        precio_usd: precio === "" ? null : Number(precio), cantidad: Number(cantidad),
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Modal
      titulo="Cargar al inventario"
      subtitulo={`${propuesta.carta} · ${propuesta.set_nombre} · ${propuesta.grado}`}
      onCerrar={onCerrar}
      ancho={480}
      pie={
        <>
          <button className="boton" onClick={onCerrar}>Cancelar</button>
          <button className="boton primario" onClick={cargar} disabled={ocupado}>
            {ocupado ? "Cargando…" : "Aceptar y cargar"}
          </button>
        </>
      }
    >
      <div className="formulario">
        <p className="ayuda">La propuesta queda como aceptada y la carta entra al stock con el precio de venta que pongas.</p>
        <div className="fila-campos">
          <label className="campo"><span>Cantidad</span>
            <input type="number" min="1" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
          </label>
          <label className="campo"><span>Precio de venta (US$)</span>
            <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} />
          </label>
        </div>
        <NotaSugerencia sugerencia={sugerencia} precio={precio} onUsar={() => setPrecio(sugerencia.precio_usd)} />
        {error && <p className="error-texto">{error}</p>}
      </div>
    </Modal>
  );
}

function Comentario({ propuesta, onGuardado, onError }) {
  const [texto, setTexto] = useState(propuesta.comentario_vendedor);
  useEffect(() => setTexto(propuesta.comentario_vendedor), [propuesta.comentario_vendedor]);
  return (
    <textarea
      className="propuesta-nota"
      rows="2"
      value={texto}
      placeholder="Nota interna (ej: le ofrecí $X por mail)…"
      onChange={(e) => setTexto(e.target.value)}
      onBlur={() => {
        if (texto.trim() === propuesta.comentario_vendedor) return;
        api.cambiarPropuesta(propuesta.id, { comentario: texto }).then(onGuardado).catch((e) => onError(e.message));
      }}
      aria-label={`Nota de la propuesta ${propuesta.id}`}
    />
  );
}

export default function Propuestas() {
  const [estado, setEstado] = useState("nueva");
  const [q, setQ] = useState("");
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);   // {tipo: "inventario"|"borrar", propuesta}
  const [avisar, aviso] = useAviso();

  async function cargar() {
    try {
      setDatos(await api.propuestas({ estado, q: q.trim() }));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    const t = setTimeout(cargar, 200);
    return () => clearTimeout(t);
  }, [estado, q]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function cambiar(p, nuevo) {
    try {
      await api.cambiarPropuesta(p.id, { estado: nuevo });
      avisar(`Propuesta #${p.id}: ${ESTADOS_PROPUESTA[nuevo].texto.toLowerCase()}.`);
      cargar();
    } catch (e) {
      avisar(e.message, true);
    }
  }

  const reemplazar = (p) => setDatos((d) => ({ ...d, propuestas: d.propuestas.map((x) => (x.id === p.id ? { ...x, ...p } : x)) }));

  return (
    <section>
      <div className="cabecera">
        <div>
          <h1>Propuestas</h1>
          <p>Cartas que los clientes le ofrecen a la tienda desde el chat.</p>
        </div>
      </div>

      <div className="barra-herramientas">
        <div className="segmentado envolvente" role="radiogroup" aria-label="Estado">
          {FILTROS.map((f) => (
            <button key={f.id || "todas"} role="radio" aria-checked={estado === f.id}
                    className={estado === f.id ? "activo" : ""} onClick={() => setEstado(f.id)}>
              {f.texto}{f.id === "nueva" && datos?.nuevas > 0 && ` (${datos.nuevas})`}
            </button>
          ))}
        </div>
        <label className="buscador ancho-medio">
          <Icono nombre="buscar" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar carta, nombre o mail"
                 aria-label="Buscar propuesta" />
        </label>
      </div>

      {error && <p className="hoja error-texto">{error}</p>}
      {!datos && !error && <p className="cargando">Cargando…</p>}
      {datos?.propuestas.length === 0 && (
        <div className="hoja vacio">
          {estado === "nueva" ? "No hay propuestas nuevas." : "No hay propuestas con esos filtros."}
        </div>
      )}

      <ul className="lista-propuestas">
        {(datos?.propuestas || []).map((p) => {
          const { unidad, otro } = precioOfrecido(p, datos.dolar);
          const est = ESTADOS_PROPUESTA[p.estado];
          return (
            <li key={p.id} className="hoja propuesta-v">
              {p.imagen ? <img src={p.imagen} alt="" className="propuesta-v-img" /> : <div className="propuesta-v-img vacia" />}
              <div className="propuesta-v-datos">
                <div className="propuesta-v-cabeza">
                  <h3>{p.carta}</h3>
                  <Etiqueta tono={est.tono}>{est.texto}</Etiqueta>
                </div>
                <p className="apagado">#{p.id} · {p.set_nombre} #{p.numero} · {fechaHora(p.creado)}</p>
                <div className="propuesta-v-oferta">
                  <Etiqueta tono={p.grado === "Sin graduar" ? "neutro" : "grado"}>{p.grado}</Etiqueta>
                  <span><strong>{p.cantidad}</strong> × <strong>{unidad}</strong>{otro && <span className="apagado"> (≈ {otro})</span>}</span>
                </div>
                <p>
                  <strong>{p.nombre} {p.apellido}</strong> ·{" "}
                  <span>{p.email}</span>
                </p>
                {p.comentario_cliente && <p className="comentario">“{p.comentario_cliente}”</p>}
                <p className="apagado chico">
                  En la tienda:{" "}
                  {p.en_tienda.length
                    ? p.en_tienda.map((t) => `${t.grado} (${t.cantidad} u., ${pesos(t.precio_ars)})`).join(" · ")
                    : "no la tenés"}
                </p>
                <Comentario propuesta={p} onGuardado={reemplazar} onError={(m) => avisar(m, true)} />
                <div className="propuesta-v-acciones">
                  {p.estado !== "en_revision" && p.estado !== "aceptada" && (
                    <button className="boton chico" onClick={() => cambiar(p, "en_revision")}>En revisión</button>
                  )}
                  {!p.cargada && (
                    <button className="boton chico primario" onClick={() => setModal({ tipo: "inventario", propuesta: p })}>
                      <Icono nombre="check" tam={14} /> {p.estado === "aceptada" ? "Cargar al inventario" : "Aceptar y cargar al inventario"}
                    </button>
                  )}
                  {p.cargada === 1 && <Etiqueta tono="stock-ok">En el inventario</Etiqueta>}
                  {p.estado !== "aceptada" && (
                    <button className="boton chico" onClick={() => cambiar(p, "aceptada")}>Aceptar sin cargar</button>
                  )}
                  {p.estado !== "rechazada" && (
                    <button className="boton chico peligro-suave" onClick={() => cambiar(p, "rechazada")}>Rechazar</button>
                  )}
                  <button className="boton chico" onClick={() => setModal({ tipo: "borrar", propuesta: p })} aria-label="Borrar propuesta">
                    <Icono nombre="borrar" tam={14} />
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {modal?.tipo === "inventario" && (
        <AlInventario
          propuesta={modal.propuesta}
          onCerrar={() => setModal(null)}
          onHecho={(item) => { avisar(`${item.nombre} (${item.grado}) cargada: ${item.cantidad} en stock.`); setModal(null); cargar(); }}
        />
      )}
      {modal?.tipo === "borrar" && (
        <Confirmar
          titulo={`Borrar propuesta #${modal.propuesta.id}`}
          mensaje="Se borra del sistema. Si sólo no te interesa, mejor marcala como rechazada."
          accion="Borrar"
          peligro
          onNo={() => setModal(null)}
          onSi={async () => { await api.borrarPropuesta(modal.propuesta.id); setModal(null); avisar("Propuesta borrada."); cargar(); }}
        />
      )}
      {aviso}
    </section>
  );
}
