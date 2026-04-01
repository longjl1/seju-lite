from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

_TOP_LEVEL_HISTORY_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]")
_CHANNEL_HINT = re.compile(r"\b(cli|discord|telegram|whatsapp|api)\b", re.IGNORECASE)


@dataclass
class ChunkingStats:
    documents: int
    chunks: int
    history_documents: int
    markdown_documents: int


class EmbeddedDataModule:
    SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".log"}

    def __init__(
        self,
        data_path: str | Path,
        *,
        history_event_window: int = 1,
        history_event_overlap: int = 0,
        chunk_mode: str = "auto",
        recursive_chunk_size: int = 300,
        recursive_chunk_overlap: int = 20,
    ) -> None:
        self.data_path = Path(data_path)
        self.history_event_window = max(1, int(history_event_window))
        self.history_event_overlap = max(0, int(history_event_overlap))
        self.chunk_mode = (chunk_mode or "auto").strip().lower()
        self.recursive_chunk_size = max(50, int(recursive_chunk_size))
        self.recursive_chunk_overlap = max(0, int(recursive_chunk_overlap))
        self.documents: list[Document] = []
        self.chunks: list[Document] = []
        self.parent_child_map: dict[str, str] = {}
        self.parent_docs_by_id: dict[str, Document] = {}

    def load_documents(self) -> list[Document]:
        if not self.data_path.exists():
            raise FileNotFoundError(f"Path not found: {self.data_path}")

        if self.data_path.is_file():
            files = [self.data_path]
        else:
            files = sorted(
                path
                for path in self.data_path.rglob("*")
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS
            )

        docs: list[Document] = []
        for file_path in files:
            content = file_path.read_text(encoding="utf-8")
            parent_id = str(uuid4())
            doc = Document(
                page_content=content,
                metadata={
                    "source": str(file_path),
                    "file_name": file_path.name,
                    "parent_id": parent_id,
                    "doc_type": "parent",
                },
            )
            self._enhance_metadata(doc)
            docs.append(doc)
            self.parent_docs_by_id[parent_id] = doc

        self.documents = docs
        return docs

    def _enhance_metadata(self, doc: Document) -> None:
        source = str(doc.metadata.get("source", ""))
        path = Path(source)
        is_history = path.name.lower() == "history.md"
        doc.metadata["is_history"] = is_history
        doc.metadata["category"] = "memory_history" if is_history else "markdown_doc"
        match = _CHANNEL_HINT.search(source)
        if match:
            doc.metadata["channel_hint"] = match.group(1).lower()

    def chunk_documents(self) -> list[Document]:
        if not self.documents:
            raise ValueError("No documents loaded. Call load_documents() first.")

        headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
        chunks: list[Document] = []

        for doc in self.documents:
            if self.chunk_mode == "recursive_300":
                child_docs = self._recursive_split(
                    doc,
                    chunk_size=self.recursive_chunk_size,
                    chunk_overlap=self.recursive_chunk_overlap,
                )
            elif bool(doc.metadata.get("is_history")):
                child_docs = self._event_split_history(doc)
            else:
                child_docs = self._markdown_header_split(doc, headers_to_split_on=headers_to_split_on)
            chunks.extend(child_docs)

        self.chunks = chunks
        return chunks

    def _recursive_split(self, parent_doc: Document, *, chunk_size: int, chunk_overlap: int) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(50, int(chunk_size)),
            chunk_overlap=max(0, int(chunk_overlap)),
        )
        split_texts = splitter.split_text(parent_doc.page_content or "")
        out: list[Document] = []

        for i, text in enumerate(split_texts):
            child_id = str(uuid4())
            meta = dict(parent_doc.metadata)
            meta.update(
                {
                    "doc_type": "child",
                    "chunk_type": "recursive_300",
                    "chunk_id": child_id,
                    "chunk_index": i,
                    "chunk_size": len(text),
                }
            )
            out.append(Document(page_content=text, metadata=meta))
            self.parent_child_map[child_id] = str(parent_doc.metadata["parent_id"])
        return out

    def _markdown_header_split(
        self,
        parent_doc: Document,
        *,
        headers_to_split_on: list[tuple[str, str]],
    ) -> list[Document]:
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,
        )
        split_docs = splitter.split_text(parent_doc.page_content)
        out: list[Document] = []

        for i, chunk in enumerate(split_docs):
            child_id = str(uuid4())
            merged_meta = dict(parent_doc.metadata)
            merged_meta.update(dict(chunk.metadata or {}))
            merged_meta.update(
                {
                    "doc_type": "child",
                    "chunk_type": "markdown",
                    "chunk_id": child_id,
                    "chunk_index": i,
                    "chunk_size": len(chunk.page_content),
                }
            )
            out.append(Document(page_content=chunk.page_content, metadata=merged_meta))
            self.parent_child_map[child_id] = str(parent_doc.metadata["parent_id"])
        return out

    def _event_split_history(self, parent_doc: Document) -> list[Document]:
        events = self._extract_history_events(parent_doc.page_content)
        if not events:
            child_id = str(uuid4())
            meta = dict(parent_doc.metadata)
            meta.update(
                {
                    "doc_type": "child",
                    "chunk_type": "event_fallback",
                    "chunk_id": child_id,
                    "chunk_index": 0,
                    "event_count": 1,
                    "chunk_size": len(parent_doc.page_content),
                }
            )
            self.parent_child_map[child_id] = str(parent_doc.metadata["parent_id"])
            return [Document(page_content=parent_doc.page_content, metadata=meta)]

        chunks: list[Document] = []
        for idx, event in enumerate(events):
            child_id = str(uuid4())
            meta = dict(parent_doc.metadata)
            meta.update(
                {
                    "doc_type": "child",
                    "chunk_type": "event",
                    "chunk_id": child_id,
                    "chunk_index": idx,
                    "chunk_size": len(event["text"]),
                    "event_count": 1,
                    "timestamp_start": event["timestamp"],
                    "timestamp_end": event["timestamp"],
                    "channels": event["channels"],
                }
            )
            chunks.append(Document(page_content=event["text"], metadata=meta))
            self.parent_child_map[child_id] = str(parent_doc.metadata["parent_id"])
        return chunks

    def _extract_history_events(self, content: str) -> list[dict[str, Any]]:
        lines = content.splitlines()
        starts: list[int] = []
        stamps: list[str] = []
        for i, line in enumerate(lines):
            match = _TOP_LEVEL_HISTORY_TS.match(line.strip())
            if match:
                starts.append(i)
                stamps.append(match.group(1))
        if not starts:
            return []

        events: list[dict[str, Any]] = []
        for idx, line_index in enumerate(starts):
            next_index = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            event_text = "\n".join(lines[line_index:next_index]).strip()
            if not event_text:
                continue
            channel_hits = sorted({m.group(1).lower() for m in _CHANNEL_HINT.finditer(event_text)})
            events.append({"timestamp": stamps[idx], "text": event_text, "channels": channel_hits})
        return events

    def get_stats(self) -> ChunkingStats:
        history_docs = sum(1 for d in self.documents if bool(d.metadata.get("is_history")))
        markdown_docs = len(self.documents) - history_docs
        return ChunkingStats(
            documents=len(self.documents),
            chunks=len(self.chunks),
            history_documents=history_docs,
            markdown_documents=markdown_docs,
        )


