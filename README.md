# seju.neo

[中文](README.zh-CN.md) | English | [Contrast Test](README.contrast-test.md)

<p align="center">
  <img src="assets/banner.svg" alt="Centered image" length= "1600" width="400"/>
</p>
<!-- ![seju.neo banner](assets/banner.svg) -->

> 🧩 A personal, lightweight multi-agent framework for pragmatic AI automation.

## ✨ Vision

`seju.neo` is designed as a **personal lightweight multi-agent framework**:

- small core, clear boundaries, easy to hack
- practical orchestration over heavy abstraction
- API-first, channel-friendly, tool-extensible

Inspired by:
- `openclaw/nanobot` → https://github.com/openclaw/nanobot

## 📚 Docs Map (Annotated)

- `README.md` - default homepage (English, stable overview)
- `README.zh-CN.md` - Chinese version of the main homepage
- `README.contrast-test.md` - contrast-style design experiment (`SYSTEM + DOODLE`)

Why separate pages on GitHub:

- GitHub README is static markdown, not dynamic i18n UI
- one-page mixed EN/ZH + style experiments quickly becomes noisy
- split docs keep the homepage clean and each document purpose clear

## 🏗️ Architecture

Request pipeline:

1. **Ingress** (`Channel` / `API`) receives user input
2. **WorkflowOrchestrator** selects route (rules + optional LLM planner)
3. **AgentOrchestrator** dispatches and tracks execution metrics
4. **AgentLoop** runs context build + LLM/tool loop + persistence
5. **Egress** returns response to the original channel/API caller

## 🧱 Core Components

- `src/seju_lite/agent`
  - `workflow_orchestrator.py`: workflow planning and route decision
  - `orchestrator.py`: execution dispatch and timing
  - `loop.py`: main LLM/tool loop and session writes
  - `context.py`: system/context assembly (memory + skills)
- `src/seju_lite/tools`
  - built-in tools + MCP wrappers
- `src/seju_lite/channels`
  - Discord / Telegram / WhatsApp adapters
- `src/seju_lite/api`
  - FastAPI server (`/health`, `/chat`)
- `workspace`
  - sessions, memory (`MEMORY.md`, `HISTORY.md`), skill assets

## 🚀 Quick Start

```bash
uv sync
uv run seju-lite config-validate --config config.json
uv run seju-lite chat --config config.json --session cli:local
```

Long-running runtime:

```bash
uv run seju-lite start --config config.json
```

HTTP API:

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

## 🧰 CLI

- `start` - start long-running workers/channels
- `chat` - local terminal chat
- `api` - run HTTP API service
- `config-validate` - validate configuration
- `tool-list` - list runtime tools
- `test-provider` - direct provider call for debugging
- `mcp-server` - built-in local MCP server
- `rag-mcp-server` - lightweight RAG MCP server

## 🔌 API Contract

- `GET /health`
- `POST /chat`

`POST /chat` request:

```json
{
  "message": "hello",
  "conversation_id": "web-room-1",
  "user_id": "alice",
  "metadata": {}
}
```

`POST /chat` response:

```json
{
  "reply": "Hi there!",
  "conversation_id": "web-room-1"
}
```

## 📁 Project Layout

```text
seju-lite/
  assets/
  src/seju_lite/
    agent/
    api/
    channels/
    config/
    providers/
    runtime/
    tools/
  tests/
  workspace/
  config.json
```
