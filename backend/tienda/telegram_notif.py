"""Integración con Telegram para URZA: mensajería, avisos al dueño y descarga de fotos.

Maneja la comunicación saliente hacia la API de Telegram:
- Envío de texto y fotos a usuarios o grupos.
- Notificaciones automáticas al dueño de la tienda (pedidos y propuestas).
- Descarga de fotos enviadas por usuarios para que Karn las examine.
- Funciona de forma segura: si TELEGRAM_BOT_TOKEN no está configurado, las notificaciones
  se omiten silenciosamente sin frenar la ejecución de la tienda.
"""

import logging
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("urza.telegram")


def token_bot() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def owner_id() -> str:
    return os.environ.get("TELEGRAM_OWNER_ID", "").strip()


def grupo_id() -> str:
    return os.environ.get("TELEGRAM_GRUPO_ID", "").strip()


def esta_configurado() -> bool:
    return bool(token_bot())


def url_api(metodo: str) -> str:
    return f"https://api.telegram.org/bot{token_bot()}/{metodo}"


def enviar_mensaje(chat_id: int | str, texto: str, parse_mode: str = "Markdown", disable_preview: bool = True) -> bool:
    """Envía un mensaje de texto a un chat o grupo de Telegram."""
    tok = token_bot()
    if not tok or not chat_id:
        return False

    payload = {
        "chat_id": str(chat_id),
        "text": texto,
        "disable_web_page_preview": disable_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(url_api("sendMessage"), json=payload, timeout=8)
        if not r.ok and parse_mode:
            # Reintento sin formato por si algún caracter de Markdown falló
            payload.pop("parse_mode", None)
            r = requests.post(url_api("sendMessage"), json=payload, timeout=8)
        return r.ok
    except Exception as e:
        logger.warning(f"No se pudo enviar mensaje a Telegram ({chat_id}): {e}")
        return False


def enviar_foto(chat_id: int | str, foto: bytes | str, caption: str = "", parse_mode: str = "Markdown") -> bool:
    """Envía una foto (por URL pública o bytes directos en memoria)."""
    tok = token_bot()
    if not tok or not chat_id:
        return False

    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode

    try:
        if isinstance(foto, str) and (foto.startswith("http://") or foto.startswith("https://")):
            data["photo"] = foto
            r = requests.post(url_api("sendPhoto"), data=data, timeout=12)
        else:
            files = {"photo": ("carta.jpg", foto, "image/jpeg")}
            r = requests.post(url_api("sendPhoto"), data=data, files=files, timeout=15)
        return r.ok
    except Exception as e:
        logger.warning(f"No se pudo enviar foto a Telegram ({chat_id}): {e}")
        return False


def descargar_foto(file_id: str) -> tuple[bytes, str] | None:
    """Descarga los bytes de una foto recibida por Telegram a partir de su file_id."""
    return descargar_archivo(file_id)


def descargar_archivo(file_id: str) -> tuple[bytes, str] | None:
    """Descarga los bytes de cualquier archivo (foto, voz, audio) desde Telegram usando getFile.
    Retorna (bytes, mime_type) o None si falla."""
    tok = token_bot()
    if not tok or not file_id:
        return None

    try:
        r_info = requests.get(url_api("getFile"), params={"file_id": file_id}, timeout=8)
        if not r_info.ok:
            return None
        file_path = r_info.json().get("result", {}).get("file_path")
        if not file_path:
            return None

        url_descarga = f"https://api.telegram.org/file/bot{tok}/{file_path}"
        r_file = requests.get(url_descarga, timeout=20)
        if not r_file.ok:
            return None

        fl = file_path.lower()
        if fl.endswith(".png"):
            mime = "image/png"
        elif fl.endswith(".webp"):
            mime = "image/webp"
        elif fl.endswith(".ogg") or fl.endswith(".oga"):
            mime = "audio/ogg"
        elif fl.endswith(".mp3"):
            mime = "audio/mp3"
        elif fl.endswith(".wav"):
            mime = "audio/wav"
        elif fl.endswith(".m4a"):
            mime = "audio/m4a"
        else:
            mime = "image/jpeg"

        return r_file.content, mime
    except Exception as e:
        logger.warning(f"Error descargando archivo {file_id} de Telegram: {e}")
        return None


def notificar_dueno(texto: str, parse_mode: str = "Markdown") -> bool:
    """Envía una notificación directa al chat personal del dueño."""
    oid = owner_id()
    if not oid:
        return False
    return enviar_mensaje(oid, texto, parse_mode=parse_mode)


def notificar_pedido(pedido: dict) -> bool:
    """Avisa al dueño que se confirmó un nuevo pedido en la tienda."""
    if not owner_id() or not pedido:
        return False

    items = pedido.get("items") or []
    lineas_items = []
    for it in items:
        lineas_items.append(f"• {it.get('cantidad', 1)}x *{it.get('nombre', 'Carta')}* ({it.get('grado', 'Sin graduar')})")

    detalle_items = "\n".join(lineas_items) if lineas_items else "• (Sin detalle de items)"

    mensaje = (
        f"🛒 *¡NUEVO PEDIDO #{pedido.get('id', '?')}!*\n\n"
        f"👤 *Cliente:* {pedido.get('nombre', '')} {pedido.get('apellido', '')}\n"
        f"📅 *Retiro:* {pedido.get('fecha_retiro', '')} a las {pedido.get('hora_retiro', '')} hs\n"
        f"💰 *Total:* ${pedido.get('total', 0):,.0f} ARS\n"
        f"📋 *Items:*\n{detalle_items}\n\n"
        f"ℹ️ _Revisalo en Mesa Central o respondé /pedidos para ver los pendientes._"
    )
    return notificar_dueno(mensaje)


def notificar_propuesta(propuesta: dict) -> bool:
    """Avisa al dueño que un cliente ofreció una carta a la tienda."""
    if not owner_id() or not propuesta:
        return False

    mensaje = (
        f"📬 *¡NUEVA PROPUESTA DE VENTA RECIBIDA!*\n\n"
        f"👤 *Cliente:* {propuesta.get('nombre', '')} {propuesta.get('apellido', '')}\n"
        f"✉️ *Contacto:* {propuesta.get('email', '')}\n"
        f"🃏 *Carta:* *{propuesta.get('carta', 'Desconocida')}* ({propuesta.get('grado', 'Sin graduar')})\n"
        f"📦 *Cantidad:* {propuesta.get('cantidad', 1)} copia(s)\n"
        f"💵 *Pide:* {propuesta.get('moneda', 'ARS')} ${propuesta.get('precio', 0):,.2f}\n\n"
        f"ℹ️ _Entrá a Mesa Central -> Propuestas para aceptarla o rechazarla._"
    )
    return notificar_dueno(mensaje)


def notificar_inicio(bot_username: str) -> bool:
    """Envía un saludo y aviso de que el bot está activo al dueño y al grupo."""
    ok = True
    oid = owner_id()
    if oid:
        mensaje_dueno = (
            f"🟢 *URZA ONLINE* (@{bot_username})\n\n"
            f"El asistente de la tienda y bot de Telegram ya está operativo y escuchando en tu PC local.\n\n"
            f"• Respondé `/ping` para verificar conectividad.\n"
            f"• Respondé `/ventas` o `/ayuda` para ver opciones de dueño."
        )
        ok = enviar_mensaje(oid, mensaje_dueno)

    gid = grupo_id()
    if gid:
        mensaje_grupo = (
            f"🧙‍♂️ *URZA está en línea* (@{bot_username})\n\n"
            f"¡Saludos! El asistente de la tienda ya está activo y listo para responder preguntas de stock, "
            f"reglas de juego (Ajani), lore (Teferi), armado de mazos (Saheeli) y fotos de cartas o jugadas (Karn)."
        )
        enviar_mensaje(gid, mensaje_grupo)
    return ok


def notificar_detencion() -> bool:
    """Avisa al dueño y al grupo que el bot se detuvo."""
    ok = True
    oid = owner_id()
    if oid:
        ok = enviar_mensaje(oid, "🔴 *URZA DESCONECTADO:* El servicio local de Telegram se ha detenido.")
    gid = grupo_id()
    if gid:
        enviar_mensaje(gid, "💤 *URZA fuera de línea:* El servicio local se ha detenido.")
    return ok

