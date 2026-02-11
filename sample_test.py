# test_sample.py
import json
import os
from pathlib import Path

def load_config(config_path: str) -> dict:
    """Загружает конфигурацию из JSON-файла."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(data: dict, cache_dir: str = "/tmp/cache") -> None:
    os.makedirs(cache_dir, exist_ok=True)
    path = Path(cache_dir) / "cache.json"
    with open(path, "w") as f:
        json.dump(data, f)

class ConfigManager:
    def __init__(self, path: str):
        self.path = path
        self.data = load_config(path)

    def get(self, key: str, default=None):
        return self.data.get(key, default)