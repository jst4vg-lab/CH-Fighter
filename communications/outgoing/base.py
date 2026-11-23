"""Contract for authorized outgoing delivery."""
from pathlib import Path
from typing import Protocol

class OutgoingProvider(Protocol):
    def status(self) -> dict: ...
    def send(self, draft_id: str, text: str, paths: list[Path], reply_to_id: str = "") -> dict: ...
