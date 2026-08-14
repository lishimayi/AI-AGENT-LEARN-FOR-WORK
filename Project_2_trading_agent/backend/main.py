import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from backend.schemas import OrderRequest, OrderResponse, HealthResponse
from backend.llm.router import llm_router
from backend.trading.executor import trading_executor

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("交易Agent服务启动")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"Exchange: {settings.EXCHANGE}")
    yield
    logger.info("交易Agent服务关闭")


app = FastAPI(
    title="交易Agent - 自然语言下单",
    description="使用LLM解析自然语言指令，执行加密货币交易",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """服务根路径"""
    return {"message": "交易Agent服务运行中", "version": "1.0.0"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="ok",
        llm_provider=settings.LLM_PROVIDER,
        exchange=settings.EXCHANGE
    )


@app.post("/api/parse", tags=["Order"])
async def parse_order_only(request: OrderRequest):
    """
    仅解析订单 - 不执行交易
    用于测试LLM解析效果
    """
    try:
        parsed = await llm_router.parse_order(request.natural_language)
        return {
            "success": True,
            "parsed_order": parsed.model_dump()
        }
    except Exception as e:
        logger.error(f"解析失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/order", response_model=OrderResponse, tags=["Order"])
async def place_order(request: OrderRequest):
    """
    自然语言下单
    
    完整流程：
    1. LLM解析自然语言 → 结构化订单
    2. 交易执行器执行订单
    3. 返回结果
    """
    try:
        logger.info(f"收到订单请求: {request.natural_language}")
        
        # Step 1: LLM解析
        parsed = await llm_router.parse_order(request.natural_language)
        logger.info(f"解析结果: action={parsed.action}, symbol={parsed.symbol}, amount={parsed.amount}")
        
        # Step 2: 执行交易
        result = await trading_executor.place_order(parsed)
        
        # Step 3: 返回结果
        return OrderResponse(
            success=result["success"],
            message=result["message"],
            order_id=result.get("order_id"),
            parsed_order=parsed
        )
        
    except Exception as e:
        logger.error(f"下单失败: {e}")
        return OrderResponse(
            success=False,
            message=f"下单失败: {str(e)}",
            order_id=None,
            parsed_order=None
        )


@app.get("/api/balance", tags=["Account"])
async def get_balance(asset: str = "USDT"):
    """查询账户余额"""
    try:
        balance = await trading_executor.get_balance(asset)
        return {
            "success": True,
            "asset": asset,
            "free": balance
        }
    except Exception as e:
        logger.error(f"查询余额失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/balances", tags=["Account"])
async def get_all_balances():
    """查询现货和合约账户余额"""
    try:
        balances = await trading_executor.get_all_balances()
        return {
            "success": True,
            "spot": balances["spot"],
            "futures": balances["futures"],
            "is_testnet": settings.BINANCE_TESTNET
        }
    except Exception as e:
        logger.error(f"查询余额失败: {e}")
        # 测试网可能没有权限，返回空余额
        return {
            "success": True,
            "spot": {},
            "futures": {},
            "is_testnet": settings.BINANCE_TESTNET,
            "warning": "测试网模式下无法获取余额，请确认API权限"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
