from datetime import datetime

class TimeTool:
    
    name = "time"
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
        return datetime.now().isoformat()