"""Comando de Django para iniciar el bot de Telegram de URZA en Long Polling.

Uso:
    python manage.py run_telegram_bot

Funcionalidades:
- Long Polling saliente: funciona en tu PC local sin necesidad de IP pública ni ngrok.
- Charla con jugadores en privado o en grupos (etiquetando a @UrzaBot).
- Visión por computadora con Karn: recibe fotos de cartas para stock o fotos de mesa para jugadas.
- Modo Dueño móvil: comandos ejecutivos (/ventas, /pedidos, /alertas) exclusivos para el dueño.
"""

import logging
import sys
import threading
import time
import requests
from django.core.management.base import BaseCommand
from langchain_core.messages import HumanMessage

from agentes.agent_sales import sin_razonamiento
from agentes.graph import app_graph
from agentes import karn
from tienda import admin_reportes, cartas, telegram_notif

logger = logging.getLogger("urza.telegram")

_bot_corriendo = False
_hilo_bot = None

# Memoria de ventanas de conversación activas en grupos:
# Guarda la marca de tiempo (time.time()) del último intercambio con un usuario en un grupo:
# key: (chat_id, user_id) -> float (timestamp)
_ultimas_interacciones_grupo: dict[tuple[int | str, str], float] = {}
VENTANA_CONVERSACION_SEGUNDOS = 180  # 3 minutos de conversación fluida sin necesidad de mencionar


def iniciar_bot_background():
    """Inicia el bot en un hilo secundario (usado por Django runserver)."""
    global _bot_corriendo, _hilo_bot
    if _bot_corriendo:
        return
    _bot_corriendo = True
    _hilo_bot = threading.Thread(target=_bucle_polling, kwargs={"background": True}, daemon=True)
    _hilo_bot.start()


def _bucle_polling(stdout=None, background=False):
    global _bot_corriendo
    _bot_corriendo = True

    token = telegram_notif.token_bot()
    owner_id = telegram_notif.owner_id()

    try:
        r = requests.get(telegram_notif.url_api("getMe"), timeout=10)
        if not r.ok:
            msg = f"[URZA TELEGRAM] Token inválido: {r.text}"
            if stdout:
                stdout.write(msg)
            logger.error(msg)
            _bot_corriendo = False
            return
        bot_info = r.json().get("result", {})
        bot_username = bot_info.get("username", "UrzaBot")
    except Exception as e:
        msg = f"[URZA TELEGRAM] Error conectando con Telegram: {e}"
        if stdout:
            stdout.write(msg)
        logger.error(msg)
        _bot_corriendo = False
        return

    banner = (
        f"\n=======================================================\n"
        f"  URZA TELEGRAM BOT ACTIVO (@{bot_username})\n"
        f"  Modo: Long Polling (PC Local{' - AutoStart' if background else ''})\n"
        f"  Dueño ID: {owner_id or '(No configurado)'}\n"
        f"  Presioná Ctrl+C para detener.\n"
        f"=======================================================\n"
    )
    if stdout:
        stdout.write(banner)
    else:
        print(banner, flush=True)

    # Registrar los comandos oficiales en el menú nativo de Telegram (botón [/] o menú emergente)
    try:
        comandos_menu = [
            {"command": "comandos", "description": "Ver qué puede hacer Urza y cómo consultarle"},
            {"command": "ayuda", "description": "Guía rápida de interacciones y ejemplos"},
            {"command": "ping", "description": "Comprobar si el bot está activo en local"},
            {"command": "estado", "description": "Ver estado del servidor y base de datos"},
        ]
        requests.post(telegram_notif.url_api("setMyCommands"), json={"commands": comandos_menu}, timeout=5)
    except Exception as e:
        logger.warning(f"No se pudieron registrar comandos de Telegram: {e}")

    # Enviar saludo inicial al dueño y al grupo para confirmar que está operativo
    try:
        telegram_notif.notificar_inicio(bot_username)
    except Exception as e:
        logger.warning(f"No se pudo enviar notificación de inicio: {e}")

    cmd_handler = Command()
    offset = 0

    try:
        while _bot_corriendo:
            try:
                params = {"offset": offset, "timeout": 25}
                r = requests.get(telegram_notif.url_api("getUpdates"), params=params, timeout=30)
                if not r.ok:
                    time.sleep(2)
                    continue

                updates = r.json().get("result", [])
                for u in updates:
                    offset = max(offset, u["update_id"] + 1)
                    cmd_handler.procesar_update(u, bot_username, owner_id)

            except requests.exceptions.RequestException:
                time.sleep(3)
            except Exception as e:
                logger.error(f"[URZA TELEGRAM] Error en bucle: {e}")
                time.sleep(2)
    finally:
        try:
            telegram_notif.notificar_detencion()
        except Exception:
            pass
        _bot_corriendo = False


