"""Propuestas: cartas que un cliente le ofrece a la tienda desde el chat.

El cliente elige la carta de la lista de Scryfall (así no hay dudas de cuál
es), dice el grado, la cantidad y a cuánto la vende, y deja nombre, apellido
y mail, que son obligatorios. El vendedor las ve en la pestaña Propuestas,
las acepta o rechaza, y si la compra la puede cargar directo al inventario.
"""

import re

import base
import cartas
import inventario

ESTADOS = ["nueva", "en_revision", "aceptada", "rechazada"]
MONEDAS = ["ARS", "USD"]


# --- detectar que el jugador quiere VENDER --------------------------------------
#
# El formulario de propuesta lo abre el agente con `iniciar_propuesta`, pero el
# modelo a veces no la llama. Por eso api.py también lo detecta acá con reglas
# fijas: si el jugador quiere venderle una carta a la tienda, el formulario
# aparece sí o sí. Ojo con "¿venden X?" / "¿vendés X?": eso es el jugador
# COMPRANDO, no vendiendo, y no tiene que disparar nada.

_VENDER = re.compile(
    r"\b(vendo|vend[eé]rte|vend[eé]rles|venderle|venderles|venderte|"
    r"quiero vender|quisiera vender|puedo vender|para vender|"
    r"les? (?:ofrezco|propongo)|ofrecer(?:les?|te)? (?:una|un|unas|unos|mis|esta|esta)|"
    r"me (?:la|lo|las|los)?\s*compr(?:[aá]s|an|ar[ií]as|ar[ií]an|ar[ií]a)|"
    r"(?:compran|compr[aá]s) cartas|(?:les|te) interesa(?:r[ií]a)? comprar\w*|"
    r"tengo\b.{0,80}?\b(?:a|por)\s*(?:\$|u\$s|us\$|usd)?\s*\d+|tengo\b.{0,80}?\bpsa\s*\d+|"
    r"hacer(?:les)? una propuesta|propuesta de venta)\b",
    re.IGNORECASE,
)
_NO_VENDER = re.compile(r"\b(venden|vend[eé]s|tienen a la venta|tenés a la venta)\b", re.IGNORECASE)
_GRADO = re.compile(r"\bpsa\s*(10|[1-9])\b", re.IGNORECASE)
_PRECIO = re.compile(
    r"(?:(?P<pre>u\$s|us\$|usd|\$)\s*)?(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d{1,2})?)\s*(?P<post>usd|d[oó]lares|u\$s|pesos|ars|lucas|mil)?",
    re.IGNORECASE,
)
_RELLENO = {"una", "un", "unas", "unos", "carta", "cartas", "algo", "esto", "esta", "eso", "mi", "mis", "la", "el", "les", "te"}


def quiere_vender(texto: str) -> bool:
    t = texto or ""
    return bool(_VENDER.search(t)) and not _NO_VENDER.search(t)


