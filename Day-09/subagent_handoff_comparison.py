"""
SubAgent 정의 + Tool Hand-off: 3가지 접근 방식 비교

사용자 질문: "SubAgent로 정의하면서도 Tool hand-off로 정보를 제어할 수 있나?"
답변: "네, 가능합니다! 여러 방법이 있습니다."
"""

import os
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.types import Command

from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.subagents import SubAgentMiddleware

# ============================================================================
# State 정의
# ============================================================================


class MainAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    files: dict
    user_data: dict  # 민감 정보
    analysis_results: list[str]


# ============================================================================
# Backend 설정
# ============================================================================

PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def create_composite_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/workspace/": FilesystemBackend(root_dir=WORKSPACE_DIR, virtual_mode=True)
        },
    )


# ============================================================================
# 방법 1: 완전 수동 구현 (현재 방식)
# ============================================================================


def approach_1_manual():
    """
    ✅ 장점: 완벽한 제어, 명시적
    ❌ 단점: 설정이 복잡, SubAgent 정의 사용 불가
    """

    def create_custom_handoff_tool(
        subagent_name: str, allowed_keys: list[str], description: str
    ):
        @tool(f"delegate_to_{subagent_name}", description=description)
        def handoff(instruction: str, runtime: ToolRuntime) -> Command:
            filtered_state = {
                k: v for k, v in runtime.state.items() if k in allowed_keys
            }
            filtered_state["messages"] = [HumanMessage(content=instruction)]

            tool_message = ToolMessage(
                content=f"Delegated to {subagent_name}",
                name=f"delegate_to_{subagent_name}",
                tool_call_id=runtime.tool_call_id,
            )

            return Command(
                goto=subagent_name,
                update={
                    **filtered_state,
                    "messages": runtime.state["messages"] + [tool_message],
                },
            )

        return handoff

    # 서브에이전트들을 개별 생성
    model = ChatOpenAI(model="gpt-4")

    analyst = create_agent(
        model,
        tools=[],
        system_prompt="You are a Data Analyst...",
        middleware=[FilesystemMiddleware(backend=create_composite_backend)],
        name="data_analyst",
    )

    # Hand-off 도구 생성
    delegate_to_analyst = create_custom_handoff_tool(
        "data_analyst",
        ["files"],  # files만 전달
        "Delegate to data analyst",
    )

    # 메인 에이전트
    main_agent = create_agent(
        model,
        tools=[delegate_to_analyst],
        system_prompt="You are the orchestrator...",
        middleware=[FilesystemMiddleware(backend=create_composite_backend)],
    )

    # 그래프 구성
    workflow = StateGraph(state_schema=MainAgentState)
    workflow.add_node("main", main_agent)
    workflow.add_node("data_analyst", analyst)
    workflow.add_edge(START, "main")
    workflow.add_edge("data_analyst", "main")

    return workflow.compile()


# ============================================================================
# 방법 2: SubAgent + 커스텀 SubAgentMiddleware
# ============================================================================


def approach_2_custom_subagent_middleware():
    """
    ✅ 장점: SubAgent 정의 사용, 정보 제어 가능
    ⚠️ 중간: SubAgentMiddleware 커스터마이징 필요

    핵심: SubAgentMiddleware의 내부 로직을 수정하여 정보 필터링
    """

    from langchain.agents.middleware.types import (
        AgentMiddleware,
        ModelRequest,
        ModelResponse,
    )
    from typing import Callable, Awaitable

    class FilteringSubAgentMiddleware(SubAgentMiddleware):
        """정보 필터링 기능이 추가된 SubAgentMiddleware"""

        def __init__(self, agent_filters: dict[str, list[str]], **kwargs):
            """
            Args:
                agent_filters: 에이전트별 허용 state 키
                    예: {"analyst": ["files"], "researcher": ["analysis_results"]}
            """
            super().__init__(**kwargs)
            self.agent_filters = agent_filters

        # _create_task_tool을 오버라이드하여 필터링 로직 추가
        # (실제 구현은 복잡하므로 개념만 표시)

    model = ChatOpenAI(model="gpt-4")

    # SubAgent 정의 (표준 방식!)
    analyst_config = {
        "name": "analyst",
        "description": "Data analysis agent",
        "system_prompt": "You are a Data Analyst...",
        "tools": [],
    }

    researcher_config = {
        "name": "researcher",
        "description": "Research agent",
        "system_prompt": "You are a Researcher...",
        "tools": [],
    }

    # 커스텀 SubAgentMiddleware 사용
    custom_subagent_middleware = FilteringSubAgentMiddleware(
        default_model=model,
        default_tools=[],
        subagents=[analyst_config, researcher_config],
        agent_filters={
            "analyst": ["files"],  # analyst는 files만
            "researcher": ["analysis_results"],  # researcher는 결과만
        },
        default_middleware=[FilesystemMiddleware(backend=create_composite_backend)],
    )

    # create_deep_agent 사용 (커스텀 미들웨어 주입!)
    deep_agent = create_deep_agent(
        model,
        tools=[],
        system_prompt="You are the orchestrator...",
        backend=create_composite_backend,
        middleware=[custom_subagent_middleware],  # ← 커스텀 미들웨어!
    )

    return deep_agent


