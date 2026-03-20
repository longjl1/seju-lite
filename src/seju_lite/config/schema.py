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
    kind: Literal["gemini", "openai_compatible"] = "gemini"
    apiKey: str
    model: str = "gemini-2.5-flash"
    temperature: float = 0.3
    maxOutputTokens: int = 1200


class TelegramConfig(BaseModel):
    enabled: bool = True
    token: str
    allowFrom: list[str] = Field(default_factory=list)
    allowGroups: bool = False
    groupPolicy: Literal["mention", "open"] = "mention"


class ChannelsConfig(BaseModel):
    telegram: TelegramConfig


class TimeToolConfig(BaseModel):
    enabled: bool = True


class ReadFileToolConfig(BaseModel):
    enabled: bool = True
    rootDir: Path = Path("./workspace")


class ShellToolConfig(BaseModel):
    enabled: bool = False
    allowedCommands: list[str] = Field(default_factory=list)
    timeoutSec: int = 8


class ToolsConfig(BaseModel): #把多个工具的配置组合到一�?
    time: TimeToolConfig = TimeToolConfig()
    readFile: ReadFileToolConfig = ReadFileToolConfig()
    shell: ShellToolConfig = ShellToolConfig()


class StorageConfig(BaseModel):
    sessionFile: Path = Path("./workspace/sessions.json")


class RootConfig(BaseModel):
    app: AppConfig
    agent: AgentConfig
    provider: ProviderConfig
    channels: ChannelsConfig
    tools: ToolsConfig = ToolsConfig()
    storage: StorageConfig = StorageConfig()
