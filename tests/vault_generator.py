# Generated utility for Phase 35 Vault Integration Testing
import os
import hashlib
from pathlib import Path

class VaultGenerator:
    """
    Programmatically generates a mock Obsidian vault with manipulated metadata.
    Designed to test the 'mtime + hash' change detection matrix.
    """
    
    @staticmethod
    def get_file_hash(path: str) -> str:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    @staticmethod
    def create_note(vault_path: str, rel_path: str, content: str, mtime: float = None) -> str:
        full_path = Path(vault_path) / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        if mtime is not None:
            # Manipulate modification time
            os.utime(full_path, (mtime, mtime))
            
        return str(full_path.absolute())

    @staticmethod
    def touch_file(path: str, new_mtime: float):
        """Changes mtime WITHOUT changing content."""
        os.utime(path, (new_mtime, new_mtime))

    @classmethod
    def setup_hardened_mock(cls, vault_path: str):
        """Creates the initial TC_ZERO state."""
        # 1. Flat file
        cls.create_note(vault_path, "root_note.md", "# Root Note\nThis is in the root.")
        
        # 2. Nested file
        cls.create_note(vault_path, "Projects/ClawBrain/spec.md", 
                        "# ClawBrain Spec\nInternal architecture details here.")
        
        # 3. Large file for chunking
        large_content = "# Big Data\n" + "This is a recurring line. " * 1000
        cls.create_note(vault_path, "Deep/Large.md", large_content)
        
        # 4. Technical identifiers
        cls.create_note(vault_path, "Network/Configs.md", 
                        "# Configs\nDatabase IP: 10.0.0.5\nGateway: 192.168.1.1")
