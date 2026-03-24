# seju.neo

[中文](README.zh-CN.md) | English | [Contrast Test](README.contrast-test.md)

<p align="center">
  <img src="assets/banner.svg" alt="seju.neo banner" width="760"/>
</p>

> 🧩 A personal lightweight multi-agent framework for practical AI automation.

`seju.neo` focuses on one goal: make agent systems easier to build, run, and evolve in real projects.

## ✨ Why seju.neo

- **Lightweight core**: small runtime surface, less framework overhead.
- **Multi-agent ready**: workflow routing + execution orchestration.
- **Tool-centric**: local tools + MCP servers for external capabilities.
- **Channel friendly**: API, Discord, Telegram, WhatsApp adapters.
- **Persistent memory**: session history + long-term memory workflow.

Inspired by:
- `openclaw/nanobot` → https://github.com/openclaw/nanobot

## 📚 Docs Map (Annotated)

- `README.md` - main homepage (English, production overview)
- `README.zh-CN.md` - Chinese main homepage
- `README.contrast-test.md` - contrast-design documentation experiment

Why separate pages:

- GitHub README is static markdown (no built-in dynamic i18n switch).
- Mixing EN/ZH + experimental style in one page hurts readability.
- Split pages keep each document focused and maintainable.

## 🏗️ Architecture

Execution flow:

1. **Ingress** receives a user message (channel or HTTP API).
2. **WorkflowOrchestrator** selects route (`rule` + optional `LLM planner`).
3. **AgentOrchestrator** dispatches to selected agent and records telemetry.
4. **AgentLoop** builds context, runs tool loop, persists history/memory.
5. **Egress** returns the final reply.

Key runtime layers:

- `src/seju_lite/agent`
  - `workflow_orchestrator.py` - workflow-level route decision
  - `orchestrator.py` - dispatch, timing, execution context
  - `loop.py` - context/LLM/tool loop, session save, memory consolidation
  - `context.py` - system prompt and runtime context assembly
- `src/seju_lite/tools`
  - built-in tools + MCP client bridge
- `src/seju_lite/channels`
  - channel adapters (Discord/Telegram/WhatsApp)
- `src/seju_lite/api`
  - FastAPI adapter for frontend/backend integration

## 📦 Project Structure

```text
seju-lite/
  assets/
  src/seju_lite/
    agent/
    api/
    bus/
    channels/
    config/
    providers/
    runtime/
    session/
    tools/
  tests/
  workspace/
    memory/
    sessions/
    skills/
  config.json
```

## 🚀 Quick Start

Requirements:

- Python 3.11+
- `uv` package manager

Install and validate:

```bash
uv sync
uv run seju-lite config-validate --config config.json
```

Run local CLI chat:

```bash
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

## 🧰 CLI Reference

- `start` - run inbound/outbound workers + enabled channels
- `chat` - local terminal chat loop
- `api` - launch HTTP API for frontend use
- `config-validate` - validate `config.json`
- `tool-list` - print runtime tool registry
- `test-provider` - direct LLM provider sanity check
- `mcp-server` - local built-in MCP server (`time/read_file/web_fetch`)
- `rag-mcp-server` - local RAG MCP server (SQLite FTS)

## ⚙️ Configuration Highlights

Main config file: `config.json`

Important blocks:

- `agent`
  - `mode`: `single` or `multi`
  - `defaultAgent`
  - `enableLlmPlanner`, `plannerConfidenceThreshold`
  - `maxIterations`, `maxHistory`
- `provider`
  - model/provider settings (`deepseek`, `gemini`, etc.)
- `channels`
  - telegram/discord/whatsapp enable + credentials
- `tools.mcp.servers`
  - external MCP server definitions (`stdio`, `sse`, `streamableHttp`)

## 🔌 API Contract

### `GET /health`

Response:

```json
{
  "status": "ok",
  "app": "seju-lite",
  "model": "deepseek-chat"
}
```

### `POST /chat`

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

`seju.neo` combines short-term and long-term memory:

- **Session history** in `workspace/sessions/*.json`
- **Consolidated memory** in `workspace/memory/MEMORY.md`
- **Long-range history summary** in `workspace/memory/HISTORY.md`

General pattern:

- Session stores recent turn-level dialogue.
- Consolidator periodically extracts stable facts.
- Context builder injects relevant memory into system/user context.

## 🔗 MCP Integration

MCP servers are registered under `tools.mcp.servers` in `config.json`.

Built-in examples already used in this repo:

- local utility MCP server
- local RAG MCP server
- Notion MCP server

At runtime, each remote MCP tool is wrapped and exposed as local tool names:

- format: `mcp_<server_name>_<tool_name>`

## 🧪 Development Tips

- Use `chat` mode for fast iteration.
- Keep `config-validate` in your edit loop.
- Prefer adding one MCP server/tool set at a time.
- For workflow tuning, monitor logs from:
  - `seju_lite.agent.workflow`
  - `seju_lite.agent.orchestrator`
  - `seju_lite.agent`

## 🛠️ Troubleshooting

- **No tool calls happen**
  - Check agent/tool allowlist logic and MCP tool registration logs.
- **Telegram conflict (`getUpdates`)**
  - Ensure only one bot process is polling at a time.
- **Slow responses**
  - Lower `maxIterations`
  - reduce unnecessary tools
  - switch to faster model for routing/simple tasks
- **MCP connect failures**
  - verify command/args
  - verify auth env vars
  - check transport type (`stdio/sse/streamableHttp`)

## 📌 Status

`seju.neo` is under active iteration.  
Architecture is intentionally modular so routing, memory, and tool layers can evolve independently.
