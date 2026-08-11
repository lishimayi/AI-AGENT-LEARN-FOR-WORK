"""LangGraph Agent 状态机 - 核心编排逻辑"""
from typing import TypedDict, Annotated, Sequence, Literal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_function
from loguru import logger

from src.core.config import config


class AgentState(TypedDict):
    """Agent 状态定义"""
    messages: Annotated[Sequence[BaseMessage], "append"]
    user_input: str
    intent: Optional[str]
    task_plan: Optional[List[str]]
    current_step: int
    retrieved_docs: Optional[List[Dict]]
    final_answer: Optional[str]
    needs_confirmation: bool
    confirmation_message: Optional[str]
    error: Optional[str]


class Intent(Enum):
    """意图类型"""
    QUERY_REQUIREMENT = "query_requirement"      # 查询需求
    QUERY_INTERFACE = "query_interface"         # 查询接口
    QUERY_MODULE = "query_module"               # 查询模块
    QUERY_VERSION = "query_version"             # 查询版本
    ANALYZE_IMPACT = "analyze_impact"          # 分析影响范围
    SEARCH_DOCUMENT = "search_document"         # 搜索文档
    GENERAL_QUESTION = "general_question"       # 通用问题
    UNKNOWN = "unknown"                         # 未知意图


@dataclass
class AgentConfig:
    """Agent 配置"""
    system_prompt: str = field(default_factory=lambda: config.agent.get(
        "system_prompt",
        "你是一个企业级产品需求智能助手。"
    ))
    max_iterations: int = field(default_factory=lambda: config.agent.get("react", {}).get("max_iterations", 10))
    enable_human_in_loop: bool = field(default_factory=lambda: config.agent.get("workflow", {}).get("enable_human_in_loop", False))
    confirmation_threshold: str = field(default_factory=lambda: config.agent.get("workflow", {}).get("confirmation_threshold", "high"))


class EnterpriseRAGAgent:
    """
    企业级产品需求智能 Agent
    基于 LangGraph 实现状态机编排
    
    状态流转:
    user_input -> intent_classification -> task_planning -> 
    tool_execution -> answer_synthesis -> END
    
    支持 Human-in-the-loop: 高风险操作需要确认
    """
    
    def __init__(
        self,
        tools: List[Any],
        llm: Any,
        config: Optional[AgentConfig] = None
    ):
        self.tools = tools
        self.llm = llm
        self.agent_config = config or AgentConfig()
        
        # 创建工具映射
        self.tool_map = {tool.name: tool for tool in tools}
        
        # 构建状态图
        self.graph = self._build_graph()
        
        # 检查点 (用于状态持久化)
        self.checkpointer = MemorySaver()
        
        logger.info(f"EnterpriseRAGAgent initialized with {len(tools)} tools")
    
    def _build_graph(self) -> StateGraph:
        """构建状态图"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("intent_classifier", self._classify_intent)
        workflow.add_node("task_planner", self._plan_tasks)
        workflow.add_node("tool_executor", self._execute_tools)
        workflow.add_node("answer_synthesizer", self._synthesize_answer)
        workflow.add_node("confirmation_handler", self._handle_confirmation)
        workflow.add_node("error_handler", self._handle_error)
        
        # 设置入口点
        workflow.set_entry_point("intent_classifier")
        
        # 定义边 (状态流转)
        workflow.add_edge("intent_classifier", "task_planner")
        workflow.add_edge("task_planner", "tool_executor")
        workflow.add_edge("tool_executor", "answer_synthesizer")
        workflow.add_edge("answer_synthesizer", END)
        
        # 条件边
        workflow.add_conditional_edges(
            "intent_classifier",
            self._should_confirm,
            {
                "confirm": "confirmation_handler",
                "continue": "task_planner"
            }
        )
        
        workflow.add_conditional_edges(
            "confirmation_handler",
            self._check_confirmation_response,
            {
                "approved": "task_planner",
                "rejected": END
            }
        )
        
        workflow.add_conditional_edges(
            "tool_executor",
            self._should_continue,
            {
                "continue": "answer_synthesizer",
                "retry": "tool_executor",
                "error": "error_handler"
            }
        )
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _classify_intent(self, state: AgentState) -> AgentState:
        """意图分类"""
        user_input = state["user_input"]
        
        intent_prompt = f"""分析用户输入，确定其意图类别。

用户输入: {user_input}

