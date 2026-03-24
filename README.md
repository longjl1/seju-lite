![seju.neo](assets/banner.svg)

# Seju Lite

A lightweight Telegram-first AI assistant inspired by nanobot.

## Features
- Telegram-only V1
- Single agent loop
- OpenAI-compatible provider
- Session memory
- File/time tools
- uv-based development

## Run
```bash
uv sync
cp .env.example .env
uv run seju-lite chat --config config.json
# or run long-lived Telegram runtime:
uv run seju-lite start --config config.json
```

## Commands
You can view built-in help with:

```bash
uv run seju-lite --help
uv run seju-lite <command> --help
```

### `start`
Start the long-running runtime service.

```bash
uv run seju-lite start --config config.json
```

Options:
- `-c, --config`: Path to config file (default: `config.json`)

Notes:
- `start` now uses a single-instance lock at `./workspace/runtime/start.lock`.
- If another instance is running, startup exits early to prevent Telegram polling conflicts.

### `chat`
Run local terminal chat (without Telegram).

```bash
uv run seju-lite chat --config config.json --session cli:local
```

Options:
- `-c, --config`: Path to config file (default: `config.json`)
- `-s, --session`: CLI session key (default: `cli:local`)

### `config-validate`
Validate config file only.

```bash
uv run seju-lite config-validate --config config.json
```

Options:
- `-c, --config`: Path to config file (default: `config.json`)

### `tool-list`
Print registered tools from runtime.

```bash
uv run seju-lite tool-list --config config.json
```

Options:
- `-c, --config`: Path to config file (default: `config.json`)

### `test-provider`
Send one prompt directly to provider for debugging.

```bash
uv run seju-lite test-provider --prompt "hello" --config config.json
```

Options:
- `-p, --prompt`: Prompt to send to provider (required)
- `-c, --config`: Path to config file (default: `config.json`)

### `mcp-server`
Start a local MCP server that exposes built-in seju-lite tools (`time`, `read_file`, `web_fetch`).

```bash
uv run seju-lite mcp-server --config config.json --transport stdio
```

Options:
- `-c, --config`: Path to config file (default: `config.json`)
- `-t, --transport`: MCP transport (`stdio`, `sse`, `streamable-http`)
- `-n, --name`: MCP server name (default: `seju-lite-tools`)

### `rag-mcp-server`
Start a lightweight RAG MCP server (SQLite FTS-based).

```bash
uv run seju-lite rag-mcp-server --transport stdio --name seju-rag --db ./workspace/rag/rag.db
```

Tools exposed by this server:
- `rag_ingest_text`
- `rag_ingest_file`
- `rag_search`
- `rag_clear_corpus`

Ingest tools default to ack-only responses (no auto summary).  
Pass `preview=true` only when you explicitly want a short preview.

Options:
- `-t, --transport`: MCP transport (`stdio`, `sse`, `streamable-http`)
- `-n, --name`: MCP server name (default: `seju-rag`)
- `--db`: SQLite index path (default: `./workspace/rag/rag.db`)

Register this server in `config.json`:

```json
{
  "tools": {
    "mcp": {
      "enabled": true,
      "servers": {
        "rag_local": {
          "type": "stdio",
          "command": "uv",
          "args": [
            "run",
            "seju-lite",
            "rag-mcp-server",
            "--transport",
            "stdio",
            "--name",
            "seju-rag",
            "--db",
            "./workspace/rag/rag.db"
          ],
          "enabledTools": ["*"],
          "toolTimeout": 20
        }
      }
    }
  }
}
```

### `api`
Start an HTTP API server for frontend integration.

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

Options:
- `-c, --config`: Path to config file (default: `config.json`)
- `--host`: Bind host (default: `127.0.0.1`)
- `--port`: Bind port (default: `8000`)
- `--reload`: Enable auto reload in development

Middleware defaults:
- CORS enabled for local frontend origins:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
- Request tracing headers:
  - `X-Request-ID`
  - `X-Process-Time-Ms`
- Optional API key auth for all endpoints except `/health`:
  - set `SEJU_API_KEY=<your-key>`
  - send header `Authorization: Bearer <your-key>`

Optional CORS env vars:
- `SEJU_API_CORS_ORIGINS` (comma-separated)
- `SEJU_API_CORS_METHODS` (comma-separated)
- `SEJU_API_CORS_HEADERS` (comma-separated)
- `SEJU_API_CORS_ALLOW_CREDENTIALS` (`true`/`false`)

Endpoints:
- `GET /health`
- `POST /chat`
  - request:
    ```json
    {
      "message": "hello",
      "conversation_id": "web-room-1",
      "user_id": "alice",
      "metadata": {}
    }
    ```
  - response:
    ```json
    {
      "reply": "Hi there!",
      "conversation_id": "web-room-1"
    }
    ```
