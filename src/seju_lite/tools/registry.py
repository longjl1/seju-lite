class ToolRegistry:
    def __init__(self) -> None:
        self._tools = {}

    def register(self, tool) -> None:
        self._tools[tool.name] = tool # self._tools["time"] = TimeTool()

    def get(self, name: str):
        return self._tools.get(name)

    ''' function calling？ 
    
    eg.
    [
        {
            "type": "function",
            "function": {
            "name": "time",
            "description": "...",
            "parameters": ...
            }
        }
    ]
    
    tools schema '''
    def get_definitions(self) -> list[dict]:
        return [tool.definition for tool in self._tools.values()]

    # {"name": "read_file", "arguments": {"path": "memory/MEMORY.md"}}
    # await ReadFileTool.run(path="memory/MEMORY.md")
    async def execute(self, name: str, arguments: dict):
        
        tool = self._tools.get(name)

        # if tools are not definded
        if not tool:
            return f"Tool '{name}' does not exist!"
        try:
            return await tool.run(**arguments) 
        except Exception as e:
            return f"Tool '{name}' execution failed: {str(e)} "