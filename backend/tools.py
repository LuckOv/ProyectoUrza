import urllib.parse
from pathlib import Path

import pandas as pd
import requests
from langchain_core.tools import tool

from cartas import ficha, resolver_nombre, _plano
from lore import consultar_lore_mtg
from reglas import consultar_reglas_mtg

# Anclado a la carpeta de este archivo, no al directorio desde donde se lanza
# el proceso: así funciona igual con uvicorn, con el test local o desde la raíz.
CSV_PATH = Path(__file__).parent / "inventario.csv"

# Cabecera obligatoria que exige la API de Scryfall para no bloquear la petición
HEADERS = {
    "User-Agent": "UrzaBot/1.0 (ProyectoEstudiantilISFT197)",
    "Accept": "application/json"
}

@tool
def consultar_precio_cardmarket(nombre_carta: str) -> str:
    """Consulta el precio actual de una carta en euros usando la API de Scryfall.

    Acepta el nombre en cualquier idioma y con errores de tipeo: antes de
    buscar lo traduce al nombre oficial en inglés.
    """
    # Extraer el valor si viene empacado como dict
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")

    nombre_limpio = resolver_nombre(nombre_carta) or str(nombre_carta).strip()
    print(f"\n[DEBUG TOOL] Solicitando a Scryfall: '{nombre_limpio}'")
    
    nombre_encoded = urllib.parse.quote(nombre_limpio)
    
    # 1. Intento por nombre exacto
    url_exact = f"https://api.scryfall.com/cards/named?exact={nombre_encoded}"
    respuesta = requests.get(url_exact, headers=HEADERS)
    
    if respuesta.status_code == 200:
        datos = respuesta.json()
        precio_eur = datos.get("prices", {}).get("eur") 
        if precio_eur:
            return f"El precio actual de '{datos.get('name')}' en CardMarket (vía Scryfall) es de €{precio_eur}."
        return f"Encontré la carta '{datos.get('name')}', pero Scryfall no registra un precio en euros actualmente."
    
    # 2. Fallback por búsqueda difusa (Fuzzy)
    url_fuzzy = f"https://api.scryfall.com/cards/named?fuzzy={nombre_encoded}"
    resp_fuzzy = requests.get(url_fuzzy, headers=HEADERS)
    
    if resp_fuzzy.status_code == 200:
        datos = resp_fuzzy.json()
        precio_eur = datos.get("prices", {}).get("eur")
        if precio_eur:
            return f"El precio actual de '{datos.get('name')}' en CardMarket (vía Scryfall) es de €{precio_eur}."
        return f"Encontré la carta '{datos.get('name')}', pero no registra precio en euros."
        
    return f"No pude encontrar la carta '{nombre_limpio}' en Scryfall (Código HTTP: {respuesta.status_code}). Verifica el nombre en inglés."


@tool
def consultar_stock_local(nombre_carta: str) -> str:
    """Revisa en el archivo CSV de inventario local si hay stock físico disponible de una carta.

    Acepta el nombre en cualquier idioma y con errores de tipeo: antes de
    buscar lo traduce al nombre oficial en inglés. La comparación contra el
    CSV ignora acentos y puntuación, así una fila escrita sin la coma
    igual matchea.
    """
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")

    original = str(nombre_carta).strip()
    nombre_limpio = resolver_nombre(original) or original

    try:
        df = pd.read_csv(CSV_PATH)
        coincidencia = df[df['Carta'].map(_plano) == _plano(nombre_limpio)]
        
        if not coincidencia.empty:
            cantidad = int(coincidencia.iloc[0]['Cantidad'])
            edicion = coincidencia.iloc[0]['Edición']
            nombre_real = coincidencia.iloc[0]['Carta']
            if cantidad > 0:
                return f"Tenemos {cantidad} copias de '{nombre_real}' ({edicion}) en stock en la tienda."
            return f"Actualmente no nos queda stock de '{nombre_real}' ({edicion})."
        
        return f"La carta '{nombre_limpio}' no figura en nuestro inventario local."
    except Exception as e:
        return f"Error al acceder al inventario local: {str(e)}"

@tool
def consultar_datos_carta(nombre_carta: str) -> str:
    """Trae los datos reales de una carta: tipo, colores, coste, texto de reglas,
    rareza, en qué formatos es legal y cómo se llama en español.

    Usar SIEMPRE antes de afirmar cualquier característica de una carta. Es la
    única fuente válida para decir de qué tipo o color es algo.
    """
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")

    datos = ficha(str(nombre_carta).strip())
    if not datos:
        return f"No encontré ninguna carta llamada '{nombre_carta}' en Scryfall."

    partes = [f"Nombre oficial (inglés): {datos['nombre']}"]
    if datos.get("nombre_es"):
        partes.append(f"Nombre en español: {datos['nombre_es']}")
    if datos.get("coste"):
        partes.append(f"Coste de maná: {datos['coste']}")
    partes.append(f"Tipo: {datos['tipo']}")
    if datos.get("tipo_es"):
        partes.append(f"Tipo en español: {datos['tipo_es']}")
    partes.append(f"Colores: {', '.join(datos['colores']) if datos.get('colores') else 'incolora'}")
    if datos.get("fuerza_resistencia"):
        partes.append(f"Fuerza/Resistencia: {datos['fuerza_resistencia']}")
    if datos.get("texto"):
        partes.append(f"Texto de reglas: {datos['texto']}")
    if datos.get("texto_es"):
        partes.append(f"Texto en español: {datos['texto_es']}")
    partes.append(f"Rareza: {datos['rareza']}")
    if datos.get("legal_en"):
        partes.append(f"Legal en: {', '.join(datos['legal_en'])}")

    return "\n".join(partes)


lista_tools = [
    consultar_precio_cardmarket,
    consultar_stock_local,
    consultar_datos_carta,
    consultar_reglas_mtg,
    consultar_lore_mtg,
]