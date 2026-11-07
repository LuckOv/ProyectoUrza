import base64
import csv
import io
import os
import re
from datetime import timedelta
from typing import Optional

from django.http import HttpResponse
from django_ratelimit.core import is_ratelimited
from langchain_core.messages import HumanMessage
from ninja import Header, NinjaAPI, Router, Schema
from ninja.errors import HttpError
from ninja.security import APIKeyHeader

from panel import bot
from tienda import base, cartas, inventario, propuestas, tienda
from agentes import karn

# Inicializar base de datos y tareas en segundo plano
base.preparar()
inventario.importar_csv_viejo()
inventario.completar_en_segundo_plano()

api = NinjaAPI(
    title="URZA API (Django)",
    version="1.0.0",
    description="API HTTP de URZA impulsada por Django, Django Ninja y LangGraph",
)


# --- Manejo Global de Errores ---
@api.exception_handler(ValueError)
def valor_error_handler(request, exc):
    return api.create_response(request, {"detail": str(exc)}, status=400)


# --- Seguridad y Autenticación del Vendedor ---
class VendedorAuth(APIKeyHeader):
    param_name = "X-Vendedor-Clave"

    def authenticate(self, request, key):
        esperada = os.getenv("VENDEDOR_CLAVE") or "urza"
        if key and key == esperada:
            return key
        return None


vendedor_router = Router(auth=VendedorAuth())
vendedor_publico = Router()


# --- Esquemas Pydantic / Ninja ---
class Consulta(Schema):
    thread_id: str
    texto: str
    imagen_base64: Optional[str] = None


class ConsultaVision(Schema):
    imagen_base64: str
    consulta: Optional[str] = ""


class ItemCarrito(Schema):
    inventario_id: int
    cantidad: int = 1


class NuevaPropuesta(Schema):
    thread_id: Optional[str] = None
    nombre: str
    apellido: str
    email: str
    scryfall_id: str
    grado: str = "Sin graduar"
    cantidad: int = 1
    precio: float
    moneda: str = "ARS"
    comentario: str = ""


class Clave(Schema):
    clave: str


class AltaCarta(Schema):
    scryfall_id: str
    grado: str = "Sin graduar"
    cantidad: int = 1
    precio_usd: Optional[float] = None


class EdicionCarta(Schema):
    grado: Optional[str] = None
    precio_usd: Optional[float] = None
    cantidad: Optional[int] = None
    motivo: str = ""


class Ids(Schema):
    ids: list[int]


class NuevaVariante(Schema):
    grado: str
    cantidad: int = 1
    precio_usd: Optional[float] = None


class LineaPedido(Schema):
    inventario_id: int
    cantidad: int


class NuevoPedido(Schema):
    nombre: str
    apellido: str
    fecha_retiro: str
    hora_retiro: str
    items: list[LineaPedido]
    comentario: str = ""


class CambioPedido(Schema):
    estado: Optional[str] = None
    comentario: Optional[str] = None
    fecha_retiro: Optional[str] = None
    hora_retiro: Optional[str] = None


class CambioPropuesta(Schema):
    estado: Optional[str] = None
    comentario: Optional[str] = None


class PropuestaAlInventario(Schema):
    precio_usd: Optional[float] = None
    cantidad: Optional[int] = None


class InstalarBot(Schema):
    partes: list[str]


class DolarConf(Schema):
    modo: str
    casa: str = "blue"
    valor: Optional[float] = None


class ConfiguracionSchema(Schema):
    alerta_precio: Optional[float] = None
    multiplicadores: Optional[dict] = None
    horarios: Optional[dict] = None
    dolar: Optional[DolarConf] = None
    stock_bajo: Optional[int] = None


class Porcentaje(Schema):
    porcentaje: float


class DescuentoCartas(Schema):
    ids: list[int]
    porcentaje: float


# --- Endpoints Públicos de la Tienda ---

@api.get("/salud")
def salud(request):
    """Chequeo de salud del backend y del agente."""
    try:
        from agentes.graph import app_graph
        _ = app_graph
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@api.get("/catalogo")
def catalogo(request):
    return {"items": inventario.catalogo()}


