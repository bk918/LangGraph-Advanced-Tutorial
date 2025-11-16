"""Deep Research 에이전트를 위한 그래프 상태 정의 및 데이터 구조."""

import operator
from typing import Annotated

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


###################
# 구조화된 출력들
###################
class ConductResearch(BaseModel):
    """특정 주제에 대한 연구를 수행하기 위해 이 도구를 호출합니다."""

    research_topic: str = Field(
        description="연구할 주제. 단일 주제여야 하며, 최소한 한 문단 정도로 상세하게 설명해야 합니다.",
    )


class ResearchComplete(BaseModel):
    """연구가 완료되었음을 나타내기 위해 이 도구를 호출합니다."""


class Summary(BaseModel):
    """주요 발견사항과 함께 연구 요약 제공."""

    summary: str
    key_excerpts: str


class ClarifyWithUser(BaseModel):
    """사용자 명확화 요청을 위한 모델."""

    need_clarification: bool = Field(
        description="사용자에게 명확화 질문을 해야 하는지 여부.",
    )
    question: str = Field(
        description="보고서 범위를 명확히 하기 위해 사용자에게 물을 질문",
    )
    verification: str = Field(
        description="사용자가 필요한 정보를 제공한 후 연구를 시작할 것임을 확인하는 메시지.",
    )


class ResearchQuestion(BaseModel):
    """연구를 안내하기 위한 연구 질문 및 개요."""

    research_brief: str = Field(
        description="연구를 안내하는 데 사용될 연구 질문.",
    )


###################
# State Definitions
###################


def override_reducer(current_value, new_value):
    """상태에서 값을 덮어쓰기할 수 있도록 하는 리듀서 함수."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class AgentInputState(MessagesState):
    """InputState는 'messages'만 포함합니다."""


class AgentState(MessagesState):
    """메시지와 연구 데이터를 포함하는 메인 에이전트 상태."""

    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str | None
    raw_notes: Annotated[list[str], override_reducer] = []
    notes: Annotated[list[str], override_reducer] = []
    final_report: str
    compressed_research_length: int = 0
    raw_notes_length: int = 0


class SupervisorState(TypedDict):
    """연구 작업을 관리하는 감독자를 위한 상태."""
    # Required
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str
    # Internal 
    notes: Annotated[list[str], override_reducer] = []
    research_iterations: int = 0
    raw_notes: Annotated[list[str], override_reducer] = []
    compressed_research_length: int = 0
    raw_notes_length: int = 0


class ResearcherState(TypedDict):
    """연구를 수행하는 개별 Researcher들을 위한 상태."""

    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int = 0
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []


class ResearcherOutputState(BaseModel):
    """개별 Researcher들로부터의 출력 상태."""

    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []
