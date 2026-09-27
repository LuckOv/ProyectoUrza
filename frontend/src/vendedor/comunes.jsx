import { useEffect, useState } from "react";

/* Piezas que comparten todas las pestañas del panel. */

// --- fechas ------------------------------------------------------------------

export const DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
export const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
  "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
export const CLAVES_DIA = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"];

/** Date → "2026-09-27" en hora local (toISOString usaría UTC y cambiaría el día de noche). */
export function iso(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function desdeIso(s) {
  const [a, m, d] = s.slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d);
}

/** "2026-09-27" → "27 sep" */
export function fechaCorta(s) {
  const d = desdeIso(s);
  return `${d.getDate()} ${MESES[d.getMonth()].slice(0, 3)}`;
}

/** "2026-09-27T18:56:13-03:00" → "27 sep · 18:56" */
export function fechaHora(s) {
  return `${fechaCorta(s)} · ${s.slice(11, 16)}`;
}

/** Hace cuánto pasó algo, en criollo. */
export function haceCuanto(s) {
  const seg = (Date.now() - new Date(s).getTime()) / 1000;
  if (seg < 60) return "Recién";
  if (seg < 3600) return `Hace ${Math.floor(seg / 60)} min`;
  if (seg < 86400) return `Hace ${Math.floor(seg / 3600)} h`;
  if (seg < 172800) return "Ayer";
  return fechaCorta(s);
}

// --- etiquetas ---------------------------------------------------------------

export const ESTADOS = {
  pendiente: "Compra pendiente",
  realizada: "Compra realizada",
  rechazada: "Compra rechazada",
};

export function Etiqueta({ tono, children, title }) {
  return <span className={`etiqueta ${tono}`} title={title}>{children}</span>;
}

export function EtiquetaEstado({ estado, corta = false }) {
  const texto = corta ? estado[0].toUpperCase() + estado.slice(1) : ESTADOS[estado];
  return <Etiqueta tono={`estado-${estado}`}>{texto}</Etiqueta>;
}

export function EtiquetaStock({ estado }) {
  const textos = { ok: "En stock", bajo: "Stock bajo", sin: "Sin stock" };
  return <Etiqueta tono={`stock-${estado}`}>{textos[estado]}</Etiqueta>;
}

// --- modal -------------------------------------------------------------------

export function Modal({ titulo, subtitulo, onCerrar, children, pie, ancho = 560 }) {
  useEffect(() => {
    const tecla = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onCerrar]);

  return (
    <div className="velo" onMouseDown={onCerrar}>
      <div
        className="modal"
        style={{ width: `min(${ancho}px, 94vw)` }}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
      >
        <header className="modal-cabeza">
          <div>
            <h2>{titulo}</h2>
            {subtitulo && <p>{subtitulo}</p>}
          </div>
          <button className="modal-cerrar" onClick={onCerrar} aria-label="Cerrar">×</button>
        </header>
        <div className="modal-cuerpo">{children}</div>
        {pie && <footer className="modal-pie">{pie}</footer>}
      </div>
    </div>
  );
}

/** Confirmación propia (los confirm() del navegador bloquean la página). */
export function Confirmar({ titulo, mensaje, accion = "Confirmar", peligro, onSi, onNo }) {
  const [ocupado, setOcupado] = useState(false);
  return (
    <Modal
      titulo={titulo}
      onCerrar={onNo}
      ancho={420}
      pie={
        <>
          <button className="boton" onClick={onNo}>Cancelar</button>
          <button
            className={`boton ${peligro ? "peligro" : "primario"}`}
            disabled={ocupado}
            onClick={async () => { setOcupado(true); try { await onSi(); } finally { setOcupado(false); } }}
          >
            {ocupado ? "Un momento…" : accion}
          </button>
        </>
      }
    >
      <p className="texto">{mensaje}</p>
    </Modal>
  );
}

// --- aviso flotante ----------------------------------------------------------

export function useAviso() {
  const [aviso, setAviso] = useState(null);
  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 3800);
    return () => clearTimeout(t);
  }, [aviso]);
  const avisar = (texto, error = false) => setAviso({ texto, error, n: Date.now() });
  const nodo = aviso && (
    <p key={aviso.n} className={`aviso${aviso.error ? " error" : ""}`} role="status">{aviso.texto}</p>
  );
  return [avisar, nodo];
}

// --- íconos ------------------------------------------------------------------

const TRAZOS = {
  buscar: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>,
  filtro: <path d="M4 5h16l-6.2 7.4V19l-3.6-1.8v-4.8Z" />,
  mas: <path d="M12 5v14M5 12h14" />,
  editar: <><path d="M4 20h4L19 9l-4-4L4 16Z" /><path d="m13.5 6.5 4 4" /></>,
  borrar: <><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></>,
  calendario: <><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>,
  descargar: <><path d="M12 4v11M7 10l5 5 5-5" /><path d="M5 20h14" /></>,
  izquierda: <path d="m15 6-6 6 6 6" />,
  derecha: <path d="m9 6 6 6-6 6" />,
  salir: <><path d="M15 4h4v16h-4" /><path d="M10 8l-4 4 4 4M6 12h10" /></>,
  tienda: <><path d="M4 9h16l-1-4H5Z" /><path d="M5 9v11h14V9M10 20v-6h4v6" /></>,
  reloj: <><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>,
  check: <path d="m5 12 5 5 9-10" />,
};

export function Icono({ nombre, tam = 16 }) {
  return (
    <svg width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {TRAZOS[nombre]}
    </svg>
  );
}