@api.get("/carta")
def carta(request, nombre: str):
    encontrada = cartas.buscar(nombre)
    if not encontrada:
        raise HttpError(404, f"No encontré la carta '{nombre}'.")
    return encontrada


@api.get("/cartas/autocompletar")
def cartas_autocompletar(request, q: str):
    return {"nombres": cartas.autocompletar(q), "grados": inventario.GRADOS}


@api.get("/cartas/impresiones")
def cartas_impresiones(request, nombre: str):
    return {"impresiones": cartas.impresiones(nombre)}


# --- Carrito ---

@api.get("/carrito/{thread_id}")
def ver_carrito(request, thread_id: str):
    return {"items": tienda.ver_carrito(thread_id)}


@api.post("/carrito/{thread_id}")
def agregar_al_carrito(request, thread_id: str, item: ItemCarrito):
    try:
        items = tienda.agregar(thread_id, item.inventario_id, item.cantidad)
    except ValueError as e:
        raise HttpError(409, str(e))
    return {"items": items}


@api.delete("/carrito/{thread_id}/{item_id}")
def quitar_del_carrito(request, thread_id: str, item_id: int):
    return {"items": tienda.quitar(thread_id, item_id)}


@api.delete("/carrito/{thread_id}")
def vaciar_carrito(request, thread_id: str):
    return {"items": tienda.vaciar(thread_id)}


# --- Propuestas de Clientes ---

@api.post("/propuestas")
def nueva_propuesta(request, datos: NuevaPropuesta):
    # Rate limiting: máximo 10 propuestas por minuto por IP para mitigar spam
    if is_ratelimited(request, group="propuestas", key="ip", rate="10/m", increment=True):
        raise HttpError(429, "Demasiadas propuestas enviadas. Esperá un minuto.")

    try:
        return propuestas.crear(
            datos.thread_id, datos.nombre, datos.apellido, datos.email, datos.scryfall_id,
            datos.grado, datos.cantidad, datos.precio, datos.moneda, datos.comentario,
        )
    except ValueError as e:
        raise HttpError(400, str(e))


# --- Visión por Computadora (Karn) ---

def _decodificar_imagen(b64_str: str) -> tuple[bytes, str]:
    mime = "image/jpeg"
    if "," in b64_str:
        header, b64_str = b64_str.split(",", 1)
        if "png" in header:
            mime = "image/png"
        elif "webp" in header:
            mime = "image/webp"
    return base64.b64decode(b64_str), mime


@api.post("/vision/carta")
def vision_identificar_carta(request, datos: ConsultaVision):
    """Karn identifica una carta física individual a partir de una foto y revisa el stock."""
    try:
        img_bytes, mime = _decodificar_imagen(datos.imagen_base64)
        return karn.identificar_carta(img_bytes, mime)
    except Exception as e:
        raise HttpError(400, f"Error al procesar la imagen: {e}")


@api.post("/vision/mesa")
def vision_analizar_mesa(request, datos: ConsultaVision):
    """Karn analiza el campo de batalla y consulta a Ajani sobre la validez de la jugada."""
    try:
        img_bytes, mime = _decodificar_imagen(datos.imagen_base64)
        return karn.analizar_mesa_y_jugada(img_bytes, datos.consulta or "", mime)
    except Exception as e:
        raise HttpError(400, f"Error al procesar la imagen: {e}")


# --- Chat con Urza (LangGraph + Rate Limiting + Visión) ---

_grafo = None
_SIN_CARTA = {"quitar_del_carrito"}
_NO_ES_VENTA = {
    "consultar_reglas_mtg", "consultar_lore_mtg", "sugerir_cartas_mazo", "agregar_al_carrito",
    "ver_carrito", "quitar_del_carrito", "confirmar_compra", "listar_cartas_disponibles",
}
AGENTE_DE = {
    "consultar_reglas_mtg": "Ajani",
    "consultar_lore_mtg": "Teferi",
    "sugerir_cartas_mazo": "Saheeli",
    "identificar_carta": "Karn",
}


def _obtener_grafo():
    global _grafo
    if _grafo is None:
        from agentes.graph import app_graph
        _grafo = app_graph
    return _grafo


