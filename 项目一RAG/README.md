# 企业级产品需求智能 Agent

基于 LangGraph + RAG + Tool Calling 的企业级产品需求智能问答系统。

## 项目概述

本项目是面向企业内部研发协作场景的智能 Agent 系统，解决产品需求、技术文档、接口规范等知识分散导致研发人员难以快速理解业务逻辑的问题。

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (React)                              │
│              WebSocket / HTTP 流式对话界面                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      FastAPI 服务层                              │
│            HTTP API + WebSocket 流式响应 + 限流                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    LangGraph Agent 编排层                        │
│         意图分类 → 任务规划 → 工具执行 → 答案合成                  │
│              (状态机 + Human-in-the-loop)                        │
└───────┬─────────────────┬──────────────────┬───────────────────┘
        │                 │                  │
        ▼                 ▼                  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────────────┐
│  文档检索工具  │ │  需求查询工具  │ │  接口/模块/版本查询工具 │
└───────┬───────┘ └───────┬───────┘ └───────────┬───────────┘
        │                 │                      │
        └─────────────────┼──────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│                   Hybrid Retrieval 引擎                         │
│              向量检索 (Embedding) + BM25 关键词检索              │
└─────────────────────────────┬─────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                       数据存储层                                 │
│         PostgreSQL (元数据) + Chroma/FAISS (向量)                │
└─────────────────────────────────────────────────────────────────┘
```

## 核心特性

### 1. LangGraph 状态机编排
- 意图分类：自动识别用户查询意图
- 任务规划：ReAct 风格的自主规划
- 工具执行：动态选择和调用工具
- 答案合成：基于检索结果生成回答

### 2. Hybrid Retrieval 混合检索
- 向量检索：基于语义相似度
- BM25 关键词检索：精确关键词匹配
- 权重融合：70% 向量 + 30% BM25

### 3. Tool Calling 工具体系
- 文档检索 (search_documents)
- 需求查询 (query_requirements)
- 接口查询 (query_interfaces)
- 模块查询 (query_modules)
- 版本查询 (query_versions)
- 影响分析 (analyze_impact)

### 4. 多模型支持
- OpenAI (GPT-4o / GPT-4o-mini)
- Anthropic (Claude)
- 智谱 GLM
- 阿里通义千问

## 项目结构

```
enterprise-rag/
├── backend/
│   ├── config/
│   │   └── config.yaml          # 配置文件
│   ├── src/
│   │   ├── api/
│   │   │   └── main.py          # FastAPI 主入口
│   │   ├── agents/
│   │   │   └── langgraph_agent.py  # LangGraph Agent
│   │   ├── tools/
│   │   │   └── agent_tools.py   # Tool Calling 工具
│   │   ├── retrieval/
│   │   │   ├── hybrid_retriever.py  # 混合检索
│   │   │   └── document_processor.py # 文档处理
│   │   ├── models/
│   │   │   └── llm_factory.py   # 多模型适配
│   │   ├── core/
│   │   │   └── config.py        # 配置管理
│   │   └── schemas/
│   │       └── api.py           # 数据模型
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # 主应用
│   │   ├── store/
│   │   │   └── chatStore.ts    # 状态管理
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
├── deploy/
│   ├── Dockerfile.backend
│   └── docker-compose.yml
└── README.md
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- Node.js 18+
- Docker (可选)

### 2. 后端安装

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key
```

### 3. 启动后端

```bash
# 开发模式
uvicorn src.api.main:app --reload --port 8000

# 或使用脚本
bash scripts/start.sh
```

### 4. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 5. Docker 部署

```bash
cd deploy

# 复制环境变量
cp ../backend/.env.example .env
# 编辑 .env

# 启动服务
docker-compose up -d
```

## API 接口

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /` | GET | 根路径 |
| `GET /health` | GET | 健康检查 |
| `GET /stats` | GET | 统计信息 |
| `POST /query` | POST | 非流式查询 |
| `POST /upload` | POST | 上传文档 |
| `WS /ws/{session_id}` | WebSocket | 流式对话 |

### 查询示例

```bash
# 健康检查
curl http://localhost:8000/health

# 查询
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "查询某个需求的详细信息"}'

# 上传文档
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/document.pdf" \
  -F "doc_type=prd"
```

## 配置说明

编辑 `backend/config/config.yaml`:

```yaml
# LLM 配置
llm:
  provider: "openai"  # openai / anthropic / zhipu / qwen
  openai:
    model: "gpt-4o-mini"

# 检索配置
retrieval:
  hybrid:
    vector_weight: 0.7
    keyword_weight: 0.3

# Agent 配置
agent:
  react:
    max_iterations: 10
```

## 开发指南

### 添加新工具

1. 在 `src/tools/agent_tools.py` 中定义工具函数
2. 使用 `@tool` 装饰器和 Pydantic `args_schema`
3. 在 `get_all_tools()` 中注册

```python
from langchain.tools import tool
from pydantic import BaseModel, Field

class NewToolInput(BaseModel):
    param: str = Field(description="参数描述")

@tool(args_schema=NewToolInput)
async def new_tool(param: str) -> dict:
    """工具描述"""
    return {"result": param}
```

### 更换 Embedding 模型

修改 `config/config.yaml`:

```yaml
embedding:
  model: "shibing624/text2vec-base-chinese"  # 中文模型
  dimension: 768
```

## 许可证

MIT License
