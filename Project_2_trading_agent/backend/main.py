import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from backend.schemas import (
    AgentRequest,
    AgentResponse,
    ConfirmRequest,
    HealthResponse,
    AccountTypeResponse,
    AccountTypeZh,
)
from backend.agent.agent import trading_agent
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


# ==================== Agent 端点 ====================

@app.get("/api/agent/account-type", response_model=AccountTypeResponse, tags=["Agent"])
async def get_account_type():
    """
    获取当前账户类型（现货/合约）。

    前端初始化时调用，决定顶部「现货/合约」开关的默认状态。
    不会覆盖当前 agent 状态。
    """
    return AccountTypeResponse(
        account_type=trading_agent.account_type,
        account_type_zh=AccountTypeZh[trading_agent.account_type],
        supported_types=["spot", "futures"],
    )


class SwitchAccountTypeRequest:
    """内部占位，避免污染 schema。"""
    pass


@app.post("/api/agent/account-type", tags=["Agent"])
async def switch_account_type(payload: dict):
    """
    切换账户类型（现货 ↔ 合约）。

    前端顶部开关会调用这个端点，后端会更新 trading_agent._account_type，
    后续的 /api/agent/chat 和 /api/agent/confirm 都会按新类型走。
    """
    new_type = payload.get("account_type")
    if new_type not in ("spot", "futures"):
        raise HTTPException(status_code=400, detail=f"不支持的账户类型: {new_type}")

    trading_agent.set_account_type(new_type)
    logger.info(f"账户类型切换为: {new_type}")
    return {
        "success": True,
        "account_type": new_type,
        "account_type_zh": AccountTypeZh[new_type],
    }


@app.post("/api/agent/chat", response_model=AgentResponse, tags=["Agent"])
async def agent_chat(request: AgentRequest):
    """
    Agent 对话接口
    接收用户消息，返回 Agent 的最终回复

    当用户意图是下单但参数缺失时：
    - needs_input=True
    - missing_fields: 缺失字段列表
    - parsed_intent: 已识别出的下单意图

    account_type 字段会传给 Agent，本条消息的「现货/合约」标签由这个字段决定。
    """
    try:
        logger.info(
            f"收到 Agent 消息: {request.message} "
        )
        result = await trading_agent.run(
            request.message,
            filled_fields=request.filled_fields,
            account_type=request.account_type,
        )
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            session_id=request.session_id,
            account_type=result.get("account_type", "spot"),
            account_type_zh=result.get("account_type_zh", "现货"),
            needs_input=result.get("needs_input", False),
            missing_fields=result.get("missing_fields", []),
            parsed_intent=result.get("parsed_intent"),
            intermediate_steps=result.get("intermediate_steps", []),
            error_code=result.get("error_code", 0),
            requires_confirmation=result.get("requires_confirmation", False),
            preview_id=result.get("preview_id"),
            order_preview=result.get("order_preview"),
        )
    except Exception as e:
        logger.error(f"Agent 执行错误: {e}")
        return AgentResponse(
            success=False,
            message=f"Agent 执行失败: {str(e)}",
            session_id=request.session_id,
            account_type=trading_agent.account_type,
            account_type_zh=AccountTypeZh[trading_agent.account_type],
            needs_input=False,
            missing_fields=[],
            parsed_intent=None,
            intermediate_steps=[],
            error_code=0,
        )


@app.post("/api/agent/reset", tags=["Agent"])
async def agent_reset():
    """重置 Agent 对话历史"""
    trading_agent.reset_history()
    return {"success": True, "message": "对话历史已重置"}


@app.post("/api/agent/confirm", response_model=AgentResponse, tags=["Agent"])
async def agent_confirm(request: ConfirmRequest):
    """
    用户点击预览订单的「确认下单」按钮后调用。
    跳过 LLM，直接用 preview 时缓存的 parsed_intent 下单。
    """
    try:
        logger.info(
            f"确认下单: preview_id={request.preview_id} "
            f"intent={request.parsed_intent} "
            f"account_type={request.account_type or '沿用'}"
        )
        result = await trading_agent.confirm_order(
            preview_id=request.preview_id,
            parsed_intent=request.parsed_intent,
            original_message=request.message,
            account_type=request.account_type,
        )
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            session_id=request.session_id,
            account_type=result.get("account_type", "spot"),
            account_type_zh=result.get("account_type_zh", "现货"),
            needs_input=result.get("needs_input", False),
            missing_fields=result.get("missing_fields", []),
            parsed_intent=result.get("parsed_intent"),
            intermediate_steps=result.get("intermediate_steps", []),
            error_code=result.get("error_code", 0),
        )
    except Exception as e:
        logger.error(f"确认下单失败: {e}")
        return AgentResponse(
            success=False,
            message=f"确认下单失败: {str(e)}",
            session_id=request.session_id,
            account_type=trading_agent.account_type,
            account_type_zh=AccountTypeZh[trading_agent.account_type],
            needs_input=False,
            missing_fields=[],
            parsed_intent=request.parsed_intent,
            intermediate_steps=[],
            error_code=0,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )