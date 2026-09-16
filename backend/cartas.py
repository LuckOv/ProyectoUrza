"""Datos de una carta para mostrarla en pantalla: imagen, precio y stock.

Separado de tools.py a propósito. Aquello es lo que usa el agente para razonar;
esto es lo que necesita el frontend para dibujar la carta.
"""

import unicodedata
import urllib.parse
from pathlib import Path

import pandas as pd
import requests

CSV_PATH = Path(__file__).parent / "inventario.csv"
HEADERS = {
    "User-Agent": "UrzaBot/1.0 (ProyectoEstudiantilISFT197)",
    "Accept": "application/json",
}

# Scryfall se consulta muchas veces por la misma carta durante una charla.
# Guardar lo que ya vino evita repetir el pedido y respeta su límite de uso.
_cache = {}
_nombres = {}


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
    _nombres[clave] = oficial
    return oficial


def _plano(texto: str) -> str:
    """Deja el nombre comparable: sin acentos, sin puntuación y en minúsculas.

    Así 'Maha, Its Feathers Night' del catálogo matchea con la fila del CSV
    que quedó escrita sin la coma.
    """
    sin_acentos = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    limpio = "".join(c for c in sin_acentos.lower() if c.isalnum() or c.isspace())
    return " ".join(limpio.split())   # colapsa los espacios repetidos


def _imagen(datos: dict):
    """Saca la imagen del frente, contemplando las cartas de doble cara.

    En las de doble cara, Scryfall no trae image_uris arriba sino un
    card_faces con una entrada por cara. Tomamos la primera.
    """
    if datos.get("image_uris"):
        return datos["image_uris"].get("normal") or datos["image_uris"].get("large")
    caras = datos.get("card_faces") or []
    for cara in caras:
        if cara.get("image_uris"):
            return cara["image_uris"].get("normal") or cara["image_uris"].get("large")
    return None


def stock_de(nombre: str):
    """Cuántas copias hay en la tienda. Devuelve (cantidad, edición) o (None, None)."""
    try:
        df = pd.read_csv(CSV_PATH)
        buscado = _plano(nombre)
        fila = df[df["Carta"].map(_plano) == buscado]
        if fila.empty:
            return None, None
        return int(fila.iloc[0]["Cantidad"]), str(fila.iloc[0]["Edición"])
    except Exception:
        return None, None


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
    """Devuelve los datos de una carta, o None si Scryfall no la conoce."""
    clave = (nombre or "").strip().lower()
    if not clave:
        return None
    if clave in _cache:
        return _cache[clave]

    oficial = resolver_nombre(nombre)
    if not oficial:
        return None

    datos = _pedir(f"https://api.scryfall.com/cards/named?exact={urllib.parse.quote(oficial)}")
    if not datos:
        return None

    cantidad, edicion_tienda = stock_de(datos.get("name", nombre))
    precios = datos.get("prices") or {}

    carta = {
        "nombre": datos.get("name"),
        "imagen": _imagen(datos),
        "edicion": edicion_tienda or datos.get("set_name"),
        "precio_eur": precios.get("eur"),
        "precio_usd": precios.get("usd"),
        "tipo": datos.get("type_line"),
        "texto": datos.get("oracle_text"),
        "en_stock": cantidad,
        "scryfall": datos.get("scryfall_uri"),
    }
    _cache[clave] = carta
    return carta
