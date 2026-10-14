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
import os
import re
import threading
import time
from datetime import datetime, timedelta

import requests

from tienda import base
from tienda import cartas
from tienda.cartas import _plano

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


# --- precio sugerido para cartas graduadas ------------------------------------
#
# Scryfall sólo da el precio de la carta sin graduar. Para PSA hay dos fuentes:
#   1. PriceCharting (pricecharting.com/api-documentation), si hay un token en
#      PRICECHARTING_TOKEN (backend/.env). Es una API paga. Trae PSA 10, 9.5, 9,
#      8 y 7; para el resto de los grados se cae al punto 2.
#   2. Multiplicador por grado (Configuración) sobre el precio de Scryfall.

# Campo de PriceCharting para cada grado (precios en centavos de dólar).
CAMPOS_PRICECHARTING = {
    "Sin graduar": "loose-price",
    "PSA 10": "manual-only-price",
    "PSA 9": "graded-price",
    "PSA 8": "new-price",
    "PSA 7": "cib-price",
}
_cache_pc = {}


def _pricecharting(nombre: str, set_nombre: str | None):
    """Precios de PriceCharting para una carta, o None si no hay token o falla."""
    token = os.getenv("PRICECHARTING_TOKEN")
    if not token:
        return None
    clave = (nombre, set_nombre)
    if clave in _cache_pc:
        return _cache_pc[clave]
    try:
        r = requests.get(
            "https://www.pricecharting.com/api/products",
            params={"t": token, "q": f"{nombre} {set_nombre or ''}".strip()}, timeout=8,
        )
        productos = r.json().get("products") or []
        if not productos:
            _cache_pc[clave] = None
            return None
        r = requests.get(
            "https://www.pricecharting.com/api/product",
            params={"t": token, "id": productos[0]["id"]}, timeout=8,
        )
        datos = r.json()
        _cache_pc[clave] = datos if datos.get("status") == "success" else None
    except Exception:
        return None   # sin red o respuesta inesperada: se usa el multiplicador
    return _cache_pc[clave]


def precio_sugerido(grado: str, precio_base_usd: float | None,
                    nombre: str = "", set_nombre: str | None = None) -> dict:
    """Precio en dólares sugerido para una carta en un grado dado.

    Devuelve {"precio_usd", "fuente", "detalle"}; precio_usd puede ser None si
    no hay de dónde sacarlo.
    """
    pc = _pricecharting(nombre, set_nombre) if nombre else None
    campo = CAMPOS_PRICECHARTING.get(grado)
    if pc and campo and pc.get(campo):
        return {
            "precio_usd": round(pc[campo] / 100, 2),
            "fuente": "pricecharting",
            "detalle": f"PriceCharting · {pc.get('product-name', nombre)}",
        }

    if precio_base_usd is None:
        return {"precio_usd": None, "fuente": "ninguna",
                "detalle": "Scryfall no tiene precio de esta carta: cargalo a mano."}
    if grado == "Sin graduar":
        return {"precio_usd": round(precio_base_usd, 2), "fuente": "scryfall",
                "detalle": "Precio de mercado de Scryfall (sin graduar)."}

    factor = float((base.config("multiplicadores") or {}).get(grado, 1.0))
    return {
        "precio_usd": round(precio_base_usd * factor, 2),
        "fuente": "multiplicador",
        "detalle": (f"{grado} = ×{factor:g} sobre US$ {precio_base_usd:.2f} (sin graduar, Scryfall)."
                    .replace(".", ",").rstrip(",") + "."),
    }


