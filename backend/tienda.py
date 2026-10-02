"""Carrito y pedidos de URZA.

No hay cuentas de usuario. El carrito se ata a la conversación (el thread_id
que el frontend genera por pestaña). Cuando el jugador quiere cerrar la
compra, el propio chat le pide nombre, apellido y día y hora de retiro, y con
eso se registra el pedido para que el vendedor lo prepare.

Estados de un pedido:
    pendiente  → confirmado por el jugador, las cartas quedan reservadas
                 (ya se descontaron del stock).
    realizada  → el jugador retiró y pagó.
    rechazada  → se canceló: las cartas vuelven al stock.

El vendedor puede mover un pedido entre estados desde su panel; el stock se
acomoda solo según el estado.
"""

from datetime import date, datetime, timedelta

import base
import inventario

ESTADOS = ["pendiente", "realizada", "rechazada"]
ETIQUETA_ESTADO = {"pendiente": "pendiente", "realizada": "realizada", "rechazada": "rechazada"}
RETIENEN_STOCK = {"pendiente", "realizada"}   # en estos estados las cartas no están en el stock
DIAS_MAXIMOS = 60                              # hasta cuántos días adelante se puede reservar


def _recortar(texto: str, largo: int = 90) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def _fecha_corta(iso: str) -> str:
    """'2026-09-29' → '29/09'."""
    return f"{iso[8:10]}/{iso[5:7]}"


# --- carrito -----------------------------------------------------------------

def ver_carrito(thread_id: str) -> list:
    with base.conectar() as con:
        filas = con.execute(
            """SELECT c.id, c.inventario_id, c.cantidad, i.cantidad AS disponible
                 FROM carrito c JOIN inventario i ON i.id = c.inventario_id
                WHERE c.thread_id = ? ORDER BY c.agregado""",
            (thread_id,),
        ).fetchall()
    items = []
    for f in filas:
        v = inventario.obtener(f["inventario_id"])
        items.append({
            "id": f["id"],
            "inventario_id": f["inventario_id"],
            "nombre": v["nombre"],
            "edicion": v["set_nombre"],
            "grado": v["grado"],
            "imagen": v["imagen"],
            "precio": v["precio_ars"],       # precio actual en pesos, con descuento
            "cantidad": f["cantidad"],
            "disponible": f["disponible"],
        })
    return items


def total_de(items: list) -> float:
    return round(sum((i["precio"] or 0) * i["cantidad"] for i in items), 2)


def agregar(thread_id: str, inventario_id: int, cantidad: int = 1) -> list:
    """Suma una variante del inventario al carrito respetando el stock real.

    El tope lo pone el inventario, no el botón ni el agente. Levanta
    ValueError con un mensaje listo para mostrar si no se puede.
    """
    if cantidad < 1:
        raise ValueError("La cantidad tiene que ser al menos 1.")
    variante = inventario.obtener(inventario_id)
    if not variante:
        raise ValueError("Esa carta no figura en el inventario de la tienda.")
    if variante["cantidad"] <= 0:
        raise ValueError(f"No queda stock de '{variante['nombre']}' ({variante['set_nombre']}, {variante['grado']}).")
    if variante["precio_ars"] is None:
        raise ValueError(f"'{variante['nombre']}' todavía no tiene precio cargado; consultalo con el vendedor.")

    with base.conectar() as con:
        fila = con.execute(
            "SELECT id, cantidad FROM carrito WHERE thread_id = ? AND inventario_id = ?",
            (thread_id, inventario_id),
        ).fetchone()
        ya_lleva = fila["cantidad"] if fila else 0
        if ya_lleva + cantidad > variante["cantidad"]:
            raise ValueError(
                f"Sólo quedan {variante['cantidad']} de '{variante['nombre']}' "
                f"({variante['grado']}) y ya tenés {ya_lleva} en el carrito."
            )
        if fila:
            con.execute("UPDATE carrito SET cantidad = ? WHERE id = ?", (ya_lleva + cantidad, fila["id"]))
        else:
            con.execute(
                "INSERT INTO carrito (thread_id, inventario_id, cantidad, agregado) VALUES (?, ?, ?, ?)",
                (thread_id, inventario_id, cantidad, base.ahora_iso()),
            )
    return ver_carrito(thread_id)


def quitar(thread_id: str, item_id: int) -> list:
    with base.conectar() as con:
        con.execute("DELETE FROM carrito WHERE id = ? AND thread_id = ?", (item_id, thread_id))
    return ver_carrito(thread_id)


