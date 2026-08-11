"""LangChain Tools - 使用 Pydantic Schema 约束入参"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain.tools import tool
from loguru import logger

from src.retrieval.hybrid_retriever import HybridRetriever


class DocumentSearchInput(BaseModel):
    """文档检索输入"""
    query: str = Field(description="搜索查询关键词", min_length=1, max_length=500)
    doc_type: Optional[str] = Field(default=None, description="文档类型: prd/接口文档/业务流程/技术文档")
    top_k: int = Field(default=5, description="返回结果数量", ge=1, le=20)


class RequirementQueryInput(BaseModel):
    """需求查询输入"""
    requirement_id: Optional[str] = Field(default=None, description="需求ID")
    keyword: Optional[str] = Field(default=None, description="需求关键词")
    module: Optional[str] = Field(default=None, description="所属模块")
    status: Optional[str] = Field(default=None, description="需求状态")


class InterfaceQueryInput(BaseModel):
    """接口查询输入"""
    interface_id: Optional[str] = Field(default=None, description="接口ID")
    interface_name: Optional[str] = Field(default=None, description="接口名称关键词")
    module: Optional[str] = Field(default=None, description="所属模块")
    method: Optional[str] = Field(default=None, description="HTTP方法: GET/POST/PUT/DELETE")


class ModuleQueryInput(BaseModel):
    """模块查询输入"""
    module_id: Optional[str] = Field(default=None, description="模块ID")
    module_name: Optional[str] = Field(default=None, description="模块名称关键词")
    layer: Optional[str] = Field(default=None, description="层级: 前端/后端/移动端")


class VersionQueryInput(BaseModel):
    """版本查询输入"""
    version_id: Optional[str] = Field(default=None, description="版本号")
    version_name: Optional[str] = Field(default=None, description="版本名称")
    status: Optional[str] = Field(default=None, description="版本状态: 开发中/测试中/已上线")


class ImpactAnalysisInput(BaseModel):
    """影响分析输入"""
    change_content: str = Field(description="变更内容描述", min_length=1)
    change_type: str = Field(description="变更类型: 接口变更/字段变更/新增功能")


@tool(args_schema=DocumentSearchInput)
async def search_documents(query: str, doc_type: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
    """
    搜索企业知识库中的文档。
    
    用途: 检索PRD、接口文档、业务流程文档、技术文档等。
    当用户询问需求、接口、模块、版本等相关信息时使用此工具。
    
    参数:
    - query: 搜索关键词
    - doc_type: 可选，按文档类型过滤
    - top_k: 返回结果数量
    
    返回:
    - 包含相关文档列表和摘要
    """
    logger.info(f"Searching documents: query={query}, doc_type={doc_type}")
    
    # 获取retriever实例
    retriever = HybridRetriever.get_instance()
    
    results = await retriever.search(
        query=query,
        top_k=top_k,
        filters={"doc_type": doc_type} if doc_type else None
    )
    
    return {
        "query": query,
        "doc_type": doc_type,
        "total": len(results),
        "documents": results
    }


@tool(args_schema=RequirementQueryInput)
async def query_requirements(
    requirement_id: Optional[str] = None,
    keyword: Optional[str] = None,
    module: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询产品需求信息。
    
    用途: 查询需求的详细信息、来源、业务规则等。
    当用户询问某个需求的具体内容、来源、优先级等信息时使用。
    
    参数:
    - requirement_id: 需求ID（精确查询）
    - keyword: 需求关键词（模糊查询）
    - module: 所属模块
    - status: 需求状态
    
    返回:
    - 需求详情列表
    """
    logger.info(f"Querying requirements: id={requirement_id}, keyword={keyword}")
    
    # 模拟数据库查询
    # 实际项目中应连接数据库
    mock_results = [
        {
            "id": "REQ-001",
            "title": "用户登录功能优化",
            "module": "用户中心",
            "status": "已上线",
            "priority": "高",
            "description": "优化用户登录流程，增加手机号验证码登录",
            "created_at": "2024-01-15",
            "source": "PRD-V2.3-第5章"
        }
    ]
    
    # 根据参数过滤
    results = mock_results
    if requirement_id:
        results = [r for r in results if r["id"] == requirement_id]
    if keyword:
        results = [r for r in results if keyword.lower() in r["title"].lower()]
    if module:
        results = [r for r in results if module in r["module"]]
    if status:
        results = [r for r in results if r["status"] == status]
    
    return {
        "query_type": "requirement",
        "total": len(results),
        "requirements": results
    }