class Command(BaseCommand):
    help = "Inicia el bot de Telegram de URZA mediante Long Polling."

    def handle(self, *args, **options):
        if not telegram_notif.esta_configurado():
            self.stdout.write(self.style.ERROR(
                "\n[URZA TELEGRAM] Error: TELEGRAM_BOT_TOKEN no está configurado en backend/.env\n"
                "1. Creá tu bot con @BotFather en Telegram para obtener el token.\n"
                "2. Agregalo a backend/.env: TELEGRAM_BOT_TOKEN=...\n"
                "3. Agregá tu ID personal: TELEGRAM_OWNER_ID=...\n"
            ))
            return

        try:
            _bucle_polling(stdout=self.stdout, background=False)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n[URZA TELEGRAM] Bot detenido por el usuario."))

    def enviar_accion(self, chat_id: int | str, action: str = "typing"):
        try:
            requests.post(telegram_notif.url_api("sendChatAction"), json={"chat_id": str(chat_id), "action": action}, timeout=4)
        except Exception:
            pass

    def procesar_update(self, u: dict, bot_username: str, owner_id: str):
        msg = u.get("message") or u.get("edited_message")
        if not msg:
            return

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        from_user = msg.get("from", {})
        user_id = str(from_user.get("id", ""))
        user_name = from_user.get("first_name", "Jugador")
        texto_raw = (msg.get("text") or "").strip()
        caption = (msg.get("caption") or "").strip()
        photos = msg.get("photo") or []

        es_dueno = bool(owner_id and user_id == str(owner_id) and chat_type == "private")

        # --- A. FOTOS RECIBIDAS (Subagente Karn) ---
        if photos:
            if chat_type in ("group", "supergroup"):
                mencion_oficial = f"@{bot_username.lower()}"
                alias_comunes = ["@urza", "@urzabot", "@urzatiendabot", "@urzamtgbot"]
                caption_lower = caption.lower()
                reply_msg = msg.get("reply_to_message", {})
                reply_from = reply_msg.get("from", {})
                es_reply_al_bot = bool(
                    reply_from.get("is_bot")
                    and (
                        reply_from.get("username", "").lower() == bot_username.lower()
                        or "urza" in reply_from.get("username", "").lower()
                        or "urza" in reply_from.get("first_name", "").lower()
                    )
                )

                ahora = time.time()
                clave_interaccion = (chat_id, user_id)
                ultimo_contacto = _ultimas_interacciones_grupo.get(clave_interaccion, 0.0)
                en_dialogo_activo = (ahora - ultimo_contacto) <= VENTANA_CONVERSACION_SEGUNDOS

                fue_mencionado = (
                    mencion_oficial in caption_lower
                    or any(alias in caption_lower for alias in alias_comunes)
                    or caption_lower.startswith("karn")
                    or caption_lower.startswith("urza")
                    or es_reply_al_bot
                    or en_dialogo_activo
                )
                if not fue_mencionado:
                    return

                _ultimas_interacciones_grupo[clave_interaccion] = ahora

                import re
                caption = (
                    caption
                    .replace(f"@{bot_username}", "")
                    .replace(f"@{bot_username.lower()}", "")
                )
                for alias in alias_comunes:
                    caption = re.sub(re.escape(alias), "", caption, flags=re.IGNORECASE)
                caption = re.sub(r"^\s*(urza|karn)\s*[:,]?\s*", "", caption, flags=re.IGNORECASE).strip()

            self.enviar_accion(chat_id, "typing")
            self.procesar_foto(chat_id, photos, caption, user_name)
            return

        # --- B. MENSAJES DE TEXTO ---
        if not texto_raw:
            return

        # En grupos, responder si:
        # 1. Mencionan al bot (@UrzaTiendaBot, @urza, etc.) o arranca con "Urza"
        # 2. Le responden directo (Reply / Responder mensaje)
        # 3. Es un comando (/ping, /start, etc.)
        # 4. Hay una conversación activa en curso con ese usuario (ventana de 3 minutos tras el último turno)
        if chat_type in ("group", "supergroup"):
            mencion_oficial = f"@{bot_username.lower()}"
            alias_comunes = ["@urza", "@urzabot", "@urzatiendabot", "@urzamtgbot"]
            reply_msg = msg.get("reply_to_message", {})
            reply_from = reply_msg.get("from", {})
            # Detecta si el reply es a un bot o específicamente a Urza (por username o bot_id)
            es_reply_al_bot = bool(
                reply_from.get("is_bot")
                and (
                    reply_from.get("username", "").lower() == bot_username.lower()
                    or "urza" in reply_from.get("username", "").lower()
                    or "urza" in reply_from.get("first_name", "").lower()
                )
            )
            texto_lower = texto_raw.lower()

            ahora = time.time()
            clave_interaccion = (chat_id, user_id)
            ultimo_contacto = _ultimas_interacciones_grupo.get(clave_interaccion, 0.0)
            en_dialogo_activo = (ahora - ultimo_contacto) <= VENTANA_CONVERSACION_SEGUNDOS

            fue_mencionado = (
                mencion_oficial in texto_lower
                or any(alias in texto_lower for alias in alias_comunes)
                or texto_lower.startswith("urza")
                or es_reply_al_bot
                or texto_raw.startswith("/")
                or en_dialogo_activo
            )

            if not fue_mencionado:
                return

            # Actualizar marca de tiempo de la interacción activa
            _ultimas_interacciones_grupo[clave_interaccion] = ahora

            # Limpiar mención del texto para pasárselo limpio al agente
            texto_raw = (
                texto_raw
                .replace(f"@{bot_username}", "")
                .replace(f"@{bot_username.lower()}", "")
            )
            for alias in alias_comunes:
                # Reemplazo insensible a mayúsculas
                import re
                texto_raw = re.sub(re.escape(alias), "", texto_raw, flags=re.IGNORECASE)

            # Si empezó con "Urza," o "Urza:", limpiarlo también
            import re
            texto_raw = re.sub(r"^\s*urza\s*[:,]?\s*", "", texto_raw, flags=re.IGNORECASE).strip()

        # Comandos administrativos exclusivos para el dueño
        if es_dueno and texto_raw.startswith("/"):
            cmd = texto_raw.split()[0].lower()
            if cmd == "/ventas":
                telegram_notif.enviar_mensaje(chat_id, admin_reportes.resumen_ventas())
                return
            elif cmd == "/pedidos":
                telegram_notif.enviar_mensaje(chat_id, admin_reportes.resumen_pedidos_pendientes())
                return
            elif cmd == "/alertas":
                telegram_notif.enviar_mensaje(chat_id, admin_reportes.resumen_alertas())
                return
            elif cmd in ("/help", "/ayuda", "/start"):
                ayuda_admin = (
                    f"👑 *¡Hola {user_name}! Modo Dueño / Vendedor de URZA.*\n\n"
                    f"Comandos ejecutivos disponibles:\n"
                    f"• `/ventas`: Resumen de facturación (hoy, 7d, 30d).\n"
                    f"• `/pedidos`: Pedidos pendientes de retiro.\n"
                    f"• `/alertas`: Cartas con stock bajo o desfasajes de precio.\n\n"
                    f"También podés hacerme consultas en lenguaje natural o mandarme fotos de cartas."
                )
                telegram_notif.enviar_mensaje(chat_id, ayuda_admin)
                return

        # Comprobación rápida de conectividad / ping (abierto a todos)
        if texto_raw.lower() in ("/ping", "ping"):
            telegram_notif.enviar_mensaje(chat_id, "🏓 *¡Pong!* URZA está 100% activo y operativo en tu PC local.")
            return

        if texto_raw.lower() in ("/estado", "estado"):
            from tienda import base
            estado_msg = (
                f"⚡ *ESTADO DEL SERVICIO URZA*\n\n"
                f"• *Bot Telegram:* 🟢 En línea (@{bot_username})\n"
                f"• *Servidor:* PC Local\n"
                f"• *Hora del servidor:* {base.ahora().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"• *Base de datos:* Conectada y lista\n"
            )
            telegram_notif.enviar_mensaje(chat_id, estado_msg)
            return

        # Comandos básicos de bienvenida / ayuda / vacío
        if not texto_raw or texto_raw.lower() in (
            "/start", "/help", "/ayuda", "/comandos", "comandos", "ayuda", "help", "hola", "buenas", "buenas tardes", "buen dia"
        ):
            bienvenida = (
                f"🧙‍♂️ *¡Saludos, {user_name}! Soy Urza, el artífice supremo de la tienda.*\n\n"
                f"Podés hablarme naturalmente o pedirme lo que necesites en el grupo o por privado. Acá tenés mis principales habilidades:\n\n"
                f"📦 *Stock y Precios de la tienda:*\n"
                f"• _\"¿Tenés Cavern of Souls?\"_\n"
                f"• _\"¿Cuánto sale un Llanowar Elves?\"_\n\n"
                f"⚖️ *Reglas Oficiales (Juez Ajani):*\n"
                f"• _\"¿Cómo funciona Deathtouch con Trample?\"_\n"
                f"• _\"¿Puedo responder al trigger de una Fetchland?\"_\n\n"
                f"📜 *Historia y Lore (Erudito Teferi):*\n"
                f"• _\"¿Quién fue Yawgmoth?\"_\n"
                f"• _\"Contame la caída de Phyrexia\"_\n\n"
                f"🛠️ *Armado de Mazos (Artífice Saheeli):*\n"
                f"• _\"Recomendame cartas rojas agresivas en stock\"_\n"
                f"• _\"¿Qué le puedo cortar a mi mazo Commander?\"_\n\n"
                f"👁️ *Visión y Análisis (Golem Karn):*\n"
                f"• Mandame una *foto de una carta* para cotizarla y ver stock.\n"
                f"• Mandame una *foto del campo de batalla* con tu duda para que Ajani y yo arbitremos la jugada.\n\n"
                f"💡 *Tip:* En el grupo podés mencionarme como `@{bot_username}` o responder a cualquiera de mis mensajes."
            )
            telegram_notif.enviar_mensaje(chat_id, bienvenida)
            return

        # Procesar con el grafo de Urza (LangGraph)
        self.enviar_accion(chat_id, "typing")
        thread_id = f"tg_{chat_id}"

        try:
            resultado = app_graph.invoke(
                {"messages": [HumanMessage(content=texto_raw)]},
                config={"configurable": {"thread_id": thread_id}},
            )
            mensajes = resultado.get("messages", [])
            texto_respuesta = ""
            if mensajes:
                texto_respuesta = sin_razonamiento(mensajes[-1].content)

            if not texto_respuesta:
                texto_respuesta = "No pude procesar tu mensaje en este momento. Probá reformularlo."

            telegram_notif.enviar_mensaje(chat_id, texto_respuesta)

        except Exception as e:
            telegram_notif.enviar_mensaje(chat_id, f"Hubo un error al procesar tu consulta con Urza: {e}")

    def procesar_foto(self, chat_id: int | str, photos: list, caption: str, user_name: str):
        # Tomar la foto de mayor tamaño
        foto_grande = photos[-1]
        file_id = foto_grande.get("file_id")

        telegram_notif.enviar_mensaje(chat_id, "👁️ *Karn está analizando la imagen...*")

        descarga = telegram_notif.descargar_foto(file_id)
        if not descarga:
            telegram_notif.enviar_mensaje(chat_id, "No pude descargar la imagen de los servidores de Telegram. Probá enviarla de nuevo.")
            return

        img_bytes, mime = descarga

        # Discriminar según el texto del pie de foto si es una mesa de juego o una carta
        palabras_mesa = {"mesa", "jugada", "regla", "ataque", "valida", "válida", "bloqueo", "prioridad", "puedo", "cementerio"}
        es_mesa = any(p in caption.lower() for p in palabras_mesa)

        if es_mesa:
            res_mesa = karn.analizar_mesa_y_jugada(img_bytes, mime, consulta_jugador=caption or "¿Qué jugadas son válidas?")
            if not res_mesa.get("exito"):
                telegram_notif.enviar_mensaje(chat_id, f"Karn no pudo analizar el campo de batalla: {res_mesa.get('error')}")
                return

            mensaje = (
                f"⚔️ *DICTAMEN DE JUGADA Y CAMPO DE BATALLA (Karn + Ajani)*\n\n"
                f"🏛️ *Permanentes visibles:*\n{res_mesa.get('permanentes', 'No identificados')}\n\n"
                f"⚖️ *Veredicto del Juez Ajani:*\n{res_mesa.get('dictamen', '')}"
            )
            telegram_notif.enviar_mensaje(chat_id, mensaje)

        else:
            # Identificación de carta y stock
            res_carta = karn.identificar_carta(img_bytes, mime)
            if not res_carta.get("exito"):
                telegram_notif.enviar_mensaje(chat_id, f"Karn no pudo identificar la carta: {res_carta.get('error', 'Imagen poco clara.')}")
                return

            nombre = res_carta["nombre"]
            set_cod = res_carta.get("set_codigo") or "s/set"
            grado = res_carta.get("grado", "Sin graduar")

            if res_carta["en_stock"]:
                vars_info = []
                for v in res_carta["variantes"]:
                    vars_info.append(f"• *{v['set_nombre']}* ({v['grado']}): ${v['precio_ars']:,.0f} — {v['cantidad']} u.")
                detalles_stock = "\n".join(vars_info)

                mensaje = (
                    f"🤖 *Karn ha reconocido la carta:*\n"
                    f"Es *{nombre}* ({set_cod.upper()}, {grado}).\n\n"
                    f"📦 *¡Tenemos stock en la tienda URZA!*\n"
                    f"{detalles_stock}\n\n"
                    f"¿Querés que te reservemos alguna copia?"
                )
            else:
                mensaje = (
                    f"🤖 *Karn ha reconocido la carta:*\n"
                    f"Es *{nombre}* ({set_cod.upper()}, {grado}).\n\n"
                    f"❌ En este momento no tenemos copias en el stock local de la tienda."
                )

            telegram_notif.enviar_mensaje(chat_id, mensaje)
