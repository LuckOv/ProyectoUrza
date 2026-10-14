"""Configuración → Bases del bot: instalar reglas/lore desde el panel (con pasos falsos, sin bajar nada)."""
import sys
import time

import pytest

from conftest import CLAVE
from panel import bot

CREAR = (
    "import sqlite3, sys, pathlib\n"
    "d = pathlib.Path(sys.argv[1]); d.mkdir(exist_ok=True)\n"
    "c = sqlite3.connect(d / 'chroma.sqlite3'); c.execute('CREATE TABLE IF NOT EXISTS embeddings (id INTEGER)')\n"
    "c.executemany('INSERT INTO embeddings VALUES (?)', [(i,) for i in range(int(sys.argv[2]))]); c.commit(); c.close()\n"
    "print('[ingesta] Listo.', flush=True)\n"
)


@pytest.fixture
def pasos_falsos(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "REGLAS_DB", tmp_path / "reglas_db")
    monkeypatch.setattr(bot, "LORE_DB", tmp_path / "lore_db")
    monkeypatch.setattr(bot, "LORE_SNAP", tmp_path / "lore")
    monkeypatch.setattr(bot, "DEPENDENCIAS", [])
    comandos = {
        "reglas": [sys.executable, "-c", CREAR, str(tmp_path / "reglas_db"), "7"],
        "modelos": [sys.executable, "-c", "print('Modelo de rerank listo.')"],
        "lore": [sys.executable, "-c", CREAR, str(tmp_path / "lore_db"), "3"],
    }
    monkeypatch.setattr(bot, "_comando", lambda paso: comandos[paso])
    yield comandos
    bot.cancelar()
    for _ in range(50):
        if not bot.estado()["trabajo"]["corriendo"]:
            break
        time.sleep(0.1)


def esperar(c):
    for _ in range(100):
        e = c.get("/vendedor/bot", headers=CLAVE).json()
        if not e["trabajo"]["corriendo"]:
            return e
        time.sleep(0.1)
    raise AssertionError("la instalación no terminó")


def test_estado_sin_bases(cliente, pasos_falsos):
    e = cliente.get("/vendedor/bot", headers=CLAVE).json()
    assert e["reglas"]["fragmentos"] is None and e["lore"]["fragmentos"] is None
    assert e["trabajo"]["corriendo"] is False


def test_instalar_todo(cliente, pasos_falsos):
    r = cliente.post("/vendedor/bot/instalar", headers=CLAVE, json={"partes": ["lore", "reglas", "modelos"]})
    assert r.status_code == 200 and r.json()["trabajo"]["pasos"] == ["reglas", "modelos", "lore"]
    e = esperar(cliente)
    assert e["trabajo"]["resultado"] == "ok", e["trabajo"]
    assert e["reglas"]["fragmentos"] == 7 and e["lore"]["fragmentos"] == 3
    assert any("Modelo de rerank listo" in l for l in e["trabajo"]["log"])
    titulos = [m["titulo"] for m in cliente.get("/vendedor/actividad", headers=CLAVE).json()["movimientos"]]
    assert "Bases del bot instaladas" in titulos


def test_una_instalacion_a_la_vez(cliente, pasos_falsos):
    pasos_falsos["reglas"] = [sys.executable, "-c", "import time; time.sleep(3)"]
    assert cliente.post("/vendedor/bot/instalar", headers=CLAVE, json={"partes": ["reglas"]}).status_code == 200
    r = cliente.post("/vendedor/bot/instalar", headers=CLAVE, json={"partes": ["lore"]})
    assert r.status_code == 409 and "en curso" in r.json()["detail"]
    cliente.post("/vendedor/bot/cancelar", headers=CLAVE)
    e = esperar(cliente)
    assert e["trabajo"]["resultado"] == "cancelado"


def test_paso_que_falla(cliente, pasos_falsos):
    pasos_falsos["reglas"] = [sys.executable, "-c", "print('sin red'); raise SystemExit(1)"]
    cliente.post("/vendedor/bot/instalar", headers=CLAVE, json={"partes": ["reglas", "lore"]})
    e = esperar(cliente)
    assert e["trabajo"]["resultado"] == "error" and "Reglas" in e["trabajo"]["mensaje"]
    assert e["lore"]["fragmentos"] is None          # no siguió con el lore
    assert "sin red" in e["trabajo"]["log"]


def test_validaciones(cliente, pasos_falsos, monkeypatch):
    assert cliente.post("/vendedor/bot/instalar", headers=CLAVE, json={"partes": ["nada"]}).status_code == 409
    monkeypatch.setattr(bot, "DEPENDENCIAS", ["libreria_que_no_existe_xyz"])
    r = cliente.post("/vendedor/bot/instalar", headers=CLAVE, json={"partes": ["reglas"]})
    assert r.status_code == 409 and "uv sync" in r.json()["detail"]


def test_comandos_reales():
    """Reinstalar reglas usa --rebuild (si no, duplica); lore con la descarga completa sólo indexa."""
    assert bot._comando("reglas")[1:3] == ["-m", "ingesta.ingestar_reglas"]
    assert bot._comando("lore")[1:3] == ["-m", "ingesta.ingestar_lore"]
