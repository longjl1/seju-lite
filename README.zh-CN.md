# seju.neo

中文 | [English](README.md)

![seju.neo banner](assets/banner.svg)

> 🧩 一个面向个人开发的轻量级多智能体框架（personal lightweight multi-agent framework）。

## ✨ 设计理念

`seju.neo` 的定位很明确：**个人可维护、可扩展、可快速迭代**。

- 核心尽量小，边界尽量清晰
- 优先实用编排，不堆叠过度抽象
- API 优先，通道友好，工具可插拔

灵感来源：
- `openclaw/nanobot` → https://github.com/openclaw/nanobot

## 🏗️ 整体架构

请求主链路：

1. **入口层**（`Channel` / `API`）接收用户输入
2. **WorkflowOrchestrator** 选择路径（规则路由 + 可选 LLM planner）
3. **AgentOrchestrator** 分发执行并记录耗时
4. **AgentLoop** 执行上下文构建 + LLM/工具循环 + 持久化
5. **出口层** 返回响应到对应通道/API

## 🧱 核心组件

- `src/seju_lite/agent`
  - `workflow_orchestrator.py`：工作流规划与路由决策
  - `orchestrator.py`：执行分发与计时
  - `loop.py`：LLM + 工具主循环与会话写入
  - `context.py`：系统提示词/上下文拼装（记忆 + 技能）
- `src/seju_lite/tools`
  - 内置工具与 MCP 包装
- `src/seju_lite/channels`
  - Discord / Telegram / WhatsApp 适配层
- `src/seju_lite/api`
  - FastAPI 服务（`/health`、`/chat`）
- `workspace`
  - 会话、记忆（`MEMORY.md`、`HISTORY.md`）、技能资源

## 🚀 快速开始

```bash
uv sync
uv run seju-lite config-validate --config config.json
uv run seju-lite chat --config config.json --session cli:local
```

常驻运行：

```bash
uv run seju-lite start --config config.json
```

启动 HTTP API：

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

## 🧰 CLI 命令

- `start` - 启动常驻 worker / channels
- `chat` - 本地终端聊天
- `api` - 启动 HTTP API 服务
- `config-validate` - 校验配置
- `tool-list` - 列出运行时工具
- `test-provider` - 直连模型调试
- `mcp-server` - 启动内置 MCP server
- `rag-mcp-server` - 启动轻量 RAG MCP server

## 🔌 API 契约

- `GET /health`
- `POST /chat`

`POST /chat` 请求：

```json
{
  "message": "hello",
  "conversation_id": "web-room-1",
  "user_id": "alice",
  "metadata": {}
}
```

`POST /chat` 返回：

```json
{
  "reply": "Hi there!",
  "conversation_id": "web-room-1"
}
```

## 📁 项目结构

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
