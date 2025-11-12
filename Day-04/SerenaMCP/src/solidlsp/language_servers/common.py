"""
SolidLSP 공통 유틸리티 모듈 - 런타임 의존성 관리 및 공통 기능

이 모듈은 SolidLSP의 언어 서버들이 공통적으로 사용하는 유틸리티 기능을 제공합니다:
- 런타임 의존성 정의 및 관리
- 플랫폼별 의존성 설치 및 구성
- 파일 다운로드 및 압축 해제
- 프로세스 실행 및 경로 처리

주요 클래스:
- RuntimeDependency: 언어 서버의 런타임 의존성을 정의하는 데이터 클래스
- RuntimeDependencyCollection: 의존성들의 설치 및 관리를 담당하는 컬렉션 클래스

주요 함수:
- quote_windows_path(): Windows 환경에서 안전한 경로 인용 처리
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.util.subprocess_util import subprocess_kwargs

log = logging.getLogger(__name__)


@dataclass(kw_only=True)
class RuntimeDependency:
    """
    언어 서버의 런타임 의존성을 나타내는 데이터 클래스.

    각 언어 서버가 필요로 하는 외부 의존성(실행 파일, 라이브러리 등)을
    정의하는 데 사용됩니다. 플랫폼별로 다른 설정을 가질 수 있습니다.

    Attributes:
        id: 의존성의 고유 식별자
        platform_id: 적용될 플랫폼 ID (None이면 모든 플랫폼)
        url: 다운로드 URL (파일 설치 시 필요)
        archive_type: 압축 파일 형식 (zip, gz 등)
        binary_name: 실행 파일 이름
        command: 설치 시 실행할 명령어
        package_name: 패키지 관리자에서의 패키지 이름
        package_version: 패키지 버전
        extract_path: 압축 해제 경로
        description: 의존성에 대한 설명
    """
    id: str
    platform_id: str | None = None
    url: str | None = None
    archive_type: str | None = None
    binary_name: str | None = None
    command: str | list[str] | None = None
    package_name: str | None = None
    package_version: str | None = None
    extract_path: str | None = None
    description: str | None = None


class RuntimeDependencyCollection:
    """
    언어 서버 런타임 의존성들의 설치 및 관리를 담당하는 유틸리티 클래스.

    여러 RuntimeDependency 인스턴스들을 관리하고, 플랫폼별로 적절한
    의존성들을 선택하여 설치하는 기능을 제공합니다.

    주요 기능:
    - 의존성 목록 관리 및 중복 검사
    - 플랫폼별 의존성 필터링
    - 의존성 설치 및 경로 관리
    - 오버라이드 지원
    """

    def __init__(self, dependencies: Sequence[RuntimeDependency], overrides: Iterable[Mapping[str, Any]] = ()) -> None:
        """
        의존성 컬렉션을 초기화하고 선택적 오버라이드를 적용합니다.

        Args:
            dependencies: 기본 RuntimeDependency 인스턴스들의 시퀀스.
                         'id'와 'platform_id'의 조합은 유일해야 합니다.
            overrides: 기본 의존성들에 대한 오버라이드나 추가를 나타내는 딕셔너리들의 리스트.
                      각 항목은 최소 'id' 키를 포함해야 하며, 선택적으로 'platform_id'를
                      포함하여 오버라이드할 의존성을 유일하게 식별할 수 있습니다.

        Raises:
            ValueError: 중복된 런타임 의존성이 발견된 경우
        """
        self._id_and_platform_id_to_dep: dict[tuple[str, str | None], RuntimeDependency] = {}
        for dep in dependencies:
            dep_key = (dep.id, dep.platform_id)
            if dep_key in self._id_and_platform_id_to_dep:
                raise ValueError(f"Duplicate runtime dependency with id '{dep.id}' and platform_id '{dep.platform_id}':\n{dep}")
            self._id_and_platform_id_to_dep[dep_key] = dep

        for dep_values_override in overrides:
            override_key = cast(tuple[str, str | None], (dep_values_override["id"], dep_values_override.get("platform_id")))
            base_dep = self._id_and_platform_id_to_dep.get(override_key)
            if base_dep is None:
                new_runtime_dep = RuntimeDependency(**dep_values_override)
                self._id_and_platform_id_to_dep[override_key] = new_runtime_dep
            else:
                self._id_and_platform_id_to_dep[override_key] = replace(base_dep, **dep_values_override)

    def get_dependencies_for_platform(self, platform_id: str) -> list[RuntimeDependency]:
        """
        지정된 플랫폼에 해당하는 의존성들을 반환합니다.

        Args:
            platform_id: 조회할 플랫폼 ID

        Returns:
            list[RuntimeDependency]: 해당 플랫폼에 맞는 의존성들의 목록
        """
        return [d for d in self._id_and_platform_id_to_dep.values() if d.platform_id in (platform_id, "any", "platform-agnostic", None)]

    def get_dependencies_for_current_platform(self) -> list[RuntimeDependency]:
        """
        현재 플랫폼에 해당하는 의존성들을 반환합니다.

        Returns:
            list[RuntimeDependency]: 현재 플랫폼에 맞는 의존성들의 목록
        """
        return self.get_dependencies_for_platform(PlatformUtils.get_platform_id().value)

    def get_single_dep_for_current_platform(self, dependency_id: str | None = None) -> RuntimeDependency:
        """
        현재 플랫폼에서 지정된 ID의 단일 의존성을 반환합니다.

        Args:
            dependency_id: 조회할 의존성 ID (None이면 첫 번째 의존성 반환)

        Returns:
            RuntimeDependency: 요청된 의존성

        Raises:
            RuntimeError: 해당하는 의존성이 없거나 여러 개일 경우
        """
        deps = self.get_dependencies_for_current_platform()
        if dependency_id is not None:
            deps = [d for d in deps if d.id == dependency_id]
        if len(deps) != 1:
            raise RuntimeError(
                f"Expected exactly one runtime dependency for platform-{PlatformUtils.get_platform_id().value} and {dependency_id=}, found {len(deps)}"
            )
        return deps[0]

    def binary_path(self, target_dir: str) -> str:
        """
        현재 플랫폼의 바이너리 경로를 반환합니다.

        Args:
            target_dir: 설치 대상 디렉토리

        Returns:
            str: 바이너리 파일의 전체 경로
        """
        dep = self.get_single_dep_for_current_platform()
        if not dep.binary_name:
            return target_dir
        return os.path.join(target_dir, dep.binary_name)

    def install(self, logger: LanguageServerLogger, target_dir: str) -> dict[str, str]:
        """
        현재 플랫폼의 모든 의존성을 지정된 디렉토리에 설치합니다.

        Args:
            logger: 설치 과정을 로깅할 로거
            target_dir: 의존성을 설치할 대상 디렉토리

        Returns:
            dict[str, str]: 의존성 ID를 키로 하고 설치된 바이너리 경로를 값으로 하는 매핑
        """
        os.makedirs(target_dir, exist_ok=True)
        results: dict[str, str] = {}
        for dep in self.get_dependencies_for_current_platform():
            if dep.url:
                self._install_from_url(dep, logger, target_dir)
            if dep.command:
                self._run_command(dep.command, target_dir)
            if dep.binary_name:
                results[dep.id] = os.path.join(target_dir, dep.binary_name)
            else:
                results[dep.id] = target_dir
        return results

    @staticmethod
    def _run_command(command: str | list[str], cwd: str) -> None:
        """
        지정된 명령어를 지정된 작업 디렉토리에서 실행합니다.

        Windows가 아닌 환경에서는 현재 사용자로 명령어를 실행합니다.

        Args:
            command: 실행할 명령어 (문자열 또는 리스트)
            cwd: 작업 디렉토리

        Note:
            Linux/macOS에서는 리스트 형태의 명령어를 문자열로 변환하여 실행합니다.
            명령어 실행 결과는 표준 출력과 표준 에러를 함께 캡처합니다.
        """
        kwargs = subprocess_kwargs()
        if not PlatformUtils.get_platform_id().is_windows():
            import pwd

            kwargs["user"] = pwd.getpwuid(os.getuid()).pw_name

        is_windows = platform.system() == "Windows"
        if not isinstance(command, str) and not is_windows:
            # Since we are using the shell, we need to convert the command list to a single string
            # on Linux/macOS
            command = " ".join(command)

        log.info("Running command %s in '%s'", f"'{command}'" if isinstance(command, str) else command, cwd)

        completed_process = subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
        if completed_process.returncode != 0:
            log.warning("Command '%s' failed with return code %d", command, completed_process.returncode)
            log.warning("Command output:\n%s", completed_process.stdout)
        else:
            log.info(
                "Command completed successfully",
            )

    @staticmethod
    def _install_from_url(dep: RuntimeDependency, logger: LanguageServerLogger, target_dir: str) -> None:
        """
        URL에서 의존성을 다운로드하여 설치합니다.

        Args:
            dep: 설치할 의존성 정보
            logger: 설치 과정을 로깅할 로거
            target_dir: 설치할 대상 디렉토리
        """
        assert dep.url is not None
        if dep.archive_type == "gz" and dep.binary_name:
            dest = os.path.join(target_dir, dep.binary_name)
            FileUtils.download_and_extract_archive(logger, dep.url, dest, dep.archive_type)
        else:
            FileUtils.download_and_extract_archive(logger, dep.url, target_dir, dep.archive_type or "zip")


def quote_windows_path(path: str) -> str:
    """
    Windows 명령어 실행을 위해 필요한 경우 경로를 인용 처리합니다.

    Windows 환경에서는 공백이 포함된 경로를 올바르게 처리하기 위해
    큰따옴표로 경로를 감싸야 합니다. 이미 인용된 경로는 중복 인용을
    피하기 위해 확인합니다. 다른 플랫폼에서는 경로를 변경하지 않고 반환합니다.

    Args:
        path: 인용 처리할 파일 경로

    Returns:
        str: Windows에서는 필요한 경우 인용된 경로,
             다른 플랫폼에서는 변경되지 않은 원본 경로

    Note:
        이 함수는 명령줄에서 안전하게 경로를 사용할 수 있도록 보장합니다.
        특히 공백이나 특수 문자가 포함된 경로를 처리할 때 유용합니다.
    """
    if platform.system() == "Windows":
        # Check if already quoted to avoid double-quoting
        # 이미 인용된 경로인지 확인하여 중복 인용 방지
        if path.startswith('"') and path.endswith('"'):
            return path
        return f'"{path}"'
    return path
