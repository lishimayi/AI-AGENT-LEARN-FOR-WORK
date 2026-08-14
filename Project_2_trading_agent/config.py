from pydantic_settings import BaseSettings
from typing import Literal
from dotenv import load_dotenv

load_dotenv()  # 从 .env 文件加载环境变量


class Settings(BaseSettings):
    """全局配置"""

    # ==================== LLM 配置 ====================
    # 支持的 LLM 类型: openai, anthropic, ollama
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
    
    # OpenAI / 智谱AI 兼容配置
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"  # 智谱AI: https://open.bigmodel.cn/api/paas/v4
    
    # Anthropic 配置
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # Ollama 本地配置
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # ==================== 交易所配置 ====================
    # 支持的交易所: binance, okx
    EXCHANGE: Literal["binance", "okx"] = "binance"
    
    # Binance 配置
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET_KEY: str = ""
    BINANCE_TESTNET: bool = True  # True=测试网, False=真实交易
    
    # OKX 配置
    OKX_API_KEY: str = ""
    OKX_SECRET_KEY: str = ""
    OKX_PASSPHRASE: str = ""
    OKX_TESTNET: bool = True

    # ==================== 交易参数 ====================
    DEFAULT_SYMBOL: str = "BTCUSDT"  # 默认交易对
    DEFAULT_ORDER_TYPE: str = "market"  # 默认订单类型: market=市价, limit=限价

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
