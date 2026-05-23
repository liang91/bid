"""配置加载模块.

只支持从 YAML 配置文件读取配置，不支持环境变量覆盖和命令行参数覆盖.
"""
from loguru import logger

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class Config:
    """配置对象，支持点号访问和字典访问."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        """通过点号路径获取配置值，如 'mysql.host'."""
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def to_dict(self) -> Dict[str, Any]:
        """返回原始字典."""
        return self._data

    def section(self, name: str) -> "Config":
        """返回指定子配置段."""
        data = self.get(name, {})
        return Config(data if isinstance(data, dict) else {})


def load_config(path: Optional[Path] = None) -> Config:
    """加载 YAML 配置文件.

    Args:
        path: 配置文件路径，默认使用项目根目录的 config.yaml

    Returns:
        Config 配置对象

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 解析失败
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("配置文件顶层必须是字典结构")

    return Config(data)


# 配置数据
config: Config | None = None

try:
    config = load_config()
    logger.info("[配置] 已加载配置文件")
except FileNotFoundError as e:
    logger.warning(f"[配置] 警告: {e}")
