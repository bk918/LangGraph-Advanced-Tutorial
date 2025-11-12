"""
serena/tools/workflow_tools.py - 에이전트 워크플로우 지원 도구

이 파일은 Serena 에이전트의 일반적인 작업 흐름을 지원하고 안내하는 도구들을 포함합니다.
이 도구들은 에이전트가 작업을 체계적으로 수행하고, 스스로의 진행 상황을 평가하며,
사용자와의 상호작용을 원활하게 하도록 돕습니다.

주요 클래스:
- CheckOnboardingPerformedTool: 프로젝트 온보딩이 수행되었는지 확인합니다.
- OnboardingTool: 프로젝트 구조와 주요 작업을 식별하는 온보딩 프로세스를 시작합니다.
- ThinkAboutCollectedInformationTool: 정보 수집 단계 후, 수집된 정보의 완전성과 관련성을 평가하도록 유도하는 "생각" 도구입니다.
- ThinkAboutTaskAdherenceTool: 작업 수행 중, 현재 진행 상황이 원래의 목표에 부합하는지 검토하도록 합니다.
- ThinkAboutWhetherYouAreDoneTool: 작업 완료 선언 전, 정말로 모든 요구사항이 충족되었는지 최종 검토를 하도록 합니다.
- SummarizeChangesTool: 작업 완료 후, 코드베이스에 적용된 변경 사항을 요약하도록 지침을 제공합니다.
- PrepareForNewConversationTool: 대화의 컨텍스트가 너무 길어졌을 때, 새로운 대화를 시작하기 위해 현재 상태를 요약하고 준비하도록 돕습니다.
- InitialInstructionsTool: 시스템 프롬프트를 설정할 수 없는 클라이언트 환경에서, 에이전트가 자신의 사용법에 대한 초기 지침을 얻기 위해 사용합니다.

아키텍처 노트:
- 이 도구들은 직접적인 코드나 파일 조작보다는, 에이전트의 "메타인지"를 자극하는 역할을 합니다.
- 대부분의 `apply` 메서드는 `PromptFactory`를 호출하여, 특정 상황에 맞는 지침이나 질문이 담긴 프롬프트를 생성하고 반환합니다.
- 이를 통해 에이전트의 행동 패턴을 특정 워크플로우에 맞게 유도하고, 보다 신뢰성 높은 결과를 얻을 수 있습니다.
"""

import json
import platform

from serena.tools import Tool, ToolMarkerDoesNotRequireActiveProject, ToolMarkerOptional


class CheckOnboardingPerformedTool(Tool):
    """
    프로젝트 온보딩이 이미 수행되었는지 확인합니다.

    에이전트가 프로젝트 작업을 시작하기 전에 이 도구를 호출하여,
    프로젝트에 대한 사전 정보(메모리)가 있는지 확인해야 합니다.
    """

    def apply(self) -> str:
        """
        프로젝트 온보딩 수행 여부를 확인합니다.

        프로젝트 활성화 후, 그리고 초기 지침 도구를 호출한 후에 항상 이 도구를 호출해야 합니다.

        Returns:
            str: 온보딩 수행 여부와 사용 가능한 메모리 목록을 포함한 결과 메시지.
        """
        from .memory_tools import ListMemoriesTool

        list_memories_tool = self.agent.get_tool(ListMemoriesTool)
        memories = json.loads(list_memories_tool.apply())
        if not memories:
            return (
                "온보딩이 아직 수행되지 않았습니다 (사용 가능한 메모리 없음). "
                + "작업을 계속하기 전에 `onboarding` 도구를 호출하여 온보딩을 수행해야 합니다."
            )
        else:
            return f"""온보딩이 이미 수행되었습니다. 아래는 사용 가능한 메모리 목록입니다.
            이 메모리들을 즉시 읽지 말고, 현재 작업에 필요한 경우 나중에 읽을 수 있다는 점만 기억해두세요.
            일부 메모리는 이전 대화를 기반으로 할 수 있고, 다른 메모리는 현재 프로젝트에 대한 일반적인 정보일 수 있습니다.
            메모리 이름을 기반으로 필요한 것을 판단할 수 있어야 합니다.
            
            {memories}"""


