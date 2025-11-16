"""딥 리서치 에이전트를 위한 스킬 도메인별로 그룹화된 도구 컬렉션입니다.

이 모듈은 도구를 논리적인 스킬 그룹으로 구성하여 전문화된 서브에이전트에
할당할 수 있도록 하며, Claude Skills 하이브리드 패턴을 따릅니다.
"""

from typing import Literal

# 도메인/스킬별 도구 그룹화
WEB_SEARCH_SKILL_TOOLS = ["tavily_search"]
RESEARCH_SKILL_TOOLS = ["tavily_search", "think_tool", "ResearchComplete"]
COMPRESSION_SKILL_TOOLS = []  # LLM만 사용, 특별한 도구 불필요
CRITIQUE_SKILL_TOOLS = []  # 미들웨어의 파일시스템 도구 사용

# MCP 도구 그룹화 (선택적, 런타임에 설정)
ARXIV_SKILL_TOOLS = ["arxiv_search"]  # MCP를 통해 사용 가능한 경우
SERPER_SKILL_TOOLS = ["serper_search"]  # MCP를 통해 사용 가능한 경우


def get_tool_names_for_skill(skill_name: Literal["research", "web", "arxiv", "compression", "critique"]) -> list[str]:
    """특정 스킬 도메인에 대한 도구 이름을 가져옵니다.

    Args:
        skill_name: 스킬 도메인의 이름

    Returns:
        해당 스킬과 연결된 도구 이름 리스트
    """
    skill_mapping = {
        "research": RESEARCH_SKILL_TOOLS,
        "web": WEB_SEARCH_SKILL_TOOLS,
        "arxiv": ARXIV_SKILL_TOOLS,
        "compression": COMPRESSION_SKILL_TOOLS,
        "critique": CRITIQUE_SKILL_TOOLS,
    }

    return skill_mapping.get(skill_name, [])


def filter_tools_by_names(all_tools: list, tool_names: list[str]) -> list:
    """지정된 이름을 가진 도구만 포함하도록 필터링합니다.

    Args:
        all_tools: 사용 가능한 전체 도구 객체 리스트
        tool_names: 포함할 도구의 이름들

    Returns:
        일치하는 이름을 가진 도구만 포함하는 필터링된 리스트
    """
    if not tool_names:
        return []

    filtered = []
    for tool in all_tools:
        tool_name = tool.name if hasattr(tool, "name") else tool.get("name", "")
        if tool_name in tool_names or tool_name in ["think_tool", "ResearchComplete"]:
            filtered.append(tool)

    return filtered
