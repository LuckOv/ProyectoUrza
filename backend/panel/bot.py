"""Instalación de las bases del bot desde el panel (Configuración → Bases del bot).

El juez de reglas (Ajani) y el erudito de lore (Teferi) responden buscando en
dos bases locales que NO viajan con git (pesan mucho): backend/reglas_db y
backend/lore_db. Acá se arman corriendo las mismas ingestas de siempre
(ingesta/ingestar_reglas.py e ingesta/ingestar_lore.py) como procesos aparte,
y el panel va mostrando la salida.

Pasos:
    reglas   baja las Reglas Completas e indexa         (unos minutos)
    modelos  baja el modelo de rerank que usa el juez   (una vez, ~500 MB)
    lore     baja la MTG Wiki (resumible) e indexa      (puede tardar horas)

Una sola instalación a la vez. Se puede cancelar: el lore retoma donde quedó.
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REGLAS_DB = BACKEND / "reglas_db"
LORE_DB = BACKEND / "lore_db"
LORE_SNAP = BACKEND / "lore"

PASOS = {
    "reglas": "Reglas (Ajani)",
    "modelos": "Modelo de búsqueda del juez",
    "lore": "Lore (Teferi)",
}
DEPENDENCIAS = ["chromadb", "langchain_chroma", "langchain_huggingface", "sentence_transformers"]

_lock = threading.Lock()
_estado = {
    "corriendo": False, "pasos": [], "paso": None, "inicio": None, "fin": None,
    "resultado": None,        # None | "ok" | "error" | "cancelado"
    "mensaje": "",
}
_log = deque(maxlen=300)
_proceso = {"p": None, "cancelar": False}


# --- estado de las bases -----------------------------------------------------------

def _fragmentos(carpeta: Path):
    """Cuántos fragmentos tiene una base de Chroma (sin cargar torch ni Chroma)."""
    archivo = carpeta / "chroma.sqlite3"
    if not archivo.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{archivo}?mode=ro", uri=True, timeout=2)
        try:
            return con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0   # existe pero no se pudo leer (a medio armar o de otra versión)


def _modificado(carpeta: Path):
    archivo = carpeta / "chroma.sqlite3"
    if not archivo.exists():
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(archivo.stat().st_mtime))


def _paginas_lore():
    archivo = LORE_SNAP / "paginas.jsonl"
    if not archivo.exists():
        return 0
    with archivo.open(encoding="utf-8") as f:
        return sum(1 for linea in f if linea.strip())


def _descarga_lore_completa() -> bool:
    ronda = LORE_SNAP / "ronda.json"
    try:
        return bool(json.loads(ronda.read_text(encoding="utf-8")).get("descarga_completa"))
    except (OSError, ValueError):
        return False


def _modelo_rerank_bajado() -> bool:
    """¿Ya está en la caché de HuggingFace el modelo de rerank del juez?"""
    from agentes.reglas import MODELO_RERANK
    cache = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
    return (cache / ("models--" + MODELO_RERANK.replace("/", "--"))).exists()


def estado() -> dict:
    faltan = [d for d in DEPENDENCIAS if importlib.util.find_spec(d) is None]
    with _lock:
        trabajo = {**_estado, "log": list(_log)}
    trabajo["segundos"] = round((trabajo["fin"] or time.time()) - trabajo["inicio"]) if trabajo["inicio"] else 0
    return {
        "dependencias_faltan": faltan,
        "reglas": {"fragmentos": _fragmentos(REGLAS_DB), "actualizado": _modificado(REGLAS_DB)},
        "lore": {"fragmentos": _fragmentos(LORE_DB), "actualizado": _modificado(LORE_DB),
                 "paginas": _paginas_lore(), "descarga_completa": _descarga_lore_completa()},
        "modelos": {"rerank": _modelo_rerank_bajado()},
        "trabajo": trabajo,
        "pasos": PASOS,
    }


# --- instalación -----------------------------------------------------------------

def _comando(paso: str) -> list:
    py = sys.executable
    if paso == "reglas":
        # Si ya existe, se rehace de cero: sin --rebuild la ingesta duplica todo.
        return [py, "-m", "ingesta.ingestar_reglas"] + (["--rebuild"] if REGLAS_DB.exists() else [])
    if paso == "lore":
        # Si la descarga ya está completa (por ejemplo, copiaste la carpeta lore/
        # de un compañero), sólo se indexa: es offline y mucho más rápido.
        return [py, "-m", "ingesta.ingestar_lore"] + (["--index"] if _descarga_lore_completa() else [])
    if paso == "modelos":
        return [py, "-c",
                "from sentence_transformers import CrossEncoder\n"
                "from agentes.reglas import MODELO_RERANK\n"
                "print('Bajando', MODELO_RERANK, '...', flush=True)\n"
                "CrossEncoder(MODELO_RERANK)\n"
                "print('Modelo de rerank listo.', flush=True)\n"]
    raise ValueError(f"Paso desconocido: {paso}")


def _soltar_bases():
    """El servidor puede tener abiertas las bases (si ya se usaron): se sueltan
    para poder rehacerlas. En la próxima pregunta se vuelven a abrir solas."""
    for nombre in ("agentes.reglas", "agentes.lore"):
        modulo = sys.modules.get(nombre)
        if modulo is not None:
            modulo._vectorstore = None
    try:
        from chromadb.api.client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass
    import gc
    gc.collect()


def _anotar(linea: str):
    linea = linea.rstrip()
    if linea:
        with _lock:
            _log.append(linea)


def _correr(pasos: list):
    resultado, mensaje = "ok", "Listo: el bot ya puede usar las bases nuevas."
    for paso in pasos:
        if _proceso["cancelar"]:
            resultado, mensaje = "cancelado", "Instalación cancelada."
            break
        with _lock:
            _estado["paso"] = paso
        _anotar(f"──── {PASOS[paso]} ────")
        if paso in ("reglas", "lore"):
            _soltar_bases()
        entorno = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            proc = subprocess.Popen(
                _comando(paso), cwd=BACKEND, env=entorno, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as e:
            resultado, mensaje = "error", f"No pude arrancar {PASOS[paso]}: {e}"
            break
        _proceso["p"] = proc
        for linea in proc.stdout:          # text=True parte también en \r (barras de progreso)
            _anotar(linea)
        codigo = proc.wait()
        _proceso["p"] = None
        if _proceso["cancelar"]:
            resultado, mensaje = "cancelado", "Instalación cancelada. El lore retoma donde quedó la próxima vez."
            break
        if codigo != 0:
            resultado = "error"
            mensaje = (f"Falló {PASOS[paso]} (código {codigo}). Mirá las últimas líneas. Si dice que un archivo "
                       "está en uso, reiniciá el backend y volvé a intentar.")
            break
        if paso in ("reglas", "lore"):
            _soltar_bases()       # que la próxima pregunta abra la base recién hecha
    with _lock:
        _estado.update(corriendo=False, paso=None, fin=time.time(), resultado=resultado, mensaje=mensaje)
    _anotar(mensaje)
    try:
        from tienda import base
        nombres = ", ".join(PASOS[p] for p in pasos)
        titulo = {"ok": "Bases del bot instaladas", "error": "Falló la instalación del bot",
                  "cancelado": "Instalación del bot cancelada"}[resultado]
        base.registrar_movimiento("config", titulo, nombres)
    except Exception:
        pass


def instalar(partes: list) -> dict:
    pasos = [p for p in PASOS if p in partes]          # siempre en el mismo orden
    if not pasos:
        raise ValueError("Elegí qué instalar: reglas, modelos o lore.")
    faltan = [d for d in DEPENDENCIAS if importlib.util.find_spec(d) is None]
    if faltan:
        raise ValueError(f"Faltan librerías ({', '.join(faltan)}). Corré 'uv sync' en la carpeta del proyecto.")
    with _lock:
        if _estado["corriendo"]:
            raise ValueError("Ya hay una instalación en curso.")
        _estado.update(corriendo=True, pasos=pasos, paso=None, inicio=time.time(), fin=None,
                       resultado=None, mensaje="")
        _log.clear()
    _proceso["cancelar"] = False
    threading.Thread(target=_correr, args=(pasos,), daemon=True).start()
    return estado()


def cancelar() -> dict:
    with _lock:
        corriendo = _estado["corriendo"]
    if corriendo:
        _proceso["cancelar"] = True
        p = _proceso["p"]
        if p is not None and p.poll() is None:
            p.terminate()
    return estado()
