"""
serena/config/context_mode.py - 컨텍스트 및 모드 설정 로더

이 파일은 Serena 에이전트의 동작을 결정하는 '컨텍스트(Context)'와 '모드(Mode)' 설정을
YAML 파일로부터 로드하고 관리하는 클래스들을 포함합니다.

주요 컴포넌트:
- SerenaAgentMode: 에이전트의 동작 모드(예: planning, editing)를 나타내는 데이터 클래스.
  모드는 도구 사용 가능 여부, 시스템 프롬프트 등을 동적으로 변경하는 데 사용됩니다.
- SerenaAgentContext: 에이전트가 운영되는 환경(예: IDE, 챗봇)을 정의하는 데이터 클래스.
  컨텍스트는 에이전트 세션 시작 시 한 번 설정되며, 기본 도구 세트와 프롬프트를 결정합니다.
- RegisteredContext / RegisteredMode: 사전 정의된 주요 컨텍스트와 모드를 열거형으로 제공합니다.

아키텍처 노트:
- 컨텍스트와 모드는 `ToolInclusionDefinition`을 상속받아, 특정 도구를 포함하거나
  제외하는 규칙을 공통된 방식으로 처리합니다.
- 설정은 계층적으로 적용됩니다: 사용자 정의 YAML 파일이 내장된 기본 YAML 파일을
  재정의(override)할 수 있어, 사용자가 쉽게 커스터마이징할 수 있습니다.
- `from_yaml`, `from_name`과 같은 클래스 메서드를 통해 유연하게 설정을 로드할 수 있습니다.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Self

import yaml
from sensai.util import logging
from sensai.util.string import ToStringMixin

from serena.config.serena_config import ToolInclusionDefinition
from serena.constants import (
    DEFAULT_CONTEXT,
    DEFAULT_MODES,
    INTERNAL_MODE_YAMLS_DIR,
    SERENAS_OWN_CONTEXT_YAMLS_DIR,
    SERENAS_OWN_MODE_YAMLS_DIR,
    USER_CONTEXT_YAMLS_DIR,
    USER_MODE_YAMLS_DIR,
)

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


@dataclass(kw_only=True)
class SerenaAgentMode(ToolInclusionDefinition, ToStringMixin):
    """에이전트의 동작 모드를 나타내며, 일반적으로 YAML 파일에서 읽어옵니다.
    에이전트는 상호 배타적이지 않은 한 여러 모드를 동시에 가질 수 있습니다.
    모드는 에이전트 실행 후에도 조정될 수 있으며, 예를 들어 계획 모드에서 편집 모드로 전환할 수 있습니다.
    """

    name: str
    prompt:
    """
    시스템 프롬프트 생성을 위한 Jinja2 템플릿입니다.
    에이전트에 의해 포맷됩니다 (SerenaAgent._format_prompt() 참조).
    """
    description: str = ""

    def _tostring_includes(self) -> list[str]:
        return ["name"]

    def print_overview(self) -> None:
        """모드에 대한 개요를 출력합니다."""
        print(f"{self.name}:\n {self.description}")
        if self.excluded_tools:
            print(" 제외된 도구:\n  " + ", ".join(sorted(self.excluded_tools)))

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> Self:
        """YAML 파일에서 모드를 로드합니다."""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        name = data.pop("name", Path(yaml_path).stem)
        return cls(name=name, **data)

    @classmethod
    def get_path(cls, name: str) -> str:
        """모드의 YAML 파일 경로를 가져옵니다."""
        fname = f"{name}.yml"
        custom_mode_path = os.path.join(USER_MODE_YAMLS_DIR, fname)
        if os.path.exists(custom_mode_path):
            return custom_mode_path

        own_yaml_path = os.path.join(SERENAS_OWN_MODE_YAMLS_DIR, fname)
        if not os.path.exists(own_yaml_path):
            raise FileNotFoundError(
                f"모드 {name}을(를) {USER_MODE_YAMLS_DIR} 또는 {SERENAS_OWN_MODE_YAMLS_DIR}에서 찾을 수 없습니다."
                f"사용 가능한 모드:\n{cls.list_registered_mode_names()}"
            )
        return own_yaml_path

    @classmethod
    def from_name(cls, name: str) -> Self:
        """등록된 Serena 모드를 로드합니다."""
        mode_path = cls.get_path(name)
        return cls.from_yaml(mode_path)

    @classmethod
    def from_name_internal(cls, name: str) -> Self:
        """내부 Serena 모드를 로드합니다."""
        yaml_path = os.path.join(INTERNAL_MODE_YAMLS_DIR, f"{name}.yml")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"내부 모드 '{name}'을(를) {INTERNAL_MODE_YAMLS_DIR}에서 찾을 수 없습니다.")
        return cls.from_yaml(yaml_path)

    @classmethod
    def list_registered_mode_names(cls, include_user_modes: bool = True) -> list[str]:
        """등록된 모든 모드의 이름 (serena 리포지토리의 해당 YAML 파일에서)."""
        modes = [f.stem for f in Path(SERENAS_OWN_MODE_YAMLS_DIR).glob("*.yml") if f.name != "mode.template.yml"]
        if include_user_modes:
            modes += cls.list_custom_mode_names()
        return sorted(set(modes))

    @classmethod
    def list_custom_mode_names(cls) -> list[str]:
        """사용자가 정의한 모든 사용자 정의 모드의 이름."""
        return [f.stem for f in Path(USER_MODE_YAMLS_DIR).glob("*.yml")]

    @classmethod
    def load_default_modes(cls) -> list[Self]:
        """기본 모드(interactive 및 editing)를 로드합니다."""
        return [cls.from_name(mode) for mode in DEFAULT_MODES]

    @classmethod
    def load(cls, name_or_path: str | Path) -> Self:
        if str(name_or_path).endswith(".yml"):
            return cls.from_yaml(name_or_path)
        return cls.from_name(str(name_or_path))


@dataclass(kw_only=True)
class SerenaAgentContext(ToolInclusionDefinition, ToStringMixin):
    """에이전트가 작동하는 컨텍스트(IDE, 채팅 등)를 나타내며, 일반적으로 YAML 파일에서 읽어옵니다.
    에이전트는 한 번에 하나의 컨텍스트에만 있을 수 있습니다.
    컨텍스트는 에이전트 실행 후 변경할 수 없습니다.
    """

    name: str
    prompt:
    """
    시스템 프롬프트 생성을 위한 Jinja2 템플릿입니다.
    에이전트에 의해 포맷됩니다 (SerenaAgent._format_prompt() 참조).
    """
    description: str = ""
    tool_description_overrides: dict[str, str] = field(default_factory=dict)
    """도구 이름을 사용자 정의 설명에 매핑합니다. 기본 설명은 도구의 docstring에서 추출됩니다."""

    def _tostring_includes(self) -> list[str]:
        return ["name"]

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> Self:
        """YAML 파일에서 컨텍스트를 로드합니다."""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        name = data.pop("name", Path(yaml_path).stem)
        # tool_description_overrides에 대한 하위 호환성 보장
        if "tool_description_overrides" not in data:
            data["tool_description_overrides"] = {}
        return cls(name=name, **data)

    @classmethod
    def get_path(cls, name: str) -> str:
        """컨텍스트의 YAML 파일 경로를 가져옵니다."""
        fname = f"{name}.yml"
        custom_context_path = os.path.join(USER_CONTEXT_YAMLS_DIR, fname)
        if os.path.exists(custom_context_path):
            return custom_context_path

        own_yaml_path = os.path.join(SERENAS_OWN_CONTEXT_YAMLS_DIR, fname)
        if not os.path.exists(own_yaml_path):
            raise FileNotFoundError(
                f"컨텍스트 {name}을(를) {USER_CONTEXT_YAMLS_DIR} 또는 {SERENAS_OWN_CONTEXT_YAMLS_DIR}에서 찾을 수 없습니다."
                f"사용 가능한 컨텍스트:\n{cls.list_registered_context_names()}"
            )
        return own_yaml_path

    @classmethod
    def from_name(cls, name: str) -> Self:
        """등록된 Serena 컨텍스트를 로드합니다."""
        context_path = cls.get_path(name)
        return cls.from_yaml(context_path)

    @classmethod
    def load(cls, name_or_path: str | Path) -> Self:
        if str(name_or_path).endswith(".yml"):
            return cls.from_yaml(name_or_path)
        return cls.from_name(str(name_or_path))

    @classmethod
    def list_registered_context_names(cls, include_user_contexts: bool = True) -> list[str]:
        """등록된 모든 컨텍스트의 이름 (serena 리포지토리의 해당 YAML 파일에서)."""
        contexts = [f.stem for f in Path(SERENAS_OWN_CONTEXT_YAMLS_DIR).glob("*.yml")]
        if include_user_contexts:
            contexts += cls.list_custom_context_names()
        return sorted(set(contexts))

    @classmethod
    def list_custom_context_names(cls) -> list[str]:
        """사용자가 정의한 모든 사용자 정의 컨텍스트의 이름."""
        return [f.stem for f in Path(USER_CONTEXT_YAMLS_DIR).glob("*.yml")]

    @classmethod
    def load_default(cls) -> Self:
        """기본 컨텍스트를 로드합니다."""
        return cls.from_name(DEFAULT_CONTEXT)

    def print_overview(self) -> None:
        """모드에 대한 개요를 출력합니다."""
        print(f"{self.name}:\n {self.description}")
        if self.excluded_tools:
            print(" 제외된 도구:\n  " + ", ".join(sorted(self.excluded_tools)))


class RegisteredContext(Enum):
    """등록된 컨텍스트입니다."""

    IDE_ASSISTANT = "ide-assistant"
    """Claude Code, Cline, Cursor 등과 같이 이미 기본 도구가 있는 어시스턴트 내에서 실행되는 Serena용."""
    DESKTOP_APP = "desktop-app"
    """Claude Desktop 또는 코드 편집을 위한 내장 도구가 없는 유사한 앱 내에서 실행되는 Serena용."""
    AGENT = "agent"
    """독립 실행형 에이전트로 실행되는 Serena용 (예: agno를 통해)."""

    def load(self) -> SerenaAgentContext:
        """컨텍스트를 로드합니다."""
        return SerenaAgentContext.from_name(self.value)


class RegisteredMode(Enum):
    """등록된 모드입니다."""

    INTERACTIVE = "interactive"
    """대화형 모드, 다중 턴 상호 작용용."""
    EDITING = "editing"
    """편집 도구가 활성화됩니다."""
    PLANNING = "planning"
    """편집 도구가 비활성화됩니다."""
    ONE_SHOT = "one-shot"
    """비대화형 모드, 자율적으로 작업을 완료하는 것이 목표입니다."""

    def load(self) -> SerenaAgentMode:
        """모드를 로드합니다."""
        return SerenaAgentMode.from_name(self.value)