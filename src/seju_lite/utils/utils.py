""" useful tools """

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any





def get_timestamp() -> str:
    return datetime.now().isoformat()

def get_current_datetime() -> str:
    """ e.g. '2026-03-15 22:30 ."""
    current = datetime.now().strftime("%Y-%m-%d %H:%M ")
    return f"{current}"
