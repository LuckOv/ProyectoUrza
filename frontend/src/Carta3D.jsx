import { useRef, useState } from "react";

import { dolares, pesos } from "./formato.js";

/* La carta se inclina siguiendo el puntero y se levanta al pasarle por encima.
   El efecto es una rotación en dos ejes proporcional a qué tan lejos del centro
   está el mouse, más un brillo que se desplaza como el de una carta foil.

   Si la tienda tiene la carta en varias variantes (set y grado, ej. "Sin
   graduar" o "PSA 10"), aparece un selector y el botón agrega la elegida. */
export default function Carta3D({ carta, onAgregar, agregando }) {
  const marcoRef = useRef(null);
  const [giro, setGiro] = useState({ x: 0, y: 0 });
  const [luz, setLuz] = useState({ x: 50, y: 50 });
  const [encima, setEncima] = useState(false);

  const variantes = carta.variantes || [];
  const conStock = variantes.filter((v) => v.cantidad > 0);
  const [elegidaId, setElegidaId] = useState(conStock[0]?.id ?? null);
  const elegida = variantes.find((v) => v.id === elegidaId) || conStock[0] || null;

  const mover = (e) => {
    const caja = marcoRef.current.getBoundingClientRect();
    const px = (e.clientX - caja.left) / caja.width;
    const py = (e.clientY - caja.top) / caja.height;
    // De 0..1 a -1..1, y de ahí a grados. El eje X se invierte para que la
    // carta "mire" hacia el puntero en vez de escaparse.
    setGiro({ x: -(py - 0.5) * 2 * 14, y: (px - 0.5) * 2 * 16 });
    setLuz({ x: px * 100, y: py * 100 });
  };

  const salir = () => {
    setEncima(false);
    setGiro({ x: 0, y: 0 });
    setLuz({ x: 50, y: 50 });
  };

  const imagen = elegida?.imagen || carta.imagen;
  let stock;
  if (elegida) stock = `${elegida.cantidad} en stock · ${pesos(elegida.precio_ars)}`;
  else if (variantes.length) stock = "Sin stock";
  else stock = "No está en la tienda";
  const referencia = !variantes.length && carta.precio_mercado_usd
    ? `Mercado: ${dolares(Number(carta.precio_mercado_usd))}`
    : null;

  return (
    <div className="carta3d">
      <div
        ref={marcoRef}
        className={`carta3d-marco${encima ? " encima" : ""}`}
        onMouseEnter={() => setEncima(true)}
        onMouseMove={mover}
        onMouseLeave={salir}
      >
        <div
          className="carta3d-cuerpo"
          style={{ transform: `rotateX(${giro.x}deg) rotateY(${giro.y}deg)` }}
        >
          {imagen ? (
            <img src={imagen} alt={carta.nombre} draggable="false" />
          ) : (
            <div className="carta3d-sinimagen">{carta.nombre}</div>
          )}
          <div
            className="carta3d-brillo"
            style={{ background: `radial-gradient(circle at ${luz.x}% ${luz.y}%, rgba(255,255,255,.45), rgba(255,255,255,0) 55%)` }}
          />
        </div>
      </div>

      <div className="carta3d-datos">
        <p className="carta3d-nombre">{carta.nombre}</p>
        <p className="carta3d-edicion">
          {elegida ? `${elegida.set_nombre || ""} · ${elegida.grado}` : carta.edicion}
        </p>
        <p className="carta3d-stock">
          {stock}
          {elegida?.descuento > 0 && ` (−${elegida.descuento}%)`}
          {referencia && ` · ${referencia}`}
        </p>

        {conStock.length > 1 && (
          <select
            className="carta3d-variante"
            value={elegida?.id ?? ""}
            onChange={(e) => setElegidaId(Number(e.target.value))}
            aria-label="Elegí la versión"
          >
            {conStock.map((v) => (
              <option key={v.id} value={v.id}>
                {v.set_nombre} · {v.grado} · {pesos(v.precio_ars)}
              </option>
            ))}
          </select>
        )}

        <button
          className="carta3d-agregar"
          onClick={() => onAgregar(carta, elegida)}
          disabled={!elegida || agregando}
        >
          {agregando ? "Agregando…" : "Agregar al carrito"}
        </button>
      </div>
    </div>
  );
}
