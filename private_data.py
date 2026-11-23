"""Private modes for application-owned state, never the source image library."""
import os
from pathlib import Path

def secure_data(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    for name in ('app.sqlite', 'app.sqlite-wal', 'app.sqlite-shm', '.env', 'communications-profiles.toml'):
        file = directory / name
        if file.is_file() and not file.is_symlink():
            try:
                file.chmod(0o600)
            except FileNotFoundError:
                pass

def initialize(directory):
    os.umask(0o077)
    secure_data(directory)
