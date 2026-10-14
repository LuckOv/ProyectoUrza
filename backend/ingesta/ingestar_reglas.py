"""Ingesta de las Reglas Completas de MTG en la base vectorial Chroma.

Uso (parado dentro de backend/):
    uv run python -m ingesta.ingestar_reglas

Sin argumentos descarga el archivo oficial más reciente conocido desde
media.wizards.com. También se puede pasar una ruta o URL propia:

    uv run python -m ingesta.ingestar_reglas https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.txt

El texto crudo queda en backend/reglas/comp_rules.txt (gitignoreado) y los
embeddings persistidos en backend/reglas_db/.
"""

# Permite correrlo también como archivo suelto (python ingesta/x.py), además de
# con python -m: agrega backend/ al path para que encuentre los paquetes.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE = Path(__file__).resolve().parent.parent
DIR_REGLA = BASE / "reglas"
TXT_PATH = DIR_REGLA / "comp_rules.txt"
RAG_DIR = BASE / "reglas_db"
COLECCION = "reglas_completas"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

URL_OFICIAL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt"
USER_AGENT = "UrzaBot/1.0 (ProyectoEstudiantilISFT197)"

CHUNK_SIZE = 1500

# Los chunks gigantes (regla 702, 613, ...) se parten con este splitter.
PARTIDOR = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=200,
    separators=["\n\n", "\n", " "],
)

# Patrones de estructura del documento de Reglas Completas.
RE_REGLON = re.compile(r"^(\d{3})\.\s+([A-Z])")           # "100. General"
SECCIONES = {
    "1. Game Concepts",
    "2. Parts of a Card",
    "3. Card Types",
    "4. Zones",
    "5. Turn Structure",
    "6. Spells, Abilities, and Effects",
    "7. Additional Rules",
    "8. Multiplayer Rules",
    "9. Casual Variants",
}


def descargar(destino: str | None) -> Path:
    """Trae las reglas (URL o ruta local) y devuelve el archivo donde quedaron."""
    if destino is None:
        destino = URL_OFICIAL

    DIR_REGLA.mkdir(parents=True, exist_ok=True)

    if destino.startswith("http://") or destino.startswith("https://"):
        print(f"[ingesta] Descargando reglas desde {destino} ...")
        req = urllib.request.Request(destino, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            datos = resp.read()
        TXT_PATH.write_bytes(datos)
        print(f"[ingesta] Guardadas en {TXT_PATH} ({len(datos) // 1024} KiB)")
        return TXT_PATH

    origen = Path(destino)
    if not origen.exists():
        sys.exit(f"No existe el archivo de reglas: {origen}")
    TXT_PATH.write_bytes(origen.read_bytes())
    return TXT_PATH


def cuerpo_de(texto: str) -> tuple[list[str], list[str]]:
    """Devuelve (cuerpo de reglas, glosario) sin portada ni tabla de contenidos."""
    lineas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # La sección "1. Game Concepts" aparece dos veces: una en la tabla de
    # contenidos y otra donde empieza el cuerpo. El cuerpo es la última.
    donde = [i for i, ln in enumerate(lineas) if ln.strip() == "1. Game Concepts"]
    if not donde:
        sys.exit("No encontré la sección '1. Game Concepts' en el documento.")
    inicio = donde[-1] + 1

    # Después del cuerpo arranca el glosario real (el de la tabla de
    # contenidos queda antes de `inicio`).
    glo = [i for i in range(inicio, len(lineas)) if lineas[i].strip() == "Glossary"]
    fin_glosario = len(lineas)

    if glo:
        ini_glosario = glo[0] + 1
    else:
        ini_glosario = len(lineas)

    # Los créditos finales no aportan nada al glosario.
    cre = [i for i in range(ini_glosario, len(lineas)) if lineas[i].strip() == "Credits"]
    if cre:
        fin_glosario = cre[0]

    return lineas[inicio : glo[0] if glo else len(lineas)], lineas[ini_glosario:fin_glosario]


def a_documentos(lineas: list[str]) -> list[Document]:
    """Arma un Document por regla de nivel superior, con su metadata."""
    docs = []
    seccion = "1 Game Concepts"
    regla_actual = None
    titulo_actual = None
    acumulado = []

    def cerrar():
        nonlocal acumulado
        if not acumulado or regla_actual is None:
            return
        texto = "\n".join(acumulado).strip()
        if not texto:
            return
        trozos = PARTIDOR.split_text(texto) if len(texto) > CHUNK_SIZE else [texto]
        cabecera = f"Rule {regla_actual} - {titulo_actual}"
        for i, pedazo in enumerate(trozos):
            docs.append(Document(
                page_content=f"{cabecera}\n{pedazo}",
                metadata={
                    "regla": regla_actual,
                    "titulo": titulo_actual,
                    "seccion": seccion,
                    "parte": i,
                },
            ))

    for ln in lineas:
        sin = ln.strip()

        if sin in SECCIONES:
            cerrar()
            seccion = sin
            regla_actual = None
            titulo_actual = None
            acumulado = []
            continue

        m_reg = RE_REGLON.match(sin)
        if m_reg:
            cerrar()
            regla_actual = m_reg.group(1)
            titulo_actual = sin[m_reg.start(2):].strip()
            acumulado = [ln]
        elif regla_actual is not None:
            acumulado.append(ln)

    cerrar()
    return docs


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Ingesta de las Reglas Completas de MTG en Chroma.")
    ap.add_argument("origen", nargs="?", default=None,
                    help="URL o ruta del TXT de reglas (opcional; por defecto la descarga oficial).")
    ap.add_argument("--rebuild", action="store_true",
                    help="Borra reglas_db/ antes de indexar (evita duplicados al re-ingirir).")
    args = ap.parse_args()

    if args.rebuild and RAG_DIR.exists():
        import shutil
        shutil.rmtree(RAG_DIR)
        print(f"[ingesta] {RAG_DIR} eliminada (--rebuild).")

    ruta = descargar(args.origen)

    cuerpo, glosario = cuerpo_de(ruta.read_text(encoding="utf-8", errors="replace"))
    docs = a_documentos(cuerpo)
    if not docs:
        sys.exit("No se pudo extraer ninguna regla del documento.")

    print(f"[ingesta] {len(docs)} documentos de reglas. Muestra:")
    for d in docs[:5]:
        print(f"  - regla={d.metadata['regla']} seccion='{d.metadata['seccion']}' "
              f"({len(d.page_content)} chars): {d.page_content[:70]!r}")

    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    print(f"[ingesta] Indexando {len(docs)} documentos en Chroma ({RAG_DIR}) ...")
    _ = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLECCION,
        persist_directory=str(RAG_DIR),
    )
    print(f"[ingesta] Listo. {len(docs)} documentos indexados en la colección '{COLECCION}'.")


if __name__ == "__main__":
    main()