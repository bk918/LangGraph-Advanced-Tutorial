"""
serena/config/serena_config.py - Serena 및 프로젝트 설정 관리

이 파일은 Serena 에이전트의 전역 설정(`SerenaConfig`)과
개별 프로젝트의 설정(`ProjectConfig`)을 관리하는 데이터 클래스들을 포함합니다.
설정은 YAML 파일을 통해 로드되고 관리되며, 계층적 구조를 가집니다.

주요 컴포넌트:
- SerenaPaths: Serena 관련 주요 디렉토리 경로를 제공하는 싱글톤 클래스.
- ToolSet: 사용 가능한 도구의 집합을 관리하고, 포함/제외 규칙을 적용합니다.
- ToolInclusionDefinition: 도구 포함/제외 규칙을 정의하는 기본 데이터 클래스.
- ProjectConfig: 단일 프로젝트의 설정(언어, 무시 경로, 도구 규칙 등)을 관리합니다.
- SerenaConfig: 에이전트의 전역 설정(프로젝트 목록, 로그 레벨, 대시보드 등)을 관리합니다.

아키텍처 노트:
- 설정은 YAML 파일(`serena_config.yml`, `project.yml`)을 통해 관리되며,
  `ruamel.yaml`을 사용하여 주석을 보존하며 안전하게 읽고 쓸 수 있습니다.
- `ProjectConfig.autogenerate` 메서드는 새 프로젝트에 대한 설정을 자동으로 생성하여
  사용자 편의성을 높입니다.
- `SerenaConfig`는 등록된 모든 프로젝트를 관리하며, 프로젝트 추가/제거 시
  설정 파일을 자동으로 업데이트합니다.
- `is_running_in_docker`와 같은 유틸리티 함수를 통해 실행 환경에 따라
  설정을 동적으로 조정합니다.
"""

import os
import shutil
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Self, TypeVar

import yaml
from ruamel.yaml.comments import CommentedMap
from sensai.util import logging
from sensai.util.logging import LogTime, datetime_tag
from sensai.util.string import ToStringMixin

from serena.constants import (
    DEFAULT_ENCODING,
    PROJECT_TEMPLATE_FILE,
    REPO_ROOT,
    SERENA_CONFIG_TEMPLATE_FILE,
    SERENA_MANAGED_DIR_IN_HOME,
    SERENA_MANAGED_DIR_NAME,
)
from serena.util.general import load_yaml, save_yaml
from serena.util.inspection import determine_programming_language_composition
from solidlsp.ls_config import Language

from ..analytics import RegisteredTokenCountEstimator
from ..util.class_decorators import singleton

if TYPE_CHECKING:
    from ..project import Project

log = logging.getLogger(__name__)
T = TypeVar("T")
DEFAULT_TOOL_TIMEOUT: float = 240


@singleton
class SerenaPaths:
    """
    Serena 관련 다양한 디렉토리 및 파일 경로를 제공합니다.
    """

    def __init__(self) -> None:
        self.user_config_dir: str = SERENA_MANAGED_DIR_IN_HOME
        """
        사용자의 Serena 설정 디렉토리 경로, 일반적으로 ~/.serena 입니다.
        """

    def get_next_log_file_path(self, prefix: str) -> str:
        """
        :param prefix: 로그 파일 유형을 나타내는 파일 이름 접두사
        :return: 사용할 로그 파일의 전체 경로
        """
        log_dir = os.path.join(self.user_config_dir, "logs", datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, prefix + "_" + datetime_tag() + ".txt")

    # TODO: constants.py의 경로들을 여기로 옮겨야 합니다.


