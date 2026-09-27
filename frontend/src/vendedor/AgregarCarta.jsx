import { useEffect, useRef, useState } from "react";

import { dolares, pesos } from "../formato.js";
import * as api from "./api.js";
import { Etiqueta, Icono, Modal } from "./comunes.jsx";

/* Alta de una carta en tres pasos, todo contra Scryfall:
   1. escribís el nombre y aparece la lista de Scryfall (autocompletado),
   2. elegís la impresión exacta (set, número, arte),
   3. cargás grado, cantidad y precio (viene sugerido el de Scryfall). */
export default function AgregarCarta({ grados, onCerrar, onAgregada }) {
  const [texto, setTexto] = useState("");
  const [sugerencias, setSugerencias] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [resaltada, setResaltada] = useState(0);

  const [nombre, setNombre] = useState(null);
  const [impresiones, setImpresiones] = useState(null);
  const [dolar, setDolar] = useState(0);
  const [elegida, setElegida] = useState(null);
  const [filtroSet, setFiltroSet] = useState("");

  const [grado, setGrado] = useState("Sin graduar");
  const [cantidad, setCantidad] = useState(1);
  const [precio, setPrecio] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const pedidoActual = useRef(0);

  // Autocompletado con una pausa de 250 ms, para no pegarle a Scryfall en
  // cada tecla. Si llega tarde una respuesta vieja, se descarta.
  useEffect(() => {
    if (nombre) return;
    const t = texto.trim();
    if (t.length < 2) { setSugerencias([]); return; }
    const n = ++pedidoActual.current;
    setBuscando(true);
    const espera = setTimeout(async () => {
      try {
        const r = await api.autocompletar(t);
        if (n === pedidoActual.current) { setSugerencias(r.nombres); setResaltada(0); }
      } catch (e) {
        if (n === pedidoActual.current) setError(e.message);
      } finally {
        if (n === pedidoActual.current) setBuscando(false);
      }
    }, 250);
    return () => clearTimeout(espera);
  }, [texto, nombre]);

  async function elegirNombre(n) {
    setNombre(n);
    setTexto(n);
    setSugerencias([]);
    setImpresiones(null);
    setElegida(null);
    setError("");
    try {
      const r = await api.impresiones(n);
      setImpresiones(r.impresiones);
      setDolar(r.dolar);
      if (r.impresiones.length === 1) elegirImpresion(r.impresiones[0]);
    } catch (e) {
      setError(e.message);
      setImpresiones([]);
    }
  }

  function elegirImpresion(imp) {
    setElegida(imp);
    setPrecio(imp.precio_usd ?? "");
  }

  function volverABuscar() {
    setNombre(null);
    setImpresiones(null);
    setElegida(null);
    setFiltroSet("");
  }

  function teclaBusqueda(e) {
    if (!sugerencias.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setResaltada((i) => Math.min(i + 1, sugerencias.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setResaltada((i) => Math.max(i - 1, 0)); }
    if (e.key === "Enter") { e.preventDefault(); elegirNombre(sugerencias[resaltada]); }
  }

  async function agregar(seguir) {
    setError("");
    setOcupado(true);
    try {
      const carta = await api.altaCarta({
        scryfall_id: elegida.scryfall_id,
        grado,
        cantidad: Number(cantidad),
        precio_usd: precio === "" ? null : Number(precio),
      });
      onAgregada(carta, seguir);
      if (seguir) { volverABuscar(); setTexto(""); setCantidad(1); setGrado("Sin graduar"); }
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  const visibles = (impresiones || []).filter((i) =>
    !filtroSet || `${i.set_nombre} ${i.set_codigo}`.toLowerCase().includes(filtroSet.toLowerCase()));
  const precioNum = precio === "" ? null : Number(precio);

  return (
    <Modal
      titulo="Agregar carta"
      subtitulo="Buscala en Scryfall, elegí la impresión y cargá el stock."
      onCerrar={onCerrar}
      ancho={860}
      pie={elegida && (
        <>
          <button className="boton" onClick={() => agregar(true)} disabled={ocupado}>Agregar y cargar otra</button>
          <button className="boton primario" onClick={() => agregar(false)} disabled={ocupado}>
            {ocupado ? "Agregando…" : "Agregar al inventario"}
          </button>
        </>
      )}
    >
      {/* Paso 1: nombre */}
      <div className="autocompletar">
        <label className="buscador ancho">
          <Icono nombre="buscar" />
          <input
            value={texto}
            onChange={(e) => { setTexto(e.target.value); if (nombre) volverABuscar(); }}
            onKeyDown={teclaBusqueda}
            placeholder="Nombre de la carta (en inglés o en español)"
            autoFocus
            role="combobox"
            aria-expanded={sugerencias.length > 0}
            aria-controls="lista-scryfall"
          />
          {buscando && <span className="girando" aria-label="Buscando" />}
        </label>
        {sugerencias.length > 0 && (
          <ul className="sugerencias-scryfall" id="lista-scryfall" role="listbox">
            {sugerencias.map((s, i) => (
              <li key={s} role="option" aria-selected={i === resaltada}>
                <button
                  className={i === resaltada ? "resaltada" : ""}
                  onMouseEnter={() => setResaltada(i)}
                  onClick={() => elegirNombre(s)}
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        )}
        {!nombre && texto.trim().length >= 2 && !buscando && !sugerencias.length && (
          <p className="ayuda">Scryfall no encontró cartas con ese nombre.</p>
        )}
      </div>

      {/* Paso 2: impresión */}
      {nombre && (
        <div className="paso">
          <div className="paso-cabeza">
            <h3>Impresiones de {nombre}</h3>
            {impresiones && impresiones.length > 6 && (
              <input
                className="entrada-chica"
                value={filtroSet}
                onChange={(e) => setFiltroSet(e.target.value)}
                placeholder="Filtrar por set"
                aria-label="Filtrar impresiones por set"
              />
            )}
          </div>
          {!impresiones && <p className="cargando">Trayendo impresiones de Scryfall…</p>}
          {impresiones && (
            <ul className="impresiones">
              {visibles.map((imp) => (
                <li key={imp.scryfall_id}>
                  <button
                    className={`impresion${elegida?.scryfall_id === imp.scryfall_id ? " elegida" : ""}`}
                    onClick={() => elegirImpresion(imp)}
                    title={`${imp.set_nombre} #${imp.numero}`}
                  >
                    {imp.imagen_chica ? <img src={imp.imagen_chica} alt="" loading="lazy" /> : <div className="ficha-sinimg">{imp.nombre}</div>}
                    <span className="impresion-set">{imp.set_codigo} · #{imp.numero}</span>
                    <span className="impresion-nombre">{imp.set_nombre}</span>
                    <span className="impresion-precio">{dolares(imp.precio_usd)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Paso 3: stock */}
      {elegida && (
        <div className="paso alta">
          <img src={elegida.imagen} alt="" className="alta-img" />
          <div className="formulario">
            <h3>{elegida.nombre}</h3>
            <p className="ayuda">
              {elegida.set_nombre} ({elegida.set_codigo}) #{elegida.numero} · {elegida.fecha?.slice(0, 4)}{" "}
              {elegida.legal_standard && <Etiqueta tono="estado-realizada">Legal en Standard</Etiqueta>}
            </p>
            <div className="fila-campos">
              <label className="campo">
                <span>Grado</span>
                <select value={grado} onChange={(e) => setGrado(e.target.value)}>
                  {grados.map((g) => <option key={g}>{g}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>Cantidad</span>
                <div className="contador">
                  <button type="button" onClick={() => setCantidad((c) => Math.max(1, Number(c) - 1))}>−</button>
                  <input type="number" min="1" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
                  <button type="button" onClick={() => setCantidad((c) => Number(c) + 1)}>+</button>
                </div>
              </label>
            </div>
            <label className="campo">
              <span>Precio en dólares {elegida.precio_usd != null && <em>(Scryfall: {dolares(elegida.precio_usd)})</em>}</span>
              <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} />
              <small>
                {precioNum != null
                  ? `Se vende a ${pesos(Math.round(precioNum * dolar))} (dólar ${pesos(dolar)}, antes de descuentos).`
                  : "Sin precio: el chat no la va a poder vender hasta que le pongas uno."}
              </small>
            </label>
          </div>
        </div>
      )}

      {error && <p className="error-texto">{error}</p>}
    </Modal>
  );
}
