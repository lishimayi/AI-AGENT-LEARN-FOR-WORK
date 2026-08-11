"""配置管理模块"""
import os
from typing import Dict, Any, Optional
from pathlib import Path
from functools import lru_cache

import yaml
from dotenv import load_dotenv
from loguru import logger


class ConfigManager:
    """配置管理器 (单例模式)"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._config:
            self.load()
    
    def load(self, config_path: Optional[str] = None) -> None:
        """加载配置文件"""
        load_dotenv()
        
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        
        if not os.path.exists(config_path):
            logger.warning(f"配置文件未找到: {config_path}，使用默认配置")
            self._set_defaults()
            return
        
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)
        
        self._substitute_env_vars()
        logger.info(f"配置加载成功: {config_path}")
    
    def _set_defaults(self) -> None:
        """设置默认配置"""
        self._config = {
            "llm": {
                "provider": "openai",
                "openai": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.3,
                    "max_tokens": 4096
                }
            },
            "embedding": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "device": "cpu"
            },
            "vector_db": {
                "type": "chroma",
                "chroma": {
                    "persist_directory": "./data/chroma",
                    "collection_name": "enterprise_knowledge"
                }
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False
            }
        }
    
    def _substitute_env_vars(self) -> None:
        """替换环境变量 ${VAR_NAME}"""
        def substitute(obj):
            if isinstance(obj, dict):
                return {k: substitute(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            return obj
        
        self._config = substitute(self._config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项 (支持点号分隔的路径)"""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    @property
    def llm(self) -> Dict[str, Any]:
        return self._config.get("llm", {})
    
    @property
    def embedding(self) -> Dict[str, Any]:
        return self._config.get("embedding", {})
    
    @property
    def vector_db(self) -> Dict[str, Any]:
        return self._config.get("vector_db", {})
    
    @property
    def database(self) -> Dict[str, Any]:
        return self._config.get("database", {})
    
    @property
    def redis(self) -> Dict[str, Any]:
        return self._config.get("redis", {})
    
    @property
    def document(self) -> Dict[str, Any]:
        return self._config.get("document", {})
    
    @property
    def retrieval(self) -> Dict[str, Any]:
        return self._config.get("retrieval", {})
    
    @property
    def agent(self) -> Dict[str, Any]:
        return self._config.get("agent", {})
    
    @property
    def api(self) -> Dict[str, Any]:
        return self._config.get("api", {})


@lru_cache()
def get_config() -> ConfigManager:
    """获取配置实例 (带缓存)"""
    return ConfigManager()


config = get_config()