# ============================================================================
# 방법 3: SubAgent + 별도 Hand-off 도구 (하이브리드)
# ============================================================================


def approach_3_hybrid():
    """
    ✅ 장점: SubAgent 정의 사용, 유연성 최고
    ⚠️ 주의: 두 가지 위임 방식 혼재 (task vs delegate_to_*)

    전략:
    1. SubAgent로 서브에이전트 정의 (표준 방식)
    2. 메인 에이전트에 추가 hand-off 도구 제공
    3. System Prompt로 어떤 도구를 쓸지 명시
    """

    def create_custom_handoff_tool(
        subagent_name: str, allowed_keys: list[str], description: str
    ):
        @tool(f"delegate_secure_{subagent_name}", description=description)
        def handoff(instruction: str, runtime: ToolRuntime) -> Command:
            # 필터링된 state만 전달
            filtered_state = {
                k: v for k, v in runtime.state.items() if k in allowed_keys
            }
            filtered_state["messages"] = [HumanMessage(content=instruction)]

            return Command(
                goto=subagent_name,
                update=filtered_state,
            )

        return handoff

    model = ChatOpenAI(model="gpt-4")

    # SubAgent 정의 (표준!)
    analyst_config = {
        "name": "analyst",
        "description": "Data analysis agent (accessible via task or delegate_secure_analyst)",
        "system_prompt": "You are a Data Analyst...",
        "tools": [],
    }

    # 커스텀 hand-off 도구 생성
    delegate_secure_analyst = create_custom_handoff_tool(
        "analyst",
        ["files"],
        "Securely delegate to analyst with limited information (files only)",
    )

    # System Prompt에서 두 가지 옵션 설명
    system_prompt = """
You are the Main Orchestrator.

You have TWO ways to delegate to sub-agents:

1. **task** tool (standard):
   - Passes ALL state to sub-agent
   - Use when sub-agent needs full context
   
2. **delegate_secure_*** tools:
   - Passes FILTERED state (only specific keys)
   - Use when dealing with sensitive information
   - Example: delegate_secure_analyst only passes 'files', NOT 'user_data'

Choose wisely based on security requirements!
"""

    # create_deep_agent 사용 (subagents + 커스텀 도구)
    deep_agent = create_deep_agent(
        model,
        tools=[delegate_secure_analyst],  # ← 추가 hand-off 도구!
        system_prompt=system_prompt,
        backend=create_composite_backend,
        subagents=[analyst_config],  # ← SubAgent 정의!
    )

    return deep_agent


# ============================================================================
# 비교 및 권장 사항
# ============================================================================


