"""
serena/util/exception.py - 예외 처리 유틸리티

이 파일은 Serena 에이전트에서 발생하는 예외, 특히 치명적인 예외를
안전하게 처리하고 사용자에게 표시하기 위한 유틸리티 함수들을 포함합니다.

주요 함수:
- is_headless_environment: 현재 실행 환경이 GUI를 지원하지 않는 헤드리스(headless) 환경인지
  감지합니다. (예: SSH 세션, Docker 컨테이너)
- show_fatal_exception_safe: 치명적인 예외가 발생했을 때, 이를 로그에 기록하고
  GUI가 사용 가능한 환경이라면 GUI 로그 뷰어를 통해 사용자에게 예외 정보를 표시합니다.

아키텍처 노트:
- 이 모듈은 에이전트의 안정성을 높이는 데 중요한 역할을 합니다. 예기치 않은 오류가 발생하더라도
  최대한 사용자에게 정보를 전달하고, GUI가 없는 환경에서 GUI 관련 코드를 실행하려다
  추가적인 오류가 발생하는 것을 방지합니다.
- `is_headless_environment` 함수는 다양한 운영 체제와 실행 환경(Linux, WSL, Docker 등)을
  고려하여 환경을 탐지하는 로직을 포함하고 있습니다.
- `show_fatal_exception_safe`는 `serena.gui_log_viewer`를 동적으로 임포트하여,
  Tkinter와 같은 GUI 라이브러리가 없는 환경에서도 임포트 오류 없이 실행될 수 있도록 합니다.
"""

import os
import sys

from serena.agent import log


def is_headless_environment() -> bool:
    """
    GUI 작업이 실패할 수 있는 헤드리스 환경에서 실행 중인지 감지합니다.

    다음과 같은 경우 True를 반환합니다:
    - Linux/Unix에서 DISPLAY 변수가 없는 경우
    - SSH 세션에서 실행 중인 경우
    - X 서버 없이 WSL에서 실행 중인 경우
    - Docker 컨테이너에서 실행 중인 경우

    Returns:
        bool: 헤드리스 환경이면 True, 그렇지 않으면 False.
    """
    # Windows에서는 GUI가 일반적으로 작동하므로 확인합니다.
    if sys.platform == "win32":
        return False

    # DISPLAY 변수 확인 (X11에 필요)
    if not os.environ.get("DISPLAY"):  # type: ignore
        return True

    # SSH 세션 확인
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT"):
        return True

    # 일반적인 CI/컨테이너 환경 확인
    if os.environ.get("CI") or os.environ.get("CONTAINER") or os.path.exists("/.dockerenv"):
        return True

    # WSL 확인 (os.uname이 있는 Unix 계열 시스템에서만)
    if hasattr(os, "uname"):
        if "microsoft" in os.uname().release.lower():
            # WSL에서는 DISPLAY가 설정되어 있어도 X 서버가 실행되지 않을 수 있습니다.
            # 이는 단순화된 확인이며 개선될 수 있습니다.
            return True

    return False


def show_fatal_exception_safe(e: Exception) -> None:
    """
    주어진 예외를 메인 스레드의 GUI 로그 뷰어에 표시하고, 예외가 로그에 기록되거나
    최소한 stderr에 출력되도록 보장합니다.

    Args:
        e (Exception): 표시할 치명적인 예외 객체.
    """
    # 오류를 로그에 기록하고 stderr에 출력합니다.
    log.error(f"치명적인 예외 발생: {e}", exc_info=e)
    print(f"치명적인 예외 발생: {e}", file=sys.stderr)

    # 헤드리스 환경에서는 GUI를 시도하지 않습니다.
    if is_headless_environment():
        log.debug("헤드리스 환경에서는 GUI 오류 표시를 건너뜁니다.")
        return

    # GUI에 오류를 표시하려고 시도합니다.
    try:
        # 참고: Tk가 없는 macOS에서는 임포트가 실패할 수 있습니다 (uv가 기반으로 사용한
        # Python 인터프리터 설치에 따라 다름). tkinter 자체는 항상 사용 가능하지만,
        # 그 의존성은 macOS에서 사용 불가능할 수 있습니다.
        from serena.gui_log_viewer import show_fatal_exception

        show_fatal_exception(e)
    except Exception as gui_error:
        log.debug(f"GUI 오류 대화 상자를 표시하지 못했습니다: {gui_error}")