"""FastAPI + WebSocket 主服务"""
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from src.core.config import config
from src.schemas.api import (
    QueryRequest, QueryResponse,
    DocumentUploadResponse, HealthResponse, StatsResponse,
    StreamChunk, SessionInfo
)
from src.models.llm_factory import LLMFactory, ModelAdapter
from src.agents.langgraph_agent import EnterpriseRAGAgent, AgentConfig
from src.tools.agent_tools import get_all_tools
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.document_processor import DocumentProcessor


# ============================================================
# 全局状态管理
# ============================================================

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sessions: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """建立连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": datetime.now().timestamp(),
                "message_count": 0,
                "history": []
            }
        
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        """断开连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        """发送消息"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, message: dict):
        """更新会话"""
        if session_id in self.sessions:
            self.sessions[session_id]["message_count"] += 1
            self.sessions[session_id]["last_message_at"] = datetime.now().timestamp()
            self.sessions[session_id]["history"].append(message)


# 全局实例
manager = ConnectionManager()

# 全局组件
agent: Optional[EnterpriseRAGAgent] = None
retriever: Optional[HybridRetriever] = None
document_processor: Optional[DocumentProcessor] = None
llm_adapter: Optional[ModelAdapter] = None


# ============================================================
# 生命周期管理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    global agent, retriever, document_processor, llm_adapter
    
    logger.info("=" * 50)
    logger.info("企业级产品需求智能 Agent 启动中...")
    logger.info("=" * 50)
    
    # 初始化组件
    try:
        # 1. 初始化文档处理器
        document_processor = DocumentProcessor()
        logger.info("✓ 文档处理器初始化完成")
        
        # 2. 初始化检索引擎
        retriever = HybridRetriever.get_instance()
        logger.info("✓ 混合检索引擎初始化完成")
        
        # 3. 初始化 LLM
        llm_adapter = ModelAdapter()
        logger.info(f"✓ LLM 模型初始化完成 (Provider: {llm_adapter.provider})")
        
        # 4. 初始化 Agent
        tools = get_all_tools()
        agent_config = AgentConfig()
        agent = EnterpriseRAGAgent(
            tools=tools,
            llm=llm_adapter.model,
            config=agent_config
        )
        logger.info(f"✓ Agent 初始化完成 (Tools: {len(tools)})")
        
        logger.info("=" * 50)
        logger.info("所有组件初始化完成，服务已就绪")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise
    
    yield
    
    logger.info("服务关闭中...")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="企业级产品需求智能 Agent",
    description="基于 LangGraph + RAG + Tool Calling 的智能问答系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.get("cors", {}).get("allow_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 路由定义
# ============================================================

@app.get("/", tags=["首页"])
async def root():
    """根路径"""
    return {
        "name": "企业级产品需求智能 Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "websocket": "/ws/{session_id}"
    }


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查"""
    stats = retriever.get_stats() if retriever else {}
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        model_provider=llm_adapter.provider if llm_adapter else "unknown",
        indexed_documents=stats.get("total_documents", 0),
        embedding_model=stats.get("embedding_model", "unknown")
    )


@app.get("/stats", response_model=StatsResponse, tags=["系统"])
async def get_stats():
    """获取系统统计"""
    if not retriever:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    stats = retriever.get_stats()
    
    return StatsResponse(
        total_chunks=stats.get("total_documents", 0),
        embedding_model=stats.get("embedding_model", "unknown"),
        vector_dimension=stats.get("dimension", 384),
        hybrid_weights={
            "vector": stats.get("vector_weight", 0.7),
            "keyword": stats.get("keyword_weight", 0.3)
        }
    )


