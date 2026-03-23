"""LangChain-based RAG skeleton for seju-lite tools.

This module is intentionally standalone and does not wire itself into the
existing runtime.  Import it in a future MCP tool/server and plug in
your own vector store + embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path
import getpass
import os


@dataclass
class RetrievedDocument:
    """Normalized retrieval output for app-level consumption."""

    page_content: str
    metadata: dict[str, Any]


if not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

class SejuRAG:
    """Minimal RAG skeleton exposing retrieve + search.

    Usage outline:
    1) Build a LangChain vector store externally.
    2) Pass `retriever` directly, or pass `vectorstore` and let this class build one.
    3) Call `retrieve()` for raw chunks, or `search()` for simple formatted output.
    """
    def __init__(self,file:Path):
        pass

    def _load_file(self): 
        pass
