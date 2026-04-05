# seju.neo

中文 | [English](README.md) | [Contrast Test](README.contrast-test.md)

> 一个轻量的 AI 助手运行时与多智能体自动化框架。

`seju-lite` 是运行时包名，`seju.neo` 是产品展示名。

## 为什么是 seju.neo

- 运行时轻量，模块边界清晰
- 支持多智能体路由
- 工具优先设计，内置工具与 MCP 并存
- 支持 CLI、API、Discord、Telegram、WhatsApp 等多通道
- 支持短期会话与长期记忆整合

## 架构概览

请求链路：

1. 入口接收消息
2. `WorkflowOrchestrator` 做路由决策
3. `AgentOrchestrator` 分发执行
4. `AgentLoop` 组装上下文、执行工具循环、写入会话与记忆
5. 返回最终结果

核心目录：

- `src/seju_lite/agent`：上下文、循环、编排、记忆、子智能体
- `src/seju_lite/tools`：内置工具、MCP 客户端与服务端
- `src/seju_lite/channels`：Discord / Telegram / WhatsApp 适配层
- `src/seju_lite/api`：FastAPI 接口
- `src/seju_lite/runtime`：应用启动、运行与关闭

## 项目结构

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

## 运行要求

- Python 3.11+
- `uv`
- Node.js 20+（前端开发或构建时需要）

## 快速开始

```bash
uv sync
uv run seju-lite config-validate --config config.json
uv run seju-lite chat --config config.json --session cli:local
```

启动长期运行模式：

```bash
uv run seju-lite start --config config.json
```

启动 API：

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

启动前端开发服务器：

```bash
cd web
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:3000
```

## 本地开发

日常开发推荐前后端分开启动。

后端：

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

前端：

```bash
cd web
npm run dev
```

这种方式热更新更快，也更方便排查问题。

## Docker 工作流

首次构建并启动：

```bash
docker compose up -d --build
```

直接启动已有容器：

```bash
docker compose up -d
```

仅重建后端：

```bash
docker compose up -d --build api
```

仅重建前端：

```bash
docker compose up -d --build web
```

查看运行状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f
```

停止整套服务：

```bash
docker compose down
```

## 环境变量

在 `.env` 中配置：

```dotenv
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
DISCORD_BOT_TOKEN=
TELEGRAM_BOT_TOKEN=
NOTION_TOKEN=
OPENAI_COMPATIBLE_BASE_URL=
SEJU_API_KEY=
```

说明：

- `config.json` 中支持 `${ENV_NAME}` 形式的环境变量插值
- 设置 `SEJU_API_KEY` 后，`/chat` 需要 Bearer Token，`/health` 保持公开

## CLI 命令

- `start`：启动长期运行服务
- `chat`：本地终端聊天
- `api`：启动 HTTP API
- `config-validate`：校验配置
- `tool-list`：列出已注册工具
- `test-provider`：直接测试模型提供方
- `mcp-server`：将内置工具作为 MCP Server 暴露

聊天内置命令：

- `/help`
- `/new`
- `/stop`
- `/restart`

## 配置重点

主配置文件：`config.json`

关键字段：

- `agent`
  - `mode`：`single` 或 `multi`
  - `defaultAgent`
  - `enableLlmPlanner`
  - `plannerConfidenceThreshold`
  - `enableSubagent`
  - `subagentMaxIterations`
  - `maxIterations`
  - `maxHistory`
  - `workspace`
  - `enableMemory`
  - `enableSkills`
  - `enableTools`
- `provider`
  - `kind`：`gemini` / `openai_compatible` / `deepseek`
  - 模型、温度与输出长度设置
- `channels`
  - Telegram / Discord / WhatsApp 等通道配置
- `tools`
  - 内置工具与 MCP 配置

## 路由与 Agent Mode

`seju-lite` 使用两层路由：

1. `WorkflowOrchestrator` 先决定目标 agent
2. `AgentOrchestrator` 再分发执行

`agent.mode` 的行为：

- `single`：始终使用 `defaultAgent`
- `multi`：先按关键字路由，再由可选的 LLM planner 调整

内置 agent 画像：

- `local`：偏本地工具
- `web`：偏网络与外部工具
- `main`：通用默认

## API

`GET /health`

```json
{
  "status": "ok",
  "app": "seju-lite",
  "model": "deepseek-chat"
}
```

`POST /chat`

请求：

```json
{
  "message": "hello",
  "conversation_id": "web-room-1",
  "user_id": "alice",
  "metadata": {}
}
```

响应：

```json
{
  "reply": "Hi there!",
  "conversation_id": "web-room-1"
}
```

## 记忆模型

- 短期会话历史：`workspace/sessions.json`
- 长期整合记忆：`workspace/memory/MEMORY.md`
- 历史摘要：`workspace/memory/HISTORY.md`

## MCP 集成

在 `config.json` 的 `tools.mcp.servers` 中配置 MCP 服务。

远端 MCP 工具会被包装为本地函数工具，命名格式：

```text
mcp_<server_name>_<tool_name>
```

## 开发

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

排查路由或工具问题时，可关注这些日志：

- `seju_lite.agent.workflow`
- `seju_lite.agent.orchestrator`
- `seju_lite.agent`

## 状态

项目仍在持续迭代中，路由、记忆和工具层都保持模块化，便于逐步演进。
