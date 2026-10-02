import { useEffect, useState } from "react";

import { dolares, numero, pesos } from "../formato.js";
import * as api from "./api.js";
import { EtiquetaEstado, fechaCorta } from "./comunes.jsx";
import GraficoVentas from "./GraficoVentas.jsx";

function Tile({ titulo, valor, nota, tono }) {
  return (
    <div className="hoja tile">
      <p className="tile-titulo">{titulo}</p>
      <p className="tile-valor">{valor}</p>
      {nota && <p className={`tile-nota ${tono || ""}`}>{nota}</p>}
    </div>
  );
}

/* Medidor horizontal: el número va escrito al lado, la barra sólo acompaña. */
function Medidor({ etiqueta, valor, maximo, tono, detalle }) {
  const ancho = maximo > 0 ? Math.max(2, (valor / maximo) * 100) : 0;
  return (
    <div className="medidor" title={detalle}>
      <div className="medidor-texto">
        <span>{etiqueta}</span>
        <strong>{numero(valor)}</strong>
      </div>
      <div className="medidor-pista" role="meter" aria-valuenow={valor} aria-valuemin={0} aria-valuemax={maximo} aria-label={etiqueta}>
        <div className={`medidor-barra ${tono}`} style={{ width: `${valor ? ancho : 0}%` }} />
      </div>
    </div>
  );
}

export default function Dashboard({ ir }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="hoja error-texto">{error}</p>;
  if (!d) return <p className="cargando">Cargando…</p>;

  const maxStock = Math.max(d.stock.disponible, d.stock.reservado, d.stock.vendido_30, 1);
  const std = d.standard;
  const cobertura = std.total ? (std.tienda / std.total) * 100 : null;

  return (
    <section>
      <div className="cabecera">
        <div>
          <h1>Dashboard</h1>
          <p>Vista general del negocio y del estado de tu colección. Dólar usado: {pesos(d.dolar)}.</p>
        </div>
      </div>

      <div className="tiles">
        <Tile
          titulo="Total de cartas en inventario"
          valor={numero(d.unidades)}
          nota={`${d.cartas_distintas} variantes · +${numero(d.entradas_mes)} este mes`}
          tono="bien"
        />
        <Tile
          titulo="Valor estimado del inventario"
          valor={pesos(d.valor_ars)}
          nota={dolares(d.valor_usd)}
        />
        <Tile
          titulo="Pedidos abiertos"
          valor={numero(d.pedidos_abiertos)}
          nota={d.retiros_hoy ? `${d.retiros_hoy} retiran hoy` : "Ninguno retira hoy"}
          tono={d.retiros_hoy ? "bien" : ""}
        />
        <Tile
          titulo="Cartas sin stock"
          valor={numero(d.sin_stock)}
          nota={d.sin_stock || d.stock_bajo ? `Requiere atención · ${d.stock_bajo} con stock bajo` : "Todo en orden"}
          tono={d.sin_stock || d.stock_bajo ? "mal" : "bien"}
        />
      </div>

      <GraficoVentas dias={d.ventas_dias || []} cartas={d.ventas_cartas || []} />

      <div className="dos-columnas">
        <div className="hoja lista-hoja">
          <div className="lista-cabeza">
            <h2>Próximos retiros</h2>
            <button className="enlace" onClick={() => ir("pedidos")}>Ver calendario</button>
          </div>
          {d.proximos.length === 0 && <p className="vacio">No hay pedidos pendientes.</p>}
          <ul className="proximos">
            {d.proximos.map((p) => (
              <li key={p.id}>
                <span className="proximos-fecha">{fechaCorta(p.fecha_retiro)} · {p.hora_retiro}</span>
                <span>#{p.id} {p.nombre} {p.apellido}</span>
                <EtiquetaEstado estado={p.estado} corta />
              </li>
            ))}
          </ul>
        </div>
        <div className="columna">
          <div className="hoja">
            <h2>Resumen del stock</h2>
            <Medidor etiqueta="Disponible" valor={d.stock.disponible} maximo={maxStock} tono="verde"
                     detalle="Unidades en el inventario, listas para vender" />
            <Medidor etiqueta="Reservado" valor={d.stock.reservado} maximo={maxStock} tono="ambar"
                     detalle="Unidades en pedidos pendientes de retiro" />
            <Medidor etiqueta="Vendido (30 días)" valor={d.stock.vendido_30} maximo={maxStock} tono="purpura"
                     detalle={`Unidades entregadas en los últimos 30 días · ${pesos(d.ventas_30)}`} />
            <p className="apagado chico">Ventas de los últimos 30 días: {pesos(d.ventas_30)}</p>
          </div>

        </div>
      </div>

      <div className="hoja cobertura">
        <div className="lista-cabeza">
          <h2>Cobertura del pool de Standard</h2>
          <span className="cobertura-numero">
            {numero(std.tienda)}{std.total ? ` / ${numero(std.total)}` : ""}
            {cobertura != null && <em> ({cobertura.toFixed(1).replace(".", ",")}%)</em>}
          </span>
        </div>
        <div className="medidor-pista alta" role="meter" aria-valuenow={std.tienda} aria-valuemin={0}
             aria-valuemax={std.total || std.tienda} aria-label="Cobertura del pool de Standard">
          <div className="medidor-barra verde" style={{ width: `${cobertura != null ? Math.max(cobertura, std.tienda ? 1 : 0) : 0}%` }} />
        </div>
        <p className="apagado chico">
          Cartas distintas legales en Standard que tenés con stock
          {std.total ? ", sobre el total de Scryfall." : ". (No pude traer el total de Scryfall.)"}
        </p>
      </div>
    </section>
  );
}