def quitar_por_nombre(thread_id: str, nombre: str) -> bool:
    """Saca una carta del carrito por nombre (todas sus variantes). Devuelve si había algo."""
    buscado = inventario._plano(nombre)
    borrar = [i["id"] for i in ver_carrito(thread_id) if inventario._plano(i["nombre"]) == buscado]
    with base.conectar() as con:
        for item_id in borrar:
            con.execute("DELETE FROM carrito WHERE id = ?", (item_id,))
    return bool(borrar)


def vaciar(thread_id: str) -> list:
    with base.conectar() as con:
        con.execute("DELETE FROM carrito WHERE thread_id = ?", (thread_id,))
    return []


# --- horario de retiro -------------------------------------------------------

def _parsear(fecha: str, hora: str):
    try:
        d = date.fromisoformat(str(fecha).strip())
    except ValueError:
        raise ValueError(f"La fecha '{fecha}' no es válida (formato AAAA-MM-DD).")
    try:
        h = datetime.strptime(str(hora).strip(), "%H:%M").time()
    except ValueError:
        raise ValueError(f"La hora '{hora}' no es válida (formato HH:MM).")
    return d, h


def validar_retiro(fecha: str, hora: str) -> tuple:
    """Controla que el retiro caiga en un día y horario en que la tienda abre.

    Devuelve (fecha 'AAAA-MM-DD', hora 'HH:MM'). Levanta ValueError con un
    mensaje que el agente le puede transmitir al jugador tal cual.
    """
    d, h = _parsear(fecha, hora)
    ahora = base.ahora()
    hoy = ahora.date()

    if d < hoy or (d == hoy and h <= ahora.time()):
        raise ValueError("Ese día y horario ya pasaron. Elegí uno a partir de ahora.")
    if d > hoy + timedelta(days=DIAS_MAXIMOS):
        raise ValueError(f"Sólo se pueden reservar retiros hasta {DIAS_MAXIMOS} días adelante.")

    dia = base.DIAS[d.weekday()]
    horario = base.config("horarios").get(dia)
    if not horario:
        raise ValueError(
            f"El {base.NOMBRE_DIA[dia]} la tienda está cerrada. Horarios: {base.horarios_texto()}."
        )
    abre = datetime.strptime(horario["abre"], "%H:%M").time()
    cierra = datetime.strptime(horario["cierra"], "%H:%M").time()
    if not (abre <= h < cierra):
        raise ValueError(
            f"El {base.NOMBRE_DIA[dia]} la tienda abre de {horario['abre']} a {horario['cierra']}. "
            "Elegí un horario dentro de ese rango."
        )
    return d.isoformat(), h.strftime("%H:%M")


# --- pedidos -----------------------------------------------------------------

