import { useEffect, useRef, useState } from "react";

import Bolitas from "./Bolitas.jsx";
import Carrito from "./Carrito.jsx";
import Carta3D from "./Carta3D.jsx";
import Sesion from "./Sesion.jsx";
import * as api from "./api.js";

const SUGERENCIAS = [
  { texto: "¿Tenés Cavern of Souls?", icono: "stock" },
  { texto: "Precio de Llanowar Elves", icono: "precio" },
  { texto: "¿Queda Twinflame Tyrant?", icono: "stock" },
];

function Icono({ tipo }) {
  const comun = {
    width: 18, height: 18, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.6,
    strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true,
  };
  if (tipo === "precio") {
    return (
      <svg {...comun}>
        <path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z" />
        <circle cx="7.5" cy="7.5" r="1.2" />
      </svg>
    );
  }
  return (
    <svg {...comun}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 10h18M9 4v16" />
    </svg>
  );
}

function IconoCarrito() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="9" cy="20" r="1.4" />
      <circle cx="18" cy="20" r="1.4" />
      <path d="M2 3h3l2.4 12.1a1.6 1.6 0 0 0 1.6 1.3h8.6a1.6 1.6 0 0 0 1.6-1.3L21 7H6" />
    </svg>
  );
}

function trazaDe(herramientas) {
  if (!herramientas || herramientas.length === 0) return "";
  return herramientas
    .map((h) => `${h.nombre}(${Object.values(h.argumentos || {}).join(", ")})`)
    .join(" · ");
}

