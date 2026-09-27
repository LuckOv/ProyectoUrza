/* Formatos compartidos por la tienda y el panel del vendedor. */

const PESOS = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });
const DOLARES = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** 12345.6 → "$ 12.346" */
export const pesos = (v) => (v === null || v === undefined ? "sin precio" : `$ ${PESOS.format(v)}`);

/** 4.1 → "US$ 4,10" */
export const dolares = (v) => (v === null || v === undefined ? "—" : `US$ ${DOLARES.format(v)}`);

export const numero = (v) => PESOS.format(v || 0);
