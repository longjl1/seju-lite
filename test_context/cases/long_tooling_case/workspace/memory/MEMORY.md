# Profile

- User is actively evolving seju-lite toward a more production-like context and memory design.
- User cares about reversibility: new work should live in isolated files when possible.
- User often asks for file-level reasoning with exact line references.

# Current Focus

- Measure how much prompt cost can be reduced with v2 context handling.
- Keep the existing runtime stable while adding a narrow adapter-based switch.
- Understand exactly which data sources are injected: recent session history, MEMORY.md, runtime metadata, and skills.

# Stable Facts

- `HISTORY.md` is archival and not directly injected into prompts.
- `MEMORY.md` is the primary long-term memory source in the current path.
- Recent session history comes from unconsolidated session messages.
- The new `test_context` folder is intended for reproducible provider-usage comparisons.
- The user uses DeepSeek-compatible models and wants official `usage` numbers when possible.

# Engineering Notes

- The v2 design lives under `src/seju_lite/agent/v2`.
- The adapter file is `runtime_adapter.py`.
- The comparison command already supports `--force-history`.
- A separate standalone script exists for official provider usage comparison.

# Preferences

- Avoid broad invasive rewrites.
- Prefer one small hook in old runtime plus new isolated files.
- Keep explanations concrete, with “where in code” answers rather than abstract summaries.
