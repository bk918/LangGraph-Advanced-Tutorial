"""
Serena 패키지 초기화 모듈

이 파일은 `serena` 패키지의 메인 `__init__.py` 파일입니다.
패키지 버전 정보를 정의하고, 버전 조회 함수를 제공합니다.

주요 기능:
- `__version__`: 패키지의 시맨틱 버전.
- `serena_version()`: 현재 Git 상태를 포함한 상세 버전 정보 반환.
"""

__version__ = "0.1.4"

import logging

log = logging.getLogger(__name__)


def serena_version() -> str:
    """
    패키지의 상세 버전을 반환합니다.

    기본 `__version__`에 Git 커밋 해시와 'dirty' 상태(워킹 트리에 수정사항이 있는 경우)를 추가하여
    더욱 상세한 버전 정보를 제공합니다. 개발 및 디버깅 시에 유용합니다.

    Returns:
        str: Git 상태가 포함된 패키지 버전 문자열.
             예: "0.1.4-a1b2c3d4-dirty"
    """
    from serena.util.git import get_git_status

    version = __version__
    try:
        git_status = get_git_status()
        if git_status is not None:
            version += f"-{git_status.commit[:8]}"
            if not git_status.is_clean:
                version += "-dirty"
    except Exception:
        pass
    return version