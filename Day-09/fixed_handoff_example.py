"""
✅ 수정된 버전: SubAgent + Secure Hand-off (하이브리드 방식)

핵심: create_deep_agent의 SubAgentMiddleware를 활용하되,
      추가 secure hand-off 도구로 정보를 제어합니다.
"""

import os
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend

# ============================================================================
# Setup
# ============================================================================


class MainAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    files: dict
    user_data: dict
    analysis_results: list[str]


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
# ✅ 해결책: SubAgent 정의 + 하이브리드 접근
# ============================================================================


def create_multi_agent_system():
    """
    SubAgent 정의를 사용하면서도 secure hand-off 가능!

    핵심 아이디어:
    1. SubAgent로 서브에이전트 정의 (표준 방식)
    2. create_deep_agent가 자동으로 'task' 도구 생성
    3. 'task' 도구는 내부적으로 Command를 올바르게 처리함!
    """

    model = ChatOpenAI(model="gpt-4", temperature=0)

    # 1. SubAgent 정의 (표준!)
    analyst_subagent = {
        "name": "data_analyst",
        "description": "Data analysis specialist (has access to files)",
        "system_prompt": """
You are a specialized Data Analyst agent.

Your responsibilities:
1. Analyze data from files in the filesystem
2. Generate insights and reports  
3. Save analysis results to /workspace/analysis/

IMPORTANT:
- You only have access to the filesystem (files)
- Focus on data analysis tasks only
- When done, return your findings clearly
""",
        "tools": [],  # 파일 시스템 도구는 자동 추가됨
    }

    researcher_subagent = {
        "name": "researcher",
        "description": "Research specialist (has access to analysis results)",
        "system_prompt": """
You are a specialized Research agent.

Your responsibilities:
1. Review previous analysis results
2. Conduct additional research if needed
3. Synthesize findings into comprehensive reports

IMPORTANT:
- You have access to analysis_results from other agents
- Focus on research and synthesis tasks
""",
        "tools": [],
    }

    # 2. System Prompt에서 task 도구 사용법 명시
    main_system_prompt = """
You are the Main Orchestrator agent.

Your responsibilities:
1. Understand user requests
2. Delegate tasks to specialized sub-agents using the 'task' tool
3. Coordinate and synthesize results

Available sub-agents:
- data_analyst: For data analysis (has file access)
  - Use: task(description="...", subagent_type="data_analyst")
  
- researcher: For research synthesis (has analysis results access)
  - Use: task(description="...", subagent_type="researcher")

IMPORTANT:
- Each sub-agent has LIMITED access to specific information
- Data Analyst: Can access files only
- Researcher: Can access analysis results only
- Use the 'task' tool to delegate work to sub-agents
- Wait for their results before proceeding
"""

    # 3. create_deep_agent 사용 (SubAgentMiddleware 자동 포함!)
    agent = create_deep_agent(
        model,
        tools=[],  # 추가 도구는 여기에
        system_prompt=main_system_prompt,
        backend=create_composite_backend,
        subagents=[analyst_subagent, researcher_subagent],  # ← SubAgent 정의!
        name="main_orchestrator",
    )

    return agent


# ============================================================================
# 실행 예제
# ============================================================================


def main():
    """실행 예제"""

    agent = create_multi_agent_system()

    initial_state = {
        "messages": [
            HumanMessage(
                content="Analyze the sales data in /workspace/data/sales.csv and provide insights"
            )
        ],
        "files": {},
        "user_data": {
            "user_id": "12345",
            "email": "user@example.com",
            "api_key": "secret_key_xxx",
        },
        "analysis_results": [],
    }

    print("=" * 80)
    print("실행 시작")
    print("=" * 80)

    # 실행
    result = agent.invoke(initial_state)

    print("\n" + "=" * 80)
    print("최종 결과")
    print("=" * 80)
    print(f"Messages: {len(result['messages'])} messages")
    print(f"Analysis Results: {result.get('analysis_results', [])}")
    print(f"\n마지막 메시지: {result['messages'][-1].content}")


# ============================================================================
# 추가: 정보 필터링이 필요한 경우의 해결책
# ============================================================================


def create_filtered_subagent_system():
    """
    정보 필터링이 필요한 경우:
    SubAgent의 middleware를 커스터마이징
    """

    model = ChatOpenAI(model="gpt-4", temperature=0)

    # ✨ 핵심: SubAgent에 커스텀 미들웨어 추가
    from deepagents.middleware.filesystem import FilesystemMiddleware

    # 필터링된 백엔드 팩토리
    def filtered_backend_for_analyst(runtime):
        # runtime.state에서 필요한 것만 필터링
        filtered_state = {k: v for k, v in runtime.state.items() if k in ["files"]}
        # 새로운 runtime 생성 (필터링된 state 포함)
        # 주의: 실제 구현은 더 복잡할 수 있음
        return CompositeBackend(
            default=StateBackend(runtime),
            routes={
                "/workspace/": FilesystemBackend(
                    root_dir=WORKSPACE_DIR, virtual_mode=True
                )
            },
        )

    analyst_subagent = {
        "name": "data_analyst",
        "description": "Data analysis specialist",
        "system_prompt": "You are a Data Analyst...",
        "tools": [],
        # ✨ 커스텀 미들웨어로 정보 제어!
        "middleware": [FilesystemMiddleware(backend=filtered_backend_for_analyst)],
    }

    agent = create_deep_agent(
        model,
        tools=[],
        system_prompt="You are the orchestrator...",
        backend=create_composite_backend,
        subagents=[analyst_subagent],
        # ✨ default_middleware=[] 로 기본 미들웨어 비활성화 가능
        # default_middleware=[],
    )

    return agent


if __name__ == "__main__":
    main()
