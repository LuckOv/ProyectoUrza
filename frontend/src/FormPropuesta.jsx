import { useEffect, useRef, useState } from "react";

import * as api from "./api.js";
import { dolares } from "./formato.js";

const GRADOS = ["Sin graduar", ...Array.from({ length: 10 }, (_, i) => `PSA ${10 - i}`)];
const MAIL = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

/* Formulario para que el cliente le ofrezca una carta a la tienda. Aparece en
   el chat cuando Tibalt detecta que el jugador quiere vender.

   1. Busca la carta en la lista de todas las que existen (Scryfall) y elige la
      edición exacta.
   2. Pone grado, cantidad y precio.
   3. Nombre, apellido y mail son obligatorios: sin eso no se puede enviar. */
export default function FormPropuesta({ inicial = {}, threadId, onEnviada }) {
  const [texto, setTexto] = useState(inicial.carta || "");
  const [sugerencias, setSugerencias] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [resaltada, setResaltada] = useState(0);
  const [filtroSet, setFiltroSet] = useState("");
  const [nombreCarta, setNombreCarta] = useState(null);
  const [impresiones, setImpresiones] = useState(null);
  const [elegida, setElegida] = useState(null);

  const [grado, setGrado] = useState(inicial.grado || "Sin graduar");
  const [cantidad, setCantidad] = useState(inicial.cantidad || 1);
  const [precio, setPrecio] = useState(inicial.precio ?? "");
  const [moneda, setMoneda] = useState(inicial.moneda || "ARS");
  const [nombre, setNombre] = useState(inicial.nombre || "");
  const [apellido, setApellido] = useState(inicial.apellido || "");
  const [email, setEmail] = useState(inicial.email || "");
  const [comentario, setComentario] = useState("");

  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enviada, setEnviada] = useState(null);
  const pedido = useRef(0);

  // Autocompletado contra Scryfall, con una pausa para no pedir en cada tecla.
  useEffect(() => {
    if (nombreCarta) return;
    const t = texto.trim();
    if (t.length < 2) { setSugerencias([]); setBuscando(false); return; }
    const n = ++pedido.current;
    setBuscando(true);
    const espera = setTimeout(() => {
      api.autocompletarCartas(t)
        .then((r) => { if (n === pedido.current) { setSugerencias(r.nombres); setResaltada(0); } })
        .catch(() => {})
        .finally(() => n === pedido.current && setBuscando(false));
    }, 250);
    return () => clearTimeout(espera);
  }, [texto, nombreCarta]);

  async function elegirNombre(n) {
    setNombreCarta(n);
    setTexto(n);
    setSugerencias([]);
    setElegida(null);
    setImpresiones(null);
    setFiltroSet("");
    try {
      const r = await api.impresionesCartas(n);
      setImpresiones(r.impresiones);
      if (r.impresiones.length === 1) setElegida(r.impresiones[0]);
    } catch (e) {
      setError(e.message);
      setImpresiones([]);
    }
  }

  function volverABuscar() {
    setNombreCarta(null);
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

  const visibles = (impresiones || []).filter((i) =>
    !filtroSet || `${i.set_nombre} ${i.set_codigo}`.toLowerCase().includes(filtroSet.toLowerCase()));

  const faltan = [
    !elegida && "la carta (elegila de la lista)",
    !(Number(precio) > 0) && "el precio",
    !nombre.trim() && "nombre",
    !apellido.trim() && "apellido",
    !MAIL.test(email.trim()) && (email.trim() ? "un mail válido" : "mail"),
  ].filter(Boolean);

  async function enviar(e) {
    e.preventDefault();
    if (faltan.length) { setError(`Falta: ${faltan.join(", ")}.`); return; }
    setError("");
    setEnviando(true);
    try {
      const p = await api.enviarPropuesta({
        thread_id: threadId, nombre, apellido, email, scryfall_id: elegida.scryfall_id,
        grado, cantidad: Number(cantidad), precio: Number(precio), moneda, comentario,
      });
      setEnviada(p);
      onEnviada?.(p);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  if (enviada) {
    return (
      <div className="propuesta enviada">
        <h3>Propuesta #{enviada.id} enviada</h3>
        <p>
          {enviada.cantidad} × {enviada.carta} ({enviada.set_nombre} · {enviada.grado}) a{" "}
          {enviada.moneda === "USD" ? "US$" : "$"} {Number(enviada.precio).toLocaleString("es-AR")} c/u.
          La revisamos y te respondemos a <strong>{enviada.email}</strong>.
        </p>
      </div>
    );
  }

  return (
    <form className="propuesta" onSubmit={enviar}>
      <h3>Ofrecé una carta a la tienda</h3>
      <p className="propuesta-ayuda">Buscala en la lista y elegí la edición exacta: así sabemos cuál es.</p>

      {/* Paso 1: la carta, de la lista de todas las que existen (Scryfall). */}
      <div className="propuesta-buscar">
        <label className="propuesta-buscador">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input
            value={texto}
            onChange={(e) => { setTexto(e.target.value); if (nombreCarta) volverABuscar(); }}
            onKeyDown={teclaBusqueda}
            placeholder="Nombre de la carta (en inglés o en español)"
            aria-label="Buscar carta"
            role="combobox"
            aria-expanded={sugerencias.length > 0}
            aria-controls="propuesta-lista"
          />
          {buscando && <span className="propuesta-girando" aria-label="Buscando" />}
        </label>
        {sugerencias.length > 0 && (
          <ul className="propuesta-sugerencias" id="propuesta-lista" role="listbox">
            {sugerencias.map((s, i) => (
              <li key={s} role="option" aria-selected={i === resaltada}>
                <button
                  type="button"
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
        {!nombreCarta && texto.trim().length >= 2 && !buscando && !sugerencias.length && (
          <p className="propuesta-ayuda">No encontramos cartas con ese nombre. Probá escribiéndolo distinto.</p>
        )}
      </div>

      {/* Paso 2: la edición exacta. */}
      {nombreCarta && (
        <div className="propuesta-paso">
          <div className="propuesta-paso-cabeza">
            <h4>Ediciones de {nombreCarta}</h4>
            {impresiones && impresiones.length > 6 && (
              <input
                className="propuesta-filtro"
                value={filtroSet}
                onChange={(e) => setFiltroSet(e.target.value)}
                placeholder="Filtrar por set"
                aria-label="Filtrar ediciones por set"
              />
            )}
          </div>
          {!impresiones && <p className="propuesta-ayuda">Buscando ediciones…</p>}
          {impresiones?.length === 0 && <p className="propuesta-ayuda">No encontramos ediciones de esa carta.</p>}
          {impresiones?.length > 0 && (
            <ul className="propuesta-impresiones">
              {visibles.map((imp) => (
                <li key={imp.scryfall_id}>
                  <button
                    type="button"
                    className={elegida?.scryfall_id === imp.scryfall_id ? "elegida" : ""}
                    onClick={() => setElegida(imp)}
                    title={`${imp.set_nombre} #${imp.numero}`}
                  >
                    {imp.imagen_chica ? <img src={imp.imagen_chica} alt="" loading="lazy" /> : <span className="propuesta-sinimg">{imp.nombre}</span>}
                    <span className="propuesta-set">{imp.set_codigo} · #{imp.numero}</span>
                    <span className="propuesta-set-nombre">{imp.set_nombre}</span>
                    {imp.precio_usd != null && <span className="propuesta-mercado">Mercado {dolares(imp.precio_usd)}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {elegida && <p className="propuesta-elegida">✓ {elegida.nombre} · {elegida.set_nombre} #{elegida.numero}</p>}

      <div className="propuesta-fila">
        <label><span>Grado</span>
          <select value={grado} onChange={(e) => setGrado(e.target.value)}>
            {GRADOS.map((g) => <option key={g}>{g}</option>)}
          </select>
        </label>
        <label><span>Cantidad</span>
          <input type="number" min="1" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
        </label>
        <label><span>Precio c/u</span>
          <div className="propuesta-precio">
            <select value={moneda} onChange={(e) => setMoneda(e.target.value)} aria-label="Moneda">
              <option value="ARS">$</option>
              <option value="USD">US$</option>
            </select>
            <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} />
          </div>
        </label>
      </div>

      <div className="propuesta-fila">
        <label><span>Nombre *</span><input value={nombre} onChange={(e) => setNombre(e.target.value)} required /></label>
        <label><span>Apellido *</span><input value={apellido} onChange={(e) => setApellido(e.target.value)} required /></label>
      </div>
      <label className="propuesta-campo"><span>Mail *</span>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@mail.com" required />
      </label>
      <label className="propuesta-campo"><span>Comentario (opcional)</span>
        <input value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Estado, si es foil, etc." />
      </label>

      {error && <p className="propuesta-error">{error}</p>}
      <button className="propuesta-enviar" disabled={enviando}>
        {enviando ? "Enviando…" : "Enviar propuesta"}
      </button>
      <p className="propuesta-ayuda">* Obligatorios. Te respondemos por mail.</p>
    </form>
  );
}
