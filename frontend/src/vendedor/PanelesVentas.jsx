import { useState } from "react";

import { dolares, numero, pesos } from "../formato.js";
import { Etiqueta, textoAlerta } from "./comunes.jsx";

// Colores de Magic. Cada porción lleva además su nombre y % en la leyenda,
// así el color nunca es lo único que la identifica.
const COLOR_MTG = {
  W: "#b9a46a", U: "#2f67b0", B: "#5b4577", R: "#b8382c", G: "#2f7a45",
  M: "#a8800f", C: "#7a7f8c", "?": "#c9b994",
};

/* Torta (dona) del color más vendido. */
export function TortaColores({ colores }) {
  const [encima, setEncima] = useState(null);
  const total = colores.reduce((s, c) => s + c.unidades, 0);
  if (!total) return <p className="vacio">Sin ventas en el período.</p>;

  const R = 70, r = 42, cx = 80, cy = 80;
  let angulo = -Math.PI / 2;
  const porciones = colores.map((c) => {
    const frac = c.unidades / total;
    const desde = angulo;
    angulo += frac * 2 * Math.PI;
    return { ...c, frac, desde, hasta: angulo };
  });
  const punto = (rad, a) => [cx + rad * Math.cos(a), cy + rad * Math.sin(a)];
  const camino = ({ desde, hasta, frac }) => {
    if (frac >= 0.999) {   // una sola porción: anillo completo
      return `M ${cx} ${cy - R} A ${R} ${R} 0 1 1 ${cx - 0.01} ${cy - R} L ${cx - 0.01} ${cy - r} A ${r} ${r} 0 1 0 ${cx} ${cy - r} Z`;
    }
    const grande = hasta - desde > Math.PI ? 1 : 0;
    const [x1, y1] = punto(R, desde), [x2, y2] = punto(R, hasta);
    const [x3, y3] = punto(r, hasta), [x4, y4] = punto(r, desde);
    return `M ${x1} ${y1} A ${R} ${R} 0 ${grande} 1 ${x2} ${y2} L ${x3} ${y3} A ${r} ${r} 0 ${grande} 0 ${x4} ${y4} Z`;
  };
  const destacado = encima != null ? porciones[encima] : porciones[0];

  return (
    <div className="torta">
      <svg viewBox="0 0 160 160" role="img" aria-label="Ventas por color">
        {porciones.map((p, i) => (
          <path
            key={p.color}
            d={camino(p)}
            fill={COLOR_MTG[p.color]}
            stroke="var(--pergamino)"
            strokeWidth="2"
            opacity={encima == null || encima === i ? 1 : 0.45}
            onMouseEnter={() => setEncima(i)}
            onMouseLeave={() => setEncima(null)}
          >
            <title>{`${p.nombre}: ${p.unidades} cartas (${Math.round(p.frac * 100)}%)`}</title>
          </path>
        ))}
        <text x={cx} y={cy - 4} textAnchor="middle" className="torta-centro-num">{Math.round(destacado.frac * 100)}%</text>
        <text x={cx} y={cy + 14} textAnchor="middle" className="torta-centro-txt">{destacado.nombre}</text>
      </svg>
      <ul className="torta-leyenda">
        {porciones.map((p, i) => (
          <li key={p.color} className={encima === i ? "activa" : ""}
              onMouseEnter={() => setEncima(i)} onMouseLeave={() => setEncima(null)}>
            <span className="torta-muestra" style={{ background: COLOR_MTG[p.color] }} />
            <span className="torta-nombre">{p.nombre}</span>
            <span className="torta-valor">{Math.round(p.frac * 100)}% · {p.unidades} u.</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* Lista de las cartas más vendidas. */
export function ListaCartas({ cartas }) {
  if (!cartas.length) return <p className="vacio">Sin ventas en el período.</p>;
  return (
    <ol className="ranking">
      {cartas.map((c, i) => (
        <li key={c.nombre}>
          <span className="ranking-pos">{i + 1}</span>
          <span className="ranking-nombre">{c.nombre}</span>
          <span className="ranking-valor"><strong>{c.unidades}</strong> u. · {pesos(c.total)}</span>
        </li>
      ))}
    </ol>
  );
}

/* Barras de las expansiones más vendidas. */
export function BarrasSets({ sets }) {
  if (!sets.length) return <p className="vacio">Sin ventas en el período.</p>;
  const maximo = Math.max(...sets.map((s) => s.unidades), 1);
  return (
    <ul className="barras-h">
      {sets.map((s) => (
        <li key={s.set} title={`${s.set}: ${s.unidades} vendidas · ${pesos(s.total)}`}>
          <span className="barras-h-nombre">{s.set}</span>
          <span className="barras-h-pista">
            <span className="barras-h-barra" style={{ width: `${Math.max(2, (s.unidades / maximo) * 100)}%` }} />
          </span>
          <span className="barras-h-valor">{s.unidades} u. · {pesos(s.total)}</span>
        </li>
      ))}
    </ul>
  );
}

/* Notificaciones de inventario: cambios bruscos de precio y de stock. */
export function AlertasInventario({ alertas, ir }) {
  const hay = alertas.precio.length || alertas.stock.length || alertas.global;
  return (
    <div className={`hoja alertas-inv${hay ? " con-alertas" : ""}`}>
      <div className="lista-cabeza">
        <h2>Alertas de inventario</h2>
        {alertas.precio_total > 0 && <button className="enlace" onClick={() => ir("inventario")}>Revisar precios</button>}
      </div>
      {!hay && <p className="vacio">Sin cambios bruscos de precio ni de stock. Todo en orden.</p>}

      {alertas.global && <p className="alerta-global">⚠ {alertas.global.texto}</p>}

      {alertas.precio.length > 0 && (
        <>
          <h3 className="alertas-sub">Precios a revisar ({alertas.precio_total})</h3>
          <ul className="alertas-mini">
            {alertas.precio.map((i) => {
              const t = textoAlerta(i);
              return (
                <li key={i.id}>
                  <span className="alertas-mini-nombre">{i.nombre} <span className="apagado">· {i.grado}</span></span>
                  <span className="apagado">
                    tu precio {dolares(i.precio_usd)} · {t.detalle}{" "}
                    {t.desde != null && <>{dolares(t.desde)} → </>}{dolares(t.hasta)}
                  </span>
                  <Etiqueta tono={t.tono}>{t.etiqueta}</Etiqueta>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {alertas.stock.length > 0 && (
        <>
          <h3 className="alertas-sub">Stock que cayó fuerte en 7 días</h3>
          <ul className="alertas-mini">
            {alertas.stock.map((i) => (
              <li key={i.id}>
                <span className="alertas-mini-nombre">{i.nombre} <span className="apagado">· {i.grado}</span></span>
                <span className="apagado">{numero(i.antes)} → {numero(i.ahora)} u.</span>
                <Etiqueta tono="estado-rechazada">▼ {i.caida_pct}%</Etiqueta>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