class EmbeddedIndexModule:
    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", device: str = "auto") -> None:
        self.model_name = model_name
        self.device = device
        self.embeddings: HuggingFaceEmbeddings | None = None
        self.vectorstore: InMemoryVectorStore | None = None
        self.setup_embeddings()

    @staticmethod
    def _resolve_device(device: str) -> str:
        request = (device or "auto").strip().lower()
        if request in {"cpu", "cuda"}:
            return request
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def setup_embeddings(self) -> None:
        resolved = self._resolve_device(self.device)
        logger.info("Embedded simpleRAG embedding model=%s device=%s", self.model_name, resolved)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={"device": resolved},
            encode_kwargs={"normalize_embeddings": True},
        )

    def build_index(self, documents: list[Document]) -> InMemoryVectorStore:
        if self.embeddings is None:
            self.setup_embeddings()
        self.vectorstore = InMemoryVectorStore(self.embeddings)
        self.vectorstore.add_documents(documents)
        return self.vectorstore


class EmbeddedRetrieveModule:
    def __init__(self, vectorstore: InMemoryVectorStore, chunks: list[Document]):
        self.vectorstore = vectorstore
        self.chunks = chunks
        self.vector_retriever = self.vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})
        try:
            from langchain_community.retrievers import BM25Retriever

            self.bm25_retriever = BM25Retriever.from_documents(self.chunks, k=5)
        except Exception as exc:
            logger.warning("Embedded simpleRAG BM25 unavailable; fallback to vector only: %s", exc)
            self.bm25_retriever = None

    def hybrid_retrieve(self, query: str, k: int = 3) -> list[Document]:
        vector_docs = self.vector_retriever.invoke(query)
        if self.bm25_retriever is None:
            return vector_docs[:k]
        bm25_docs = self.bm25_retriever.invoke(query)
        return self._rrf_rerank(vector_docs, bm25_docs)[:k]

    def _rrf_rerank(self, vector_docs: list[Document], bm25_docs: list[Document], k: int = 60) -> list[Document]:
        doc_scores: dict[int, float] = {}
        doc_objects: dict[int, Document] = {}
        for rank, doc in enumerate(vector_docs):
            doc_id = hash(doc.page_content)
            doc_objects[doc_id] = doc
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
        for rank, doc in enumerate(bm25_docs):
            doc_id = hash(doc.page_content)
            doc_objects[doc_id] = doc
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        out: list[Document] = []
        for doc_id, final_score in sorted_docs:
            doc = doc_objects[doc_id]
            doc.metadata["rrf_score"] = float(final_score)
            out.append(doc)
        return out


