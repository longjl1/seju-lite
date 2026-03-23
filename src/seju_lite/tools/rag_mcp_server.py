"""Lightweight RAG MCP server backed by SQLite FTS5.

This server is intentionally dependency-light so it can run out of the box:
- ingest text/file into chunked documents
- retrieve top-k chunks with full-text ranking (bm25)

Tools:
- rag_ingest_text
- rag_ingest_file
- rag_search
- rag_clear_corpus
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    content = (text or "").strip()
    if not content:
        return []

    size = max(100, int(chunk_size))
    ov = max(0, min(int(overlap), size - 1))
    step = size - ov

    chunks: list[str] = []
    idx = 0
    while idx < len(content):
        chunk = content[idx : idx + size].strip()
        if chunk:
            chunks.append(chunk)
        idx += step
    return chunks


def _build_preview(text: str, max_chars: int = 220) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "..."


class RagStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks
                USING fts5(
                    corpus_id UNINDEXED,
                    source UNINDEXED,
                    chunk_text
                )
                """
            )
            conn.commit()

    def ingest_text(
        self,
        *,
        corpus_id: str,
        text: str,
        source: str = "",
        chunk_size: int = 800,
        overlap: int = 120,
    ) -> int:
        corpus = (corpus_id or "default").strip() or "default"
        chunks = _chunk_text(text=text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            return 0

        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO rag_chunks (corpus_id, source, chunk_text) VALUES (?, ?, ?)",
                [(corpus, source, c) for c in chunks],
            )
            conn.commit()
        return len(chunks)

    def search(self, *, query: str, corpus_id: str = "default", top_k: int = 5) -> list[dict[str, str]]:
        q = (query or "").strip()
        if not q:
            return []
        corpus = (corpus_id or "default").strip() or "default"
        k = max(1, min(int(top_k), 20))

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, chunk_text, bm25(rag_chunks) AS score
                FROM rag_chunks
                WHERE rag_chunks MATCH ? AND corpus_id = ?
                ORDER BY score
                LIMIT ?
                """,
                (q, corpus, k),
            ).fetchall()

        return [
            {
                "source": row[0] or "",
                "text": row[1] or "",
                "score": f"{row[2]:.4f}" if row[2] is not None else "",
            }
            for row in rows
        ]

    def clear_corpus(self, corpus_id: str = "default") -> int:
        corpus = (corpus_id or "default").strip() or "default"
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM rag_chunks WHERE corpus_id = ?", (corpus,))
            conn.commit()
            return int(cur.rowcount or 0)


def create_rag_mcp_server(
    *,
    name: str = "seju-rag",
    db_path: Path = Path("./workspace/rag/rag.db"),
):
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("MCP SDK is not installed. Install it with: pip install mcp") from exc

    store = RagStore(db_path)
    mcp = FastMCP(name=name)

    @mcp.tool(name="rag_ingest_text", description="Ingest raw text into a retrieval corpus")
    async def rag_ingest_text(
        corpus_id: str,
        text: str,
        source: str = "",
        chunk_size: int = 800,
        overlap: int = 120,
        preview: bool = False,
    ) -> str:
        n = store.ingest_text(
            corpus_id=corpus_id,
            text=text,
            source=source,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        if not preview:
            return f"Ingested {n} chunk(s) into corpus '{corpus_id}'."

        brief = _build_preview(text)
        return (
            f"Ingested {n} chunk(s) into corpus '{corpus_id}'.\n"
            f"Preview: {brief or '(empty)'}"
        )

    @mcp.tool(name="rag_ingest_file", description="Read a local file and ingest its content")
    async def rag_ingest_file(
        path: str,
        corpus_id: str,
        source: str = "",
        encoding: str = "utf-8",
        chunk_size: int = 800,
        overlap: int = 120,
        preview: bool = False,
    ) -> str:
        p = Path(path)
        if not p.is_file():
            return f"File not found: {path}"

        text = p.read_text(encoding=encoding)
        src = source or str(p)
        n = store.ingest_text(
            corpus_id=corpus_id,
            text=text,
            source=src,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        if not preview:
            return f"Ingested file '{p}' as {n} chunk(s) into corpus '{corpus_id}'."

        brief = _build_preview(text)
        return (
            f"Ingested file '{p}' as {n} chunk(s) into corpus '{corpus_id}'.\n"
            f"Preview: {brief or '(empty)'}"
        )

    @mcp.tool(name="rag_search", description="Retrieve top-k relevant chunks for a query")
    async def rag_search(query: str, corpus_id: str = "default", top_k: int = 5) -> str:
        rows = store.search(query=query, corpus_id=corpus_id, top_k=top_k)
        if not rows:
            return "No relevant chunks found."

        lines: list[str] = []
        for i, row in enumerate(rows, start=1):
            source = row["source"] or "(unknown source)"
            score = row["score"]
            text = row["text"].replace("\n", " ").strip()
            lines.append(f"[{i}] source={source} score={score}\n{text}")
        return "\n\n".join(lines)

    @mcp.tool(name="rag_clear_corpus", description="Delete all indexed chunks for one corpus")
    async def rag_clear_corpus(corpus_id: str = "default") -> str:
        n = store.clear_corpus(corpus_id=corpus_id)
        return f"Deleted {n} chunk(s) from corpus '{corpus_id}'."

    return mcp


def run_rag_mcp_server(
    *,
    transport: str = "stdio",
    name: str = "seju-rag",
    db_path: Path = Path("./workspace/rag/rag.db"),
) -> None:
    mcp = create_rag_mcp_server(name=name, db_path=db_path)
    mcp.run(transport=transport)
