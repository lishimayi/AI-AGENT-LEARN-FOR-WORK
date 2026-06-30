import os

from openai import OpenAI
from dotenv import load_dotenv

def main() -> None:
    # 读取项目根目录下 .env 中的环境变量
    load_dotenv()
    print("Hello from 多轮对话/demo.py")
    ConversationHistory = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你好，请做个自我介绍。"},
    ]
    # 创建客户端
    api_key = os.getenv("ZHIPUAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请先在 .env 中设置 ZHIPUAI_API_KEY 或 OPENAI_API_KEY")
    client = OpenAI(
        api_key=api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )
    user_message_1 = "你好，请做个自我介绍。"
    ConversationHistory.append({"role": "user", "content": user_message_1})
    # 第一轮对话
    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=ConversationHistory,
        temperature=0.7,
    )
    print(response.choices[0].message.content)
    # 第二轮对话
    user_message_2 = response.choices[0].message.content
    ConversationHistory.append({"role": "assistant", "content": user_message_2})

if __name__ == "__main__":
    main()
