"""
SerenaMCP Tool System - 도구 시스템 기반 클래스 및 유틸리티

이 모듈은 SerenaMCP의 도구 시스템을 구성하는 핵심 클래스들을 제공합니다:
- Tool: 모든 도구의 베이스 클래스
- ToolMarker: 도구 속성 및 메타데이터를 정의하는 마커 클래스
- ToolRegistry: 도구 자동 발견 및 등록 시스템
- Component: 도구가 공통적으로 사용하는 에이전트 컴포넌트 접근 인터페이스

도구 시스템 아키텍처:
1. ToolRegistry가 모든 Tool 서브클래스를 자동으로 발견
2. 각 Tool은 SerenaAgent와 연결되어 프로젝트, LSP, 메모리 등에 접근
3. ToolMarker를 통해 도구의 특성(편집 가능, 선택적, 심볼 기반 등)을 정의
4. MCP 서버는 Tool의 메타데이터를 통해 도구를 클라이언트에 노출
"""

import inspect
import os
from abc import ABC
from collections.abc import Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Any, Protocol, Self, TypeVar

from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata, func_metadata
from sensai.util import logging
from sensai.util.string import dict_string

from serena.project import Project
from serena.prompt_factory import PromptFactory
from serena.symbol import LanguageServerSymbolRetriever
from serena.util.class_decorators import singleton
from serena.util.inspection import iter_subclasses
from solidlsp.ls_exceptions import SolidLSPException

if TYPE_CHECKING:
    from serena.agent import LinesRead, MemoriesManager, SerenaAgent
    from serena.code_editor import CodeEditor

log = logging.getLogger(__name__)
T = TypeVar("T")
SUCCESS_RESULT = "OK"


class Component(ABC):
    """
    모든 도구 컴포넌트의 공통 베이스 클래스.

    이 클래스는 도구들이 SerenaAgent의 핵심 컴포넌트들에 접근할 수 있도록
    편리한 인터페이스를 제공합니다.

    주요 기능:
    - 프로젝트 루트 경로 접근
    - 프롬프트 팩토리 접근
    - 메모리 관리자 접근
    - 언어 서버 심볼 검색기 생성
    - 코드 편집기 생성
    - 읽기 캐시 접근
    """

    def __init__(self, agent: "SerenaAgent"):
        """
        Component를 초기화합니다.

        Args:
            agent: 연결할 SerenaAgent 인스턴스
        """
        self.agent = agent

    def get_project_root(self) -> str:
        """
        활성 프로젝트의 루트 디렉토리 경로를 반환합니다.

        Returns:
            프로젝트 루트 디렉토리 경로

        Raises:
            ValueError: 활성 프로젝트가 설정되지 않은 경우
        """
        return self.agent.get_project_root()

    @property
    def prompt_factory(self) -> PromptFactory:
        """에이전트의 프롬프트 팩토리를 반환합니다."""
        return self.agent.prompt_factory

    @property
    def memories_manager(self) -> "MemoriesManager":
        """에이전트의 메모리 관리자를 반환합니다."""
        assert self.agent.memories_manager is not None
        return self.agent.memories_manager

    def create_language_server_symbol_retriever(self) -> LanguageServerSymbolRetriever:
        """언어 서버 심볼 검색기를 생성합니다."""
        if not self.agent.is_using_language_server():
            raise Exception("Cannot create LanguageServerSymbolRetriever; agent is not in language server mode.")
        language_server = self.agent.language_server
        assert language_server is not None
        return LanguageServerSymbolRetriever(language_server, agent=self.agent)

    @property
    def project(self) -> Project:
        return self.agent.get_active_project_or_raise()

    def create_code_editor(self) -> "CodeEditor":
        from ..code_editor import JetBrainsCodeEditor, LanguageServerCodeEditor

        if self.agent.is_using_language_server():
            return LanguageServerCodeEditor(self.create_language_server_symbol_retriever(), agent=self.agent)
        else:
            return JetBrainsCodeEditor(project=self.project, agent=self.agent)

    @property
    def lines_read(self) -> "LinesRead":
        assert self.agent.lines_read is not None
        return self.agent.lines_read


class ToolMarker:
    """
    Base class for tool markers.
    """


class ToolMarkerCanEdit(ToolMarker):
    """
    Marker class for all tools that can perform editing operations on files.
    """


class ToolMarkerDoesNotRequireActiveProject(ToolMarker):
    pass


class ToolMarkerOptional(ToolMarker):
    """
    Marker class for optional tools that are disabled by default.
    """


class ToolMarkerSymbolicRead(ToolMarker):
    """
    Marker class for tools that perform symbol read operations.
    """


