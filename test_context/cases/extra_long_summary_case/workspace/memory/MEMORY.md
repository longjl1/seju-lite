# Profile

- User prefers Chinese.
- User frequently tests long-session behavior, memory injection, and token cost.
- User wants practical, reproducible fixtures for prompt-size comparisons.

# Current Focus

- Verify that `v2_llm_summary` actually triggers an extra summary call.
- Compare old context, trimmed context, and summarized context under a long session.
- Keep the runtime migration path reversible and low-risk.

# Stable Facts

- Project: seju-lite
- Provider: DeepSeek-compatible chat model
- Comparison target: `old` vs `v2_trim` vs `v2_llm_summary`
- Long-term concern: excessive prompt growth during extended conversations
- Desired outcome: less prompt bloat without losing important continuity

# Preferences

- High-signal technical answers
- Concrete file references
- Minimal invasive changes
