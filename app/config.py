"""
配置加载模块
从 config.json 文件加载系统配置
"""
import json
from pathlib import Path
from typing import Dict, Any


class Config:
    """配置管理类"""

    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self.load_config()

    def load_config(self, config_path: str = None):
        if config_path is None:
            root_dir = Path(__file__).parent.parent
            config_path = root_dir / "config.json"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = json.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    @property
    def database(self) -> Dict[str, Any]:
        return self._config.get('database', {})

    @property
    def redis(self) -> Dict[str, Any]:
        return self._config.get('redis', {})

    @property
    def jwt(self) -> Dict[str, Any]:
        return self._config.get('jwt', {})

    @property
    def app(self) -> Dict[str, Any]:
        return self._config.get('app', {})



config = Config()
