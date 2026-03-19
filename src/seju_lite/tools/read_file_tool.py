from pathlib import Path


class ReadFileTool:

    # name
    name = "read_file"

    def __init__(self, root_dir: Path):

        # convert to abs path
        self.root_dir = root_dir.resolve() 
        self.definition = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file from workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    
                    "required": ["path"]
                }
            }
        }

    async def run(self, path: str) -> str:
        target = (self.root_dir / path).resolve()
        if self.root_dir not in target.parents and target != self.root_dir:
            return "Access denied."
        if not target.exists():
            return "File not found."
        
        # 8000 tokens
        return target.read_text(encoding="utf-8")[:8000]