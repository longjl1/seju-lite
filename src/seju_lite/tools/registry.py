class ToolRegistry:
    def __init__(self) -> None:
        self._tools = {}

    def register(self, tool) -> None:
        self._tools[tool.name] = tool # self._tools["time"] = TimeTool()

    def get(self, name: str):
        return self._tools.get(name)

    ''' function calling？ tools schema '''
    def get_definitions(self) -> list[dict]:
        return [tool.definition for tool in self._tools.values()]

    # {"name": "read_file", "arguments": {"path": "memory/MEMORY.md"}}
    # await ReadFileTool.run(path="memory/MEMORY.md")
    async def execute(self, name: str, arguments: dict):
        tool = self._tools[name]
        return await tool.run(**arguments) 