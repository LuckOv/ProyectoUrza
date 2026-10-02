import { useEffect, useMemo, useState } from "react";

import * as api from "./api.js";
import { pesos } from "./formato.js";

/* Todas las cartas a la venta, en una lista simple con buscador. Se abre con
   el botón "Ver todas las cartas" que aparece cuando Urza responde qué hay. */
export default function Catalogo({ onCerrar }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    api.catalogo().then((r) => setItems(r.items)).catch((e) => setError(e.message));
    const tecla = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onCerrar]);

  const visibles = useMemo(() => {
    const plano = (t) => (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const buscado = plano(q.trim());
    return (items || []).filter((i) => !buscado || plano(`${i.nombre} ${i.set_nombre} ${i.grado}`).includes(buscado));
  }, [items, q]);

  return (
    <div className="velo" onClick={onCerrar}>
      <aside className="cajon catalogo" onClick={(e) => e.stopPropagation()} aria-label="Cartas disponibles">
        <header>
          <h2>Cartas disponibles</h2>
          <button className="cajon-cerrar" onClick={onCerrar} aria-label="Cerrar">×</button>
        </header>

        <div className="catalogo-buscar">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar carta, set o grado"
            aria-label="Buscar carta"
            autoFocus
          />
        </div>

        {error && <p className="cajon-vacio">{error}</p>}
        {!items && !error && <p className="cajon-vacio">Cargando…</p>}
        {items && (
          <p className="catalogo-cuenta">
            {visibles.length} de {items.length} {items.length === 1 ? "carta" : "cartas"}
          </p>
        )}
        {items && visibles.length === 0 && <p className="cajon-vacio">Ninguna carta coincide con la búsqueda.</p>}

        <ul className="cajon-lista">
          {visibles.map((i) => (
            <li key={i.id}>
              {i.imagen ? <img src={i.imagen} alt="" loading="lazy" /> : <div className="cajon-sinimagen" />}
              <div className="cajon-datos">
                <p className="cajon-nombre">{i.nombre}</p>
                <p className="cajon-edicion">{[i.set_nombre, i.grado].filter(Boolean).join(" · ")}</p>
                <p className="cajon-precio">
                  {pesos(i.precio_ars)}{i.descuento > 0 && ` (−${i.descuento}%)`} · {i.cantidad} en stock
                </p>
              </div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
