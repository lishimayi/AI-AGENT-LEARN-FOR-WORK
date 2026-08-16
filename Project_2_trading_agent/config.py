from pydantic_settings import BaseSettings
from typing import Literal
from dotenv import load_dotenv

load_dotenv()  # 从 .env 文件加载环境变量


class Settings(BaseSettings):
    """全局配置"""

    # ==================== LLM 配置 ====================
    # 支持的 LLM 类型: openai, anthropic, ollama
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"

    # LangSmith 追踪
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "trading_agent"

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
    BINANCE_TESTNET: bool = False  # True=测试网, False=真实交易

    # OKX 配置
    OKX_API_KEY: str = ""
    OKX_SECRET_KEY: str = ""
    OKX_PASSPHRASE: str = ""
    OKX_TESTNET: bool = True

    # ==================== 生产网络安全护栏 ====================
    # 任意一个不满足时，/api/order 会被拦截，返回 422。
    # 仅在 BINANCE_TESTNET=false 时生效（测试网不做限制）。
    PRODUCTION_CONFIRM_TOKEN: str = ""              # 调用方必须传入 X-Confirm-Token 与此值一致
    PRODUCTION_ALLOWED_SYMBOLS: str = "BTCUSDT,ETHUSDT"  # 允许的现货交易对白名单
    PRODUCTION_MAX_QUOTE_USDT: float = 50.0         # 单笔 quote 金额（USDT）上限
    PRODUCTION_MAX_BASE_QTY: float = 0.01           # 单笔 base 数量上限（适用于 BTC 等高价币）
    DRY_RUN: bool = False                           # True=不真正下单，仅返回"模拟成交"结果

    # ==================== 交易参数 ====================
    DEFAULT_SYMBOL: str = "BTCUSDT"  # 默认交易对
    DEFAULT_ORDER_TYPE: str = "market"  # 默认订单类型: market=市价, limit=限价

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
