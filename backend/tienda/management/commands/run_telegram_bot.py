"""Comando de Django para iniciar el bot de Telegram de URZA en Long Polling.

Uso:
    python manage.py run_telegram_bot

Funcionalidades:
- Long Polling saliente: funciona en tu PC local sin necesidad de IP pública ni ngrok.
- Charla con jugadores en privado o en grupos (etiquetando a @UrzaBot).
- Visión por computadora con Karn: recibe fotos de cartas para stock o fotos de mesa para jugadas.
- Modo Dueño móvil: comandos ejecutivos (/ventas, /pedidos, /alertas) exclusivos para el dueño.
"""

import sys
import time
import requests
from django.core.management.base import BaseCommand
from langchain_core.messages import HumanMessage

from agentes.agent_sales import sin_razonamiento
from agentes.graph import app_graph
from agentes import karn
from tienda import admin_reportes, cartas, telegram_notif


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

        token = telegram_notif.token_bot()
        owner_id = telegram_notif.owner_id()

        # Obtener información del bot
        try:
            r = requests.get(telegram_notif.url_api("getMe"), timeout=10)
            if not r.ok:
                self.stdout.write(self.style.ERROR(f"[URZA TELEGRAM] Token inválido: {r.text}"))
                return
            bot_info = r.json().get("result", {})
            bot_username = bot_info.get("username", "UrzaBot")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[URZA TELEGRAM] Error conectando con Telegram: {e}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\n=======================================================\n"
            f"  URZA TELEGRAM BOT ACTIVO (@{bot_username})\n"
            f"  Modo: Long Polling (PC Local)\n"
            f"  Dueño ID: {owner_id or '(No configurado)'}\n"
            f"  Presioná Ctrl+C para detener.\n"
            f"=======================================================\n"
        ))

        offset = 0
        while True:
            try:
                params = {"offset": offset, "timeout": 25}
                r = requests.get(telegram_notif.url_api("getUpdates"), params=params, timeout=30)
                if not r.ok:
                    time.sleep(2)
                    continue

                updates = r.json().get("result", [])
                for u in updates:
                    offset = max(offset, u["update_id"] + 1)
                    self.procesar_update(u, bot_username, owner_id)

            except requests.exceptions.RequestException:
                time.sleep(3)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n[URZA TELEGRAM] Bot detenido por el usuario."))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[URZA TELEGRAM] Error en bucle: {e}"))
                time.sleep(2)

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
                mencion = f"@{bot_username.lower()}"
                es_reply_al_bot = msg.get("reply_to_message", {}).get("from", {}).get("is_bot")
                if not (mencion in caption.lower() or es_reply_al_bot):
                    return
                caption = caption.replace(f"@{bot_username}", "").replace(f"@{bot_username.lower()}", "").strip()

            self.enviar_accion(chat_id, "typing")
            self.procesar_foto(chat_id, photos, caption, user_name)
            return

        # --- B. MENSAJES DE TEXTO ---
        if not texto_raw:
            return

        # En grupos, responder solo si mencionan al bot, le responden o es comando
        if chat_type in ("group", "supergroup"):
            mencion = f"@{bot_username.lower()}"
            es_reply_al_bot = msg.get("reply_to_message", {}).get("from", {}).get("is_bot")
            if not (mencion in texto_raw.lower() or es_reply_al_bot or texto_raw.startswith("/")):
                return
            # Limpiar mención del texto
            texto_raw = texto_raw.replace(f"@{bot_username}", "").replace(f"@{bot_username.lower()}", "").strip()

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

        # Comandos básicos de bienvenida
        if texto_raw in ("/start", "/help", "/ayuda"):
            bienvenida = (
                f"🧙‍♂️ *¡Saludos, {user_name}! Soy Urza, el artífice supremo.*\n\n"
                f"Estoy aquí para asistirte con la tienda de Magic:\n"
                f"• *Stock y Precios:* Preguntame por cartas físicas y sus variantes.\n"
                f"• *Reglas de Juego:* Consultale a Ajani sobre cualquier interacción o jugada.\n"
                f"• *Lore e Historia:* Teferi te contará sobre los planos y personajes.\n"
                f"• *Armado de Mazos:* Saheeli optimiza tus listas y curva de maná.\n"
                f"• *Visión (Karn):* ¡Envíame una foto de una carta física para saber si hay stock, o de una mesa de juego para arbitrar una jugada!\n"
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
