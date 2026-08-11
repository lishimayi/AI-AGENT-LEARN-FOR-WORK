# lang chain 生态概览

## 模型层（Models）

* langchain1.0的统一模型抽象层，为所有模型提供标准化调用，覆盖文本，多磨态，rerank，embedding 等多类型模型，实现跨供应商一致体验。
	* 统一抽象：init_chat_model() 适配20+ 模型厂商。
	*  异步/流式/批处理：ainvoke(), stream(), batch()
	*  执行方式：完全兼容 LCEL 和 LangGraph
	*  拓展能力：tools，with\_structred\_output , Tool Calling , 多模态的 content Blocks

## 工具层（Tools）

>  工具系统提供统一Tools 抽象，支持所有主流模型的tool calling，深度集成LangGraph，构建可执行Agent环境的关键能力层。

* 内置工具：搜索，计算，代码执行等100+ Tools
* 自定义工具：@tool装饰器，BaseTool，ToolNode
* 工具包：ToolKit（如github，Slack集成）

## 记忆层
> 提供统一的State管理，对话记录，长期检索，多模态memory等能力，支持持久化与复杂工作流状态流转。

* 短期记忆：消息历史自动管理
* 长期记忆：向量数据库存储（Chroma，Pinecone）
* 存储接口：Store （夸会话持久化）

## Agent层（Agents）
> LangChain1.0 Agents系统实现了从碎片化到标准化升级，以create_agent为核心接口，基于LangGraph构建统一Agent抽象，10行代码即可创建基础Agent，封装“模型调用➡️工具选择➡️执行➡️结束”闭环流程。

* 核心API：create_agent()
* 执行引擎：LangGraph Runtime （自动持久化）
* 中间件：Middleware （HITL，压缩，路由）

## 工作流层（workflows)
> Workflows体系实现从线性链式（chain）到图结构（graph）的范式转移，以StateGraph为核心画布，将业务逻辑解耦为“节点（node）+边（Edge）+状态（State）”，原生支持循环（Loop）与条件分支，完美适配复杂任务编排，容错重试以及长会话保持。

* 简单链：chain（快速串联）
* 复杂图：LangGraph（条件分支，循环）
* 模板库：LangChain Hub（共享Agent模板）

## 调试监控层（Debugging）
> LangChain1.0 调试监控层实现了从日志黑盒到全链路可观测性（observability)的质变，深度集成LangSmith平台，自动捕获链与图的每一步状态，token消耗以及延迟，支持“Trace-->Playground"一键回放调试，彻底解决复杂Agent逻辑难以排查的痛点。

* 本地日志：verbose=True
* 云端平台：LangSmith（可视化链路追踪）
* 评估工具：LangChain Evaluate（效果评估）

## 其他关键组件（LangGraph & LangServe）
* langgraph：是一个底层的Agent调度框架（Agent Runtime），是一个相对低级low-level的编排框架，它专注于解决复杂的控制流问题，用于构建健壮且有状态的多角色LLM 应用程序，LC1.0（LangChain1.0）中的新Agents（通过create_agent())就是简历在LangGraph之上的。
* langserve：用于将任何LangChain chain或者Agent 部署为Rest API 包，



