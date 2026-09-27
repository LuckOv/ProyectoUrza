"""Inventario de la tienda: cartas, variantes, precios y descuentos.

Cada fila es una VARIANTE: la misma carta puede estar varias veces, una por
impresión (set/número) y grado (Sin graduar, PSA 9, PSA 10...). Así el
vendedor puede tener un Blind Seer de Invasion sin graduar y otro PSA 10 con
precios distintos.

Precios: se guardan en dólares (precio_usd) y se muestran en pesos:

    precio en pesos = precio_usd × dólar × (1 − descuento / 100)

El dólar y los descuentos se configuran en el panel del vendedor, así que
si sube el dólar se actualizan todos los precios solos.
"""

import csv
import re
import threading
import time
from datetime import datetime

import requests

import base
import cartas
from cartas import _plano

GRADOS = ["Sin graduar"] + [f"PSA {n}" for n in range(10, 0, -1)]
CASAS_DOLAR = ["blue", "oficial", "tarjeta", "bolsa", "contadoconliqui", "cripto", "mayorista"]


# --- dólar -------------------------------------------------------------------

def traer_dolar(casa: str) -> float:
    """Cotización de venta desde dolarapi.com. Levanta ValueError si no responde."""
    try:
        r = requests.get(f"https://dolarapi.com/v1/dolares/{casa}", timeout=6)
        r.raise_for_status()
        venta = float(r.json()["venta"])
    except Exception as e:
        raise ValueError(f"No pude traer la cotización '{casa}' de dolarapi.com ({e}).")
    return venta


_ultimo_intento = {"cuando": 0.0}


def dolar() -> dict:
    """La configuración del dólar, refrescada si está en automático y tiene más de una hora.

    Si dolarapi no responde, no se reintenta en cada pedido (cada intento
    tarda hasta 6 segundos): se espera 5 minutos entre intentos.
    """
    conf = base.config("dolar")
    if conf.get("modo") == "auto" and time.time() - _ultimo_intento["cuando"] > 300:
        viejo = True
        if conf.get("actualizado"):
            try:
                edad = base.ahora() - datetime.fromisoformat(conf["actualizado"])
                viejo = edad.total_seconds() > 3600
            except ValueError:
                pass
        if viejo:
            _ultimo_intento["cuando"] = time.time()
            try:
                conf["valor"] = traer_dolar(conf.get("casa", "blue"))
                conf["actualizado"] = base.ahora_iso()
                base.guardar_config("dolar", conf)
            except ValueError:
                pass   # sin red: se sigue con el último valor conocido
    return conf


def valor_dolar() -> float:
    return float(dolar().get("valor") or 0)


# --- descuentos --------------------------------------------------------------

def _descuentos_por_carta(con) -> dict:
    return {
        f["inventario_id"]: f["porcentaje"]
        for f in con.execute("SELECT inventario_id, porcentaje FROM descuentos").fetchall()
    }


def listar_descuentos() -> dict:
    with base.conectar() as con:
        filas = con.execute(
            """SELECT d.id, d.inventario_id, d.porcentaje, i.nombre, i.set_nombre, i.grado, i.imagen
                 FROM descuentos d JOIN inventario i ON i.id = d.inventario_id
                ORDER BY i.nombre"""
        ).fetchall()
    return {"general": float(base.config("descuento_general") or 0), "cartas": [dict(f) for f in filas]}


def _validar_porcentaje(p: float) -> float:
    p = float(p)
    if not 0 <= p <= 90:
        raise ValueError("El descuento tiene que estar entre 0% y 90%.")
    return round(p, 2)


def guardar_descuento_general(porcentaje: float):
    base.guardar_config("descuento_general", _validar_porcentaje(porcentaje))


def poner_descuento(inventario_ids: list, porcentaje: float):
    p = _validar_porcentaje(porcentaje)
    with base.conectar() as con:
        for item_id in inventario_ids:
            if p == 0:
                con.execute("DELETE FROM descuentos WHERE inventario_id = ?", (item_id,))
            else:
                con.execute(
                    "INSERT INTO descuentos (inventario_id, porcentaje, creado) VALUES (?, ?, ?) "
                    "ON CONFLICT(inventario_id) DO UPDATE SET porcentaje = excluded.porcentaje",
                    (item_id, p, base.ahora_iso()),
                )


def quitar_descuento(descuento_id: int):
    with base.conectar() as con:
        con.execute("DELETE FROM descuentos WHERE id = ?", (descuento_id,))


# --- lectura -----------------------------------------------------------------

def sku(fila) -> str:
    return f"URZ-{fila['id']:04d}"


def estado_stock(cantidad: int, umbral: int) -> str:
    if cantidad <= 0:
        return "sin"
    if cantidad <= umbral:
        return "bajo"
    return "ok"


