"""Pruebas unitarias para la integración de Telegram y reportes de Urza."""

from unittest.mock import patch
from tienda import admin_reportes, telegram_notif


def test_telegram_sin_token_no_falla(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "")
    assert telegram_notif.esta_configurado() is False
    assert telegram_notif.enviar_mensaje(12345, "hola") is False
    assert telegram_notif.notificar_dueno("hola") is False
    assert telegram_notif.notificar_pedido({"id": 1, "nombre": "Ana"}) is False
    assert telegram_notif.notificar_propuesta({"id": 1, "carta": "Cavern of Souls"}) is False


def test_telegram_notificar_pedido_formato(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test_token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "999888")

    enviados = []

    def mock_enviar(chat_id, texto, **kwargs):
        enviados.append((chat_id, texto))
        return True

    monkeypatch.setattr(telegram_notif, "enviar_mensaje", mock_enviar)

    pedido = {
        "id": 42,
        "nombre": "Ana",
        "apellido": "Pérez",
        "fecha_retiro": "2026-11-10",
        "hora_retiro": "17:30",
        "total": 50000,
        "items": [
            {"nombre": "Llanowar Elves", "grado": "Sin graduar", "cantidad": 4},
            {"nombre": "Cavern of Souls", "grado": "PSA 10", "cantidad": 1},
        ],
    }

    res = telegram_notif.notificar_pedido(pedido)
    assert res is True
    assert len(enviados) == 1
    chat_id, texto = enviados[0]
    assert chat_id == "999888"
    assert "PEDIDO #42" in texto
    assert "Ana Pérez" in texto
    assert "2026-11-10" in texto and "17:30" in texto
    assert "4x *Llanowar Elves*" in texto
    assert "1x *Cavern of Souls*" in texto
    assert "$50,000" in texto


def test_telegram_notificar_propuesta_formato(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test_token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "999888")

    enviados = []

    def mock_enviar(chat_id, texto, **kwargs):
        enviados.append((chat_id, texto))
        return True

    monkeypatch.setattr(telegram_notif, "enviar_mensaje", mock_enviar)

    propuesta = {
        "id": 7,
        "nombre": "Carlos",
        "apellido": "Gómez",
        "email": "carlos@gmail.com",
        "carta": "Heartfire Hero",
        "grado": "PSA 9",
        "cantidad": 2,
        "precio": 1500,
        "moneda": "ARS",
    }

    res = telegram_notif.notificar_propuesta(propuesta)
    assert res is True
    assert len(enviados) == 1
    chat_id, texto = enviados[0]
    assert chat_id == "999888"
    assert "PROPUESTA DE VENTA" in texto
    assert "Carlos Gómez" in texto
    assert "Heartfire Hero" in texto
    assert "PSA 9" in texto
    assert "$1,500.00" in texto


def test_admin_reportes_sin_errores(cliente):
    ventas = admin_reportes.resumen_ventas()
    assert "REPORTE DE VENTAS" in ventas

    pedidos = admin_reportes.resumen_pedidos_pendientes()
    assert ("PEDIDOS PENDIENTES" in pedidos) or ("No hay pedidos pendientes" in pedidos)

    alertas = admin_reportes.resumen_alertas()
    assert ("ALERTAS DE INVENTARIO" in alertas) or ("Inventario en orden" in alertas)


def test_telegram_notificar_inicio_y_detencion(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test_token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "999888")
    monkeypatch.setenv("TELEGRAM_GRUPO_ID", "-1001234")

    enviados = []

    def mock_enviar(chat_id, texto, **kwargs):
        enviados.append((chat_id, texto))
        return True

    monkeypatch.setattr(telegram_notif, "enviar_mensaje", mock_enviar)

    telegram_notif.notificar_inicio("UrzaTestBot")
    assert len(enviados) == 2
    assert enviados[0][0] == "999888" and "URZA ONLINE" in enviados[0][1]
    assert enviados[1][0] == "-1001234" and "en línea" in enviados[1][1]

    enviados.clear()
    telegram_notif.notificar_detencion()
    assert len(enviados) == 2
    assert enviados[0][0] == "999888" and "DESCONECTADO" in enviados[0][1]
    assert enviados[1][0] == "-1001234" and "fuera de línea" in enviados[1][1]


def test_voz_transcribir_audio_groq(monkeypatch):
    from agentes import voz

    monkeypatch.setenv("GROQ_API_KEY", "dummy_groq_key")

    class FalsaTranscripcion:
        def __str__(self):
            return "¿Tenés Cavern of Souls en stock?"

    class FalsoAudio:
        class transcriptions:
            @staticmethod
            def create(*args, **kwargs):
                return FalsaTranscripcion()

    class FalsoGroq:
        def __init__(self, *args, **kwargs):
            self.audio = FalsoAudio()

    import groq
    monkeypatch.setattr(groq, "Groq", FalsoGroq)

    texto = voz.transcribir_audio(b"dummy_ogg_bytes", filename="audio.ogg", mime_type="audio/ogg")
    assert texto == "¿Tenés Cavern of Souls en stock?"


def test_telegram_bot_procesar_audio(monkeypatch):
    from tienda.management.commands.run_telegram_bot import Command
    from agentes import voz

    cmd = Command()
    mensajes_enviados = []

    monkeypatch.setattr(telegram_notif, "descargar_archivo", lambda fid: (b"bytes_audio", "audio/ogg"))
    monkeypatch.setattr(voz, "transcribir_audio", lambda b, **kwargs: "¿Cuánto sale Llanowar Elves?")
    monkeypatch.setattr(telegram_notif, "enviar_mensaje", lambda cid, txt, **kwargs: mensajes_enviados.append((cid, txt)))
    monkeypatch.setattr(cmd, "enviar_accion", lambda cid, act: None)

    update = {
        "update_id": 1001,
        "message": {
            "message_id": 50,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "Lucas"},
            "voice": {"file_id": "file_voice_123", "mime_type": "audio/ogg"},
        },
    }

    cmd.procesar_update(update, bot_username="UrzaTiendaBot", owner_id="417409540")

    assert len(mensajes_enviados) >= 1
    ultimo_mensaje = mensajes_enviados[-1][1]
    assert "🎙️ _«¿Cuánto sale Llanowar Elves?»_" in ultimo_mensaje

