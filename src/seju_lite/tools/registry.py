class ToolRegistry:
    def __init__(self, permission_manager=None) -> None:
        self._tools = {}
        self._permission_manager = permission_manager

    def set_permission_manager(self, permission_manager) -> None:
        self._permission_manager = permission_manager

    def register(self, tool) -> None:
        self._tools[tool.name] = tool # self._tools["time"] = TimeTool()

    def get(self, name: str):
        return self._tools.get(name)

    def iter_tools(self):
        return self._tools.values()

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
        if self._permission_manager is not None:
            decision = self._permission_manager.check(name, arguments) # PermissionDecision(behavior="...", reason="...")
            if decision.behavior == "deny":
                return f"Permission denied for tool '{name}': {decision.reason}"
        try:
            return await tool.run(**arguments) 
        except Exception as e:
            return f"Tool '{name}' execution failed: {str(e)} "
