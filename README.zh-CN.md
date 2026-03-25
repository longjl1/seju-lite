# seju.neo

中文 | [English](README.md) | [对比设计实验](README.contrast-test.md)

<p align="center">
  <img src="assets/banner.svg" alt="seju.neo banner" length="1600" width="400"/>
</p>

> 这是一个轻量级多智能体框架.

`seju-lite` 是运行时包名，`seju.neo` 是产品展示名称。


## ✨ seju.neo？

- 运行时轻量，模块边界清晰。
- 支持多智能体路由（规则 + 可选 LLM Planner）。
- 工具优先（内置工具 + MCP 服务）。
- 多通道接入（CLI、API、Discord、Telegram、WhatsApp）。
- 持久记忆（短期会话 + 长期归档整合）。

灵感来源：`openclaw & nanobot` 

## 🍤 Update 
- 2026.3.24 新增路由决策层，选择agent（规则路由 + 可选 LLM planner）派发task

## 🏗️ 架构总览

请求主链路：

1. 入口接收消息（`channel` 或 `API`）。
2. `WorkflowOrchestrator` 进行路由决策。
3. `AgentOrchestrator` 分发执行。
4. `AgentLoop` 组装上下文、执行工具循环、写入会话与记忆。
5. 出口返回最终回复。

核心目录：

- `src/seju_lite/agent`：上下文、循环、编排、记忆、子智能体。
- `src/seju_lite/tools`：内置工具、MCP 客户端/服务端、RAG MCP 服务。
- `src/seju_lite/channels`：Discord/Telegram/WhatsApp 适配层。
- `src/seju_lite/api`：FastAPI 服务（`/health`、`/chat`）。
- `src/seju_lite/runtime`：应用启动、worker、优雅关闭。

## 📦 项目结构

```text
seju-lite/                        # root
  assets/
  src/seju_lite/                  
    agent/                        # 智能体
    api/                          # 封装接口
    bus/                          # queue
    channels/                     # 操作平台
    cli/
    config/
    providers/
    runtime/
    session/
    tools/
    utils/
  tests/
  workspace/                      # 记忆+skills
    memory/
    sessions/
    skills/
  config.json
```

## ✅ 运行要求

- Python 3.11+
- `uv` 包管理器

## 🚀 快速开始

```bash
uv sync
uv run seju-lite config-validate --config config.json
uv run seju-lite chat --config config.json --session cli:local
```

启动常驻运行时：

```bash
uv run seju-lite start --config config.json
```

启动 API 服务：

```bash
uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000
```

## 🔐 环境变量

在 `.env` 中配置凭据（示例键）：

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

- `config.json` 中的 `provider.apiKey` 与各通道 token 支持 `${ENV_NAME}` 插值。
- 设置 `SEJU_API_KEY` 后，`/chat` 需要 Bearer Token，`/health` 保持公开。

## 🧰 CLI 命令

- `start`：启动 worker 与已启用通道。
- `chat`：本地终端聊天。
- `api`：启动 HTTP API。
- `config-validate`：校验配置文件。
- `tool-list`：列出已注册工具。
- `test-provider`：直连模型调试。
- `mcp-server`：将内置工具暴露为 MCP 服务。
- `rag-mcp-server`：启动基于 SQLite FTS 的 RAG MCP 服务。

聊天内置命令：

- `/help`
- `/new`（重置短期会话历史，保留长期记忆）
- `/stop`（停止当前子智能体任务）
- `/restart`

## ⚙️ 配置重点

主配置文件：`config.json`

关键字段：

- `agent`
  - `mode`：`single` 或 `multi`
  - `defaultAgent`
  - `enableLlmPlanner`、`plannerConfidenceThreshold`
  - `enableSubagent`、`subagentMaxIterations`
  - `maxIterations`、`maxHistory`
  - `workspace`、`enableMemory`、`enableSkills`、`enableTools`
- `provider`
  - `kind`：`gemini` / `openai_compatible` / `deepseek`
  - 模型、温度、输出 token 等参数
- `channels`
  - 目前支持 Telegram / Discord / WhatsApp 
  - soon：webui
- `tools`
  - 内置工具（`time`、`readFile`、`web`、`shell`）
  - `mcp.servers`（`stdio`、`sse`、`streamableHttp`）

### 路由层与 Agent Mode

`seju-lite` 采用两层路由链路：

1. `WorkflowOrchestrator` 先选择目标 agent。
2. `AgentOrchestrator` 再把请求派发到该 agent 执行。

`agent.mode` 的行为：

- `single`：始终使用 `defaultAgent`，不会走关键词路由，也不会启用 LLM planner 的改写。
- `multi`：先按 `agent.routing` 关键词路由，再由可选的 LLM planner（`enableLlmPlanner`）进行二次决策覆盖。

内置 agent 画像：

- `local`：本地/非网络工具为主。
- `web`：网络/外部工具为主（例如 `mcp_playwright_*`、网页抓取类工具）。
- `main`：通用兜底 agent。

实践说明：

- 如果 `agent.mode = "single"` 且 `defaultAgent = "local"`，即使提示词里有“google 搜索”，仍会停留在 `local`，不会触发 Playwright 等网络工具。

## 🔌 API

### ❤️ `GET /health`

```json
{
  "status": "ok",
  "app": "seju-lite",
  "model": "deepseek-chat"
}
```

### 💬 `POST /chat`

请求：

```json
{
  "message": "hello",
  "conversation_id": "web-room-1",
  "user_id": "alice",
  "metadata": {}
}
```

返回：

```json
{
  "reply": "Hi there!",
  "conversation_id": "web-room-1"
}
```

## 🧠 记忆模型

- 短期会话历史：`workspace/sessions.json`
- 长期整合记忆：`workspace/memory/MEMORY.md`
- 历史摘要：`workspace/memory/HISTORY.md`

工作方式：

- 上下文阶段加载最近会话 -> session.JSON
- Consolidator 周期抽取稳定事实。
- Context Builder 将记忆与技能注入提示词。

## 🔗 MCP 集成

在 `config.json` 的 `tools.mcp.servers` 中配置 MCP 服务。

仓库内已有示例：

- 本地工具 MCP 服务
- 本地 RAG MCP 服务
- Notion MCP 服务
- Playwright MCP 服务

远端 MCP 工具会被包装成本地函数工具：

- 命名格式：`mcp_<server_name>_<tool_name>`

## 🧪 开发

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

排查路由/工具问题时可关注日志：

- `seju_lite.agent.workflow`
- `seju_lite.agent.orchestrator`
- `seju_lite.agent`

## 📌 状态

> 当前新增LLM planner (决策层)
项目持续迭代中。路由、记忆、工具层均保持模块化，便于逐步演进。
