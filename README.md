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
