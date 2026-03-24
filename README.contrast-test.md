# SEJU.NEO

> **A + B + Contrast**
>  
> `SYSTEM (cold)` + `DOODLE (human)` + `HIGH CONTRAST`

<p align="center">
  <img src="assets/banner.svg" alt="seju.neo banner" length= "1600" width="400"/>
</p>

---

## Design DNA

SEJU.NEO is a **personal lightweight multi-agent framework** built on contrast:

- **A / System (Cold):** modular runtime, predictable interfaces, explicit orchestration
- **B / Doodle (Human):** playful prompts, expressive personality, imperfect-but-alive interactions
- **Visual Contrast:** clean blocks + quirky notes, strict hierarchy + emotional accents

---

## Core Formula

```text
A (System / Cold) + B (Emotion / Chaos / Cute / Human) + High-Contrast Visual Language = SEJU.NEO
```

---

## Architecture (System)

```text
Ingress (API / Channel)
  -> Workflow Orchestrator
    -> Agent Orchestrator
      -> Agent Loop (LLM + Tools + Memory)
        -> Egress (Reply)
```

- **WorkflowOrchestrator**: route planning (rule + optional LLM planner)
- **AgentOrchestrator**: dispatch + timing + telemetry
- **AgentLoop**: context build, tool calls, persistence
- **MCP Layer**: external capability injection

---

## Doodle Layer (Human)

> little notes from the machine:
>
> - "I can be strict in structure, but warm in interaction."
> - "I route with logic, I answer with personality."
> - "I am not a giant framework. I am your fast, hackable companion."

```text
  (^_^)/  "system on the outside"
   /|_|\   "human in the loop"
    / \
```

---

## Tone Examples

> "Structure first. Warmth always."
>  
> "I route with logic, and I speak like a teammate."
>  
> "Small framework, fast loops, human feel."

---

## Quick Test

```bash
uv sync
uv run seju-lite config-validate --config config.json
uv run seju-lite chat --config config.json --session cli:local
```

API mode:

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

---

## Why This README Exists

This file is a **contrast-design README experiment**.

- Keeps current production README untouched
- Tests `SYSTEM + DOODLE` brand direction
- Serves as a style prototype for future docs/site
- `README.md` is the production usage page (`how to use`)
- This file is the brand and design page (`why it feels this way`)

---

## Reference

- Inspired by `openclaw/nanobot`: https://github.com/openclaw/nanobot