@api.post("/chat")
def chat(request, consulta: Consulta):
    # Rate limiting: 45 consultas por minuto por IP para proteger tokens de Groq
    if is_ratelimited(request, group="chat", key="ip", rate="45/m", increment=True):
        return {
            "texto": "Estás enviando mensajes muy rápido. Por favor esperá unos segundos antes de continuar.",
            "herramientas": [], "carta": None, "carrito": tienda.ver_carrito(consulta.thread_id),
            "pedido": None, "mazo": None, "catalogo": False, "propuesta": None, "agentes": [],
            "error": "Rate limit superado",
        }

    vacia = {
        "texto": "", "herramientas": [], "carta": None,
        "carrito": tienda.ver_carrito(consulta.thread_id), "pedido": None,
        "mazo": None, "catalogo": False, "propuesta": None, "agentes": [],
    }

    # Si el jugador adjuntó una imagen, Karn toma la delantera
    if consulta.imagen_base64:
        try:
            img_bytes, mime = _decodificar_imagen(consulta.imagen_base64)
            texto_lower = (consulta.texto or "").lower()
            es_mesa = any(p in texto_lower for p in ("mesa", "jugada", "valida", "válida", "bloque", "ataca", "puedo", "regla", "juego", "turno", "partida"))

            if es_mesa:
                res_mesa = karn.analizar_mesa_y_jugada(img_bytes, consulta.texto, mime)
                if not res_mesa.get("exito"):
                    return {**vacia, "error": res_mesa.get("error", "Error de visión")}
                return {
                    **vacia,
                    "texto": f"**Karn (Análisis de mesa):**\n{res_mesa['analisis_mesa']}\n\n**Ajani (Dictamen de reglas):**\n{res_mesa['dictamen_reglas']}",
                    "herramientas": [{"nombre": "analizar_mesa_karn", "argumentos": {}, "resultado": "Mesa analizada con éxito"}],
                    "agentes": ["Karn", "Ajani"],
                }
            else:
                res_carta = karn.identificar_carta(img_bytes, mime)
                if not res_carta.get("exito"):
                    return {**vacia, "error": res_carta.get("error", "Error de visión")}

                nombre = res_carta["nombre"]
                if res_carta["en_stock"]:
                    desde = f" (desde ${res_carta['variantes'][0]['precio_ars']})" if res_carta["variantes"] else ""
                    stock_msg = f"Tenemos {res_carta['unidades_stock']} unidades en stock en la tienda{desde}. ¿Querés que te la sume al carrito?"
                else:
                    stock_msg = "No nos queda stock en este momento en la tienda."

                desc = f" {res_carta['detalles']}" if res_carta.get("detalles") else ""
                msg = f"Karn observó la carta: es **{nombre}** ({res_carta.get('set_codigo') or 's/set'}, {res_carta.get('grado', 'Sin graduar')}).{desc}\n\n{stock_msg}"

                return {
                    **vacia,
                    "texto": msg,
                    "carta": res_carta.get("carta"),
                    "herramientas": [{"nombre": "identificar_carta_karn", "argumentos": {"carta": nombre}, "resultado": f"Carta identificada: {nombre}"}],
                    "agentes": ["Karn", "Tibalt"],
                }
        except Exception as e:
            return {**vacia, "error": f"Fallo al procesar la imagen con Karn: {e}"}

    try:
        grafo = _obtener_grafo()
    except Exception as e:
        return {**vacia, "error": f"No pude iniciar el agente: {e}"}

    config = {"configurable": {"thread_id": consulta.thread_id}}

    try:
        estado = grafo.invoke({"messages": [HumanMessage(content=consulta.texto)]}, config=config)
    except Exception as e:
        return {**vacia, "error": f"Falló la consulta al agente: {e}"}

    mensajes = estado.get("messages", [])
    if not mensajes:
        return {**vacia, "error": "El agente no devolvió ningún mensaje."}

    corte = 0
    for i in range(len(mensajes) - 1, -1, -1):
        if getattr(mensajes[i], "type", "") == "human":
            corte = i
            break
    tramo = mensajes[corte + 1:]

    herramientas = []
    args_por_id = {}
    ultimo_nombre = None
    pedido = None
    mazo = None
    catalogo_pedido = False
    propuesta = None
    agentes = []

    for m in tramo:
        for llamada in getattr(m, "tool_calls", None) or []:
            args_por_id[llamada.get("id")] = (llamada.get("name", ""), llamada.get("args", {}))
        if getattr(m, "type", "") == "tool":
            nombre, args = args_por_id.get(
                getattr(m, "tool_call_id", None),
                (getattr(m, "name", "herramienta"), {}),
            )
            resultado = str(m.content)
            herramientas.append({"nombre": nombre, "argumentos": args, "resultado": resultado})
            if nombre not in _SIN_CARTA and isinstance(args, dict) and args.get("nombre_carta"):
                ultimo_nombre = args["nombre_carta"]
            if nombre == "confirmar_compra" and resultado.startswith("Pedido #"):
                pedido = resultado
            if nombre == "sugerir_cartas_mazo" and getattr(m, "artifact", None):
                mazo = [{"nombre": c["nombre"], "imagen": c.get("imagen")} for c in m.artifact]
            if nombre == "listar_cartas_disponibles":
                catalogo_pedido = True
            if nombre == "iniciar_propuesta" and getattr(m, "artifact", None) is not None:
                propuesta = m.artifact
            quien = AGENTE_DE.get(nombre, "Tibalt")
            if quien not in agentes:
                agentes.append(quien)

    from agentes.agent_sales import sin_razonamiento
    texto = sin_razonamiento(tramo[-1].content) if tramo else ""

    usadas = {h["nombre"] for h in herramientas}
    if propuesta is None and not (usadas & _NO_ES_VENTA) and propuestas.quiere_vender(consulta.texto):
        propuesta = propuestas.datos_desde_texto(consulta.texto)
        texto = propuestas.TEXTO_FORMULARIO
        if "Tibalt" not in agentes:
            agentes.append("Tibalt")

    if not texto:
        texto = "No obtuve una respuesta del agente para esa consulta. Probá reformulándola."

    return {
        "texto": texto,
        "herramientas": herramientas,
        "carta": cartas.buscar(ultimo_nombre) if ultimo_nombre and propuesta is None else None,
        "carrito": tienda.ver_carrito(consulta.thread_id),
        "pedido": pedido,
        "mazo": mazo,
        "catalogo": catalogo_pedido,
        "propuesta": propuesta,
        "agentes": agentes,
        "error": "",
    }


