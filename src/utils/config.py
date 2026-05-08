# Generated from design/config.md v1.2
import os
import platform
from typing import Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Find project root (the directory containing .env)
# We look for .env starting from this file's parent's parent
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent

env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

def get_env(key: str, default: Any = None) -> Any:
    system = platform.system().upper()
    platform_key = f"{system}_{key}"
    
    val = os.getenv(platform_key)
    if val is not None: return val
        
    return os.getenv(key, default)
