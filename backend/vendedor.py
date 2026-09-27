"""Endpoints del panel del vendedor (Mesa Central).

Todo cuelga de /vendedor y exige el header X-Vendedor-Clave con la clave
definida en backend/.env (VENDEDOR_CLAVE). El jugador nunca pasa por acá:
es la única puerta para escribir el inventario, tal como pide FE-08.
"""

import csv
import io
import os
import re
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import base
import cartas
import inventario
import tienda

load_dotenv()

CLAVE_POR_DEFECTO = "urza"


def _clave_vendedor() -> str:
    return os.getenv("VENDEDOR_CLAVE") or CLAVE_POR_DEFECTO


def solo_vendedor(x_vendedor_clave: str | None = Header(default=None)):
    if not x_vendedor_clave or x_vendedor_clave != _clave_vendedor():
        raise HTTPException(status_code=401, detail="Clave de vendedor incorrecta.")
    return True


router = APIRouter(prefix="/vendedor", tags=["vendedor"])
protegido = APIRouter(prefix="/vendedor", tags=["vendedor"], dependencies=[Depends(solo_vendedor)])


def _error(e: ValueError, codigo: int = 400):
    raise HTTPException(status_code=codigo, detail=str(e))


# --- entrada -----------------------------------------------------------------

class Clave(BaseModel):
    clave: str


@router.post("/entrar")
def entrar(datos: Clave):
    if datos.clave != _clave_vendedor():
        raise HTTPException(status_code=401, detail="Clave de vendedor incorrecta.")
    return {"ok": True, "clave_por_defecto": not os.getenv("VENDEDOR_CLAVE")}


# --- inventario --------------------------------------------------------------

class AltaCarta(BaseModel):
    scryfall_id: str
    grado: str = "Sin graduar"
    cantidad: int = 1
    precio_usd: float | None = None


class EdicionCarta(BaseModel):
    grado: str | None = None
    precio_usd: float | None = None
    cantidad: int | None = None
    motivo: str = ""


class Ids(BaseModel):
    ids: list[int]


@protegido.get("/inventario")
def ver_inventario(q: str | None = None, estado: str | None = None):
    items = inventario.listar(q, estado)
    return {
        "items": items,
        "cartas": len(items),
        "unidades": sum(i["cantidad"] for i in items),
        "grados": inventario.GRADOS,
        "dolar": inventario.valor_dolar(),
    }


@protegido.post("/inventario")
def alta_carta(datos: AltaCarta):
    try:
        return inventario.alta(datos.scryfall_id, datos.grado, datos.cantidad, datos.precio_usd)
    except ValueError as e:
        _error(e)


@protegido.patch("/inventario/{item_id}")
def editar_carta(item_id: int, datos: EdicionCarta):
    try:
        return inventario.editar(item_id, datos.grado, datos.precio_usd, datos.cantidad, datos.motivo)
    except ValueError as e:
        _error(e)


@protegido.post("/inventario/borrar")
def borrar_cartas(datos: Ids):
    return {"borradas": inventario.borrar(datos.ids)}


# --- Scryfall (para dar de alta) ---------------------------------------------

@protegido.get("/scryfall/autocompletar")
def autocompletar(q: str):
    return {"nombres": cartas.autocompletar(q)}


@protegido.get("/scryfall/impresiones")
def impresiones(nombre: str):
    lista = cartas.impresiones(nombre)
    if not lista:
        raise HTTPException(status_code=404, detail=f"Scryfall no devolvió impresiones de '{nombre}'.")
    return {"impresiones": lista, "dolar": inventario.valor_dolar()}


# --- pedidos -----------------------------------------------------------------

class LineaPedido(BaseModel):
    inventario_id: int
    cantidad: int


class NuevoPedido(BaseModel):
    nombre: str
    apellido: str
    fecha_retiro: str
    hora_retiro: str
    items: list[LineaPedido]
    comentario: str = ""


class CambioPedido(BaseModel):
    estado: str | None = None
    comentario: str | None = None
    fecha_retiro: str | None = None
    hora_retiro: str | None = None


@protegido.get("/pedidos")
def ver_pedidos(desde: str | None = None, hasta: str | None = None, estado: str | None = None,
                q: str | None = None, por: str = "retiro"):
    return {"pedidos": tienda.listar_pedidos(desde, hasta, estado, q, por), "estados": tienda.ESTADOS}


