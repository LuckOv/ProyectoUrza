"""Ingesta del lore de MTG (MTG Wiki, mtg.fandom.com) en la base vectorial Chroma.

ETL en dos fases: bajar a disco (red) e indexar (offline). Pensado para
conexiones intermitentes y para producción: la descarga es resumible y
nunca pierde lo ya bajado.

Uso (parado dentro de backend/):
    uv run python -m ingesta.ingestar_lore            # baja (si falta) e indexa
    uv run python -m ingesta.ingestar_lore --solo-bajar   # solo red → snapshot en backend/lore/
    uv run python -m ingesta.ingestar_lore --index        # solo índice offline → backend/lore_db/

Si la red corta a mitad de una corrida, volvé a correr el mismo comando: el
crawler retoma donde quedó (salta categorías completadas y páginas ya bajadas).
Cada ronda queda registrada en backend/lore/ronda.json con su etiqueta
(baja_<fecha>_<ronda>), que se estampa en cada chunk indexado para poder
auditar qué sabía el bot.

Opciones:
    --rebuild     borra el snapshot y lore_db/ antes de empezar
    --categorias  raíces a recorrer recursivamente (default: las de v1)
    --titulos     títulos puntuales (reemplazan la lista curada por defecto)
    --completo    texto completo en vez del intro (~15x más lento)

El RAG de runtime (lore.py) carga lore_db/ una sola vez por proceso; si el
índice no existe avisa en vez de romper. Datos regenerables → gitignore.
"""

# Permite correrlo también como archivo suelto (python ingesta/x.py), además de
# con python -m: agrega backend/ al path para que encuentre los paquetes.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import requests
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE = Path(__file__).resolve().parent.parent
RAG_DIR = BASE / "lore_db"
SNAP_DIR = BASE / "lore"
PAGINAS_JSONL = SNAP_DIR / "paginas.jsonl"
ESTADO_JSON = SNAP_DIR / "estado.json"
RONDA_JSON = SNAP_DIR / "ronda.json"
COLECCION = "lore_mtg"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"
VERSION = "1.0"

API_BASE = "https://mtg.fandom.com/api.php"
USER_AGENT = "UrzaBot/1.0 (ProyectoEstudiantilISFT197)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

TANDA = 20       # tope de 'exlimit' de la extensión extracts
CM_LIMIT = 500   # miembros por request en list=categorymembers (anda en Fandom)
PAUSA = 0.5      # segundos entre requests para no ser cortado
REINTENTOS = 6   # reintentos con backoff ante throttling/resets de Fandom

# Una sola conexión reutilizada (keep-alive) en vez de abrir socket por pedido:
# Fandom cierra conexiones nuevas a mansalva y eso dispara ConnectionReset.
SESION = requests.Session()

# V1: solo páginas de referencia (resúmenes), no la ficción completa.
CATEGORIAS = [
    "Planeswalker characters",
    "Characters by plane",
    "Planes",
    "Events",
    "Storylines",
]

# Red de seguridad de cobertura: personajes/planos/eventos emblemáticos que se
# bajan por título aunque el walk de alguna categoría falle. Los títulos que no
# existan en la wiki se descartan solos.
TITULOS_CURADOS = [
    "Urza", "Karn", "Yawgmoth", "Mishra", "Teferi",
    "Jace Beleren", "Liliana Vess", "Chandra Nalaar", "Gideon Jura", "Nissa Revane",
    "Nicol Bolas", "Ajani Goldmane", "Elspeth Tirel", "Sorin Markov", "Ugin",
    "Garruk Wildspeaker", "Tamiyo", "Kaya", "Elesh Norn", "Jin-Gitaxias",
    "Sheoldred", "Urabrask", "Vorinclex", "Emrakul", "Kozilek", "Ulamog",
    "Serra", "Avacyn", "Gerrard Capashen", "Venser", "Koth",
    "The Mending", "War of the Spark", "Weatherlight", "Mirari", "Power Nine",
    "Thran", "Tolaria", "Urza's Saga",
    "Dominaria", "Ravnica", "Phyrexia (plane)", "Innistrad (plane)",
    "Zendikar (plane)", "Theros (plane)", "Kamigawa (plane)", "Ixalan (plane)",
    "Amonkhet (plane)", "Kaldheim (plane)", "Eldraine (plane)",
]

CAP_SUBCATEGORIAS = 5000  # freno de seguridad contra árboles infinitos

CHUNK_SIZE = 1500
PARTIDOR = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=200,
    separators=["\n\n", "\n", " "],
)


# --- API de Fandom ----------------------------------------------------------

