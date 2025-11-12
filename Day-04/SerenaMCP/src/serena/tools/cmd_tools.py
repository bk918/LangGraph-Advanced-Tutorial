"""
serena/tools/cmd_tools.py - 셸 명령어 실행 도구

이 파일은 Serena 에이전트가 운영 체제의 셸 명령어를 실행할 수 있도록 하는 도구를 포함합니다.
이를 통해 에이전트는 빌드, 테스트, 린팅, 파일 시스템 조작 등 다양한 외부 작업을 수행할 수 있습니다.

주요 클래스:
- ExecuteShellCommandTool: 지정된 셸 명령어를 실행하고 그 결과를 반환합니다.

아키텍처 노트:
- 이 도구는 `serena.util.shell.execute_shell_command` 유틸리티 함수를 사용하여
  실제 명령어 실행을 처리합니다. 이 유틸리티는 서브프로세스를 안전하게 생성하고
  stdout, stderr, 종료 코드 등을 캡처하는 역할을 합니다.
- `ToolMarkerCanEdit` 마커를 상속받아, 이 도구가 시스템 상태를 변경할 수 있는
  편집성 작업임을 명시합니다. `read_only` 모드에서는 이 도구가 비활성화됩니다.
- 보안을 위해, 에이전트는 `rm -rf /`와 같은 위험한 명령어는 실행하지 않도록
  기본 프롬프트에 지침이 포함되어 있습니다.
- 작업 디렉토리(cwd)를 지정할 수 있어, 프로젝트 내의 특정 하위 디렉토리에서
  명령어를 실행하는 것이 가능합니다.
"""

import os.path

from serena.tools import Tool, ToolMarkerCanEdit
from serena.util.shell import execute_shell_command


class ExecuteShellCommandTool(Tool, ToolMarkerCanEdit):
    """
    셸 명령어를 실행합니다.

    이 도구를 사용하여 빌드, 테스트, 린트 실행 등 다양한 외부 명령을 수행할 수 있습니다.
    보안에 유의해야 하며, `rm -rf /`와 같이 시스템에 해를 끼칠 수 있는 위험한 명령어는
    절대 실행해서는 안 됩니다.
    """

    def apply(
        self,
        command: str,
        cwd: str | None = None,
        capture_stderr: bool = True,
        max_answer_chars: int = -1,
    ) -> str:
        """
        셸 명령어를 실행하고 그 출력을 반환합니다.

        만약 제안된 명령어에 대한 메모리가 있다면, 먼저 그것을 읽어보세요.
        `rm -rf /`와 같은 안전하지 않은 셸 명령어는 절대 실행하지 마세요!

        Args:
            command (str): 실행할 셸 명령어.
            cwd (str | None): 명령어를 실행할 작업 디렉토리. None이면 프로젝트 루트가 사용됩니다.
            capture_stderr (bool): stderr 출력을 캡처하여 반환할지 여부.
            max_answer_chars (int): 출력이 이 문자 수를 초과하면 내용이 반환되지 않습니다.
                -1은 기본값을 의미하며, 작업에 필요한 내용을 얻을 다른 방법이 없는 경우에만 조정하세요.

        Returns:
            str: 명령어의 stdout과 선택적으로 stderr 출력을 포함하는 JSON 객체 문자열.

        Raises:
            FileNotFoundError: `cwd`로 지정된 상대 경로가 유효한 디렉토리가 아닐 경우 발생합니다.
        """
        if cwd is None:
            _cwd = self.get_project_root()
        else:
            if os.path.isabs(cwd):
                _cwd = cwd
            else:
                _cwd = os.path.join(self.get_project_root(), cwd)
                if not os.path.isdir(_cwd):
                    raise FileNotFoundError(
                        f"상대 작업 디렉토리({cwd})를 지정했지만, 결과 경로가 디렉토리가 아닙니다: {_cwd}"
                    )

        result = execute_shell_command(command, cwd=_cwd, capture_stderr=capture_stderr)
        result = result.json()
        return self._limit_length(result, max_answer_chars)