class ToolMarkerSymbolicEdit(ToolMarkerCanEdit):
    """
    Marker class for tools that perform symbolic edit operations.
    """


class ApplyMethodProtocol(Protocol):
    """Callable protocol for the apply method of a tool."""

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        pass


class Tool(Component):
    """
    모든 SerenaMCP 도구의 베이스 클래스.

    이 클래스는 SerenaMCP의 모든 도구들이 상속받아야 하는 추상 베이스 클래스입니다.
    각 도구는 apply() 메서드를 구현하여 특정 기능을 제공해야 합니다.

    도구의 주요 특징:
    1. apply() 메서드: 도구의 핵심 기능을 구현 (서브클래스에서 구현해야 함)
    2. apply_ex() 메서드: 오류 처리 및 로깅이 포함된 안전한 도구 실행
    3. 메타데이터 자동 추출: apply() 메서드의 타입 힌트와 독스트링을 활용
    4. 자동 도구 발견: ToolRegistry를 통한 자동 등록

    도구 개발 시 주의사항:
    - apply() 메서드는 반드시 구현해야 함
    - apply() 메서드의 독스트링은 LLM이 사용할 도구 설명으로 사용됨
    - 타입 힌트는 도구 호출 인자 검증에 사용됨
    - ToolMarker 클래스들을 상속하여 도구 속성 정의

    Note:
        apply() 메서드는 Tool 인터페이스의 일부로 선언되지 않음.
        각 도구의 시그니처를 미리 알 수 없기 때문.
        대신 apply_ex() 메서드가 중앙에서 apply()를 호출하고
        오류 처리, 로깅, 캐싱 등의 부가 기능을 제공.
    """

    @classmethod
    def get_name_from_cls(cls) -> str:
        name = cls.__name__
        if name.endswith("Tool"):
            name = name[:-4]
        # convert to snake_case
        name = "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")
        return name

    def get_name(self) -> str:
        return self.get_name_from_cls()

    def get_apply_fn(self) -> ApplyMethodProtocol:
        apply_fn = getattr(self, "apply")
        if apply_fn is None:
            raise RuntimeError(f"apply not defined in {self}. Did you forget to implement it?")
        return apply_fn

    @classmethod
    def can_edit(cls) -> bool:
        """
        Returns whether this tool can perform editing operations on code.

        :return: True if the tool can edit code, False otherwise
        """
        return issubclass(cls, ToolMarkerCanEdit)

    @classmethod
    def get_tool_description(cls) -> str:
        docstring = cls.__doc__
        if docstring is None:
            return ""
        return docstring.strip()

    @classmethod
    def get_apply_docstring_from_cls(cls) -> str:
        """Get the docstring for the apply method from the class (static metadata).
        Needed for creating MCP tools in a separate process without running into serialization issues.
        """
        # First try to get from __dict__ to handle dynamic docstring changes
        if "apply" in cls.__dict__:
            apply_fn = cls.__dict__["apply"]
        else:
            # Fall back to getattr for inherited methods
            apply_fn = getattr(cls, "apply", None)
            if apply_fn is None:
                raise AttributeError(f"apply method not defined in {cls}. Did you forget to implement it?")

        docstring = apply_fn.__doc__
        if not docstring:
            raise AttributeError(f"apply method has no (or empty) docstring in {cls}. Did you forget to implement it?")
        return docstring.strip()

    def get_apply_docstring(self) -> str:
        """Gets the docstring for the tool application, used by the MCP server."""
        return self.get_apply_docstring_from_cls()

    def get_apply_fn_metadata(self) -> FuncMetadata:
        """Gets the metadata for the tool application function, used by the MCP server."""
        return self.get_apply_fn_metadata_from_cls()

    @classmethod
    def get_apply_fn_metadata_from_cls(cls) -> FuncMetadata:
        """Get the metadata for the apply method from the class (static metadata).
        Needed for creating MCP tools in a separate process without running into serialization issues.
        """
        # First try to get from __dict__ to handle dynamic docstring changes
        if "apply" in cls.__dict__:
            apply_fn = cls.__dict__["apply"]
        else:
            # Fall back to getattr for inherited methods
            apply_fn = getattr(cls, "apply", None)
            if apply_fn is None:
                raise AttributeError(f"apply method not defined in {cls}. Did you forget to implement it?")

        return func_metadata(apply_fn, skip_names=["self", "cls"])

    def _log_tool_application(self, frame: Any) -> None:
        params = {}
        ignored_params = {"self", "log_call", "catch_exceptions", "args", "apply_fn"}
        for param, value in frame.f_locals.items():
            if param in ignored_params:
                continue
            if param == "kwargs":
                params.update(value)
            else:
                params[param] = value
        log.info(f"{self.get_name_from_cls()}: {dict_string(params)}")

    def _limit_length(self, result: str, max_answer_chars: int) -> str:
        if max_answer_chars == -1:
            max_answer_chars = self.agent.serena_config.default_max_tool_answer_chars
        if max_answer_chars <= 0:
            raise ValueError(f"Must be positive or the default (-1), got: {max_answer_chars=}")
        if (n_chars := len(result)) > max_answer_chars:
            result = (
                f"The answer is too long ({n_chars} characters). "
                + "Please try a more specific tool query or raise the max_answer_chars parameter."
            )
        return result

    def is_active(self) -> bool:
        return self.agent.tool_is_active(self.__class__)

    def apply_ex(self, log_call: bool = True, catch_exceptions: bool = True, **kwargs) -> str:  # type: ignore
        """
        Applies the tool with logging and exception handling, using the given keyword arguments
        """

        def task() -> str:
            apply_fn = self.get_apply_fn()

            try:
                if not self.is_active():
                    return f"Error: Tool '{self.get_name_from_cls()}' is not active. Active tools: {self.agent.get_active_tool_names()}"
            except Exception as e:
                return f"RuntimeError while checking if tool {self.get_name_from_cls()} is active: {e}"

            if log_call:
                self._log_tool_application(inspect.currentframe())
            try:
                # check whether the tool requires an active project and language server
                if not isinstance(self, ToolMarkerDoesNotRequireActiveProject):
                    if self.agent._active_project is None:
                        return (
                            "Error: No active project. Ask to user to select a project from this list: "
                            + f"{self.agent.serena_config.project_names}"
                        )
                    if self.agent.is_using_language_server() and not self.agent.is_language_server_running():
                        log.info("Language server is not running. Starting it ...")
                        self.agent.reset_language_server()

                # apply the actual tool
                try:
                    result = apply_fn(**kwargs)
                except SolidLSPException as e:
                    if e.is_language_server_terminated():
                        log.error(f"Language server terminated while executing tool ({e}). Restarting the language server and retrying ...")
                        self.agent.reset_language_server()
                        result = apply_fn(**kwargs)
                    else:
                        raise

                # record tool usage
                self.agent.record_tool_usage_if_enabled(kwargs, result, self)

            except Exception as e:
                if not catch_exceptions:
                    raise
                msg = f"Error executing tool: {e}"
                log.error(f"Error executing tool: {e}", exc_info=e)
                result = msg

            if log_call:
                log.info(f"Result: {result}")

            try:
                if self.agent.language_server is not None:
                    self.agent.language_server.save_cache()
            except Exception as e:
                log.error(f"Error saving language server cache: {e}")

            return result

        future = self.agent.issue_task(task, name=self.__class__.__name__)
        return future.result(timeout=self.agent.serena_config.tool_timeout)


