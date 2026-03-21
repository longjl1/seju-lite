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