可选意图:
- query_requirement: 查询产品需求相关信息
- query_interface: 查询接口/API相关信息
- query_module: 查询功能模块信息
- query_version: 查询版本/迭代信息
- analyze_impact: 分析影响范围
- search_document: 搜索文档
- general_question: 通用问题

请只返回一个意图类别，如: query_requirement"""
        
        messages = [
            SystemMessage(content="你是一个意图分类专家。"),
            HumanMessage(content=intent_prompt)
        ]
        
        try:
            response = await self.llm.invoke(messages)
            intent_str = response.content.strip().lower()
            
            # 映射意图
            intent_map = {
                "query_requirement": Intent.QUERY_REQUIREMENT,
                "query_interface": Intent.QUERY_INTERFACE,
                "query_module": Intent.QUERY_MODULE,
                "query_version": Intent.QUERY_VERSION,
                "analyze_impact": Intent.ANALYZE_IMPACT,
                "search_document": Intent.SEARCH_DOCUMENT,
                "general_question": Intent.GENERAL_QUESTION,
            }
            
            intent = intent_map.get(intent_str, Intent.GENERAL_QUESTION)
            
            logger.info(f"Intent classified: {intent.value}")
            
            return {
                **state,
                "intent": intent.value,
                "messages": state["messages"] + [AIMessage(content=f"意图识别: {intent.value}")]
            }
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return {**state, "intent": Intent.UNKNOWN.value}
    
    async def _plan_tasks(self, state: AgentState) -> AgentState:
        """任务规划"""
        user_input = state["user_input"]
        intent = state.get("intent", Intent.GENERAL_QUESTION.value)
        
        planning_prompt = f"""根据用户意图规划执行步骤。

用户输入: {user_input}
意图类别: {intent}

可用的工具:
{self._format_tools_for_planning()}

请规划执行步骤，使用JSON格式返回:
{{
    "steps": ["step1", "step2", ...],
    "reasoning": "规划理由"
}}

步骤应该按照执行顺序排列，使用工具名称作为步骤标识。"""
        
        messages = [
            SystemMessage(content="你是一个任务规划专家。"),
            HumanMessage(content=planning_prompt)
        ]
        
        try:
            response = await self.llm.invoke(messages)
            
            import json
            try:
                plan = json.loads(response.content)
                steps = plan.get("steps", [])
            except:
                # 默认单步执行
                steps = ["search_documents"]
            
            logger.info(f"Task planned: {steps}")
            
            return {
                **state,
                "task_plan": steps,
                "current_step": 0,
                "messages": state["messages"] + [AIMessage(content=f"任务规划: {steps}")]
            }
        except Exception as e:
            logger.error(f"Task planning error: {e}")
            return {**state, "task_plan": ["search_documents"], "current_step": 0}
    
    async def _execute_tools(self, state: AgentState) -> AgentState:
        """工具执行"""
        task_plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        retrieved_docs = state.get("retrieved_docs", [])
        
        if current_step >= len(task_plan):
            return state
        
        tool_name = task_plan[current_step]
        
        # 获取工具
        tool = self.tool_map.get(tool_name)
        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
            return {
                **state,
                "current_step": current_step + 1,
                "messages": state["messages"] + [AIMessage(content=f"工具 {tool_name} 未找到")]
            }
        
        # 构建工具输入
        user_input = state["user_input"]
        tool_input = {"query": user_input}
        
        try:
            # 执行工具
            result = await tool.ainvoke(tool_input)
            
            # 合并检索结果
            if isinstance(result, dict) and "documents" in result:
                retrieved_docs.extend(result["documents"])
            
            logger.info(f"Tool executed: {tool_name}")
            
            return {
                **state,
                "current_step": current_step + 1,
                "retrieved_docs": retrieved_docs,
                "messages": state["messages"] + [AIMessage(content=f"已执行: {tool_name}")]
            }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                **state,
                "current_step": current_step + 1,
                "error": str(e),
                "messages": state["messages"] + [AIMessage(content=f"执行失败: {tool_name}")]
            }
    
    async def _synthesize_answer(self, state: AgentState) -> AgentState:
        """答案合成"""
        user_input = state["user_input"]
        retrieved_docs = state.get("retrieved_docs", [])
        
        # 构建上下文
        context = self._build_context(retrieved_docs)
        
        synthesis_prompt = f"""{self.agent_config.system_prompt}

用户问题: {user_input}

相关文档:
{context}

