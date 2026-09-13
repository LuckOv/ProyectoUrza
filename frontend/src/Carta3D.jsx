import { useRef, useState } from "react";

/* La carta se inclina siguiendo el puntero y se levanta al pasarle por encima.
   El efecto es una rotación en dos ejes proporcional a qué tan lejos del centro
   está el mouse, más un brillo que se desplaza como el de una carta foil. */
export default function Carta3D({ carta, onAgregar, sesionIniciada, agregando }) {
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

  const precio = carta.precio_eur ? `€${carta.precio_eur}` : carta.precio_usd ? `$${carta.precio_usd}` : null;
  const hay = typeof carta.en_stock === "number" && carta.en_stock > 0;

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
          {carta.imagen ? (
            <img src={carta.imagen} alt={carta.nombre} draggable="false" />
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
        {carta.edicion && <p className="carta3d-edicion">{carta.edicion}</p>}
        <p className="carta3d-stock">
          {hay ? `${carta.en_stock} en stock` : carta.en_stock === 0 ? "Sin stock" : "No está en la tienda"}
          {precio && ` · ${precio}`}
        </p>

        <button
          className="carta3d-agregar"
          onClick={() => onAgregar(carta)}
          disabled={!hay || agregando}
          title={!sesionIniciada ? "Necesitás iniciar sesión para comprar" : undefined}
        >
          {agregando ? "Agregando…" : !sesionIniciada ? "Iniciá sesión para comprar" : "Agregar al carrito"}
        </button>
      </div>
    </div>
  );
}
