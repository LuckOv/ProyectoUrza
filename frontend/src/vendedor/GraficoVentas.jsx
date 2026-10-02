import { useState } from "react";

import { numero, pesos } from "../formato.js";
import { MESES, desdeIso } from "./comunes.jsx";

/* Escala "redonda" para el eje: 0, 5.000, 10.000... según el máximo. */
function escala(maximo) {
  if (maximo <= 0) return { tope: 1, marcas: [0, 1] };
  const potencia = 10 ** Math.floor(Math.log10(maximo));
  const paso = [1, 2, 2.5, 5, 10].map((f) => f * potencia).find((p) => maximo / p <= 4) || potencia * 10;
  const tope = Math.ceil(maximo / paso) * paso;
  const marcas = [];
  for (let v = 0; v <= tope + paso / 2; v += paso) marcas.push(v);
  return { tope, marcas };
}

const compacto = (v) => (v >= 1_000_000 ? `$ ${numero(v / 1_000_000)} M` : v >= 1000 ? `$ ${numero(v / 1000)} mil` : pesos(v));

function PorDia({ dias }) {
  const [encima, setEncima] = useState(null);
  const { tope, marcas } = escala(Math.max(...dias.map((d) => d.total)));

  return (
    <div className="grafico">
      <div className="grafico-eje" aria-hidden="true">
        {[...marcas].reverse().map((m) => <span key={m}>{compacto(m)}</span>)}
      </div>
      <div className="grafico-area">
        {marcas.map((m) => (
          <div key={m} className="grafico-linea" style={{ bottom: `${(m / tope) * 100}%` }} />
        ))}
        <div className="grafico-columnas" role="list">
          {dias.map((d, i) => {
            const fecha = desdeIso(d.fecha);
            const etiqueta = `${fecha.getDate()} ${MESES[fecha.getMonth()].slice(0, 3)}`;
            return (
              <div
                key={d.fecha}
                className={`grafico-slot${encima === i ? " activo" : ""}`}
                role="listitem"
                tabIndex={0}
                aria-label={`${etiqueta}: ${pesos(d.total)}, ${d.unidades} cartas`}
                onMouseEnter={() => setEncima(i)}
                onMouseLeave={() => setEncima(null)}
                onFocus={() => setEncima(i)}
                onBlur={() => setEncima(null)}
              >
                {d.total > 0 && <div className="grafico-barra" style={{ height: `${(d.total / tope) * 100}%` }} />}
                {encima === i && (
                  <div className={`grafico-tip${i > dias.length - 6 ? " izquierda" : ""}`} role="tooltip">
                    <strong>{etiqueta}</strong>
                    <span>{pesos(d.total)}</span>
                    <span className="apagado">{d.unidades} {d.unidades === 1 ? "carta" : "cartas"} · {d.pedidos} {d.pedidos === 1 ? "pedido" : "pedidos"}</span>
                  </div>
                )}
                {(i % 5 === 0 || i === dias.length - 1) && <span className="grafico-x">{etiqueta}</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function PorCarta({ cartas }) {
  const maximo = Math.max(...cartas.map((c) => c.unidades), 1);
  return (
    <ul className="barras-h">
      {cartas.map((c) => (
        <li key={c.nombre} title={`${c.nombre}: ${c.unidades} vendidas · ${pesos(c.total)}`}>
          <span className="barras-h-nombre">{c.nombre}</span>
          <span className="barras-h-pista">
            <span className="barras-h-barra" style={{ width: `${Math.max(2, (c.unidades / maximo) * 100)}%` }} />
          </span>
          <span className="barras-h-valor">{c.unidades} u. · {pesos(c.total)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function GraficoVentas({ dias, cartas }) {
  const [vista, setVista] = useState("dia");
  const [tabla, setTabla] = useState(false);
  const total = dias.reduce((s, d) => s + d.total, 0);
  const unidades = dias.reduce((s, d) => s + d.unidades, 0);
  const vacio = total === 0;

  return (
    <div className="hoja ventas-mes">
      <div className="lista-cabeza">
        <div>
          <h2>Ventas del último mes</h2>
          <p className="apagado chico">
            {vacio ? "Todavía no hay ventas en los últimos 30 días." : `${pesos(total)} · ${numero(unidades)} cartas vendidas`}
          </p>
        </div>
        <div className="ventas-controles">
          <div className="segmentado" role="radiogroup" aria-label="Agrupar ventas">
            {[["dia", "Por día"], ["carta", "Por carta"]].map(([v, t]) => (
              <button key={v} role="radio" aria-checked={vista === v} className={vista === v ? "activo" : ""}
                      onClick={() => setVista(v)}>{t}</button>
            ))}
          </div>
          <button className="enlace chico" onClick={() => setTabla((t) => !t)}>
            {tabla ? "Ver gráfico" : "Ver como tabla"}
          </button>
        </div>
      </div>

      {vacio ? (
        <p className="vacio">Cuando marques pedidos como entregados, las ventas aparecen acá.</p>
      ) : tabla ? (
        <table className="tabla-chica">
          <thead>
            {vista === "dia"
              ? <tr><th>Día</th><th className="num">Pedidos</th><th className="num">Cartas</th><th className="num">Total</th></tr>
              : <tr><th>Carta</th><th className="num">Vendidas</th><th className="num">Total</th></tr>}
          </thead>
          <tbody>
            {vista === "dia"
              ? dias.filter((d) => d.total > 0).map((d) => (
                <tr key={d.fecha}><td>{d.fecha.split("-").reverse().join("/")}</td><td className="num">{d.pedidos}</td>
                  <td className="num">{d.unidades}</td><td className="num">{pesos(d.total)}</td></tr>))
              : cartas.map((c) => (
                <tr key={c.nombre}><td>{c.nombre}</td><td className="num">{c.unidades}</td><td className="num">{pesos(c.total)}</td></tr>))}
          </tbody>
        </table>
      ) : vista === "dia" ? <PorDia dias={dias} /> : <PorCarta cartas={cartas} />}
    </div>
  );
}
