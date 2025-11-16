"""연구자 스킬 서브에이전트 설정입니다."""

from typing import Any

from prompts.researcher import RESEARCHER_SYSTEM_PROMPT


def create_researcher_subagent_config(
    tools: list[Any],
    date: str,
    mcp_prompt: str = "",
) -> dict:
    """DeepAgent를 위한 연구자 서브에이전트 설정을 생성합니다.

    Args:
        tools: 연구자에게 제공할 도구 객체 리스트
        date: 프롬프트 포맷팅을 위한 현재 날짜 문자열
        mcp_prompt: 선택적 MCP 도구 설명

    Returns:
        DeepAgent용 SubAgent 설정 딕셔너리
    """
    # 연구자를 위한 도구 필터링: tavily_search, think_tool, ResearchComplete
    researcher_tool_names = {"tavily_search", "think_tool", "ResearchComplete"}
    researcher_tools = [t for t in tools if getattr(t, "name", None) in researcher_tool_names]

    return {
        "name": "researcher",
        "description": (
            """특정 주제에 대한 집중적이고 심도 있는 연구를 수행하는 전문 연구 에이전트입니다.
            특정 하위 질문에 대한 포괄적인 정보를 수집해야 할 때 이 에이전트를 사용하세요. 
            연구자는 웹 검색을 사용하고, 결과를 파일시스템에 저장하며, 완료를 알립니다.
            최적 용도: 특정 사실 조사, 출처 수집, 복잡한 주제의 단일 차원 탐색."""
        ),
        "system_prompt": RESEARCHER_SYSTEM_PROMPT.format(
            date=date,
            mcp_prompt=mcp_prompt if mcp_prompt else "",
        ),
        "tools": researcher_tools,
        # 연구자는 기본 미들웨어를 상속합니다 (TodoList, Filesystem 등)
    }
