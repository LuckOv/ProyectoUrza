import { useEffect, useRef, useState } from "react";

import { numero } from "../compartido/formato.js";
import * as api from "./api.js";
import { Etiqueta, fechaHora } from "./comunes.jsx";

/* Configuración → Bases del bot. Ajani (reglas) y Teferi (lore) responden
   buscando en dos bases que se arman en ESTA compu (la que corre el backend)
   y no viajan con git. Acá se instalan con un botón y se ve el avance.
   Quien usa el chat desde otro dispositivo no necesita instalar nada. */

const duracion = (s) => (s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`);

function Fila({ titulo, quien, instalado, detalle, partes, ocupado, onInstalar }) {
  return (
    <div className="bot-fila">
      <div>
        <strong>{titulo}</strong> <span className="apagado">· {quien}</span>
        <p className="ayuda">{detalle}</p>
      </div>
      <Etiqueta tono={instalado ? "stock-ok" : "stock-bajo"}>{instalado ? "Instalado" : "No instalado"}</Etiqueta>
      <button className="boton chico" disabled={ocupado} onClick={() => onInstalar(partes)}>
        {instalado ? "Reinstalar" : "Instalar"}
      </button>
    </div>
  );
}

export default function BasesBot({ avisar }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const logRef = useRef(null);

  async function cargar() {
    try { setD(await api.bot()); setError(""); } catch (e) { setError(e.message); }
  }
  useEffect(() => { cargar(); }, []);

  // Mientras instala, se consulta cada 2 segundos.
  const corriendo = d?.trabajo.corriendo;
  useEffect(() => {
    if (!corriendo) return;
    const t = setInterval(cargar, 2000);
    return () => clearInterval(t);
  }, [corriendo]);

  useEffect(() => { logRef.current?.scrollTo(0, logRef.current.scrollHeight); }, [d?.trabajo.log.length]);

  async function instalar(partes) {
    try { setD(await api.instalarBot(partes)); } catch (e) { avisar(e.message, true); }
  }
  async function cancelar() {
    try { setD(await api.cancelarBot()); } catch (e) { avisar(e.message, true); }
  }

  if (error) return <p className="error-texto">{error}</p>;
  if (!d) return <p className="cargando">Cargando…</p>;

  const t = d.trabajo;
  const reglasOk = Boolean(d.reglas.fragmentos);
  const loreOk = Boolean(d.lore.fragmentos);
  const faltan = d.dependencias_faltan.length > 0;
  const bloqueado = corriendo || faltan;

  return (
    <section className="bloque">
      <div className="bloque-cabeza">
        <div>
          <h3>Bases del bot (reglas y lore)</h3>
          <p className="ayuda">
            Ajani y Teferi responden buscando en estas bases.
          </p>
        </div>
        <button className="boton primario" disabled={bloqueado || (reglasOk && loreOk && d.modelos.rerank)}
                onClick={() => instalar(["reglas", "modelos", "lore"])}>
          {reglasOk && loreOk && d.modelos.rerank ? "Todo instalado" : "Instalar todo"}
        </button>
      </div>

      {faltan && (
        <p className="aviso-suave">
          Faltan librerías en el backend ({d.dependencias_faltan.join(", ")}). En la carpeta del proyecto corré{" "}
          <code>uv sync</code> y reiniciá el backend.
        </p>
      )}

      <div className="bot-filas">
        <Fila
          titulo="Reglas" quien="Ajani, el juez" instalado={reglasOk} ocupado={bloqueado} partes={["reglas", "modelos"]}
          onInstalar={instalar}
          detalle={reglasOk
            ? `${numero(d.reglas.fragmentos)} fragmentos de las Reglas Completas · ${fechaHora(d.reglas.actualizado)}`
            : "Baja las Reglas Completas oficiales y las indexa. Tarda unos minutos."}
        />
        <Fila
          titulo="Lore" quien="Teferi, el historiador" instalado={loreOk} ocupado={bloqueado} partes={["lore"]}
          onInstalar={instalar}
          detalle={loreOk
            ? `${numero(d.lore.fragmentos)} fragmentos de la MTG Wiki${d.lore.paginas ? ` (${numero(d.lore.paginas)} páginas)` : ""} · ${fechaHora(d.lore.actualizado)}`
            : d.lore.descarga_completa
              ? `Ya hay ${numero(d.lore.paginas)} páginas bajadas: sólo falta indexarlas (sin internet, unos minutos).`
              : `Baja la MTG Wiki${d.lore.paginas ? ` (van ${numero(d.lore.paginas)} páginas)` : ""} e indexa. Puede tardar horas; si se corta, retoma.`}
        />
      </div>

      {(corriendo || t.resultado) && (
        <div className="bot-trabajo">
          <div className="bot-trabajo-cabeza">
            {corriendo ? (
              <span><span className="girando" /> {t.paso ? d.pasos[t.paso] : "Arrancando"}… · {duracion(t.segundos)}
                {t.pasos.length > 1 && <span className="apagado"> (paso {t.pasos.indexOf(t.paso) + 1} de {t.pasos.length})</span>}
              </span>
            ) : (
              <Etiqueta tono={t.resultado === "ok" ? "stock-ok" : t.resultado === "error" ? "estado-rechazada" : "neutro"}>
                {t.mensaje}
              </Etiqueta>
            )}
            {corriendo && <button className="boton chico peligro-suave" onClick={cancelar}>Cancelar</button>}
          </div>
          <pre className="bot-log" ref={logRef}>{t.log.slice(-60).join("\n") || "…"}</pre>
        </div>
      )}
    </section>
  );
}
