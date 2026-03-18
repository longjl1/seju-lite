class ToolRegistry:
    def __init__(self) -> None:
        self._tools = {}

    def register(self, tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def get_definitions(self) -> list[dict]:
        return [tool.definition for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict):
        tool = self._tools[name]
        return await tool.run(**arguments)