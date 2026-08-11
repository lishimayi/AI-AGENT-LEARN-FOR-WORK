# LangChain 1.0 底层架构

```
#简单架构示意图

————————————————
| langChain 1.0 应用层
| （create_agent, 工具 和中间件）
————————————————
🔽
————————————————
| LangGraph 编排层
| （StateGraph，Nodes，Edges，CheckPoints）
————————————————
🔽
————————————————
| LCEL 运行时层
| （Runnable接口，|运算符，流式/批处理）
————————————————
🔽
————————————————
| LLM API
| （Open AI / DeepSeek ）
————————————————

```

* LCEL: 提供runnable接口（invoke，Stream，batch）和 组合原语（|运算符）是 无状态的函数式编排，构建”流水线（pipeline）“的工具
* LangGraph：在LCEL基础上增加了状态管理，循环控制，持久化，是有状态的图结构编排，构建”流程图（workflow/graph）“的工具。