# --- Endpoints de Mesa Central (Panel del Vendedor) ---

@vendedor_publico.post("/entrar")
def entrar(request, datos: Clave):
    esperada = os.getenv("VENDEDOR_CLAVE") or "urza"
    if datos.clave != esperada:
        raise HttpError(401, "Clave de vendedor incorrecta.")
    return {"ok": True, "clave_por_defecto": not os.getenv("VENDEDOR_CLAVE")}


@vendedor_router.get("/inventario")
def ver_inventario(request, q: Optional[str] = None, estado: Optional[str] = None):
    inventario.refrescar_mercado()
    items = inventario.listar(q, estado)
    return {
        "items": items,
        "cartas": len(items),
        "unidades": sum(i["cantidad"] for i in items),
        "grados": inventario.GRADOS,
        "dolar": inventario.valor_dolar(),
        "alerta_precio": base.config("alerta_precio"),
    }


@vendedor_router.post("/inventario")
def alta_carta(request, datos: AltaCarta):
    try:
        return inventario.alta(datos.scryfall_id, datos.grado, datos.cantidad, datos.precio_usd)
    except ValueError as e:
        raise HttpError(400, str(e))


@vendedor_router.patch("/inventario/{item_id}")
def editar_carta(request, item_id: int, datos: EdicionCarta):
    try:
        return inventario.editar(item_id, datos.grado, datos.precio_usd, datos.cantidad, datos.motivo)
    except ValueError as e:
        raise HttpError(400, str(e))


@vendedor_router.post("/inventario/{item_id}/variante")
def nueva_variante(request, item_id: int, datos: NuevaVariante):
    try:
        return inventario.agregar_variante(item_id, datos.grado, datos.cantidad, datos.precio_usd)
    except ValueError as e:
        raise HttpError(400, str(e))