def datos_desde_texto(texto: str) -> dict:
    """Lo que se pueda sacar del mensaje para precargar el formulario (todo opcional)."""
    t = texto or ""
    grado = ""
    g = _GRADO.search(t)
    if g:
        grado = f"PSA {g.group(1)}"

    precio, moneda = None, "ARS"
    # El precio va después de "a" / "por" / "en" o con signo de moneda; no se
    # confunde con el número del PSA.
    sin_grado = _GRADO.sub(" ", t)
    for m in _PRECIO.finditer(sin_grado):
        antes = sin_grado[max(0, m.start() - 6):m.start()].lower()
        if not (m.group("pre") or m.group("post") or re.search(r"\b(a|por|en)\s*$", antes)):
            continue
        num = m.group("num")
        if re.search(r"[.,]\d{3}\b", num):        # 25.000 / 25,000 → miles
            valor = float(re.sub(r"[.,]", "", num))
        else:
            valor = float(num.replace(",", "."))
        post = (m.group("post") or "").lower()
        if post in ("lucas", "mil"):
            valor *= 1000
        pre = (m.group("pre") or "").lower()
        if pre in ("u$s", "us$", "usd") or post in ("usd", "dolares", "dólares", "u$s"):
            moneda = "USD"
        if valor > 0:
            precio = valor
            break

    # Nombre de la carta: lo que viene después de "tengo/vendo/vender..." hasta
    # el PSA, el precio o el fin. Es sólo el texto inicial del buscador: la carta
    # exacta la elige el jugador de la lista.
    carta = ""
    c = re.search(
        r"(?:tengo|vendo|vender(?:les|te|le)?|ofrecer(?:les|te)?|ofrezco|compr\w*)\s+(?P<c>.+?)"
        r"(?=\s+(?:psa|en\s+psa|sin\s+graduar|a\s+\$?\d|por\s+\$?\d|en\s+\$?\d|a\s+u|que|y\s|,)|[,.!?]|$)",
        t, re.IGNORECASE,
    )
    if c:
        palabras = [w for w in re.split(r"\s+", c.group("c").strip()) if w]
        while palabras and palabras[0].lower() in _RELLENO | {"1", "2", "3", "4", "5"}:
            palabras.pop(0)
        candidato = " ".join(palabras).strip(" '\"")
        if candidato and candidato.lower() not in _RELLENO and len(candidato) >= 3 and not candidato.isdigit():
            carta = candidato[:60]

    cantidad = 1
    q = re.search(r"(?:tengo|vendo|vender\w*|ofrezco|ofrecer\w*)\s+(\d{1,2})\s+(?!psa)", t, re.IGNORECASE)
    if q and 0 < int(q.group(1)) <= 99:
        cantidad = int(q.group(1))

    return {
        "carta": carta, "grado": grado or "Sin graduar", "precio": precio, "moneda": moneda,
        "cantidad": cantidad, "nombre": "", "apellido": "", "email": "",
    }


TEXTO_FORMULARIO = (
    "¡Dale, la vemos! Completá la planilla de acá abajo: buscá la carta en la lista "
    "y elegí la edición exacta (así sabemos cuál es), poné el grado, la cantidad "
    "y el precio, y dejá tu nombre, apellido y mail, que son obligatorios. "
    "Cuando la envíes, la revisamos y te respondemos por mail."
)
_MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _validar(nombre, apellido, email, grado, cantidad, precio, moneda):
    faltan = [c for c, v in (("nombre", nombre), ("apellido", apellido), ("mail", email)) if not (v or "").strip()]
    if faltan:
        raise ValueError(f"Faltan datos obligatorios: {', '.join(faltan)}.")
    if not _MAIL.match(email.strip()):
        raise ValueError("El mail no parece válido (ej: nombre@gmail.com).")
    if grado not in inventario.GRADOS:
        raise ValueError(f"Grado inválido. Opciones: {', '.join(inventario.GRADOS)}.")
    if int(cantidad) < 1:
        raise ValueError("La cantidad tiene que ser al menos 1.")
    if precio is None or float(precio) <= 0:
        raise ValueError("Poné el precio al que querés vender la carta.")
    if moneda not in MONEDAS:
        raise ValueError("La moneda tiene que ser ARS o USD.")


