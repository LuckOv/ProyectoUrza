"""Ingesta del conocimiento de construcción de mazos en la base vectorial Chroma (mazos_db).

Uso (parado dentro de backend/):
    uv run python -m ingesta.ingestar_mazos
    uv run python -m ingesta.ingestar_mazos --rebuild
"""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import shutil
import sys
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingesta.corpus_mazos import DOCUMENTOS_MAZOS

BASE = Path(__file__).resolve().parent.parent
RAG_DIR = BASE / "mazos_db"
COLECCION = "arquetipos_mtg"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " "],
)


def preparar_documentos() -> list[Document]:
    docs = []
    for doc in DOCUMENTOS_MAZOS:
        chunks = SPLITTER.split_text(doc["contenido"].strip())
        for i, chunk in enumerate(chunks):
            docs.append(Document(
                page_content=chunk,
                metadata={
                    "doc_id": doc["id"],
                    "titulo": doc["titulo"],
                    "categoria": doc["categoria"],
                    "formato": doc["formato"],
                    "parte": i + 1,
                    "total_partes": len(chunks),
                }
            ))
    return docs


def indexar(rebuild: bool = False):
    if rebuild and RAG_DIR.exists():
        print(f"Borrando índice anterior en {RAG_DIR}...", flush=True)
        shutil.rmtree(RAG_DIR, ignore_errors=True)

    RAG_DIR.mkdir(parents=True, exist_ok=True)
    docs = preparar_documentos()
    print(f"Preparados {len(docs)} fragmentos a partir de {len(DOCUMENTOS_MAZOS)} guías de mazo.", flush=True)

    print(f"Cargando modelo de embeddings '{MODELO_EMBEDDINGS}'...", flush=True)
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)

    print(f"Creando colección '{COLECCION}' en {RAG_DIR}...", flush=True)
    vectorstore = Chroma(
        collection_name=COLECCION,
        embedding_function=embeddings,
        persist_directory=str(RAG_DIR),
    )

    vectorstore.add_documents(docs)
    print("¡Listo! Base de conocimiento de mazos indexada con éxito.", flush=True)


if __name__ == "__main__":
    rebuild_flag = "--rebuild" in sys.argv
    indexar(rebuild=rebuild_flag)