@vendedor_router.post("/inventario/{item_id}/mantener-precio")
def mantener_precio(request, item_id: int):
    try:
        return inventario.mantener_precio(item_id)
    except ValueError as e:
        raise HttpError(400, str(e))


@vendedor_router.get("/precio-sugerido")
def precio_sugerido(request, grado: str, scryfall_id: Optional[str] = None, item_id: Optional[int] = None):
    nombre, set_nombre, base_usd = "", None, None
    item = inventario.obtener(item_id) if item_id else None
    if item:
        scryfall_id = scryfall_id or item["scryfall_id"]
        nombre, set_nombre = item["nombre"], item["set_nombre"]
    if scryfall_id:
        imp = cartas.impresion_por_id(scryfall_id)
        if imp:
            nombre, set_nombre, base_usd = imp["nombre"], imp["set_nombre"], imp["precio_usd"]
    if base_usd is None and item:
        sin_graduar = [v for v in inventario.variantes_de(item["nombre"])
                       if v["grado"] == "Sin graduar" and v["set_nombre"] == item["set_nombre"]]
        if sin_graduar:
            base_usd = sin_graduar[0]["precio_usd"]
    return inventario.precio_sugerido(grado, base_usd, nombre, set_nombre)


@vendedor_router.post("/inventario/borrar")
def borrar_cartas(request, datos: Ids):
    return {"borradas": inventario.borrar(datos.ids)}


@vendedor_router.get("/scryfall/autocompletar")
def autocompletar(request, q: str):
    return {"nombres": cartas.autocompletar(q)}


@vendedor_router.get("/scryfall/impresiones")
def impresiones(request, nombre: str):
    lista = cartas.impresiones(nombre)
    if not lista:
        raise HttpError(404, f"Scryfall no devolvió impresiones de '{nombre}'.")
    return {"impresiones": lista, "dolar": inventario.valor_dolar()}


# --- Pedidos Vendedor ---

@vendedor_router.get("/pedidos")
def ver_pedidos(request, desde: Optional[str] = None, hasta: Optional[str] = None,
                estado: Optional[str] = None, q: Optional[str] = None, por: str = "retiro"):
    return {"pedidos": tienda.listar_pedidos(desde, hasta, estado, q, por), "estados": tienda.ESTADOS}


@vendedor_router.post("/pedidos")
def nuevo_pedido(request, datos: NuevoPedido):
    try:
        return tienda.crear_pedido_manual(
            datos.nombre, datos.apellido, datos.fecha_retiro, datos.hora_retiro,
            [l.dict() for l in datos.items], datos.comentario,
        )
    except ValueError as e:
        raise HttpError(409, str(e))


@vendedor_router.patch("/pedidos/{pedido_id}")
def cambiar_pedido(request, pedido_id: int, datos: CambioPedido):
    try:
        return tienda.actualizar_pedido(
            pedido_id, datos.estado, datos.comentario, datos.fecha_retiro, datos.hora_retiro
        )
    except ValueError as e:
        raise HttpError(409, str(e))


@vendedor_router.post("/pedidos/borrar")
def borrar_pedidos(request, datos: Ids):
    return {"borrados": tienda.borrar_pedidos(datos.ids)}