def pedir(params: dict) -> dict:
    """Un request a la API de MediaWiki, con reintentos y control de errores.

    Fandom es agresivo con el throttling (corta conexiones, devuelve 429/5xx):
    ante cualquier fallo volátil se espera con backoff creciente y se reutiliza
    la sesión (keep-alive).
    """
    base = dict(params, format="json", formatversion="2")
    ultimo_error = None
    for intento in range(1, REINTENTOS + 1):
        try:
            r = SESION.get(API_BASE, params=base, headers=HEADERS, timeout=90)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code} de la wiki")
            r.raise_for_status()
            datos = r.json()
            if "error" in datos:
                raise RuntimeError(f"Error de la API de la wiki: {datos['error']}")
            return datos
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                RuntimeError) as e:
            ultimo_error = e
            if intento == REINTENTOS:
                break
            espera = 3 * intento
            print(f"[ingesta]   reintento {intento}/{REINTENTOS} en {espera}s "
                  f"({type(e).__name__}: {e})")
            time.sleep(espera)
            SESION.close()
    raise ultimo_error


def _listar(categoria: str, namespace: int, tipo: str) -> list[str]:
    """Títulos de una categoría (subcats o páginas), paginando con 'cmcontinue'."""
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": categoria,
        "cmnamespace": namespace,
        "cmtype": tipo,
        "cmlimit": CM_LIMIT,
    }
    resultado = []
    vistos = set()
    while True:
        datos = pedir(params)
        for m in datos.get("query", {}).get("categorymembers") or []:
            titulo = m.get("title")
            if titulo and titulo not in vistos:
                vistos.add(titulo)
                resultado.append(titulo)
        continue_ = datos.get("continue") or {}
        if "cmcontinue" not in continue_:
            break
        params["cmcontinue"] = continue_["cmcontinue"]
        time.sleep(PAUSA)
    return resultado


def subcategorias_de(categoria: str) -> list[str]:
    return _listar(categoria, 14, "subcat")


def paginas_de_categoria(categoria: str, solo_intro: bool = True) -> dict[str, dict]:
    """Artículos (ns 0) de una categoría, con su texto según el modo.

    Con solo_intro=True baja únicamente el intro (resumen): Fandom lo entrega
    de a ~20 por request. Con solo_intro=False baja el texto completo (un
    extracto por request): hay que seguir además 'excontinue' hasta agotar los
    extractos pendientes antes de avanzar con 'gcmcontinue'. Pasarlos juntos
    devuelve 'badcontinue'.
    """
    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": categoria,
        "gcmnamespace": 0,
        "gcmlimit": TANDA,
        "prop": "extracts|info",
        "explaintext": 1,
        "exintro": int(solo_intro),
        "exlimit": TANDA,
        "inprop": "url",
    }
    por_titulo = {}
    while True:
        datos = pedir(params)
        for pagina in datos.get("query", {}).get("pages") or []:
            titulo = pagina.get("title")
            if not titulo:
                continue
            # La misma página vuelve en más de una tanda: unimos los campos.
            if titulo in por_titulo:
                por_titulo[titulo].update(pagina)
            else:
                por_titulo[titulo] = pagina

        continue_ = datos.get("continue") or {}
        if "excontinue" in continue_:
            params["excontinue"] = continue_["excontinue"]
            params.pop("gcmcontinue", None)
        elif "gcmcontinue" in continue_:
            params["gcmcontinue"] = continue_["gcmcontinue"]
            params.pop("excontinue", None)
        else:
            break
        time.sleep(PAUSA)

    return por_titulo


def paginas_por_titulo(titulos: list[str]) -> list[dict]:
    """Extractos de títulos puntuales, de a uno por request.

    La extensión extracts de Fandom con 'titles=' devuelve un solo extracto
    por request, así que la llamada se hace por título.
    """
    paginas = []
    for titulo in titulos:
        params = {
            "action": "query",
            "titles": titulo,
            "prop": "extracts|info",
            "explaintext": 1,
            "inprop": "url",
        }
        paginas += pedir(params).get("query", {}).get("pages") or []
        time.sleep(PAUSA)
    return paginas


# --- snapshot en disco ------------------------------------------------------

def cargar_titulos_bajados() -> set[str]:
    """Los títulos ya presentes en paginas.jsonl (para no repetirlos)."""
    if not PAGINAS_JSONL.exists():
        return set()
    bajados = set()
    with PAGINAS_JSONL.open(encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            try:
                bajados.add(json.loads(linea).get("title", ""))
            except json.JSONDecodeError:
                continue
    return {t for t in bajados if t}


def escribir_pagina(pagina: dict) -> None:
    with PAGINAS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(pagina, ensure_ascii=False) + "\n")