class EditedFileContext:
    """
    Context manager for file editing.

    Create the context, then use `set_updated_content` to set the new content, the original content
    being provided in `original_content`.
    When exiting the context without an exception, the updated content will be written back to the file.
    """

    def __init__(self, relative_path: str, agent: "SerenaAgent"):
        self._project = agent.get_active_project()
        assert self._project is not None
        self._abs_path = os.path.join(self._project.project_root, relative_path)
        if not os.path.isfile(self._abs_path):
            raise FileNotFoundError(f"File {self._abs_path} does not exist.")
        with open(self._abs_path, encoding=self._project.project_config.encoding) as f:
            self._original_content = f.read()
        self._updated_content: str | None = None

    def __enter__(self) -> Self:
        return self

    def get_original_content(self) -> str:
        """
        :return: the original content of the file before any modifications.
        """
        return self._original_content

    def set_updated_content(self, content: str) -> None:
        """
        Sets the updated content of the file, which will be written back to the file
        when the context is exited without an exception.

        :param content: the updated content of the file
        """
        self._updated_content = content

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        if self._updated_content is not None and exc_type is None:
            assert self._project is not None
            with open(self._abs_path, "w", encoding=self._project.project_config.encoding) as f:
                f.write(self._updated_content)
            log.info(f"Updated content written to {self._abs_path}")
            # Language servers should automatically detect the change and update its state accordingly.
            # If they do not, we may have to add a call to notify it.


@dataclass(kw_only=True)
class RegisteredTool:
    tool_class: type[Tool]
    is_optional: bool
    tool_name: str


