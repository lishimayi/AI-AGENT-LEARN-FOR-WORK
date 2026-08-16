import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from backend.schemas import AgentRequest, AgentResponse, HealthResponse
from backend.agent.agent import trading_agent

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


# ==================== Agent 端点 ====================

@app.post("/api/agent/chat", response_model=AgentResponse, tags=["Agent"])
async def agent_chat(request: AgentRequest):
    """
    Agent 对话接口
    接收用户消息，返回 Agent 的最终回复

    当用户意图是下单但参数缺失时：
    - needs_input=True
    - missing_fields: 缺失字段列表
    - parsed_intent: 已识别出的下单意图
    """
    try:
        logger.info(f"收到 Agent 消息: {request.message}")
        result = await trading_agent.run(
            request.message,
            filled_fields=request.filled_fields,
        )
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            session_id=request.session_id,
            needs_input=result.get("needs_input", False),
            missing_fields=result.get("missing_fields", []),
            parsed_intent=result.get("parsed_intent"),
        )
    except Exception as e:
        logger.error(f"Agent 执行错误: {e}")
        return AgentResponse(
            success=False,
            message=f"Agent 执行失败: {str(e)}",
            session_id=request.session_id,
            needs_input=False,
            missing_fields=[],
            parsed_intent=None,
        )


@app.post("/api/agent/reset", tags=["Agent"])
async def agent_reset():
    """重置 Agent 对话历史"""
    trading_agent.reset_history()
    return {"success": True, "message": "对话历史已重置"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
