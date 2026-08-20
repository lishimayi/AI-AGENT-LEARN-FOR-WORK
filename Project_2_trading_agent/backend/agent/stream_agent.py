
from dotenv import load_dotenv
import os
from langchain.agents import create_agent
from langchain.tools import tool
from pydantic import BaseModel,Field
from langchain_openai.chat_models import ChatOpenAI

from langchain.messages import AIMessage, HumanMessage

from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

@tool
def search_weather() -> str:
    """用户搜索天气用"""
    return "北京今天天气31度适合穿半袖."
@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"),api_key=os.getenv("OPENAI_API_KEY"),base_url=os.getenv("OPENAI_BASE_URL"))

class Answer(BaseModel):
    summary: str
    confidence: float

class TravelPlan(BaseModel):
    destination: str = Field(description="推荐的旅游目的地")
    days: int = Field(description="旅游天数")
    budget: float = Field(description="预算，单位：人民币")
    travel_style: str = Field(description="旅游风格，例如自然、城市、美食")
    recommendation: str = Field(description="推荐理由")

agent = create_agent(
    model=model,
    # tools=[search_weather,search],
    tools=[],
    system_prompt="你是一个优秀的个人助手",
    response_format=TravelPlan,
    # checkpointer=InMemorySaver()
)
# #----------------------- 流 事件---------------
# stream = agent.stream_events(
#     {"messages": [{"role": "user", "content": "Search for AI news and summarize the findings"}]},
#     version="v3",
# )
# for snapshot in stream.values:
#     # Each snapshot contains the full state at that point
#     latest_message = snapshot["messages"][-1]
#     if latest_message.content:
#         if isinstance(latest_message, HumanMessage):
#             print(f"User: {latest_message.content}")
#         elif isinstance(latest_message, AIMessage):
#             print(f"Agent: {latest_message.content}")
#     elif latest_message.tool_calls:
#         print(f"Calling tools: {[tc['name'] for tc in latest_message.tool_calls]}")
#
#
# #----------------------- 配置---------------
# config = {"configurable":{"thread_id": str(uuid7())}}
# result = agent.invoke({
#     "messages": [{
#         "role": "user",
#         "content": "我想去日本玩5天，预算5000元，喜欢自然风景，帮我推荐一下"}]},
#     config=config
# )
#
# result = agent.invoke({
#     "messages": [{
#         "role": "user",
#         "content": "还能去哪里"}]},
#     config=config
# )

# print(result)

# Configure the harness
# create_agent is highly extensible.
# Middleware is the primitive for customization:
# 中间件是定制化的基础
# each piece handles one concern,
# 每件产品解决一个具体问题
# hooks into the agent loop at the right moment,
# and composes freely with any other. Take exactly what your use case needs and skip the rest.
# Common patterns are prebuilt as first-class middleware.
# 常见模式作为第一类预先构建
# You can build anything else as custom middleware.


print(agent.invoke( {""}"hi,give me a traval plan"))