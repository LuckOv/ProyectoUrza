"""Subagente armador y optimizador de mazos: SAHEELI, con RAG de arquetipos y sinergias.

Cuando URZA detecta una consulta sobre:
- Cómo armar un mazo desde cero o qué cartas usar para una estrategia.
- Cómo mejorar, optimizar o ajustar un mazo existente (cortes y adiciones).
- Qué cartas de la tienda comprar para completar o potenciar un arquetipo.

Llama a Saheeli, quien:
1. Recupera las mejores guías de arquetipos, curvas de maná y ratios desde `mazos_db` (Chroma).
2. Cruza la estrategia con el stock e inventario real de la tienda (`inventario.catalogo()`).
3. Genera una recomendación técnica fundamentada indicando qué cartas de la tienda comprar y qué cartas sacar/sumar.
4. Devuelve las cartas sugeridas como artifact para mostrarlas en el abanico visual.
"""

from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agentes.reglas import (
    _expandir,
    _funcion_embedding,
    _funcion_rerank,
    _juez_llm,
    motivo_no_disponible,
    sin_razonamiento,
)
from tienda import cartas, inventario

BASE = Path(__file__).resolve().parent.parent
RAG_DIR = BASE / "mazos_db"
COLECCION = "arquetipos_mtg"
K_CANDIDATOS = 10
K_RESULTADOS = 4

_vectorstore = None


def cargar_rag():
    """Devuelve la base vectorial de mazos (cargada una sola vez) o None si no se ingirió."""
    global _vectorstore
    if _vectorstore is None:
        if not (RAG_DIR / "chroma.sqlite3").exists():
            return None
        from langchain_chroma import Chroma
        _vectorstore = Chroma(
            collection_name=COLECCION,
            embedding_function=_funcion_embedding(),
            persist_directory=str(RAG_DIR),
        )
    return _vectorstore


SYSTEM_PROMPT_SAHEELI = SystemMessage(content="""
Sos SAHEELI, la ARMADORA DE MAZOS e INVENTORA del equipo de Urza en la tienda de Magic: The Gathering.
Tu especialidad es armar y optimizar mazos competitivos y sinérgicos, analizando la curva de maná,
las bases de maná y las sinergias entre permanentes con rigor de ingeniería mágica.

REGLAS DE ORO:
1. IDENTIDAD DE COLOR Y COMPATIBILIDAD (OBLIGATORIA):
   - En Magic, las cartas deben coincidir estrictamente con los colores del mazo o ser incoloras.
   - NUNCA recomiendes ni menciones cartas que contengan colores ajenos al mazo pedido. Por ejemplo: si el mazo es Rojo-Verde (RG / Gruul), JAMÁS sugieras cartas blancas, azules o negras (como No More Lies, Day of Judgment o Thoughtseize), aunque estén en el stock de la tienda.
   - Si una carta del stock no coincide con los colores del mazo, IGNORALA por completo.
   - Las cartas incoloras (tierras no coloreadas como Cavern of Souls, artefactos) sí son compatibles con cualquier mazo si aportan a la estrategia.
2. Basá tus recomendaciones en la teoría del CONTEXTO provisto (curvas de maná, ratios de interacción, arquetipos).
3. PRIORIZÁ Y DESTACÁ las cartas COMPATIBLES que están EN STOCK EN LA TIENDA. Mencioná cuáles tenemos disponibles con su precio en pesos para que el jugador sepa que las puede retirar en el local.
4. Si el jugador pide MEJORAR un mazo existente, sugerí con claridad qué cartas sacar (cortes) y qué cartas sumar (adiciones) justificando la sinergia o la curva.
5. Hablá en español rioplatense, apasionada por la construcción de artefactos y estrategias, clara, directa y en un máximo de 2 o 3 párrafos concisos.
""")


