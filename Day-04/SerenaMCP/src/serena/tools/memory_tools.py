"""
serena/tools/memory_tools.py - Serena 메모리 관리 도구

이 파일은 Serena 에이전트의 장기 기억을 담당하는 메모리 관리 도구들을 포함합니다.
에이전트는 이 도구들을 사용하여 프로젝트에 대한 정보를 학습하고, 저장하며, 필요할 때 다시 참조할 수 있습니다.

주요 클래스:
- WriteMemoryTool: 프로젝트 관련 정보를 마크다운 파일 형식의 '메모리'로 저장합니다.
- ReadMemoryTool: 저장된 메모리의 내용을 읽어옵니다.
- ListMemoriesTool: 현재 프로젝트에서 사용 가능한 모든 메모리의 목록을 조회합니다.
- DeleteMemoryTool: 더 이상 필요 없거나 오래된 메모리를 삭제합니다.

아키텍처 노트:
- 메모리 관리는 `serena.agent.MemoriesManager` 클래스를 통해 이루어지며, 이 도구들은 해당 클래스의
  메서드들을 호출하는 인터페이스 역할을 합니다.
- 각 프로젝트는 `.serena/memories/` 디렉토리 내에 독립적인 메모리 공간을 가집니다.
- 메모리는 단순한 마크다운 파일이므로, 사용자가 직접 파일을 생성하거나 수정하여 에이전트에게
  정보를 제공하는 것도 가능합니다.
"""

import json

from serena.tools import Tool


class WriteMemoryTool(Tool):
    """
    프로젝트와 관련된 정보를 '메모리'로 저장합니다.

    이 도구는 현재 대화의 중요한 맥락, 코드 구조에 대한 분석, 작업 계획 등
    향후 세션에서 재사용될 수 있는 정보를 영구적으로 기록하는 데 사용됩니다.
    메모리 이름은 내용과 관련성이 높고, 나중에 쉽게 식별할 수 있도록 명확하게 지정해야 합니다.
    """

    def apply(self, memory_name: str, content: str, max_answer_chars: int = -1) -> str:
        """
        주어진 이름과 내용으로 프로젝트 메모리를 생성하거나 덮어씁니다.

        Args:
            memory_name (str): 저장할 메모리의 이름. 파일명으로 사용되므로 명확하고 간결해야 합니다.
            content (str): 저장할 내용. 주로 마크다운 형식이 권장됩니다.
            max_answer_chars (int): 허용되는 최대 내용 길이. -1이면 설정된 기본값을 따릅니다.

        Returns:
            str: 메모리 저장 작업의 성공을 알리는 확인 메시지.

        Raises:
            ValueError: `content`의 길이가 `max_answer_chars`를 초과할 경우 발생합니다.
        """
        if max_answer_chars == -1:
            max_answer_chars = self.agent.serena_config.default_max_tool_answer_chars
        if len(content) > max_answer_chars:
            raise ValueError(
                f"{memory_name}에 대한 내용이 너무 깁니다. 최대 길이는 {max_answer_chars}자입니다. " + "내용을 더 짧게 만들어 주세요."
            )

        return self.memories_manager.save_memory(memory_name, content)


class ReadMemoryTool(Tool):
    """
    저장된 메모리의 내용을 읽어옵니다.

    이 도구는 `ListMemoriesTool`을 통해 존재를 확인한 메모리의 상세 내용을 조회할 때 사용됩니다.
    현재 작업과 관련이 있는 메모리만 읽어야 하며, 동일한 대화에서 불필요하게 반복해서
    메모리를 읽는 것은 피해야 합니다.
    """

    def apply(self, memory_file_name: str, max_answer_chars: int = -1) -> str:
        """
        지정된 이름의 메모리 파일 내용을 반환합니다.

        Args:
            memory_file_name (str): 읽어올 메모리의 파일 이름.
            max_answer_chars (int): 반환될 내용의 최대 길이. -1이면 제한이 없습니다.

        Returns:
            str: 메모리 파일의 전체 내용.
        """
        return self.memories_manager.load_memory(memory_file_name)


class ListMemoriesTool(Tool):
    """
    현재 프로젝트에서 사용 가능한 모든 메모리의 목록을 조회합니다.

    이 도구를 사용하여 어떤 메모리들이 저장되어 있는지 확인하고, `ReadMemoryTool`을 사용하여
    특정 메모리의 내용을 읽을지 결정할 수 있습니다.
    """

    def apply(self) -> str:
        """
        현재 프로젝트에 저장된 모든 메모리의 파일 이름 목록을 JSON 형식으로 반환합니다.

        Returns:
            str: 메모리 파일 이름들을 담은 JSON 배열 문자열.
        """
        return json.dumps(self.memories_manager.list_memories())


class DeleteMemoryTool(Tool):
    """
    프로젝트 메모리를 삭제합니다.

    이 도구는 더 이상 유효하지 않거나 관련 없는 정보를 담고 있는 메모리를 영구적으로 제거하기 위해 사용됩니다.
    삭제된 메모리는 복구할 수 없으므로, 사용자의 명시적인 요청이 있을 때 신중하게 사용해야 합니다.
    """

    def apply(self, memory_file_name: str) -> str:
        """
        지정된 이름의 메모리 파일을 삭제합니다.

        Args:
            memory_file_name (str): 삭제할 메모리의 파일 이름.

        Returns:
            str: 메모리 삭제 작업의 성공을 알리는 확인 메시지.
        """
        return self.memories_manager.delete_memory(memory_file_name)