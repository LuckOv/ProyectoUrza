import { useEffect, useState } from "react";

import * as api from "./api.js";
import { Icono } from "./comunes.jsx";
import Configuracion from "./Configuracion.jsx";
import Dashboard from "./Dashboard.jsx";
import Historial from "./Historial.jsx";
import Inventario from "./Inventario.jsx";
import Pedidos from "./Pedidos.jsx";
import Propuestas from "./Propuestas.jsx";

const PESTANAS = [
  { id: "inventario", nombre: "Inventario", Vista: Inventario },
  { id: "pedidos", nombre: "Pedidos", Vista: Pedidos },
  { id: "propuestas", nombre: "Propuestas", Vista: Propuestas },
  { id: "dashboard", nombre: "Dashboard", Vista: Dashboard },
  { id: "historial", nombre: "Historial", Vista: Historial },
  { id: "configuracion", nombre: "Configuración", Vista: Configuracion },
];

/* La pestaña va en el hash (#pedidos) para que un F5 no te devuelva al inicio. */
function pestanaDelHash() {
  const id = window.location.hash.replace("#", "");
  return PESTANAS.some((p) => p.id === id) ? id : "inventario";
}

function Entrada({ onEntrar }) {
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    setError("");
    setOcupado(true);
    try {
      const r = await api.entrar(clave);
      api.guardarClave(clave);
      onEntrar(r.clave_por_defecto);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="mesa">
      <form className="entrada" onSubmit={enviar}>
        <span className="logo grande">MC</span>
        <h1>Mesa Central</h1>
        <p>Panel del vendedor de URZA</p>
        <label className="campo">
          <span>Clave de vendedor</span>
          <input type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoFocus />
        </label>
        {error && <p className="error-texto">{error}</p>}
        <button className="boton primario ancho" disabled={ocupado || !clave}>
          {ocupado ? "Entrando…" : "Entrar"}
        </button>
        <a className="enlace-suave" href="/">Volver a la tienda</a>
      </form>
    </div>
  );
}

export default function Panel() {
  const [adentro, setAdentro] = useState(api.hayClave());
  const [claveDebil, setClaveDebil] = useState(false);
  const [pestana, setPestana] = useState(pestanaDelHash);
  const [nuevas, setNuevas] = useState(0);   // propuestas sin mirar, para el globito de la pestaña

  useEffect(() => {
    if (!adentro) return;
    const mirar = () => api.propuestas({ estado: "nueva" }).then((r) => setNuevas(r.nuevas)).catch(() => {});
    mirar();
    const t = setInterval(mirar, 60000);
    return () => clearInterval(t);
  }, [adentro, pestana]);

  useEffect(() => {
    api.cuandoVenza(() => setAdentro(false));
    const cambio = () => setPestana(pestanaDelHash());
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);

  if (!adentro) {
    return <Entrada onEntrar={(debil) => { setClaveDebil(debil); setAdentro(true); }} />;
  }

  const { Vista } = PESTANAS.find((p) => p.id === pestana);
  const ir = (id) => { window.location.hash = id; };

  return (
    <div className="mesa">
      <div className="mesa-scroll">
        <header className="barra">
          <a className="marca" href="#inventario">
            <span className="logo">MC</span>
            <span>Mesa Central</span>
          </a>
          <nav className="pestanas" aria-label="Secciones">
            {PESTANAS.map((p) => (
              <button
                key={p.id}
                className={p.id === pestana ? "activa" : ""}
                aria-current={p.id === pestana ? "page" : undefined}
                onClick={() => ir(p.id)}
              >
                {p.nombre}
                {p.id === "propuestas" && nuevas > 0 && <span className="globito" aria-label={`${nuevas} nuevas`}>{nuevas}</span>}
              </button>
            ))}
          </nav>
          <div className="barra-acciones">
            <a className="icono-boton" href="/" title="Ver la tienda"><Icono nombre="tienda" /></a>
            <button
              className="icono-boton"
              title="Salir"
              onClick={() => { api.olvidarClave(); setAdentro(false); }}
            >
              <Icono nombre="salir" />
            </button>
          </div>
        </header>

        {claveDebil && (
          <p className="banda-aviso">
            Estás usando la clave por defecto. Definí <code>VENDEDOR_CLAVE</code> en <code>backend/.env</code> y reiniciá el backend.
            <button onClick={() => setClaveDebil(false)} aria-label="Cerrar aviso">×</button>
          </p>
        )}

        <main className="contenido">
          <Vista ir={ir} />
        </main>
      </div>
    </div>
  );
}
