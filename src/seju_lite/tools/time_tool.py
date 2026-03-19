from datetime import datetime

class TimeTool:
    # tool's name
    name = "time"

    # schema
    definition = {
        "type": "function",
        "function": {
            "name": "time",
            "description": "Get current local time",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }

    async def run(self) -> str:
        return datetime.now().isoformat() # return datetime string