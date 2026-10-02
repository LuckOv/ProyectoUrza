import urllib.parse
from datetime import date

import requests
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

import base
import cartas
import inventario
import tienda
from cartas import _plano, ficha, resolver_nombre
from lore import consultar_lore_mtg
from reglas import consultar_reglas_mtg

# Cabecera obligatoria que exige la API de Scryfall para no bloquear la petición
HEADERS = {
    "User-Agent": "UrzaBot/1.0 (ProyectoEstudiantilISFT197)",
    "Accept": "application/json"
}


def _pesos(valor) -> str:
    """12345.6 → '$12.346' (formato argentino, sin centavos)."""
    if valor is None:
        return "sin precio"
    return "$" + f"{round(valor):,}".replace(",", ".")


def _linea_variante(v: dict) -> str:
    precio = _pesos(v["precio_ars"])
    if v["descuento"]:
        precio += f" (con {v['descuento']:g}% off, antes {_pesos(v['precio_lista_ars'])})"
    stock = f"{v['cantidad']} en stock" if v["cantidad"] > 0 else "sin stock"
    return f"- [variante {v['id']}] {v['set_nombre'] or 's/set'} · {v['grado']} · {precio} · {stock}"


@tool
def consultar_precio_cardmarket(nombre_carta: str) -> str:
    """Consulta el precio actual de una carta en euros usando la API de Scryfall.

    Acepta el nombre en cualquier idioma y con errores de tipeo: antes de
    buscar lo traduce al nombre oficial en inglés.
    """
    # Extraer el valor si viene empacado como dict
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")

    nombre_limpio = resolver_nombre(nombre_carta) or str(nombre_carta).strip()
    print(f"\n[DEBUG TOOL] Solicitando a Scryfall: '{nombre_limpio}'")
    
    nombre_encoded = urllib.parse.quote(nombre_limpio)
    
    # 1. Intento por nombre exacto
    url_exact = f"https://api.scryfall.com/cards/named?exact={nombre_encoded}"
    respuesta = requests.get(url_exact, headers=HEADERS)
    
    if respuesta.status_code == 200:
        datos = respuesta.json()
        precio_eur = datos.get("prices", {}).get("eur") 
        if precio_eur:
            return f"El precio actual de '{datos.get('name')}' en CardMarket (vía Scryfall) es de €{precio_eur}."
        return f"Encontré la carta '{datos.get('name')}', pero Scryfall no registra un precio en euros actualmente."
    
    # 2. Fallback por búsqueda difusa (Fuzzy)
    url_fuzzy = f"https://api.scryfall.com/cards/named?fuzzy={nombre_encoded}"
    resp_fuzzy = requests.get(url_fuzzy, headers=HEADERS)
    
    if resp_fuzzy.status_code == 200:
        datos = resp_fuzzy.json()
        precio_eur = datos.get("prices", {}).get("eur")
        if precio_eur:
            return f"El precio actual de '{datos.get('name')}' en CardMarket (vía Scryfall) es de €{precio_eur}."
        return f"Encontré la carta '{datos.get('name')}', pero no registra precio en euros."
        
    return f"No pude encontrar la carta '{nombre_limpio}' en Scryfall (Código HTTP: {respuesta.status_code}). Verifica el nombre en inglés."


@tool
def consultar_stock_local(nombre_carta: str) -> str:
    """Revisa en el inventario de la tienda si hay stock de una carta y a qué precio.

    Devuelve cada variante que tiene la tienda (set y grado: Sin graduar,
    PSA 10, etc.) con su precio en pesos y unidades. Acepta el nombre en
    cualquier idioma y con errores de tipeo.
    """
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")

    original = str(nombre_carta).strip()
    nombre_limpio = resolver_nombre(original) or original

    try:
        variantes = inventario.variantes_de(nombre_limpio)
    except Exception as e:
        return f"Error al acceder al inventario: {e}"

    if not variantes:
        return f"La carta '{nombre_limpio}' no figura en el inventario de la tienda."
    total = sum(v["cantidad"] for v in variantes)
    encabezado = (
        f"Stock de '{variantes[0]['nombre']}': {total} unidades en total."
        if total else f"No nos queda stock de '{variantes[0]['nombre']}'."
    )
    return encabezado + "\n" + "\n".join(_linea_variante(v) for v in variantes)


