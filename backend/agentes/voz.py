"""Módulo de procesamiento y transcripción de voz a texto (STT) para URZA.

Implementa un doble motor de transcripción:
1. Primario (Ultrarrápido): Groq Whisper Large v3 (mediante el SDK oficial de Groq).
2. Respaldo (Tolerante / Especializado en MTG): Google Gemini 2.5 Flash (vía google-genai).
"""

import io
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("urza.voz")


# Prompt especializado de contexto para guiar el reconocimiento fonético hacia el universo de Magic
MTG_AUDIO_PROMPT = (
    "Magic: The Gathering, MTG, cartas, Llanowar Elves, Elfos de Llanowar, Cavern of Souls, "
    "Black Lotus, Sol Ring, Sheoldred, The One Ring, Mana Crypt, Mox, dual lands, Commander, "
    "Modern, Standard, Pioneer, Pauper, Deathtouch, Trample, Flying, Haste, Counterspell, "
    "Urza, Karn, Ajani, Teferi, Saheeli, Tibalt, planeswalker, criatura, conjuro, instantáneo, "
    "cementerio, exilio, stack, fase de combate, tapping, turno, stock, precio, pesos, dólares."
)


def corregir_terminos_mtg(texto: str) -> str:
    """Corrige posibles deformaciones fonéticas de nombres de cartas o términos de MTG en el texto transcripto."""
    if not texto or len(texto.strip()) < 3:
        return texto

    try:
        from agentes.agent_sales import _obtener_llm, sin_razonamiento

        llm = _obtener_llm()
        prompt_correccion = (
            "Sos el normalizador fonético de una tienda de Magic: The Gathering. "
            "El siguiente texto fue transcripto desde un audio de un jugador en español. "
            "Corregí únicamente aquellos nombres de cartas, personajes, mecánicas o términos de Magic "
            "que hayan sido mal escuchados o deformados fonéticamente (por ejemplo: "
            "'elfos de xanowar' -> 'Elfos de Llanowar', 'cavern of souls' -> 'Cavern of Souls', "
            "'tres arboles' -> 'Three Tree City', 'llanowar elfs' -> 'Llanowar Elves', 'blak lotus' -> 'Black Lotus'). "
            "Mantené el resto de la frase exactamente igual. "
            "Respondé ÚNICAMENTE con la frase corregida, sin comillas, sin explicaciones ni razonamiento.\n\n"
            f"Texto: {texto}"
        )
        respuesta = llm.invoke(prompt_correccion).content
        texto_limpio = sin_razonamiento(str(respuesta)).strip()
        if texto_limpio:
            return texto_limpio
    except Exception as e:
        logger.warning(f"[URZA VOZ] No se pudo ejecutar post-corrección MTG: {e}")

    return texto


def transcribir_audio(audio_bytes: bytes, filename: str = "audio.ogg", mime_type: str = "audio/ogg") -> str:
    """Transcribe un buffer de audio a texto en español y aplica normalización de términos MTG.

    Intenta primero con Groq Whisper Large v3 (con prompt de contexto de MTG);
    si falla, utiliza Gemini 2.5 Flash. Luego aplica una pasada de refinamiento fonético.
    """
    if not audio_bytes:
        return ""

    texto_transcrito = ""

    # --- 1. INTENTO CON GROQ WHISPER ---
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq

            client = Groq(api_key=groq_key)

            transcription = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model="whisper-large-v3",
                language="es",
                prompt=MTG_AUDIO_PROMPT,
                response_format="text",
                temperature=0.0,
            )
            raw = str(transcription).strip()
            if raw:
                logger.info(f"[URZA VOZ] Transcripción exitosa con Groq Whisper: {raw[:60]}...")
                texto_transcrito = raw
        except Exception as e:
            logger.warning(f"[URZA VOZ] Falló transcripción con Groq Whisper: {e}. Probando Gemini Flash...")

    # --- 2. INTENTO CON GEMINI FLASH (FALLBACK) ---
    if not texto_transcrito:
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if gemini_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_key)
                prompt = (
                    "Sos el transcriptor de voz de la tienda de Magic: The Gathering 'The Deckwarden' y del asistente Urza. "
                    "Escuchá atentamente este mensaje de audio en español y transcribí de forma exacta lo que dice la persona. "
                    "Es fundamental reconocer los nombres de cartas y términos de Magic: The Gathering con su escritura correcta "
                    "(por ejemplo: Llanowar Elves / Elfos de Llanowar, Cavern of Souls, Black Lotus, Sol Ring, Heartfire Hero, Three Tree City, "
                    "Commander, Deathtouch, Trample, Modern, etc.). "
                    "Devolvé ÚNICAMENTE el texto transcripto, sin introducciones ni notas."
                )

                audio_part = types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime_type or "audio/ogg",
                )

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, audio_part],
                )
                raw = (response.text or "").strip()
                if raw:
                    logger.info(f"[URZA VOZ] Transcripción exitosa con Gemini Flash: {raw[:60]}...")
                    texto_transcrito = raw
            except Exception as e:
                logger.error(f"[URZA VOZ] Falló transcripción con Gemini Flash: {e}")

    if not texto_transcrito:
        return ""

    # --- 3. REFINAMIENTO FONÉTICO MTG ---
    texto_final = corregir_terminos_mtg(texto_transcrito)
    logger.info(f"[URZA VOZ] Texto final post-corrección: {texto_final}")
    return texto_final