@vendedor_router.get("/historial.csv")
def exportar_historial(request, desde: Optional[str] = None, hasta: Optional[str] = None,
                       estado: Optional[str] = None, q: Optional[str] = None, por: str = "pedido"):
    pedidos = tienda.listar_pedidos(desde, hasta, estado, q, por)
    salida = io.StringIO()
    salida.write("\ufeff")
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
    response = HttpResponse(salida.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return response


# --- Dashboard ---

from panel.vendedor import _alertas, _rankings, _ventas_ultimo_mes

@vendedor_router.get("/dashboard")
def dashboard(request, dias: int = 30):
    inventario.refrescar_mercado()
    items = inventario.listar()
    hoy = base.ahora().date()
    inicio_mes = hoy.replace(day=1).isoformat()

    pedidos = tienda.listar_pedidos()
    pendientes = [p for p in pedidos if p["estado"] == "pendiente"]

    with base.conectar() as con:
        entradas_mes = con.execute(
            "SELECT COALESCE(SUM(unidades), 0) FROM movimientos WHERE tipo = 'entrada' AND substr(fecha, 1, 10) >= ?",
            (inicio_mes,),
        ).fetchone()[0]

    en_standard = {inventario._plano(i["nombre"]) for i in items if i["legal_standard"] and i["cantidad"] > 0}
    ventas_dias, ventas_cartas = _ventas_ultimo_mes(pedidos, hoy)
    desde_rank = (hoy - timedelta(days=dias - 1)).isoformat() if dias and dias > 0 else None

    return {
        "ventas_dias": ventas_dias,
        "ventas_cartas": ventas_cartas,
        "rankings": _rankings(pedidos, desde_rank),
        "periodo": dias,
        "alertas": _alertas(items, pedidos, hoy),
        "propuestas_nuevas": propuestas.contar_nuevas(),
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
            "vendido_30": sum(d["unidades"] for d in ventas_dias),
        },
        "ventas_30": round(sum(d["total"] for d in ventas_dias)),
        "actividad": base.movimientos(8),
        "proximos": sorted(pendientes, key=lambda p: (p["fecha_retiro"], p["hora_retiro"]))[:8],
        "standard": {"tienda": len(en_standard), "total": cartas.total_pool_standard()},
        "dolar": inventario.valor_dolar(),
    }


@vendedor_router.post("/mercado/actualizar")
def actualizar_mercado(request):
    n = inventario.refrescar_mercado(forzar=True)
    return {"actualizadas": n}


@vendedor_router.get("/alertas-precio")
def alertas_precio(request):
    inventario.refrescar_mercado()
    items = [i for i in inventario.listar() if i["alerta_precio"]]
    return {"items": sorted(items, key=lambda i: -abs(i["alerta_pct"])),
            "umbral": float(base.config("alerta_precio") or 30)}


@vendedor_router.get("/propuestas")
def ver_propuestas(request, estado: Optional[str] = None, q: Optional[str] = None):
    return {"propuestas": propuestas.listar(estado, q), "estados": propuestas.ESTADOS,
            "nuevas": propuestas.contar_nuevas(), "dolar": inventario.valor_dolar()}


@vendedor_router.patch("/propuestas/{pid}")
def cambiar_propuesta(request, pid: int, datos: CambioPropuesta):
    try:
        return propuestas.actualizar(pid, datos.estado, datos.comentario)
    except ValueError as e:
        raise HttpError(400, str(e))


@vendedor_router.post("/propuestas/{pid}/al-inventario")
def propuesta_al_inventario(request, pid: int, datos: PropuestaAlInventario):
    try:
        return propuestas.al_inventario(pid, datos.precio_usd, datos.cantidad)
    except ValueError as e:
        raise HttpError(400, str(e))


@vendedor_router.delete("/propuestas/{pid}")
def borrar_propuesta(request, pid: int):
    propuestas.borrar(pid)
    return {"ok": True}


@vendedor_router.get("/bot")
def estado_bot(request):
    return bot.estado()


@vendedor_router.post("/bot/instalar")
def instalar_bot(request, datos: InstalarBot):
    try:
        return bot.instalar(datos.partes)
    except ValueError as e:
        raise HttpError(409, str(e))


@vendedor_router.post("/bot/cancelar")
def cancelar_bot(request):
    return bot.cancelar()


@vendedor_router.get("/actividad")
def actividad(request, q: Optional[str] = None, tipo: Optional[str] = None,
              limite: int = 50, antes_de: Optional[int] = None):
    limite = max(1, min(limite, 200))
    filas = base.movimientos(limite + 1, q, tipo, antes_de)
    return {"movimientos": filas[:limite], "hay_mas": len(filas) > limite}


from panel.vendedor import _config_completa, _validar_horarios

@vendedor_router.get("/config")
def ver_config(request):
    return _config_completa()