def crear(thread_id: str | None, nombre: str, apellido: str, email: str, scryfall_id: str,
          grado: str, cantidad: int, precio: float, moneda: str = "ARS", comentario: str = "") -> dict:
    _validar(nombre, apellido, email, grado, cantidad, precio, moneda)
    if not scryfall_id:
        raise ValueError("Elegí la carta de la lista para que el vendedor sepa exactamente cuál es.")
    imp = cartas.impresion_por_id(scryfall_id)
    if not imp:
        raise ValueError("No pude encontrar esa carta en Scryfall. Probá elegirla de nuevo.")

    with base.conectar() as con:
        cur = con.execute(
            """INSERT INTO propuestas (thread_id, nombre, apellido, email, carta, scryfall_id, set_nombre,
                                       numero, imagen, grado, cantidad, precio, moneda, comentario_cliente,
                                       creado, actualizado)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (thread_id, nombre.strip(), apellido.strip(), email.strip().lower(), imp["nombre"], scryfall_id,
             imp["set_nombre"], imp["numero"], imp["imagen"], grado, int(cantidad), float(precio), moneda,
             (comentario or "").strip(), base.ahora_iso(), base.ahora_iso()),
        )
        pid = cur.lastrowid
        simbolo = "US$" if moneda == "USD" else "$"
        base.registrar_movimiento(
            "propuesta", f"Propuesta #{pid}: {imp['nombre']} ({grado})",
            f"{nombre.strip()} {apellido.strip()} ofrece {int(cantidad)} a {simbolo} "
            + f"{float(precio):,.0f}".replace(",", ".") + " c/u",
            con=con,
        )
    return obtener(pid)


def obtener(pid: int):
    with base.conectar() as con:
        f = con.execute("SELECT * FROM propuestas WHERE id = ?", (pid,)).fetchone()
    return _con_referencia(dict(f)) if f else None


def _con_referencia(p: dict) -> dict:
    """Suma el precio de mercado (Scryfall) y lo que la tienda ya tiene de esa carta."""
    variantes = inventario.variantes_de(p["carta"])
    p["en_tienda"] = [{"grado": v["grado"], "cantidad": v["cantidad"], "precio_ars": v["precio_ars"]} for v in variantes]
    return p


def listar(estado: str | None = None, q: str | None = None) -> list:
    sql, params = "SELECT * FROM propuestas WHERE 1=1", []
    if estado:
        sql += " AND estado = ?"
        params.append(estado)
    if q:
        sql += " AND (carta LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR email LIKE ?)"
        params += [f"%{q}%"] * 4
    sql += " ORDER BY id DESC"
    with base.conectar() as con:
        filas = [dict(f) for f in con.execute(sql, params).fetchall()]
    return [_con_referencia(f) for f in filas]


def contar_nuevas() -> int:
    with base.conectar() as con:
        return con.execute("SELECT COUNT(*) FROM propuestas WHERE estado = 'nueva'").fetchone()[0]


ETIQUETA = {"nueva": "nueva", "en_revision": "en revisión", "aceptada": "aceptada", "rechazada": "rechazada"}


def actualizar(pid: int, estado: str | None = None, comentario: str | None = None) -> dict:
    actual = obtener(pid)
    if not actual:
        raise ValueError(f"No existe la propuesta #{pid}.")
    if estado is not None and estado not in ESTADOS:
        raise ValueError(f"Estado inválido. Opciones: {', '.join(ESTADOS)}.")
    with base.conectar() as con:
        if estado and estado != actual["estado"]:
            con.execute("UPDATE propuestas SET estado = ? WHERE id = ?", (estado, pid))
            base.registrar_movimiento(
                "propuesta", f"Propuesta #{pid}: {ETIQUETA[actual['estado']]} → {ETIQUETA[estado]}",
                f"{actual['carta']} · {actual['nombre']} {actual['apellido']}", con=con,
            )
        if comentario is not None and comentario.strip() != actual["comentario_vendedor"]:
            con.execute("UPDATE propuestas SET comentario_vendedor = ? WHERE id = ?", (comentario.strip(), pid))
            base.registrar_movimiento(
                "comentario", f"Comentario en la propuesta #{pid}", f"“{comentario.strip()[:90]}”", con=con,
            )
        con.execute("UPDATE propuestas SET actualizado = ? WHERE id = ?", (base.ahora_iso(), pid))
    return obtener(pid)


def al_inventario(pid: int, precio_venta_usd: float | None, cantidad: int | None = None) -> dict:
    """Acepta la propuesta y carga la carta al inventario con el precio de venta de la tienda."""
    p = obtener(pid)
    if not p:
        raise ValueError(f"No existe la propuesta #{pid}.")
    if not p["scryfall_id"]:
        raise ValueError("La propuesta no tiene la carta de Scryfall: cargala a mano desde Inventario.")
    item = inventario.alta(p["scryfall_id"], p["grado"], int(cantidad or p["cantidad"]), precio_venta_usd)
    actualizar(pid, estado="aceptada")
    return item


def borrar(pid: int):
    p = obtener(pid)
    with base.conectar() as con:
        con.execute("DELETE FROM propuestas WHERE id = ?", (pid,))
        if p:
            base.registrar_movimiento("baja", f"Propuesta #{pid} eliminada", f"{p['carta']} · {p['nombre']} {p['apellido']}", con=con)