export default function App() {
  // Un thread_id por pestaña: el historial lo guarda el checkpointer del grafo.
  const [threadId] = useState(() => crypto.randomUUID());
  const [mensajes, setMensajes] = useState([]);
  const [entrada, setEntrada] = useState("");
  const [pensando, setPensando] = useState(false);
  const [verTrazas, setVerTrazas] = useState(false);

  const [usuario, setUsuario] = useState(null);
  const [items, setItems] = useState([]);
  const [panel, setPanel] = useState(null);        // "sesion" | "carrito" | null
  const [agregando, setAgregando] = useState(null);
  const [aviso, setAviso] = useState("");
  const [latido, setLatido] = useState(false);     // animación del ícono al sumar

  const finRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, pensando]);

  // Si quedó un token de una sesión anterior, lo revalidamos al abrir.
  useEffect(() => {
    if (!api.leerToken()) return;
    api.quienSoy()
      .then((r) => { setUsuario(r.usuario); return api.verCarrito(); })
      .then((r) => setItems(r.items))
      .catch(() => { api.borrarToken(); setUsuario(null); });
  }, []);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(""), 3500);
    return () => clearTimeout(t);
  }, [aviso]);

  async function entrar(u, c) {
    const r = await api.ingresar(u, c);
    api.guardarToken(r.token);
    setUsuario(r.usuario);
    setItems((await api.verCarrito()).items);
    setPanel(null);
  }

  async function registrar(u, c) {
    const r = await api.registrar(u, c);
    api.guardarToken(r.token);
    setUsuario(r.usuario);
    setItems([]);
    setPanel(null);
  }

  async function cerrarSesion() {
    await api.salir().catch(() => {});
    api.borrarToken();
    setUsuario(null);
    setItems([]);
    setPanel(null);
  }

  async function agregarCarta(carta) {
    // Ésta es la regla de negocio: sin cuenta no se compra.
    if (!usuario) {
      setPanel("sesion");
      setAviso("Necesitás una cuenta para poder comprar.");
      return;
    }
    setAgregando(carta.nombre);
    try {
      const r = await api.agregarAlCarrito({
        nombre: carta.nombre,
        edicion: carta.edicion,
        precio: carta.precio_eur ? Number(carta.precio_eur) : null,
        imagen: carta.imagen,
        cantidad: 1,
      });
      setItems(r.items);
      setLatido(true);
      setTimeout(() => setLatido(false), 600);
      setAviso(`${carta.nombre} va al carrito.`);
    } catch (e) {
      setAviso(e.message);
    } finally {
      setAgregando(null);
    }
  }

  async function quitar(id) {
    try { setItems((await api.quitarDelCarrito(id)).items); }
    catch (e) { setAviso(e.message); }
  }

  async function vaciar() {
    try { setItems((await api.vaciarCarrito()).items); }
    catch (e) { setAviso(e.message); }
  }

  async function enviar(texto) {
    const consulta = (texto ?? "").trim();
    if (!consulta || pensando) return;

    setMensajes((m) => [...m, { rol: "jugador", texto: consulta }]);
    setEntrada("");
    setPensando(true);

    try {
      const data = await api.preguntar(threadId, consulta);
      setMensajes((m) => [
        ...m,
        data.error
          ? { rol: "falla", texto: data.error }
          : { rol: "urza", texto: data.texto, herramientas: data.herramientas, carta: data.carta },
      ]);
    } catch (e) {
      setMensajes((m) => [...m, { rol: "falla", texto: e.message }]);
    } finally {
      setPensando(false);
    }
  }

  const vacio = mensajes.length === 0 && !pensando;
  const unidades = items.reduce((s, i) => s + i.cantidad, 0);

  return (
    <div className="escena">
      {vacio && <Bolitas />}

      <header className="barra-superior">
        {usuario ? (
          <>
            <span className="usuario">{usuario}</span>
            <button className="enlace" onClick={cerrarSesion}>Salir</button>
          </>
        ) : (
          <button className="enlace" onClick={() => setPanel("sesion")}>Entrar</button>
        )}

        {/* El carrito sólo se muestra cuando hay algo adentro. */}
        {unidades > 0 && (
          <button
            className={`carrito-boton${latido ? " latido" : ""}`}
            onClick={() => setPanel("carrito")}
            aria-label={`Carrito, ${unidades} cartas`}
          >
            <IconoCarrito />
            <span className="carrito-cuenta">{unidades}</span>
          </button>
        )}
      </header>

      <main className={vacio ? "centro vacio" : "centro"}>
        {vacio && <h1 className="hero">¿Qué carta estás buscando?</h1>}

        <div className="scroll">
          {mensajes.map((m, i) => {
            const traza = verTrazas ? trazaDe(m.herramientas) : "";
            return (
              <div key={i} className="turno">
                <div className={`msg ${m.rol}`}>
                  {m.texto}
                  {traza && <div className="traza">{traza}</div>}
                </div>
                {m.carta && (
                  <Carta3D
                    carta={m.carta}
                    onAgregar={agregarCarta}
                    sesionIniciada={Boolean(usuario)}
                    agregando={agregando === m.carta.nombre}
                  />
                )}
              </div>
            );
          })}

          {pensando && (
            <div className="msg urza">
              <span className="puntos">Urza está buscando</span>
            </div>
          )}

          <div ref={finRef} />
        </div>

        <div className="barra">
          <input
            className="entrada"
            value={entrada}
            placeholder="Preguntá lo que quieras"
            onChange={(e) => setEntrada(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && enviar(entrada)}
            disabled={pensando}
            aria-label="Escribí tu consulta"
          />
          <button
            className="enviar"
            onClick={() => enviar(entrada)}
            disabled={pensando || !entrada.trim()}
            aria-label="Enviar consulta"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                 strokeLinejoin="round" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>

        {vacio && (
          <ul className="sugerencias">
            {SUGERENCIAS.map((s) => (
              <li key={s.texto}>
                <button onClick={() => enviar(s.texto)}>
                  <Icono tipo={s.icono} />
                  {s.texto}
                </button>
              </li>
            ))}
          </ul>
        )}

        {!vacio && (
          <label className="toggle">
            <input type="checkbox" checked={verTrazas}
                   onChange={(e) => setVerTrazas(e.target.checked)} />
            Mostrar qué herramientas usó
          </label>
        )}
      </main>

      {aviso && <p className="aviso" role="status">{aviso}</p>}

      {panel === "sesion" && (
        <Sesion onEntrar={entrar} onRegistrar={registrar} onCerrar={() => setPanel(null)} />
      )}
      {panel === "carrito" && (
        <Carrito items={items} onQuitar={quitar} onVaciar={vaciar} onCerrar={() => setPanel(null)} />
      )}
    </div>
  );
}
