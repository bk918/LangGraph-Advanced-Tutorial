"""
serena/util/git.py - Git 관련 유틸리티

이 파일은 Git 저장소와 상호작용하기 위한 유틸리티 함수를 포함합니다.
주로 로컬 Git 저장소의 상태를 조회하는 기능을 제공합니다.

주요 함수:
- get_git_status: 현재 디렉토리의 Git 상태(커밋 해시, 변경사항 등)를 조회합니다.

아키텍처 노트:
- 이 모듈은 `serena.util.shell.subprocess_check_output` 함수를 사용하여
  직접 `git` CLI 명령어를 실행하고 그 결과를 파싱합니다.
- `sensai.util.git.GitStatus` 데이터 클래스를 사용하여, 조회된 Git 상태 정보를
  구조화된 객체로 반환합니다.
- Git 명령어가 실패할 경우(예: 현재 디렉토리가 Git 저장소가 아닌 경우)를 대비하여
  예외 처리를 포함하고 있으며, 이 경우 `None`을 반환하여 안정적인 동작을 보장합니다.
"""

import logging

from sensai.util.git import GitStatus

from .shell import subprocess_check_output

log = logging.getLogger(__name__)


def get_git_status() -> GitStatus | None:
    """
    현재 디렉토리의 Git 저장소 상태를 조회합니다.

    `git` CLI 명령어를 사용하여 다음 정보를 수집합니다:
    - 현재 커밋 해시 (`git rev-parse HEAD`)
    - 스테이징되지 않은 변경사항 존재 여부 (`git diff --name-only`)
    - 스테이징된 변경사항 존재 여부 (`git diff --staged --name-only`)
    - 추적되지 않은 파일 존재 여부 (`git ls-files --others --exclude-standard`)

    Returns:
        GitStatus | None: Git 저장소 상태 정보를 담은 `GitStatus` 객체.
                          현재 디렉토리가 Git 저장소가 아니거나 오류가 발생하면 `None`을 반환합니다.
    """
    try:
        commit_hash = subprocess_check_output(["git", "rev-parse", "HEAD"])
        unstaged = bool(subprocess_check_output(["git", "diff", "--name-only"]))
        staged = bool(subprocess_check_output(["git", "diff", "--staged", "--name-only"]))
        untracked = bool(subprocess_check_output(["git", "ls-files", "--others", "--exclude-standard"]))
        return GitStatus(
            commit=commit_hash, has_unstaged_changes=unstaged, has_staged_uncommitted_changes=staged, has_untracked_files=untracked
        )
    except Exception as e:
        log.debug(f"Git 상태 조회 중 오류 발생: {e}")
        return None