def cargar_estado() -> dict:
    if ESTADO_JSON.exists():
        try:
            return json.loads(ESTADO_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"por_raiz": {}}


def guardar_estado(estado: dict) -> None:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    ESTADO_JSON.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def siguiente_ronda(rebuild: bool) -> int:
    if rebuild or not RONDA_JSON.exists():
        return 1
    try:
        return int(json.loads(RONDA_JSON.read_text(encoding="utf-8")).get("ronda", 0)) + 1
    except (json.JSONDecodeError, TypeError, ValueError):
        return 1


def guardar_manifiesto(ronda: int, etiqueta: str, modo: str, raices, estado: dict,
                       total_paginas: int, extra: dict | None = None) -> None:
    manifiesto = {
        "version_script": VERSION,
        "ronda": ronda,
        "etiqueta": etiqueta,
        "modo": modo,
        "fecha": date.today().isoformat(),
        "raices": raices,
        "titulos_curados": len(TITULOS_CURADOS),
        "total_paginas": total_paginas,
        "estado": estado,
    }
    if extra:
        manifiesto.update(extra)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    RONDA_JSON.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")


# --- descarga resumible -----------------------------------------------------

def bajar_raiz(raiz: str, estado: dict, bajados: set[str],
               solo_intro: bool, etiqueta: str) -> None:
    """BFS sobre subcategorías con guarda de ciclos, resumible y sin repetir.

    El avance (visitadas + cola pendiente) se persiste después de cada
    categoría. Si la red corta, la corrida aborta y una próxima retoma.
    """
    por_raiz = estado["por_raiz"].setdefault(raiz, {
        "hecha": False, "visitadas": [], "cola": [f"Category:{raiz}"],
    })
    if por_raiz["hecha"]:
        print(f"[ingesta]   {raiz}: ya estaba completa; se omite.")
        return

    visitadas = set(por_raiz["visitadas"])
    cola = por_raiz["cola"]
    nuevas = 0

    while cola:
        categoria = cola.pop(0)
        if categoria in visitadas:
            continue
        visitadas.add(categoria)

        subcats = subcategorias_de(categoria)
        for sub in subcats:
            if sub not in visitadas:
                cola.append(sub)
        paginas = paginas_de_categoria(categoria, solo_intro)

        for titulo, pagina in paginas.items():
            if titulo in bajados:
                continue
            pagina["categoria"] = raiz
            pagina["baja"] = etiqueta
            escribir_pagina(pagina)
            bajados.add(titulo)
            nuevas += 1

        if len(visitadas) >= CAP_SUBCATEGORIAS:
            print(f"[ingesta]   (cap de {CAP_SUBCATEGORIAS} subcategorías; corto la expansión)")
            cola.clear()

        por_raiz.update({"visitadas": sorted(visitadas), "cola": cola})
        guardar_estado(estado)
        print(f"[ingesta]   {raiz} · {categoria}: +{nuevas} páginas nuevas "
              f"({len(cola)} categorías en cola)")
        nuevas = 0
        time.sleep(PAUSA)

    por_raiz.update({"hecha": True, "visitadas": sorted(visitadas), "cola": []})
    guardar_estado(estado)
    print(f"[ingesta]   {raiz}: completa.")


def bajar_titulos(titulos: list[str], bajados: set[str], etiqueta: str) -> None:
    faltantes = [t for t in titulos if t not in bajados]
    if not faltantes:
        print("[ingesta]   lista curada: todos los títulos ya estaban bajados.")
        return
    for pagina in paginas_por_titulo(faltantes):
        titulo = pagina.get("title")
        if not titulo or titulo in bajados or pagina.get("missing"):
            continue
        pagina["categoria"] = "Manual"
        pagina["baja"] = etiqueta
        escribir_pagina(pagina)
        bajados.add(titulo)
    print(f"[ingesta]   lista curada: {len(faltantes)} pedidos, "
          f"{sum(1 for t in titulos if t in bajados)} presentes en el snapshot.")


# --- indexación (offline) ---------------------------------------------------

def a_documentos(paginas: list[dict]) -> list[Document]:
    """Arma un Document por chunk, con metadata de origen y de ronda."""
    docs = []
    vistos = set()

    for pagina in paginas:
        titulo = pagina.get("title")
        texto = (pagina.get("extract") or "").strip()
        if pagina.get("missing") or pagina.get("redirect"):
            continue
        if not titulo or not texto or titulo in vistos:
            continue
        vistos.add(titulo)

        trozos = PARTIDOR.split_text(texto) if len(texto) > CHUNK_SIZE else [texto]
        for i, pedazo in enumerate(trozos):
            docs.append(Document(
                page_content=f"Artículo: {titulo}\n{pedazo}",
                metadata={
                    "titulo": titulo,
                    "categoria": pagina.get("categoria", ""),
                    "baja": pagina.get("baja", ""),
                    "pageid": pagina.get("pageid", 0),
                    "url": pagina.get("fullurl", ""),
                    "parte": i,
                },
            ))
    return docs


