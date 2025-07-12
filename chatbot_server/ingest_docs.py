"""
Bulk-ingest *all* supported documents found in /app/pdfs
into the LangChain PGVector store.

Supported extensions in this version
------------------------------------
    .pdf   – UnstructuredPDFLoader  (OCR for scanned PDFs)
    .doc   – UnstructuredWordDocumentLoader
    .docx  – UnstructuredWordDocumentLoader
    .xlsx  – UnstructuredExcelLoader
    .html  – UnstructuredFileLoader
    .eml   – UnstructuredFileLoader
    .txt   – UnstructuredFileLoader

Add more by updating EXTENSION_MAP.

Run inside the container:
    docker compose exec chatbot-server python ingest_docs.py
"""

from pathlib import Path
from langchain.document_loaders import (
    UnstructuredPDFLoader,            # OCR-capable for scanned PDFs
    UnstructuredWordDocumentLoader,   # .doc / .docx
    UnstructuredExcelLoader,          # .xlsx
    UnstructuredFileLoader,           # .html / .eml / .txt
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from chatbot_server.vectorstore import get_vectorstore

# --------------------------------------------------------------------
PDF_DIR       = Path("/app/pdfs")     # folder mounted in docker-compose.yml
CHUNK_SIZE    = 1000
CHUNK_OVERLAP = 200

EXTENSION_MAP = {
    ".pdf":  UnstructuredPDFLoader,
    ".doc":  UnstructuredWordDocumentLoader,
    ".docx": UnstructuredWordDocumentLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".html": UnstructuredFileLoader,
    ".eml":  UnstructuredFileLoader,
    ".txt":  UnstructuredFileLoader,
}
# --------------------------------------------------------------------


def load_and_split(file_path: Path):
    """Load one file, split into chunks, tag each chunk with its source path and category."""
    loader_cls = EXTENSION_MAP.get(file_path.suffix.lower())
    if not loader_cls:
        print(f"⚠️  Skipping unsupported type: {file_path.name}")
        return []

    docs = loader_cls(str(file_path)).load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)

    # Tag every chunk so we can query by file name later
    for doc in chunks:
        doc.metadata["source"] = str(file_path)
        
        # Add category metadata for bedford information files
        if file_path.name.startswith("bedford_"):
            doc.metadata["category"] = "bedford_information"
            # Extract topic from filename (e.g., "bedford_trash_recycling.txt" -> "trash_recycling")
            topic = file_path.name.replace("bedford_", "").replace(".txt", "").replace(".pdf", "")
            doc.metadata["topic"] = topic

    return chunks


def main() -> None:
    vs = get_vectorstore()
    files = sorted(
        f for f in PDF_DIR.iterdir()
        if f.suffix.lower() in EXTENSION_MAP
    )

    if not files:
        print(f"❌  No supported files found in {PDF_DIR.resolve()}")
        return

    for f in files:
        chunks = load_and_split(f)
        if not chunks:
            continue
        vs.add_documents(chunks)
        print(f"✅  Indexed {f.name:<50s} ({len(chunks)} chunks)")

    print("🎉  Bulk ingest complete.")


if __name__ == "__main__":
    main()
