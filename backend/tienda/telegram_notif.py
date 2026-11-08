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
import requests

logger = logging.getLogger("urza.telegram")


def token_bot() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def owner_id() -> str:
    return os.environ.get("TELEGRAM_OWNER_ID", "").strip()


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
        r_file = requests.get(url_descarga, timeout=15)
        if not r_file.ok:
            return None

        mime = "image/jpeg"
        if file_path.lower().endswith(".png"):
            mime = "image/png"
        elif file_path.lower().endswith(".webp"):
            mime = "image/webp"

        return r_file.content, mime
    except Exception as e:
        logger.warning(f"Error descargando foto {file_id} de Telegram: {e}")
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
