# Generated from design/gateway.md v1.6
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

class ToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction

class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class StandardRequest(BaseModel):
    model: str
    messages: List[Message]
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Ollama specific options")

class StandardResponse(BaseModel):
    id: str
    model: str
    created: int
    message: Message
    done: bool = True
    usage: Optional[Dict[str, int]] = None
