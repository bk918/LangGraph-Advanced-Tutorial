"""
serena/util/inspection.py - 코드 및 리포지토리 검사 유틸리티

이 파일은 클래스 구조를 검사하거나, 리포지토리의 언어 구성을 분석하는 등
코드베이스를 "검사(inspect)"하기 위한 유틸리티 함수들을 제공합니다.

주요 함수:
- iter_subclasses: 주어진 클래스의 모든 서브클래스를 재귀적으로 탐색하는 제너레이터를 반환합니다.
- determine_programming_language_composition: 리포지토리 내의 파일들을 분석하여,
  각 프로그래밍 언어가 차지하는 비율을 계산합니다.

아키텍처 노트:
- `iter_subclasses`는 클래스 상속 구조를 동적으로 탐색해야 하는 경우(예: 플러그인 시스템,
  도구 등록 등)에 유용하게 사용될 수 있습니다.
- `determine_programming_language_composition` 함수는 `serena.util.file_system`의
  `find_all_non_ignored_files`를 사용하여 `.gitignore`에 명시된 파일들을 제외하고 분석을 수행합니다.
  또한 `solidlsp.ls_config.Language` 열거형에 정의된 각 언어별 파일 확장자 정보를 활용하여
  언어를 식별합니다. 이는 프로젝트의 주 사용 언어를 자동으로 감지하는 데 사용됩니다.
"""

import logging
import os
from collections.abc import Generator
from typing import TypeVar

from serena.util.file_system import find_all_non_ignored_files
from solidlsp.ls_config import Language

T = TypeVar("T")

log = logging.getLogger(__name__)


def iter_subclasses(cls: type[T], recursive: bool = True) -> Generator[type[T], None, None]:
    """
    클래스의 모든 서브클래스를 반복합니다.

    Args:
        cls (type[T]): 서브클래스를 찾을 부모 클래스.
        recursive (bool): True이면 서브클래스의 서브클래스까지 재귀적으로 모두 찾습니다.

    Yields:
        Generator[type[T], None, None]: 찾은 서브클래스들을 순차적으로 반환하는 제너레이터.
    """
    for subclass in cls.__subclasses__():
        yield subclass
        if recursive:
            yield from iter_subclasses(subclass, recursive)


def determine_programming_language_composition(repo_path: str) -> dict[str, float]:
    """
    리포지토리의 프로그래밍 언어 구성을 결정합니다.

    `.gitignore`를 존중하여 리포지토리 내의 모든 파일을 스캔하고,
    각 언어별 파일 확장자를 기준으로 파일 수를 세어 언어별 비율을 계산합니다.

    Args:
        repo_path (str): 분석할 리포지토리의 경로.

    Returns:
        dict[str, float]: 각 언어 이름을 키로, 해당 언어 파일의 백분율을 값으로 하는 딕셔너리.
    """
    all_files = find_all_non_ignored_files(repo_path)

    if not all_files:
        return {}

    language_counts: dict[str, int] = {}
    total_files = len(all_files)

    for language in Language.iter_all(include_experimental=False):
        matcher = language.get_source_fn_matcher()
        count = 0

        for file_path in all_files:
            filename = os.path.basename(file_path)
            if matcher.is_relevant_filename(filename):
                count += 1

        if count > 0:
            language_counts[str(language)] = count

    language_percentages: dict[str, float] = {}
    for language_name, count in language_counts.items():
        percentage = (count / total_files) * 100
        language_percentages[language_name] = round(percentage, 2)

    return language_percentages