@protegido.post("/pedidos")
def nuevo_pedido(datos: NuevoPedido):
    try:
        return tienda.crear_pedido_manual(
            datos.nombre, datos.apellido, datos.fecha_retiro, datos.hora_retiro,
            [l.model_dump() for l in datos.items], datos.comentario,
        )
    except ValueError as e:
        _error(e, 409)


@protegido.patch("/pedidos/{pedido_id}")
def cambiar_pedido(pedido_id: int, datos: CambioPedido):
    try:
        return tienda.actualizar_pedido(
            pedido_id, datos.estado, datos.comentario, datos.fecha_retiro, datos.hora_retiro
        )
    except ValueError as e:
        _error(e, 409)


@protegido.post("/pedidos/borrar")
def borrar_pedidos(datos: Ids):
    return {"borrados": tienda.borrar_pedidos(datos.ids)}


@protegido.get("/historial.csv")
def exportar_historial(desde: str | None = None, hasta: str | None = None, estado: str | None = None,
                       q: str | None = None, por: str = "pedido"):
    """El protocolo de pedidos en CSV (separado por ';' para que Excel en español lo abra bien)."""
    pedidos = tienda.listar_pedidos(desde, hasta, estado, q, por)
    salida = io.StringIO()
    salida.write("﻿")   # BOM: Excel reconoce los acentos
    w = csv.writer(salida, delimiter=";")
    w.writerow(["Pedido", "Fecha y hora de retiro", "Fecha y hora de pedido", "Nombre",
                "Unidades", "Detalle", "Total ($)", "Estado", "Origen", "Comentario"])
    for p in pedidos:
        detalle = ", ".join(f"{i['cantidad']} x {i['nombre']} ({i['grado']})" for i in p["items"])
        w.writerow([
            p["id"], f"{p['fecha_retiro']} {p['hora_retiro']}", p["creado"][:16].replace("T", " "),
            f"{p['nombre']} {p['apellido']}", p["unidades"], detalle,
            f"{p['total']:.0f}", p["estado"], p["origen"], p["comentario"],
        ])
    nombre = f"historial_{base.ahora().date().isoformat()}.csv"
    return StreamingResponse(
        iter([salida.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


# --- dashboard ---------------------------------------------------------------

@protegido.get("/dashboard")
def dashboard():
    items = inventario.listar()
    hoy = base.ahora().date()
    inicio_mes = hoy.replace(day=1).isoformat()
    hace_30 = (hoy - timedelta(days=30)).isoformat()

    pedidos = tienda.listar_pedidos()
    pendientes = [p for p in pedidos if p["estado"] == "pendiente"]
    realizadas_30 = [p for p in pedidos if p["estado"] == "realizada" and p["actualizado"][:10] >= hace_30]

    with base.conectar() as con:
        entradas_mes = con.execute(
            "SELECT COALESCE(SUM(unidades), 0) FROM movimientos WHERE tipo = 'entrada' AND substr(fecha, 1, 10) >= ?",
            (inicio_mes,),
        ).fetchone()[0]

    # Cobertura del pool de Standard: cuántas cartas distintas legales en
    # Standard tiene la tienda con stock, sobre el total de Scryfall.
    en_standard = {inventario._plano(i["nombre"]) for i in items if i["legal_standard"] and i["cantidad"] > 0}

    return {
        "unidades": sum(i["cantidad"] for i in items),
        "cartas_distintas": len(items),
        "entradas_mes": entradas_mes,
        "valor_ars": round(sum((i["precio_ars"] or 0) * i["cantidad"] for i in items)),
        "valor_usd": round(sum((i["precio_usd"] or 0) * i["cantidad"] for i in items), 2),
        "pedidos_abiertos": len(pendientes),
        "retiros_hoy": sum(1 for p in pendientes if p["fecha_retiro"] == hoy.isoformat()),
        "sin_stock": sum(1 for i in items if i["estado_stock"] == "sin"),
        "stock_bajo": sum(1 for i in items if i["estado_stock"] == "bajo"),
        "stock": {
            "disponible": sum(i["cantidad"] for i in items),
            "reservado": sum(p["unidades"] for p in pendientes),
            "vendido_30": sum(p["unidades"] for p in realizadas_30),
        },
        "ventas_30": round(sum(p["total"] for p in realizadas_30)),
        "actividad": base.movimientos(8),
        "proximos": sorted(pendientes, key=lambda p: (p["fecha_retiro"], p["hora_retiro"]))[:5],
        "standard": {"tienda": len(en_standard), "total": cartas.total_pool_standard()},
        "dolar": inventario.valor_dolar(),
    }


# --- configuración -----------------------------------------------------------

class DolarConf(BaseModel):
    modo: str               # "manual" | "auto"
    casa: str = "blue"
    valor: float | None = None


class Configuracion(BaseModel):
    horarios: dict | None = None
    dolar: DolarConf | None = None
    stock_bajo: int | None = None


def _validar_horarios(horarios: dict) -> dict:
    limpio = {}
    for dia in base.DIAS:
        h = horarios.get(dia)
        if not h:
            limpio[dia] = None
            continue
        abre, cierra = str(h.get("abre", "")), str(h.get("cierra", ""))
        if not re.fullmatch(r"\d{2}:\d{2}", abre) or not re.fullmatch(r"\d{2}:\d{2}", cierra):
            raise ValueError(f"Horario inválido el {base.NOMBRE_DIA[dia]} (usá HH:MM).")
        if abre >= cierra:
            raise ValueError(f"El {base.NOMBRE_DIA[dia]} la hora de cierre tiene que ser después de la apertura.")
        limpio[dia] = {"abre": abre, "cierra": cierra}
    return limpio


def _config_completa():
    return {
        "horarios": base.config("horarios"),
        "horarios_texto": base.horarios_texto(),
        "dolar": inventario.dolar(),
        "stock_bajo": base.config("stock_bajo"),
        "casas": inventario.CASAS_DOLAR,
        "dias": [{"clave": d, "nombre": base.NOMBRE_DIA[d]} for d in base.DIAS],
    }


@protegido.get("/config")
def ver_config():
    return _config_completa()


@protegido.put("/config")
def guardar_config(datos: Configuracion):
    try:
        if datos.horarios is not None:
            base.guardar_config("horarios", _validar_horarios(datos.horarios))
        if datos.stock_bajo is not None:
            if datos.stock_bajo < 0:
                raise ValueError("El umbral de stock bajo no puede ser negativo.")
            base.guardar_config("stock_bajo", datos.stock_bajo)
        if datos.dolar is not None:
            if datos.dolar.modo not in ("manual", "auto"):
                raise ValueError("Modo de dólar inválido.")
            if datos.dolar.casa not in inventario.CASAS_DOLAR:
                raise ValueError("Tipo de dólar inválido.")
            conf = base.config("dolar")
            conf.update(modo=datos.dolar.modo, casa=datos.dolar.casa)
            if datos.dolar.modo == "manual":
                if not datos.dolar.valor or datos.dolar.valor <= 0:
                    raise ValueError("Poné un valor de dólar mayor a cero.")
                conf.update(valor=float(datos.dolar.valor), actualizado=base.ahora_iso())
            else:
                conf.update(valor=inventario.traer_dolar(datos.dolar.casa), actualizado=base.ahora_iso())
            base.guardar_config("dolar", conf)
    except ValueError as e:
        _error(e)
    return _config_completa()


@protegido.post("/config/dolar/actualizar")
def actualizar_dolar():
    conf = base.config("dolar")
    try:
        conf.update(valor=inventario.traer_dolar(conf.get("casa", "blue")), actualizado=base.ahora_iso())
    except ValueError as e:
        _error(e, 502)
    base.guardar_config("dolar", conf)
    return _config_completa()


# --- descuentos --------------------------------------------------------------

class Porcentaje(BaseModel):
    porcentaje: float


class DescuentoCartas(BaseModel):
    ids: list[int]
    porcentaje: float


@protegido.get("/descuentos")
def ver_descuentos():
    return inventario.listar_descuentos()


@protegido.put("/descuentos/general")
def descuento_general(datos: Porcentaje):
    try:
        inventario.guardar_descuento_general(datos.porcentaje)
    except ValueError as e:
        _error(e)
    return inventario.listar_descuentos()


@protegido.post("/descuentos")
def descuento_cartas(datos: DescuentoCartas):
    try:
        inventario.poner_descuento(datos.ids, datos.porcentaje)
    except ValueError as e:
        _error(e)
    return inventario.listar_descuentos()


@protegido.delete("/descuentos/{descuento_id}")
def quitar_descuento(descuento_id: int):
    inventario.quitar_descuento(descuento_id)
    return inventario.listar_descuentos()
