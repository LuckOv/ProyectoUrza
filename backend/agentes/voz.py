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


def transcribir_audio(audio_bytes: bytes, filename: str = "audio.ogg", mime_type: str = "audio/ogg") -> str:
    """Transcribe un buffer de audio a texto en español.

    Intenta primero con Groq Whisper Large v3; si falla, utiliza Gemini 2.5 Flash.
    Retorna el texto transcrito o una cadena vacía si no se pudo interpretar.
    """
    if not audio_bytes:
        return ""

    # --- 1. INTENTO CON GROQ WHISPER ---
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq

            client = Groq(api_key=groq_key)
            buffer = io.BytesIO(audio_bytes)
            buffer.name = filename

            transcription = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model="whisper-large-v3",
                language="es",
                response_format="text",
                temperature=0.0,
            )
            texto = str(transcription).strip()
            if texto:
                logger.info(f"[URZA VOZ] Transcripción exitosa con Groq Whisper: {texto[:60]}...")
                return texto
        except Exception as e:
            logger.warning(f"[URZA VOZ] Falló transcripción con Groq Whisper: {e}. Probando Gemini Flash...")

    # --- 2. INTENTO CON GEMINI FLASH (FALLBACK) ---
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            prompt = (
                "Sos el transcriptor de voz de la tienda de Magic: The Gathering 'The Deckwarden' y del asistente Urza. "
                "Escuchá atentamente este mensaje de audio en español y transcribí de forma exacta y literal lo que dice la persona. "
                "Los nombres de cartas, reglas o formatos de Magic deben escribirse correctamente (ej. Llanowar Elves, Black Lotus, "
                "Commander, Deathtouch, Trample, Modern, etc.). "
                "Devolvé ÚNICAMENTE el texto transcripto, sin explicaciones ni notas adicionales."
            )

            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type or "audio/ogg",
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, audio_part],
            )
            texto = (response.text or "").strip()
            if texto:
                logger.info(f"[URZA VOZ] Transcripción exitosa con Gemini Flash: {texto[:60]}...")
                return texto
        except Exception as e:
            logger.error(f"[URZA VOZ] Falló transcripción con Gemini Flash: {e}")

    return ""