@singleton
@singleton
class ToolRegistry:
    """
    SerenaMCP 도구 자동 발견 및 등록 시스템.

    이 클래스는 싱글톤 패턴을 사용하여 모든 Tool 서브클래스를 자동으로 발견하고
    등록하는 역할을 담당합니다. 도구의 메타데이터를 관리하고, 도구 인스턴스화를 담당합니다.

    주요 기능:
    - 도구 클래스 자동 발견 (iter_subclasses 활용)
    - 도구 중복 이름 검증
    - 선택적/필수 도구 분리 관리
    - 도구 인스턴스 생성 및 관리
    - 도구 메타데이터 제공

    도구 발견 과정:
    1. serena.tools 패키지 내의 모든 Tool 서브클래스 검색
    2. ToolMarkerOptional 상속 여부 확인
    3. 도구 이름 중복 검사
    4. RegisteredTool 객체로 등록

    Attributes:
        _tool_dict: 도구 이름 -> RegisteredTool 매핑
    """

    def __init__(self) -> None:
        """ToolRegistry를 초기화하고 모든 도구를 자동으로 등록합니다."""
        self._tool_dict: dict[str, RegisteredTool] = {}

        # 모든 Tool 서브클래스를 자동으로 발견하여 등록
        for cls in iter_subclasses(Tool):
            if not cls.__module__.startswith("serena.tools"):
                continue

            # ToolMarkerOptional 상속 여부 확인
            is_optional = issubclass(cls, ToolMarkerOptional)
            name = cls.get_name_from_cls()

            # 도구 이름 중복 검사
            if name in self._tool_dict:
                raise ValueError(f"Duplicate tool name found: {name}. Tool classes must have unique names.")

            # 도구 등록
            self._tool_dict[name] = RegisteredTool(tool_class=cls, is_optional=is_optional, tool_name=name)

    def get_tool_class_by_name(self, tool_name: str) -> type[Tool]:
        """
        도구 이름을 통해 도구 클래스를 반환합니다.

        Args:
            tool_name: 도구 이름

        Returns:
            도구 클래스
        """
        return self._tool_dict[tool_name].tool_class

    def get_all_tool_classes(self) -> list[type[Tool]]:
        """
        모든 도구 클래스의 리스트를 반환합니다.

        Returns:
            모든 도구 클래스의 리스트
        """
        return list(t.tool_class for t in self._tool_dict.values())

    def get_tool_classes_default_enabled(self) -> list[type[Tool]]:
        """
        기본적으로 활성화된 도구 클래스의 리스트를 반환합니다.

        Returns:
            기본 활성화 도구 클래스의 리스트 (선택적 도구 제외)
        """
        return [t.tool_class for t in self._tool_dict.values() if not t.is_optional]

    def get_tool_classes_optional(self) -> list[type[Tool]]:
        """
        선택적 도구 클래스의 리스트를 반환합니다.

        Returns:
            선택적 도구 클래스의 리스트 (기본적으로 비활성화)
        """
        return [t.tool_class for t in self._tool_dict.values() if t.is_optional]

    def get_tool_names_default_enabled(self) -> list[str]:
        """
        :return: the list of tool names that are enabled by default (i.e. non-optional tools).
        """
        return [t.tool_name for t in self._tool_dict.values() if not t.is_optional]

    def get_tool_names_optional(self) -> list[str]:
        """
        :return: the list of tool names that are optional (i.e. disabled by default).
        """
        return [t.tool_name for t in self._tool_dict.values() if t.is_optional]

    def get_tool_names(self) -> list[str]:
        """
        :return: the list of all tool names.
        """
        return list(self._tool_dict.keys())

    def print_tool_overview(
        self, tools: Iterable[type[Tool] | Tool] | None = None, include_optional: bool = False, only_optional: bool = False
    ) -> None:
        """
        Print a summary of the tools. If no tools are passed, a summary of the selection of tools (all, default or only optional) is printed.
        """
        if tools is None:
            if only_optional:
                tools = self.get_tool_classes_optional()
            elif include_optional:
                tools = self.get_all_tool_classes()
            else:
                tools = self.get_tool_classes_default_enabled()

        tool_dict: dict[str, type[Tool] | Tool] = {}
        for tool_class in tools:
            tool_dict[tool_class.get_name_from_cls()] = tool_class
        for tool_name in sorted(tool_dict.keys()):
            tool_class = tool_dict[tool_name]
            print(f" * `{tool_name}`: {tool_class.get_tool_description().strip()}")

    def is_valid_tool_name(self, tool_name: str) -> bool:
        return tool_name in self._tool_dict