def guardar_multiplicadores(valores: dict) -> dict:
    limpio = {}
    for grado in GRADOS[1:]:
        if grado not in valores:
            continue
        v = float(valores[grado])
        if not 0.1 <= v <= 100:
            raise ValueError(f"El multiplicador de {grado} tiene que estar entre 0,1 y 100.")
        limpio[grado] = round(v, 2)
    actual = {**(base.config("multiplicadores") or {}), **limpio}
    base.guardar_config("multiplicadores", actual)
    base.registrar_movimiento(
        "config", "Multiplicadores de precio por grado actualizados",
        ", ".join(f"{g} ×{actual[g]:g}" for g in GRADOS[1:4] if g in actual) + "…",
    )
    return actual


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
    p = _validar_porcentaje(porcentaje)
    anterior = float(base.config("descuento_general") or 0)
    base.guardar_config("descuento_general", p)
    if p != anterior:
        base.registrar_movimiento(
            "config", "Descuento general actualizado", f"{anterior:g}% → {p:g}% en todo el inventario"
        )


def poner_descuento(inventario_ids: list, porcentaje: float):
    p = _validar_porcentaje(porcentaje)
    with base.conectar() as con:
        # Las cartas que ya no existen (borradas en otra pestaña) se ignoran.
        existentes = {f["id"] for f in con.execute("SELECT id FROM inventario").fetchall()}
        inventario_ids = [i for i in dict.fromkeys(inventario_ids) if i in existentes]
        nombres = [
            f"{f['nombre']} ({f['grado']})"
            for f in con.execute(
                f"SELECT nombre, grado FROM inventario WHERE id IN ({','.join('?' * len(inventario_ids))})",
                list(inventario_ids),
            ).fetchall()
        ] if inventario_ids else []
        for item_id in inventario_ids:
            if p == 0:
                con.execute("DELETE FROM descuentos WHERE inventario_id = ?", (item_id,))
            else:
                con.execute(
                    "INSERT INTO descuentos (inventario_id, porcentaje, creado) VALUES (?, ?, ?) "
                    "ON CONFLICT(inventario_id) DO UPDATE SET porcentaje = excluded.porcentaje",
                    (item_id, p, base.ahora_iso()),
                )
        if nombres:
            base.registrar_movimiento(
                "config",
                f"Descuento del {p:g}% aplicado" if p else "Descuento quitado",
                ", ".join(nombres[:6]) + (f" y {len(nombres) - 6} más" if len(nombres) > 6 else ""),
                con=con,
            )


def quitar_descuento(descuento_id: int):
    with base.conectar() as con:
        fila = con.execute(
            """SELECT d.porcentaje, i.nombre, i.grado FROM descuentos d
                 JOIN inventario i ON i.id = d.inventario_id WHERE d.id = ?""",
            (descuento_id,),
        ).fetchone()
        con.execute("DELETE FROM descuentos WHERE id = ?", (descuento_id,))
        if fila:
            base.registrar_movimiento(
                "config", "Descuento quitado",
                f"{fila['nombre']} ({fila['grado']}) · era {fila['porcentaje']:g}%", con=con,
            )


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
    umbral_precio = float(base.config("alerta_precio") or 30)
    multiplicadores = base.config("multiplicadores") or {}
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
        # Dos avisos de precio, contra el precio de mercado de Scryfall de hoy:
        #
        # 1. "precio": TU precio está muy lejos del mercado actual (ej. cargaste
        #    una carta carísima o regalada). Para las graduadas el mercado es una
        #    estimación (Scryfall sin graduar × multiplicador del grado), así que
        #    se avisa recién con el doble de diferencia.
        # 2. "mercado": el mercado se movió mucho desde que pusiste tu precio;
        #    se sugiere mover el tuyo en la misma proporción.
        mercado, ref = d.get("precio_mercado_usd"), d.get("mercado_referencia_usd")
        graduada = d["grado"] != "Sin graduar"
        d["mercado_hoy_usd"] = (
            round(mercado * float(multiplicadores.get(d["grado"], 1.0)), 2) if mercado and graduada
            else mercado
        )
        d["mercado_estimado"] = bool(mercado and graduada)
        if d["mercado_hoy_usd"] and d["precio_usd"]:
            d["vs_mercado_pct"] = round((d["precio_usd"] / d["mercado_hoy_usd"] - 1) * 100, 1)
        else:
            d["vs_mercado_pct"] = None
        if mercado and ref and d["precio_usd"]:
            proporcion = mercado / ref
            d["mercado_cambio_pct"] = round((proporcion - 1) * 100, 1)
        else:
            proporcion = None
            d["mercado_cambio_pct"] = None

        tope_precio = umbral_precio * (2 if graduada else 1)
        aceptado = d.get("precio_aceptado_usd") is not None and d["precio_usd"] is not None \
            and abs(d["precio_aceptado_usd"] - d["precio_usd"]) < 0.005
        if not aceptado and d["vs_mercado_pct"] is not None and abs(d["vs_mercado_pct"]) >= tope_precio:
            d["alerta_tipo"] = "precio"
            d["alerta_pct"] = d["vs_mercado_pct"]
            d["sugerido_usd"] = d["mercado_hoy_usd"]
        elif d["mercado_cambio_pct"] is not None and abs(d["mercado_cambio_pct"]) >= umbral_precio:
            d["alerta_tipo"] = "mercado"
            d["alerta_pct"] = d["mercado_cambio_pct"]
            d["sugerido_usd"] = round(d["precio_usd"] * proporcion, 2)
        else:
            d["alerta_tipo"] = None
            d["alerta_pct"] = None
            d["sugerido_usd"] = None
        d["alerta_precio"] = d["alerta_tipo"] is not None
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


