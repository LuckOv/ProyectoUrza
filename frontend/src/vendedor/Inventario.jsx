import { useEffect, useMemo, useState } from "react";

import { dolares, numero, pesos } from "../compartido/formato.js";
import AgregarCarta from "./AgregarCarta.jsx";
import * as api from "./api.js";
import {
  Confirmar, Etiqueta, EtiquetaStock, Icono, Modal, NotaSugerencia, useAviso, usePrecioSugerido, textoAlerta,
} from "./comunes.jsx";

const RAREZA = { common: "Común", uncommon: "Infrecuente", rare: "Rara", mythic: "Mítica", special: "Especial", bonus: "Bonus" };

const ORDENES = {
  nombre: { texto: "Nombre", fn: (a, b) => a.nombre.localeCompare(b.nombre) },
  precio_desc: { texto: "Precio (mayor)", fn: (a, b) => (b.precio_ars || 0) - (a.precio_ars || 0) },
  precio_asc: { texto: "Precio (menor)", fn: (a, b) => (a.precio_ars || 0) - (b.precio_ars || 0) },
  stock: { texto: "Stock (menor)", fn: (a, b) => a.cantidad - b.cantidad },
  nuevo: { texto: "Más recientes", fn: (a, b) => b.id - a.id },
};

function EditarCarta({ carta, grados, dolar, onCerrar, onGuardado }) {
  const [grado, setGrado] = useState(carta.grado);
  const [precio, setPrecio] = useState(carta.precio_usd ?? "");
  const [cantidad, setCantidad] = useState(carta.cantidad);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const precioNum = precio === "" ? null : Number(precio);
  const vista = precioNum != null ? Math.round(precioNum * dolar * (1 - carta.descuento / 100)) : null;

  async function guardar() {
    setError("");
    setOcupado(true);
    try {
      const r = await api.editarCarta(carta.id, {
        grado, precio_usd: precioNum, cantidad: Number(cantidad), motivo,
      });
      onGuardado(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Modal
      titulo={`Editar ${carta.nombre}`}
      subtitulo={`${carta.sku} · ${carta.set_nombre || "sin set"} #${carta.numero || "—"}`}
      onCerrar={onCerrar}
      pie={
        <>
          <button className="boton" onClick={onCerrar}>Cancelar</button>
          <button className="boton primario" onClick={guardar} disabled={ocupado}>
            {ocupado ? "Guardando…" : "Guardar cambios"}
          </button>
        </>
      }
    >
      <div className="edicion">
        {carta.imagen ? <img src={carta.imagen} alt="" className="edicion-img" /> : <div className="edicion-img vacia" />}
        <div className="formulario">
          <label className="campo">
            <span>Grado</span>
            <select value={grado} onChange={(e) => setGrado(e.target.value)}>
              {grados.map((g) => <option key={g}>{g}</option>)}
            </select>
          </label>
          <label className="campo">
            <span>Precio en dólares</span>
            <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} />
            <small>
              Se vende a {pesos(vista)}
              {carta.descuento > 0 && ` (con ${carta.descuento}% de descuento)`} · dólar {pesos(dolar)}
            </small>
          </label>
          <label className="campo">
            <span>Unidades en stock</span>
            <div className="contador">
              <button type="button" onClick={() => setCantidad((c) => Math.max(0, Number(c) - 1))}>−</button>
              <input type="number" min="0" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
              <button type="button" onClick={() => setCantidad((c) => Number(c) + 1)}>+</button>
            </div>
          </label>
          {Number(cantidad) !== carta.cantidad && (
            <label className="campo">
              <span>Motivo del ajuste (queda en la actividad)</span>
              <input value={motivo} placeholder="Ej: recuento manual" onChange={(e) => setMotivo(e.target.value)} />
            </label>
          )}
          {error && <p className="error-texto">{error}</p>}
        </div>
      </div>
    </Modal>
  );
}

/* La misma carta (misma impresión) con otro grado: entra un PSA 10 de algo
   que ya tenías sin graduar, o al revés. Copia los datos de la carta, así no
   hay que volver a buscarla en Scryfall. */
function OtroGrado({ carta, todas, grados, dolar, onCerrar, onGuardado }) {
  // Grados que ya existen de esta misma impresión, para mostrarlos y no ofrecerlos primero.
  const hermanas = todas.filter((i) =>
    carta.scryfall_id
      ? i.scryfall_id === carta.scryfall_id
      : i.nombre === carta.nombre && i.set_codigo === carta.set_codigo);
  const usados = new Set(hermanas.map((h) => h.grado));
  const libres = grados.filter((g) => !usados.has(g));

  const [grado, setGrado] = useState(libres[0] || grados[0]);
  const [cantidad, setCantidad] = useState(1);
  const [precio, setPrecio] = useState(carta.precio_usd ?? "");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const precioNum = precio === "" ? null : Number(precio);
  const yaExiste = usados.has(grado);
  const sugerencia = usePrecioSugerido(grado, { item_id: carta.id }, setPrecio);

  async function guardar() {
    setError("");
    setOcupado(true);
    try {
      onGuardado(await api.nuevaVariante(carta.id, { grado, cantidad: Number(cantidad), precio_usd: precioNum }));
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Modal
      titulo={`Otro grado de ${carta.nombre}`}
      subtitulo={`${carta.set_nombre || "sin set"} #${carta.numero || "—"} · misma impresión, otro PSA`}
      onCerrar={onCerrar}
      pie={
        <>
          <button className="boton" onClick={onCerrar}>Cancelar</button>
          <button className="boton primario" onClick={guardar} disabled={ocupado}>
            {ocupado ? "Guardando…" : yaExiste ? "Sumar unidades" : "Agregar grado"}
          </button>
        </>
      }
    >
      <div className="edicion">
        {carta.imagen ? <img src={carta.imagen} alt="" className="edicion-img" /> : <div className="edicion-img vacia" />}
        <div className="formulario">
          <div className="campo">
            <span>Ya tenés de esta carta</span>
            <div className="grados-existentes">
              {hermanas.map((h) => (
                <Etiqueta key={h.id} tono={h.grado === "Sin graduar" ? "neutro" : "grado"}>
                  {h.grado} · {h.cantidad} u. · {pesos(h.precio_ars)}
                </Etiqueta>
              ))}
            </div>
          </div>
          <label className="campo">
            <span>Nuevo grado</span>
            <select value={grado} onChange={(e) => setGrado(e.target.value)}>
              {libres.map((g) => <option key={g}>{g}</option>)}
              {libres.length > 0 && usados.size > 0 && <option disabled>──────────</option>}
              {grados.filter((g) => usados.has(g)).map((g) => <option key={g} value={g}>{g} (ya existe: suma unidades)</option>)}
            </select>
          </label>
          <div className="fila-campos">
            <label className="campo">
              <span>Cantidad</span>
              <div className="contador">
                <button type="button" onClick={() => setCantidad((c) => Math.max(1, Number(c) - 1))}>−</button>
                <input type="number" min="1" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
                <button type="button" onClick={() => setCantidad((c) => Number(c) + 1)}>+</button>
              </div>
            </label>
            <label className="campo">
              <span>Precio en dólares</span>
              <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} />
            </label>
          </div>
          <NotaSugerencia sugerencia={sugerencia} precio={precio} onUsar={() => setPrecio(sugerencia.precio_usd)} />
          <small className="ayuda">
            {precioNum != null
              ? `Se vende a ${pesos(Math.round(precioNum * dolar))} antes de descuentos.`
              : "Sin precio el chat no la puede vender."}
          </small>
          {error && <p className="error-texto">{error}</p>}
        </div>
      </div>
    </Modal>
  );
}

/* Arriba de todo: las cartas cuyo precio de mercado (Scryfall) se movió mucho
   desde que les pusiste precio. Se sugiere mover el tuyo en la misma
   proporción (sirve igual para las graduadas). Un clic lo pone al día. */
function PreciosARevisar({ items, umbral, onActualizar, onMantener, onRefrescar, refrescando }) {
  const [abierto, setAbierto] = useState(true);
  if (!items.length) return null;
  return (
    <div className="hoja alertas-precio">
      <div className="lista-cabeza">
        <div>
          <h2>Precios a revisar ({items.length})</h2>
          <p className="apagado chico">
            Cartas con tu precio {umbral}% o más lejos del precio de mercado de hoy (el doble para las graduadas,
            que se estiman con el multiplicador), o cuyo mercado se movió {umbral}% o más desde que les pusiste precio.
          </p>
        </div>
        <div className="resumen-acciones">
          <button className="boton chico" onClick={onRefrescar} disabled={refrescando}>
            {refrescando ? "Consultando Scryfall…" : "Actualizar precios de mercado"}
          </button>
          <button className="boton chico" onClick={() => setAbierto((a) => !a)}>{abierto ? "Ocultar" : "Ver"}</button>
        </div>
      </div>
      {abierto && (
        <ul className="alertas-lista">
          {items.map((i) => {
            const t = textoAlerta(i);
            return (
              <li key={i.id}>
                {i.imagen ? <img src={i.imagen} alt="" /> : <span className="mini-sinimg" />}
                <div className="alertas-datos">
                  <strong>{i.nombre}</strong>
                  <span className="apagado">{i.set_nombre} · {i.grado}</span>
                </div>
                <div className="alertas-precios">
                  <span>Tu precio <strong>{dolares(i.precio_usd)}</strong></span>
                  <span>
                    {t.detalle} {t.desde != null && <>{dolares(t.desde)} → </>}<strong>{dolares(t.hasta)}</strong>
                  </span>
                </div>
                <Etiqueta tono={t.tono}>{t.etiqueta}</Etiqueta>
                <div className="alertas-botones">
                  <button className="boton chico primario" onClick={() => onActualizar(i)}>
                    Poner {dolares(i.sugerido_usd)}
                  </button>
                  <button className="boton chico" onClick={() => onMantener(i)} title="No avisar más mientras no cambies este precio">
                    Dejarlo así
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function Inventario() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [verFiltros, setVerFiltros] = useState(false);
  const [estado, setEstado] = useState("");
  const [grado, setGrado] = useState("");
  const [orden, setOrden] = useState("nombre");
  const [elegidas, setElegidas] = useState(new Set());
  const [modal, setModal] = useState(null);     // "agregar" | "editar" | "grado" | "borrar"
  const [avisar, aviso] = useAviso();
  const [refrescando, setRefrescando] = useState(false);

  async function cargar() {
    try {
      setDatos(await api.inventario());
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => { cargar(); }, []);

  // El filtro es local: el inventario de una tienda entra entero en memoria
  // y así la búsqueda responde a cada tecla.
  const items = useMemo(() => {
    if (!datos) return [];
    const plano = (t) => (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const buscado = plano(q.trim());
    return datos.items
      .filter((i) => !buscado || plano(`${i.nombre} ${i.set_nombre} ${i.set_codigo} ${i.sku} ${i.grado}`).includes(buscado))
      .filter((i) => !estado || i.estado_stock === estado)
      .filter((i) => !grado || (grado === "graduadas" ? i.grado !== "Sin graduar" : i.grado === grado))
      .sort(ORDENES[orden].fn);
  }, [datos, q, estado, grado, orden]);

  const unidades = items.reduce((s, i) => s + i.cantidad, 0);
  const filtrosActivos = [estado, grado].filter(Boolean).length + (orden !== "nombre" ? 1 : 0);
  const seleccion = datos ? datos.items.filter((i) => elegidas.has(i.id)) : [];

  const alternar = (id) => setElegidas((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <section>
      <div className="cabecera">
        <div>
          <h1>Inventario</h1>
          <p>Gestión de productos y existencias.</p>
        </div>
        <div className="cabecera-acciones">
          <label className="buscador">
            <Icono nombre="buscar" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar carta, set o SKU"
              aria-label="Buscar carta, set o SKU"
            />
          </label>
          <button className={`boton${verFiltros ? " activo" : ""}`} onClick={() => setVerFiltros((v) => !v)}>
            <Icono nombre="filtro" /> Filtros{filtrosActivos > 0 && <span className="contador-chico">{filtrosActivos}</span>}
          </button>
          <button className="boton primario" onClick={() => setModal("agregar")}>
            <Icono nombre="mas" /> Agregar carta
          </button>
        </div>
      </div>

      {verFiltros && (
        <div className="hoja filtros">
          <label className="campo en-linea">
            <span>Stock</span>
            <select value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Todos</option>
              <option value="ok">En stock</option>
              <option value="bajo">Stock bajo</option>
              <option value="sin">Sin stock</option>
            </select>
          </label>
          <label className="campo en-linea">
            <span>Grado</span>
            <select value={grado} onChange={(e) => setGrado(e.target.value)}>
              <option value="">Todos</option>
              <option value="graduadas">Sólo graduadas</option>
              {(datos?.grados || []).map((g) => <option key={g}>{g}</option>)}
            </select>
          </label>
          <label className="campo en-linea">
            <span>Ordenar por</span>
            <select value={orden} onChange={(e) => setOrden(e.target.value)}>
              {Object.entries(ORDENES).map(([k, o]) => <option key={k} value={k}>{o.texto}</option>)}
            </select>
          </label>
          {filtrosActivos > 0 && (
            <button className="boton chico" onClick={() => { setEstado(""); setGrado(""); setOrden("nombre"); }}>
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      <PreciosARevisar
        items={(datos?.items || []).filter((i) => i.alerta_precio).sort((a, b) => Math.abs(b.alerta_pct) - Math.abs(a.alerta_pct))}
        umbral={datos?.alerta_precio ?? 30}
        refrescando={refrescando}
        onRefrescar={async () => {
          setRefrescando(true);
          try {
            const r = await api.actualizarMercado();
            avisar(`Precios de mercado actualizados (${r.actualizadas} cartas).`);
            cargar();
          } catch (e) {
            avisar(e.message, true);
          } finally {
            setRefrescando(false);
          }
        }}
        onMantener={async (i) => {
          try {
            await api.mantenerPrecio(i.id);
            avisar(`${i.nombre} (${i.grado}) se queda en ${dolares(i.precio_usd)}. No te aviso más mientras no lo cambies.`);
            cargar();
          } catch (e) {
            avisar(e.message, true);
          }
        }}
        onActualizar={async (i) => {
          try {
            await api.editarCarta(i.id, { precio_usd: i.sugerido_usd, motivo: "precio al día con el mercado" });
            avisar(`${i.nombre} (${i.grado}) ahora está a ${dolares(i.sugerido_usd)}.`);
            cargar();
          } catch (e) {
            avisar(e.message, true);
          }
        }}
      />

      <div className="hoja resumen">
        <p>
          <strong>{items.length}</strong> {items.length === 1 ? "carta" : "cartas"} · <strong>{numero(unidades)}</strong> unidades en stock
          {elegidas.size > 0 && (
            <span className="chip-seleccion">
              {elegidas.size} {elegidas.size === 1 ? "seleccionada" : "seleccionadas"}
              <button onClick={() => setElegidas(new Set())} aria-label="Quitar selección">×</button>
            </span>
          )}
        </p>
        <div className="resumen-acciones">
          <button className="boton" disabled={seleccion.length !== 1} onClick={() => setModal("editar")}
                  title={seleccion.length > 1 ? "Elegí una sola carta para editar" : undefined}>
            <Icono nombre="editar" /> Editar
          </button>
          <button className="boton" disabled={seleccion.length !== 1} onClick={() => setModal("grado")}
                  title="La misma carta con otro grado (PSA)">
            <Icono nombre="mas" /> Otro PSA
          </button>
          <button className="boton peligro-suave" disabled={!seleccion.length} onClick={() => setModal("borrar")}>
            <Icono nombre="borrar" /> Borrar
          </button>
        </div>
      </div>

      {error && <p className="hoja error-texto">{error}</p>}
      {!datos && !error && <p className="cargando">Cargando inventario…</p>}

      {datos && items.length === 0 && (
        <div className="hoja vacio">
          {datos.items.length === 0
            ? <>Todavía no hay cartas. <button className="enlace" onClick={() => setModal("agregar")}>Agregá la primera</button>.</>
            : "Ninguna carta coincide con la búsqueda o los filtros."}
        </div>
      )}

      <ul className="grilla-cartas">
        {items.map((c) => {
          const elegida = elegidas.has(c.id);
          return (
            <li key={c.id}>
              <article
                className={`ficha${elegida ? " elegida" : ""}`}
                onClick={() => alternar(c.id)}
                onDoubleClick={() => { setElegidas(new Set([c.id])); setModal("editar"); }}
              >
                <div className="ficha-img">
                  {c.imagen ? <img src={c.imagen} alt="" loading="lazy" /> : <div className="ficha-sinimg">{c.nombre}</div>}
                  <input
                    type="checkbox"
                    className="ficha-check"
                    checked={elegida}
                    onChange={() => alternar(c.id)}
                    onClick={(e) => e.stopPropagation()}
                    aria-label={`Seleccionar ${c.nombre}`}
                  />
                  {c.descuento > 0 && <span className="ficha-desc">−{c.descuento}%</span>}
                </div>
                <h3 title={c.nombre}>{c.nombre}</h3>
                <p className="ficha-set" title={c.set_nombre}>
                  {c.set_nombre || "Sin set"} · {RAREZA[c.rareza] || c.rareza || "—"}
                </p>
                <div className="ficha-fila">
                  <strong title={`${dolares(c.precio_usd)}${c.descuento ? ` · lista ${pesos(c.precio_lista_ars)}` : ""}`}>
                    {pesos(c.precio_ars)}
                  </strong>
                  <Etiqueta tono={c.grado === "Sin graduar" ? "neutro" : "grado"}>{c.grado === "Sin graduar" ? "Sin graduar" : c.grado}</Etiqueta>
                </div>
                <div className="ficha-fila">
                  <span className="ficha-stock">Stock: {c.cantidad}</span>
                  <EtiquetaStock estado={c.estado_stock} />
                </div>
              </article>
            </li>
          );
        })}
      </ul>

      {modal === "agregar" && (
        <AgregarCarta
          grados={datos?.grados || ["Sin graduar"]}
          inventario={datos?.items || []}
          onCerrar={() => setModal(null)}
          onAgregada={(c, seguir) => {
            avisar(`${c.nombre} (${c.grado}) quedó con ${c.cantidad} en stock.`);
            cargar();
            if (!seguir) setModal(null);
          }}
        />
      )}

      {modal === "editar" && seleccion[0] && (
        <EditarCarta
          carta={seleccion[0]}
          grados={datos.grados}
          dolar={datos.dolar}
          onCerrar={() => setModal(null)}
          onGuardado={(c) => { avisar(`Guardé los cambios de ${c.nombre}.`); setModal(null); cargar(); }}
        />
      )}

      {modal === "grado" && seleccion[0] && (
        <OtroGrado
          carta={seleccion[0]}
          todas={datos.items}
          grados={datos.grados}
          dolar={datos.dolar}
          onCerrar={() => setModal(null)}
          onGuardado={(c) => {
            avisar(`${c.nombre} ${c.grado}: ${c.cantidad} en stock.`);
            setModal(null);
            setElegidas(new Set([c.id]));
            cargar();
          }}
        />
      )}

      {modal === "borrar" && (
        <Confirmar
          titulo={seleccion.length === 1 ? "Borrar carta" : `Borrar ${seleccion.length} cartas`}
          mensaje={
            seleccion.length === 1
              ? `Se va a sacar ${seleccion[0].nombre} (${seleccion[0].grado}) del inventario con sus ${seleccion[0].cantidad} unidades. Los pedidos que ya la incluyen no cambian.`
              : `Se van a sacar ${seleccion.length} cartas del inventario. Los pedidos que ya las incluyen no cambian.`
          }
          accion="Borrar"
          peligro
          onNo={() => setModal(null)}
          onSi={async () => {
            try {
              const r = await api.borrarCartas(seleccion.map((s) => s.id));
              avisar(`Borré ${r.borradas} ${r.borradas === 1 ? "carta" : "cartas"}.`);
              setElegidas(new Set());
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
