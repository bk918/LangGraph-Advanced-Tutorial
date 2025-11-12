"""
solidlsp/settings.py - Solid-LSP 설정

이 파일은 Solid-LSP 라이브러리의 전역 및 프로젝트별 설정을 정의합니다.

주요 클래스:
- SolidLSPSettings: Solid-LSP의 동작을 제어하는 설정 값들을 담는 데이터 클래스.

주요 설정:
- solidlsp_dir: 전역 Solid-LSP 데이터(예: 언어 서버 바이너리)를 저장할 디렉토리 경로.
- project_data_relative_path: 각 프로젝트 내에서 프로젝트별 데이터(예: 캐시 파일)를
  저장할 상대 경로.
- ls_specific_settings: 각 언어 서버 구현체에 특화된 고급 설정 옵션.

아키텍처 노트:
- 이 설정 클래스는 라이브러리의 유연성을 높여줍니다. 사용자는 이 설정을 통해
  데이터 저장 위치를 변경하거나, 특정 언어 서버의 동작을 미세 조정할 수 있습니다.
- `__post_init__` 메서드를 사용하여, 설정 객체가 생성될 때 필요한 디렉토리들이
  자동으로 생성되도록 보장합니다.
"""

import os
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from solidlsp.ls_config import Language


@dataclass
class SolidLSPSettings:
    """
    Solid-LSP 라이브러리의 설정을 정의하는 데이터 클래스.
    """

    solidlsp_dir: str = str(pathlib.Path.home() / ".solidlsp")
    """
    전역 Solid-LSP 데이터(프로젝트에 특정되지 않은 데이터)를 저장할 디렉토리 경로.
    """
    project_data_relative_path: str = ".solidlsp"
    """
    각 프로젝트 디렉토리 내에서 Solid-LSP가 프로젝트별 데이터(예: 캐시 파일)를 저장할 수 있는 상대 경로.
    예를 들어, 이 값이 ".solidlsp"이고 프로젝트가 "/home/user/myproject"에 위치하면,
    Solid-LSP는 "/home/user/myproject/.solidlsp"에 프로젝트별 데이터를 저장합니다.
    """
    ls_specific_settings: dict["Language", Any] = field(default_factory=dict)
    """
    언어 서버 구현별 특정 옵션을 구성할 수 있는 고급 설정 옵션.
    사용 가능한 옵션을 보려면 solidlsp 내의 해당 LS 구현체의 생성자 docstring을 참조하십시오.
    옵션에 대한 문서가 없으면 사용 가능한 옵션이 없음을 의미합니다.
    """

    def __post_init__(self):
        """객체 초기화 후 필요한 디렉토리를 생성합니다."""
        os.makedirs(str(self.solidlsp_dir), exist_ok=True)
        os.makedirs(str(self.ls_resources_dir), exist_ok=True)

    @property
    def ls_resources_dir(self) -> str:
        """언어 서버 관련 리소스(예: 다운로드된 바이너리)가 저장될 디렉토리 경로를 반환합니다."""
        return os.path.join(str(self.solidlsp_dir), "language_servers", "static")
