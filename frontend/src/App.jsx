import { useEffect, useRef, useState } from "react";

import Abanico from "./Abanico.jsx";
import Bolitas from "./Bolitas.jsx";
import Catalogo from "./Catalogo.jsx";
import FormPropuesta from "./FormPropuesta.jsx";
import Carrito from "./Carrito.jsx";
import Carta3D from "./Carta3D.jsx";
import * as api from "./api.js";

// El equipo de Urza: quién está detrás de cada respuesta.
const EQUIPO = {
  Tibalt: "el vendedor",
  Ajani: "el juez",
  Teferi: "el historiador",
  Saheeli: "la armadora de mazos",
};

function QuienResponde({ agentes }) {
  const otros = (agentes || []).filter((a) => EQUIPO[a]);
  return (
    <p className="quien">
      <strong>Urza</strong>
      {otros.length > 0 && (
        <> · consultó a {otros.map((a, i) => (
          <span key={a}>{i > 0 && (i === otros.length - 1 ? " y " : ", ")}<strong>{a}</strong>, {EQUIPO[a]}</span>
        ))}</>
      )}
    </p>
  );
}

const SUGERENCIAS = [
  { texto: "¿Tenés Cavern of Souls?", icono: "stock" },
  { texto: "Precio de Llanowar Elves", icono: "precio" },
  { texto: "Quiero comprar Heartfire Hero", icono: "compra" },
  { texto: "¿Qué cartas tenés?", icono: "stock" },
  { texto: "Ayudame a armar un mazo verde de elfos", icono: "precio" },
  { texto: "Quiero venderles una carta", icono: "compra", propuesta: true },
];

