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


def test_admin_reportes_sin_errores():
    ventas = admin_reportes.resumen_ventas()
    assert "REPORTE DE VENTAS" in ventas

    pedidos = admin_reportes.resumen_pedidos_pendientes()
    assert ("PEDIDOS PENDIENTES" in pedidos) or ("No hay pedidos pendientes" in pedidos)

    alertas = admin_reportes.resumen_alertas()
    assert ("ALERTAS DE INVENTARIO" in alertas) or ("Inventario en orden" in alertas)
