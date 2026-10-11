"""Subagente juez de reglas de Magic: The Gathering, con RAG.

Cuando URZA (agent_ventas) detecta una consulta sobre reglas, una jugada o una
interacción entre cartas, llama a la herramienta `consultar_reglas_mtg`. Esa
herramienta:

  1. recupera los fragmentos más relevantes de las Reglas Completas desde la
     base vectorial Chroma (backend/reglas_db/),
  2. le pasa ese contexto a un LLM independiente con rol de juez,
  3. devuelve la respuesta del juez citando los números de regla.

La base vectorial se carga una sola vez por proceso; si todavía no se ingirió,
la herramienta avisa en vez de romper. La ingesta se hace con ingestar_reglas.py.
"""

import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq

# Chroma, los embeddings y el reranker se importan recién cuando se usan (ver
# _funcion_embedding, _funcion_rerank y cargar_rag). Arrastran torch, que es
# pesado y en algunos Windows lo bloquea "Control inteligente de aplicaciones"
# (WinError 4551). Importados acá arriba, ese bloqueo tiraba abajo el agente
# entero; así sólo se pierde el juez (y el lore) y el resto del chat sigue.

load_dotenv()

BASE = Path(__file__).resolve().parent.parent
RAG_DIR = BASE / "reglas_db"
COLECCION = "reglas_completas"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"
MODELO_RERANK = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MODELO_JUEZ = "qwen/qwen3.8-27b"
K_CANDIDATOS = 15
K_RESULTADOS = 6

# Expansión léxica español -> inglés. Las reglas están en inglés y el jugador
# pregunta en español: añadir las keywords equivalentes cierra la brecha de
# vocabulario ("contrarrestar" -> counter) y mejora la recuperación. Las frases
# se comparan sin acentos y con bordes de palabra.
TERMINOS = [
    ("instantaneo", "instant"),
    ("instantaneos", "instant"),
    ("conjuro", "sorcery"),
    ("hechizo", "spell"),
    ("hechizos", "spell"),
    ("contrarresta", "counter"),
    ("anula", "counter"),
    ("habilidad", "ability"),
    ("habilidades", "ability"),
    ("disparo", "triggered ability"),
    ("prioridad", "priority"),
    ("fase de combate", "combat phase"),
    ("combate", "combat"),
    ("dano", "damage"),
    ("mortal", "lethal"),
    ("ataca", "attack"),
    ("bloquea", "block"),
    ("vuela", "flying"),
    ("voladora", "flying"),
    ("trample", "trample"),
    ("primer golpe", "first strike"),
    ("turno", "turn"),
    ("pila", "stack"),
    ("stack", "stack"),
    ("resuelve", "resolve"),
    ("leyenda", "legendary"),
    ("legendario", "legendary"),
    ("legendarios", "legendary"),
    ("criatura", "creature"),
    ("permanente", "permanent"),
    ("objetivo", "target"),
    ("roba", "draw a card"),
    ("robar", "draw a card"),
    ("robo", "draw a card"),
    ("cementerio", "graveyard"),
    ("biblioteca", "library"),
    ("mano", "hand"),
    ("campo de batalla", "battlefield"),
    ("exilio", "exile"),
    ("exilia", "exile"),
    ("token", "token"),
    ("contador", "counter"),
]


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).lower()


def _expandir(pregunta: str) -> str:
    """Agrega keywords en inglés a la pregunta para cerrar la brecha ES->EN."""
    limpia = _sin_acentos(pregunta)
    extra = set()
    for es, en in TERMINOS:
        if en and re.search(rf"\b{re.escape(es)}", limpia):
            extra.add(en)
    if not extra:
        return pregunta
    return f"{pregunta} ({', '.join(sorted(extra))})"

_embeddings = None
_vectorstore = None
_juez = None
_rerank = None


def _funcion_embedding():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    return _embeddings


def _funcion_rerank():
    global _rerank
    if _rerank is None:
        from sentence_transformers import CrossEncoder
        _rerank = CrossEncoder(MODELO_RERANK)
    return _rerank


def cargar_rag():
    """Devuelve la base vectorial (cargada una sola vez) o None si no se ingirió."""
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


SYSTEM_PROMPT_JUEZ = SystemMessage(content="""
Sos AJANI, el JUEZ de reglas del equipo de Urza en la tienda de Magic: The Gathering.
Resolvés dudas de jugadas con total precisión.

REGLAS DE ORO:
1. Respondé ÚNICAMENTE con la información de las Reglas Completas que te dan como CONTEXTO. No uses conocimiento previo.
2. Cita siempre los números de regla cuando sustentes la respuesta (por ejemplo "según la regla 510.2...").
3. Si el contexto no alcanza para resolver la duda, decilo sin vueltas en vez de inventar.
4. No afirmes nada que no esté en el contexto. Ante una contradicción, preferí la regla más específica citada.
5. Respondé en español rioplatense, claro y directo, en un máximo de cuatro o cinco oraciones.
""")