class ToolSet:
    def __init__(self, tool_names: set[str]) -> None:
        self._tool_names = tool_names

    @classmethod
    def default(cls) -> "ToolSet":
        """
        :return: 기본적으로 활성화된 모든 도구를 포함하는 기본 도구 세트
        """
        from serena.tools import ToolRegistry

        return cls(set(ToolRegistry().get_tool_names_default_enabled()))

    def apply(self, *tool_inclusion_definitions: "ToolInclusionDefinition") -> "ToolSet":
        """
        :param tool_inclusion_definitions: 적용할 정의들
        :return: 정의가 적용된 새로운 도구 세트
        """
        from serena.tools import ToolRegistry

        registry = ToolRegistry()
        tool_names = set(self._tool_names)
        for definition in tool_inclusion_definitions:
            included_tools = []
            excluded_tools = []
            for included_tool in definition.included_optional_tools:
                if not registry.is_valid_tool_name(included_tool):
                    raise ValueError(f"포함에 잘못된 도구 이름 '{included_tool}'이 제공되었습니다.")
                if included_tool not in tool_names:
                    tool_names.add(included_tool)
                    included_tools.append(included_tool)
            for excluded_tool in definition.excluded_tools:
                if not registry.is_valid_tool_name(excluded_tool):
                    raise ValueError(f"제외에 잘못된 도구 이름 '{excluded_tool}'이 제공되었습니다.")
                if excluded_tool in tool_names:
                    tool_names.remove(excluded_tool)
                    excluded_tools.append(excluded_tool)
            if included_tools:
                log.info(f"{definition}이(가) {len(included_tools)}개의 도구를 포함했습니다: {', '.join(included_tools)}")
            if excluded_tools:
                log.info(f"{definition}이(가) {len(excluded_tools)}개의 도구를 제외했습니다: {', '.join(excluded_tools)}")
        return ToolSet(tool_names)

    def without_editing_tools(self) -> "ToolSet":
        """
        :return: 편집할 수 있는 모든 도구를 제외하는 새로운 도구 세트
        """
        from serena.tools import ToolRegistry

        registry = ToolRegistry()
        tool_names = set(self._tool_names)
        for tool_name in self._tool_names:
            if registry.get_tool_class_by_name(tool_name).can_edit():
                tool_names.remove(tool_name)
        return ToolSet(tool_names)

    def get_tool_names(self) -> set[str]:
        """
        현재 도구 세트에 포함된 도구의 이름을 반환합니다.
        """
        return self._tool_names

    def includes_name(self, tool_name: str) -> bool:
        return tool_name in self._tool_names


@dataclass
class ToolInclusionDefinition:
    excluded_tools: Iterable[str] = ()
    included_optional_tools: Iterable[str] = ()


class SerenaConfigError(Exception):
    pass


def get_serena_managed_in_project_dir(project_root: str | Path) -> str:
    return os.path.join(project_root, SERENA_MANAGED_DIR_NAME)


def is_running_in_docker() -> bool:
    """Docker 컨테이너 내부에서 실행 중인지 확인합니다."""
    # Docker 관련 파일 확인
    if os.path.exists("/.dockerenv"):
        return True
    # cgroup에서 docker 참조 확인
    try:
        with open("/proc/self/cgroup") as f:
            return "docker" in f.read()
    except FileNotFoundError:
        return False


