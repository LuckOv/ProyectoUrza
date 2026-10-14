"""Pruebas del backend de URZA.

Correr parado en backend/:
    uv run --with pytest python -m pytest tests -q

Arma un backend aislado: copia del código en una carpeta temporal, base nueva
por prueba, Scryfall/dolarapi simulados (tests/falsos/red.py) y un Groq falso
que sigue un guion (tests/falsos/langchain_groq.py). Nunca tocan la base real
(urza.db), la red ni la API key.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
ORIGEN = AQUI.parent                     # backend/

# 1. Copia del backend (sin .env, sin la base real, sin los RAG ni las pruebas).
DESTINO = Path(tempfile.mkdtemp(prefix="urza_test_")) / "backend"
shutil.copytree(ORIGEN, DESTINO, ignore=shutil.ignore_patterns(
    ".env", "urza.db", "inventario.csv", "__pycache__", "*_db", "lore", "reglas", "tests", ".pytest_cache"))
os.chdir(DESTINO)
os.environ["VENDEDOR_CLAVE"] = "clave-test"
os.environ["GROQ_API_KEY"] = "falsa"
os.environ.pop("PRICECHARTING_TOKEN", None)

# 2. Falsos primero en el path: langchain_groq falso y requests interceptado.
sys.path.insert(0, str(AQUI / "falsos"))
sys.path.insert(0, str(DESTINO))
import red  # noqa: E402
red.instalar()
import langchain_groq as groq_falso  # noqa: E402

CLAVE = {"X-Vendedor-Clave": "clave-test"}


def _reiniciar():
    import gc
    from tienda import base, cartas, inventario
    if base.BASE.exists():
        gc.collect()          # Windows no deja borrar un archivo con una conexión abierta
        base.BASE.unlink()
    base.preparar()
    base.guardar_config("dolar", {"modo": "manual", "casa": "blue", "valor": 1000.0, "actualizado": base.ahora_iso()})
    cartas._cache.clear()
    cartas._nombres.clear()
    cartas._pool_standard.update(total=None, cuando=0.0)
    inventario._ultimo_intento["cuando"] = 0.0
    inventario._ultimo_refresco["cuando"] = 0.0
    inventario._cache_pc.clear()
    red.RED.update(modo="ok", pedidos=[], dolar=1500.0)
    red.MOVIDAS.clear()
    groq_falso.GUION.clear()
    groq_falso.LLAMADAS.clear()


@pytest.fixture
def cliente():
    _reiniciar()
    from fastapi.testclient import TestClient
    import api
    with TestClient(api.app) as c:
        yield c
    groq_falso.GUION.clear()


@pytest.fixture
def guion():
    return groq_falso.GUION


@pytest.fixture
def llamadas():
    return groq_falso.LLAMADAS


def id_de(nombre, i=0):
    return red.TODAS[nombre][i]["id"]


def alta(c, nombre, i=0, grado="Sin graduar", cantidad=3, precio=None):
    r = c.post("/vendedor/inventario", headers=CLAVE,
               json={"scryfall_id": id_de(nombre, i), "grado": grado, "cantidad": cantidad, "precio_usd": precio})
    assert r.status_code == 200, r.text
    return r.json()
