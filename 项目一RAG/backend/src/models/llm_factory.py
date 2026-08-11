"""多模型适配层 - 支持 OpenAI/Claude/Qwen/智谱"""
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncIterator
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage, SystemMessage, AIMessage, BaseMessage
from loguru import logger

from src.core.config import config


class ModelProvider(Enum):
    """支持的模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ZHIPU = "zhipu"
    QWEN = "qwen"


class BaseLLM(ABC):
    """LLM 基类"""
    
    @abstractmethod
    async def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        """同步调用"""
        pass
    
    @abstractmethod
    async def stream(self, messages: List[BaseMessage]) -> AsyncIterator[str]:
        """流式调用"""
        pass


class OpenAIModel(BaseLLM):
    """OpenAI 模型 (GPT-4o / GPT-4o-mini)"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", **kwargs):
        self.model_name = model_name
        
        model_config = config.llm.get("openai", {})
        api_key = model_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = model_config.get("base_url", "https://api.openai.com/v1")
        
        self.client = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 4096),
            **kwargs
        )
        logger.info(f"Initialized OpenAI model: {model_name}")
    
    async def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        return await self.client.ainvoke(messages)
    
    async def stream(self, messages: List[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in self.client.astream(messages):
            if chunk.content:
                yield chunk.content


class AnthropicModel(BaseLLM):
    """Anthropic 模型 (Claude)"""
    
    def __init__(self, model_name: str = "claude-3-haiku-20240307", **kwargs):
        self.model_name = model_name
        
        model_config = config.llm.get("anthropic", {})
        api_key = model_config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        
        self.client = ChatAnthropic(
            model=model_name,
            anthropic_api_key=api_key,
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 4096),
            **kwargs
        )
        logger.info(f"Initialized Anthropic model: {model_name}")
    
    async def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        return await self.client.ainvoke(messages)
    
    async def stream(self, messages: List[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in self.client.astream(messages):
            if chunk.content:
                yield chunk.content


class QwenModel(BaseLLM):
    """通义千问模型"""
    
    def __init__(self, model_name: str = "qwen-turbo", **kwargs):
        self.model_name = model_name
        
        model_config = config.llm.get("qwen", {})
        api_key = model_config.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
        base_url = model_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        self.client = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 4096),
            **kwargs
        )
        logger.info(f"Initialized Qwen model: {model_name}")
    
    async def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        return await self.client.ainvoke(messages)
    
    async def stream(self, messages: List[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in self.client.astream(messages):
            if chunk.content:
                yield chunk.content


class ZhipuModel(BaseLLM):
    """智谱 GLM 模型"""
    
    def __init__(self, model_name: str = "glm-4", **kwargs):
        self.model_name = model_name
        
        model_config = config.llm.get("zhipu", {})
        api_key = model_config.get("api_key") or os.getenv("ZHIPU_API_KEY")
        base_url = model_config.get("base_url", "https://open.bigmodel.cn/api/paas/v4")
        
        self.client = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 4096),
            **kwargs
        )
        logger.info(f"Initialized Zhipu model: {model_name}")
    
    async def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        return await self.client.ainvoke(messages)
    
    async def stream(self, messages: List[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in self.client.astream(messages):
            if chunk.content:
                yield chunk.content


class LLMFactory:
    """LLM 工厂类 - 根据配置创建对应的模型实例"""
    
    _instances: Dict[str, BaseLLM] = {}
    
    @classmethod
    def get_model(cls, provider: Optional[str] = None) -> BaseLLM:
        """获取模型实例"""
        if provider is None:
            provider = config.llm.get("provider", "openai")
        
        # 返回缓存的实例
        if provider in cls._instances:
            return cls._instances[provider]
        
        # 根据提供商创建实例
        model_map = {
            ModelProvider.OPENAI.value: cls._create_openai,
            ModelProvider.ANTHROPIC.value: cls._create_anthropic,
            ModelProvider.QWEN.value: cls._create_qwen,
            ModelProvider.ZHIPU.value: cls._create_zhipu,
        }
        
        creator = model_map.get(provider)
        if not creator:
            logger.warning(f"未知模型提供商: {provider}，使用默认 OpenAI")
            creator = model_map["openai"]
        
        instance = creator()
        cls._instances[provider] = instance
        return instance
    
    @classmethod
    def _create_openai(cls) -> BaseLLM:
        model_config = config.llm.get("openai", {})
        model_name = model_config.get("model", "gpt-4o-mini")
        return OpenAIModel(model_name)
    
    @classmethod
    def _create_anthropic(cls) -> BaseLLM:
        model_config = config.llm.get("anthropic", {})
        model_name = model_config.get("model", "claude-3-haiku-20240307")
        return AnthropicModel(model_name)
    
    @classmethod
    def _create_qwen(cls) -> BaseLLM:
        model_config = config.llm.get("qwen", {})
        model_name = model_config.get("model", "qwen-turbo")
        return QwenModel(model_name)
    
    @classmethod
    def _create_zhipu(cls) -> BaseLLM:
        model_config = config.llm.get("zhipu", {})
        model_name = model_config.get("model", "glm-4")
        return ZhipuModel(model_name)
    
    @classmethod
    def clear_cache(cls):
        """清空缓存"""
        cls._instances.clear()


class ModelAdapter:
    """
    统一模型适配器
    提供一致的接口访问不同的 LLM
    """
    
    def __init__(self, provider: Optional[str] = None):
        self.model = LLMFactory.get_model(provider)
        self.provider = provider or config.llm.get("provider", "openai")
    
    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        **kwargs
    ) -> str:
        """聊天接口"""
        messages = []
        
        if system:
            messages.append(SystemMessage(content=system))
        
        if history:
            for item in history[-5:]:  # 限制历史长度
                role = item.get("role", "user")
                content = item.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=prompt))
        
        response = await self.model.invoke(messages)
        return response.content
    
    async def chat_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """流式聊天接口"""
        messages = []
        
        if system:
            messages.append(SystemMessage(content=system))
        
        if history:
            for item in history[-5:]:
                role = item.get("role", "user")
                content = item.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=prompt))
        
        async for chunk in self.model.stream(messages):
            yield chunk