SYSTEM_PROMPT_TRADUCTOR = SystemMessage(content="""
Respondé solo con la traducción al inglés de la consulta del jugador, redactada
como la preguntaría un jugador de MTG buscando en las Comprehensive Rules.
Devolvé únicamente la frase traducida, sin comillas ni comentarios.
""")


def _traducir(pregunta: str):
    """Pasa la pregunta a inglés para alinear la búsqueda con las reglas.

    Best-effort: devuelve None si no hay API key configurada o si Groq falla.
    """
    try:
        respuesta = _juez_llm().invoke(
            [SYSTEM_PROMPT_TRADUCTOR, HumanMessage(content=f"Consulta del jugador:\n{pregunta}")]
        )
        traduccion = respuesta.content.strip()
        return traduccion if traduccion else None
    except Exception:
        return None


def motivo_no_disponible(e: Exception) -> str:
    """Explica por qué no se pudieron cargar los modelos del RAG (reglas o lore)."""
    texto = str(e)
    if "4551" in texto or "Control de aplicaciones" in texto or "Application Control" in texto:
        return ("Windows bloqueó la librería torch en esta computadora (Control inteligente de "
                "aplicaciones), así que no puedo usar los modelos de búsqueda.")
    return f"No pude cargar los modelos de búsqueda ({type(e).__name__}: {texto[:200]})."


def _citar_reglas(docs):
    return ", ".join(sorted({d.metadata.get("regla") for d in docs if d.metadata.get("regla")}))


def _juez_llm():
    global _juez
    if _juez is None:
        _juez = ChatGroq(model=MODELO_JUEZ, temperature=0, max_tokens=500)
    return _juez


@tool
def consultar_reglas_mtg(pregunta: str) -> str:
    """Resuelve una jugada, regla o interacción entre cartas de Magic usando las Reglas Completas oficiales.

    Usala cuando el jugador pregunte por reglas del juego, timing y prioridad,
    cómo se resuelve una jugada concreta, o cómo interactúan dos o más cartas o
    habilidades. Devuelve la respuesta de un juez con los números de regla citados.
    """
    try:
        vs = cargar_rag()
    except Exception as e:
        return f"El juez de reglas no está disponible ahora. {motivo_no_disponible(e)}"
    if vs is None:
        return (
            "Todavía no tengo cargada la base de reglas en el servidor. "
            "Avisá que corran 'uv run python ingestar_reglas.py' dentro de backend/."
        )

    # La mejor forma de preguntarle a las reglas es en inglés; si no hay API key,
    # la expansión léxica ES->EN cubre lo esencial y como último recurso queda
    # la pregunta original en español.
    consulta = _traducir(pregunta) or _expandir(pregunta)
    try:
        docs = vs.similarity_search(consulta, k=K_CANDIDATOS)
        if not docs:
            return "No recuperé ninguna regla para esa consulta. Probemos reformularla."

        # Rerank: el bi-encoder suele traer ruido (#603/#120 en temas de timing);
        # el cross-encoder multilingüe ordena los candidatos por relevancia real.
        puntajes = _funcion_rerank().predict([(consulta, d.page_content) for d in docs])
    except Exception as e:
        return f"El juez de reglas no está disponible ahora. {motivo_no_disponible(e)}"
    mejores = [d for _, d in sorted(zip(puntajes, docs), key=lambda x: -x[0])][:K_RESULTADOS]

    contexto = "\n\n".join(
        f"[Regla {d.metadata.get('regla', '?')} · {d.metadata.get('seccion', '?')}]\n{d.page_content}"
        for d in mejores
    )

    mensaje = (
        "CONSULTA DEL JUGADOR (en español):\n"
        f"{pregunta}\n\n"
        "CONTEXTO (fragmentos de las Reglas Completas de MTG):\n"
        f"{contexto}"
    )
    try:
        respuesta = _juez_llm().invoke([SYSTEM_PROMPT_JUEZ, HumanMessage(content=mensaje)])
    except Exception as e:
        return (
            f"No pude consultar al juez de reglas: {e}\n\n"
            "Contexto recuperado mientras tanto:\n\n"
            f"{contexto}"
        )

    return f"{respuesta.content.strip()}\n\nBases consultadas: {_citar_reglas(mejores)}"