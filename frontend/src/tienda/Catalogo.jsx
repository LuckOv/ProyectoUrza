import { useEffect, useMemo, useRef, useState } from "react";

import * as api from "./api.js";
import { pesos } from "../compartido/formato.js";

// Colores de Magic, con los íconos de maná que ya usa la tienda.
const COLORES = [
  { id: "W", nombre: "Blanco", icono: "/mana-blanco.png" },
  { id: "U", nombre: "Azul", icono: "/mana-azul.png" },
  { id: "B", nombre: "Negro", icono: "/mana-negro.png" },
  { id: "R", nombre: "Rojo", icono: "/mana-rojo.png" },
  { id: "G", nombre: "Verde", icono: "/mana-verde.png" },
  { id: "M", nombre: "Multicolor" },
  { id: "C", nombre: "Incolora" },
];

const ORDENES = {
  nombre: { texto: "Nombre", fn: (a, b) => a.nombre.localeCompare(b.nombre) },
  barato: { texto: "Más baratas", fn: (a, b) => a.precio_ars - b.precio_ars },
  caro: { texto: "Más caras", fn: (a, b) => b.precio_ars - a.precio_ars },
  stock: { texto: "Más stock", fn: (a, b) => b.cantidad - a.cantidad },
};

const plano = (t) => (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** ¿La carta (colores "WU", "" = incolora, null = sin dato) pasa el filtro de colores elegidos? */
function pasaColor(colores, elegidos) {
  if (!elegidos.size) return true;
  if (colores == null) return false;
  if (colores === "") return elegidos.has("C");
  if (colores.length > 1 && elegidos.has("M")) return true;
  return [...colores].some((c) => elegidos.has(c));
}

/* Todas las cartas a la venta, con buscador y filtros por color, grado (PSA),
   expansión y precio. Se abre con el botón "Ver todas las cartas". */
export default function Catalogo({ onCerrar }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [verFiltros, setVerFiltros] = useState(false);
  const [colores, setColores] = useState(new Set());
  const [grado, setGrado] = useState("");
  const [expansion, setExpansion] = useState("");
  const [minimo, setMinimo] = useState("");
  const [maximo, setMaximo] = useState("");
  const [conDescuento, setConDescuento] = useState(false);
  const [orden, setOrden] = useState("nombre");

  // La lista se pide una sola vez al abrir. (Antes el efecto dependía de
  // onCerrar, que es una función nueva en cada render del chat, y se volvía
  // a pedir el catálogo entero cada vez que algo cambiaba en la página.)
  const cerrarRef = useRef(onCerrar);
  cerrarRef.current = onCerrar;
  useEffect(() => {
    api.catalogo().then((r) => setItems(r.items)).catch((e) => setError(e.message));
    const tecla = (e) => e.key === "Escape" && cerrarRef.current();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  const expansiones = useMemo(
    () => [...new Set((items || []).map((i) => i.set_nombre).filter(Boolean))].sort(),
    [items],
  );
  const grados = useMemo(() => {
    const g = [...new Set((items || []).map((i) => i.grado))];
    return g.sort((a, b) => (a === "Sin graduar" ? -1 : b === "Sin graduar" ? 1 : b.localeCompare(a, "es", { numeric: true })));
  }, [items]);

  const visibles = useMemo(() => {
    const buscado = plano(q.trim());
    const min = minimo === "" ? null : Number(minimo);
    const max = maximo === "" ? null : Number(maximo);
    return (items || [])
      .filter((i) => !buscado || plano(`${i.nombre} ${i.set_nombre} ${i.grado}`).includes(buscado))
      .filter((i) => pasaColor(i.colores, colores))
      .filter((i) => !grado || (grado === "graduadas" ? i.grado !== "Sin graduar" : i.grado === grado))
      .filter((i) => !expansion || i.set_nombre === expansion)
      .filter((i) => (min == null || i.precio_ars >= min) && (max == null || i.precio_ars <= max))
      .filter((i) => !conDescuento || i.descuento > 0)
      .sort(ORDENES[orden].fn);
  }, [items, q, colores, grado, expansion, minimo, maximo, conDescuento, orden]);

  const activos = colores.size + [grado, expansion, minimo, maximo].filter(Boolean).length + (conDescuento ? 1 : 0);
  const limpiar = () => {
    setColores(new Set()); setGrado(""); setExpansion(""); setMinimo(""); setMaximo(""); setConDescuento(false);
  };
  const alternarColor = (id) => setColores((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <div className="velo" onClick={onCerrar}>
      <aside className="cajon catalogo" onClick={(e) => e.stopPropagation()} aria-label="Cartas disponibles">
        <header>
          <h2>Cartas disponibles</h2>
          <button className="cajon-cerrar" onClick={onCerrar} aria-label="Cerrar">×</button>
        </header>

        <div className="catalogo-buscar">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar carta, expansión o grado"
            aria-label="Buscar carta"
            autoFocus
          />
          <button className={`catalogo-filtros-boton${verFiltros ? " activo" : ""}`} onClick={() => setVerFiltros((v) => !v)}>
            Filtros{activos > 0 && ` (${activos})`}
          </button>
        </div>

        {verFiltros && (
          <div className="catalogo-filtros">
            <div className="catalogo-colores" role="group" aria-label="Colores">
              {COLORES.map((c) => (
                <button
                  key={c.id}
                  className={`color-chip${colores.has(c.id) ? " elegido" : ""}`}
                  onClick={() => alternarColor(c.id)}
                  aria-pressed={colores.has(c.id)}
                  title={c.nombre}
                >
                  {c.icono ? <img src={c.icono} alt="" /> : <span className={`color-letra ${c.id}`}>{c.id === "M" ? "★" : "◇"}</span>}
                  <span>{c.nombre}</span>
                </button>
              ))}
            </div>
            <div className="catalogo-fila">
              <label>
                <span>Grado</span>
                <select value={grado} onChange={(e) => setGrado(e.target.value)}>
                  <option value="">Todos</option>
                  <option value="graduadas">Sólo graduadas (PSA)</option>
                  {grados.map((g) => <option key={g}>{g}</option>)}
                </select>
              </label>
              <label>
                <span>Expansión</span>
                <select value={expansion} onChange={(e) => setExpansion(e.target.value)}>
                  <option value="">Todas</option>
                  {expansiones.map((x) => <option key={x}>{x}</option>)}
                </select>
              </label>
            </div>
            <div className="catalogo-fila">
              <label>
                <span>Precio mínimo</span>
                <input type="number" min="0" placeholder="$" value={minimo} onChange={(e) => setMinimo(e.target.value)} />
              </label>
              <label>
                <span>Precio máximo</span>
                <input type="number" min="0" placeholder="$" value={maximo} onChange={(e) => setMaximo(e.target.value)} />
              </label>
            </div>
            <div className="catalogo-fila">
              <label>
                <span>Ordenar</span>
                <select value={orden} onChange={(e) => setOrden(e.target.value)}>
                  {Object.entries(ORDENES).map(([k, o]) => <option key={k} value={k}>{o.texto}</option>)}
                </select>
              </label>
              <label className="catalogo-check">
                <input type="checkbox" checked={conDescuento} onChange={(e) => setConDescuento(e.target.checked)} />
                <span>Sólo con descuento</span>
              </label>
            </div>
            {activos > 0 && <button className="catalogo-limpiar" onClick={limpiar}>Limpiar filtros</button>}
          </div>
        )}

        {error && <p className="cajon-vacio">{error}</p>}
        {!items && !error && <p className="cajon-vacio">Cargando…</p>}
        {items && (
          <p className="catalogo-cuenta">
            {visibles.length} de {items.length} {items.length === 1 ? "carta" : "cartas"}
          </p>
        )}
        {items && visibles.length === 0 && <p className="cajon-vacio">Ninguna carta coincide con la búsqueda o los filtros.</p>}

        <ul className="cajon-lista">
          {visibles.map((i) => (
            <li key={i.id}>
              {i.imagen ? <img src={i.imagen} alt="" loading="lazy" /> : <div className="cajon-sinimagen" />}
              <div className="cajon-datos">
                <p className="cajon-nombre">{i.nombre}</p>
                <p className="cajon-edicion">{[i.set_nombre, i.grado].filter(Boolean).join(" · ")}</p>
                <p className="cajon-precio">
                  {pesos(i.precio_ars)}{i.descuento > 0 && ` (−${i.descuento}%)`} · {i.cantidad} en stock
                </p>
              </div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
