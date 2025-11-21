"""
커스텀 Hand-off 도구를 활용한 Tool-Based Delegation 예제

이 예제는 langgraph-supervisor-py의 hand_off 패턴을 참고하여
서브에이전트에게 필요한 정보만 선택적으로 전달하는 방법을 보여줍니다.

참고: https://github.com/langchain-ai/langgraph-supervisor-py
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

# ToolRuntime 임포트 (LangChain v1.0+ 표준)
from langchain.tools import ToolRuntime

from langchain.agents import create_agent  # ✨ SubAgentMiddleware 없는 버전!
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend
from deepagents.middleware.filesystem import (
    FilesystemMiddleware,
)  # 파일 시스템 미들웨어
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# 1. State 정의
# ============================================================================


class MainAgentState(TypedDict):
    """메인 에이전트의 상태"""

    messages: Annotated[list[BaseMessage], add_messages]
    files: dict  # 파일 시스템 상태
    user_data: dict  # 사용자 데이터 (민감 정보 포함 가능)
    analysis_results: list[str]  # 분석 결과 누적


# ============================================================================
# 2. 커스텀 Hand-off 도구 생성 함수
# ============================================================================


def create_custom_handoff_tool(
    subagent_name: str,
    allowed_state_keys: list[str],
    description: str,
):
    """
    서브에이전트에게 필요한 정보만 전달하는 hand-off 도구를 생성합니다.

    ✨ ToolRuntime 활용: InjectedState, InjectedToolCallId 대신 단일 매개변수 사용!

    Args:
        subagent_name: 서브에이전트 노드 이름
        allowed_state_keys: 서브에이전트에게 전달할 state 키 리스트
        description: 도구 설명

    Returns:
        BaseTool: 커스텀 hand-off 도구
    """
    tool_name = f"delegate_to_{subagent_name}"

    @tool(tool_name, description=description)
    def handoff_to_subagent(
        instruction: str,
        runtime: ToolRuntime,  # ✨ 단일 매개변수로 state, tool_call_id 등 모두 접근!
    ) -> Command:
        """
        서브에이전트에게 작업을 위임합니다.

        Args:
            instruction: 서브에이전트에게 전달할 구체적인 지시사항
            runtime: 도구 실행 컨텍스트 (자동 주입)
                - runtime.state: 현재 그래프 상태
                - runtime.tool_call_id: 도구 호출 ID
                - runtime.config: RunnableConfig
                - runtime.store: BaseStore (영구 저장소)

        Returns:
            Command: 서브에이전트로 라우팅하는 명령
        """
        # 1. 필요한 정보만 필터링
        filtered_state = {
            k: v for k, v in runtime.state.items() if k in allowed_state_keys
        }

        # 2. instruction을 새로운 메시지로 추가
        filtered_state["messages"] = [HumanMessage(content=instruction)]

        # 3. 서브에이전트로 라우팅
        tool_message = ToolMessage(
            content=f"Successfully delegated to {subagent_name}",
            name=tool_name,
            tool_call_id=runtime.tool_call_id,  # ✨ runtime에서 직접 접근
        )

        return Command(
            goto=subagent_name,
            update={
                **filtered_state,
                "messages": runtime.state["messages"] + [tool_message],
            },
        )

    return handoff_to_subagent


# ============================================================================
# 3. 서브에이전트 생성
# ============================================================================

# 프로젝트 설정
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def create_composite_backend(runtime):
    """CompositeBackend 팩토리 함수"""
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/workspace/": FilesystemBackend(root_dir=WORKSPACE_DIR, virtual_mode=True)
        },
    )


# 3-1. 데이터 분석 서브에이전트
def create_data_analyst_agent(model):
    """
    데이터 분석 전문 서브에이전트

    - 접근 가능: files (파일 시스템)
    - 접근 불가: user_data (민감 정보 차단!)

    ⚠️ create_agent 사용: SubAgentMiddleware 없이 순수 에이전트 생성
    """
    system_prompt = """
You are a specialized Data Analyst agent.

Your responsibilities:
1. Analyze data from files in the filesystem
2. Generate insights and reports
3. Save analysis results to /workspace/analysis/

IMPORTANT:
- You only have access to the filesystem (files)
- You do NOT have access to user_data or other sensitive information
- Focus on data analysis tasks only
"""

    # ✨ create_agent 사용 (SubAgentMiddleware 없음!)
    return create_agent(
        model,
        tools=[],
        system_prompt=system_prompt,
        middleware=[FilesystemMiddleware(backend=create_composite_backend)],
        name="data_analyst",
    )


# 3-2. 연구 서브에이전트
def create_researcher_agent(model):
    """
    연구 전문 서브에이전트

    - 접근 가능: analysis_results (이전 분석 결과)
    - 접근 불가: files, user_data
    """
    system_prompt = """