def mantener_precio(item_id: int):
    """El vendedor deja su precio como está: no se avisa más por esta diferencia
    (hasta que cambie el precio) y el mercado de hoy pasa a ser la referencia."""
    with base.conectar() as con:
        fila = con.execute("SELECT nombre, grado, precio_usd FROM inventario WHERE id = ?", (item_id,)).fetchone()
        if not fila:
            raise ValueError("Esa carta no está en el inventario.")
        con.execute(
            """UPDATE inventario SET precio_aceptado_usd = precio_usd,
                      mercado_referencia_usd = COALESCE(precio_mercado_usd, mercado_referencia_usd)
                WHERE id = ?""", (item_id,))
    base.registrar_movimiento("edicion", f"Precio mantenido: {fila['nombre']} ({fila['grado']})",
                   f"Se dejó en US$ {fila['precio_usd']:.2f} aunque está lejos del mercado")
    return obtener(item_id)


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
                """UPDATE inventario SET cantidad = ?, precio_usd = COALESCE(?, precio_usd),
                          mercado_referencia_usd = CASE WHEN ? IS NULL THEN mercado_referencia_usd ELSE ? END,
                          actualizado = ? WHERE id = ?""",
                (existente["cantidad"] + cantidad, precio_usd, precio_usd, imp["precio_usd"], base.ahora_iso(), item_id),
            )
        else:
            cur = con.execute(
                """INSERT INTO inventario (nombre, set_codigo, set_nombre, numero, rareza, imagen,
                                           scryfall_id, grado, precio_usd, cantidad, legal_standard,
                                           colores, precio_mercado_usd, mercado_actualizado, mercado_referencia_usd,
                                           creado, actualizado)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (imp["nombre"], imp["set_codigo"], imp["set_nombre"], imp["numero"], imp["rareza"],
                 imp["imagen"], scryfall_id, grado, precio, cantidad, int(imp["legal_standard"]),
                 imp["colores"], imp["precio_usd"], base.ahora_iso(), imp["precio_usd"],
                 base.ahora_iso(), base.ahora_iso()),
            )
            item_id = cur.lastrowid

        base.registrar_movimiento(
            "entrada", f"Alta de {imp['nombre']}",
            f"{imp['set_nombre']} · {grado}", cantidad, con=con,
        )
    return obtener(item_id)


def agregar_variante(item_id: int, grado: str, cantidad: int = 1,
                     precio_usd: float | None = None) -> dict:
    """Suma la misma carta (misma impresión) con otro grado: ej. ya tenés el
    Blind Seer sin graduar y entra uno PSA 10.

    Copia los datos de la carta de la fila existente, así no hace falta volver
    a buscarla en Scryfall. Si ese grado ya existía, suma las unidades.
    """
    grado = _validar_grado(grado)
    if cantidad < 1:
        raise ValueError("La cantidad tiene que ser al menos 1.")
    if precio_usd is not None and precio_usd < 0:
        raise ValueError("El precio no puede ser negativo.")
    origen = obtener(item_id)
    if not origen:
        raise ValueError("Esa carta ya no está en el inventario.")

    with base.conectar() as con:
        # Misma impresión: por scryfall_id si lo hay; si no (filas del CSV
        # viejo sin completar), por nombre + set.
        if origen["scryfall_id"]:
            existente = con.execute(
                "SELECT id, cantidad FROM inventario WHERE scryfall_id = ? AND grado = ?",
                (origen["scryfall_id"], grado),
            ).fetchone()
        else:
            existente = con.execute(
                """SELECT id, cantidad FROM inventario
                    WHERE nombre = ? AND IFNULL(set_codigo,'') = IFNULL(?,'') AND grado = ?""",
                (origen["nombre"], origen["set_codigo"], grado),
            ).fetchone()

        if existente:
            nuevo_id = existente["id"]
            con.execute(
                "UPDATE inventario SET cantidad = ?, precio_usd = COALESCE(?, precio_usd), actualizado = ? WHERE id = ?",
                (existente["cantidad"] + cantidad, precio_usd, base.ahora_iso(), nuevo_id),
            )
        else:
            cur = con.execute(
                """INSERT INTO inventario (nombre, set_codigo, set_nombre, numero, rareza, imagen,
                                           scryfall_id, grado, precio_usd, cantidad, legal_standard,
                                           colores, precio_mercado_usd, mercado_actualizado, mercado_referencia_usd,
                                           creado, actualizado)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (origen["nombre"], origen["set_codigo"], origen["set_nombre"], origen["numero"],
                 origen["rareza"], origen["imagen"], origen["scryfall_id"], grado,
                 precio_usd if precio_usd is not None else origen["precio_usd"], cantidad,
                 int(origen["legal_standard"]), origen.get("colores"), origen.get("precio_mercado_usd"),
                 origen.get("mercado_actualizado"), origen.get("precio_mercado_usd"),
                 base.ahora_iso(), base.ahora_iso()),
            )
            nuevo_id = cur.lastrowid
        base.registrar_movimiento(
            "entrada", f"Nuevo grado de {origen['nombre']}",
            f"{origen['set_nombre'] or 'sin set'} · {grado}", cantidad, con=con,
        )
    return obtener(nuevo_id)