@tool(args_schema=InterfaceQueryInput)
async def query_interfaces(
    interface_id: Optional[str] = None,
    interface_name: Optional[str] = None,
    module: Optional[str] = None,
    method: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询接口/API信息。
    
    用途: 查询接口的详细信息、参数、返回值、调用示例等。
    当用户询问某个接口的具体实现、参数定义、返回值格式等信息时使用。
    
    参数:
    - interface_id: 接口ID（精确查询）
    - interface_name: 接口名称关键词（模糊查询）
    - module: 所属模块
    - method: HTTP方法
    
    返回:
    - 接口详情列表
    """
    logger.info(f"Querying interfaces: id={interface_id}, name={interface_name}")
    
    # 模拟数据库查询
    mock_results = [
        {
            "id": "API-001",
            "name": "获取用户信息",
            "method": "GET",
            "path": "/api/v1/user/info",
            "module": "用户中心",
            "description": "获取当前登录用户的详细信息",
            "parameters": [
                {"name": "user_id", "type": "string", "required": True, "description": "用户ID"}
            ],
            "response": {"code": 0, "message": "success", "data": {...}},
            "source": "接口文档-V3.0-5.1节"
        }
    ]
    
    # 根据参数过滤
    results = mock_results
    if interface_id:
        results = [r for r in results if r["id"] == interface_id]
    if interface_name:
        results = [r for r in results if interface_name.lower() in r["name"].lower()]
    if module:
        results = [r for r in results if module in r["module"]]
    if method:
        results = [r for r in results if r["method"] == method.upper()]
    
    return {
        "query_type": "interface",
        "total": len(results),
        "interfaces": results
    }


@tool(args_schema=ModuleQueryInput)
async def query_modules(
    module_id: Optional[str] = None,
    module_name: Optional[str] = None,
    layer: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询功能模块信息。
    
    用途: 查询模块的层级结构、依赖关系、负责人等。
    当用户询问某个模块的详细信息、上下游依赖等信息时使用。
    
    参数:
    - module_id: 模块ID
    - module_name: 模块名称关键词
    - layer: 所属层级
    
    返回:
    - 模块详情列表
    """
    logger.info(f"Querying modules: id={module_id}, name={module_name}")
    
    # 模拟数据库查询
    mock_results = [
        {
            "id": "MOD-001",
            "name": "用户中心",
            "layer": "后端",
            "description": "用户账号、认证、权限相关功能",
            "owner": "张三",
            "dependencies": ["MOD-002", "MOD-003"],
            "related_interfaces": ["API-001", "API-002"],
            "source": "架构文档-V1.5"
        }
    ]
    
    # 根据参数过滤
    results = mock_results
    if module_id:
        results = [r for r in results if r["id"] == module_id]
    if module_name:
        results = [r for r in results if module_name.lower() in r["name"].lower()]
    if layer:
        results = [r for r in results if r["layer"] == layer]
    
    return {
        "query_type": "module",
        "total": len(results),
        "modules": results
    }


@tool(args_schema=VersionQueryInput)
async def query_versions(
    version_id: Optional[str] = None,
    version_name: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询版本/迭代信息。
    
    用途: 查询版本的发布时间、包含的需求、变更内容等。
    当用户询问某个版本的详情、发布时间、包含哪些需求等信息时使用。
    
    参数:
    - version_id: 版本号
    - version_name: 版本名称关键词
    - status: 版本状态
    
    返回:
    - 版本详情列表
    """
    logger.info(f"Querying versions: id={version_id}, name={version_name}")
    
    # 模拟数据库查询
    mock_results = [
        {
            "id": "V2.5.0",
            "name": "2024年Q2大版本",
            "status": "已上线",
            "release_date": "2024-06-30",
            "requirements": ["REQ-001", "REQ-002", "REQ-003"],
            "changes": [
                "优化用户登录流程",
                "新增消息推送功能",
                "修复已知问题15个"
            ],
            "source": "版本计划-V2.5"
        }
    ]
    
    # 根据参数过滤
    results = mock_results
    if version_id:
        results = [r for r in results if version_id in r["id"]]
    if version_name:
        results = [r for r in results if version_name.lower() in r["name"].lower()]
    if status:
        results = [r for r in results if r["status"] == status]
    
    return {
        "query_type": "version",
        "total": len(results),
        "versions": results
    }


@tool(args_schema=ImpactAnalysisInput)
async def analyze_impact(change_content: str, change_type: str) -> Dict[str, Any]:
    """
    分析变更的影响范围。
    
    用途: 分析接口/字段/功能变更会影响到哪些模块、接口、需求。
    当用户询问某个变更会影响哪些地方、需要注意什么风险时使用。
    注意: 这是一个高风险操作，可能返回需要确认的信息。
    
    参数:
    - change_content: 变更内容描述
    - change_type: 变更类型 (接口变更/字段变更/新增功能)
    
    返回:
    - 影响分析结果
    """
    logger.info(f"Analyzing impact: {change_content}, type={change_type}")
    
    # 模拟影响分析
    mock_analysis = {
        "change_type": change_type,
        "change_content": change_content,
        "affected_modules": [
            {"id": "MOD-001", "name": "用户中心", "impact_level": "高"},
            {"id": "MOD-002", "name": "订单服务", "impact_level": "中"},
        ],
        "affected_interfaces": [
            {"id": "API-001", "name": "获取用户信息", "action_required": "需要同步更新"},
            {"id": "API-015", "name": "订单列表", "action_required": "需要兼容性处理"},
        ],
        "affected_versions": [
            {"id": "V2.6.0", "name": "下个版本", "schedule_impact": "可能延期3天"}
        ],
        "risks": [
            "接口兼容性需要特别处理",
            "需要更新相关文档"
        ],
        "recommendations": [
            "建议先在测试环境验证",
            "注意接口版本管理"
        ]
    }
    
    return {
        "analysis_type": "impact",
        "analysis": mock_analysis
    }


def get_all_tools() -> List:
    """获取所有工具"""
    return [
        search_documents,
        query_requirements,
        query_interfaces,
        query_modules,
        query_versions,
        analyze_impact
    ]


def get_tool_by_name(name: str):
    """根据名称获取工具"""
    tools = get_all_tools()
    for tool in tools:
        if tool.name == name:
            return tool
    return None