def _preview_text(text: str, limit: int = 240) -> str:
    compact = " ".join((text or "").split())
    return compact if len(compact) <= limit else compact[:limit].rstrip() + "..."


@dataclass
class EmbeddedCorpus:
    data_path: str
    signature: tuple[tuple[str, int, int], ...]
    stats: ChunkingStats
    retrieve_module: EmbeddedRetrieveModule


class EmbeddedSimpleRAGRuntime:
    def __init__(self, workspace: Path, embedding_model: str = "Qwen/Qwen3-Embedding-0.6B") -> None:
        self.workspace = workspace
        self.embedding_model = embedding_model
        self._cache: dict[str, EmbeddedCorpus] = {}

    def _build_signature(self, data_path: Path) -> tuple[tuple[str, int, int], ...]:
        if data_path.is_file():
            stat = data_path.stat()
            return ((str(data_path.resolve()), int(stat.st_mtime_ns), stat.st_size),)

        files = sorted(
            path
            for path in data_path.rglob("*")
            if path.is_file() and path.suffix.lower() in EmbeddedDataModule.SUPPORTED_EXTENSIONS
        )
        signature: list[tuple[str, int, int]] = []
        for file_path in files:
            stat = file_path.stat()
            signature.append((str(file_path.resolve()), int(stat.st_mtime_ns), stat.st_size))
        return tuple(signature)

    def ingest(self, data_path: str) -> ChunkingStats:
        path = Path(data_path).expanduser().resolve()
        data_module = EmbeddedDataModule(path)
        data_module.load_documents()
        chunks = data_module.chunk_documents()
        index_module = EmbeddedIndexModule(model_name=self.embedding_model)
        vectorstore = index_module.build_index(chunks)
        retrieve_module = EmbeddedRetrieveModule(vectorstore, chunks)
        stats = data_module.get_stats()
        self._cache[str(path)] = EmbeddedCorpus(
            data_path=str(path),
            signature=self._build_signature(path),
            stats=stats,
            retrieve_module=retrieve_module,
        )
        return stats

    def ensure_ready(self, data_path: str, force_rebuild: bool = False) -> EmbeddedCorpus:
        path = Path(data_path).expanduser().resolve()
        key = str(path)
        signature = self._build_signature(path)
        cached = self._cache.get(key)
        if force_rebuild or cached is None or cached.signature != signature:
            self.ingest(key)
            cached = self._cache[key]
        return cached


