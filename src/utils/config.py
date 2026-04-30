# Generated from design/config.md v1.1
import os
import platform
from typing import Any, Optional

def get_env(key: str, default: Any = None) -> Any:
    """
    Fetch environment variable with platform-specific fallback.
    Priority:
    1. [PLATFORM]_[KEY] (e.g. LINUX_CLAWBRAIN_DB_DIR)
    2. [KEY] (e.g. CLAWBRAIN_DB_DIR)
    3. default
    """
    system = platform.system().upper()
    # Handle Darwin -> MACOS if preferred, but DARWIN is standard for platform.system()
    # We will use the raw platform.system() uppered.
    platform_key = f"{system}_{key}"
    
    val = os.getenv(platform_key)
    if val is not None:
        return val
        
    return os.getenv(key, default)
