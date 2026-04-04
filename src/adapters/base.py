# Generated from design/gateway.md v1.6
from abc import ABC, abstractmethod
from typing import AsyncIterable, Union
from src.models import StandardRequest, StandardResponse

class BaseAdapter(ABC):
    """
    所有后端适配器的抽象基类。
    定义了网关与不同 LLM 服务通信的标准接口。
    """
    
    @abstractmethod
    async def chat(self, request: StandardRequest) -> Union[StandardResponse, AsyncIterable[StandardResponse]]:
        """执行对话请求"""
        pass

    @abstractmethod
    async def generate(self, request: StandardRequest) -> Union[StandardResponse, AsyncIterable[StandardResponse]]:
        """执行提示词生成请求"""
        pass

    @abstractmethod
    async def list_models(self) -> Dict[str, Any]:
        """获取可用模型列表"""
        pass

    @abstractmethod
    async def get_version(self) -> str:
        """获取后端服务版本"""
        pass