class _EmbeddedSimpleRAGBaseTool:
    def __init__(self, runtime: EmbeddedSimpleRAGRuntime):
        self.runtime = runtime
        self._context: dict[str, Any] = {}

    def set_context(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        chat_id: str | None = None,
        session_key: str | None = None,
        channel: str | None = None,
        **_: Any,
    ) -> None:
        self._context = dict(metadata or {})
        if chat_id:
            self._context["chat_id"] = chat_id
        if session_key:
            self._context["session_key"] = session_key
        if channel:
            self._context["channel"] = channel

    def _resolve_data_path(self, data_path: str = "") -> str:
        metadata_upload_data_path = str(self._context.get("upload_data_path") or "").strip()
        chat_id = str(self._context.get("chat_id") or "").strip()
        resolved = (data_path or metadata_upload_data_path or "").strip()
        if not resolved:
            if chat_id:
                candidate = self.runtime.workspace / "uploads" / chat_id
                if candidate.exists():
                    resolved = str(candidate)
        logger.info(
            "embedded_rag path resolution upload_data_path=%s chat_id=%s resolved=%s",
            metadata_upload_data_path or "(empty)",
            chat_id or "(empty)",
            resolved or "(empty)",
        )
        if not resolved:
            raise ValueError("No upload data path is available for this session.")
        return resolved


class EmbeddedRagIngestTool(_EmbeddedSimpleRAGBaseTool):
    name = "rag_ingest"

    def __init__(self, runtime: EmbeddedSimpleRAGRuntime):
        super().__init__(runtime)
        self.definition = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "Build or refresh the embedded simpleRAG index for uploaded files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_path": {"type": "string"},
                        "index_path": {"type": "string"},
                    },
                },
            },
        }

    async def run(self, data_path: str = "", index_path: str = "") -> str:
        del index_path
        resolved = self._resolve_data_path(data_path)
        stats = self.runtime.ingest(resolved)
        return (
            f"Embedded simpleRAG index ready for {resolved}.\n"
            f"documents={stats.documents} chunks={stats.chunks} "
            f"history_documents={stats.history_documents} markdown_documents={stats.markdown_documents}"
        )


class EmbeddedRagRetrieveTool(_EmbeddedSimpleRAGBaseTool):
    name = "rag_retrieve"

    def __init__(self, runtime: EmbeddedSimpleRAGRuntime):
        super().__init__(runtime)
        self.definition = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "Retrieve top-k relevant chunks from uploaded files using embedded simpleRAG.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "default": 5},
                        "data_path": {"type": "string"},
                        "index_path": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        }

    async def run(self, query: str, top_k: int = 5, data_path: str = "", index_path: str = "") -> str:
        del index_path
        resolved = self._resolve_data_path(data_path)
        corpus = self.runtime.ensure_ready(resolved)
        chunks = corpus.retrieve_module.hybrid_retrieve(query, k=max(1, int(top_k)))
        if not chunks:
            return "No relevant chunks found."
        lines = [f"embedded_data_path={resolved}", f"chunks={len(chunks)}"]
        for idx, chunk in enumerate(chunks, start=1):
            meta = dict(chunk.metadata or {})
            source = meta.get("source") or meta.get("file_name") or "(unknown source)"
            rrf = meta.get("rrf_score", "")
            suffix = f" rrf={rrf}" if rrf != "" else ""
            lines.append(f"[{idx}] source={source}{suffix}\n{_preview_text(chunk.page_content)}")
        return "\n\n".join(lines)


class EmbeddedRagAnswerTool(_EmbeddedSimpleRAGBaseTool):
    name = "rag_answer"

    def __init__(self, runtime: EmbeddedSimpleRAGRuntime):
        super().__init__(runtime)
        self.definition = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "Retrieve grounded context from uploaded files for answering a question with embedded simpleRAG.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "default": 5},
                        "data_path": {"type": "string"},
                        "index_path": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        }

    async def run(self, query: str, top_k: int = 5, data_path: str = "", index_path: str = "") -> str:
        del index_path
        resolved = self._resolve_data_path(data_path)
        corpus = self.runtime.ensure_ready(resolved)
        chunks = corpus.retrieve_module.hybrid_retrieve(query, k=max(1, int(top_k)))
        if not chunks:
            return "No relevant chunks found for the question."
        lines = [
            f"Question: {query}",
            "Use the following retrieved context to answer strictly from the uploaded files.",
        ]
        for idx, chunk in enumerate(chunks, start=1):
            meta = dict(chunk.metadata or {})
            source = meta.get("source") or meta.get("file_name") or "(unknown source)"
            lines.append(f"[Context {idx}] source={source}\n{chunk.page_content.strip()}")
        return "\n\n".join(lines)
