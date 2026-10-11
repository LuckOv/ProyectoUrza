"""Subagente erudito de lore de Magic: The Gathering, con RAG.

Cuando URZA (agent_ventas) detecta una consulta sobre la historia o la narrativa
del multiverso (planos, personajes, eventos, tramas), llama a la herramienta
`consultar_lore_mtg`. Esa herramienta:

  1. recupera los fragmentos más relevantes de la MTG Wiki desde la base
     vectorial Chroma (backend/lore_db/),
  2. le pasa ese contexto a un LLM independiente con rol de erudito,
  3. devuelve la respuesta citando los artículos usados como fuente.

Es el mismo patrón del subagente juez de reglas (FE-05, reglas.py): reutiliza
sus singletons (traductor ES->EN, embeddings, reranker y ChatGroq) y solo
cambia la base vectorial y el rol. La base se carga una sola vez por proceso;
si todavía no se ingirió, la herramienta avisa en vez de romper. La ingesta se
hace con ingestar_lore.py.
"""

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from reglas import _funcion_embedding, _funcion_rerank, _juez_llm, _traducir, motivo_no_disponible

# Chroma se importa recién al cargar la base (cargar_rag): arrastra torch, que
# algunos Windows bloquean. Así un bloqueo sólo apaga el lore, no el agente.

BASE = Path(__file__).parent
RAG_DIR = BASE / "lore_db"
COLECCION = "lore_mtg"
K_CANDIDATOS = 15
K_RESULTADOS = 6

_vectorstore = None


def cargar_rag():
    """Devuelve la base vectorial de lore (cargada una sola vez) o None."""
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


SYSTEM_PROMPT_HISTORIADOR = SystemMessage(content="""
Sos TEFERI, el ERUDITO del lore del equipo de Urza en la tienda de Magic: The
Gathering. Contás la historia y la narrativa del multiverso: planos, personajes,
eventos y tramas.

REGLAS DE ORO:
1. Respondé ÚNICAMENTE con la información que te dan como CONTEXTO, extraída de
   la MTG Wiki. No uses conocimiento previo de la historia del juego.
2. Cita siempre el artículo de dónde sacás cada dato (por ejemplo "según la
   página de Urza...").
3. Si el contexto no alcanza para responder, decilo sin vueltas en vez de
   inventar. No afirmes nada que no esté en el contexto.
4. Distinguí hecho de interpretación: si algo no está dicho explícitamente,
   no lo des por confirmado.
5. Respondé en español rioplatense, claro y directo, en un máximo de cuatro o
   cinco oraciones.
""")


def _citar_fuentes(docs):
    return ", ".join(sorted({d.metadata.get("titulo") for d in docs if d.metadata.get("titulo")}))


@tool
def consultar_lore_mtg(pregunta: str) -> str:
    """Responde preguntas sobre la historia y el lore de Magic: The Gathering.

    Usala cuando el jugador pregunte por el trasfondo narrativo: planos
    (Dominaria, Ravnica, Innistrad...), personajes (planeswalkers, villanos),
    eventos (la Guerra Phyrexiana, The Mending) o tramas del multiverso.
    NO usarla para reglas del juego, precios, stock ni datos de cartas.
    Devuelve la respuesta con las fuentes citadas (artículos de la MTG Wiki).
    """
    try:
        vs = cargar_rag()
    except Exception as e:
        return f"El erudito de lore no está disponible ahora. {motivo_no_disponible(e)}"
    if vs is None:
        return (
            "Todavía no tengo cargada la base de lore en el servidor. "
            "Avisá que corran 'uv run python ingestar_lore.py' dentro de backend/."
        )

    # La wiki está en inglés; traducir la pregunta mejora la recuperación. Si no
    # hay API key o Groq falla, los embeddings multilingües cubren lo esencial.
    consulta = _traducir(pregunta) or pregunta
    try:
        docs = vs.similarity_search(consulta, k=K_CANDIDATOS)
        if not docs:
            return "No recuperé ninguna página de lore para esa consulta. Probemos reformularla."

        # Rerank: el cross-encoder multilingüe ordena los candidatos por relevancia
        # real para el jugador, en vez del ruido del bi-encoder de recuperación.
        puntajes = _funcion_rerank().predict([(consulta, d.page_content) for d in docs])
    except Exception as e:
        return f"El erudito de lore no está disponible ahora. {motivo_no_disponible(e)}"
    mejores = [d for _, d in sorted(zip(puntajes, docs), key=lambda x: -x[0])][:K_RESULTADOS]

    contexto = "\n\n".join(
        f"[Artículo {d.metadata.get('titulo', '?')} · {d.metadata.get('categoria', '?')}]\n{d.page_content}"
        for d in mejores
    )

    mensaje = (
        "CONSULTA DEL JUGADOR (en español):\n"
        f"{pregunta}\n\n"
        "CONTEXTO (fragmentos de la MTG Wiki):\n"
        f"{contexto}"
    )
    try:
        respuesta = _juez_llm().invoke([SYSTEM_PROMPT_HISTORIADOR, HumanMessage(content=mensaje)])
    except Exception as e:
        return (
            f"No pude consultar al erudito del lore: {e}\n\n"
            "Contexto recuperado mientras tanto:\n\n"
            f"{contexto}"
        )

    return f"{respuesta.content.strip()}\n\nFuentes consultadas: {_citar_fuentes(mejores)}"