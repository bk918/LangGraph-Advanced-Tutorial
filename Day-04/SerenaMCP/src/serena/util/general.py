"""
serena/util/general.py - 일반 유틸리티 함수

이 파일은 프로젝트 전반에서 사용되는 범용 유틸리티 함수들을 포함합니다.
주로 YAML 파일의 로딩 및 저장을 처리하는 기능을 제공합니다.

주요 함수:
- _create_YAML: `ruamel.yaml` 라이브러리의 YAML 객체를 생성합니다. 주석 보존 여부를 설정할 수 있습니다.
- load_yaml: 지정된 경로의 YAML 파일을 읽어 파이썬 객체(dict 또는 CommentedMap)로 변환합니다.
- save_yaml: 파이썬 객체를 YAML 형식으로 변환하여 지정된 경로에 저장합니다.

아키텍처 노트:
- `ruamel.yaml` 라이브러리를 사용하여 YAML 파일을 처리합니다. 이 라이브러리는 표준 `PyYAML`과 달리
  주석과 형식을 보존하는 기능을 제공하여, 설정 파일 등을 수정할 때 원본의 가독성을 해치지 않습니다.
- `preserve_comments` 매개변수를 통해 주석 보존 기능의 활성화 여부를 제어할 수 있어,
  단순 데이터 로딩과 형식 보존이 필요한 경우를 모두 지원합니다.
- 함수 오버로딩(`@overload`)을 사용하여 `preserve_comments` 값에 따라 반환 타입을
  정적으로 명확하게 정의함으로써, 타입 힌트의 정확성을 높였습니다.
"""

import os
from typing import Literal, overload

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


def _create_YAML(preserve_comments: bool = False) -> YAML:
    """
    주석 보존 기능이 있는 YAML 객체를 생성합니다.

    Args:
        preserve_comments (bool): True이면 주석을 보존하는 YAML 객체를 생성합니다.

    Returns:
        YAML: 생성된 `ruamel.yaml`의 YAML 인스턴스.
    """
    typ = None if preserve_comments else "safe"
    result = YAML(typ=typ)
    result.preserve_quotes = preserve_comments
    return result


@overload
def load_yaml(path: str, preserve_comments: Literal[False]) -> dict: ...
@overload
def load_yaml(path: str, preserve_comments: Literal[True]) -> CommentedMap: ...
def load_yaml(path: str, preserve_comments: bool = False) -> dict | CommentedMap:
    """
    지정된 경로에서 YAML 파일을 로드합니다.

    Args:
        path (str): 로드할 YAML 파일의 경로.
        preserve_comments (bool): True이면 주석과 형식을 보존하는 `CommentedMap`을 반환하고,
            False이면 일반 `dict`를 반환합니다.

    Returns:
        dict | CommentedMap: 로드된 YAML 데이터.
    """
    with open(path, encoding="utf-8") as f:
        yaml = _create_YAML(preserve_comments)
        return yaml.load(f)


def save_yaml(path: str, data: dict | CommentedMap, preserve_comments: bool = False) -> None:
    """
    주어진 데이터를 YAML 파일로 저장합니다.

    Args:
        path (str): 저장할 파일의 경로. 디렉토리가 없으면 자동으로 생성됩니다.
        data (dict | CommentedMap): 저장할 데이터.
        preserve_comments (bool): `data`가 `CommentedMap`일 경우, 주석과 형식을 보존하여 저장할지 여부.
    """
    yaml = _create_YAML(preserve_comments)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)