import { useEffect, useMemo, useState } from "react";

import { pesos } from "../formato.js";
import * as api from "./api.js";
import { Icono, Modal, haceCuanto, useAviso } from "./comunes.jsx";

const NOMBRE_CASA = {
  blue: "Blue", oficial: "Oficial", tarjeta: "Tarjeta", bolsa: "MEP (bolsa)",
  contadoconliqui: "CCL", cripto: "Cripto", mayorista: "Mayorista",
};

function PanelDescuentos({ onCerrar, onCambio }) {
  const [datos, setDatos] = useState(null);
  const [inventario, setInventario] = useState([]);
  const [general, setGeneral] = useState("");
  const [buscar, setBuscar] = useState("");
  const [elegidas, setElegidas] = useState(new Set());
  const [porcentaje, setPorcentaje] = useState(10);
  const [error, setError] = useState("");

  const aplicar = (r) => { setDatos(r); setGeneral(r.general); onCambio(r); };

  useEffect(() => {
    api.descuentos().then(aplicar).catch((e) => setError(e.message));
    api.inventario().then((r) => setInventario(r.items)).catch(() => {});
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const candidatas = useMemo(() => {
    const t = buscar.trim().toLowerCase();
    return inventario.filter((i) => !t || `${i.nombre} ${i.set_nombre} ${i.sku} ${i.grado}`.toLowerCase().includes(t));
  }, [buscar, inventario]);

  async function correr(fn) {
    setError("");
    try { aplicar(await fn()); } catch (e) { setError(e.message); }
  }

  return (
    <Modal titulo="Descuentos" subtitulo="Si una carta tiene los dos, se aplica el mayor." onCerrar={onCerrar} ancho={720}
           pie={<button className="boton primario" onClick={onCerrar}>Listo</button>}>
      {!datos ? <p className="cargando">Cargando…</p> : (
        <div className="formulario">
          <section className="bloque">
            <h3>Descuento general</h3>
            <p className="ayuda">Se aplica a todo el inventario, en la tienda y en el chat.</p>
            <div className="fila-campos al-pie">
              <label className="campo">
                <span>Porcentaje</span>
                <div className="con-sufijo">
                  <input type="number" min="0" max="90" step="0.5" value={general} onChange={(e) => setGeneral(e.target.value)} />
                  <span>%</span>
                </div>
              </label>
              <button className="boton primario" onClick={() => correr(() => api.descuentoGeneral(Number(general || 0)))}>
                Guardar
              </button>
            </div>
          </section>

          <section className="bloque">
            <h3>Descuentos por carta ({datos.cartas.length})</h3>
            {datos.cartas.length === 0 && <p className="ayuda">Ninguna carta tiene descuento propio.</p>}
            <ul className="lista-descuentos">
              {datos.cartas.map((d) => (
                <li key={d.id}>
                  {d.imagen ? <img src={d.imagen} alt="" /> : <span className="mini-sinimg" />}
                  <span>{d.nombre} <span className="apagado">· {d.set_nombre} · {d.grado}</span></span>
                  <strong>−{d.porcentaje}%</strong>
                  <button className="quitar" onClick={() => correr(() => api.quitarDescuento(d.id))} aria-label={`Quitar descuento de ${d.nombre}`}>×</button>
                </li>
              ))}
            </ul>
          </section>

          <section className="bloque">
            <h3>Aplicar descuento a cartas</h3>
            <label className="buscador ancho">
              <Icono nombre="buscar" />
              <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Filtrar el inventario" />
            </label>
            <ul className="lista-elegir">
              {candidatas.map((i) => (
                <li key={i.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={elegidas.has(i.id)}
                      onChange={() => setElegidas((s) => { const n = new Set(s); if (n.has(i.id)) n.delete(i.id); else n.add(i.id); return n; })}
                    />
                    <span>{i.nombre} <span className="apagado">· {i.set_nombre} · {i.grado} · {pesos(i.precio_lista_ars)}</span></span>
                  </label>
                </li>
              ))}
            </ul>
            <div className="fila-campos al-pie">
              <label className="campo">
                <span>Porcentaje</span>
                <div className="con-sufijo">
                  <input type="number" min="1" max="90" value={porcentaje} onChange={(e) => setPorcentaje(e.target.value)} />
                  <span>%</span>
                </div>
              </label>
              <button
                className="boton primario"
                disabled={!elegidas.size}
                onClick={() => correr(async () => {
                  const r = await api.descuentoCartas([...elegidas], Number(porcentaje));
                  setElegidas(new Set());
                  return r;
                })}
              >
                Aplicar a {elegidas.size} {elegidas.size === 1 ? "carta" : "cartas"}
              </button>
            </div>
          </section>
          {error && <p className="error-texto">{error}</p>}
        </div>
      )}
    </Modal>
  );
}

export default function Configuracion() {
  const [conf, setConf] = useState(null);
  const [horarios, setHorarios] = useState(null);
  const [dolar, setDolar] = useState(null);
  const [stockBajo, setStockBajo] = useState(2);
  const [descuentos, setDescuentos] = useState(null);
  const [panel, setPanel] = useState(false);
  const [ocupado, setOcupado] = useState("");
  const [error, setError] = useState("");
  const [avisar, aviso] = useAviso();

  const aplicar = (c) => {
    setConf(c);
    setHorarios(c.horarios);
    setDolar({ modo: c.dolar.modo, casa: c.dolar.casa, valor: c.dolar.valor });
    setStockBajo(c.stock_bajo);
  };

  useEffect(() => {
    api.config().then(aplicar).catch((e) => setError(e.message));
    api.descuentos().then(setDescuentos).catch(() => {});
  }, []);

  async function guardar(parte, datos, mensaje) {
    setOcupado(parte);
    try {
      aplicar(await api.guardarConfig(datos));
      avisar(mensaje);
    } catch (e) {
      avisar(e.message, true);
    } finally {
      setOcupado("");
    }
  }

  if (error) return <p className="hoja error-texto">{error}</p>;
  if (!conf) return <p className="cargando">Cargando…</p>;

  const cambiarDia = (dia, valor) => setHorarios((h) => ({ ...h, [dia]: valor }));

  return (
    <section>
      <div className="cabecera">
        <div>
          <h1>Configuración</h1>
          <p>Personalizá horarios, precios y reglas de gestión.</p>
        </div>
      </div>

      <div className="hoja preferencias">
        <h2>Preferencias generales</h2>
        <p className="apagado">Todo lo que cambies acá lo usa también Urza en el chat, al momento.</p>

        {/* Horarios */}
        <section className="bloque">
          <div className="bloque-cabeza">
            <div>
              <h3><Icono nombre="reloj" /> Horarios de la tienda</h3>
              <p className="ayuda">Los jugadores sólo pueden elegir retirar dentro de estos horarios.</p>
            </div>
          </div>
          <div className="horarios">
            {conf.dias.map(({ clave, nombre }) => {
              const h = horarios[clave];
              return (
                <div key={clave} className={`horario${h ? "" : " cerrado"}`}>
                  <label className="interruptor">
                    <input
                      type="checkbox"
                      checked={Boolean(h)}
                      onChange={(e) => cambiarDia(clave, e.target.checked ? { abre: "10:00", cierra: "20:00" } : null)}
                    />
                    <span className="horario-dia">{nombre}</span>
                  </label>
                  {h ? (
                    <span className="horario-horas">
                      <input type="time" value={h.abre} onChange={(e) => cambiarDia(clave, { ...h, abre: e.target.value })} aria-label={`${nombre} abre`} />
                      <span>a</span>
                      <input type="time" value={h.cierra} onChange={(e) => cambiarDia(clave, { ...h, cierra: e.target.value })} aria-label={`${nombre} cierra`} />
                    </span>
                  ) : <span className="apagado">Cerrado</span>}
                </div>
              );
            })}
          </div>
          <div className="bloque-pie">
            <span className="apagado">Hoy: {conf.horarios_texto}</span>
            <button className="boton primario" disabled={ocupado === "horarios"}
                    onClick={() => guardar("horarios", { horarios }, "Horarios guardados.")}>
              {ocupado === "horarios" ? "Guardando…" : "Guardar horarios"}
            </button>
          </div>
        </section>

        {/* Dólar */}
        <section className="bloque">
          <div className="bloque-cabeza">
            <div>
              <h3>$ Precio del dólar</h3>
              <p className="ayuda">Los precios se cargan en dólares y se venden en pesos con esta cotización.</p>
            </div>
            <div className="dolar-actual">
              <strong>{pesos(conf.dolar.valor)}</strong>
              <span className="apagado chico">
                {conf.dolar.modo === "auto" ? `${NOMBRE_CASA[conf.dolar.casa]} · automático` : "manual"}
                {conf.dolar.actualizado && ` · ${haceCuanto(conf.dolar.actualizado).toLowerCase()}`}
              </span>
            </div>
          </div>
          <div className="fila-campos al-pie">
            <div className="segmentado" role="radiogroup" aria-label="Modo del dólar">
              {[["auto", "Automático"], ["manual", "Manual"]].map(([v, t]) => (
                <button key={v} role="radio" aria-checked={dolar.modo === v}
                        className={dolar.modo === v ? "activo" : ""} onClick={() => setDolar((d) => ({ ...d, modo: v }))}>
                  {t}
                </button>
              ))}
            </div>
            {dolar.modo === "auto" ? (
              <label className="campo">
                <span>Cotización (dolarapi.com, se actualiza cada hora)</span>
                <select value={dolar.casa} onChange={(e) => setDolar((d) => ({ ...d, casa: e.target.value }))}>
                  {conf.casas.map((c) => <option key={c} value={c}>{NOMBRE_CASA[c] || c}</option>)}
                </select>
              </label>
            ) : (
              <label className="campo">
                <span>Valor en pesos</span>
                <input type="number" min="1" step="0.5" value={dolar.valor ?? ""}
                       onChange={(e) => setDolar((d) => ({ ...d, valor: e.target.value }))} />
              </label>
            )}
            <button className="boton primario" disabled={ocupado === "dolar"}
                    onClick={() => guardar("dolar", { dolar: { ...dolar, valor: dolar.valor ? Number(dolar.valor) : null } }, "Dólar guardado. Los precios ya se recalcularon.")}>
              {ocupado === "dolar" ? "Guardando…" : "Guardar"}
            </button>
            {conf.dolar.modo === "auto" && (
              <button className="boton" disabled={ocupado === "refrescar"}
                      onClick={async () => {
                        setOcupado("refrescar");
                        try { aplicar(await api.actualizarDolar()); avisar("Cotización actualizada."); }
                        catch (e) { avisar(e.message, true); }
                        finally { setOcupado(""); }
                      }}>
                {ocupado === "refrescar" ? "Consultando…" : "Actualizar ahora"}
              </button>
            )}
          </div>
        </section>

        {/* Stock bajo */}
        <section className="bloque">
          <div className="bloque-cabeza">
            <div>
              <h3>Aviso de stock bajo</h3>
              <p className="ayuda">Una carta figura con "Stock bajo" cuando le quedan estas unidades o menos.</p>
            </div>
          </div>
          <div className="fila-campos al-pie">
            <label className="campo">
              <span>Unidades</span>
              <input type="number" min="0" value={stockBajo} onChange={(e) => setStockBajo(e.target.value)} />
            </label>
            <button className="boton primario" disabled={ocupado === "stock"}
                    onClick={() => guardar("stock", { stock_bajo: Number(stockBajo) }, "Umbral de stock bajo guardado.")}>
              Guardar
            </button>
          </div>
        </section>

        {/* Descuentos */}
        <section className="bloque">
          <div className="bloque-cabeza">
            <div>
              <h3>% Descuentos</h3>
              <p className="ayuda">
                {descuentos
                  ? `General: ${descuentos.general}% · ${descuentos.cartas.length} ${descuentos.cartas.length === 1 ? "carta" : "cartas"} con descuento propio.`
                  : "Descuento general y por carta."}
              </p>
            </div>
            <button className="boton primario" onClick={() => setPanel(true)}>Gestionar descuentos</button>
          </div>
        </section>
      </div>

      {panel && <PanelDescuentos onCerrar={() => setPanel(false)} onCambio={setDescuentos} />}
      {aviso}
    </section>
  );
}