@tool
def consultar_datos_carta(nombre_carta: str) -> str:
    """Trae los datos reales de una carta: tipo, colores, coste, texto de reglas,
    rareza, en qué formatos es legal y cómo se llama en español.

    Usar SIEMPRE antes de afirmar cualquier característica de una carta. Es la
    única fuente válida para decir de qué tipo o color es algo.
    """
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")

    datos = ficha(str(nombre_carta).strip())
    if not datos:
        return f"No encontré ninguna carta llamada '{nombre_carta}' en Scryfall."

    partes = [f"Nombre oficial (inglés): {datos['nombre']}"]
    if datos.get("nombre_es"):
        partes.append(f"Nombre en español: {datos['nombre_es']}")
    if datos.get("coste"):
        partes.append(f"Coste de maná: {datos['coste']}")
    partes.append(f"Tipo: {datos['tipo']}")
    if datos.get("tipo_es"):
        partes.append(f"Tipo en español: {datos['tipo_es']}")
    partes.append(f"Colores: {', '.join(datos['colores']) if datos.get('colores') else 'incolora'}")
    if datos.get("fuerza_resistencia"):
        partes.append(f"Fuerza/Resistencia: {datos['fuerza_resistencia']}")
    if datos.get("texto"):
        partes.append(f"Texto de reglas: {datos['texto']}")
    if datos.get("texto_es"):
        partes.append(f"Texto en español: {datos['texto_es']}")
    partes.append(f"Rareza: {datos['rareza']}")
    if datos.get("legal_en"):
        partes.append(f"Legal en: {', '.join(datos['legal_en'])}")

    return "\n".join(partes)


# --- catálogo y mazos --------------------------------------------------------------

@tool
def listar_cartas_disponibles() -> str:
    """Resume qué cartas tiene la tienda a la venta (con stock y precio).

    Usar cuando el jugador pregunta qué cartas hay, qué tenés, o pide ver el
    catálogo. El chat le muestra al jugador un botón con la lista completa y
    un buscador, así que no hace falta enumerarlas todas.
    """
    items = inventario.catalogo()
    if not items:
        return "La tienda no tiene cartas con stock en este momento."
    nombres = list(dict.fromkeys(i["nombre"] for i in items))
    unidades = sum(i["cantidad"] for i in items)
    muestra = ", ".join(nombres[:8])
    return (
        f"La tienda tiene {len(nombres)} cartas distintas a la venta ({unidades} unidades). "
        f"Algunas: {muestra}{'…' if len(nombres) > 8 else '.'} "
        "El jugador ve la lista completa, con buscador, en el botón 'Ver todas las cartas' que aparece debajo de tu mensaje."
    )


@tool(response_format="content_and_artifact")
def sugerir_cartas_mazo(colores: str = "", formato: str = "standard", tipo: str = "",
                        palabras_clave: str = "", cantidad: int = 12):
    """Busca cartas candidatas para armar un mazo y marca cuáles hay en la tienda.

    Usar cuando el jugador pide ayuda para armar un mazo o pregunta qué cartas
    usar. Parámetros (todos opcionales):
    - colores: en español o en letras, ej. "rojo y verde", "azul negro", "RG".
    - formato: standard, pioneer, modern, pauper, commander... (por defecto standard).
    - tipo: criatura, instantáneo, conjuro, encantamiento, artefacto, tierra, planeswalker.
    - palabras_clave: en INGLÉS, tribu o mecánica, ej. "elf", "flying", "token", "lifelink".
    - cantidad: cuántas sugerir (máximo 20).
    Prioriza las que la tienda tiene en stock. El chat muestra las sugeridas
    como un abanico de cartas.
    """
    cantidad = max(4, min(int(cantidad or 12), 20))
    consulta = cartas.consulta_mazo(colores, formato, tipo, palabras_clave)
    candidatas = cartas.candidatas_mazo(consulta)
    if not candidatas:
        return (f"Scryfall no devolvió cartas para esa búsqueda ({consulta}). "
                "Probá con otros colores, formato o palabras clave.", [])

    # Stock de la tienda por nombre (todas las variantes juntas).
    stock = {}
    for i in inventario.catalogo():
        clave = _plano(i["nombre"])
        previo = stock.get(clave, {"cantidad": 0, "precio_ars": None})
        precios = [p for p in (previo["precio_ars"], i["precio_ars"]) if p is not None]
        stock[clave] = {"cantidad": previo["cantidad"] + i["cantidad"], "precio_ars": min(precios) if precios else None}

    en_tienda = [c for c in candidatas if _plano(c["nombre"]) in stock]
    resto = [c for c in candidatas if _plano(c["nombre"]) not in stock]
    elegidas = (en_tienda + resto)[:cantidad]

    lineas = []
    for c in elegidas:
        s = stock.get(_plano(c["nombre"]))
        donde = (f"EN LA TIENDA: {s['cantidad']} u., desde {_pesos(s['precio_ars'])}"
                 if s else "no está en la tienda")
        lineas.append(f"- {c['nombre']} ({c['tipo']}) — {donde}")
        c["en_stock"] = bool(s)

    texto = (
        f"Búsqueda en Scryfall: {consulta}. Candidatas ordenadas por popularidad, "
        f"primero las que hay en la tienda ({len(en_tienda)} de {len(candidatas)} encontradas):\n"
        + "\n".join(lineas)
        + "\nEl jugador ya ve estas cartas en un abanico debajo de tu mensaje."
    )
    return texto, elegidas


# --- compra --------------------------------------------------------------------
#
# El carrito es de la conversación. LangGraph le pasa a cada herramienta la
# config con la que se invocó el grafo; de ahí sale el thread_id. El
# parámetro `config` no lo ve el modelo: lo inyecta LangChain solo.

def _thread(config: RunnableConfig) -> str:
    return (config or {}).get("configurable", {}).get("thread_id", "")