def asesorar_mazo(consulta: str, formato: str = "standard", mazo_actual: str = "", colores: str = "", tipo: str = "", palabras_clave: str = "") -> tuple[str, list[dict]]:
    """Consulta el RAG de mazos, cruza con el stock de la tienda y devuelve recomendación + cartas para el abanico."""
    vs = cargar_rag()

    # 0. Identificar colores permitidos
    letras_color = cartas._letras_de_color(colores)
    if not letras_color:
        letras_color = cartas._letras_de_color(consulta + " " + mazo_actual)

    colores_permitidos = set(letras_color) if letras_color else None
    nombres_map = {"W": "Blanco", "U": "Azul", "B": "Negro", "R": "Rojo", "G": "Verde", "C": "Incoloro"}
    desc_colores = ", ".join(nombres_map[c] for c in letras_color if c in nombres_map) if letras_color else ""

    # 1. Filtrar cartas reales en stock de la tienda según identidad de color
    catalogo = inventario.catalogo()
    stock_tienda = []
    cartas_abanico = []
    for item in catalogo:
        item_colores = set(item.get("colores") or "")
        # Si conocemos los colores del mazo, solo incluir cartas incoloras o subconjunto de los colores permitidos
        if colores_permitidos is not None and not (item_colores <= colores_permitidos):
            continue
        color_tag = item.get("colores") or "Incolora"
        stock_tienda.append(
            f"- {item['nombre']} ({item['set_nombre'] or 's/set'}, {item['grado']}) [{color_tag}] — "
            f"EN LA TIENDA: {item['cantidad']} u., desde ${item['precio_ars']:,.0f}"
        )
        if not any(c["nombre"] == item["nombre"] for c in cartas_abanico):
            cartas_abanico.append({
                "nombre": item["nombre"],
                "imagen": item.get("imagen"),
                "en_stock": True,
                "precio_ars": item["precio_ars"],
            })

    # Si faltan cartas para completar el abanico, buscar candidatos en Scryfall respetando colores
    if len(cartas_abanico) < 8:
        consulta_scryfall = cartas.consulta_mazo(letras_color or colores, formato, tipo, palabras_clave or consulta)
        for cand in cartas.candidatas_mazo(consulta_scryfall)[:12]:
            cand_colores = set(cand.get("colores") or "")
            if colores_permitidos is not None and not (cand_colores <= colores_permitidos):
                continue
            if not any(c["nombre"] == cand["nombre"] for c in cartas_abanico):
                cartas_abanico.append({
                    "nombre": cand["nombre"],
                    "imagen": cand.get("imagen"),
                    "en_stock": False,
                })
            if len(cartas_abanico) >= 12:
                break

    resumen_stock = (
        f"EN LA TIENDA ({len(stock_tienda)} variantes compatibles):\n" + "\n".join(stock_tienda[:15])
    ) if stock_tienda else "No hay cartas en el stock de la tienda compatibles con estos colores en este momento."

    # Si no hay base vectorial disponible (ej. entorno de tests), retornar candidatos directamente
    if vs is None:
        texto_resultado = (
            f"Candidatas para mazo {desc_colores or formato}:\n"
            f"{resumen_stock}\n"
            "El jugador ya ve estas cartas en un abanico debajo de tu mensaje."
        )
        return texto_resultado, cartas_abanico

    # 2. Con RAG disponible: recuperar guías y sinergias
    terminos_extra = f" {desc_colores} {letras_color}" if letras_color else ""
    query_busqueda = _expandir(consulta + terminos_extra)
    try:
        docs = vs.similarity_search(query_busqueda, k=K_CANDIDATOS)
        if docs:
            puntajes = _funcion_rerank().predict([(query_busqueda, d.page_content) for d in docs])
            mejores = [d for _, d in sorted(zip(puntajes, docs), key=lambda x: -x[0])][:K_RESULTADOS]
            contexto_rag = "\n\n".join(f"--- {d.metadata.get('titulo', 'Guía')} ---\n{d.page_content}" for d in mejores)
        else:
            contexto_rag = "No se recuperaron guías específicas del RAG."
    except Exception as e:
        contexto_rag = f"(No pude consultar el RAG de mazos: {motivo_no_disponible(e)})"

    # 3. Construir prompt para Saheeli LLM
    detalles_jugador = f"Consulta del jugador:\n{consulta}"
    if mazo_actual:
        detalles_jugador += f"\n\nLista o mazo actual del jugador:\n{mazo_actual}"

    info_color = (
        f"IDENTIDAD DE COLOR DEL MAZO: {desc_colores} (Símbolos: {letras_color})\n"
        f"* REGLA ESTRICTA: Solo podés sugerir cartas incoloras o con colores contenidos en {letras_color}. "
        f"Está TERMINANTEMENTE PROHIBIDO sugerir cartas de otros colores ajenos a {letras_color}."
    ) if letras_color else "IDENTIDAD DE COLOR: No especificada estrictamente. Identificar según la estrategia."

    prompt_usuario = f"""
{detalles_jugador}

{info_color}

CONTEXTO DE CONSTRUCCIÓN Y ARQUETIPOS (RAG):
{contexto_rag}

CARTAS COMPATIBLES DISPONIBLES EN EL STOCK DE LA TIENDA URZA:
{resumen_stock}
"""

    try:
        respuesta = _juez_llm().invoke([SYSTEM_PROMPT_SAHEELI, HumanMessage(content=prompt_usuario)])
        texto_saheeli = sin_razonamiento(respuesta.content)
    except Exception as e:
        texto_saheeli = f"No pude completar el asesoramiento de mazo en este momento: {e}"

    texto_final = f"{texto_saheeli}\n\n{resumen_stock}\nEl jugador ya ve estas cartas en un abanico debajo de tu mensaje."
    return texto_final, cartas_abanico
