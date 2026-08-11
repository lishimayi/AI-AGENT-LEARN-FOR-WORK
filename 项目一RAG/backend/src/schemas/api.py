"""API 数据模型"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[float] = Field(default=None, description="时间戳")


class QueryRequest(BaseModel):
    """查询请求"""
    question: str = Field(..., description="用户问题", min_length=1)
    session_id: Optional[str] = Field(default=None, description="会话ID")
    stream: bool = Field(default=True, description="是否流式输出")


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str = Field(..., description="生成的回答")
    session_id: str = Field(..., description="会话ID")
    intent: Optional[str] = Field(default=None, description="识别的意图")
    sources: List[Dict[str, Any]] = Field(default=[], description="来源文档")
    tokens_used: Optional[int] = Field(default=None, description="使用的token数量")


class StreamChunk(BaseModel):
    """流式输出块"""
    type: str = Field(..., description="类型: content/error/complete")
    content: str = Field(default="", description="内容")
    sources: Optional[List[Dict]] = Field(default=None, description="来源")


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""
    doc_type: Optional[str] = Field(default=None, description="文档类型")
    category: Optional[str] = Field(default=None, description="分类")


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小")
    chunks_created: int = Field(..., description="创建的块数量")
    doc_type: str = Field(..., description="文档类型")
    message: str = Field(..., description="处理信息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="API版本")
    model_provider: str = Field(..., description="当前模型提供商")
    indexed_documents: int = Field(..., description="索引文档数")
    embedding_model: str = Field(..., description="Embedding模型")


class StatsResponse(BaseModel):
    """统计信息"""
    total_chunks: int = Field(..., description="总块数")
    embedding_model: str = Field(..., description="Embedding模型")
    vector_dimension: int = Field(..., description="向量维度")
    hybrid_weights: Dict[str, float] = Field(..., description="混合检索权重")


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str = Field(..., description="会话ID")
    created_at: float = Field(..., description="创建时间")
    message_count: int = Field(..., description="消息数量")
    last_message_at: Optional[float] = Field(default=None, description="最后消息时间")


class ToolCall(BaseModel):
    """工具调用记录"""
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(..., description="调用参数")
    result: Optional[Dict[str, Any]] = Field(default=None, description="调用结果")
    success: bool = Field(..., description="是否成功")
    duration_ms: Optional[int] = Field(default=None, description="执行耗时")
