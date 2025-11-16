"""DeepAgent 프레임워크를 사용한 딥 리서치 에이전트 구현입니다."""

import os
from datetime import datetime
from typing import Any, Optional

from deepagents import create_deep_agent
from deepagents.backends import StateBackend, FilesystemBackend, CompositeBackend
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from subagents.compressor import create_compressor_subagent_config
from subagents.critic import create_critic_subagent_config
from subagents.researcher import create_researcher_subagent_config

from prompts.orchestrator import format_orchestrator_prompt


def get_today_str() -> str:
    """프롬프트에 사용할 현재 날짜를 포맷팅하여 반환합니다.

    Returns:
        'Mon Jan 15, 2024'와 같은 사람이 읽기 쉬운 날짜 문자열
    """
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"


async def create_deep_research_agent(
    tools: list[Any],
    *,
    model: str = "openai:gpt-4.1",
    max_researcher_iterations: int = 10,
    enable_critique: bool = False,
    enable_clarification: bool = True,
    mcp_prompt: str = "",
    config: Optional[RunnableConfig] = None,
    checkpointer=None,
) -> CompiledStateGraph:
    """DeepAgent 프레임워크를 사용하여 딥 리서치 에이전트를 생성합니다.

    Args:
        tools: 도구 객체 리스트 (tavily_search, think_tool, ResearchComplete, MCP 도구들)
        model: LLM 모델 식별자 (langchain의 init_chat_model을 통해 OpenAI, Anthropic 지원)
        max_researcher_iterations: 최종화 전 최대 연구 반복 횟수
        enable_critique: 품질 검증을 위한 비평가 서브에이전트 포함 여부
        enable_clarification: STAGE 1 명확화 단계 활성화 여부 (False면 자동으로 STAGE 2로 진행)
        mcp_prompt: 프롬프트에 사용할 선택적 MCP 도구 설명
        config: 선택적 런타임 설정
        checkpointer: 세션 간 상태 영속화를 위한 checkpointer.
                     None이면 기본값으로 MemorySaver 사용 (메모리 내 영속화).
                     영구 저장이 필요하면 SqliteSaver.from_conn_string("checkpoints.db") 사용.
                     State의 files 필드도 checkpointer를 통해 세션 간 보존됨.

    Returns:
        실행 준비가 완료된 컴파일된 LangGraph 에이전트
    """
    from langgraph.checkpoint.memory import MemorySaver

    # 기본 checkpointer 제공
    if checkpointer is None:
        checkpointer = MemorySaver()

    # 프롬프트에 사용할 현재 날짜 가져오기
    date = get_today_str()

    # 서브에이전트 설정 생성
    researcher_config = create_researcher_subagent_config(
        tools=tools,
        date=date,
        mcp_prompt=mcp_prompt,
    )

    compressor_config = create_compressor_subagent_config(date=date)

    # 서브에이전트 리스트 구성
    subagents = [researcher_config, compressor_config]

    # 선택적으로 비평가 추가
    if enable_critique:
        critic_config = create_critic_subagent_config(date=date)
        subagents.append(critic_config)

    # 오케스트레이터 시스템 프롬프트 포맷팅
    orchestrator_prompt = format_orchestrator_prompt(
        date=date,
        max_researcher_iterations=max_researcher_iterations,
        enable_clarification=enable_clarification,
        mcp_prompt=mcp_prompt,
    )

    # DeepAgent 생성
    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=orchestrator_prompt,
        subagents=subagents,
        backend=lambda rt: StateBackend(rt),  # 파일시스템 작업을 위한 StateBackend 사용 (런타임 설정으로 초기화)
        checkpointer=checkpointer,  # 세션 간 상태 영속화
        name="SeparateDeepAgentResearcher",
        debug=True,
        # 미들웨어는 create_deep_agent에 의해 자동으로 설정됩니다:
        # - TodoListMiddleware (계획 수립)
        # - FilesystemMiddleware (파일 작업)
        # - SubAgentMiddleware (동적 할당)
        # - SummarizationMiddleware (컨텍스트 압축)
        # - AnthropicPromptCachingMiddleware (비용 최적화)
        # - PatchToolCallsMiddleware (도구 호출 수정)
    )

    return agent


# 예제 사용 함수
async def run_research(
    question: str,
    tools: list[Any],
    *,
    model: str = "anthropic:claude-sonnet-4-5-20250929",  # provider:model 형식
    thread_id: str = "default",
    max_researcher_iterations: int = 10,
    enable_critique: bool = False,
    enable_clarification: bool = True,
    checkpointer=None,
) -> dict[str, Any]:
    """딥 리서치 에이전트를 사용하여 연구 쿼리를 실행합니다.

    Args:
        question: 사용자의 연구 질문
        tools: 연구에 사용 가능한 도구들
        model: 사용할 LLM 모델
        thread_id: 상태 지속성을 위한 스레드 식별자
        max_researcher_iterations: 최대 연구 반복 횟수
        enable_critique: 품질 검증 단계 활성화 여부
        enable_clarification: 명확화 단계 활성화 여부 (테스트용으로 비활성화 가능)
        checkpointer: 세션 간 상태 영속화용 checkpointer.
                     None이면 기본값 MemorySaver 사용.

    Returns:
        메시지와 파일시스템 상태를 포함하는 최종 에이전트 상태
    """
    # 에이전트 생성
    agent = await create_deep_research_agent(
        tools=tools,
        model=model,
        max_researcher_iterations=max_researcher_iterations,
        enable_critique=enable_critique,
        enable_clarification=enable_clarification,
        checkpointer=checkpointer,
    )

    # 런타임 설정
    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 100,  # 복잡한 멀티에이전트 워크플로우를 위한 높은 제한값
    }

    # 에이전트 실행
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config=config,
    )

    return result

