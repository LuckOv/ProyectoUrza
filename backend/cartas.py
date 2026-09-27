"""Todo lo que viene de Scryfall: nombres, fichas, imágenes e impresiones.

Separado de tools.py a propósito. Aquello es lo que usa el agente para
razonar; esto es lo que necesitan el frontend del cliente (dibujar la carta)
y el panel del vendedor (buscar una carta para darla de alta).

El stock y los precios de la tienda NO salen de acá sino de inventario.py.
"""

import time
import unicodedata
import urllib.parse

import requests

HEADERS = {
    "User-Agent": "UrzaBot/1.0 (ProyectoEstudiantilISFT197)",
    "Accept": "application/json",
}

# Scryfall se consulta muchas veces por la misma carta durante una charla.
# Guardar lo que ya vino evita repetir el pedido y respeta su límite de uso.
_cache = {}
_nombres = {}
_pool_standard = {"total": None, "cuando": 0.0}


def _pedir(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
    except requests.RequestException:
        return None
    return r.json() if r.status_code == 200 else None


def resolver_nombre(nombre: str):
    """Traduce cualquier forma de escribir una carta al nombre oficial en inglés.

    Sirve para tres cosas a la vez: nombres en español ("Elfos de Llanowar"),
    errores de tipeo ("Lanowar Elfs") y nombres a los que les falta la
    puntuación ("Maha Its Feathers Night"). Devuelve None si no la encuentra.

    El orden importa. Primero el nombre exacto en inglés, que es el caso
    común y el más barato. Después la búsqueda multilingüe, que es la que
    entiende el español. La difusa va última porque es la que más se
    equivoca: ante un nombre en español devuelve cualquier cosa parecida.
    """
    limpio = (nombre or "").strip()
    if not limpio:
        return None
    clave = limpio.lower()
    if clave in _nombres:
        return _nombres[clave]

    cod = urllib.parse.quote(limpio)

    datos = _pedir(f"https://api.scryfall.com/cards/named?exact={cod}")

    if not datos:
        # include_multilingual hace que Scryfall mire también los nombres
        # impresos en otros idiomas, no sólo el oracle en inglés.
        busqueda = _pedir(
            f"https://api.scryfall.com/cards/search?q={cod}"
            "&include_multilingual=true&unique=cards&order=released"
        )
        if busqueda and busqueda.get("data"):
            datos = busqueda["data"][0]

    if not datos:
        datos = _pedir(f"https://api.scryfall.com/cards/named?fuzzy={cod}")

    oficial = datos.get("name") if datos else None
    # Sólo se guardan los aciertos: si Scryfall no respondió (sin red), la
    # próxima vez se vuelve a intentar.
    if oficial:
        _nombres[clave] = oficial
    return oficial


def _plano(texto: str) -> str:
    """Deja el nombre comparable: sin acentos, sin puntuación y en minúsculas.

    Así 'Maha, Its Feathers Night' del catálogo matchea con una fila que
    quedó escrita sin la coma.
    """
    sin_acentos = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    limpio = "".join(c for c in sin_acentos.lower() if c.isalnum() or c.isspace())
    return " ".join(limpio.split())   # colapsa los espacios repetidos


def _imagen(datos: dict, tamano: str = "normal"):
    """Saca la imagen del frente, contemplando las cartas de doble cara.

    En las de doble cara, Scryfall no trae image_uris arriba sino un
    card_faces con una entrada por cara. Tomamos la primera.
    """
    if datos.get("image_uris"):
        return datos["image_uris"].get(tamano) or datos["image_uris"].get("large")
    for cara in datos.get("card_faces") or []:
        if cara.get("image_uris"):
            return cara["image_uris"].get(tamano) or cara["image_uris"].get("large")
    return None


def stock_de(nombre: str):
    """Cuántas copias hay en la tienda. Devuelve (cantidad, edición) o (None, None).

    Suma todas las variantes (sets y grados) de la carta.
    """
    import inventario   # import tardío: inventario también usa este módulo
    return inventario.stock_total(nombre)


def version_es(nombre_oficial: str):
    """Trae la impresión en español de una carta, si existe.

    Scryfall guarda cada idioma como una impresión aparte. En esas
    impresiones el nombre, el tipo y el texto traducidos vienen en los
    campos printed_*, mientras que name y type_line siguen en inglés.
    """
    cod = urllib.parse.quote(f'!"{nombre_oficial}" lang:es')
    datos = _pedir(
        f"https://api.scryfall.com/cards/search?q={cod}"
        "&include_multilingual=true&unique=prints"
    )
    if not datos or not datos.get("data"):
        return {}
    carta = datos["data"][0]
    caras = carta.get("card_faces") or []
    if not carta.get("printed_name") and caras:
        carta = {**carta, **caras[0]}
    return {
        "nombre_es": carta.get("printed_name"),
        "tipo_es": carta.get("printed_type_line"),
        "texto_es": carta.get("printed_text"),
    }


def ficha(nombre: str):
    """Todo lo que se sabe de una carta, para que el agente no invente nada.

    Devuelve None si Scryfall no la conoce. Incluye la versión en español
    cuando la carta llegó a imprimirse en ese idioma.
    """
    oficial = resolver_nombre(nombre)
    if not oficial:
        return None

    datos = _pedir(f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(oficial)}")
    if not datos:
        return None

    cara = datos
    caras = datos.get("card_faces") or []
    if not datos.get("type_line") and caras:
        cara = caras[0]

    legal_en = [f for f, e in (datos.get("legalities") or {}).items() if e == "legal"]
    cantidad, edicion_tienda = stock_de(oficial)
    precios = datos.get("prices") or {}

    resultado = {
        "nombre": datos.get("name"),
        "coste": cara.get("mana_cost") or datos.get("mana_cost"),
        "valor_maná": datos.get("cmc"),
        "tipo": cara.get("type_line") or datos.get("type_line"),
        "colores": datos.get("colors") or datos.get("color_identity"),
        "texto": cara.get("oracle_text") or datos.get("oracle_text"),
        "fuerza_resistencia": (
            f"{cara.get('power')}/{cara.get('toughness')}" if cara.get("power") else None
        ),
        "rareza": datos.get("rarity"),
        "edicion": datos.get("set_name"),
        "legal_en": legal_en,
        "precio_eur": precios.get("eur"),
        "en_stock": cantidad,
        "edicion_tienda": edicion_tienda,
    }
    resultado.update(version_es(oficial))
    return resultado


def buscar(nombre: str):
    """Datos de una carta para dibujarla en el chat, o None si Scryfall no la conoce.

    Lo de Scryfall (imagen, tipo) se cachea; el stock y el precio de la
    tienda se releen siempre, porque cambian con cada venta o edición.
    """
    import inventario

    clave = (nombre or "").strip().lower()
    if not clave:
        return None

    base = _cache.get(clave)
    if base is None:
        oficial = resolver_nombre(nombre)
        if not oficial:
            return None
        datos = _pedir(f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(oficial)}")
        if not datos:
            return None
        precios = datos.get("prices") or {}
        base = {
            "nombre": datos.get("name"),
            "imagen": _imagen(datos),
            "edicion_scryfall": datos.get("set_name"),
            "precio_mercado_usd": precios.get("usd"),
            "tipo": datos.get("type_line"),
            "texto": datos.get("oracle_text"),
            "scryfall": datos.get("scryfall_uri"),
        }
        _cache[clave] = base

    variantes = inventario.variantes_de(base["nombre"])
    con_stock = [v for v in variantes if v["cantidad"] > 0]
    primera = (con_stock or variantes or [None])[0]

    return {
        **base,
        # Si la tienda la tiene, se muestra la imagen de la impresión que vende.
        "imagen": (primera or {}).get("imagen") or base["imagen"],
        "edicion": (primera or {}).get("set_nombre") or base["edicion_scryfall"],
        "en_stock": sum(v["cantidad"] for v in variantes) if variantes else None,
        "precio_ars": min((v["precio_ars"] for v in con_stock), default=None),
        "variantes": variantes,
    }


# --- para el panel del vendedor ---------------------------------------------

def _impresion(datos: dict) -> dict:
    """Una impresión de Scryfall reducida a lo que guarda el inventario."""
    precios = datos.get("prices") or {}
    usd = precios.get("usd") or precios.get("usd_foil") or precios.get("usd_etched")
    return {
        "scryfall_id": datos.get("id"),
        "nombre": datos.get("name"),
        "set_codigo": (datos.get("set") or "").upper(),
        "set_nombre": datos.get("set_name"),
        "numero": datos.get("collector_number"),
        "rareza": datos.get("rarity"),
        "imagen": _imagen(datos),
        "imagen_chica": _imagen(datos, "small"),
        "precio_usd": float(usd) if usd else None,
        "fecha": datos.get("released_at"),
        "legal_standard": (datos.get("legalities") or {}).get("standard") == "legal",
    }


def autocompletar(texto: str) -> list:
    """Nombres de cartas que empiezan o se parecen a lo tipeado.

    El autocompletado de Scryfall sólo conoce nombres en inglés; si no
    encuentra nada, se prueba con la búsqueda multilingüe para que también
    funcione "Elfos de Llanowar".
    """
    texto = (texto or "").strip()
    if len(texto) < 2:
        return []
    datos = _pedir(f"https://api.scryfall.com/cards/autocomplete?q={urllib.parse.quote(texto)}")
    nombres = (datos or {}).get("data") or []
    if nombres:
        return nombres[:15]

    busqueda = _pedir(
        f"https://api.scryfall.com/cards/search?q={urllib.parse.quote(texto)}"
        "&include_multilingual=true&unique=cards&order=name"
    )
    vistos = []
    for c in (busqueda or {}).get("data", [])[:15]:
        if c.get("name") not in vistos:
            vistos.append(c.get("name"))
    return vistos


def impresiones(nombre: str) -> list:
    """Todas las impresiones de una carta (una por set/número), de la más nueva a la más vieja."""
    cod = urllib.parse.quote(f'!"{nombre}"')
    datos = _pedir(
        f"https://api.scryfall.com/cards/search?q={cod}&unique=prints&order=released&dir=desc"
    )
    return [_impresion(c) for c in (datos or {}).get("data", [])]


def impresion_por_id(scryfall_id: str):
    datos = _pedir(f"https://api.scryfall.com/cards/{urllib.parse.quote(scryfall_id)}")
    return _impresion(datos) if datos else None


def impresion_por_set(nombre: str, set_codigo: str | None):
    """La impresión de una carta en un set dado (o la más reciente si no se sabe el set)."""
    if set_codigo:
        cod = urllib.parse.quote(f'!"{nombre}" set:{set_codigo.lower()}')
        datos = _pedir(f"https://api.scryfall.com/cards/search?q={cod}&unique=prints")
        if datos and datos.get("data"):
            return _impresion(datos["data"][0])
    datos = _pedir(f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(nombre)}")
    if not datos:
        datos = _pedir(f"https://api.scryfall.com/cards/named?fuzzy={urllib.parse.quote(nombre)}")
    return _impresion(datos) if datos else None


def total_pool_standard():
    """Cuántas cartas distintas son legales hoy en Standard. Se cachea un día."""
    if _pool_standard["total"] and time.time() - _pool_standard["cuando"] < 86400:
        return _pool_standard["total"]
    datos = _pedir("https://api.scryfall.com/cards/search?q=f%3Astandard&unique=cards")
    if datos and datos.get("total_cards"):
        _pool_standard.update(total=datos["total_cards"], cuando=time.time())
    return _pool_standard["total"]
