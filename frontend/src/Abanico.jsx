import { useEffect, useRef, useState } from "react";

/* Las cartas que Saheeli sugiere para un mazo, abiertas en abanico como una
   mano de cartas. Al pasar el cursor por una, sube y muestra su nombre; nada más.

   El abanico mide el ancho que tiene en el chat y calcula el tamaño de las
   cartas, cuánto se superponen y cuánto se abren, para que entre entero
   contando el giro de las cartas de las puntas: nunca hay que scrollear a los
   costados para verlo. */

const ALTO = 1.4;      // alto / ancho de una carta (5:7)
const PIVOTE = 1.2;    // el giro es alrededor de un punto 1.2 cartas por debajo del borde de arriba
const MARGEN = 14;     // aire a cada lado (incluye el agrandado al pasar el cursor)
const rad = (g) => (g * Math.PI) / 180;

/* Mitad del ancho que ocupa el abanico, desde el centro hasta la esquina más
   alejada de la carta de la punta (girada). */
function mitad(w, sep, giroMax, medio) {
  const h = w * ALTO;
  const t = rad(giroMax);
  return medio * sep + PIVOTE * h * Math.sin(t) + (w / 2) * Math.cos(t);
}

export function medidas(ancho, n) {
  const medio = (n - 1) / 2;
  const libre = ancho / 2 - MARGEN;
  // Cuanto más cartas, más se abre, pero con tope para que no se desarme.
  let giroMax = n > 1 ? Math.min(22, 3.2 * medio) : 0;

  for (let w = 112; w >= 40; w -= 2) {
    const ideal = w * 0.42;
    const minimo = w * 0.14;
    // Separación que hace falta para llenar justo el ancho disponible.
    const resto = libre - (mitad(w, 0, giroMax, medio));
    const sep = medio > 0 ? Math.min(ideal, resto / medio) : 0;
    if (medio === 0 ? resto >= 0 : sep >= minimo) return { w, sep, giroMax };
  }
  // Muchísimas cartas en un chat muy angosto: se cierran casi derechas.
  giroMax = Math.min(giroMax, 8);
  const w = 40;
  const sep = Math.max(2, (libre - mitad(w, 0, giroMax, medio)) / Math.max(medio, 1));
  return { w, sep, giroMax };
}

export default function Abanico({ cartas }) {
  const cajaRef = useRef(null);
  const [ancho, setAncho] = useState(0);
  const [encima, setEncima] = useState(null);
  const n = cartas.length;

  useEffect(() => {
    const caja = cajaRef.current;
    if (!caja) return;
    const medir = () => setAncho(caja.clientWidth);
    medir();
    const obs = new ResizeObserver(medir);
    obs.observe(caja);
    return () => obs.disconnect();
  }, []);

  if (!n) return null;

  const { w, sep, giroMax } = medidas(ancho || 320, n);
  const medio = (n - 1) / 2;
  const h = w * ALTO;
  const caidaMax = w * 0.16;                       // las de las puntas bajan un poco
  // Lo que bajan las esquinas de las puntas por el giro + la caída: espacio abajo.
  const abajo = caidaMax + (w / 2) * Math.sin(rad(giroMax)) + 6;
  // Arriba: lo que sube la carta al pasar el cursor + el cartelito con el nombre.
  const arriba = 62;

  return (
    <div
      ref={cajaRef}
      className="abanico"
      style={{
        "--ancho": `${w}px`,
        height: `${h + abajo + arriba}px`,
        visibility: ancho ? "visible" : "hidden",
      }}
      aria-label={`${n} cartas sugeridas`}
    >
      {cartas.map((c, i) => {
        const pos = i - medio;
        const frac = medio ? pos / medio : 0;      // -1 … 1
        const angulo = frac * giroMax;
        const caida = frac * frac * caidaMax;
        const activa = encima === i;
        return (
          <div
            key={`${c.nombre}-${i}`}
            className={`abanico-carta${activa ? " activa" : ""}`}
            style={{
              "--giro": `${angulo}deg`,
              "--caida": `${caida}px`,
              "--x": `${pos * sep}px`,
              bottom: `${abajo}px`,
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
            {activa && (
              <span className={`abanico-nombre${frac < -0.6 ? " izq" : frac > 0.6 ? " der" : ""}`} role="tooltip">{c.nombre}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