请基于以上文档内容，准确回答用户问题。
如果文档中没有相关信息，请明确告知用户。
并提供答案的来源引用。"""
        
        messages = [
            SystemMessage(content="你是一个答案合成专家。"),
            HumanMessage(content=synthesis_prompt)
        ]
        
        try:
            response = await self.llm.invoke(messages)
            
            logger.info("Answer synthesized")
            
            return {
                **state,
                "final_answer": response.content,
                "messages": state["messages"] + [response]
            }
        except Exception as e:
            logger.error(f"Answer synthesis error: {e}")
            return {
                **state,
                "final_answer": f"抱歉，生成回答时发生错误: {str(e)}"
            }
    
    async def _handle_confirmation(self, state: AgentState) -> AgentState:
        """确认处理 (Human-in-the-loop)"""
        confirmation_msg = state.get("confirmation_message", "请确认是否继续操作？")
        
        return {
            **state,
            "needs_confirmation": True,
            "confirmation_message": confirmation_msg,
            "messages": state["messages"] + [AIMessage(content=confirmation_msg)]
        }
    
    async def _handle_error(self, state: AgentState) -> AgentState:
        """错误处理"""
        error = state.get("error", "未知错误")
        
        return {
            **state,
            "final_answer": f"处理过程中遇到问题: {error}",
            "messages": state["messages"] + [AIMessage(content=f"错误: {error}")]
        }
    
    def _should_confirm(self, state: AgentState) -> str:
        """判断是否需要确认"""
        if not self.agent_config.enable_human_in_loop:
            return "continue"
        
        intent = state.get("intent", "")
        high_risk_intents = ["analyze_impact"]
        
        if intent in high_risk_intents:
            return "confirm"
        
        return "continue"
    
    def _check_confirmation_response(self, state: AgentState) -> str:
        """检查确认响应"""
        # 这里需要从外部获取用户确认状态
        # 暂时返回 approved
        return "approved"
    
    def _should_continue(self, state: AgentState) -> str:
        """判断是否继续执行"""
        if state.get("error"):
            return "error"
        
        current_step = state.get("current_step", 0)
        task_plan = state.get("task_plan", [])
        
        if current_step < len(task_plan):
            return "retry"
        
        return "continue"
    
    def _format_tools_for_planning(self) -> str:
        """格式化工具列表供规划使用"""
        tool_info = []
        for tool in self.tools:
            tool_info.append(f"- {tool.name}: {tool.description}")
        return "\n".join(tool_info) if tool_info else "无可用工具"
    
    def _build_context(self, docs: List[Dict]) -> str:
        """构建上下文"""
        if not docs:
            return "没有找到相关的知识库内容。"
        
        context_parts = []
        for i, doc in enumerate(docs[:5], 1):  # 限制上下文长度
            content = doc.get("content", "")
            source = doc.get("metadata", {}).get("source", "未知来源")
            score = doc.get("score", 0)
            
            context_parts.append(f"【文档 {i}】来源: {source} (相关度: {score:.2%})\n{content}")
        
        return "\n\n".join(context_parts)
    
    async def run(self, user_input: str, thread_id: str = "default") -> Dict[str, Any]:
        """运行 Agent"""
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "user_input": user_input,
            "intent": None,
            "task_plan": None,
            "current_step": 0,
            "retrieved_docs": None,
            "final_answer": None,
            "needs_confirmation": False,
            "confirmation_message": None,
            "error": None
        }
        
        config_options = {"configurable": {"thread_id": thread_id}}
        
        try:
            result = await self.graph.ainvoke(initial_state, config=config_options)
            return {
                "answer": result.get("final_answer", "未能生成回答"),
                "intent": result.get("intent"),
                "sources": result.get("retrieved_docs", []),
                "messages": result.get("messages", [])
            }
        except Exception as e:
            logger.error(f"Agent run error: {e}")
            return {
                "answer": f"Agent 执行错误: {str(e)}",
                "intent": None,
                "sources": [],
                "messages": []
            }
    
    async def run_stream(self, user_input: str, thread_id: str = "default"):
        """流式运行 Agent"""
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "user_input": user_input,
            "intent": None,
            "task_plan": None,
            "current_step": 0,
            "retrieved_docs": None,
            "final_answer": None,
            "needs_confirmation": False,
            "confirmation_message": None,
            "error": None
        }
        
        config_options = {"configurable": {"thread_id": thread_id}}
        
        async for event in self.graph.astream(initial_state, config=config_options):
            yield event
