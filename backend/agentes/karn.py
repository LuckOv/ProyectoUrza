"""Subagente de visión por computadora: KARN, el gólem de ojos de plata.

Karn se encarga de:
1. Identificar cartas individuales a partir de una foto o imagen (cámara o archivo),
   traduciendo el nombre al oficial de Scryfall y consultando el stock local y precio en la tienda.
2. Analizar mesas de juego (battlefield) a partir de una foto de la partida,
   extrayendo permanentes, cartas giradas/enderezadas, contadores y recursos,
   y combinándose con Ajani (el juez de reglas) para validar jugadas o sugerir tácticas.
"""

import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from tienda import cartas, inventario

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MODELO_VISION = "gemini-2.5-flash"
_cliente_gemini = None


def _obtener_cliente():
    global _cliente_gemini
    load_dotenv(BASE_DIR / ".env", override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    if _cliente_gemini is None:
        try:
            from google import genai
            _cliente_gemini = genai.Client(api_key=api_key)
        except Exception:
            return None
    return _cliente_gemini


def _preparar_imagen_bytes(imagen_bytes: bytes, mime_type: str = "image/jpeg"):
    from google.genai import types
    return types.Part.from_bytes(data=imagen_bytes, mime_type=mime_type)


PROMPT_IDENTIFICAR_CARTA = """
Sos KARN, el gólem de ojos de plata del equipo de Urza, con visión de precisión sobre artefactos y cartas de Magic: The Gathering.
Analizá la foto de esta carta física de Magic.

Extraé con la mayor exactitud posible:
1. El nombre oficial de la carta en inglés (Card name).
2. Si está en español, el nombre impreso en español.
3. El set / edición (si ves el símbolo de expansión o el código de 3 letras al pie).
4. El grado o estado (si está en un encapsulado graduado como PSA, BGS, CGC, indicá ej. 'PSA 10', 'PSA 9', sino 'Sin graduar').

Respondé ÚNICAMENTE con un objeto JSON válido con este formato:
{
  "nombre_ingles": "Nombre oficial en inglés",
  "nombre_es": "Nombre en español si corresponde, o null",
  "set_codigo": "código de 3 letras en minúsculas si es legible, o null",
  "set_nombre": "nombre de la expansión si es legible, o null",
  "grado": "Sin graduar" o "PSA X",
  "confianza": "alta" o "media" o "baja",
  "detalles": "Una breve descripción de una oración en español rioplatense"
}
"""

PROMPT_ANALIZAR_MESA = """
Sos KARN, el gólem de ojos de plata. Poseés una vista panorámica y analítica del campo de batalla de Magic: The Gathering.
Analizá esta foto de la mesa de juego (partida en curso).

Identificá:
1. Permanentes en juego: tierras, criaturas, artefactos, encantamientos y planeswalkers visibles de cada jugador.
2. Estado de los permanentes: cuáles están enderezados (untapped) y cuáles girados (tapped / 90 grados).
3. Modificadores y contadores visibles: fichas (+1/+1), auras anexadas, cartas atacando o bloqueando.
4. Recursos y vida: dados de 20 caras (spindowns) o contadores de vidas si son legibles.

Consulta del jugador sobre la jugada: "{consulta}".

Devolvé un resumen técnico, claro y estructurado en español rioplatense describiendo la situación de la mesa para que el juez de reglas Ajani pueda dictaminar la legalidad de la jugada.
"""


def identificar_carta(imagen_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Identifica una carta a partir de su foto y consulta el stock en la tienda."""
    cliente = _obtener_cliente()
    if cliente is None:
        return {
            "exito": False,
            "error": "Karn necesita una clave de Gemini para ver la imagen. Configurá GEMINI_API_KEY en backend/.env.",
        }

    try:
        part_imagen = _preparar_imagen_bytes(imagen_bytes, mime_type)
        respuesta = cliente.models.generate_content(
            model=MODELO_VISION,
            contents=[part_imagen, PROMPT_IDENTIFICAR_CARTA],
        )
        texto = respuesta.text.strip()
        # Limpiar bloques de código markdown
        texto_limpio = re.sub(r"^```json\s*|^```\s*|```$", "", texto, flags=re.MULTILINE).strip()
        datos = json.loads(texto_limpio)
    except Exception as e:
        return {
            "exito": False,
            "error": f"Karn no pudo interpretar la foto: {e}",
        }

    nombre_detectado = datos.get("nombre_ingles") or datos.get("nombre_es") or ""
    oficial = cartas.resolver_nombre(nombre_detectado) or nombre_detectado

    # Consultar stock local en la base de datos de la tienda
    variantes = inventario.variantes_de(oficial) if oficial else []
    total_stock = sum(v["cantidad"] for v in variantes)
    ficha_carta = cartas.buscar(oficial) if oficial else None

    return {
        "exito": True,
        "nombre": oficial,
        "nombre_original": nombre_detectado,
        "set_codigo": datos.get("set_codigo"),
        "grado": datos.get("grado", "Sin graduar"),
        "detalles": datos.get("detalles", ""),
        "en_stock": total_stock > 0,
        "unidades_stock": total_stock,
        "variantes": variantes,
        "carta": ficha_carta,
    }


def analizar_mesa_y_jugada(imagen_bytes: bytes, consulta: str, mime_type: str = "image/jpeg") -> dict:
    """Analiza la mesa de juego completa y consulta las reglas oficiales con Ajani."""
    cliente = _obtener_cliente()
    if cliente is None:
        return {
            "exito": False,
            "error": "Karn necesita una clave de Gemini para ver la mesa. Configurá GEMINI_API_KEY en backend/.env.",
        }

    prompt_mesa = PROMPT_ANALIZAR_MESA.format(consulta=consulta or "Revisá si la jugada actual es válida y qué opciones hay.")

    try:
        part_imagen = _preparar_imagen_bytes(imagen_bytes, mime_type)
        respuesta_karn = cliente.models.generate_content(
            model=MODELO_VISION,
            contents=[part_imagen, prompt_mesa],
        )
        analisis_mesa = respuesta_karn.text.strip()
    except Exception as e:
        return {
            "exito": False,
            "error": f"Karn no pudo procesar la foto de la mesa: {e}",
        }

    # Ahora consultamos al juez Ajani pasando el estado de la mesa + la duda del jugador
    from agentes.reglas import consultar_reglas_mtg
    pregunta_para_ajani = (
        f"Situación del campo de batalla observada por Karn:\n{analisis_mesa}\n\n"
        f"Pregunta del jugador sobre la jugada:\n{consulta}"
    )
    dictamen_ajani = consultar_reglas_mtg.invoke(pregunta_para_ajani)

    return {
        "exito": True,
        "analisis_mesa": analisis_mesa,
        "dictamen_reglas": dictamen_ajani,
    }
