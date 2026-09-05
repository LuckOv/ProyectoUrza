import urllib.parse
import pandas as pd
import requests
from langchain_core.tools import tool

CSV_PATH = "inventario.csv"

# Cabecera obligatoria que exige la API de Scryfall para no bloquear la petición
HEADERS = {
    "User-Agent": "UrzaBot/1.0 (ProyectoEstudiantilISFT197)",
    "Accept": "application/json"
}

@tool
def consultar_precio_cardmarket(nombre_carta: str) -> str:
    """Consulta el precio actual de una carta en euros usando la API de Scryfall."""
    # Extraer el valor si viene empacado como dict
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")
    
    nombre_limpio = str(nombre_carta).strip()
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
    """Revisa en el archivo CSV de inventario local si hay stock físico disponible de una carta."""
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")
        
    nombre_limpio = str(nombre_carta).strip().lower()
    
    try:
        df = pd.read_csv(CSV_PATH)
        coincidencia = df[df['Carta'].str.lower() == nombre_limpio]
        
        if not coincidencia.empty:
            cantidad = int(coincidencia.iloc[0]['Cantidad'])
            edicion = coincidencia.iloc[0]['Edición']
            nombre_real = coincidencia.iloc[0]['Carta']
            if cantidad > 0:
                return f"Tenemos {cantidad} copias de '{nombre_real}' ({edicion}) en stock en la tienda."
            return f"Actualmente no nos queda stock de '{nombre_real}' ({edicion})."
        
        return f"La carta '{nombre_carta}' no figura en nuestro inventario local."
    except Exception as e:
        return f"Error al acceder al inventario local: {str(e)}"

lista_tools = [consultar_precio_cardmarket, consultar_stock_local]