class OnboardingTool(Tool):
    """
    프로젝트 온보딩을 수행합니다.

    프로젝트 구조와 테스트, 빌드 등 필수 작업을 식별하는 프로세스를 시작합니다.
    """

    def apply(self) -> str:
        """
        온보딩이 아직 수행되지 않은 경우 이 도구를 호출합니다.
        대화당 최대 한 번만 호출해야 합니다.

        Returns:
            str: 온보딩 정보 생성을 위한 지침.
        """
        system = platform.system()
        return self.prompt_factory.create_onboarding_prompt(system=system)


class ThinkAboutCollectedInformationTool(Tool):
    """
    수집된 정보의 완전성에 대해 숙고하는 "생각" 도구입니다.
    """

    def apply(self) -> str:
        """
        수집된 정보가 충분하고 관련성이 있는지 생각합니다.

        `find_symbol`, `find_referencing_symbols`, `search_for_pattern`, `read_file` 등
        중요한 정보 검색 단계를 완료한 후에는 항상 이 도구를 호출해야 합니다.
        """
        return self.prompt_factory.create_think_about_collected_information()


class ThinkAboutTaskAdherenceTool(Tool):
    """
    에이전트가 현재 작업 목표에 맞게 진행하고 있는지 판단하는 "생각" 도구입니다.
    """

    def apply(self) -> str:
        """
        당면한 과제와 현재 진행 상황이 올바른 방향으로 가고 있는지 생각합니다.
        특히 대화가 길어지고 많은 상호작용이 있었을 때 중요합니다.

        코드를 삽입, 교체 또는 삭제하기 전에는 항상 이 도구를 호출해야 합니다.
        """
        return self.prompt_factory.create_think_about_task_adherence()


class ThinkAboutWhetherYouAreDoneTool(Tool):
    """
    작업이 정말로 완료되었는지 판단하는 "생각" 도구입니다.
    """

    def apply(self) -> str:
        """
        사용자가 요청한 작업이 완료되었다고 생각될 때마다 이 도구를 호출하는 것이 중요합니다.
        """
        return self.prompt_factory.create_think_about_whether_you_are_done()


class SummarizeChangesTool(Tool, ToolMarkerOptional):
    """
    코드베이스에 적용된 변경 사항을 요약하기 위한 지침을 제공합니다.
    """

    def apply(self) -> str:
        """
        코드베이스에 적용한 변경 사항을 요약합니다.

        중요한 코딩 작업을 완전히 마친 후에 항상 이 도구를 호출해야 하지만,
        `think_about_whether_you_are_done`을 호출한 이후에만 사용해야 합니다.
        """
        return self.prompt_factory.create_summarize_changes()


class PrepareForNewConversationTool(Tool):
    """
    새로운 대화를 준비하기 위한 지침을 제공합니다 (필요한 컨텍스트를 이어가기 위해).
    """

    def apply(self) -> str:
        """
        새로운 대화를 준비하기 위한 지침입니다. 이 도구는 사용자의 명시적인 요청이 있을 때만 호출해야 합니다.
        """
        return self.prompt_factory.create_prepare_for_new_conversation()


class InitialInstructionsTool(Tool, ToolMarkerDoesNotRequireActiveProject, ToolMarkerOptional):
    """
    현재 프로젝트에 대한 초기 지침을 가져옵니다.

    시스템 프롬프트를 설정할 수 없는 환경(예: 제어할 수 없는 클라이언트인 Claude Desktop)에서만 사용해야 합니다.
    """

    def apply(self) -> str:
        """
        현재 코딩 프로젝트에 대한 초기 지침을 가져옵니다.

        시스템 프롬프트에서 Serena 도구 사용법에 대한 지침을 받지 못한 경우,
        프로그래밍 작업을 시작하기 전(다른 도구를 사용하기 포함)에 항상 이 도구를 호출해야 합니다.
        단, `activate_project`를 호출하라는 요청을 받은 경우에는 그 전에 해당 도구를 호출해야 합니다.
        """
        return self.agent.create_system_prompt()