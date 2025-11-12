"""
solidlsp/util/subprocess_util.py - 서브프로세스 유틸리티

이 파일은 `subprocess` 모듈을 사용하여 외부 프로세스를 생성할 때,
플랫폼별로 일관된 설정을 적용하기 위한 유틸리티 함수를 제공합니다.
"""

import platform
import subprocess


def subprocess_kwargs():
    """
    Subprocess 호출에 대한 키워드 인수 딕셔너리를 반환하며,
    일관되게 사용하고자 하는 플랫폼별 플래그를 추가합니다.

    Windows에서는 `CREATE_NO_WINDOW` 플래그를 추가하여,
    셸 명령 실행 시 불필요한 콘솔 창이 나타나는 것을 방지합니다.
    """
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore
    return kwargs