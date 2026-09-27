"""Base de datos de URZA: conexión, esquema, configuración y movimientos.

Todo vive en un SQLite al lado de este archivo (urza.db). Acá está lo que
comparten los demás módulos:

- conectar() y preparar() (crea/migra las tablas),
- la configuración dinámica de la tienda (horarios, dólar, stock bajo,
  descuento general), que el vendedor edita desde su panel,
- el registro de movimientos, que alimenta la actividad reciente.

La hora es la de Argentina (UTC-3, sin horario de verano), fija a propósito:
así no depende de que Windows tenga instalada la base de zonas horarias.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent / "urza.db"
CSV_VIEJO = Path(__file__).parent / "inventario.csv"

ARG = timezone(timedelta(hours=-3))
VERSION_ESQUEMA = 2

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
NOMBRE_DIA = {
    "lun": "lunes", "mar": "martes", "mie": "miércoles", "jue": "jueves",
    "vie": "viernes", "sab": "sábado", "dom": "domingo",
}

CONFIG_INICIAL = {
    # None = cerrado ese día.
    "horarios": {
        "lun": {"abre": "10:00", "cierra": "20:00"},
        "mar": {"abre": "10:00", "cierra": "20:00"},
        "mie": {"abre": "10:00", "cierra": "20:00"},
        "jue": {"abre": "10:00", "cierra": "20:00"},
        "vie": {"abre": "10:00", "cierra": "20:00"},
        "sab": {"abre": "10:00", "cierra": "20:00"},
        "dom": None,
    },
    # modo "manual": se usa `valor` tal cual.
    # modo "auto": se trae de dolarapi.com (casa = blue/oficial/tarjeta/bolsa)
    # y se refresca solo si tiene más de una hora.
    "dolar": {"modo": "auto", "casa": "blue", "valor": 1000.0, "actualizado": None},
    "stock_bajo": 2,
    "descuento_general": 0.0,
}


def ahora() -> datetime:
    return datetime.now(ARG)


def ahora_iso() -> str:
    return ahora().isoformat(timespec="seconds")


def conectar():
    con = sqlite3.connect(BASE)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def preparar():
    """Crea las tablas si no existen y migra bases de versiones anteriores.

    Versiones viejas: la primera tenía usuarios/sesiones; la segunda, un
    carrito sin referencia al inventario y pedidos con horario en texto
    libre. Esas tablas se descartan (eran datos de prueba) y el inventario
    del CSV se importa una sola vez.
    """
    with conectar() as con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version < VERSION_ESQUEMA:
            con.executescript("""
                DROP TABLE IF EXISTS pedido_items;
                DROP TABLE IF EXISTS pedidos;
                DROP TABLE IF EXISTS carrito;
                DROP TABLE IF EXISTS sesiones;
                DROP TABLE IF EXISTS usuarios;
            """)

        con.executescript("""
            CREATE TABLE IF NOT EXISTS inventario (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre          TEXT NOT NULL,
                set_codigo      TEXT,
                set_nombre      TEXT,
                numero          TEXT,
                rareza          TEXT,
                imagen          TEXT,
                scryfall_id     TEXT,
                grado           TEXT NOT NULL DEFAULT 'Sin graduar',
                precio_usd      REAL,
                cantidad        INTEGER NOT NULL DEFAULT 0,
                legal_standard  INTEGER NOT NULL DEFAULT 0,
                creado          TEXT NOT NULL,
                actualizado     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS carrito (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id      TEXT NOT NULL,
                inventario_id  INTEGER NOT NULL REFERENCES inventario(id) ON DELETE CASCADE,
                cantidad       INTEGER NOT NULL DEFAULT 1,
                agregado       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pedidos (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id     TEXT,
                nombre        TEXT NOT NULL,
                apellido      TEXT NOT NULL,
                fecha_retiro  TEXT NOT NULL,     -- YYYY-MM-DD
                hora_retiro   TEXT NOT NULL,     -- HH:MM
                total         REAL NOT NULL,     -- en pesos
                estado        TEXT NOT NULL DEFAULT 'pendiente',
                comentario    TEXT NOT NULL DEFAULT '',
                origen        TEXT NOT NULL DEFAULT 'chat',
                creado        TEXT NOT NULL,
                actualizado   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pedido_items (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id      INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                inventario_id  INTEGER,          -- sin FK: el pedido sobrevive si se borra la carta
                nombre         TEXT NOT NULL,
                set_nombre     TEXT,
                grado          TEXT,
                precio         REAL,             -- unitario, en pesos, al momento del pedido
                cantidad       INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS movimientos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha      TEXT NOT NULL,
                tipo       TEXT NOT NULL,
                titulo     TEXT NOT NULL,
                detalle    TEXT NOT NULL DEFAULT '',
                unidades   INTEGER NOT NULL DEFAULT 0,
                pedido_id  INTEGER
            );

            CREATE TABLE IF NOT EXISTS descuentos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                inventario_id  INTEGER NOT NULL UNIQUE REFERENCES inventario(id) ON DELETE CASCADE,
                porcentaje     REAL NOT NULL,
                creado         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config (
                clave  TEXT PRIMARY KEY,
                valor  TEXT NOT NULL
            );
        """)
        con.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")

        for clave, valor in CONFIG_INICIAL.items():
            con.execute(
                "INSERT OR IGNORE INTO config (clave, valor) VALUES (?, ?)",
                (clave, json.dumps(valor)),
            )


# --- configuración -----------------------------------------------------------

def config(clave: str):
    with conectar() as con:
        fila = con.execute("SELECT valor FROM config WHERE clave = ?", (clave,)).fetchone()
    if not fila:
        return CONFIG_INICIAL.get(clave)
    return json.loads(fila["valor"])


def guardar_config(clave: str, valor):
    with conectar() as con:
        con.execute(
            "INSERT INTO config (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, json.dumps(valor)),
        )


def horarios_texto(horarios: dict | None = None) -> str:
    """Los horarios en una línea legible, agrupando días seguidos iguales.

    Ej: "lunes a viernes de 10:00 a 20:00; sábado de 10:00 a 14:00; domingo cerrado".
    """
    horarios = horarios or config("horarios")
    tramos = []
    for dia in DIAS:
        h = horarios.get(dia)
        clave = (h["abre"], h["cierra"]) if h else None
        if tramos and tramos[-1][2] == clave:
            tramos[-1][1] = dia
        else:
            tramos.append([dia, dia, clave])

    partes = []
    for desde, hasta, clave in tramos:
        dias = NOMBRE_DIA[desde] if desde == hasta else f"{NOMBRE_DIA[desde]} a {NOMBRE_DIA[hasta]}"
        partes.append(f"{dias} de {clave[0]} a {clave[1]}" if clave else f"{dias} cerrado")
    return "; ".join(partes)


# --- movimientos -------------------------------------------------------------

def registrar_movimiento(tipo: str, titulo: str, detalle: str = "", unidades: int = 0,
                         pedido_id: int | None = None, con=None):
    """Deja constancia de algo que pasó con el stock o los pedidos.

    Acepta una conexión abierta para quedar dentro de la misma transacción
    que el cambio que registra.
    """
    sql = ("INSERT INTO movimientos (fecha, tipo, titulo, detalle, unidades, pedido_id) "
           "VALUES (?, ?, ?, ?, ?, ?)")
    datos = (ahora_iso(), tipo, titulo, detalle, unidades, pedido_id)
    if con is not None:
        con.execute(sql, datos)
    else:
        with conectar() as c:
            c.execute(sql, datos)


def movimientos(limite: int = 20) -> list:
    with conectar() as con:
        filas = con.execute(
            "SELECT * FROM movimientos ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
    return [dict(f) for f in filas]
