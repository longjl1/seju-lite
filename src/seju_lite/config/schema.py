from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "seju-lite"
    env: str = "dev"
    logLevel: str = "INFO"


class AgentConfig(BaseModel):
    name: str = "SejuLite"
    systemPrompt: str
    maxIterations: int = 8
    maxHistory: int = 12
    workspace: Path = Path("./workspace")
    enableMemory: bool = True
    enableSkills: bool = True
    enableTools: bool = True


class ProviderConfig(BaseModel):
    kind: Literal["gemini", "openai_compatible", "deepseek", "litellm_deepseek"] = "gemini"
    apiKey: str
    apiBase: str | None = None
    model: str = "gemini-2.5-flash"
    temperature: float = 0.3
    maxOutputTokens: int = 1200


class TelegramConfig(BaseModel):
    enabled: bool = True
    token: str
    allowFrom: list[str] = Field(default_factory=list)
    allowGroups: bool = False
    groupPolicy: Literal["mention", "open"] = "mention"


class WhatsAppConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    phoneNumberId: str = ""
    apiBase: str = "https://graph.facebook.com/v22.0"
    allowFrom: list[str] = Field(default_factory=list)


class DiscordConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    allowFrom: list[str] = Field(default_factory=list)
    groupPolicy: Literal["mention", "open"] = "mention"


class ChannelsConfig(BaseModel):
    telegram: TelegramConfig
    whatsapp: WhatsAppConfig = WhatsAppConfig()
    discord: DiscordConfig = DiscordConfig()


class TimeToolConfig(BaseModel):
    enabled: bool = True


class ReadFileToolConfig(BaseModel):
    enabled: bool = True
    rootDir: Path = Path("./workspace")


class ShellToolConfig(BaseModel):
    enabled: bool = False
    allowedCommands: list[str] = Field(default_factory=list)
    timeoutSec: int = 8


class WebToolConfig(BaseModel):
    enabled: bool = True
    maxChars: int = 12000


class MCPServerToolConfig(BaseModel):
    type: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    enabledTools: list[str] = Field(default_factory=lambda: ["*"])
    toolTimeout: int = 30


class MCPToolConfig(BaseModel):
    enabled: bool = False
    servers: dict[str, MCPServerToolConfig] = Field(default_factory=dict)


class ToolsConfig(BaseModel):
    time: TimeToolConfig = TimeToolConfig()
    readFile: ReadFileToolConfig = ReadFileToolConfig()
    shell: ShellToolConfig = ShellToolConfig()
    web: WebToolConfig = WebToolConfig()
    mcp: MCPToolConfig = MCPToolConfig()


class StorageConfig(BaseModel):
    sessionFile: Path = Path("./workspace/sessions.json")


class RootConfig(BaseModel):
    app: AppConfig
    agent: AgentConfig
    provider: ProviderConfig
    channels: ChannelsConfig
    tools: ToolsConfig = ToolsConfig()
    storage: StorageConfig = StorageConfig()
