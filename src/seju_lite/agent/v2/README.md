# seju-lite agent v2

This folder contains an isolated v2 design for context and memory handling.

Goals:

- keep the current runtime untouched
- provide a DeerFlow-inspired summarization pre-processor
- experiment with structured long-term memory outside `MEMORY.md`
- make rollback trivial by keeping all new logic in one folder

Contents:

- `types.py`: small data models for v2 memory/context flow
- `memory/store.py`: structured memory store backed by `workspace/memory/memory.v2.json`
- `middleware/summarization.py`: DeerFlow-style short-term history processing
- `context/assembler.py`: standalone context assembler that consumes the v2 pieces
- `runtime_adapter.py`: bridge layer that can switch between old / v2_trim / v2_llm_summary modes

Summarization supports two modes:

- trim-only mode: decide what old history should be compressed, but do not call the LLM
- LLM mode: when `SummarizationConfigV2.llm_enabled=True`, call the provider to produce a compact summary text

Short-term history behavior is now closer to DeerFlow:

- trigger summarization when history exceeds a threshold
- keep a recent message window intact
- avoid splitting assistant/tool message bundles
- optionally replace older history with one synthetic summary message

These modules are not wired into the production path yet.