@app.post("/query", response_model=QueryResponse, tags=["Agent"])
async def query(request: QueryRequest):
    """非流式查询接口"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    result = await agent.run(request.question, thread_id=session_id)
    
    return QueryResponse(
        answer=result.get("answer", ""),
        session_id=session_id,
        intent=result.get("intent"),
        sources=result.get("sources", []),
        tokens_used=None
    )


@app.post("/upload", response_model=DocumentUploadResponse, tags=["文档"])
async def upload_document(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Query(default=None, description="文档类型")
):
    """上传并索引文档"""
    global retriever
    
    if not document_processor or not retriever:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    # 检查文件格式
    allowed_extensions = config.document.get("supported_formats", [".pdf", ".docx", ".txt", ".md"])
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式。支持: {', '.join(allowed_extensions)}"
        )
    
    # 保存文件
    upload_folder = config.document.get("upload_folder", "./data/uploads")
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, f"{uuid.uuid4()}_{file.filename}")
    
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        file_size = len(content)
        
        # 处理文档
        chunks = document_processor.process_file(file_path)
        chunk_dicts = document_processor.chunks_to_dict(chunks)
        
        # 更新 doc_type
        if doc_type:
            for chunk in chunk_dicts:
                chunk["metadata"]["doc_type"] = doc_type
        
        # 索引文档
        retriever.index_documents(chunk_dicts)
        
        logger.info(f"文档已索引: {file.filename}, chunks: {len(chunks)}")
        
        return DocumentUploadResponse(
            filename=file.filename,
            file_size=file_size,
            chunks_created=len(chunks),
            doc_type=doc_type or "general",
            message="文档上传并索引成功"
        )
        
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")
    
    finally:
        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/sessions/{session_id}", response_model=SessionInfo, tags=["会话"])
async def get_session(session_id: str):
    """获取会话信息"""
    session = manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return SessionInfo(
        session_id=session_id,
        created_at=session["created_at"],
        message_count=session["message_count"],
        last_message_at=session.get("last_message_at")
    )


@app.delete("/sessions/{session_id}", tags=["会话"])
async def delete_session(session_id: str):
    """删除会话"""
    if session_id in manager.sessions:
        del manager.sessions[session_id]
        return {"message": "会话已删除"}
    
    raise HTTPException(status_code=404, detail="会话不存在")


# ============================================================
# WebSocket 端点
# ============================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 流式对话"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
                question = payload.get("question", "")
                stream = payload.get("stream", True)
            except json.JSONDecodeError:
                question = data
                stream = True
            
            if not question:
                continue
            
            logger.info(f"Received question: {question[:50]}...")
            
            # 更新会话
            manager.update_session(session_id, {
                "role": "user",
                "content": question,
                "timestamp": datetime.now().timestamp()
            })
            
            # 流式处理
            if stream and agent:
                # 发送开始信号
                await manager.send_message(session_id, {
                    "type": "start",
                    "session_id": session_id
                })
                
                # 流式运行 Agent
                accumulated = ""
                async for event in agent.run_stream(question, thread_id=session_id):
                    # 提取内容
                    for node, state in event.items():
                        if isinstance(state, dict) and "final_answer" in state:
                            content = state["final_answer"]
                        elif isinstance(state, dict) and state.get("messages"):
                            messages = state["messages"]
                            if messages and hasattr(messages[-1], "content"):
                                content = messages[-1].content
                            else:
                                continue
                        else:
                            continue
                        
                        # 发送增量内容
                        delta = content[len(accumulated):]
                        if delta:
                            accumulated = content
                            await manager.send_message(session_id, {
                                "type": "content",
                                "content": delta
                            })
                
                # 发送完成信号
                await manager.send_message(session_id, {
                    "type": "complete",
                    "full_content": accumulated,
                    "session_id": session_id
                })
                
            else:
                # 非流式处理
                result = await agent.run(question, thread_id=session_id)
                await manager.send_message(session_id, {
                    "type": "complete",
                    "content": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "intent": result.get("intent"),
                    "session_id": session_id
                })
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.send_message(session_id, {
            "type": "error",
            "content": str(e)
        })
        manager.disconnect(session_id)


@app.websocket("/ws-stream/{session_id}")
async def websocket_stream(websocket: WebSocket, session_id: str):
    """简化的流式对话 WebSocket"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
                question = payload.get("question", "")
            except json.JSONDecodeError:
                question = data
            
            if not question:
                continue
            
            # 使用 LLM 直接流式生成
            if llm_adapter:
                system_prompt = config.agent.get("system_prompt", "")
                
                # 先检索相关文档
                if retriever:
                    docs = await retriever.search(question, top_k=3)
                    context = "\n\n".join([d.get("content", "") for d in docs])
                    prompt = f"基于以下知识回答问题：\n\n{context}\n\n问题：{question}"
                else:
                    prompt = question
                
                # 流式生成
                await manager.send_message(session_id, {"type": "start"})
                
                full_response = ""
                async for chunk in llm_adapter.chat_stream(prompt, system=system_prompt):
                    full_response += chunk
                    await manager.send_message(session_id, {
                        "type": "content",
                        "content": chunk
                    })
                
                await manager.send_message(session_id, {
                    "type": "complete",
                    "content": full_response
                })
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"Stream error: {e}")
        await manager.send_message(session_id, {"type": "error", "content": str(e)})


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    api_config = config.api
    uvicorn.run(
        "src.api.main:app",
        host=api_config.get("host", "0.0.0.0"),
        port=api_config.get("port", 8000),
        reload=api_config.get("debug", False),
        workers=api_config.get("workers", 1)
    )
