import { useRef, useState } from "react";

import { dolares, pesos } from "../compartido/formato.js";

/* Imagen de carta que se inclina siguiendo el puntero y se levanta al pasarle
   por encima. El efecto es una rotación en dos ejes proporcional a qué tan
   lejos del centro está el mouse, más un brillo que se desplaza como el de una
   carta foil. La usan la carta del chat y sus variantes.
   acabado ("normal" | "foil" | "etched", lo dice Scryfall): las foil suman un
   reflejo tornasolado que se mueve con el puntero, y las etched uno metálico. */
const NOMBRE_ACABADO = { foil: "Foil", etched: "Etched" };

export function CartaInclinable({ imagen, nombre, ancho, acabado = "normal" }) {
  const marcoRef = useRef(null);
  const [giro, setGiro] = useState({ x: 0, y: 0 });
  const [luz, setLuz] = useState({ x: 50, y: 50 });
  const [encima, setEncima] = useState(false);

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

  return (
    <div
      ref={marcoRef}
      className={`carta3d-marco${encima ? " encima" : ""}${NOMBRE_ACABADO[acabado] ? ` acabado-${acabado}` : ""}`}
      style={{ ...(ancho ? { width: ancho } : {}), "--lx": `${luz.x}%`, "--ly": `${luz.y}%` }}
      onMouseEnter={() => setEncima(true)}
      onMouseMove={mover}
      onMouseLeave={salir}
    >
      <div
        className="carta3d-cuerpo"
        style={{ transform: `rotateX(${giro.x}deg) rotateY(${giro.y}deg)` }}
      >
        {imagen ? (
          <img src={imagen} alt={nombre} draggable="false" />
        ) : (
          <div className="carta3d-sinimagen">{nombre}</div>
        )}
        {NOMBRE_ACABADO[acabado] && <div className="carta3d-holo" aria-hidden="true" />}
        <div
          className="carta3d-brillo"
          style={{ background: `radial-gradient(circle at ${luz.x}% ${luz.y}%, rgba(255,255,255,.45), rgba(255,255,255,0) 55%)` }}
        />
      </div>
    </div>
  );
}

function BotonAgregar({ onClick, hay, agregando }) {
  return (
    <button className="carta3d-agregar" onClick={onClick} disabled={!hay || agregando}>
      {agregando ? "Agregando…" : hay ? "Agregar al carrito" : "Sin stock"}
    </button>
  );
}

/* Precio de una variante. Si el vendedor no le cargó precio, se avisa, pero
   la carta se puede comprar igual: el precio se confirma en el local. */
function Precio({ valor }) {
  if (valor == null) {
    return (
      <span className="carta3d-sinprecio" title="Esta carta todavía no tiene precio cargado">
        Sin precio · se confirma en el local
      </span>
    );
  }
  return <strong className="carta3d-precio">{pesos(valor)}</strong>;
}

/* La carta de la que habló Urza. Si la tienda la tiene en varias versiones
   (mismo nombre, distinto grado o set: "Sin graduar", "PSA 9", "PSA 10"...),
   se muestran todas, una al lado de la otra, cada una con su precio abajo. */
export default function Carta3D({ carta, onAgregar, agregando }) {
  const variantes = carta.variantes || [];

  // Varias versiones en la tienda: una carta por cada una.
  if (variantes.length > 1) {
    return (
      <div className="carta3d-grupo">
        <p className="carta3d-nombre">{carta.nombre}</p>
        <p className="carta3d-edicion">{variantes.length} versiones en la tienda</p>
        <div className="carta3d-variantes">
          {variantes.map((v) => {
            const hay = v.cantidad > 0;
            return (
              <div key={v.id} className={`carta3d-variante${hay ? "" : " agotada"}`}>
                <CartaInclinable imagen={v.imagen || carta.imagen} nombre={carta.nombre} acabado={v.acabado} />
                <span className={`carta3d-grado${v.grado === "Sin graduar" ? "" : " psa"}`}>
                  {v.grado}{NOMBRE_ACABADO[v.acabado] ? ` · ${NOMBRE_ACABADO[v.acabado]}` : ""}
                </span>
                <Precio valor={v.precio_ars} />
                {v.descuento > 0 && <span className="carta3d-desc">−{v.descuento}%</span>}
                <span className="carta3d-stock">
                  {hay ? `${v.cantidad} en stock` : "Sin stock"}{v.set_nombre ? ` · ${v.set_nombre}` : ""}
                </span>
                <BotonAgregar
                  hay={hay}
                  agregando={agregando}
                  onClick={() => onAgregar(carta, v)}
                />
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Una sola versión (o la tienda no la tiene).
  const v = variantes[0] || null;
  const acabado = v ? v.acabado : carta.acabado;
  const hay = Boolean(v && v.cantidad > 0);
  let stock;
  if (v) stock = hay ? `${v.cantidad} en stock` : "Sin stock";
  else stock = "No está en la tienda";
  const referencia = !v && carta.precio_mercado_usd
    ? `Mercado: ${dolares(Number(carta.precio_mercado_usd))}`
    : null;

  return (
    <div className="carta3d">
      <CartaInclinable imagen={v?.imagen || carta.imagen} nombre={carta.nombre} acabado={acabado} />
      <div className="carta3d-datos">
        <p className="carta3d-nombre">{carta.nombre}</p>
        <p className="carta3d-edicion">
          {v ? `${v.set_nombre || ""} · ${v.grado}` : carta.edicion}
          {NOMBRE_ACABADO[acabado] && ` · ${NOMBRE_ACABADO[acabado]}`}
        </p>
        <p className="carta3d-stock">
          {stock}
          {hay && v.precio_ars != null && ` · ${pesos(v.precio_ars)}`}
          {v?.descuento > 0 && ` (−${v.descuento}%)`}
          {referencia && ` · ${referencia}`}
        </p>
        {hay && v.precio_ars == null && <Precio valor={null} />}
        {v && (
          <BotonAgregar hay={hay} agregando={agregando} onClick={() => onAgregar(carta, v)} />
        )}
      </div>
    </div>
  );
}