def catalogo() -> list:
    """Lo que el jugador puede comprar: todas las variantes con stock y precio."""
    return [
        {k: i.get(k) for k in ("id", "nombre", "set_nombre", "set_codigo", "rareza", "grado", "precio_ars",
                               "cantidad", "imagen", "descuento", "colores")}
        for i in listar()
        if i["cantidad"] > 0 and i["precio_ars"] is not None
    ]


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
        if nuevo_grado != actual["grado"]:
            # La misma impresión no puede quedar dos veces con el mismo grado.
            if actual["scryfall_id"]:
                otra = con.execute(
                    "SELECT id FROM inventario WHERE scryfall_id = ? AND grado = ? AND id != ?",
                    (actual["scryfall_id"], nuevo_grado, item_id),
                ).fetchone()
            else:
                otra = con.execute(
                    """SELECT id FROM inventario WHERE nombre = ? AND IFNULL(set_codigo,'') = IFNULL(?,'')
                          AND grado = ? AND id != ?""",
                    (actual["nombre"], actual["set_codigo"], nuevo_grado, item_id),
                ).fetchone()
            if otra:
                raise ValueError(
                    f"Ya tenés {actual['nombre']} ({actual['set_nombre'] or 'sin set'}) en {nuevo_grado} "
                    f"(URZ-{otra['id']:04d}). Sumale las unidades a esa en vez de cambiar el grado."
                )
        con.execute(
            "UPDATE inventario SET grado = ?, precio_usd = ?, cantidad = ?, actualizado = ? WHERE id = ?",
            (nuevo_grado, nuevo_precio, nueva_cantidad, base.ahora_iso(), item_id),
        )
        if nuevo_precio != actual["precio_usd"]:
            # Precio nuevo: desde acá se vuelve a medir cuánto se mueve el mercado.
            con.execute(
                "UPDATE inventario SET mercado_referencia_usd = precio_mercado_usd WHERE id = ?", (item_id,)
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
    if not base.CSV_VIEJO.exists() or base.config("csv_importado"):
        return 0
    with base.conectar() as con:
        if con.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]:
            base.guardar_config("csv_importado", True)
            return 0
        # utf-8-sig: si el CSV se guardó desde Excel trae BOM y la primera
        # columna dejaba de llamarse "Carta".
        with open(base.CSV_VIEJO, encoding="utf-8-sig") as f:
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
    base.guardar_config("csv_importado", True)
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
                          scryfall_id = ?, precio_usd = COALESCE(precio_usd, ?), legal_standard = ?,
                          colores = ?, precio_mercado_usd = ?, mercado_actualizado = ?,
                          mercado_referencia_usd = COALESCE(mercado_referencia_usd, ?)
                    WHERE id = ?""",
                (imp["nombre"], imp["set_codigo"], imp["set_nombre"], imp["numero"], imp["rareza"],
                 imp["imagen"], imp["scryfall_id"], imp["precio_usd"], int(imp["legal_standard"]),
                 imp["colores"], imp["precio_usd"], base.ahora_iso(), imp["precio_usd"], f["id"]),
            )
    # Las filas que ya tenían Scryfall pero no colores o precio de mercado
    # (bases de versiones anteriores) se completan en lote.
    refrescar_mercado(forzar=False)


_ultimo_refresco = {"cuando": 0.0}
HORAS_MERCADO = 6


def refrescar_mercado(forzar: bool = False) -> int:
    """Trae de Scryfall el precio de mercado (y los colores) de todo el inventario.

    Se hace en lote (75 cartas por pedido) y como mucho cada 6 horas, salvo
    que se fuerce. Devuelve cuántas filas actualizó.
    """
    if not forzar and time.time() - _ultimo_refresco["cuando"] < 300:
        return 0
    _ultimo_refresco["cuando"] = time.time()
    limite = (base.ahora() - timedelta(hours=HORAS_MERCADO)).isoformat()
    with base.conectar() as con:
        filas = con.execute(
            """SELECT id, scryfall_id FROM inventario
                WHERE scryfall_id IS NOT NULL
                  AND (? OR colores IS NULL OR mercado_actualizado IS NULL OR mercado_actualizado < ?)""",
            (int(forzar), limite),
        ).fetchall()
    if not filas:
        return 0
    datos = cartas.precios_actuales([f["scryfall_id"] for f in filas])
    actualizadas = 0
    with base.conectar() as con:
        for f in filas:
            d = datos.get(f["scryfall_id"])
            if not d:
                continue
            con.execute(
                """UPDATE inventario SET colores = ?, precio_mercado_usd = ?, mercado_actualizado = ?,
                          mercado_referencia_usd = COALESCE(mercado_referencia_usd, ?) WHERE id = ?""",
                (d["colores"], d["precio_usd"], base.ahora_iso(), d["precio_usd"], f["id"]),
            )
            actualizadas += 1
    return actualizadas


def completar_en_segundo_plano():
    threading.Thread(target=completar_desde_scryfall, daemon=True).start()
