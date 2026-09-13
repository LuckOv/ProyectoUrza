"""Usuarios, sesiones y carrito de URZA.

Todo va a un SQLite al lado de este archivo. No hace falta instalar nada:
sqlite3 y hashlib vienen con Python.

Las claves nunca se guardan en texto plano. Se guarda el resultado de pasarlas
por PBKDF2 con una sal distinta para cada usuario, que es lo mismo que hace
cualquier sitio serio: aunque alguien se robe la base, no puede leer las claves.
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent / "urza.db"
ITERACIONES = 200_000
DIAS_SESION = 7


def conectar():
    con = sqlite3.connect(BASE)
    con.row_factory = sqlite3.Row
    return con


def preparar():
    """Crea las tablas si todavía no existen. Se llama al arrancar la API."""
    with conectar() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario  TEXT NOT NULL UNIQUE COLLATE NOCASE,
                clave    TEXT NOT NULL,
                sal      TEXT NOT NULL,
                creado   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sesiones (
                token       TEXT PRIMARY KEY,
                usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                vence       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS carrito (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                nombre      TEXT NOT NULL,
                edicion     TEXT,
                precio      REAL,
                imagen      TEXT,
                cantidad    INTEGER NOT NULL DEFAULT 1,
                agregado    TEXT NOT NULL
            );
        """)


# --- claves ------------------------------------------------------------------

def _hashear(clave: str, sal: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, ITERACIONES).hex()


def registrar(usuario: str, clave: str) -> dict:
    usuario = usuario.strip()
    if len(usuario) < 3:
        raise ValueError("El usuario tiene que tener al menos 3 caracteres.")
    if len(clave) < 6:
        raise ValueError("La clave tiene que tener al menos 6 caracteres.")

    sal = os.urandom(16)
    with conectar() as con:
        ya_existe = con.execute(
            "SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
        if ya_existe:
            raise ValueError("Ese nombre de usuario ya está tomado.")

        cur = con.execute(
            "INSERT INTO usuarios (usuario, clave, sal, creado) VALUES (?, ?, ?, ?)",
            (usuario, _hashear(clave, sal), sal.hex(), datetime.now(timezone.utc).isoformat()),
        )
        return {"id": cur.lastrowid, "usuario": usuario}


def verificar(usuario: str, clave: str) -> dict:
    with conectar() as con:
        fila = con.execute(
            "SELECT id, usuario, clave, sal FROM usuarios WHERE usuario = ?",
            (usuario.strip(),),
        ).fetchone()

    # El mensaje es el mismo tanto si el usuario no existe como si la clave
    # está mal, así nadie puede averiguar qué usuarios hay probando nombres.
    if not fila or _hashear(clave, bytes.fromhex(fila["sal"])) != fila["clave"]:
        raise ValueError("Usuario o clave incorrectos.")
    return {"id": fila["id"], "usuario": fila["usuario"]}


# --- sesiones ----------------------------------------------------------------

def abrir_sesion(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    vence = (datetime.now(timezone.utc) + timedelta(days=DIAS_SESION)).isoformat()
    with conectar() as con:
        con.execute(
            "INSERT INTO sesiones (token, usuario_id, vence) VALUES (?, ?, ?)",
            (token, usuario_id, vence),
        )
    return token


def cerrar_sesion(token: str):
    with conectar() as con:
        con.execute("DELETE FROM sesiones WHERE token = ?", (token,))


def quien_es(token: str):
    """Devuelve el usuario dueño del token, o None si no vale o ya venció."""
    if not token:
        return None
    with conectar() as con:
        fila = con.execute(
            """SELECT u.id, u.usuario, s.vence
                 FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id
                WHERE s.token = ?""",
            (token,),
        ).fetchone()
        if not fila:
            return None
        if datetime.fromisoformat(fila["vence"]) < datetime.now(timezone.utc):
            con.execute("DELETE FROM sesiones WHERE token = ?", (token,))
            return None
    return {"id": fila["id"], "usuario": fila["usuario"]}


# --- carrito -----------------------------------------------------------------

def ver_carrito(usuario_id: int) -> list:
    with conectar() as con:
        filas = con.execute(
            """SELECT id, nombre, edicion, precio, imagen, cantidad
                 FROM carrito WHERE usuario_id = ? ORDER BY agregado""",
            (usuario_id,),
        ).fetchall()
    return [dict(f) for f in filas]


def agregar(usuario_id: int, nombre: str, edicion=None, precio=None, imagen=None, cantidad=1) -> list:
    with conectar() as con:
        # Si ya está la misma carta de la misma edición, sumo cantidad en vez
        # de repetir la fila.
        fila = con.execute(
            """SELECT id, cantidad FROM carrito
                WHERE usuario_id = ? AND nombre = ? AND IFNULL(edicion,'') = IFNULL(?,'')""",
            (usuario_id, nombre, edicion),
        ).fetchone()

        if fila:
            con.execute(
                "UPDATE carrito SET cantidad = ? WHERE id = ?",
                (fila["cantidad"] + cantidad, fila["id"]),
            )
        else:
            con.execute(
                """INSERT INTO carrito (usuario_id, nombre, edicion, precio, imagen, cantidad, agregado)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (usuario_id, nombre, edicion, precio, imagen, cantidad,
                 datetime.now(timezone.utc).isoformat()),
            )
    return ver_carrito(usuario_id)


def quitar(usuario_id: int, item_id: int) -> list:
    with conectar() as con:
        con.execute(
            "DELETE FROM carrito WHERE id = ? AND usuario_id = ?", (item_id, usuario_id)
        )
    return ver_carrito(usuario_id)


def vaciar(usuario_id: int) -> list:
    with conectar() as con:
        con.execute("DELETE FROM carrito WHERE usuario_id = ?", (usuario_id,))
    return []
