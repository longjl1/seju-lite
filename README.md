# seju.neo

[中文](README.zh-CN.md) | English | [Contrast Test](README.contrast-test.md)

<!-- <p align="center">
  <img src="assets/banner.svg" alt="seju.neo banner" length="1600" width="400"/>
</p> -->

> A personal lightweight multi-agent framework for AI automation.

`seju-lite` is the runtime package. `seju.neo` is the product-facing identity.



## ✨ Why seju.neo

- Lightweight runtime with clear module boundaries.
- Multi-agent routing (`rule + optional LLM planner`).
- Tool-first design (built-in tools + MCP servers).
- Multi-channel support (CLI, API, Discord, Telegram, WhatsApp).
- Persistent memory with short-term and long-term consolidation.

Inspired by `openclaw & nanobot`

## 🏗️ Architecture

Request lifecycle:

1. Ingress receives user input (`channel` or `API`).
2. `WorkflowOrchestrator` decides route.
3. `AgentOrchestrator` dispatches execution.
4. `AgentLoop` builds context, runs tool loop, stores session/memory.
5. Egress returns final response.

Core modules:

- `src/seju_lite/agent`: context, loop, orchestration, memory, subagent.
- `src/seju_lite/tools`: built-in tools, MCP client/server.
- `src/seju_lite/channels`: Discord/Telegram/WhatsApp adapters.
- `src/seju_lite/api`: FastAPI service (`/health`, `/chat`).
- `src/seju_lite/runtime`: app bootstrap, workers, graceful shutdown.

## 📦 Project Structure

```text
seju-lite/
  assets/
  src/seju_lite/
    agent/
    api/
    bus/
    channels/
    cli/
    config/
    providers/
    runtime/
    session/
    tools/
    utils/
  tests/
  workspace/
    memory/
    sessions/
    skills/
  config.json
```

## ✅ Requirements

- Python 3.11+
- `uv` package manager

## 🚀 Quick Start

```bash
uv sync
uv run seju-lite config-validate --config config.json
uv run seju-lite chat --config config.json --session cli:local
```

Run long-lived runtime:

```bash
uv run seju-lite start --config config.json
```

Run API server:

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

## 🔐 Environment Variables

Set credentials in `.env` (example keys):

```dotenv
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
DISCORD_BOT_TOKEN=
TELEGRAM_BOT_TOKEN=
NOTION_TOKEN=
OPENAI_COMPATIBLE_BASE_URL=
SEJU_API_KEY=
```

Notes:

- `provider.apiKey` and channel tokens in `config.json` support `${ENV_NAME}` interpolation.
- `SEJU_API_KEY` enables Bearer auth for `/chat` (health endpoint stays public).

## 🧰 CLI Commands

- `start`: start workers and enabled channels.
- `chat`: local terminal chat loop.
- `api`: start HTTP API server.
- `config-validate`: validate `config.json`.
- `tool-list`: list registered tools.
- `test-provider`: direct LLM provider check.
- `mcp-server`: expose built-in tools as an MCP server.

Built-in slash commands in chat sessions:

- `/help`
- `/new` (reset short-term history, keep long-term memory)
- `/stop` (cancel running subagent tasks)
- `/restart`

## ⚙️ Configuration Highlights

Main config file: `config.json`

Important sections:

- `agent`
  - `mode`: `single` or `multi`
  - `defaultAgent`
  - `enableLlmPlanner`, `plannerConfidenceThreshold`
  - `enableSubagent`, `subagentMaxIterations`
  - `maxIterations`, `maxHistory`
  - `workspace`, `enableMemory`, `enableSkills`, `enableTools`
- `provider`
  - `kind`: `gemini` / `openai_compatible` / `deepseek`
  - model + temperature + output token settings
- `channels`
  - Telegram / Discord / WhatsApp enable + credentials + policy
- `tools`
  - built-in tools (`time`, `readFile`, `web`, `shell`)
  - `mcp.servers` (`stdio`, `sse`, `streamableHttp`)

### Routing and Agent Mode

`seju-lite` uses a two-stage routing pipeline:

1. `WorkflowOrchestrator` selects the target agent.
2. `AgentOrchestrator` dispatches the request to the selected agent.

`agent.mode` behavior:

- `single`: always runs `defaultAgent`; keyword routing and LLM planner are bypassed.
- `multi`: uses keyword routing first (`agent.routing`), then optional LLM planner (`enableLlmPlanner`) may override the result.

Built-in agent profiles:

- `local`: local/non-network tools.
- `web`: network/external tools (for example `mcp_playwright_*` and web fetch style tools).
- `main`: general fallback profile.

Practical note:

- If `agent.mode` is `single` and `defaultAgent` is `local`, a prompt like "google search ..." still stays on `local`, so Playwright/network tools will not be called.

## 🔌 API Contract

### ❤️ `GET /health`

```json
{
  "status": "ok",
  "app": "seju-lite",
  "model": "deepseek-chat"
}
```

### 💬 `POST /chat`

Request:

```json
{
  "message": "hello",
  "conversation_id": "web-room-1",
  "user_id": "alice",
  "metadata": {}
}
```

Response:

```json
{
  "reply": "Hi there!",
  "conversation_id": "web-room-1"
}
```

## 🧠 Memory Model

- Short-term session history: `workspace/sessions.json`
- Long-term consolidated memory: `workspace/memory/MEMORY.md`
- Historical digest: `workspace/memory/HISTORY.md`

Behavior:

- Recent turns are loaded for context.
- Consolidator periodically extracts stable facts.
- Context builder injects memory and skills into prompts.

## 🔗 MCP Integration

Define MCP servers in `tools.mcp.servers` under `config.json`.

This repository includes examples for:

- local utility MCP server
- external simpleRAG MCP server
- Notion MCP server
- Playwright MCP server

Remote MCP tools are wrapped as local function tools:

- naming format: `mcp_<server_name>_<tool_name>`

Default config points the `simple_rag` MCP entry at the sibling project:

```bash
uv run --project ../simpleRAG simple-rag --data-path ../simpleRAG/data --index-path ../simpleRAG/index_store mcp-server --transport stdio --name simple-rag
```

## 🧪 Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

Useful logs for routing/tool issues:

- `seju_lite.agent.workflow`
- `seju_lite.agent.orchestrator`
- `seju_lite.agent`

## 📌 Status

Project is under active iteration. Routing, memory, and tooling are intentionally modular for incremental evolution.