@vendedor_router.put("/config")
def guardar_config(request, datos: ConfiguracionSchema):
    try:
        if datos.multiplicadores is not None:
            inventario.guardar_multiplicadores(datos.multiplicadores)
        if datos.alerta_precio is not None:
            if not 5 <= datos.alerta_precio <= 300:
                raise ValueError("El aviso de diferencia de precio tiene que estar entre 5% y 300%.")
            anterior = base.config("alerta_precio")
            base.guardar_config("alerta_precio", datos.alerta_precio)
            if datos.alerta_precio != anterior:
                base.registrar_movimiento(
                    "config", "Aviso de diferencia de precio actualizado", f"{anterior}% → {datos.alerta_precio:g}%")
        if datos.horarios is not None:
            anterior = base.horarios_texto()
            base.guardar_config("horarios", _validar_horarios(datos.horarios))
            if base.horarios_texto() != anterior:
                base.registrar_movimiento("config", "Horarios de la tienda actualizados", base.horarios_texto())
        if datos.stock_bajo is not None:
            if datos.stock_bajo < 0:
                raise ValueError("El umbral de stock bajo no puede ser negativo.")
            anterior = base.config("stock_bajo")
            base.guardar_config("stock_bajo", datos.stock_bajo)
            if datos.stock_bajo != anterior:
                base.registrar_movimiento(
                    "config", "Aviso de stock bajo actualizado",
                    f"{anterior} → {datos.stock_bajo} unidades o menos",
                )
        if datos.dolar is not None:
            if datos.dolar.modo not in ("manual", "auto"):
                raise ValueError("Modo de dólar inválido.")
            if datos.dolar.casa not in inventario.CASAS_DOLAR:
                raise ValueError("Tipo de dólar inválido.")
            conf = base.config("dolar")
            antes = (conf.get("modo"), conf.get("casa"), conf.get("valor"))
            conf.update(modo=datos.dolar.modo, casa=datos.dolar.casa)
            if datos.dolar.modo == "manual":
                if not datos.dolar.valor or datos.dolar.valor <= 0:
                    raise ValueError("Poné un valor de dólar mayor a cero.")
                conf.update(valor=float(datos.dolar.valor), actualizado=base.ahora_iso())
            else:
                conf.update(valor=inventario.traer_dolar(datos.dolar.casa), actualizado=base.ahora_iso())
            base.guardar_config("dolar", conf)
            if (conf["modo"], conf["casa"], conf["valor"]) != antes:
                modo = "manual" if conf["modo"] == "manual" else f"automático ({conf['casa']})"
                base.registrar_movimiento(
                    "config", "Precio del dólar actualizado",
                    f"{modo} · ${conf['valor']:,.0f}".replace(",", "."),
                )
    except ValueError as e:
        raise HttpError(400, str(e))
    return _config_completa()


@vendedor_router.post("/config/dolar/actualizar")
def actualizar_dolar(request):
    conf = base.config("dolar")
    try:
        conf.update(valor=inventario.traer_dolar(conf.get("casa", "blue")), actualizado=base.ahora_iso())
    except ValueError as e:
        raise HttpError(502, str(e))
    base.guardar_config("dolar", conf)
    base.registrar_movimiento(
        "config", "Cotización del dólar actualizada a mano",
        f"{conf.get('casa', 'blue')} · ${conf['valor']:,.0f}".replace(",", "."),
    )
    return _config_completa()


@vendedor_router.get("/descuentos")
def ver_descuentos(request):
    return inventario.listar_descuentos()


@vendedor_router.put("/descuentos/general")
def descuento_general(request, datos: Porcentaje):
    try:
        inventario.guardar_descuento_general(datos.porcentaje)
    except ValueError as e:
        raise HttpError(400, str(e))
    return inventario.listar_descuentos()


@vendedor_router.post("/descuentos")
def descuento_cartas(request, datos: DescuentoCartas):
    try:
        inventario.poner_descuento(datos.ids, datos.porcentaje)
    except ValueError as e:
        raise HttpError(400, str(e))
    return inventario.listar_descuentos()


@vendedor_router.delete("/descuentos/{descuento_id}")
def quitar_descuento(request, descuento_id: int):
    inventario.quitar_descuento(descuento_id)
    return inventario.listar_descuentos()


# Registrar los routers en la NinjaAPI
api.add_router("/vendedor", vendedor_publico)
api.add_router("/vendedor", vendedor_router)