def comparison():
    print("=" * 80)
    print("SubAgent + Tool Hand-off: 3가지 접근 방식 비교")
    print("=" * 80)

    print("\n방법 1: 완전 수동 구현")
    print("-" * 80)
    print("설명: create_agent + 수동 그래프 구성")
    print("\n장점:")
    print("  ✅ 완벽한 제어")
    print("  ✅ 정보 필터링 완벽")
    print("  ✅ 명시적")
    print("\n단점:")
    print("  ❌ 설정 복잡")
    print("  ❌ SubAgent 정의 사용 불가")
    print("  ❌ 반복적인 코드")
    print("\n적합한 경우:")
    print("  - 완전한 커스터마이징 필요")
    print("  - 복잡한 라우팅 로직")
    print("  - 프로덕션 환경")

    print("\n방법 2: SubAgent + 커스텀 SubAgentMiddleware")
    print("-" * 80)
    print("설명: SubAgentMiddleware를 상속하여 필터링 로직 추가")
    print("\n장점:")
    print("  ✅ SubAgent 정의 사용 (표준)")
    print("  ✅ 정보 필터링 가능")
    print("  ✅ create_deep_agent 활용")
    print("\n단점:")
    print("  ❌ SubAgentMiddleware 커스터마이징 복잡")
    print("  ❌ 내부 구조 이해 필요")
    print("\n적합한 경우:")
    print("  - SubAgent 정의 표준 사용")
    print("  - 일관된 필터링 정책")
    print("  - 라이브러리 수준 커스터마이징")

    print("\n방법 3: 하이브리드 (SubAgent + 별도 Hand-off)")
    print("-" * 80)
    print("설명: SubAgent 정의 + 추가 커스텀 hand-off 도구")
    print("\n장점:")
    print("  ✅ SubAgent 정의 사용")
    print("  ✅ 유연성 최고")
    print("  ✅ 두 가지 위임 방식 선택 가능")
    print("  ✅ 구현 간단")
    print("\n단점:")
    print("  ⚠️ 두 가지 도구 혼재 (혼란 가능)")
    print("  ⚠️ System Prompt 명확화 필요")
    print("\n적합한 경우:")
    print("  - 빠른 프로토타입")
    print("  - 일부만 정보 제어 필요")
    print("  - 점진적 마이그레이션")

    print("\n" + "=" * 80)
    print("🎯 권장 사항")
    print("=" * 80)
    print("""
상황별 권장:
- 빠른 개발: 방법 3 (하이브리드) ⭐
- 프로덕션/보안: 방법 1 (수동) ⭐
- 표준 준수: 방법 2 (커스텀 미들웨어)
- 복잡한 워크플로우: 방법 1 (수동)

대부분의 경우: **방법 3 (하이브리드)** 추천!
- SubAgent 정의의 편리함 유지
- 필요한 곳만 secure hand-off 사용
- 점진적으로 방법 1 또는 2로 전환 가능
""")


# ============================================================================
# 실제 사용 예제: 방법 3 (하이브리드)
# ============================================================================


def example_hybrid_usage():
    """방법 3 (하이브리드) 실제 사용 예제"""

    model = ChatOpenAI(model="gpt-4", temperature=0)

    # 1. 커스텀 hand-off 도구
    def create_secure_handoff(
        subagent_name: str, allowed_keys: list[str], description: str
    ):
        @tool(f"delegate_secure_{subagent_name}", description=description)
        def handoff(instruction: str, runtime: ToolRuntime) -> Command:
            filtered_state = {
                k: v for k, v in runtime.state.items() if k in allowed_keys
            }
            filtered_state["messages"] = [HumanMessage(content=instruction)]
            return Command(goto=subagent_name, update=filtered_state)

        return handoff

    # 2. SubAgent 정의
    analyst_subagent = {
        "name": "analyst",
        "description": "Data analysis specialist",
        "system_prompt": "You are a Data Analyst. Focus on data analysis from files.",
        "tools": [],
    }

    # 3. Secure hand-off 도구 생성
    delegate_secure_analyst = create_secure_handoff(
        "analyst",
        ["files"],  # files만 전달!
        "Securely delegate to analyst (files only, no user_data)",
    )

    # 4. Main agent 생성
    system_prompt = """
You are the Main Orchestrator.

Available delegation tools:
1. task(description, subagent_type="analyst"): 
   - Standard delegation (passes all state)
   - Use for normal operations
   
2. delegate_secure_analyst(instruction):
   - Secure delegation (files only, NO user_data)
   - Use when handling sensitive user information
   
IMPORTANT: When user_data is present, ALWAYS use delegate_secure_* tools!
"""

    agent = create_deep_agent(
        model,
        tools=[delegate_secure_analyst],  # 커스텀 도구 추가
        system_prompt=system_prompt,
        backend=create_composite_backend,
        subagents=[analyst_subagent],  # SubAgent 정의
    )

    # 5. 사용
    initial_state = {
        "messages": [HumanMessage(content="Analyze data without exposing user info")],
        "files": {"data.csv": "..."},
        "user_data": {"api_key": "secret_xxx"},  # 민감!
        "analysis_results": [],
    }

    # 에이전트는 user_data가 있으므로 delegate_secure_analyst를 사용할 것임
    result = agent.invoke(initial_state)

    return result


if __name__ == "__main__":
    comparison()

    print("\n" + "=" * 80)
    print("실제 사용 예제 실행")
    print("=" * 80)
    # example_hybrid_usage()  # 실제 실행은 주석 처리