def _enriquecer(filas, con) -> list:
    """Agrega a cada fila el SKU, el precio en pesos, el descuento y el estado del stock."""
    cotizacion = valor_dolar()
    general = float(base.config("descuento_general") or 0)
    umbral = int(base.config("stock_bajo") or 0)
    por_carta = _descuentos_por_carta(con)

    resultado = []
    for f in filas:
        d = dict(f)
        desc = max(general, por_carta.get(d["id"], 0))
        d["sku"] = sku(d)
        d["descuento"] = desc
        d["precio_lista_ars"] = round(d["precio_usd"] * cotizacion) if d["precio_usd"] else None
        d["precio_ars"] = (
            round(d["precio_usd"] * cotizacion * (1 - desc / 100)) if d["precio_usd"] else None
        )
        d["estado_stock"] = estado_stock(d["cantidad"], umbral)
        d["legal_standard"] = bool(d["legal_standard"])
        resultado.append(d)
    return resultado


def listar(q: str | None = None, estado: str | None = None) -> list:
    """Todo el inventario, filtrable por texto (carta, set, SKU, grado) y estado de stock."""
    with base.conectar() as con:
        filas = con.execute("SELECT * FROM inventario ORDER BY nombre, set_nombre, grado").fetchall()
        items = _enriquecer(filas, con)

    if q:
        buscado = _plano(q)
        items = [
            i for i in items
            if buscado in _plano(" ".join(str(i.get(k) or "") for k in
                                          ("nombre", "set_nombre", "set_codigo", "sku", "grado", "numero")))
        ]
    if estado:
        items = [i for i in items if i["estado_stock"] == estado]
    return items


def obtener(item_id: int):
    with base.conectar() as con:
        fila = con.execute("SELECT * FROM inventario WHERE id = ?", (item_id,)).fetchone()
        return _enriquecer([fila], con)[0] if fila else None


def variantes_de(nombre: str) -> list:
    """Todas las variantes de una carta, primero las que tienen stock y más baratas."""
    buscado = _plano(nombre)
    with base.conectar() as con:
        filas = [f for f in con.execute("SELECT * FROM inventario").fetchall()
                 if _plano(f["nombre"]) == buscado]
        items = _enriquecer(filas, con)
    return sorted(items, key=lambda v: (v["cantidad"] <= 0, v["precio_ars"] or 0))


def stock_total(nombre: str):
    """(unidades sumando todas las variantes, set de la primera) o (None, None) si no está."""
    variantes = variantes_de(nombre)
    if not variantes:
        return None, None
    return sum(v["cantidad"] for v in variantes), variantes[0]["set_nombre"]


# --- escritura ---------------------------------------------------------------

def _validar_grado(grado: str) -> str:
    grado = (grado or "Sin graduar").strip()
    if grado not in GRADOS:
        raise ValueError(f"Grado inválido: '{grado}'. Opciones: {', '.join(GRADOS)}.")
    return grado