def indexar() -> tuple[int, int]:
    """Reconstruye lore_db/ desde el snapshot (sin red)."""
    if not PAGINAS_JSONL.exists():
        sys.exit("No hay snapshot (backend/lore/paginas.jsonl). Corré --solo-bajar primero.")

    paginas = []
    with PAGINAS_JSONL.open(encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                try:
                    paginas.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue

    docs = a_documentos(paginas)
    if not docs:
        sys.exit("El snapshot no tiene páginas con texto para indexar.")

    if RAG_DIR.exists():
        shutil.rmtree(RAG_DIR)
        print(f"[ingesta] {RAG_DIR} eliminada antes de re-indexar.")

    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    print(f"[ingesta] Indexando {len(docs)} chunks de un snapshot de "
          f"{len(paginas)} páginas en Chroma ({RAG_DIR}) ...")
    _ = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLECCION,
        persist_directory=str(RAG_DIR),
    )
    print(f"[ingesta] Listo. {len(docs)} documentos en la colección '{COLECCION}'.")
    return len(paginas), len(docs)


# --- CLI --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Ingesta del lore de MTG (resumible).")
    ap.add_argument("--rebuild", action="store_true",
                    help="Borra snapshot y lore_db/ antes de empezar.")
    ap.add_argument("--solo-bajar", action="store_true",
                    help="Solo red: actualiza backend/lore/paginas.jsonl (resumible).")
    ap.add_argument("--index", action="store_true",
                    help="Solo índice offline: reconstruye lore_db/ desde el snapshot.")
    ap.add_argument("--categorias", default=",".join(CATEGORIAS),
                    help="Categorías raíz a recorrer recursivamente.")
    ap.add_argument("--titulos", default="",
                    help="Títulos puntuales separados por coma (reemplazan la lista curada).")
    ap.add_argument("--completo", action="store_true",
                    help="Baja el texto completo en vez del intro (~15x más lento).")
    args = ap.parse_args()

    solo_bajar = args.solo_bajar
    solo_index = args.index
    hacer_bajar = solo_bajar or not solo_index
    hacer_index = solo_index or not solo_bajar

    if args.rebuild:
        for d in (SNAP_DIR, RAG_DIR):
            if d.exists():
                shutil.rmtree(d)
                print(f"[ingesta] {d} eliminada (--rebuild).")

    raices = [c.strip() for c in args.categorias.split(",") if c.strip()]
    titulos = ([t.strip() for t in args.titulos.split(",") if t.strip()]
               if args.titulos else TITULOS_CURADOS)
    modo = "completo" if args.completo else "intro"

    ronda = siguiente_ronda(args.rebuild)
    etiqueta = f"{date.today().isoformat()}_r{ronda}"

    if hacer_bajar:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        bajados = cargar_titulos_bajados()
        estado = cargar_estado()
        print(f"[ingesta] Ronda {ronda} ({etiqueta}, modo {modo}). "
              f"{len(bajados)} páginas ya en el snapshot. Bajando desde {API_BASE} ...")
        try:
            for raiz in raices:
                bajar_raiz(raiz, estado, bajados, not args.completo, etiqueta)
            bajar_titulos(titulos, bajados, etiqueta)
        except Exception as e:
            guardar_estado(estado)
            print(f"[ingesta] Red cortó ({type(e).__name__}: {e}). "
                  "El progreso quedó guardado: volvé a correr este comando para retomar.")
            sys.exit(1)

        guardar_manifiesto(ronda, etiqueta, modo, raices, estado, len(bajados),
                           extra={"descarga_completa": True, "indexado": False})
        print(f"[ingesta] Descarga lista. {len(bajados)} páginas en el snapshot.")

    if hacer_index:
        total_paginas, total_chunks = indexar()
        if RONDA_JSON.exists():
            try:
                m = json.loads(RONDA_JSON.read_text(encoding="utf-8"))
                m.update({"indexado": True, "total_paginas": total_paginas,
                          "total_chunks": total_chunks,
                          "fecha_index": date.today().isoformat()})
                RONDA_JSON.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            except json.JSONDecodeError:
                pass


if __name__ == "__main__":
    main()