"""Complete LangChain-based RAG pipeline for seju-lite.

Pipeline:
1) document loader
2) text splitter
3) embedding model
4) vector store
5) retrieval/search helpers
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class SearchResult:
    page_content: str
    metadata: dict[str, Any]
    score: float | None = None


class SejuRAG:
    """End-to-end RAG helper.

    Defaults are local and dependency-light:
    - embedding: HuggingFace local model
    - vector store: InMemoryVectorStore

    Optional:
    - pass `vector_backend="chroma"` and `persist_directory` for persistent storage.
    """

    def __init__(
        self,
        *,
        embedding_model: str = "google/embeddinggemma-300m",
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        vector_backend: str = "inmemory",
        collection_name: str = "seju_rag",
        persist_directory: str | Path | None = None,
    ):
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(100, int(chunk_size)),
            chunk_overlap=max(0, int(chunk_overlap)),
        )
        self.vector_backend = vector_backend.lower().strip()
        self.collection_name = collection_name
        self.persist_directory = (
            str(Path(persist_directory).resolve()) if persist_directory else None
        )
        self.vectorstore = self._build_vectorstore()

    def _build_vectorstore(self):
        if self.vector_backend == "inmemory":
            return InMemoryVectorStore(self.embeddings)

        if self.vector_backend == "chroma":
            try:
                from langchain_community.vectorstores import Chroma
            except Exception as exc:
                raise RuntimeError(
                    "Chroma backend requested but unavailable. Install dependencies: uv add chromadb"
                ) from exc

            if not self.persist_directory:
                raise ValueError(
                    "persist_directory is required when vector_backend='chroma'."
                )

            return Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory,
            )

        raise ValueError(
            f"Unsupported vector_backend='{self.vector_backend}'. Use 'inmemory' or 'chroma'."
        )

    def _loader_auto(self, file_path: str | Path):
        """Choose a LangChain loader by file extension."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        as_posix = str(path)

        if suffix in {".txt", ".log", ".md", ".markdown", ".rst"}:
            from langchain_community.document_loaders import TextLoader

            return TextLoader(as_posix, encoding="utf-8")

        if suffix in {".html", ".htm"}:
            from langchain_community.document_loaders import BSHTMLLoader

            return BSHTMLLoader(as_posix, open_encoding="utf-8")

        if suffix == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader

            return PyPDFLoader(as_posix)

        if suffix == ".docx":
            from langchain_community.document_loaders import Docx2txtLoader

            return Docx2txtLoader(as_posix)

        if suffix == ".csv":
            from langchain_community.document_loaders import CSVLoader

            return CSVLoader(file_path=as_posix, encoding="utf-8")

        if suffix == ".json":
            from langchain_community.document_loaders import JSONLoader

            return JSONLoader(file_path=as_posix, jq_schema=".", text_content=False)

        from langchain_community.document_loaders import TextLoader

        return TextLoader(as_posix, encoding="utf-8")

    def load_documents(self, file_path: str | Path) -> list[Document]:
        loader = self._loader_auto(file_path)
        try:
            docs = loader.load()
        except Exception as exc:
            raise RuntimeError(f"Failed to load '{file_path}': {exc}") from exc
        return docs

    def _split_documents(self, documents: list[Document]) -> list[Document]:
        return self.splitter.split_documents(documents)

    def ingest_file(
        self,
        file_path: str | Path,
        *,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        docs = self.load_documents(file_path)
        base_source = source or str(Path(file_path))
        extra = dict(metadata or {})

        for d in docs:
            d.metadata = dict(d.metadata or {})
            d.metadata.setdefault("source", base_source)
            d.metadata.update(extra)

        chunks = self._split_documents(docs)
        if not chunks:
            return {"documents": len(docs), "chunks": 0}

        self.vectorstore.add_documents(chunks)
        self._persist_if_needed()
        return {"documents": len(docs), "chunks": len(chunks)}

    def ingest_text(
        self,
        text: str,
        *,
        source: str = "inline",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        content = (text or "").strip()
        if not content:
            return {"documents": 0, "chunks": 0}

        doc = Document(page_content=content, metadata={"source": source, **(metadata or {})})
        chunks = self._split_documents([doc])
        if not chunks:
            return {"documents": 1, "chunks": 0}

        self.vectorstore.add_documents(chunks)
        self._persist_if_needed()
        return {"documents": 1, "chunks": len(chunks)}

    def retrieve(self, query: str, *, top_k: int = 5) -> list[SearchResult]:
        q = (query or "").strip()
        if not q:
            return []

        k = max(1, int(top_k))
        items = self.vectorstore.similarity_search_with_score(q, k=k)
        results: list[SearchResult] = []
        for doc, score in items:
            results.append(
                SearchResult(
                    page_content=doc.page_content,
                    metadata=dict(doc.metadata or {}),
                    score=float(score),
                )
            )
        return results

    def search(self, query: str, *, top_k: int = 5) -> str:
        rows = self.retrieve(query, top_k=top_k)
        if not rows:
            return "No relevant chunks found."

        lines: list[str] = []
        for i, row in enumerate(rows, start=1):
            source = row.metadata.get("source", "(unknown source)")
            score = f"{row.score:.4f}" if row.score is not None else "n/a"
            text = " ".join(row.page_content.split())
            lines.append(f"[{i}] source={source} score={score}\\n{text}")
        return "\\n\\n".join(lines)

    def _persist_if_needed(self) -> None:
        if self.vector_backend == "chroma":
            persist_fn = getattr(self.vectorstore, "persist", None)
            if callable(persist_fn):
                persist_fn()