@dataclass(kw_only=True)
class ProjectConfig(ToolInclusionDefinition, ToStringMixin):
    project_name: str
    language: Language
    ignored_paths: list[str] = field(default_factory=list)
    read_only: bool = False
    ignore_all_files_in_gitignore: bool = True
    initial_prompt: str = ""
    encoding: str = DEFAULT_ENCODING

    SERENA_DEFAULT_PROJECT_FILE = "project.yml"

    def _tostring_includes(self) -> list[str]:
        return ["project_name"]

    @classmethod
    def autogenerate(
        cls,
        project_root: str | Path,
        project_name: str | None = None,
        project_language: Language | None = None,
        save_to_disk: bool = True
    ) -> Self:
        """
        주어진 프로젝트 루트에 대한 프로젝트 설정을 자동 생성합니다.

        :param project_root: 프로젝트 루트 경로
        :param project_name: 프로젝트 이름; None이면 프로젝트를 포함하는 디렉토리의 이름이 됩니다.
        :param project_language: 프로젝트의 프로그래밍 언어; None이면 자동으로 결정됩니다.
        :param save_to_disk: 프로젝트 설정을 디스크에 저장할지 여부
        :return: 프로젝트 설정
        """
        project_root = Path(project_root).resolve()
        if not project_root.exists():
            raise FileNotFoundError(f"프로젝트 루트를 찾을 수 없습니다: {project_root}")
        with LogTime("프로젝트 설정 자동 생성", logger=log):
            project_name = project_name or project_root.name
            if project_language is None:
                language_composition = determine_programming_language_composition(str(project_root))
                if len(language_composition) == 0:
                    raise ValueError(
                        f"{project_root}에서 소스 파일을 찾을 수 없습니다.\n\n"
                        f"이 프로젝트에서 Serena를 사용하려면 다음 중 하나를 수행해야 합니다:\n"
                        f"1. 지원되는 언어(Python, JavaScript/TypeScript, Java, C#, Rust, Go, Ruby, C++, PHP, Swift, Elixir, Terraform, Bash) 중 하나로 소스 파일을 추가합니다.\n"
                        f"2. 다음 위치에 프로젝트 설정 파일을 수동으로 생성합니다:\n"
                        f"   {os.path.join(project_root, cls.rel_path_to_project_yml())}\n\n"
                        f"예제 project.yml:\n"
                        f"  project_name: {project_name}\n"
                        f"  language: python  # 또는 typescript, java, csharp, rust, go, ruby, cpp, php, swift, elixir, terraform, bash\n"
                    )
                # 가장 높은 비율을 가진 언어 찾기
                dominant_language = max(language_composition.keys(), key=lambda lang: language_composition[lang])
            else:
                dominant_language = project_language.value
            config_with_comments = load_yaml(PROJECT_TEMPLATE_FILE, preserve_comments=True)
            config_with_comments["project_name"] = project_name
            config_with_comments["language"] = dominant_language
            if save_to_disk:
                save_yaml(str(project_root / cls.rel_path_to_project_yml()), config_with_comments, preserve_comments=True)
            return cls._from_dict(config_with_comments)

    @classmethod
    def rel_path_to_project_yml(cls) -> str:
        return os.path.join(SERENA_MANAGED_DIR_NAME, cls.SERENA_DEFAULT_PROJECT_FILE)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Self:
        """
        설정 딕셔너리에서 ProjectConfig 인스턴스를 생성합니다.
        """
        language_str = data["language"].lower()
        project_name = data["project_name"]
        # 하위 호환성
        if language_str == "javascript":
            log.warning(f"프로젝트 {project_name}에서 사용되지 않는 프로젝트 언어 `javascript`를 찾았습니다. `typescript`로 변경해주세요.")
            language_str = "typescript"
        try:
            language = Language(language_str)
        except ValueError as e:
            raise ValueError(f"잘못된 언어: {data['language']}.\n유효한 언어: {[l.value for l in Language]}") from e
        return cls(
            project_name=project_name,
            language=language,
            ignored_paths=data.get("ignored_paths", []),
            excluded_tools=data.get("excluded_tools", []),
            included_optional_tools=data.get("included_optional_tools", []),
            read_only=data.get("read_only", False),
            ignore_all_files_in_gitignore=data.get("ignore_all_files_in_gitignore", True),
            initial_prompt=data.get("initial_prompt", ""),
            encoding=data.get("encoding", DEFAULT_ENCODING),
        )

    @classmethod
    def load(cls, project_root: Path | str, autogenerate: bool = False) -> Self:
        """
        프로젝트 루트 경로에서 ProjectConfig 인스턴스를 로드합니다.
        """
        project_root = Path(project_root)
        yaml_path = project_root / cls.rel_path_to_project_yml()
        if not yaml_path.exists():
            if autogenerate:
                return cls.autogenerate(project_root)
            else:
                raise FileNotFoundError(f"프로젝트 설정 파일을 찾을 수 없습니다: {yaml_path}")
        with open(yaml_path, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        if "project_name" not in yaml_data:
            yaml_data["project_name"] = project_root.name
        return cls._from_dict(yaml_data)


class RegisteredProject(ToStringMixin):
    def __init__(self, project_root: str, project_config: "ProjectConfig", project_instance: Optional["Project"] = None) -> None:
        """
        Serena 설정에 등록된 프로젝트를 나타냅니다.

        :param project_root: 프로젝트의 루트 디렉토리
        :param project_config: 프로젝트의 설정
        """
        self.project_root = Path(project_root).resolve()
        self.project_config = project_config
        self._project_instance = project_instance

    def _tostring_exclude_private(self) -> bool:
        return True

    @property
    def project_name(self) -> str:
        return self.project_config.project_name

    @classmethod
    def from_project_instance(cls, project_instance: "Project") -> "RegisteredProject":
        return RegisteredProject(
            project_root=project_instance.project_root,
            project_config=project_instance.project_config,
            project_instance=project_instance,
        )

    def matches_root_path(self, path: str | Path) -> bool:
        """
        주어진 경로가 프로젝트 루트 경로와 일치하는지 확인합니다.

        :param path: 확인할 경로
        :return: 경로가 프로젝트 루트와 일치하면 True, 그렇지 않으면 False
        """
        return self.project_root == Path(path).resolve()

    def get_project_instance(self) -> "Project":
        """
        이 등록된 프로젝트에 대한 프로젝트 인스턴스를 반환하며, 필요한 경우 로드합니다.
        """
        if self._project_instance is None:
            from ..project import Project

            with LogTime(f"{self}에 대한 프로젝트 인스턴스 로딩 중", logger=log):
                self._project_instance = Project(project_root=str(self.project_root), project_config=self.project_config)
        return self._project_instance


@dataclass(kw_only=True)
class SerenaConfig(ToolInclusionDefinition, ToStringMixin):
    """
    Serena 에이전트 설정을 보유하며, 일반적으로 YAML 설정 파일에서 로드됩니다
    (:method:`from_config_file`을 통해 인스턴스화될 때). 프로젝트가 추가되거나 제거될 때 업데이트됩니다.
    테스트 목적으로 원하는 매개변수로 직접 인스턴스화할 수도 있습니다.
    """

    projects: list[RegisteredProject] = field(default_factory=list)
    gui_log_window_enabled: bool = False
    log_level: int = logging.INFO
    trace_lsp_communication: bool = False
    web_dashboard: bool = True
    web_dashboard_open_on_launch: bool = True
    tool_timeout: float = DEFAULT_TOOL_TIMEOUT
    loaded_commented_yaml: CommentedMap | None = None
    config_file_path: str | None = None
    """
    설정 업데이트를 저장할 설정 파일 경로;
    None이면 설정이 디스크에 저장되지 않습니다.
    """
    jetbrains: bool = False
    """
    JetBrains 모드를 적용할지 여부
    """
    record_tool_usage_stats: bool = False
    """도구 사용 통계를 기록할지 여부, 기록이 활성화되면 웹 대시보드에 표시됩니다.
    """
    token_count_estimator: str = RegisteredTokenCountEstimator.TIKTOKEN_GPT4O.name
    """`record_tool_usage`가 True일 때만 관련이 있습니다. 도구 사용 통계에 사용할 토큰 수 추정기의 이름입니다.
    사용 가능한 옵션은 `RegisteredTokenCountEstimator` 열거형을 참조하세요.
    
    참고: 일부 토큰 추정기(예: tiktoken)는 첫 실행 시 데이터 파일을 다운로드해야 할 수 있으며,
    시간이 걸리고 인터넷 연결이 필요할 수 있습니다. Anthropic과 같은 다른 추정기는 API 키가 필요할 수 있으며
    속도 제한이 적용될 수 있습니다.
    """
    default_max_tool_answer_chars: int = 150_000
    """apply 메서드에 기본 최대 답변 길이가 있는 도구의 기본값으로 사용됩니다.
    max_answer_chars 값은 도구를 호출할 때 변경할 수 있지만, 이 기본값을
    전역 설정을 통해 조정하는 것이 합리적일 수 있습니다.
    """
    ls_specific_settings: dict = field(default_factory=dict)
    """언어 서버 구현별 옵션을 구성할 수 있는 고급 구성 옵션입니다. 자세한 내용은 SolidLSPSettings를 참조하세요."""

    CONFIG_FILE = "serena_config.yml"
    CONFIG_FILE_DOCKER = "serena_config.docker.yml"  # Docker 관련 설정 파일; 없으면 자동 생성, 사용자 정의를 위해 docker-compose로 마운트

    def _tostring_includes(self) -> list[str]:
        return ["config_file_path"]

    @classmethod
    def generate_config_file(cls, config_file_path: str) -> None:
        """
        지정된 경로에 템플릿 파일로부터 Serena 설정 파일을 생성합니다.

        :param config_file_path: 설정 파일을 생성할 경로
        """
        log.info(f"{config_file_path}에 Serena 설정 파일을 자동 생성합니다.")
        loaded_commented_yaml = load_yaml(SERENA_CONFIG_TEMPLATE_FILE, preserve_comments=True)
        save_yaml(config_file_path, loaded_commented_yaml, preserve_comments=True)

    @classmethod
    def _determine_config_file_path(cls) -> str:
        """
        :return: Serena 설정 파일이 저장되거나 저장되어야 할 위치
        """
        if is_running_in_docker():
            return os.path.join(REPO_ROOT, cls.CONFIG_FILE_DOCKER)
        else:
            config_path = os.path.join(SERENA_MANAGED_DIR_IN_HOME, cls.CONFIG_FILE)

            # 설정 파일이 존재하지 않으면 이전 위치에서 마이그레이션할 수 있는지 확인합니다.
            if not os.path.exists(config_path):
                old_config_path = os.path.join(REPO_ROOT, cls.CONFIG_FILE)
                if os.path.exists(old_config_path):
                    log.info(f"Serena 설정 파일을 {old_config_path}에서 {config_path}로 이동합니다.")
                    os.makedirs(os.path.dirname(config_path), exist_ok=True)
                    shutil.move(old_config_path, config_path)

            return config_path

    @classmethod
    def from_config_file(cls, generate_if_missing: bool = True) -> "SerenaConfig":
        """
        설정 파일에서 SerenaConfig를 생성하는 정적 생성자
        """
        config_file_path = cls._determine_config_file_path()

        # 필요한 경우 템플릿에서 설정 파일 생성
        if not os.path.exists(config_file_path):
            if not generate_if_missing:
                raise FileNotFoundError(f"Serena 설정 파일을 찾을 수 없습니다: {config_file_path}")
            log.info(f"{config_file_path}에서 Serena 설정 파일을 찾을 수 없어 자동 생성합니다...")
            cls.generate_config_file(config_file_path)

        # 설정 로드
        log.info(f"{config_file_path}에서 Serena 설정을 로드합니다.")
        try:
            loaded_commented_yaml = load_yaml(config_file_path, preserve_comments=True)
        except Exception as e:
            raise ValueError(f"{config_file_path}에서 Serena 설정을 로드하는 중 오류 발생: {e}") from e

        # 설정 인스턴스 생성
        instance = cls(loaded_commented_yaml=loaded_commented_yaml, config_file_path=config_file_path)

        # 프로젝트 읽기
        if "projects" not in loaded_commented_yaml:
            raise SerenaConfigError("`projects` 키를 Serena 설정에서 찾을 수 없습니다. `serena_config.yml` 파일을 업데이트해주세요.")

        # 알려진 프로젝트 목록 로드
        instance.projects = []
        num_project_migrations = 0
        for path in loaded_commented_yaml["projects"]:
            path = Path(path).resolve()
            if not path.exists() or (path.is_dir() and not (path / ProjectConfig.rel_path_to_project_yml()).exists()):
                log.warning(f"프로젝트 경로 {path}가 존재하지 않거나 프로젝트 설정 파일을 포함하지 않아 건너뜁니다.")
                continue
            if path.is_file():
                path = cls._migrate_out_of_project_config_file(path)
                if path is None:
                    continue
                num_project_migrations += 1
            project_config = ProjectConfig.load(path)
            project = RegisteredProject(
                project_root=str(path),
                project_config=project_config,
            )
            instance.projects.append(project)

        # 다른 설정 매개변수 설정
        if is_running_in_docker():
            instance.gui_log_window_enabled = False  # Docker에서 지원되지 않음
        else:
            instance.gui_log_window_enabled = loaded_commented_yaml.get("gui_log_window", False)
        instance.log_level = loaded_commented_yaml.get("log_level", loaded_commented_yaml.get("gui_log_level", logging.INFO))
        instance.web_dashboard = loaded_commented_yaml.get("web_dashboard", True)
        instance.web_dashboard_open_on_launch = loaded_commented_yaml.get("web_dashboard_open_on_launch", True)
        instance.tool_timeout = loaded_commented_yaml.get("tool_timeout", DEFAULT_TOOL_TIMEOUT)
        instance.trace_lsp_communication = loaded_commented_yaml.get("trace_lsp_communication", False)
        instance.excluded_tools = loaded_commented_yaml.get("excluded_tools", [])
        instance.included_optional_tools = loaded_commented_yaml.get("included_optional_tools", [])
        instance.jetbrains = loaded_commented_yaml.get("jetbrains", False)
        instance.record_tool_usage_stats = loaded_commented_yaml.get("record_tool_usage_stats", False)
        instance.token_count_estimator = loaded_commented_yaml.get(
            "token_count_estimator", RegisteredTokenCountEstimator.TIKTOKEN_GPT4O.name
        )
        instance.default_max_tool_answer_chars = loaded_commented_yaml.get("default_max_tool_answer_chars", 150_000)
        instance.ls_specific_settings = loaded_commented_yaml.get("ls_specific_settings", {})

        # 마이그레이션이 수행된 경우 설정 파일 다시 저장
        if num_project_migrations > 0:
            log.info(
                f"{num_project_migrations}개의 프로젝트 설정을 레거시 형식에서 프로젝트 내 설정으로 마이그레이션했습니다. 설정을 다시 저장합니다."
            )
            instance.save()

        return instance

    @classmethod
    def _migrate_out_of_project_config_file(cls, path: Path) -> Path | None:
        """
        레거시 프로젝트 설정 파일(프로젝트 루트를 포함하는 YAML 파일)을 프로젝트 루트 디렉토리 내의
        프로젝트 내 설정 파일(project.yml)로 마이그레이션합니다.

        :param path: 레거시 프로젝트 설정 파일 경로
        :return: 마이그레이션이 성공하면 프로젝트 루트 경로, 그렇지 않으면 None.
        """
        log.info(f"레거시 프로젝트 설정 파일 {path}를 찾았으므로 프로젝트 내 설정으로 마이그레이션합니다.")
        try:
            with open(path, encoding="utf-8") as f:
                project_config_data = yaml.safe_load(f)
            if "project_name" not in project_config_data:
                project_name = path.stem
                with open(path, "a", encoding="utf-8") as f:
                    f.write(f"\nproject_name: {project_name}")
            project_root = project_config_data["project_root"]
            shutil.move(str(path), str(Path(project_root) / ProjectConfig.rel_path_to_project_yml()))
            return Path(project_root).resolve()
        except Exception as e:
            log.error(f"설정 파일 마이그레이션 중 오류 발생: {e}")
            return None

    @cached_property
    def project_paths(self) -> list[str]:
        return sorted(str(project.project_root) for project in self.projects)

    @cached_property
    def project_names(self) -> list[str]:
        return sorted(project.project_config.project_name for project in self.projects)

    def get_project(self, project_root_or_name: str) -> Optional["Project"]:
        # 이름으로 프로젝트 찾기
        project_candidates = []
        for project in self.projects:
            if project.project_config.project_name == project_root_or_name:
                project_candidates.append(project)
        if len(project_candidates) == 1:
            return project_candidates[0].get_project_instance()
        elif len(project_candidates) > 1:
            raise ValueError(
                f"이름이 '{project_root_or_name}'인 프로젝트가 여러 개 있습니다. 대신 위치로 활성화해주세요. "
                f"위치: {[p.project_root for p in project_candidates]}"
            )
        # 이름으로 프로젝트를 찾지 못함; 경로인지 확인
        if os.path.isdir(project_root_or_name):
            for project in self.projects:
                if project.matches_root_path(project_root_or_name):
                    return project.get_project_instance()
        return None

    def add_project_from_path(self, project_root: Path | str) -> "Project":
        """
        주어진 경로에서 Serena 설정에 프로젝트를 추가합니다. 경로에 이미
        프로젝트가 있는 경우 FileExistsError를 발생시킵니다.

        :param project_root: 추가할 프로젝트 경로
        :return: 추가된 프로젝트
        """
        from ..project import Project

        project_root = Path(project_root).resolve()
        if not project_root.exists():
            raise FileNotFoundError(f"오류: 경로가 존재하지 않습니다: {project_root}")
        if not project_root.is_dir():
            raise FileNotFoundError(f"오류: 경로가 디렉토리가 아닙니다: {project_root}")

        for already_registered_project in self.projects:
            if str(already_registered_project.project_root) == str(project_root):
                raise FileExistsError(
                    f"경로 {project_root}의 프로젝트가 이미 '{already_registered_project.project_name}' 이름으로 추가되었습니다."
                )

        project_config = ProjectConfig.load(project_root, autogenerate=True)

        new_project = Project(project_root=str(project_root), project_config=project_config, is_newly_created=True)
        self.projects.append(RegisteredProject.from_project_instance(new_project))
        self.save()

        return new_project

    def remove_project(self, project_name: str) -> None:
        # 원하는 이름의 프로젝트 인덱스를 찾아 제거
        for i, project in enumerate(list(self.projects)):
            if project.project_name == project_name:
                del self.projects[i]
                break
        else:
            raise ValueError(f"프로젝트 '{project_name}'을(를) Serena 설정에서 찾을 수 없습니다. 유효한 프로젝트 이름: {self.project_names}")
        self.save()

    def save(self) -> None:
        """
        설정을 로드된 파일에 저장합니다 (있는 경우).
        """
        if self.config_file_path is None:
            return
        assert self.loaded_commented_yaml is not None, "로드된 YAML 없이 설정을 저장할 수 없습니다."
        loaded_original_yaml = deepcopy(self.loaded_commented_yaml)
        # 프로젝트는 고유한 절대 경로입니다.
        # 저장하기 전에 정규화합니다.
        loaded_original_yaml["projects"] = sorted({str(project.project_root) for project in self.projects})
        save_yaml(self.config_file_path, loaded_original_yaml, preserve_comments=True)