# Context Usage Test Kit

This folder contains isolated fixtures and a standalone script for comparing
provider-billed token usage between the legacy context path and the v2 context
pipeline.

Goals:

- keep production runtime behavior unchanged
- test against a fixed `MEMORY.md`, `HISTORY.md`, and session file
- compare `old`, `v2_trim`, and `v2_llm_summary`
- read official provider `usage` fields instead of relying only on local estimates

Recommended structure:

- `cases/<case-name>/workspace/memory/MEMORY.md`
- `cases/<case-name>/workspace/memory/HISTORY.md`
- `cases/<case-name>/workspace/sessions/<session-key>.json`

Built-in cases:

- `sample_case`: minimal sanity-check fixture
- `long_story_case`: longer creative/worldbuilding-heavy fixture
- `long_tooling_case`: longer engineering/runtime-history fixture
- `extra_long_summary_case`: intentionally exceeds the default summary trigger so `v2_llm_summary` can make an extra LLM call

Example command:

```powershell
uv run python .\test_context\run_provider_usage_compare.py `
  --config .\config.json `
  --case-dir .\test_context\cases\sample_case `
  --session sample_session `
  --message "按照之前的历史讲个故事" `
  --with-llm-summary `
  --force-history
```

Notes:

- Official token usage requires an actual provider API call.
- For `v2_llm_summary`, the script includes both:
  - the summary pre-pass usage
  - the final answer generation usage
- `HISTORY.md` is kept in fixtures for realism, but the current runtime does not
  inject `HISTORY.md` directly into prompts. The main comparison point is:
  - legacy path: recent session history + compact/current memory path in codebase
  - v2 path: recent session history after v2 processing + structured memory context
