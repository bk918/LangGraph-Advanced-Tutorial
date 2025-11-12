"""
serena/util/shell.py - 셸 명령어 실행 유틸리티

이 파일은 운영 체제의 셸 명령어를 실행하고 그 결과를 처리하기 위한
저수준 유틸리티 함수들을 제공합니다.

주요 컴포넌트:
- ShellCommandResult: `pydantic.BaseModel`을 상속받아, 셸 명령어 실행 결과를
  (stdout, stderr, 종료 코드 등) 구조화된 데이터로 캡슐화합니다.
- execute_shell_command: `subprocess.Popen`을 사용하여 셸 명령어를 비동기적으로 실행하고,
  실행이 완료되면 `ShellCommandResult` 객체를 반환합니다.
- subprocess_check_output: `subprocess.check_output`의 래퍼(wrapper) 함수로,
  간단한 명령어의 출력을 직접 문자열로 받아오는 데 사용됩니다.

아키텍처 노트:
- `subprocess.Popen`을 사용하여 프로세스를 생성함으로써, 에이전트가 외부 명령어를 실행하는 동안
  블로킹되지 않고 다른 작업을 수행할 수 있는 기반을 마련합니다. (현재 구현은 `communicate()`로 대기)
- `solidlsp.util.subprocess_util.subprocess_kwargs()`를 호출하여, Windows 환경에서
  불필요한 콘솔 창이 뜨는 것을 방지하는 등 플랫폼별 프로세스 생성 플래그를 일관되게 적용합니다.
- 에러 스트림(`stderr`) 캡처 여부를 선택할 수 있어, 필요에 따라 오류 정보만 따로 처리하거나
  무시할 수 있습니다.
"""

import os
import subprocess

from pydantic import BaseModel

from solidlsp.util.subprocess_util import subprocess_kwargs


class ShellCommandResult(BaseModel):
    """
    셸 명령어 실행 결과를 담는 데이터 모델.

    Attributes:
        stdout (str): 명령어의 표준 출력(stdout) 내용.
        return_code (int): 프로세스의 종료 코드. 0은 성공을 의미합니다.
        cwd (str): 명령어가 실행된 현재 작업 디렉토리.
        stderr (str | None): 명령어의 표준 에러(stderr) 내용. `capture_stderr=True`일 때만 값이 설정됩니다.
    """

    stdout: str
    return_code: int
    cwd: str
    stderr: str | None = None


def execute_shell_command(command: str, cwd: str | None = None, capture_stderr: bool = False) -> ShellCommandResult:
    """
    지정된 셸 명령어를 실행하고 그 결과를 반환합니다.

    Args:
        command (str): 실행할 셸 명령어 문자열.
        cwd (str | None): 명령어를 실행할 작업 디렉토리. None이면 현재 디렉토리가 사용됩니다.
        capture_stderr (bool): True이면 stderr 출력을 캡처하여 결과에 포함합니다.

    Returns:
        ShellCommandResult: 명령어 실행의 stdout, stderr, 종료 코드 등을 담은 객체.
    """
    if cwd is None:
        cwd = os.getcwd()

    process = subprocess.Popen(
        command,
        shell=True,
        stdin=subprocess.DEVNULL,  # 표준 입력은 사용하지 않음
        stdout=subprocess.PIPE,    # 표준 출력을 파이프로 연결하여 캡처
        stderr=subprocess.PIPE if capture_stderr else None,  # stderr 캡처 여부 설정
        text=True,
        encoding="utf-8",
        errors="replace",  # 인코딩 오류 발생 시 대체 문자로 처리
        cwd=cwd,
        **subprocess_kwargs(),  # 플랫폼별 추가 프로세스 생성 인자
    )

    stdout, stderr = process.communicate()  # 프로세스 종료까지 대기하고 출력 가져오기
    return ShellCommandResult(stdout=stdout, stderr=stderr, return_code=process.returncode, cwd=cwd)


def subprocess_check_output(args: list[str], encoding: str = "utf-8", strip: bool = True, timeout: float | None = None) -> str:
    """
    서브프로세스를 실행하고 표준 출력을 문자열로 반환합니다.

    `subprocess.check_output`의 간단한 래퍼 함수로, 기본 인코딩과 공백 제거 옵션을 제공합니다.

    Args:
        args (list[str]): 실행할 명령어와 인자들의 리스트.
        encoding (str): 출력 디코딩에 사용할 인코딩.
        strip (bool): 반환된 문자열의 양쪽 공백을 제거할지 여부.
        timeout (float | None): 명령어 실행 시간 제한(초).

    Returns:
        str: 명령어의 표준 출력 내용.

    Raises:
        subprocess.CalledProcessError: 명령어가 0이 아닌 코드로 종료될 경우 발생합니다.
        subprocess.TimeoutExpired: 지정된 시간 내에 명령어가 완료되지 않을 경우 발생합니다.
    """
    output = subprocess.check_output(args, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout, env=os.environ.copy(), **subprocess_kwargs()).decode(encoding)  # type: ignore
    if strip:
        output = output.strip()
    return output