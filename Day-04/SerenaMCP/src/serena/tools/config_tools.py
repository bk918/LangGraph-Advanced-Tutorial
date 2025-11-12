"""
serena/tools/config_tools.py - Serena 구성 관리 도구

이 파일은 Serena 에이전트의 동작 환경과 설정을 관리하는 도구들을 포함합니다.
프로젝트 활성화, 모드 전환, 현재 설정 조회 등의 기능을 제공하여
사용자가 동적으로 에이전트의 동작을 제어할 수 있도록 합니다.

주요 클래스:
- ActivateProjectTool: 지정된 프로젝트를 활성화하고, 관련 환경을 설정합니다.
- RemoveProjectTool: Serena 설정에서 프로젝트를 제거합니다.
- SwitchModesTool: 에이전트의 동작 모드(예: 'planning', 'editing')를 전환합니다.
- GetCurrentConfigTool: 에이전트의 현재 전체 구성 상태를 조회합니다.

아키텍처 노트:
- 각 도구는 `Tool` 베이스 클래스를 상속받아 일관된 인터페이스를 제공합니다.
- `ToolMarkerDoesNotRequireActiveProject`와 같은 마커 클래스를 사용하여, 특정 도구가
  프로젝트 활성화 없이도 사용 가능함을 명시합니다.
- `ToolMarkerOptional` 마커는 기본적으로 비활성화되어 있지만, 사용자가 필요에 따라
  명시적으로 활성화할 수 있는 선택적 도구임을 나타냅니다.
"""

import json

from serena.config.context_mode import SerenaAgentMode
from serena.tools import Tool, ToolMarkerDoesNotRequireActiveProject, ToolMarkerOptional


class ActivateProjectTool(Tool, ToolMarkerDoesNotRequireActiveProject):
    """
    지정된 이름이나 경로의 프로젝트를 활성화합니다.

    이 도구는 Serena가 특정 코드베이스에 대해 작업할 수 있도록 준비시킵니다.
    새로운 경로가 제공되면 프로젝트를 자동으로 생성하고 설정하며,
    기존에 등록된 프로젝트 이름이 제공되면 해당 프로젝트를 활성화합니다.
    """

    def apply(self, project: str) -> str:
        """
        프로젝트를 활성화하고 관련 정보를 반환합니다.

        Args:
            project (str): 활성화할 프로젝트의 이름 또는 디렉토리 경로.

        Returns:
            str: 프로젝트 활성화 결과, 생성 여부, 초기 프롬프트, 사용 가능한 메모리 및 도구 목록 등
                 작업 시작에 필요한 종합적인 정보를 담은 문자열.
        """
        active_project = self.agent.activate_project_from_path_or_name(project)
        if active_project.is_newly_created:
            result_str = (
                f"'{active_project.project_name}' 이름의 새 프로젝트를 생성하고 활성화했습니다. 위치: {active_project.project_root}, 언어: {active_project.project_config.language.value}. "
                "이후에는 이름으로 이 프로젝트를 활성화할 수 있습니다.\n"
                f"프로젝트의 Serena 설정 파일은 {active_project.path_to_project_yml()}에 있습니다. 특히 프로젝트 이름과 초기 프롬프트를 수정할 수 있습니다."
            )
        else:
            result_str = f"기존 프로젝트 '{active_project.project_name}'을(를) 활성화했습니다. 위치: {active_project.project_root}, 언어: {active_project.project_config.language.value}"

        if active_project.project_config.initial_prompt:
            result_str += f"\n추가 프로젝트 정보:\n {active_project.project_config.initial_prompt}"
        result_str += (
            f"\n사용 가능한 메모리:\n {json.dumps(list(self.memories_manager.list_memories()))}"
            + "이 메모리들을 직접 읽어서는 안 되며, 작업에 필요할 경우 나중에 `read_memory` 도구를 사용해야 합니다."
        )
        result_str += f"\n사용 가능한 도구:\n {json.dumps(self.agent.get_active_tool_names())}"
        return result_str


class RemoveProjectTool(Tool, ToolMarkerDoesNotRequireActiveProject, ToolMarkerOptional):
    """
    Serena 설정에서 프로젝트를 제거합니다.

    이 도구는 등록된 프로젝트를 구성 파일에서 영구적으로 삭제합니다.
    선택적 도구이므로, 기본적으로 비활성화되어 있으며 필요 시 명시적으로 활성화해야 합니다.
    """

    def apply(self, project_name: str) -> str:
        """
        지정된 이름의 프로젝트를 Serena 구성에서 제거합니다.

        Args:
            project_name (str): 제거할 프로젝트의 이름.

        Returns:
            str: 프로젝트 제거 완료를 알리는 확인 메시지.
        """
        self.agent.serena_config.remove_project(project_name)
        return f"'{project_name}' 프로젝트를 설정에서 성공적으로 제거했습니다."


class SwitchModesTool(Tool, ToolMarkerOptional):
    """
    에이전트의 동작 모드를 전환합니다.

    이 도구를 사용하여 특정 작업에 맞게 에이전트의 동작 방식(예: 프롬프트, 사용 가능 도구)을 동적으로 변경할 수 있습니다.
    선택적 도구이므로, 기본적으로 비활성화되어 있으며 필요 시 명시적으로 활성화해야 합니다.

    사용 가능한 모드 예시:
    - `planning`: 분석 및 계획 작업에 최적화됩니다.
    - `editing`: 직접적인 코드 수정 작업에 최적화됩니다.
    - `interactive`: 대화형 상호작용에 적합합니다.
    """

    def apply(self, modes: list[str]) -> str:
        """
        제공된 모드 목록을 활성화합니다.

        Args:
            modes (list[str]): 활성화할 모드 이름의 리스트. 예: ["editing", "interactive"].

        Returns:
            str: 모드 전환 결과와 현재 활성화된 도구 목록을 포함하는 정보 메시지.
        """
        mode_instances = [SerenaAgentMode.load(mode) for mode in modes]
        self.agent.set_modes(mode_instances)

        result_str = f"모드 활성화 성공: {', '.join([mode.name for mode in mode_instances])}" + "\n"
        result_str += "\n".join([mode_instance.prompt for mode_instance in mode_instances]) + "\n"
        result_str += f"현재 활성 도구: {', '.join(self.agent.get_active_tool_names())}"
        return result_str


class GetCurrentConfigTool(Tool):
    """
    에이전트의 현재 구성 상태를 조회합니다.

    이 도구는 디버깅이나 현재 에이전트의 상태를 파악하는 데 유용합니다.
    활성 프로젝트, 사용 가능한 모든 프로젝트, 활성화된 도구, 컨텍스트, 모드 등
    에이전트의 전체 설정 상태를 상세히 출력합니다.
    """

    def apply(self) -> str:
        """
        에이전트의 현재 구성 상태에 대한 상세한 개요를 반환합니다.

        Returns:
            str: 에이전트의 전체 구성 상태(활성 프로젝트, 사용 가능한 프로젝트, 도구, 컨텍스트, 모드 등)를
                 담은 상세한 텍스트.
        """
        return self.agent.get_current_config_overview()