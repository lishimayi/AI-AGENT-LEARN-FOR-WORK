# Runnable底层执行引擎
> Runnable是LangChain 1.0 的“统一接口标准”，任何可以运行的组件-----模型，prompt，Tools，解析器，memory ,Graph节点 ---- 在1.0中都被抽象为Runnable
> 
> Runnable 使所有LangChain组件能够以统一接口组合，执行，链式调用，并支撑LCEL（LangChain Expression Language）的整个运行语义，支撑可组合，可并行，可路由的链式执行，LangChain 1.0 的核心底座之一。
> 
> 核心思想：Runnable抽象与可组合链（composable chains）

* LangChain 1.0 将所有链式元素统一为Runnable（执行模型）：
	* LLM
	* prompt
	* Parser
	* Retriever
	* tool
	* agent
	* custom function 

> 	这些都可以 .invoke() .batch() .steam() .astream() .events()

* 工程价值：
	* 链路清晰
	* 任意组件 可无缝组合
	* 执行方式统一（同步，异步，批处理，事件流）
	* 这是LangChain 1.0最具革命性的改变，使其“模型调用管道”

## prompt Runnable 