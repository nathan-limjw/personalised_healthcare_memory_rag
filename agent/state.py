# agent/state.py
from typing import Annotated

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import Literal, TypedDict


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    user_name: str
    framework: str  # "mem0" | "langmem"
    relevance: Literal["relevant", "irrelevant"]
    reason: str


class RelevanceOutput(BaseModel):
    relevance: Literal["relevant", "irrelevant"] = Field(
        description="Depends on whether the following query is medical or clinical in nature"
    )
    reason: str
