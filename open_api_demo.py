import os

from openai import OpenAI
from transformers import AutoTokenizer


def estimate_messages_tokens(messages, tokenizer) -> int:
    """使用 Hugging Face tokenizer 本地估算消息 token。"""
    try:
        # 对支持 chat template 的 tokenizer，优先按对话格式计数。
        token_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
        )
        return len(token_ids)
    except Exception:
        # 回退：拼接 role/content 后编码计数。
        text = "\n".join(
            f"{msg.get('role', '')}: {msg.get('content', '')}" for msg in messages
        )
        return len(tokenizer.encode(text, add_special_tokens=True))


def main() -> None:
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        raise ValueError("请先设置环境变量 ZHIPUAI_API_KEY")

    client = OpenAI(
        api_key=api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )
    tokenizer_name = os.getenv("TOKENIZER_NAME", "bert-base-chinese")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你好，请做个自我介绍。"},
    ]
    local_prompt_tokens = estimate_messages_tokens(messages, tokenizer)
    print(f"本地预估 prompt tokens({tokenizer_name}): {local_prompt_tokens}")

    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=messages,
        temperature=0.7,
    )

    print(response.choices[0].message.content)
    if response.usage:
        print(
            f"接口返回 usage - prompt: {response.usage.prompt_tokens}, "
            f"completion: {response.usage.completion_tokens}, "
            f"total: {response.usage.total_tokens}"
        )


if __name__ == "__main__":
    main()
