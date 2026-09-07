import { useEffect, useRef, useState } from "react";

const API = "http://localhost:8000";

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

/* La serpiente de cuentas cruza el fondo cada tanto y se va sola.
   El key que cambia fuerza a recrear el <img>, y eso reinicia la animación
   del webp desde el primer cuadro sin volver a descargarlo. */
function Serpiente() {
  const [visita, setVisita] = useState(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let aparecer, esconder;
    const programar = () => {
      const espera = 10000 + Math.random() * 20000;   // entre 10 y 30 segundos
      aparecer = setTimeout(() => {
        // Cada pasada entra a una altura distinta, entre el 10% y el 80%.
        setVisita({ id: Date.now(), alto: 10 + Math.random() * 70 });
        esconder = setTimeout(() => setVisita(null), 7000);
        programar();
      }, espera);
    };
    programar();

    return () => {
      clearTimeout(aparecer);
      clearTimeout(esconder);
    };
  }, []);

  if (!visita) return null;
  return (
    <img
      key={visita.id}
      className="serpiente"
      style={{ top: `${visita.alto}%` }}
      src="/bolitas.webp"
      alt=""
      aria-hidden="true"
    />
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
  const finRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, pensando]);

  async function enviar(texto) {
    const consulta = (texto ?? "").trim();
    if (!consulta || pensando) return;

    setMensajes((m) => [...m, { rol: "jugador", texto: consulta }]);
    setEntrada("");
    setPensando(true);

    try {
      const respuesta = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, texto: consulta }),
      });
      const data = await respuesta.json();
      setMensajes((m) => [
        ...m,
        data.error
          ? { rol: "falla", texto: data.error }
          : { rol: "urza", texto: data.texto, herramientas: data.herramientas },
      ]);
    } catch {
      setMensajes((m) => [
        ...m,
        {
          rol: "falla",
          texto: `No pude contactar la API en ${API}. Fijate que uvicorn esté corriendo.`,
        },
      ]);
    } finally {
      setPensando(false);
    }
  }

  const vacio = mensajes.length === 0 && !pensando;

  return (
    <div className="escena">
      <div className="holo" aria-hidden="true" />
      <Serpiente />

      <main className={vacio ? "centro vacio" : "centro"}>
        {vacio && <h1 className="hero">¿Qué carta estás buscando?</h1>}

        <div className="scroll">
          {mensajes.map((m, i) => {
            const traza = verTrazas ? trazaDe(m.herramientas) : "";
            return (
              <div key={i} className={`msg ${m.rol}`}>
                {m.texto}
                {traza && <div className="traza">{traza}</div>}
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
    </div>
  );
}