def alta(scryfall_id: str, grado: str = "Sin graduar", cantidad: int = 1,
         precio_usd: float | None = None) -> dict:
    """Da de alta una carta a partir de una impresión de Scryfall.

    Si ya existe la misma impresión con el mismo grado, suma las unidades
    en vez de duplicar la fila.
    """
    grado = _validar_grado(grado)
    if cantidad < 1:
        raise ValueError("La cantidad tiene que ser al menos 1.")
    if precio_usd is not None and precio_usd < 0:
        raise ValueError("El precio no puede ser negativo.")

    imp = cartas.impresion_por_id(scryfall_id)
    if not imp:
        raise ValueError("No pude traer esa carta de Scryfall. Probá de nuevo en un rato.")
    precio = precio_usd if precio_usd is not None else imp["precio_usd"]

    with base.conectar() as con:
        existente = con.execute(
            "SELECT id, cantidad FROM inventario WHERE scryfall_id = ? AND grado = ?",
            (scryfall_id, grado),
        ).fetchone()

        if existente:
            item_id = existente["id"]
            con.execute(
                "UPDATE inventario SET cantidad = ?, precio_usd = COALESCE(?, precio_usd), actualizado = ? WHERE id = ?",
                (existente["cantidad"] + cantidad, precio_usd, base.ahora_iso(), item_id),
            )
        else:
            cur = con.execute(
                """INSERT INTO inventario (nombre, set_codigo, set_nombre, numero, rareza, imagen,
                                           scryfall_id, grado, precio_usd, cantidad, legal_standard,
                                           creado, actualizado)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (imp["nombre"], imp["set_codigo"], imp["set_nombre"], imp["numero"], imp["rareza"],
                 imp["imagen"], scryfall_id, grado, precio, cantidad, int(imp["legal_standard"]),
                 base.ahora_iso(), base.ahora_iso()),
            )
            item_id = cur.lastrowid

        base.registrar_movimiento(
            "entrada", f"Alta de {imp['nombre']}",
            f"{imp['set_nombre']} · {grado}", cantidad, con=con,
        )
    return obtener(item_id)


def editar(item_id: int, grado: str | None = None, precio_usd: float | None = None,
           cantidad: int | None = None, motivo: str = "") -> dict:
    actual = obtener(item_id)
    if not actual:
        raise ValueError("Esa carta ya no está en el inventario.")

    nuevo_grado = _validar_grado(grado) if grado is not None else actual["grado"]
    nuevo_precio = actual["precio_usd"] if precio_usd is None else float(precio_usd)
    nueva_cantidad = actual["cantidad"] if cantidad is None else int(cantidad)
    if nueva_cantidad < 0:
        raise ValueError("La cantidad no puede ser negativa.")
    if nuevo_precio is not None and nuevo_precio < 0:
        raise ValueError("El precio no puede ser negativo.")

    with base.conectar() as con:
        con.execute(
            "UPDATE inventario SET grado = ?, precio_usd = ?, cantidad = ?, actualizado = ? WHERE id = ?",
            (nuevo_grado, nuevo_precio, nueva_cantidad, base.ahora_iso(), item_id),
        )
        diferencia = nueva_cantidad - actual["cantidad"]
        if diferencia:
            base.registrar_movimiento(
                "ajuste", f"Ajuste de stock: {actual['nombre']}",
                motivo or f"{actual['cantidad']} → {nueva_cantidad} unidades", diferencia, con=con,
            )
        cambios = []
        if nuevo_grado != actual["grado"]:
            cambios.append(f"grado {actual['grado']} → {nuevo_grado}")
        if nuevo_precio != actual["precio_usd"]:
            cambios.append(f"precio US$ {actual['precio_usd'] or 0:.2f} → US$ {nuevo_precio or 0:.2f}")
        if cambios:
            base.registrar_movimiento("edicion", f"Edición de {actual['nombre']}", ", ".join(cambios), con=con)
    return obtener(item_id)


def borrar(ids: list) -> int:
    borradas = 0
    with base.conectar() as con:
        for item_id in ids:
            fila = con.execute("SELECT * FROM inventario WHERE id = ?", (item_id,)).fetchone()
            if not fila:
                continue
            con.execute("DELETE FROM inventario WHERE id = ?", (item_id,))
            base.registrar_movimiento(
                "baja", f"Baja de {fila['nombre']}",
                f"{fila['set_nombre'] or ''} · {fila['grado']}", -fila["cantidad"], con=con,
            )
            borradas += 1
    return borradas


def mover_stock(con, item_id: int, delta: int) -> bool:
    """Suma o resta unidades dentro de una transacción abierta. False si no alcanza."""
    fila = con.execute("SELECT cantidad FROM inventario WHERE id = ?", (item_id,)).fetchone()
    if not fila or fila["cantidad"] + delta < 0:
        return False
    con.execute(
        "UPDATE inventario SET cantidad = cantidad + ?, actualizado = ? WHERE id = ?",
        (delta, base.ahora_iso(), item_id),
    )
    return True


# --- migración desde el CSV viejo --------------------------------------------

def importar_csv_viejo():
    """Si el inventario está vacío y existe inventario.csv, lo importa una vez.

    El CSV sólo tiene nombre, edición y cantidad: la imagen, el número y el
    precio se completan después desde Scryfall (completar_desde_scryfall).
    """
    if not base.CSV_VIEJO.exists():
        return 0
    with base.conectar() as con:
        if con.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]:
            return 0
        with open(base.CSV_VIEJO, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        for fila in filas:
            edicion = fila.get("Edición") or ""
            m = re.match(r"^(.*?)\s*\((\w+)\)\s*$", edicion)
            set_nombre, set_codigo = (m.group(1), m.group(2).upper()) if m else (edicion, None)
            con.execute(
                """INSERT INTO inventario (nombre, set_codigo, set_nombre, grado, cantidad, creado, actualizado)
                   VALUES (?, ?, ?, 'Sin graduar', ?, ?, ?)""",
                (fila["Carta"].strip(), set_codigo, set_nombre, int(fila.get("Cantidad") or 0),
                 base.ahora_iso(), base.ahora_iso()),
            )
        base.registrar_movimiento(
            "entrada", "Importación del CSV", f"{len(filas)} cartas desde inventario.csv",
            sum(int(f.get("Cantidad") or 0) for f in filas), con=con,
        )
    return len(filas)


def completar_desde_scryfall():
    """Completa imagen, número, rareza y precio de las filas que no los tienen."""
    with base.conectar() as con:
        pendientes = con.execute(
            "SELECT id, nombre, set_codigo, precio_usd FROM inventario WHERE scryfall_id IS NULL"
        ).fetchall()
    for f in pendientes:
        imp = cartas.impresion_por_set(f["nombre"], f["set_codigo"])
        if not imp:
            continue
        with base.conectar() as con:
            con.execute(
                """UPDATE inventario
                      SET nombre = ?, set_codigo = ?, set_nombre = ?, numero = ?, rareza = ?, imagen = ?,
                          scryfall_id = ?, precio_usd = COALESCE(precio_usd, ?), legal_standard = ?
                    WHERE id = ?""",
                (imp["nombre"], imp["set_codigo"], imp["set_nombre"], imp["numero"], imp["rareza"],
                 imp["imagen"], imp["scryfall_id"], imp["precio_usd"], int(imp["legal_standard"]), f["id"]),
            )


def completar_en_segundo_plano():
    threading.Thread(target=completar_desde_scryfall, daemon=True).start()
