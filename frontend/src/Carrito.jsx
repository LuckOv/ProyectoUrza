/* Cajón del carrito. Se despliega desde la derecha y lista lo que hay
   adentro, con el total abajo. */
export default function Carrito({ items, onQuitar, onVaciar, onCerrar }) {
  const total = items.reduce((suma, i) => suma + (i.precio || 0) * i.cantidad, 0);
  const unidades = items.reduce((suma, i) => suma + i.cantidad, 0);

  return (
    <div className="velo" onClick={onCerrar}>
      <aside className="cajon" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>Tu carrito</h2>
          <button className="cajon-cerrar" onClick={onCerrar} aria-label="Cerrar carrito">×</button>
        </header>

        {items.length === 0 ? (
          <p className="cajon-vacio">Todavía no agregaste ninguna carta.</p>
        ) : (
          <>
            <ul className="cajon-lista">
              {items.map((i) => (
                <li key={i.id}>
                  {i.imagen
                    ? <img src={i.imagen} alt="" />
                    : <div className="cajon-sinimagen" />}
                  <div className="cajon-datos">
                    <p className="cajon-nombre">{i.nombre}</p>
                    {i.edicion && <p className="cajon-edicion">{i.edicion}</p>}
                    <p className="cajon-precio">
                      {i.cantidad} × {i.precio ? `€${i.precio.toFixed(2)}` : "sin precio"}
                    </p>
                  </div>
                  <button onClick={() => onQuitar(i.id)} aria-label={`Quitar ${i.nombre}`}>×</button>
                </li>
              ))}
            </ul>

            <footer>
              <p className="cajon-total">
                <span>{unidades} {unidades === 1 ? "carta" : "cartas"}</span>
                <strong>€{total.toFixed(2)}</strong>
              </p>
              <button className="cajon-vaciar" onClick={onVaciar}>Vaciar carrito</button>
            </footer>
          </>
        )}
      </aside>
    </div>
  );
}