You are a specialized Research agent.

Your responsibilities:
1. Review previous analysis results
2. Conduct additional research if needed
3. Synthesize findings into comprehensive reports

IMPORTANT:
- You have access to analysis_results from other agents
- You do NOT have direct file system access
- Focus on research and synthesis tasks
"""

    return create_deep_agent(
        model,
        tools=[],
        system_prompt=system_prompt,
        backend=create_composite_backend,
        name="researcher",
    )


# ============================================================================
# 4. 메인 에이전트 생성 (Hand-off 도구 포함)
# ============================================================================


def create_main_agent_with_handoff(model):
    """
    커스텀 hand-off 도구를 가진 메인 에이전트 생성
    """

    # Hand-off 도구 생성
    delegate_to_analyst = create_custom_handoff_tool(
        subagent_name="data_analyst",
        allowed_state_keys=["files"],  # 파일 시스템만 전달!
        description=(
            "Delegate data analysis tasks to the Data Analyst agent. "
            "Use this when you need to analyze data from files. "
            "The analyst ONLY has access to files, not user_data."
        ),
    )

    delegate_to_researcher = create_custom_handoff_tool(
        subagent_name="researcher",
        allowed_state_keys=["analysis_results"],  # 분석 결과만 전달!
        description=(
            "Delegate research tasks to the Research agent. "
            "Use this when you need to synthesize or expand on analysis results. "
            "The researcher ONLY has access to previous analysis results."
        ),
    )

    system_prompt = """
You are the Main Orchestrator agent.

Your responsibilities:
1. Understand user requests
2. Delegate tasks to specialized sub-agents
3. Coordinate and synthesize results

Available sub-agents:
- delegate_to_data_analyst: For data analysis (has file access)
- delegate_to_researcher: For research synthesis (has analysis results access)

IMPORTANT:
- Each sub-agent has LIMITED access to specific information
- Choose the right sub-agent based on the task
- Data Analyst: Can access files only
- Researcher: Can access analysis results only
"""

    # 메인 에이전트 생성 (hand-off 도구 포함)
    return create_deep_agent(
        model,
        tools=[delegate_to_analyst, delegate_to_researcher],
        system_prompt=system_prompt,
        backend=create_composite_backend,
        name="main_orchestrator",
    )


# ============================================================================
# 5. StateGraph 구성
# ============================================================================


def create_multi_agent_workflow(model):
    """
    Tool-Based Delegation을 사용하는 멀티 에이전트 워크플로우
    """

    # 서브에이전트들 생성
    main_agent = create_main_agent_with_handoff(model)
    data_analyst = create_data_analyst_agent(model)
    researcher = create_researcher_agent(model)

    # StateGraph 생성
    workflow = StateGraph(state_schema=MainAgentState)

    # 노드 추가
    workflow.add_node("main_orchestrator", main_agent)
    workflow.add_node("data_analyst", data_analyst)
    workflow.add_node("researcher", researcher)

    # 엣지 설정
    workflow.add_edge(START, "main_orchestrator")

    # 서브에이전트 완료 후 메인으로 복귀
    workflow.add_edge("data_analyst", "main_orchestrator")
    workflow.add_edge("researcher", "main_orchestrator")

    # 컴파일
    return workflow.compile(debug=True)


# ============================================================================
# 6. 사용 예제
# ============================================================================


def main():
    # 모델 생성
    model = ChatOpenAI(model="gpt-4.1", temperature=0)

    # 워크플로우 생성
    app = create_multi_agent_workflow(model)

    # 초기 상태
    initial_state = {
        "messages": [
            HumanMessage(
                content="Analyze the sales data in /workspace/data/sales.csv and provide insights"
            )
        ],
        "files": {},  # 파일 시스템 상태
        "user_data": {  # 민감 정보
            "user_id": "12345",
            "email": "user@example.com",
            "api_key": "secret_key_xxx",
        },
        "analysis_results": [],
    }

    # 실행
    result = app.invoke(initial_state)

    print("=" * 80)
    print("최종 결과:")
    print("=" * 80)
    print(f"Messages: {len(result['messages'])} messages")
    print(f"Analysis Results: {result.get('analysis_results', [])}")


if __name__ == "__main__":
    main()