function Icono({ tipo }) {
  const comun = {
    width: 18, height: 18, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.6,
    strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true,
  };
  if (tipo === "compra") {
    return (
      <svg {...comun}>
        <circle cx="9" cy="20" r="1.2" />
        <circle cx="18" cy="20" r="1.2" />
        <path d="M2 3h3l2.4 12.1a1.6 1.6 0 0 0 1.6 1.3h8.6a1.6 1.6 0 0 0 1.6-1.3L21 7H6" />
      </svg>
    );
  }
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
  // Un thread_id por pestaña: el historial lo guarda el checkpointer del grafo
  // y el carrito queda atado a este mismo id (no hay cuentas de usuario).
  const [threadId] = useState(() => crypto.randomUUID());
  const [mensajes, setMensajes] = useState([]);
  const [entrada, setEntrada] = useState("");
  const [pensando, setPensando] = useState(false);
  const [verTrazas, setVerTrazas] = useState(false);

  const [items, setItems] = useState([]);
  const [panel, setPanel] = useState(null);        // "carrito" | "catalogo" | null
  const [agregando, setAgregando] = useState(null);
  const [aviso, setAviso] = useState("");
  const [latido, setLatido] = useState(false);     // animación del ícono al sumar

  const finRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, pensando]);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(""), 3500);
    return () => clearTimeout(t);
  }, [aviso]);

  function latir() {
    setLatido(true);
    setTimeout(() => setLatido(false), 600);
  }

  // La carta puede estar en varias variantes (set y grado): el botón manda
  // la que el jugador eligió en el selector de la carta.
  async function agregarCarta(carta, variante) {
    setAgregando(carta.nombre);
    try {
      const r = await api.agregarAlCarrito(threadId, {
        inventario_id: variante.id,
        cantidad: 1,
      });
      setItems(r.items);
      latir();
      setAviso(`${carta.nombre} va al carrito. Cuando quieras cerrar la compra, decíselo a Urza.`);
    } catch (e) {
      setAviso(e.message);
    } finally {
      setAgregando(null);
    }
  }

  async function quitar(id) {
    try { setItems((await api.quitarDelCarrito(threadId, id)).items); }
    catch (e) { setAviso(e.message); }
  }

  async function vaciar() {
    try { setItems((await api.vaciarCarrito(threadId)).items); }
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
          : {
              rol: "urza",
              texto: data.texto,
              herramientas: data.herramientas,
              carta: data.carta,
              pedido: data.pedido,
              mazo: data.mazo,
              catalogo: data.catalogo,
              propuesta: data.propuesta,
              agentes: data.agentes,
            },
      ]);
      // El agente pudo haber agregado, sacado o cerrado la compra: el
      // carrito que vuelve es la verdad.
      if (Array.isArray(data.carrito)) {
        const antes = items.reduce((s, i) => s + i.cantidad, 0);
        const ahora = data.carrito.reduce((s, i) => s + i.cantidad, 0);
        setItems(data.carrito);
        if (ahora > antes) latir();
      }
    } catch (e) {
      setMensajes((m) => [...m, { rol: "falla", texto: e.message }]);
    } finally {
      setPensando(false);
    }
  }

  // Botón "Ofrecer una carta": abre la planilla de propuesta al toque, sin
  // esperar al agente.
  function abrirPropuesta(dijo) {
    setMensajes((m) => [...m, ...(dijo ? [{ rol: "jugador", texto: dijo }] : []), {
      rol: "urza",
      agentes: ["Tibalt"],
      texto: "Completá la planilla: buscá la carta en la lista y elegí la edición exacta, "
        + "poné grado, cantidad y precio, y dejá tu nombre, apellido y mail (obligatorios). "
        + "Te respondemos por mail.",
      propuesta: {},
    }]);
  }

  function finalizarCompra() {
    setPanel(null);
    enviar("Quiero finalizar la compra");
  }

  const vacio = mensajes.length === 0 && !pensando;
  const unidades = items.reduce((s, i) => s + i.cantidad, 0);

  return (
    <div className="escena">
      {vacio && <Bolitas />}

      <header className="barra-superior">
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
                {m.rol === "urza" && <QuienResponde agentes={m.agentes} />}
                <div className={`msg ${m.rol}`}>
                  {m.texto}
                  {traza && <div className="traza">{traza}</div>}
                </div>
                {m.carta && (
                  <Carta3D
                    carta={m.carta}
                    onAgregar={agregarCarta}
                    agregando={agregando === m.carta.nombre}
                  />
                )}
                {m.mazo?.length > 0 && <Abanico cartas={m.mazo} />}
                {m.propuesta && (
                  <FormPropuesta
                    inicial={m.propuesta}
                    threadId={threadId}
                    onEnviada={(p) => setMensajes((ms) => [...ms, {
                      rol: "urza",
                      agentes: ["Tibalt"],
                      texto: `¡Listo, recibimos tu propuesta #${p.id}! La revisamos y te respondemos a ${p.email}.`,
                    }])}
                  />
                )}
                {m.catalogo && (
                  <button className="ver-catalogo" onClick={() => setPanel("catalogo")}>
                    Ver todas las cartas
                  </button>
                )}
                {m.pedido && (
                  <div className="comprobante">
                    <h3>Comprobante de pedido</h3>
                    {m.pedido}
                  </div>
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
                <button onClick={() => (s.propuesta ? abrirPropuesta(s.texto) : enviar(s.texto))}>
                  <Icono tipo={s.icono} />
                  {s.texto}
                </button>
              </li>
            ))}
          </ul>
        )}

        {!vacio && (
          <div className="pie-chat">
            <label className="toggle">
              <input type="checkbox" checked={verTrazas}
                     onChange={(e) => setVerTrazas(e.target.checked)} />
              Mostrar qué herramientas usó
            </label>
            <button className="ofrecer-carta" onClick={() => abrirPropuesta()} disabled={pensando}>
              Ofrecer una carta a la tienda
            </button>
          </div>
        )}
      </main>

      {aviso && <p className="aviso" role="status">{aviso}</p>}

      {panel === "catalogo" && <Catalogo onCerrar={() => setPanel(null)} />}
      {panel === "carrito" && (
        <Carrito
          items={items}
          onQuitar={quitar}
          onVaciar={vaciar}
          onFinalizar={finalizarCompra}
          onCerrar={() => setPanel(null)}
          ocupado={pensando}
        />
      )}
    </div>
  );
}
