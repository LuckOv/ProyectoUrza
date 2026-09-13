"""Datos de una carta para mostrarla en pantalla: imagen, precio y stock.

Separado de tools.py a propósito. Aquello es lo que usa el agente para razonar;
esto es lo que necesita el frontend para dibujar la carta.
"""

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
        fila = df[df["Carta"].str.lower() == nombre.strip().lower()]
        if fila.empty:
            return None, None
        return int(fila.iloc[0]["Cantidad"]), str(fila.iloc[0]["Edición"])
    except Exception:
        return None, None


def buscar(nombre: str):
    """Devuelve los datos de una carta, o None si Scryfall no la conoce."""
    clave = nombre.strip().lower()
    if not clave:
        return None
    if clave in _cache:
        return _cache[clave]

    codificado = urllib.parse.quote(nombre.strip())
    datos = None
    for modo in ("exact", "fuzzy"):
        try:
            r = requests.get(
                f"https://api.scryfall.com/cards/named?{modo}={codificado}",
                headers=HEADERS,
                timeout=8,
            )
        except requests.RequestException:
            return None
        if r.status_code == 200:
            datos = r.json()
            break
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
