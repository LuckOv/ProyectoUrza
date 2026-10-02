import { useState } from "react";

/* Las cartas que Urza sugiere para un mazo, abiertas en abanico como una mano
   de cartas. Al pasar el cursor por una, sube y muestra su nombre; nada más. */
export default function Abanico({ cartas }) {
  const [encima, setEncima] = useState(null);
  const n = cartas.length;
  if (!n) return null;

  // Apertura total del abanico: crece con la cantidad de cartas, con tope.
  const apertura = Math.min(64, 7 * (n - 1));
  const paso = n > 1 ? apertura / (n - 1) : 0;
  const medio = (n - 1) / 2;

  return (
    <div className="abanico" style={{ "--cartas": n }} aria-label={`${n} cartas sugeridas`}>
      {cartas.map((c, i) => {
        const angulo = (i - medio) * paso;
        // Las de las puntas bajan un poco, como cuando sostenés cartas.
        const caida = Math.abs(i - medio) ** 1.6 * 3;
        const activa = encima === i;
        return (
          <div
            key={`${c.nombre}-${i}`}
            className={`abanico-carta${activa ? " activa" : ""}`}
            style={{
              "--giro": `${angulo}deg`,
              "--caida": `${caida}px`,
              "--pos": i - medio,
              zIndex: activa ? 100 : i,
            }}
            onMouseEnter={() => setEncima(i)}
            onMouseLeave={() => setEncima(null)}
            onFocus={() => setEncima(i)}
            onBlur={() => setEncima(null)}
            tabIndex={0}
            aria-label={c.nombre}
          >
            {c.imagen
              ? <img src={c.imagen} alt="" draggable="false" />
              : <div className="abanico-sinimagen">{c.nombre}</div>}
            {activa && <span className="abanico-nombre" role="tooltip">{c.nombre}</span>}
          </div>
        );
      })}
    </div>
  );
}