def _crear_pedido(con, lineas: list, nombre: str, apellido: str, fecha: str, hora: str,
                  origen: str, thread_id: str | None = None, comentario: str = "") -> int:
    """Inserta el pedido y reserva el stock, todo en la transacción `con`.

    `lineas` = [{"inventario_id", "cantidad"}]. Si alguna carta no alcanza,
    levanta ValueError y la transacción entera se deshace.
    """
    detalle = []
    for linea in lineas:
        v = inventario.obtener(linea["inventario_id"])
        if not v:
            raise ValueError("Una de las cartas ya no está en el inventario.")
        if v["cantidad"] < linea["cantidad"]:
            raise ValueError(
                f"Ya no alcanza el stock de '{v['nombre']}' ({v['grado']}): "
                f"quedan {v['cantidad']}, pediste {linea['cantidad']}."
            )
        detalle.append((v, linea["cantidad"]))

    total = round(sum((v["precio_ars"] or 0) * c for v, c in detalle), 2)
    cur = con.execute(
        """INSERT INTO pedidos (thread_id, nombre, apellido, fecha_retiro, hora_retiro, total,
                                estado, comentario, origen, creado, actualizado)
           VALUES (?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?, ?)""",
        (thread_id, nombre, apellido, fecha, hora, total, comentario, origen,
         base.ahora_iso(), base.ahora_iso()),
    )
    pedido_id = cur.lastrowid

    for v, cant in detalle:
        con.execute(
            """INSERT INTO pedido_items (pedido_id, inventario_id, nombre, set_nombre, grado, precio, cantidad)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pedido_id, v["id"], v["nombre"], v["set_nombre"], v["grado"], v["precio_ars"], cant),
        )
        inventario.mover_stock(con, v["id"], -cant)

    unidades = sum(c for _, c in detalle)
    base.registrar_movimiento(
        "reserva",
        f"Pedido #{pedido_id} confirmado por el chat" if origen == "chat" else f"Pedido #{pedido_id} cargado a mano",
        f"{nombre} {apellido} · {unidades} {'carta' if unidades == 1 else 'cartas'}",
        -unidades, pedido_id, con=con,
    )
    return pedido_id


def confirmar_pedido(thread_id: str, nombre: str, apellido: str, fecha_retiro: str, hora_retiro: str) -> dict:
    """Convierte el carrito de la charla en un pedido para retirar en el local."""
    nombre, apellido = (nombre or "").strip(), (apellido or "").strip()
    if not nombre or not apellido:
        raise ValueError("Falta el nombre y apellido de quien retira.")
    fecha, hora = validar_retiro(fecha_retiro, hora_retiro)

    items = ver_carrito(thread_id)
    if not items:
        raise ValueError("El carrito está vacío: no hay nada para confirmar.")

    with base.conectar() as con:
        pedido_id = _crear_pedido(
            con, [{"inventario_id": i["inventario_id"], "cantidad": i["cantidad"]} for i in items],
            nombre, apellido, fecha, hora, "chat", thread_id,
        )
        con.execute("DELETE FROM carrito WHERE thread_id = ?", (thread_id,))
    return obtener_pedido(pedido_id)


def crear_pedido_manual(nombre: str, apellido: str, fecha_retiro: str, hora_retiro: str,
                        lineas: list, comentario: str = "") -> dict:
    """Pedido cargado por el vendedor (por ejemplo, alguien que llamó por teléfono).

    No se valida contra el horario de la tienda: el vendedor sabe lo que acordó.
    """
    nombre, apellido = (nombre or "").strip(), (apellido or "").strip()
    if not nombre or not apellido:
        raise ValueError("Falta el nombre y apellido.")
    d, h = _parsear(fecha_retiro, hora_retiro)
    lineas = [l for l in lineas if int(l.get("cantidad") or 0) > 0]
    if not lineas:
        raise ValueError("El pedido tiene que tener al menos una carta.")

    with base.conectar() as con:
        pedido_id = _crear_pedido(
            con, lineas, nombre, apellido, d.isoformat(), h.strftime("%H:%M"),
            "vendedor", None, (comentario or "").strip(),
        )
    return obtener_pedido(pedido_id)


def _con_items(con, pedidos) -> list:
    resultado = []
    for p in pedidos:
        items = con.execute(
            "SELECT inventario_id, nombre, set_nombre, grado, precio, cantidad FROM pedido_items WHERE pedido_id = ?",
            (p["id"],),
        ).fetchall()
        d = dict(p)
        d["items"] = [dict(i) for i in items]
        d["unidades"] = sum(i["cantidad"] for i in items)
        resultado.append(d)
    return resultado


def obtener_pedido(pedido_id: int):
    with base.conectar() as con:
        p = con.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        return _con_items(con, [p])[0] if p else None


def listar_pedidos(desde: str | None = None, hasta: str | None = None,
                   estado: str | None = None, q: str | None = None,
                   por: str = "retiro") -> list:
    """Pedidos filtrados. `desde`/`hasta` (AAAA-MM-DD) se aplican a la fecha de
    retiro (por="retiro") o a la fecha en que se hizo el pedido (por="pedido")."""
    campo = "fecha_retiro" if por == "retiro" else "substr(creado, 1, 10)"
    sql, params = "SELECT * FROM pedidos WHERE 1=1", []
    if desde:
        sql += f" AND {campo} >= ?"
        params.append(desde)
    if hasta:
        sql += f" AND {campo} <= ?"
        params.append(hasta)
    if estado:
        sql += " AND estado = ?"
        params.append(estado)
    sql += " ORDER BY fecha_retiro, hora_retiro, id"

    with base.conectar() as con:
        pedidos = _con_items(con, con.execute(sql, params).fetchall())

    if q:
        buscado = inventario._plano(q.lstrip("#"))
        pedidos = [
            p for p in pedidos
            if buscado in inventario._plano(
                f"{p['id']} {p['nombre']} {p['apellido']} {p['comentario']} "
                + " ".join(i["nombre"] for i in p["items"])
            )
        ]
    return pedidos


def actualizar_pedido(pedido_id: int, estado: str | None = None, comentario: str | None = None,
                      fecha_retiro: str | None = None, hora_retiro: str | None = None) -> dict:
    """Cambia estado, comentario u horario de un pedido, acomodando el stock.

    Pasar a 'rechazada' devuelve las cartas al stock; volver de 'rechazada'
    a otro estado las reserva de nuevo (si todavía hay).
    """
    actual = obtener_pedido(pedido_id)
    if not actual:
        raise ValueError(f"No existe el pedido #{pedido_id}.")
    if estado is not None and estado not in ESTADOS:
        raise ValueError(f"Estado inválido. Opciones: {', '.join(ESTADOS)}.")

    quien = f"{actual['nombre']} {actual['apellido']}"
    with base.conectar() as con:
        # Cada cambio queda en el registro de actividad (Configuración), con
        # el antes y el después, aunque no mueva stock.
        if estado and estado != actual["estado"]:
            antes = actual["estado"] in RETIENEN_STOCK
            despues = estado in RETIENEN_STOCK
            nota, unidades = "", 0
            if antes and not despues:
                for i in actual["items"]:
                    if i["inventario_id"]:
                        inventario.mover_stock(con, i["inventario_id"], i["cantidad"])
                nota, unidades = " · las cartas volvieron al stock", actual["unidades"]
            elif despues and not antes:
                for i in actual["items"]:
                    if not i["inventario_id"] or not inventario.mover_stock(con, i["inventario_id"], -i["cantidad"]):
                        raise ValueError(
                            f"No hay stock suficiente de '{i['nombre']}' para reactivar el pedido."
                        )
                nota, unidades = " · las cartas se reservaron de nuevo", -actual["unidades"]
            tipo = {"realizada": "venta", "rechazada": "devolucion"}.get(estado, "estado")
            base.registrar_movimiento(
                tipo, f"Pedido #{pedido_id}: {ETIQUETA_ESTADO[actual['estado']]} → {ETIQUETA_ESTADO[estado]}",
                f"{quien}{nota}", unidades, pedido_id, con=con,
            )
            con.execute("UPDATE pedidos SET estado = ? WHERE id = ?", (estado, pedido_id))

        if comentario is not None and comentario.strip() != (actual["comentario"] or "").strip():
            texto = comentario.strip()
            con.execute("UPDATE pedidos SET comentario = ? WHERE id = ?", (texto, pedido_id))
            if not texto:
                titulo, detalle = f"Comentario borrado en el pedido #{pedido_id}", quien
            elif not (actual["comentario"] or "").strip():
                titulo, detalle = f"Comentario agregado al pedido #{pedido_id}", f"“{_recortar(texto)}”"
            else:
                titulo, detalle = f"Comentario editado en el pedido #{pedido_id}", f"“{_recortar(texto)}”"
            base.registrar_movimiento("comentario", titulo, detalle, 0, pedido_id, con=con)

        if fecha_retiro is not None or hora_retiro is not None:
            d, h = _parsear(fecha_retiro or actual["fecha_retiro"], hora_retiro or actual["hora_retiro"])
            nueva_fecha, nueva_hora = d.isoformat(), h.strftime("%H:%M")
            if (nueva_fecha, nueva_hora) != (actual["fecha_retiro"], actual["hora_retiro"]):
                con.execute(
                    "UPDATE pedidos SET fecha_retiro = ?, hora_retiro = ? WHERE id = ?",
                    (nueva_fecha, nueva_hora, pedido_id),
                )
                base.registrar_movimiento(
                    "pedido", f"Pedido #{pedido_id}: retiro reprogramado",
                    f"{quien} · {_fecha_corta(actual['fecha_retiro'])} {actual['hora_retiro']} → "
                    f"{_fecha_corta(nueva_fecha)} {nueva_hora}",
                    0, pedido_id, con=con,
                )

        con.execute("UPDATE pedidos SET actualizado = ? WHERE id = ?", (base.ahora_iso(), pedido_id))
    return obtener_pedido(pedido_id)


def borrar_pedidos(ids: list) -> int:
    """Saca pedidos del sistema. Si estaban pendientes, las cartas vuelven al stock."""
    borrados = 0
    for pedido_id in ids:
        p = obtener_pedido(pedido_id)
        if not p:
            continue
        with base.conectar() as con:
            if p["estado"] == "pendiente":
                for i in p["items"]:
                    if i["inventario_id"]:
                        inventario.mover_stock(con, i["inventario_id"], i["cantidad"])
            con.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
            base.registrar_movimiento(
                "baja", f"Pedido #{pedido_id} eliminado",
                f"{p['nombre']} {p['apellido']} · estaba {p['estado']}",
                p["unidades"] if p["estado"] == "pendiente" else 0, con=con,
            )
        borrados += 1
    return borrados
