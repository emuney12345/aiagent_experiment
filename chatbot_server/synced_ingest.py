"""
Realtime watcher: keep /app/pdfs and langchain_pg_embedding in sync.

 • New / modified file → embeds (re-embeds if it already exists)
 • Deleted file        → removes its vectors
 • Renamed file        → handled automatically (old vectors dropped, new embedded)
 • Failsafe reconcile  → every 60 s folder ↔ DB diff is re-checked (never drifts)

Run inside the container:
    python synced_ingest.py
"""

import os, time
from pathlib import Path
from sqlalchemy import create_engine, text
from watchdog.observers.polling import PollingObserver as Observer   # cross-platform
from watchdog.events import FileSystemEventHandler

from chatbot_server.ingest_docs import load_and_split
from chatbot_server.vectorstore import get_vectorstore

# ─────────────────── env & db setup ───────────────────────────────
PDF_DIR = Path("/app/pdfs")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:securepass123@postgres:5432/chatbot_db",
)
engine = create_engine(DB_URL, pool_pre_ping=True)
vs = get_vectorstore()
# ──────────────────────────────────────────────────────────────────


def _sql_delete(path: Path):
    """Low-level helper."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM langchain_pg_embedding "
                "WHERE cmetadata->>'source' = :p"
            ),
            {"p": str(path)},
        )


def delete_vectors(path: Path) -> None:
    _sql_delete(path)
    print(f"🗑️  Removed vectors for {path.name}")


def ingest_file(path: Path) -> None:
    """(Re)embed one document and write its chunks."""
    if not path.exists():      # vanished mid-event
        return
    chunks = load_and_split(path)
    if not chunks:
        print(f"⚠️  No chunks found in {path.name}")
        return
    _sql_delete(path)          # de-dupe first
    vs.add_documents(chunks)
    
    # Enhanced logging for bedford information files
    if path.name.startswith("bedford_"):
        print(f"✅  Indexed {path.name} ({len(chunks)} chunks) - Bedford Information")
    else:
        print(f"✅  Indexed {path.name} ({len(chunks)} chunks)")


# ───────────────── watchdog handlers ──────────────────────────────
class Handler(FileSystemEventHandler):
    def on_created(self, ev):  ingest_file(Path(ev.src_path))
    def on_modified(self, ev): ingest_file(Path(ev.src_path))
    def on_deleted(self, ev):  delete_vectors(Path(ev.src_path))
    def on_moved(self, ev):    # rename = delete old + ingest new
        delete_vectors(Path(ev.src_path))
        ingest_file(Path(ev.dest_path))


def reconcile() -> None:
    """Every minute: ensure DB and folder are identical."""
    current = {p.resolve() for p in PDF_DIR.glob("*")}
    with engine.begin() as conn:
        db_paths = {
            Path(r[0]) for r in conn.execute(
                text("SELECT DISTINCT cmetadata->>'source' FROM langchain_pg_embedding")
            )
        }
    for extra in db_paths - current:
        delete_vectors(extra)
    for missing in current - db_paths:
        ingest_file(missing)


# ─────────────────────────── main ────────────────────────────────
if __name__ == "__main__":
    print("📡  Watching /app/pdfs for changes … (polling, 0.5 s)")
    observer = Observer(timeout=0.5)        # faster poll → catches quick renames
    observer.schedule(Handler(), str(PDF_DIR), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(60)                  # heartbeat every minute
            reconcile()                     # failsafe sync
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