def _resumen_carrito(items: list) -> str:
    if not items:
        return "El carrito está vacío."
    lineas = [
        f"- {i['cantidad']} x {i['nombre']} ({i['edicion'] or 's/set'}, {i['grado']}) a {_pesos(i['precio'])} c/u"
        for i in items
    ]
    return "Carrito actual:\n" + "\n".join(lineas) + f"\nTotal: {_pesos(tienda.total_de(items))}"


@tool
def agregar_al_carrito(nombre_carta: str, cantidad: int, config: RunnableConfig,
                       variante_id: int | None = None) -> str:
    """Agrega copias de una carta al carrito del jugador.

    Usar cuando el jugador dice que quiere comprar, llevar o reservar una
    carta. Si la tienda tiene la carta en más de una variante (set o grado)
    con stock y el jugador no eligió, la herramienta devuelve las opciones:
    preguntale cuál quiere y volvé a llamarla con `variante_id`.
    Controla sola que haya stock suficiente.
    """
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")
    cantidad = int(cantidad or 1)
    thread = _thread(config)

    if variante_id:
        elegida = inventario.obtener(int(variante_id))
        if not elegida:
            return f"No existe la variante {variante_id} en el inventario."
    else:
        original = str(nombre_carta).strip()
        oficial = resolver_nombre(original) or original
        variantes = inventario.variantes_de(oficial)
        if not variantes:
            return f"'{oficial}' no figura en el inventario de la tienda."
        con_stock = [v for v in variantes if v["cantidad"] > 0]
        if not con_stock:
            return f"No nos queda stock de '{variantes[0]['nombre']}'."
        if len(con_stock) > 1:
            return (
                f"Hay {len(con_stock)} variantes de '{con_stock[0]['nombre']}' con stock. "
                "Preguntale al jugador cuál quiere y volvé a llamar con variante_id:\n"
                + "\n".join(_linea_variante(v) for v in con_stock)
            )
        elegida = con_stock[0]

    try:
        items = tienda.agregar(thread, elegida["id"], cantidad)
    except ValueError as e:
        return f"No se pudo agregar: {e}"
    return (
        f"Agregué {cantidad} x '{elegida['nombre']}' ({elegida['set_nombre']}, {elegida['grado']}) al carrito.\n"
        + _resumen_carrito(items)
    )


@tool
def ver_carrito(config: RunnableConfig) -> str:
    """Muestra qué cartas tiene el jugador en el carrito y el total en pesos."""
    return _resumen_carrito(tienda.ver_carrito(_thread(config)))


@tool
def quitar_del_carrito(nombre_carta: str, config: RunnableConfig) -> str:
    """Saca una carta del carrito del jugador."""
    if isinstance(nombre_carta, dict):
        nombre_carta = nombre_carta.get("nombre_carta", "")
    original = str(nombre_carta).strip()
    oficial = resolver_nombre(original) or original
    thread = _thread(config)
    if not tienda.quitar_por_nombre(thread, oficial):
        return f"'{oficial}' no estaba en el carrito.\n" + _resumen_carrito(tienda.ver_carrito(thread))
    return f"Saqué '{oficial}' del carrito.\n" + _resumen_carrito(tienda.ver_carrito(thread))


@tool
def confirmar_compra(nombre: str, apellido: str, fecha_retiro: str, hora_retiro: str,
                     config: RunnableConfig) -> str:
    """Cierra la compra y registra el pedido para retirar en el local.

    Llamar SOLO cuando el jugador ya confirmó que quiere finalizar la compra
    y ya dio su nombre, su apellido y el día y la hora en que pasa a retirar.
    fecha_retiro va en formato AAAA-MM-DD y hora_retiro en HH:MM (24 hs),
    calculadas a partir de lo que dijo el jugador y la fecha de hoy.
    Si el horario no sirve, la herramienta explica por qué: transmitíselo al
    jugador y pedile otro. Nunca inventar ninguno de los datos.
    """
    try:
        pedido = tienda.confirmar_pedido(_thread(config), nombre, apellido, fecha_retiro, hora_retiro)
    except ValueError as e:
        return f"No se pudo confirmar la compra: {e}"

    dia = base.NOMBRE_DIA[base.DIAS[date.fromisoformat(pedido["fecha_retiro"]).weekday()]]
    d = pedido["fecha_retiro"]
    detalle = "\n".join(f"- {i['cantidad']} x {i['nombre']} ({i['grado']})" for i in pedido["items"])
    return (
        f"Pedido #{pedido['id']} confirmado a nombre de {pedido['nombre']} {pedido['apellido']}.\n"
        f"Retira: {dia} {d[8:10]}/{d[5:7]} a las {pedido['hora_retiro']} hs.\n"
        f"{detalle}\nTotal: {_pesos(pedido['total'])}"
    )


lista_tools = [
    consultar_precio_cardmarket,
    consultar_stock_local,
    consultar_datos_carta,
    consultar_reglas_mtg,
    consultar_lore_mtg,
    listar_cartas_disponibles,
    sugerir_cartas_mazo,
    agregar_al_carrito,
    ver_carrito,
    quitar_del_carrito,
    confirmar_compra,
]
